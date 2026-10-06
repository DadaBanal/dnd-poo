-- 067 — several members on one ticket, without a visit (Dada, 6 Oct 2026:
-- "assigning tickets to multiple members").
--
-- The reference PSA has one Owner and any number of Resources. Until today a
-- resource here was only somebody with a visit booked on the ticket (038), so
-- putting a second person on a job meant inventing an appointment for them.
-- This is the plain assignment: the person is on the ticket, it is in their
-- list, and nobody has to say when they will turn up.
--
-- The owner stays the one point of contact (ticket.owner). The resources the
-- ticket page shows are the union of this table and the people with a visit;
-- removing a row here never touches a visit.
PRAGMA foreign_keys = ON;

CREATE TABLE ticket_resource (
  work_item_id  TEXT NOT NULL REFERENCES work_item(work_item_id),
  member        TEXT NOT NULL,
  added_at      TEXT NOT NULL,
  added_by      TEXT NOT NULL,
  PRIMARY KEY (work_item_id, member)
);

-- "My tickets": every ticket a person is on, by person.
CREATE INDEX ix_ticket_resource_member ON ticket_resource (member);
