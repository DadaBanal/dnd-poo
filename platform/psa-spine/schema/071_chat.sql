-- 071 — Chat: a requester and the desk, live (Dada, 7 Oct 2026: "can we do
-- something to connectwise chat?"; confirmed: requester <-> desk, offered on
-- the portal at any time, patient details flagged and warned, never blocked).
--
-- The reference PSA's Chat: a requester starts a chat from the portal, it waits
-- in a queue, a technician picks it up and replies, and the chat can become a
-- ticket (the transcript its first note) or join an existing one.
--
-- Additive only: two new tables.
--
-- * chat_session: one conversation. WAITING until a technician picks it up,
--   ACTIVE while they talk, CLOSED when either side ends it. work_item_id is
--   the ticket it became or joined.
-- * chat_message: its lines, in order. sender_kind says whose side wrote it;
--   SYSTEM lines are the desk's own ("picked up by ...").
PRAGMA foreign_keys = ON;

CREATE TABLE chat_session (
  chat_id       INTEGER PRIMARY KEY,
  board_id      TEXT NOT NULL REFERENCES board(board_id),
  requester     TEXT NOT NULL,
  subject       TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'WAITING' CHECK (status IN ('WAITING', 'ACTIVE', 'CLOSED')),
  started_at    TEXT NOT NULL,
  picked_by     TEXT,
  picked_at     TEXT,
  closed_at     TEXT,
  closed_by     TEXT,
  work_item_id  TEXT REFERENCES ticket(work_item_id),
  last_at       TEXT NOT NULL
);
CREATE INDEX ix_chat_session_status ON chat_session (status, board_id);
CREATE INDEX ix_chat_session_requester ON chat_session (requester);

CREATE TABLE chat_message (
  message_id    INTEGER PRIMARY KEY,
  chat_id       INTEGER NOT NULL REFERENCES chat_session(chat_id),
  sender        TEXT NOT NULL,
  sender_kind   TEXT NOT NULL CHECK (sender_kind IN ('REQUESTER', 'STAFF', 'SYSTEM')),
  body          TEXT NOT NULL,
  sent_at       TEXT NOT NULL
);
CREATE INDEX ix_chat_message_chat ON chat_message (chat_id, message_id);
