-- 050 — channels beyond email, and on-call paging.
--
-- The desk's outbox carried one kind of message: an email, sent by the host's
-- Graph sender. A ward at 02:00 needs more than an email nobody is reading:
-- a card in the IT team's Teams channel, and a page to the person on call
-- that repeats until they acknowledge it and hands to the duty manager when
-- they do not. So:
--   * channel_target names a Teams channel by a short name; the address it
--     posts to (a webhook URL) lives only on the host, in a file the sender
--     reads, never in this database and never in the repository.
--   * notification gains a channel (EMAIL as before, or TEAMS) and the target
--     a Teams card goes to; the two senders each take their own channel.
--   * workflow_action gains a channel (EMAIL, TEAMS or PAGE) and a target, so
--     a rule can say "notify the on-call channel" or "page the on-call".
--   * page is one paging episode: who, how often, how many times, and how it
--     ended (acknowledged, exhausted and escalated, stopped, ticket closed).
-- Nothing here holds a secret; nothing here holds a summary or a note.
PRAGMA foreign_keys = ON;

CREATE TABLE channel_target (
  target_id   TEXT PRIMARY KEY,                                     -- a short name: helpdesk-alerts
  kind        TEXT NOT NULL DEFAULT 'TEAMS_WEBHOOK' CHECK (kind IN ('TEAMS_WEBHOOK')),
  label       TEXT NOT NULL,                                        -- what people call it
  pages       INTEGER NOT NULL DEFAULT 0 CHECK (pages IN (0, 1)),   -- also carries pages to the on-call
  note        TEXT,
  inactive    INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1)),
  created_at  TEXT NOT NULL,
  created_by  TEXT NOT NULL
);

CREATE TABLE page (
  page_id        INTEGER PRIMARY KEY,
  work_item_id   TEXT NOT NULL REFERENCES ticket(work_item_id),
  member         TEXT NOT NULL,                                     -- who is being paged
  role           TEXT NOT NULL CHECK (role IN ('ON_CALL', 'DUTY_MANAGER', 'NAMED')),
  started_at     TEXT NOT NULL,
  started_by     TEXT NOT NULL,
  every_minutes  INTEGER NOT NULL CHECK (every_minutes BETWEEN 1 AND 120),
  max_attempts   INTEGER NOT NULL CHECK (max_attempts BETWEEN 1 AND 20),
  attempts       INTEGER NOT NULL DEFAULT 0,
  last_sent_at   TEXT,
  status         TEXT NOT NULL DEFAULT 'OPEN'
                   CHECK (status IN ('OPEN', 'ACKNOWLEDGED', 'EXHAUSTED', 'STOPPED')),
  ended_at       TEXT,
  ended_by       TEXT,
  note           TEXT
);
CREATE INDEX ix_page_open ON page (status, work_item_id);

-- Added columns are NULL-able by the port's rule (a row from before 050 has no
-- value); the desk reads NULL as EMAIL everywhere.
ALTER TABLE notification ADD COLUMN channel TEXT DEFAULT 'EMAIL' CHECK (channel IN ('EMAIL', 'TEAMS'));
ALTER TABLE notification ADD COLUMN target_id TEXT REFERENCES channel_target(target_id);
ALTER TABLE notification ADD COLUMN page_id INTEGER REFERENCES page(page_id);
ALTER TABLE workflow_action ADD COLUMN channel TEXT DEFAULT 'EMAIL' CHECK (channel IN ('EMAIL', 'TEAMS', 'PAGE'));
-- A card's channel is also written to target_member: 008's CHECK asks that a
-- notify reach someone, and for a card the someone is the channel.
ALTER TABLE workflow_action ADD COLUMN target_id TEXT REFERENCES channel_target(target_id);
