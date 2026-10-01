# HANDOFF-cloud-sql01-WS36-20261001-dispatch-cc: 059, 060, 061 live; the queue claims helpdesk@; Procurement live; calendars on Outlook; Cc. One message

| Field | |
|---|---|
| To | SQL01, with Dada for two gates (the calendar grant; the Procurement owner and deputy) |
| From | Cloud Build (WS36) |
| Workstream | WS36 |
| Bucket | Everything Dada asked for on 1 Oct 2026 after the mail cut-over, live in one run: the desk in the reference PSA's shape (owner and resources, priorities, the Dispatch board, Outlook), helpdesk@ and help@ onto the Unrouted queue, Procurement live, Cc on tickets, the summary editable, files viewed in place. |
| Builds on | `HANDOFF-cloud-sql01-WS36-20261001-cutover-run.md` (the mail cut-over run) and SQL01's part 27. This file is the whole run; nothing else is needed to finish. |
| Head | The head this file arrives with. **Three schema steps, 059, 060 and 061**, in the one port. |
| Fence | No tenant ID, client ID, thumbprint or password in the repository, the runbook or a log. The task scripts read them from `D:\psa\mail-app.txt` and `D:\psa\mail-cert.txt`. No patient detail, no address, no credential in anything here. |

## Dada's words, 1 Oct 2026, verbatim

> "i also need a drop down for asiggning tickets out of the members also scheduling is not flowing through the
> tickets also procure,ment board isnt live" · "also priority changing" · "also add statuses type and subtypes that is
> fit for pmc" · "also can it be real time" · "also make the scheduling and calendar interacctive wherein clicking on
> the time can add either a task schedule or ticket that is synced with their emails ... the members should have their
> accounts calendars synced with the actual calendars on outlook or exchange"

> "if you would look at how connectwise works there is a ticket owner and a member it should be unassigned to start
> with and the dispatcher would assign the tickets / priorities should match what connectgwise has and can be overriden
> / scheduling should flow into ticket ... the calendars should be interactive ... what should go in outlook is the
> same as the outlook api or integration from connectgwise"

> "also ticket summaries cannot be edited" · "also autoviwer on attachments rather than being downloaded" · "also for
> the unrouted board add helpdesk and help@ emails" · "also can we add a cc on the tickets ... make sure its one bigh
> update when passed to sql"

## What this head adds (the README has a section per item)

| | Where | What |
|---|---|---|
| 1 | ticket, board | A ticket starts **unassigned**. Owner dropdown (Me first, then the board's members); **Assign me** (owner only); **Schedule me** (a visit for me, the ticket becomes mine when nobody has it). The people with a visit are its **resources**. |
| 2 | Setup › Priorities (060) | P1 to P4 with a name, a colour, an order and the default; the words paint every badge. A person sets a ticket's priority by hand and gives it back to the matrix. |
| 3 | Setup › Catalogue, statuses | `setup-pmc`: the PMC statuses, Areas, Subtypes and Items on PMO Helpdesk and Procurement; Procurement goes live with an owner and a deputy. |
| 4 | board, ticket, schedule | **Real time**: the page refreshes itself when something changes (every 10 s; never while you type). |
| 5 | /dispatch, /schedule, /calendar | The **Dispatch board** in the reference PSA's dispatch portal shape (VERIFIED 1 Oct 2026 against docs.connectwise.com, "Dispatch Portal"): people down the side, 06:00 to 20:00 across, every visit, block and Outlook busy time a strip across its hours, a red line at the current time, a conflict outlined red, utilisation per person (red under 50 %, yellow under 75 %, green from 75 %), a **To schedule** list. Drag a ticket onto a person's hour to book; drag a visit to move it; click an hour to book by hand; ✓ done, 👁 acknowledged. |
| 6 | Outlook (059) | Each member's visits and tasks on their Outlook calendar, their Outlook busy times back on the desk. Subject `PMC-nnnnnn - <company> - <summary>`; a restricted board or a PHI-flagged summary goes by number and board alone. A note never goes. |
| 7 | ticket | The **summary** is edited with the pencil beside it; PHI-scanned; written to the history. |
| 8 | ticket, portal | **Files open in place** (a picture, a PDF, a text file); Download beside; Office documents still download. |
| 9 | ticket (061) | **Cc**: an email's Cc addresses stay on the ticket; a person edits the list; the requester's emails copy them (within `pmcne.ph`). |
| 10 | mail | The **Unrouted queue claims helpdesk@ and help@**; support@ stays on PMO Helpdesk (step 2 below). The "we have your request" email now goes out **from the address the mail came to** (it was queued before intake had written that address, so it went from the sender's mailbox: fixed). |

## Run it, in order

**1. Apply 059, 060 and 061 by the sitting-1 road.** COPY_ONLY backup; the preview; stop PSA-Desk; apply the port;
`init` (it seeds the four priority rows, once); start PSA-Desk. Drop any scratch copy.

**Pass:**
- **tables:** 128 → **132**: `calendar_sync`, `outlook_busy`, `priority`, `ticket_cc`;
- **columns:** 1,226 → **1,253** (INFERRED from the schema files: 2 + 9 + 6 + 5 + 5; `ticket_schedule.outlook_event_id`,
  `schedule_block.outlook_event_id`, then the four tables);
- **indexes:** 52 → **54** (`ix_calendar_sync_status`, `ix_outlook_busy_member`); **triggers** 4, unchanged. The port's own
  verify block expects 132 tables, 4 triggers and at least 54 indexes (MEASURED from the generated port);
- **rows:** `priority` gains 4 (`P1`..`P4`) from `init`; nothing else changes.
- Every page opens before and after: a desk without 060 reads the default priority words and says so on Setup › Priorities.

**2. The Unrouted queue claims helpdesk@ and help@.** An address belongs to one board, so PMO Helpdesk gives the two up
first. Preview each, then `--apply`:

```powershell
C:\PMC\Python312\python.exe -m psaspine mail-setup "<the desk's connection>" --board IT_HELP --addresses support@pmcne.ph --actor "sql01 for dada.banal"
C:\PMC\Python312\python.exe -m psaspine mail-setup "<the desk's connection>" --board UNROUTED --addresses helpdesk@pmcne.ph,help@pmcne.ph --email-requester on --actor "sql01 for dada.banal"
```

- **Pass:** `mail-setup --board UNROUTED --show` lists the two addresses and `email the requester: ON`; `--board IT_HELP --show`
  lists `support@pmcne.ph` only. Both audited as `BOARD_INTAKE_ADDRESS`.
- **The tasks do not change.** `PSA-Mail-Helpdesk` keeps `-BoardId IT_HELP`: that is only the fallback for mail to an
  address nobody claims. A claim wins over it (`intake.route`).
- **What changes for the ward:** new mail to helpdesk@ or help@ opens on the **Unrouted queue**; the dispatcher routes it
  from the Dispatch page's Unrouted queue card or the ticket's Board field (a move keeps the number and the clocks).
  Its "we have your request" email goes out from helpdesk@, where they wrote. support@ mail opens on PMO Helpdesk as now.

**3. Procurement live.** Preview, then `--apply`:

```powershell
C:\PMC\Python312\python.exe -m psaspine setup-pmc "<the desk's connection>" --procurement PROCUREMENT --live --owner <member> --deputy <member> --actor "sql01 for dada.banal"
```

- **Gate: Dada names the owner and the deputy** (asked 1 Oct; not answered). Until then run it **without** `--live --owner
  --deputy`: the statuses and the catalogue go on and the board stays not live; the same command with the three switches
  later makes it live and adds nothing twice.
- The board id: read it from `SELECT board_id, display_name FROM board` first; `PROCUREMENT` is the id on the demo desk.
  The command refuses an id it does not know and changes nothing.
- **Pass:** the report ends `board PROCUREMENT: live, owner <member>, deputy <member>`; PMO Helpdesk gains the three
  waiting statuses (`Waiting on Parts`, `Waiting on BizBox`, `Awaiting approval`) and the PMC Areas; audited as `PMC_PACK`.
  A second run reports nothing added.

**4. Calendars on Outlook (059).** Three parts; (a) is Dada's.

- **(a) Dada, elevated, as himself, after `New-PsaMailApp.ps1`:** `scripts\Grant-PsaCalendars.ps1` (preview), then `-Apply`.
  It makes the mail-enabled security group **PSA desk calendars** with exactly the desk's members, the scope over it, and
  assigns `Application Calendars.ReadWrite` to the mail app on that scope. Never a Calendars grant in Entra. PASS text:
  InScope True for every member, False for another mailbox. Takes 30 minutes to 2 hours. Re-run it when the members change.
- **(b) SQL01, elevated:** `scripts\Register-PsaMail.ps1 -IncludeSupport -IncludeCalendar` (preview), then `-Apply`.
  PCSD has stopped (Dada, 1 Oct: "i have stopped pcsd"), so support@ goes in now. Tasks already registered are left as
  they are; this adds `PSA-Mail-Support` and `PSA-Calendar` (`Sync-PsaCalendars.ps1 -Apply` every minute: one pass
  writes what is due, then reads each member's busy times 28 days ahead, as blocks only).
- **(c) SQL01, once:** `C:\PMC\Python312\python.exe -m psaspine calendar-backfill "<the desk's connection>" --apply`, so
  visits booked before the sync reach Outlook.
- **Pass:** `D:\psa\logs\PSA-Calendar.log` shows a pass with writes SENT; a member's Outlook shows a visit under the
  category **Dada PSA**, subject `PMC-nnnnnn - <company> - <summary>`, body with the status and a link to the desk;
  an appointment they make in Outlook shows on `/dispatch` and `/schedule` as a grey chip within a minute or two.

**5. Walk the desk.** Each row is one check; record what it shows.

| | Do | Expect |
|---|---|---|
| a | Open a new ticket | Owner empty; **Assign me** and **Schedule me** on the header |
| b | Assign me | Owner is you; the picked-up email goes to the requester (and any Cc) |
| c | Schedule me, book an hour | A visit; `resources: <you>`; the Outlook event within two minutes |
| d | Setup › Priorities, rename P2 | The new words on every badge's title and the ticket header at once |
| e | Ticket › Priority, pick P1, Save | `priority P2 -> P1 (set by <you>)` in the history; **Matrix** gives it back |
| f | /dispatch, drag a To-schedule ticket onto a person's hour | Booked; it leaves the list; the ticket becomes theirs if nobody had it |
| g | Drag the visit to another hour or person | Moved, same length; a clash is refused with a reason |
| h | The pencil beside the summary | Edit, Save; the history line; the Outlook subject follows |
| i | Click a picture on a ticket | It opens in the page; Download beside it; a .docx still downloads |
| j | Email helpdesk@ with a Cc | The ticket on the Unrouted queue with the Cc on it; the "we have your request" from helpdesk@, Cc copied |
| k | Route it to PMO Helpdesk | The ticket moves; its number and clocks stay; the status email from helpdesk@ |

## Stop switches

- `Register-PsaMail.ps1 -Undo -Apply` removes the four tasks; `Grant-PsaCalendars.ps1 -Undo -Apply` removes the
  assignment, the scope and the group.
- Addresses back as they were: `mail-setup --board UNROUTED --addresses ""` then `--board IT_HELP --addresses
  helpdesk@pmcne.ph,help@pmcne.ph,support@pmcne.ph`, each with `--apply`.
- Nothing in 059–061 is read by the old code; the schema steps need no undo.

## Not verified, said once

- The reference PSA's default priority names (`Priority 1 - Emergency Response` ...) are NOT VERIFIED: its documentation
  is behind a sign-in. They are editable at Setup › Priorities.
- Which fields its Outlook sync writes is INFERRED from the indexed documentation; the subject shape is ours.
- A PDF shown inline carries `default-src 'none'` rather than the `sandbox` flag, INFERRED from Chromium's plugin rules.
- Column count 1,253 is INFERRED from the schema files; the port's verify block is what the apply proves.

## Added the same evening: two mails not ingested (yahoo, gmail). Measure first, then step 0

Dada, 1 Oct 2026, verbatim, with a screenshot of the **PMC - Central Support Desk** inbox: *"these two tickets arent
being ingested make sure it ingests all"* · *"yahoo and gmail"* · *"and all other generic emails"*. The two: from
`jrby_cancer2014@yahoo.com`, subject "HIMS - NETWORK PROBLEM - JRBY BILLING", 16:41, with an inline picture; and from
Nueva Ecija Stone Center, subject "Property Request", 16:34.

**MEASURED on this head, here:** a yahoo.com sender with an inline picture, and an Outlook mail that references a
thread intake never saw, both open tickets. Intake has no rule on a sender's domain: the public-domain list only stops
company matching, and the loop guard knows mailer-daemon, postmaster and MicrosoftExchange only. The pickup's Graph
query is as documented (VERIFIED 1 Oct 2026, learn.microsoft.com/graph/delta-query-messages: `changeType=created`,
`$filter=receivedDateTime ge`, nextLink then deltaLink). So the cause is on the host and is one of three. Each is one
command, and the order is: measure, then act.

**0a. Ask the desk.** As the desk, on this head (step 1 above pulled; no schema step is needed for this):

```powershell
C:\PMC\Python312\python.exe -m psaspine mail-why "<the desk's connection>" --sender yahoo.com --days 2
C:\PMC\Python312\python.exe -m psaspine mail-why "<the desk's connection>" --sender gmail.com --days 2
C:\PMC\Python312\python.exe -m psaspine mail-why "<the desk's connection>" --subject "Property Request" --days 2
```

It prints, per matching message, what intake did (opened a ticket, joined one, set aside and why) with its findings and
message-id, whether an **exclusion rule catches the sender**, and which addresses are claimed. Or it says nothing arrived
from the pickup. Subjects print: keep the output on the host; put only the disposition words in your reply.

**0b. What each answer means, and what to do:**

| mail-why says | Cause | Do |
|---|---|---|
| `UNCLASSIFIED` with `excluded domain yahoo.com` (or gmail.com) | A DOMAIN exclusion on Setup › Email connector. Dada's ruling now: ingest all. | Remove the rule there (audited). Then `mail-retry "<db>" --message-id <id> --actor "sql01 for dada.banal" --apply` for each set-aside message, delete `D:\psa\mail-state\inbox-deltalink-<slug>.txt` for that mailbox, and run that mailbox's pickup once by hand with `-Since '2026-10-01 00:00' -Apply`: the fresh sync re-fetches the day, intake skips what it already placed (by Message-ID) and imports the forgotten ones. |
| nothing arrived, and the mailbox is support@ | The screenshot's "PMC - Central Support Desk" is `support@` (INFERRED from the record: support@ is the PCSD mailbox). Its pickup, `PSA-Mail-Support`, exists only after `Register-PsaMail.ps1 -IncludeSupport` (step 4b). Nothing from support@ is read until then. | Step 4b, with `-Since '2026-10-01 00:00'` on the first run of `PSA-Mail-Support` so the day is picked up. Check elevated first: `Get-ScheduledTask PSA-Mail-Support`. |
| nothing arrived, and the task exists | A stuck pass: `D:\psa\logs\PSA-Mail-Support.log` (or -Helpdesk) repeating `Import FAILED ... delta link NOT advanced` every minute. At the old head one message that could not be placed lost the whole pass and held every later message behind it. | Pull this head (step 1). The next pass places the rest, records the one that cannot be placed as `UNCLASSIFIED` with an `INTAKE_ERROR` naming the error and the file, keeps that pass's files in `D:\psa\mail-drop\failed\`, and advances. Paste the INTAKE_ERROR line to WS36. |
| `NEW_TICKET -> PMC-nnnnnn` | It was ingested; the ticket is on the board named. | Say which board; nothing else. |

**0c. They hear back.** Replies were released to `pmcne.ph` only (`-AllowedDomain`, the 058 default): a requester on
yahoo or gmail got a ticket and no "we have your request". At this head `Register-PsaMail.ps1` registers `PSA-Notify`
with `-AllowedDomain '*'`, and a public mail domain can no longer be excluded (one address still can). `PSA-Notify` is
already registered with the old value, so once: elevated, `Unregister-ScheduledTask -TaskName PSA-Notify -Confirm:$false`,
then `Register-PsaMail.ps1 -Apply` (it registers only what is missing). Pass: the task's Execute shows
`-AllowedDomain '*'`; the next acknowledgement to a yahoo address goes SENT.

**Pass:** `mail-why` shows every one of the day's mails to helpdesk@ and support@ as `NEW_TICKET` or `APPENDED`, the two
named ones included; the Setup › Email connector page shows no exclusion on a public domain; the yahoo requester's
acknowledgement is SENT.

