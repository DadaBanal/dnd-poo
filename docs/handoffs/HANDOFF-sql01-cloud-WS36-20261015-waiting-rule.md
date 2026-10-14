# HANDOFF — SQL01 → Cloud Build, WS36, 15 Oct 2026 (Dada's rule for tickets waiting on someone outside the desk: clocks stop, a reminder at 3 days, closed at 3 more, a reply reopens)

**Dada's ruling, 15 Oct 2026, verbatim:** *"the respond to usually if the requester or the ticket is on awaiting the
sla clock or resolution clock should stop and if it isnt answered after 3 days the message should go out to the one
who made the ticket ie we tried to get in contact with you for an approval or response so there should be waiting
approval or waiting user response status something like that and if they dont respond after 3 days the ticket gets
resolved ie ur ticket has been closed we tried to contact you but failed to get a response on this ticket , if you
feel this is a mistake pls reply back to this ticket or reply through the portal or help portal to reopen the ticket
with the awaited response something like that"*

It came out of PMC-001527 (Pulmonary, *Awaiting approval* since 12 Oct 14:13, respond clock "Breached by 28h" while
nobody had been asked anything) and the ConnectWise comparison: ConnectWise meets respond by a status move and stops
escalation entirely in *We are waiting (do not escalate)*. The desk copied the vocabulary — every status carries an
`escalation_status` — and not the behaviour. **This brief is the behaviour.** Nothing on the host changes for it.

## 1. The rule, as read — one reading stated, his to correct

| | |
|---|---|
| The two statuses | **Awaiting approval** and **Waiting on requester** — both `NO_ESCALATION`, both exist on IT_HELP today (`IT_HELP.AWAITING_APPROVAL`, `IT_HELP.WAITING_ON_REQUESTER`). It is the *waiting user response* status he asked for, under its current name; rename it *Waiting user response* if he prefers the word; no new status is needed. |
| While in either | **Both clocks stop** — respond and resolve. Today only resolve pauses; respond kept running on PMC-001527 and breached. |
| Day 3 in the status, no answer | **A reminder goes out.** His words: to the one who made the ticket — *we tried to get in contact with you for an approval / a response*. |
| Day 3 after the reminder, still no answer | **The ticket closes** with: *your ticket has been closed; we tried to contact you but failed to get a response on this ticket; if you feel this is a mistake, reply to this ticket or through the help portal to reopen it with the awaited response*. |
| A reply, by email or portal | **Reopens the ticket.** Exists: `closed_reply_policy = REOPEN` on IT_HELP with no time limit (`reopen_within_days` null), so a reply to the closed thread reopens it today. The portal path must land in the same place. |

**The reading I am acting on, said once:** two separate three-day periods — day 3 the reminder, day 6 the close —
counted in calendar days from entering the waiting status, with the second three days counted from the reminder. If
he meant three days in total, he will say so in two words.

**One refinement, SQL01's reading and not his words — he has been told and can strike it.** On *Awaiting approval*
the person who has not answered is usually the **approver**, not the requester. So: on *Waiting on requester* the
reminder and the close go to the requester exactly as he said; on *Awaiting approval* the reminder goes **to both — the
approver and the requester** (Dada, 15 Oct: *"it should go to both"*), and the close reads *your request was not approved in time* rather than *we
could not reach you*. Same clock, same days, the right address.

## 2. What exists and what is missing — measured on the live desk, 15 Oct

| Piece | State | |
|---|---|---|
| The two waiting statuses | **exist** | 11 tickets sit in a `NO_ESCALATION` status right now |
| Stop both clocks on `NO_ESCALATION` | **missing** | only resolve pauses; respond runs — the defect behind "Breached by 28h" |
| Respond met by a status move | **missing** | ConnectWise's rule: the move from *New* to anything but a *not responded* status is the response |
| A trigger on time in status | **missing** | the rules engine fires on `TICKET.AGE_MINUTES` (since opened), not minutes in the current status; the reminder needs the latter |
| The reminder template | **missing** | `outbox.TEMPLATE_KINDS` has OPENED, UPDATED, CLOSED; add **WAITING_REMINDER** with an approval wording and a response wording |
| The close-for-no-response template | **missing** as its own kind | add **CLOSED_NO_RESPONSE** (and its approval variant) so the board can word it apart from a normal close |
| Reply reopens | **exists** | `intake.py:478–492`; the portal reply path must do the same |

## 3. Three things to hold while building it

1. **The clocks stop; they are not reset.** A ticket that waited four days and comes back resumes its respond and
   resolve clocks where they were — `paused_minutes` already carries this for resolve; respond joins it.
2. **The close for no response is a close, not a resolution.** It goes to `>Closed` with the reason recorded
   (*no response after 6 days*), never to *Resolved* — the requester did not get what they asked for, and the reopen
   sentence only makes sense on a close.
3. **Awaiting approval must ask someone before its clock can mean anything.** `psa.department.approver` is null on
   all 53 departments and `requires_approval` is unset on the status. Dada sets the approver per department (the
   department head); the status gets the flag so the move sends the request and records the decision.

## 4. The ConnectWise reference, for the words

Escalation statuses: *We have NOT responded · We have responded · We have created a resolution plan · We have resolved
the issue · We are waiting (do not escalate)*. Respond = first *not responded* status to first *responded* status.
*Waiting* = the next action is not on the desk; no escalation. (MSP+ service-board guide; BrightGauge CW SLA training;
r/ConnectWise SLA basics.) The desk's `escalation_status` values map one to one; honour them.

`PSA_BIZBOX_WRITE_ODBC` unset; nothing on the host changed.
