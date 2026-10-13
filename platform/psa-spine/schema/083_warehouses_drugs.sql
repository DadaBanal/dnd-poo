-- 083 — warehouses, and drugs and medicines (Dada, 13 Oct 2026):
--
--   "add warehousing" (SQL01's measurement: 73 warehouses in 6 groups, which
--   the desk knew nothing about) and "an area for procurement of drugs and
--   medicine specifically" (BizBox marks 2,166 items as medicines, with a
--   controlled-drug flag).
--
-- Confirmed before building: a Warehouses tab by group, read hourly from one
-- small view; a Drugs tab as its own rights area (PROC_DRUG in Security
-- roles) with a Controlled filter; stock on hand stays in the MMS reports
-- until SQL01 has measured how many rows carry stock, so nothing of its
-- 591,000 rows is copied blind. Two mirror kinds, read by sync-bizbox like
-- the others: present or absent, never deleted.
PRAGMA foreign_keys = ON;

CREATE TABLE ext_warehouse (
  source_id    TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref      TEXT NOT NULL,
  name         TEXT NOT NULL,
  group_name   TEXT,
  active       INTEGER,
  present      INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at    TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);
CREATE INDEX ix_ext_warehouse_group ON ext_warehouse (source_id, group_name, present);

-- One row per item that is a medicine; ext_ref is the item's code, the same
-- key ext_product carries, so the two join. Nothing here is a patient's.
CREATE TABLE ext_medicine (
  source_id    TEXT NOT NULL REFERENCES ext_source(source_id),
  ext_ref      TEXT NOT NULL,
  generic      TEXT,
  dosage       TEXT,
  controlled   INTEGER,
  doh_ref      TEXT,
  mims_ref     TEXT,
  admin_group  TEXT,
  remarks      TEXT,
  present      INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at    TEXT NOT NULL,
  PRIMARY KEY (source_id, ext_ref)
);
CREATE INDEX ix_ext_medicine_controlled ON ext_medicine (source_id, controlled, present);
