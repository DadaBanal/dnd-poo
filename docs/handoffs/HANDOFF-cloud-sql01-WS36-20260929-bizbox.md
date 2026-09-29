# HANDOFF-cloud-sql01-WS36-20260929-bizbox

**From:** Cloud Build (WS36 PSA desk). **To:** SQL01, the row with the route to
`DND-SQL01`. **Date:** 29 Sep 2026. **Branch:** `claude/psa-ticketing-build`.

## Why this exists

Dada's direction (29 Sep 2026): finance, agreements and procurement are
BizBox's. Dada PSA shows them beside the work, and makes room to send edits
back later, but keeps no ledger of its own. The desk side is built:
schema 043 mirrors agreements, products, purchase orders (with lines) and
invoices; `psaspine sync-bizbox` fills the mirror; the Finance pages show it
and link it to tickets and projects; a change log records proposed edits
without touching BizBox.

What the desk cannot do from the cloud is see BizBox. That is this handoff.

## What the record already says about BizBox (MEASURED, build scope §8.1)

BizBox is the live hospital information system on `DND-SQL01`, with a
173-finding audit open, `sa` enabled, SSRS running as Enterprise Admin and
the Domain firewall profile disabled. **It holds patient records.** Every step
below keeps the desk away from them.

## The fence (built into the desk, and why each step below looks the way it does)

- The desk reads **only views named in a map file**, only the columns named
  there, with `SELECT TOP (50001)` and nothing else.
- Every name must be a plain identifier. A name that looks like a patient
  table or field (patient, admission, diagnosis, PhilHealth, case number,
  birth date, first or last name, doctor, lab result and the like) is
  refused before any query is sent.
- The ODBC login may not be `sa`; the connection asks for read-only intent.
- The connection string lives in `PSA_BIZBOX_ODBC` on the host, never in the
  repo. The real map lives on the host too (`D:\psa\bizbox-map.json`).
- Preview is the default: nothing is written without `--apply`.
- Nothing in the desk writes to BizBox. Proposed edits wait in `ext_change`.

## Steps

**1. Discover, read-only, and report names only.**
In the BizBox database, list the tables that hold agreements or contracts,
items or products, purchase orders and their lines, and supplier invoices.
Report back **table and column names only** (no rows, no counts of patients,
nothing from any clinical table). **Pass:** a list in the Reply below, each
table named with the columns that would fill each field in
`bizbox/bizbox-map.sample.json`.

**2. Views for the desk, in their own schema.**
After Dada approves the list, create a schema `psa` in the BizBox database and
one view per kind (`psa.vw_agreement`, `psa.vw_product`,
`psa.vw_purchase_order`, `psa.vw_purchase_order_line`, `psa.vw_invoice`) that
selects only those columns, renamed if a name would trip the patient-word
fence. **Pass:** each view returns rows, and none joins a clinical table.

**3. A read-only login that can see only those views.**
Create a SQL login (for example `psa_bizbox_reader`), a user for it in the
BizBox database, `GRANT SELECT ON SCHEMA::psa`, and nothing else: no role
membership, no other grant. **Pass:** as that login, `SELECT` from a view
works, and `SELECT TOP 1 *` from any base table fails with permission denied.
The password is typed on the host and stored only in the connection string
on the host.

**4. The map and the connection string, on the host.**
Copy `bizbox/bizbox-map.sample.json` to `D:\psa\bizbox-map.json`, set the
real view and column names, and set `PSA_BIZBOX_ODBC` in the desk task's
environment (the same way as the other `PSA_*` settings). **Pass:**
`psaspine sync-bizbox $db --map D:\psa\bizbox-map.json --odbc` (preview)
prints one line per kind with plausible counts and "preview only".

**5. Apply, then schedule.** Run it once with `--apply` as the task account;
then a scheduled task every hour, `--apply`, logging to `D:\psa\logs`.
**Pass:** Finance on `desk.pmcne.ph` shows the rows, the Setup › BizBox card
says when it last synced, and one `BIZBOX_SYNC` audit row per run.

**6. Edits back to BizBox: not now.**
`psaspine bizbox-changes $db` lists the changes people have proposed, as
JSON. When someone makes one in BizBox by hand, close it with
`psaspine bizbox-changes $db --decide <id> --as APPLIED --answer "done in BizBox by <name>"`.
A real write path (a BizBox API or a stored procedure BizBox's owner
approves) is a later decision; the desk has a `Writer` hook for it and the
one in force today refuses everything.

## Reply

### Part 1: 2026-09-29, about 11:05 +08:00. **Step 1: the names. Four kinds map, agreements have no home in BizBox, and one decision is Dada's. Stopped here for his approval.**

**How it was read.** Everything is MEASURED unless marked otherwise.

- Only `LiveDB_PMC`'s catalog was read:
  - `sys.tables`, `sys.columns`, `sys.indexes`, `sys.foreign_keys` and `sys.sql_expression_dependencies`;
  - the code of two BizBox report views.
- The login was SQL01's own Windows login, with read-only intent.
- **No table was read and no row was counted.** Tables named `ps*`, `emd*` or `hr*`, and tables with a clinical word in the name, never had their columns listed.
- The database holds 1,522 tables and 264 views, all in `dbo`. Procurement is BizBox's MMS module (`iw*`); finance is its FMS module (`fa*`).

**purchase_order ← `iwPOinv`** (the PO header, key `PK_TRXNO`)

| Field | Column | Note |
|---|---|---|
| ext_ref | `docno` | The PO number. Only `PK_TRXNO` has a unique index. Step 2 should check `docno` for duplicates and fall back to `PK_TRXNO` if any exist |
| vendor | `FK_faVendors` | Where the name comes from is the decision below |
| ordered_on | `docdate` | |
| status | `postatus`, `postflag`, `approvalflag`, `cancelflag`, `deleteflag` | A CASE in the view. What `postatus`'s codes mean is NOT VERIFIED |
| total | `netcurramt` | Paired with `currency`. `netlocamt` is the same amount in pesos (INFERRED from the names) |
| currency | `FK_mscCurrencies` | A code |

**po_line ← `iwPOitem`** (key `PK_iwPOitem`)

| Field | Column | Note |
|---|---|---|
| ext_ref | `PK_iwPOitem` | |
| po_ref | `FK_TRXNO`, then `iwPOinv.docno` | Must equal the purchase order's ext_ref |
| line_no | none | BizBox keeps no line number. Use `ROW_NUMBER()` over `PK_iwPOitem` within `FK_TRXNO` |
| product_ref | `FK_iwItems` | Equals `iwItems.PK_iwItems` |
| description | `itemSpec`, else `iwItems.itemdesc` | |
| quantity | `qty` | `qtyapproved` also exists |
| received_qty | `servqty` | "Served" is INFERRED. Cross-check it against the sum of `iwApitem.qty` by `iwApitem.FK_iwPOitem`; that link is MEASURED |
| unit_cost | `price` | |

**product ← `iwItems`** (key `PK_iwItems`, a text item code)

| Field | Column | Note |
|---|---|---|
| ext_ref | `PK_iwItems` | |
| name | `itemdesc` | |
| category | `FK_mscItemCategory` (a code), or `itemgroup` | |
| unit | `unit` | |
| unit_cost | `avgcost` | `purcprice` and `lastpurcprice` also exist |
| (filter) | `isInventory = 1`, `isactive = 1` | The item master also holds services: it carries `FK_mscExamTypes`, `FK_mscCPTSections`, `FK_mscDoctorServiceClass` and `FK_mscPHICCategory`. Products should be stock items only |

**invoice ← `iwApinv`** (key `PK_TRXNO`)

This is BizBox's receiving report, which carries the supplier's invoice. BizBox's own view `vwReportMMSIwAPINV` labels three of its columns: `docno` as RRNo, `docdate` as RRDate and `refno` as invoiceno.

| Field | Column | Note |
|---|---|---|
| ext_ref | `docno` | The receiving number. It has no unique index, so step 2 checks it as for purchase orders. The supplier's own invoice number is `refno`: staff type it and it can repeat across suppliers. The desk's invoice kind has no field to hold it (a WS36 choice) |
| party | `FK_faVendors` | The decision below |
| invoiced_on | `refdate` | The date of the supplier's invoice (INFERRED: it is paired with `refno`). `docdate` is the receiving date |
| due_on | none stored | `refdate` + `terms` (a number; that it counts days is INFERRED). `FK_mscTerms` is a terms code |
| status | `postflag`, `cancelflag`, `deleteflag`, `balance`, `paidamt` | For example cancelled, paid (`balance` 0) or open |
| total | `netcurramt` | As for purchase orders |
| currency | `FK_mscCurrency` | |
| agreement_ref | none | BizBox has no supplier agreements (below) |

The lines are in `iwApitem`: `FK_TRXNO`, plus `FK_iwPOitem` back to the PO line. The desk has no invoice-line kind, so they are not needed. `iwApinv.FK_TRXNO_VP` links to the AP voucher.

**agreement: BizBox has nothing to map.**

- No supplier-agreement or contract table exists outside the excluded families.
- `faContracts` and `faContractItems` are **patient coverage contracts**, as their column names show: `FK_psPatRegisters`, `FK_emdPatients` and `FK_psPatitem`. Excluded.
- Two more tables are excluded:
  - `faInvoiceMstr`, which is patient and customer billing (`FK_psPatregisters`);
  - `faVPMstr`, the AP vouchers, which also pay professional fees and carry PhilHealth fields.
- So Finance › Agreements stays empty unless Dada names where supplier agreements are kept.

**The decision for Dada: the supplier's name.**

- `faVendors` has **no name column**. Its other columns are `suppid` (the supplier code), status, terms, TIN and bank.
- Its key `PK_faVendors` is declared as a foreign key to **`psDatacenter`**. So are `iwPOinv.FK_faVendors` and `iwApinv.FK_faVendors`.
- BizBox's own procurement reports all get the supplier's name from `dbo.udf_GetFullName(FK_faVendors)`. The reports are `vwReportPRToPO`, `vwReportMMSIwAPINV` and `vwReportReceivingRep`. The function reads only `psDatacenter`.
- BizBox's vendor view `MIGHS8VENDOR` joins `faVendors` to `psDatacenter` and `psPersonaldata`, and carries first, middle and last name columns.
- `faVendors` has an `isDoctor` flag.
- INFERRED: `psDatacenter` is BizBox's single register of people and organisations, holding patients, doctors and suppliers together. **A supplier's name therefore comes only from the table that also holds patients.**

| Option | What Finance shows | What the view touches |
|---|---|---|
| **(a) Code only** | `faVendors.suppid` | Nothing in `ps*`. Meets step 2's Pass as written ("none joins a clinical table") |
| **(b) Name** | `dbo.udf_GetFullName(FK_faVendors)`, BizBox's own function, reached by a vendor key only | `psDatacenter`, one row per vendor key. The desk's login still sees only the `psa` views (step 3). Step 2's Pass would need rewording |
| **(b′) Name, except doctors** | As (b), but a vendor flagged `isDoctor = 1` shows its code | As (b) |

**SQL01's pick is (b′). This is INFERRED; the decision is Dada's.** The key only ever reaches vendor rows, and the function is BizBox's own. Doctors are the one group of people among the vendors, and they stay as codes.

**What approval releases.** Steps 2 and 3 are the first writes to `LiveDB_PMC` in this work: a schema, four views (not five, since there are no agreements), a login and a user. None of them runs until Dada approves:

- this list;
- (a), (b) or (b′);
- where agreements come from, if anywhere.

### Part 2: 2026-09-29, 11:20 +08:00. **Step 2 done: schema `psa` and four views in `LiveDB_PMC`, with Dada's (b). Stopped before step 3, which needs one decision.**

**Dada's answer to part 1, 29 Sep, verbatim: "b".** SQL01 read it as:
- the list is approved;
- the supplier's name comes from BizBox's own `udf_GetFullName`, doctors included;
- agreements stay empty.

**What the data settled.** All MEASURED. Only the procurement tables were read, and only as counts and codes; no row's content is recorded here.

| Question from part 1 | Answer |
|---|---|
| Is the PO `docno` unique? | Yes: 526 of 526 not deleted. It becomes `PONo` |
| Is the receipt `docno` unique? | Yes: 634 of 634. It becomes `ReceivingNo`, the invoice's ext_ref |
| Is the supplier's `refno` unique? | No: 626 distinct of 634, one of them repeated within a single supplier. It is not a key |
| What does `postatus` mean? | FS, PS and NS mean all, some or none of the PO's lines received. Checked line by line: 234, 40 and 236 POs |
| Is `servqty` the received quantity? | Yes: it equals the sum of receipts on all 1,432 PO lines. It becomes `QtyReceived` |
| Which PO total? | `netcurramt`. It matches the lines on 524 of 526 POs (`netlocamt` on 512), and BizBox's own PO reports read it in 7 of 9 |
| Which receipt total? | `netlocamt`. It matches the lines on 634 of 634 (`netcurramt` on 613) |
| Paid or not? | **Not knowable from these tables.** `balance` and `paidamt` are 0 on every receipt row. So an invoice's status is Cancelled, Posted or Draft |
| `itemSpec`? | Blank on all 1,432 lines, so the description is the item's `itemdesc` |
| Currency? | PHP on every row |
| `terms`? | 30, 15, 7, 4, 0 or 60: days. DueDate is the invoice date plus terms |
| Vendors? | All 169 vendors on POs and receipts resolve to a name, and none is flagged `isDoctor`. One receipt has the AP type "Doctor" (1002); it is included under (b) |

**Before the change.** All MEASURED:
- `LiveDB_PMC` had no schema `psa` and nothing outside `dbo`;
- there is no DDL trigger at database or server level;
- the database is not in an availability group;
- its last backups were the full at 22:01 on 28 Sep, the differential at 07:00 on 29 Sep and the log at 11:15.

**The change, at 11:20.** One transaction, as SQL01's sysadmin, from `bizbox-step2.py` on SQL01:
- `CREATE SCHEMA psa AUTHORIZATION dbo`;
- the four views defined below, with no agreement view.

The views are **not schema-bound**, so they can never block a BizBox upgrade: if an upgrade renames a column, the desk's sync fails and says so, and BizBox is untouched. To reverse: drop the four views, then the schema (`bizbox-step2.py reverse`).

**Pass.** Dada's (b) rewords the Pass "none joins a clinical table" to: none does, except for the supplier's name. That comes from BizBox's own `udf_GetFullName` over `psDatacenter`, reached by the vendor key only.

| View | Rows returned to the desk's own query | Reads | Desk's fence |
|---|---|---|---|
| `psa.vw_product` | 5,113 | `iwItems`, `iwPOitem` | PASS |
| `psa.vw_purchase_order` | 526 | `iwPOinv`, `udf_GetFullName` | PASS |
| `psa.vw_purchase_order_line` | 1,399 | `iwPOitem`, `iwPOinv`, `iwItems` | PASS |
| `psa.vw_invoice` | 634 | `iwApinv`, `udf_GetFullName` | PASS |

Three more checks passed:
- no view has a duplicate key;
- every PO line's PO and item are in the other two views;
- no supplier name is blank.

**The map for step 4.** The desk's own `check_map` accepts it. It uses the sample map's column names, except that the invoice's ext_ref is `ReceivingNo`, and it has no `agreement` and no `agreement_ref`.

```sql
CREATE VIEW psa.vw_product AS            -- stock items, active, plus any still on a PO line
SELECT CAST(i.PK_iwItems AS nvarchar(64)) AS ItemCode, i.itemdesc AS ItemName,
       CAST(i.FK_mscItemCategory AS nvarchar(20)) AS Category, i.unit AS Unit, i.avgcost AS UnitCost
FROM dbo.iwItems AS i
WHERE i.isInventory = 1
  AND (i.isactive = 1 OR EXISTS (SELECT 1 FROM dbo.iwPOitem AS l WHERE l.FK_iwItems = i.PK_iwItems));

CREATE VIEW psa.vw_purchase_order AS
SELECT CAST(p.docno AS nvarchar(20)) AS PONo, dbo.udf_GetFullName(p.FK_faVendors) AS VendorName,
       p.docdate AS PODate,
       CASE WHEN p.cancelflag = 1 THEN N'Cancelled'
            WHEN ISNULL(p.postflag, 0) = 0 AND p.approvalflag = 1 THEN N'Approved'
            WHEN ISNULL(p.postflag, 0) = 0 THEN N'Draft'
            WHEN p.postatus = N'FS' THEN N'Received'
            WHEN p.postatus = N'PS' THEN N'Partly received'
            ELSE N'Ordered' END AS Status,
       p.netcurramt AS TotalAmount, p.FK_mscCurrencies AS Currency
FROM dbo.iwPOinv AS p
WHERE ISNULL(p.deleteflag, 0) = 0;

CREATE VIEW psa.vw_purchase_order_line AS
SELECT CAST(l.PK_iwPOitem AS nvarchar(20)) AS LineID, CAST(p.docno AS nvarchar(20)) AS PONo,
       CAST(ROW_NUMBER() OVER (PARTITION BY l.FK_TRXNO ORDER BY l.PK_iwPOitem) AS int) AS [LineNo],
       CAST(l.FK_iwItems AS nvarchar(64)) AS ItemCode,
       COALESCE(NULLIF(LTRIM(RTRIM(l.itemSpec)), N''), i.itemdesc) AS Description,
       l.qty AS QtyOrdered, l.servqty AS QtyReceived, l.price AS UnitCost
FROM dbo.iwPOitem AS l
JOIN dbo.iwPOinv AS p ON p.PK_TRXNO = l.FK_TRXNO
LEFT JOIN dbo.iwItems AS i ON i.PK_iwItems = l.FK_iwItems
WHERE ISNULL(p.deleteflag, 0) = 0;

CREATE VIEW psa.vw_invoice AS            -- BizBox's receiving report, which carries the supplier's invoice
SELECT CAST(a.docno AS nvarchar(20)) AS ReceivingNo, dbo.udf_GetFullName(a.FK_faVendors) AS VendorName,
       COALESCE(a.refdate, a.docdate) AS InvoiceDate,
       DATEADD(day, ISNULL(a.terms, 0), COALESCE(a.refdate, a.docdate)) AS DueDate,
       CASE WHEN a.cancelflag = 1 THEN N'Cancelled' WHEN a.postflag = 1 THEN N'Posted' ELSE N'Draft' END AS Status,
       a.netlocamt AS TotalAmount, a.FK_mscCurrency AS Currency
FROM dbo.iwApinv AS a
WHERE ISNULL(a.deleteflag, 0) = 0;
```

**Step 3 needs one decision from Dada: which identity reads the views.**

- **As written:** a new SQL login whose password Dada types, kept in `PSA_BIZBOX_ODBC`.
  - The desk's `PSA_*` settings sit in the PSA-Desk task's PowerShell command line (MEASURED).
  - `D:\psa\logs\PSA-Desk.log` already prints part of that line on every start, in the `NativeCommandError` wrapper (MEASURED).
  - So a password kept there could land in a log file (INFERRED). The hourly sync task in step 5 would carry the same string.
- **SQL01's pick: the desk's own Windows account.**
  - Create a user for `DND-SQL01\psa_desk` in `LiveDB_PMC` with `GRANT SELECT ON SCHEMA::psa` and nothing else, and set `PSA_BIZBOX_ODBC` with `Trusted_Connection=yes`.
  - **No password exists anywhere**, and the Pass is the same.
  - `public` holds no grant on any `dbo` table (MEASURED: its object grants are on 195 `sys` catalog views and on 22 objects the catalog does not list), so the user inherits nothing that reaches a base table.
  - The desk's code needs no change: `odbc_string` refuses only `sa`.

### Part 3: 2026-09-29, 11:47 +08:00. **Step 3 PASS: the desk's own SQL login. Step 4 is ready and dry-run; one run of Dada's registers the hourly sync (step 5).**

**Dada's answers, 29 Sep, verbatim and in order:**
1. "active directory accounts"
2. "there should be a bizboxsa account"
3. "no sorry"
4. "no use sql to read and write thats what i meant"

SQL01 read the last one as: a SQL login, as step 3 is written. Two points came up on the way (MEASURED):

- **`bizboxsa` exists, and it is BizBox's own login.** It is db_owner of `LiveDB_PMC`, and BizBox had 96 sessions open on it during the check. **Not used.** The desk would inherit every right BizBox has, patient tables included, on BizBox's own password.
- **"Write":** the desk has no BizBox writer today; the one in force is `NoWriter`. The desk's own account writes the mirror in `PMC_PSA`. When a write path is built, it gets exactly the rights it needs.

**Step 3: Dada ran `D:\psa\bin\New-PsaBizboxLogin.ps1` at 11:40.**

- It created the SQL login `psa_bizbox_reader`: policy checked, no expiry, and a random 32-character password that nobody saw or typed.
- In `LiveDB_PMC`, the login has a user with SELECT on schema `psa` and nothing else.
- The connection string is only in `D:\psa\bizbox.odbc`, which SYSTEM, Administrators and the desk's task account can open.
- **Pass**, tested by logging in as the new login:
  - the four views read: 5,113, 527, 1,400 and 636 rows;
  - `iwPOinv`, `iwItems`, `faVendors`, `psDatacenter` and `udf_GetFullName` are refused;
  - it is neither sysadmin nor db_owner.

**Step 4: SQL01, 11:43.**

- `D:\psa\bizbox-map.json` holds the four kinds, and the desk's `load_map` accepts it.
- **`PSA_BIZBOX_ODBC` is not in any task's arguments.**
  - `D:\psa\bin\Invoke-PsaBizboxSync.ps1` loads it from `D:\psa\bizbox.odbc` at run time, masks `PWD=` in its log, and clears it afterwards.
  - The handoff said "the same way as the other PSA_* settings". Those sit in the PSA-Desk task's command line, part of which the desk log prints (part 2).
  - Only the sync reads BizBox; the web desk reads the mirror. So the PSA-Desk task needs nothing.
- **Dry run** into a scratch SQLite desk, deleted afterwards:
  - the preview printed one line per kind (5,113, 527, 1,400 and 636 rows, 0 skipped) and "preview only";
  - the apply wrote them, and a second apply found them all unchanged;
  - every PO line's product is in the mirror, and every invoice has a due date;
  - each apply wrote one `BIZBOX_SYNC` audit row;
  - no secret reached the log.

**Step 5 needs psa_desk's password, which Task Scheduler keeps, so Dada runs `D:\psa\bin\Register-PsaBizboxSync.ps1`.**

- It registers `PSA-BizBox` as psa_desk: hourly at five past, IgnoreNew, 10-minute limit.
- It runs the task once in preview, which is step 4's Pass on the live desk.
- It then switches the task to `-Apply` and runs it once. That is step 5's first apply, and it must add exactly one `BIZBOX_SYNC` audit row.
- If either run fails, it removes the task again.
- Its preflight passed at 11:46, with no `BIZBOX_SYNC` audit rows yet.

### Part 4: 2026-09-29, 11:56 +08:00. **Steps 4 and 5 PASS on the live desk. `PSA-BizBox` runs hourly. Step 6 is not started, as the handoff says.**

Dada ran `Register-PsaBizboxSync.ps1` at 11:48. Everything below is MEASURED.

**The task: `PSA-BizBox`.**
- It runs as `DND-SQL01\psa_desk`, with a stored password and run level Limited.
- It runs every hour from 12:05, indefinitely, with IgnoreNew and a 10-minute limit.
- Its action is `Invoke-PsaBizboxSync.ps1 -Apply`. No connection string is in its arguments.

**Step 4's Pass**, the preview through Task Scheduler as psa_desk, 11:48:33 to 11:48:52, result 0:
- one line per kind: product 5,113, purchase_order 527, po_line 1,400, invoice 636, all new and 0 skipped;
- then "preview only".

**Step 5's first apply**, 11:49:00 to 11:49:13, result 0:
- "applied";
- `BIZBOX_SYNC` audit rows went from 0 to 1;
- `ext_source` records the last sync as 11:49.

**The mirror in `PMC_PSA`,** read back by SQL01 afterwards:

| Table | Rows, all present |
|---|---|
| `ext_product` | 5,113 |
| `ext_purchase_order` | 527 |
| `ext_po_line` | 1,400 |
| `ext_invoice` | 636 |
| `ext_agreement` | 0 |

The desk's own tables were untouched: 4 boards, as before.

**One reading to disregard.** `Get-ScheduledTaskInfo` shows a last run at 11:49:49. Task Scheduler's own history for the task shows exactly two runs, at 11:48:33 and 11:49:00, and so does the sync log. The 11:49:49 is not a run (INFERRED: a quirk of that field).

**Still open:**
- **The 12:05 hourly run.** SQL01 reads it back: a new "applied" line and `BIZBOX_SYNC` rows going from 1 to 2.
- **Dada's check:** Finance on `desk.pmcne.ph` shows the rows, and Setup › BizBox shows the last sync.
- **Step 6** (edits back to BizBox) is not started, as the handoff says. The desk's writer is still `NoWriter`, and the login can only read.

*Part 4, continued, 12:05 +08:00:* **the first hourly run PASS** (MEASURED, read back by SQL01).
- `PSA-BizBox` ran on schedule at 12:05:09 as psa_desk, exit 0.
- It picked up BizBox's changes from the past hour:

  | Kind | Rows now | New | Changed |
  |---|---|---|---|
  | purchase_order | 528 | 1 | 15 |
  | po_line | 1,408 | 8 | 0 |
  | invoice | 638 | 2 | 0 |
  | product | 5,113 | 0 | 0 |

  Nothing was skipped or absent.
- `BIZBOX_SYNC` audit rows went from 1 to 2: one per run.
- `ext_source` records the last sync as 12:05.

Step 5's Pass is met, except Dada's look at Finance and Setup › BizBox.

### Cloud Build, 29 Sep, after part 4: the three code points, answered; one small step for SQL01

Read in full; every count above is taken as MEASURED. Steps 1–5 are done.
The code at the head this arrives with answers parts 1 and 2's three points
(runbook, "Folded in from part 18 and the BizBox Reply"):

1. **The supplier's invoice number.** Schema 044 adds `ext_invoice.supplier_ref`,
   NULL-able. After the apply, SQL01 adds one column to one view and one line
   to the map, and the next hourly run fills it:
   ```sql
   ALTER VIEW psa.vw_invoice AS
   SELECT CAST(a.docno AS nvarchar(20)) AS ReceivingNo, a.refno AS SupplierInvoiceNo,
          dbo.udf_GetFullName(a.FK_faVendors) AS VendorName,
          COALESCE(a.refdate, a.docdate) AS InvoiceDate,
          DATEADD(day, ISNULL(a.terms, 0), COALESCE(a.refdate, a.docdate)) AS DueDate,
          CASE WHEN a.cancelflag = 1 THEN N'Cancelled' WHEN a.postflag = 1 THEN N'Posted' ELSE N'Draft' END AS Status,
          a.netlocamt AS TotalAmount, a.FK_mscCurrency AS Currency
   FROM dbo.iwApinv AS a
   WHERE ISNULL(a.deleteflag, 0) = 0;
   ```
   and in `D:\psa\bizbox-map.json`, under `invoice.columns`:
   `"supplier_ref": "SupplierInvoiceNo"`. The desk's `check_map` accepts it
   (the word passes the patient fence). **Pass:** the next run's invoice line
   counts every present invoice as changed, once; Finance › Invoices shows
   *Supplier's invoice no.*; the run after says 0 changed.
2. **Paid.** Nothing to add: the desk shows BizBox's own word and never says
   paid or overdue. The Invoices tab now summarises by that word.
3. **Agreements.** The Finance pages show the kinds BizBox has rows for. On
   the live desk: Procurement, Products, Invoices, and a one-line note. If a
   source is ever named, the map gains an `agreement` object and the
   invoice's `agreement_ref`, and the tab appears on the next run.

**One more small step, for the record:** `Invoke-PsaBizboxSync.ps1`,
`Register-PsaBizboxSync.ps1`, `New-PsaBizboxLogin.ps1` and `bizbox-step2.py`
exist only in `D:\psa\bin`. Every other task wrapper the desk runs is in
`platform/psa-spine/scripts/` in the repo, so a rebuilt host can be made from
it. Please commit those four there (they carry a path to the connection-string
file and no secret, so the fence allows them), with the same preview-by-default
header the others have.

**Rollback, which the handoff should have carried** (per the template):
`Disable-ScheduledTask PSA-BizBox`; then, only if the desk comes off BizBox
for good, in `LiveDB_PMC` `DROP VIEW` the four views, `DROP SCHEMA psa`,
`DROP USER psa_bizbox_reader`, then `DROP LOGIN psa_bizbox_reader`, and
`Remove-Item D:\psa\bizbox.odbc`. The `ext_*` rows in `PMC_PSA` may stay
(Finance then shows them as of the last sync) or be marked absent by one
`sync-bizbox --apply` from an empty CSV folder; nothing in the desk depends on
their being present. Step 4's preview runs as `psa_desk` (the task account),
which is what `Register-PsaBizboxSync.ps1` did.

**Do NOT decide** (the template's field, late): anything about a write path
to BizBox (step 6); whether a view may read any table outside `iw*`, `fa*`
and `udf_GetFullName`; the retention of the mirror. Those are Dada's.

**Step 6 stands as written.** The writer is `NoWriter`; `psa_bizbox_reader`
can only read; nothing here changes that.

**Two things SQL01 chose that Cloud Build records as right, so nobody undoes
them:** the connection string in `D:\psa\bizbox.odbc` read at run time (never
in a task's arguments, since the desk log prints part of that line), and the
random password nobody saw. The handoff's step 4 said "the same way as the
other `PSA_*` settings"; SQL01's way is better and is now the way.

