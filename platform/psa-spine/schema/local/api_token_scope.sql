-- PSA spine -- machine API token scopes (gap 8, 29 Sep 2026)
--
-- api_token.sql gives a machine one thing: raise tickets onto one board and
-- read the ones it raised. Other systems want to read and update: a
-- monitoring dashboard that lists the board's open tickets, a runbook tool
-- that adds a note and closes what it fixed. So a token carries a scope:
--   RAISE  raise tickets onto its board and read those (as before; the default,
--          and what a row from before this file reads as when the column is NULL)
--   READ   RAISE, and list and read every ticket on its board, and the
--          configurations
--   WRITE  READ, and add a note, set the status or the owner on its board
-- Still one board, still a local token, still audited on every use; a token
-- for a restricted board is minted deliberately and every read on that board
-- is audited like a person's.
PRAGMA foreign_keys = ON;

ALTER TABLE api_token ADD COLUMN scope TEXT DEFAULT 'RAISE' CHECK (scope IN ('RAISE', 'READ', 'WRITE'));
