-- PSA spine 009 — the ticket points at its board's status
--
-- 005 gave `ticket.state` a CHECK over eight values. That was right for a schema
-- with no board configuration: something had to name the lifecycle, and the two
-- gate triggers depend on it.
--
-- 006 made statuses per-board rows. So there are now two levels, and they are
-- not duplication -- the reference PSA has exactly the same pair, and for the same
-- reason:
--
--   * `state` is the UNIVERSAL lifecycle. Eight values, the same on every board,
--     and what the variation gate in 005 tests. A rule that must hold hospital
--     wide cannot depend on a vocabulary each board edits.
--   * `board_status_id` is what the BOARD calls it. "Waiting for parts",
--     "Awaiting PhilHealth", "With biomedical" -- as many as a board needs,
--     each declaring which SLA milestone it represents.
--
-- The board status is authoritative where it is set, and psaspine/board.py keeps
-- `state` in step with it. It is NULL on every ticket imported from the desk,
-- because history arrives with a status string that was never one of our rows,
-- and inventing a mapping would be inventing the record.

PRAGMA foreign_keys = ON;

ALTER TABLE ticket ADD COLUMN board_status_id TEXT REFERENCES board_status(board_status_id);
