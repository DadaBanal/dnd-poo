-- 079 — the department a ticket is for (Dada, 12 Oct 2026: "can we add a
-- department mark on each tickets or a column whichever u think is best";
-- confirmed before building: a column on the Service Board with a filter, a
-- badge on the ticket, and a dropdown on the desk and on the portal's raise
-- form, already set to the requester's own department).
--
-- A name from Setup › Departments (034), written only when it matches one
-- there: the portal's dropdown offers that list, an emailed ticket takes the
-- sender's AD department when it is on it, and the desk's dropdown is the same
-- list. NULL means not known, and every ticket raised before this step reads
-- NULL until someone sets it or `ticket-departments --apply` fills it from the
-- requester's contact. No foreign key: a department is never deleted (034
-- retires it), and the code checks the name, so the step stays one column.
ALTER TABLE ticket ADD COLUMN department TEXT;
CREATE INDEX ix_ticket_department ON ticket (department);
