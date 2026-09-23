-- 021 — configurations: the machines and devices a ticket is about.
--
-- ConnectWise calls them Configurations: each belongs to a company, may have a
-- primary contact, and a ticket lists the ones it concerns. Here they are read
-- from what already knows them, starting with Active Directory's computer
-- objects, never typed in.
--
-- Hostnames only. No IP address is collected: the desk reaches a machine through
-- its remote-support tool, by session, not by address, and an address list is
-- network topology this repository and its data keep out of.
PRAGMA foreign_keys = ON;

CREATE TABLE configuration (
  configuration_id  TEXT PRIMARY KEY,
  entity_id         TEXT NOT NULL REFERENCES entity(entity_id),
  name              TEXT NOT NULL,          -- the hostname, as AD holds it
  config_type       TEXT NOT NULL CHECK (config_type IN
                      ('WORKSTATION', 'LAPTOP', 'SERVER', 'PRINTER', 'NETWORK', 'MOBILE', 'OTHER')),
  status            TEXT NOT NULL DEFAULT 'ACTIVE'
                      CHECK (status IN ('ACTIVE', 'INACTIVE', 'RETIRED')),
  contact_id        TEXT REFERENCES contact(contact_id),
  site_id           TEXT REFERENCES site(site_id),
  dns_name          TEXT,
  os_name           TEXT,
  os_version        TEXT,
  manufacturer      TEXT,
  model             TEXT,
  serial_number     TEXT,
  description       TEXT,
  -- The ScreenConnect session this machine's agent reports as. It is what a
  -- launch link needs, and nothing here can read it from ScreenConnect, so it is
  -- set on the configuration page (NOT VERIFIED: a bulk export route).
  remote_session_id TEXT,
  ad_object_guid    TEXT,
  source            TEXT NOT NULL CHECK (source IN ('AD', 'SCREENCONNECT', 'MANUAL')),
  created_at        TEXT NOT NULL,
  last_synced_at    TEXT,
  last_seen_at      TEXT                    -- AD's LastLogonDate, as a freshness hint
);

CREATE INDEX ix_configuration_entity ON configuration (entity_id);

-- One configuration per AD object; manual ones have no GUID (see 020).
CREATE UNIQUE INDEX ux_configuration_ad_guid ON configuration (ad_object_guid)
  WHERE ad_object_guid IS NOT NULL;

-- Which configurations a ticket concerns, as ConnectWise's Configurations tab.
CREATE TABLE ticket_configuration (
  work_item_id     TEXT NOT NULL REFERENCES ticket(work_item_id),
  configuration_id TEXT NOT NULL REFERENCES configuration(configuration_id),
  linked_at        TEXT NOT NULL,
  linked_by        TEXT NOT NULL,
  PRIMARY KEY (work_item_id, configuration_id)
);

-- Links out to the tools the desk does not replace: ScreenConnect first, and
-- anything else that can be opened by URL. A template names fields in braces,
-- e.g. {remote_session_id}; each value is URL-encoded when the link is drawn,
-- and a link whose field is empty is shown disabled with the reason. HTTPS only.
-- The instance's own address is typed in Setup, never shipped here.
CREATE TABLE integration_link (
  link_id      TEXT PRIMARY KEY,
  label        TEXT NOT NULL,
  applies_to   TEXT NOT NULL CHECK (applies_to IN ('CONFIGURATION', 'CONTACT')),
  url_template TEXT NOT NULL CHECK (url_template LIKE 'https://%'),
  inactive     INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1)),
  created_at   TEXT NOT NULL,
  created_by   TEXT NOT NULL
);
