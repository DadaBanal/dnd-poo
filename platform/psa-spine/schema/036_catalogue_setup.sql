-- 036 — the catalogue setup tables: Areas, Subtypes and Items are edited in Setup.
--
-- The reference PSA's Service Board setup table lets a person add, rename and
-- inactivate a Type, a Subtype and an Item, and associate them (VERIFIED,
-- docs.connectwise.com/ConnectWise_Documentation/090/020/170/100/020). Until
-- now the desk's tree came only from the template or the CLI. Setup ›
-- Catalogue now edits it: an area (service_family), a subtype
-- (service_component, retired with is_draft as before) and an item verb
-- (service_action) each get a name, a retire flag and an audit row per change.
-- Nothing is ever deleted: a retired area or item stays on every ticket that
-- carries it and leaves the pickers.
--
-- The two new columns are NULL-able by the port's rule (an added column may not
-- be NOT NULL); NULL reads as 0, in use.
PRAGMA foreign_keys = ON;

ALTER TABLE service_family ADD COLUMN inactive INTEGER DEFAULT 0 CHECK (inactive IN (0, 1));
ALTER TABLE service_action ADD COLUMN inactive INTEGER DEFAULT 0 CHECK (inactive IN (0, 1));
