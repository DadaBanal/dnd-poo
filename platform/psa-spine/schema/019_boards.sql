-- 019 — many boards, created and retired by the people who run them.
--
-- The reference PSA: "A service board cannot be deleted once any items are tied to it
-- ... your best option is to mark it as inactive" (build scope §5.2). So a board
-- is retired, never deleted, and `inactive` is a different state from `is_live`
-- (not started yet vs closed down).
PRAGMA foreign_keys = ON;

-- Nullable, as every added column must be (the port refuses to invent values
-- for rows that already exist): NULL and 0 both mean active.
ALTER TABLE board ADD COLUMN inactive INTEGER CHECK (inactive IN (0, 1));
ALTER TABLE board ADD COLUMN description TEXT;
