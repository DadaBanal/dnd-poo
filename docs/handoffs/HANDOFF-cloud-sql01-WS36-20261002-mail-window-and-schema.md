# HANDOFF — Cloud Build → SQL01, WS36, 2 Oct 2026

**One job: the 78 messages sitting in the two Inboxes are not becoming tickets, and the
064 schema step has not been applied to PMC_PSA.** Everything else in this file is the
evidence for why, measured on DND-SQL01 today by Dada, in output he pasted to me.

Supersedes nothing. Adds to `HANDOFF-cloud-sql01-WS36-20261001-single.md`, which still
stands for 058–064 and the calendar work.

Branch `claude/psa-ticketing-build`, head **after** this handoff's fixes. Pull before
reading the scripts.

---

## 1. What is already fixed and MEASURED good

| | |
|---|---|
| The mail plumbing | PSA-Mail-Helpdesk, PSA-Mail-Support, PSA-Notify, PSA-Calendar all Ready/Running, last result 0, running every minute. Certificate valid to 2027-10-01 (364 days). Drop and files folders empty, nothing in `failed\`. |
| The audit truncation | **FIXED and PROVEN on the host.** `mail-retry --all --apply` had failed on `String or binary data would be truncated ... column 'subject_id'`; it now runs, and released **9** set-aside messages, exit 0 (MEASURED 2 Oct 10:0x). `audit_event.subject_id` is class ID (64); a Message-ID is longer, so `db.audit` cuts the key, marks it cut, and writes the whole identifier into `detail` (FREE). No schema change. Same defect class as your part 28 finding on `data_quality.subject_id`. |

## 2. The live defect: a delta reset imports nothing, by design

MEASURED, twice, on DND-SQL01:

- 09:39 — both delta links forgotten. Preview from `-Since` sees **13 and 68** waiting.
- 09:40 through 10:06 — every scheduled pass logs `0 new message(s) since last pass;
  imported and delta link saved.`
- 10:06 — links forgotten again. Preview from `-Since` still sees **12 and 66** waiting.

The cause is not Graph and not the desk. `Register-PsaMail.ps1` registers the pickup with
no `-Since`, and `Invoke-PmcMailPickup.ps1 -Since` **defaults to now**. So the first pass
after a reset asks Graph for mail that arrived since that minute, finds none, and saves a
fresh delta link over the window the reset was meant to re-read. The reset was being
undone within 60 seconds, every time.

**Fixed in this pull, in `Repair-PsaMailPickup.ps1`:** when `-Apply -ResetDelta` forgets a
mailbox's link, step 6 runs that mailbox's pass **for real** with `-Since`, instead of in
preview. That pass is what imports the window; the minute task then carries on from the
link it saves. Nothing arrives twice — the import is keyed by Message-ID. Without
`-ResetDelta` the script still changes nothing and still only previews.

## 3. The other defect, mine, which blocked the schema step

`Invoke-PsaSpine.ps1 -SchemaPreview` and `-SchemaApply` both answered
`psaspine: error: unrecognized arguments: schema-preview` / `init`. In PowerShell `1..0`
counts **down**, so `$words[1..0]` on a one-word command returned the verb again and the
command went in twice. `-MailHealth` had the same fault. Fixed and tested.

## 4. What to run, in this order

Elevated, on DND-SQL01, from `D:\dnd-poo\platform\psa-spine\scripts`, after `git pull`.

**Step 1 — the 064 schema step.** `ticket_event.body_format` and `notification.body_html`,
both nullable, both guarded. Until they exist, a note written in the new editor will not
save and an import that writes a ticket event fails.

    .\Invoke-PsaSpine.ps1 -SchemaPreview
    .\Invoke-PsaSpine.ps1 -SchemaApply

That runs as `DND-SQL01\psa_desk`. **If that account is refused for want of ALTER rights**,
run the generated port instead as a sysadmin, which does not go through the desk's
connection guard at all:

    sqlcmd -I -S "DND-SQL01\PMC_SS" -d PMC_PSA -i D:\dnd-poo\platform\psa-spine\sqlserver\PMC_PSA_Spine_SqlServer.sql

with `@Apply = 1` and `@AllowExisting = 1` set at the head of the file — `@AllowExisting`
is what makes a re-run add only what is missing. It is one transaction with a verify gate.

**Step 2 — import the window.** One line, and it is the whole of it now:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Repair-PsaMailPickup.ps1 -Apply -ResetDelta -AsDesk

Step 6 will say `(importing from <date>)` for each mailbox and then how many it took.
Expect roughly 12 on helpdesk@ and 66 on support@. `-AsDesk` is only so step 5 can ask the
desk under the right account; leave it off and that step reports a refusal, which is not a
fault.

**Step 3 — read the board.** PMO Helpdesk should carry those requests, most with a name
taken from the sender's first line, because the subjectless mail fix (`summary_from`) is in
this branch too.

## 5. What is NOT VERIFIED

- Whether `psa_desk` may ALTER in PMC_PSA. If it may not, step 1's fallback is the answer,
  and please say which it was.
- Whether the real pass in step 6 imports all 78 cleanly, or whether intake sets any of
  them aside again. `Invoke-PsaSpine.ps1 -MailRetry` lists anything it did, and
  `-MailWhy <sender>` names the cause for one.
- Nothing in this file was run from the cloud session: no PowerShell and no route to the
  host here. The script changes are covered by the suite as text (702 tests) and by nothing
  else. Everything labelled MEASURED above was measured by Dada, in output he pasted.

## 6. One thing for you to decide

The task's `-Since` defaulting to now is correct in steady state — the delta link is what
keeps the place — but it means a reset can never recover a window on its own. Options, and
I have taken none of them: leave it as it is and let the repair own the recovery (what this
pull does); or give the two pickup tasks an explicit `-Since` of a day or two, so that any
reset, however it happens, re-reads that much. The second costs a longer first pass after
every reset and nothing else, because the import is idempotent. Your call.
