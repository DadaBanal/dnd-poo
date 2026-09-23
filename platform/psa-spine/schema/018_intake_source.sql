-- 018 — where a ticket came from.
--
-- ConnectWise keeps a global Source table (call, email, website) and the build
-- scope (§5.8) asked for the same: `ticket.intake_source`. It is a different
-- axis from work_item.source, which says register versus desk versus manual.
-- For PMC the phone and walk-up counts are the interesting ones, because that
-- is the work that today leaves no trace at all.
--
-- NULL for tickets opened before this column existed; nothing is back-filled
-- by guessing.
PRAGMA foreign_keys = ON;

ALTER TABLE ticket ADD COLUMN intake_source TEXT
  CHECK (intake_source IN ('EMAIL', 'PHONE', 'WALK_UP', 'PORTAL', 'API', 'DESK', 'IMPORT'));
