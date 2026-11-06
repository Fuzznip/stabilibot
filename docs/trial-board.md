# Trial coordination: backend owns the workflow

This update is paired with `Fuzznip/stabilisite-backend`. The backend stores all
trial records in its existing PostgreSQL database. Stabilibot is the Discord UI
and delivery transport: commands, modals, embeds, buttons and permission checks.
There is no local trial SQLite database and no trial API on the bot's API server.
Existing host commands, API routes, handlers, intents and cron jobs are preserved.
Both services are disabled by default; the backend migration starts paused.

## What lives where

| Backend | Stabilibot |
|---|---|
| Volunteer approval and availability; timezone/DST validation | Reads the actual Discord member/roles for each interaction |
| Trials, matching, capacity/overlap rules, proposal expiry and outcomes | Renders commands, forms, cards and private replies |
| Reminder scheduling, durable outbox, leases, receipts and audit | Polls for a delivery, checks channel permissions, sends it, acknowledges it |
| Feedback records; authorized participant/staff access | Sends feedback only to the configured staff channel |
| Durable records identifying persistent buttons | Re-registers button handlers from backend records on restart |

Database rules and role/participant checks run on the backend even when the bot
has already checked them. The service credential is server-only; actor IDs/roles
are assertions made by the trusted bot, never input accepted from browser clients.
No automatic admission, rank changes or volunteer invitation DMs are introduced.
Normal/efficient are general categories; shared matching is the default. No raid,
SECS, rank or tenure requirements are added.

## Configure both services

1. Deploy the paired backend code and apply its `022_add_trial_board` migration
   using the backend's normal `flask db upgrade` process. Do not run migrations on
   a production database while merely testing. Backend setup: see its
   `docs/trial-board.md`.
2. Set the backend's `TRIAL_BOARD_GUILD_ID`, `TRIAL_BOARD_QUEUE_CHANNEL_ID`,
   `TRIAL_BOARD_STAFF_CHANNEL_ID`, `TRIAL_BOARD_STAFF_ROLE_IDS` and
   `TRIAL_BOARD_VOLUNTEER_ROLE_IDS`. Role lists are comma-separated. Staff and
   volunteer role lists must be disjoint, even though a person may hold both roles.
3. Copy `trial_board_bot/config.example.toml` to `private/trial-board.toml` in the
   bot working directory. Fill the same guild/channel/role IDs. The bot's existing
   `GUILD_ID` must match. The backend is authoritative: a mismatch stops delivery.
4. Set the bot's existing `BACKEND_URL` and `BACKEND_API_KEY`. The backend's existing
   `API_KEYS` list must accept that bot key. Set a separate `TRIAL_BOARD_API_KEY` in
   **both** services' secret environments. Never commit keys, configs, trial data
   or feedback, or put these credentials in website JavaScript. HTTPS is required;
   plain HTTP is accepted by the bot only for localhost tests. Redirects are refused.
5. Use separate private text channels for the volunteer queue and staff feedback.
   Deny @everyone View Channel. Queue access: configured staff/volunteer roles and
   Stabilibot. Feedback: configured staff roles and Stabilibot only. Administrators
   inherently retain access. Existing application channels must be private to the
   applicant, staff, bot and an intentionally assigned volunteer. Unrelated role
   access or member overrides fail closed. The bot never changes permissions.
6. Stabilibot needs View Channel, Send Messages, Embed Links and Read Message
   History in those channels. No extra privileged intent, Administrator, Manage
   Roles or Manage Channels is needed by this feature.
7. After approving a private test, set backend `TRIAL_BOARD_ENABLED=true`, bot
   `TRIAL_BOARD_ENABLED=true` and TOML `enabled=true`. Start the existing bot with
   `python main.py`. Do not also run the standalone entry point with the same bot.
8. Check `/board status`. The backend starts paused. Once the test participants,
   channels, messages and reminder cadence are approved, use `/board resume`.

The earlier SQLite-era config is obsolete: remove `database`, `shared_pool`,
`offer_limit` and `trial_days` from the bot TOML. The backend environment now owns
`TRIAL_BOARD_SHARED_POOL` (true), `TRIAL_BOARD_OFFER_LIMIT` (3), and
`TRIAL_BOARD_TRIAL_DAYS` (14). This is a predeployment refactor; no private SQLite
records are silently copied or discarded. If someone has already accumulated live
SQLite data, pause and plan an explicit, backed-up migration before switching.

## Workflow and commands

Staff grant the volunteer Discord role and run `/board approve`. Volunteers opt
in separately with `/board availability`, giving 1–5 dated windows and an IANA
timezone. `/board away` stops new offers while preserving existing bookings.

Staff run `/trial start` with a human applicant and their private application
channel. The applicant supplies 2–3 suitable windows. The backend offers the trial
to up to three compatible volunteers, favouring lower workload and less recently
offered volunteers. A volunteer picks a time and the applicant confirms it.
Reservations count towards capacity and expire within 24 hours or five minutes
before the session. Cross-trial overlaps are blocked under a PostgreSQL row lock.

A volunteer submits short private feedback after the scheduled start. Staff record
an outcome with `/trial close`; the feature does not change admission/rank roles.
See [all 13 commands and buttons](trial-board-commands.md).

The backend endpoint is `POST /trial-board/actions`. The bot passes the real
Discord actor and current role IDs; server-side checks enforce staff, volunteer
and participant scope. The old bot `POST /trials/start` route is removed. Existing
website application-acceptance behavior is unchanged. `/trial start` is the full
manual entry route; a future website integration can call the backend's domain
service directly once an accepted application is explicitly associated with its
private Discord channel. No webhook back into the bot or website frontend change
is required for this manual test.

## Notifications, outages and restart

The bot polls every 30 seconds; backend code performs matching, expiry and reminder
calculations. Notifications include availability requests, targeted offers,
proposals/bookings, approximately one-day and one-hour reminders, and staff alerts
for stalled trials, deadlines and missing feedback. Deadlines do not reject people.
`/board pause` stops new actions and outgoing jobs; an in-flight send may finish.
Disable with the feature environment switches and restart; data stays in Postgres.

Only one Discord delivery worker holds the backend lease. Claimed jobs have unique
tokens; stale acknowledgements are rejected. Failed/ambiguous deliveries hold later
jobs for that trial. Lost claims expire to `uncertain`, including when the same bot
stays alive. Lost receipt responses do not trigger another Discord send. Inspect
the expected channel for footer `Trial N · delivery J`, then use `/board recover`
with a verified message ID or an explicit retry after verifying absence.

Backend outages fail closed. The transport retries startup after the backend
recovers, rehydrates persistent buttons from durable backend receipts, and never
retries a mutating HTTP request blindly. Feedback is not cached on disk by the bot.
Keep normal PostgreSQL backups; no new private bot database volume is needed.

## Test before enabling for the clan

Use Python 3.12 and an isolated environment in each repository.

```sh
# Stabilibot
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m trial_board_bot.demo
```

Bot tests cover real host loading enabled/disabled, preserved commands/handlers,
persistent controls, HTTP credentials, timeout handling, staff-only feedback and
receipt loss. The demo is a synthetic transport demonstration, not a live trial.

Run the paired backend's tests against an isolated PostgreSQL `*_test` database
(never production), including booking races, migration upgrade/downgrade, access
checks and worker takeover. See that repository's setup instructions.

For the private Discord acceptance test: verify unauthorized actors cannot act;
approve and opt in a consenting volunteer; start a synthetic trial; set overlapping
windows; propose and confirm; test conflicts/rescheduling; submit feedback and
verify staff-only visibility; restart both services and use existing buttons;
simulate an unavailable backend and changed channel permissions; test pause and
receipt reconciliation. Offline tests do not replace this private live check.
