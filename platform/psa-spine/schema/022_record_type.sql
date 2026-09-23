-- 022 — ITIL record types: what kind of work a ticket is, apart from who pays.
--
-- Dada's direction (23 Sep 2026): boards are not split into "issues" and
-- "requests"; the model follows ITIL. The evidence for how:
--
--   * ConnectWise's own "Service Type Examples" workbook (ConnectWise University
--     content, ITIL Example sheet) uses exactly four Types on a service board:
--     Event, Incident, Problem, Request. Dada's workbook column A is the same
--     four. In ConnectWise the ITIL class is a per-board Type, not a board, and
--     change is a "Request for Change" flag on a Type (VERIFIED 23 Sep 2026,
--     cw-www.s3.us-east-1.amazonaws.com/university/content/User_Documents/
--     ServiceTypeExamplesPSA.xlsx; docs.connectwise.com/ConnectWise_Documentation/
--     090/020/170/100/020).
--   * ConnectWise's service board guidance divides boards by team and workflow,
--     not by ITIL class (VERIFIED, docs.connectwise.com/ConnectWise_Documentation/
--     090/020/170/100). Projects run on project boards (projectFlag).
--
-- So every service board takes incidents, service requests, problems and events;
-- a board whose workflow differs (change control, projects) is its own board.
-- Which types a board takes is a row per board, not code, so either of Dada's two
-- phrasings is configuration.
--
-- ticket.path keeps its meaning from 005 and its gate triggers are unchanged:
-- 'VARIATION' when the work is a fee-bearing variation, and otherwise the
-- record type's side of ConnectWise's Reactive/Proactive split (INCIDENT,
-- PROBLEM, EVENT -> 'INCIDENT'; SERVICE_REQUEST, CHANGE, PROJECT ->
-- 'SERVICE_REQUEST'). It is derived in one place (tickets.derive_path), never
-- passed in. An ITIL change is NOT a commercial variation: a change can be in
-- baseline, and a variation can be any record type.
--
-- No column here has a DEFAULT and nothing is back-filled. SQL Server stores NULL
-- in existing rows for a new nullable column with a default, SQLite reads the
-- default: the two engines would disagree about every ticket that already
-- exists (the 018 precedent). A NULL record type reads "not set".
PRAGMA foreign_keys = ON;

ALTER TABLE ticket ADD COLUMN record_type TEXT
  CHECK (record_type IN ('INCIDENT', 'SERVICE_REQUEST', 'PROBLEM', 'EVENT', 'CHANGE', 'PROJECT'));

-- A catalogue item can say what it is; blank means "from the action's kind"
-- (FAULT -> INCIDENT, REQUEST -> SERVICE_REQUEST).
ALTER TABLE catalogue_item ADD COLUMN record_type TEXT
  CHECK (record_type IN ('INCIDENT', 'SERVICE_REQUEST', 'PROBLEM', 'EVENT', 'CHANGE', 'PROJECT'));

-- Which record types a board takes. A board with no rows takes every type, so a
-- board set up before this migration behaves as it did.
CREATE TABLE board_record_type (
  board_id    TEXT NOT NULL REFERENCES board(board_id),
  record_type TEXT NOT NULL CHECK (record_type IN
                ('INCIDENT', 'SERVICE_REQUEST', 'PROBLEM', 'EVENT', 'CHANGE', 'PROJECT')),
  is_default  INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
  PRIMARY KEY (board_id, record_type)
);

-- SLA targets for one record type on a board. ITIL measures a service request
-- by its fulfilment time, not an incident's restore time, and Dada's workbook
-- had separate numbers for the two ("respond within 2 h" for Help, "within 1
-- day" for Request). Merging the boards must not merge those numbers, so a
-- ticket takes its record type's targets where they exist and the board's
-- general ones (sla_target) where they do not.
CREATE TABLE sla_target_type (
  board_id           TEXT NOT NULL REFERENCES board(board_id),
  record_type        TEXT NOT NULL CHECK (record_type IN
                       ('INCIDENT', 'SERVICE_REQUEST', 'PROBLEM', 'EVENT', 'CHANGE', 'PROJECT')),
  priority           TEXT NOT NULL CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),
  clock              TEXT NOT NULL CHECK (clock IN
                       ('RESPOND', 'RESOLUTION_PLAN', 'RESOLVE', 'ACKNOWLEDGE', 'DECISION')),
  target_minutes     INTEGER NOT NULL CHECK (target_minutes > 0),
  calendar           TEXT NOT NULL CHECK (calendar IN ('CLINICAL_24x7', 'MANILA_BUSINESS')),
  attainment_percent REAL,
  enforced           INTEGER NOT NULL DEFAULT 0 CHECK (enforced IN (0, 1)),
  note               TEXT,
  PRIMARY KEY (board_id, record_type, priority, clock)
);

-- ------------------------------------------------------------ change enablement
--
-- ITIL 4 names three types of change, and ConnectWise's Service Transition page
-- uses the same three (VERIFIED, docs.connectwise.com/ConnectWise_Business_
-- Knowledge/110/030): STANDARD is pre-authorised and needs no approval; NORMAL
-- is authorised by a change authority before it is built; EMERGENCY goes ahead
-- at once and is authorised as soon as it can be, afterwards. ConnectWise's
-- ticket has no change fields (only Ticket.approved), so these are the spine's
-- own, named as such.
ALTER TABLE ticket ADD COLUMN change_type TEXT
  CHECK (change_type IN ('STANDARD', 'NORMAL', 'EMERGENCY'));
ALTER TABLE ticket ADD COLUMN change_risk TEXT
  CHECK (change_risk IN ('LOW', 'MEDIUM', 'HIGH'));
ALTER TABLE ticket ADD COLUMN planned_start TEXT;       -- the implementation window
ALTER TABLE ticket ADD COLUMN planned_end TEXT;
ALTER TABLE ticket ADD COLUMN backout_plan TEXT;        -- how it is undone if it fails

-- A status a change may enter only once it is authorised (Approved, Scheduled,
-- Implementing). NULL or 0: no gate. The engine enforces it; see board.change_status.
ALTER TABLE board_status ADD COLUMN requires_approval INTEGER
  CHECK (requires_approval IN (0, 1));

-- The authorisation record. Append-only: a decision is evidence, and a later
-- decision is a new row, never an edit. The person who owns the change cannot
-- authorise it (separation of duties; enforced in board.decide_change).
CREATE TABLE change_approval (
  approval_id  INTEGER PRIMARY KEY,
  work_item_id TEXT NOT NULL REFERENCES ticket(work_item_id),
  decided_by   TEXT NOT NULL,
  authority    TEXT NOT NULL CHECK (authority IN ('CHANGE_AUTHORITY', 'CAB', 'ECAB', 'CLIENT')),
  decision     TEXT NOT NULL CHECK (decision IN ('APPROVED', 'DECLINED')),
  decided_at   TEXT NOT NULL,
  comment      TEXT
);

CREATE INDEX ix_change_approval_ticket ON change_approval (work_item_id);

-- ------------------------------------------------ incident -> problem -> change
--
-- ITIL's chain: incidents are linked to the problem that causes them, and a
-- problem (or anything else) to the change that fixes it. ConnectWise does this
-- by bundling child tickets under a parent, which stops workflow and billing on
-- the children and is a known cause of SLA reports running for years on open
-- children (VERIFIED, visionary360.com/the-hidden-sla-killer-in-connectwise-psa-
-- child-merged-tickets/). A link here changes neither ticket: each keeps its
-- own clocks, status and time.
--
-- This is not handover. One fault worked by two teams is still ONE ticket that
-- moves (005, board.move): two tickets each waiting on the other is what produced
-- the twenty-five day MRI-to-PACS outage. A link joins two different pieces of
-- work, such as twelve incidents and the one problem behind them.
CREATE TABLE ticket_link (
  work_item_id TEXT NOT NULL REFERENCES ticket(work_item_id),
  linked_id    TEXT NOT NULL REFERENCES ticket(work_item_id),
  relation     TEXT NOT NULL CHECK (relation IN ('CAUSED_BY', 'FIXED_BY', 'RELATED')),
  linked_at    TEXT NOT NULL,
  linked_by    TEXT NOT NULL,
  PRIMARY KEY (work_item_id, linked_id)
);
