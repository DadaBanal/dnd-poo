# Rule 3 is now load-bearing: `sp_apply_change` needs a concurrency token

**Relates to:** §7 rule 3 of `docs/bizbox-mms-design-brief-20261014.md` — *honour the rowversion
columns, or the two clients overwrite each other silently.* Dada permitted BizBox table writes for
the MMS build on 14 Oct, so rule 3 stops being advice and becomes a requirement.
**The brief is not edited** (`bb96800`, sha256 `0b3072d1…48cd005`).

**Measured 14 Oct 2026**, `LiveDB_PMC` on `DND-SQL01\PMC_SS`, read-only, control passed.
Script: `scripts/Measure-BizBoxMMS-11_rowversion-20261014.py`.

---

## The finding

| Measured | |
|---|---|
| Tables in `LiveDB_PMC` carrying a `rowversion`/`timestamp` column | **1,163** |
| Of the 23 MMS write targets — every document header and line table, plus `iwItems`, `iwItemMedicines`, `iwWareitem`, `iwItemLedger`, `iwItemPrices` — how many carry `tstamp` | **23 of 23. None without.** |
| Procedures in `LiveDB_PMC` whose text mentions `tstamp` | **1 of 457** |
| Ledger rows written in the last 30 days | **106,468 over 31 days — mean 3,434/day, busiest 4,267 on 1 Oct** |
| Schema `psa` exists in `LiveDB_PMC` | **yes** |
| `sp_apply_change` exists | **no** |

**The two facts that matter together:** every table a write path would touch has a concurrency
token, and the vendor's own server-side code almost never looks at one. **Optimistic concurrency on
this database is enforced in the WinForms client's own code, not in the database.** So a second
writer that does not carry and check the token gets **no protection from the server at all** — a lost
update is silent, and there is no constraint, trigger or procedure that would refuse it.

At 3,434 movements a day this is not a theoretical race.

## What that means for the procedure as described

The signature relayed is `@change_id, @kind, @change_kind, @ext_ref, @field, @new_value, @payload,
@requested_by, @approved_by` → `ok BIT, message NVARCHAR(400), ext_ref NVARCHAR(64)`.

**There is no parameter carrying the row's expected current state.** I have not read the
implementation — this is about the signature as described, not a claim about the code. But on that
signature, `sp_apply_change` cannot tell the difference between:

- the row still being as it was when the desk read it, and
- a department having edited it in the vendor client in the meantime.

**Suggested, as the smallest change that closes it:** one more input — either `@expected_tstamp
BINARY(8)` or, if passing an opaque token through the desk is awkward, `@expected_value` for the
single `@field` being changed — and the `UPDATE` carries it in the `WHERE`. Nothing updated means
somebody else got there first, which returns `ok = 0` with a message saying so, and the desk
re-reads and asks again. That fits the existing contract exactly: it is a fifth refusal alongside
the four already coded, and `ok = 0` already means do not commit.

**Why `@expected_tstamp` is the stronger of the two:** `tstamp` moves when *any* column on the row
changes, so it catches an edit to a field the desk was not touching. `@expected_value` only catches
a conflict on the same field. For a stock or quantity row, an edit elsewhere on the row usually
matters.

## Correction to a figure already in the record

The 1:1 proposal of 13 Oct states **1,203 rowversion columns**, and §7 rule 3 of the brief repeats
*"the 1,203 rowversion columns"*. What I measure today is **1,163 tables** carrying a
`rowversion`/`timestamp` column. These may not be the same quantity — columns against tables — and I
have not reconciled them. **Treat 1,163 as the measured figure for tables, and 1,203 as unverified
until someone re-runs it.** The argument does not depend on either: what matters is that all 23 MMS
write targets have one, which was counted directly.

## Not measured

- **The implementation of `sp_apply_change`**, which does not exist yet, and `psaspine/bizbox.py`,
  which is not reachable from this host — no local checkout, GitHub unauthenticated here. Cannot
  see, not absent.
- **How the vendor client detects a conflict.** That 1 of 457 procedures references `tstamp` is
  strong evidence it is client-side, but the discriminating measurement is a disassembly of the
  client's save path, which was not run.
- **Whether `iwItemLedger` rows are ever updated after insert**, or only inserted. If append-only,
  rule 3 binds on the header, line and stock tables but not the ledger. Not checked.

Read-only throughout. Nothing built, nothing changed.

*Prepared by the Bizbox Chat session on DND-SQL01, 14 Oct 2026. No patient identifiers, no staff
names, no addresses or topology — safe for a committed repo.*
