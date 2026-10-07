-- 068 — the rest of the reference PSA's project (Dada, 7 Oct 2026: "adding
-- project members have not yet added please review connectwise projects and
-- load everything that is missing ... tickets ... can be created inside the
-- project itself").
--
-- Additive only: two new tables and two nullable columns. Nothing that exists
-- changes, and every row already stored keeps its meaning.
--
-- * project_member: the project's team. A member, their role on this project,
--   the dates they are on it and the hours planned for them. The manager stays
--   project.manager; the team is everybody else (and may include the manager).
-- * project_note: the project's own notes, apart from any ticket's.
-- * project_ticket.budget_hours: a project ticket's budget, as the reference
--   PSA keeps one on each ticket in a phase.
-- * project.entity_id: the company the project is for.
PRAGMA foreign_keys = ON;

CREATE TABLE project_member (
  project_id    TEXT NOT NULL REFERENCES project(project_id),
  member        TEXT NOT NULL,
  project_role  TEXT NOT NULL DEFAULT 'TEAM_MEMBER',
  starts_on     TEXT,
  ends_on       TEXT,
  hours         REAL,
  added_at      TEXT NOT NULL,
  added_by      TEXT NOT NULL,
  PRIMARY KEY (project_id, member)
);
-- "My projects": every project a person is on, by person.
CREATE INDEX ix_project_member_member ON project_member (member);

CREATE TABLE project_note (
  note_id       INTEGER PRIMARY KEY,
  project_id    TEXT NOT NULL REFERENCES project(project_id),
  body          TEXT NOT NULL,
  written_at    TEXT NOT NULL,
  written_by    TEXT NOT NULL
);
CREATE INDEX ix_project_note_project ON project_note (project_id);

ALTER TABLE project_ticket ADD COLUMN budget_hours REAL;
ALTER TABLE project ADD COLUMN entity_id TEXT;
