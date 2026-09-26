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

### Sitting 1, part 1: 2026-09-26, 15:26 UTC. **BLOCKED at step 3 (the login): the task account does not exist**

SQL01, the local Claude Code session on `DND-SQL01`, at `a8cfa21`, run per the 26 Sep
runbook. Operator's instruction, pasted verbatim: *"Run the sittings in its order, using its
defaults for any decision I have not answered. Its first rule applies to every line: nothing
the hospital already runs on this host is touched."*

| Step | State | Evidence |
|---|---|---|
| 0 | **PASS** | `D:\psa\spine.db`: `no file` (MEASURED) |
| 1 | **PASS** | Edition `Standard Edition (64-bit)`; ProductVersion `16.0.1190.2`; Collation `SQL_Latin1_General_CP1_CI_AS`; `DB_ID('PMC_PSA')` `NULL` (MEASURED) |
| 1b | **PASS** | 8085 not listening (8086, 8087 and 8443 free as well; 8080 listening and left alone). No `PSA-*` task among 667 visible from an elevated session. `D:\psa` and `D:\PMC\sql` absent. No database `PMC_PSA%`, no server principal `%psa%`, no `PSA-%` job; a control database name returns 0. `max server memory (MB)` value_in_use = **49152** (read, not set). All MEASURED |
| 2 | **PASS** | `pip install pyodbc` from PyPI: **pyodbc 5.3.0** (cp312 win_amd64 wheel, 70 kB) into `C:\PMC\Python312`, no dependencies, 11 → 12 packages. `pyodbc.drivers()` lists `ODBC Driver 17 for SQL Server` (MEASURED) |
| 3 (database) | **PASS** | Created `D:\PMC\sql`, `D:\psa\files`, `D:\psa\drop` and `D:\psa\logs`. Previewed, then applied, three statements through `System.Data.SqlClient` as sysadmin: the repo's `sqlcmd` rule is untouched. `CREATE DATABASE PMC_PSA` on `D:\PMC\sql`, `SET RECOVERY SIMPLE`, `SET READ_COMMITTED_SNAPSHOT ON`. Read back: `ONLINE`, `SIMPLE`, RCSI 1, data and log 8 MB each at `D:\PMC\sql\PMC_PSA.mdf` / `PMC_PSA_log.ldf`, created 15:21 UTC (MEASURED). No ACL change was needed. The SQL service wrote into `D:\PMC\sql` under the folder's inherited ACL and set its own explicit ACL on the two files (inheritance off, 3 entries) (MEASURED). Database owner: the operator's login, not named here (MEASURED); whether to hand it to another principal is Dada's |
| 3 (login) | **BLOCKED** | The runbook's default is a local account `psa_desk`, created by the operator with a password typed at a prompt. It does not exist: `Get-LocalUser` finds it absent, a control name also returns nothing, and the built-in -500 account is found as an anchor (MEASURED). A Claude session does not create accounts or type passwords |
| 4 | **PASS, by the alternative road; SQL01's decision, reversible** | The handoff says: "If Dada prefers the script run by hand in SSMS with `@Apply` edited on a copy, that is the same result by another road; never edit the committed file." Dada had not stated that preference. It is also not one of the runbook's two named resolutions for step 4. SQL01 took this road itself, through pyodbc rather than SSMS, because neither named resolution can work here. `connect()` refuses any login whose default schema is not `psa` (`psaspine/mssql.py:778-787`, MEASURED). A sysadmin always has default schema `dbo` (VERIFIED, https://learn.microsoft.com/sql/t-sql/statements/create-user-transact-sql and https://learn.microsoft.com/sql/t-sql/statements/alter-user-transact-sql, Remarks: "All members of the sysadmin fixed server role have a default schema of `dbo`"). This operator is sysadmin (MEASURED). So "the operator with `db_owner` and default schema `psa` for the sitting" cannot work. The committed script ran through pyodbc as the operator. Preview (unchanged file): `PREVIEW ONLY … 73 tables, 25 indexes, 4 triggers. Existing objects in [psa] right now: 0.` Apply (in-memory copy, `@Apply = 1`): `Created: 73 tables, 4 triggers, 25 indexes in [psa].` Read back: 73 tables, 4 triggers, 25 indexes, 0 rows; schema `psa` owned by `dbo`. A second run of the same copy refuses: `schema [psa] already holds 77 objects`. That copy set only `@Apply`, not `@AllowExisting`, so this refusal stands in for the handoff's Pass. `init`'s `ready:` line and its idempotent second run were not produced; they need the task account. The file as executed (the CRLF working copy) has sha256 `0a327fba…29aa10`. It is git blob `6efd4bc`, identical to HEAD (whose LF blob hashes to `2995368d…ab6d8218`), and the tree is clean (all MEASURED). Ownership is why this road was taken: the script's `CREATE SCHEMA psa` has no `AUTHORIZATION` (line 216), so if the task account applied it, that account would own the schema after any temporary `db_owner` was revoked (INFERRED from the SQL Server ownership rules). One warning from the apply: `The maximum key length for a clustered index is 900 bytes. The index 'PK_api_alert' has maximum length of 928 bytes.` (MEASURED). That is a schema finding for the generator: in SQL Server's own words, "the insert/update operation will fail" for some large key values (MEASURED, the warning's text) |
| 5, 6, 7 | **NOT RUN** | Each runs through the desk's `connect()`, so each needs the task account (step 6's test user too, for the reason in step 4) |
| 8 | **NOT RUN** | Kept in order, after 7. `D:\PMC\backup\PMC_PSA` not yet created; no job created |
| `D:\psa\test-sqlserver-20260925.txt` | **none** | step 6 not run |

**What the operator does to unblock it** (elevated PowerShell on `DND-SQL01`; the password
goes into the prompt and nowhere else):

```powershell
$pw = Read-Host -AsSecureString 'Password for the PSA desk task account'
New-LocalUser -Name psa_desk -Password $pw -Description 'WS36 PSA desk task account' -UserMayNotChangePassword -PasswordNeverExpires
Remove-Variable pw
```

Then grant "Log on as a batch job" to `psa_desk`: `secpol.msc`, Local Policies, User Rights
Assignment, "Log on as a batch job", Add. No admin membership. `gpresult /x` has no
user-rights assignment in any GPO, while its extension data is present as a control (MEASURED).
So the local grant should stay (INFERRED). Today the right is held by four built-in groups
(Administrators, Backup Operators, Performance Log Users, IIS_IUSRS), not by Users, and no deny
right is set (MEASURED, `secedit /export`). So `psa_desk` needs the explicit grant.

**The payroll watchdog noticed.** `Watch-PMCBridge.ps1` alerts every 24 h for any online
database that is not in its expected list and has no recent FULL backup (lines 156 and 357-365,
read-only, MEASURED). The infra session reports that it emailed Dada "Database PMC_PSA has no
recent FULL backup" at 23:25 host time, four minutes after `PMC_PSA` was created (theirs; the
email itself is NOT VERIFIED here). Step 8 quiets it. SQL01 has told the infra session it will
say when step 8 has run, so that `PMC_PSA` can be added to the watchdog's expected list by that
session's gated edit. SQL01 does not touch the watchdog.

**What SQL01 does next, in the next sitting:** confirm the account, then step 3's login
(`[DND-SQL01\psa_desk]`, user on `PMC_PSA` only, default schema `psa`, `db_datareader`,
`db_datawriter`, `EXECUTE`, `VIEW DEFINITION`; no `db_owner`, because the schema is already
dbo's). Then `PMC_PSA_TEST` on `D:\PMC\sql` with `psa_desk` as its test user, and steps 5 to 8.
Steps 5 and 6 need the operator in one PowerShell window running as `psa_desk` (`runas`, with
the password typed there), because `create-local-account` prompts for passwords and the suite
must connect as a non-sysadmin.

Sittings 2 to 4: not started; each depends on sitting 1.

### Sitting 1, part 2: 2026-09-26, 15:38 UTC. **Step 8 PASS, run ahead of 5 to 7 on Dada's word**

Dada, verbatim: *"step 8 but cant u do the creation"*. Step 8 was run out of order so that
`PMC_PSA` has a verified FULL backup and the payroll watchdog's daily alert stops. On the second
half: a Claude session does not create accounts or set passwords. The operator's part is now one
script, `D:\psa\bin\New-PsaDeskAccount.ps1`: it prompts for the password twice, creates the local
account without admin membership, and logs only that it was created. It parses under Windows
PowerShell 5.1 with 0 errors and is pure ASCII (MEASURED); it has NOT been run. It deliberately
leaves "Log on as a batch job" to `secpol.msc`, because a scripted user-rights import can replace
the holders of other rights, such as "Log on as a service" (INFERRED risk; the GUI adds one name
to one right).

| Check | Evidence |
|---|---|
| Read before change | `PMC_PSA` ONLINE, SIMPLE; no job `PSA-Backup-PMC_PSA`; `D:\PMC\backup\PMC_PSA` absent; 0 backups or restores running; SQL Server Agent (PMC_SS) running (all MEASURED). The instance's backup jobs are owned by `sa` (`sa` enabled, not renamed). Nothing is scheduled at 03:40: the LiveDB log backup runs at :00, :15, :30 and :45, the LiveDB differential at 01:00, 07:00, 13:00 and 19:00, and `syspolicy_purge_history` at 02:00. The busy window is 22:00 to 23:30: LiveDB FULL at 22:00 (its last three runs took 1 min 47 s to 1 min 53 s), SystemAndSSRS FULL at 22:30, Stock Snapshot at 23:30 (all MEASURED) |
| Preview, then apply | One new job, `PSA-Backup-PMC_PSA`: owner `sa`, enabled, category `[Uncategorized (Local)]`, target `(local)`. One T-SQL step in `master`: `BACKUP DATABASE [PMC_PSA] TO DISK = N'D:\PMC\backup\PMC_PSA\PMC_PSA_full.bak' WITH INIT, CHECKSUM, COMPRESSION;` then `RESTORE VERIFYONLY FROM DISK = N'…' WITH CHECKSUM;`. On failure it quits reporting failure; the instance has no Agent operators, so the payroll watchdog is the notifier. Schedule `PSA-Backup-PMC_PSA`: **daily at 03:40:00**. Read back: job enabled, owner `sa`, 1 step, 1 target server, schedule attached and enabled. The other jobs: 8, unchanged in count (all MEASURED) |
| Run once by hand | The job succeeded. Step 1: `BACKUP DATABASE successfully processed 514 pages in 0.492 seconds` … `The backup set on file 1 is valid.` `msdb.backupset`: type `D`, `is_copy_only` 0, `has_backup_checksums` 1, finished 23:37:55 host time (15:37 UTC); 4,284,416 bytes, 626,966 compressed. File `D:\PMC\backup\PMC_PSA\PMC_PSA_full.bak`, 643,072 bytes, sha256 `991374490C9142E05F87204A4E29E8998CCC5F39C1541F3FF5D40B9B351E1E03` (all MEASURED) |
| Watchdog | The infra session was told at once, as it asked, so it can add `PMC_PSA` to `Watch-PMCBridge.ps1`'s expected list by its own gated edit. SQL01 does not touch that script |

Two properties of the job as the handoff specified it, stated once. `WITH INIT` keeps one file,
overwritten daily, so a failed run leaves no good backup until the next success (INFERRED from
`INIT` semantics). The database and its backup are on the same host. Retention and an offsite
copy are the record's, as for the Orthanc index. Under SIMPLE recovery, a daily full is the whole
chain.

Still open in sitting 1: step 3 (the login), then 5, 6 and 7, all waiting on the task account.

### Sitting 1, part 3: 2026-09-26, 16:29 UTC. **Steps 3, 4 (init), 5 PASS; step 6 RED; stopped before step 7 as the runbook says**

The operator created the task account with `D:\psa\bin\New-PsaDeskAccount.ps1` ("script has been
run"). Checked read-only: `DND-SQL01\psa_desk` is enabled, password never expires, the user
cannot change it, and it is not in Administrators. It is not a direct member of Users, but Users
contains Authenticated Users and INTERACTIVE, so it gets Users' read rights and interactive
logon. **"Log on as a batch job" is not granted yet**: the right still has its 4 built-in
holders. It is needed only at step 7 (all MEASURED).

| Step | State | Evidence |
|---|---|---|
| 3 (login) | **PASS** | Previewed, then applied as sysadmin: `CREATE LOGIN [DND-SQL01\psa_desk] FROM WINDOWS`; user on `PMC_PSA` with `DEFAULT_SCHEMA = psa`; `db_datareader`, `db_datawriter`; `GRANT EXECUTE, VIEW DEFINITION`. **Pass line:** `default_schema_name` = `psa`. Read back: roles `db_datareader,db_datawriter`; grants `CONNECT, EXECUTE, VIEW DEFINITION`; no server role. No `db_owner`, because `[psa]` is dbo's (MEASURED) |
| 4 (init) | **PASS** | Run as `psa_desk` by the operator (`runas`, password typed there) through `D:\psa\bin\Sitting1-AsDesk.ps1`: `init` twice printed `ready: SQL Server, Driver={ODBC Driver 17 for SQL Server};Server=DND-SQL01\PMC_SS;Database=PMC_PSA` both times, exit 0 (MEASURED, the operator's pasted console and `D:\psa\logs\Sitting1-AsDesk.log`) |
| 5 | **PASS** | `setup-board UNROUTED` and `IT_HELP`: each "added 8 statuses, 12 SLA targets, calendar ALL_HOURS". A re-run added 0, so the command is idempotent. SLA targets are the starter placeholders, `enforced = 0`, for the Service Manager to set. Two break-glass accounts, one sysadmin and one board-scoped technician; the names are not recorded here, and the passwords were typed by the operator at the desk's no-echo prompt. The first attempt at the technician stopped on a password mismatch and wrote nothing; the re-run created it. `psa.local_account` now holds 2 rows: 1 sysadmin, 1 not, 0 disabled. `psa.ticket` holds 0 rows (MEASURED, read-only) |
| 6 | **RED: `FAILED (errors=2, skipped=11)`, 471 run in 450.7 s** | `PMC_PSA_TEST` was created on `D:\PMC\sql` (SIMPLE, RCSI) with `psa_desk` as `db_owner` and default schema `psa`. The handoff names the operator here, but a sysadmin's default schema is always `dbo`. The database was given one normal FULL at creation, because the payroll watchdog's new-database check alerts at once on a database with no FULL and ignores COPY_ONLY backups (`Watch-PMCBridge.ps1` lines 166 and 364). **Both errors are Windows-only and are not the SQL Server backend.** Each is `tearDown` failing `tempfile.cleanup()` with `PermissionError: [WinError 32]` on a SQLite `cli.db` that is still open. Both tests call `psaspine.__main__.main()` in-process, and `main()` opens `conn = db.connect(a.database)` (line 213) but returns from most commands without closing it. Windows cannot delete an open file; Linux can. Reproduced as the operator with **no SQL Server at all** (`PSA_TEST_DB` unset, SQLite only): the same 2 errors, the same `WinError 32` (MEASURED). There are 0 FAILs, so neither test's assertions failed (INFERRED from unittest reporting). The skips: 8 "SQLite's file settings; SQL Server has its own" (the README's 8), 2 "openssl is not on this machine to make a test certificate" (`openssl` is not on `psa_desk`'s PATH), and 1 "this asserts the refusal on a non-Windows host" (MEASURED) |
| 6 (close-out) | **done** | `DROP DATABASE PMC_PSA_TEST` (0 sessions in it), its files gone from `D:\PMC\sql`, and its one backup file deleted. `PMC_PSA` untouched; the instance is back to 10 user databases (MEASURED). The infra session was told when it was created and when it was dropped |
| 7 | **NOT RUN** | The runbook: "The desk does not run on SQL Server on a red suite." It also needs the batch-logon grant |
| 8 | PASS in part 2 | unchanged |

**The fix belongs upstream.** Close the connection in `main()` (one `try/finally` around the
dispatch after line 213), or have the two tests close what they open. Then the re-run is step 6
alone. SQL01 recreates `PMC_PSA_TEST` the same way, and the operator runs
`runas /user:DND-SQL01\psa_desk "powershell.exe -NoProfile -NoExit -File D:\psa\bin\Sitting1-AsDesk.ps1 -TestsOnly"`.
The script gained `-TestsOnly` for this, and it now prints stderr text instead of 8
`System.Management.Automation.RemoteException` lines. Those 8 lines are in today's test file;
they are a Windows PowerShell 5.1 artifact of the wrapper, not test output.

The last 40 lines of `D:\psa\test-sqlserver-20260925.txt`, the 8 wrapper-artifact lines
removed (MEASURED):

```
test_a_p1_fires_at_the_moment_it_is_created (__main__.WorkflowRunnerTest.test_a_p1_fires_at_the_moment_it_is_created) ... ok
test_a_rule_that_was_never_tested_cannot_be_switched_on (__main__.WorkflowRunnerTest.test_a_rule_that_was_never_tested_cannot_be_switched_on) ... ok
test_a_rules_own_status_change_fires_no_further_rules (__main__.WorkflowRunnerTest.test_a_rules_own_status_change_fires_no_further_rules) ... ok
test_escalation_is_successive_events_on_sla_time (__main__.WorkflowRunnerTest.test_escalation_is_successive_events_on_sla_time)
ConnectWise's own pattern: New too long tells dispatch; later still, ... ok
======================================================================
ERROR: test_setup_board_cli (__main__.BoardSetupTest.test_setup_board_cli)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "shutil.py", line 633, in _rmtree_unsafe
PermissionError: [WinError 32] The process cannot access the file because it is being used by another process: 'C:\\Users\\psa_desk\\AppData\\Local\\Temp\\tmpcxafer4o\\cli.db'
During handling of the above exception, another exception occurred:
Traceback (most recent call last):
  File "D:\dnd-poo\platform\psa-spine\tests\test_spine.py", line 3800, in tearDown
    self.tmp.cleanup()
  File "tempfile.py", line 954, in cleanup
  File "tempfile.py", line 934, in _rmtree
  File "shutil.py", line 781, in rmtree
  File "shutil.py", line 635, in _rmtree_unsafe
  File "tempfile.py", line 909, in onexc
PermissionError: [WinError 32] The process cannot access the file because it is being used by another process: 'C:\\Users\\psa_desk\\AppData\\Local\\Temp\\tmpcxafer4o\\cli.db'
======================================================================
ERROR: test_the_cli_imports_and_counts (__main__.ContactsTest.test_the_cli_imports_and_counts)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "shutil.py", line 633, in _rmtree_unsafe
PermissionError: [WinError 32] The process cannot access the file because it is being used by another process: 'C:\\Users\\psa_desk\\AppData\\Local\\Temp\\tmpp7nkbmei\\cli.db'
During handling of the above exception, another exception occurred:
Traceback (most recent call last):
  File "D:\dnd-poo\platform\psa-spine\tests\test_spine.py", line 5830, in tearDown
    self.tmp.cleanup()
  File "tempfile.py", line 954, in cleanup
  File "tempfile.py", line 934, in _rmtree
  File "shutil.py", line 781, in rmtree
  File "shutil.py", line 635, in _rmtree_unsafe
  File "tempfile.py", line 909, in onexc
PermissionError: [WinError 32] The process cannot access the file because it is being used by another process: 'C:\\Users\\psa_desk\\AppData\\Local\\Temp\\tmpp7nkbmei\\cli.db'
----------------------------------------------------------------------
Ran 471 tests in 450.707s
FAILED (errors=2, skipped=11)
```

Sitting 1 stands **BLOCKED at step 6, on the upstream fix**. Everything else is in place:
`PMC_PSA` with its schema, boards and break-glass accounts, the task account's login, and a
verified daily backup.

### Sitting 1, part 4: 2026-09-26, 16:35 UTC. **Step 7 pre-check (read-only): a second code fix, and what else each task waits on**

A correction to part 3: the technician account failed twice before it was created. The first
attempt was a password mismatch; the second was an empty password ("refused: a break-glass
password may not be empty"). Neither wrote anything (MEASURED, `D:\psa\logs\Sitting1-AsDesk.log`).

**Second code fix needed: the three PowerShell task scripts cannot take a connection string.**
`Invoke-PmcMailPickup.ps1:236`, `Send-PmcNotifications.ps1:212` and
`Invoke-PmcAttachmentRetention.ps1:69` each run
`foreach ($p in $Database, $SpineDir) { if (-not (Test-Path $p)) { throw "Not found: $p" } }`.
On this host `Test-Path` on the SQL Server connection string returns `False`; the control,
`Test-Path D:\psa`, returns `True` (MEASURED, Windows PowerShell 5.1). So `PSA-MailPickup`,
`PSA-Notify` and `PSA-Retention` would throw before their first pass. Step 7's "put `$db` in
place of `D:\psa\spine.db`" cannot work for them until the guard skips a connection string.

| Task | Waits on (all MEASURED read-only today unless marked) |
|---|---|
| `PSA-Desk` (`serve $db --host 127.0.0.1 --port 8085`, at start-up) | A green step 6, and "Log on as a batch job" for the task account (not granted; its 4 built-in holders are unchanged). `--port` must always be passed, because the code's default is 8080 (`__main__.py` line 74) |
| `PSA-Rules` (`run-rules $db`, every minute) | The same two, nothing else |
| `PSA-MailPickup` | The `Test-Path` fix. Also the mail handoff's steps 1 to 3, which were never run (its Reply is empty): there is no certificate for Graph in either store, and no app registration or Exchange Mail.Read scope that can be seen from here. Those are the operator's, an Entra admin's and an Exchange admin's. Its `-DropDir D:\psa\mail-drop` differs from the `D:\psa\drop` that sitting 1 created, so one needs choosing |
| `PSA-Notify` | The `Test-Path` fix, the same Graph prerequisites (Mail.Send), and the rules handoff's steps 2 to 4 (never run) |
| `PSA-Retention` (weekly, preview only) | The `Test-Path` fix. `-Apply` also waits for the DPO's periods (sitting 4) |
| The daily copy of `D:\psa\files` (pilot step 8) | A destination. No volume other than `D:` exists, and `C:` is outside the footprint. It is Dada's |

Two findings for the record:
- `D:\psa` and `D:\PMC\backup\PMC_PSA` carry only the ACL inherited from `D:`, which includes
  `BUILTIN\Users` read. The mail and attachments handoffs require the task account,
  Administrators and SYSTEM only, before any `.eml` or attachment lands (MEASURED). That is not
  changed from here.
- For sitting 3 (HTTPS): the `*.pmcne.ph` wildcard is on the host with its private key, but the
  key is marked **non-exportable**, so the portal handoff's `Export-PfxCertificate` route to PEM
  cannot work from this store. `dnd-sql01.pmcne.ph` resolves to this host and is covered by the
  wildcard; `desk.pmcne.ph` has no record (MEASURED by a read-only survey agent today; the key
  flag and the DNS lookups were not repeated by SQL01 itself).

Step 7 can register `PSA-Desk` and `PSA-Rules` once step 6 is green and the batch-logon right is
granted. The other three wait for the `Test-Path` fix and their own prerequisites above.

### Sitting 1, part 5: 2026-09-26, 17:30 UTC. **Step 6 GREEN at `5353316`; the runbook's ACLs set; the batch right granted**

Pulled `claude/psa-ticketing-build` to `4873f6b` (`5353316` plus a settings-only commit).
Dada's instruction: *"Re-run step 6 as you described, then continue sitting 1 from step 7 for
PSA-Desk and PSA-Rules once 'Log on as a batch job' is granted. Set the ACL on D:\psa as the
runbook now says. Then sitting 2."*

| Item | State | Evidence (MEASURED unless marked) |
|---|---|---|
| ACL, runbook "Folded in" | **done** | The existing ACLs were saved first with `icacls /save` (every entry had been inherited from `D:`). Then the runbook's line: `D:\psa` got `/inheritance:r` and `/grant:r` for `DND-SQL01\psa_desk` `(OI)(CI)M`, Administrators F, SYSTEM F; `D:\PMC\backup\PMC_PSA` got the same with `NT SERVICE\MSSQL$PMC_SS` in place of the task account. Read back: both are protected with exactly those three entries, and 0 of their 11 children still grant Users, Everyone or Authenticated Users. Nothing above either folder was touched. The empty `D:\psa\drop` was removed; `D:\psa\mail-drop` is left for the mail script to create |
| "Log on as a batch job" | **granted** | The operator ran `D:\psa\bin\Grant-PsaDeskBatchLogon.ps1 -Apply`. It calls `LsaAddAccountRights`, which adds one right to one account (VERIFIED, https://learn.microsoft.com/windows/win32/api/ntsecapi/nf-ntsecapi-lsaaddaccountrights). Holders went from 4 to 5, and no other user right changed (the script's before/after diff). Its "UNEXPECTED" line was SQL01's comparison bug: `secedit` writes a named local account by name, not `*SID`. It is fixed in the script, and a re-check reads the 4 built-in groups plus `psa_desk`, whose entry resolves to its own SID |
| Step 6 re-run | **PASS** | `PMC_PSA_TEST` was recreated the same way (one FULL at creation; the SQL service wrote it into the newly restricted backup folder, which also proves the new ACL). The operator ran `Sitting1-AsDesk.ps1 -TestsOnly` as `psa_desk`: **`Ran 473 tests in 449.332s` / `OK (skipped=9)`**, exit 0. The skips are the 8 SQLite-settings ones and 1 "this asserts the refusal on a non-Windows host". The 2 openssl skips are gone: the tests found Git's `openssl.exe`. No wrapper-artifact lines this time. Then `DROP DATABASE PMC_PSA_TEST`, and its backup file deleted; 10 user databases remain. The infra session was told at creation and at the drop |
| No password-free road to step 7 | **measured** | An S4U task registered as `psa_desk` by the administrator without a password was refused: `Register-ScheduledTask` answered "Access is denied". That matches Microsoft's rule that an administrator registering an S4U task for a *different* user must supply that user's password (VERIFIED, https://learn.microsoft.com/windows/win32/taskschd/security-contexts-for-running-tasks). Nothing was left behind (0 `PSA-*` tasks after). So step 7's registration is the operator's one password prompt: `D:\psa\bin\Register-PsaTasks.ps1 -Apply` registers `PSA-Desk` (`serve … --host 127.0.0.1 --port 8085` at start-up, restart every minute) and `PSA-Rules` (`run-rules`, every minute) as `psa_desk`, each writing `D:\psa\logs\<TaskName>.log`. Its preview is clean |

The daily copy of `D:\psa\files` still has no destination. The files are on `D:` only, while the
SQL backup covers the metadata (the runbook asks for this line every sitting).
