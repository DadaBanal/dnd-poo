# HANDOFF — SQL01 → Cloud Build, WS36, 13 Oct 2026 (all of MMS, a drugs area, and MMS report printing)

**A requirement from Dada, with the BizBox side measured so nothing here has to be guessed.** No code is asked of
SQL01; this is the host-side survey Cloud Build needs to design against.

Dada, 13 Oct 2026, after 080/081 went live and he saw Procurement working:

> *"also i need all the modules on the procurement or mms loaded in here also an area for procurement of drugs and
> medicine specifically and printing out reports for MMS"*

and, on how it is to be built:

> *"make sure it has all the data it needs and it conforms to modern design load skills needed also tell that to the
> spine"*

So: **(1)** mirror the rest of MMS, not just the four objects; **(2)** a procurement area specifically for drugs and
medicines; **(3)** printable MMS reports. Built to a modern standard, with the relevant skills loaded first.

---

## 1. What the desk mirrors today — all of it

Four objects, through four views in `LiveDB_PMC`, read hourly by `PSA-BizBox`. MEASURED 13 Oct:

| Object | View | Rows |
|---|---|---|
| product | `psa.vw_product` | 5,472 |
| purchase_order | `psa.vw_purchase_order` | 798 |
| po_line | `psa.vw_purchase_order_line` | 2,067 |
| invoice (receiving) | `psa.vw_invoice` | 1,002 |

Vendors are not an object: the desk derives them from what orders and receipts name.

## 2. What BizBox has that the desk does NOT mirror

MEASURED row counts, `LiveDB_PMC`, 13 Oct 2026. 1,603 base tables in all.

| What | Table | Rows | Worth mirroring? |
|---|---|---|---|
| Vendor master | `dbo.faVendors` | **718** | Yes — today a vendor is only a name on an order. A real record gives terms, type, contact. |
| Vendor categories | `dbo.faVendorsCateg` | 5,911 | With the above. |
| Vendor types | `dbo.mscVendorTypes` | 11 | A lookup list. |
| Item master | `dbo.iwItems` | **8,558** | The view already narrows to 5,472; the difference is worth understanding before widening. |
| Stock on hand, per warehouse | `dbo.iwWareitem` | **591,084** | Yes, but see the warning in §5. |
| Stock movements | `dbo.iwItemLedger` | **225,281** | The stock card. Big. |
| Stock movements, daily roll-up | `dbo.iwItemLedgerDaily` | 56,572 | Cheaper than the ledger for most reports. |
| Warehouses | `dbo.mscWarehouse` | **73** | Yes — nothing in the desk knows a warehouse today. |
| Warehouse groups | `dbo.mscWarehouseGrp` | 6 | With the above. |
| Receiving / AP source | `dbo.iwApinv` | 1,036 | Already behind `vw_invoice`. |
| Assets | `dbo.iwItemAssets` | 48 | Probably Configurations' business, not Procurement's. |

**A negative finding, with a control.** There is **no requisition or issuance data to mirror**:
`dbo.EipSRRequisition` holds **0 rows**, and no issuance, transfer or adjustment table carries materials data
(`psPatRoomTransfer` 1,640 and `psPatAdjustments` 795 are patient movements and patient billing adjustments, not
stock). A made-up table name is refused by the same method, so this is absence, not a blind probe. **Do not design a
requisition screen against BizBox data that is not there** — if Dada wants requisitions, they would be the desk's
own records, like Agreements.

## 3. Drugs and medicines — the data exists and it is good

This is the strongest part of the request, because BizBox already distinguishes a medicine properly.

| What | Table | Rows |
|---|---|---|
| The medicine extension of an item | **`dbo.iwItemMedicines`** | **2,166** |
| Generic names | `dbo.mscGenerics` | 832 |
| DOH drug list | `dbo.mscDOHDrugList` | 2,426 |
| MIMS drug list | `dbo.mscMIMSDrugList` | 2,261 |
| DOH generic list | `dbo.mscDOHGenericList` | 2,071 |
| Drug administration groups | `dbo.mscDrugAdminGroup` | 3 |

`dbo.iwItemMedicines` keys on `FK_iwItems` and carries, among others:

`FK_mscGenerics` · `dosage` · `defaultqty` · **`isControlDrug` (bit)** · `mimsGUID` · `mimsDesc` · `mimsType` ·
`isMimsAllergy` · `FK_emdTempPreparations` · `FK_emdTempUnitMeasure` · `FK_emdTempUnitVolume` ·
`FK_emdTempFrequency` · `FK_emdTempDurations` · `FK_emdTempRoutes` · `rxlineitem` · `remarks`

And `dbo.iwItems` itself carries `FK_mscDOHDrugList`, `EDPMSDrugCode`, `kisDrugGroup`, `FK_mscDrugAdminGroup`,
`FK_mscPHICCategory`.

**So "is this item a drug" is answerable exactly**: an item with a row in `iwItemMedicines`. 2,166 of 8,558.
**`isControlDrug` is a real column** — a controlled-drugs view is therefore possible, and in a hospital that is
probably the single most useful thing in this whole request.

## 4. The dropdown-label problem is now measurable

`psa.vw_product.Category` returns **numeric codes**, not words. MEASURED distribution: `1001` 1,973 · `1002` 1,122 ·
`1020` 472 · `1010` 438 · `1019` 416 · `1055` 405 · `1015` 301 · `1018` 151 · `1056` 98 · `1017` 77 · and a tail.

The label tables exist: **`dbo.mscItemCategory` 58 rows**, `dbo.mscUnits` 83, `dbo.mscVendorTypes` 11,
`dbo.mscWarehouse` 73. This is exactly what §5 of the 081 handoff (`psa.vw_lookup` → `psa.ext_lookup`) is for, and it
should probably come **before** any of the new areas, because every new screen will show codes until it lands.

## 5. Warnings worth having before design

- **`iwItemPrices` holds 13,038,577 rows and `iwItemPriceDiscounts` 2,070,578.** Do not mirror prices. If a screen
  needs a price, read the one item's price, do not sync the table.
- **`iwWareitem` is 591,084 rows** against the desk's current largest mirror of 5,472. The hourly full-read pattern
  that works today will not scale to it unchanged. Stock on hand probably wants a narrowed view (one warehouse, or
  non-zero quantities only) or a changed-since read.
- Several `PMC_Backup_*` and `zz_Snapshot_*` tables sit in `LiveDB_PMC` beside the real ones. **Do not read a
  `PMC_Backup_` or `zz_` table**; they are other sessions' safety copies.
- Nothing above is a write. The write path to BizBox stays unbuilt and `PSA_BIZBOX_WRITE_ODBC` stays unset.

## 6. Reports for MMS

Dada asked for *"printing out reports for MMS"*. Not yet specified: which reports. Worth settling with him, but the
data supports at least: stock on hand by warehouse; stock card (movements) for an item; purchase orders by vendor
and by period; receiving by period; items with no movement; and — the hospital-specific one — **controlled drugs**,
which `isControlDrug` makes exact.

Note the estate already has SSRS on this instance (`ReportServer`), and a separate session owns BizBox SSRS work.
Whether MMS reports belong in the desk or in SSRS is a real design question, not an implementation detail. The desk
already downloads a Maintenance record as a spreadsheet, so there is a precedent for the desk doing its own.

## 7. How Dada wants it built

His words: *"make sure it has all the data it needs and it conforms to modern design load skills needed"*.

- **All the data it needs** — the point of this document. If something needed is not in §1 to §4, ask SQL01 to measure
  it rather than designing around a guess.
- **Modern design** — the Procurement screens set the bar: grids with search, column choice, filters, tick-and-send,
  inline cells, dropdowns that only offer what BizBox accepts.
- **Load the skills needed** — his instruction, relayed verbatim. `pmc-estate` carries the BizBox module facts and
  the LiveDB traps; `pmc-writing` governs anything staff read.

## 8. What SQL01 will do on request

The views are host-side and SQL01 owns them. Name the columns wanted and SQL01 will build each view in
`LiveDB_PMC`'s `psa` schema, grant SELECT to `psa_bizbox_reader`, and add the object to `D:\psa\bizbox-map.json` —
preview read first, as for the four that exist. Nothing is built until Cloud Build says which objects and columns.

**Dada has not been asked to choose anything yet.** The open questions for him are: which MMS reports; whether
requisitions should become the desk's own records given BizBox holds none; and whether stock on hand is wanted given
its size.
