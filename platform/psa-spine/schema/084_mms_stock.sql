-- 084 — BizBox's MMS rendered in full on the desk (Dada, 13 Oct 2026: "a
-- full render of the bizbox mms app into the procurement module, but make it
-- better"), and the intake duplicate guard made honest (SQL01, Part 82).
--
-- Stock on hand: SQL01 measured dbo.iwWareitem at 591,369 rows of which
-- 4,358 carry a quantity (0.7%), in 25 of the 73 warehouses. A view narrowed
-- to those rows is smaller than the item list, so stock is mirrored hourly
-- like everything else, never read live. Movements: the item ledger, through
-- a view SQL01 narrows by time (Dada: "whichever is more efficient: views
-- based on time or days or months"); rows that fall out of the window leave
-- the desk. Receiving lines: what each receiving report took in, as a
-- purchase order's lines already are. Nothing writes to BizBox.
PRAGMA foreign_keys = ON;

-- The intake guard (SQL01, Part 82, 30 genuine requests filed as resends):
-- a resend is the same sender, the same subject AND the same words. The
-- words are kept as a hash, never as text.
ALTER TABLE intake_message ADD COLUMN body_hash TEXT;

-- One row per (warehouse, item) that holds stock; ext_ref is
-- <warehouse_ref>:<item_ref>, made by the read when the view has no key.
CREATE TABLE ext_stock (
  source_id      TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref        TEXT NOT NULL,
  warehouse_ref  TEXT NOT NULL,
  item_ref       TEXT NOT NULL,
  quantity       REAL NOT NULL,
  unit_cost      REAL,
  as_of          TEXT,
  present        INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at      TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);
CREATE INDEX ix_ext_stock_item ON ext_stock (source_id, item_ref, present);
CREATE INDEX ix_ext_stock_warehouse ON ext_stock (source_id, warehouse_ref, present);

-- One row per movement of an item in a warehouse inside the view's window:
-- received, issued, transferred, adjusted, counted. kind is BizBox's own
-- word; doc_ref the document that moved it (a receiving report, an issue
-- slip, a transfer). Rows the view no longer returns are deleted, not kept
-- absent: the window moved, nothing was lost in BizBox.
CREATE TABLE ext_movement (
  source_id      TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref        TEXT NOT NULL,
  item_ref       TEXT NOT NULL,
  warehouse_ref  TEXT,
  moved_on       TEXT NOT NULL,
  kind           TEXT,
  doc_ref        TEXT,
  qty_in         REAL,
  qty_out        REAL,
  balance        REAL,
  unit_cost      REAL,
  remarks        TEXT,
  present        INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at      TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);
CREATE INDEX ix_ext_movement_item ON ext_movement (source_id, item_ref, moved_on);
CREATE INDEX ix_ext_movement_warehouse ON ext_movement (source_id, warehouse_ref, moved_on);
CREATE INDEX ix_ext_movement_when ON ext_movement (source_id, moved_on);

-- A receiving report's lines, as ext_po_line is a purchase order's.
CREATE TABLE ext_rr_line (
  source_id      TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref        TEXT NOT NULL,
  rr_ref         TEXT NOT NULL,
  line_no        INTEGER,
  product_ref    TEXT,
  description    TEXT,
  quantity       REAL,
  unit_cost      REAL,
  po_ref         TEXT,
  present        INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at      TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);
CREATE INDEX ix_ext_rr_line_rr ON ext_rr_line (source_id, rr_ref);
