-- PSA spine 005 — the ticket, and the gate that was the blocking gap
--
-- A ticket IS a work item. 003 anticipated this: work_item.work_item_id is
-- documented as "'WS23', later 'ITO-1723'" and work_item.source allows 'desk'.
-- So time_entry already hangs off a ticket without a line of new code, and the
-- effort on a ticket can reach a variation the same way a workstream's does.
--
-- This file adds only what a ticket has that a workstream does not: a board, a
-- catalogue item, the two answers a requester gives, and the clocks.

PRAGMA foreign_keys = ON;

CREATE TABLE ticket (
  work_item_id      TEXT PRIMARY KEY REFERENCES work_item(work_item_id),
  external_ref      TEXT,                  -- what the desk calls it, kept verbatim
  board_id          TEXT NOT NULL REFERENCES board(board_id),
  catalogue_item_id TEXT REFERENCES catalogue_item(catalogue_item_id),

  -- Three paths, not two. The workbook's two-board line collapses in-baseline
  -- fulfilment with fee-bearing variation: its own Request list contains
  -- "Onboard new user", "New Shared Mailbox" and "Create security group", which
  -- sit squarely inside baseline items 2 and 4 [MEASURED]. Two boards make
  -- every new-user request look like a fee event, and that destroys PMC's
  -- willingness to use the request path at all.
  path              TEXT NOT NULL CHECK (path IN ('INCIDENT', 'SERVICE_REQUEST', 'VARIATION')),

  -- The requester answers two plain questions -- who is affected, and is a
  -- patient waiting -- and never sees a priority dropdown.
  impact            TEXT NOT NULL CHECK (impact IN ('I1', 'I2', 'I3')),
  urgency           TEXT NOT NULL CHECK (urgency IN ('U1', 'U2', 'U3')),
  priority          TEXT NOT NULL CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),
  priority_source   TEXT NOT NULL CHECK (priority_source IN
                      ('MATRIX', 'CATALOGUE_FLOOR', 'CLINICAL_IMPACT', 'CLINICAL_FLOOR', 'OVERRIDE')),

  requested_by      TEXT,
  requested_at      TEXT NOT NULL,
  owner             TEXT,
  opened_at         TEXT NOT NULL,
  closed_at         TEXT,
  -- A pause state that stops the resolve clock. Without one, eleven of the
  -- thirty-five register rows report as a breach on day one.
  paused_minutes    INTEGER NOT NULL DEFAULT 0 CHECK (paused_minutes >= 0),
  state             TEXT NOT NULL CHECK (state IN
                      ('NEW','TRIAGED','IN_PROGRESS','WAITING_CLIENT','WAITING_VENDOR','RESOLVED','CLOSED','CANCELLED')),
  source_ref        TEXT,                  -- the export row this came from
  note              TEXT
);

-- Append-only. A ticket's history is evidence; it is never edited in place.
CREATE TABLE ticket_event (
  ticket_event_id INTEGER PRIMARY KEY,
  work_item_id    TEXT NOT NULL REFERENCES ticket(work_item_id),
  occurred_at     TEXT NOT NULL,
  kind            TEXT NOT NULL,
  actor           TEXT,
  detail          TEXT
);

-- Cross-board handover is ONE ticket with a changing owner, never two linked
-- tickets. The MRI-to-PACS fault is simultaneously biomedical (the scanner) and
-- IT (DICOM, AE title, network); two tickets each waiting on the other is
-- exactly what produced a twenty-five day outage.
CREATE TABLE ticket_handover (
  handover_id   INTEGER PRIMARY KEY,
  work_item_id  TEXT NOT NULL REFERENCES ticket(work_item_id),
  from_board_id TEXT REFERENCES board(board_id),
  to_board_id   TEXT NOT NULL REFERENCES board(board_id),
  handover_at   TEXT NOT NULL,
  from_owner    TEXT,
  to_owner      TEXT,
  reason        TEXT,
  CHECK (from_board_id IS NULL OR from_board_id <> to_board_id)
);

-- Lowering a priority below a clinical floor takes a named clinical escalation
-- role, a typed reason, and an audit event. Not a fulfiller's judgement call.
CREATE TABLE priority_override (
  override_id     INTEGER PRIMARY KEY,
  work_item_id    TEXT NOT NULL REFERENCES ticket(work_item_id),
  overridden_at   TEXT NOT NULL,
  was_priority    TEXT NOT NULL,
  now_priority    TEXT NOT NULL,
  escalation_role TEXT NOT NULL CHECK (escalation_role IN
                    ('NURSING_SUPERVISOR', 'DUTY_MANAGER', 'CHIEF_OF_HOSPITAL', 'QUALITY_OFFICER')),
  reason          TEXT NOT NULL,
  CHECK (length(trim(reason)) >= 15)       -- a typed reason, not a keystroke
);

-- ------------------------------------------------------------------ the gate
--
-- THIS is the blocking gap the spine was missing. Effort could be banded
-- against the thirty-five workstreams but not against tickets, so a
-- hospital-wide uplift claim could not be evidenced from ticket effort.
--
-- A variation-path ticket must be attached to a variation before it can consume
-- effort. Enforced here rather than in the importer, because an importer can be
-- bypassed and a trigger cannot: the moment somebody logs time against
-- unapproved out-of-scope work, the database refuses it and the work stays
-- visible as work nobody has agreed to pay for.

CREATE TRIGGER time_entry_requires_a_variation
BEFORE INSERT ON time_entry
FOR EACH ROW
WHEN EXISTS (
  SELECT 1 FROM ticket t
    JOIN work_item w ON w.work_item_id = t.work_item_id
   WHERE t.work_item_id = NEW.work_item_id
     AND t.path = 'VARIATION'
     AND w.variation_id IS NULL)
BEGIN
  SELECT RAISE(ABORT,
    'a variation-path ticket must be attached to a variation before it can consume effort');
END;

-- The same rule at close: a variation ticket cannot be resolved while the work
-- it did has no commercial home.
CREATE TRIGGER ticket_close_requires_a_variation
BEFORE UPDATE OF state ON ticket
FOR EACH ROW
WHEN NEW.state IN ('RESOLVED', 'CLOSED')
 AND NEW.path = 'VARIATION'
 AND (SELECT variation_id FROM work_item WHERE work_item_id = NEW.work_item_id) IS NULL
BEGIN
  SELECT RAISE(ABORT,
    'a variation-path ticket cannot be closed with no variation attached');
END;
