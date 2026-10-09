-- 077: the Outlook entry itself, for its owner.
--
-- 059 kept Outlook busy times only, "never a subject, an attendee or a body".
-- Dada, 9 Oct 2026, reversing that for one reader: "if owner owns outlook show
-- exact schedule dont just show free busy on the calendars". Confirmed before
-- building: the subject and location are kept as Outlook has them, with no
-- patient-detail check (Dada's choice); an entry marked Private or
-- Confidential in Outlook keeps neither; and only the person whose calendar it
-- is sees them. Everyone else still reads Busy, Tentative, Out of office or
-- Working elsewhere. Attendees and the body are still never kept.
ALTER TABLE outlook_busy ADD COLUMN subject TEXT;
ALTER TABLE outlook_busy ADD COLUMN location TEXT;
ALTER TABLE outlook_busy ADD COLUMN private INTEGER DEFAULT 0;
