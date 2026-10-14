-- 088 — BizBox's own document number on the six document mirrors (SQL01, 14 Oct 2026,
-- HANDOFF-sql01-cloud-WS36-20261014-087-applied-and-docno-is-per-department.md).
--
-- BizBox numbers stock and expense requisitions, both issuances and physical
-- counts per requesting department (docno = MAX(docno) + 1 per destination
-- warehouse, never reset), so "1" is 33 different stock requisitions. The
-- mirrors therefore key on the header's transaction key (TrxKey, PK_TRXNO), and
-- the printed number is kept here beside it: shown with its department, never
-- used as the identity. Purchase orders and purchase requisitions number
-- globally; purchase_req carries the column too, for one shape across the six.
ALTER TABLE ext_stock_req ADD COLUMN doc_no TEXT;
ALTER TABLE ext_expense_req ADD COLUMN doc_no TEXT;
ALTER TABLE ext_purchase_req ADD COLUMN doc_no TEXT;
ALTER TABLE ext_stock_issuance ADD COLUMN doc_no TEXT;
ALTER TABLE ext_expense_issuance ADD COLUMN doc_no TEXT;
ALTER TABLE ext_physical_count ADD COLUMN doc_no TEXT;
