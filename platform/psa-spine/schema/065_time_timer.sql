-- 065 — the stopwatch on a ticket, which is not an SLA clock.
--
-- Dada, 3 Oct 2026: *"there is usually a clock on the ConnectWise ticketing for
-- time entries, that's apart from the SLA"*. He is right, and the desk had no
-- such thing: a technician could only type a start and an end into the time
-- entry form from memory, after the fact.
--
-- THE TWO CLOCKS ARE DIFFERENT THINGS AND MUST NOT BE CONFUSED:
--
--   ticket_clock (007)   the hospital's obligation. When the desk must respond
--                        and resolve, measured on the board's calendar, paused
--                        by the statuses that pause it, and reported as the
--                        SLA. It starts itself and nobody may start or stop it
--                        by hand.
--
--   time_timer (here)    one technician's worked time on one ticket. Started
--                        and stopped by that person, paused when they step
--                        away, and its only purpose is to fill in time_start
--                        and time_end on a time entry (033) so the hours are
--                        measured rather than remembered. It counts wall-clock
--                        seconds, honours no calendar, and no SLA number is
--                        computed from it, ever.
--
-- A timer is a draft, not a record: it is the raw material of a time entry and
-- carries no hours, no work role and no bill option. Those are chosen when the
-- entry is saved, which is the moment the time becomes a fact.
PRAGMA foreign_keys = ON;

CREATE TABLE time_timer (
  timer_id      INTEGER PRIMARY KEY,
  work_item_id  TEXT NOT NULL REFERENCES work_item(work_item_id),
  member        TEXT NOT NULL,
  started_at    TEXT NOT NULL,
  -- Set when the person stops it. A stopped timer is kept until its entry is
  -- saved or it is discarded, so a stop is never a loss.
  stopped_at    TEXT,
  -- Accumulated seconds the timer was paused for, and when the current pause
  -- began (NULL when it is running). Elapsed is (stop or now) - started_at
  -- - paused_seconds, and while paused it is paused_at - started_at - the rest.
  paused_seconds INTEGER NOT NULL DEFAULT 0 CHECK (paused_seconds >= 0),
  paused_at     TEXT,
  -- What the person was doing, typed while it runs so it is not invented
  -- afterwards. Carried into the time entry's note.
  note          TEXT,
  -- The entry it became, once saved. A timer with this set is spent.
  time_entry_id INTEGER REFERENCES time_entry(time_entry_id),
  CHECK (stopped_at IS NULL OR stopped_at >= started_at),
  CHECK (paused_at IS NULL OR paused_at >= started_at),
  -- A running timer cannot already be spent.
  CHECK (time_entry_id IS NULL OR stopped_at IS NOT NULL)
);

-- One running timer per person per ticket. Two would double-count the same
-- hour, and a person who wants a second one wants a second ticket. Nothing
-- stops the same person running timers on several tickets at once, which is
-- what a technician carrying three jobs actually does.
CREATE UNIQUE INDEX ux_time_timer_running
  ON time_timer (work_item_id, member) WHERE stopped_at IS NULL;

-- What the Time pod and the header indicator read: this person's timers,
-- newest first.
CREATE INDEX ix_time_timer_member ON time_timer (member, stopped_at);
