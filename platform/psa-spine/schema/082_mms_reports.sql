-- 082 — MMS reports on the desk, rendered by SSRS (Dada, 13 Oct 2026):
--
--   "printing out reports for MMS" ... "make sure it has all the data it
--   needs and it conforms to modern design"
--
-- SQL01 measured it (handoff of 13 Oct): the reports already exist, 164 of
-- them under /BizBox MMS Reports on the host's Reporting Services, and the
-- report server answers. So nothing is written anew: the desk keeps a
-- catalogue of what the report server lists, shows each report to the roles
-- its area allows (the same three Procurement areas), asks SSRS for the
-- report's own parameters, and renders through SSRS to PDF on the page or to
-- Excel as a download. Staff never leave the desk and never touch SSRS.
--
-- mms_report: one row per report the server lists. path is the server's
-- own (the key); name is the server's item name; title is what a person
-- reads (made from the name, or set on Setup); area is the Procurement area
-- whose See level shows it; present is 0 once the server stops listing it
-- (kept, never deleted, so a run's history still names it).
-- mms_report_run: every render, by whom, with which parameter values, in
-- which format, and how SSRS answered. The audit of what left the server.
PRAGMA foreign_keys = ON;

CREATE TABLE mms_report (
  report_id    INTEGER PRIMARY KEY,
  path         TEXT NOT NULL,
  name         TEXT NOT NULL,
  title        TEXT NOT NULL,
  description  TEXT,
  area         TEXT NOT NULL CHECK (area IN ('purchase_order', 'invoice', 'product')),
  shown        INTEGER NOT NULL DEFAULT 1 CHECK (shown IN (0, 1)),
  sort_no      INTEGER,
  params_json  TEXT,
  present      INTEGER NOT NULL DEFAULT 1 CHECK (present IN (0, 1)),
  synced_at    TEXT NOT NULL,
  title_set_by TEXT,
  area_set_by  TEXT
);
CREATE UNIQUE INDEX ux_mms_report_path ON mms_report (path);
CREATE INDEX ix_mms_report_area ON mms_report (area, shown, present);

CREATE TABLE mms_report_run (
  run_id       INTEGER PRIMARY KEY,
  report_id    INTEGER NOT NULL REFERENCES mms_report(report_id),
  member       TEXT NOT NULL,
  ran_at       TEXT NOT NULL,
  format       TEXT NOT NULL CHECK (format IN ('PDF', 'EXCELOPENXML')),
  params_json  TEXT,
  outcome      TEXT NOT NULL CHECK (outcome IN ('OK', 'ERROR')),
  message      TEXT,
  bytes        INTEGER,
  millis       INTEGER
);
CREATE INDEX ix_mms_report_run_member ON mms_report_run (member, report_id, ran_at);
