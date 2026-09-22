-- PSA spine 004 — the service catalogue
--
-- Five tables, not a per-board tree. ConnectWise scopes Types and SubTypes per
-- board [VERIFIED, docs.connectwise.com: System > Setup Tables > Service Boards >
-- [board] > Types]; at fourteen hospital boards that is fourteen maintenance
-- surfaces for one tree. A defect to avoid, not a pattern to copy. So the verb
-- set is shared across every board and the tree is curated triples.
--
-- Every name here carries a stable machine id separate from what an executive
-- reads, because the source workbook contains ten misspellings and WS07 already
-- paid once to remediate 450 label defects that reached a report.

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------------- boards
--
-- One accountable fulfiller group, one named owner, one named deputy, its own
-- SLA. A board with no owner is worse than no board -- so a board may be
-- RECORDED without one, and may not be LIVE without one. That is the rule as a
-- constraint rather than as a paragraph somebody has to remember.

CREATE TABLE board (
  board_id        TEXT PRIMARY KEY,        -- 'IT_HELP'
  display_name    TEXT NOT NULL,
  phase           TEXT NOT NULL CHECK (phase IN ('2','3a','3b')),
  fulfiller_group TEXT NOT NULL,
  owner           TEXT,                    -- a named person, not a role
  deputy          TEXT,
  restricted      INTEGER NOT NULL DEFAULT 0 CHECK (restricted IN (0, 1)),
  is_live         INTEGER NOT NULL DEFAULT 0 CHECK (is_live IN (0, 1)),
  is_unrouted     INTEGER NOT NULL DEFAULT 0 CHECK (is_unrouted IN (0, 1)),
  -- Closing a ticket on this board goes through the closed loop: the answer to
  -- the requester and the banding of the effort are one action, so the effort is
  -- captured by construction and not by a fulfiller remembering to. Off by
  -- default; a board turns it on when it is ready to be measured that way.
  closed_loop_required INTEGER NOT NULL DEFAULT 0 CHECK (closed_loop_required IN (0, 1)),
  note            TEXT,
  CHECK (is_live = 0 OR (owner IS NOT NULL AND deputy IS NOT NULL))
);

-- --------------------------------------------------------------- the tree
--
-- family -> component, and a verb set that belongs to no board.

CREATE TABLE service_family (
  family_id     TEXT PRIMARY KEY,          -- 'SERVERS_STORAGE'
  display_name  TEXT NOT NULL,
  raw_name      TEXT,                      -- as the source workbook spelt it
  note          TEXT
);

CREATE TABLE service_component (
  component_id  TEXT PRIMARY KEY,
  family_id     TEXT NOT NULL REFERENCES service_family(family_id),
  display_name  TEXT NOT NULL,
  raw_name      TEXT,
  is_draft      INTEGER NOT NULL DEFAULT 0 CHECK (is_draft IN (0, 1)),
  note          TEXT
);

-- The verbs. The workbook's Item column is a hand-written cross-join of these
-- against ~100 components with drifting case; they are normalised once, here.
--
-- The recommendation says "six canonical verbs" while its own rulings enumerate
-- seven. The seed carries the seven that are enumerated and the discrepancy is
-- recorded rather than resolved by picking one quietly.
--
-- The load-bearing definition, kept verbatim from the workbook's margin:
--   outage  = a shared service or a clinical service is down   (impact I1)
--   failure = one device or one user                           (impact I3)
CREATE TABLE service_action (
  action_id     TEXT PRIMARY KEY,          -- 'OUTAGE'
  display_name  TEXT NOT NULL,
  raw_name      TEXT,                      -- as the source workbook spelt it
  kind          TEXT NOT NULL CHECK (kind IN ('REQUEST', 'FAULT')),
  implies_impact TEXT CHECK (implies_impact IN ('I1', 'I2', 'I3') OR implies_impact IS NULL),
  note          TEXT
);

-- ----------------------------------------------------------- curated triples
--
-- Defaulting the scope item and the contract basis from the catalogue is what
-- lets a nurse file a ticket without ever seeing a commercial field. Which is
-- also why an item that claims to be baseline must name the baseline item it
-- sits in: "baseline, but we cannot say under which heading" is not a defence.

CREATE TABLE catalogue_item (
  catalogue_item_id     TEXT PRIMARY KEY,
  component_id          TEXT NOT NULL REFERENCES service_component(component_id),
  action_id             TEXT NOT NULL REFERENCES service_action(action_id),
  default_board_id      TEXT NOT NULL REFERENCES board(board_id),
  default_scope_item_id TEXT REFERENCES scope_item(scope_item_id),
  default_contract_basis TEXT NOT NULL CHECK (default_contract_basis IN
                          ('BASELINE', 'VARIATION', 'UNKNOWN')),
  clinical_impact       INTEGER NOT NULL DEFAULT 0 CHECK (clinical_impact IN (0, 1)),
  min_priority          TEXT CHECK (min_priority IN ('P1','P2','P3','P4') OR min_priority IS NULL),
  restricted            INTEGER NOT NULL DEFAULT 0 CHECK (restricted IN (0, 1)),
  is_draft              INTEGER NOT NULL DEFAULT 0 CHECK (is_draft IN (0, 1)),
  note                  TEXT,
  UNIQUE (component_id, action_id),
  CHECK (default_contract_basis <> 'BASELINE' OR default_scope_item_id IS NOT NULL)
);

-- -------------------------------------------------------------- clinical floors
--
-- Priorities no fulfiller may lower, enforced at raise AND at close. This list
-- is signed off by the Chief of Hospital, the Chief Nurse and the Quality
-- officer -- not by Dada IT. So a floor that nobody has signed is PROPOSED and
-- does not bind, and the schema will not let it claim otherwise.

CREATE TABLE clinical_floor (
  floor_id      TEXT PRIMARY KEY,
  description   TEXT NOT NULL,
  priority      TEXT NOT NULL CHECK (priority IN ('P1', 'P2')),
  status        TEXT NOT NULL CHECK (status IN ('PROPOSED', 'SIGNED_OFF', 'WITHDRAWN')),
  signed_off_by TEXT,
  signed_off_on TEXT,
  CHECK (status <> 'SIGNED_OFF' OR (signed_off_by IS NOT NULL AND signed_off_on IS NOT NULL))
);

-- ------------------------------------------------------------------- the SLA
--
-- Three clocks, each with its own target, its own calendar and its own
-- attainment percentage, because the workbook's three numbers are
-- incommensurable as written: "response within 1 day" is a per-ticket target,
-- "90% within 2 hours" is a population percentile, "16 hours" has no calendar.
--
-- Every target ships with enforced = 0. The agreement contains no response or
-- resolution commitment and three clauses actively disclaim creating one
-- [MEASURED]. Turning enforcement on silently creates an obligation Dada IT is
-- not paid for and a two-to-three person team cannot meet.

CREATE TABLE sla_target (
  sla_target_id      INTEGER PRIMARY KEY,
  board_id           TEXT NOT NULL REFERENCES board(board_id),
  priority           TEXT NOT NULL CHECK (priority IN ('P1','P2','P3','P4')),
  clock              TEXT NOT NULL CHECK (clock IN
                       ('RESPOND','RESOLUTION_PLAN','RESOLVE','ACKNOWLEDGE','DECISION')),
  target_minutes     INTEGER NOT NULL,
  calendar           TEXT NOT NULL CHECK (calendar IN ('CLINICAL_24x7', 'MANILA_BUSINESS')),
  attainment_percent REAL,                 -- stated separately from the per-ticket target
  enforced           INTEGER NOT NULL DEFAULT 0 CHECK (enforced IN (0, 1)),
  note               TEXT,
  UNIQUE (board_id, priority, clock)
);
