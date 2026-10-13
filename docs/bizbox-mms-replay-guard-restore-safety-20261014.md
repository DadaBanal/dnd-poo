# The replay guard as I specified it is not restore-safe — anchor it to the row, not a side table

**Revises:** my own replay-refusal condition, accepted as binding in SQL01's `d1f6ef1`. **Second
revision of my own advice in this thread, and better issued before it is built than after.**
**Also corrects:** my host-move wording, which I said was mine to fix.

**Measured 14 Oct 2026**, `DND-SQL01\PMC_SS`, read-only, controls both ways.
Script: `scripts/Probe-RestoreHistory-20261014.py`.

---

## 1. The defect

I specified a **consumed-`change_id` table in `LiveDB_PMC`**, written by the procedure, refusing any
id already applied. SQL01 asked WS36 whether the spine could mint a duplicate id. **The other
direction is the problem, and nobody had looked at it: that table can go back in time.**

| MEASURED, from `msdb` history | |
|---|---|
| Restores **into `LiveDB_PMC`** | **2** — 9 Jul and 16 Jul 2026 |
| Restores **into `TrainingDB_HIS8`** | **35**, most recent **12 Oct 2026** |
| `LiveDB_PMC` recovery model | **FULL** — 196 full, 216 differential, **5,175 log** backups, latest log 14 Oct 05:15 |
| `PMC_PSA` recovery model | **SIMPLE** — **57 full backups, no log backups at all** |
| `TrainingDB_HIS8` recovery model | SIMPLE |
| Controls | a destination database that cannot exist returned 0; `backupset` holds 10,572 rows, so the history is genuinely readable |

**Three consequences, and the third is the one that matters most.**

1. **A `LiveDB_PMC` restore un-consumes the ids.** It has happened twice, and with 15-minute log
   backups a point-in-time restore is available at any moment. After one, previously-applied
   `change_id`s are absent from the side table, so the guard permits a second application of a change
   the spine still records as applied once.
2. **Every training refresh destroys the proving-step artefacts.** `TrainingDB_HIS8` has been
   restored from live **35 times, most recently two days ago**. If `psa.sp_apply_change` and its
   consumed-ids table live there for build rule 2, **each refresh wipes both.** Operational rather
   than security, but it means the procedure must be re-created after every refresh, and a proving
   run that silently used a wiped table proves nothing.
3. **The two sides of the change ledger cannot be restored to a matching instant.** The desk's record
   of what was applied is in `PMC_PSA` — **SIMPLE recovery, full backups only, so no
   point-in-time restore at all.** BizBox's record is in `LiveDB_PMC` — **FULL recovery with
   15-minute logs.** After a restore of either, the two disagree about what has been applied, with
   **no granularity in common to reconcile them to.** The replay guard sits on the `LiveDB_PMC` side
   of that gap.

## 2. The fix — anchor idempotency to the data, not beside it

**A separate consumed-ids table is the wrong mechanism precisely because it can diverge from the data
it is protecting.** The procedure already returns `ext_ref`. Write that `ext_ref` onto **the BizBox
row the change actually modifies**, and detect double-application by reading **that row**, not a
ledger beside it.

| | Side table | `ext_ref` on the affected row |
|---|---|---|
| After a `LiveDB_PMC` restore | the marker rolls back, **the change rolls back too** → guard now permits re-applying a change that **is** absent. Divergent | marker and change roll back **together**. If the change is gone it **should** be re-appliable — correct by construction |
| After a training refresh | table wiped silently | the column comes back with the data, consistently |
| Needs a second object to maintain, back up, reconcile | yes | **no** |

**Restore-consistency falls out of it rather than being engineered.** The guard cannot disagree with
the data because it *is* the data.

Mechanically: on apply, stamp `ext_ref` on the row (or rows) written; before applying, refuse when
the target row already carries this `change_id`'s `ext_ref` — `ok = 0`, same contract, same refusal
shape. No side table, no secret, no cross-database read.

**Where it needs a column** is the honest cost: the `iw*` tables have no `ext_ref` field, so this
needs either a nullable column added to the tables a change can touch — a schema change to the
vendor's live database, which is a materially bigger decision than a table in `psa` and **is Dada's
call, not a detail** — or a mapping table in `psa` that is **itself** restore-consistent with
`LiveDB_PMC` because it lives in the same database and is restored with it.

**The second option is the cheap one and it keeps the property.** A `psa` table in `LiveDB_PMC`
holding `(change_id, ext_ref, applied_at, target_key)` is restored *with* the `iw*` rows it describes,
so the two never diverge — which the `PMC_PSA` copy cannot be. That is the same table I originally
specified, **but the reason it works is that it shares a restore boundary with the data, not that it
is a ledger** — and that reason is what I failed to state, and what would have been lost the first
time somebody suggested "move it to `PMC_PSA` beside the other change tables", which would have
quietly broken it.

**So: keep the table in `LiveDB_PMC` schema `psa`, and record WHY** — it must share a restore
boundary with `dbo.iw*`. Never in `PMC_PSA`.

## 3. The host-move wording, corrected — mine to fix, as stated

My earlier note said moving the desk to another host "needs a domain account **or a SQL login**",
which reads as two supported alternatives. **It is not, now that the guard refuses any write string
carrying `uid=`.** Corrected:

> `DND-SQL01\psa_desk` is a **local** Windows account and does not travel. Moving the desk to another
> host requires a **domain** Windows account, which keeps trusted authentication and needs no change
> to the guard. **A SQL login is not a drop-in alternative** — the inverted guard refuses any write
> string carrying an explicit `uid=`, by the decision of 14 Oct 2026, and taking that route means
> **deliberately changing the guard**, not merely changing a connection string.

## 4. Still not measured

- **Whether the spine can mint a duplicate `change_id`** after a reset, reseed or restore. SQL01 has
  put that to WS36; it is theirs and it is the other half of this.
- **Why `LiveDB_PMC` was restored on 9 and 16 July 2026.** Two restores into the live clinical
  database is worth knowing the reason for; I read the history, not the cause.
- **Whether `PMC_PSA` being SIMPLE recovery is deliberate.** It holds the desk's record of every
  change applied to the vendor's live database and **cannot be restored to a point in time.** Stated
  once, measured, no recommendation attached.

Read-only throughout. Nothing built, nothing changed.

*Prepared by the Bizbox Chat session on DND-SQL01, 14 Oct 2026. No patient identifiers, no staff
names, no passwords, no connection strings, no addresses or topology.*
