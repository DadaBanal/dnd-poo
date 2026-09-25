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

*(filled in at the foot of this file once the suite is green on both stores;
see the last commit touching it.)*
