-- 069 — projects, the rest of the reference PSA's (Dada, 7 Oct 2026: "add
-- those missing ... except for the billing bit").
--
-- Additive only: three new tables and four nullable columns. Nothing that
-- exists changes; a NULL in a new column means what the project meant before.
--
-- * project_contact: the people a project is for or answers to (the reference
--   PSA's Contacts tab), from the desk's contacts.
-- * project_ticket_dependency: a project ticket that waits on another
--   (predecessor). Time is not booked on a ticket while its predecessor is open,
--   as the reference PSA blocks it.
-- * project_plan_item: a template's planned tickets. A template is a project
--   marked is_template; what it plans are not tickets until a project is made
--   from it, so they never sit on a board.
-- * project.is_template: 1 for a template.
-- * project.health: On track, At risk, High risk or Off track, as set by a
--   person; NULL leaves the desk's own reading (budget and dates) in charge.
-- * project_ticket.starts_on / due_on: a project ticket's estimated start and
--   required date, which the Gantt draws.
PRAGMA foreign_keys = ON;

CREATE TABLE project_contact (
  project_id    TEXT NOT NULL REFERENCES project(project_id),
  contact_id    TEXT NOT NULL REFERENCES contact(contact_id),
  role          TEXT,
  added_at      TEXT NOT NULL,
  added_by      TEXT NOT NULL,
  PRIMARY KEY (project_id, contact_id)
);

CREATE TABLE project_ticket_dependency (
  work_item_id  TEXT NOT NULL REFERENCES project_ticket(work_item_id),
  depends_on    TEXT NOT NULL REFERENCES project_ticket(work_item_id),
  PRIMARY KEY (work_item_id, depends_on),
  CHECK (work_item_id <> depends_on)
);

CREATE TABLE project_plan_item (
  item_id       INTEGER PRIMARY KEY,
  project_id    TEXT NOT NULL REFERENCES project(project_id),
  phase_id      INTEGER REFERENCES project_phase(phase_id),
  summary       TEXT NOT NULL,
  budget_hours  REAL,
  sort_order    INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL
);
CREATE INDEX ix_project_plan_item_project ON project_plan_item (project_id);

ALTER TABLE project ADD COLUMN is_template INTEGER;
ALTER TABLE project ADD COLUMN health TEXT;
ALTER TABLE project_ticket ADD COLUMN starts_on TEXT;
ALTER TABLE project_ticket ADD COLUMN due_on TEXT;
