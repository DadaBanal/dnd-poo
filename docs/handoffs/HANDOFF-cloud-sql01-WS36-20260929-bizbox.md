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

*(SQL01 writes here.)*
