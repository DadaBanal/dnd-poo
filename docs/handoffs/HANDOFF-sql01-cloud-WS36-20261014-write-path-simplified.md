# HANDOFF — SQL01 → Cloud Build (WS36) — 14 Oct 2026
## The write path, simplified: three mechanisms, each doing one job. Supersedes the replay table.

**Dada, 14 Oct 2026, verbatim:**

> *"if the procedure is too complicated simplify it to many checks isnt good at all it can be secured
> and simplified properly"*

**He is right, and the count is the evidence.** Across Parts 87–93 the write path had collected six
coded refusals, a concurrency token with a fallback, a replay table with a location rule and a
restore-safety analysis, and six verifier controls. **This supersedes §2 and §3 of
`HANDOFF-sql01-cloud-WS36-20261014-two-conditions-on-uniform.md`** — the replay table is withdrawn —
and leaves everything else in that handoff standing.

**What stays is three mechanisms. Each exists because one specific thing goes wrong without it.**

---

## 1. Identity is the grant. Nothing else.

**`psa_desk`, Windows, no password.** One user in each of `LiveDB_PMC` and `TrainingDB_HIS8`, holding
exactly two things:

```sql
GRANT SELECT  ON SCHEMA::psa                 TO [psa_desk];
GRANT EXECUTE ON OBJECT::psa.sp_apply_change TO [psa_desk];
```

**That is the security.** The login can read the desk's views and run one procedure. It cannot
touch a table. Ownership chaining — proven in production on 13 Oct, and now measured in Training
too — means the procedure writes the `iw*` tables without the caller holding any right to them.

**The code-side guard collapses to one condition.** `write_odbc_string()` today has four refusals;
under uniform three are dead or subsumed. What remains:

| Condition | Effect |
|---|---|
| `PSA_BIZBOX_WRITE_ODBC` unset | `NoWriter` — the off-switch. **Stays.** |
| the write string carries any explicit `uid=` | **Refused**, with the remedy in the message: *the write path is Windows-authenticated by decision of 14 Oct 2026; if the desk has moved host, use a domain account, or change this guard deliberately.* |

Gone: the `sa` check (subsumed — `sa` is a `uid=`), and the read-login-reused check (void under
uniform, and it passed silently anyway). **A guard that cannot fail is deleted, not kept.**

---

## 2. Concurrency is one parameter.

**`@expected_tstamp BINARY(8)`**, carried into the `UPDATE`'s `WHERE`. Nothing updated means a
department edited the row first; the procedure returns `ok = 0` with *re-read and ask again*, and
the caller does not commit.

**No `@expected_value` fallback.** One mechanism, not two. `tstamp` moves when any column changes,
so it catches an edit to a field the desk was not touching — which on a stock or quantity row is
usually the edit that matters. The read views and the 084 mirror tables carry `tstamp` so the desk
can send it back.

The numbers that make this non-negotiable, theirs: 23 of 23 MMS write targets carry `tstamp`, 1 of
457 vendor procedures checks one, **`iwWareitem` takes 8.5 vendor updates a minute.**

---

## 3. Replay is one `UPDATE` in the desk's sender.

**The replay table in BizBox is withdrawn.** It was the wrong place. The risk it covered is in the
desk's own code, and SQL01 read it: `push()` selects every `PENDING` row and calls `writer.apply()`
**before** marking anything, so two overlapping runs would both apply the same change. Nothing in
BizBox can fix a race in the desk.

**The fix, where the risk lives — claim before apply:**

```sql
UPDATE ext_change SET status = 'SENDING', decided_by = ?, decided_at = ?
 WHERE change_id = ? AND status = 'PENDING'
```

rowcount must be **1** or the row is skipped — somebody else has it. Then apply. Then `APPLIED`
or `REJECTED`. **Restore-safe by construction**: the claim lives in the same row as the change it
claims, so they can never disagree about whether a change was sent. No second table, no location
rule, no cross-database question, nothing new in BizBox.

**For WS36 — one schema step, two CHECKs, done together:**

- `ext_change.status` and `ext_batch.status` gain **`SENDING`**.
- `ext_change.kind` and `ext_batch.kind` gain the **ten MMS kinds** from Part 90. `ext_stock` is not
  among them — a position is derived, the correctable thing is a movement (MEASURED, Part 91).

**Carried forward unchanged:** the two-database grant; `psa.sp_apply_change` needs no `EXECUTE AS`;
`@approved_by` is passed for the audit trail only — the desk already derives it from the stored
batch row, which is the right place and already correct.

---

## 4. Verify once, with four controls that must fail — then prove

As `psa_desk`, wrapped in `EXECUTE AS USER = 'psa_desk'` … `REVERT` (checked as a sysadmin,
everything returns 1 and reads like a pass):

| Check | Must return | Why it exists |
|---|---|---|
| `EXECUTE` on `psa.sp_apply_change` | **1** | the one thing it may do |
| `UPDATE` on `dbo.iwWareitem` | **0** | it holds no table right — one `iw*` table stands for all |
| `UPDATE` on `dbo.appsysUserSubmodules` | **0** | it cannot grant itself rights inside BizBox — the objection to `db_owner` |
| `SELECT` on one `ps%` table | **0** | the patient fence, which has a different consequence from the others |

Any 1 where 0 is required voids the run. Then one execution with a payload a refusal must reject,
confirming `ok = 0` and no commit. Then prove on `TrainingDB_HIS8` against what the vendor client
itself produces.

---

## 5. Two operational notes, not mechanisms

From the Bizbox Chat session's restore-history measurement — filed verbatim as
`docs/bizbox-mms-replay-guard-restore-safety-20261014.md`. The design it analysed is superseded;
**the facts in it stand and two of them matter here.**

- **`TrainingDB_HIS8` is refreshed from live — 35 restores into it, the most recent 12 Oct 2026.**
  Every refresh wipes `psa.sp_apply_change` and the `psa_desk` user there. **Re-create both after
  every refresh, and verify the procedure exists before a proving run** — a proving run against a
  wiped database proves nothing and looks like a pass.
- **`LiveDB_PMC` has been restored into twice — 9 and 16 July 2026.** After any such restore, BizBox
  may have lost changes the desk recorded as `APPLIED`. That is a **reconciliation report**, read-only,
  desk-side: for every `APPLIED` change, does the `ext_ref` BizBox returned still exist with the value
  the desk sent? Missing ones are re-queued deliberately. A report, not a guard — it runs when a
  restore has happened, not on every write.

---

## 6. What was dropped, so nobody puts it back

| Dropped | Why |
|---|---|
| consumed-ids table in BizBox | the race is in the desk's sender; fixed there by one `UPDATE` |
| its "never in `PMC_PSA`" location rule | no table, no rule |
| its `DELETE`-must-be-refused control | no table |
| `@expected_value` fallback | one concurrency mechanism, not two |
| the `sa` refusal | subsumed by refusing any `uid=` |
| the read-login-reused refusal | void under uniform, and it could not fail anyway |
| two of six verifier controls (`INSERT` on `iwItemLedger`, `DELETE` on the dropped table) | `iwWareitem` already proves "no table rights"; the table is gone |

**Nothing run. Nothing scheduled. Code untouched. `PSA_BIZBOX_WRITE_ODBC` unset.** Order when Dada
says go: the one-condition guard → `psa.sp_apply_change` with `@expected_tstamp` → WS36's schema step
(`SENDING` + the ten kinds) → the sender's claim-before-apply → user and grant in both databases →
verify → prove on Training.
