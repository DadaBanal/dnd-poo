# The eleven `iwItemLedger` doctypes, in BizBox's own words

**Answers:** the design-review question routed via SQL01 on 14 Oct 2026 — what `CA`, `CN` and `PP`
mean, and whether the eight proposed names are right.

**Source: BizBox's own stock-card builder**, `usp_InventoryStockCard`, whose `CASE aa.doctype WHEN …
THEN` builds the description column a user reads on the Electronic Stock Card. **This is the
product's own vocabulary, not an inference from the codes.**

**Measured 14 Oct 2026**, `LiveDB_PMC`, read-only, controls both ways.
Scripts: `scripts/Probe-LedgerDoctypes-20261014.py`, `-DoctypeLabels-20261014.py`,
`-DoctypeUnseen-20261014.py`.

**A route that failed, recorded so nobody repeats it:** `mscDocTypes` — the table that looks like the
vocabulary — **is empty, 0 rows**, and `FK_mscDocTypes` is null on every ledger row. My control
caught it and voided that section. The names are not in a lookup table; they are in the procedure.

---

## 1. Read this before building a word map — the privacy point

The labels below are **templates that embed a patient-name subquery**. `CA`, `CH`, `CN` and `DC` each
read `select ag.fullname from psPatinv af left outer join psDatacenter ag …`, so the Electronic Stock
Card prints **`Charges to "<patient full name>"`**.

> **A desk that renders BizBox's movement description verbatim will surface patient names.** Use the
> code's **word** — charged, returned, issued — and never the product's full description string.
> `DR` and `PR` embed the **vendor** name and `SS` the warehouse, which are not patient data, but the
> four charge codes are, and they are **82.6% of the ledger.**

## 2. The eleven present at PMC, with BizBox's label and its own bucket

The stock card sorts movements into three buckets, which are the product's own grouping:
**Receipts** = `PR`, `DR`, `PI` · **Issuances** = `CA`, `CH`, `CN`, `DC` · **Transfers** = `QA`,
`SS`, `MP`, `PC`, `EI`.

| Code | Rows | Direction measured | BizBox's own label | Bucket | One word |
|---|---|---|---|---|---|
| `CH` | 128,626 | 0 in / 127,967 out | `Charges to "<patient>"` | Issuances | charged |
| **`CA`** | **58,971** | **0 in / 58,929 out** | **`Charges to "<patient>"` — identical to `CH`** | Issuances | charged |
| **`CN`** | **17,136** | **17,136 in / 0 out** | **`Return from "<patient>"`** | Issuances | returned by patient |
| `SS` | 8,076 | 4,038 in / 4,038 out | `Transferred from (<warehouse>)` / `to` | Transfers | transferred |
| `PC` | 7,253 | 6,108 in / 28 out | `Qty Adjustment per Actual Count (<dept>)` | Transfers | counted |
| `EI` | 4,363 | 65 in / 4,298 out | `Expense Issuance to (<dept>)` | Transfers | issued |
| `DR` | 2,335 | 2,175 in / 160 out | `Deliveries from "<vendor>"` | **Receipts** | received |
| `MP` | 317 | 158 in / 159 out | production in / out | Transfers | produced |
| `QA` | 196 | 134 in / 62 out | quantity adjustment | Transfers | adjusted |
| **`PP`** | **92** | **46 in / 46 out** | **asset movement — see §4** | asset variant only | — |
| `PR` | 2 | 0 in / 2 out | `Return to "<vendor>"` | **Receipts** | returned to supplier |

## 3. The three that were unnamed

**`CA` — a patient charge, and BizBox gives it the same words as `CH`.** Strictly out, in the
Issuances bucket, label `Charges to "<patient>"`. **Why the product carries two charge codes is NOT
established** — the label, the direction and the bucket are identical, and both resolve the
counterparty through `psPatinv`. **It is not a charge-adjustment or charge-cancellation pair with
`CH`**: an adjustment would show mixed direction, and `CA` is 0 in / 58,929 out. The volume
coincidence that made that reading attractive does not survive the direction measurement.

**`CN` — a return from a patient.** Label `Return from "<patient>"`, strictly **in** (17,136 / 0),
Issuances bucket. The direction and the label agree, so this one is settled. Note `vwCreditNotesList`
pairs `CH` with `CA` rather than with `CN`, so **credit notes are built on the charge codes** and
`CN` is the stock consequence, not the document.

**`PP` — an asset movement, not a materials one.** It appears **only** in the asset variants
(`usp_InventoryStockCard_AssetGovt`, `udf_GetCurAssetBalance`, which maps `PP` → `DP`), and the
ordinary stock card **explicitly excludes it**: `and aa.doctype not in ('AT','PP','DP','GL','RT','RS')`.
Measured shape fits — 92 rows, 46 documents, exactly 46 in and 46 out, all within **6–7 Oct 2026**.
**So `PP` belongs to Asset Management, which is out of phase 1, and a materials movement map should
not carry it as a materials word.**

## 4. The eight proposed names — seven stand, one caveat, one trap

| Proposed | Verdict |
|---|---|
| `CH` charged | **correct** |
| `SS` transferred | **correct** |
| `EI` issued | **correct** — BizBox says *Expense Issuance to* |
| `DR` received | **correct** — BizBox says *Deliveries from*; note its bucket is **Receipts** |
| `MP` produced | **correct** |
| `QA` adjusted | **correct** |
| `PC` counted | **correct, with a caveat** — BizBox's own words are *Qty Adjustment per Actual Count*, and it sits in **Transfers**, not a bucket of its own. "Counted" reads well and is faithful; just do not expect the product to call it that |
| `PR` returned | **correct but dangerous as a single word — this is the trap** |

**The trap.** `PR` is *Return **to** vendor* and `CN` is *Return **from** patient*. **Two opposite
movements, opposite directions, different counterparties — and "returned" fits both.** A map that
renders each code to one word will show the same word for an outward supplier return and an inward
patient return. BizBox distinguishes them by direction and counterparty, so the map must too:
**returned to supplier** against **returned by patient**.

**The second trap, and it is bigger.** `CA` and `CH` carry the **identical** label in BizBox, and
together they are **187,597 of 227,104 ledger rows — 82.6%**. A map that insists on a distinct word
per code will **invent a distinction the product does not make.** Give both *charged*, or carry the
code beside the word.

## 5. Seven codes the product handles that PMC has never produced

`DC` (Deleted Charges from patient), `PI` (Petty Cash Purchases from payee), `AT`, `DP`, `GL`, `RT`,
`RS` — **all 0 rows.** Eleven distinct doctypes are present out of eighteen the code handles.
Controls: an impossible code returned 0 through the same query, and the same query returns 128,626
for `CH`, so the zeros are measured absences.

**`DC` is worth carrying in the map despite zero rows** — it is a charge *deletion*, it sits in the
Issuances bucket, and the day it appears a map without it falls through to a capitalised code.

## 6. Not established

- **Why two charge codes exist.** `CA` and `CH` are indistinguishable by label, direction, bucket and
  counterparty source. The discriminator is likely a field on `psPatinv` — in-patient against
  out-patient, or charge slip against direct charge — and I did not look, because it needs reading
  patient-encounter rows and the question did not require it.
- **The `AT`/`DP`/`GL`/`RT`/`RS` meanings.** Zero rows, asset or GL family, not read.
- **`CA`'s date range runs to 2026-12-08**, which is the future-dated ledger rows noted earlier
  (6 rows, 4 of them `CA`). Not chased.

Read-only throughout. Nothing built, nothing changed, and no patient name was selected or printed.

*Prepared by the Bizbox Chat session on DND-SQL01, 14 Oct 2026. No patient identifiers, no staff
names, no passwords, no connection strings, no addresses or topology.*
