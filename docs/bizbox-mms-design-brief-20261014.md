# BizBox MMS design brief — what it does, where it falls short, how Dada wants the replacement built

**For:** the WS36 / PSA desk build (peer session SQL and the WS36 cloud session)
**From:** Bizbox Chat session, DND-SQL01, 14 Oct 2026
**Measured against:** `LiveDB_PMC` on `DND-SQL01\PMC_SS`, read-only, 13–14 Oct 2026
**Every number below is MEASURED** unless marked INFERRED or DERIVED.

---

## 0. Dada's instruction — his words, 13 Oct 2026

> *"i also want you to tell it bow i want it built as per the bizbox but better mms only module"*

Three things that carries, and the third is the one that is easy to lose:

1. **MMS only.** Not HIS, not PIS, not FMS. The 1:1 proposal covers all four; this build is the
   materials module alone.
2. **As per BizBox.** Same tree, same screens, same steps, same words. His earlier correction on
   the proposal was exactly this — *"it should functio nsimilar to bixbox but better"* — after four
   draft screens had redesigned the workflows into boards and worklists. That was the wrong reading
   of "similar" and was withdrawn. **A department head must recognise the screen.**
3. **But better.** Improvements go *on top of* the copied screen, not instead of it. Section 5 below
   is the list of what "better" means in MMS specifically, and every item on it is a measured defect
   in the live system, not a preference.

Standing constraint, his words, 13 Oct: *"dont make anuy changes that will destroy things ok"* /
*"or what i meant was break things"*. The vendor client keeps writing these same tables throughout.

---

## 1. Do not re-measure the screen layer — it is already filed

The 1:1 proposal of 13 Oct already measured MMS at the screen and function layer. Use it rather
than repeating the work:

| What | Where | Figure for MMS |
|---|---|---|
| Module and submodule catalogue | `deliverables/PMC_OwnApp_1to1_Inventory_20261013.xlsx` sheet 1 | **22 modules, 137 submodules**, 133 distinct screens catalogued |
| In use | same, with holder counts per function | **68 of 137 have a `selected=1` grant row; 67 resolve to at least one real user; 69 have no grant at all** |
| Windows in the shipped program | `docs/bizbox-window-classes-20261013.txt` | **129** in the MMS assembly, plus shared Common Components (906) |
| The main screen, extracted from the program's own `InitializeComponent` | `docs/bizbox-ui-inventory-MMS-20261013.txt` | `…Details.frmStockRequisitionDetails` — **239 grid columns over 6 bands**, real captions |
| The proposal and its MMS screen mock | `deliverables/PMC_OwnApp_Proposal_v2-1_20261013.pdf`, `PMC_OwnApp_1to1_MMS_20261013.png` | 10 pages; MMS screen at full width |
| Narrative and corrections | `docs/bizbox-clone-question-20261013.md` | includes a correction: 709 distinct screens across four modules, not 797 — the earlier figure double-counted shared forms |

Reflection over the assemblies **requires Windows PowerShell 5.1**. pwsh 7 refuses
`ReflectionOnlyLoadFrom` (SYSLIB0018) and returns zero windows, which reads as "no forms found".
Route it through `powershell.exe`.

What follows is the layer the proposal does **not** contain: the data model, the document chain and
the business rules behind those screens. That is what makes "better" specifiable.

---

## 2. The 22 modules, and the distribution of use

Heaviest-held functions, by number of people holding the screen — this is where MMS actually lives:

| Function | People holding |
|---|---|
| Expense Requisition Details | **655** |
| Purchase Requisition Details | **640** |
| Job Order Request Details | **632** |
| Stock Requisition Details | **570** |

Then a long tail. **69 of 137 submodules carry no grant at all.** Six modules have submodules but
not one of them is held by anybody - **MM13 Supplies Availability and Inquiry** (1), **MM14
Allotment and Obligations** (1), **MM17 System Users** (5), **MM21 Put Away** (1), **MM22 Asset
Repair** (3), **MM23 Audit Trail** (1) - and two modules have no submodules catalogued at all:
**MM18 Report Manager** and **MM19 Setup and Options**.

Two of those are worth a second look rather than a skip. **Nobody holds Audit Trail**, so nobody in
materials can see who changed what. **Nobody holds System Users** either, which is consistent with
user administration being done from another module, but it means those MMS screens are dead weight.

The shape this implies: **MMS is a requisition system used by the whole hospital, with a small
procurement and warehouse core.** Six hundred-odd people raise requests; a handful buy, receive and
issue. The new app's two front doors are therefore very different in weight.

---

## 3. What MMS actually does — the document chain, with volumes

Header / line pairs, whole history:

| Document | Headers | Lines | State columns measured |
|---|---|---|---|
| Purchase Requisition | 634 | 1,893 | status FS=387, NS=178, PS=69 |
| Purchase Order | 837 | 2,151 | `postatus`, plus `approvalflag` 802/35 and `approval2flag` 762/75 |
| Delivery / Receiving | 1,069 | 2,250 | |
| Purchase Return | 2 | 2 | |
| Stock Requisition | 1,095 | 4,566 | |
| Stock Issuance | 998 | 4,094 | |
| Expense Requisition | 1,223 | 4,910 | |
| Expense Issuance | 1,085 | 4,310 | |
| Quantity Adjustment | 40 | 195 | |
| Material Production | 169 | 175 | |
| Physical Count | 104 | 2,202 | |
| Job Order | 21 | 23 | |
| Job Order Request | 5 | 5 | |
| Allotment / Obligation | **0** | **0** | |

Movement, from `iwItemLedger` (227,077 rows) by doctype:

| Doctype | Rows | Documents | Note |
|---|---|---|---|
| CH | 128,462 | 40,219 | charges — the HIS side consuming stock |
| CA | 58,847 | | |
| CN | 17,136 | | |
| SS | 8,076 | | in = out = 508,061 exactly — **transfer semantics, not consumption** |
| PC | 7,253 | | physical count |
| EI | 4,363 | | expense issuance |
| DR | 2,335 | | delivery receipt |
| MP / QA / PP / PR | 315 / 196 / 92 / 2 | | |

**The ledger is dominated by HIS charges, not by MMS documents.** 128,462 of 227,077 ledger rows
arrive from patient charging. Any replacement that owns the stock number must accept writes from
the clinical side it does not control. That is the single most important architectural fact here.

---

## 4. What people actually run — 60 days of SSRS, 16 Aug to 14 Oct 2026

From `ReportServer.dbo.ExecutionLog3`, 316,383 rows total in the window:

| Report | Runs in 60 days |
|---|---|
| `MMS_ADHOC_ExpRequisition` | 3,263 |
| `MMS_ADHOC_StockReq` | 3,057 |
| `MMS_ADHOC_DelReceiveRep` | 3,013 |
| `MMS_ADHOC_POSLIP` | 2,983 |
| `MMS_ADHOC_ExpIssuance` | 2,445 |
| `MMS_ADHOC_StockIssuance` | 2,164 |
| `MMS_ElectronicStockCard` | 1,712 |
| `MMS_ADHOC_PurcReq` | 1,345 |
| `MMS_DeptInventoryRep` | 573 |
| `MMS_PerpetualInventory` | 464 |
| then a tail | QtyAdj 171, deptExpenseIssuances 144, JobOrder 106, Store_Tran_Rep_All 99, PhysicalCount 54, PurcReport 43, MaterialProd 27, DeptItemPriceList 18, PurchaseRet 15, JobOrderReq 14 |

Control: an impossible report path matched 0 rows.

**About 21,700 MMS report runs in 60 days — roughly 360 a day — and the top eight are all
`MMS_ADHOC_*` document prints, not analytics.** MMS's day job is producing paper: a requisition
slip, a PO slip, an issuance slip. Analysis is the 1,037 runs of DeptInventory plus
PerpetualInventory, under 5% of the total.

**Design consequence.** The printed document is not a report feature, it is the product. Every
document screen in the new app needs a print that a department will accept in place of the current
slip, available at the same click, from day one. Get this wrong and nothing else matters. The 629
RDL reports stay on the same report server and remain callable — do not rebuild them.

---

## 5. Where it falls short — seven measured defects

Each is a measured fact about the live system, with the control where one applies. This is the
"better" list, and nothing on it is a matter of taste.

### 5.1 The stock number does not reconcile to its own movement buckets

`iwWareitem` holds the per-item-per-warehouse position as a set of buckets — `purcqty`, `salesqty`,
`issinqty`, `issoutqty`, `adjinqty`, `adjoutqty`, `reqinqty`, `reqoutqty`, `prodqty`, `prodoutqty`
— alongside `actualqty`.

| | |
|---|---|
| Rows | 591,583 |
| Rows with non-zero `actualqty` | **4,358** |
| Rows where `actualqty` ≠ (ins − outs), all rows | **3,931** |
| — of those, rows that hold stock (`actualqty` ≠ 0) | **2,617**, i.e. **60.1% of the 4,358** |
| — of those, rows showing zero stock whose buckets show movement | **1,314** |
| Rows with negative `actualqty` | 1 |

**`actualqty` disagrees with the bucket arithmetic on 2,617 of the 4,358 rows that hold stock —
60.1%.** A further 1,314 rows report zero stock while their own movement buckets are non-zero,
which is the worse of the two groups: the position says nothing is there and the movement says
otherwise. There is a disabled SQL Agent job named `PMC - MMS Movement Column Alignment`, which
suggests the vendor knows. INFERRED, from the name and its disabled state; not confirmed with the
vendor.

**Better:** one derived position, computed from the ledger, never a maintained bucket that can drift
from it. If buckets are kept for the vendor client's benefit, they are a projection, and a reconcile
check runs on a schedule and reports rather than silently diverging.

### 5.2 There is no costing method running at all

| Field, on 5,443 MED+SUP items | Populated |
|---|---|
| `avgcost > 0` | **0** |
| `saleprice > 0` | **0** |
| `allowedcost > 0` | **0** |
| `purcprice > 0` | 4,398 |
| `landcost` / `lastpurcprice > 0` | 1,325 |
| `iwItemsWareCost` rows (cost per warehouse) | **0** |
| `iwItemsBranchCost` rows | **0** |
| `iwItemLedger` rows carrying `purcprice` | 219,406 of 227,077 (96.6%) |

**No weighted average, no FIFO, no per-warehouse cost. Cost exists only on the movement row.** So
"what is this stock worth" has no answer from the item master, and any valuation has to be rebuilt
from the ledger every time it is asked.

**Better:** pick a method, state it, implement it once, and make the valuation reproducible. Whether
that is moving average or FIFO is a decision for Dada and Finance, not for the build — but the
absence of any method is the defect, and it is measured.

### 5.3 The entire reorder apparatus is unconfigured

| Field | Items set |
|---|---|
| `lowinven`, `maxinven`, `ReOrderRate`, `reorderbufferdays`, `isreorderitem`, `LeadTime` | **all 0** |
| `InvCritLevel`, `minlevel`, `maxlevel`, `ReorderPoint`, `AverageMovement`, `AnnualDemand` (on `iwWareitem`) | **all 0** |
| `isReplenishment = 1` | 56 rows |

The screens exist — Reorder Point, Critical Inventory Level Report, Inventory Critical Level — and
**zero data drives any of them.** Reordering is therefore entirely in people's heads.

**Better:** this is the biggest single opportunity in MMS and it needs no new data entry. Both
inputs already exist and were checked:

- **Consumption** — 227,077 ledger rows, per item per warehouse.
- **Lead time** — the receipt-to-PO chain is complete. **All 2,250 of 2,250 receipt lines carry
  `FK_iwPOitem`**, so actual lead time is the gap between the PO's `docdate` and the receipt's,
  measurable on every line without exception.

**Compute the reorder point; do not ask anyone to type it.** A field that nobody fills is a field
that should have been a calculation.

One thing that genuinely cannot be derived: **`iwPOinv.deliverdate` is populated on 0 of 837 POs**,
so the promised delivery date is never captured. Actual lead time is measurable; vendor lateness
against a promise is not, until that field is filled. Capture it on the PO screen in the new app.

### 5.4 Lot and expiry tracking is completely unused — in a hospital

| | |
|---|---|
| `iwItemLedgerLot`, `iwIssitemLot`, `iwApitemLot`, `iwAdjItemLot`, `iwPhentitemLot`, `iwApretitemlot` | **0 rows, every one** |
| `iwItemLedger` rows with a `lotno` | **0** |
| `iwItemLedger` rows with an `expdate` | **0** |
| Items flagged `isRequireLotNo` | **0** |
| Items flagged `isRequireExpDate` | **0** |

The schema supports lot and expiry fully. **Nothing has ever been written to it.** Meanwhile
`frmStockRequisitionDetails` displays *Generic Name* and *Expiry Date* columns on screen, and the
stock count cards that came back from departments this week carry lot numbers and expiry dates
written in by hand.

This is 2,008 medicine items, including chemotherapy drugs. **The hospital tracks expiry on paper
because the system's expiry tracking was never switched on.**

**Better:** lot and expiry captured at receipt, carried through issue, FEFO suggested on issue, and
an expiring-stock report that exists. Start with the drug and chemo warehouses, not all 73.

### 5.5 Controlled drugs are not flagged

`iwItemMedicines` holds 2,167 rows for 2,008 MED items. `isControlDrug = 1` on **0** of them.
`isMimsAllergy = 1` on **0**. 12 MED items have no medicine row at all.

Other flags are partly used — `isphicdeductable` on 639, `isVATExempt` on 1,966 — so the table is
live; the control-drug flag specifically is not.

**Better:** controlled substances need a register, a two-person count and a non-deletable audit, and
right now the system cannot even tell you which items they are. This is the one on this list with a
regulatory edge.

### 5.6 Approval is barely present, and separation of duties is not enforced anywhere

| Document | Distinct posters | Approval columns |
|---|---|---|
| Purchase Order | 3 | `approvalflag` 802/35, `approval2flag` 762/75; **1 of 802 posted and approved by the same person** |
| Purchase Requisition | 29 | **no approval column exists** |
| Stock Issuance | 35 | **none** |
| Delivery / Receiving | 11 | **none** |

PO has a two-stage approval and uses it. **The 1,223 expense requisitions and 634 purchase
requisitions - the documents 655 and 640 people respectively hold the screen for - have no approval
field in the schema at all.** Approval for those happens on paper, or not at all.

**Better:** this is the natural home of the PSA desk. Approval routing, one approver per stage,
preparer ≠ approver enforced rather than observed, and the state visible to the person who raised
the request. §2 says 655 people hold the expense requisition screen; **the requester experience is
the high-volume surface of this product and BizBox does not have one.**

### 5.7 Thirteen million price rows that are a cross product, not data

`iwItemPrices`: **13,042,176 rows** for 8,504 distinct items — **1,534 rows per item**. 26 price
schemes × 73 warehouses = 1,898 combinations. `iwItemPriceDiscounts` adds 2,072,058 more.

**That is a materialised cross product of scheme × warehouse × item.** It is **1,523× the size of
the item master** (8,565 rows) and the largest thing in MMS by three orders of magnitude.

**Better:** a price is a rule plus a small set of exceptions. Compute it; store the exceptions. This
is also the one defect that will show up as a performance problem rather than a correctness one.

### Smaller, and worth fixing while passing

- **85 distinct free-text unit strings** on 5,443 items. `conversion = 1` on 4,797 of them, so
  pack-size conversion is effectively unused. One of the unit values is `Supplies`, on 127 items —
  that is not a unit. **A controlled list, not a text box.**
- **73 warehouses defined, 25 hold any stock.** The top five by item count: Pharmacy (1,013 items),
  Procurement/Inventory/Warehouse (682), OPD Pharmacy (487), OR (357), CSSD (214). 48 warehouses are
  scaffolding, and they are what inflates §5.1 and §5.7.
- **6 ledger rows dated in the future**, to 2026-12-08 (4 CA, 2 CH). Small, but there is no date
  guard.
- **All government-procurement tables are empty** — `iwLBPMstr/Dtls`, `iwPAOOEMstr/Dtls`,
  `iwPPMPMstr/Dtls`, `iwAPPMstr/Items`, and Allotment/Obligation at 0/0. If PMC ever needs APP/PPMP
  reporting, nothing exists to build it from. Not a defect today; a gap to know about.

---

## 6. Before concluding anything is absent

Every zero above was taken with the real query beside a control. Two that specifically could have
been method artefacts and were checked:

- `isControlDrug` is on **`iwItemMedicines`, not `iwItems`** — the first probe failed with
  `Invalid column name` rather than returning 0, which is why the 0 is trustworthy.
- The SSRS log column is **`ItemPath`, not `ReportPath`**, and `ExecutionLog3` is an indexed view
  that **requires `SET QUOTED_IDENTIFIER ON`** — sqlcmd does not set it and fails with Msg 1934.
  A session that swallowed that error would report zero report usage.

If your own measurements of these contradict mine, mine are wrong until re-run — say so rather than
averaging.

---

## 7. How Dada wants it built — the rules, applied to MMS

Rule 0 first, because it is his and it overrides the rest:

**0. Same tree, same screens, same steps, same words.** `frmStockRequisitionDetails` has 239 columns
over 6 bands with captions *Issuing Department, Warehouse, Center, Item ID, Item Description, Unit,
Quantity, Served Quantity, Unit Price, Total Amount, Generic Name, Expiry Date*, and buttons *Add,
Edit Mode, Delete*, with footers *Total Record(s)* and *Total Item*. Those are the captions. A
department head opens the new screen and recognises it. Improvements are additive.

Then the engineering rules already recorded in the proposal, as they apply here:

1. **Exclusive cutover per screen.** The vendor client writes these same tables until the last
   screen moves. When a new screen goes live, its old submodule is unticked for those users —
   `appsysUserSubmodules` and `appsysUserGroupSubModules` already enforce access per user per
   screen, and the new app reads the same tables, so permissions stay in one place.
2. **Write paths proven on `TrainingDB_HIS8` first**, each save path derived from the client IL and
   its output compared byte-for-byte with the vendor client's own before live.
3. **Honour the rowversion columns** (1,203 across the database) or the two clients silently
   overwrite each other.
4. **Reads first on every screen.** Reads are cheap and proven; the risk is entirely on writes.
5. **A dialog is built with its parent**, not deferred.

And three that this measurement adds, specific to MMS:

6. **The printed document is a day-one requirement, not a phase 2 report.** §4 — 21,700 runs in 60
   days, 360 a day, and eight of the top ten are document prints.
7. **Do not own the stock number alone.** §3 — 128,462 of 227,077 ledger rows come from HIS
   charging. The new app is one writer among several, and must be correct when the clinical side
   writes behind it.
8. **Anything currently a field that nobody fills becomes a calculation.** §5.3 — six reorder fields
   and six critical-level fields at zero across the board is not a data-entry backlog, it is a
   design error. Compute it from the 227,077 ledger rows.

### A phase 1 that is defensible from the measurements

Not a recommendation on priority — **Dada sets priority.** This is what the numbers point at, for
him to order:

| | Why, from the measurement |
|---|---|
| Requester intake for Expense and Purchase Requisition, with approval routing | 655 and 640 holders; §5.6 — no approval field exists in the schema for either |
| The three document prints that carry the volume | §4 — ExpRequisition 3,263, StockReq 3,057, POSLIP 2,983 in 60 days |
| Stock position computed from the ledger, with the reconcile check reporting | §5.1 — 2,617 of 4,358 stock rows disagree with their own buckets, plus 1,314 showing zero while movement says otherwise |
| Lot and expiry at receipt and issue, drug and chemo warehouses first | §5.4 — six lot tables at zero, in a hospital with 2,008 medicine items |
| Computed reorder point per item per warehouse | §5.3 — twelve fields, all zero, and the data to compute them already exists |

Deliberately **not** phase 1: Asset Management (18 submodules, a whole sub-product), the 70
submodules nobody holds, the six modules with zero holders, and the 629 RDL reports, which stay
where they are.

---

## 8. What is still unmeasured, and what it gates

- **How many MMS screens write.** 133 screens is not the estimate driver; the count of save paths
  is. One reflection pass over the MMS assembly under PowerShell 5.1 gives it. **This is the first
  measurement before anyone sizes effort.**
- **BizBox's contract terms** on direct database writes and on reverse-engineering the assemblies.
  Open since 13 Oct. Either could change the answer.
- **Whether the vendor has a web client or an API on its own roadmap.** Same.
- **Whether `PMC - MMS Movement Column Alignment` is the vendor's own fix for §5.1**, and why it is
  disabled. Reading that job's steps would settle it; it has not been read.

Nothing built, nothing changed. Everything above is read-only measurement.

---

*Prepared by the Bizbox Chat session on DND-SQL01, 14 Oct 2026, for the WS36 / PSA desk build.
No patient identifiers, no staff names, no addresses or topology — safe for a committed repo.*
