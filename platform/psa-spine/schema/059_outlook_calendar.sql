-- 059: the desk's schedule on each member's Outlook calendar, and their
-- Outlook busy times on the desk (Dada, 1 Oct 2026: "the members should have
-- their accounts calendars synced with the actual calendars on outlook").
--
-- The desk holds no mail or calendar credential. It queues what changed;
-- scripts/Sync-PsaCalendars.ps1 on DND-SQL01 writes it to the member's
-- calendar through Microsoft Graph (the mail app's certificate, Exchange RBAC
-- for Applications "Application Calendars.ReadWrite" scoped to the desk's
-- members) and reports back, then reads each member's busy times back in.

-- The Outlook event a visit or a block is, once it has been written.
ALTER TABLE ticket_schedule ADD COLUMN outlook_event_id TEXT;
ALTER TABLE schedule_block ADD COLUMN outlook_event_id TEXT;

-- What to write: one row per change. A visit or block removed before it was
-- ever written is SUPERSEDED, never sent.
CREATE TABLE calendar_sync (
  sync_id     INTEGER PRIMARY KEY,
  kind        TEXT NOT NULL CHECK (kind IN ('VISIT', 'BLOCK')),
  ref_id      INTEGER NOT NULL,
  member      TEXT NOT NULL,
  action      TEXT NOT NULL CHECK (action IN ('UPSERT', 'DELETE')),
  event_id    TEXT,
  created_at  TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'PENDING'
                CHECK (status IN ('PENDING', 'SENT', 'FAILED', 'NO_MAILBOX', 'SUPERSEDED')),
  sent_at     TEXT
);
CREATE INDEX ix_calendar_sync_status ON calendar_sync (status);

-- What each member's Outlook calendar says they are doing, as busy blocks
-- only: never a subject, an attendee or a body. Replaced on every pull.
CREATE TABLE outlook_busy (
  busy_id     INTEGER PRIMARY KEY,
  member      TEXT NOT NULL,
  starts_at   TEXT NOT NULL,
  ends_at     TEXT NOT NULL,
  show_as     TEXT NOT NULL CHECK (show_as IN ('BUSY', 'TENTATIVE', 'OOF', 'WORKING_ELSEWHERE')),
  pulled_at   TEXT NOT NULL
);
CREATE INDEX ix_outlook_busy_member ON outlook_busy (member, starts_at);
