-- 037 — the Calendar and Holiday List setup tables, in the reference PSA's shape.
--
-- Its Calendar is a name, a start and end for each of the seven days, and a
-- holiday list; its Holiday is a date, a name, an allDayFlag and, when the flag
-- is off, a timeStart and timeEnd for a half-day closure (the record's
-- extracted model, VERIFIED 9 Sep 2026 from its published OpenAPI schema). 006
-- had the calendar and the whole-day holiday; this adds the part-day holiday
-- and lets a calendar be retired, so Setup › Calendars can edit both without
-- the CLI. NULL-able by the port's rule: all_day NULL reads as 1, whole day.
--
-- The clocks honour it: a part-day holiday closes the calendar for its hours
-- on that date and nothing else. Nothing is deleted except a holiday date,
-- which is reference data typed by a person and may be typed wrong; removing
-- one is audited, and every clock recomputes from the rows as they now stand.
PRAGMA foreign_keys = ON;

ALTER TABLE holiday ADD COLUMN all_day INTEGER DEFAULT 1 CHECK (all_day IN (0, 1));
ALTER TABLE holiday ADD COLUMN time_start TEXT;
ALTER TABLE holiday ADD COLUMN time_end TEXT;
ALTER TABLE calendar ADD COLUMN inactive INTEGER DEFAULT 0 CHECK (inactive IN (0, 1));
