-- PSA spine 015 -- what arrived, and what it became
--
-- Intake has one job beyond creating tickets: never create the same ticket
-- twice, and never lose a message that could not be classified. Both are
-- measured problems rather than theoretical ones. §13 lists "alias
-- support@pmcne.ph onto helpdesk@pmcne.ph" as a cheap fix that "kills the
-- MEASURED double-creation" -- the same request arriving on two addresses
-- becomes two tickets today, and a fulfiller works one of them while the
-- requester reads the other.
--
-- So every message that arrives is written down here exactly once, with what it
-- became. That makes intake idempotent: re-running it over the same drop
-- produces no second ticket, because the message is already spoken for.

PRAGMA foreign_keys = ON;

CREATE TABLE intake_message (
  -- RFC 5322 Message-ID, as the sender wrote it. The natural key of a message,
  -- and the reason a redelivery cannot become a second ticket.
  message_id     TEXT PRIMARY KEY,
  received_at    TEXT NOT NULL,
  -- The address as sent, kept verbatim. Measured intake today includes consumer
  -- Gmail and Yahoo mailboxes (§6.1), and normalising that away loses evidence
  -- about who is actually raising tickets.
  from_address   TEXT,
  subject        TEXT,
  -- Which mailbox it landed in: 'helpdesk', 'support', or whatever the drop is
  -- named. This is how the double-creation is visible as a number rather than
  -- as an anecdote.
  channel        TEXT,

  -- What happened to it. Exactly one of these, always:
  --   NEW_TICKET  it opened a ticket
  --   APPENDED    it was a reply or a resend; it became a note on one
  --   DUPLICATE   same requester, same subject, inside the window
  --   UNCLASSIFIED it could not be placed, and is flagged rather than dropped
  disposition    TEXT NOT NULL CHECK (disposition IN
                   ('NEW_TICKET','APPENDED','DUPLICATE','UNCLASSIFIED')),
  work_item_id   TEXT REFERENCES work_item(work_item_id),
  -- The message this one was judged to continue, when it was.
  duplicate_of   TEXT REFERENCES intake_message(message_id),
  run_id         TEXT,

  -- A disposition that names a ticket must have one, and one that does not must
  -- not. Otherwise "APPENDED to nothing" is a state the table can hold.
  CHECK ((disposition IN ('NEW_TICKET','APPENDED')) = (work_item_id IS NOT NULL))
);

-- "Have I seen this thread before" and "what else came from this requester with
-- this subject" are the two questions asked on the hot path.
CREATE INDEX ix_intake_thread ON intake_message (from_address, subject);
CREATE INDEX ix_intake_ticket ON intake_message (work_item_id);
