# Trial coordination in Stabilibot

Prepared November 4, 2026 against upstream commit
`f61481998cd11bec3cd425de3ae854af279fa649`. This update has not been deployed.
It uses Stabilibot's existing Pycord 2.7.1, bot account, `TOKEN`, `GUILD_ID`
and FastAPI server. No new production dependencies or Discord application are needed.

The feature is disabled by default. Existing commands, event handlers, intents,
API routes and scheduled jobs remain in place. Loading the trial cog adds only
`/trial` and `/board`. A configuration failure skips the cog; a channel-access
failure pauses its workflow without shutting down the rest of Stabilibot.

## Workflow

1. Staff grant the private volunteer role and run `/board approve` for volunteers.
   Volunteers opt in through `/board availability`, supplying dated windows and
   a timezone. Approval alone never opts someone in; `/board away` stops new offers.
2. Staff start a trial with `/trial start`, selecting an applicant and their
   existing private application channel. Alternatively the website backend can
   explicitly hand off an accepted application through the API described below.
3. The applicant supplies 2–3 availability windows using a button in their channel.
4. The bot offers it to up to three available volunteers, favouring lower current
   workload and people offered trials less recently. Approved volunteers can also
   claim compatible times from the private queue.
5. A volunteer proposes a time; the applicant confirms it. Conflicting bookings
   and volunteer capacity are enforced transactionally. Unconfirmed reservations
   expire within 24 hours or five minutes before the session, whichever is sooner.
6. The bot confirms and reminds each participant in their respective channels.
   They arrange the actual game/voice group themselves.
7. The assigned volunteer supplies feedback after the scheduled start. Feedback
   (`recommend`, `more_time`, `concern` plus a note) goes to staff only.
8. Staff record an outcome through `/trial close`. No Discord roles, ranks or
   membership are changed automatically.

`shared_pool=true` uses one general volunteer pool for normal and efficient trials.
These are general categories, with no raid-specific qualifications. Separate routing
can be enabled later: efficient volunteers cover either route; normal volunteers
cover normal trials only. No rank, KC, SECS or tenure thresholds are introduced.
The source contains no real applicant data or seeded volunteer roster.

## Configuration and activation

Keep this disabled until the owner approves the concrete channels, message
templates and reminder cadence. This update does not authorize posting or DMing.
The bot sends no volunteer invitation DMs and no public recruiting messages.

1. Keep the existing production `TOKEN` and `GUILD_ID` in the host's secret store.
2. Copy `trial_board_bot/config.example.toml` to `private/trial-board.toml`.
   Set the real IDs and `guild_id` to the same server as `GUILD_ID`.
3. Configure separate **private text channels** for the volunteer queue and staff
   feedback. Deny @everyone View Channel. Allow only staff, approved volunteers
   and Stabilibot in the queue; staff and Stabilibot in the feedback channel.
   Discord administrators inherently retain access.
4. Existing application channels must be private to the applicant, staff and bot
   (plus an assigned volunteer if staff intentionally grants access). Other
   non-admin roles/member overrides fail validation. The bot never edits permissions.
5. Give Stabilibot View Channel, Send Messages, Embed Links and Read Message History
   in these channels. This feature requires no additional privileged intents,
   Administrator, Manage Roles or Manage Channels permissions.
6. Keep SQLite under `private/` on a persistent local volume; restrict OS access
   and take private backups using SQLite's backup API or including WAL files.
   Never commit or upload the database, tokens, transcripts or feedback.
7. After approval, set `enabled=true` in the TOML and `TRIAL_BOARD_ENABLED=true`
   in the host environment. Optional `TRIAL_BOARD_CONFIG` changes the config path.
   Start Stabilibot through the existing `python main.py` process. Its normal
   command-sync behaviour registers the two new guild-scoped command groups.
   Do not run the standalone `trial_board_bot` entry point alongside it.
8. The database starts **paused**. Inspect `/board status`, complete the private
   acceptance test below, then use `/board resume` for the approved workflow.

Config defaults: shared pool, three initial targeted offers, 60-minute sessions,
14-day planning deadline and capacity two per volunteer. Staff can select 30–240
minutes and volunteer capacity 1–5. Deadlines never automatically reject anyone.

Use one always-on Stabilibot process for this database. A worker lease prevents
competing trial dispatchers, but ephemeral disks/sleeping hosts are unsuitable.
`/board pause` stops new actions and outgoing jobs; an in-flight send may finish.
To disable entirely, set `TRIAL_BOARD_ENABLED=false` and restart. This does not
delete trial data. Normal host sync may remove the now-absent trial commands.

## Availability and commands

See the [full command reference](trial-board-commands.md) for every command's
permissions, required/optional options, defaults, examples and button behaviour.

Use an IANA timezone such as `America/New_York`, `Europe/London` or `UTC`.
Each line supplies both dates:

```text
2026-11-08 18:00 / 2026-11-08 21:00
2026-11-09 19:00 / 2026-11-09 22:00
```

Windows must be at least five minutes away, within 21 days, non-overlapping and
at most 12 hours each. Supply 1–5 dated windows; availability is not recurring.
The slot picker labels UTC; Discord booking cards display local timestamps.
Ambiguous DST times require an explicit offset; nonexistent times are rejected.

| Command | Access and purpose |
|---|---|
| `/board approve`, `/board remove` | Staff manage approval/capacity; existing bookings need reassignment when removing someone |
| `/board availability`, `/board away` | Approved volunteers opt in/set availability or stop new assignments |
| `/board status`, `/board pause`, `/board resume` | Staff inspect and control the workflow |
| `/board recover` | Staff reconcile failed/uncertain deliveries after inspecting the expected channel |
| `/trial start`, `/trial reassign`, `/trial close` | Staff create, reopen or record an outcome |
| `/trial list` | Staff/approved volunteers see the queue |
| `/trial status` | Authorised participants inspect a trial and its current controls |

Buttons handle applicant availability/confirmation/rescheduling, volunteer claims
and private feedback. Role and actor checks apply to buttons and commands.

## Website handoff

This repository has no website acceptance handler to modify. The website backend
must call the new route **after staff accept an application for a trial**; until
that separate change, `/trial start` provides the complete manual entry route.
Generic role/channel API calls do not automatically start trials.

The existing API server adds `POST /trials/start`, using the existing `API_TOKEN`
body-token convention. Call from a trusted backend over HTTPS/private transport;
never put this token in browser JavaScript. Configure proxy/APM logging not to
capture request bodies. Use the existing server URL, without adding a `/v1` prefix.

```json
{
  "token": "<existing server-side API_TOKEN>",
  "request_id": "application:123:accepted-trial:v1",
  "applicant_id": 123456789012345678,
  "application_channel_id": 234567890123456789,
  "route": "normal",
  "minutes": 60
}
```

Use a stable unique request ID per accepted application, persisted by the website.
The first successful call returns HTTP 201 with `trial_id`, `status`, `replayed=false`;
a repeat returns 200 and the same trial (`replayed=true`), even after it closes.
Reusing an ID with a different payload or invalid channel access returns 409.
Invalid/missing configured API credentials return 401; invalid fields return 422.
Disabled, paused, not-ready or unavailable Discord access returns 503. Retry network
errors/503 with backoff and the **same** request ID; investigate 401/409/422 instead.
The website must retain unsuccessful handoffs for retry/staff attention.

## Delivery and recovery

Notifications include the initial applicant availability request, targeted volunteer
offers, proposals/bookings, and reminders approximately one day and one hour before
the session. If first seen within the last hour, only the hour reminder is sent.
Staff-only alerts flag missing availability/unclaimed trials after 24 hours, missing
feedback an hour after session end and trial deadlines, once per trial revision.
Outcomes are not automatically announced to applicants.

SQLite stores the workflow and an outbox; buttons survive restarts. Permission
errors halt delivery. Ambiguous sends become `uncertain` and block later jobs for
that trial; they are never blindly resent to another channel. Inspect the expected
channel for embed footer `Trial N · delivery J`, then use `/board recover` with
`action:found` and its message ID, or `action:retry` only after verifying absence.
Logs contain exception types/delivery IDs, not feedback or interaction payloads.

## Offline verification and private acceptance test

Use Python 3.12 and a clean virtual environment. Production requirements stay unchanged:

```sh
python -m pip install -r requirements.txt
python -m pip install httpx==0.28.1
python -m unittest discover -s tests -v
python -m trial_board_bot.demo
```

httpx is only needed for offline ASGI endpoint tests. Tests stub Discord login,
existing cron tasks and the API listener. They verify the real host with the
feature both disabled and enabled, including preservation of existing commands.

Before production use, obtain approval for a private test with consenting staff
accounts. Verify unauthorised access is denied; approve/opt in a volunteer; create
a synthetic application; add overlap; propose/confirm; reschedule; submit feedback
and verify staff-only visibility; restart and test pause and permission failure.
Offline tests do not replace this real Discord acceptance test.
