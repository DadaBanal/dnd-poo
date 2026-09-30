-- 056: configuration types and statuses as setup tables, with typed questions
--
-- 021 fixed seven types and three statuses in a CHECK. A hospital's CMDB
-- outgrows that the day biomedical devices join it: an infusion pump is not
-- OTHER, and the questions asked of it (its asset tag, its last calibration)
-- are not asked of a printer. The reference PSA has ConfigurationType,
-- ConfigurationStatus and ConfigurationTypeQuestion; these are the same.
--
-- The 021 columns stay, and the CHECKs with them: a type MAPS TO one of the
-- seven codes and a status to one of the three, so every report, filter and
-- API shape that reads config_type or status keeps its meaning. The seven
-- and the three are written as rows on first use (configurations.
-- ensure_vocabulary), each mapping to itself; nothing is seeded here.

CREATE TABLE configuration_type (
  type_id     TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  maps_to     TEXT NOT NULL CHECK (maps_to IN
                ('WORKSTATION', 'LAPTOP', 'SERVER', 'PRINTER', 'NETWORK', 'MOBILE', 'OTHER')),
  inactive    INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1)),
  sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE configuration_status (
  status_id   TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  maps_to     TEXT NOT NULL CHECK (maps_to IN ('ACTIVE', 'INACTIVE', 'RETIRED')),
  inactive    INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1)),
  sort_order  INTEGER NOT NULL DEFAULT 0
);

-- A question a type asks of every configuration of that type.
CREATE TABLE configuration_question (
  question_id INTEGER PRIMARY KEY,
  type_id     TEXT NOT NULL REFERENCES configuration_type(type_id),
  label       TEXT NOT NULL,
  field_type  TEXT NOT NULL CHECK (field_type IN ('TEXT', 'NUMBER', 'DATE', 'CHECKBOX')),
  required    INTEGER NOT NULL DEFAULT 0 CHECK (required IN (0, 1)),
  sort_order  INTEGER NOT NULL DEFAULT 0,
  inactive    INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1))
);
CREATE INDEX ix_configuration_question_type ON configuration_question (type_id);

CREATE TABLE configuration_answer (
  configuration_id TEXT NOT NULL REFERENCES configuration(configuration_id),
  question_id      INTEGER NOT NULL REFERENCES configuration_question(question_id),
  value            TEXT,
  PRIMARY KEY (configuration_id, question_id)
);

-- The type and status a configuration has, when it is one made here; NULL
-- reads as the 021 code in config_type / status.
ALTER TABLE configuration ADD COLUMN type_id TEXT REFERENCES configuration_type(type_id);
ALTER TABLE configuration ADD COLUMN status_id TEXT REFERENCES configuration_status(status_id);
