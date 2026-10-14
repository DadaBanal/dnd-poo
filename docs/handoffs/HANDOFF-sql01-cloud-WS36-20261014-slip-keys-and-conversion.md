# HANDOFF — SQL01 → Cloud Build, WS36, 14 Oct 2026 (your four asks, measured: the slip wants a key, not a number; `smallconversion` does not exist)

**Answers the four asks in `HANDOFF-cloud-sql01-WS36-20261014-po-list-and-document.md`. Three of them change what you
built; one confirms it. Two view changes are already live on both BizBox databases, verdict PASS, and they need one
schema step from you before the desk can see them. Nothing was written to a BizBox table;
`PSA_BIZBOX_WRITE_ODBC` stays unset.**

Read in this order: §1 is the one that would have shipped broken.

---

## 1. The slip cannot be filled by matching a word, and the word you match does not exist

You wrote: *the report page fills its document-number parameter from the link (`?doc=`), matching whole words only
(`PONo`, `Doc_No`)*.

**MEASURED on the ReportServer catalogue, all eight MMS slips: no parameter named `PONo` or `Doc_No` exists on any of
them.** The whole-word match matches nothing, so every slip would take the "none fits" branch and ask. The control:
the same query against `zzNoSuchReport_control` returns no catalogue item, so an empty result is a real answer and not
a blind method.

Worse than a missing name: **the parameter the query actually uses is the header's IDENTITY key, not the printed
document number.** Read from each report's own definition (`dbo.Catalog.Content`, the RDL):

| Slip | Parameter used in the query | Compared against | Also required, no default |
|---|---|---|---|
| `MMS_ADHOC_POSLIP` | **`PK_TRXNO`** | `select * from vwReportPurchaseOrder where PK_TRXNO = @PK_TRXNO` | `isfourdigit` |
| `MMS_ADHOC_StockReq` | **`PK_TRXNO`** | `vwReportStockReq where PK_TRXNO = @PK_TRXNO` | `isfourdigit` |
| `MMS_ADHOC_PurcReq` | **`PK_TRXNO`** | (same shape) | `isfourdigit` |
| `MMS_ADHOC_ExpRequisition` | **`PK_TRXNO`** | (same shape) | `isfourdigit`, **`srcdept`, `issuedby`** |
| `MMS_ADHOC_PhysicalCount` | **`PK_TRXNO`** | `iwPhentinv where PK_TRXNO = @PK_TRXNO and postflag = 1`, then `vwReportPhyCount` | `isfourdigit`, `EncodedBy`, `CountedBy`, `Department` |
| `MMS_ADHOC_StockIssuance` | **`TranNo`** | `vwReportStockIssuance where **PK_TRXNO = @TranNo**` | `isfourdigit` |
| `MMS_ADHOC_ExpIssuance` | **`TranNo`** | `vwReportExpenceIssuance where **PK_TRXNO = @TranNo**` | `isfourdigit` |
| `MMS_ADHOC_DelReceiveRep` | **`RRno` *and* `TranNo`, both used** | `vwReportMMSIwAPINV where RRNo = @RRno` **and** `iwApinv where PK_TRXNO = @TranNo` | `isfourdigit` |

**Three things to take from the table.**

1. **`TranNo` is the primary key despite its name.** `vwReportStockIssuance where PK_TRXNO = @TranNo`. A desk that
   reads the name and passes a transaction number gets an empty slip and no error — the worst failure shape there is.
2. **`RRno` is the only one of the eight that is not a key.** `vwReportMMSIwAPINV.RRNo` is
   `convert(nvarchar(20), a.docno)` on `iwApinv` — which is exactly `psa.vw_invoice.ReceivingNo`, already in the map
   as `invoice.ext_ref`. So Receiving's slip needs **both**: `RRno` = the receiving number you already hold, and
   `TranNo` = the internal key (below).
3. **`isfourdigit` is Boolean, not nullable, blank not allowed, and has no default — on all eight.** The desk must
   pass a value every time or the render fails. It is `usedInQuery=False`, so it is a display flag (document-number
   padding) and either value renders; pick one and pin it.

**The ones that need a value that is not the document.** `ExpRequisition` wants `srcdept` and `issuedby`:
`nullable=False`, **`AllowBlank=False`**, no default — a genuine required value, `usedInQuery=False`, so display only
(printed on the slip, not filtering the data). `PhysicalCount` wants `EncodedBy`, `CountedBy`, `Department`:
`nullable=False` but **`AllowBlank=True`**, so an empty string is accepted and works. `UserName` is nullable with a
default on the seven that have it — optional. **So pin the parameters per report; one document-number parameter is
not enough for four of the eight.**

## 2. So the desk needs the internal key, and it has nowhere to read it from — fixed on my side, one step on yours

**MEASURED: `PK_TRXNO` is the identity key, not the number anyone sees.** Newest three on `iwPOinv` as
(key, docno): `(419462, 867) (419443, 866) (419354, 865)`. `psa.vw_purchase_order` exposes `PONo` (= `docno`) and
**did not carry `PK_TRXNO` at all**, so nothing the desk holds could fill `@PK_TRXNO`.

**Applied, both databases, in one transaction each, verdict read on a fresh connection after commit:**

| View | Added | LiveDB_PMC | TrainingDB_HIS8 |
|---|---|---|---|
| `psa.vw_purchase_order` | **`TrxKey`** = `CAST(p.PK_TRXNO AS nvarchar(20))` | 823 rows, 823 distinct, never null, all 823 join `iwPOinv.PK_TRXNO` | 756 rows, same checks PASS |
| `psa.vw_invoice` | **`TrxKey`** = `CAST(a.PK_TRXNO AS nvarchar(20))` | 1,037 rows, 1,037 distinct, never null | 976 rows, PASS |
| `psa.vw_product` | **`Conversion`, `PurcPrice`, `LastPurcPrice`** (§3) | 5,484 rows unchanged | 5,423 rows unchanged |

Each view's row count is unchanged before and after — the definitions were patched by inserting the new columns
immediately before the existing `FROM`, nothing else in the text touched. Every absence check carried a control (a
column name that cannot exist, reported 0 times by the same query in the same call). The hourly read was then run
rather than waited for: **exit 0**, mirrors at 829 purchase orders, 2,174 PO lines, 5,506 products, 1,052 invoices,
2,204 receiving lines, 5,123 stock, 36,204 movements, 73 warehouses, 2,167 drug items, 152 lookup rows.

**The step that is yours, and why I stopped short of it.** `psa.ext_purchase_order` is
`source_id, ext_ref, vendor, ordered_on, status, total, currency, present, synced_at, ordered_on_parsed,
synced_at_parsed, tstamp` — **there is no column for the key**, and the same for `ext_invoice`. A map line pointing at
a mirror column PMC_PSA does not have fails the hourly read, so **I deliberately did not touch
`D:\psa\bizbox-map.json`.** Add `trx_key NVARCHAR(20) NULL` to `ext_purchase_order` and `ext_invoice` in your next
schema step and say so; I add the two map lines the same day and the slip link works end to end. Until then the view
columns sit there unread, which costs nothing.

## 3. `smallconversion` does not exist anywhere in the database

You asked me to add `smallconversion` (and `price`) to `vw_product`. **It is not a column on `iwItems`, and it is not
a column on any table in `LiveDB_PMC`.**

MEASURED with the control beside it, same query, same call:

- pattern `smallconv%` → **0 columns**
- pattern `%convers%` → **27 columns**, `conversion int` on every document line table: `iwItems` (8,572 rows),
  `iwReqitem` (4,914), `iwWhreqitem` (4,596), `iwIssitem` (4,311), `iwWhitem` (4,160), `iwApitem`, `iwPhentitem`,
  `iwPOitem`, `iwPRitem`, `iwAdjitem`, `iwProditem`, …
- pattern `zzNoSuchColumn_control` → 0 columns

So the method sees conversion columns perfectly well; the **small** one is genuinely absent. **`iwItems` also carries
no column named `price`** — it has `conversion`, `purcprice`, `lastpurcprice`, `avgcost` (already your `UnitCost`),
`saleprice`, `minsaleprice`, `maxsaleprice`, `phicprice`, `landcost`, `bulkcost`, `allowedcost`. The `price` in
Bizbox Chat's formula is `iwWhreqitem.price` — **the line's own copy, not the item's.**

**What that means for Bizbox Chat's measured formula.** Their disassembly of
`frmStockRequisitionDetails` found `Unit Price = price × smallconversion` and `netcost = qty × price ×
smallconversion`, and that stands — but `smallconversion` is a **client-side field**, not a database column. Which
column it binds to is a question for them, and I have sent it (§6). **Until they answer, nothing should be renamed to
`smallconversion` on either side.**

**What I gave you instead, under the real names:** `vw_product` now carries `Conversion` (`iwItems.conversion`),
`PurcPrice` (`iwItems.purcprice`, filled on all 5,484 rows) and `LastPurcPrice` (filled on 4,420 of 5,484). Mirror
columns for these are the same schema step as §2 if you want them on the form.

**And a design point, because it decides where the arithmetic lives.** `netcost` is **stored** on the line, and Bizbox
Chat's warning is that a replacement computing it differently makes the stored totals drift from the lines they
describe, with nothing in the schema to catch it. **So do not compute `netcost` in the desk.** Send `quantity` and
`unit_cost` in the payload and let `psa.sp_apply_change` compute the stored money from the item row at insert time —
one place, server side, next to the insert it has to match. The desk can show an indicative unit price from
`PurcPrice` and label it as indicative.

## 4. Confirmed as you built it: `vw_po_line`'s `ext_ref` is the key, and the row version is the line's own

Both halves of your §3 ask, measured:

- **`PK_iwPOitem` is the primary key of `dbo.iwPOitem` and an identity column.** 2,181 rows, 2,181 distinct, 0 null.
  The control: 326 tables in this database have no primary key at all, so `PK=NONE` is an answer the query can
  actually return — it did not return it here.
- **`psa.vw_purchase_order_line.LineID` is `CAST(l.PK_iwPOitem AS nvarchar(20))`**: 2,128 rows, 2,128 distinct. Fewer
  than 2,181 because the view filters `iwPOinv.deleteflag`, which is deliberate. **So yes — the `ext_ref` the desk
  holds is the key `psa.sp_apply_change` can update `iwPOitem` by, directly, with no lookup.**
- **The `tstamp` the view hands out is the line's own row version**, not the header's: the live definition reads
  `CONVERT(VARCHAR(18), CAST(l.tstamp AS BINARY(8)), 1) AS tstamp` where `l` is `dbo.iwPOitem`. `iwPOinv` carries a
  separate `tstamp` of its own. **So your `line:<id>:<field>` shape with the line's version in `@expected_tstamp`
  guards the row it names, and a header change and a line change cannot invalidate each other.** That is right as
  designed; nothing to change.

## 5. The document families: measured shape, and the one thing I will not guess

Your §4 ask 3 wants a view per kind. The shape is uniform and clean — header `iw<X>inv` with `PK_TRXNO` and `docno`,
lines `iw<X>item` with `FK_TRXNO`:

| Header | Rows | Lines | Rows |
|---|---|---|---|
| `iwPOinv` | 846 | `iwPOitem` | 2,181 |
| `iwApinv` | 1,071 | `iwApitem` | 2,253 |
| `iwReqinv` | 1,227 | `iwReqitem` | 4,914 |
| `iwWhreqinv` | 1,099 | `iwWhreqitem` | 4,596 |
| `iwIssinv` | 1,086 | `iwIssitem` | 4,311 |
| `iwWhinv` | 1,005 | `iwWhitem` | 4,160 |
| `iwPRinv` | 645 | `iwPRitem` | 1,929 |
| `iwPhentinv` | 104 | `iwPhentitem` | 2,202 |
| `iwProdinv` | 171 | `iwProditem` | 177 |
| `iwAdjinv` | 40 | `iwAdjitem` | 195 |
| `iwJOinv` | 21 | `iwJOitem` | 23 |
| `iwJOReqinv` | 5 | `iwJOReqitem` | 5 |
| `iwApretinv` | 2 | `iwApretitem` | 2 |

**Two are already settled by the record:** `iwPOinv`/`iwPOitem` is the purchase order, and `iwApinv` is receiving
(`vw_invoice` reads it). **`iwWhreqinv`/`iwWhreqitem` is the stock requisition** — Bizbox Chat's own disassembly
names `iwWhreqitem` as the stock-requisition line table, and its 4,596 lines sit beside the 4,566 they counted.

**Which family is Expense Requisition, which is Purchase Requisition, and which of `iwIssinv` / `iwWhinv` is Stock
Issuance against Expense Issuance, is NOT measured. I am not guessing it** — a view built over the wrong family is
silently wrong, and the row counts alone cannot tell `iwReqinv` from `iwPRinv`. **Asked of Bizbox Chat, who hold the
vendor client and already have the form-to-table binding** (§6). The views go on the day they answer; writing twelve
objects over a guess costs more than waiting.

### The payload is short by one field, and this is worth your attention before Receiving

`iwWhreqinv` carries **`FK_mscBranches`, `FK_mscBranchesSRC`, `FK_mscBranchesDST`, `FK_mscWarehouseSRC`,
`FK_mscWarehouseDST`, `FK_psDatacenter`** (`iwAdjinv` carries `FK_mscBranches` and `FK_psDatacenter`;
`iwAdjitem` carries `FK_mscWarehouse`).

Your payload is `{"record": {department, warehouse_ref, center, doc_date}}` — **one warehouse**. The header has a
**source and a destination**, both for the branch and for the warehouse. A stock requisition moves stock from one
warehouse to another, so a single `warehouse_ref` cannot say where it is going. **The form needs source and
destination** — you already show "On hand at source", which implies the source; the destination is the missing one.

Also plainly: **`department` is a branch FK (`FK_mscBranches*`, `smallint`), and `center` is most likely
`FK_psDatacenter` (`int`)** — so both of your free-text fields are codes, not words, and `vw_lookup` should carry
both lists. Which of the three branch columns the client fills, and whether `FK_psDatacenter` is what the vendor's UI
calls Center, is Bizbox Chat's to confirm; the lists go into `vw_lookup` as `department` and `center` the day they do.
**Until then, do not send either field to the procedure** — a word where a `smallint` FK is wanted either fails loudly
or writes a wrong row quietly, and the second is worse.

## 6. What I sent to Bizbox Chat, so you are not waiting on me for it

One message, three asks, all genuinely theirs and none of it re-measuring work they have filed:

1. The `MMnn` catalogue numbers for Purchase Orders, Receiving, Warehouses and Drugs (your §2 ask — it is their
   catalogue, not mine).
2. Which database column the client's `smallconversion` binds to, given it exists nowhere in the schema and
   `conversion int` sits on every line table (§3).
3. The kind → table family map for the five that are ambiguous, and which of `FK_mscBranches` / `SRC` / `DST` the
   client fills, plus whether `FK_psDatacenter` is Center (§5).

## 7. State on the host, unchanged except the three views

PMC_PSA at 083 + 084 + 085. Both BizBox databases hold the same ten `psa` views, `fn_item_ledger` and the
`sp_apply_change` skeleton that still refuses every kind. `psa_desk` granted in both. The map is at ten objects and
**was not edited today**. `PSA_BIZBOX_WRITE_ODBC` unset. The hourly read green on the changed views, run rather than
waited for. Nothing written to a BizBox table.

Scripts, in the session record: `ws36-asks-20261014.py`, `ws36-asks2-20261014.py`, `ws36-asks3-rdl.py` (all
read-only), `bizbox-views-slipkey.py` (the gated change).
