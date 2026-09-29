-- 052 — opportunities and quotes: the Sell-shaped slice.
--
-- Dada, 29 Sep: "we can add something like ConnectWise Sell if need be". A
-- hospital IT desk sells little, but it does propose: a new ward's cabling,
-- a licence renewal, a printer fleet. An opportunity is the proposal's
-- progress (a stage, a probability, an expected close, an amount, an owner);
-- a quote is what was offered, line by line, sent and then accepted or
-- declined. A won opportunity becomes an agreement (045), so the work that
-- follows is covered by it. Nothing here invoices: BizBox does that.
PRAGMA foreign_keys = ON;

CREATE TABLE opportunity (
  opportunity_id  TEXT PRIMARY KEY,                                  -- 'OPP-0001'
  name            TEXT NOT NULL,
  entity_id       TEXT REFERENCES entity(entity_id),
  contact_id      TEXT REFERENCES contact(contact_id),
  stage           TEXT NOT NULL DEFAULT 'LEAD'
                    CHECK (stage IN ('LEAD', 'QUALIFIED', 'PROPOSAL', 'WON', 'LOST')),
  probability     INTEGER NOT NULL DEFAULT 10 CHECK (probability BETWEEN 0 AND 100),
  expected_on     TEXT,                                              -- expected close, a day
  amount          REAL,
  currency        TEXT,
  owner           TEXT,
  notes           TEXT,
  agreement_id    TEXT REFERENCES agreement(agreement_id),           -- once won
  lost_reason     TEXT,
  closed_at       TEXT,
  created_at      TEXT NOT NULL,
  created_by      TEXT NOT NULL,
  updated_at      TEXT NOT NULL,
  updated_by      TEXT NOT NULL
);
CREATE INDEX ix_opportunity_stage ON opportunity (stage, expected_on);

CREATE TABLE quote (
  quote_id        TEXT PRIMARY KEY,                                  -- 'Q-0001'
  opportunity_id  TEXT NOT NULL REFERENCES opportunity(opportunity_id),
  name            TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'DRAFT'
                    CHECK (status IN ('DRAFT', 'SENT', 'ACCEPTED', 'DECLINED', 'EXPIRED')),
  valid_until     TEXT,
  tax_percent     REAL NOT NULL DEFAULT 0 CHECK (tax_percent BETWEEN 0 AND 100),
  subtotal        REAL NOT NULL DEFAULT 0,
  total           REAL NOT NULL DEFAULT 0,
  note            TEXT,
  sent_at         TEXT,
  decided_at      TEXT,
  created_at      TEXT NOT NULL,
  created_by      TEXT NOT NULL,
  updated_at      TEXT NOT NULL,
  updated_by      TEXT NOT NULL
);
CREATE INDEX ix_quote_opportunity ON quote (opportunity_id);

CREATE TABLE quote_line (
  line_id         INTEGER PRIMARY KEY,
  quote_id        TEXT NOT NULL REFERENCES quote(quote_id),
  sort_order      INTEGER NOT NULL DEFAULT 0,
  description     TEXT NOT NULL,
  quantity        REAL NOT NULL CHECK (quantity > 0),
  unit_price      REAL NOT NULL CHECK (unit_price >= 0),
  line_total      REAL NOT NULL
);
CREATE INDEX ix_quote_line_quote ON quote_line (quote_id);
