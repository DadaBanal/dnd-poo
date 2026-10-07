-- 070 — the reference PSA's project setup tables, and project Issues (Dada,
-- 7 Oct 2026: "you havent copied its entire setup make sure to review and
-- check this is not a full copy").
--
-- Additive only: four new tables and two nullable columns.
--
-- * project_status: Setup › Project Statuses. A name, its status indicator
--   (On Track, At Risk, High Risk, Off Track: the project's health), whether it
--   is the default, closed, or allows no time entry, and inactive. The five
--   statuses a project could have before are seeded with their old codes as ids,
--   so project.status keeps meaning exactly what it did.
-- * project_type: Setup › Project Types (name, default, inactive).
-- * project_role: the project roles a team member can hold (Setup › Roles,
--   project category), editable instead of fixed.
-- * project_issue: a project's Issues tab: a problem raised against the
--   project, open or closed, that can be turned into a project ticket.
-- * project.project_status_id / project_type_id: NULL reads as the old status
--   code and no type.
PRAGMA foreign_keys = ON;

CREATE TABLE project_status (
  status_id     TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  indicator     TEXT NOT NULL DEFAULT 'ON_TRACK'
                  CHECK (indicator IN ('ON_TRACK', 'AT_RISK', 'HIGH_RISK', 'OFF_TRACK')),
  is_default    INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
  is_closed     INTEGER NOT NULL DEFAULT 0 CHECK (is_closed IN (0, 1)),
  no_time       INTEGER NOT NULL DEFAULT 0 CHECK (no_time IN (0, 1)),
  inactive      INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1)),
  sort_order    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE project_type (
  type_id       TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  is_default    INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
  inactive      INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1))
);

CREATE TABLE project_role (
  role_id       TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  inactive      INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1)),
  sort_order    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE project_issue (
  issue_id      INTEGER PRIMARY KEY,
  project_id    TEXT NOT NULL REFERENCES project(project_id),
  summary       TEXT NOT NULL,
  details       TEXT,
  status        TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED')),
  assigned_to   TEXT,
  raised_by     TEXT NOT NULL,
  raised_at     TEXT NOT NULL,
  work_item_id  TEXT REFERENCES ticket(work_item_id)
);
CREATE INDEX ix_project_issue_project ON project_issue (project_id);

ALTER TABLE project ADD COLUMN project_status_id TEXT;
ALTER TABLE project ADD COLUMN project_type_id TEXT;
