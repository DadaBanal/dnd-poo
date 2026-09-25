-- 029 — the indexes the desk's hot queries walk.
--
-- MEASURED over a 3,000-ticket database (24 Sep 2026): the board took 1.7 s,
-- and a third of that was the per-ticket lookups of the last note and the
-- clocks scanning whole tables. Nothing here changes what is stored; each index
-- names a lookup a screen does for every row it shows.
PRAGMA foreign_keys = ON;

CREATE INDEX ix_ticket_event_ticket ON ticket_event (work_item_id, ticket_event_id);
CREATE INDEX ix_ticket_clock_ticket ON ticket_clock (work_item_id);
CREATE INDEX ix_ticket_clock_pause_clock ON ticket_clock_pause (clock_id, paused_at);
CREATE INDEX ix_ticket_board_state ON ticket (board_id, state);
