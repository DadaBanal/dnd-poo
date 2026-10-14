# Four BizBox answers for the desk's Procurement screens

**Answers** the four questions routed via SQL01 on 14 Oct 2026 from WS36's rebuild of the Procurement
screens. **Measured 14 Oct 2026**, `LiveDB_PMC` plus reflection-only disassembly of the MMS
assembly under Windows PowerShell 5.1. Controls in every section.

Scripts: `scripts/Probe-ModulesAndForms-20261014.py`, `-BranchAndUnits-20261014.py`,
`-SmallConversionSolve-20261014.py`, `-SmallConversionResidual-20261014.py`,
`Probe-SRGridArithmetic-20261014.ps1`.

---

## 1. `smallconversion` binds to the line's `conversion`

**It is not a database column** — confirmed independently: `smallconv%` matches **0 columns**
anywhere, while `%convers%` matches **39** and `%bigunit%` matches **8**, so the method sees
conversion columns perfectly well. `smallunit` exists in exactly one place, the **view**
`vwReportProdAssembly`.

**It is a client-side DataTable column.** From the IL of `<InsertItemsUnits>b__32`: the form builds
`dtUnits` from `DataRow["smallunit"]` keyed on `DataRow["FK_iwItems"]`, and the grid reads
`smallconversion` out of that repository. So it is a query alias, and chasing the data-access layer
was unnecessary — **the stored rows can be solved instead.**

**Solved from stored data**, since `netcost`, `qty`, `price` and `conversion` are all on
`iwWhreqitem`: `smallconversion = netcost ÷ (qty × price)`.

| | |
|---|---|
| Solvable rows (`qty ≠ 0`, `price ≠ 0`, `netcost` not null) | **4,594** of 4,596 |
| solved **= 1** | 4,172 (90.8%) |
| solved **= `conversion`** | 4,173 (90.8%) |
| fitting neither | 421 (9.2%) |
| **of those 421, within 2% of 1** | **420** — range **0.983 … 1.020** |
| structurally different (`>1.5` or `<0.5`) | **0** |

**So the 9.2% is entirely `netcost` being stored rounded to two decimal places**, not a different
formula.

**The discriminating case:** `conversion = 1` on **4,593 of the 4,594** rows, so the two candidate
answers are indistinguishable on all but one line. On that one line — `qty` 1, `price` 1.00,
`netcost` 50.00, `conversion` 50 — the solved value is **exactly 50**. **`smallconversion` =
`conversion`.**

**Strength of that, stated honestly:** one discriminating observation, zero contradicting ones, with
rounding fully accounting for the residual, and no `smallconversion` column existing to bind to
instead. Sound, but it rests on a single row — **if a second item with `conversion > 1` ever posts a
requisition line, re-run the solve and confirm.**

**Recommendation:** map `smallconversion` → the line's `conversion`. **But do not recompute `netcost`
for display — read the stored value.** Recomputation disagrees with history on about 9% of lines by
up to 2% because of the stored rounding. Compute it only when *creating* a line.

## 2. Which header/line family is which document — from the client's own save-method names

Each Details form has a method that **names its table**, so this is read rather than inferred:

| Header / lines | Document | Evidence |
|---|---|---|
| `iwReqinv` / `iwReqitem` | **Expense Requisition** | `frmExpenseRequisitionDetails` → `InsertItemsToIwReqitem` |
| `iwPRinv` / `iwPRitem` | **Purchase Requisition** | `frmPurchaseRequisitionDetails` → `get_IwPRinvTable`, `get_IwPRitemTable`, `InsertDataToPRinv` |
| `iwWhinv` / `iwWhitem` | **Stock Issuance** | `frmStockIssuanceDetails` → `InsertDataToIwWhitemLot` |
| `iwIssinv` / `iwIssitem` | **Expense Issuance** | `frmExpenseIssuanceDetails` → `InsertDataToIwIssitemLot` |
| `iwPhentinv` / `iwPhentitem` | **Physical Count** | `frmPhysicalCountDetails` → `InsertDataToIwPhentitemLot` |
| `iwWhreqinv` / `iwWhreqitem` | Stock Requisition | `frmStockRequisitionDetails` → `InsertItemsToIwWhreqitem` |

> **The trap, and it is the one a guess gets wrong.** The `Iss` tables are **Expense** Issuance, and
> **Stock** Issuance is `Wh` — the same prefix as Stock *Requisition* (`iwWhreqinv`). Reading
> `iwIssinv` as "issuance, therefore stock issuance" inverts two documents, and a view over the
> wrong family would be silently wrong in exactly the way SQL01 wanted to avoid.

**Also measured, consistent with §5.4:** the Issuance and Physical Count forms carry
`InsertDataToIw*ItemLot` save paths — and **every lot table holds 0 rows.** The product has lot
capture on these three documents and it has never been used.

## 3. None of the branch columns carries information, and there is no Centre

Measured across all **1,099** stock requisitions:

| Column | Filled | **Distinct values** |
|---|---|---|
| `FK_mscBranches` | 1,099 | **1** |
| `FK_mscBranchesSRC` | 1,099 | **1** |
| `FK_mscBranchesDST` | 1,099 | **1** |
| `FK_psDatacenter` | 1,099 | **1** |
| **`FK_mscWarehouseSRC`** | 1,099 | **14** |
| **`FK_mscWarehouseDST`** | 1,099 | **37** |

`mscBranches` has **1 row** — PMC is a single-branch installation, so all four branch-ish columns are
constants.

**So the desk's `department` maps to `FK_mscWarehouseSRC` (issuing) and `FK_mscWarehouseDST`
(requesting)** — `smallint` FKs into `mscWarehouse`. Those are the only two that vary, and the
requisition screen's own handlers confirm the pair: `cboIssuingDeptSRC_ValueChanged` and
`cboRequestingDeptDST_ValueChanged`.

**There is no Centre dimension in the data.** `FK_psDatacenter` is a single constant, and
`psDatacenter` is a **10,508-row entity master** — the same table `usp_InventoryStockCard` joins to
print patient names on the stock card. **It must not be surfaced as a "centre" picker**, and nothing
should select a name from it.

**Recommendation:** carry one department reference, as the `smallint` warehouse FK, in the two roles
source and destination. Drop `center` from the payload rather than mapping it to something that does
not vary.

## 4. The module numbers — and three of the six WS36 already holds are wrong

From `appsysModules`, system 3. Control: `MM99` returns 0 rows.

**Asked for:** Purchase Orders **MM04** · Delivery / Receiving Entries **MM20**.

**Warehouses and Drugs are not modules at all** — they are submodules of **MM02 Items and
Services**, so they have no `MMnn` badge:

| | Submodule id | Form |
|---|---|---|
| Departments / Warehouses | **1355** | `frmTempWarehouses` |
| Department Groups | **1354** | `frmTempWarehouseGrp` |
| Drug Administration Group | **1340** | `frmTempDrugAdminGroups` |
| Generics | **1343** | `frmTempGenerics` |
| Manage Departmental Access | `MM07` *(as a submodule id under MM02)* | `frmManageWarehouseAccessibility` |

**And the numbers WS36 is working from need correcting:**

| WS36 holds | Measured |
|---|---|
| 02 Items and Services | **MM02** ✓ |
| **05 Purchase Requisitions** | **MM03** ✗ — and **there is no MM05 in the system at all** |
| 06 Stock Requisitions | **MM06** ✓ |
| 08 Expense Requisitions | **MM08** ✓ |
| **11 Issuances** | **MM07 Stock Issuances** and **MM09 Expense Issuances** ✗ — two modules, not one, and 11 is **Quantity Adjustments** |
| **14 Physical Count** | **MM12** ✗ — 14 is **Allotment and Obligations** |

The full list, for the menu: MM01 Vendors/Suppliers · MM02 Items and Services · MM03 Purchase
Requisitions · MM04 Purchase Orders · *(no MM05)* · MM06 Stock Requisitions · MM07 Stock Issuances ·
MM08 Expense Requisitions · MM09 Expense Issuances · MM10 Material Productions · MM11 Quantity
Adjustments · MM12 Physical Counts · MM13 Supplies Availability and Inquiry · MM14 Allotment and
Obligations · MM15 Asset Management · MM16 Purchase Returns · MM17 System Users · MM18 Report
Manager · MM19 Setup and Options · MM20 Delivery / Receiving Entries · MM21 Put Away · MM22 Asset
Repair · MM23 Audit Trail.

## Not established

- **Where `dtItemRepository` gets `smallconversion` from in SQL.** The alias is resolved in the data
  layer (`BizBox.Business.Services` or a BizObj assembly), which was not disassembled. The solve
  above answers the question the build actually has; the query text would answer it directly.
- **Whether `unitprice` is written on save** — unchanged from the earlier note, still
  expected-not-measured.

Read-only throughout. No BizBox code executed — reflection-only. Nothing written. No name was
selected from `psDatacenter`.

*Prepared by the Bizbox Chat session on DND-SQL01, 14 Oct 2026. No patient identifiers, no staff
names, no passwords, no connection strings, no addresses or topology.*
