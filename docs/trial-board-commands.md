# Trial board command reference

These are the 13 commands added by the trial-board update. Existing Stabilibot
commands are outside this reference. The feature is not deployed or enabled.

Examples use placeholder members/channels and trial number `12`. Select the real
member/channel through Discord's command options; replace `12` with the number
shown on the trial card. Replies to slash commands are private to the person using
them. Commands that change a trial can also queue channel messages as described.

## Who can use what

- **Staff:** people holding a configured staff role. Administrator alone is not
  treated as a configured staff role by this feature.
- **Approved volunteers:** people approved through `/board approve` who also hold
  a configured volunteer role. Being approved does not itself grant that role.
- **Applicants:** can access their own trial and its applicant buttons.

All commands require the configured server and valid private queue/feedback channel
permissions. If validation fails, staff must fix those permissions before commands
can proceed. Approval and availability management, status/list, pause/resume and
delivery recovery can be used while paused. Creating/changing trials and submitting
feedback require the workflow to be running. Pause also stops outgoing jobs; an
already in-flight Discord send may finish.

## Staff commands

### `/board approve`

Approve a volunteer in the bot, or update an existing volunteer's route/capacity.

- `member` — required; the person being approved, not a bot account.
- `route` — optional; `normal` (default) or `efficient`.
- `capacity` — optional; 1–5 concurrent proposed/booked/awaiting-review trials,
  default `2`.

Example: `/board approve member:@Volunteer route:normal capacity:2`

Staff must also grant the configured volunteer role manually. A newly approved
volunteer must use `/board availability` to opt in. Reapproving an existing record
updates its approval, route and capacity without clearing its saved availability
or changing its opt-in state. With the default shared pool, route does not restrict
matching. It does not impose raid qualifications or calculate eligibility.

### `/board remove`

Stop a volunteer receiving new assignments and revoke their bot approval.

- `member` — required; the volunteer to remove.

Example: `/board remove member:@Volunteer`

It does not remove Discord roles or release existing bookings. Review `/trial list`
and use `/trial reassign` for affected trials. A removed volunteer cannot submit
feedback until approved again with the required role.

### `/trial start`

Create a trial and queue an availability request in the applicant's channel, plus
a card in the private volunteer queue.

- `applicant` — required; the applicant, not a bot account.
- `application` — required; their existing private text channel in this server.
- `route` — optional; `normal` (default) or `efficient`.
- `minutes` — optional; session length 30–240 minutes, default `60`.

Example: `/trial start applicant:@Applicant application:#application-example route:normal minutes:60`

The applicant must be able to view the channel. It cannot be the shared queue or
staff feedback channel. Only one open trial is allowed per applicant. The planning
deadline uses the configured `trial_days` (default 14); reaching it alerts staff
and never automatically decides admission.

### `/trial reassign`

Release an existing assignment/booking and request fresh applicant availability.

- `number` — required; the trial number.

Example: `/trial reassign number:12`

This clears the assigned volunteer, booked/proposed time and previous applicant
windows. It queues an applicant availability request and tells the previous
volunteer that the booking was released. It does not directly assign a named
replacement or reopen a closed trial.

### `/trial close`

Record the staff decision and close a trial.

- `number` — required; the trial number.
- `outcome` — required; `accepted`, `declined` or `withdrawn`.

Example: `/trial close number:12 outcome:accepted`

The outcome is recorded and a staff-channel update is queued. No Discord roles or
clan membership are changed, and the applicant is not automatically sent a decision
message. Staff complete the usual membership steps and communication themselves.

### `/board status`

Show whether the workflow is paused and list unresolved failed/uncertain deliveries
(up to 25 in the reply). It takes no options. Use the delivery IDs with
`/board recover` after inspecting the expected channel.

### `/board pause`

Pause new trial actions and outgoing workflow messages. It takes no options and
does not cancel existing bookings or delete data. Administrative/status commands
remain available as described above; an in-flight message may still finish.

### `/board resume`

Resume trial actions and outgoing jobs. It takes no options. Due pending messages
may be delivered once resumed. Use only for the approved channels and notification
workflow, after inspecting current state. This is separate from the deployment
feature switches, which must already allow the cog to load.

### `/board recover`

Reconcile a failed or uncertain outgoing delivery after checking Discord.

- `delivery` — required; the delivery ID from `/board status`.
- `action` — required; `found` or `retry`.
- `message_id` — required for `found`; omitted for `retry`.

If the message arrived, inspect its embed footer (`Trial N · delivery J`) and use:

`/board recover delivery:45 action:found message_id:123456789012345678`

The bot fetches the message from the expected channel and verifies its author and
footer before recording the receipt. It does not resend it.

Only after verifying the message did not arrive, use:

`/board recover delivery:45 action:retry`

This makes the job pending again; sending waits if the workflow is paused. Do not
blindly retry an uncertain delivery, because Discord may already have accepted it.

## Volunteer commands

### `/board availability`

Open a form to set your dated availability/timezone and opt in to new assignments.
It takes no command options. It replaces your saved windows; it is not a weekly
recurring schedule. Existing bookings are not rescheduled by changing availability.

Enter an IANA timezone such as `America/New_York`, `Europe/London` or `UTC`, then
1–5 non-overlapping windows, one per line, with both dates:

```text
2026-11-08 18:00 / 2026-11-08 21:00
2026-11-09 19:00 / 2026-11-09 22:00
```

Choose actual future dates: at least five minutes away, ending within 21 days,
and at most 12 hours per window. Ambiguous DST times require an explicit UTC offset;
nonexistent times are rejected. Use this command again to return after `/board away`.

### `/board away`

Opt out of new assignments while retaining your approval and saved availability.
It takes no options. Existing bookings still need you or a staff reassignment.
Pending proposals may no longer be confirmable while you are away; tell staff if
someone is waiting on one. Use `/board availability` to opt back in.

## Viewing trials

### `/trial list`

**Staff and approved volunteers.** List up to 30 open trials, newest first, showing
trial number, applicant and status. It takes no options. Open a specific trial
with `/trial status` to see its details and controls.

### `/trial status`

**Staff, approved volunteers, or that trial's applicant/assigned volunteer.**

- `number` — required; the trial number.

Example: `/trial status number:12`

Show the applicant, route/pool, volunteer, availability, session length, deadline
and proposed/booked time. Open trials include buttons appropriate to the viewer.
Closed trials can be viewed but have no action buttons. Staff-only feedback notes
are not included in this card.

## Buttons and forms

These actions use buttons rather than additional slash commands. Buttons still
check the actor and current state; use `/trial status` if a card is out of date.

| Button | Who uses it | What it does |
|---|---|---|
| Set availability | That applicant, while unbooked | Opens the dated-window/timezone form; windows must fit the session length and trial deadline |
| Pick a time | Approved volunteer with a compatible slot and capacity | Opens a UTC-labelled picker and proposes a time; applicant confirmation is still required |
| Confirm time | That applicant | Confirms the current unexpired proposal and queues booking notices for both participants |
| Reschedule | Applicant, assigned volunteer or staff | Releases the assignment/time and requests fresh applicant windows, like `/trial reassign` |
| Submit feedback | Approved assigned volunteer, while booked and after the scheduled start | Opens a form for `recommend`, `more_time` or `concern`, plus 5–1800 characters about communication, effort, participation and fit; sends only to staff |

Staff and volunteers normally access board controls from the queue card or
`/trial status`; the applicant uses their application-channel card or their own
`/trial status`. A button being visible does not authorise its use. Feedback moves
the trial to staff review; staff still record the final outcome themselves.
