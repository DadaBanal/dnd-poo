-- 033 — time entry, as Dada PSA records it.
--
-- Dada PSA's TimeEntry (the reference PSA's, in the record's extracted model,
-- VERIFIED 9 Sep 2026 from its published OpenAPI schema): timeStart and timeEnd, or
-- actualHours; hoursDeduct; a workRole and a workType; a billableOption of
-- Billable, DoNotBill, NoCharge or NoDefault; notes carrying the Internal /
-- Discussion / Resolution flags; a status that starts Open. A technician who
-- has used the reference PSA expects that form, so the desk takes it.
--
-- The spine's own numbers stay. band_hours is now DERIVED: the actual hours,
-- rounded up to the record's band (0.5, 2, 4, 8, 20), because §5.2's capacity
-- arithmetic is in bands and an uplift claim is defended in bands. Nothing that
-- read band_hours changes. The charge method (the commercial classification,
-- which Dada PSA leaves to the agreement) is still chosen on every entry.
PRAGMA foreign_keys = ON;

-- Dada PSA's WorkRole and WorkType, as the desk needs them: a name, whether
-- it is still offered, and for a type the bill default Dada PSA gives it
-- (WorkType.billTime: Billable, DoNotBill, NoCharge). Setup › Time edits both.
CREATE TABLE work_role (
  work_role_id TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  inactive     INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1)),
  sort_order   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE work_type (
  work_type_id TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  bill_time    TEXT NOT NULL DEFAULT 'BILLABLE'
                 CHECK (bill_time IN ('BILLABLE', 'DO_NOT_BILL', 'NO_CHARGE')),
  inactive     INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1)),
  sort_order   INTEGER NOT NULL DEFAULT 0
);

ALTER TABLE time_entry ADD COLUMN time_start TEXT;
ALTER TABLE time_entry ADD COLUMN time_end TEXT;
-- Added columns are NULL-able by the port's rule (a migration invents no data);
-- the engine writes every one of them on every new row.
ALTER TABLE time_entry ADD COLUMN hours_deduct REAL DEFAULT 0;
ALTER TABLE time_entry ADD COLUMN actual_hours REAL;
ALTER TABLE time_entry ADD COLUMN work_role_id TEXT REFERENCES work_role(work_role_id);
ALTER TABLE time_entry ADD COLUMN work_type_id TEXT REFERENCES work_type(work_type_id);
ALTER TABLE time_entry ADD COLUMN billable_option TEXT DEFAULT 'NO_DEFAULT'
  CHECK (billable_option IN ('BILLABLE', 'DO_NOT_BILL', 'NO_CHARGE', 'NO_DEFAULT'));
-- The note the entry was written with, when it was (Dada PSA's time entry
-- carries its notes; here the note is the ticket_event and this points at it).
ALTER TABLE time_entry ADD COLUMN ticket_event_id INTEGER REFERENCES ticket_event(ticket_event_id);
-- Dada PSA's TimeEntry.status, the part of it the desk has a use for.
ALTER TABLE time_entry ADD COLUMN entry_status TEXT DEFAULT 'OPEN'
  CHECK (entry_status IN ('OPEN', 'READY_TO_BILL', 'BILLED', 'WRITTEN_OFF', 'BILLED_AGREEMENT'));

CREATE INDEX ix_time_entry_ticket ON time_entry (work_item_id, worked_on);
