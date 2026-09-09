-- PSA spine 003 — work items, effort, documents, data quality, audit

PRAGMA foreign_keys = ON;

-- --------------------------------------------------------------- work items
--
-- One row per workstream today (the register), one row per ticket later. The
-- desk owns the ticket; the spine owns the money. contract_basis is set on the
-- work item and inherited by effort, never typed per time entry.

CREATE TABLE work_item (
  work_item_id    TEXT PRIMARY KEY,        -- 'WS23', later 'ITO-1723'
  source          TEXT NOT NULL,           -- 'register' | 'desk' | 'manual'
  name            TEXT NOT NULL,
  entity_id       TEXT REFERENCES entity(entity_id),
  entity_raw      TEXT,                    -- the source string, kept verbatim
  contract_basis  TEXT NOT NULL CHECK (contract_basis IN
                    ('BASELINE','VARIATION','UNKNOWN')),
  contract_basis_raw TEXT,                 -- e.g. 'variation (Amendment 1)', '?'
  variation_id    TEXT REFERENCES variation(variation_id),
  status          TEXT,
  status_raw      TEXT,
  blocked_on      TEXT,
  next_action     TEXT,
  next_action_by  TEXT,
  risk            TEXT CHECK (risk IN ('L','M','H') OR risk IS NULL),
  container       TEXT,
  last_activity   TEXT,
  parent_id       TEXT REFERENCES work_item(work_item_id),
  -- Lane is derived from status + blocked_on + next_action_by, because the
  -- programme is run by who has to act next, not by queue or priority.
  lane            TEXT
);

-- Many-to-many: the register carries compound scope values ('2->8', '3+5',
-- '1/2', '4/8'). Each becomes two links. A row is never dropped for being
-- compound, and never silently reduced to its first element.
CREATE TABLE work_item_scope_item (
  work_item_id  TEXT NOT NULL REFERENCES work_item(work_item_id),
  scope_item_id TEXT NOT NULL REFERENCES scope_item(scope_item_id),
  relation      TEXT NOT NULL DEFAULT 'PRIMARY'
                CHECK (relation IN ('PRIMARY','SECONDARY','SUCCEEDS','ALTERNATIVE')),
  raw           TEXT,                      -- the original cell, for audit
  PRIMARY KEY (work_item_id, scope_item_id, relation)
);

-- Append-only running record. The register's free-text next_action field is
-- thousands of characters of history in one cell; imported notes preserve it.
CREATE TABLE work_item_note (
  note_id       INTEGER PRIMARY KEY,
  work_item_id  TEXT NOT NULL REFERENCES work_item(work_item_id),
  noted_on      TEXT NOT NULL,
  author        TEXT,
  body          TEXT NOT NULL
);

CREATE TABLE work_item_evidence (
  work_item_id  TEXT NOT NULL REFERENCES work_item(work_item_id),
  ordinal       INTEGER NOT NULL,
  raw           TEXT NOT NULL,             -- verbatim from the register
  kind          TEXT NOT NULL CHECK (kind IN ('DOC','SCRIPT','DELIVERABLE','PATH','UNRESOLVED')),
  resolved_ref  TEXT,                      -- SharePoint item id once resolved
  PRIMARY KEY (work_item_id, ordinal)
);

-- -------------------------------------------------------------------- effort
--
-- Banded, not stopwatch. Baseline hours are never invoiced but are the
-- DENOMINATOR of any capacity uplift — without them every uplift is an
-- assertion. Only hours performed by Dada IT personnel count toward capacity;
-- client-employed fulfiller effort is recorded and excluded.

CREATE TABLE time_entry (
  time_entry_id INTEGER PRIMARY KEY,
  work_item_id  TEXT NOT NULL REFERENCES work_item(work_item_id),
  entity_id     TEXT NOT NULL REFERENCES entity(entity_id),
  site_id       TEXT REFERENCES site(site_id),
  worked_on     TEXT NOT NULL,
  band_hours    REAL NOT NULL,             -- 0.5 | 2 | 4 | 8 | 20
  performed_by  TEXT NOT NULL,
  entered_by    TEXT NOT NULL,
  counts_to_capacity INTEGER NOT NULL DEFAULT 1 CHECK (counts_to_capacity IN (0, 1)),
  after_hours   INTEGER NOT NULL DEFAULT 0 CHECK (after_hours IN (0, 1)),
  charge_method TEXT NOT NULL CHECK (charge_method IN
                  ('INCLUDED_IN_MONTHLY_FEE','CAPACITY_UPLIFT','SEPARATE_CHARGE',
                   'PASS_THROUGH','NON_CHARGEABLE')),
  review_category TEXT,                    -- one of the six-monthly review categories
  authority_source TEXT,                   -- who asked for it, and how
  note          TEXT
);

CREATE INDEX ix_time_entry_period ON time_entry (entity_id, worked_on);

-- The declared capacity a uplift percentage is computed against. Stored, dated
-- and offered for the client to initial — an undisclosed denominator is the
-- single easiest way for a finance function to reject an uplift invoice.
CREATE TABLE capacity_declaration (
  declaration_id  INTEGER PRIMARY KEY,
  effective_from  TEXT NOT NULL,
  effective_to    TEXT,
  hours_per_month REAL NOT NULL,
  basis           TEXT NOT NULL,
  agreed_by       TEXT,
  agreed_on       TEXT
);

-- ---------------------------------------------------------------- documents

CREATE TABLE document (
  document_id   TEXT PRIMARY KEY,
  title         TEXT NOT NULL,
  kind          TEXT NOT NULL,
  entity_id     TEXT REFERENCES entity(entity_id),
  dated         TEXT,
  source_ref    TEXT,                      -- SharePoint item id, never a path
  sha256        TEXT,
  state         TEXT NOT NULL DEFAULT 'CURRENT'
                CHECK (state IN ('DRAFT','CURRENT','SUPERSEDED','WITHDRAWN')),
  supersedes    TEXT REFERENCES document(document_id)
);

-- ------------------------------------------------------------- data quality
--
-- The standing rule in this programme is that flags are COUNTED, never filtered
-- out. Anything an import could not classify lands here and appears on every
-- report as a number. Nothing is ever silently dropped.

CREATE TABLE data_quality (
  finding_id    INTEGER PRIMARY KEY,
  run_id        TEXT NOT NULL,
  subject_kind  TEXT NOT NULL,             -- 'work_item', 'evidence', 'scope_item'
  subject_id    TEXT,
  code          TEXT NOT NULL,
  detail        TEXT NOT NULL,
  severity      TEXT NOT NULL CHECK (severity IN ('INFO','WARN','ERROR'))
);

-- -------------------------------------------------------------------- audit

CREATE TABLE audit_event (
  audit_id      INTEGER PRIMARY KEY,
  occurred_at   TEXT NOT NULL,
  actor         TEXT NOT NULL,
  action        TEXT NOT NULL,
  subject_kind  TEXT NOT NULL,
  subject_id    TEXT,
  detail        TEXT,
  override_reason TEXT                     -- set when an execution gate was overridden
);

CREATE TABLE import_run (
  run_id        TEXT PRIMARY KEY,
  started_at    TEXT NOT NULL,
  source        TEXT NOT NULL,
  source_sha256 TEXT,
  rows_in       INTEGER,
  rows_out      INTEGER,
  note          TEXT
);
