-- 030 — child tickets.
--
-- ConnectWise's parent/child: five people report the same printer, one ticket
-- is the parent and the others hang off it; when the parent closes, its
-- children close with it. One level only, as ConnectWise has it -- a child has
-- no children -- so the tree is a list and nothing can loop. This is not a
-- handover (005: a handover is ONE ticket changing board) and not a link
-- (022: a link says why, and each ticket keeps its own life); a child's status
-- follows its parent's close.
PRAGMA foreign_keys = ON;

ALTER TABLE ticket ADD COLUMN parent_id TEXT REFERENCES ticket(work_item_id);
CREATE INDEX ix_ticket_parent ON ticket (parent_id);
