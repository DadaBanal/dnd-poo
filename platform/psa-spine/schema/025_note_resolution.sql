-- 025 — a note can be the resolution as well as a discussion or internal note.
--
-- ConnectWise's note carries three flags, and one note may carry more than one:
-- Discussion, Internal, Resolution (VERIFIED 23 Sep 2026, the ServiceNote model
-- in ConnectWise's public OpenAPI, Service.json v2026.13). In 017 a note had
-- exactly one. Who can read a note stays note_flag: DISCUSSION (the requester
-- sees it) or INTERNAL (never leaves the desk); RESOLUTION alone still reads as
-- a discussion note that is the resolution. is_resolution adds the Resolution
-- flag to either. An INTERNAL resolution stays internal: the portal never shows it.
PRAGMA foreign_keys = ON;

ALTER TABLE ticket_event ADD COLUMN is_resolution INTEGER
  CHECK (is_resolution IN (0, 1));
