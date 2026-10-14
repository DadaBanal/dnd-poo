# The Stock Requisition grid's bound columns, recovered from the IL — "Unit Price" is neither

**Supersedes** the *Not established* line in
`docs/bizbox-mms-draft-screen-under-function-parity-20261014.md`, which asked whether BizBox binds
`price` or `netcost` to *Unit Price*. **It binds neither.** That file is not edited.

**Method:** the 13 Oct extraction `docs/bizbox-ui-inventory-MMS-20261013.txt` is real IL, so no new
reflection pass was needed. `frmStockRequisitionDetails.InitializeComponent` is **10,112 IL lines**
and builds each grid column as `ldstr "<bound key>"` → `newobj UltraGridColumn::.ctor` → `stloc N`,
then captions it later via `ldloc N` → `get_Header` → `ldstr "<caption>"` → `set_Caption`. Walking
both passes recovers the key-to-caption map. **239 columns constructed with a key.**
Script: `scripts/Probe-GridColumnMap-20261014.py`. Controls: an impossible caption matched 0 slots,
and the caption pass found captions, so an empty result would have been visible.

## The map, for the columns the draft shows

| Caption on screen | Bound key | On `iwWhreqitem`? |
|---|---|---|
| Item ID | `FK_iwItems` | yes |
| Item Description | `itemdesc` | no — from `iwItems` |
| Generic Name | `genericname` | no — not on the line table |
| Unit | `unit` | yes |
| Quantity | `qty` | yes |
| Served Quantity | **`servqty`** | yes |
| **Unit Price** | **`unitprice`** | **NO — see below** |
| Price | `price` | yes |
| **Total Amount** | **`netcost`** | yes |
| Expiry Date | `expdate` | yes — **and empty on all 4,566 rows** |
| Conversion | `conversion`, `smallconversion` | `conversion` yes |
| Abbreviation | `itemabbrev` | no — from `iwItems` |

## Two corrections to my own earlier note

1. **I said the draft's *Unit Price* is `price`. Wrong — it is `unitprice`.** And `unitprice` **does
   not exist on `iwWhreqitem`**: it is present in 9 tables in the database, none of them this one,
   and **no procedure or view mentions both `unitprice` and `Whreq`.** So it is a **client-side
   computed field**, not a stored column.
2. **`netcost` is not an alternative to `price`** — it is the *Total Amount* column. The grid shows
   **both** a `price` ("Price") and a derived `unitprice` ("Unit Price").

**INFERRED, not measured:** `unitprice` is most likely `price ÷ conversion`, since both are bound on
the same grid and that is the pattern `usp_InventoryStockCard` uses elsewhere
(`ad.landcost / ad.conversion`). **Not confirmed** — the arithmetic is in the client, and reading it
needs the method body, not `InitializeComponent`. **Do not bind a schema to that guess.**

## A finding that touches the "On hand at source" better item

**`warebalance` is bound to this grid as a column key, with no caption set anywhere in
`InitializeComponent`** — which for an UltraGrid column normally means hidden. It exists in exactly
**one** object in the database, the view `vwReportPurchaseAnalysisNew_PSRDtls`.

So **BizBox already carries a warehouse balance on the Stock Requisition grid and does not show it.**
That reframes the better item: *On hand at source* is partly **unhiding a field the product already
binds**, not inventing one. The caption-absence reading is **INFERRED** from no `set_Caption` being
found for that slot; it could be captioned outside this method.

**It does not change the source rule.** Whatever `warebalance` resolves to, the position shown must
come from the ledger derivation — `actualqty` agrees with the ledger on **33.3%** of item+warehouse
pairs.

Read-only throughout. Nothing built, nothing changed.

*Prepared by the Bizbox Chat session on DND-SQL01, 14 Oct 2026. No patient identifiers, no staff
names, no addresses or topology.*
