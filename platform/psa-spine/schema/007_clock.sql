-- PSA spine 007 — the SLA clocks
--
-- Three clocks, each with its own target and its own calendar, because the
-- workbook's three numbers are incommensurable as written: "response within 1
-- day" is a per-ticket target, "90% within 2 hours" is a population percentile,
-- and "16 hours" has no calendar attached at all.
--
-- Two disciplines carried from the design and enforced here rather than
-- remembered:
--
--   * BREACH IS NEVER STORED. It is derived at read time from the target, the
--     calendar and the pauses. A stored breach flag goes stale the moment a
--     target is corrected or a calendar is fixed, and then the report defends a
--     number nobody can reproduce.
--
--   * A PAUSE IS A ROW, NOT A RUNNING TOTAL. `paused_minutes` as a counter is a
--     number you cannot audit and cannot recompute. Each pause is an interval
--     with a reason, so "why was this ticket not breaching on the 14th" has an
--     answer somebody can read.
--
-- Every target still ships enforced = 0 on sla_target. The agreement contains no
-- response or resolution commitment and three clauses disclaim creating one, so
-- these clocks MEASURE. They do not promise.

PRAGMA foreign_keys = ON;

CREATE TABLE ticket_clock (
  clock_id       INTEGER PRIMARY KEY,
  work_item_id   TEXT NOT NULL REFERENCES ticket(work_item_id),
  clock          TEXT NOT NULL CHECK (clock IN
                   ('RESPOND','RESOLUTION_PLAN','RESOLVE','ACKNOWLEDGE','DECISION')),
  -- Which working week this clock counts against. A ward roster and Manila
  -- business hours are different rows, so a clock on a clinical board and a
  -- clock on the agreement board can disagree about whether Sunday counts.
  calendar_id    TEXT NOT NULL REFERENCES calendar(calendar_id),
  target_minutes INTEGER NOT NULL CHECK (target_minutes > 0),
  started_at     TEXT NOT NULL,
  -- Set when the ticket reaches a status whose escalation_status satisfies this
  -- clock. Until then the clock is running and elapsed is computed to now.
  stopped_at     TEXT,
  -- The status that stopped it, so the reason is on the record rather than
  -- inferred from a timestamp.
  stopped_by_status TEXT REFERENCES board_status(board_status_id),
  UNIQUE (work_item_id, clock),
  CHECK (stopped_at IS NULL OR stopped_at >= started_at)
);

-- One row per interval the clock was not counting. Derived from the ticket
-- entering a status whose escalation_status is NO_ESCALATION, but stored
-- explicitly because the status list can be edited afterwards and this must
-- still recompute to the same answer.
CREATE TABLE ticket_clock_pause (
  pause_id        INTEGER PRIMARY KEY,
  clock_id        INTEGER NOT NULL REFERENCES ticket_clock(clock_id),
  paused_at       TEXT NOT NULL,
  resumed_at      TEXT,
  -- Which status paused it. NULL only for a pause applied by hand, which then
  -- needs a reason instead.
  board_status_id TEXT REFERENCES board_status(board_status_id),
  reason          TEXT,
  CHECK (resumed_at IS NULL OR resumed_at >= paused_at),
  CHECK (board_status_id IS NOT NULL OR reason IS NOT NULL)
);
