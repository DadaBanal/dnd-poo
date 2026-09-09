-- PSA spine 001 — instruments, scope, entities
--
-- The spine exists because no PSA on the market models this contract: a fixed
-- monthly fee against nine numbered baseline scope items, with everything else
-- a named variation under Annex B. The ticket desk stays where it is; nothing
-- commercial is ever authoritative in the desk.
--
-- Portability: authored for SQLite (zero install, one file, escrowable) and
-- kept to constructs SQL Server also accepts, so the Azure SQL lift is a
-- migration and not a rewrite. NOT VERIFIED on SQL Server — see README.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- entities

CREATE TABLE entity (
  entity_id     TEXT PRIMARY KEY,          -- 'PMC', 'JRBY-CI', 'DADA-IT', 'UNCLASSIFIED'
  name          TEXT NOT NULL,
  is_covered    INTEGER NOT NULL DEFAULT 0 -- covered by an executed instrument?
                CHECK (is_covered IN (0, 1)),
  note          TEXT
);

CREATE TABLE site (
  site_id       TEXT PRIMARY KEY,          -- 'PH01', 'PH02', 'REMOTE-MEL'
  entity_id     TEXT NOT NULL REFERENCES entity(entity_id),
  name          TEXT NOT NULL
);

-- ---------------------------------------------------- agreement instruments
--
-- Three instruments are in circulation with three different clause-numbering
-- schemes, so a bare clause number is never stored against work. The clause
-- printed on a client-facing document is derived from whichever instrument was
-- in force on the work date.

CREATE TABLE instrument (
  instrument_id     TEXT PRIMARY KEY,
  kind              TEXT NOT NULL CHECK (kind IN ('AGREEMENT','AMENDMENT','CHANGE_ORDER','ANNEX')),
  title             TEXT NOT NULL,
  effective_from    TEXT,                  -- ISO date; NULL = not yet in force
  effective_to      TEXT,
  -- The execution gate turns on this column. DRAFT and SIGNED_ONE_PARTY are not
  -- a basis for invoicing; see fee_line and variation.
  execution_status  TEXT NOT NULL
                    CHECK (execution_status IN ('DRAFT','ISSUED','SIGNED_ONE_PARTY','EXECUTED')),
  signatory_pmc     TEXT,
  signatory_dadait  TEXT,
  signed_on         TEXT,
  prevails_over     TEXT REFERENCES instrument(instrument_id),
  -- Payment terms are per-instrument because two values are in circulation.
  payment_terms_days  INTEGER,
  payment_terms_basis TEXT CHECK (payment_terms_basis IN ('CALENDAR','BUSINESS')),
  dispute_window_days INTEGER,
  source_ref        TEXT,                  -- SharePoint item id, never a path string
  source_sha256     TEXT,
  note              TEXT
);

-- The nine baseline items, plus VAR for everything outside them.
CREATE TABLE scope_item (
  scope_item_id TEXT PRIMARY KEY,          -- '1'..'9', 'VAR'
  heading       TEXT NOT NULL,
  is_baseline   INTEGER NOT NULL CHECK (is_baseline IN (0, 1))
);

-- The same scope item is cited differently in each instrument.
CREATE TABLE instrument_scope_item (
  instrument_id TEXT NOT NULL REFERENCES instrument(instrument_id),
  scope_item_id TEXT NOT NULL REFERENCES scope_item(scope_item_id),
  clause_ref    TEXT,                      -- e.g. 'Section 2 item 3', 'cl.2.3'
  PRIMARY KEY (instrument_id, scope_item_id)
);

-- ------------------------------------------------------------- fee schedule
--
-- Effective-dated so a retrospective, pro-rated adjustment is an insert with a
-- recalculation trail, not an edit. Amounts are NOT seeded in this repository —
-- they are commercial figures and load from a data file held outside git.

CREATE TABLE fee_line (
  fee_line_id     INTEGER PRIMARY KEY,
  instrument_id   TEXT NOT NULL REFERENCES instrument(instrument_id),
  entity_id       TEXT NOT NULL REFERENCES entity(entity_id),
  description     TEXT NOT NULL,
  amount          REAL NOT NULL,
  currency        TEXT NOT NULL,
  period          TEXT NOT NULL CHECK (period IN ('MONTHLY','ONE_OFF','ANNUAL')),
  effective_from  TEXT NOT NULL,
  effective_to    TEXT,
  basis           TEXT NOT NULL
                  CHECK (basis IN ('BASELINE_FEE','CAPACITY_UPLIFT','SEPARATE_CHARGE','PASS_THROUGH')),
  variation_id    TEXT,                    -- set iff basis <> 'BASELINE_FEE'
  recalc_of       INTEGER REFERENCES fee_line(fee_line_id),
  entered_on      TEXT NOT NULL
);

CREATE INDEX ix_fee_line_effective ON fee_line (entity_id, effective_from);
