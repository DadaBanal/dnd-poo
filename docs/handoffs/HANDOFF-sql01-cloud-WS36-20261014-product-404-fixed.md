# HANDOFF — SQL01 → Cloud Build, WS36, 14 Oct 2026 (the item page 404 was my filter; fixed on both databases, and your Items list just grew)

**Dada hit `/procurement/product?ref=11367` on the live desk and got "404 Not Found — No such record in the BizBox
mirror". The desk was right; the mirror was wrong, and the defect was mine. Fixed and proven through to
`psa.ext_product`. Nothing for you to deploy — but two things change on your screens, so read §3.**

## 1. What was wrong

`psa.vw_product` filtered `WHERE i.isInventory = 1 AND (i.isactive = 1 OR EXISTS (a purchase-order line))`.
Item 11367 is `isInventory=1`, `isactive=0`, and has never been on a purchase order. The view dropped it, the mirror
had no row, the desk reported what it saw.

**Measured before changing anything: 238 distinct item codes are shown by some other `psa` view and had no product
page** — each one a guaranteed 404 when clicked:

| View | Orphan item codes | of distinct |
|---|---|---|
| `vw_drug_item` | **203** | 2,167 |
| `vw_stock_on_hand` | 41 | 2,699 |
| `vw_physical_count_line` | 38 | 1,480 |
| `vw_stock_req_line` · `vw_stock_issuance_line` | 10 each | 985 · 960 |
| `vw_purchase_req_line` | 5 | 1,310 |
| `vw_item_ledger` · `vw_receiving_line` · `vw_expense_req_line` | 3 each | — |
| `vw_expense_issuance_line` | 1 | 526 |
| **`vw_purchase_order_line`** | **0** | 1,422 |

The zero is the tell: the old filter's `EXISTS` clause guaranteed it, which is why the hole was invisible on the one
screen anybody had been looking at.

## 2. Why the obvious fix was wrong, and what I did instead

Tightening to `isInventory = 1` would have fixed **71 of the 238**: measured, **167 of them are not inventory items
and 165 are active**. All 238 exist in `iwItems`; none is dangling. The bug was never "inactive items" — it was a
catalogue filter deciding whether a *page exists*.

**So the filter is gone.** `psa.vw_product` is now every row of `iwItems` — **5,484 → 8,572 on Live**, 5,423 → 8,503
on Training — and exposes **`IsActive`** and **`IsInventory`**. A page resolves for any code any view can show; what
a person may *pick* is a flag. The view is now simpler than it was: no `WHERE`, no correlated subquery.

Verified inside the transaction: **0 orphans across all eleven views**, `ItemCode` unique over 8,572, the control code
still absent, flags still discriminating (8,118 active, 5,906 inventory). Then the hourly read was run rather than
waited for: exit 0, `psa.ext_product` at **8,572 rows, 11367 present with `present = 1`**.

**And every other cross-view reference was then checked rather than argued about** — thirteen of them,
`WarehouseCode` → `vw_warehouse` from nine views, `PONo` → `vw_purchase_order` (826), `ReceivingNo` → `vw_invoice`
(1,041), `ItemCode` → `vw_product` (2,167 and 2,699). **Views with a broken reference: 0.**

## 3. Two things that change on your screens — one needs you today

1. **The Items list grows from 5,506 to 8,572**, and now includes 2,666 non-inventory items and 454 inactive ones.
   That is the honest price of removing the 404s. **`IsActive` and `IsInventory` on `ext_product` are now the
   priority in your schema step, ahead of `trx_key`** — with them you filter the list to active inventory items by
   default and the page still resolves for everything. Until then the list is simply longer.
2. **An inactive item should look inactive, not missing.** Once the flag is mirrored, label it on the item page
   rather than hiding the item — 11367 is a real drug with stock history that happens to be deactivated.

## 4. The running total of what you owe the mirror

In one step, so it is one port rather than three: `trx_key NVARCHAR(20) NULL` on `ext_purchase_order` and
`ext_invoice`; **`is_active BIT` and `is_inventory BIT` on `ext_product`**; `conversion`, `purc_price`,
`last_purc_price` on `ext_product` if you want them on the form; and the twelve mirror tables for the document views
(`HANDOFF-sql01-cloud-WS36-20261014-twelve-document-views.md`). **I add every map line the day it lands** and prove
them on an hourly read.

Script: `bizbox-fix-product-404.py`. Nothing written to a BizBox table; `PSA_BIZBOX_WRITE_ODBC` unset.
