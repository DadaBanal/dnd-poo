-- 087 — what SQL01 asked the mirror for on 14 Oct 2026, in one step so it is
-- one port (HANDOFF-sql01-cloud-WS36-20261014-slip-keys-and-conversion.md,
-- -twelve-document-views.md, -product-404-fixed.md, -three-corrections-measured.md):
--
--   * trx_key on ext_purchase_order and ext_invoice: the header's identity key
--     (PK_TRXNO), which every MMS slip filters on. The printed number is not
--     the key; a slip opened with the number renders empty and says nothing.
--   * is_active, is_inventory on ext_product: vw_product now carries every row
--     of iwItems (5,484 -> 8,572), so a page resolves for any code any view can
--     show; what a person may pick is a flag. And conversion, purc_price,
--     last_purc_price under BizBox's own names (smallconversion is not a column
--     anywhere; SQL01 measured it).
--   * the twelve mirrors for BizBox's six existing documents, on the uniform
--     contract SQL01 built the views to (vw_<kind> and vw_<kind>_line). The
--     family map is Bizbox Chat's, read from the vendor client: the Iss tables
--     are Expense Issuance, and Stock Issuance is Wh. No view exposes remarks or
--     any BizBox-authored text, and these tables have no column for it.
--
-- Read-only mirrors like the rest: a row gone from BizBox is kept absent, never
-- deleted. Nothing here changes an existing column; four ALTERs add columns.
ALTER TABLE ext_purchase_order ADD COLUMN trx_key TEXT;
ALTER TABLE ext_invoice ADD COLUMN trx_key TEXT;
ALTER TABLE ext_product ADD COLUMN is_active INTEGER;
ALTER TABLE ext_product ADD COLUMN is_inventory INTEGER;
ALTER TABLE ext_product ADD COLUMN conversion REAL;
ALTER TABLE ext_product ADD COLUMN purc_price REAL;
ALTER TABLE ext_product ADD COLUMN last_purc_price REAL;

-- Stock Requisition (iwWhreqinv / iwWhreqitem)
CREATE TABLE ext_stock_req (
  source_id      TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref        TEXT NOT NULL,
  trx_key        TEXT,
  doc_date       TEXT,
  warehouse_src  TEXT,
  warehouse_dst  TEXT,
  status         TEXT,
  total_qty      REAL,
  total_items    INTEGER,
  total          REAL,
  tstamp         TEXT,
  present        INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at      TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);
CREATE TABLE ext_stock_req_line (
  source_id      TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref        TEXT NOT NULL,
  doc_ref        TEXT NOT NULL,
  line_no        INTEGER,
  product_ref    TEXT,
  description    TEXT,
  quantity       REAL,
  served_qty     REAL,
  system_qty     REAL,
  variance       REAL,
  unit           TEXT,
  conversion     REAL,
  unit_cost      REAL,
  total          REAL,
  tstamp         TEXT,
  present        INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at      TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);
CREATE INDEX ix_ext_stock_req_line_doc ON ext_stock_req_line (source_id, doc_ref);
-- Expense Requisition (iwReqinv / iwReqitem)
CREATE TABLE ext_expense_req (
  source_id      TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref        TEXT NOT NULL,
  trx_key        TEXT,
  doc_date       TEXT,
  warehouse_src  TEXT,
  warehouse_dst  TEXT,
  status         TEXT,
  total_qty      REAL,
  total_items    INTEGER,
  total          REAL,
  tstamp         TEXT,
  present        INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at      TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);
CREATE TABLE ext_expense_req_line (
  source_id      TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref        TEXT NOT NULL,
  doc_ref        TEXT NOT NULL,
  line_no        INTEGER,
  product_ref    TEXT,
  description    TEXT,
  quantity       REAL,
  served_qty     REAL,
  system_qty     REAL,
  variance       REAL,
  unit           TEXT,
  conversion     REAL,
  unit_cost      REAL,
  total          REAL,
  tstamp         TEXT,
  present        INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at      TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);
CREATE INDEX ix_ext_expense_req_line_doc ON ext_expense_req_line (source_id, doc_ref);
-- Purchase Requisition (iwPRinv / iwPRitem)
CREATE TABLE ext_purchase_req (
  source_id      TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref        TEXT NOT NULL,
  trx_key        TEXT,
  doc_date       TEXT,
  warehouse_src  TEXT,
  warehouse_dst  TEXT,
  status         TEXT,
  total_qty      REAL,
  total_items    INTEGER,
  total          REAL,
  tstamp         TEXT,
  present        INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at      TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);
CREATE TABLE ext_purchase_req_line (
  source_id      TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref        TEXT NOT NULL,
  doc_ref        TEXT NOT NULL,
  line_no        INTEGER,
  product_ref    TEXT,
  description    TEXT,
  quantity       REAL,
  served_qty     REAL,
  system_qty     REAL,
  variance       REAL,
  unit           TEXT,
  conversion     REAL,
  unit_cost      REAL,
  total          REAL,
  tstamp         TEXT,
  present        INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at      TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);
CREATE INDEX ix_ext_purchase_req_line_doc ON ext_purchase_req_line (source_id, doc_ref);
-- Stock Issuance (iwWhinv / iwWhitem)
CREATE TABLE ext_stock_issuance (
  source_id      TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref        TEXT NOT NULL,
  trx_key        TEXT,
  doc_date       TEXT,
  warehouse_src  TEXT,
  warehouse_dst  TEXT,
  status         TEXT,
  total_qty      REAL,
  total_items    INTEGER,
  total          REAL,
  tstamp         TEXT,
  present        INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at      TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);
CREATE TABLE ext_stock_issuance_line (
  source_id      TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref        TEXT NOT NULL,
  doc_ref        TEXT NOT NULL,
  line_no        INTEGER,
  product_ref    TEXT,
  description    TEXT,
  quantity       REAL,
  served_qty     REAL,
  system_qty     REAL,
  variance       REAL,
  unit           TEXT,
  conversion     REAL,
  unit_cost      REAL,
  total          REAL,
  tstamp         TEXT,
  present        INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at      TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);
CREATE INDEX ix_ext_stock_issuance_line_doc ON ext_stock_issuance_line (source_id, doc_ref);
-- Expense Issuance (iwIssinv / iwIssitem)
CREATE TABLE ext_expense_issuance (
  source_id      TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref        TEXT NOT NULL,
  trx_key        TEXT,
  doc_date       TEXT,
  warehouse_src  TEXT,
  warehouse_dst  TEXT,
  status         TEXT,
  total_qty      REAL,
  total_items    INTEGER,
  total          REAL,
  tstamp         TEXT,
  present        INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at      TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);
CREATE TABLE ext_expense_issuance_line (
  source_id      TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref        TEXT NOT NULL,
  doc_ref        TEXT NOT NULL,
  line_no        INTEGER,
  product_ref    TEXT,
  description    TEXT,
  quantity       REAL,
  served_qty     REAL,
  system_qty     REAL,
  variance       REAL,
  unit           TEXT,
  conversion     REAL,
  unit_cost      REAL,
  total          REAL,
  tstamp         TEXT,
  present        INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at      TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);
CREATE INDEX ix_ext_expense_issuance_line_doc ON ext_expense_issuance_line (source_id, doc_ref);
-- Physical Count (iwPhentinv / iwPhentitem)
CREATE TABLE ext_physical_count (
  source_id      TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref        TEXT NOT NULL,
  trx_key        TEXT,
  doc_date       TEXT,
  warehouse_src  TEXT,
  warehouse_dst  TEXT,
  status         TEXT,
  total_qty      REAL,
  total_items    INTEGER,
  total          REAL,
  tstamp         TEXT,
  present        INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at      TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);
CREATE TABLE ext_physical_count_line (
  source_id      TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref        TEXT NOT NULL,
  doc_ref        TEXT NOT NULL,
  line_no        INTEGER,
  product_ref    TEXT,
  description    TEXT,
  quantity       REAL,
  served_qty     REAL,
  system_qty     REAL,
  variance       REAL,
  unit           TEXT,
  conversion     REAL,
  unit_cost      REAL,
  total          REAL,
  tstamp         TEXT,
  present        INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at      TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);
CREATE INDEX ix_ext_physical_count_line_doc ON ext_physical_count_line (source_id, doc_ref);
