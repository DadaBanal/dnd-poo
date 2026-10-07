# HANDOFF — Cloud Build → SQL01, WS36, 7 Oct 2026 (project access, survey live)

**No schema step. One data step (the survey), one read-only check (project teams), then the usual restart.**

This follows `HANDOFF-cloud-sql01-WS36-20261007-projects-070.md` and supersedes nothing. Apply 070 first if it is not in yet. This restart can be the same one.

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file.

---

## 1. What Dada asked for

Dada, 7 Oct: "make sure that they will only have access to projects they are a member of", and "can have the survey live". Dada confirmed before anything was built:

- **Project access, by team** (code only):
  - A project is seen by its **manager**, the people on its **Team**, and **administrators** (system administrators, or the Projects module at Admin).
  - Anyone else gets *No such project*: on Projects, the project page and every tab, its live refresh, the ticket's Project picker and search.
  - A project ticket opens for a non-member only when it is **assigned to them** (owner or resource).
  - Whoever creates or copies a project is put on its team.
  - Service tickets are untouched.
- **Survey live**: switch the satisfaction survey on for every service board. The code already asks it on the portal once a ticket closes. The closing email says "On the portal you can tell us how we did" with the link to the ticket.

## 2. Before the restart: who is on each project (read-only)

INFERRED from the code: after this restart, a project with no manager and nobody on its team is seen only by administrators. Check first, so nobody is surprised:

```sql
SELECT p.project_id, p.name, p.manager,
       (SELECT COUNT(*) FROM psa.project_member m WHERE m.project_id = p.project_id) AS team
FROM psa.project p
WHERE COALESCE(p.is_template, 0) = 0
ORDER BY team, p.project_id;
```

Report the rows with no manager and `team = 0`. Change nothing; an administrator adds the people on the project's Team tab.

## 3. The survey: on for every service board

1. Read first and report:

   ```sql
   SELECT board_id, display_name, kind, survey_enabled, notify_requester
   FROM psa.board ORDER BY board_id;
   ```

   - `survey_enabled` NULL already means on; 0 means a board switched it off.
   - `notify_requester` 0 means the board sends requesters no email. They see the survey only when they open the portal.
2. Then, in one transaction:

   ```sql
   UPDATE psa.board SET survey_enabled = 1
   WHERE COALESCE(kind, 'SERVICE') <> 'PROJECT' AND (survey_enabled IS NULL OR survey_enabled = 0);
   ```

3. Verify that this returns **0**:

   ```sql
   SELECT COUNT(*) FROM psa.board
   WHERE COALESCE(kind, 'SERVICE') <> 'PROJECT' AND COALESCE(survey_enabled, 0) <> 1;
   ```

`notify_requester` is **not** changed here. Turning on requester emails is a separate decision for Dada, per board.

## 4. Restart

Stop `PSA-Desk`, start it. Expect `:8085` to answer 401, go down, then answer 401 again.

## 5. Evidence on this head

| | |
|---|---|
| Unit suite | **774 OK**, 1 skipped; browser checks 104 of 104; smoke 7 of 7. New: `test_only_a_projects_members_see_it_and_its_tickets`. It covers a board worker off the team refused on the project, its tabs, live stamp, list, notes, ticket pages, ticket forms and search; a resource opening only their own ticket; a team member seeing all of it; an administrator seeing everything; a service ticket untouched; the creator on their new project. |
| Not run here | Against SQL Server; the `sql-server` CI job runs on push. |
