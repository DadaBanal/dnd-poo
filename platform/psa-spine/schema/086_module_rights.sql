-- 086 — rights per module, per person (SQL01's Part 99 ruling, 14 Oct 2026;
-- Dada: "the procurement module should be like what's everything on bizbox
-- mms but better, the menu on top and only visible to who has access to the
-- procurement module and proper rbac to modules to users").
--
-- BizBox grants access per user per submodule (appsysUserSubmodules: 655
-- people hold Expense Requisition Details, 570 Stock Requisition Details, a
-- dozen hold receiving and physical count). The desk's four Procurement areas
-- could not say that, so:
--
--   * the unit of grant is the MMS module. Six more modules join the four in
--     security.MODULES — purchase requisitions, stock requisitions, expense
--     requisitions, stock issuances, expense issuances, physical count — as
--     rows in role_grant like every other module (its module column carries
--     any name; no change to that table). A role written before 086 has no
--     row for a new module and keeps the level of the area the module came
--     out of (purchase requisitions from purchase orders, the rest from
--     items) until Setup saves one: nobody loses or gains a page on the day
--     this is applied.
--   * a level set for one person on one module wins over their role for that
--     module and that module only (SQL01, Part 100: "role as the base, a
--     per-user override that wins, Setup able to set one person on one module
--     in one screen"). That is this table. Removing the row puts the person
--     back on their role. A system administrator holds everything regardless;
--     "never one's own" on approval is unchanged.
--
-- Every write to it is audited (audit_event, action SECURITY_ROLE), as the
-- roles are.
CREATE TABLE member_module_grant (
  member   TEXT NOT NULL,
  module   TEXT NOT NULL,
  level    TEXT NOT NULL CHECK (level IN ('NONE', 'READ', 'WRITE', 'ADMIN')),
  set_at   TEXT NOT NULL,
  set_by   TEXT NOT NULL,
  PRIMARY KEY (member, module)
);
