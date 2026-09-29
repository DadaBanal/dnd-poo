-- 043 — agreements, procurement, products and invoices: a read-only mirror of BizBox.
--
-- Dada's direction (29 Sep 2026): finance, agreements and procurement are
-- BizBox's, and the desk makes way for them rather than keeping its own. So
-- these tables are a MIRROR, written only by `psaspine sync-bizbox`, never by a
-- person: each row is keyed by BizBox's own reference and says when it was last
-- seen. A row that disappears from BizBox is marked absent, never deleted, so
-- a ticket linked to it keeps its link. The desk issues no invoice (the
-- record's rule): an invoice here is BizBox's, shown beside the work it pays for.
--
-- What crosses (psaspine/bizbox.py): only the views named in a map file, only
-- the columns named there, through a read-only login. BizBox is the hospital
-- information system and holds patient records (the record, §8.1, MEASURED):
-- a name that looks like a patient table is refused before any query is sent.
PRAGMA foreign_keys = ON;

CREATE TABLE ext_source (
  source_id     TEXT PRIMARY KEY,                       -- 'BIZBOX'
  name          TEXT NOT NULL,
  last_sync_at  TEXT,
  last_sync_by  TEXT,
  last_result   TEXT
);

CREATE TABLE ext_agreement (
  source_id    TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref      TEXT NOT NULL,
  name         TEXT NOT NULL,
  party        TEXT,
  starts_on    TEXT,
  ends_on      TEXT,
  status       TEXT,
  amount       REAL,
  currency     TEXT,
  present      INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at    TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);

CREATE TABLE ext_product (
  source_id    TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref      TEXT NOT NULL,
  name         TEXT NOT NULL,
  category     TEXT,
  unit         TEXT,
  unit_cost    REAL,
  present      INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at    TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);

CREATE TABLE ext_purchase_order (
  source_id    TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref      TEXT NOT NULL,
  vendor       TEXT,
  ordered_on   TEXT,
  status       TEXT,
  total        REAL,
  currency     TEXT,
  present      INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at    TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);

CREATE TABLE ext_invoice (
  source_id     TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref       TEXT NOT NULL,
  party         TEXT,
  invoiced_on   TEXT,
  due_on        TEXT,
  status        TEXT,
  total         REAL,
  currency      TEXT,
  agreement_ref TEXT,
  present       INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at     TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);

-- A ticket or a project names the BizBox record it concerns: the PO a
-- replacement printer was bought on, the agreement a vendor visit is under.
CREATE TABLE ext_link (
  subject_kind  TEXT NOT NULL CHECK (subject_kind IN ('TICKET', 'PROJECT')),
  subject_id    TEXT NOT NULL,
  source_id     TEXT NOT NULL REFERENCES ext_source(source_id),
  kind          TEXT NOT NULL CHECK (kind IN ('AGREEMENT', 'PRODUCT', 'PURCHASE_ORDER', 'INVOICE')),
  ext_ref       TEXT NOT NULL,
  linked_at     TEXT NOT NULL,
  linked_by     TEXT NOT NULL,
  PRIMARY KEY (subject_kind, subject_id, source_id, kind, ext_ref)
);
CREATE INDEX ix_ext_link_ref ON ext_link (source_id, kind, ext_ref);

-- A purchase order's lines, as the reference PSA shows them under a PO: the
-- item, its description, quantity ordered and received, and unit cost. Keyed
-- by BizBox's own line reference; po_ref ties it to its order.
CREATE TABLE ext_po_line (
  source_id     TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref       TEXT NOT NULL,
  po_ref        TEXT NOT NULL,
  line_no       INTEGER,
  product_ref   TEXT,
  description   TEXT,
  quantity      REAL,
  received_qty  REAL,
  unit_cost     REAL,
  present       INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at     TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);
CREATE INDEX ix_ext_po_line_po ON ext_po_line (source_id, po_ref);

-- Room for edits back to BizBox, later. A person proposes a change to a
-- mirrored field; it is recorded here, PENDING, and BizBox is NOT touched. When
-- a write path is approved (a BizBox API or a stored procedure SQL01 creates),
-- a writer takes PENDING rows, applies them, and marks each APPLIED or
-- REJECTED with BizBox's answer; the next sync then shows the new value. Until
-- then the desk says plainly that BizBox has not changed.
CREATE TABLE ext_change (
  change_id     INTEGER PRIMARY KEY,
  source_id     TEXT NOT NULL REFERENCES ext_source(source_id),
  kind          TEXT NOT NULL CHECK (kind IN ('AGREEMENT', 'PRODUCT', 'PURCHASE_ORDER', 'INVOICE')),
  ext_ref       TEXT NOT NULL,
  field         TEXT NOT NULL,
  old_value     TEXT,
  new_value     TEXT,
  reason        TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'PENDING'
                  CHECK (status IN ('PENDING', 'APPLIED', 'REJECTED', 'CANCELLED')),
  requested_at  TEXT NOT NULL,
  requested_by  TEXT NOT NULL,
  decided_at    TEXT,
  decided_by    TEXT,
  answer        TEXT
);
CREATE INDEX ix_ext_change_ref ON ext_change (source_id, kind, ext_ref);
