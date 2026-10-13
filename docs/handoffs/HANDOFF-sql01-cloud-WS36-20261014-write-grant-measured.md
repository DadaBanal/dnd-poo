# HANDOFF — SQL01 → Cloud Build (WS36) — 14 Oct 2026
## The write grant is two statements. Ownership chaining works, so EXECUTE alone is sufficient. `ext_stock` gets no change kind — now MEASURED.

**Nothing has been run.** The grant is a production change to `LiveDB_PMC` and waits on Dada's word.
Measurements are the Bizbox Chat session's, metadata only, controls passed; **SQL01 re-ran none of
them** per the standing routing rule (Part 89 addition).

---

## 1. The one that could have broken the whole design: ownership chaining works

**MEASURED:** schema `[psa]` is owned by `dbo`, and schema `[dbo]` is owned by `dbo`. **Same owner.**

So a procedure in `[psa]` writing `dbo.iw*` tables **gets ownership chaining, and the caller needs
no table rights at all.** `EXECUTE` on the procedure is genuinely sufficient, and
**`psa.sp_apply_change` needs no `EXECUTE AS`.**

**Had those owners differed, the chain would break at the `dbo` tables** and the procedure would
fail with permission denied *despite a correct `EXECUTE` grant* — which reads exactly like a bad
grant and would have cost a debugging session chasing the wrong thing. It does not apply here.
**Re-check it if anyone ever re-owns `[psa]`.**

Also measured, and **nothing needs changing — do not turn either on:** `LiveDB_PMC` has
`TRUSTWORTHY = False` and cross-database chaining `False`. Safe defaults.

---

## 2. `psa_desk` is the right principal, and now by measurement rather than preference

SQL01 leaned to `psa_desk` over a new SQL login. **Measured and confirmed:**

| | |
|---|---|
| `DND-SQL01\psa_desk` | 1 live session, against **`PMC_PSA`**, program name `Python`. **Not `LiveDB_PMC`.** |
| Database users in `LiveDB_PMC` — `psa_desk` | **NONE (0).** It cannot touch that database today. |
| Database users in `LiveDB_PMC` — `psa_bizbox_reader` | **one**, holding `GRANT SELECT` at **SCHEMA** level on `[psa]` |

**So read and write are structurally different principals:** read is `psa_bizbox_reader`, which has
a `LiveDB_PMC` user and the SELECT; write would be `psa_desk`, which has no user at all. **The
"write login must differ from the read login" guard is satisfied by construction, not by the
regex.**

**One limitation, stated plainly because it would otherwise get baked into a runbook unnoticed:**
`DND-SQL01\psa_desk` is a **local** Windows account on that host. This works **only while the desk
runs there.** If the desk ever moves host, the login does not travel and a domain account or a SQL
login is needed instead.

---

## 3. The grant. Two statements, and the order matters

**`psa.sp_apply_change` does not exist yet** — independently re-confirmed below — so **the `GRANT`
cannot run before the procedure exists.** The order is therefore:

**procedure → user → grant → verify.** Not the order the list below reads in.

### Step 1 — create the database user. None exists today (measured 0).

```sql
USE LiveDB_PMC;
CREATE USER [psa_desk] FOR LOGIN [DND-SQL01\psa_desk] WITH DEFAULT_SCHEMA = psa;
```

`CREATE USER` carries `CONNECT` on the database by default. **Add `GRANT CONNECT TO [psa_desk];`
only if `CONNECT` has been revoked from that user on this database — otherwise do not.**

### Step 2 — the single permission.

```sql
GRANT EXECUTE ON OBJECT::psa.sp_apply_change TO [psa_desk];
```

**`OBJECT`-level, deliberately not schema-level.** `psa_bizbox_reader` already holds `SELECT` on
`SCHEMA::[psa]`, so schema-level grants on `[psa]` are in use here — **and if this were
`EXECUTE ON SCHEMA::psa`, every future procedure added to that schema would silently become
executable by the desk.** Object-level pins the grant to the one procedure.

### Step 3 — nothing else. That is the whole list.

### Explicitly NOT to be granted, so the script can be read against this

- **no database role of any kind** — not `db_owner`, not `db_datareader`, not `db_datawriter`
- **no `SELECT`/`INSERT`/`UPDATE`/`DELETE` on any table or view, and none needed** — ownership
  chaining covers the procedure's own writes, per §1
- **not `EXECUTE ON SCHEMA::psa`**, per step 2
- no `ALTER`, no `CONTROL`, no `VIEW DEFINITION`
- **nothing at server level** — the login's existing `CONNECT SQL` is sufficient and it already has it
- **`bizboxsa` is not touched at all**

---

## 4. The verifier, and the control that must fail

This is the part that proves the grant is narrow rather than merely intended to be.

**Must pass**, as `psa_desk`:

```
HAS_PERMS_BY_NAME('psa.sp_apply_change', 'OBJECT', 'EXECUTE') = 1
```

**Must FAIL — if any returns 1 the run is void and says so:**

```
HAS_PERMS_BY_NAME('dbo.iwWareitem',            'OBJECT', 'UPDATE') = 0
HAS_PERMS_BY_NAME('dbo.iwItemLedger',          'OBJECT', 'INSERT') = 0
HAS_PERMS_BY_NAME('dbo.appsysUserSubmodules',  'OBJECT', 'UPDATE') = 0
   plus one ps% table, SELECT = 0
```

**The `appsys` one matters most: it is the check that the write path cannot grant itself rights
inside BizBox**, which was the whole objection to `db_owner`.

Then **execute the procedure once with a payload one of the four coded refusals must reject**, and
confirm it returns `ok = 0` and does not commit. **A refusal proving it refuses is worth more than a
success proving it succeeds.**

### The trap in this verifier, and it is the same shape as their `FK_mscBranches` one

**Wrap the `HAS_PERMS_BY_NAME` checks in `EXECUTE AS USER = 'psa_desk'` … `REVERT`**, so they are
evaluated as that principal. **Checked as a sysadmin they return 1 for everything and read like a
pass.**

> **A check that cannot fail looks exactly like a check that passed.**

---

## 5. `ext_stock` gets no change kind — SQL01's INFERRED is now MEASURED

Part 90 recorded SQL01's reading as **INFERRED** and invited a counter-example: a case where a
department corrects a *position* rather than a *movement*. **They went looking for it.**

**The paradigm case exists — a Physical Count is exactly "the position is X regardless of what the
movements say". And BizBox already records it as a movement:**

| Doctype | Ledger rows | Documents | |
|---|---|---|---|
| `PC` physical count | 7,253 | 88 | qtyin 724,353 / qtyout 3,181 |
| `QA` quantity adjustment | 196 | 42 | |

Physical Count has 104 headers; Quantity Adjustment 40.

**So the conceptual case is real and the product already resolves it the same way: a position
correction is written as a movement.** `ext_stock` gets a **read path and no change kind.**
**Upgraded from INFERRED to MEASURED**, on their evidence, and they state they are not challenging
it because the counter-example they went looking for turned out to be modelled their way.

**One loose end in that data, not chased:** 104 PC headers against 88 PC documents in the ledger —
**16 physical counts have no ledger rows at all.**

---

## 6. They corrected their own earlier figure. Read Part 90's version with this

Part 90 carried their *"1 procedure with `UPDATE…iwItemLedger` and 2 with `DELETE`"*. **That came
from a `LIKE` pattern which matches any `DELETE` anywhere in a procedure body plus any mention of
the table — it does not prove the `DELETE` targets `iwItemLedger`.**

**The real finding:** two procedures mention both a mutating verb and that table —
`MergeAccountEntities` (`UPDATE`, `DELETE` and `INSERT`, 68,828 chars) and `usp_InventoryStockCard`
(`DELETE`, 17,057 chars). `MergeAccountEntities` is the merge-entity path, re-pointing rows when two
accounts are merged — **an identity merge, not a stock correction.** `usp_InventoryStockCard` is by
name a stock-card build and its `DELETE` **may well target a temp table.**

**What is solid: 17 leaf updates on `iwItemLedger` in 21 hours — a counter, not a pattern match.
So the ledger is not append-only, and that stands.** Attributing those 17 to a named procedure is
**NOT established**, and Part 84's point that a derived position inherits whatever they do needs
those two bodies read, **which nobody has done.**

---

## 7. An absence finding independently confirmed

Schema `[psa]` in `LiveDB_PMC` holds **exactly five views** — `vw_invoice`, `vw_lookup`,
`vw_product`, `vw_purchase_order`, `vw_purchase_order_line`. **That matches the five wired map
entries exactly**, and independently confirms SQL01's Part 84 finding: **no `vw_stock_on_hand`, no
`vw_item_ledger`, no `vw_receiving_line`.** Measured twice, from two sides, agreeing.

---

## 8. What changes for WS36

Two things only:

1. **`ext_stock` has no change kind.** It is a read path. The correctable thing is a movement. When
   the CHECK is widened, `ext_stock` is not among the kinds.
2. **`psa.sp_apply_change` needs no `EXECUTE AS`**, because ownership chaining covers it. If you
   see a design that adds one, it is unnecessary here.

Everything else is unchanged: the ten in-scope change kinds from Part 90, the token requirement, and
**priority is still Dada's.**

**Nothing written. Nothing scheduled. `PSA_BIZBOX_WRITE_ODBC` confirmed unset;
`writer_in_force()` returns `NoWriter`. No password or hash was read by either session at any
point.** The procedure is SQL01's to write, the user creation and the credential are Dada's steps,
and `bizboxsa`'s `modify_date` and `his_app_svc` both stay open and unchased on both sides.
