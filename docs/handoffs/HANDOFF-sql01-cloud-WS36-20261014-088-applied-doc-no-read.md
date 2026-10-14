# HANDOFF — SQL01 → Cloud Build, WS36, 14 Oct 2026 (088 applied, `doc_no` mapped and read; `docno` confirmed as the procedure's answer; the restart waits on Dada)

**Answers `HANDOFF-cloud-sql01-WS36-20261014-docno-088-and-the-stock-req-contract.md`. Went on `sql-server` green
for `52b6433`, per Dada's "what are we waiting for" ruling this afternoon — that job runs the port against a real SQL
Server; `windows` buys nothing. `PSA_BIZBOX_WRITE_ODBC` stays unset.**

## 1. Done, in your order up to the restart

| Step | Result |
|---|---|
| Pull | `52b6433`, local = remote |
| Backup | `PMC_PSA_COPYONLY_pre088_20261014-151432.bak`, 32.2 MB |
| 088 | six `doc_no NVARCHAR(32) NULL` added from the port unretyped; no table added or removed (174 → 174); both controls clean; **committed, proven on a fresh connection** (all six `COL_LENGTH = 64`, a column that cannot exist null) |
| Map | `"doc_no": "DocNo"` on the six headers; `ext_ref: TrxKey` and `doc_ref: TrxKey` stand; 22 objects; `check_map` accepting; backup `.bak_20261014_151435` |
| Read | exit 0; **`doc_no` filled on every present header** — stock_req 1,067 (253 distinct numbers), expense_req 1,208 (264), purchase_req 646 (646), stock_issuance 990 (521), expense_issuance 1,090 (637), physical_count 99 (80) |

Sample, three stock requisitions all numbered 1: keys `114689`, `118642`, `126550`, requesting departments `1015`,
`1011`, `1018`. **The number is per department and the key is the identity**, exactly as the map now says.

**Not done: the restart.** Dada's go this afternoon covered one restart; this is a second, so it is his word. The
desk is serving `294aa2a`; the "No. 7 · BizBox ref 85476" rendering goes live when he says.

One thing of mine recorded plainly: my 088 apply script printed `VERDICT: FAIL` **after** a successful commit — a
verdict line carried over from 087 that still tested for twelve tables. The commit was then proven from a fresh
connection rather than inferred from the read. The script is corrected in the session record; the lesson is the
same as Part 100's, from the other side.

## 2. Your §3 — the field is spelled `docno`

Confirmed. `psa.sp_apply_change`'s result row widens from `(ok, message, ext_ref)` to
**`(ok, message, ext_ref, docno)`** — `ext_ref` the transaction key as `NVARCHAR(64)`, `docno NVARCHAR(32)` the
per-department number, both filled on a successful ADD, `docno` null on anything else. The column goes on with the
STOCK_REQ branch, not before, so the skeleton's shape does not change until there is something to fill it. Read the
row by name, never by position.

## 3. Your §4 and §5 — taken as written, two notes

- **Same department refused for STOCK_REQ only; purchase requisitions permitted; issuances and counts permitted until
  measured.** Agreed, and the procedure will refuse exactly what the client refuses and nothing more: no lines, `qty
  ≤ 0`, an item BizBox does not have, source = destination (stock requisitions), blank unit, `conversion` 0 or null.
  Duplicate items and zero prices pass.
- **Removing the desk's inactive-item refusal:** right by the profile, which found no column to answer it. One
  caution so it is not a surprise later — an inactive item can still be *picked* on the desk now, and whether the
  vendor client lets one be picked is **not established**. If the first Training push with an inactive item is
  refused by BizBox, that is the answer, and the desk's refusal comes back for that case only.
- **Your reading of the contract (§5)** matches mine: `docno = MAX(docno) + 1 WHERE FK_mscWarehouseDST = @dst`
  inside the insert's own transaction, `status = 'NS'`, `postflag = 0`, the four constants `1000`, `price` a snapshot
  of `purcprice` sent from the desk and never re-read, `netcost` computed at insert, `servqty = 0`, nothing written
  outside the two tables. `FK_ASUPost` is written at save with a meaning that is not established; the procedure will
  write what the client writes and the desk derives nothing from it.

## 4. Also today, on the host

- **Ethel Luciano** holds *See* on Drugs as a per-person override (086), audited under `SECURITY_ROLE` exactly as
  Setup writes it — the one Procurement module her role gave her nothing on. She keeps Approve on items, purchase
  orders and receiving from `PROCUREMENT_APPROVER_TECHNICIAN`. Dada has been offered the ceiling (See on all ten,
  Approve removed) and has not yet said.
- PMC_PSA is at 083 + 084 + 085 + 086 + 087 + 088. Both BizBox databases hold 22 `psa` views, `fn_item_ledger` and
  the procedure skeleton. Nothing written to a BizBox table.

Scripts in the session record: `apply-088.py`, `map-088.py`.
