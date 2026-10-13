# HANDOFF — Cloud Build → SQL01, WS36, 13 Oct 2026 (BizBox's MMS in full on the desk: stock on hand, the item ledger, receiving lines, 084; the intake guard; the report server without pywin32)

**Three read-only views for the hourly read, one schema step (three tables, one column), one recovery step that waits
for Dada's word, and one thing you need not do any more. Nothing writes to BizBox.**

This follows your Part 81 (082 applied; lookup names confirmed; stock measured at **4,358** non-zero rows; the
package-free route to the report server proven) and Part 82 (the intake duplicate guard), and Dada's ask of the same
evening: *"a full render of the bizbox mms app into the procurement module but make it better … whichever is more
efficient: views based on time or days or months"*. It supersedes §4 of `…-20261013-warehouses-drugs-083.md` (the
measurement is done; the choice is made) and nothing else.

## 1. What Dada chose, 13 Oct 2026 (evening)

- **Stock on hand, mirrored hourly** like the other kinds, from a view narrowed to the rows with a quantity (your
  measurement: 4,358 of 591,369, smaller than the item list). Not read live.
- **Movements through a view kept to a window** — his words, *"views based on time or days or months"*: you keep the
  item ledger view to the last N days; the desk reads it hourly and deletes any row the view stops returning
  (`bizbox.WINDOWED`), so the desk never grows past the window and BizBox loses nothing.
- **Receiving lines**, as a purchase order's lines already are.
- **Procurement opens on an overview**; an item's page shows its stock and movements and raises a ticket about it.
- **The intake guard**: a resend is the same sender, the same subject **and the same words**. The 30 mails filed as
  resends are to be **raised as their own tickets, cross-linked** — by a previewed step you run, after his word (§5).

## 2. The three views, in `LiveDB_PMC`'s `psa` schema

Name the desk-side columns exactly as below; the map on the host carries BizBox's names. No patient table, no price
table (`iwItemPrices` is never read, as before), no `PMC_Backup_` or `zz_` table. Everything about BizBox's columns
below is **INFERRED** from the table names you have reported (`iwWareitem`, `iwItemLedger`, `iwItemLedgerDaily`,
`iwApitem`, `iwApinv`) and the one column you measured (`actualqty`); you name the real ones.

**`psa.vw_stock_on_hand`** from `dbo.iwWareitem WHERE actualqty <> 0` (**4,358** rows, MEASURED):

| Desk field | Your column | What it is |
|---|---|---|
| `warehouse_ref` | the warehouse code | joins `psa.vw_warehouse.ext_ref` |
| `item_ref` | the item code | joins `psa.vw_product.ext_ref` |
| `quantity` | `actualqty` | on hand, in the item's unit |
| `unit_cost` | a cost column on the row **if there is one that is not a price list**; else leave it out | the desk falls back to the item's unit cost |
| `as_of` | the row's last-updated date if the table has one; else `CAST(GETDATE() AS date)` | shown as "BizBox's as-of" |

No `ext_ref`: the desk makes the key as `<warehouse_ref>:<item_ref>`.

**`psa.vw_item_ledger`** from `dbo.iwItemLedger` (or `iwItemLedgerDaily` if that is the one with a balance per
movement), **kept to a window**: `WHERE <date> >= DATEADD(day, -90, CAST(GETDATE() AS date))` to start. **Measure
first**: the row count for 30, 90 and 365 days. The desk refuses a read over **50,000** rows (`MAX_ROWS`), so pick the
widest window under that; 90 days is the proposal, and Dada can widen or narrow it later without a desk change.

| Desk field | Your column | What it is |
|---|---|---|
| `ext_ref` | the ledger row's own id | **required**; the key |
| `item_ref` | the item code | required |
| `warehouse_ref` | the warehouse code | |
| `moved_on` | the transaction date | required |
| `kind` | the transaction type as BizBox stores it | the desk shows it as a word: receipt → Received, issue → Issued, transfer in/out, adjust, count, return; tell me BizBox's actual codes and I map them |
| `doc_ref` | the document number (RR, issue slip, transfer, adjustment) | |
| `qty_in`, `qty_out` | the in and out quantities (or one signed quantity split in the view) | |
| `balance` | the balance after the movement, if the table carries it | |
| `unit_cost` | the movement's unit cost if carried | |
| `remarks` | the row's remarks | words only; nothing of a patient's (an issue slip's "ward" is fine; a patient's name is not) |

**`psa.vw_receiving_line`** from `dbo.iwApitem` joined to `dbo.iwApinv` for the receiving number:

| Desk field | Your column | What it is |
|---|---|---|
| `ext_ref` | the line's own id | required |
| `rr_ref` | the receiving number | required; joins `psa.vw_invoice.ext_ref` (the desk's "invoice" is BizBox's receiving report) |
| `line_no` | the line number | |
| `product_ref` | the item code | |
| `description` | the line's description | |
| `quantity` | quantity received | |
| `unit_cost` | unit cost | |
| `po_ref` | the purchase order it was received against | joins `psa.vw_purchase_order.ext_ref` |

SELECT on all three to the read-only login, as for the others.

## 3. The map on the host (`D:\psa\bizbox-map.json`)

Three objects beside the others; the desk-side names are fixed, your column names go on the right:

```json
"stock":    {"view": "psa.vw_stock_on_hand",  "columns": {"warehouse_ref": "...", "item_ref": "...", "quantity": "...", "unit_cost": "...", "as_of": "..."}},
"movement": {"view": "psa.vw_item_ledger",    "columns": {"ext_ref": "...", "item_ref": "...", "warehouse_ref": "...", "moved_on": "...", "kind": "...",
                                                          "doc_ref": "...", "qty_in": "...", "qty_out": "...", "balance": "...", "unit_cost": "...", "remarks": "..."}},
"rr_line":  {"view": "psa.vw_receiving_line", "columns": {"ext_ref": "...", "rr_ref": "...", "line_no": "...", "product_ref": "...", "description": "...",
                                                          "quantity": "...", "unit_cost": "...", "po_ref": "..."}}
```

`check_map` refuses a stock object without `warehouse_ref`, `item_ref` and `quantity`, a movement object without
`ext_ref`, `item_ref` and `moved_on`, a receiving line without `rr_ref`, any view or column name with a patient word,
and a view whose name contains *price*. `bizbox/bizbox-map.sample.json` carries the note.

## 4. The step on the host

1. Pull the head that carries this file, once CI is green on it.
2. COPY_ONLY backup; stop PSA-Desk; apply **084** from `sqlserver/PMC_PSA_Spine_SqlServer.sql`: one `ALTER TABLE
   psa.intake_message ADD body_hash` and three `CREATE TABLE` blocks (`ext_stock`, `ext_movement`, `ext_rr_line`) with
   their indexes; verify the column (`COL_LENGTH(N'psa.intake_message', N'body_hash')` is 64) and that the three
   tables exist and are empty; start PSA-Desk. The desk shows the Overview and the Warehouses' holdings at once; the
   Stock on hand and Movements tabs say "not read from BizBox yet" until step 3.
3. The three views, the measurement in §2, the map; preview with `sync-bizbox` (the read's summary names *stock
   lines*, *movements*, *receiving lines*); let the hourly read run. The read banner on every Procurement page says
   what came in.
4. **Nothing to install for the MMS reports tab.** Your Part 81 finding is the fix: the desk now signs in through
   `C:\Windows\System32\curl.exe --negotiate` (`ssrs.CurlTransport`), picked up by itself on Windows when pywin32 is
   absent, so steps 10 and 11 of the 082 handoff (the first `sync-mms-reports` read, the walk-through) can be run as
   written. A 401 now says which it is: the Browser role (curl or pywin32 in use) or no Windows identity at all
   (Python's own client). `PSA_SSRS_CURL` names a curl elsewhere if ever needed.
5. The intake recovery, **after Dada's word** (he has given it to me; you run it when he says so to you):
   `python -m psaspine intake-split-duplicates <db>` previews, one line per mail: when it arrived, from whom, the
   ticket it was filed on, the board and summary it would get. Then `--apply`. Each becomes its own ticket, dated when
   it arrived, on the board its mailbox belongs to (or the parent's), with the words taken back from the note the
   import left on the parent, linked RELATED both ways, a note on each ticket saying what happened, the
   `intake_message` row turned to NEW_TICKET with `duplicate_of` kept, and an `INTAKE_SPLIT` audit row. The parent's
   note stays where it is. No acknowledgement mail is sent for the new tickets.

## 5. For the Bizbox Reporting SSRS session, through you

Dada: *"as sql01 to message bizbox chat for a similar build"*. The desk's full render of the MMS needs, after stock
and the ledger, the documents people actually raise (your Part 81's run counts say which: `StockReq` 3,023,
`MMS_ADHOC_ExpRequisition` 3,229, `ExpIssuance` 2,445, `DelReceiveRep` 2,982, `POSLIP` 2,979). Please ask that
session, and bring back:

1. For each of **stock requisitions, issuances, transfers, adjustments and physical counts, purchase requests**: the
   header table and the line table, their keys, the status column and its values, the date column, the department
   or requesting unit column, and the **rows per month** over the last six months.
2. The **supplier master** table (name, address-free contact fields, terms): which table, and whether any column
   is a person's private detail (then it stays out).
3. The item master's **reorder level, minimum, maximum and bin** columns, if BizBox keeps them, and the unit
   conversion table.
4. BizBox's own list of **ledger transaction types** (the `kind` codes in §2) with their meanings.

With those the desk's next step (085) is one generic document mirror (header + lines, kind-tagged, windowed like the
ledger) and a tab per document type, and the words on screen will be BizBox's. Nothing of it is built until the
volumes are known.

## 6. Evidence

`StockAndMovementsTest` (3: the read, the window moving, the fence; the overview, the tabs, the item and receiving
pages, the warehouses' holdings; a ticket raised from an item and linked), `EmailIntakeTest` (+3: the standing subject
line, the time order and the mailbox, the recovery), `MmsReportsTest` (+1: curl and the refusal's words). Port
`--check` in step. Screens on a throwaway desk with sample rows. Not run here: anything against BizBox or the report
server.
