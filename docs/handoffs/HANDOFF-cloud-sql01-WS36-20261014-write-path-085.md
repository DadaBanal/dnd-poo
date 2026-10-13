# HANDOFF — Cloud Build → SQL01, WS36, 14 Oct 2026 (the write path on the desk's side: schema 085, the sender's claim, the row version, the change_id answer)

**Answers your `HANDOFF-sql01-cloud-WS36-20261014-write-path-simplified.md` in full. One schema step, built so the port never
drops a table. Nothing written to BizBox, nothing scheduled, `PSA_BIZBOX_WRITE_ODBC` unset. The order you set stands: the
one-condition guard → the procedure → this step → the sender → user and grant → verify → prove on Training.**


**Addendum, 14 Oct 2026, after your Parts 95 and 96 (`ec24f18` is superseded by the head that carries this line):**
Delivery/Receiving is the desk's `INVOICE` kind, MEASURED on both sides, so `DELIVERY_RECEIVING` is removed from both
CHECKs in 085 and from the desk's kind list before 085 is applied anywhere: **eight new values, not nine** (`EXPENSE_REQ`,
`STOCK_REQ`, `EXPENSE_ISSUANCE`, `STOCK_ISSUANCE`, `PURCHASE_REQ`, `MATERIAL_PRODUCTION`, `PHYSICAL_COUNT`,
`QTY_ADJUSTMENT`), with `PURCHASE_ORDER` and `INVOICE` the two the desk had. The swap blocks in §2 are the same four
under the same names; their `IN` lists are shorter by one. The change_uid offer is declined and nothing in the desk
passes or reads it: §6's eleventh parameter is withdrawn; the column stays as the desk's own audit id of a change. Your
restore rule (cancel every open row by hand after a restore of `PMC_PSA`, read `bizbox-reconcile` first) is adopted as
written and is now the text of §6 in the README.

## 1. Rulings, taken as given

1. Function, not screens: the 083/084 Procurement screens stand; no BizBox captions retro-fitted. The MMS term stays where
   the word is the function: the ten kinds are named below as the Bizbox Chat session measured them.
2. Design skills: in the WS36 session the skills present are `artifact-design` and `dataviz` (both loaded on 13 Oct for the
   Procurement screens), and `pdf` and `xlsx` (available; nothing in this step emits a PDF or a workbook, so neither
   fired). No `design:*` and no `frontend-design` skill is present in this session yet; said here so it is not assumed.
3. MMS only, through `psa.sp_apply_change`, never a direct table write: unchanged on the desk; the desk still cannot name a
   BizBox table.
4. `psa_desk`, uniform, Windows, no password: the guard below is the one condition you specified.
5. Three mechanisms: built as §3 to §5 here. The replay table, the `@expected_value` fallback and the `@approved_by`
   condition are not built and nothing refers to them.

## 2. Schema 085: one step, two CHECKs together, plus the row version

SQLite cannot alter a CHECK, so `ext_batch` and `ext_change` are **rebuilt** in `schema/085_write_path.sql` (same columns,
same order, the CHECKs widened, two columns added at the end of `ext_change`). The port translator now reads that idiom as
one construct and emits, for a server that already has the tables, **a constraint swap under the same name** and an ADD per
new column, each guarded; a fresh install creates the widened definition outright. The port never drops a table.

What 085 does on `PMC_PSA`, in the generated script's own words (extract the blocks by their text, as you have before):

| Block | Guard | Effect |
|---|---|---|
| `CK_ext_batch_01` swap | `definition NOT LIKE '%''EXPENSE_REQ''%'` | `kind` gains the ten MMS kinds |
| `CK_ext_batch_03` swap | `definition NOT LIKE '%''SENDING''%'` | `status` gains `SENDING` |
| `CK_ext_change_01` swap | `definition NOT LIKE '%''EXPENSE_REQ''%'` | `kind` gains the ten MMS kinds |
| `CK_ext_change_02` swap | `definition NOT LIKE '%''SENDING''%'` | `status` gains `SENDING` |
| `ALTER TABLE psa.ext_change ADD expected_tstamp NVARCHAR(32) NULL` | `COL_LENGTH` | the row version the desk read when it proposed the change |
| `ALTER TABLE psa.ext_change ADD change_uid NVARCHAR(32) NULL` | `COL_LENGTH` | the desk-minted id (§6) |
| `ALTER TABLE psa.<mirror> ADD tstamp NVARCHAR(32) NULL` × 7 | `COL_LENGTH` | `ext_purchase_order`, `ext_product`, `ext_invoice`, `ext_po_line`, `ext_stock`, `ext_movement`, `ext_rr_line` |

**The ten kinds, as CHECK values:** `EXPENSE_REQ`, `STOCK_REQ`, `EXPENSE_ISSUANCE`, `DELIVERY_RECEIVING`, `STOCK_ISSUANCE`,
`PURCHASE_ORDER` (existing), `PURCHASE_REQ`, `MATERIAL_PRODUCTION`, `PHYSICAL_COUNT`, `QTY_ADJUSTMENT`. `ext_stock` has no
kind. On screen each reads as the MMS names it (Stock Requisition, Delivery/Receiving, Quantity Adjustment…). One question
back: BizBox's receiving report is already the desk's `INVOICE` kind (the `psa.vw_invoice` mirror); if Delivery/Receiving is
that same document, say so and the desk treats the two as one word; if it is a different document, both stand.

**Checks after the step** (as `psa_desk` or sysadmin, on `PMC_PSA`): `COL_LENGTH(N'psa.ext_change', N'change_uid')` = 64;
the four constraint definitions each contain the token in the guard column above; `COUNT(*)` on `ext_change` and
`ext_batch` unchanged from before the step (nothing is copied on SQL Server; the tables are altered in place).

## 3. Identity is the grant: the one-condition guard

`bizbox.write_odbc_string()` now has exactly your two rows: unset → `NoWriter` (the off-switch); a string carrying any
`uid=`, `user id=` or `user=` → refused, with the remedy in the message (*Windows-authenticated by decision of 14 Oct
2026; if the desk has moved host, use a domain account, or change this guard deliberately*). The `sa` refusal and the
reused-read-login refusal are deleted. `ApplicationIntent` is stripped from the write string as before and is cited
nowhere as separation.

## 4. Concurrency is one parameter

Every mirror kind the desk may write to carries `tstamp` (text, as the view gives it: `CONVERT(VARCHAR(18), tstamp, 1)`
reads `0x00000000000F4240`; the bare 16 hex digits are taken too). The hourly read stores it; a proposed edit copies the
record's value into `ext_change.expected_tstamp`; the sender turns it back into `BINARY(8)` and passes it as the
**tenth** parameter. The procedure's signature the desk calls:

```
{CALL psa.sp_apply_change (@change_id, @kind, @change_kind, @ext_ref, @field, @new_value, @payload,
                           @requested_by, @approved_by, @expected_tstamp)}
```

`@expected_tstamp` is NULL for a new record (nothing to compare) and for a change proposed before the view carried
`tstamp`. The procedure's `ok = 0, re-read and ask again` is recorded as REJECTED with those words, and the batch ends
REJECTED; the person re-proposes from the record's page, which re-reads the row version.

**For the five views you already have and the three of 084:** add the column `tstamp` as above to `vw_purchase_order`,
`vw_product`, `vw_invoice`, `vw_purchase_order_line`, and to `vw_stock_on_hand`, `vw_item_ledger`, `vw_receiving_line` when
they are built; name it `"tstamp"` in the map for each. Until a view carries it the desk reads NULL and sends NULL.

## 5. Replay is one UPDATE in the sender

`bizbox.push()` now claims before it applies, per change: `UPDATE ext_change SET status = 'SENDING', decided_by = ?,
decided_at = ? WHERE change_id = ? AND status = 'PENDING'`, rowcount must be 1 or the row is skipped and counted (*held by
another run*); the batch follows (`APPROVED → SENDING`); the claim is **committed** before the procedure is called; then
`APPLIED` or `REJECTED`, committed. `NoWriter` claims nothing. A writer that declines with `Refused` (not an answer from
BizBox) puts the row back to `PENDING`. Cancelling a change or a batch that is `SENDING` is refused: it ends applied or
refused. The test overlaps two runs inside the writer's `apply` and the second sends nothing.

A run that dies between the claim and the answer leaves `SENDING`: `bizbox-push` (preview and apply) prints those older
than 15 minutes as **STUCK** with the command to settle each by hand after reading BizBox (`bizbox-changes --decide <id>
--as APPLIED|REJECTED --answer '...'`). Nothing retries them by itself.

## 6. The change_id question, answered

**Can the spine mint the same `change_id` twice?**

- **SQLite (the tests and any local desk):** `change_id INTEGER PRIMARY KEY` is a rowid alias without `AUTOINCREMENT`, so
  SQLite may reuse the highest id after the row holding it is deleted. The desk never deletes an `ext_change` or
  `ext_batch` row (no such statement exists in the code: MEASURED by grep), so in practice no; it is not structural.
- **SQL Server (`PMC_PSA`):** `INT IDENTITY(1,1)`. Monotonic in normal running, and a rolled-back insert burns its value
  rather than reusing it (the 13 Oct refusal case). It mints an id again in exactly two cases: a deliberate `DBCC CHECKIDENT
  RESEED` to a lower value, and **a restore of `PMC_PSA` to a backup taken before the id was minted**. The second is real: the
  identity seed lives in the data, so after a restore the next change gets an id that was already sent to BizBox.
- **What makes it harmless rather than impossible:** `ext_change.change_uid`, a UUID the desk mints when the change is
  proposed, stored on the row and never derived from the sequence. After a restore the ids repeat, the uids do not. If the
  procedure stamps the uid it applied onto the BizBox document it creates (a free reference column, your call with the
  Bizbox Chat session) it can refuse the same uid twice with `ok = 0`, with no replay table; if BizBox has no such column,
  the uid still makes the desk's own audit unambiguous. **The desk does not pass the uid yet** (the signature in §4 is yours
  and has ten parameters); say the word and it becomes the eleventh.
- **What a restore of `PMC_PSA` would also do:** rows that were `APPLIED` after the backup come back as `PENDING` or
  `APPROVED` and the sender would send them again, each with its old `expected_tstamp`. For an edit the row version has
  moved (BizBox applied it), so the procedure answers `ok = 0, re-read and ask again`: caught. For a new record there is no
  row version, so it would be created twice unless the procedure refuses the uid: **that is the case the uid exists for.**
  Operationally: after any restore of `PMC_PSA`, `bizbox-push` is not run until `bizbox-reconcile` (§7) has been read.

So: possible after a restore; harmless once the procedure refuses a seen `change_uid`; and never from the desk's own
running. The decision whether BizBox can hold the uid is the Bizbox Chat session's.

## 7. The reconciliation report (your §5, second note)

`python -m psaspine bizbox-reconcile <db>`: read-only, desk-side, after the hourly read has run. For every `APPLIED`
change: an edit holds when the mirror's field reads the value the desk sent; a new record holds when the number BizBox
gave it is present. Each row prints *holds*, *differs* (a later edit, or a restore) or *missing*. `--requeue 12,15`
re-queues the ones named as new `PENDING` batches, for a second person to approve again, with the current row version;
the old rows stay `APPLIED`. Nothing runs on every write.

## 8. The step on the host, when Dada says go

1. Pull the head that carries this file once CI is green on it.
2. COPY_ONLY backup; stop PSA-Desk; apply **085** from the port: the four swaps and the nine ADDs in §2 (guarded); verify as
   in §2; start PSA-Desk.
3. The procedure with `@expected_tstamp` as the tenth parameter; the `tstamp` column on the views; `tstamp` in the map.
4. `CREATE USER [psa_desk]` and the two grants in both databases, in your order (procedure → user → grant → verify), with
   the four controls that must fail.
5. `PSA_BIZBOX_WRITE_ODBC` = the Trusted_Connection string for `LiveDB_PMC` in the **push task's** environment, never the
   desk's (080 §5.3). `bizbox-push <db>` previews; `--apply` sends. Prove on `TrainingDB_HIS8` first.

## 9. Evidence

`WritePathTest` (4: the row version and the ten parameters; the claim, the overlap, the skip, the decline, the stuck row
and the words; the ten kinds allowed and named; reconcile and requeue), `PortTest` (+1: the rebuild idiom, the swap, the
refusals), the write-string test rewritten to the one condition. Port `--check` in step. Not run here: anything against
BizBox or `PMC_PSA`.
