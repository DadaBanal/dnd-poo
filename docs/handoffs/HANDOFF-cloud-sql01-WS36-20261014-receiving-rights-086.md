# HANDOFF — Cloud Build → SQL01, WS36, 14 Oct 2026 (the rest of your order: Receiving, rights per module per person, the 084 fixes, the buckets)

**Follows `HANDOFF-cloud-sql01-WS36-20261014-po-list-and-document.md` on the same day; that one is not superseded.
Dada: "yes do all". One schema step this time, 086, which adds one table and changes none. `PSA_BIZBOX_WRITE_ODBC`
stays unset; nothing here touches BizBox. The head and its CI run are named in the message that brings it. Suite:
`849 tests, OK (skipped=2), 369 s, on this exact tree`.**

## 1. Receiving, as a document (your step 2)

Receiving is the desk's `invoice` kind (your Part 95, MEASURED: `psa.vw_invoice` reads the receiving header).

- **The list** is read-only rows that open the document, with the lines counted from the receiving-lines mirror.
- **The document** follows the purchase order's template: title and breadcrumb, search, the header as pickers
  (Vendor · Receiving date · Supplier's invoice no. · Due date · Status · Currency), the lines with **Purchase Order**
  on each line opening that order, the footer (Total Record(s) · Total Item · Total Amount · Total in BizBox), the
  approval sentence, **Print Receiving Report**, and BizBox's `MMS_ADHOC_DelReceiveRep` by name once the catalogue has
  it, with the number filled in by whole words (`RRNo`, `DRNo` and `ReceivingNo` all match).
- **Edit Mode is the header only.** A received quantity is a stock movement; the desk never edits one. The write
  contract does not widen for receiving.
- **No Add.** BizBox receives.
- **The purchase order's other half:** each order now shows *Received against this order*, every receiving line
  naming it with its report, date, vendor and status.

**Asked of you:** confirm `MMS_ADHOC_DelReceiveRep`'s document parameter name, so it is pinned rather than matched.

## 2. Rights per module, per person (your Part 99 ruling; schema 086)

The design you left to Cloud Build for Dada's approval, as built:

- **The unit of grant is the MMS module.** Six join the four: purchase requisitions, stock requisitions, expense
  requisitions, stock issuances, expense issuances, physical count. Each is a menu entry and a column in Setup ›
  Security roles, with the same levels: None · See · Propose · Approve, never one's own.
- **Role as the base.** A module's level lives in `role_grant` like every other module; that table does not change.
  A role written before 086 has no row for the six and reads the level of the area each came out of (purchase
  requisitions from purchase orders, the rest from items) until the role is saved. **Nobody gains or loses a page on
  the day 086 is applied.**
- **The per-person override that wins.** `psa.member_module_grant (member, module, level, set_at, set_by)`, primary key
  `(member, module)`: one person's level on one module, winning over the role for that module only. Setup's *Rights
  for one person* card sets one person on one module in one screen; *Follow the role* removes the row. Every write is
  audited under `SECURITY_ROLE`.
- **Visibility:** the Procurement menu shows each module only to those who hold it above None, and Procurement itself
  only to those holding any.

**What 086 does on `PMC_PSA`:** one `CREATE TABLE`, guarded like every object in the port, with the five column widths
recorded in `tools/tsql-decisions.json` (member and set_by as PERSON, module and level as CODE, set_at as
TIMESTAMP_TEXT). No existing table changes; no data moves. Check after: `OBJECT_ID(N'psa.member_module_grant')` is not
null and the table is empty.

**Asked of you, for the seed:** the brief's holder counts (655 Expense Requisition Details, 640 Purchase Requisition
Details, 570 Stock Requisition Details, a dozen on receiving, purchase orders and physical count) are per BizBox user.
If you send the user-to-submodule list as counts per role BizBox uses, not names, the desk's starter roles can be cut
to match before anyone is set apart one by one.

## 3. The 084 review's minor items (3 to 7)

| # | Your finding | Now |
|---|---|---|
| 3 | Tile name reads "0purchase orders" | Number and caption are one name with a space; the tile link carries it as its label |
| 4 | Products grid, a form in every row | The items list is a list since this morning; now tested |
| 5 | Money has no currency | The currency once, on the caption or the total, from what BizBox puts on its orders |
| 6 | "As of" on every stock row | In the caption when every row agrees; per row only when rows differ |
| 7 | Remarks column always empty | Gone, and remarks rendered nowhere |

## 4. The stock card's buckets on Movements (your doctypes document)

Receipts = PR, DR, PI · Issuances = CA, CH, CN, DC · Transfers = QA, SS, MP, PC, EI. They are the first filter on
Movements; the kinds inside the bucket chosen are the second. The asset family (PP, AT, DP, GL, RT, RS) sits in
**Other**, shown only when something is in it, with the code and no word.

## 5. Design skills (your ruling 2)

artifact-design fired for the screens, on the desk's own tokens in both themes, nothing loaded from outside.
dataviz, pdf and xlsx did not fire: no chart, and no PDF or workbook is emitted by the desk.

## 6. Your order, after this

Every step of it is on this head. What is open is yours: the parameter names (POSLIP, StockReq, DelReceiveRep), the
department and centre codes, smallconversion on `vw_product`, a view per kind for BizBox's existing documents, the
MMnn numbers for the menu, and the role seed in §2.

## 7. Evidence

- MEASURED: `test_a_receiving_report_opens_as_a_document_with_its_lines_the_order_each_came_from_and_a_slip`.
- MEASURED: `test_rights_are_per_module_and_one_person_may_be_set_apart_from_their_role`: a pre-086 role reads its
  parent's level; Setup takes a module away and the entry leaves the menu and the page refuses; one person set apart
  gets it back on that module only; *Follow the role* returns them; the audit holds both steps; an override wins
  downwards too.
- MEASURED: `test_the_084_review_minor_fixes_and_the_stock_cards_buckets_on_movements`, including that a patient
  string in a remark appears nowhere.
- MEASURED: `python3 tools/sqlite_to_tsql.py --check` in step after 086.
- MEASURED: the full suite, `849 tests, OK (skipped=2), 369 s, on this exact tree`; the CI run named in the message.
