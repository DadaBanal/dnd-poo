-- PMC's platform database (Path A, M5.3): a study read.
--
-- reading.done says a reader has finished with a study: they marked it read
-- from the reading list, once they had reported it where PMC's reports live
-- today (BizBox). When reports come to the platform, a signed report will
-- mark its study read by itself. A study marked read is no longer claimed: a
-- claim says "I am reading this"; done says "I have".
--
-- audit.event gains the two actions ('read', 'unread'). Its constraint is
-- replaced here, never the migration that made it: that one has run.

-- migrate:up
CREATE TABLE reading.done (
  study_uid   text        PRIMARY KEY CHECK (study_uid ~ '^[0-9.]{1,64}$'),
  reader      text        NOT NULL,
  reader_name text        NOT NULL,
  read_at     timestamptz NOT NULL DEFAULT now()
);
COMMENT ON COLUMN reading.done.reader IS 'the reader''s Windows logon name (AD sAMAccountName)';

ALTER TABLE audit.event DROP CONSTRAINT event_action_check;
ALTER TABLE audit.event ADD CONSTRAINT event_action_check
  CHECK (action IN ('open', 'claim', 'release', 'read', 'unread'));

GRANT SELECT, INSERT, UPDATE, DELETE ON reading.done TO platform_app;

-- migrate:down
-- The audit record is never deleted, so the old constraint comes back without
-- checking the rows that already carry the two new actions.
ALTER TABLE audit.event DROP CONSTRAINT event_action_check;
ALTER TABLE audit.event ADD CONSTRAINT event_action_check
  CHECK (action IN ('open', 'claim', 'release')) NOT VALID;
DROP TABLE reading.done;
