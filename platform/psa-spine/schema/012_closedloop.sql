-- PSA spine 012 — the closed loop
--
-- The single feature most likely to make the capacity evidence real. Today
-- effort reaches time_entry only if a fulfiller remembers to band it after the
-- fact, and the record's own base rate for "somebody remembers to, every time"
-- is not one you build a fee claim on. The closed loop removes the discipline:
-- the answer to the requester and the banding of the effort are ONE action, so
-- closing a ticket the honest way captures the numerator by construction.
--
-- loop_reply is the requester-facing answer. The effort it captured lands in
-- time_entry the same way all effort does — through the variation gate in 005,
-- which still refuses a variation-path ticket that has no variation attached.
-- The loop does not get to bypass the gate; it just makes the ordinary path the
-- easy one.

PRAGMA foreign_keys = ON;

CREATE TABLE loop_reply (
  loop_reply_id  TEXT PRIMARY KEY,
  work_item_id   TEXT NOT NULL REFERENCES work_item(work_item_id),
  -- What the fulfiller typed to the requester. Not a clinical note: the §6.1
  -- fence keeps PHI out of ticket text, and this is ticket text.
  body           TEXT NOT NULL,
  sent_at        TEXT NOT NULL,
  sent_by        TEXT NOT NULL,
  -- The band recorded at reply time, in minutes, so the loop can be shown
  -- without joining time_entry. NULL when the reply banded nothing (a chase,
  -- a holding answer). The authoritative effort is still the time_entry row.
  effort_minutes INTEGER,
  banded_at      TEXT
);

-- The effort banded through a loop points back at the reply that captured it, so
-- the uplift evidence can say not just how many hours but that each hour was
-- answered to the requester in the same breath.
ALTER TABLE time_entry ADD COLUMN loop_reply_id TEXT REFERENCES loop_reply(loop_reply_id);
