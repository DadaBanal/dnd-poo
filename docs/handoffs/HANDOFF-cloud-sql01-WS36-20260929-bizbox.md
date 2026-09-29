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
