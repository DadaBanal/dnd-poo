# Addendum to the MMS design brief — which stock figure is actually true

**Corrects:** §5.1 of `docs/bizbox-mms-design-brief-20261014.md`. **That brief is not edited** — it is
committed to `claude/psa-ticketing-build` as `bb96800` and was verified byte-identical by sha256.
This is a separate file so that verification still holds. Read it alongside §5.1, not instead of it.

**Why it exists:** peer session SQL reported that WS36 shipped schema 084, *"BizBox's MMS in full on
the desk: the overview, stock on hand, movements, receiving lines"*, on the same ground as §5.1. §5.1
told them to compute the position from the ledger **without proving the ledger can produce one.**
That gap is now measured.

**Measured 14 Oct 2026**, `LiveDB_PMC` on `DND-SQL01\PMC_SS`, read-only, control passed.
Script: `scripts/Measure-BizBoxMMS-10_threeway-20261014.py`.

---

## The finding — `actualqty` is the outlier, not the buckets

Three candidate figures exist for stock on hand at an item-and-warehouse pair:

1. **`iwWareitem.actualqty`** — the single stored number the screens show.
2. **The buckets** — `purcqty + issinqty + adjinqty + reqinqty + prodqty` minus
   `salesqty + issoutqty + adjoutqty + reqoutqty + prodoutqty`, on the same row.
3. **The ledger** — `SUM(qtyin) − SUM(qtyout)` from `iwItemLedger`, grouped by
   `FK_iwItems` and **`FK_mscWarehouse`**.

Across **5,681** item-and-warehouse pairs where any of the three is non-zero:

| Comparison | Pairs | Share |
|---|---|---|
| **ledger == buckets** | **4,458** | **78.5%** |
| `actualqty` == buckets | 1,750 | 30.8% |
| `actualqty` == ledger | 1,893 | 33.3% |
| all three agree | 1,711 | 30.1% |
| none of the three agree | 1,002 | 17.6% |

**The ledger and the buckets are two broadly consistent views of the same movement history. The
stored `actualqty` — the number every screen displays — agrees with neither about two thirds of the
time.**

Worked rows, largest stock first, all in warehouse 1019 (Procurement / Inventory / Warehouse):

| Item | `actualqty` | ledger | buckets | agree |
|---|---|---|---|---|
| 20001 | 35,000 | 6,000 | 6,000 | ledger = buckets |
| 20145 | 33,700 | 54,000 | 54,000 | ledger = buckets |
| 20032 | 17,800 | 2,000 | 2,000 | ledger = buckets |
| 50041 | 15,000 | 7,500 | 7,500 | ledger = buckets |
| 50042 | 11,200 | 4,900 | 4,900 | ledger = buckets |
| 20462 | 10,400 | 5,600 | 5,600 | ledger = buckets |
| 21398 | 8,600 | 8,500 | 8,500 | ledger = buckets |
| 50028 | 8,500 | 7,500 | 7,500 | ledger = buckets |

On all eight, the two derived figures agree exactly and the stored one does not. Note the direction
is not consistent — item 20001 is stored **higher** than its history supports, item 20145 **lower**
— so this is not a single systematic offset that could be corrected with one formula.

### What it is not — three explanations ruled out, each measured

| Candidate explanation | Measured | Verdict |
|---|---|---|
| Cancelled ledger rows inflate the net | 610 cancelled of 227,084. The whole table was summed **both** ways, counting and excluding them — **every figure above is identical to the digit** | **Ruled out.** Flags counted, not filtered, per the house rule |
| `actualqty` is merely stale, left behind by old movement | of 4,351 stock-holding pairs with ledger history, **0** last moved more than a year ago | **Ruled out** |
| The pairs have no history to compare against | only **7** stock-holding pairs have no ledger row at all | **Ruled out** |

---

## Correction to §5.1, stated plainly

§5.1 said `actualqty` disagrees with the bucket arithmetic on 2,617 of 4,358 stock-holding rows
(60.1%), and framed the buckets as the figure liable to drift. **Both halves need adjusting:**

- The **direction** was wrong. The buckets are a faithful projection of the ledger 78.5% of the
  time. It is `actualqty` that departs from both.
- The **denominators differ** and should not be compared directly. §5.1 counted rows of
  `iwWareitem` holding stock (4,358). This counts item-and-warehouse pairs where **any** of the
  three figures is non-zero (5,681), which also picks up pairs with ledger movement but no stored
  stock. Neither figure is wrong; they answer different questions.

§5.1's recommendation — *one derived position, computed from the ledger, never a maintained bucket*
— **stands, and is now evidenced rather than asserted.** It was the right instruction for a reason I
had not proven when I wrote it.

---

## What this means for the PSA desk, concretely

**A stock-on-hand view that reads `iwWareitem.actualqty` shows a figure that its own movement
history does not support, for roughly two pairs in three.** That is the one thing worth checking in
schema 084 before anyone builds further on it.

I **cannot see** schema 084 from DND-SQL01 — there is no local checkout of
`claude/psa-ticketing-build` on this host and the GitHub routes here are unauthenticated. That is
*cannot see*, not *not there*; I am not asserting anything about what WS36 built. The check belongs
to whoever can read it, and it is one question: **which of the three figures does the stock view
read?**

| If it reads | Then |
|---|---|
| `actualqty` | it inherits the discrepancy, and the desk will show a number Procurement cannot reconcile |
| the buckets | 78.5% defensible, but it depends on the vendor maintaining them |
| the ledger, grouped by `FK_iwItems` + `FK_mscWarehouse` | correct by construction, and it is the only one of the three that can also carry lot, expiry and cost, since `iwItemLedger` holds `lotno`, `expdate` and `purcprice` on the row |

The third option is the one to build on, and it is strictly better than the other two because it
answers the §5.2, §5.3 and §5.4 gaps from the same source rather than needing three.

### The trap that nearly made this measurement meaningless

The first run of this comparison selected the ledger's warehouse key by pattern-matching column
names, and matched **`FK_mscBranches`** before `FK_mscWarehouse`. Joining branch against warehouse
matched nothing, every ledger net came back `0.00`, and the output read as a clean, alarming
**"0.0% agreement"** — a finding that would have been entirely a method artefact.

The tell was that *every* ledger value was exactly zero, which is not what disagreement looks like.
**`iwItemLedger` carries both `FK_mscBranches` and `FK_mscWarehouse`; the warehouse key is the
second.** Anyone reproducing this must name the column explicitly rather than matching on a pattern.

---

## Still not measured

- **Which figure the vendor client itself displays** on the stock screens. The disassembly route
  exists (`frmHISItems`, the warehouse detail screens) and was not run.
- **Whether `PMC - MMS Movement Column Alignment`** — the disabled SQL Agent job named in §5.1 — is
  the vendor's own reconcile between these very figures. Reading its steps would settle both that
  question and the direction of the fix. Still unread.
- **Which of the three the 1,712 `MMS_ElectronicStockCard` runs and the 464 `MMS_PerpetualInventory`
  runs are reporting.** The RDL would say. Not read.

Read-only throughout. Nothing built, nothing changed, and the brief itself is untouched.

*Prepared by the Bizbox Chat session on DND-SQL01, 14 Oct 2026. No patient identifiers, no staff
names, no addresses or topology — safe for a committed repo.*
