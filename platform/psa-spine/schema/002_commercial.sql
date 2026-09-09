-- PSA spine 002 — variations, notices, dependencies, reclassification
--
-- This is the half no PSA on the market ships, and the whole reason the spine
-- is built rather than bought.

PRAGMA foreign_keys = ON;

-- --------------------------------------------------------------- variations
--
-- A variation is a state machine, not a boolean. PERFORMED_WITHOUT_APPROVAL is
-- the commercially load-bearing state: work done on best efforts without waiver
-- of the right to additional fees. Off-the-shelf PSAs cannot express it, which
-- is why unbilled variation work currently disappears.

CREATE TABLE variation (
  variation_id    TEXT PRIMARY KEY,        -- 'VAR-0001'
  title           TEXT NOT NULL,
  entity_id       TEXT NOT NULL REFERENCES entity(entity_id),
  category        TEXT NOT NULL,           -- an Annex B category
  state           TEXT NOT NULL CHECK (state IN (
                    'IDENTIFIED','RECORDED_IN_ANNEX_B','NOTICED','PRICED','APPROVED','BILLED',
                    'DECLINED','PAUSED_PENDING_AUTHORISATION','PERFORMED_WITHOUT_APPROVAL')),
  pricing_method  TEXT CHECK (pricing_method IN
                    ('CAPACITY_UPLIFT','SEPARATE_CHARGE','PASS_THROUGH','DELIVERY_REBASELINE')),
  -- sustained_from is distinct from approved_on so a retrospective pro-rated
  -- adjustment can be evidenced from the date the load actually started.
  sustained_from  TEXT,
  approved_on     TEXT,
  eac_percent     REAL,                    -- effort-as-capacity %, the uplift numerator basis
  instrument_id   TEXT REFERENCES instrument(instrument_id),
  note            TEXT
);

-- Append-only. A variation's history is evidence; it is never edited in place.
CREATE TABLE variation_event (
  event_id      INTEGER PRIMARY KEY,
  variation_id  TEXT NOT NULL REFERENCES variation(variation_id),
  from_state    TEXT,
  to_state      TEXT NOT NULL,
  occurred_on   TEXT NOT NULL,
  actor         TEXT,
  reason        TEXT,
  evidence_ref  TEXT
);

-- ------------------------------------------------------------------ notices
--
-- Every commercially useful right in the agreement — pause, suspend, reclassify,
-- dependency relief, cure, exit — is conditioned on WRITTEN NOTICE. Eleven
-- workstreams are blocked on the client today and not one notice is recorded
-- against any of them. This table is worth more than the ticketing module.

CREATE TABLE notice (
  notice_id       TEXT PRIMARY KEY,        -- 'NOT-0001'
  kind            TEXT NOT NULL CHECK (kind IN
                    ('DEPENDENCY','VARIATION','RECLASSIFICATION','PAUSE','CURE','EXIT','EXCEPTION')),
  entity_id       TEXT NOT NULL REFERENCES entity(entity_id),
  issued_on       TEXT NOT NULL,
  issued_to       TEXT NOT NULL,
  subject         TEXT NOT NULL,
  body_ref        TEXT,                    -- SharePoint item id of the sent letter
  instrument_id   TEXT REFERENCES instrument(instrument_id),
  delivery_channel TEXT,
  receipt_evidence TEXT,
  variation_id    TEXT REFERENCES variation(variation_id),
  work_item_id    TEXT
);

-- ------------------------------------------------------- client dependencies
--
-- A blocked workstream is only a commercial event once notice has been given.
-- days_outstanding is derived at report time, never stored.

CREATE TABLE client_dependency (
  dependency_id   TEXT PRIMARY KEY,        -- 'DEP-0001'
  work_item_id    TEXT NOT NULL,
  entity_id       TEXT NOT NULL REFERENCES entity(entity_id),
  raised_on       TEXT NOT NULL,
  owner_name      TEXT,                    -- the party who owes the answer
  owner_department TEXT,
  description     TEXT NOT NULL,
  scope_item_id   TEXT REFERENCES scope_item(scope_item_id),
  impact          TEXT CHECK (impact IN ('TIMELINE','PRICING','BOTH')),
  notice_id       TEXT REFERENCES notice(notice_id),   -- NULL = relief not yet claimable
  resolved_on     TEXT
);

-- --------------------------------------------------------- reclassification
--
-- Basis changes are events, not edits, because the right to reclassify is
-- itself reserved in the agreement and has to be evidenced when exercised.

CREATE TABLE reclassification (
  reclass_id    INTEGER PRIMARY KEY,
  work_item_id  TEXT NOT NULL,
  old_basis     TEXT NOT NULL,
  new_basis     TEXT NOT NULL,
  changed_on    TEXT NOT NULL,
  changed_by    TEXT NOT NULL,
  reason        TEXT NOT NULL,
  instrument_id TEXT REFERENCES instrument(instrument_id),
  notice_id     TEXT REFERENCES notice(notice_id)
);

-- ----------------------------------------------------------- decision notes
--
-- The liability position depends on risk having been communicated in writing
-- BEFORE management decided. The constraint enforces the ordering, because a
-- decision note written afterwards is worth nothing.

CREATE TABLE decision_note (
  note_id       INTEGER PRIMARY KEY,
  entity_id     TEXT NOT NULL REFERENCES entity(entity_id),
  subject       TEXT NOT NULL,
  advisory_at   TEXT NOT NULL,
  decision_at   TEXT,
  advised_by    TEXT NOT NULL,
  decided_by    TEXT,
  outcome       TEXT,
  evidence_ref  TEXT,
  CHECK (decision_at IS NULL OR advisory_at <= decision_at)
);
