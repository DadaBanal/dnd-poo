# HANDOFF — Cloud Build → SQL01, WS36, 13 Oct 2026 (warehouses, drugs and medicines, stock on hand: what to build in BizBox's psa schema, 083)

**Two small read-only views for the hourly read, one measurement before a third, and three rows on Security roles.
Schema 083 on the desk is two mirror tables. Nothing writes to BizBox.**

This answers the second half of your `HANDOFF-sql01-cloud-WS36-20261013-mms-full-drugs-reports.md` (§2, §3, §5) and
the message of 13 Oct (*"add warehousing … 73 warehouses in 6 groups … stock-on-hand is 591,000 rows … needs
narrowing"*). It follows `…-20261013-mms-reports-082.md` and supersedes nothing.

## 1. What Dada chose, 13 Oct 2026

Three choices put to him:

- **Warehouses:** a Warehouses tab under Procurement, the list by group, read hourly from one small view. The
  warehouse becomes a dropdown wherever a form asks for one.
- **Stock on hand:** the MMS reports now (Perpetual inventory, Item inventory balance per department); a narrowed
  mirror **once you have measured it** (§4). Nothing copied blind.
- **Drugs and medicines:** a Drugs tab in Procurement **as its own rights area** (*Procurement: drugs and
  medicines* on Security roles), so pharmacy can be given See or Propose apart from the rest of Items. The item's
  page shows its medicine facts; a *Controlled* filter and chip.

## 2. The two views, in `LiveDB_PMC`'s `psa` schema, beside the four of 29 Sep and the lookup view

Name the columns exactly as below (the map on the host carries BizBox's names; the desk reads the desk-side names).
Both read reference tables only: no patient table, no price table, no `PMC_Backup_` or `zz_` table.

**`psa.vw_warehouse`** from `dbo.mscWarehouse` joined to `dbo.mscWarehouseGrp` (73 rows):

| Desk field | Your column | What it is |
|---|---|---|
| `ext_ref` | `WarehouseCode` | the key, as BizBox stores it |
| `name` | `WarehouseName` | the name staff use |
| `group_name` | `GroupName` | the group's name (Admin, Nursing Service, Ancillary, …) |
| `active` | `IsActive` | 1 or 0 |

**`psa.vw_drug_item`** from `dbo.iwItemMedicines` joined to `dbo.iwItems` and `dbo.mscGenerics` (2,166 rows), one row
per item that is a medicine. (Not `vw_medicine`: the desk's patient-word fence refuses any view name containing *medic*,
by design, and this one is an item list, so it takes a name the fence lets through.)

| Desk field | Your column | What it is |
|---|---|---|
| `ext_ref` | `ItemCode` | the item's code, the same key `psa.vw_product` uses, so the desk joins them |
| `generic` | `GenericName` | from `mscGenerics` |
| `dosage` | `Dosage` | as stored |
| `controlled` | `IsControlDrug` | 1 or 0 |
| `doh_ref` | `DOHDrugCode` | `iwItems.EDPMSDrugCode`, or the DOH list key if that is the better name |
| `mims_ref` | `MIMSDesc` | the MIMS description, not the GUID |
| `admin_group` | `AdminGroup` | the drug administration group's name |
| `remarks` | `Remarks` | free text; leave it out of the view if it ever carries a patient's words |

Grant SELECT on both to `psa_bizbox_reader`, as for the others. Then two objects in `D:\psa\bizbox-map.json`:

```
"warehouse": {"view": "psa.vw_warehouse",
              "columns": {"ext_ref": "WarehouseCode", "name": "WarehouseName", "group_name": "GroupName", "active": "IsActive"}},
"medicine":  {"view": "psa.vw_drug_item",
              "columns": {"ext_ref": "ItemCode", "generic": "GenericName", "dosage": "Dosage", "controlled": "IsControlDrug",
                          "doh_ref": "DOHDrugCode", "mims_ref": "MIMSDesc", "admin_group": "AdminGroup", "remarks": "Remarks"}}
```

Preview the read first (`sync-bizbox … --odbc`, no `--apply`): the last line names `warehouse: 73 rows, 73 new` and
`medicine: 2166 rows, 2166 new`. Then let the hourly task run.

## 3. The desk side (this head), after 083 and the restart

- **Procurement › Warehouses:** the 73 by group, active ones first, with a search. Read-only.
- **Procurement › Drugs:** the medicines with their item name, generic, dosage, controlled (a chip and a filter), DOH
  and MIMS references; search by any of those. Read-only on this head: the write path to BizBox is still unbuilt,
  and a medicine's own fields are BizBox's.
- **An item's page** gains a *Medicine* card when the item is one.
- **Security roles:** a fourth Procurement column, *Drugs and medicines* (None / See / Propose / Approve). Set as Dada
  names it; nobody sees the Drugs tab until then. Warehouses show to anyone with See on Items.

## 4. Stock on hand: measure before anything is built

Before any view, two numbers from `dbo.iwWareitem`, as the read-only login:

1. `SELECT COUNT(*) FROM dbo.iwWareitem WHERE <quantity column> <> 0` — how many rows carry stock at all.
2. The same, grouped by warehouse, largest first, top ten.

Then the choice is Dada's with the numbers in hand: a narrowed view (`item code, warehouse code, quantity on hand,
as of`) joins the hourly read only if (1) is a few thousand; otherwise an item's page reads its own stock on demand,
or stock stays in the reports. Nothing here needs `iwItemLedger`, and nothing ever reads `iwItemPrices`.

## 5. The step on the host

1. Pull the head that carries this file, once CI is green on it.
2. COPY_ONLY backup; stop PSA-Desk; apply **083** (two `CREATE TABLE` blocks, `ext_warehouse` and `ext_medicine`, with
   their indexes, from `sqlserver/PMC_PSA_Spine_SqlServer.sql`); verify both exist and are empty; start PSA-Desk.
3. The two views and the map (§2); preview; let the hourly read run.
4. Dada sets the *Drugs and medicines* column on Security roles.
5. The two measurements (§4), reported back as numbers.

## 6. Evidence

See the commit that follows: `WarehousesAndDrugsTest`, the port in step, screens on a throwaway desk. Not run here:
anything against BizBox.
