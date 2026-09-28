-- 024 — running the rules: test before activate, and somewhere for a page to go.
--
-- 008 made rules data; nothing ran them outside the walkthrough. psaspine.workflow
-- now runs them at every engine seam (create, status, note, owner, move) and on a
-- sweep for time-based events, and two things the reference PSA does are copied
-- (VERIFIED 23 Sep 2026, docs.connectwise.com/ConnectWise_Documentation/090/020/
-- 070/130, archived 2025-08-30):
--
--   * each event must be TESTED before its rule can be activated: the test shows
--     how many open tickets match now, so nobody switches on a rule that would
--     page on four hundred tickets;
--   * editing a rule deactivates it, so a changed rule is re-tested.
PRAGMA foreign_keys = ON;

ALTER TABLE workflow_event ADD COLUMN tested_at TEXT;
ALTER TABLE workflow_event ADD COLUMN tested_matches INTEGER;

-- A NOTIFY or ESCALATE action writes here. The desk sends no mail yet: this is
-- the queue a sender works through, and until one exists it is what the desk
-- shows as "who was told what". Nothing is lost for the lack of a sender.
CREATE TABLE notification (
  notification_id INTEGER PRIMARY KEY,
  work_item_id    TEXT REFERENCES ticket(work_item_id),
  event_id        TEXT REFERENCES workflow_event(event_id),
  recipient       TEXT NOT NULL,            -- a member id or an address
  recipient_role  TEXT,                     -- the board role it was resolved from
  subject         TEXT NOT NULL,            -- carries the ticket token, e.g. [PMC-000123]
  body            TEXT,
  created_at      TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING', 'SENT', 'FAILED', 'NO_SENDER')),
  sent_at         TEXT
);

CREATE INDEX ix_notification_status ON notification (status);
