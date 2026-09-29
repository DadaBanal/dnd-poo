-- 041 — projects, in the reference PSA's shape.
--
-- A project has a manager, dates, a status and budget hours. Its work breakdown
-- is phases, which may nest one inside another and may wait on one another
-- (predecessors), each with its own dates and budget. Tickets are the work:
-- a ticket is linked to one project and, optionally, one phase, and its time
-- entries are the project's actual hours. Nothing about a ticket changes when
-- it is linked, so its board, clocks and SLA stay its own; a project board
-- (022, kind PROJECT) is where project tickets usually live.
PRAGMA foreign_keys = ON;

CREATE TABLE project (
  project_id    TEXT PRIMARY KEY,                       -- 'PRJ-0001'
  name          TEXT NOT NULL,
  board_id      TEXT REFERENCES board(board_id),
  manager       TEXT,
  status        TEXT NOT NULL DEFAULT 'PLANNED'
                  CHECK (status IN ('PLANNED', 'ACTIVE', 'ON_HOLD', 'DONE', 'CANCELLED')),
  starts_on     TEXT,
  ends_on       TEXT,
  budget_hours  REAL,
  description   TEXT,
  created_at    TEXT NOT NULL,
  created_by    TEXT NOT NULL
);

CREATE TABLE project_phase (
  phase_id      INTEGER PRIMARY KEY,
  project_id    TEXT NOT NULL REFERENCES project(project_id),
  parent_id     INTEGER REFERENCES project_phase(phase_id),
  name          TEXT NOT NULL,
  sort_order    INTEGER NOT NULL DEFAULT 0,
  starts_on     TEXT,
  ends_on       TEXT,
  budget_hours  REAL,
  status        TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'DONE')),
  created_at    TEXT NOT NULL
);
CREATE INDEX ix_project_phase_project ON project_phase (project_id);

CREATE TABLE phase_dependency (
  phase_id    INTEGER NOT NULL REFERENCES project_phase(phase_id),
  depends_on  INTEGER NOT NULL REFERENCES project_phase(phase_id),
  PRIMARY KEY (phase_id, depends_on),
  CHECK (phase_id <> depends_on)
);

CREATE TABLE project_ticket (
  work_item_id  TEXT PRIMARY KEY REFERENCES ticket(work_item_id),
  project_id    TEXT NOT NULL REFERENCES project(project_id),
  phase_id      INTEGER REFERENCES project_phase(phase_id),
  linked_at     TEXT NOT NULL,
  linked_by     TEXT NOT NULL
);
CREATE INDEX ix_project_ticket_project ON project_ticket (project_id);
