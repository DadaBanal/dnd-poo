# HANDOFF — Cloud Build → SQL01, WS36, 7 Oct 2026 (070)

**One more schema step, 070 (four new tables, two nullable columns), applied in the same sitting as 068 and 069, then the one restart.**

This extends `HANDOFF-cloud-sql01-WS36-20261007-projects-068.md`; it supersedes nothing in it. If 068 and 069 are not in yet, apply 068, then 069, then 070 in one transaction and restart once. If they are already in, apply 070 alone and restart.

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file.

---

## 1. What Dada asked for, and what is built

Dada, 7 Oct: "the project board isnt a service board … load each tab on its own page … it will be a hodge podge of tickets / you can convert a service ticket into a project ticket / you havent copied its entire setup".

1. **Project boards are kept apart from service boards** (code only).
   - The Service Board never shows a ticket from a PROJECT board.
   - Projects shows one card per project board: the board holds its projects, each project holds its tickets (Dada: "the project board holds the projects the projects hold the tickets").
   - Setup shows *Project boards* as a separate card.
   - A project with tickets on a service board shows a banner with **Move to the project board**. Every one of its tickets goes across with its number, notes, time and history.
2. **Converting a ticket** (code only).
   - The ticket's Project pod offers **Convert to project ticket**. The ticket goes onto the project's board as a Project ticket, its SLA clocks stop, and it lands in the phase picked.
   - A project ticket offers **Convert to service ticket** to go back.
   - The Work plan's **Add an existing ticket** converts in the same way.
3. **Each project tab is its own page**: `/project/<id>/<tab>`. The tabs are Work plan, Gantt, Tickets, Issues, Attachments, Team, Contacts, Recap, Time, Configurations, Audit trail and Finance, with the Project tab at `/project/<id>`. Billing is still left out.
4. **Project setup tables** (schema 070), under **Setup › Projects**:
   - project statuses, each with an indicator, default, closed, *No time* and inactive;
   - project types;
   - project roles;
   - **Issues** on each project.

## 2. The step: 070, then restart

**070 must be in before PSA-Desk starts on this head.** INFERRED from the code: every project page reads `project_status` and `project_role`. **Every time entry** also joins `project_status` in `board.may_book_effort`, to check the *No time* flag. Without 070, time entry would fail on every ticket. Treat this as blocking.

1. Pull.
2. Take a COPY_ONLY backup of `PMC_PSA`, unless the 068/069 backup was taken in this same sitting.
3. Stop `PSA-Desk`.
4. Apply 070 as you applied 066 to 069: as sysadmin, via pyodbc, in one transaction. Take the statements from `sqlserver/PMC_PSA_Spine_SqlServer.sql`, under `-- … (from schema/070_project_setup.sql)`. Each one is guarded:
   - `CREATE TABLE psa.[project_status]`
   - `CREATE TABLE psa.[project_type]`
   - `CREATE TABLE psa.[project_role]`
   - `CREATE TABLE psa.[project_issue]`, with an FK to `project`
   - `CREATE INDEX [ix_project_issue_project]`
   - `IF COL_LENGTH(N'psa.[project]', N'project_status_id') IS NULL ALTER TABLE … ADD … NULL`
   - the same guard for `project_type_id`
5. Verify:
   - `OBJECT_ID` is non-NULL for all four new tables.
   - `COL_LENGTH` is non-NULL for both new columns.
   - `SELECT COUNT(*) FROM psa.project` is unchanged, and `SELECT COUNT(*) FROM psa.project WHERE project_status_id IS NOT NULL` returns **0**. A NULL status id reads as the old `status` code.
6. Run `init`. It seeds into the empty setup tables only:
   - five project statuses, with the old codes as ids (PLANNED default, ACTIVE, ON_HOLD, DONE closed, CANCELLED closed), **none with No time**;
   - the six project roles;
   - one type, General.

   Then check:
   - `SELECT COUNT(*) FROM psa.project_status` returns **5**;
   - `SELECT COUNT(*) FROM psa.project_status WHERE no_time = 1` returns **0**.
   **If `init` cannot be run** (Part 46: the desk account is still shut to you), run these in the same transaction as step 4 instead. They are guarded, add rows only to empty tables, and are exactly what `init` would write (`projects.SEED_STATUSES`, `projects.ROLES`):

   ```sql
   IF NOT EXISTS (SELECT 1 FROM psa.project_status)
   INSERT INTO psa.project_status (status_id, name, indicator, is_default, is_closed, no_time, sort_order) VALUES
     (N'PLANNED', N'Planned', N'ON_TRACK', 1, 0, 0, 10), (N'ACTIVE', N'Active', N'ON_TRACK', 0, 0, 0, 20),
     (N'ON_HOLD', N'On hold', N'AT_RISK', 0, 0, 0, 30), (N'DONE', N'Done', N'ON_TRACK', 0, 1, 0, 40),
     (N'CANCELLED', N'Cancelled', N'ON_TRACK', 0, 1, 0, 50);
   IF NOT EXISTS (SELECT 1 FROM psa.project_role)
   INSERT INTO psa.project_role (role_id, name, sort_order) VALUES
     (N'PROJECT_MANAGER', N'Project manager', 10), (N'TEAM_LEAD', N'Team lead', 20), (N'TEAM_MEMBER', N'Team member', 30),
     (N'ENGINEER', N'Engineer', 40), (N'CONSULTANT', N'Consultant', 50), (N'STAKEHOLDER', N'Stakeholder', 60);
   IF NOT EXISTS (SELECT 1 FROM psa.project_type)
   INSERT INTO psa.project_type (type_id, name, is_default) VALUES (N'GENERAL', N'General', 1);
   ```

7. Start `PSA-Desk`. Expect `:8085` to answer 401, go down, then answer 401 again.

**Nothing live changes meaning.** No ticket moves on its own. A project still on IT Help keeps its tickets there until someone presses *Move to the project board*. Until then, those tickets stay on the Service Board as they are today. Time is held only on a status an administrator marks *No time*.

## 3. What to look for (Dada's eye)

- **Service Board**: no ticket from IT Projects. On **Projects**, the IT Projects card holds its projects, each with its tickets under it.
- A project's **tab bar**: each tab opens a page of its own, and the tab is underlined.
- On a project still on a service board:
  - the red banner, with **Move to the project board**;
  - after the move, the project sits in the IT Projects card with its tickets, and they are gone from the Service Board.
- A service ticket's **Project** pod:
  - *project › phase* and **Convert to project ticket**;
  - after converting, **Convert to service ticket**.
- **Setup › Projects**: Project statuses (indicator, default, closed, no time, inactive), Project types, Project roles.
- **Issues** tab: raise an issue, close it or **Make a ticket**.
- A person with no service board, but on a project board, lands on Projects.

## 4. Evidence on this head

| | |
|---|---|
| Unit suite | **772 OK**, 1 skipped. New: `test_project_boards_are_apart_tickets_convert_and_projects_have_setup_tables`. It covers the Service Board exclusion, convert there and back with clocks stopped, a reader refused, move-to-project-board, every tab answering 200 and an unknown tab 404, issues to a ticket, Setup › Projects for a sysadmin only, a *No time* status holding time, indicator-driven health, and seeds without No time. The 068/069 tests now read the tabbed pages. |
| Browser checks | **99 of 99**. New: each tab is a link and opens marked; project tickets are absent from the Service Board and present under their project in the project board's card; an issue is raised; the pod offers Convert; Setup › Projects lists the statuses. |
| Drift gate | In step. 070 is in the port. |
| Smoke | 7 of 7. |
| Not run here | 070 against SQL Server. The `sql-server` CI job runs it on push. |
