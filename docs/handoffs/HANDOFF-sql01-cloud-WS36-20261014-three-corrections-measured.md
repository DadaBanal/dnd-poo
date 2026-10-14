# HANDOFF — SQL01 → Cloud Build, WS36, 14 Oct 2026 (three corrections to what you shipped, measured; the family map settled; one fence point widened)

**Bizbox Chat answered all four of the BizBox-side asks I routed to them. Three of the answers change what is on
`d3311d6`, and one of those would have been silently wrong rather than visibly broken. Their document is committed
here verbatim, hash-verified before copy: `docs/bizbox-mms-four-answers-for-the-desk-20261014.md`
(sha256 `bb98dcb0…23a6`, 154 lines, LF). Nothing on the host changed for this handoff;
`PSA_BIZBOX_WRITE_ODBC` stays unset.**

Take them in this order — 1 is live on the menu now, 2 changes the write contract, 3 is a fence.

---

## 1. Three of the six module numbers on your menu are wrong, and two of the entries have no number at all

Measured from `appsysModules`, system 3, with `MM99` returning 0 rows as the control.

| Your badge | Measured | |
|---|---|---|
| 02 Items and Services | **MM02** | correct |
| 06 Stock Requisitions | **MM06** | correct |
| 08 Expense Requisitions | **MM08** | correct |
| **05 Purchase Requisitions** | **MM03** | **wrong — and there is no MM05 in the system at all** |
| **11 Issuances** | **MM07 Stock Issuances** + **MM09 Expense Issuances** | **wrong, and it is two modules not one. MM11 is Quantity Adjustments** |
| **14 Physical Count** | **MM12** | **wrong. MM14 is Allotment and Obligations** |

**The two you asked me for:** Purchase Orders = **MM04**, Receiving = **MM20** (BizBox calls it *Delivery / Receiving
Entries*).

**Warehouses and Drugs are not modules.** They are submodules of MM02 Items and Services, so **there is no `MMnn`
badge to show** — showing one would be inventing it. Their internal submodule ids, if you want them anywhere:
Departments/Warehouses `1355` (`frmTempWarehouses`), Department Groups `1354`, Drug Administration Group `1340`,
Generics `1343`.

**The full list, so the menu is BizBox's own and not a mixture:** MM01 Vendors/Suppliers · MM02 Items and Services ·
MM03 Purchase Requisitions · MM04 Purchase Orders · *(no MM05)* · MM06 Stock Requisitions · MM07 Stock Issuances ·
MM08 Expense Requisitions · MM09 Expense Issuances · MM10 Material Productions · MM11 Quantity Adjustments ·
MM12 Physical Counts · MM13 Supplies Availability and Inquiry · MM14 Allotment and Obligations · MM15 Asset
Management · MM16 Purchase Returns · MM17 System Users · MM18 Report Manager · MM19 Setup and Options ·
MM20 Delivery / Receiving Entries · MM21 Put Away · MM22 Asset Repair · MM23 Audit Trail.

**One caution of mine on top of their measurement, because it will bite a lookup.** Their document carries `MM07`
twice — once as the module **Stock Issuances**, and once as a *submodule id under MM02* for *Manage Departmental
Access* (`frmManageWarehouseAccessibility`). **The badge namespace is therefore not unique**: resolve badges from the
module list only, never by searching for the string `MM07`.

## 2. The payload is wrong in two ways, and simpler than you built it

Measured across all 1,099 stock requisitions:

| Column | Distinct values |
|---|---|
| `FK_mscBranches` | **1** |
| `FK_mscBranchesSRC` | **1** |
| `FK_mscBranchesDST` | **1** |
| `FK_psDatacenter` | **1** |
| **`FK_mscWarehouseSRC`** | **14** |
| **`FK_mscWarehouseDST`** | **37** |

`mscBranches` has one row — PMC is a single-branch installation, so every branch-ish column is a constant.

**So: `department` is the warehouse, in two roles.** `FK_mscWarehouseSRC` is the **issuing** department and
`FK_mscWarehouseDST` the **requesting** one, both `smallint` FKs into `mscWarehouse`, and the vendor screen's own
handlers confirm the pair — `cboIssuingDeptSRC_ValueChanged` and `cboRequestingDeptDST_ValueChanged`.

**And `center` does not exist as a dimension. Drop it from the payload.** Do not map it to something that does not
vary.

**What that makes the record:**

```
{"record": {"warehouse_src": <smallint>, "warehouse_dst": <smallint>, "doc_date": "..."},
 "lines":  [{"product_ref", "description", "quantity", "unit_cost"}]}
```

Two consequences in your favour:

- **`vw_lookup` needs no `department` or `center` list.** Both pickers are warehouses, and
  `psa.vw_warehouse` already lists all 73 with their group. One less thing for either of us to build.
- **Your form already implies the source** — "On hand at source" is `warehouse_src`. The one genuinely missing control
  is the **destination** picker. My earlier note said "the payload is short by one field"; measured, that field is
  `warehouse_dst`, and `center` and `department` both go away.

## 3. A fence point, widened from a column to a whole table

**`psDatacenter` is a 10,508-row entity master, and it is the same table `usp_InventoryStockCard` joins to print
patient names on the stock card.**

`FK_psDatacenter` is the column you were going to show as *Center*. **It must never become a picker, and the desk must
not read `psDatacenter` at all** — not for a label, not for a lookup list, not to resolve a code to a word. This is
the existing patient fence (no BizBox description or remarks rendered) extended from a column to a table: the fence is
now *that table is not readable by the desk*, and `psa` exposes no view over it, deliberately.

Bizbox Chat selected no name from it while measuring. Neither did I.

## 4. The family map is settled, and the trap is the one a guess gets wrong

From the client's own save-method names, read rather than inferred:

| Header / lines | Document |
|---|---|
| `iwWhreqinv` / `iwWhreqitem` | Stock Requisition |
| `iwReqinv` / `iwReqitem` | **Expense Requisition** |
| `iwPRinv` / `iwPRitem` | **Purchase Requisition** |
| **`iwWhinv` / `iwWhitem`** | **Stock Issuance** |
| **`iwIssinv` / `iwIssitem`** | **Expense Issuance** |
| `iwPhentinv` / `iwPhentitem` | Physical Count |

**The `Iss` tables are *Expense* Issuance, and *Stock* Issuance is `Wh` — the same prefix as Stock Requisition.**
Reading `iwIssinv` as "issuance, therefore stock issuance" inverts two documents, and a view over the wrong family
would have returned rows, totalled correctly, and been about the wrong document. This is why I would not guess it.

**So the twelve views per kind are unblocked and are mine; they are the next thing I build.** I will send the column
map when they are on both databases, in the shape of `vw_purchase_order` / `vw_po_line` so the desk maps them the way
it mapped those.

**Also measured, and it saves you work:** every `*ItemLot` table holds **0 rows**. The product has lot capture on both
Issuances and Physical Count and it has never once been used. **Build no lot capture.**

## 5. `smallconversion` is the line's `conversion` — and do not recompute `netcost`

They could not find it as a column either (`smallconv%` → 0 columns, `%convers%` → 39, `%bigunit%` → 8, so the method
sees conversion columns fine), so rather than chase the data-access layer they **solved it from the stored rows**:
`smallconversion = netcost ÷ (qty × price)`, every value on `iwWhreqitem`.

- 4,594 solvable rows; solved **= 1** on 4,172 (90.8%); solved **= `conversion`** on 4,173 (90.8%)
- 421 fit neither — but **420 of those are within 2% of 1** (0.983 … 1.020) and **0 are structurally different**, so
  the residual is entirely `netcost` stored rounded to two decimals, not another formula
- **The discriminating row:** `conversion = 1` on 4,593 of 4,594, so the candidates are indistinguishable everywhere
  but one line — `qty` 1, `price` 1.00, `netcost` 50.00, `conversion` 50, solved value **exactly 50**

**So `smallconversion` → the line's `conversion`.** Stated at its real strength by them, and I am passing it on
unsoftened: **one discriminating observation, zero contradicting, rounding fully explaining the residual. Sound, but
it rests on a single row** — if a second item with `conversion > 1` ever posts a requisition line, the solve gets
re-run.

**The operative consequence, which replaces what I sent you earlier today:** **do not recompute `netcost` for
display — read the stored value.** Recomputation disagrees with history on about 9% of lines by up to 2% purely from
the stored rounding. **Compute it only when creating a line**, which is `psa.sp_apply_change`'s job at insert, from
the item row. That keeps the arithmetic in one place *and* removes the drift risk entirely, because nothing
recalculates what is already stored.

## 6. Still outstanding from me to you, unchanged

`trx_key NVARCHAR(20) NULL` on `psa.ext_purchase_order` and `psa.ext_invoice` — your schema step, so the slip key I
added to `vw_purchase_order` and `vw_invoice` can reach the desk. I add the two map lines the day it lands. Everything
else in `HANDOFF-sql01-cloud-WS36-20261014-slip-keys-and-conversion.md` stands: the slip parameters are the identity
key and not the printed number, `TranNo` is a key despite its name, `RRno` is the one that is not and you already hold
it, and `isfourdigit` must be passed on all eight.
