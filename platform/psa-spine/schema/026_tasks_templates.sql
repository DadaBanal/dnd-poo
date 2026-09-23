-- 026 — ticket tasks and ticket templates, as ConnectWise keeps them.
--
-- A task is one line of a ticket's checklist ("create the AD account", "issue
-- the badge"). A template is a board's recipe for repeatable work: a summary, a
-- Type, a Subtype > Item, a description and its tasks. A fulfiller starts a
-- ticket from one, or applies one to a ticket already open, and a workflow rule
-- can apply one (008's APPLY_TEMPLATE action, now carried out).
--
-- ConnectWise: a ticket has a Tasks tab, and service templates carry Tasks
-- (VERIFIED 23 Sep 2026, the Ticket tasks sub-resource in ConnectWise's public
-- OpenAPI, Service.json v2026.13; visionary360.com/cw-manage-service-ticket-templates/).
PRAGMA foreign_keys = ON;

CREATE TABLE ticket_template (
  template_id       TEXT PRIMARY KEY,
  board_id          TEXT NOT NULL REFERENCES board(board_id),
  name              TEXT NOT NULL,
  summary           TEXT,
  record_type       TEXT CHECK (record_type IN
                      ('INCIDENT', 'SERVICE_REQUEST', 'PROBLEM', 'EVENT', 'CHANGE', 'PROJECT')),
  catalogue_item_id TEXT REFERENCES catalogue_item(catalogue_item_id),
  description       TEXT,
  inactive          INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1)),
  created_at        TEXT NOT NULL,
  created_by        TEXT NOT NULL
);

CREATE TABLE ticket_template_task (
  template_id TEXT NOT NULL REFERENCES ticket_template(template_id),
  sort_order  INTEGER NOT NULL,
  text        TEXT NOT NULL,
  PRIMARY KEY (template_id, sort_order)
);

-- A ticket's checklist. Done is a time and a person, never a bare flag: who
-- ticked it off is what an audit asks.
CREATE TABLE ticket_task (
  task_id      INTEGER PRIMARY KEY,
  work_item_id TEXT NOT NULL REFERENCES ticket(work_item_id),
  text         TEXT NOT NULL,
  sort_order   INTEGER NOT NULL DEFAULT 0,
  template_id  TEXT REFERENCES ticket_template(template_id),
  created_at   TEXT NOT NULL,
  created_by   TEXT NOT NULL,
  done_at      TEXT,
  done_by      TEXT,
  CHECK ((done_at IS NULL) = (done_by IS NULL))
);

CREATE INDEX ix_ticket_task_ticket ON ticket_task (work_item_id);

-- Which template a workflow rule's APPLY_TEMPLATE action applies.
ALTER TABLE workflow_action ADD COLUMN target_template_id TEXT
  REFERENCES ticket_template(template_id);
