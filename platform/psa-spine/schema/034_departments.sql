-- 034 — departments, and which boards each may send requests to.
--
-- Dada's checklist (SQL01's handoff of 28 Sep 2026): a system administrator
-- ticks which departments may send requests to which boards. A tick lets a
-- department's staff RAISE a request onto that board; it never makes them
-- members (they do not see the board or its tickets). The Employee Portal door
-- lets a department in when it has at least one tick; the portal's raise form
-- offers the ticked boards; anything else lands on Unrouted, as today.
--
-- Names are exact, case included: the door matches the Department string the
-- payroll bridge returns, and the AD contact import's department attribute.
-- A department is never deleted; one gone from payroll is retired and keeps
-- its ticks, like a retired status.
PRAGMA foreign_keys = ON;

CREATE TABLE department (
  name        TEXT PRIMARY KEY,
  source      TEXT NOT NULL DEFAULT 'MANUAL' CHECK (source IN ('PAYROLL', 'MANUAL')),
  retired     INTEGER NOT NULL DEFAULT 0 CHECK (retired IN (0, 1)),
  created_at  TEXT NOT NULL,
  last_seen_at TEXT
);

CREATE TABLE department_board (
  department  TEXT NOT NULL REFERENCES department(name),
  board_id    TEXT NOT NULL REFERENCES board(board_id),
  ticked_at   TEXT NOT NULL,
  ticked_by   TEXT NOT NULL,
  PRIMARY KEY (department, board_id)
);
CREATE INDEX ix_department_board_board ON department_board (board_id);
