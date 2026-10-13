# Rule 3, second pass: the contention is measured, and the MMS change kinds derived

**Extends:** `docs/bizbox-mms-rule3-concurrency-20261014.md` (`68e1dcf`, sha256 `880028d4…3593c68`),
closing two items its own "Not measured" section listed. **Neither that note nor the brief is
edited.**

**Measured 14 Oct 2026**, `LiveDB_PMC` on `DND-SQL01\PMC_SS`, read-only, control passed.
Script: `scripts/Measure-BizBoxMMS-12_kinds-20261014.py`.

---

## 1. The ledger is **not** append-only — and `iwWareitem` is the real contention point

The earlier note asked whether `iwItemLedger` is only ever inserted, because if so rule 3 would not
bind on it. **It is mutated.** From `sys.dm_db_index_operational_stats`, over a window of **21 hours**
since the last SQL Server start:

| Table | Inserts | **Updates** | Deletes |
|---|---|---|---|
| **`iwWareitem`** | 15,832 | **10,667** | 0 |
| `iwItemLedger` | 3,559 | **17** | 0 |
| `iwItems` | 1,379 | **1,023** | 0 |
| `iwPOinv` | 33 | **97** | 0 |
| `iwReqinv` | 41 | **91** | 0 |
| `iwWhreqinv` | 54 | **85** | 0 |

Corroborated in the vendor's own code: **1** procedure's text contains `UPDATE … iwItemLedger`, **2**
contain `DELETE … iwItemLedger`, **1** contains `INSERT … iwItemLedger`. No triggers on the table.

**Two conclusions, and the second is the one that matters.**

1. **Append-only is false.** 17 updates in 21 hours is rare — about 0.5% of operations on that table
   — but it is not zero, so **rule 3 binds on `iwItemLedger` as well.** A write path must not assume
   a ledger row it read is immutable.
2. **`iwWareitem` is where the race actually is: 10,667 updates in 21 hours — about 508 an hour, 8.5
   a minute, and far higher in working hours since the window includes the night.** This is the
   stock table, the one a stock correction would touch. Rule 3 is not a precaution here; **any write
   to `iwWareitem` without a concurrency token is racing roughly nine vendor updates a minute.**

Note also that `iwPOinv`, `iwReqinv` and `iwWhreqinv` all take **more updates than inserts** — which
is what posting and approving a document looks like, and confirms the document tables are edited
after creation rather than written once.

**Incidental proof the system is live under us:** `iwItemLedger` measured **227,077** rows earlier
today and **227,104** now. The concurrency being designed for is happening during the design.

## 2. The MMS change kinds, derived from measured volume

So that *"widen both CHECKs to the MMS kinds in scope and only those"* is derived rather than
guessed. `CK_ext_change_01` and `CK_ext_batch_01` currently allow only `AGREEMENT`, `PRODUCT`,
`PURCHASE_ORDER`, `INVOICE`.

| Document | Headers | Lines | Verdict |
|---|---|---|---|
| Expense Requisition | 1,223 | 4,910 | **in scope** |
| Stock Requisition | 1,095 | 4,566 | **in scope** |
| Expense Issuance | 1,085 | 4,310 | **in scope** |
| Delivery / Receiving | 1,069 | 2,250 | **in scope** |
| Stock Issuance | 998 | 4,094 | **in scope** |
| Purchase Order | 837 | 2,151 | **in scope** — kind already exists |
| Purchase Requisition | 634 | 1,893 | **in scope** |
| Material Production | 169 | 175 | **in scope** |
| Physical Count | 104 | 2,202 | **in scope** |
| Quantity Adjustment | 40 | 195 | **in scope** |
| Job Order | 21 | 23 | exclude from phase 1 — negligible |
| Job Order Request | 5 | 5 | exclude from phase 1 — negligible |
| Purchase Return | 2 | 2 | exclude from phase 1 — negligible |
| Allotment / Obligation | **0** | **0** | **exclude — never used** |

**Ten document kinds in scope, four excluded.** The cut is at 25 headers, which is a judgement, not
a measurement — but the gap in the data is wide and obvious: the tenth-largest is 40 and the
eleventh is 21, and the four excluded total **28 headers between them** against 7,254 for the ten.

Plus the three 084 containers, which are **not documents** and need kinds of their own:

| Container | Maps to | Measured scale |
|---|---|---|
| `ext_stock` | the stock position | 4,358 item+warehouse rows holding stock |
| `ext_movement` | the ledger | 227,104 rows |
| `ext_rr_line` | receiving lines | 2,250 lines |

**Whether a change kind is needed for all three is a design question I am not answering** — a stock
position that is derived from the ledger arguably cannot be "changed" directly at all, which is
§5.1's point. If the position is derived, the correctable thing is a **movement**, not a position,
and `ext_stock` may need a read path but no change kind. That matters for the CHECK widening, so it
is worth settling before widening rather than after.

## 3. The sequencing point, agreed and reinforced

The judgement that the CHECK widening and the token must go together is right, and the measurement
above strengthens it: **a widened CHECK with no token would let an MMS change be recorded and
applied against `iwWareitem` while it is taking roughly nine vendor updates a minute.** That is
strictly worse than today's refusal, as stated.

## Still not measured

- **How the vendor client detects a conflict.** Still inferred from 1 of 457 procedures mentioning
  `tstamp`; the discriminating measurement is a disassembly of the client's save path. Not run.
- **What the 1 updating and 2 deleting ledger procedures actually do**, and under what conditions.
  Their names and bodies were counted, not read. Worth reading before a write path assumes the
  ledger is correction-by-insert.
- **The 21-hour window is one window.** It covers a Tuesday into Wednesday and includes a night. A
  longer window would give a better peak, and month-end may differ materially.
- **The save-path count.** Unchanged, unrun, and still the number that gates estimating.

Read-only throughout. Nothing built, nothing changed.

*Prepared by the Bizbox Chat session on DND-SQL01, 14 Oct 2026. No patient identifiers, no staff
names, no addresses or topology — safe for a committed repo.*
