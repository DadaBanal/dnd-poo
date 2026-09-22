-- PSA spine 014 — one ticket sequence, across every board
--
-- D4. The scope document's own words: *"cheap now, very expensive after the
-- first thousand tickets"*. Phase C is precisely what produces the first
-- thousand, so this closes before intake opens or it never closes cheaply.
--
-- ONE sequence for the whole hospital, not one per board. Per-board numbering
-- reads as tidier and is not: a ticket moves board — that is what a handover is
-- (005) — and a number that belongs to the board it started on either follows
-- the ticket and stops matching its own board, or is reissued and stops being a
-- reference. A hospital-wide number survives the handover, which is the one
-- thing a ticket number has to do.
--
-- What the desk called it is NOT replaced. `ticket.external_ref` already keeps
-- the source's own reference verbatim, and imported history keeps its own id:
-- renumbering thirty-five thousand historical rows would break every reference
-- anybody has ever written down.

PRAGMA foreign_keys = ON;

-- The prefix is configuration, not a constant, because §12 is explicit: if PMC
-- cannot change it without a deployment, it is in the wrong place. Exactly one
-- row, enforced, so there is never a question of which prefix is in force.
-- The single row is written by db.seed(), not here: schema/*.sql is DDL only,
-- and the translator refuses a statement it does not recognise rather than
-- guessing what a seed INSERT should become on SQL Server.
CREATE TABLE ticket_numbering (
  id       INTEGER PRIMARY KEY CHECK (id = 1),
  prefix   TEXT NOT NULL DEFAULT 'PMC',
  -- Zero padding, so PMC-000001 sorts as text in the order it was issued for
  -- the first million tickets. Twelve is well past any hospital's lifetime.
  padding  INTEGER NOT NULL CHECK (padding BETWEEN 1 AND 12)
);

-- The sequence itself. Append-only: a row is written when a number is ISSUED,
-- never deleted, so a number is never reused. A reused ticket number is a
-- reference that points at two different tickets, which is worse than a gap —
-- and gaps are fine. `issued_to` is filled in once the ticket exists, so a
-- number issued and then abandoned is visible as exactly that rather than
-- silently vanishing.
CREATE TABLE ticket_number (
  number     INTEGER PRIMARY KEY,
  issued_at  TEXT NOT NULL,
  issued_to  TEXT REFERENCES ticket(work_item_id)
);
