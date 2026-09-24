#!/bin/bash
# pg-index's first start only (docker-entrypoint-initdb.d): the engine's own
# login role, which owns the index database and nothing else. The cluster's
# superuser (POSTGRES_USER) is for backups and ICT; the engine never logs in
# as it. The password is read inside psql, so it never appears on a command
# line. The database is open only to the engine, not to every login.
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
\set engine_password `cat /run/secrets/pg-index-password`
CREATE ROLE orthanc LOGIN PASSWORD :'engine_password';
ALTER DATABASE orthanc OWNER TO orthanc;
REVOKE CONNECT ON DATABASE orthanc FROM PUBLIC;
GRANT CONNECT ON DATABASE orthanc TO orthanc;
SQL
