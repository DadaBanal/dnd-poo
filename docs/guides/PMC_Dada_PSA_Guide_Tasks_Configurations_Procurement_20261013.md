# Dada PSA: Tasks, Configurations and Procurement — a guide for the desk

**For:** PMC IT technicians and service managers (first reader: Shane). **Date:** 13 October 2026.
**Covers:** the desk after the 13 October update (schema 080 and 081). Nothing here reaches BizBox by itself: every
change you queue waits for a second person's approval, and the link that sends approved changes to BizBox is not
switched on yet.

Read it in order the first time; afterwards jump to the part you need.

---

## 1. What changed, in one minute

- **A ticket's Tasks tab** is now a grid you work in directly: tick a task done, type notes and how it was fixed in the
  row, drag tasks into order, and book a visit for a task.
- **Configurations** (every PC, printer, server, switch and device the desk supports) has a list you can shape (choose
  your columns, sort any of them, change several at once) and a screen with tabs: *Configuration*, *Tickets*,
  *History*. New fields: tag number, installed by, notes, and a parent (a monitor under its PC).
- **Procurement** is a new menu. It shows BizBox's purchase orders, receiving reports, items and vendors, read from
  BizBox every hour. You can queue edits and new records there; a second person approves them on the *Changes* tab.
- **Dropdowns only offer what BizBox accepts.** A status, a vendor, a currency, a unit or a category is picked from a
  list, never typed. If a value is not on the list, the desk refuses it and tells you so.
- **What you may do in Procurement depends on your role**, per area: *See*, *Propose* or *Approve* for purchase
  orders, receiving and items. If you cannot see Procurement at all, your role has nothing set yet; ask Dada.

## 2. The Tasks tab on a ticket

Open any ticket and click **Tasks**. The tab shows *Tasks 1/3* when one of three is done.

| Column | What it is | What to do |
|---|---|---|
| **Done** | The tick box | Tick it when the task is finished. Your name appears under it. |
| **Pri** | The task's place in the list | Drag the handle at the left of the row, or use the up and down arrows. |
| **Task** | The words of the task | Change them in the row, then press the tick at the right of the row to save. |
| **Notes** | Notes for the tech doing it | Same: type, then press the tick. |
| **Resolution** | How it was fixed | Type it when you are done, then press the tick. |
| **Schedule** | A visit booked for this task | *Schedule…* opens a small form: who, which day, what time, how long. It books a visit on the ticket, the same visit you see on Dispatch and the Schedule tab. |

**Add a task:** the box at the bottom. Type the task, optionally notes, then **Add task**. *Add from template* fills
the usual tasks for a kind of job.

**Remove** (the cross) takes the task off the list; a visit already booked for it stays on the ticket.

If you only read a board, you see the grid with no boxes and no buttons.

## 3. Configurations

### 3.1 The list

Menu: **Configurations**. The tiles at the top count machines by type and show warranties ending in 90 days and
already ended; click a tile to filter.

- **Search** reads the name, DNS name, serial, tag and description.
- **Columns** (top right) lets you choose which columns show. Click a column heading to sort by it.
- **Tick rows, then *Apply to ticked***: set one status, type or contact on every ticked machine at once. Leave a
  box on *leave* to keep that field as it is. Each machine is changed on its own, so each has its own history line.
- **New configuration** at the bottom is for a machine Active Directory does not know (a printer, a switch, a
  biomedical device). PCs that come from Active Directory arrive by import and are never typed in.

### 3.2 A configuration's screen

Click a name. The header shows the name, its type, its tag number, the company, and where it came from (*typed in by
hand* or *Active Directory*). **Raise a ticket for this machine** opens a new ticket already linked to it.
**Maintenance record** downloads every ticket on it, with hours and visits, as a spreadsheet.

Three tabs:

- **Configuration**: the facts (type, status, company, site, location, contact, tag, parent), the details (make,
  model, serial, vendor, purchase and warranty dates, installed by, notes), the questions its type asks, the child
  configurations under it, and the **Change** form.
- **Tickets**: open tickets on it, then recently closed ones. The number on the tab is the open count.
- **History**: everything the desk did to it, newest first.

**Parent:** on Change, pick the machine this one belongs under (a monitor under its PC, a card under its server).
The parent must be at the same company, and the desk refuses a loop.

## 4. Procurement

Menu: **Procurement**. The green line under the heading says when BizBox was last read and what it holds, for
example *Read from BizBox 2026-10-13 09:00 · 5 purchase orders (5 new) · 3 order lines · 4 items · 2 receiving
reports*. Everything on these pages comes from BizBox; the desk is a mirror of it.

### 4.1 The tabs

| Tab | What it shows |
|---|---|
| **Purchase orders** | BizBox's purchase orders: number, vendor, order date, status, total, how many lines, and whether a change is waiting. |
| **Receiving** | BizBox's receiving reports: number, the supplier's invoice number, vendor, dates, status, total. |
| **Products** | BizBox's items: code, name, category, unit, unit cost. |
| **Vendors** | The vendors BizBox names on orders and receipts, with counts and totals. A vendor's own record lives in BizBox; nothing is edited here. |
| **Changes** | Every batch of changes: waiting for approval, approved and waiting to be sent, applied, refused, cancelled. |

You see only the tabs your role allows (section 6).

### 4.2 Reading and filtering

Each grid has a search box, a status filter (for items, a category filter), a vendor filter, and *Gone from BizBox
too*, which also shows records BizBox no longer returns. Click a number to open the record's own page, with its lines
and the work linked to it.

### 4.3 Changing several records at once (tick and send)

1. Tick the rows you want to change (the box at the top ticks every row shown).
2. In the bar above the grid, choose the field (*Status*, *Vendor*, *Order date*…).
3. Choose or type the new value. For a status, a vendor or a currency it is a dropdown of what BizBox accepts.
4. Write **why**, in a sentence. The approver reads it, and BizBox's owner may read it later.
5. **Send for approval.**

The desk answers *Batch #N queued: 2 record(s)* and the rows show a chip under **Waiting** naming the field. A row
that already has that value is left out and counted.

### 4.4 Editing cells in place

Change the cells you want directly in the rows (a dropdown, a date box or a text box), write why in the lower bar,
then **Send edited cells for approval**. Only the cells that differ from what BizBox has are sent; the count on the
left tells you how many you have changed. A cell set back to its original value is not a change.

### 4.5 A new purchase order or a new item

**New purchase order** (top right of the Purchase orders tab): vendor (a dropdown of BizBox's vendors), order date,
currency, status (leave it to BizBox unless told otherwise), up to eight lines (item code, description, quantity,
unit cost), and why. The item on a line must be an item BizBox has; the box offers them as you type.

**New item** (Products tab): code (leave empty and BizBox numbers it), name, category, unit, unit cost, why.

Both go to the Changes tab as one batch. BizBox gives the record its number once it is created there.

### 4.6 The Changes tab, and approving

Each row is one **batch**: one reason, one approval, any number of changes. Click the batch number to see each
change (record, field, from → to, who asked, when).

| State | Meaning |
|---|---|
| **Waiting for approval** | Someone proposed it. A person with *Approve* for that area, other than the one who asked, approves or cancels it. |
| **Approved, waiting to be sent** | Approved; it waits for the link to BizBox. Until that link is switched on, it stays here, or someone makes the change in BizBox by hand and marks it applied. |
| **Applied in BizBox** | Done. BizBox's answer is shown under the state. |
| **Refused by BizBox** | BizBox would not take it. Its reason is shown. Propose it again with the reason addressed. |
| **Cancelled** | Withdrawn by the person who asked, or by an approver. |

**You cannot approve your own batch.** The row says *yours: someone else approves*. This is deliberate: two people
look at every change before it reaches the hospital's purchasing system.

**Nothing is sent to BizBox automatically yet.** The Changes tab says so in its own words. Approved changes wait
there until the link is built and switched on, which Dada and BizBox's owner decide.

## 5. Dropdowns: why you cannot type a status

BizBox only accepts its own values. So on the desk a purchase order's status, vendor and currency, a receiving
report's status, and an item's unit and category are dropdowns, in the grid, on the tick-and-send bar, on a record's
page and on the New forms. The list is what BizBox has used on real records; once BizBox's own code lists are read
by the desk, the dropdowns show those, with their proper labels.

If a value is forced in another way, the desk refuses it with *That is not a status BizBox uses on purchase orders;
pick one from the list*, and no batch is opened. A date must be a real date; an amount must be a number; a line's
item must be an item BizBox has.

## 5a. MMS reports: run one, read it on the page, or take the Excel

**Procurement › Reports** lists the hospital's MMS reports (stock on hand, reorder points, purchases by vendor,
receiving, issued supplies and the rest), grouped by area. You see the areas your role allows. Search by a word in
the title.

1. Click a report. Its page asks for what the report needs: dates, a warehouse group, a warehouse, yes or no. Lists
   come from the report server itself, so you can only pick what it knows.
2. When a list depends on another (the warehouse on the warehouse group), choose the first and the second fills in.
   If it does not, click **Refresh choices**.
3. **Run and show the PDF.** The report appears on the page. **Open in a new tab** shows it larger or prints it;
   **Download Excel** saves a workbook with the same values.
4. Next time, the page opens with the values you used last.

If the page says the report server refused the desk's sign-in or could not be reached, nothing is wrong with your
values: tell Dada, who tells SQL01. Every run is logged, so a report you ran can always be found again.

## 6. What your role lets you do in Procurement

Procurement has three areas, as BizBox grants purchasing, receiving and inventory separately: **Purchase orders**,
**Receiving**, **Items**. For each, your role has one of:

| Level | You can |
|---|---|
| **None** | Nothing; the tab does not show. With none in any area, the Procurement menu does not show. |
| **See** | Open the tab and the records. No bars, no editable cells, no New button. |
| **Propose** | Tick and send, edit cells, add a new order or item. Cancel your own batches. |
| **Approve** | Everything above, plus approve other people's batches and cancel anyone's. Never approve your own. |

The desk sends every approved change to BizBox under one login, so these levels are what BizBox's own per-person
rights used to be. Dada sets them on Setup › Security roles. If you expect to see something and cannot, that is the
first place to ask.

## 7. How to: step by step

**Work a ticket's tasks**

1. Open the ticket, click **Tasks**.
2. Type the first task in *Add a task* (notes are optional), click **Add task**. Repeat, or use *Add from template*.
3. Drag the handle at the left of a row to put tasks in order.
4. For a task that needs a visit, click *Schedule…* on its row: who, which day, what time, how long, then **Book**.
   It shows on Dispatch and the Schedule tab.
5. When a task is done, tick **Done**, type how it was fixed under *Resolution*, press the tick at the right of the
   row. The tab now reads *Tasks 1/3*.

**Record a new printer and put it under its PC**

1. **Configurations**, scroll to *New configuration*.
2. Name (as the ward knows it), company, type *Printer*, tag number from the asset sticker, make, model, serial, a
   line on where it is. **Add**.
3. Open it, go to **Change**, choose its *Parent configuration* (the PC it hangs off), **Save**. The PC's page now
   lists it under *Child configurations*.
4. From its page, **Raise a ticket for this machine** opens a ticket already linked to it.

**Change the status of several purchase orders**

1. **Procurement**, Purchase orders tab. Filter by vendor or status if it helps.
2. Tick the orders. The bar reads *N ticked*.
3. Field *Status*; pick the new status from the dropdown; write why; **Send for approval**.
4. The rows show *Status* under *Waiting*. Tell your approver.

**Fix one wrong cell**

1. On the grid, change the cell in the row: pick the vendor from the dropdown, or set the date.
2. The lower bar reads *1 cell(s) edited*. Write why; **Send edited cells for approval**.

**Raise a new purchase order**

1. Purchase orders tab, **New purchase order**.
2. Vendor from the dropdown; order date; currency (PHP is set); leave status to BizBox unless told otherwise.
3. One line per item: start typing the item code and pick it; description; quantity; unit cost.
4. Why; **Send for approval**. It appears on Changes as *New purchase order: <vendor>, N line(s)*. BizBox numbers
   it once it is created there.

**Add a new item**

1. Products tab, **New item**.
2. Leave the code empty unless the hospital has one; name; category and unit from the dropdowns; unit cost; why;
   **Send for approval**.

**Approve, or cancel, a batch** (needs *Approve* for that area)

1. **Procurement**, Changes tab. The filter starts on *Waiting to be approved or sent*.
2. Click the batch number to read each change and the reason.
3. **Approve**, or **Cancel** with a word to the person who asked. You cannot approve your own; the row says so.
4. An approved batch reads *Approved, waiting to be sent* until the link to BizBox is on.

**See what happened to a change**

1. Changes tab; set the filter to *Applied in BizBox*, *Refused by BizBox* or *All*; **Show**.
2. BizBox's answer is under the state. A refusal names the reason; propose it again with that addressed.

**Give a role its Procurement rights** (a system administrator)

1. **Setup › Security roles**.
2. On the role's row, set *Purchase orders*, *Receiving* and *Items* to None, See, Propose or Approve. **Save**.
3. Under *Members*, put each person on the right role. The change shows in Setup › Audit.

## 8. Common messages and what to do

| The desk says | It means | Do |
|---|---|---|
| *Your security role does not let you see procurement* | Your role has None in every area | Ask Dada to set your role. |
| *That is not a vendor BizBox has; pick one from the list* | The vendor is not on any BizBox order or receipt | Pick an existing vendor. A new vendor is created in BizBox first. |
| *Every ticked record already has that value in BizBox* | Nothing to change | Nothing to do. |
| *Nothing was changed: every cell still reads what BizBox has* | You sent the edited-cells bar with no cell changed | Change a cell first. |
| *Say why, so the person who approves it and BizBox's owner know* | The why box was empty | Write one sentence. |
| *A change to status on PO-… is already pending; cancel it first* | Someone has already queued that field on that record | Open Changes, read the pending one, cancel it if yours or ask its owner. |
| *A change is approved by someone other than the person who asked for it* | You tried to approve your own | Ask a second approver. |
| *Line 2: IT-9 is not an item BizBox has* | The item code is wrong | Pick the item from the list as you type. |

## 9. Good habits

- Write the **why** as if BizBox's owner will read it next month, because they may.
- Tick and send one field at a time; one batch, one reason.
- Before proposing a vendor change, open the order's page and read its lines.
- Do not retype a value you can pick.
- If a screen shows a code or a column name instead of a word, tell Dada: that is a bug, not how it should read.

---

*Questions: the PMO Helpdesk board, or Dada. This guide is kept in the repository under `docs/guides/` and is
superseded, never edited, when the desk changes.*
