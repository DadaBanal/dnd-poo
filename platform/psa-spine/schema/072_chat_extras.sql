-- 072 — Chat, round two (Dada, 7 Oct 2026: "can we add reactions and emojis to
-- the chat and also attachments and a survey at the end"; confirmed: Teams-
-- style reactions and an emoji picker, pictures and files through the patient-
-- details review, the requester rates the chat when it ends).
--
-- Additive only: three new tables.
--
-- * chat_reaction: one person's reaction to one line (a fixed set of emoji);
--   reacting again with the same one takes it off.
-- * chat_file: a picture or file sent in a chat, kept in the same store as the
--   tickets' files (by its sha256), reviewed for patient details the same way:
--   a requester's arrives PENDING, the desk clears or withholds it; the desk's
--   own is CLEARED as it is sent.
-- * chat_survey: the requester's rating of an ended chat, one to five, and a
--   sentence if they like.
-- * board.chat_welcome: what a ward reads the moment its chat starts, while it
--   waits to be picked up (Dada, 7 Oct 2026: "please wait your ticket is being
--   picked up something like that similar to support chats"). NULL reads as the
--   desk's own words.
PRAGMA foreign_keys = ON;

CREATE TABLE chat_reaction (
  message_id    INTEGER NOT NULL REFERENCES chat_message(message_id),
  member        TEXT NOT NULL,
  emoji         TEXT NOT NULL,
  reacted_at    TEXT NOT NULL,
  PRIMARY KEY (message_id, member, emoji)
);

CREATE TABLE chat_file (
  file_id       INTEGER PRIMARY KEY,
  chat_id       INTEGER NOT NULL REFERENCES chat_session(chat_id),
  message_id    INTEGER NOT NULL REFERENCES chat_message(message_id),
  filename      TEXT NOT NULL,
  media_type    TEXT NOT NULL,
  size_received INTEGER NOT NULL CHECK (size_received > 0),
  size_stored   INTEGER NOT NULL CHECK (size_stored > 0),
  sha256        TEXT NOT NULL,
  encoding      TEXT NOT NULL CHECK (encoding IN ('IDENTITY', 'GZIP')),
  uploaded_by   TEXT NOT NULL,
  uploaded_at   TEXT NOT NULL,
  review_status TEXT NOT NULL CHECK (review_status IN ('PENDING', 'CLEARED', 'WITHHELD')),
  reviewed_by   TEXT,
  reviewed_at   TEXT
);
CREATE INDEX ix_chat_file_chat ON chat_file (chat_id);

CREATE TABLE chat_survey (
  chat_id       INTEGER PRIMARY KEY REFERENCES chat_session(chat_id),
  score         INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
  comment       TEXT,
  answered_by   TEXT NOT NULL,
  answered_at   TEXT NOT NULL
);

ALTER TABLE board ADD COLUMN chat_welcome TEXT;
