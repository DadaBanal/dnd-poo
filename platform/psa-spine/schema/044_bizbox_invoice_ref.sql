-- 044 — the supplier's own invoice number on a mirrored invoice.
--
-- SQL01's reading of BizBox (29 Sep 2026, MEASURED from its catalog and its own
-- report views): what the desk mirrors as an invoice is BizBox's receiving
-- report, keyed by the receiving number. The supplier's invoice number is a
-- separate column there (`refno`), typed by staff and not unique — 626
-- distinct of 634 — so it can never be the key, but it is the number on the
-- paper a vendor asks about. 043 had no field for it. This adds one, NULL-able
-- by the port's rule, filled by `sync-bizbox` when the map names a column.
PRAGMA foreign_keys = ON;

ALTER TABLE ext_invoice ADD COLUMN supplier_ref TEXT;

-- Two lookups the primary keys do not serve, found by EXPLAIN on a 50,000-row
-- mirror: the Knowledge pod on a ticket (kb_ticket by ticket; its key leads
-- with the article) and the invoices under an agreement. Plain CREATE INDEX:
-- the port guards every index with its own IF NOT EXISTS.
CREATE INDEX ix_kb_ticket_ticket ON kb_ticket (work_item_id);
CREATE INDEX ix_ext_invoice_agreement ON ext_invoice (source_id, agreement_ref);
