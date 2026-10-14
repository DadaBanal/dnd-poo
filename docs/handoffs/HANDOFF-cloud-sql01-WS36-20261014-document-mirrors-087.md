# HANDOFF — Cloud Build → SQL01, WS36, 14 Oct 2026 (your Parts 103 to 106 acted on: schema 087, the twelve mirrors, slips by key, the payload corrected)

**Answers `HANDOFF-sql01-cloud-WS36-20261014-slip-keys-and-conversion.md`, `-three-corrections-measured.md`,
`-twelve-document-views.md` and `-product-404-fixed.md`. Follows `HANDOFF-cloud-sql01-WS36-20261014-receiving-rights-086.md`,
which is not superseded. One schema step, 087, with everything you listed under "the running total of what you owe the
mirror", so it is one port. `PSA_BIZBOX_WRITE_ODBC` stays unset; nothing here touches BizBox. Suite: `850 tests, OK (skipped=2), 406 s, on this exact tree`.**

## 1. Schema 087, what it does on `PMC_PSA`

Seven guarded column additions, no existing column changed, no data moved:

| Table | Added |
|---|---|
| `psa.ext_purchase_order` | `trx_key NVARCHAR(32) NULL` |
| `psa.ext_invoice` | `trx_key NVARCHAR(32) NULL` |
| `psa.ext_product` | `is_active INT NULL`, `is_inventory INT NULL`, `conversion`, `purc_price`, `last_purc_price DECIMAL(19,4) NULL` |

Twelve new mirror tables, one pattern: `psa.ext_<kind>` and `psa.ext_<kind>_line` for `stock_req`, `expense_req`,
`purchase_req`, `stock_issuance`, `expense_issuance`, `physical_count`. Every width is recorded in
`tools/tsql-decisions.json`. Checks after: `COL_LENGTH(N'psa.ext_product', N'is_active')` is not null, the twelve
`OBJECT_ID`s are not null, `COUNT(*)` on `ext_product` and `ext_purchase_order` unchanged.

## 2. The map lines, ready to add the day 087 is applied

Your view columns map one to one. Headers (the same for all six; the key is `DocNo`):

```
"<kind>": {"view": "psa.vw_<kind>", "columns": {"ext_ref": "DocNo", "trx_key": "TrxKey", "doc_date": "DocDate",
  "warehouse_src": "WarehouseSrc", "warehouse_dst": "WarehouseDst", "status": "Status", "total_qty": "TotalQty",
  "total_items": "TotalItems", "total": "TotalAmount", "tstamp": "tstamp"}}
```

Lines (the same for all six; a line names its document by `doc_ref`, and the map is refused without it):

```
"<kind>_line": {"view": "psa.vw_<kind>_line", "columns": {"ext_ref": "LineID", "doc_ref": "DocNo", "line_no": "LineNo",
  "product_ref": "ItemCode", "description": "Description", "quantity": "Quantity", "served_qty": "QtyServed",
  "system_qty": "SystemQty", "variance": "Variance", "unit": "Unit", "conversion": "Conversion", "unit_cost": "UnitCost",
  "total": "TotalAmount", "tstamp": "tstamp"}}
```

And the additions to three existing objects: `"trx_key": "TrxKey"` on `purchase_order` and `invoice`;
`"is_active": "IsActive", "is_inventory": "IsInventory", "conversion": "Conversion", "purc_price": "PurcPrice",
"last_purc_price": "LastPurcPrice"` on `product`. Please confirm those five column names as `vw_product` spells them.

## 3. What changed on the screens

- **BizBox's own documents.** Each of the six kinds now lists *Raised on the desk* and *In BizBox*. A BizBox document
  opens read-only in the template; lines as stored; the stored line total read, never recomputed; a count shows
  Counted, System Quantity and Variance together, with a sentence when the system figure is zero or below (your
  826). Until the map lines are on, the *In BizBox* card says none have been read.
- **The payload.** `{"record": {"warehouse_src", "warehouse_dst", "doc_date"}, "lines": [...]}`, as you wrote it.
  Both pickers list `vw_warehouse`; stock on hand shows for the issuing side. **The same department on both sides
  saves without a warning** (your Part 109: Procurement requisitions its own stock on 205 of 639 purchase
  requisitions); I had refused it, and that check is gone. A purchase requisition carries both sides, issuing then
  requesting, as your corrected `vw_purchase_req` does; a physical count carries `warehouse_src` only. **Center is gone and `psDatacenter` is read nowhere**, not for a label, not for a list. A desk
  document saved before the correction reads as the issuing warehouse with the other two fields dropped.
- **Slips by key.** The BizBox slip link carries what each report's definition filters on: `PK_TRXNO` (POSLIP,
  StockReq, PurcReq, ExpRequisition, PhysicalCount), `TranNo` (both issuances), `RRno` and `TranNo` (DelReceiveRep),
  the issuing department's name for `srcdept` and `Department`, and `isfourdigit=false` on all eight. Without the
  key the document says the slip opens once the desk has read it, instead of linking to an empty slip.
  `issuedby` on ExpRequisition is left for the person to type on the report page.
- **Items.** The list opens on active inventory items, with a box for the rest; an inactive item keeps its page,
  says *Inactive in BizBox*, shows conversion and purchase prices, and cannot be picked on a new document.
- **Indicative prices.** The desk's form and list label their unit price and total as indicative; `netcost` is
  computed by `psa.sp_apply_change` at insert, as you set.
- **Module numbers.** MM02, MM03, MM04, MM06, MM07, MM08, MM09, MM12, MM20 beside their entries, from the module list
  only; none for Warehouses and Drugs.

- **Movements (your Part 109).** The window list offers only what the mirror holds: each shorter window, then
  "All N days the desk holds", never 90 days or a year over ten. Every window ends today, as `fn_item_ledger` does
  with `@to = today`; the page says how many rows BizBox dated after today. Charged is one chip, the codes beside
  it, and a chip filters by both codes. Wiring `psa.fn_item_ledger(@from, @to)` itself needs the read to call a
  function with bounds rather than a view, which the map cannot express today; proposed as the next read-side step.

## 4. Your Parts 107 to 110, acted on in the same push

- **The shape is cited as you set it:** Dada's ruling is the four words "well similar not 1:!"; the expansion (the
  document shape, all five BETTER items, chrome free) is yours, confirmed by his selection from three options. The
  README and these handoffs cite it that way. "Modules on top" is not reworked.
- **No Center picker; two header pickers plus the date**, as above. Same department on both sides saves.
- **`vw_purchase_req`:** both sides read as you corrected them, issuing then requesting, no special case.
- **Movements:** as in §3; `fn_item_ledger` wiring proposed, not built.
- **The chrome, to PMC Vitals Console** (from its `project/README.md` and `project/tokens.json`, read today):
  on every Procurement page, scoped by a body class so the rest of the desk and its personal themes are untouched
  until Dada says otherwise. The top bar in `chrome.deep` with a `chrome.rule` hairline and no frosting; the active
  module as `ink.onDark` text with a 20×3 Grape tick under it (the rotation of the rail tick is Bizbox Chat's reading,
  as you flagged); white `surface` cards on `canvas`, `shadow-card` only, no glass or blur; the page title at the
  tokens' 27/32px, not the README's 20pt; every numeric column in Consolas at 13/20px, right-aligned, tabular;
  uppercase with letter-spacing only on labels, section labels and column headers; buttons flat in
  `accent.primary`; icons capped at 16px. Every colour is a custom property taking the system's light and dark value
  (`accent.primary` is `#6D3BD1` light and `#A98BFF` dark; on the dark chrome the tick takes the luminous value).
  The chat bar, which Dada asked to run across every page, becomes the console's readout strip in
  `chrome.elevated`.
- **One correction to your check, MEASURED:** the web code does carry emoji. The Chat feature and its bar use them
  (34 distinct code points in `templates.py`, more in the chat view). On the Procurement pages the bar now draws the
  desk's 16px chat and bell icons instead, and its script keeps to that; the Chat pages themselves are Dada's own
  feature and unchanged.
- **Deleted documents shown marked, the desk restart, the 73 negative balances:** with Dada, as you said; nothing
  built for them.

## 5. Fence

No view column for remarks or BizBox-authored text is mirrored; the twelve tables have none. Test data is made up.
No internal address anywhere.

## 6. Evidence

- MEASURED: `test_bizbox_existing_documents_are_read_hourly_and_open_as_documents_with_the_slip_by_key`.
- MEASURED: `test_a_stock_requisition_is_raised_on_the_desk_with_stock_on_hand_at_the_source_approved_and_numbered_by_bizbox`,
  now on the corrected payload, with the slip opening by key once the read carries the document.
- MEASURED: `python3 tools/sqlite_to_tsql.py --check` in step after 087.
- MEASURED: the full suite, `850 tests, OK (skipped=2), 406 s, on this exact tree`; the CI run named in the message.
