-- PMC's own platform database (Path A, M2.3): what no archive holds.
-- First: who is reading which study, and a record of who did what.
--
-- Studies are named only by their DICOM identifiers (StudyInstanceUID), never
-- by an engine's internal IDs, so the engine stays swappable. Every time is a
-- timestamptz. The migration role owns every object; the app's role gets
-- grants, and never UPDATE or DELETE on the audit record.

-- migrate:up
CREATE SCHEMA reading;
CREATE SCHEMA audit;

-- A reader's claim on a study: one reader at a time.
CREATE TABLE reading.claim (
  study_uid   text        PRIMARY KEY CHECK (study_uid ~ '^[0-9.]{1,64}$'),
  reader      text        NOT NULL,  -- the reader's sign-in email
  reader_name text        NOT NULL,
  claimed_at  timestamptz NOT NULL DEFAULT now()
);

-- Who did what, append-only. uuidv7 keys sort by time.
CREATE TABLE audit.event (
  id        uuid        PRIMARY KEY DEFAULT uuidv7(),
  at        timestamptz NOT NULL DEFAULT now(),
  actor     text        NOT NULL,  -- the sign-in email, or a service name
  action    text        NOT NULL CHECK (action IN ('open', 'claim', 'release')),
  study_uid text        CHECK (study_uid ~ '^[0-9.]{1,64}$'),
  detail    jsonb       NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX event_study ON audit.event (study_uid, at);

GRANT USAGE ON SCHEMA reading, audit TO platform_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON reading.claim TO platform_app;
GRANT SELECT, INSERT ON audit.event TO platform_app;

-- migrate:down
DROP SCHEMA audit CASCADE;
DROP SCHEMA reading CASCADE;
