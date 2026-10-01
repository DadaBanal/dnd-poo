-- 058: the mail cut-over (SQL01, 1 Oct 2026). Three addresses (helpdesk@, its
-- help@ alias, and support@) all land on one board, and the requester hears
-- at each status change in that status's own words.

-- A board claims as many addresses as it is sent mail on; an address belongs
-- to one board. Lower case, as intake compares them. Before 058 a board
-- claimed one (board.intake_address). `init` moves any such value here and
-- empties the column (db.seed, which every init runs), so the claim lives in
-- one place only; the column stays, unread, for the databases that have it.
CREATE TABLE board_intake_address (
  address   TEXT PRIMARY KEY,
  board_id  TEXT NOT NULL REFERENCES board(board_id)
);

-- The email a requester gets when their ticket enters a status. No row: that
-- status sends nothing, as before 058. A row with no words uses the desk's
-- words for that kind of status. Placeholders as for mail_template, and none
-- carries the summary, a note or the requester's own subject (6.1).
CREATE TABLE status_mail (
  board_status_id TEXT PRIMARY KEY REFERENCES board_status(board_status_id),
  enabled         INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  subject         TEXT,
  body            TEXT,
  updated_at      TEXT NOT NULL,
  updated_by      TEXT NOT NULL
);

-- Which address a notification goes out from: the one the requester wrote
-- to, when a board claims it. NULL: the sender's own mailbox, as before.
ALTER TABLE notification ADD COLUMN from_address TEXT;
