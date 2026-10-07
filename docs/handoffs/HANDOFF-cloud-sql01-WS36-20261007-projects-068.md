# HANDOFF — Cloud Build → SQL01, WS36, 7 Oct 2026

**One schema step (068: two new tables, two nullable columns), then the usual restart.**

Supersedes nothing. It follows `…-20261006-resources-cancelled-067.md`, whose §8.6 is still pending a restart; this restart covers both.

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file.

---

## 1. What Dada asked for, and what is built

1. **Time entries** (code only), on PMC-000336: 09:30–11:30 with 2 in Actual hours was refused "not both".
   - Start and End now decide, and Actual hours is read from them.
   - A Start with Actual hours works out its End.
   - The window fills Actual hours as Start and End are typed.
2. **Projects in the reference PSA's shape** (schema 068). These were checked against ConnectWise's own Project documentation (MEASURED):
   - a project **team**: member, project role, dates, planned hours;
   - **tickets created inside the project**, from a phase or from the top of the project page;
   - a **work plan** showing each phase's tickets, and a **ticket board** by status;
   - project **notes** and a **company** on the project;
   - a **projects list** that shows each project's open tickets and refreshes itself, with a *My projects* filter.

Dada also asked that it break nothing: 068 adds and never alters. Unit suite 770 OK, browser checks **86 of 86**, smoke 7 of 7, drift gate in step.

## 2. The step: 068, then restart

**068 must be in before PSA-Desk starts on this head.** INFERRED from the code: the project pages, the projects list and their live refresh all read `project_member`, `project_note`, `project_ticket.budget_hours` and `project.entity_id`. Without them, those pages would fail. Ticket pages and the board do not read them.

1. Pull.
2. Take a COPY_ONLY backup of `PMC_PSA`.
3. Stop `PSA-Desk`.
4. Apply 068 the way you applied 066 and 067: as sysadmin, via pyodbc, in one transaction. Take the statements from `sqlserver/PMC_PSA_Spine_SqlServer.sql`; each one is guarded, so a re-run adds nothing:
   - `IF OBJECT_ID(N'psa.[project_member]', N'U') IS NULL … CREATE TABLE psa.[project_member]`, with primary key (project_id, member) and FK to `project`;
   - `CREATE INDEX [ix_project_member_member]`;
   - `IF OBJECT_ID(N'psa.[project_note]', N'U') IS NULL … CREATE TABLE psa.[project_note]`, with FK to `project`;
   - `CREATE INDEX [ix_project_note_project]`;
   - `IF COL_LENGTH(N'psa.[project_ticket]', N'budget_hours') IS NULL ALTER TABLE … ADD [budget_hours] DECIMAL(9,2) NULL`;
   - `IF COL_LENGTH(N'psa.[project]', N'entity_id') IS NULL ALTER TABLE … ADD [entity_id] NVARCHAR(64) NULL`.
5. Verify all four:
   - `SELECT OBJECT_ID(N'psa.project_member'), OBJECT_ID(N'psa.project_note')` returns two non-NULL values.
   - `SELECT COL_LENGTH(N'psa.project_ticket', N'budget_hours'), COL_LENGTH(N'psa.project', N'entity_id')` returns two non-NULL values.
   - `SELECT COUNT(*) FROM psa.project_member` returns **0**. Projects made before today have no team rows. Their manager joins the team the next time the manager is changed, or anyone can add people on the page.
   - `SELECT COUNT(*) FROM psa.project_ticket` is **the same as before**. No existing row changes.
6. Run `init`, then start `PSA-Desk`. Expect `:8085` to answer 401, go down, then answer 401 again.

## 3. What to look for (Dada's eye; nothing here can reach it)

- On a project:
  - the tiles across the top (Complete, Actual hours, Budget hours, Tickets, Actual start);
  - the tab bar;
  - **+ Ticket** on each phase, which opens *New project ticket* with that phase already picked;
  - the new ticket under its phase in the Work plan and on the Ticket board;
  - the **Team** card with its Add to the team form;
  - the **Notes** card.
- **Projects** list:
  - Company, Complete and Team columns;
  - "N open ticket(s)" under each project, opening to the tickets;
  - the *My projects* choice.
- **A project needs a board** before tickets can be opened inside it. A project with none says so in the window, and the board can be set on the project's own form.

## 4. Evidence on this head

| | |
|---|---|
| Unit suite | **770 OK**, 1 skipped. New: `test_a_project_has_a_team_and_opens_its_own_tickets`, which covers the team, a ticket opened inside, the reader refused, the list, *Mine*, and the live stamp moving. Also `test_start_and_end_decide_and_a_start_with_hours_finds_its_end`. |
| Browser checks | **86 of 86**. New: each phase offers + Ticket; it opens with that phase picked; the ticket sits under its phase and on the board; a member is added with a role and hours; the list shows each project's open tickets. |
| Drift gate | In step. 068 is in the port (137 tables). |
| Smoke | 7 of 7. |
| Not run here | 068 against SQL Server. The `sql-server` CI job runs it on push. |
