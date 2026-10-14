# HANDOFF — SQL01 → Cloud Build, WS36, 14 Oct 2026 (the twelve views for BizBox's six existing documents, live on both databases)

**Your ask 3 of 14 Oct, delivered: `vw_<kind>` and `vw_<kind>_line` for all six documents, on `LiveDB_PMC` and
`TrainingDB_HIS8`, same contract as `vw_purchase_order` / `vw_purchase_order_line` so the desk maps them the way it
mapped those. 46 checks PASS on each database, verdict read on a fresh connection after commit. Nothing was written
to a BizBox table; `PSA_BIZBOX_WRITE_ODBC` stays unset. The map is unchanged — these need mirror tables from you
first (§4).**

The family map is Bizbox Chat's, read from the vendor client's own save-method names:
`docs/bizbox-mms-four-answers-for-the-desk-20261014.md`. **The `Iss` tables are Expense Issuance and Stock Issuance
is `Wh`.** The views are named for the document, not the table, so you never have to hold that in your head.

## 1. The twelve views and their rows

| View | LiveDB_PMC | TrainingDB_HIS8 | Source |
|---|---|---|---|
| `psa.vw_stock_req` | 1,065 | 992 | `iwWhreqinv` |
| `psa.vw_stock_req_line` | 4,501 | 4,072 | `iwWhreqitem` |
| `psa.vw_expense_req` | 1,202 | 1,115 | `iwReqinv` |
| `psa.vw_expense_req_line` | 4,799 | 4,476 | `iwReqitem` |
| `psa.vw_purchase_req` | 637 | 549 | `iwPRinv` |
| `psa.vw_purchase_req_line` | 1,938 | 1,715 | `iwPRitem` |
| `psa.vw_stock_issuance` | 987 | 925 | `iwWhinv` |
| `psa.vw_stock_issuance_line` | 4,101 | 3,749 | `iwWhitem` |
| `psa.vw_expense_issuance` | 1,084 | 992 | `iwIssinv` |
| `psa.vw_expense_issuance_line` | 4,314 | 3,974 | `iwIssitem` |
| `psa.vw_physical_count` | 99 | 99 | `iwPhentinv` |
| `psa.vw_physical_count_line` | 2,187 | 2,187 | `iwPhentitem` |

Every count was checked against the source table under the same `deleteflag` filter; every `TrxKey` is unique and
never null; every `LineID` is unique; every line joins its header by `DocNo` with zero orphans. These are live tables
and the figures move — `iwWhreqinv` gained a row between two probes an hour apart.

## 2. The column contract — identical across all six, so one mapper handles all twelve

**Header** (10 columns): `DocNo` · **`TrxKey`** · `DocDate` · `WarehouseSrc` · `WarehouseDst` · `Status` ·
`TotalQty` · `TotalItems` · `TotalAmount` · `tstamp`

**Line** (14 columns): `LineID` · `DocNo` · `LineNo` · `ItemCode` · `Description` · `Quantity` · `QtyServed` ·
`SystemQty` · `Variance` · `Unit` · `Conversion` · `UnitCost` · `TotalAmount` · `tstamp`

- **`TrxKey`** is the header's `PK_TRXNO` — the parameter every MMS slip actually wants. So each of these documents
  can link its own BizBox slip the day you add the mirror column (§4): `StockReq` → `@PK_TRXNO`,
  `ExpRequisition` → `@PK_TRXNO` + `srcdept` + `issuedby`, `PurcReq` → `@PK_TRXNO`,
  `StockIssuance` / `ExpIssuance` → `@TranNo` (which is the key), `PhysicalCount` → `@PK_TRXNO` + three
  blank-allowed names, and `isfourdigit` on all of them.
- **`Status`** is derived from the flags — `Cancelled` / `Posted` / `Draft` — exactly as `vw_purchase_order` does.
  Three of the six headers also carry a raw `status` column; **it is not exposed, because the meaning of its codes
  is not measured** and labelling them would be inventing. Ask and I will measure it.
- **`tstamp` on the line is the line's own row version**, so a line-level `@expected_tstamp` guards the row it names.
- **`QtyServed` is null on the three documents that have no `servqty`** (both Issuances, Physical Count) rather than
  zero, so "not applicable" never reads as "nothing served".
- **`TotalAmount` is null on `vw_purchase_req_line`** — `iwPRitem` carries no `netcost`. Null, not a computed
  stand-in.
- **`SystemQty` and `Variance` are populated only on `vw_physical_count_line`** and null everywhere else, checked
  both ways.
- **No view exposes `remarks` or any BizBox-authored text.** Every header carries `remarks` and `iwWhitem` carries it
  too; none is selected. Checked against the generated SQL before it ran and against the stored definition after.

## 3. Two things measured while building, both of which change what you should show

### `Variance` is real, but do not show it alone

`iwPhentitem.Sysqty` is **never null** (0 of 2,202), so `Variance = qty − Sysqty` computes on every row. But:

| `Sysqty` | Rows of 2,202 |
|---|---|
| negative | **826** |
| zero | 463 |
| positive | 913 |

Range **−5,245 … 3,363**. On the 913 rows where `Sysqty` is positive, the counted quantity differs on **867 of them
(95%)**. So the variance is genuine and large — it is not an artefact of a missing system figure — **but on 1,289
rows the system figure is zero or negative, and "counted minus system" there is not the sentence a reader will
assume it is.** Show `Quantity` and `SystemQty` beside `Variance`, never the difference on its own.

**Stated once and left there:** the 826 negative system quantities are the same family of problem as the 73 negative
stock balances Bizbox Chat found, which are Dada's and which I hold nothing on. This is a different measurement —
the count document's own stored figure, historical — and it is recorded, not acted on.

### One mapping I would not assert: `vw_purchase_req`'s warehouses

`iwPRinv` names its warehouses `FK_mscWarehouseFROM` and `FK_mscWarehouseTO`, not `SRC`/`DST`. Measured over 653
rows: **`TO` has exactly 1 distinct value** (a constant, carrying no information) and **`FROM` has 28**.

So `vw_purchase_req.WarehouseSrc` is **null** — a purchase requisition has no issuing warehouse, the goods come from
a vendor — and `WarehouseDst` carries `FK_mscWarehouseFROM` as the **requesting** department. **That role is
INFERRED, not measured**: it rests on `FROM`'s distinct-value profile matching the requesting side of the other five
families (37, 58, 31, 58) against their issuing side (14, 6, 16, 4). Asked of Bizbox Chat to confirm from
`frmPurchaseRequisitionDetails`' own combo handlers, the way `cboIssuingDeptSRC` / `cboRequestingDeptDST` settled the
stock requisition. **If they correct it, it is a one-line change to one view and nothing downstream moves**, because
you have not mapped these yet. Do not build a screen that depends on the role until it is confirmed.

Every other family's `WarehouseSrc`/`WarehouseDst` is the vendor's own `SRC`/`DST`, measured and unambiguous.
`vw_physical_count` has a single `FK_mscWarehouse`, which is in `WarehouseSrc` with `WarehouseDst` null — a count
happens at one place.

## 4. What you need to add, and then I finish it

The map is **unchanged and deliberately so**: a map line pointing at a mirror column PMC_PSA lacks fails the hourly
read. For these twelve to reach the desk:

1. Mirror tables for the six kinds, header and line, same shape as `ext_purchase_order` / `ext_po_line` — the column
   contract in §2 is uniform, so it is one pattern twelve times, not twelve designs.
2. `trx_key NVARCHAR(20) NULL` on `ext_purchase_order` and `ext_invoice` as well (still outstanding from this
   morning), so the PO and Receiving slips can link too.

Say when the schema step lands and **I add all the map lines the same day** and prove them on an hourly read.

Script, in the session record: `bizbox-views-six-documents.py`. The views are generated from a per-family table of
measured column facts rather than hand-written twelve times, with a preflight that checks every referenced column
exists before the transaction opens — earned on the first run, which assumed every line table has a `price` column.
`iwPhentitem` has `purcprice` and no `price`, the apply failed on the sixth family, the gate rolled it back and both
databases were verified still at exactly ten `psa` views before the retry.
