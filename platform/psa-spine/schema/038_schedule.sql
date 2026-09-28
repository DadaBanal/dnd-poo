-- 038 — scheduling, in the reference PSA's shape.
--
-- Its ScheduleEntry (the record's extracted model, VERIFIED 9 Sep 2026 from its
-- published OpenAPI schema) carries a member, dateStart and dateEnd, a status
-- (the ScheduleStatus setup table: Firm, Tentative, …), a where (the
-- ServiceLocation setup table: On-site, Remote, In-house), ownerFlag (the lead
-- on a ticket several people visit), doneFlag and closeDate, acknowledgedFlag
-- and acknowledgedDate, and allowScheduleConflictsFlag. Its schedule also holds
-- entries that are not tickets: meetings, activities and days off, so a member
-- on leave is not dispatched.
--
-- 032 gave a ticket its visits. This adds the rest: the two setup tables, the
-- flags on a visit, and `schedule_block` for what is not a ticket. What is not
-- copied: reminders (a reminder is an email the desk would send, and the
-- outbox sends only what a board has switched on) and recurring spans (a
-- hospital desk books visits one at a time; a recurring meeting is a Teams
-- invite, not a ticket).
--
-- Added columns are NULL-able by the port's rule; NULL reads as the default.
PRAGMA foreign_keys = ON;

CREATE TABLE schedule_status (
  status_id   TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  is_default  INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
  inactive    INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1)),
  sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE service_location (
  location_id TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  inactive    INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1))
);

ALTER TABLE ticket_schedule ADD COLUMN status_id TEXT REFERENCES schedule_status(status_id);
ALTER TABLE ticket_schedule ADD COLUMN location_id TEXT REFERENCES service_location(location_id);
ALTER TABLE ticket_schedule ADD COLUMN is_lead INTEGER DEFAULT 0 CHECK (is_lead IN (0, 1));
ALTER TABLE ticket_schedule ADD COLUMN conflict_allowed INTEGER DEFAULT 0 CHECK (conflict_allowed IN (0, 1));
ALTER TABLE ticket_schedule ADD COLUMN done_at TEXT;
ALTER TABLE ticket_schedule ADD COLUMN acknowledged_at TEXT;

-- What is on a person's schedule that is not a ticket. TIME_OFF blocks a
-- visit outright; a MEETING or an ACTIVITY is a clash like any other, which
-- "allow the double booking" can override.
CREATE TABLE schedule_block (
  block_id    INTEGER PRIMARY KEY,
  member      TEXT NOT NULL,
  kind        TEXT NOT NULL CHECK (kind IN ('MEETING', 'ACTIVITY', 'TIME_OFF')),
  name        TEXT NOT NULL,
  starts_at   TEXT NOT NULL,
  ends_at     TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  created_by  TEXT NOT NULL,
  CHECK (ends_at > starts_at)
);
CREATE INDEX ix_schedule_block_day ON schedule_block (starts_at);
CREATE INDEX ix_schedule_block_member ON schedule_block (member);
