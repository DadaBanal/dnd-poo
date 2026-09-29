-- 042 — saved reports: the reference PSA's report writer, kept safe.
--
-- A report is a dataset the desk defines (tickets, time, visits, projects,
-- knowledge), the columns and grouping a person picks from that dataset's own
-- list, and filters as a query string. No SQL is ever stored or typed: the
-- dataset's code writes the query, and every dataset is limited to the boards
-- the viewer may see. A shared report is listed for everyone who may use
-- Reports; a pinned one sits on the Reports page as a dashboard tile.
PRAGMA foreign_keys = ON;

CREATE TABLE report_def (
  report_id   INTEGER PRIMARY KEY,
  name        TEXT NOT NULL,
  dataset     TEXT NOT NULL CHECK (dataset IN ('TICKETS', 'TIME', 'VISITS', 'PROJECTS', 'KNOWLEDGE')),
  columns     TEXT NOT NULL,
  group_by    TEXT,
  filters     TEXT,
  owner       TEXT NOT NULL,
  shared      INTEGER NOT NULL DEFAULT 0 CHECK (shared IN (0, 1)),
  pinned      INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0, 1)),
  created_at  TEXT NOT NULL
);
