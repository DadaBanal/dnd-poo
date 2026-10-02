# HANDOFF-cloud-sql01-WS36-20261001-single: everything from 1 Oct 2026 in one message

| | |
|---|---|
| From | Cloud Build (WS36), 1 Oct 2026, evening |
| To | SQL01; two lines for Dada at the end |
| Supersedes | `HANDOFF-cloud-sql01-WS36-20261001-dispatch-cc.md` and the three sections appended to it the same day. That file stays as the record of what was said when; **this one is the list to run.** Dada: "do as a single handover". |
| Head | the latest commit on `claude/psa-ticketing-build`; `git log -1` after the pull names it |

## What this head carries beyond 4d79ad2 (live on the host at your part 29)

| Item | Where it shows | Host step |
|---|---|---|
| A mega menu: the modules across the bar, each opening its pages; one Menu on a phone | every desk page | none |
| 062: a desk sysadmin by the member record, so a Windows sign-in runs Setup › Members | Setup › Members › the person › Desk sysadmin | schema step + one command, below |
| 063: whose rows the Dispatch board shows, kept per dispatcher | Dispatch › People | schema step, below |
| Pod sizes (Full / Medium / Half / Small), pod height by dragging the bottom edge, the Screen layout gear with Pod configuration (Displayed / Available) | the ticket page | none (per person, in their browser) |
| The exchange so far under every requester email, newest first, each entry through the PHI gate | the requester's emails | none |

## Run, in order

1. **Pull and restart** as before: stop PSA-Desk, `git pull`, start. Expect the suite's count in the start log to be 645 OK (MEASURED here).
2. **Schema, one step**, elevated on `DND-SQL01\PMC_SS`, after the usual backup: run the generated port `sqlserver\PMC_PSA_Spine_SqlServer.sql` once more. It is guarded, so on the live store it does exactly two things and nothing else: `ALTER TABLE psa.[member] ADD [is_sysadmin] INT NULL DEFAULT (0)` (062) and `CREATE TABLE psa.[dispatch_view]` (063). Read back: `member` has the column, `dispatch_view` exists and is empty, tables 132 → **133**, no row changed.
3. **The first sysadmin**, once, as the task account:
   `C:\PMC\Python312\python.exe -m psaspine set-sysadmin "<the desk's connection>" --member dada.banal --actor sql01`
   It prints `dada.banal is now a sysadmin.` and the list. From then on Dada signs in with his Windows account and runs Setup › Members from there; the break-glass interim is no longer needed.
4. **Pass**, then reply as part 30:
   - Dada, signed in via Windows: Setup › Members answers 200 and a member can be taken off a board.
   - Dispatch › People › tick two › Save as my view › reopen: two rows, the button reads "2 of N · saved".
   - A ticket page: the gear opens Pod configuration; untick a card, Save, reload: it stays hidden; drag a card's bottom edge, reload: the height stays.
   - An Updated email in Outlook shows "Earlier in this request, newest first" under the reply.

## Still Dada's, elevated, unchanged from your part 29

- `Register-PsaMail.ps1 -IncludeSupport -IncludeCalendar -Apply` (PSA-Notify is not registered, so no requester email goes out until it is; `Grant-PsaCalendars.ps1` first for PSA-Calendar).
- The Procurement owner and deputy (`--live`).

## Not verified, said once

Nothing in this message was run against `DND-SQL01\PMC_SS` or Outlook from here; every "expect" is from the suite and the demo desk. Step 2's two statements are read from the generated script (MEASURED), not from a run on the live store.


---

## Added 2 Oct 2026: inbound mail, and a member's mailbox on a second domain

Dada is running these himself; they are here so the record has them. **Neither needs a schema step.**

| | |
|---|---|
| `Invoke-PmcMailPickup.ps1` | an expired delta link made Graph answer 410 and the pass threw on every run from then on, so mail stopped and nothing restarted it. It now forgets the link, reads from `-Since`, and logs that it did. No message arrives twice: the import is keyed by Message-ID. |
| `Repair-PsaMailPickup.ps1` (new) | one pass over the tasks, the certificate, the delta links and logs, the folders, and a live preview pass per mailbox; says which of them is the cause. Preview by default; `-Apply` starts a stopped task, `-ResetDelta` forgets an expired link. |
| `Grant-PsaCalendars.ps1`, `Sync-PsaCalendars.ps1` | `-AllowedDomain` takes a list, so a member whose mailbox is on a second domain is in the calendar sync once that domain is named. A mailbox on no named domain is still never written to. |

If PSA-Calendar is registered, re-register it once so its command carries the second domain
(`Register-PsaMail.ps1 -IncludeSupport -IncludeCalendar -Apply` leaves a registered task as it is, so remove
`PSA-Calendar` first if its arguments must change).


---

## Added 2 Oct 2026, later: 064, a note written as rich text

| | |
|---|---|
| Schema | `064_note_format.sql`: `ticket_event.body_format` and `notification.body_html`, both nullable. **One schema step**, the port's two guarded ALTERs; a re-run adds nothing twice. No existing row changes, and every note written before today stays plain text and reads as it did. |
| What it is | the note box on a ticket is an editor: bold, lists, a link, and a paste out of Outlook or Word that keeps the words and none of the markup. Nothing is stored until `richtext.clean` has rebuilt it, and the PHI scan reads the words, never the markup. |
| Also | the requester's email carries the note as written (`notification.body_html`), with the text of the email always sent as well. |
| Pass | write a note with a bold word and a bullet, save: the ticket shows them. Paste a block out of Outlook: the words arrive, no fonts or colours do. An Updated email in Outlook shows the bold word. |

---

## Added 2 Oct 2026, later still: the audit key a Message-ID would not fit in

MEASURED on DND-SQL01 by Dada, 2 Oct 2026. Releasing the messages intake had set aside
(`mail-retry --all --apply`) failed on the host and released none of them:

    String or binary data would be truncated in table 'PMC_PSA.psa.audit_event', column 'subject_id'

| | |
|---|---|
| Cause | `audit_event.subject_id` is class `ID`, `NVARCHAR(64)`: a key, indexed beside `subject_kind` (054) and joined to `ticket.work_item_id` by Setup > Audit. Every subject the spine names itself is far shorter. A mail Message-ID is not ours and is longer. The same defect you found in part 28 for `data_quality.subject_id`, which is why that one is class `REF`. |
| Why the cloud suite never saw it | SQLite stores the long value and says nothing. So the audit row is now shaped in `psaspine/db.py`, where both stores read the same code, rather than relying on the host to refuse it. |
| The fix | **no schema change.** The key is cut to the width the column promises and marked as cut (a trailing ellipsis), and the **whole** identifier is written into `detail`, which is class `FREE` and is the field Setup > Audit searches. Nothing is lost, and the index stays as narrow as it was designed to be. Covered by a test on both stores. |
| Also | `Invoke-PsaSpine.ps1` grew `-SchemaPreview` / `-SchemaApply`, because the schema step cannot be run as a sysadmin either (same `[dbo]` refusal), and `-OutFile` for a caller that reads the answer. `-ViaTask` now stops at a refused `Register-ScheduledTask` instead of failing three more times after it: that error is non-terminating. `Repair-PsaMailPickup.ps1` and `Fix-PsaToday.ps1` take `-AsDesk`, which puts their questions to the desk through the desk's own account instead of reporting a refusal as a fault. |
| Pass | `Invoke-PsaSpine.ps1 -MailRetry -All -Apply` releases every set-aside message, one audit row each; Setup > Audit shows a MAIL_RETRY row per message whose detail carries the full Message-ID. |
