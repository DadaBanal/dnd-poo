-- 028 — retention of files on tickets.
--
-- A file is removed under a retention rule (psaspine attachments-purge), not
-- by hand. The row stays: the ticket's history still says a file was sent, by
-- whom, what it was and who reviewed it; only the bytes are gone. §6.1 point 3:
-- retention is designed, not inherited, and the periods are an operator's
-- arguments, never a default in code, until the Data Protection Officer has
-- signed them.
PRAGMA foreign_keys = ON;

ALTER TABLE attachment ADD COLUMN purged_at TEXT;
ALTER TABLE attachment ADD COLUMN purge_reason TEXT
  CHECK (purge_reason IN ('WITHHELD', 'CLOSED', 'MISSING'));
