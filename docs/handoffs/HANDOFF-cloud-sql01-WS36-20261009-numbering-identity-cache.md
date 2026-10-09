# HANDOFF — Cloud Build → SQL01, WS36, 9 Oct 2026 (ticket numbers: no more 1,000-jumps)

**One database setting, which can be undone. No schema step and no code change. Also pull and restart for the
Came-from badges.**

This answers SQL01's numbering read (9 Oct). It supersedes nothing. 014's rule stands: a number is never reused, and
a gap is better than a reused number.

## What SQL01 measured, and what it means

- **The cause.** 7 gaps, 1,140 numbers missing, 319 tickets, highest number 1459.
  - The 999 between PMC-000454 (13:00) and PMC-001454 (13:34) is SQL Server's IDENTITY cache. It was lost in the
    unclean shutdown at 13:10 on 9 Oct: event 6008, with no 6006.
  - The five clean restarts since 1 Oct lost nothing. MEASURED.
- **The other 141.** They were spent inside transactions that rolled back whole: `issued_to IS NULL` = 0, so no
  number was abandoned half-way. The two large ones (47 and 88) are 1 Oct's rolled-back previews during the mail
  recovery. MEASURED.
- **Chat was not the cause.** PMC-001454 and PMC-001455 were simply the first tickets raised after the crash. The
  other chat tickets sit between their neighbours. MEASURED.

**Microsoft's guidance** (SQL01 VERIFIED it today): `IDENTITY_CACHE = OFF` avoids identity gaps when the server
restarts unexpectedly or fails over. It is the database-scoped form of trace flag 272.

**The choice.** Cloud Build recommends **OFF** for `PMC_PSA`:

- The cost is a log write per new identity value. INFERRED negligible at about 30 tickets a day.
- It stops the next unclean shutdown costing another 1,000 numbers.
- It recovers nothing already lost, and nothing should try to. **Never reseed `ticket_number` below 1459.** The
  numbers 1454–1459 exist, so a reseed would collide with them, and numbers already sent in emails must stay where
  they are.

## The step

1. As sysadmin, in `PMC_PSA`, note the setting first:
   `SELECT value FROM sys.database_scoped_configurations WHERE name = N'IDENTITY_CACHE';` gives **1**.
2. Turn the cache off:
   `ALTER DATABASE SCOPED CONFIGURATION SET IDENTITY_CACHE = OFF;`
3. Verify:
   - the same SELECT gives **0**;
   - `IDENT_CURRENT(N'psa.ticket_number')` is still **1459**, or higher if tickets arrived meanwhile;
   - the next ticket raised is that number + 1.

**Undo, if ever needed:** `ALTER DATABASE SCOPED CONFIGURATION SET IDENTITY_CACHE = ON;`

No restart, no backup required (it is metadata), and PSA-Desk can stay up. It applies to every IDENTITY in
`PMC_PSA`, which is what we want.

## Also in this pull: Came-from badges (`98b30eb`, code only)

Dada, 9 Oct: *"chat tickets differ from regular ticketing can we do a separation if the tickets came from chat rather
than numbering?"*

- Every ticket and board row carries a pill: Chat #n (it opens the chat), Portal, Email, Desk or Other.
- The board's *Source* filter becomes *Came from*.
- Reports split by it.
- No schema step. It takes effect after PSA-Desk restarts: expect 401, then down, then 401.

## Not ours, but noted for Dada

The 13:10 reboot on 9 Oct was not a clean shutdown: event 6008, and the 1074 shutdown request had no matching 6006.
It is worth a look in its own right: power, an update, or a forced restart.

## Process note (INFERRED)

Rolled-back previews against production spend numbers: 135 of the 141 came from 1 Oct's previews. Where a preview
would open tickets, prefer the test store.

## Evidence

| | |
|---|---|
| Measurements | SQL01's numbering read, 9 Oct 2026 (gaps, totals, IDENTITY_CACHE = ON, SQL Server 2022 16.0.1190.2, restart log). |
| Came-from code | Unit suite 803 OK (SQLite). CI `psa-spine` run 81 on `98b30eb`: green on all four jobs (Linux 3.11 and 3.14, sql-server, windows). MEASURED, 9 Oct 2026. |
