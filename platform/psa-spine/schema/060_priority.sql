-- 060: the Priority setup table, in the reference PSA's shape (Dada, 1 Oct
-- 2026: "priorities should match what connectwise has and can be overriden").
--
-- ConnectWise's Priority entity is id, name (50), color (a named colour),
-- sortOrder and defaultFlag (MEASURED from its OpenAPI schema, docs/
-- WS36-connectwise-model-20260909.md). The desk's P1-P4 codes stay the key
-- every clock and floor already uses; this table gives each its name and
-- colour, editable at Setup > Priorities. The names seeded are the desk's
-- reading of ConnectWise's defaults (NOT VERIFIED against a live instance:
-- its documentation is behind a sign-in); a wrong word is a setup edit.
CREATE TABLE priority (
  priority_id TEXT PRIMARY KEY CHECK (priority_id IN ('P1', 'P2', 'P3', 'P4')),
  name        TEXT NOT NULL,
  color       TEXT NOT NULL CHECK (color IN ('Red', 'Orange', 'Yellow', 'Green', 'Blue', 'Cyan', 'Lime',
                                             'Purple', 'Pink', 'Gray', 'Black', 'White')),
  sort_order  INTEGER NOT NULL DEFAULT 0,
  is_default  INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1))
);
