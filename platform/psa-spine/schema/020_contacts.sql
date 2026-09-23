-- 020 — contacts: who asks, as ConnectWise keeps them under each company.
--
-- entity is the company (PMC, JRBY-CI, ...). A contact is a person at one,
-- almost always a member of staff synced from PMC's Active Directory. These
-- are staff, never patients: nothing here is a patient identifier.
--
-- ad_object_guid is the AD objectGUID: stable across renames, so a sync never
-- mistakes a renamed person for a new one. A person disabled in AD is marked
-- inactive, never deleted, because their old tickets still name them.
PRAGMA foreign_keys = ON;

CREATE TABLE contact (
  contact_id     TEXT PRIMARY KEY,
  entity_id      TEXT NOT NULL REFERENCES entity(entity_id),
  display_name   TEXT NOT NULL,
  email          TEXT,
  phone          TEXT,
  department     TEXT,                    -- ward or department, as AD holds it
  title          TEXT,
  office         TEXT,
  upn            TEXT,
  sam_account    TEXT,
  ad_object_guid TEXT,
  source         TEXT NOT NULL CHECK (source IN ('AD', 'ENTRA', 'MANUAL', 'INTAKE')),
  inactive       INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1)),
  created_at     TEXT NOT NULL,
  last_synced_at TEXT
);

CREATE INDEX ix_contact_email ON contact (email);

-- One contact per AD object. Manual contacts have no GUID, and there may be many
-- of them, so NULL is kept out of the index (see the translator's emit_index).
CREATE UNIQUE INDEX ux_contact_ad_guid ON contact (ad_object_guid)
  WHERE ad_object_guid IS NOT NULL;

-- Which contact a ticket is for. requested_by keeps what intake was told,
-- verbatim; contact_id is the resolved person, when there is one.
ALTER TABLE ticket ADD COLUMN contact_id TEXT REFERENCES contact(contact_id);
