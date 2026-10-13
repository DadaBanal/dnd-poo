# HANDOFF — SQL01 → Cloud Build (WS36) — 14 Oct 2026
## The write contract has two gaps, not one. Neither is reachable from the brief.

**Read with** `HANDOFF-sql01-cloud-WS36-20261014-dada-ruling-mms-may-write.md` (`261b31f`), which
granted MMS writes. **Nothing here changes that grant.** It says what must be built before the
first write, and it is SQL01's work, not yours.

**Carries:** `docs/bizbox-mms-rule3-concurrency-20261014.md` — Bizbox Chat's, verbatim, 79 lines,
sha256 `880028d4…3b593c68`, **matching the hash they stated before I copied it**. Their three
earlier files re-verified unchanged, so `bb96800`, `49e6fdb` and `26d2c30` all still hold.

---

## 1. Gap one, theirs: there is no concurrency token, and the database will not catch a lost update

**Their measurement, 14 Oct, `LiveDB_PMC`, read-only. Not re-run by SQL01.**

| | |
|---|---|
| Tables in `LiveDB_PMC` carrying a rowversion/timestamp column | 1,163 |
| **Of the 23 MMS write targets** — every document header and line table plus `iwItems`, `iwItemMedicines`, `iwWareitem`, `iwItemLedger`, `iwItemPrices` — **carrying `tstamp`** | **23 of 23. None without.** |
| Vendor procedures whose text mentions `tstamp` | **1 of 457** |
| Ledger rows in the last 30 days | 106,468 over 31 days — mean **3,434/day**, busiest 4,267 |
| Schema `psa` in `LiveDB_PMC` | **exists** |
| `psa.sp_apply_change` | **does not exist yet** |

**The two facts that matter together:** every table a write path touches has a concurrency token,
and the vendor's own server-side code almost never looks at one. **Optimistic concurrency on this
database is enforced in the WinForms client's own code, not in the database.** So a second writer
that does not carry and check the token gets **no protection from the server at all** — the lost
update is silent, and no constraint, trigger or procedure would refuse it. At 3,434 movements a day
that is not a theoretical race.

### SQL01 confirms the gap. It is not withdrawn.

They asked me to check, were careful to say they had not read `psaspine/bizbox.py` and could not,
and offered to withdraw in one line if a token were already there. **MEASURED from the checkout:**

- **No token exists anywhere in the write path.** Searching `psaspine/`, `schema/` and `sqlserver/`
  for `tstamp`, `rowversion`, `row_version`, `expected_`, `concurrency`, `optimistic`, `etag`
  returns **nothing relevant** — every `expected_*` hit is `expected_on`, a sales close date, or an
  auth digest in `web/auth.py`.
- `ProcedureWriter.apply` passes exactly the nine parameters they were told about. There is no
  tenth, and nothing carries the row's expected state.

**Their finding stands as written.**

### One thing that makes their fix cheaper than they knew

**`ext_change` already has `old_value`** — `TEXT` in `schema/043_bizbox_mirror.sql`,
`NVARCHAR(400)` in the SQL Server spine — and it is already populated when a change is raised.
**`ProcedureWriter.apply` simply does not pass it.**

So of their two options:

| Option | Cost | Catches |
|---|---|---|
| **`@expected_value`** | **one parameter. The data is already captured** — only the call needs it | a same-field conflict only |
| **`@expected_tstamp BINARY(8)`** | the read views must surface `tstamp` **and** the mirror must store it — `ext_stock`, `ext_movement`, `ext_rr_line` (084) have no such column, so it is a schema change plus a map change | **any** change to the row, including a field the desk was not touching |

Their judgement that `@expected_tstamp` is the stronger of the two is right, and their reason is the
operative one: **`tstamp` moves when any column on the row changes**, so it catches a department
editing a different field on a stock or quantity row — which usually matters. `@expected_value`
would miss exactly that.

**SQL01's read:** carry `@expected_tstamp` and treat `@expected_value` as the fallback for a field
where threading an opaque token is genuinely awkward. The fifth refusal they describe needs no new
mechanism — nothing updated means somebody got there first, which returns `ok = 0` with a message,
and `ok = 0` already means do not commit and the desk re-reads and asks again.

---

## 2. Gap two, SQL01's, and it blocks MMS writes before concurrency ever arrives

Bizbox Chat could not see this; it is in the desk's own schema, not in BizBox.

**`ext_change.kind` and `ext_batch.kind` each carry a CHECK constraint that allows only four
values:**

```
CHECK (kind IN ('AGREEMENT', 'PRODUCT', 'PURCHASE_ORDER', 'INVOICE'))
```

`CK_ext_change_01` and `CK_ext_batch_01` in `sqlserver/PMC_PSA_Spine_SqlServer.sql`, matching
`schema/043_bizbox_mirror.sql`. **080 added `batch_id` to `ext_change` but did not widen either
CHECK, and 084 added no change kinds at all.**

**There is no MMS kind.** No stock, no movement, no receiving line, no requisition, no issuance.
So **no MMS change can be recorded today, let alone written** — the insert fails on the CHECK long
before anything reaches `psa.sp_apply_change`. The grant Dada gave is real; the plumbing to carry an
MMS change does not exist yet.

**That is a good thing to have found now rather than mid-build**, and it sets the shape of the next
schema step.

---

## 3. What this means, and whose work it is

**SQL01's, in one schema step rather than three.** The first MMS write needs, together:

1. **Widen `CK_ext_change_01` and `CK_ext_batch_01`** to carry the MMS kinds in scope — and only
   those, so the constraint keeps doing its job.
2. **Add the token.** `@expected_tstamp BINARY(8)` as a tenth parameter on
   `psa.sp_apply_change`, carried into the `UPDATE`'s `WHERE`, with nothing-updated returning
   `ok = 0`. Where `tstamp` must reach the desk to be sent back, the 084 mirror tables and the map
   need the column.
3. **Then** write `psa.sp_apply_change` itself and prove it on `TrainingDB_HIS8` against what the
   vendor client produces, before anything exists in `LiveDB_PMC`.

Doing these as one gated step is deliberate: a widened CHECK with no token would let an MMS change
be recorded and applied with no concurrency protection at all, which is strictly worse than the
refusal we have today.

**Nothing for WS36 to start.** What changes for you is only that **rule 3 is now a measured
requirement with a number behind it** — 23 of 23 write targets carry `tstamp`, 1 of 457 vendor
procedures checks one, 3,434 movements a day. Honour the token in your model and keep save paths
separable per screen. The desk still writes nothing: `PSA_BIZBOX_WRITE_ODBC` is unset and
`writer_in_force()` returns `NoWriter`.

---

## 4. A figure in the record they have corrected, and it is theirs

The 13 Oct 1:1 proposal says **1,203 rowversion columns**, and the brief's §7 rule 3 repeats it.
They measure **1,163 tables** carrying one. **Those may not be the same quantity and they have not
reconciled them**, so: **1,163 is MEASURED for tables; 1,203 is NOT VERIFIED until someone re-runs
it.** Neither figure carries the argument — **23 of 23 write targets, counted directly, does.**

---

## 5. State of play

- **Bizbox Chat has written nothing and states it will write nothing to any BizBox table.** They
  note explicitly that Dada's permission went to the MMS build and to SQL01 as its driver, and is
  **not authorisation for their session** — they are not treating a relayed ruling as a licence.
  Correct, and worth recording as the standard.
- Their script is `scripts/Measure-BizBoxMMS-11_rowversion-20261014.py`, control passed.
- **Their §8 contract item** — BizBox's terms on direct database writes — remains unread and has
  been stated once to Dada by each of us. Neither of us is re-raising it. His call, and he has made
  the technical one.
- **The save-path count** is still unmeasured, still theirs, still on his word. It is now also the
  count of procedure branches, which makes it the single number gating estimating.

**Nothing changed on any host.** Read-only throughout, both sessions.
