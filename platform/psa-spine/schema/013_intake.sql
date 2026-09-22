-- PSA spine 013 — a ticket references a patient, it never carries one
--
-- §6.1 is the largest new risk in going hospital-wide, and it is measured rather
-- than feared: on 9 Sep 2026 a message to helpdesk@pmcne.ph carried a named
-- patient and a PhilHealth case number, in the body, on the same address as
-- printer faults [MEASURED]. Opening intake to 400 clinical staff over that path
-- scales the RA 10173 exposure instead of containing it.
--
-- The design answer is one sentence: a ticket REFERENCES a patient record and
-- never carries one. This file is the structured place for that reference, and
-- the rule that keeps it from becoming a second copy of the chart.

PRAGMA foreign_keys = ON;

-- The reference itself. A record number, nothing else — no name, no date of
-- birth, no diagnosis. Everything a fulfiller needs to find the patient in the
-- system that is actually the record of care, and nothing that makes this
-- database into a second one.
ALTER TABLE ticket ADD COLUMN patient_reference TEXT;

-- A patient reference belongs only on a board that is restricted, because
-- `restricted` is what makes membership a hard filter at the query (§5.6) and
-- what makes a read auditable (§6.1). Putting one on an open board would place a
-- patient identifier on the same queue as printer faults, which is the exact
-- defect this file exists to answer.
--
-- In the schema and not the importer, for the reason 005 gives: an importer can
-- be bypassed and a trigger cannot.
CREATE TRIGGER patient_reference_needs_a_restricted_board
BEFORE INSERT ON ticket
FOR EACH ROW
WHEN NEW.patient_reference IS NOT NULL
 AND (SELECT restricted FROM board WHERE board_id = NEW.board_id) = 0
BEGIN
  SELECT RAISE(ABORT,
    'a patient reference may only be held on a restricted board');
END;

-- The same rule on the way through, so a ticket cannot acquire one by being
-- moved or edited onto an open board.
CREATE TRIGGER patient_reference_stays_on_a_restricted_board
BEFORE UPDATE ON ticket
FOR EACH ROW
WHEN NEW.patient_reference IS NOT NULL
 AND (SELECT restricted FROM board WHERE board_id = NEW.board_id) = 0
BEGIN
  SELECT RAISE(ABORT,
    'a patient reference may only be held on a restricted board');
END;
