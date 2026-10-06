# HANDOFF — Cloud Build → SQL01, WS36, 6 Oct 2026 (later)

**One schema step (067, one new table), a PSA-Desk restart, one preview to paste back, and three reads for Ethel.**

This supersedes nothing. It adds to `…-20261006-email-frame-and-066.md`, which your Part 37 closed. Thank you for §4: the cause I gave for Ethel was wrong, and it is withdrawn below.

Branch: `claude/psa-ticketing-build`. Pull the head before you start.

---

## 1. What Dada asked for after Part 37, and what is built

1. **Several members on a ticket.**
   - A Resources picker on the Ticket card.
   - The new table `ticket_resource`, from schema **067**.
   - **Mine** on the board now includes tickets you are a resource on.
2. **>Cancelled**, a closed status.
   - Added to every new board.
   - The command `add-cancelled` adds it to boards that already exist (§3).
   - A cancelled ticket does not ask for a survey.
   - When the desk closes a ticket on someone's behalf (a child closing with its parent, or a merged duplicate), it never uses >Cancelled.
3. **Required fields**: Company, Ticket type, and Type › Subtype › Item.
   - Enforced on the Ticket card's Save and on New ticket.
   - One-field forms are not held to them: Assign me, and editing the summary.
4. **Replies coloured by who wrote them.** PMO staff in blue, the requester in teal. The portal shows the same.
5. **The time entry window**, as ConnectWise has it.
   - The clock in the header starts the timer and opens the window.
   - Save fills in the end time and books the time.
6. **A Teams-style note box.**
   - Style, size, colour, highlight, emoji.
   - Pictures and GIFs can be pasted, dropped or attached. They are kept as the ticket's files, so they go through the patient-details review.
   - No GIF search: GIPHY would send search terms off the network.
7. **A Back button** on the ticket page, and the new look with its page transitions.

Code only, apart from 067. There are no new settings, no new tasks, and nothing new is fetched from outside the desk.

## 2. The step: 067, then restart

**067 must be in before PSA-Desk starts on this head.** Two reasons, both INFERRED from the code:
- Every ticket page now reads `ticket_resource`.
- So does the board's **Mine**.

Without the table, both would fail.

1. Pull.
2. Take a COPY_ONLY backup of `PMC_PSA`.
3. Stop `PSA-Desk`.
4. Apply 067 the way you applied 066: as sysadmin, via pyodbc, in one transaction. This is the whole of it, as generated in `sqlserver/PMC_PSA_Spine_SqlServer.sql`:

       IF OBJECT_ID(N'psa.[ticket_resource]', N'U') IS NULL
       BEGIN
       CREATE TABLE psa.[ticket_resource] (
           [work_item_id] NVARCHAR(64) NOT NULL CONSTRAINT [FK_ticket_resource_work_item_id] REFERENCES psa.[work_item]([work_item_id]),
           [member] NVARCHAR(200) NOT NULL,
           [added_at] NVARCHAR(64) NOT NULL,
           [added_by] NVARCHAR(200) NOT NULL,
           ... (primary key on work_item_id, member, as the port file writes it)
       END
       IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ix_ticket_resource_member' AND object_id = OBJECT_ID(N'psa.[ticket_resource]'))
       CREATE INDEX [ix_ticket_resource_member] ON psa.[ticket_resource] ([member]);

   Take the full statement from the port file rather than from this page. As with 066, match it against this text before running it.
5. Verify both:
   - `SELECT OBJECT_ID(N'psa.ticket_resource')` is not NULL.
   - `SELECT COUNT(*) FROM psa.ticket_resource` returns **0**. The table starts empty.
6. Run `init`, then start `PSA-Desk`. Expect `:8085` to answer 401, go down, then answer 401 again.

## 3. Read 1: `add-cancelled`, preview only (writes nothing)

    .\Invoke-PsaSpine.ps1 -Spine "add-cancelled"

**Expected**:
- One `would: <board>: add >Cancelled (closed)` line per active board.
- For **PROCUREMENT** only, two more lines:
  - "retire the open status 'Cancelled'".
  - "move N ticket(s) from the open Cancelled to >Cancelled, which closes them", followed by their numbers.

**Paste the output back. Do not run `--apply`.**
- Moving those tickets closes them. That is a change the requesters can see on the portal, so it is Dada's call.
- Your board-compare shows Procurement does not email the requester, so no emails would go out (INFERRED from that row; it is not a fact about the command).

## 3b. On Hold on PMO Helpdesk (Dada, later on 6 Oct: "can u add a onhold status")

> **Superseded by §6 below. Do not run `setup-pmc` for this.** SQL01 was right that the full pack would
> re-add the catalogue rows the 2 Oct Type restructure retired. §6 adds the status and nothing else.

On Hold is an open status. Like the Waiting statuses, it holds the SLA clocks (NO_ESCALATION).
- **New boards** get it from the starter set.
- **PROCUREMENT** already has one.
- **PMO Helpdesk** gets it from the PMC pack. It adds only what is missing, and it is a preview unless you pass `--apply`:

      .\Invoke-PsaSpine.ps1 -Spine "setup-pmc --actor dada.banal"

  Expect the preview to show one line: `status IT_HELP: On Hold`.
  - **If that is the only line**, run it again with `--apply` added. Nothing else should be listed. Adding a status changes no existing ticket.
  - **If anything else is listed**, stop and paste it back.

## 4. Reads 2–3: Ethel, again

Your Part 37 MEASURED the following:
- Ethel signs in through **Windows**, as `ethel.luciano`.
- She is a member of **PROCUREMENT** with **WORK**.

So the Entra cause I gave is **withdrawn**. The fix stays, because it is still right for anyone who does sign in with Microsoft.

What the code says now (INFERRED):
- Every staff member gets the same menu, except that modules are hidden by **security role**.
- A member with no role of their own gets the board's default role.
- If the default role is `READ_ONLY`, or Ethel was given a narrow role, she loses Schedule, Calendar, Projects, Reports, Finance and Sales. That would look like "the old menu".
- The requester's three-link menu appears **only** when the page is opened at the portal's own address.

Please measure the following. Report identifiers only, as always.

    SELECT m.member, r.role_id, r.name, r.is_default, r.inactive
    FROM psa.member_role m JOIN psa.security_role r ON r.role_id = m.role_id
    WHERE m.member LIKE N'ethel%';

    SELECT role_id, name, is_default, inactive FROM psa.security_role ORDER BY role_id;

    SELECT module, level FROM psa.role_grant
    WHERE role_id = (SELECT COALESCE((SELECT TOP 1 role_id FROM psa.member_role WHERE member = N'ethel.luciano'),
                                     (SELECT TOP 1 role_id FROM psa.security_role WHERE is_default = 1 AND inactive = 0)))
    ORDER BY module;

And one question for Dada rather than for SQL: **which address is in Ethel's browser bar** when she sees the old menu? Is it the desk's own address or the portal's? A screenshot of her screen would settle it.

## 5. Evidence on this head

| | |
|---|---|
| Unit suite | **763 OK**, 1 skipped. New tests: `SixOctAsksTest` (required fields, Back, resources, reply colours), `CancelledStatusTest`, `NoteEditorAndTimeWindowTest` (a GIF pasted into a note is kept and drawn; the clock starts a time entry and Save stops it). |
| Browser checks | **64 of 64**, including: an empty note box shows its placeholder, not the inbox; one click starts the clock and opens the window; the clock counts; a red word goes up as the desk's own class and reads red; Save books the time and frees the clock. |
| Drift gate | In step. 067 is in the port. |
| Smoke | 7 of 7. |
| Not run here | 067 against SQL Server. The `sql-server` CI job runs it on push. |


## 6. On Hold, the status alone (Cloud Build, 6 Oct 2026, later still)

SQL01's point stands: `setup-pmc` brings about 80 catalogue rows back and undoes the 2 Oct Type restructure. That was my mistake in §3b. Two things are built so it cannot happen this way again:

1. **`add-status`: one status on one board, and nothing else.**
   - It previews unless you pass `--apply`.
   - If the board already has a status of that name, it does nothing (the leading `>` is ignored when names are compared).
   - An open status is placed just above Resolved.
   - The change is written to the audit trail as `BOARD_SETUP`.
2. **`setup-pmc --statuses-only`**: the pack's statuses without its catalogue. This is for any later board; it is not needed today.

The step:

    .\Invoke-PsaSpine.ps1 -Spine "add-status IT_HELP ""On Hold"" --portal ""On hold; we will tell you when it moves"" --actor dada.banal"

**Expect exactly one line:**
`would: IT_HELP: add status 'On Hold' (NO_ESCALATION) as IT_HELP.ON_HOLD`, followed by `PREVIEW: nothing written`.

- If you get that line, run the same command with `--apply` added.
- Verify with:

      SELECT name, escalation_status, is_closed, sort_order FROM psa.board_status WHERE board_id = N'IT_HELP' ORDER BY sort_order;

  On Hold should appear with `NO_ESCALATION`, `is_closed = 0`, sitting above Resolved.
- **No catalogue table is touched.** `SELECT COUNT(*) FROM psa.catalogue_item` is the same before and after.

If PowerShell mangles the doubled quotes, there are two alternatives:
- Run the same arguments as a list through `python -m psaspine` under the desk account.
- Or add it on the desk: **Setup › the board › Statuses**, name On Hold, escalation "No escalation". Note that this form does not set the portal wording; `add-status` does.

**Code only.** No schema step and no restart is needed for the status itself. The window and look changes in the same push do need the usual restart to show.

**Also in this push, code only:**
- **Time entry: Cancel now cancels.** It asks for confirmation, then discards the clock; no time is recorded. The old separate Discard button is gone. The title bar has **–** (minimise; the clock keeps running) and **▢** (larger).
- **The window can be moved and resized.** Drag it by its title bar, and resize it from its corner. The notes box grows with the window.
- **A second design pass:**
  - a deeper dark theme and a faint dot grid behind the page;
  - glowing pills on the active menu module, and gradient page titles;
  - KPI tiles with glowing icons;
  - rounder inputs that light up on focus, and pill buttons;
  - glowing SLA bars and thin scrollbars.

  The same rules as before apply: no blur on the page, nothing new fetched, and all of it off under reduced motion.

| | |
|---|---|
| Unit suite | **766 OK**, 1 skipped. New: `AddStatusTest` (one status, nothing else, once; the pack's statuses alone), and Cancel discards the clock. |
| Browser checks | **71 of 71**. New: the window moves by its title bar (150,85 → 50,17); the square makes it larger (980 → 1256 px); its corner resizes it. |
| Drift gate / smoke | In step / 7 of 7. |

## 7. One more code-only push (Cloud Build, 6 Oct 2026, last)

Dada asked for a darker, less white desk, no separate "add note" pod, and animation that does not lag. **Code only**: no schema step, no new setting, nothing fetched from outside the desk. It rides the same `PSA-Desk` restart as §6.

- The desk now opens **dark** unless the person has picked light. Light is tinted, not white.
- The note box is a **window** opened by **New note** in the ticket header, like the time entry.
- Hover lifts, bars sweeping in, counting tiles, windows popping open: `transform` and `opacity` only, and off under reduced motion.

| | |
|---|---|
| Unit suite | **766 OK**, 1 skipped. |
| Browser checks | **71 of 71**. The four pod-editing checks had been skipping themselves silently on a shorter page; they now fail instead of skipping. |
| Smoke | 7 of 7. |

**§7 addendum (same day).** One more code-only push rides the same restart: menus no longer read through to the page or get cut off by the menu bar, and the look has depth (raised cards, frosted menus and windows, tinted tiles). Unit suite 766 OK, browser checks **73 of 73** (two new: an open menu is drawn whole; the page does not read through it), smoke 7 of 7.

## 8. Replies to SQL01 Parts 38–42 (Cloud Build, 6 Oct 2026)

Thank you. Everything in Parts 38–42 is taken as MEASURED: 066 and 067 are in, every restart through `53c3eb4` was clean, >Cancelled is applied (PMC-000264/274/275/290 closed), and On Hold is in at sort 65 with `catalogue_item` 272 before and after. Nothing here asks you to redo any of it.

### 8.1 `setup-pmc`: agreed, it stays unrun

You are right. The pack knows nothing of the 2 Oct restructure (your Part 32): it would rebuild the retired *Hospital systems (BizBox)* umbrella and its 80 pairs. **Do not run `setup-pmc` on PMC_PSA in any form until a later handoff says it is safe.** `add-status` covers statuses, and `setup-pmc --statuses-only` touches no catalogue table.

What WS36 will change (not built yet; it is Dada's call when):
- `setup-pmc` adds no catalogue rows unless it is given `--with-catalogue`.
- Even then, it never re-adds a type, subtype or item that exists retired (`inactive = 1`), and never one under a retired umbrella. Instead it lists each such row as `skip: retired on this desk`.
- A test will build the 2 Oct shape and assert that the preview is a single line.

### 8.2 Ethel: closed, and a correction to the Calendar/Sales question

Both of my causes are withdrawn on your measurements: she signs in only by Windows, holds the default TECHNICIAN role, and Dada's screenshot shows the full staff menu. There is no fault.

On Calendar and Sales: **there is no CALENDAR or SALES module.** Calendar and Sales are not missing for anyone on TECHNICIAN (MEASURED from the code: `security.MODULES` and the menu gate in `templates.page`).
- **Calendar** sits under *Service Desk* and is gated by the **SCHEDULE** grant.
- **Sales** sits under *Companies* and is gated by the **FINANCE** grant.

TECHNICIAN holds SCHEDULE WRITE and FINANCE READ, so Ethel sees both: Calendar in the Service Desk menu, Sales in the Companies menu. Their being absent from `role_grant` is expected. Nothing for Dada to decide unless she wants Sales hidden from technicians, which would mean FINANCE NONE on that role.

### 8.3 Search cost: recorded, with a line to watch

Recorded as the baseline: 146 tickets and 1,691 `ticket_event` rows; ~37 ms worst case (no match, full scan); 17–29 ms on a match; all under the 140 ms debounce.

If the scan grows in line with the rows (INFERRED, not measured), it would reach the 140 ms debounce at roughly **6,000 `ticket_event` rows**. Please re-measure the same no-match term when the table passes **5,000 rows**. If the worst case is then over 100 ms, WS36 will add a full-text index as a schema step of its own.

### 8.4 Still Dada's eye

The same as always: anything behind the Windows sign-in. That means the §3 visual list, the pickers, the time and note windows moving, and the new menus. One more is coming. The next push is code only and rides the usual restart: dark mode gets the depth that light already has (raised cards, table header band, edged buttons), and its menus become solid.

### 8.5 `setup-pmc` is now safe, and it is still not a step (later on 6 Oct)

What §8.1 promised is built. `setup-pmc` adds **statuses only** unless `--with-catalogue` is passed. Even with that flag, it never re-adds an Area, Subtype or Item this desk has retired, nor a Subtype that sits under another Area here. Each such row prints as `skip: …`.

**Nothing to run.** On Hold is already in, so on this database a plain preview should print `nothing to add`. If you want to confirm the guard, both of these previews write nothing:

    .\Invoke-PsaSpine.ps1 -Spine "setup-pmc --actor dada.banal"
    .\Invoke-PsaSpine.ps1 -Spine "setup-pmc --with-catalogue --actor dada.banal"

- **Expected for the first:** `nothing to add: the pack is already there`.
- **Expected for the second:** only `skip:` lines (`skip: area Hospital systems (BizBox) is retired on this desk`, plus any moved Subtypes), and no `area:`, `subtype:`, `item:` or `pair:` lines.
- **If either prints an `area:`, `subtype:`, `item:` or `pair:` line**, do not apply. Paste it back.

The same push restores the hover glows that the depth pass had overridden. It is code only and rides the usual restart. Unit suite 767 OK, browser checks **77 of 77**, smoke 7 of 7.

### 8.6 Time entries (later on 6 Oct): code only, the usual restart

Thank you for Part 44: both `setup-pmc` previews wrote nothing, as intended.

Dada reported on PMC-000331 that saved time entries "were not saving anywhere". Two causes were fixed, both MEASURED in Chromium before the fix:

1. **Save could silently do nothing.** The Start and End boxes allowed only 5-minute steps, counted from the clock's start time, so an End such as 16:40 after a 16:27 start made the browser refuse the submit.
2. **A blank *Charged as* refused the Save and lost the typed notes.** On Dada's word this is no longer a dependency: blank now means **Included in monthly fee**. This supersedes the earlier "never assumed" rule. A refused Save now reopens the window with the notes kept.

The activity also gains a **Time** tab, and the Time card moves up under the Ticket card.

There is **no schema step**, and no existing `time_entry` row changes. Pull to the head that carries this section and restart PSA-Desk as usual.

Unit suite 768 OK, browser checks **80 of 80**, smoke 7 of 7.
