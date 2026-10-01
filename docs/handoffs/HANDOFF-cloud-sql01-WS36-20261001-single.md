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
