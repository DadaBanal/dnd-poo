#!/bin/bash
# pg-platform's first start only (docker-entrypoint-initdb.d): Keycloak's own
# database, and PMC's platform database, each with its own login roles. The
# passwords are read inside psql, so they never appear on a command line.
# A database is open only to its own roles, not to every login.
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
\set kc_password `cat /run/secrets/keycloak-db-password`
CREATE ROLE keycloak LOGIN PASSWORD :'kc_password';
CREATE DATABASE keycloak OWNER keycloak;
REVOKE CONNECT ON DATABASE keycloak FROM PUBLIC;

-- The platform database (db/migrations): platform_owner owns every object and
-- runs the migrations; the front door app logs in as platform_app, which the
-- migrations grant only what it needs.
\set owner_password `cat /run/secrets/platform-owner-password`
\set app_password `cat /run/secrets/platform-app-password`
CREATE ROLE platform_owner LOGIN PASSWORD :'owner_password';
CREATE ROLE platform_app LOGIN PASSWORD :'app_password';
-- The BizBox connector (M3.2): its own role, granted only the ris schema.
\set orders_password `cat /run/secrets/platform-orders-password`
CREATE ROLE platform_orders LOGIN PASSWORD :'orders_password';
CREATE DATABASE platform OWNER platform_owner;
REVOKE CONNECT ON DATABASE platform FROM PUBLIC;
GRANT CONNECT ON DATABASE platform TO platform_app, platform_orders;
SQL
