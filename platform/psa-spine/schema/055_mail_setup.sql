-- 055: the email connector's settings on the desk
--
-- What arrives by mail is decided by three things: which board claims the
-- address it was sent to (053), the board's reply policy (023), and what
-- must never open a ticket. The third lived in code: delivery-system senders
-- and auto-replies (the loop guard), and the desk's own addresses passed on
-- the command line. A hospital mailbox also gets vendor newsletters, a
-- monitoring system's digests and a scanner's "document attached" mail, and
-- each of those is a decision a person makes once, here, not a code change.
--
-- A row is an exclusion: mail from an ADDRESS, from a DOMAIN, or whose
-- SUBJECT contains a phrase, is imported and recorded (nothing is dropped,
-- as intake has always promised) but opens nothing, with the reason on the
-- data-quality finding.

CREATE TABLE mail_exclusion (
  exclusion_id  INTEGER PRIMARY KEY,
  kind          TEXT NOT NULL CHECK (kind IN ('ADDRESS', 'DOMAIN', 'SUBJECT')),
  pattern       TEXT NOT NULL,             -- lower case; an address, a domain, or a phrase
  note          TEXT,
  created_at    TEXT NOT NULL,
  created_by    TEXT NOT NULL
);
