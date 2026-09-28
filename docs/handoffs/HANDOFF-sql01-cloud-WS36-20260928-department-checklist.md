# HANDOFF-sql01-cloud-WS36-20260928 — Setup: a department × board checklist

| Field | |
|---|---|
| To | Cloud (WS36) |
| From | SQL01 |
| Workstream | WS36 |
| Bucket | A checklist in the desk's Setup where a system administrator ticks which departments may send requests to which boards. The Employee Portal door and *My requests* obey it, replacing the `PSA_EMPLOYEE_PORTAL_DEPARTMENTS` setting. |
| Read first | This file; `HANDOFF-sql01-cloud-WS36-20260928-portal-link.md` and `…-portal-door-fixes.md`; `psaspine/web/sso.py`, `views/portal.py`, `views/admin.py`. |
| Do | Build the page, the table and the rules below, with tests; add the host steps to the runbook. |
| Do NOT decide | Which departments get which boards: Dada ticks them. The first department still waits on him. |
| Fence | Hostnames only; no people, no credentials. Labels as usual. |
| Done means | The page on desk.pmcne.ph Setup; the door and the raise form follow it; tests; the runbook says how the department list is loaded. |
| Written | 2026-09-28, +08:00 |

## Decided

Dada, verbatim, 28 Sep: *"can i have a checklist on the main admin menu or setup menu of the psa or
desk.pmcne.ph to check which department should have access to which board"*. Earlier, the same day: *"dont do it
help as the tickets may be for other departments"*.

What "access" means here (INFERRED from the desk's own rule; SQL01 will confirm with Dada if it reads otherwise):
a department's staff are **requesters**. A tick lets them **send requests to** that board. It never makes them
members: they do not see the board or its tickets. Board membership (READ/WORK/ADMIN) stays per person, for
fulfillers.

## The page

`Setup › Departments` on desk.pmcne.ph. **System administrator only**, like the other cross-board cards. Every
change is audited.

- **A grid.** Rows are departments; columns are the live service boards (not Unrouted, which is where anything
  unticked lands). Each cell is a checkbox.
- **Row and column controls:** "all boards" per row and "all departments" per column, and a filter box over the
  department names, because there are 52 (MEASURED from payroll today).
- **One Save for the whole grid.** Audit what changed, as "Ward A: + IT Help, − Maintenance", not a row per
  cell.
- **An "Open for My requests" column** per department, derived: on if at least one board is ticked. It shows
  Dada at a glance who the portal door lets in.

## Where the department list comes from

The desk holds no department list today, and the desk's SQL login should not read `PMC_Apps`. So:

- A `department` table, filled by a CLI command (for example
  `psaspine import-departments <db> <csv>`, where the CSV has one column, `Department`). SQL01 produces the CSV
  from payroll: the 52 distinct `payroll.Employee.Department` names, read-only, no people.
- **Re-running it adds new names and never deletes one.** A name that has gone from payroll is marked retired and
  its ticks are kept, like a retired status.
- The page also allows **"Add a department"** by hand, for a department payroll does not have yet.
- Names are **exact**, case included: the door matches on the `Department` string the bridge returns.

## What obeys it

1. **The Employee Portal door** (`POST /sso/portal`): the pilot gate becomes "the employee's Department has at
   least one ticked board". It replaces `PSA_EMPLOYEE_PORTAL_DEPARTMENTS`. Keep the env var only as a
   migration: if it is set and the table is empty, honour it, and say so on the page.
   - Record the department on the session (`user.department`), so the raise form can use it.
   - A refusal still says "My requests is not open for your department yet" and is audited with the department
     name.
2. **The raise form on `/my`:** a "Who is this for?" choice listing the ticked boards by name. The ticket lands
   **on that board**, source Portal.
   - If only one board is ticked, there's no choice to make; say where it goes.
   - If none is ticked, the person should not be on the portal door at all.
   - For a Windows-door requester, the department comes from the AD contact import (`contact.department`, the AD
     `department` attribute) when present. When unknown, the ticket lands on Unrouted, exactly as today.
3. **Dispatch** still sees and routes everything on Unrouted, unchanged.

## Tests

- The grid saves, audits the change, and survives re-import.
- A retired department keeps its ticks.
- The door lets in a department with a tick and refuses one without.
- The raise form lists only ticked boards, and a ticket lands on the chosen board.
- A requester can never post to an unticked board (check it server-side, not only in the form).
- The env var fallback.
- A non-sysadmin gets no page.

## Reply

**Cloud, 2026-09-28. BUILT at the head this Reply arrives with.**

- **Tables (034):** `department` (name is the key, exact, case included; `source` PAYROLL or MANUAL; `retired`,
  never deleted) and `department_board` (one row per tick, who and when). In the T-SQL port.
- **The list:** `psaspine import-departments <db> <csv>`, one column `Department`; a re-run adds new names, marks
  names gone from payroll retired (ticks kept), restores a name that comes back, and leaves a by-hand name alone.
  Audited `DEPARTMENT_IMPORT` with the counts. Setup › Departments also has *Add a department*.
- **The page:** `Setup › Departments`, system administrator only. Rows are departments (retired ones dimmed),
  columns the live service boards (never Unrouted), a filter box, "all boards" per row and "all departments" per
  column, an *My requests* column derived from the ticks (open / closed), and **one Save** for the grid. A
  filtered view still submits the off-screen ticks, so a filtered Save unticks nothing it did not show. Audit:
  one `DEPARTMENT_BOARDS` row per Save, "Ward A: + IT Help, − Maintenance; …".
- **What obeys it:** the door's gate is "the employee's Department has at least one ticked board"; while no box
  is ticked, `PSA_EMPLOYEE_PORTAL_DEPARTMENTS` is honoured and the page shows a banner saying so. The department
  rides on the session (`dept`), from payroll for the portal door and from the AD contact's `department` for the
  Windows door. The raise form on `/my`: no tick → no question, Unrouted as today; one tick → "This goes to
  <board>"; several → "Who is this for?"; the chosen board is checked on the server, a board not ticked for the
  department is refused, and the ticket lands on the board with source Portal. Dispatch is unchanged.
- **Tests:** `DepartmentsTest` (import/retire/restore, the grid and its audit, the form and the server-side
  check, the Windows door's department) and `EmployeePortalDoorTest` (the grid decides once a box is ticked; the
  setting only before). The runbook's "Folded in from part 12" section has the host steps.

Not decided here: which departments get which boards (Dada ticks them).
