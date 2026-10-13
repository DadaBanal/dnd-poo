# §3 of the MMS brief counts deleted and cancelled documents — both columns, and the verdict is unchanged

**Corrects:** the document-chain volume table in §3 of `docs/bizbox-mms-design-brief-20261014.md`
(`bb96800`, sha256 `0b3072d1…48cd005`) and the volumes quoted in
`docs/bizbox-mms-rule3-contention-and-kinds-20261014.md`. **Neither file is edited.**

**Why it surfaced:** SQL01 established that `psa.vw_invoice` filters `ISNULL(a.deleteflag,0) = 0`,
which is why 1,069 headers become 1,035 rows. **My §3 counted raw table rows throughout**, so the
same overstatement applies to all fourteen document types, and §3 is the table being used for sizing.

**Measured 14 Oct 2026**, `LiveDB_PMC`, read-only, control passed.
Script: `scripts/Probe-Section3FlagAudit-20261014.py`.

---

## Both columns, because the house rule says count flags rather than drop them

CLAUDE.md: *"Never exclude data. Flags are counted, never filtered out."* So the correction is **not**
to replace the raw count with a live one — it is to show both and label which is which. A raw count
answers *how much is in the table*; a live count answers *how many documents a department would
recognise*. §3 gave only the first while being read as the second.

| Document | §3 as published (raw) | deleted | cancelled | **live** | overstated by |
|---|---|---|---|---|---|
| Expense Requisition | 1,223 | 28 | 32 | **1,163** | 60 (4.9%) |
| Stock Requisition | 1,095 | 35 | 39 | **1,021** | 74 (6.8%) |
| Expense Issuance | 1,085 | 5 | 12 | **1,068** | 17 (1.6%) |
| Delivery / Receiving | 1,069 | **34** | 49 | **986** | 83 (7.8%) |
| Stock Issuance | 998 | 19 | 6 | **973** | 25 (2.5%) |
| Purchase Order | 837 | 23 | 18 | **796** | 41 (4.9%) |
| Purchase Requisition | 634 | 16 | 13 | **605** | 29 (4.6%) |
| Material Production | 169 | 12 | 7 | **150** | 19 (11.2%) |
| Physical Count | 104 | 5 | 7 | **92** | 12 (11.5%) |
| Quantity Adjustment | 40 | 3 | 1 | **36** | 4 (10.0%) |
| Job Order | 21 | 0 | 0 | **21** | 0 |
| Job Order Request | 5 | 0 | 2 | **3** | 2 (**40.0%**) |
| Purchase Return | 2 | 0 | 0 | **2** | 0 |
| Allotment / Obligation | 0 | 0 | 0 | **0** | 0 |
| **Total** | **7,282** | **180** | **186** | **6,916** | **366 (5.0%)** |

Cross-check both ways: `iwApinv` with `deleteflag <> 0` measures **exactly 34**, matching SQL01's
1,069 − 34 = 1,035 to the row. Control: an impossible flag value returned 0 rows.

**Overall 5.0%, but it is not uniform** — 0% on three documents, 1.6% on Expense Issuance, 11.5% on
Physical Count, **40% on Job Order Request**. So a single blanket adjustment would be wrong; the
per-document figures are the ones to use.

## The verdict is unchanged, which is the point worth recording

My kind-list cut was at 25 headers. Against the **live** figures:

| At risk of moving | Raw | Live | Still |
|---|---|---|---|
| Quantity Adjustment — the lowest in scope | 40 | **36** | **in scope** |
| Job Order — the highest excluded | 21 | 21 | excluded |
| Job Order Request | 5 | **3** | excluded |
| Purchase Return | 2 | 2 | excluded |

**Nothing crosses the threshold in either direction.** Ten documents in scope, four excluded, and
with Delivery/Receiving being the existing `INVOICE` kind that remains **nine new kinds**. The
ranking order shifts slightly; the in/out split does not. **So nothing downstream of the kind list
needs revisiting** — the `CHECK` widening, the verifier and the phase-1 list all stand.

The gap also widens rather than narrows: the lowest in scope is now 36 and the highest excluded 21,
so the cut sits in a 15-document gap instead of a 19-row one. Still a judgement, still not a
measurement, and still defensible.

## What this does and does not touch elsewhere

- **§4 report usage — unaffected.** Those are SSRS execution counts, not document rows.
- **§2 holder counts — unaffected.** Permission rows, not documents.
- **§5 defect list — unaffected.** The stock, costing, reorder, lot and approval findings are counted
  from `iwWareitem`, `iwItems`, `iwItemLedger` and the lot tables, not from document headers.
- **§5.6 approval figures need the same treatment and have not had it.** I quoted `approvalflag`
  802/35 and `approval2flag` 762/75 **against raw PO headers of 837.** Against 796 live those
  proportions change. **Not re-measured here** — flagged, not fixed.
- **The ledger figures are unaffected by this**, but note `iwItemLedger` carries its own `cancelflag`:
  610 cancelled of 227,084, measured earlier, and every three-way stock comparison was run **both
  counting and excluding them with identical results to the digit.**

## Why §3 was built this way, said plainly

Not an oversight of a filter I knew about — **I did not check whether these tables carried
`deleteflag` and `cancelflag` at all** before publishing counts that would be read as live document
volumes. The house rule about counting flags rather than filtering them is the reason a raw count is
defensible; it is not a reason to omit the live one, and §3 presented one number without saying which
of the two it was.

Read-only throughout. Nothing built, nothing changed.

*Prepared by the Bizbox Chat session on DND-SQL01, 14 Oct 2026. No patient identifiers, no staff
names, no passwords, no connection strings, no addresses or topology.*
