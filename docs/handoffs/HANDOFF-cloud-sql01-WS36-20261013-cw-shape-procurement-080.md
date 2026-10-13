# HANDOFF — Cloud Build → SQL01, WS36, 13 Oct 2026 (Tasks and Configurations in the reference PSA's shape; Procurement from BizBox's MMS, 080)

**One schema step, 080 (columns on `psa.ticket_task` and `psa.configuration`, one new table `psa.ext_batch`, one
column on `psa.ext_change`), the usual PSA-Desk restart. Nothing else to run now. The write path to BizBox is
specified here (§5) but is NOT to be built until Dada and BizBox's owner say so.**

This follows `…-20261012-warm-emails-department-079.md`. It supersedes nothing.

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file, **once CI is green on it**.

---

## 1. What Dada asked for, each part confirmed before building

Dada, 13 Oct 2026: *"i need to revamp tasks and configurations to look like the connectwise build and also i want you
to make sure that the mms module is mirrored in a spearate procurement module on connectwise where it will be easier
for them to do edits and adds on the bizbox system and easier for them to do multiple edits as well"*.

Four choices put to him, each taken as recommended:

1. **Tasks:** the full grid (Done, Pri, Task, Notes, Resolution, Schedule), edited in place, reordered, scheduled.
2. **Configurations:** the list (its columns, a column chooser, rows ticked and changed together) and the screen
   (header, tabs, pods) both; new fields tag number, installed by, notes, parent.
3. **Procurement:** a menu of its own with Purchase orders, Receiving, Products, Vendors and Changes.
4. **Edits to BizBox:** *approve on the desk, push by a procedure inside BizBox*. Not the other option (type into
   BizBox by hand). Never direct table writes from the desk.

The README section is *Tasks, Configurations and Procurement in the reference PSA's shape*.

## 2. What runs without 080

**This head runs without 080.** MEASURED from the code: the Tasks tab asks `tasks._grid` (the `notes` column), the
Configurations pages ask `configurations.cw_shape` (the `tag_number` column), and without them both show what they
show today. Procurement's grids read the mirror as Finance does; only queuing a batch needs `ext_batch`, and the
pages that queue are reached only by a person with Procurement WRITE. So the order is not critical, but the step is
small and the module is unfinished without it: apply it in the same window.

**Live on restart, with or without 080:**

- **The Procurement menu** appears for everyone whose role has Finance READ or above. MEASURED from `security.py`:
  a role with no PROCUREMENT row takes its Finance level. Setup › Security roles gains a *Procurement (BizBox)*
  column; nothing needs setting.
- **Finance's record pages** are unchanged, except the wording under *Changes to BizBox*.

## 3. The step: 080, then restart

1. Pull (once CI is green on the head).
2. Take a COPY_ONLY backup of `PMC_PSA`.
3. Stop `PSA-Desk`. PSA-Notify, PSA-Calendar and the pickups can stay as they are: none of them touches these tables.
   The hourly `sync-bizbox` task does not either (it writes `ext_*` mirror rows, never `ext_batch` or `ext_change`).
4. Note `SELECT COUNT(*) FROM psa.ticket_task`, `… psa.configuration`, `… psa.ext_change`.
5. In one transaction, as sysadmin via pyodbc as for 066 to 079, run these blocks, each taken verbatim from
   `sqlserver/PMC_PSA_Spine_SqlServer.sql`. All are guarded, so a second run changes nothing:
   - `psa.[ticket_task]`: `ADD [priority] INT NULL`, `ADD [notes] NVARCHAR(MAX) NULL`, `ADD [resolution] NVARCHAR(MAX) NULL`,
     `ADD [schedule_id] INT NULL CONSTRAINT [FK_ticket_task_schedule_id] REFERENCES psa.[ticket_schedule]([schedule_id])`;
   - `psa.[configuration]`: `ADD [tag_number] NVARCHAR(400) NULL`, `ADD [installed_by] NVARCHAR(200) NULL`,
     `ADD [notes] NVARCHAR(MAX) NULL`, `ADD [parent_configuration_id] NVARCHAR(64) NULL CONSTRAINT
     [FK_configuration_parent_configuration_id] REFERENCES psa.[configuration]([configuration_id])`, and the index
     `ix_configuration_parent`;
   - the `CREATE TABLE` block under `-- ext_batch (from schema/080_cw_shape.sql)` and its index `ix_ext_batch_status`;
   - `psa.[ext_change]`: `ADD [batch_id] INT NULL CONSTRAINT [FK_ext_change_batch_id] REFERENCES psa.[ext_batch]([batch_id])`
     and the index `ix_ext_change_batch`.
6. Verify, inside the transaction:
   - `COL_LENGTH(N'psa.ticket_task', N'notes')` is **-1** (MAX); `COL_LENGTH(N'psa.ticket_task', N'schedule_id')` is **4**.
   - `COL_LENGTH(N'psa.configuration', N'tag_number')` is **800**; `… N'parent_configuration_id'` is **128**.
   - `OBJECT_ID(N'psa.ext_batch')` is non-NULL, and `COLUMNPROPERTY(OBJECT_ID(N'psa.ext_batch'), N'batch_id', 'IsIdentity')`
     is **1** (the table's own numbers, as 078's were).
   - `COL_LENGTH(N'psa.ext_change', N'batch_id')` is **4**; `SELECT COUNT(*) FROM psa.ext_change WHERE batch_id IS NOT NULL`
     is **0**.
   - The three counts from step 4 are unchanged.
   - Control first, as in Part 77: probe a made-up column and see it read absent.
   - If any check fails, roll back and hand back.
7. Start `PSA-Desk`. Expect `:8085` to answer 401, go down, then answer 401 again.

Nothing changes in any scheduled task, the file store or the backup.

## 4. What to look for

- **A ticket's Tasks tab:** the grid; add a task, save a row, drag it, tick it done; *Tasks 1/3* on the tab (it reads
  *0/3* before anything is done);
  *Schedule…* books a visit that shows on the Schedule tab and on Dispatch.
- **Configurations:** the new columns and *Columns*; tick two rows, change their status, read the two audit rows;
  a configuration's screen with its three tabs; give a monitor a parent PC and see it under the PC.
- **Procurement** (a service manager): Purchase orders, Receiving, Products, Vendors counts match Finance's; the read
  banner reads in words (*5 purchase orders (5 new)*), never a table name; tick two orders, set Status, say why and
  *Send for approval*; the Changes tab shows the batch *Waiting for approval*, *yours: someone else approves*; a
  second manager approves; the row on the grid reads *Status* under *Waiting*.
- **Nothing in BizBox changes.** MEASURED from the code: no code path on this head opens a connection to BizBox for
  writing. `ProcedureWriter` exists but is built only when `PSA_BIZBOX_WRITE_ODBC` is set, and it is not set.
- `psaspine bizbox-push "<conn>"` (no `--apply`) prints *approved and waiting: N change(s)* and *PREVIEW*.

## 5. The write path to BizBox: specified, NOT yet to be built

Dada chose it; building it needs **his go and BizBox's owner's**, because BizBox is the hospital information system
(the record, §8.1) and the read-only login was a deliberate fence. When both have said yes, this is the whole of it.
Nothing in the desk is to be changed for it.

**5.1 The procedure, inside `LiveDB_PMC`, in the `psa` schema SQL01 made on 29 Sep:**

```
CREATE PROCEDURE psa.sp_apply_change
    @change_id     INT,
    @kind          NVARCHAR(32),      -- PURCHASE_ORDER, PRODUCT, INVOICE
    @change_kind   NVARCHAR(8),       -- EDIT or ADD
    @ext_ref       NVARCHAR(64),      -- the record's number (EDIT); NEW-<batch> (ADD)
    @field         NVARCHAR(64),      -- EDIT: status, vendor, ordered_on, due_on, supplier_ref, name, category, unit, unit_cost; ADD: NEW
    @new_value     NVARCHAR(400),     -- EDIT: the value as the desk shows it (dates ISO, money plain)
    @payload       NVARCHAR(MAX),     -- ADD: {"record": {...}, "lines": [{product_ref, description, quantity, unit_cost}, ...]}
    @requested_by  NVARCHAR(128),
    @approved_by   NVARCHAR(128)
AS ...
```

It returns **one row**: `ok BIT, message NVARCHAR(400), ext_ref NVARCHAR(64)`. `ok = 1` means applied, `message` is
what BizBox says, and for an ADD `ext_ref` is the number BizBox gave the new record. `ok = 0` means refused, with
the reason in `message`; the desk records it as REJECTED and nobody retries by accident. The desk commits only
on `ok = 1`, so the procedure may RAISERROR instead of returning 0 and the effect is the same.

The procedure owns every rule: which `postatus` codes a status word maps to, what `postflag`, `approvalflag` and
`cancelflag` mean, how a PO number is issued, which tables a line goes into. That is why it is BizBox's owner's
procedure and not the desk's: the desk knows none of it and must not guess.

**5.2 The login:** `psa_bizbox_writer`, a user in `LiveDB_PMC`, `GRANT EXECUTE ON psa.sp_apply_change`, and nothing
else: no role membership, no SELECT, no INSERT. **Pass:** as that login, `EXEC` works and `SELECT TOP 1 *` from any
table fails with permission denied. It is a different login from `psa_bizbox_reader`: the desk refuses a write
string whose UID equals the read string's.

**5.3 On the host:** `PSA_BIZBOX_WRITE_ODBC` in the environment of a scheduled task
`psaspine bizbox-push "<conn>" --apply`, say every 15 minutes, logging to `D:\psa\logs`. Not in PSA-Desk's
environment: the desk itself never pushes. Preview first, as always.

**5.4 Vendors, later if wanted:** the Vendors tab lists the names BizBox puts on orders and receipts. A vendor view of
its own (`psa.vw_vendor`, code and name, never `psDatacenter`'s people columns) would make a vendor kind; that is a
separate ask.

## 6. Evidence

| | |
|---|---|
| Unit suite | `CwShapeTest` (5): the Tasks grid end to end (add with notes, save a row with a history line, reorder by order and by arrows with refusals, the count on the tab, schedule a task to a member and read the visit, a second schedule refused, remove renumbers and keeps the visit, a reader sees no forms and a write answers 404 as time and notes do); the Configurations list (default and chosen columns, sort by tag, search by tag, bulk change audited per row, refusals counted, 403 for a reader); the screen (tabs, pods, tag, installed by, notes, parent and children, a cycle refused at any depth and itself); Procurement (read at the Finance level, grids and counts, vendor filter, the record page under its own menu, 403 to write, bulk to a batch with the mirror untouched, the Waiting chip, approval refused to the asker and taken from root, edited cells to a batch of only what differs, a new order with lines and its refusals, a new item and its refusals, cancel, push through NoWriter then a fake writer with one refusal, the write string's fence, the CLI preview); a role with Finance NONE sees neither until given its own Procurement level. Full suite: see the commit message. |
| T-SQL port | `tools/sqlite_to_tsql.py --check`: in step (MEASURED, this commit). |
| CI | See the commit that follows. |
| Not run here | 080 against `PMC_PSA`; anything against BizBox. |
