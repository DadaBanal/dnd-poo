# WS36 — the SQL Server port, the desk importer and the uplift evidence

**9 September 2026.** Continues `WS36-ticketing-handover-20260909.md`, which
stays current for everything it says about the constraint and the fence. This
document records what was built against it, the decisions taken on the way, and
what a person with a route to `DND-SQL01` has to do next.

## The constraint held

**[MEASURED]** No environment on this account has a network route to
`DND-SQL01\PMC_SS`. Nothing in this work was executed against a SQL Server, and
no claim below that concerns the server's behaviour is anything but
**NOT VERIFIED**. What was built is a script for somebody who has a route.

## What is now in the repository

| | |
|---|---|
| `platform/psa-spine/tools/sqlite_ddl.py` | A strict reader for the SQLite DDL. No default branch anywhere in it. |
| `platform/psa-spine/tools/sqlite_to_tsql.py` | The translator, and the `--check` drift gate CI runs. |
| `platform/psa-spine/tools/tsql-decisions.json` | Every NVARCHAR width and DECIMAL precision, one per column, with the reason. |
| `platform/psa-spine/sqlserver/PMC_PSA_Spine_SqlServer.sql` | **Generated.** Do not edit. |
| `platform/psa-spine/psaspine/tickets.py` | The desk-export importer. |
| `reports.uplift_evidence` | Effort by contract basis, per entity, per month. |

**[MEASURED]** `python3 tests/test_spine.py` passes 83 tests, up from 23. The
whole pipeline runs end to end on the synthetic fixtures: 15 register rows in,
15 work items out; 13 export rows in, 13 tickets out; five reports and five
dependency notices written.

## Running the port — for whoever has the route

```
sqlcmd -S "DND-SQL01\PMC_SS" -d PMC_SS -i PMC_PSA_Spine_SqlServer.sql
```

1. **Run it as it stands first.** `@Apply = 0`. It prints the plan — 33 tables,
   2 indexes, 2 triggers, in creation order — and changes nothing.
2. **Read the plan, then set `@Apply = 1`** at the top of the file and run again.
3. It refuses if the connected database is not `PMC_SS`, and refuses if anything
   already exists in the `psa` schema. To fill in what is missing after a partial
   run, set `@AllowExisting = 1` as well; every object is guarded individually.
4. The whole apply is one transaction with a verify gate: if the object counts do
   not match what the script intended, it rolls back and throws. A half-created
   schema is worse than none.
5. The rollback is at the foot of the file, commented out, in dependency order.

It creates **structure only** — no fee amount, no board owner, no signed clinical
floor, no enforced SLA target. Each of those is a decision with a name attached.

### What to check once it is up

**NOT VERIFIED, all of it.** These are the things that would tell us the port is
sound, and none can be checked from here:

- The two triggers actually fire. Insert a variation-path ticket with no
  variation, then try to log a time entry against it, then try to close it. Both
  should throw 50001 and 50002.
- `TRY_CONVERT` accepts both date shapes on that server's collation and language
  settings. The computed `_parsed` columns are deliberately **not** persisted, so
  a determinism disagreement cannot block the deployment.
- `LTRIM(RTRIM(...))` was used instead of `TRIM()` because the SQL Server version
  on `DND-SQL01` is not known from here. If it is 2017 or later, `TRIM()` is
  available and the translator can be told so in one line.

## Decisions taken, and how to overrule them

Each of these is written down in one place so it can be argued with, rather than
being spread through a generated file.

| Decision | Where | To change it |
|---|---|---|
| `INTEGER PRIMARY KEY` → `INT IDENTITY(1,1)` | `sqlite_to_tsql.py` | It is a rowid alias; the values are generated either way |
| NVARCHAR widths, by class | `tsql-decisions.json` | Edit the class or the column, regenerate |
| `DECIMAL(19,4)` for money, `(9,4)` for EAC%, `(9,2)` for hours | `tsql-decisions.json` | Same |
| Dates stay text, parsed column beside | `tsql-decisions.json` classes `DATE_TEXT` / `TIMESTAMP_TEXT` | Same |
| `BEFORE` → `AFTER` + `ROLLBACK` + `THROW` | `sqlite_to_tsql.py` | See below — this one has a real consequence |
| Priority matrix | `psaspine/tickets.py`, as a table | Edit the table; one place, nine rows |

**The trigger difference is not cosmetic. [INFERRED]** SQLite's `BEFORE` trigger
refuses the offending statement and leaves the transaction intact. SQL Server has
no `BEFORE` trigger, so the port uses `AFTER` with a rollback: the write is still
refused, but a caller who batched that insert with other work loses the other
work too. That is the right trade — a gate that yields inside a batch is not a
gate — but anyone writing an application against `psa` needs to know it.

## One thing found on the way

**[MEASURED]** The close trigger guards an `UPDATE`. A ticket that arrives from a
desk export **already closed** on the variation path with no variation attached
is an `INSERT`, so it never passes through the gate.

That is correct and was left alone. Historical exports are full of already-closed
work, and a schema that refused to import history would simply not be used. But
it is a real hole in the commercial argument, so those rows now carry an ERROR
finding at import and appear on the uplift report under **"Closed on the
variation path with no variation"** — which is exactly the list of work already
given away unless somebody raises a variation for it.

If that is judged wrong, the fix is a third trigger on `INSERT ON ticket` in
`schema/005_ticket.sql`, and the port picks it up with no further work. It is not
Dada IT's call to make quietly, which is why it is written here instead.

## Rules that were not relaxed

Named because a port is exactly where they get relaxed by accident. Each is
asserted by a test.

- **No live board without a named owner and deputy.** Fifteen boards seed, none
  live, and the schema refuses to make one live without both names.
- **No BASELINE catalogue item without a baseline heading.** Twenty-one seed
  UNKNOWN and stay UNKNOWN. The desk importer does not file PACS under the
  nearest of the nine headings; it lists it as a decision somebody owes.
- **No signed clinical floor.** All four seed PROPOSED, and the importer applies
  none of them to any priority. The import run says so out loud each time, so
  silence is never read as "the floors are working".
- **No enforced SLA target.** Twenty-one seed with `enforced = 0`.
- **Flags are counted, never filtered.** Both importers exit non-zero if rows in
  do not equal rows out.

## The fence

**[MEASURED]** No API key was used, read or written. `psaspine/tickets.py` reads
an export file; there is no HTTP client in the module and a test asserts the
absence of credential-shaped code. **Both TeamsWork keys should still be
rotated** — that action is not discharged by anything here.

No patient identifier, no credential and no internal IP address is committed. CI
greps for private network addresses across the whole tree.

## Still undecided, and still not for the agent to decide

Unchanged from the ticketing handover, plus one:

- Whether the variation is approved.
- Who owns each board, and who deputises.
- Whether the clinical floor list is signed, and by whom.
- Whether PACS, imaging and medical gas sit inside any baseline heading. Twenty-one
  catalogue items and, on the synthetic export, three tickets wait on that ruling.
- **The available-capacity denominator.** The uplift report prints no percentage
  without one and will not invent one. It is a decision to be initialled, not a
  measurement to be taken.
