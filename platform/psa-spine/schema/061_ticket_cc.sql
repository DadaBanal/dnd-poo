-- 061: Cc on a ticket (Dada, 1 Oct 2026: "can we add a cc on the tickets").
--
-- The people copied on a ticket, as the reference PSA's ticket Cc field: the
-- addresses an email came in with (never the sender, never the desk's own
-- addresses), and whatever a person types on the ticket. The requester's
-- emails (we have it, status changes, picked up, closed) go to them as Cc,
-- within the allowed domains. They see nothing on the portal; the requester
-- does. Carries no words of the ticket: an address only.
CREATE TABLE ticket_cc (
  work_item_id  TEXT NOT NULL REFERENCES ticket(work_item_id),
  address       TEXT NOT NULL,
  source        TEXT NOT NULL CHECK (source IN ('EMAIL', 'DESK')),
  added_at      TEXT NOT NULL,
  added_by      TEXT NOT NULL,
  PRIMARY KEY (work_item_id, address)
);
