-- PSA spine 016 -- one open ticket per alert, however often it fires
--
-- Machines re-fire. A monitor that flaps every five minutes overnight is a
-- hundred and forty-four alerts by morning, and a desk that opens a ticket for
-- each one has made itself useless for the only morning that mattered. So an
-- alert carries a key it chooses -- 'orthanc-down', 'ups-on-battery' -- and
-- while the ticket that key opened is still open, a repeat firing is a note on
-- that ticket and a count, not a new ticket.
--
-- Once that ticket is resolved, the next firing opens a fresh one. A fault that
-- comes back after being fixed is a new fault, and folding it into a closed
-- ticket would hide the recurrence, which is the most useful thing about it.

PRAGMA foreign_keys = ON;

CREATE TABLE api_alert (
  board_id      TEXT NOT NULL REFERENCES board(board_id),
  -- Chosen by the sender. Stable across firings of the same condition.
  dedup_key     TEXT NOT NULL,
  work_item_id  TEXT NOT NULL REFERENCES ticket(work_item_id),
  first_seen    TEXT NOT NULL,
  last_seen     TEXT NOT NULL,
  times         INTEGER NOT NULL DEFAULT 1 CHECK (times >= 1),
  PRIMARY KEY (board_id, dedup_key)
);
