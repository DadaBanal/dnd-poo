-- 035 — three board settings the reference PSA has and a technician expects.
--
-- Board.workRole and Board.workType (the record's extracted model): the work
-- role and type a time entry on this board starts with, before the member's
-- own choice. Board.sendToResourceFlag: the owner is emailed when a ticket is
-- assigned to them. All three are NULL-able by the port's rule; unset means
-- the desk's default (the first role and type in Setup › Time; no owner mail).
PRAGMA foreign_keys = ON;

ALTER TABLE board ADD COLUMN default_work_role_id TEXT REFERENCES work_role(work_role_id);
ALTER TABLE board ADD COLUMN default_work_type_id TEXT REFERENCES work_type(work_type_id);
ALTER TABLE board ADD COLUMN notify_owner INTEGER CHECK (notify_owner IN (0, 1));
