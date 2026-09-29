# HANDOFF-sql01-cloud-WS36-20260929 — agreements are made on the desk; from one, link what BizBox holds

| Field | |
|---|---|
| To | Cloud (WS36) |
| From | SQL01 |
| Workstream | WS36 |
| Bucket | Agreements created and kept in Dada PSA, since BizBox holds none. From an agreement, staff add the BizBox invoices, purchase orders and products it covers. |
| Read first | This file; `HANDOFF-cloud-sql01-WS36-20260929-bizbox.md`, Reply part 1 and Cloud Build's section; `psaspine/bizbox.py` (`KINDS`, `sync`, `_filter`, `link`); `psaspine/web/views/finance.py` |
| Do | Build it, with tests. Say in the branch whether a schema step comes with it; SQL01 applies any schema by the sitting-1 road. |
| Do NOT decide | Who may create or edit agreements: which roles, which departments. Anything sent back to BizBox: step 6 stands, and the writer is `NoWriter`. |
| Fence | Hostnames only; no patient identifier, credential or internal address. Labels MEASURED / VERIFIED / INFERRED / NOT VERIFIED. |

## Dada's words, 29 Sep 2026, about 14:10 +08:00, verbatim

> "the agreements need to exist they can add it on the psa the agreements from there and add the needed invoices and whatever is exisitng on bizbox"

## How SQL01 read it

- **Agreements exist on the desk.** Staff create and edit them in Dada PSA. BizBox holds no supplier agreements (Reply part 1, MEASURED).
- **From an agreement, staff add the BizBox records it covers:** the invoices, and whatever else BizBox has, meaning purchase orders and products.
- **An agreement is therefore the desk's own record.** Invoices, POs and products stay BizBox's, mirrored read-only as now, and nothing is written to BizBox.
- **For agreements only, this changes the BizBox handoff's opening line** ("finance, agreements and procurement are BizBox's"): agreements are the desk's, because BizBox has none. This is SQL01's reading; Dada corrects it if it is wrong.

## What the code does today (MEASURED at `23caa5f`)

- **`ext_agreement` exists (0 rows on the host), but only as a mirror kind.**
  - It is filled only by `sync-bizbox`, scoped to `source_id = 'BIZBOX'`.
  - Every Finance list, count and summary filters on that source (`bizbox._filter`). A row under any other source would not show.
- **Invoices and agreements are joined by one column.**
  - An invoice points at an agreement only through `ext_invoice.agreement_ref`, and `ix_ext_invoice_agreement` (044) indexes it.
  - The agreement page already lists "Invoices under this agreement" by that column.
- **The sync writes only the fields the map names.** It builds each row from the mapped columns (`rec = {... if f in raw}`) and compares only those.
  - The live map does not name `agreement_ref`, so the hourly sync never writes that column. A value the desk sets there would survive every run.
- **Links:** `link()` joins a subject (today a ticket or a project) to a mirror record through `ext_link` (subject kind and id, kind, `ext_ref`).
- **The Agreements tab** appears only when an agreement row exists.

## What the desk would need (the design is WS36's)

1. **Agreements:** create, edit and retire them on the desk (Finance › Agreements › New), with the fields `ext_agreement` already has:
   - number, name, party (a supplier from the mirror?), starts, ends, status, amount, currency.
2. **Linking:** from an agreement, search the mirror and add or remove invoices, POs and products; show them with totals.
   - Invoices can use `agreement_ref`, or a link row; POs and products need a link either way.
3. **Survive the hourly sync:**
   - an agreement made on the desk is never marked absent by it;
   - a link from an agreement to a BizBox row is never cleared by it.
4. **Audit and rights:**
   - audit rows for create, edit and link, as the other Finance actions have;
   - rights from Security roles › Finance, presumably Write to create or link and Read to see. Which roles get which is Dada's.

## SQL01's part afterwards

- Any schema step, by the sitting-1 road.
- The map and the four BizBox views stay as they are, unless the design asks otherwise.
- Nothing changes in `LiveDB_PMC`.
