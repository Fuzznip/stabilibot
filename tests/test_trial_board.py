"""Offline workflow tests: no Discord login, token, messages or private clan data."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import threading
import unittest

from trial_board_bot.store import RuleError, Store, parse_windows


class TrialBoardTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'work/test-runs'
        root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root)
        self.path=Path(self.temp.name)/'trials.sqlite3'
        self.now=int(datetime(2026,11,4,12,tzinfo=timezone.utc).timestamp())
        self.s=Store(self.path,clock=lambda:self.now)
        self.s.pause(False,99)
        self.start=self.now+2*86400
        self.windows=[[self.start,self.start+4*3600]]
        for user in (10,11):
            self.s.approve(user,'normal',2,99)
            self.s.availability(user,self.windows,'UTC',True)

    def tearDown(self):
        self.temp.cleanup()

    def trial(self,applicant=1,board='normal'):
        t=self.s.create(applicant,100+applicant,board,60,14,99)
        self.s.applicant_availability(t['id'],applicant,self.windows,'UTC')
        return self.s.get(t['id'])

    def booked(self,applicant=1,owner=10):
        t=self.trial(applicant)
        t=self.s.propose(t['id'],owner,self.start,t['revision'])
        return self.s.confirm(t['id'],applicant,t['revision'])

    def drain(self):
        jobs=[]
        while (job:=self.s.next_job()) is not None:
            jobs.append(job)
            self.s.finish_job(job,'sent',job['id']+1000,555)
        return jobs

    def test_end_to_end_confirm_feedback_staff_close(self):
        t=self.booked()
        self.now=self.start+3600
        self.s.feedback(t['id'],10,'recommend','Listened and joined the group well.')
        self.assertEqual(self.s.get(t['id'])['status'],'review')
        self.s.close(t['id'],99,'accepted')
        t=self.s.get(t['id'])
        self.assertEqual((t['status'],t['outcome']),('closed','accepted'))
        self.assertTrue(any(j['kind']=='feedback' for j in self.drain()))

    def test_default_paused_and_resume_persists(self):
        self.s.pause(True,99)
        with self.assertRaises(RuleError): self.trial()
        self.assertTrue(Store(self.path).paused())

    def test_duplicate_active_applicant_rejected_but_can_reapply_after_close(self):
        t=self.trial()
        with self.assertRaises(RuleError): self.trial()
        self.s.close(t['id'],99,'withdrawn')
        self.assertNotEqual(t['id'],self.trial()['id'])

    def test_concurrent_website_retries_create_only_one_trial_and_notice_set(self):
        barrier=threading.Barrier(2)
        def handoff():
            barrier.wait()
            return self.s.create(1,101,'normal',60,14,0,external_key='application:123')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda unused:handoff(),range(2)))
        self.assertEqual(len({t['id'] for t in results}),1)
        self.assertEqual(sorted(t['replayed'] for t in results),[False,True])
        self.assertEqual(len(self.s.list()),1)
        self.assertEqual(sorted(j['kind'] for j in self.drain()),['application','card'])

    def test_approval_does_not_opt_in(self):
        self.s.approve(12,'normal',1,99)
        self.assertFalse(self.s.volunteer(12)['active'])
        self.assertFalse(self.s.available_slots(self.trial()['id'],12))

    def test_shared_pool_and_future_split(self):
        t=self.trial(board='efficient')
        self.assertTrue(self.s.available_slots(t['id'],10))
        split=Store(self.path,clock=lambda:self.now,shared_pool=False)
        self.assertFalse(split.available_slots(t['id'],10))
        split.approve(10,'efficient',2,99)
        self.assertTrue(split.available_slots(t['id'],10))

    def test_matching_requires_overlap_and_capacity(self):
        t=self.trial()
        self.s.availability(10,[[self.start+86400,self.start+90000]],'UTC',True)
        self.assertFalse(self.s.available_slots(t['id'],10))
        self.s.approve(11,'normal',1,99)
        self.booked(2,11)
        self.assertFalse(self.s.available_slots(t['id'],11))

    def test_conflicting_volunteer_bookings_rejected(self):
        self.booked()
        t=self.trial(2)
        with self.assertRaises(RuleError): self.s.propose(t['id'],10,self.start,t['revision'])
        self.assertTrue(all(s>=self.start+3600 for s,e in self.s.available_slots(t['id'],10)))

    def test_no_self_trial(self):
        t=self.trial(10)
        self.assertFalse(self.s.available_slots(t['id'],10))

    def test_simultaneous_claim_has_one_winner(self):
        t=self.trial()
        barrier=threading.Barrier(2)
        def claim(user):
            store=Store(self.path,clock=lambda:self.now)
            barrier.wait()
            try:
                store.propose(t['id'],user,self.start,t['revision'])
                return True
            except RuleError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(claim,[10,11])),1)

    def test_only_applicant_can_confirm_current_proposal(self):
        t=self.trial()
        offered=self.s.propose(t['id'],10,self.start,t['revision'])
        with self.assertRaises(RuleError): self.s.confirm(t['id'],11,offered['revision'])
        with self.assertRaises(RuleError): self.s.confirm(t['id'],1,t['revision'])
        self.assertEqual(self.s.confirm(t['id'],1,offered['revision'])['status'],'booked')

    def test_stale_slot_after_availability_edit(self):
        t=self.trial()
        self.s.applicant_availability(t['id'],1,self.windows,'UTC')
        with self.assertRaises(RuleError): self.s.propose(t['id'],10,self.start,t['revision'])

    def test_disabled_volunteer_cannot_confirm_or_submit_feedback(self):
        t=self.trial()
        t=self.s.propose(t['id'],10,self.start,t['revision'])
        self.s.disable(10,99)
        with self.assertRaises(RuleError): self.s.confirm(t['id'],1,t['revision'])
        self.s.approve(10,'normal',2,99)
        self.s.availability(10,self.windows,'UTC',True)
        t=self.s.confirm(t['id'],1,t['revision'])
        self.s.disable(10,99)
        self.now=self.start
        with self.assertRaises(RuleError): self.s.feedback(t['id'],10,'recommend','Example feedback.')

    def test_proposals_expire_and_release_capacity(self):
        t=self.trial()
        t=self.s.propose(t['id'],10,self.start,t['revision'])
        self.now=t['proposal_expires']
        self.s.tick()
        t=self.s.get(t['id'])
        self.assertEqual((t['status'],t['owner']),('open',None))

    def test_feedback_requires_owner_and_session_start_and_no_duplicates(self):
        t=self.booked()
        with self.assertRaises(RuleError): self.s.feedback(t['id'],10,'recommend','Too early still.')
        self.now=self.start
        with self.assertRaises(RuleError): self.s.feedback(t['id'],11,'recommend','Wrong volunteer.')
        self.s.feedback(t['id'],10,'more_time','Would like another session.')
        with self.assertRaises(RuleError): self.s.feedback(t['id'],10,'recommend','Duplicate feedback.')

    def test_reschedule_cancels_old_notifications_and_releases_owner(self):
        t=self.booked()
        self.s.reopen(t['id'],1,revision=t['revision'])
        t=self.s.get(t['id'])
        self.assertEqual((t['status'],t['owner']),('availability',None))
        jobs=self.drain()
        self.assertFalse(any(json.loads(j['data']).get('event')=='booked' for j in jobs))
        self.assertTrue(any(json.loads(j['data']).get('event')=='availability' for j in jobs))

    def test_outbox_uncertain_blocks_only_its_trial(self):
        a,b=self.trial(),self.trial(2)
        job=self.s.next_job()
        self.s.finish_job(job,'uncertain',error='Simulated timeout')
        rest=self.drain()
        self.assertTrue(rest)
        self.assertTrue(all(j['trial']!=job['trial'] for j in rest))
        self.assertEqual(len(self.s.issues()),1)

    def test_restart_preserves_booking_and_marks_inflight_uncertain(self):
        t=self.booked()
        self.s.acquire_worker('first')
        job=self.s.next_job()
        self.now+=301
        restarted=Store(self.path,clock=lambda:self.now)
        self.assertTrue(restarted.acquire_worker('second'))
        self.assertEqual(restarted.get(t['id'])['status'],'booked')
        self.assertEqual(restarted.job(job['id'])['status'],'uncertain')

    def test_worker_lease_prevents_competing_dispatcher(self):
        self.assertTrue(self.s.acquire_worker('first'))
        self.assertFalse(self.s.acquire_worker('second'))
        self.assertTrue(self.s.acquire_worker('first'))

    def test_offers_limit_and_repeat_ticks_do_not_duplicate(self):
        self.trial()
        self.s.tick(1)
        self.s.tick(1)
        offers=[j for j in self.drain() if j['kind']=='offer']
        self.assertEqual(len(offers),1)
        self.assertEqual(len(json.loads(offers[0]['data'])['users']),1)

    def test_deadline_alert_does_not_admit_or_reject(self):
        t=self.trial()
        self.now=t['deadline']+1
        self.s.tick()
        self.assertEqual(self.s.get(t['id'])['status'],'open')
        self.assertTrue(any(json.loads(j['data']).get('event')=='deadline' for j in self.drain()))

    def test_pending_delivery_does_not_run_while_paused(self):
        self.trial()
        self.s.pause(True,99)
        self.assertIsNone(self.s.next_job())

    def test_both_sides_have_separate_confirmation_and_reminder_jobs(self):
        t=self.booked()
        jobs=self.drain()
        self.assertTrue(any(j['kind']=='application' and json.loads(j['data'])['event']=='booked' for j in jobs))
        self.assertTrue(any(j['kind']=='owner' and json.loads(j['data'])['event']=='booked' for j in jobs))
        self.now=t['start']-1800
        self.s.tick()
        jobs=self.drain()
        self.assertEqual(sum(j['kind']=='reminder' for j in jobs),1)
        self.assertTrue(any(j['kind']=='owner' and json.loads(j['data'])['event']=='reminder' for j in jobs))
        self.s.tick()
        self.assertFalse(self.drain())

    def test_applicant_cannot_be_double_booked_as_a_volunteer(self):
        t=self.booked(applicant=10,owner=11)
        other=self.trial(2)
        with self.assertRaises(RuleError): self.s.propose(other['id'],10,self.start,other['revision'])

    def test_reschedule_notifies_previous_owner(self):
        t=self.booked()
        self.drain()
        self.s.reopen(t['id'],1,revision=t['revision'])
        jobs=self.drain()
        owner=[j for j in jobs if j['kind']=='owner']
        self.assertEqual(len(owner),1)
        self.assertEqual(json.loads(owner[0]['data']),{'event':'rescheduled','user':10})

    def test_late_restart_does_not_send_stale_reminders(self):
        t=self.booked()
        self.drain()
        self.now=t['start']-1800
        self.s.tick()
        self.now=t['end']+3600
        jobs=self.drain()
        self.assertFalse(any(j['kind']=='reminder' or json.loads(j['data']).get('event')=='reminder' for j in jobs))

    def test_dst_gap_and_overlap_rejected_without_offset(self):
        base=int(datetime(2026,3,1,tzinfo=timezone.utc).timestamp())
        with self.assertRaises(RuleError):
            parse_windows('2026-03-08 02:30 / 2026-03-08 04:30','America/New_York',base)
        base=int(datetime(2026,10,20,tzinfo=timezone.utc).timestamp())
        with self.assertRaises(RuleError):
            parse_windows('2026-11-01 01:30 / 2026-11-01 03:30','America/New_York',base)
        result=parse_windows('2026-11-01 01:30-04:00 / 2026-11-01 03:30-05:00','America/New_York',base)
        self.assertEqual(result[0][1]-result[0][0],3*3600)

    def test_invalid_timezone_and_past_windows_rejected(self):
        with self.assertRaises(RuleError): parse_windows('2026-11-06 12:00 / 2026-11-06 14:00','Mars/Olympus',self.now)
        with self.assertRaises(RuleError): parse_windows('2026-11-03 12:00 / 2026-11-03 14:00','UTC',self.now)
        result=parse_windows('2026-11-06 12:00 / 2026-11-06 14:00','UTC',self.now)
        self.assertEqual(result[0],[self.start,self.start+7200])


if __name__=='__main__':
    unittest.main()
