-- 031 — saved board views, and standard notes.
--
-- A saved view is a person's own filter on the board (Dada PSA's "My
-- views"): a name and the query it stands for, theirs alone. A standard note
-- is a board's canned reply (Dada PSA's standard notes): the words a
-- technician pastes twenty times a week, kept once, edited by the board's
-- administrators, never carrying patient details because they are written
-- before any ticket exists.
PRAGMA foreign_keys = ON;

CREATE TABLE user_view (
  view_id     INTEGER PRIMARY KEY,
  member      TEXT NOT NULL,                -- the person, as board_member.member
  name        TEXT NOT NULL,
  query       TEXT NOT NULL,                -- the board's query string, e.g. board=IT_HELP&pri=P1
  sort_order  INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL
);
CREATE INDEX ix_user_view_member ON user_view (member, sort_order);

CREATE TABLE standard_note (
  note_id     INTEGER PRIMARY KEY,
  board_id    TEXT NOT NULL REFERENCES board(board_id),
  name        TEXT NOT NULL,                -- what the picker shows
  body        TEXT NOT NULL,                -- what lands in the note box
  flag        TEXT NOT NULL CHECK (flag IN ('DISCUSSION', 'INTERNAL')),
  inactive    INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1)),
  created_at  TEXT NOT NULL,
  created_by  TEXT NOT NULL
);
CREATE INDEX ix_standard_note_board ON standard_note (board_id, inactive, name);
