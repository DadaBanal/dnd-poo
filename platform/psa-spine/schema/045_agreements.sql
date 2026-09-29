-- 045 — agreements are made and kept on the desk; from one, staff add what
-- BizBox holds.
--
-- Dada, 29 Sep 2026 (SQL01's handoff of the same day, verbatim): "the
-- agreements need to exist they can add it on the psa the agreements from
-- there and add the needed invoices and whatever is exisitng on bizbox".
-- BizBox holds no supplier agreements (its contract tables are patient
-- coverage; SQL01, MEASURED), so an agreement is the desk's own record, in
-- the reference PSA's shape: a name, the other party, a term, a status, an
-- amount. Invoices, purchase orders and products stay BizBox's, mirrored
-- read-only in 043; an agreement names the mirrored records it covers here,
-- in its own table, so the hourly sync never touches an agreement or a
-- covering, and nothing is written to BizBox. The mirror's ext_agreement
-- stays what it was: a mirror kind, for a source that may one day be named.
PRAGMA foreign_keys = ON;

CREATE TABLE agreement (
  agreement_id  TEXT PRIMARY KEY,                       -- AGR-0001
  name          TEXT NOT NULL,
  party         TEXT,                                   -- the supplier, as BizBox names it
  starts_on     TEXT,
  ends_on       TEXT,
  status        TEXT NOT NULL DEFAULT 'DRAFT'
                  CHECK (status IN ('DRAFT', 'ACTIVE', 'INACTIVE', 'CANCELLED')),
  amount        REAL,
  currency      TEXT,
  notes         TEXT,
  created_at    TEXT NOT NULL,
  created_by    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  updated_by    TEXT NOT NULL
);

-- What an agreement covers: a mirrored BizBox invoice, purchase order or
-- product, by the mirror's own key. A row here is the desk's; the sync
-- marks a mirrored record absent but never removes it, so a covering
-- survives, and the page says the record is gone from BizBox.
CREATE TABLE agreement_item (
  agreement_id  TEXT NOT NULL REFERENCES agreement(agreement_id),
  source_id     TEXT NOT NULL REFERENCES ext_source(source_id),
  kind          TEXT NOT NULL CHECK (kind IN ('INVOICE', 'PURCHASE_ORDER', 'PRODUCT')),
  ext_ref       TEXT NOT NULL,
  added_at      TEXT NOT NULL,
  added_by      TEXT NOT NULL,
  note          TEXT,
  PRIMARY KEY (agreement_id, source_id, kind, ext_ref)
);
CREATE INDEX ix_agreement_item_ref ON agreement_item (source_id, kind, ext_ref);
