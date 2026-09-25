-- PSA spine — break-glass local accounts
--
-- This file lives under schema/local/, one directory below the migrations, and
-- until 25 Sep 2026 that kept it out of the SQL Server port: the spine on
-- DND-SQL01 was to be the commercial record alone, and a credential table had no
-- business there. D7 now puts the whole desk on that instance (its own database,
-- PMC_PSA), and a desk has to sign people in, so the translator includes this
-- file and db.create() applies it wherever it runs. What it holds is unchanged:
-- a salted scrypt digest, never a password, and the table ships empty.
--
-- WHY THESE EXIST. Entra SSO is the normal way in and the only way in for
-- everyone but the on-call rota. But the desk has to answer when the WAN is down
-- (§11 test 10), and Entra needs the cloud. So a small number of sealed local
-- accounts — held by whoever is on the rota — are the fallback, and only the
-- fallback.
--
-- THE RULES, enforced by where creation lives, not by hope:
--   * created only by `psaspine create-local-account`, which reads the password
--     from a no-echo prompt and never from an argument or an environment
--     variable. There is no web path that creates one.
--   * the password is never stored. scrypt_hash holds a salted scrypt digest in
--     the shape 'scrypt$N$r$p$salt_hex$hash_hex' and nothing else.
--   * every use of one writes an audit event at login. A break-glass login that
--     leaves no trace is the thing this whole arrangement exists to avoid.
--   * seeded into no repository, no fixture, no seed file. The table ships empty.

PRAGMA foreign_keys = ON;

CREATE TABLE local_account (
  username       TEXT PRIMARY KEY,
  -- 'scrypt$N$r$p$salt_hex$hash_hex'. Never a password, never reversible.
  scrypt_hash    TEXT NOT NULL,
  -- Cross-board admin (calendars, clinical floors, catalogue) as against a
  -- board-scoped ADMIN membership. Off by default; a break-glass account is not
  -- a superuser unless somebody deliberately made it one.
  is_sysadmin    INTEGER NOT NULL DEFAULT 0 CHECK (is_sysadmin IN (0, 1)),
  created_at     TEXT NOT NULL,
  -- 'cli' always. The column exists so a future non-CLI path would have to lie
  -- to hide itself, which is harder than leaving a truthful field blank.
  created_by     TEXT NOT NULL,
  last_login_at  TEXT,
  disabled       INTEGER NOT NULL DEFAULT 0 CHECK (disabled IN (0, 1))
);
