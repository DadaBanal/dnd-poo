# HANDOFF — SQL01 → Cloud Build, WS36, 14 Oct 2026 (087 applied, desk restarted, map on; BizBox numbers requisitions per department, so the mirror keys on the transaction key; one validation you removed must come back for stock requisitions)

**Dada's go, executed in his order: `294aa2a` pulled; 087 applied (COPY_ONLY backup `PMC_PSA_COPYONLY_pre087_20261014-142423.bak`,
twelve tables created empty, seven columns added, 162 → 174 tables, counts unchanged, fresh-connection verdict
PASS); `PSA-Desk` restarted at 14:25 and answering; the 087 map lines on and proven by a read. `PSA_BIZBOX_WRITE_ODBC`
stays unset. Two things in this handoff change what you build; read §2 before anything else.**

## 1. State

| | |
|---|---|
| PMC_PSA | 083 + 084 + 085 + 086 + 087 |
| Desk | process started 14:25:02, old one gone; login page serves the Vitals chrome (`0E1520` ×5, `A98BFF` ×3, `Consolas` ×4, "vitals" ×59, "cells-edited" ×0) — the authenticated visual check in Dada's step 4 is his |
| Map | 22 objects; `check_map` accepting; backups `.bak_20261014_142619` and `.bak_20261014_143152` |
| Read | exit 0; every one of the twelve new mirrors equals its view (below); the seven columns filled — `is_active` and `is_inventory` on all 8,575 items, `trx_key` on 826 of 832 POs and 1,044 of 1,059 invoices (the rest are `present = 0` rows no longer in the view), `last_purc_price` on 7,204 |

| Mirror | Headers | Lines |
|---|---|---|
| stock_req | 1,067 | 4,503 |
| expense_req | 1,206 | 4,807 |
| purchase_req | 643 | 1,944 |
| stock_issuance | 989 | 4,103 |
| expense_issuance | 1,087 | 4,320 |
| physical_count | 99 | 2,187 |

Lines with no header, by `doc_ref`: **0** on all six.

## 2. BizBox numbers requisitions, issuances and counts *per requesting department* — the map now keys on `TrxKey`

The first read with your §2 map lines (`ext_ref: DocNo`) came back short on four kinds: **stock_req 253 of 1,067,
expense_req 264 of 1,206, stock_issuance 520 of 989, physical_count 80 of 99.** Lines were full. MEASURED why:

| View | Rows | Distinct `DocNo` | Distinct `TrxKey` |
|---|---|---|---|
| `vw_stock_req` | 1,067 | **253** | 1,067 |
| `vw_expense_req` | 1,206 | **264** | 1,206 |
| `vw_purchase_req` | 643 | 643 | 643 |
| `vw_stock_issuance` | 989 | **520** | 989 |
| `vw_expense_issuance` | 1,087 | **636** | 1,087 |
| `vw_physical_count` | 99 | **80** | 99 |

**`DocNo '1'` is 33 different stock requisitions**, one per destination warehouse. Bizbox Chat measured the rule
independently the same hour from 1,102 saved headers: `docno = MAX(docno) + 1 WHERE FK_mscWarehouseDST = @dst`,
a dense sequence from 1 per requesting department, never reset by year, no numbering table. **Purchase orders and
purchase requisitions number globally**, which is why `PONo` worked and the pattern looked safe.

The mirror's primary key is `(source_id, ext_ref)`, so 1,067 collapsed into 253. **So, applied on my side and now
live:**

- the six **line views carry `TrxKey`** (the header's `PK_TRXNO`), both databases, 0 nulls, 0 orphans;
- the map keys **headers by `ext_ref: TrxKey`** and **lines by `doc_ref: TrxKey`**; `DocNo` is not mapped at all
  until there is a column for it.

**Asked of you — schema 088, one column:** `doc_no NVARCHAR(32) NULL` on the six header mirrors. The day it lands I
map `DocNo` to it and the "In BizBox" list shows BizBox's own number. **Until then `ext_ref` on those six is the
transaction key, and the screen should say so rather than present `85476` as a requisition number.** Show it as
*BizBox ref 85476* or hold the number column empty; do not label the key as the number.

**Two consequences for the write path, both of which you need before the pilot:**

1. **The document "number" is not unique and never identifies a document.** The desk must hold `TrxKey` as the
   identity for every BizBox document and show `DocNo` only beside its requesting department. A search by number
   alone will return up to 33 documents.
2. **`psa.sp_apply_change` must allocate `docno` inside the same transaction as the insert** — two concurrent saves
   to one department otherwise collide, and `iwWhreqinv` takes live traffic. The procedure returns `TrxKey` as the
   `ext_ref` and `docno` beside it; the desk stores both.

## 3. A check you removed on my word must come back — for stock requisitions only

My Part 109 said *same department on both sides saves without a warning*, measured on **purchase** requisitions
(205 of 639). You removed the check for every kind. Bizbox Chat's save-path profile corrects the scope:

- **Purchase requisitions:** source = destination on **205 of 639**. Permitted. Your removal stands.
- **Stock requisitions:** source = destination on **0 of 1,102**. **The vendor client refuses it.** Put the check
  back for `STOCK_REQ`.
- Issuances and counts: **not measured either way.** Do not infer from the names; ask and I will measure before the
  pilot reaches them.

Different documents, different rule — and I carried one across. The asymmetry is theirs to have found and mine to
have passed on wrongly.

## 4. What the vendor client writes on a stock requisition save — the contract for the first write kind

From Bizbox Chat's profile of 1,102 saved headers and 4,600 lines (`docs/bizbox-stock-requisition-save-path-20261014.md`,
committed verbatim), the parts the desk and the procedure share:

- **Refused by the client, so refused by the procedure and nothing more:** no lines; `qty ≤ 0`; a null item or one
  absent from `iwItems`; source = destination; blank unit; `conversion` 0 or null. **Permitted, so the desk must not
  refuse them:** the same item twice on one header (occurs 3 times), a line priced at 0 (occurs twice). *Rare is not
  forbidden* — Dada's "too many checks".
- **`price` is a snapshot of `iwItems.purcprice` at pick time** and is never re-read; `netcost = qty × price ×
  conversion` at insert; `servqty = 0`; `expdate` and `lotno` null; nothing else is written anywhere — no trigger, no
  audit row, no ledger movement (a requisition alone never moves stock).
- **`FK_ASUPost` is written at save, is not the registrant, and does not mean posted-by.** What it holds is not
  established. Nothing on the desk derives a "posted by" from it.
- **`status = 'NS'` and `postflag = 0` on a new save**; cancel, delete and inactive flags 0; the four branch
  constants are `1000`; `docbarcodeid` left null (the client never fills it).

## 5. Fence and record

No `remarks` column is mapped on any of the 22 objects. `psDatacenter` is read nowhere. Nothing written to a BizBox
table. Scripts in the session record: `apply-087.py`, `map-087.py`, `bizbox-views-line-trxkey.py`.
