-- 080 — three screens in the reference PSA's shape (Dada, 13 Oct 2026):
--
--   "i need to revamp tasks and configurations to look like the connectwise
--   build and also i want you to make sure that the mms module is mirrored in
--   a spearate procurement module on connectwise where it will be easier for
--   them to do edits and adds on the bizbox system and easier for them to do
--   multiple edits as well"
--
-- Each part confirmed before building (the full grid; list and detail both;
-- a Procurement menu of its own; approve on the desk, push by a BizBox
-- procedure). Every column added is NULL-able: a migration invents no data.
PRAGMA foreign_keys = ON;

-- 1. A ticket's tasks as the reference PSA's grid: Done, Priority, Task,
--    Notes, Resolution, Schedule. A task scheduled to a member is a visit on
--    the ticket (ticket_schedule), and the task remembers which.
ALTER TABLE ticket_task ADD COLUMN priority INTEGER;
ALTER TABLE ticket_task ADD COLUMN notes TEXT;
ALTER TABLE ticket_task ADD COLUMN resolution TEXT;
ALTER TABLE ticket_task ADD COLUMN schedule_id INTEGER REFERENCES ticket_schedule(schedule_id);

-- 2. A configuration as the reference PSA keeps it: a tag number (the
--    hospital's asset tag, not the serial), who installed it, free notes, and
--    a parent (a monitor under its PC, a card under its server). One level or
--    many; a cycle is refused by the code.
ALTER TABLE configuration ADD COLUMN tag_number TEXT;
ALTER TABLE configuration ADD COLUMN installed_by TEXT;
ALTER TABLE configuration ADD COLUMN notes TEXT;
ALTER TABLE configuration ADD COLUMN parent_configuration_id TEXT REFERENCES configuration(configuration_id);
CREATE INDEX ix_configuration_parent ON configuration (parent_configuration_id);

-- 3. Changes to BizBox in batches. 043's ext_change is one field on one
--    record; a bulk edit on ticked rows, an edit of many cells saved at once,
--    or a new record (a purchase order with its lines, an item) is a batch:
--    one reason, one approval, one answer from BizBox. A batch is PENDING
--    (waiting for a person with Procurement WRITE, never the one who asked),
--    APPROVED (waiting for the push), then APPLIED, REJECTED or CANCELLED.
--    ADD carries the new record as JSON in payload; its one ext_change row
--    has field NEW and ext_ref NEW-<batch> until BizBox answers with its own
--    number. Nothing here reaches BizBox: the push (bizbox.push) hands each
--    change to the writer in force, which until SQL01 builds the procedure
--    is NoWriter.
CREATE TABLE ext_batch (
  batch_id      INTEGER PRIMARY KEY,
  source_id     TEXT NOT NULL REFERENCES ext_source(source_id),
  kind          TEXT NOT NULL CHECK (kind IN ('AGREEMENT', 'PRODUCT', 'PURCHASE_ORDER', 'INVOICE')),
  change_kind   TEXT NOT NULL CHECK (change_kind IN ('EDIT', 'ADD')),
  reason        TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'PENDING'
                  CHECK (status IN ('PENDING', 'APPROVED', 'APPLIED', 'REJECTED', 'CANCELLED')),
  payload       TEXT,
  requested_at  TEXT NOT NULL,
  requested_by  TEXT NOT NULL,
  approved_at   TEXT,
  approved_by   TEXT,
  decided_at    TEXT,
  decided_by    TEXT,
  answer        TEXT
);
CREATE INDEX ix_ext_batch_status ON ext_batch (source_id, status);
ALTER TABLE ext_change ADD COLUMN batch_id INTEGER REFERENCES ext_batch(batch_id);
CREATE INDEX ix_ext_change_batch ON ext_change (batch_id);
