-- PSA spine 011 — the on-call rota
--
-- board_role in 006 answers "who is the on-call member for this board" with one
-- named person. That is right for the org chart and wrong for 02:00: the person
-- who owns a P1 raised at two in the morning is whoever is ON SHIFT, not the one
-- name somebody typed into the board once. This table is the shift, so a page at
-- 02:00 reaches the person actually awake for it.
--
-- ConnectWise documents the duty manager as "backup for the on-call member ...
-- if the on-call member does not respond", so the two roles that rotate are
-- ON_CALL and DUTY_MANAGER — the same vocabulary board_role already carries, on
-- purpose, so the dispatch view can show the rota's answer over the board's.

PRAGMA foreign_keys = ON;

CREATE TABLE oncall_slot (
  slot_id    TEXT PRIMARY KEY,
  board_id   TEXT NOT NULL REFERENCES board(board_id),
  -- The same namespace as board_member.member and board_role.member: a named
  -- person, never a role name. Who to page, not what to page.
  member     TEXT NOT NULL,
  role       TEXT NOT NULL CHECK (role IN ('ON_CALL', 'DUTY_MANAGER')),
  starts_at  TEXT NOT NULL,
  ends_at    TEXT NOT NULL,
  -- A shift that ends before it starts is a typo, not a shift.
  CHECK (ends_at > starts_at)
);

-- "Who is on call for this board and role right now" is the only question asked
-- of this table on a hot path, so it is the shape the index serves.
CREATE INDEX ix_oncall_active ON oncall_slot (board_id, role, starts_at, ends_at);
