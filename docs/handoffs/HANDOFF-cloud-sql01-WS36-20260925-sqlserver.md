# HANDOFF-cloud-sql01-WS36-20260925-sqlserver

The desk onto the SQL Server PMC has (D7, `docs/WS36-decisions-d7-20260925.md`).
Builds on the pilot handoff (`…-20260925-pilot.md`), which is not edited; where
this file and it differ, this file is later and wins: the pilot database becomes
`PMC_PSA` on `DND-SQL01\PMC_SS` instead of `D:\psa\spine.db`, and every task and
command that named the file names the connection string.

| Field | |
|---|---|
| **To** | SQL01, with the operator at the keyboard. One sitting. |
| **From** | Cloud Build |
| **Workstream** | WS36 (PSA ticketing): the store |
| **Bucket** | The database `PMC_PSA` on the existing instance, the schema applied by the generated script, the desk and its tasks running against it, the test suite green against it, and one verified backup. Nothing in `PMC_SS` is touched. |
| **Read first** | 1. `platform/psa-spine/README.md`, "On SQL Server (D7, 25 Sep 2026)" 2. `docs/WS36-decisions-d7-20260925.md` 3. `sqlserver/PMC_PSA_Spine_SqlServer.sql`, its header 4. this file |

## Before you start

- **The instance.** `DND-SQL01\PMC_SS` is the imaging index's instance. This
  sitting adds a *database* to it and touches nothing in `PMC_SS`. The script
  refuses any database but `PMC_PSA` by name.
- **NOT VERIFIED from here, all of it.** Everything below was run against SQL
  Server 2022 Express 16.0 in a container on 25 Sep 2026 (MEASURED there) and
  never against `DND-SQL01`. Edition, version and collation of `PMC_SS` are not
  known here; step 1 reads them and the reply carries them.
- **Version floor.** The runtime SQL uses `TRIM()`, which is SQL Server 2017+.
  If step 1 reports an older version, **stop and report BLOCKED**; the fix is
  one line in the translator, not a workaround here.
- **If the pilot has begun** on `D:\psa\spine.db` and that file holds tickets,
  **stop and report BLOCKED** at step 0: there is no importer between the two
  stores and this file does not invent one.

## Do

Every step that changes something is marked **CHANGE**. `$py` is
`C:\PMC\Python312\python.exe`. Run PowerShell as the operator; SQL as a login
that is `sysadmin` on the instance, at the keyboard, never in a file.

**0. Check before you change.**

```powershell
C:\PMC\Python312\python.exe -c "import sqlite3,os;p=r'D:\psa\spine.db';print(sqlite3.connect(p).execute('select count(*) from ticket').fetchone() if os.path.exists(p) else 'no file')"
```

**Pass:** `(0,)` or `no file`. Anything else: BLOCKED (above).

**1. Read the instance** (changes nothing):

```sql
SELECT SERVERPROPERTY('Edition'), SERVERPROPERTY('ProductVersion'),
       SERVERPROPERTY('Collation'), DB_ID('PMC_PSA');
```

**Pass:** `ProductVersion` 14.x or higher (2017+); `DB_ID('PMC_PSA')` is NULL.
Write all four values into the reply.

**2. CHANGE: the driver.** As the operator:

```powershell
Get-OdbcDriver -Name "ODBC Driver 1*" | Select Name
C:\PMC\Python312\python.exe -m pip install pyodbc
C:\PMC\Python312\python.exe -c "import pyodbc;print(pyodbc.version, pyodbc.drivers())"
```

**Pass:** a driver named `ODBC Driver 17 for SQL Server` or `ODBC Driver 18 for
SQL Server` is listed by both. If neither exists, install Microsoft's ODBC Driver
18 for SQL Server from learn.microsoft.com (the x64 MSI; no other option
changed) and re-run. If `pip` has no route to PyPI, say so in the reply: the
wheel can be handed over on the next sitting.

**3. CHANGE: the database and the desk's login.** In SSMS or `sqlcmd`, as
`sysadmin`, `@Apply`-style — read, then run:

```sql
-- the database, its own; recovery model as the instance's index database uses
CREATE DATABASE PMC_PSA;
ALTER DATABASE PMC_PSA SET READ_COMMITTED_SNAPSHOT ON;   -- readers do not wait on writers, as SQLite's WAL gave the pilot
GO
USE PMC_PSA;
-- the account the scheduled tasks run as; Windows authentication, no password anywhere
CREATE LOGIN [PMCNE\<psa task account>] FROM WINDOWS;           -- skip if it exists on the instance
CREATE USER [PMCNE\<psa task account>] FOR LOGIN [PMCNE\<psa task account>] WITH DEFAULT_SCHEMA = psa;
ALTER ROLE db_datareader ADD MEMBER [PMCNE\<psa task account>];
ALTER ROLE db_datawriter ADD MEMBER [PMCNE\<psa task account>];
GRANT EXECUTE, VIEW DEFINITION TO [PMCNE\<psa task account>];
```

The domain and account name are the record's, not this file's. **Pass:**
`SELECT default_schema_name FROM sys.database_principals WHERE name = N'PMCNE\<psa task account>'`
returns `psa` (the schema need not exist yet; the desk checks this very row).

**4. CHANGE: the schema.** Preview first, as the file insists:

```powershell
cd D:\dnd-poo
git pull origin claude/psa-ticketing-build
sqlcmd -S "DND-SQL01\PMC_SS" -E -d PMC_PSA -i platform\psa-spine\sqlserver\PMC_PSA_Spine_SqlServer.sql
```

**Pass:** `PREVIEW ONLY … 73 tables, 25 indexes, 4 triggers … Existing objects
in [psa] right now: 0`. Then set `@Apply = 1` at the top of a **copy** of the
file (never the committed one) and run the copy the same way.
**Pass:** `Created: 73 tables, 4 triggers, 25 indexes in [psa].` Run the copy
once more unchanged: **Pass:** it refuses (`already holds 77 objects`). Delete
the copy.

**5. CHANGE: seed and accounts.** Everything the pilot handoff did to the file,
done to the database. The connection string below is the only one this desk
uses; it holds no secret.

```powershell
$py = 'C:\PMC\Python312\python.exe'
$db = 'Driver={ODBC Driver 18 for SQL Server};Server=DND-SQL01\PMC_SS;Database=PMC_PSA;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes'
$env:PSA_ATTACHMENT_DIR = 'D:\psa\files'
& $py -m psaspine init $db
& $py -m psaspine setup-board $db --board UNROUTED
& $py -m psaspine setup-board $db --board IT_HELP
& $py -m psaspine create-local-account $db --username <sysadmin> --sysadmin
& $py -m psaspine create-local-account $db --username <technician>
```

Run these **as the task account** (or grant the operator the same database
roles for the sitting and revoke them after): `init` connects as whoever runs
it and refuses a user whose default schema is not `psa`. Use
`ODBC Driver 17 for SQL Server` in `$db` if that is what step 2 found.
`TrustServerCertificate=yes` is for the instance's self-signed certificate
(INFERRED; if the instance carries a CA-issued certificate, drop it).
**Pass:** `init` prints `ready: SQL Server, Driver=…;Server=DND-SQL01\PMC_SS;Database=PMC_PSA`
and exits 0 (the schema is already there; it changes nothing; the console
never shows more of a connection string than that); each account signs in at
step 7.

**6. The test suite, against the real instance.** The one step that turns NOT
VERIFIED into MEASURED, and the reason for a separate test database:

```sql
CREATE DATABASE PMC_PSA_TEST;
ALTER DATABASE PMC_PSA_TEST SET READ_COMMITTED_SNAPSHOT ON;
USE PMC_PSA_TEST;
CREATE USER [PMCNE\<operator>] FOR LOGIN [PMCNE\<operator>] WITH DEFAULT_SCHEMA = psa;
ALTER ROLE db_owner ADD MEMBER [PMCNE\<operator>];
```

```powershell
cd D:\dnd-poo\platform\psa-spine
$env:PSA_TEST_DB = 'Driver={ODBC Driver 18 for SQL Server};Server=DND-SQL01\PMC_SS;Database=PMC_PSA_TEST;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes'
& $py tests\test_spine.py 2>&1 | Tee-Object D:\psa\test-sqlserver-20260925.txt | Select-Object -Last 5
Remove-Item Env:PSA_TEST_DB
```

The tests call the script with `@Apply = 1, @AllowExisting = 1` themselves
(`PMC_PSA_TEST` is not `PMC_PSA`, so the script's own name check is what the
tests bypass — deliberately, and only there: `db.init(…, reset=True)` empties
that database before every test). **Pass:** `OK` with the count the README
gives. Then `DROP DATABASE PMC_PSA_TEST;`. Anything but `OK`: the reply
carries the file, and nothing further in this sitting runs the desk on SQL
Server.

**7. CHANGE: the desk and its tasks.** Every scheduled task from the pilot
handoff (serve, mail pickup, run-rules, send notifications, retention preview)
re-registered with `$db` in place of `D:\psa\spine.db` and `PSA_ATTACHMENT_DIR`
set in the task's environment or the wrapper it runs. The `serve` task first:

```powershell
& $py -m psaspine serve $db --host 127.0.0.1 --port 8080
```

**Pass:** `/login` answers 200; the operator signs in with the step 5 account;
a ticket raised on the board appears in
`SELECT TOP 5 work_item_id, board_id, state FROM psa.ticket ORDER BY opened_at DESC`
run in SSMS. Each task shows `Last Run Result 0x0`.

**8. CHANGE: the backup.** `psaspine backup` refuses for SQL Server and says
why; the database is backed up by SQL Server. Add `PMC_PSA` to the job that
backs up the index database, or, if none exists yet (the WS23 handoff's
finding), create the smallest safe one:

```sql
BACKUP DATABASE PMC_PSA TO DISK = N'<the WS23 backup volume>\PMC_PSA_full.bak'
  WITH INIT, CHECKSUM, COMPRESSION;
RESTORE VERIFYONLY FROM DISK = N'<the same file>' WITH CHECKSUM;
```

daily, as a SQL Agent job if the edition has Agent (Express does not: then a
scheduled task running `sqlcmd -E -Q "…"`). The attachment folder `D:\psa\files`
keeps the robocopy from the attachments handoff. **Pass:** `RESTORE VERIFYONLY`
says the backup set is valid, and the reply names the job and its schedule.

## Do NOT decide

- Whether `PMC_SS`'s recovery model or backup job change. They do not, here.
- Log-backup cadence and retention for `PMC_PSA` (proposed: whatever the index's
  job does; the record decides).
- Anything in the pilot handoff's own "Do NOT decide".
- Turning requester emails or the portal on.

## Fence

Hostnames and account *roles* only. The task account's name, any password, the
sysadmin login and every address stay off this file, the commit and the reply.
The connection string committed in README and here carries a hostname, a
database name and `Trusted_Connection=yes`, and nothing else.

## Done means

- Steps 0 to 8 each report their **Pass** line (MEASURED), step 1's four values
  in the reply.
- `D:\psa\test-sqlserver-20260925.txt` ends in `OK` and the reply gives the
  count.
- The desk answers on the LAN from `PMC_PSA`, every task `0x0`, and one
  verified backup exists before the first real ticket.

| Written | 2026-09-25, UTC |
|---|---|

## Reply

*(appended once by SQL01)*
