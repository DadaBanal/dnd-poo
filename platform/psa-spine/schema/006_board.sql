-- PSA spine 006 — the board as configuration, not as a label
--
-- Until now `board` was seven columns and a note. That is a queue name. A board
-- in the sense the whole design rests on OWNS ITS VOCABULARY: its statuses, its
-- teams, who may see it, and the working week its clocks run against.
--
-- Shapes here follow ConnectWise's own entity model where it is better than what
-- was drafted, and the places it is better are recorded rather than quietly
-- copied. See docs/WS36-connectwise-model-20260909.md, extracted from
-- ConnectWise's published OpenAPI schemas.

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------ board_status
--
-- A status is not a string. If "Waiting for parts" is a name, nothing in the
-- system knows a clock should stop, and every pause becomes a special case
-- somebody codes by hand.
--
-- The design drafted three booleans -- stops_respond, stops_resolve, and one
-- more for the plan. ConnectWise carries ONE field instead, and it is better:
-- the status declares WHICH SLA MILESTONE IT REPRESENTS and the clock engine
-- derives the rest. NO_ESCALATION is the pause. Taken as-is, because inventing
-- a worse version of a solved problem is not craft.

CREATE TABLE board_status (
  board_status_id   TEXT PRIMARY KEY,      -- 'IT_HELP.IN_PROGRESS'
  board_id          TEXT NOT NULL REFERENCES board(board_id),
  name              TEXT NOT NULL,         -- what a fulfiller reads
  -- What a REQUESTER reads, which is a different sentence. Internally
  -- "Awaiting parts from vendor, PO raised"; on the portal "We are waiting on a
  -- delivery". Without this you either leak internal language to 400 clinical
  -- staff or you write statuses too vague to be useful to the people working.
  customer_description TEXT,
  escalation_status TEXT NOT NULL CHECK (escalation_status IN
                      ('NOT_RESPONDED','RESPONDED','RESOLUTION_PLAN','RESOLVED',
                       'NO_ESCALATION')),
  is_default        INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
  is_closed         INTEGER NOT NULL DEFAULT 0 CHECK (is_closed IN (0, 1)),
  -- A status that forbids booking effort. This is how time stops accruing
  -- against a parked ticket, and it composes with the variation gate in 005
  -- rather than duplicating it.
  time_entry_allowed INTEGER NOT NULL DEFAULT 1 CHECK (time_entry_allowed IN (0, 1)),
  display_on_board  INTEGER NOT NULL DEFAULT 1 CHECK (display_on_board IN (0, 1)),
  sort_order        INTEGER NOT NULL DEFAULT 0,
  -- Retired, never deleted. ConnectWise refuses to delete a board once anything
  -- references it, and the same is true of a status: the tickets that sat in it
  -- are evidence.
  inactive          INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1)),
  UNIQUE (board_id, name),
  -- A new ticket must not land already closed. The default status is where
  -- work starts, so it cannot also be where work ends.
  CHECK (is_default = 0 OR is_closed = 0)
);

-- ------------------------------------------------------------- board_role
--
-- Owner and deputy is too thin, and the record already shows why: triage today
-- is one person, and when she is unavailable the path is a personal chat to a
-- CIO in another country [MEASURED]. Two names cannot express "who answers at
-- 02:00, and who answers when they do not".
--
-- ConnectWise carries four per board -- dispatchMember, dutyManagerMember,
-- oncallMember, serviceManagerMember -- and documents the duty manager as
-- "backup for the on-call member ... if the on-call member does not respond to
-- the ticket within the specified time." That is the escalation chain a hospital
-- needs, and DUTY_MANAGER is already a clinical escalation role on
-- priority_override in 005, so the vocabularies converge for free.
--
-- board.owner and board.deputy stay for now: they are seeded, tested, and the
-- is_live CHECK depends on them. This table is the model going forward, and the
-- CHECK moves here when boards are created through it rather than seeded.

CREATE TABLE board_role (
  board_id  TEXT NOT NULL REFERENCES board(board_id),
  role      TEXT NOT NULL CHECK (role IN
              ('SERVICE_MANAGER','DISPATCH','ON_CALL','DUTY_MANAGER')),
  member    TEXT NOT NULL,                 -- a named person, never a role name
  PRIMARY KEY (board_id, role)
);

-- --------------------------------------------------------------- the teams

CREATE TABLE board_team (
  team_id      TEXT PRIMARY KEY,
  board_id     TEXT NOT NULL REFERENCES board(board_id),
  name         TEXT NOT NULL,
  team_leader  TEXT,                       -- who the queue falls to unassigned
  is_default   INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
  UNIQUE (board_id, name)
);

-- Membership is the access control on a restricted board, not a hint to the
-- interface. Every read path filters by this at the query, and the acceptance
-- test the record wrote for the incumbent and never ran -- can a departmental
-- fulfiller be PROVABLY excluded from a PHI-bearing board -- is answered here.
CREATE TABLE board_member (
  board_id  TEXT NOT NULL REFERENCES board(board_id),
  member    TEXT NOT NULL,
  team_id   TEXT REFERENCES board_team(team_id),
  access    TEXT NOT NULL CHECK (access IN ('READ', 'WORK', 'ADMIN')),
  PRIMARY KEY (board_id, member)
);

-- ------------------------------------------------------ the working week
--
-- The design said two calendars, CLINICAL_24x7 and MANILA_BUSINESS, as fixed
-- values. That breaks the first time a board needs a ward roster or a supplier's
-- support window. ConnectWise lets an SLA run on a company calendar, a customer
-- site calendar, 24x7, or a custom one -- so a calendar is a TABLE.
--
-- Philippine public holidays are rows, not code. PMC's holidays are not
-- Melbourne's, and an SLA that breaches on Bonifacio Day because the calendar
-- was compiled in is a report nobody trusts twice.

CREATE TABLE holiday_list (
  holiday_list_id TEXT PRIMARY KEY,
  name            TEXT NOT NULL
);

CREATE TABLE holiday (
  holiday_list_id TEXT NOT NULL REFERENCES holiday_list(holiday_list_id),
  observed_on     TEXT NOT NULL,           -- as the source wrote it; see the port
  name            TEXT NOT NULL,
  PRIMARY KEY (holiday_list_id, observed_on)
);

-- A NULL start or end means the calendar is closed that day. 24x7 is
-- '00:00'..'24:00' on all seven, which is a row rather than a special case.
CREATE TABLE calendar (
  calendar_id     TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  monday_start    TEXT,
  monday_end      TEXT,
  tuesday_start   TEXT,
  tuesday_end     TEXT,
  wednesday_start TEXT,
  wednesday_end   TEXT,
  thursday_start  TEXT,
  thursday_end    TEXT,
  friday_start    TEXT,
  friday_end      TEXT,
  saturday_start  TEXT,
  saturday_end    TEXT,
  sunday_start    TEXT,
  sunday_end      TEXT,
  holiday_list_id TEXT REFERENCES holiday_list(holiday_list_id)
);
