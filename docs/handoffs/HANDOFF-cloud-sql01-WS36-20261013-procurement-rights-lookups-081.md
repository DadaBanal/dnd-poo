# HANDOFF — Cloud Build → SQL01, WS36, 13 Oct 2026 (Procurement: rights per area, dropdowns of what BizBox accepts, 081)

**One window: schema 080 and 081 together, the usual PSA-Desk restart, then three rows for Dada to set on
Setup › Security roles. One small read-only view inside BizBox is asked for (§5), at SQL01's pace; the desk works
without it.**

This follows `…-20261013-cw-shape-procurement-080.md` and **supersedes its §3**: run §3 below instead, which
includes 080. Its §4 (what to look for) and §5 (the write path, NOT to be built yet) still apply as written.

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file, **once CI is green on it**.

---

## 1. What Dada asked for, after seeing the 080 build

Dada, 13 Oct 2026, in order:

- *"make sure its user friendly and easy to understand"* and *"dont go by column names or db names or variables"*:
  every new screen reads in a person's words (the commit before this one).
- *"status or fields that needs a drop down to match bizbox choices must be done; all fields must not error when
  importing into bizbox"*. Chosen: **the values BizBox has shown so far, then BizBox's own lists** once SQL01 exposes
  them (§5); a value off the list is refused on the desk.
- *"rbac for the procurement module needs to be made as it will bypass the bizbox permissions"*. Chosen: **per area,
  See / Propose / Approve**: Purchase orders, Receiving, Items, as BizBox grants purchasing, receiving and inventory
  apart. No fallback from Finance.
- SQL01's message held so that 080 and 081 go in **one window**.

The README section is *Tasks, Configurations and Procurement in the reference PSA's shape*, under *Rights, per area*
and *Dropdowns of what BizBox accepts*.

## 2. What this head does on restart, before anything is set

- **Nobody sees the Procurement menu.** MEASURED from `security.py`: the three new rows (`PROC_PO`, `PROC_RR`,
  `PROC_ITEM`) have no grant for any existing role, there is no fallback, and a role with nothing there has no menu.
  The starter roles get rows only on an empty roles table, which the live desk's is not. So after the restart Dada
  sets them (§4). Until then Procurement is invisible and nothing can be proposed or approved.
- **Finance is unchanged.** Its pages still answer to the Finance level. On a Finance record page, the *Propose a
  change* box now offers a dropdown for a field BizBox has choices for, and refuses a value off the list.
- **081 is needed for the dropdowns to switch to BizBox's own lists** (§5). Without it the lists are what BizBox has
  used on real records, which on the live mirror is every status, vendor, currency, unit and category in use.
  MEASURED from the code: `bizbox.choices` asks for the table first and carries on without it.

## 3. The step: 080 and 081, then restart

1. Pull (once CI is green on the head).
2. Take a COPY_ONLY backup of `PMC_PSA`.
3. Stop `PSA-Desk`. PSA-Notify, PSA-Calendar, the pickups and the hourly `sync-bizbox` stay as they are.
4. Note `SELECT COUNT(*)` of `psa.ticket_task`, `psa.configuration`, `psa.ext_change`.
5. In one transaction, as sysadmin via pyodbc as for 066 to 079, run these blocks, each taken verbatim from
   `sqlserver/PMC_PSA_Spine_SqlServer.sql`. All are guarded, so a second run changes nothing:
   - **080** (as the earlier handoff listed them): `psa.[ticket_task]` ADD `priority`, `notes`, `resolution`,
     `schedule_id` (+ FK); `psa.[configuration]` ADD `tag_number`, `installed_by`, `notes`, `parent_configuration_id`
     (+ FK) and `ix_configuration_parent`; `CREATE TABLE psa.[ext_batch]` and `ix_ext_batch_status`;
     `psa.[ext_change]` ADD `batch_id` (+ FK) and `ix_ext_change_batch`.
   - **081**: the `CREATE TABLE` block under `-- ext_lookup (from schema/081_bizbox_lookup.sql)` and its index
     `ix_ext_lookup_list`.
6. Verify, inside the transaction:
   - the 080 checks from the earlier handoff's §3 step 6 (`ticket_task.notes` is -1, `schedule_id` is 4;
     `configuration.tag_number` is 800, `parent_configuration_id` is 128; `psa.ext_batch` exists with `batch_id`
     IDENTITY; `ext_change.batch_id` is 4 and no row has one);
   - `OBJECT_ID(N'psa.ext_lookup')` is non-NULL; `COL_LENGTH(N'psa.ext_lookup', N'list')` is **64** (32 characters);
     `COL_LENGTH(N'psa.ext_lookup', N'code')` is **800**; `SELECT COUNT(*) FROM psa.ext_lookup` is **0**;
   - the three counts from step 4 are unchanged;
   - control first, as in Part 77: probe a made-up column and see it read absent.
   - If any check fails, roll back and hand back.
7. Start `PSA-Desk`. Expect `:8085` to answer 401, go down, then answer 401 again.

Nothing changes in any scheduled task, the file store or the backup.

## 4. Then Dada, on the desk: the three rows

Setup › Security roles now has three Procurement columns. Each role takes **None**, **See**, **Propose** or
**Approve** for *Purchase orders*, *Receiving* and *Items*. Approve includes Propose; a person never approves their own
batch, and the Changes tab says *yours: someone else approves*. Suggested, to be confirmed by Dada with BizBox's
owner, since these rows stand in for BizBox's own per-person rights:

| Role | Purchase orders | Receiving | Items |
|---|---|---|---|
| Technician | See | See | See |
| Service manager | Approve | Approve | Approve |
| Read only | None | None | None |
| A buyer's role, if one is made | Propose | See | Propose |

Each save is audited (`SECURITY_ROLE`). Nothing else needs setting.

## 5. For SQL01, at its own pace: one lookup view inside BizBox

The desk's dropdowns switch from *what BizBox has used so far* to *BizBox's own list* the first time the hourly read
finds a `lookup` kind in the map. What it needs, in `LiveDB_PMC`'s `psa` schema beside the four views of 29 Sep:

- A read-only view, say `psa.vw_lookup`, with one row per entry of each list and four columns:
  `ListName`, `Code`, `Label`, `SortNo`. `ListName` is one of **`po_status`**, **`rr_status`**, **`currency`**,
  **`unit`**, **`category`** (any other name is read and ignored). `Code` is what BizBox stores on the record (what
  the desk will send back through the procedure); `Label` is what a person reads; `SortNo` orders the dropdown.
  Only BizBox's own code tables feed it: never a column from a people or patient table. The desk refuses a view or
  column name that looks like one.
- Grant SELECT on it to `psa_bizbox_reader`, as for the others.
- On the host, add to `D:\psa\bizbox-map.json` under `"objects"`:

```
"lookup": {"view": "psa.vw_lookup",
           "columns": {"list": "ListName", "code": "Code", "label": "Label", "sort_no": "SortNo"}}
```

- Preview the next read first (`sync-bizbox` without `--apply`): the last line names `lookup: N rows, N new`. Then let
  the hourly task run. The Procurement banner reads *… · N list entries (N new)* and a status dropdown shows the labels.

Until this exists, nothing is wrong: the lists are the values on real records, and a value off them is still refused.

## 6. What to look for

- After the restart and before §4: no Procurement in the menu for anyone but a system administrator.
- After §4, as a technician: Procurement shows; the grids have no bulk bar and no editable cells.
- As a service manager: a purchase order's *Status* cell is a dropdown of the statuses BizBox uses; *Vendor* lists the
  vendors BizBox has named; *Order date* is a date box. Tick two orders, choose a status from the dropdown, say why,
  *Send for approval*: a batch waits on the Changes tab, *yours: someone else approves*. A second manager approves.
- Type a vendor that is not BizBox's into a new order: it cannot be chosen at all (the vendor is a dropdown); the
  server refuses it too if forced.
- Setup › Security roles: the three columns read See / Propose / Approve, and the paragraph above the table says why.

## 7. Evidence

| | |
|---|---|
| Unit suite | `CwShapeTest` (+2): the lists per field from what BizBox has shown, the dropdowns in the cell, the bulk bar, the record page and both New forms, seven refusals (bulk, a cell, the record page, a vendor, a currency, a unit, a category) with no batch opened, a value on the list going through with the dropdown's value read for the chosen field, a lookup view read from CSV (labels, `ext_ref` made as `<list>:<code>`, the banner's words), the list taking over, a map without `code` refused, a second read unchanged, an absent entry leaving the list and the list falling back to what was seen; rights per area for a buyer (sees two areas, 403 on the third, proposes on one, cannot approve), an approver (approves another's, never their own, cancels), a batch in an unseen area hidden and 403, see-only without buttons, the umbrella level, no menu and a worded 403 with nothing set. `ModulesTest`: Finance's propose with BizBox's own list. CI run 92 (SQL Server) found the batch number burnt on a rolled-back refusal: every refusal now comes before a batch opens. Full suite: see the commit message. |
| T-SQL port | `tools/sqlite_to_tsql.py --check`: in step (MEASURED, this commit). |
| Screens | Roles page, the grids with dropdowns, Changes, New purchase order; taken on a throwaway desk, not attached. |
| CI | See the commit that follows. |
| Not run here | 080 and 081 against `PMC_PSA`; the lookup view against BizBox. |
