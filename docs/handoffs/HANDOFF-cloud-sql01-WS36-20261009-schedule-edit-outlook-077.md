# HANDOFF — Cloud Build → SQL01, WS36, 9 Oct 2026 (changing a booking in place, and your own Outlook entries, 077)

**One schema step, 077 (three nullable columns on `psa.outlook_busy`), the usual restart, and PSA-Calendar held while
it goes in.**

This follows `…-20261008-chat-survey-repair.md`, which SQL01 applied at Part 56 (`034de80`). It supersedes nothing.

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file.

---

## 1. What Dada asked for

Dada, 9 Oct 2026, each part confirmed before building:

- *"u can dispatch but when changing a schedule there is no modify on calendars and dispatch portal"*. Built:
  - an **Edit window**, opened by a right-click (**Edit…**) or a double-click, on Dispatch, the Schedule and the
    calendars;
  - **Move to tomorrow** on the same right-click;
  - time off, meetings and activities edit the same way;
  - the technician is told when someone else changes their visit.
- *"outlook too"*. The Outlook event follows each change, as for a drag.
- *"if owner owns outlook show exact schedule dont just show free busy on the calendars"*. Built:
  - The person whose Outlook it is now sees each entry's **subject and location** on Dispatch, the Schedule and their
    calendar.
  - **Everyone else** still reads *Busy*, *Tentative*, *Out of office* or *Working elsewhere* only.
  - An entry marked **Private** or **Confidential** in Outlook keeps neither its subject nor its location.
  - By Dada's choice, the subject is kept as Outlook has it, with no patient-detail check.
  - This reverses 059's *"never a subject"* for that one reader. It is recorded in `schema/077_outlook_detail.sql`
    and the README.

The README section is *Changing a booking in place, and your own Outlook entries*.

## 2. What runs without 077

**This head runs without 077.** MEASURED from the code:

- `calsync.import_busy` and `calsync.busy` check `db.column_exists(conn, "outlook_busy", "subject")` first. Without
  the column, the sync stores busy times exactly as before, and every page shows the Outlook word.
- The Edit window and Move to tomorrow need no schema step.

So the order is not critical. Until 077 is in, nobody sees their entries by name.

## 3. The step: 077, then restart

1. **Disable** PSA-Calendar, so no pass runs half-pulled code. A stopped minute task fires again on its own trigger.
   PSA-Notify can stay as it is: it does not touch `outlook_busy`.
2. Pull. `scripts/Sync-PsaCalendars.ps1` comes with it (§4).
3. Take a COPY_ONLY backup of `PMC_PSA`.
4. Stop `PSA-Desk`.
5. Note `SELECT COUNT(*) FROM psa.outlook_busy`.
6. In one transaction, as sysadmin via pyodbc as for 066 to 076, run the three statements taken verbatim from
   `sqlserver/PMC_PSA_Spine_SqlServer.sql` under `-- 077: the Outlook entry itself, for its owner.`. Each is guarded:
   - `IF COL_LENGTH(N'psa.[outlook_busy]', N'subject') IS NULL`
     `ALTER TABLE psa.[outlook_busy] ADD [subject] NVARCHAR(400) NULL;`
   - `IF COL_LENGTH(N'psa.[outlook_busy]', N'location') IS NULL`
     `ALTER TABLE psa.[outlook_busy] ADD [location] NVARCHAR(400) NULL;`
   - `IF COL_LENGTH(N'psa.[outlook_busy]', N'private') IS NULL`
     `ALTER TABLE psa.[outlook_busy] ADD [private] INT NULL CONSTRAINT [DF_outlook_busy_private] DEFAULT (0);`
7. Verify, inside the transaction:
   - `COL_LENGTH(N'psa.outlook_busy', N'subject')` and `COL_LENGTH(N'psa.outlook_busy', N'location')` are each
     **800**, which is 400 characters.
   - `COL_LENGTH(N'psa.outlook_busy', N'private')` is **4**.
   - `SELECT COUNT(*) FROM psa.outlook_busy WHERE subject IS NOT NULL` returns **0**.
   - `outlook_busy` holds the count from step 5.
   - If any check fails, roll back and hand back.
8. Start `PSA-Desk`. Expect `:8085` to answer 401, go down, then answer 401 again.
9. **Re-enable** PSA-Calendar.

Nothing changes in any scheduled task's command line, the file store or the backup.

## 4. The sync script

`Sync-PsaCalendars.ps1` now asks Graph's `calendarView` for `subject,location,sensitivity` as well as the times. It
sends the subject and the location's display name, except for an entry whose sensitivity is `private` or
`confidential`, which sends neither and is marked private. It still never reads attendees or the body. The file is
still plain ASCII.

**Permission.** INFERRED: no new Graph permission is needed. `calendarView` with the permission PSA-Calendar already
holds returns every field of the event, and only the `$select` changed. If a pass fails with 403 after the pull, that
inference is wrong: hand back with the log line and leave PSA-Calendar disabled.

The busy times already pulled have no subject until the next pass. Each pass deletes and re-reads its window
(`calsync.import_busy`), so within a minute of step 9 the window it covers carries subjects.

## 5. What to look for

- **PSA-Calendar.** `D:\psa\logs\PSA-Calendar.log` shows the next pass with last result 0.
- **In the database.** `SELECT COUNT(*) FROM psa.outlook_busy WHERE subject IS NOT NULL` goes above 0, if anyone in
  the sync has an Outlook entry in the window that is not Private.
  - `SELECT COUNT(*) FROM psa.outlook_busy WHERE private = 1 AND (subject IS NOT NULL OR location IS NOT NULL)`
    must stay **0**. Anything else is a defect: hand back.
  - Do not paste subjects back. A count is enough.
- **On the desk (Dada or a technician):**
  - Their own Outlook time on Dispatch, the Schedule and *My calendar* reads the meeting's subject, then
    `· location`. Another person's still reads *Busy*.
  - Right-click a visit, then **Edit…**: the window opens filled in. Change the time or the day and **Save**. It lands
    back on the same page with *Visit changed: …*, and the ticket's activity says the same.
  - Double-click a visit or a time off: the same window. A single click on a visit no longer opens *Add on …*, but an
    empty hour still does.
  - **Move to tomorrow** moves it a day on at the same time. Onto someone's time off, it is refused with the reason.
  - A visit changed by someone other than its technician reads as not acknowledged again. On a board that emails its
    owners, PSA-Notify sends the technician the new time.
  - The Outlook event moves within a minute. Given to another person, it leaves the first person's calendar and
    appears on the new one.

## 6. Evidence

| | |
|---|---|
| Unit suite | See the commit message (SQLite). New: `ConnectWiseShapeTest.test_a_visit_or_a_block_is_edited_in_place_and_rescheduled`, `OutlookCalendarTest.test_the_owner_reads_their_own_outlook_entries_and_nobody_else_does`. |
| Browser checks | `tests/browsercheck.py`, all pass (MEASURED, this commit). New: right-click > Edit opens a filled window; Save moves the visit on the same page; a double-click opens the same window and not *Add*. That last check found the single-click bug in §5, which is fixed here. |
| T-SQL port | `tools/sqlite_to_tsql.py --check`: in step (MEASURED, this commit). |
| SQL Server | CI `psa-spine` run 77, dispatched on `124ab71`: green on all four jobs (Linux 3.11 and 3.14, sql-server, windows). MEASURED, 9 Oct 2026. |
| Not run here | 077 against `PMC_PSA`, and the sync script against Graph. |
