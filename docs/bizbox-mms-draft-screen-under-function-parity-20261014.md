# The 13 Oct MMS draft, re-read under function parity — what still applies

**Why:** Dada ruled 14 Oct that the MMS document screens are built **similar to** the 13 Oct Stock
Requisition draft — the document shape with the BETTER items on it — **not 1:1**. That draft
(`deliverables/PMC_OwnApp_1to1_MMS_20261013.png`, source
`scripts/Build-OwnApp1to1Screens-MMS-20261013.html`) was drawn **while Rule 0 was in force**, so it
reproduces BizBox's captions exactly. Rule 0 has since been withdrawn. **Only the person who drew it
can say which half of it the new ruling keeps.**

**Measured 14 Oct 2026**, `LiveDB_PMC`, read-only, control passed.
Script: `scripts/Probe-DraftScreenBacking-20261014.py`.

---

## What was copied 1:1 — no longer binding

Captions *Item ID, Item Description, Generic Name, Unit, Quantity, Served Quantity, Unit Price,
Total Amount, Expiry Date*; buttons *Add, Edit Mode, Delete*; footers *Total Record(s), Total Item,
Total Amount*; the header pickers *Issuing Department, Warehouse, Center*.

**One of those is not merely non-binding, it is misleading, and I did not know that on 13 Oct.**

> **Expiry Date is backed by `iwWhreqitem.expdate`, which is populated on 0 of 4,566 rows.** `lotno`
> on the same table: also **0 of 4,566**. The column exists on BizBox's screen and on the table and
> **has never held a value.** The draft faithfully reproduced an always-blank column.

Under function parity the better version either **populates** it — which is defect §5.4, lot and
expiry wholly unused in a hospital with 2,008 medicine items — or drops it. **Reproducing a blank
column is the one option that should be off the table**, and a 1:1 rule would have required exactly
that.

## The five BETTER items — what the ruling keeps, three now evidenced

| From the draft | Status on 14 Oct |
|---|---|
| **On hand at source** — stock shown on every row | **Keep, with a correction.** It must come from the **ledger derivation**, not `iwWareitem.actualqty`. `actualqty` agrees with the ledger on **33.3%** of item+warehouse pairs. On 13 Oct I drew the field without knowing which number it should show; now there is only one defensible source |
| **Shortfall made visible** — row showing 12 on hand against 20 requested, submittable with the gap shown | **Keep.** Depends entirely on the item above, so it inherits the same correction |
| **Approval shown** — *Chief Nurse, then Central Supply issues* | **Keep, now evidenced.** `iwWhreqinv` has **0 approval columns**. The chain cannot be stored in BizBox at all, so it must live in the desk — which is §5.6, and is why this is a *better* item rather than a copied one |
| **Items picked from what exists** — type to search; a new item is never created here | **Keep.** Unchanged |
| **Print Stock Requisition Slip** at the same click | **Keep, now evidenced.** §4 measured **3,057 `MMS_ADHOC_StockReq` runs in 60 days.** The slip is the product, not a reporting feature |

## Two corrections to the draft itself

- The caption *Served Quantity* maps to the column **`servqty`**, not `servedqty`. Caption against
  column name, harmless on a drawing, wrong in a schema.
- `iwWhreqitem` has **no `purcprice`**; the line price column is **`price`**, with `netcost`
  alongside. The draft's *Unit Price* is `price`.

## Not established

Whether `netcost` or `price` is the figure BizBox shows in *Unit Price* on that screen. Both exist on
the line; I did not read the client's binding. One `InitializeComponent` pass would settle it.

Read-only throughout. Nothing built, nothing changed.

*Prepared by the Bizbox Chat session on DND-SQL01, 14 Oct 2026. No patient identifiers, no staff
names, no addresses or topology.*
