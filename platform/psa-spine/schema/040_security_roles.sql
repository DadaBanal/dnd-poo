-- 040 — security roles, in the reference PSA's shape.
--
-- Its Security Roles setup table grants each module a level (none, inquire,
-- add/edit, all) per role, and every member has one role. Dada PSA keeps that
-- for the modules that are not boards: the knowledge base, projects, reports,
-- the schedule and finance (the BizBox mirror). A board's own tickets are still
-- governed by board membership (006), which a role never widens: a restricted
-- board stays members-only whatever a role says. A member with no role row
-- takes the default role; a system administrator holds every module at ADMIN.
PRAGMA foreign_keys = ON;

CREATE TABLE security_role (
  role_id     TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  is_default  INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
  inactive    INTEGER NOT NULL DEFAULT 0 CHECK (inactive IN (0, 1))
);

CREATE TABLE role_permission (
  role_id  TEXT NOT NULL REFERENCES security_role(role_id),
  module   TEXT NOT NULL CHECK (module IN ('KNOWLEDGE', 'PROJECTS', 'REPORTS', 'SCHEDULE', 'FINANCE')),
  level    TEXT NOT NULL CHECK (level IN ('NONE', 'READ', 'WRITE', 'ADMIN')),
  PRIMARY KEY (role_id, module)
);

CREATE TABLE member_role (
  member       TEXT PRIMARY KEY,
  role_id      TEXT NOT NULL REFERENCES security_role(role_id),
  assigned_at  TEXT NOT NULL,
  assigned_by  TEXT NOT NULL
);
