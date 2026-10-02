-- 064: a note may be written as rich text (Dada, 2 Oct 2026: "a proper text
-- editor via html or like html or teams text editor").
--
-- A technician writes a note the way they write a Teams message, and pastes
-- out of Outlook or Word. So `ticket_event.detail` may now hold HTML as well
-- as plain text, and this column says which it is: NULL or 'TEXT' for every
-- note ever written until now and every note that arrives by email, 'HTML'
-- for one written in the editor.
--
-- Nothing is stored as HTML until `richtext.clean` has rebuilt it out of its
-- own allow-lists, and the PHI scan reads `richtext.text` of it, never the
-- markup, so a patient's name cannot hide inside an attribute.
ALTER TABLE ticket_event ADD COLUMN body_format TEXT;   -- NULL reads as TEXT

-- And the requester's email carries the note as it was written. The text of
-- the email is always there; this is the same email with the note's own
-- formatting in it, built when the note is written and sent as the HTML part.
ALTER TABLE notification ADD COLUMN body_html TEXT;
