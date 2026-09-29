-- 046 — timesheets and time approval.
--
-- The uplift claim (§5.2) rests on time entries, and a finance function
-- reading them will ask who approved them. So every time entry belongs to
-- one timesheet: the week (Monday to Sunday) of the day it was worked, by the
-- person who performed it. A sheet is OPEN while the week is being written,
-- SUBMITTED when that person says it is complete, APPROVED or REJECTED by a
-- time administrator who is not that person, and reopened only with a note.
-- A submitted or approved week takes no new entries: the sheet is the record,
-- and the reference PSA's timesheet works the same way. Every decision is
-- appended, never edited.
PRAGMA foreign_keys = ON;

CREATE TABLE timesheet (
  timesheet_id  INTEGER PRIMARY KEY,
  member        TEXT NOT NULL,                          -- time_entry.performed_by, as spelt there
  week_start    TEXT NOT NULL,                          -- the Monday, YYYY-MM-DD
  status        TEXT NOT NULL DEFAULT 'OPEN'
                  CHECK (status IN ('OPEN', 'SUBMITTED', 'APPROVED', 'REJECTED')),
  created_at    TEXT NOT NULL,
  submitted_at  TEXT,
  submitted_by  TEXT,
  decided_at    TEXT,
  decided_by    TEXT,
  note          TEXT,                                   -- the decision's reason, or why it was reopened
  UNIQUE (member, week_start)
);

-- Append-only: submit, approve, reject, reopen, each with who and when.
CREATE TABLE timesheet_event (
  event_id      INTEGER PRIMARY KEY,
  timesheet_id  INTEGER NOT NULL REFERENCES timesheet(timesheet_id),
  occurred_at   TEXT NOT NULL,
  actor         TEXT NOT NULL,
  action        TEXT NOT NULL CHECK (action IN ('SUBMIT', 'APPROVE', 'REJECT', 'REOPEN')),
  note          TEXT
);
CREATE INDEX ix_timesheet_event_sheet ON timesheet_event (timesheet_id);

-- Hours a week a person is expected to record, for the utilisation figure.
-- Unset means the desk's default (40). Not the capacity declaration of 003,
-- which is the client's denominator for the uplift; this is the team's own.
CREATE TABLE member_capacity (
  member         TEXT PRIMARY KEY,
  hours_per_week REAL NOT NULL,
  set_at         TEXT NOT NULL,
  set_by         TEXT NOT NULL
);

-- Which sheet an entry sits on. Stamped when the entry is written into an
-- open week, and on every entry of the week when it is submitted, so rows
-- that predate this step join their sheet the first time it is submitted.
ALTER TABLE time_entry ADD COLUMN timesheet_id INTEGER REFERENCES timesheet(timesheet_id);
CREATE INDEX ix_time_entry_sheet ON time_entry (timesheet_id);

-- The module vocabulary belongs to the code (security.MODULES), not to a
-- CHECK. 040's role_permission listed five modules in its CHECK, so the sixth
-- (Timesheets) could not be written into it on either store: OR IGNORE
-- swallowed the refusal and every role silently had no level. role_grant takes
-- its place: the same key and levels, no list of modules. The rows already in
-- role_permission are read across by the desk the first time a role is
-- looked up (security.ensure_roles). role_permission stays, superseded and
-- unread, because the port never drops a table on a live database.
CREATE TABLE role_grant (
  role_id  TEXT NOT NULL REFERENCES security_role(role_id),
  module   TEXT NOT NULL,
  level    TEXT NOT NULL CHECK (level IN ('NONE', 'READ', 'WRITE', 'ADMIN')),
  PRIMARY KEY (role_id, module)
);
