-- 027 — attachments, and telling the requester their ticket moved.
--
-- Files are kept outside the database (psaspine/attachments.py); this row says
-- what the file is, how it was stored and whether anyone has checked it for
-- patient information. Every file starts PENDING: ConnectWise keeps documents on
-- a ticket with no such check, and a screenshot of a patient list is the
-- commonest way a hospital leaks data into a ticket system (§6.1).
PRAGMA foreign_keys = ON;

CREATE TABLE attachment (
  attachment_id  INTEGER PRIMARY KEY,
  work_item_id   TEXT NOT NULL REFERENCES ticket(work_item_id),
  filename       TEXT NOT NULL,              -- cleaned; never used as a path
  media_type     TEXT NOT NULL,              -- from the file's own bytes
  size_received  INTEGER NOT NULL CHECK (size_received > 0),
  size_stored    INTEGER NOT NULL CHECK (size_stored > 0),
  sha256         TEXT NOT NULL,              -- of the file as served; also its name on disk
  encoding       TEXT NOT NULL CHECK (encoding IN ('IDENTITY', 'GZIP')),
  treatment      TEXT NOT NULL,              -- what compression did, in words
  source         TEXT NOT NULL CHECK (source IN ('DESK', 'PORTAL', 'EMAIL')),
  uploaded_by    TEXT NOT NULL,
  uploaded_at    TEXT NOT NULL,
  review_status  TEXT NOT NULL CHECK (review_status IN ('PENDING', 'CLEARED', 'WITHHELD')),
  reviewed_by    TEXT,
  reviewed_at    TEXT,
  CHECK ((review_status = 'PENDING') = (reviewed_by IS NULL))
);

CREATE INDEX ix_attachment_ticket ON attachment (work_item_id);

-- Emailing the requester: ConnectWise mails the contact on a new ticket and on a
-- Discussion note, per board. Here the mail says only that the ticket moved and
-- links to the portal; the note's words never leave the desk (§6.1). NULL reads
-- as on.
ALTER TABLE board ADD COLUMN notify_requester INTEGER
  CHECK (notify_requester IN (0, 1));
