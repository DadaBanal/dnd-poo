# HANDOFF — Cloud Build → SQL01, WS36, 14 Oct 2026 (the Procurement screens replaced: the template, the module menu, every MMS document on the desk)

**Answers your review of 14 Oct ("The screen on the live desk is rejected") and Dada's three instructions the same day:
the whole template of the Bizbox Chat draft with an edit on the PO; the module list on top, with a hover that waits;
and "everything not on the desk yet, add on the desk". Nothing on the host changes for any of it: no schema step, no
view, no grant. `PSA_BIZBOX_WRITE_ODBC` stays unset. The head on `claude/psa-ticketing-build` that carries this file,
and its CI run, are named in the message that brings it. Suite: `846 tests, OK (skipped=2), 370 s, on this exact tree`.**

## 1. What you rejected, and what is gone

| Rejected | State on this head |
|---|---|
| An input box in every cell of every row | Gone. A list row carries no control. |
| The "0 ticked · change" bar | Gone, with its routes (`/procurement/<kind>/bulk`, `/bulk/review`): they answer 404. |
| The "0 cell(s) edited" bar | Gone, with its routes (`/procurement/<kind>/edits`, `/edits/review`): 404. |
| The four-line paragraph on every Procurement tab | Gone. The dated sync bar stays. |
| Mirror-table tabs with counts | Gone. BizBox's module list is the top menu (§2). |

## 2. The module menu, on top (your step 4, brought forward by Dada)

Procurement ▾ in the desk's top bar opens BizBox's MMS module list, each entry shown per the member's module rights:
**Overview · Purchase Requisitions · Purchase Orders · Receiving · Stock Requisitions · Expense Requisitions · Stock
Issuances · Expense Issuances · Physical Count · Items · Stock on hand · Movements · Warehouses · Drugs · Reports ·
Changes** (`PROC_PO` for the purchasing pair, `PROC_RR` for Receiving, `PROC_ITEM` for the stores, `PROC_DRUG` for
Drugs; Reports and Changes for any area). Stock on hand and Movements sit inside Items, as you set. The in-page tabs bar
is gone.

Said plainly: the entries are gated by the four areas the desk already has, not yet by the per-module, per-user rights
your Part 99 ruled (role as the base carrying a level per module, a per-user override that wins, set in Setup). That is
a schema step and a Setup screen; it is not on this head and sits in the order (§7).

Dada: *"make sure when the hover is done it doesn't go away immediately when choosing the menu, only when the mouse
leaves the area"*. A panel opened by hover now stays open for a third of a second after the mouse leaves its heading,
and the gap under the heading is bridged, so crossing into the panel never closes it; it closes once the mouse has
left heading and panel together. MEASURED with the browser: still open 120 ms after leaving, closed at 570 ms.

**Asked of you:** the draft shows BizBox's catalogue numbers beside the modules (02 Items and Services, 05 Purchase
Requisitions, 06 Stock Requisitions, 08 Expense Requisitions, 11 Issuances, 14 Physical Count). The menu carries none
yet: the numbers for Purchase Orders, Receiving, Warehouses and Drugs are not in anything I hold. Send the `MMnn` for
each and the badges go on as BizBox's own.

## 3. The document, to the draft's template

Built to `deliverables/PMC_OwnApp_1to1_MMS_20261013.png` in the record (read through the Microsoft 365 connector; the
branding there is the PMC wordmark with *Materials Management System* under it, and no separate logo file exists in
the record, so that wordmark is what the slip carries). Top to bottom:

1. **Title and breadcrumb** (`Purchase Order Details`, *Purchase Orders › PO-… › Approved*) with a *Find a purchase
   order…* search on the right.
2. **The action bar:** **Add** and **Edit Mode**, BizBox's own buttons; on the right, read from BizBox when and how
   many changes wait.
3. **The pickers in one row:** Vendor · Order date · Status · Currency. Plain values until Edit Mode; in it, BizBox's
   vendor and status lists as dropdowns and a date box, prefilled with BizBox's value.
4. **The grid:** `# · Item ID · Item Description · Quantity · Served Quantity · Unit Price · Total Amount`, BizBox's
   captions, from `ext_po_line`, with a lines total. **In Edit Mode the description, quantity and unit price of each
   line are controls, and three rows take a new item each**, picked from the items BizBox has (*a new item is never
   created from here*). That is Dada's "why is there no edit also for the PO".
5. **The footer:** Total Record(s) · Total Item · Total Amount · Total in BizBox, the approval sentence, **Print
   Purchase Order Slip**, **BizBox's slip (MMS_ADHOC_POSLIP)** when the catalogue has it, and in Edit Mode *Why* and
   **Save**.
6. **Save** opens the window that says what will change (field, from → to; a line's change named *Quantity on line
   L-1*; a new line spelled out *IT-1 Toner cyan · 1 @ 600.00*); **Send for approval** queues one batch; a second
   person approves on the document's own approval line; BizBox changes only when the approved batch is pushed.
7. **The approval line** below: every batch that touches the document as a path **Proposed → Approval → Sent to
   BizBox → In BizBox** (or Refused by BizBox, or Cancelled) with who and when on each step reached, the changes under
   it, **Approve** / **Cancel** for an approver of the area, never on their own.

**The write contract widens by two field shapes, nothing else.** The header's fields travel as before. A line's change
is one `ext_change` whose `field` is `line:<line id>:<field>` (`quantity`, `unit_cost`, `description`) with the line's
own row version as `@expected_tstamp` (from `ext_po_line.tstamp`, which your 085 view adds); a new line is
`line:new:<n>` whose `new_value` is the line as JSON: `{"product_ref": "IT-1", "description": "…", "quantity": 1.0,
"unit_cost": 600.0}`. `psa.sp_apply_change` takes the same ten parameters; its EDIT branch for `PURCHASE_ORDER` needs
the two shapes (`iwPOitem` by line id with the version check; an insert for `line:new`). Until it has them a line
change is refused by the procedure and the desk records it REJECTED with the reason, never applied half. **Asked of
you:** confirm the line id your `vw_po_line` gives as `ext_ref` is the key the procedure can update by.

## 4. Every MMS document on the desk (Dada: "everything not on the desk yet, add on the desk")

The desk has no mirror of BizBox's existing requisitions, issuances or counts (your ten views do not include them), so
each goes on as a document the desk raises and tracks itself, to the same template: **Stock Requisition, Expense
Requisition, Purchase Requisition, Stock Issuance, Expense Issuance, Physical Count.**

- **The form:** the pickers in a row (Issuing Department from the desk's own department list; Warehouse from BizBox's
  active warehouses; Center free text until you map BizBox's list as `center` in `vw_lookup`; the date), eight rows
  that take an item each from the items BizBox has, and **On hand at source** filled in as a person picks
  (`/procurement/stock.json`, from `ext_stock`, never `actualqty`), *Why*, **Save**. The window shows the header as it
  will be kept and the lines with on hand and the shortfall (*Short on 1 line: row 1: only 12 on hand at the source
  against 20 requested*; the document can still be sent, the row shows the shortfall instead of silently serving
  less). A Physical Count shows the variance instead.
- **The document** (`/procurement/<kind>?ref=NEW-<batch>`): the same screen, read from the batch's payload; the
  approval path; **Print … Slip** (the desk's own); **BizBox's slip** once BizBox has numbered it (`MMS_ADHOC_StockReq`,
  `ExpRequisition`, `PurcReq`, `StockIssuance`, `ExpIssuance`, `PhysicalCount`, by name in the catalogue). **Edit
  Mode** while it still waits for approval: the same form, prefilled; Save keeps it waiting as it now reads (audited).
  Once approved it is read-only on the desk.
- **The list:** the desk's own, open ones by default, newest first, BizBox's number once applied.
- **To BizBox:** one ADD under the kind (`STOCK_REQ`, `EXPENSE_REQ`, `PURCHASE_REQ`, `STOCK_ISSUANCE`,
  `EXPENSE_ISSUANCE`, `PHYSICAL_COUNT`; 085's CHECKs carry all six) with the payload
  `{"record": {"department", "warehouse_ref", "center", "doc_date"}, "lines": [{"product_ref", "description",
  "quantity", "unit_cost"}]}`, `@ext_ref = NEW-<batch>`, `@field = NEW`; the procedure answers `ok, message, ext_ref`
  with BizBox's number, which the document then shows. Required: department and warehouse on the requisitions and
  issuances, department alone on a purchase requisition, warehouse alone on a count.

**Asked of you, for the procedure and the views:**
1. `department` travels as the desk's department name; `center` as typed. Tell me the BizBox codes the procedure
   wants for `iwWhreqinv` (and its siblings) and whether a lookup list for each (`vw_lookup` lists `department`,
   `center`) should feed the pickers, so the words become BizBox's codes before they are sent.
2. Unit price: a blank on the form is the item's unit cost from `vw_product`. Your arithmetic note says *price ×
   smallconversion*; the item view carries no conversion. Add `smallconversion` (and `price` if `UnitCost` is not it)
   to `vw_product` and the desk computes Unit Price your way, shown not stored.
3. A view per kind for BizBox's existing documents (`vw_stock_req` + lines, and the rest), so the lists show BizBox's
   own beside the desk's. Same shape as `vw_purchase_order` / `vw_po_line`; the desk maps them as it mapped those.

## 5. Also in this push

- **The movement words, from your Part on BizBox's stock-card procedure.** `CH`/`CA` Charged · `CN` Returned by
  patient · `DC` Charge deleted · `DR` Received · `PI` Received (petty cash) · `PR` Returned to supplier · `SS`
  Transferred · `EI` Issued · `MP` Produced · `QA` Adjusted · `PC` Counted; `PP AT DP GL RT RS` the code alone. The
  code beside the word for a two-letter doctype; a view that spells a word out gets none; an unnamed code shows as the
  code, never a guess.
- **The fence.** The Movements tab and the item page no longer render `ext_movement.remarks`, and the Remarks column
  is gone. Tested with a remarks string carrying a made-up patient name: it does not reach the page.
- **BizBox's slip from a document:** the report page fills its document-number parameter from the link (`?doc=`),
  matching whole words only (`PONo`, `Doc_No`; never *Company* or *Paid*); when none fits it says so and asks, never
  the values of the last run. **Asked of you:** POSLIP's and StockReq's parameter names, and I pin them instead.
- **The Windows failure on `3fb7453`.** `AuthTest` built a throwaway RSA keypair whose prime had `p−1` divisible by
  65537, so `e` had no inverse: one draw in many thousands, unrelated to 085 or to the network. The helper now redraws
  until `gcd(e, (p−1)(q−1)) = 1`. Nothing in the suite waits on the network unbounded (every call carries a timeout,
  the longest 180 s); the 66-minute step was a slow runner throughout.

## 6. Design skills, named (your ruling 2)

In this cloud session the design skills present are `artifact-design` (fundamentals: hierarchy, gap-based layout,
consistent repeated elements, selective card styling, tabular numerals, both themes from tokens) and `dataviz`
(charts). Also present: `canvas-design`, `brand-guidelines` (Anthropic's brand, not applicable), `theme-factory`,
`web-artifacts-builder` (React, not applicable: the desk is server-rendered), `pdf` and `xlsx`.

**`artifact-design` fired** and its fundamentals were applied to the desk's own tokens and type scale (both themes,
nothing loaded from outside, which the suite's self-contained check enforces). **`dataviz` did not fire**: no chart.
**`pdf` and `xlsx` did not fire**: the desk emits no PDF or workbook; the slip is the page print-styled, BizBox's slip
comes from the report server through the Reports route of 082. No `design:*` or `frontend-design` skill exists in
this account.

## 7. The order ahead

Your order stands for what is left: **Receiving** as a document (lines from `ext_rr_line` with the order each came
from, print `MMS_ADHOC_DelReceiveRep`), then **rights per module, per user** (your Part 99: role as the base with a
level per module, a per-user override that wins, one screen in Setup; a schema step, so with a port and a handoff),
then the minor fixes from the 084 review (tile names, per-row labels, currency on money, "As of" out of the rows),
and the Movements bucket from your doctypes document (Receipts = PR, DR, PI; Issuances = CA, CH, CN, DC; Transfers =
QA, SS, MP, PC, EI) as the filter on that page. Purchase Orders, the module menu and every MMS document are on this
head. Noted from your Part 100: the row version travels as `CAST(tstamp AS BINARY(8))`, not the `CONVERT(VARCHAR(18),
tstamp, 1)` the 085 handoff wrote; the desk only carries the text it is given back, so nothing here changes.

## 8. Evidence

- MEASURED: the rejected items absent from the rendered pages; the removed routes answer 404; the rights hold through
  the menu and the document (a reader has no form, a proposer never approves their own, an approver of another area
  is refused): `test_procurement_lists_are_lists_and_a_document_carries_its_changes_adds_and_approval`,
  `test_a_purchase_order_opens_as_a_document_with_header_lines_totals_approval_and_a_slip`,
  `test_procurement_rights_are_per_area_see_propose_approve_and_never_ones_own`.
- MEASURED: a stock requisition raised, shown with on hand and the shortfall, edited while waiting, approved, pushed
  as one ADD with the payload above, numbered by BizBox's answer, read-only after:
  `test_a_stock_requisition_is_raised_on_the_desk_with_stock_on_hand_at_the_source_approved_and_numbered_by_bizbox`.
- MEASURED: the movement words and the fence: `test_movement_words_come_from_bizbox_codes_and_its_remarks_are_never_shown`.
- MEASURED: the full suite, `846 tests, OK (skipped=2), 370 s, on this exact tree`; the CI run named in the message.
- Screenshots of the list, the document in read and Edit Mode, the menu open, the slip as it prints, and the stock
  requisition's form and document were taken from a seeded desk (made-up vendors and items) and sent to Dada; not
  committed.
