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

**Step 1 — 063 and 064, by the sitting-1 road.** Not just the ALTERs: this head also
changes the desk's own code (the ticket editor, the pods behind an Edit button, the portal's
identity match), and none of that reaches a browser until PSA-Desk restarts. So:

1. a COPY_ONLY backup;
2. the preview;
3. **stop PSA-Desk**;
4. apply the port;
5. `init`;
6. **start PSA-Desk**.

Steps 2 and 4–5 as the desk's own account:

    .\Invoke-PsaSpine.ps1 -SchemaPreview
    .\Invoke-PsaSpine.ps1 -SchemaApply

**If `psa_desk` is refused for want of ALTER rights**, run the generated port as a sysadmin
instead — it does not go through the desk's connection guard at all:

    sqlcmd -I -S "DND-SQL01\PMC_SS" -d PMC_PSA -i D:\dnd-poo\platform\psa-spine\sqlserver\PMC_PSA_Spine_SqlServer.sql

with `@Apply = 1` and `@AllowExisting = 1` set at the head of the file — `@AllowExisting`
is what makes a re-run add only what is missing. It is one transaction with a verify gate.

**What 063 and 064 add:** `dispatch_view` (one table: member, people, board_id, updated_at);
`ticket_event.body_format` (NVARCHAR(32) NULL) and `notification.body_html`
(NVARCHAR(MAX) NULL). No existing row changes, and a note written before today stays plain
text and reads as it did. Until those columns exist, a note written in the new editor will
not save and an import that writes a ticket event fails.

**What the restart is what makes visible** (all of it already on this branch, none of it
needing anything from you beyond the restart): the ticket note box is a real editor with
copy and paste, bold, lists and a link, and a paste out of Outlook that keeps the words and
none of the markup; the side pods are fixed in place and move only behind an **Edit layout**
button, with small/half/medium/full widths and plus-minus height; the mega menu; and the
portal's 404 fix for a requester whose mail address and sign-in are on different domains.

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

---

## Reply to part 31 (Cloud Build, 2 Oct 2026, later)

Read. 064 in, desk restarted onto the new code, 78 messages imported, tickets 26 → 90, gap
swept and clean. Three things back.

**1. Your step-6 flag is right, and it is now fixed at the root.** You are right that the
repair's real pass imports as the launching identity, so even Dada launching it himself hits
the `[dbo]` guard. The deeper fault was underneath it: `Invoke-PmcMailPickup.ps1` ran
`import-mail` **only when that pass had written a file**, and the import takes the drop
folder whole. So a pass whose import was refused left its files there and no later pass ever
looked again — the next pass found 0 new, skipped the import, and the window sat on disk.
That is the trap your hand recovery stepped around.

Changed: a pass now imports whatever `.eml` is waiting in the drop folder even when it
fetched nothing, and says so in the log. The minute task runs as the desk's own account, so
it places them within a minute or two; the import is keyed by Message-ID, so nothing arrives
twice, and both this pass's files and the ones that were waiting are cleared (or moved to
`failed\`) together. The repair now says exactly that when its own placing is refused:
fetched and waiting, not lost. No credential plumbing added, and no step asks anyone for the
`psa_desk` password.

**2. Your two blocked paths are noted and the handoff was wrong to assume them.** `sqlcmd`
denied to your session, and S4U registration needing SeTcbPrivilege that an elevated
administrator does not hold (the live tasks carry a stored password) — that also explains
Dada's `-ViaTask` *Access is denied* on 2 Oct, which I had put down to a batch-logon right.
`-ViaTask` cannot work for anyone here; the password prompt is the only road, and
`Invoke-PsaSpine.ps1` already says so when it is refused. Your sysadmin-via-pyodbc DDL and
`EXECUTE AS USER` import are the right substitutes; recorded as the method on this host.
`psa_desk`'s own ALTER right stays NOT VERIFIED, and nothing now depends on it.

**3. The three UNCLASSIFIED are Dada's to read, not yours to guess.**
`Invoke-PsaSpine.ps1 -MailWhy <sender>` names the cause for one, and `-MailRetry` lists them;
once the cause is put right, `-MailRetry --all --apply` releases them, which is measured
working now. Not a defect until one of them says otherwise.

**The `-Since` default stays as it is**, and the repair owns the recovery. With the change
above, a reset now recovers even when the person who ran it could not place the messages,
which was the remaining reason to want the task to carry a window.

---

## Both of your specs are built (Cloud Build, 2 Oct 2026, later still)

Code only. **No schema step, no new column** — `body_format` was already there from
064, and the catalogue tables are untouched. One pull and a PSA-Desk restart is the
whole of it.

**1. The composer.** The toolbar and the note box are one frame, as the Teams composer
is: the border and focus ring belong to the frame, the buttons sit above it in three
groups (marks; lists and blocks; link and clear), the placeholder opens "Type a note",
and the box grows as it is written in to 60% of the window and then scrolls. Rich and
Plain are unchanged, and the textarea is still what is submitted and still what a
browser with no script types into.

**2. Type → Subtype → Item.** Three dependent selects, resolving to the same single
`catalogue_item_id`, board-scoped as before. The third select is the answer and the
only one with a `name`; it carries every live pair with its Type, Subtype and Item on
its own `data-` attributes, and the two narrowing selects are `hidden` until the script
fills them from those attributes. So the script can never offer a pair the catalogue
does not hold, and with no script at all the page is exactly the picker it was: one
select, grouped by Type, labelled in full. Nothing was added to the form's answer, so
every POST handler, every test of them and the API are untouched.

**The pickers are not empty.** MEASURED on a fresh help desk (seed template + the PMC
pack): **16 Types, 53 Subtypes, 210 pairs**. A test now holds that floor. On PMC_PSA,
the pack went in at parts 29–30, so to confirm rather than assume:

    .\Invoke-PsaSpine.ps1 -Spine "setup-pmc --actor dada.banal"

It previews and writes nothing; *nothing to add: the pack is already there* is the
answer you want. If it lists things instead, the pack is partly in and `--apply` adds
only what is missing.

**Pass:** open a ticket. Type shows ~16 areas; picking "Hospital systems (BizBox)"
narrows Subtype to its eight; picking "BizBox HIS" leaves its Items; Save keeps the
classification. The note box is one bordered frame whose ring lights on focus, and
typing past its height grows it.

**Before you demo it, confirm the pickers hold something** (Dada asked twice to be sure):

    .\Invoke-PsaSpine.ps1 -CatalogueHealth

Reads only. It prints the tree (Types, Subtypes, Items, pairs) and, per board, how many
pairs its picker offers, flagging any board below 20 pairs as THIN. On PMC_PSA the pack
went in at parts 29–30, so expect no THIN boards and PMO Helpdesk showing its own pairs; if
anything reads THIN, `setup-pmc --apply` (or Setup › Catalogue › Apply the template) fills
only what is missing. This is the live-store answer to "do the pickers have data", rather
than my test DB's.

---

## #3, the label fix (Cloud Build, 2 Oct 2026)

Code only, no schema, one PSA-Desk restart. The ITIL record-kind field and the catalogue's
Type were both labelled "Type" on the ticket page, which read as two of the same thing. The
record kind (Incident, Request, Problem, Event) is now **Ticket type**; the cascade keeps
Type → Subtype → Item. Renamed in both places the field appears: the ticket edit form and the
board's New-template form. The POST field name is unchanged (`record_type`), so nothing behind
it moved and no handler, test or the API is touched.

**Pass:** open a ticket — the first classification field reads "Ticket type", the cascade below
it reads Type / Subtype / Item. Nothing else changed.
