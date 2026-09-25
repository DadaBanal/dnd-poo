-- PSA spine -- machine API tokens
--
-- Beside local_account.sql, and ported for the same reason since 25 Sep 2026:
-- the desk runs on the SQL Server instance (D7), so the table that lets a
-- monitoring machine raise a ticket runs there too. It holds the sha256 of a
-- token, never the token.
--
-- WHY A TOKEN AND NOT ENTRA. A machine could hold an Entra app registration and
-- present a client-credentials token, and the RS256 check in web/auth.py would
-- verify it. But §6.2 is the whole argument for building on premises: a desk
-- that needs the WAN is unavailable exactly when it is most needed, and the
-- monitoring system raising "the WAN is down" cannot fetch an Entra token while
-- the WAN is down. So machines get a local token, and only machines do.
--
-- THE RULES, enforced by where creation lives:
--   * created only by `psaspine create-api-token`, which prints the token ONCE
--     and stores only its sha256. There is no web path that creates one.
--   * sha256 and not scrypt, deliberately: scrypt exists to make guessing a
--     low-entropy password expensive. A token is 256 random bits; nobody guesses
--     it, and a slow hash on every API call buys nothing but latency.
--   * scoped to ONE board. A token raises tickets onto its board and reads only
--     tickets it raised; it cannot see a restricted board it was not issued for.
--   * every use is audited.

PRAGMA foreign_keys = ON;

CREATE TABLE api_token (
  token_id      TEXT PRIMARY KEY,
  -- sha256 of the token, lower-case hex. The token itself is never stored.
  token_sha256  TEXT NOT NULL,
  -- What it is for, in words: 'orthanc monitoring', 'UPS alerts'.
  label         TEXT NOT NULL,
  board_id      TEXT NOT NULL REFERENCES board(board_id),
  created_at    TEXT NOT NULL,
  created_by    TEXT NOT NULL,
  last_used_at  TEXT,
  disabled      INTEGER NOT NULL DEFAULT 0 CHECK (disabled IN (0, 1))
);

-- One token, one row. A table-level unique index rather than an inline UNIQUE
-- because the port's DDL reader takes the former and refuses the latter.
CREATE UNIQUE INDEX ux_api_token_sha256 ON api_token (token_sha256);
