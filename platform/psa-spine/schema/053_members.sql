-- 053: members as records, a calendar feed, and a board's own intake address
--
-- Until now a member was a string: the sign-in identifier repeated across
-- board_member, member_role, member_capacity, oncall_slot, time_entry and
-- local_account, with a name only when the AD contact import happened to
-- carry it. The reference PSA's Member is a record with 123 fields; a
-- hospital desk needs about fifteen of them, and one page per person.
--
-- The identifier stays the key everywhere. This step adds a table beside the
-- rows that already exist and changes none of them, so a member who has no
-- row here is exactly what they were yesterday.

CREATE TABLE member (
  member           TEXT PRIMARY KEY,            -- the identifier every other table carries
  display_name     TEXT,
  title            TEXT,
  email            TEXT,
  phone            TEXT,
  mobile           TEXT,
  department       TEXT,                        -- a department name, as Setup › Departments has it
  location         TEXT,                        -- where Dada IT keeps them: the office, a ward store room
  reports_to       TEXT,                        -- a member identifier
  default_board_id TEXT REFERENCES board(board_id),
  work_role_id     TEXT REFERENCES work_role(work_role_id),
  time_approver    TEXT,                        -- a member identifier; who approves this person's week
  inactive_from    TEXT,                        -- the day they left; memberships were ended then
  notes            TEXT,
  created_at       TEXT NOT NULL,
  created_by       TEXT NOT NULL,
  updated_at       TEXT NOT NULL,
  updated_by       TEXT NOT NULL
);

-- A person's calendar feed (.ics), for the phone's own calendar app: one
-- token per member, stored hashed, rotated from their profile. The feed
-- names tickets, boards and places, never a ticket's summary.
CREATE TABLE calendar_feed (
  member       TEXT PRIMARY KEY,
  token_hash   TEXT NOT NULL,
  created_at   TEXT NOT NULL
);
CREATE INDEX ix_calendar_feed_hash ON calendar_feed (token_hash);

-- A board claims an address. Mail to it lands on that board, whichever
-- mailbox delivered it: Exchange can alias biomed@ onto the one helpdesk
-- mailbox and one pickup task serves every board, or each board can have a
-- mailbox of its own with a pickup task each. The reference PSA needs a
-- connector (a mailbox and a credential) per board; this needs an address.
ALTER TABLE board ADD COLUMN intake_address TEXT;

-- The address the message was routed by, when one was.
ALTER TABLE intake_message ADD COLUMN to_address TEXT;
