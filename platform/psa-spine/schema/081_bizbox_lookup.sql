-- 081 — BizBox's own lists, for the desk's dropdowns (Dada, 13 Oct 2026):
--
--   "status or fields that needs a drop down to match bizbox choices must be
--   done; all fields must not error when importing into bizbox"
--
-- Confirmed before building: a dropdown offers only values BizBox accepts.
-- Until SQL01 exposes BizBox's code lists through one read-only view, the
-- lists are the values the mirror has seen on real records; once the view is
-- mapped (kind "lookup" in the map) and read by sync-bizbox, the rows here
-- take over, labels and all. A value off the list is refused on the desk,
-- before approval, so nothing reaches BizBox's procedure that it would refuse.
--
-- One row per list entry. list names the field it serves (po_status,
-- rr_status, currency, unit, category); code is what BizBox stores and what
-- the desk sends back; label is what a person reads. Keyed like every other
-- mirrored kind, by ext_ref ("<list>:<code>", made up by the reader when the
-- view has no key of its own), so sync treats it as any other kind: present
-- or absent, never deleted.
PRAGMA foreign_keys = ON;

CREATE TABLE ext_lookup (
  source_id    TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref      TEXT NOT NULL,
  list         TEXT NOT NULL,
  code         TEXT NOT NULL,
  label        TEXT,
  sort_no      INTEGER,
  present      INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at    TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);
CREATE INDEX ix_ext_lookup_list ON ext_lookup (source_id, list, present);
