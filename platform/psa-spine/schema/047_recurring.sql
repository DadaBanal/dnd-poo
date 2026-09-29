-- 047 — recurring tickets: a board's template raised on a cadence.
--
-- Preventive maintenance is a ticket that must exist on a day nobody
-- remembered: the monthly analyser check, the quarterly printer care, the
-- yearly UPS test. A recurrence names a template (026), a cadence and the next
-- due day; the minute runner (psaspine run-rules) raises the ticket through
-- the one door every ticket uses, with the template's tasks, an owner or the
-- board's queue, the machine it concerns, and a line on the ticket saying
-- which recurrence raised it. A runner that was down raises the ticket once
-- and moves the due day past today, never once per missed period.
PRAGMA foreign_keys = ON;

CREATE TABLE recurrence (
  recurrence_id    INTEGER PRIMARY KEY,
  name             TEXT NOT NULL,
  board_id         TEXT NOT NULL REFERENCES board(board_id),
  template_id      TEXT NOT NULL REFERENCES ticket_template(template_id),
  cadence          TEXT NOT NULL CHECK (cadence IN ('DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'YEARLY')),
  every_n          INTEGER NOT NULL DEFAULT 1,
  anchor_day       INTEGER NOT NULL,                     -- the day of the month the series was set on
  next_due_on      TEXT NOT NULL,                        -- YYYY-MM-DD
  owner            TEXT,                                 -- a board member, or NULL for the board's queue
  entity_id        TEXT NOT NULL REFERENCES entity(entity_id),
  contact_id       TEXT REFERENCES contact(contact_id),
  configuration_id TEXT REFERENCES configuration(configuration_id),
  impact           TEXT NOT NULL DEFAULT 'I3' CHECK (impact IN ('I1', 'I2', 'I3')),
  urgency          TEXT NOT NULL DEFAULT 'U3' CHECK (urgency IN ('U1', 'U2', 'U3')),
  active           INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  last_raised_at   TEXT,
  last_work_item_id TEXT REFERENCES ticket(work_item_id),
  created_at       TEXT NOT NULL,
  created_by       TEXT NOT NULL
);
CREATE INDEX ix_recurrence_due ON recurrence (active, next_due_on);

-- The recurrence a ticket was raised by, so the ticket says so and a report can group them.
ALTER TABLE ticket ADD COLUMN recurrence_id INTEGER REFERENCES recurrence(recurrence_id);
