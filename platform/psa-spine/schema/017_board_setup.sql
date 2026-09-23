-- 017 — the pieces that make a board run the way a ConnectWise service board
-- does: its own calendar, notes that say who may read them, and the time a
-- ticket was last touched.
--
-- ConnectWise's SLA carries `basedOn` and a `customCalendar`; here the board
-- names its calendar and the clocks it starts run on it. NULL means the board
-- has not been set up, and a ticket on it starts no clock — which the board
-- view says in words rather than showing a clock that is not there.
PRAGMA foreign_keys = ON;

ALTER TABLE board ADD COLUMN calendar_id TEXT REFERENCES calendar(calendar_id);

-- ConnectWise flags every note: Discussion (the requester sees it), Internal
-- (fulfillers only) and Resolution (the answer, which the requester sees).
-- NULL is a system event: a status change, an import, a routing.
ALTER TABLE ticket_event ADD COLUMN note_flag TEXT
  CHECK (note_flag IN ('DISCUSSION', 'INTERNAL', 'RESOLUTION'));

-- Who the ticket is for, in ConnectWise's words the contact. requested_by
-- already carries it; this is the time of the last touch, for the board's
-- "Updated" column and for sorting by it.
ALTER TABLE ticket ADD COLUMN updated_at TEXT;
