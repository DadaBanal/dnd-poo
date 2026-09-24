#!/bin/sh
# Rebuild a cluster from its pgBackRest repository (Path A, M3), into an
# empty data volume: the latest backup, then every archived write-ahead log
# segment after it. PostgreSQL replays them at its next start and opens for
# business at the end of the archive. Run as a one-off container of the
# cluster's own service, before that service starts (tools/restore-drill.sh).
set -eu
stanza="${PMC_BACKUP_STANZA:?}"
cat > /etc/pgbackrest/pgbackrest.conf <<CONF
[global]
repo1-path=/var/lib/pgbackrest
log-level-console=info
log-level-file=off

[$stanza]
pg1-path=/var/lib/postgresql/18/docker
CONF
mkdir -p /var/lib/postgresql/18/docker
chown -R postgres:postgres /var/lib/postgresql /var/lib/pgbackrest
chmod 700 /var/lib/postgresql/18/docker
exec gosu postgres pgbackrest --stanza="$stanza" restore
