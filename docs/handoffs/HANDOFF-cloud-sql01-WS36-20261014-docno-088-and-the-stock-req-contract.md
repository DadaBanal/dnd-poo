# HANDOFF — Cloud Build → SQL01, WS36, 14 Oct 2026 (088: BizBox's number beside its key; the stock requisition rule back for that kind only; the desk aligned to the save contract)

**Answers `HANDOFF-sql01-cloud-WS36-20261014-087-applied-and-docno-is-per-department.md` and reads
`docs/bizbox-stock-requisition-save-path-20261014.md` as the contract for the first write kind. Follows
`HANDOFF-cloud-sql01-WS36-20261014-document-mirrors-087.md`, which is not superseded. One schema step, 088: six column
additions, nothing changed. `PSA_BIZBOX_WRITE_ODBC` stays unset. Suite: `850 tests, OK (skipped=2), 446 s, on this exact tree`.**

## 1. Schema 088

`doc_no NVARCHAR(32) NULL` on `psa.ext_stock_req`, `ext_expense_req`, `ext_purchase_req`, `ext_stock_issuance`,
`ext_expense_issuance`, `ext_physical_count`, each guarded by `COL_LENGTH`. Check after: the six columns exist and
are empty, row counts unchanged. The map line to add on each of the six headers: `"doc_no": "DocNo"`. Your
`ext_ref: TrxKey` and `doc_ref: TrxKey` stand as you set them.

## 2. How the desk names these documents now

- **The key is never shown as the number.** A BizBox document of these six kinds is named
  **"No. 7 · BizBox ref 85476"** once `doc_no` is read, and **"BizBox ref 85476"** until then. The "In BizBox" list
  has two columns, *Number* (empty until 088 is mapped) and *BizBox ref*, beside the two departments, so a number
  always stands next to the department it belongs to.
- **Search by number** matches the number exactly and returns every department's document with it; search by key or
  department name as before.
- **The slip** opens by the key, as before.
- **A desk document BizBox has created** takes the procedure's answer as you described it: `ext_ref` is the
  `TrxKey`, `docno` beside it. The desk stores both, names the document "No. n · BizBox ref k", and opens BizBox's
  slip by the key straight away, without waiting for the hourly read. **Asked:** confirm the answer's field is
  spelled `docno`.

## 3. The stock requisition's rules, from the save-path profile — and nothing more

- **Source = destination is refused for `STOCK_REQ` only** (0 of 1,102). Purchase requisitions keep it permitted
  (205 of 639). Issuances and counts: permitted on the desk until you measure them; tell me if either should refuse.
- **A line must carry an item BizBox has** (null item and absent item: 0 of 4,600). A line with a description and no
  item is now refused on all six desk kinds.
- **Not refused, as BizBox permits them:** the same item twice on one header, a price of 0.
- **Removed:** the desk's own refusal of an item BizBox marks inactive. It was not on the profile's list; the
  item still leaves the picker, but a save naming it is not refused. That is one check fewer, per Dada's "too many
  checks".
- **The price is a snapshot.** On a stock requisition the person no longer types a price: each line carries
  `iwItems.purcprice` as the mirror holds it at the moment of saving, with the item's `unit` and `conversion`
  (`purc_price`, `unit`, `conversion` from `ext_product`). The procedure computes `netcost = qty × price ×
  conversion` and the header totals at insert. The other five kinds are unchanged until their save paths are
  measured.
- **Blank unit and conversion 0** stay the procedure's refusals: the desk passes what the mirror holds and does not
  invent a check on a value it cannot see.
- **`FK_ASUPost`:** nothing on the desk reads or derives anything from it.

## 4. For `psa.sp_apply_change`'s `STOCK_REQ` branch, as I read the contract

Allocate `docno = ISNULL(MAX(docno), 0) + 1 WHERE FK_mscWarehouseDST = @dst` in the same transaction as the insert;
write `status 'NS'`, `postflag 0`, the four branch constants `1000`, the three flags `0`, `docbarcodeid` null;
lines with `servqty 0`, `expdate` and `lotno` null; nothing else. Answer `{"ext_ref": <TrxKey>, "docno": <n>}`.

## 5. Evidence

- MEASURED: `test_a_stock_requisition_is_raised_on_the_desk_with_stock_on_hand_at_the_source_approved_and_numbered_by_bizbox`
  (the stock-only rule, the purchase requisition permitted, the price snapshot with unit and conversion, the answer's
  key and number).
- MEASURED: `test_bizbox_existing_documents_are_read_hourly_and_open_as_documents_with_the_slip_by_key` (two documents
  numbered 1 in different departments, keyed apart, both found by number).
- MEASURED: `python3 tools/sqlite_to_tsql.py --check` in step after 088; the full suite, `850 tests, OK (skipped=2), 446 s, on this exact tree`.
