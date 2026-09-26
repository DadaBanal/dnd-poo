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
| **Read first** | 0. `HANDOFF-cloud-sql01-WS36-20260926-runbook.md` (the order, the defaults, what to do when a step does not pass, the rule that outranks every line here) 1. `platform/psa-spine/README.md`, "On SQL Server (D7, 25 Sep 2026)" 2. `docs/WS36-decisions-d7-20260925.md` 3. `sqlserver/PMC_PSA_Spine_SqlServer.sql`, its header 4. this file |

## Pre-flight findings, 26 Sep 2026 (SQL01, MEASURED, read-only) and what changed

SQL01 paused at pre-flight and reported; this section records what it found
and how the steps below were corrected before anything was created. Nothing
on the server has changed.

| Found | Consequence here |
|---|---|
| `DND-SQL01\PMC_SS` is **Standard Edition, 16.0.1190.2** (SQL Server 2022), collation `SQL_Latin1_General_CP1_CI_AS`; SQL Agent running; `DB_ID('PMC_PSA')` NULL. | Version floor met. Standard, not Express: no 10 GB cap; the backup is an **Agent job**, not a scheduled task. |
| The instance holds **nine user databases, all on `C:`**, among them `LiveDB_PMC` (the live HIS), `PMC_Apps`, `PMC_Reporting`, `ReportServer` and the Orthanc index. | `PMC_PSA` is created on **`D:`** (step 3). The premise that this is "the imaging index's instance" was wrong; D7's record carries the correction and the HIS-separation risk, which is Dada's to accept. |
| Port **8080 belongs to the live queue screens** (`http.sys`, IIS site `PMC-Queue`). The estate record says never bind 8080 here. | The desk binds **8085** on this host (steps 7 and the pilot handoff). `--port 8080` on `DND-SQL01` is a mistake, not a default. |
| `model` is FULL, so a new database would be FULL, and a daily full backup alone would start a log chain nothing truncates. | Step 3 creates `PMC_PSA` **SIMPLE** for the pilot (D7 addendum says why and when that changes). |
| **ODBC Driver 17** is present, Driver 18 is absent; pyodbc not installed. | Every connection string here names **Driver 17**; no MSI; `pip install pyodbc` stands. Driver 17 does not default to encryption, so `Encrypt=yes` is stated. |
| `sqlcmd` is denied to Claude sessions by this repo's `.claude/settings.json`. | Step 4 previews and applies through pyodbc: `psaspine schema-preview` prints the plan, `psaspine init` applies. No rule changes. The backup is an Agent job the operator creates in SSMS. |
| The PSA task account is named nowhere. The nightly backup folder is nobody's decision yet. | Both are Dada's; see "Do NOT decide". Until named, the steps say `<psa task account>` and `<backup folder>`. |

## The desk's footprint on this host, and the no-clash check

Dada's direction, 26 Sep: on-prem, and **nothing the hospital runs on this
host may be touched or displaced.** So here is everything the desk adds to
`DND-SQL01`, by name, and a read-only check that none of it collides with
something already there. If any line of the check finds a collision, stop at
that line and report it; the fix is a different name or port in this file,
never a change to what was found.

| The desk adds | Name | Never |
|---|---|---|
| One database on the instance | `PMC_PSA` (and `PMC_PSA_TEST` for step 6, dropped after) | any other database read or written, any instance setting changed |
| One login and one database user | `<psa task account>` (Windows), default schema `psa` on `PMC_PSA` only | membership of any server role; any right on another database |
| One folder tree | `D:\psa\` (files, drop, logs) and `D:\PMC\sql\` for the database files | anything on `C:` |
| One listening port, one address | **8085** on `127.0.0.1` or the one LAN address the record names (**8443** once the portal handoff puts HTTPS on it) | 8080, `0.0.0.0`, any port `Get-NetTCPConnection` shows listening |
| Scheduled tasks | all named `PSA-…` (`PSA-Desk`, `PSA-MailPickup`, `PSA-Rules`, `PSA-Notify`, `PSA-Retention`) | editing or disabling any existing task |
| One SQL Agent job | `PSA-Backup-PMC_PSA` | editing any existing job |
| Python packages | `pyodbc` into `C:\PMC\Python312` | a system-wide install; any other package |

The check, read-only, before step 2 (**1b**):

```powershell
# ports: 8085 must be absent from this list; 8080's owner is left alone
Get-NetTCPConnection -State Listen | Sort-Object LocalPort | Select-Object LocalAddress, LocalPort, OwningProcess
# names: none of these may exist yet
Get-ScheduledTask | Where-Object TaskName -like 'PSA-*' | Select-Object TaskName, State
Test-Path D:\psa; Test-Path D:\PMC\sql
# SQL: the database, the login and the job must not exist; the instance's memory cap is read, not set
Invoke-Sqlcmd is denied here; run these in SSMS as the operator and paste the results:
--   SELECT name FROM sys.databases WHERE name LIKE 'PMC_PSA%';
--   SELECT name FROM sys.server_principals WHERE name LIKE '%psa%';
--   SELECT name FROM msdb.dbo.sysjobs WHERE name LIKE 'PSA-%';
--   SELECT value_in_use FROM sys.configurations WHERE name = 'max server memory (MB)';
```

**Pass:** 8085 not listening; no `PSA-*` task; neither folder; no such
database, login or job; the memory figure written into the reply. The desk's
own process is small (one Python process, tens of MB; INFERRED) and its
database is small (the D7 record's estimate is ~1 GB a year); neither is
expected to change what the HIS gets from this host, and the memory figure is
recorded so that claim can be checked later rather than assumed.

## Before you start

- **The instance.** `DND-SQL01\PMC_SS` carries the live HIS and eight other
  databases (above). This sitting adds a *database* to it and touches nothing
  in any of them. The script refuses any database but `PMC_PSA` by name.
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

**1b. The no-clash check** (above). **Pass:** every line clean, memory figure
in the reply.

**2. CHANGE: pyodbc.** Driver 17 is already there (MEASURED, 26 Sep); only
the Python package is missing:

```powershell
C:\PMC\Python312\python.exe -m pip install pyodbc
C:\PMC\Python312\python.exe -c "import pyodbc;print(pyodbc.version, pyodbc.drivers())"
```

**Pass:** `ODBC Driver 17 for SQL Server` in the list. If `pip` has no route to
PyPI, say so in the reply: the wheel can be handed over on the next sitting.

**3. CHANGE: the database and the desk's login.** In SSMS, as `sysadmin`,
`@Apply`-style — read, then run. The files go on `D:`, not beside the HIS on
`C:`; the folder is the operator's to create first (`D:\PMC\sql` is the shape
SQL01 used for the Orthanc copy; the record may name another):

```sql
CREATE DATABASE PMC_PSA
    ON PRIMARY (NAME = PMC_PSA, FILENAME = N'D:\PMC\sql\PMC_PSA.mdf')
    LOG ON     (NAME = PMC_PSA_log, FILENAME = N'D:\PMC\sql\PMC_PSA_log.ldf');
-- SIMPLE for the pilot: a daily full backup is then the whole story, and the
-- log cannot grow unbounded. FULL plus log backups is the go-live change
-- (D7 addendum); it is one ALTER and one Agent job, made when the pilot ends.
ALTER DATABASE PMC_PSA SET RECOVERY SIMPLE;
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

**4. CHANGE: the schema.** Preview first, as the file insists. Through
pyodbc, since `sqlcmd` is denied to Claude sessions in this repo and that rule
stands; the same script, the same switches, run by `psaspine`:

```powershell
cd D:\dnd-poo
git pull origin claude/psa-ticketing-build
cd platform\psa-spine
$py = 'C:\PMC\Python312\python.exe'
$db = 'Driver={ODBC Driver 17 for SQL Server};Server=DND-SQL01\PMC_SS;Database=PMC_PSA;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes'
& $py -m psaspine schema-preview $db
```

Run **as the task account** (or as a user given `db_owner` on `PMC_PSA` with
default schema `psa` for the sitting, revoked after): the desk refuses a login
whose default schema is not `psa`. **Pass:** `PREVIEW ONLY … 73 tables, 25
indexes, 4 triggers … Existing objects in [psa] right now: 0`, and nothing
created. Then apply:

```powershell
& $py -m psaspine init $db
```

which runs the same script with `@Apply = 1` and `@AllowExisting = 1`.
**Pass:** `ready: SQL Server, Driver=…;Server=DND-SQL01\PMC_SS;Database=PMC_PSA`,
and in SSMS `SELECT COUNT(*) FROM sys.tables WHERE schema_id = SCHEMA_ID('psa')`
returns 73, `SELECT COUNT(*) FROM sys.triggers` 4. Run `init` once more:
**Pass:** the same line, and the counts unchanged (every object is guarded).
If Dada prefers the script run by hand in SSMS with `@Apply` edited on a copy,
that is the same result by another road; never edit the committed file.

**5. CHANGE: seed and accounts.** Everything the pilot handoff did to the file,
done to the database. The connection string below is the only one this desk
uses; it holds no secret.

```powershell
$env:PSA_ATTACHMENT_DIR = 'D:\psa\files'
& $py -m psaspine setup-board $db --board UNROUTED
& $py -m psaspine setup-board $db --board IT_HELP
& $py -m psaspine create-local-account $db --username <sysadmin> --sysadmin
& $py -m psaspine create-local-account $db --username <technician>
```

Run these as step 4 was run. `TrustServerCertificate=yes` is for the
instance's self-signed certificate (INFERRED; if the instance carries a
CA-issued certificate, drop it). The passwords at the two prompts are typed by
the operator, never by a Claude session. **Pass:** each account signs in at
step 7.

**6. The test suite, against the real instance.** The one step that turns NOT
VERIFIED into MEASURED, and the reason for a separate test database:

```sql
CREATE DATABASE PMC_PSA_TEST
    ON PRIMARY (NAME = PMC_PSA_TEST, FILENAME = N'D:\PMC\sql\PMC_PSA_TEST.mdf')
    LOG ON     (NAME = PMC_PSA_TEST_log, FILENAME = N'D:\PMC\sql\PMC_PSA_TEST_log.ldf');
ALTER DATABASE PMC_PSA_TEST SET RECOVERY SIMPLE;
ALTER DATABASE PMC_PSA_TEST SET READ_COMMITTED_SNAPSHOT ON;
USE PMC_PSA_TEST;
CREATE USER [PMCNE\<operator>] FOR LOGIN [PMCNE\<operator>] WITH DEFAULT_SCHEMA = psa;
ALTER ROLE db_owner ADD MEMBER [PMCNE\<operator>];
```

```powershell
cd D:\dnd-poo\platform\psa-spine
$env:PSA_TEST_DB = 'Driver={ODBC Driver 17 for SQL Server};Server=DND-SQL01\PMC_SS;Database=PMC_PSA_TEST;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes'
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
registered under the `PSA-…` names in the footprint table, with `$db` in place
of `D:\psa\spine.db` and `PSA_ATTACHMENT_DIR` set in the task's environment or
the wrapper it runs. The `serve` task first. `serve` now refuses a port
something else already holds, in a sentence naming the port, so a clash stops
the desk rather than the other service:

```powershell
& $py -m psaspine serve $db --host 127.0.0.1 --port 8085
```

**Never 8080 on this host**: it is the live queue screens' (MEASURED, 26 Sep).
8085 is the desk's port here and in the pilot handoff; if the record assigns
another, use that one everywhere the two files say 8085.
**Pass:** `/login` answers 200 on 8085; the operator signs in with the step 5 account;
a ticket raised on the board appears in
`SELECT TOP 5 work_item_id, board_id, state FROM psa.ticket ORDER BY opened_at DESC`
run in SSMS. Each task shows `Last Run Result 0x0`.

**8. CHANGE: the backup.** `psaspine backup` refuses for SQL Server and says
why; the database is backed up by SQL Server. No Agent job backs up any
database on this instance today (MEASURED, 26 Sep), so this is a **new SQL
Agent job** (Agent is running; Standard Edition has it), created in SSMS by
the operator, one step, daily:

```sql
BACKUP DATABASE PMC_PSA TO DISK = N'<backup folder>\PMC_PSA_full.bak'
  WITH INIT, CHECKSUM, COMPRESSION;
RESTORE VERIFYONLY FROM DISK = N'<backup folder>\PMC_PSA_full.bak' WITH CHECKSUM;
```

`<backup folder>` is Dada's (below); `D:\PMC\backup\PMC_PSA` is the shape of
SQL01's one-off Orthanc copy and is the proposal. Under SIMPLE recovery a
daily full is the whole chain; nothing else needs truncating. The attachment
folder `D:\psa\files` keeps the robocopy from the attachments handoff.
**Pass:** the job runs once by hand and `RESTORE VERIFYONLY` says the backup
set is valid; the reply names the job, its schedule and the folder.

## Do NOT decide

Four of these came back from pre-flight on 26 Sep and are Dada's; the steps
above carry a proposal for each so the sitting can run once Dada says yes or
names otherwise:

- **The PSA task account** (step 3, step 7): which AD account the desk's
  tasks run as. Not named anywhere in the record or the repo; whether one
  exists is NOT VERIFIED. Dada names it, or says to create one.
- **The desk's port on this host**: 8085 proposed, 8080 refused by the estate.
- **Recovery model**: SIMPLE for the pilot proposed; FULL plus log backups at
  go-live. Dada may want FULL from day one; then step 8 gains a log-backup job
  every 15 minutes and the reply says so.
- **The backup folder and volume**: `D:\PMC\backup\PMC_PSA` proposed; the
  long-term volume is the record's.
- Whether the HIS and the desk share an instance at all. Dada decided "the
  SQL we have"; the D7 addendum records that the instance is the HIS's, and
  the alternative (a second, free instance on the same host) if that is
  reconsidered.
- Whether any other database's recovery model or backup changes. They do not,
  here.
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
