-- 048 — the life of a machine: bought when, under warranty until when,
-- installed when, from whom, under which agreement, where it stands.
--
-- A DOH inspection asks for the maintenance record per asset; a service
-- manager asks which warranties end this quarter. 021 holds what Active
-- Directory knows about a machine; this adds what only the desk can know.
-- Added columns are NULL-able (a migration invents no data) and the
-- configuration page edits them; the report writer gains a Configurations
-- dataset and a Maintenance dataset (tickets by configuration), and a
-- machine's page exports its maintenance record as CSV.
PRAGMA foreign_keys = ON;

ALTER TABLE configuration ADD COLUMN purchased_on TEXT;
ALTER TABLE configuration ADD COLUMN warranty_ends_on TEXT;
ALTER TABLE configuration ADD COLUMN installed_on TEXT;
ALTER TABLE configuration ADD COLUMN vendor TEXT;
ALTER TABLE configuration ADD COLUMN purchase_ref TEXT;      -- the BizBox PO number, as a plain reference
ALTER TABLE configuration ADD COLUMN location TEXT;          -- the ward and room, in words
ALTER TABLE configuration ADD COLUMN agreement_id TEXT REFERENCES agreement(agreement_id);
