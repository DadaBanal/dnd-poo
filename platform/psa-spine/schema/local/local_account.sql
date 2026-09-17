-- PSA spine — break-glass local accounts (SQLite only, never ported)
--
-- This file is NOT under schema/*.sql, and that is deliberate. The generator in
-- tools/sqlite_to_tsql.py globs schema/*.sql non-recursively; so does
-- db.create(). Living one directory down, this table is applied to the local
-- SQLite pilot database by db.create() explicitly, and is never emitted into the
-- SQL Server port on DND-SQL01. A credential table has no business on the
-- commercial spine, and a T-SQL copy of one is a credential store nobody
-- reviewed.
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

CREATE TABLE IF NOT EXISTS local_account (
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
