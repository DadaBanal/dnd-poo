# HANDOFF — Cloud Build → SQL01, WS36, 12 Oct 2026 (warmer emails, a department on every ticket, PMC by default, 079)

**One schema step, 079: one nullable column and one index on `psa.ticket`. Then the usual PSA-Desk restart and three
preview-first commands: `mail-words` twice, then `ticket-fill`.**

This follows `…-20261010-help-stays-lan.md`. It supersedes nothing.

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file, **once CI is green on it**.

---

## 1. What Dada asked for, each part confirmed before building

Dada, 12 Oct 2026, with a screenshot of a *"we think your request is fixed"* email:

- *"the messages or replies are very robotic can we please do specific replies for procurement board and the pmo
  helpdesk board and make it more human and fit for the hospital"*. Chosen from two samples: **warm and plain**.
- *"on the requests … can the fields be dropdown like department"*. Chosen: a **Department dropdown, already set to
  the requester's own**. Department only: no other new dropdowns.
- *"a department mark on each tickets or a column"*. Chosen: **a column, a badge and a filter**.
- Then: *"the default should be premiere medical center as that the only company we are working with atm"*, and Type,
  Subtype and Item picked automatically when a ticket is raised from the requests page.

The README section is *Warmer emails, a department on every ticket, PMC by default*.

## 2. What runs without 079

**This head runs without 079.** MEASURED from the code: every reader asks `departments.on_tickets(conn)` first. That
holds for the board's column and filter, the ticket's badge and dropdown, the portal's dropdown, and writing a new
ticket's department. Without the column they all behave exactly as today. Pinned by
`DepartmentCompanyAndWordsTest.test_a_store_without_079_carries_on_as_before`.

**Two changes are live as soon as PSA-Desk restarts on this head, with or without 079:**

- **The desk's default email words.** Every requester email that uses the desk's own words reads warm and plain, and
  so does the patient-guard line. The senders (PSA-Notify) pick this up on their next pass, with no restart.
- **A new ticket's company is PMC** when intake cannot tell, instead of UNCLASSIFIED. This reverses the earlier rule,
  on Dada's word, and the reversal is recorded in `board.py`. A desk with no `PMC` company keeps UNCLASSIFIED.

## 3. The step: 079, then restart

1. Pull (once CI is green on the head).
2. Take a COPY_ONLY backup of `PMC_PSA`.
3. Stop `PSA-Desk`. PSA-Notify, PSA-Calendar and the pickups can stay as they are: none of them touches the new
   column.
4. Note `SELECT COUNT(*) FROM psa.ticket`.
5. In one transaction, as sysadmin via pyodbc as for 066 to 078, run these two blocks, each taken verbatim from
   `sqlserver/PMC_PSA_Spine_SqlServer.sql`. Both are guarded:
   - `IF COL_LENGTH(N'psa.[ticket]', N'department') IS NULL` … `ADD [department] NVARCHAR(400) NULL`
   - `IF NOT EXISTS (… N'ix_ticket_department' …) CREATE INDEX [ix_ticket_department] ON psa.[ticket] ([department]);`
6. Verify, inside the transaction:
   - `COL_LENGTH(N'psa.ticket', N'department')` is **800** (400 characters).
   - `SELECT COUNT(*) FROM sys.indexes WHERE name = N'ix_ticket_department'` returns **1**.
   - `SELECT COUNT(*) FROM psa.ticket WHERE department IS NOT NULL` returns **0**.
   - `ticket` holds the count from step 4.
   - If any check fails, roll back and hand back.
7. Start `PSA-Desk`. Expect `:8085` to answer 401, go down, then answer 401 again.

## 4. Each board's own words, preview first

Run under the desk account, from `platform/psa-spine`:

```
C:\PMC\Python312\python.exe -m psaspine mail-words "<the desk's connection>" --board IT_HELP --words HELPDESK --actor "sql01 for dada.banal"
C:\PMC\Python312\python.exe -m psaspine mail-words "<the desk's connection>" --board PROCUREMENT --words PROCUREMENT --actor "sql01 for dada.banal"
```

Each one writes nothing. It prints one line per email:

- `+` will be written, with its new subject;
- `=` already so;
- `~` the board's own words are kept (someone wrote them on Setup › board › Emails);
- `?` a status with no words in the set, so the desk's defaults stay.

The last line reads `Would write N email(s); …`. The lines hold subjects and status names only.

- **No `~` lines:** run the same commands again with `--apply`. Each ends `applied`.
- **Any `~` line:** paste both previews back and wait. Overwriting words someone on the desk wrote (`--replace`) is
  Dada's call.

**Not touched:** whether each status emails at all. That stays the board's own switch, including Procurement's 16 that
were turned on on 9 Oct.

A second run reads `Wrote 0 email(s)`. Setup › Audit shows `MAIL_TEMPLATE` and `STATUS_MAIL` rows by the actor named.

## 5. The one-off tidy, preview first

**Superseded in part, 13 Oct 2026 (runbook Part 77).** Dada ruled that a ticket's department is never filled in
afterwards: it is set only at the door (the portal's dropdown, an emailed ticket's sender, a member on the desk). So
the department half of `ticket-fill` is **gone from the code** at the head carrying this note, and the company half
(46 tickets, UNCLASSIFIED → PMC) was **already applied by SQL01** on 12 Oct. What is left of the command names the tiles
with no Item, and prints `department: never filled in here`. Nothing below is still to run unless Dada asks for the
tile list again. The `IT_HELP` *Resolved* `+` line SQL01 reported is also fixed: words equal to the desk's own are
stored NULL, so the preview now compares the words, not the flag, and a second run reads `Wrote 0`.


```
C:\PMC\Python312\python.exe -m psaspine ticket-fill "<the desk's connection>" --actor "sql01 for dada.banal"
```

It writes nothing and prints counts, department names and tile labels only (never a person, never a summary):

- `department: N ticket(s) with none; M take their contact's; K stay unset …`, then a count per department.
- `company: N ticket(s) under UNCLASSIFIED -> PMC`. If it reads `no PMC company on this desk`, hand back: the default
  depends on the company id `PMC` (INFERRED from the desk's New ticket form, which already defaults to it).
- `portal tiles with no Type > Subtype > Item: N`, then their labels. A ticket raised from one of these still needs
  the ticketer to pick its Item. Dada sets them on Setup › Portal tiles, which now shows the same list in a banner.

**Paste it back whole.** Run it with `--apply` once Dada has seen it. A second run reads 0 everywhere.

## 6. What to look for

- **A requester's email**, the next status change on either board. For example, a Resolved on PMO Helpdesk reads:
  - *"Hi Via, Good news: Anne has fixed your request. Could you check it on the ward when you get a moment? …
    Thanks, PMO Helpdesk"*;
  - with no *"as of"*, and with no portal wording pasted mid-sentence.
  - Do not paste a real email back. Say which one read wrong, if any.
- **The patient guard:** a reply that the PHI scan flags now reads *"We've kept this message off email in case it
  mentions a patient. You can read it on the PMC Requests portal from any PMC computer."*
- **The board:** a *Department* column after *Company*, a Department filter beside *Came from*, and a sky-blue
  department badge on each ticket's header.
- **The portal** (a ward PC): *Which department is this for?* appears, already set to the person's own.
- **A new emailed ticket** from a person whose AD department is on Setup › Departments arrives with that department.
- **A new ticket from an unknown sender** gets Company *Premiere Medical Center*, not UNCLASSIFIED.

## 7. Evidence

| | |
|---|---|
| Unit suite | `DepartmentCompanyAndWordsTest` (9). Portal dropdown pre-set, chosen, and junk falling back to their own; tile form too. Email and desk tickets take the contact's AD department, the desk changes it with history, and an unknown one is refused. Board column, filter (`none` too) and sort. A store without 079 is unchanged. PMC default, and `ticket-fill` preview, apply and once-only, keeping the catch-all where there is no PMC. Tiles with no Item named, on the Setup page too. `mail-words` preview, apply, once-only, a board's own words kept unless `--replace`, on/off untouched, every PMO Helpdesk status covered. A Resolved email reads as a person wrote it. The guard line. Full suite: see the commit message. |
| Screens | Board with the Department column (sorted) and filter; a ticket's department badge and field; the portal form; the Resolved email. Taken on a throwaway desk, not attached here (the record keeps none). |
| T-SQL port | `tools/sqlite_to_tsql.py --check`: in step (MEASURED, this commit). |
| CI | See the commit that follows. |
| Not run here | 079 against `PMC_PSA`; `mail-words` and `ticket-fill` against the live boards. |
