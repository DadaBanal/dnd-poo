-- 085 — the write path to BizBox, as SQL01 simplified it on 14 Oct 2026
-- (HANDOFF-sql01-cloud-WS36-20261014-write-path-simplified.md): identity is
-- the grant, concurrency is one parameter, replay is one UPDATE in the sender.
--
--   * ext_change.status and ext_batch.status gain SENDING: the sender claims a
--     change (PENDING -> SENDING, rowcount 1) before it applies it, so two
--     overlapping runs cannot both send the same change.
--   * ext_change.kind and ext_batch.kind gain the MMS document kinds the
--     Bizbox Chat session measured in scope (Part 90): ten, of which Purchase
--     Order and Delivery/Receiving are the desk's PURCHASE_ORDER and INVOICE
--     already (SQL01, Part 95, MEASURED: psa.vw_invoice reads the receiving
--     header), so eight new values. ext_stock has no kind: a position is
--     derived; the correctable thing is a movement.
--   * ext_change carries expected_tstamp, the record's BizBox row version as
--     the desk read it when the change was proposed, sent back to the
--     procedure as @expected_tstamp; and change_uid, a desk-minted id that
--     survives a restore of PMC_PSA (the change_id question, answered in
--     HANDOFF-cloud-sql01-WS36-20261014-write-path-085.md).
--   * every mirror kind the desk may write to carries tstamp.
--
-- SQLite cannot alter a CHECK, so the two tables are rebuilt in place: the
-- same columns in the same order, the CHECKs widened, two columns added at
-- the end. The port turns that into a constraint swap and two ADDs, guarded.
-- Foreign keys are off for the rebuild only: ext_change refers to ext_batch.
PRAGMA foreign_keys = OFF;

CREATE TABLE ext_batch_new (
  batch_id      INTEGER PRIMARY KEY,
  source_id     TEXT NOT NULL REFERENCES ext_source(source_id),
  kind          TEXT NOT NULL CHECK (kind IN ('AGREEMENT', 'PRODUCT', 'PURCHASE_ORDER', 'INVOICE',
                                              'EXPENSE_REQ', 'STOCK_REQ', 'EXPENSE_ISSUANCE', 'STOCK_ISSUANCE',
                                              'PURCHASE_REQ', 'MATERIAL_PRODUCTION', 'PHYSICAL_COUNT', 'QTY_ADJUSTMENT')),
  change_kind   TEXT NOT NULL CHECK (change_kind IN ('EDIT', 'ADD')),
  reason        TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'PENDING'
                  CHECK (status IN ('PENDING', 'APPROVED', 'SENDING', 'APPLIED', 'REJECTED', 'CANCELLED')),
  payload       TEXT,
  requested_at  TEXT NOT NULL,
  requested_by  TEXT NOT NULL,
  approved_at   TEXT,
  approved_by   TEXT,
  decided_at    TEXT,
  decided_by    TEXT,
  answer        TEXT
);
INSERT INTO ext_batch_new (batch_id, source_id, kind, change_kind, reason, status, payload, requested_at, requested_by,
                           approved_at, approved_by, decided_at, decided_by, answer)
  SELECT batch_id, source_id, kind, change_kind, reason, status, payload, requested_at, requested_by,
         approved_at, approved_by, decided_at, decided_by, answer FROM ext_batch;
DROP TABLE ext_batch;
ALTER TABLE ext_batch_new RENAME TO ext_batch;
CREATE INDEX ix_ext_batch_status ON ext_batch (source_id, status);

CREATE TABLE ext_change_new (
  change_id     INTEGER PRIMARY KEY,
  source_id     TEXT NOT NULL REFERENCES ext_source(source_id),
  kind          TEXT NOT NULL CHECK (kind IN ('AGREEMENT', 'PRODUCT', 'PURCHASE_ORDER', 'INVOICE',
                                              'EXPENSE_REQ', 'STOCK_REQ', 'EXPENSE_ISSUANCE', 'STOCK_ISSUANCE',
                                              'PURCHASE_REQ', 'MATERIAL_PRODUCTION', 'PHYSICAL_COUNT', 'QTY_ADJUSTMENT')),
  ext_ref       TEXT NOT NULL,
  field         TEXT NOT NULL,
  old_value     TEXT,
  new_value     TEXT,
  reason        TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'PENDING'
                  CHECK (status IN ('PENDING', 'SENDING', 'APPLIED', 'REJECTED', 'CANCELLED')),
  requested_at  TEXT NOT NULL,
  requested_by  TEXT NOT NULL,
  decided_at    TEXT,
  decided_by    TEXT,
  answer        TEXT,
  batch_id      INTEGER REFERENCES ext_batch(batch_id),
  -- The record's BizBox row version (tstamp, as the read view gives it) when
  -- the change was proposed; the procedure updates only if it still holds.
  expected_tstamp TEXT,
  -- Minted by the desk when the change is proposed: a change keeps this id
  -- through a restore of PMC_PSA, where change_id would be minted again.
  change_uid    TEXT
);
INSERT INTO ext_change_new (change_id, source_id, kind, ext_ref, field, old_value, new_value, reason, status,
                            requested_at, requested_by, decided_at, decided_by, answer, batch_id)
  SELECT change_id, source_id, kind, ext_ref, field, old_value, new_value, reason, status,
         requested_at, requested_by, decided_at, decided_by, answer, batch_id FROM ext_change;
DROP TABLE ext_change;
ALTER TABLE ext_change_new RENAME TO ext_change;
CREATE INDEX ix_ext_change_ref ON ext_change (source_id, kind, ext_ref);
CREATE INDEX ix_ext_change_batch ON ext_change (batch_id);

PRAGMA foreign_keys = ON;

-- The row version BizBox keeps on every MMS write target (23 of 23, measured):
-- the read view gives it as text, the desk keeps it, a change sends it back.
ALTER TABLE ext_purchase_order ADD COLUMN tstamp TEXT;
ALTER TABLE ext_product ADD COLUMN tstamp TEXT;
ALTER TABLE ext_invoice ADD COLUMN tstamp TEXT;
ALTER TABLE ext_po_line ADD COLUMN tstamp TEXT;
ALTER TABLE ext_stock ADD COLUMN tstamp TEXT;
ALTER TABLE ext_movement ADD COLUMN tstamp TEXT;
ALTER TABLE ext_rr_line ADD COLUMN tstamp TEXT;
