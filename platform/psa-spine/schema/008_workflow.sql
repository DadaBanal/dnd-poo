-- PSA spine 008 — the rules engine, as rows
--
-- "It has multiple rules in it" was the requirement, and this is the part most
-- likely to be under-built, because the easy version is a handful of `if`
-- statements in the application. That version cannot be changed without a
-- deployment, cannot be audited, and cannot be explained to an inspector.
--
-- So a rule is DATA. PMC edits it; nobody ships a release.
--
-- The shape follows ConnectWise's, which splits across four entities, because
-- two of the parts are ones the draft design did not have and both are load
-- bearing:
--
--   * AN EXECUTION POLICY. Firing once is not enough. "Page IT every thirty
--     minutes until somebody owns this, up to four times" is exactly the
--     Unrouted ageing rule the record calls for -- triage today is one person,
--     and when she is unavailable the path is a personal chat to a CIO in
--     another country [MEASURED]. Without a policy the rule either nags for
--     ever or fires once into an empty room.
--
--   * A CONDITION VOCABULARY THAT IS ITSELF DATA. `workflow_trigger` lists the
--     fields a condition may read and the type of each. The engine therefore
--     never evaluates an arbitrary expression -- there is no expression
--     language here, and nothing is ever passed to eval -- while PMC can still
--     build a condition without a developer. That is decision D5, answered.
--
-- `workflow_run` is ours, not ConnectWise's. A rules engine you cannot audit is
-- a system nobody can explain, and in a hospital that is the whole ballgame.

PRAGMA foreign_keys = ON;

CREATE TABLE workflow (
  workflow_id  TEXT PRIMARY KEY,
  -- NULL means global. A rule that pages on a clinical P1 should not have to be
  -- copied onto fourteen boards.
  board_id     TEXT REFERENCES board(board_id),
  name         TEXT NOT NULL,
  table_type   TEXT NOT NULL CHECK (table_type IN
                 ('TICKET','WORK_ITEM','TIME_ENTRY','VARIATION')),
  -- Off by default. A rule nobody has read should not be running.
  is_active    INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1)),
  -- Time-based rules are first class, not an afterthought. And the schedule can
  -- run on SLA HOURS rather than wall clock: a rule that escalates at 80% of a
  -- target must be evaluated on the same calendar the target uses, or it fires
  -- at the wrong time on a public holiday.
  batch_interval       INTEGER,
  batch_frequency_unit TEXT CHECK (batch_frequency_unit IN
                         ('MINUTES','HOURS','DAYS') OR batch_frequency_unit IS NULL),
  batch_schedule       TEXT CHECK (batch_schedule IN
                         ('ANY_TIME','BUSINESS_HOURS','SLA_HOURS') OR batch_schedule IS NULL),
  sort_order   INTEGER NOT NULL DEFAULT 0,
  note         TEXT
);

CREATE TABLE workflow_event (
  event_id     TEXT PRIMARY KEY,
  workflow_id  TEXT NOT NULL REFERENCES workflow(workflow_id),
  name         TEXT,
  fires_on     TEXT NOT NULL CHECK (fires_on IN
                 ('ON_CREATE','ON_STATUS_CHANGE','ON_OWNER_CHANGE','ON_NOTE_ADDED',
                  'ON_HANDOVER','ON_SCHEDULE','ON_SLA_THRESHOLD')),
  execution_time TEXT NOT NULL DEFAULT 'ONCE' CHECK (execution_time IN
                 ('ONCE','MULTIPLE_TIMES','CONTINUOUSLY')),
  frequency      INTEGER,
  frequency_unit TEXT CHECK (frequency_unit IN
                   ('MINUTES','HOURS','DAYS') OR frequency_unit IS NULL),
  max_executions INTEGER,
  -- A repeating rule with no interval repeats as fast as the loop runs, which is
  -- how a notification rule becomes an outage.
  CHECK (execution_time = 'ONCE'
         OR (frequency IS NOT NULL AND frequency > 0 AND frequency_unit IS NOT NULL)),
  -- MULTIPLE_TIMES without a cap is CONTINUOUSLY wearing a different name. If
  -- you mean for ever, say CONTINUOUSLY and mean it.
  CHECK (execution_time <> 'MULTIPLE_TIMES'
         OR (max_executions IS NOT NULL AND max_executions > 0))
);

-- ----------------------------------------------------- the condition vocabulary
--
-- Which fields a rule may look at, and what kind of value each holds. Rows, so
-- adding a field a rule can test is a row rather than a release.

CREATE TABLE workflow_trigger (
  trigger_id    TEXT PRIMARY KEY,          -- 'TICKET.PRIORITY'
  table_type    TEXT NOT NULL CHECK (table_type IN
                  ('TICKET','WORK_ITEM','TIME_ENTRY','VARIATION')),
  field         TEXT NOT NULL,             -- the column the engine reads
  display_name  TEXT NOT NULL,             -- what an administrator sees
  value_type    TEXT NOT NULL CHECK (value_type IN
                  ('TEXT','NUMBER','CODE','DATE','BOOLEAN')),
  -- Where the option list comes from, when there is one. NULL means free entry.
  option_source TEXT,
  UNIQUE (table_type, field)
);

CREATE TABLE workflow_condition (
  condition_id INTEGER PRIMARY KEY,
  event_id     TEXT NOT NULL REFERENCES workflow_event(event_id),
  trigger_id   TEXT NOT NULL REFERENCES workflow_trigger(trigger_id),
  operator     TEXT NOT NULL CHECK (operator IN
                 ('EQ','NE','IN','NOT_IN','LT','LTE','GT','GTE',
                  'IS_NULL','IS_NOT_NULL','CONTAINS')),
  value        TEXT,
  conjunction  TEXT NOT NULL DEFAULT 'AND' CHECK (conjunction IN ('AND','OR')),
  sort_order   INTEGER NOT NULL DEFAULT 0,
  -- Every operator except the null tests needs something to compare against.
  CHECK (operator IN ('IS_NULL','IS_NOT_NULL') OR value IS NOT NULL)
);

-- ------------------------------------------------------------------ actions

CREATE TABLE workflow_action (
  action_id    INTEGER PRIMARY KEY,
  event_id     TEXT NOT NULL REFERENCES workflow_event(event_id),
  action       TEXT NOT NULL CHECK (action IN
                 ('SET_STATUS','SET_BOARD','ASSIGN_TEAM','ASSIGN_OWNER','NOTIFY',
                  'ESCALATE','ADD_NOTE','FLAG','REQUIRE_APPROVAL','APPLY_TEMPLATE')),
  -- Who a NOTIFY or ESCALATE reaches. A board role rather than a name, so the
  -- rule survives somebody leaving.
  notify_role  TEXT CHECK (notify_role IN
                 ('SERVICE_MANAGER','DISPATCH','ON_CALL','DUTY_MANAGER',
                  'TEAM_LEADER','OWNER','REQUESTER') OR notify_role IS NULL),
  target_board_id  TEXT REFERENCES board(board_id),
  target_status_id TEXT REFERENCES board_status(board_status_id),
  target_team_id   TEXT REFERENCES board_team(team_id),
  target_member    TEXT,
  detail       TEXT,
  sort_order   INTEGER NOT NULL DEFAULT 0,
  -- A notification with nobody to notify is a rule that silently does nothing,
  -- which is worse than a rule that fails.
  CHECK (action NOT IN ('NOTIFY','ESCALATE')
         OR notify_role IS NOT NULL OR target_member IS NOT NULL)
);

-- --------------------------------------------------------------- the record
--
-- Append-only, and every firing writes here whether it acted or not. "Why did
-- nobody get paged" and "why did this page four times" are both questions with
-- an answer, and both get asked after the incident rather than before.

CREATE TABLE workflow_run (
  run_id           INTEGER PRIMARY KEY,
  event_id         TEXT NOT NULL REFERENCES workflow_event(event_id),
  work_item_id     TEXT,
  occurred_at      TEXT NOT NULL,
  execution_number INTEGER NOT NULL DEFAULT 1,
  outcome          TEXT NOT NULL CHECK (outcome IN
                     ('MATCHED','NOT_MATCHED','ACTED','SUPPRESSED','ERROR')),
  detail           TEXT
);

CREATE INDEX ix_workflow_run_event ON workflow_run (event_id, work_item_id);
