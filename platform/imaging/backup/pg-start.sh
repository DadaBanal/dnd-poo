#!/bin/sh
# Start of both PostgreSQL clusters (Path A, M3): write pgBackRest's
# configuration, then start PostgreSQL as the official image does. Every
# finished write-ahead log segment is archived at once (archive_command), so
# a cluster can be restored to any second, not just to last night.
#
# The repository is the pgbackrest-repo volume. The database containers never
# leave the engine network (no route out): the nightly Kopia snapshot takes
# this repository to the R740xd, append-only, and from there off-site
# (tools/backup.sh). M4 can make the R740xd pgBackRest's repository host, for
# a copy off this host by the minute rather than by the night.
set -eu

stanza="${PMC_BACKUP_STANZA:?PMC_BACKUP_STANZA is not set}"
cat > /etc/pgbackrest/pgbackrest.conf <<EOF
[global]
repo1-path=/var/lib/pgbackrest
repo1-retention-full=2
compress-type=zst
start-fast=y
log-level-console=info
log-level-file=off

[$stanza]
pg1-path=/var/lib/postgresql/18/docker
pg1-user=${POSTGRES_USER:?}
pg1-database=${POSTGRES_DB:?}
EOF
chown postgres:postgres /etc/pgbackrest/pgbackrest.conf
chmod 640 /etc/pgbackrest/pgbackrest.conf

exec docker-entrypoint.sh "$@"
