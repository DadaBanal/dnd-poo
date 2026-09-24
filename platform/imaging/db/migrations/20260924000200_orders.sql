-- PMC's platform database (Path A, M3.2): orders from BizBox, as the BizBox
-- connector (orders/) keeps them on the consoles' worklists.
--
-- ris.order_map is the connector's record of each order: its worklist entries
-- (one per console), where it has got to, and the last change it read.
-- ris.sync_cursor is where it is in BizBox's view and in the engine's change
-- feed. ris.event is what it did, append-only. The connector logs in as
-- platform_orders, with only these grants; the front door app may read the
-- orders, never change them.

-- migrate:up
CREATE SCHEMA ris;

CREATE TABLE ris.order_map (
  order_no     text        PRIMARY KEY,
  accession    text        NOT NULL UNIQUE CHECK (length(accession) BETWEEN 1 AND 16),
  patient_id   text        NOT NULL,
  study_uid    text        NOT NULL CHECK (study_uid ~ '^[0-9.]{1,64}$'),
  worklist_ids jsonb       NOT NULL DEFAULT '[]'::jsonb,  -- one entry per console
  tags_hash    text        NOT NULL,
  change_seq   bigint      NOT NULL,
  state        text        NOT NULL
               CHECK (state IN ('SCHEDULED', 'PERFORMED', 'CANCELLED', 'NEEDS_REVIEW')),
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX order_map_study ON ris.order_map (study_uid);

CREATE TABLE ris.sync_cursor (
  name  text   PRIMARY KEY,
  value bigint NOT NULL
);

CREATE TABLE ris.event (
  id       uuid        PRIMARY KEY DEFAULT uuidv7(),
  at       timestamptz NOT NULL DEFAULT now(),
  actor    text        NOT NULL,
  action   text        NOT NULL,
  order_no text        NOT NULL,
  detail   jsonb       NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX event_order ON ris.event (order_no, at);

GRANT USAGE ON SCHEMA ris TO platform_orders, platform_app;
GRANT SELECT, INSERT, UPDATE ON ris.order_map, ris.sync_cursor TO platform_orders;
GRANT SELECT, INSERT ON ris.event TO platform_orders;
GRANT SELECT ON ris.order_map TO platform_app;

-- Since 24 Sep a person is their Windows logon name (Active Directory), not an
-- email. Said here, because a migration that has run is never edited.
COMMENT ON COLUMN reading.claim.reader IS 'the reader''s Windows logon name (AD sAMAccountName)';
COMMENT ON COLUMN audit.event.actor IS 'the Windows logon name, or a service name';

-- migrate:down
COMMENT ON COLUMN audit.event.actor IS NULL;
COMMENT ON COLUMN reading.claim.reader IS NULL;
DROP SCHEMA ris CASCADE;
