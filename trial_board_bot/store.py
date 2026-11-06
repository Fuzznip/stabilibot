"""Transactional trial workflow. All times are UTC epoch seconds.

Discord delivery is an outbox: uncertain sends require reconciliation, not retries.
This module deliberately knows nothing about clan admission/rank requirements.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class RuleError(ValueError):
    pass


def parse_windows(text, zone, now=None):
    """One `YYYY-MM-DD HH:MM / YYYY-MM-DD HH:MM` window per line.

An explicit UTC offset can disambiguate fall-back times. Reject spring gaps.
"""
    now = int(time.time()) if now is None else now
    try:
        tz = ZoneInfo(zone.strip())
    except ZoneInfoNotFoundError:
        raise RuleError("Use an IANA timezone, e.g. America/New_York or Europe/London.")

    def instant(value):
        try:
            dt = datetime.fromisoformat(value.strip())
        except ValueError:
            raise RuleError("Use YYYY-MM-DD HH:MM / YYYY-MM-DD HH:MM, one window per line.")
        if dt.tzinfo:
            local = dt.astimezone(tz)
            if local.replace(tzinfo=None) != dt.replace(tzinfo=None):
                raise RuleError("That UTC offset does not match the named timezone.")
            return int(dt.timestamp())
        candidates = set()
        for fold in (0, 1):
            aware = dt.replace(tzinfo=tz, fold=fold)
            if aware.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None) == dt:
                candidates.add(int(aware.timestamp()))
        if len(candidates) != 1:
            raise RuleError("That local time is ambiguous or does not exist (DST). Include its UTC offset.")
        return candidates.pop()

    result = []
    for line in text.strip().splitlines():
        parts = line.split(" / ")
        if len(parts) != 2:
            raise RuleError("Separate start and end with ' / '.")
        start, end = map(instant, parts)
        if not now + 300 <= start < end <= now + 21 * 86400:
            raise RuleError("Choose future windows at least 5 minutes away and within the next 21 days.")
        if end - start > 12 * 3600:
            raise RuleError("Each window must be at most 12 hours.")
        result.append([start, end])
    if not 1 <= len(result) <= 5:
        raise RuleError("Provide 1–5 windows (2–3 is ideal).")
    result.sort()
    if any(a[1] > b[0] for a, b in zip(result, result[1:])):
        raise RuleError("Availability windows must not overlap.")
    return result


class Store:
    def __init__(self, path, clock=time.time, shared_pool=True):
        self.path, self.clock, self.shared_pool = str(path), clock, shared_pool
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
            INSERT OR IGNORE INTO settings VALUES('paused','1');
            CREATE TABLE IF NOT EXISTS volunteers(
              user_id INTEGER PRIMARY KEY, board TEXT NOT NULL, approved INTEGER NOT NULL DEFAULT 1,
              active INTEGER NOT NULL DEFAULT 0, capacity INTEGER NOT NULL DEFAULT 2,
              windows TEXT NOT NULL DEFAULT '[]', zone TEXT NOT NULL DEFAULT 'UTC', offered INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS trials(
              id INTEGER PRIMARY KEY, applicant INTEGER NOT NULL, channel INTEGER NOT NULL,
              board TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'availability',
              windows TEXT NOT NULL DEFAULT '[]', zone TEXT NOT NULL DEFAULT 'UTC',
              duration INTEGER NOT NULL, owner INTEGER, start INTEGER, end INTEGER,
              created INTEGER NOT NULL, deadline INTEGER NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
              card INTEGER, outcome TEXT, proposal_expires INTEGER);
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_trial ON trials(applicant)
              WHERE status NOT IN ('closed','cancelled');
            CREATE TABLE IF NOT EXISTS feedback(
              id INTEGER PRIMARY KEY, trial INTEGER NOT NULL, author INTEGER NOT NULL,
              recommendation TEXT NOT NULL, notes TEXT NOT NULL, created INTEGER NOT NULL,
              UNIQUE(trial,author));
            CREATE TABLE IF NOT EXISTS jobs(
              id INTEGER PRIMARY KEY, dedupe TEXT UNIQUE NOT NULL, trial INTEGER NOT NULL,
              revision INTEGER NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending', message INTEGER, channel INTEGER,
              created INTEGER NOT NULL, error TEXT);
            CREATE TABLE IF NOT EXISTS audit(
              id INTEGER PRIMARY KEY, actor INTEGER, action TEXT, trial INTEGER, created INTEGER);
            CREATE TABLE IF NOT EXISTS leases(name TEXT PRIMARY KEY,owner TEXT,expires INTEGER);
            CREATE TABLE IF NOT EXISTS external_requests(
              request_key TEXT PRIMARY KEY, applicant INTEGER NOT NULL, channel INTEGER NOT NULL,
              board TEXT NOT NULL, duration INTEGER NOT NULL, trial INTEGER NOT NULL);
            """)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def tx(self):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def now(self):
        return int(self.clock())

    def paused(self):
        with self.db() as db:
            return db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0] == '1'

    def pause(self, value, actor):
        with self.tx() as db:
            db.execute("UPDATE settings SET value=? WHERE key='paused'", ('1' if value else '0',))
            self.audit(db, actor, 'pause' if value else 'resume', None)

    def audit(self, db, actor, action, trial):
        db.execute("INSERT INTO audit(actor,action,trial,created) VALUES(?,?,?,?)",
                   (actor, action, trial, self.now()))

    def require_running(self, db):
        if db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0] == '1':
            raise RuleError("Trial workflow is paused. Ask staff to review /board status.")

    def volunteer(self, user):
        with self.db() as db:
            row = db.execute("SELECT * FROM volunteers WHERE user_id=?", (user,)).fetchone()
            return dict(row) if row else None

    def approve(self, user, board, capacity, actor):
        if board not in ('normal', 'efficient') or not 1 <= capacity <= 5:
            raise RuleError("Choose normal/efficient and a capacity of 1–5.")
        with self.tx() as db:
            db.execute("""INSERT INTO volunteers(user_id,board,capacity) VALUES(?,?,?)
              ON CONFLICT(user_id) DO UPDATE SET board=excluded.board,capacity=excluded.capacity,
              approved=1""", (user, board, capacity))
            self.audit(db, actor, 'approve_volunteer', None)

    def disable(self, user, actor):
        with self.tx() as db:
            db.execute("UPDATE volunteers SET approved=0,active=0 WHERE user_id=?", (user,))
            self.audit(db, actor, 'disable_volunteer', None)

    def availability(self, user, windows, zone, active):
        with self.tx() as db:
            row = db.execute("SELECT * FROM volunteers WHERE user_id=? AND approved=1", (user,)).fetchone()
            if not row:
                raise RuleError("Staff must approve you for the volunteer pool first.")
            db.execute("UPDATE volunteers SET windows=?,zone=?,active=? WHERE user_id=?",
                       (json.dumps(windows), zone, int(active), user))
            self.audit(db, user, 'volunteer_availability', None)

    def enqueue(self, db, t, kind, data=None, suffix=''):
        db.execute("""INSERT OR IGNORE INTO jobs(dedupe,trial,revision,kind,data,created)
                      VALUES(?,?,?,?,?,?)""",
                   (f"{t['id']}:{t['revision']}:{kind}:{suffix}", t['id'], t['revision'],
                    kind, json.dumps(data or {}), self.now()))

    def row(self, db, trial):
        row = db.execute("SELECT * FROM trials WHERE id=?", (trial,)).fetchone()
        if not row:
            raise RuleError("Trial not found.")
        return dict(row)

    def get(self, trial):
        with self.db() as db:
            return self.row(db, trial)

    def list(self, active=True):
        with self.db() as db:
            sql = "SELECT * FROM trials"
            if active:
                sql += " WHERE status NOT IN ('closed','cancelled')"
            return [dict(r) for r in db.execute(sql + " ORDER BY id DESC")]

    def changed(self, db, trial):
        db.execute("UPDATE trials SET revision=revision+1 WHERE id=?", (trial,))
        t = self.row(db, trial)
        self.enqueue(db, t, 'card')
        return t

    def create(self, applicant, channel, board, duration, days, actor, external_key=None):
        if board not in ('normal', 'efficient') or not 30 <= duration <= 240 or not 1 <= days <= 30:
            raise RuleError("Use normal/efficient, 30–240 minutes, and a 1–30 day trial window.")
        with self.tx() as db:
            self.require_running(db)
            if external_key is not None:
                if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}',external_key):
                    raise RuleError('Use a stable application ID as the request key (1–100 simple characters).')
                previous=db.execute('SELECT * FROM external_requests WHERE request_key=?',(external_key,)).fetchone()
                if previous:
                    if (previous['applicant'],previous['channel'],previous['board'],previous['duration']) != (applicant,channel,board,duration):
                        raise RuleError('This application request ID was already used with different details.')
                    result=self.row(db,previous['trial'])
                    result['replayed']=True
                    return result
            try:
                cur = db.execute("""INSERT INTO trials(applicant,channel,board,duration,created,deadline)
                  VALUES(?,?,?,?,?,?)""", (applicant, channel, board, duration * 60,
                                           self.now(), self.now() + days * 86400))
            except sqlite3.IntegrityError:
                raise RuleError("This applicant already has an open trial. Use /trial status.")
            t = self.row(db, cur.lastrowid)
            if external_key is not None:
                db.execute('INSERT INTO external_requests VALUES(?,?,?,?,?,?)',
                           (external_key,applicant,channel,board,duration,t['id']))
            self.enqueue(db, t, 'card')
            self.enqueue(db, t, 'application', {'event': 'availability'})
            self.audit(db, actor, 'start', t['id'])
            t['replayed']=False
            return t

    def applicant_availability(self, trial, user, windows, zone):
        with self.tx() as db:
            self.require_running(db)
            t = self.row(db, trial)
            if user != t['applicant'] or t['status'] not in ('availability', 'open'):
                raise RuleError("Only this applicant can edit availability on an unbooked trial.")
            if not windows or any(e - s < t['duration'] or e > t['deadline'] for s, e in windows):
                raise RuleError("Each window must fit the session and end before your trial deadline.")
            db.execute("UPDATE trials SET windows=?,zone=?,status='open' WHERE id=?",
                       (json.dumps(windows), zone, trial))
            self.changed(db, trial)
            self.audit(db, user, 'applicant_availability', trial)

    def load(self, db, user):
        return db.execute("SELECT COUNT(*) FROM trials WHERE owner=? AND status IN ('proposed','booked','review')",
                          (user,)).fetchone()[0]

    def slots(self, db, t, user):
        v = db.execute("SELECT * FROM volunteers WHERE user_id=? AND approved=1 AND active=1", (user,)).fetchone()
        if not v or user == t['applicant'] or self.load(db, user) >= v['capacity']:
            return []
        if not self.shared_pool and t['board'] == 'efficient' and v['board'] != 'efficient':
            return []
        conflicts = db.execute("SELECT start,end FROM trials WHERE (owner=? OR applicant=?) AND status IN ('proposed','booked')",
                               (user, user)).fetchall()
        conflicts += db.execute("SELECT start,end FROM trials WHERE (owner=? OR applicant=?) AND status IN ('proposed','booked') AND id!=?",
                                (t['applicant'], t['applicant'], t['id'])).fetchall()
        result = set()
        for a, b in json.loads(t['windows']):
            for c, d in json.loads(v['windows']):
                start, end = max(a, c, self.now() + 300), min(b, d, t['deadline'])
                start = ((start + 899) // 900) * 900
                while start + t['duration'] <= end:
                    finish = start + t['duration']
                    if not any(start < r['end'] and finish > r['start'] for r in conflicts):
                        result.add((start, finish))
                    start += 1800
        return sorted(result)[:25]

    def available_slots(self, trial, user):
        with self.db() as db:
            t = self.row(db, trial)
            return self.slots(db, t, user) if t['status'] == 'open' else []

    def propose(self, trial, user, start, revision):
        with self.tx() as db:
            self.require_running(db)
            t = self.row(db, trial)
            if t['status'] != 'open' or t['revision'] != revision:
                raise RuleError("This trial changed. Open its latest card and choose again.")
            slots = self.slots(db, t, user)
            chosen = next((s for s in slots if s[0] == start), None)
            if not chosen:
                raise RuleError("That slot is no longer available. Refresh the trial card.")
            expires = min(self.now() + 86400, start - 300)
            db.execute("UPDATE trials SET owner=?,start=?,end=?,proposal_expires=?,status='proposed' WHERE id=?",
                       (user, *chosen, expires, trial))
            t = self.changed(db, trial)
            self.enqueue(db, t, 'application', {'event': 'confirm'})
            self.enqueue(db, t, 'owner', {'event': 'waiting'})
            self.audit(db, user, 'propose', trial)
            return t

    def confirm(self, trial, user, revision):
        with self.tx() as db:
            self.require_running(db)
            t = self.row(db, trial)
            if user != t['applicant'] or t['status'] != 'proposed' or revision != t['revision']:
                raise RuleError("Only the applicant can confirm the current proposal.")
            v = db.execute("SELECT * FROM volunteers WHERE user_id=? AND approved=1 AND active=1", (t['owner'],)).fetchone()
            if not v or t['proposal_expires'] <= self.now():
                raise RuleError("The proposal expired or the volunteer is unavailable. Ask staff to reopen it.")
            db.execute("UPDATE trials SET status='booked' WHERE id=?", (trial,))
            t = self.changed(db, trial)
            self.enqueue(db, t, 'application', {'event': 'booked'})
            self.enqueue(db, t, 'owner', {'event': 'booked'})
            self.audit(db, user, 'confirm', trial)
            return t

    def reopen(self, trial, user, staff=False, revision=None):
        with self.tx() as db:
            self.require_running(db)
            t = self.row(db, trial)
            if not staff and user not in (t['applicant'], t['owner']):
                raise RuleError("Only the applicant, assigned volunteer or staff can reschedule.")
            if t['status'] in ('closed','cancelled') or (revision is not None and revision != t['revision']):
                raise RuleError("This trial changed or is closed. Refresh its status.")
            previous_owner = t['owner']
            db.execute("UPDATE trials SET owner=NULL,start=NULL,end=NULL,proposal_expires=NULL,status='availability',windows='[]' WHERE id=?", (trial,))
            t = self.changed(db, trial)
            self.enqueue(db, t, 'application', {'event': 'availability'})
            if previous_owner:
                self.enqueue(db, t, 'owner', {'event':'rescheduled','user':previous_owner})
            self.audit(db, user, 'reopen', trial)

    def feedback(self, trial, user, recommendation, notes):
        if recommendation not in ('recommend','more_time','concern') or not 5 <= len(notes.strip()) <= 1800:
            raise RuleError("Choose recommend/more_time/concern and write 5–1800 characters.")
        with self.tx() as db:
            self.require_running(db)
            t = self.row(db, trial)
            v = db.execute("SELECT approved FROM volunteers WHERE user_id=?", (user,)).fetchone()
            if user != t['owner'] or not v or not v[0] or t['status'] not in ('booked','review') or self.now() < t['start']:
                raise RuleError("Only the approved assigned volunteer can submit feedback after the session starts.")
            try:
                cur = db.execute("INSERT INTO feedback(trial,author,recommendation,notes,created) VALUES(?,?,?,?,?)",
                                 (trial,user,recommendation,notes.strip(),self.now()))
            except sqlite3.IntegrityError:
                raise RuleError("Feedback already submitted. Ask staff if a correction is needed.")
            db.execute("UPDATE trials SET status='review' WHERE id=?", (trial,))
            t = self.changed(db, trial)
            self.enqueue(db, t, 'feedback', {'feedback':cur.lastrowid})
            self.audit(db, user, 'feedback', trial)

    def close(self, trial, actor, outcome):
        if outcome not in ('accepted','declined','withdrawn'):
            raise RuleError("Choose accepted, declined or withdrawn.")
        with self.tx() as db:
            self.require_running(db)
            t = self.row(db, trial)
            if t['status'] in ('closed','cancelled'):
                raise RuleError("Trial is already closed.")
            db.execute("UPDATE trials SET status='closed',outcome=? WHERE id=?", (outcome,trial))
            t = self.changed(db, trial)
            self.enqueue(db, t, 'staff', {'event':'closed'})
            self.audit(db, actor, 'close:' + outcome, trial)

    def tick(self, offer_limit=3):
        with self.tx() as db:
            if db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0] == '1':
                return
            now = self.now()
            for row in db.execute("SELECT * FROM trials WHERE status NOT IN ('closed','cancelled')").fetchall():
                t = dict(row)
                if t['status'] == 'proposed' and t['proposal_expires'] <= now:
                    db.execute("UPDATE trials SET status='open',owner=NULL,start=NULL,end=NULL WHERE id=?", (t['id'],))
                    t = self.changed(db, t['id'])
                    self.enqueue(db,t,'application',{'event':'expired'})
                if now >= t['deadline']:
                    self.enqueue(db,t,'staff',{'event':'deadline'})
                    continue
                if t['status'] == 'open':
                    eligible = []
                    for v in db.execute("SELECT * FROM volunteers WHERE approved=1 AND active=1").fetchall():
                        if self.slots(db,t,v['user_id']):
                            eligible.append((self.load(db,v['user_id']),v['offered'],v['user_id']))
                    offered = [v[2] for v in sorted(eligible)[:offer_limit]]
                    if offered:
                        self.enqueue(db,t,'offer',{'users':offered})
                    if now - t['created'] >= 86400:
                        self.enqueue(db,t,'staff',{'event':'unclaimed'})
                if t['status'] == 'availability' and now - t['created'] >= 86400:
                    self.enqueue(db,t,'staff',{'event':'availability_missing'})
                if t['status'] == 'booked':
                    for label, before in [('day',86400),('hour',3600)]:
                        upper = t['start'] - 3600 if label == 'day' else t['start']
                        if t['start'] - before <= now < upper:
                            self.enqueue(db,t,'reminder',{'event':label},label)
                            self.enqueue(db,t,'owner',{'event':'reminder'},label)
                    if now >= t['end'] + 3600:
                        self.enqueue(db,t,'staff',{'event':'feedback_due'})

    def acquire_worker(self, owner):
        with self.tx() as db:
            row = db.execute("SELECT * FROM leases WHERE name='dispatcher'").fetchone()
            if row and row['owner'] != owner and row['expires'] > self.now():
                return False
            # A dead process could have sent a message before recording its receipt.
            if row is None or row['owner'] != owner:
                db.execute("UPDATE jobs SET status='uncertain',error='Worker stopped during delivery' WHERE status='sending'")
            db.execute("INSERT INTO leases VALUES('dispatcher',?,?) ON CONFLICT(name) DO UPDATE SET owner=excluded.owner,expires=excluded.expires",
                       (owner,self.now()+300))
            return True

    def next_job(self):
        with self.tx() as db:
            if db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0] == '1':
                return None
            # Hold later deliveries for a trial with an unresolved send.
            rows = db.execute("""SELECT * FROM jobs WHERE status='pending' AND trial NOT IN
              (SELECT trial FROM jobs WHERE status IN ('sending','uncertain','failed')) ORDER BY id""").fetchall()
            for row in rows:
                job = dict(row)
                t = self.row(db,job['trial'])
                if job['kind'] != 'feedback' and job['revision'] != t['revision']:
                    db.execute("UPDATE jobs SET status='cancelled' WHERE id=?", (job['id'],))
                    continue
                data = json.loads(job['data'])
                is_reminder = job['kind'] == 'reminder' or (job['kind'] == 'owner' and data.get('event') == 'reminder')
                expired_request = job['kind'] in ('offer','application') and self.now() >= t['deadline']
                if (is_reminder and (not t['start'] or self.now() >= t['start'])) or expired_request:
                    db.execute("UPDATE jobs SET status='cancelled' WHERE id=?", (job['id'],))
                    continue
                db.execute("UPDATE jobs SET status='sending' WHERE id=?", (job['id'],))
                return job
            return None

    def finish_job(self, job, status, message=None, channel=None, error=None):
        with self.tx() as db:
            db.execute("UPDATE jobs SET status=?,message=?,channel=?,error=? WHERE id=?",
                       (status,message,channel,error,job['id']))
            if status == 'sent' and job['kind'] == 'card':
                db.execute("UPDATE trials SET card=? WHERE id=?", (message,job['trial']))
            if status == 'sent' and job['kind'] == 'offer':
                for user in json.loads(job['data'])['users']:
                    db.execute("UPDATE volunteers SET offered=? WHERE user_id=?", (self.now(),user))

    def job(self, job_id):
        with self.db() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise RuleError("Delivery not found.")
            return dict(row)

    def issues(self):
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT id,trial,kind,status FROM jobs WHERE status IN ('uncertain','failed') ORDER BY id")]

    def feedback_record(self, ident):
        with self.db() as db:
            return dict(db.execute("SELECT * FROM feedback WHERE id=?", (ident,)).fetchone())
