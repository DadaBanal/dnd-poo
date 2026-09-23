#!/bin/bash
# pg-platform's first start only (docker-entrypoint-initdb.d): Keycloak's own
# database and login role. The password is read inside psql, so it never
# appears on a command line.
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
\set kc_password `cat /run/secrets/keycloak-db-password`
CREATE ROLE keycloak LOGIN PASSWORD :'kc_password';
CREATE DATABASE keycloak OWNER keycloak;
SQL
