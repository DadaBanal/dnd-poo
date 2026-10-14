# The Stock Requisition save path, measured — what `psa.sp_apply_change` must write

**Answers** SQL01's four questions of 14 Oct 2026 for the `STOCK_REQ` branch, so a desk-raised
requisition is indistinguishable from one the vendor client saved.

**Measured 14 Oct 2026** on `LiveDB_PMC`, read-only, over **1,102 headers and 4,600 lines**, plus
reflection-only disassembly. Controls throughout, including one that **failed and is reported as a
failure**.
Scripts: `scripts/Probe-SaveHeaderProfile-20261014.py`, `-SaveStateCrosstab-20261014.py`,
`-SaveSideEffects-20261014.py`.

**Most of this is measured from what the client has actually left in 1,102 saved rows, not from the
IL.** That is the stronger evidence for "what does the client set" — but it means a column the client
sets to the same value every time cannot be distinguished from a column with a default. Where that
matters it is flagged.

---

## 1. The header insert on `iwWhreqinv` — 35 columns

| Column | What to write | Evidence |
|---|---|---|
| `PK_TRXNO` | identity, let the table allocate | range 85,476 … 421,404, 1,102 distinct |
| `ownerID` | **`'00000000'`** — NOT NULL, one value on all 1,102 | |
| `FK_psDatacenter` | **1000** | one value, all rows |
| `FK_mscBranches`, `FK_mscBranchesSRC`, `FK_mscBranchesDST` | **1000** each — all NOT NULL | one value each, all rows |
| `FK_mscWarehouseSRC` | the **issuing** department, NOT NULL | 14 distinct |
| `FK_mscWarehouseDST` | the **requesting** department, NOT NULL | 37 distinct |
| **`docno`** | **`int`. See §2 — it is per-destination-warehouse, not global** | 256 distinct over 1,102 |
| `docdate`, `regdate` | `smalldatetime`, both filled on every row | |
| `FK_ASUReg` | the registering user | filled on all, 62 distinct |
| **`FK_ASUPost`** | **filled at SAVE, and it is NOT the registrant — see the warning below** | filled on 89 of 89 unposted |
| **`status`** | **`'NS'`** | the only status on live unposted rows, 54 of 54 |
| `postflag` | **0**; `postdate` **null** | 89 unposted rows, postdate null on all |
| `cancelflag`, `deleteflag`, `inactiveflag` | **0** each | |
| `canceldate`, `deletedate`, `cancelrem`, `deleterem`, `FK_ASUCancel`, `FK_ASUDelete`, `FK_ASUinactive`, `inactivedate` | **null** | only filled on cancelled/deleted rows |
| `totqty`, `totitm`, `amount` | **computed at save** — see §3 | filled on all 1,102 |
| **`docbarcodeid`, `docbarcodeidstring`** | **leave null — the client never generates them** | filled on **0** of 1,102 |
| `isDangerousDrugs` | **0** | `False` on all 1,102; the flag is set on no requisition in the system |
| `remarks` | `ntext`, free text, null unless the user typed one | |

> **The `FK_ASUPost` warning. It is populated on all 89 unposted rows, it equals `FK_ASUReg` on
> ZERO of them, and `postdate` is null on all 89.** So the client writes it at save, it is *not* the
> registering user, and it does *not* mean "posted by". **Do not infer its meaning from its name and
> do not derive a posted-by from it.** What it actually holds is **not established** — I measured the
> pattern, not the intent.

### The three status codes
`FS` 812 · `NS` 189 · `PS` 101. Live unposted rows are **`NS` only**. Posted rows are `FS`, `PS`, or
still `NS` (61). So `NS` is the saved-not-yet-served state and `FS`/`PS` are fully and partly served.

## 2. `docno` — a per-requesting-department running number

256 distinct values over 1,102 rows, so **`docno` repeats and is not the identity.** Measured scope:

| Unique within | Duplicate groups |
|---|---|
| destination warehouse | **0 — unique here** |
| source warehouse | 188 |
| year of `docdate` | 116 |

And each destination warehouse runs a **dense sequence from 1**: warehouse 1041 holds `docno` 1…256
over 256 rows, 1008 holds 1…116 over 116, 1001 holds 1…71 over 71.

> **So: `docno = ISNULL(MAX(docno),0) + 1 WHERE FK_mscWarehouseDST = @dst`, never reset by year.**
> No numbering table drives it — `mscDocIDs` holds only `description` and `isSystemDefault`, and the
> series tables (`mscInvSeries`, `mscPRseries`, `mscSeriesNo`, …) are for other documents.
> **Allocate it inside the same transaction as the insert, or two concurrent saves to one department
> collide.** That is a real race: `iwWhreqinv` takes real traffic.

## 3. The totals — computed at save

| | Matches the line sum on |
|---|---|
| `totqty` = `SUM(qty)` | **1,101 of 1,102 (99.9%)** |
| `totitm` = `COUNT(lines)` | **1,101 of 1,102 (99.9%)** |
| `amount` = `SUM(netcost)` | **823 of 1,102 (74.7%)** |

**Compute all three at save.** The `amount` shortfall is the `netcost` rounding already measured —
the header is not recomputed when a line is later edited, so historical drift is expected and is not
a reason to recompute history.

## 4. The line insert on `iwWhreqitem` — 13 columns

| Column | What to write | Evidence |
|---|---|---|
| `PK_iwWhreqitm` | identity | |
| `FK_TRXNO` | the header's `PK_TRXNO` | the only declared FK on either table |
| `FK_iwItems` | `nvarchar(20)` item code | 988 distinct |
| `qty` | the requested quantity | **never 0, never negative** — see §6 |
| **`servqty`** | **0** | **0 on all 314 lines of unposted headers** |
| `unit` | the chosen unit, **never null or blank** | 46 distinct |
| `conversion` | the line's conversion | 1 on 4,599, 50 on 1 |
| `price` | **a snapshot of `iwItems.purcprice` at pick time** — see below | |
| `netcost` | **`qty × price × conversion`** | as measured earlier |
| **`expdate`, `lotno`** | **null** | **0 of 4,600 on both** |
| `isDonation` | **0** | `False` on 4,599 of 4,600 |

**On `price`:** it matches today's `iwItems.purcprice` on 58.4% of lines, `lastpurcprice` on 23.0%
and `landcost` on 23.0% — **and `purcprice` equals each of those two on exactly 1,606 items, so the
23% pairs are the same coincidence, not two other sources.** `purcprice` is the source; the 42%
that no longer match are the item master having moved since the line was raised. **It is a snapshot:
write `iwItems.purcprice` as at pick time and never re-read it.**

## 5. What else a save writes — nothing

| | Measured |
|---|---|
| Triggers on either table | **none** |
| Foreign keys into them | one, the line→header FK |
| Ledger rows for a requisition | **0** — doctypes `SR`/`WR`/`RQ` do not exist, so **a requisition alone never moves stock** |
| Audit rows | **see the control failure below** |

**On the audit table, and the control that failed.** `appsysAudits` holds 52,418 rows. I tried to
join `refpkvalue` to `iwWhreqinv.PK_TRXNO` and got 0 — **but the positive control failed**: the same
join form matches **nothing anywhere**, including `Item*` rows against `iwItems`, so **that method is
blind and its 0 proves nothing.** Reported as a failure rather than as a finding.

**What does stand, from the module breakdown rather than the join:** MMS (`FK_appsyssystems = 3`)
audit rows are **only** *Items and Sevices* 1,256, *Item and Services* 1,173, *Vendors . Suppliers*
67, *Setup and Options* 7 — **2,503 rows, all master data. No document module appears at all**, and
`Render Requisition` (1,242 rows) is **not** system 3 and its `refpkvalue` runs 2,096…2,243 against
requisition keys of 85,476+, so it is a different document entirely.

> **So: the client audits master-data changes, not document saves. Write the two tables and nothing
> else.** Stated as measured from the module breakdown; the key-level confirmation was not obtainable.

## 6. What the client refuses — eight things that never occur in 1,102 headers and 4,600 lines

| Never occurs | Count |
|---|---|
| a header with no lines | **0** |
| a line with `qty = 0` | **0** |
| a line with `qty < 0` | **0** |
| a line with a null item | **0** |
| a line whose item is absent from `iwItems` | **0** |
| **source warehouse = destination warehouse** | **0** |
| a null or blank `unit` | **0** |
| `conversion` 0 or null | **0** |

**And two things that DO occur, so they are NOT refused — this is the part that matters for "too many
checks":**

| Occurs | Count |
|---|---|
| the same item twice on one header | **3** |
| a line priced at 0 | **2** |

**A procedure that rejected a duplicate item or a zero price would refuse what BizBox permits.**
Rare is not forbidden.

**Note the asymmetry with purchase requisitions:** source = destination occurs on **205 of 639**
purchase requisitions but on **0 of 1,102** stock requisitions. **Different documents, different
rule** — do not carry one check across.

## Not established

- **The header insert's own IL.** I profiled what the client leaves in the table rather than
  disassembling its insert, so a column it writes with the same value every time is
  indistinguishable from a column default. The values above are what is *in* the rows.
- **What `FK_ASUPost` actually means** on an unposted row. Pattern measured, intent not.
- **The client's refusal messages.** `ValidateRequiredFields` (406 bytes) and its closures hold no
  literal strings — the messages come from a resource or a shared helper, not disassembled. The
  refusal list above is inferred from 1,102 saved headers, not read from the validator.
- **Whether an inactive item can be picked.** `iwItems` has no `inactiveflag` column, so the
  question as posed has no column to answer it.

Read-only throughout. Reflection-only; no BizBox code executed. Nothing written.

*Prepared by the Bizbox Chat session on DND-SQL01, 14 Oct 2026. No patient identifiers, no staff
names, no addresses or topology.*
