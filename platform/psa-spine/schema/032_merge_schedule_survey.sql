-- 032 — merged duplicates, scheduled visits, and the satisfaction survey.
--
-- merged_into: Dada PSA's Merge. The duplicate is closed on its own board
-- and says where its words went; the row stays, so its number still answers.
-- ticket_schedule: a visit, as Dada PSA's schedule entry -- who, when, on
-- which ticket -- so Dispatch can show a day. survey_response: one answer per
-- ticket from its requester after it closes, one to five and a sentence,
-- scanned for patient details like every other requester text.
PRAGMA foreign_keys = ON;

ALTER TABLE ticket ADD COLUMN merged_into TEXT REFERENCES ticket(work_item_id);
CREATE INDEX ix_ticket_merged ON ticket (merged_into);

CREATE TABLE ticket_schedule (
  schedule_id  INTEGER PRIMARY KEY,
  work_item_id TEXT NOT NULL REFERENCES ticket(work_item_id),
  member       TEXT NOT NULL,
  starts_at    TEXT NOT NULL,
  ends_at      TEXT NOT NULL,
  note         TEXT,
  created_at   TEXT NOT NULL,
  created_by   TEXT NOT NULL,
  CHECK (ends_at > starts_at)
);
CREATE INDEX ix_ticket_schedule_day ON ticket_schedule (starts_at);
CREATE INDEX ix_ticket_schedule_ticket ON ticket_schedule (work_item_id);

CREATE TABLE survey_response (
  work_item_id TEXT PRIMARY KEY REFERENCES ticket(work_item_id),
  score        INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
  comment      TEXT,
  answered_by  TEXT NOT NULL,
  answered_at  TEXT NOT NULL
);
