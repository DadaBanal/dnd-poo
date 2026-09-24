#!/bin/bash
# Tests only: make the stand-in BizBox's database (once) and the connector's
# read-only login. SQL Server answers "SELECT 1", and so looks healthy, a
# moment before it can create a database (MEASURED in the research proof), so
# this retries.
set -euo pipefail
sql() { /opt/mssql-tools18/bin/sqlcmd -C -S bizbox -U sa -P "$(cat /run/secrets/bizbox-sa-password)" -b "$@"; }
for attempt in $(seq 1 20); do
  if exists="$(sql -h -1 -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM sys.databases WHERE name = 'BizBoxSim'" 2>&1)"; then
    if [[ "$(echo "$exists" | tr -d '[:space:]')" == 0 ]]; then
      sql -i /init/schema.sql >/tmp/schema.log 2>&1 || { tail -3 /tmp/schema.log; sleep 3; continue; }
    fi
    sql -v ro_password="$(cat /run/secrets/bizbox-password)" -i /init/login.sql
    echo "stand-in BizBox ready (attempt $attempt)"
    exit 0
  fi
  sleep 3
done
echo "stand-in BizBox did not come up" >&2
exit 1
