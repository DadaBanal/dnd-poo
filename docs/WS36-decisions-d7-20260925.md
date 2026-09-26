# WS36 — D7 closed: the desk runs on the SQL Server PMC has

**25 September 2026.** Supersedes the D7 row of
`WS36-decisions-d4-d5-20260922.md`, which stays as written for D4, D5 and D6.
The programme record in OneDrive `Documents/Claude` remains the master; this is
the repo side, for the decision whose evidence is code in this repository.

---

## D7 — SQLite, SQL Server Express, or an existing instance. **CLOSED.**

**Decision: the existing instance, `DND-SQL01\PMC_SS`, in a database of its
own, `PMC_PSA`, schema `psa`.** Dada's direction, 25 Sep 2026: *"lets add it on
the sql database that we have."* SQLite stays as the store for tests, for a
laptop, and for the pilot until the sitting below moves it.

**Why a separate database on the same instance, and not a schema inside
`PMC_SS`.** The earlier port script targeted `PMC_SS` itself, when the spine was
imagined as a commercial record beside the imaging index. It is now the whole
desk: tickets, notes, files' metadata, sessions, audit. Two things that must
never be restored together should not share a database:

- **Restore.** A restore of the imaging index (an Orthanc incident) would roll
  the desk back with it, and a restore of the desk would roll the index back.
  Separate databases restore separately. **INFERRED** from how SQL Server
  restores work; the estate's own backup handoffs (`WS23`) say the same of the
  index.
- **The cap.** SQL Server Express caps *each database* at 10 GB (**VERIFIED**,
  learn.microsoft.com, editions and supported features). Two databases, two
  caps; the desk's growth (INFERRED ~1.2 GB a year, scope §8) never eats the
  index's room.
- **Locks and load.** Orthanc's ODBC index and the desk hold locks in different
  databases. Same instance, so the CPU and the 1 GB Express buffer pool are
  shared; that is the trade Dada chose by saying "the one we have", and it is
  cheaper than a second instance to patch and back up.

What is shared is exactly what should be: the host, its patching, its backup
job, its monitoring and its one SQL Server to keep current.

**What this is not.** Not ADR-001. ADR-001 is the *imaging index's* store
(SQL Server/ODBC → PostgreSQL) and remains **Proposed**; nothing here depends on
it or moves it. D7 is the *desk's* store. The two share the words "SQL Server"
and nothing else.

### Built (MEASURED, this repository, 25 Sep 2026)

| | |
|---|---|
| `psaspine/mssql.py` | The backend: a pyodbc connection wearing sqlite3's surface, a statement translator that refuses what it has not decided, `apply_port()`, `wipe()` for tests. |
| `psaspine/db.py` | `connect()` picks the store from the shape of the target (path or ODBC connection string); `init`, `close`, `table_exists`, `backup` (refuses for SQL Server, pointing at `BACKUP DATABASE`). |
| `tools/sqlite_to_tsql.py` | Three fixes the first real run found (nested block comments, boolean-equality CHECKs, IDENTITY on a checked key); `@Database` variable; `schema/local/` now ported. |
| `sqlserver/PMC_PSA_Spine_SqlServer.sql` | Regenerated: 73 tables, 25 indexes, 4 triggers. |
| `tests/test_spine.py` | `PSA_TEST_DB` runs every test against a SQL Server; nothing else in the tests changed. |
| `README.md` | "On SQL Server (D7, 25 Sep 2026)". |
| `docs/handoffs/HANDOFF-cloud-sql01-WS36-20260925-sqlserver.md` | The sitting that stands the database up and moves the pilot. |

### The one dependency

The zero-dependency rule (D2's shape: standard library, nothing to install) is
kept for SQLite and **broken deliberately, in one place, for SQL Server**:
`pyodbc` plus Microsoft's ODBC Driver for SQL Server, imported only inside
`psaspine/mssql.py` and only when a connection string is used. There is no
standard-library way to speak TDS, and a hand-written ODBC binding over ctypes
would be a credential-adjacent piece of code nobody reviewed. `pyodbc` is
Microsoft's own recommendation for Python (**VERIFIED**, learn.microsoft.com,
"Python SQL driver — pyodbc") and installs from a wheel with no compiler on
Windows. A SQLite desk still needs nothing.

### The authentication

The desk's connection uses **Windows authentication** (`Trusted_Connection=yes`):
the scheduled task's account is the credential and no password exists to keep.
The connection string therefore holds hostnames and names only and may sit in
the task's arguments. A SQL login with a password is used for the test
container here and nowhere else.

### Proof

- The generated port applies to SQL Server 2022 Express 16.0 in a container:
  the gate passes, both refusals (wrong database, second run) refuse, a re-run
  with `@AllowExisting = 1` is a no-op. **MEASURED, 25 Sep 2026.**
- The test suite runs against that server with `PSA_TEST_DB` set. The count at
  close of this record is in its last section, with the SQLite count beside it.
- **NOT VERIFIED on `DND-SQL01`.** No session here has a route. The handoff's
  step 6 is that run and its reply is where this becomes MEASURED there.

### What stays open

- **D6** — whether Phase A is funded as a variation, at what number. Commercial,
  Dada's.
- Whether `PMC_PSA` joins the index's `BACKUP DATABASE` job or gets its own,
  and the log-backup cadence. The handoff proposes; SQL01 measures the job that
  exists (**NOT VERIFIED** from here).
- The move of the pilot's data from `D:\psa\spine.db` into `PMC_PSA`, if the
  pilot has begun on SQLite before the sitting: there is no importer between the
  two stores yet, deliberately. The pilot handoff's step 0 stops on a database
  that holds tickets; so does this one.

### Result of the run against SQL Server

**MEASURED, 25 Sep 2026**, SQL Server 2022 Express 16.0.4295 (Linux container),
ODBC Driver 18.7, pyodbc 5.3, Python 3.11:

| Store | Tests | Result |
|---|---|---|
| SQLite | 464 | OK |
| SQL Server (`PSA_TEST_DB`) | 464 | OK, 8 skipped (SQLite's own file settings) |

Forty-odd statements changed shape on the way, every one in one of the two
places the README names (the translator, or the code, where a portable spelling
existed: `JOIN … ON` for `USING`, `WHERE NOT EXISTS` for `INSERT OR IGNORE …
SELECT`, `CASE WHEN` for a predicate used as a value, the expression for an
alias in `GROUP BY`). No test's assertion changed; three fixtures did (a commit
before a trigger is walked into, a store path read from the module, a dump read
from the table rather than SQLite's `iterdump`).

---

## Addendum, 26 September 2026 — what the instance is (MEASURED by SQL01)

SQL01's pre-flight of the sitting read the instance. Two premises above were
wrong and are corrected here rather than rewritten, so the reasoning that was
made on them stays visible.

**It is not "the imaging index's instance".** `DND-SQL01\PMC_SS` is **SQL
Server 2022 Standard Edition** (16.0.1190.2, collation
`SQL_Latin1_General_CP1_CI_AS`) and holds nine user databases, all on `C:`:
`LiveDB_PMC` (the live HIS), `PMC_Apps` (payroll), `PMC_Reporting`,
`ReportServer`, the Orthanc index and four more. The "cap" argument above
therefore does not apply: Standard has no 10 GB limit. The separation argument
applies **more**, not less: the scope document's own criterion for D7 was
*"separation from the live HIS, which carries a 173-finding audit, `sa`
enabled and the Domain firewall off"*, and this instance **is** the HIS's.

**What that means for the decision.** Dada's direction was "the SQL we have",
and it stands; this addendum makes sure it stands knowingly. The desk in its
own database on the HIS's instance shares the instance's CPU, memory, patching
window, `sa` posture and restarts with the HIS. A restore or an outage of one
does not roll back the other, but a restart of the instance takes both down. If
that coupling is not wanted, the alternative is cheap and on the same host: a
second named instance (**SQL Server Express is free**) for `PMC_PSA` alone,
patched with the host, with its own `sa` disabled. The handoff runs against
`PMC_SS` unless Dada says "second instance", in which case its step 3 changes
the instance name and nothing else.

**Recovery model.** The instance's `model` database is FULL, so `PMC_PSA` would
inherit FULL, and a daily full backup alone would then start a transaction-log
chain that nothing truncates (VERIFIED, learn.microsoft.com, "Recovery
models": the log grows until a log backup). The handoff creates `PMC_PSA`
**SIMPLE for the pilot**: the desk's data are dual-run with Kitameraki and a
day's loss is recoverable from it; one daily full backup is then the whole
story. At go-live the change is `ALTER DATABASE … SET RECOVERY FULL` plus an
Agent job taking log backups every 15 minutes, and the record decides that day.

**Files on `D:`.** Every database on the instance sits on `C:`; `PMC_PSA` is
created with its files on `D:`, so the desk's growth never competes with the
system volume the HIS lives on.

**Port.** 8080 on `DND-SQL01` is the live queue screens' (`http.sys`, IIS site
`PMC-Queue`); the desk binds **8085** there. The default in `psaspine serve`
stays 8080 for a laptop; the handoffs name 8085.

**Driver.** ODBC Driver 17 is installed, 18 is not; the connection strings name
17. The backend needs neither in particular.

**Still Dada's (the handoff's "Do NOT decide")**: the PSA task account's name,
the backup folder and volume, whether SIMPLE for the pilot is accepted, and
whether the HIS's instance is accepted now that it is known to be the HIS's.
