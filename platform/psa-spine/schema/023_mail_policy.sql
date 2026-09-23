-- 023 — mail intake policy, the way ConnectWise's email connector sets it.
--
-- ConnectWise decides per board what a reply to a closed ticket does: reopen it
-- to a chosen status, or open a new ticket once it has been closed longer than N
-- days (VERIFIED 23 Sep 2026, docs.connectwise.com/ConnectWise_Documentation/
-- 090/020/170/040, archived 2024-07-15). A reply that lands silently on a
-- closed ticket is a request nobody sees, so every board now has an answer.
--
-- NULL policy reads as REOPEN with no day limit, to the board's default status.
PRAGMA foreign_keys = ON;

ALTER TABLE board ADD COLUMN closed_reply_policy TEXT
  CHECK (closed_reply_policy IN ('REOPEN', 'NEW_TICKET'));
-- REOPEN only within this many days of closing; older replies open a new ticket.
ALTER TABLE board ADD COLUMN reopen_within_days INTEGER
  CHECK (reopen_within_days > 0);
ALTER TABLE board ADD COLUMN reopen_status_id TEXT REFERENCES board_status(board_status_id);

-- ConnectWise's "customer updated": the requester has written since a fulfiller
-- last did. Set by every inbound reply (mail or portal), cleared by a fulfiller's
-- note, shown on the board so a reply is never missed. NULL reads as 0.
ALTER TABLE ticket ADD COLUMN customer_updated INTEGER
  CHECK (customer_updated IN (0, 1));
