#!/bin/sh
# The primary's nightly snapshot (Path A, M3), to the R740xd's Kopia server,
# always after the databases' own backup. Two sources, each mounted read-only,
# in this order:
#   /sources/database-backups   the pgBackRest repository of both clusters
#   /sources/engine-files       the engine's DICOM files
# The database backups go first. The engine writes a file before it indexes
# it, so an index restored from them never names a file the snapshot missed.
#
#   --prove-append-only   then try to delete a snapshot just made, with the
#                         same credentials, and fail unless the server refuses
#                         (ci/run.sh proves the ACL on every run)
set -u
export KOPIA_PASSWORD="$(cat /run/secrets/kopia-client-password)"
k="kopia --config-file=/tmp/client.config --log-dir=/tmp/logs"
$k repository connect server --url="${PMC_KOPIA_SERVER_URL:?}" \
  --server-cert-fingerprint="${PMC_KOPIA_SERVER_FINGERPRINT:?}" \
  --override-username=orthanc --override-hostname=pmc-primary >/tmp/connect.log 2>&1 || { cat /tmp/connect.log; exit 1; }
last=""
for name in database-backups engine-files; do
  src="/sources/$name"
  $k snapshot create "$src" --description="nightly" --no-progress >/tmp/create.log 2>&1 || { cat /tmp/create.log; exit 1; }
  last=$($k snapshot list "$src" --json | tr -d '\n ' | grep -o '"id":"[0-9a-f]*"' | tail -1 | cut -d'"' -f4)
  [ -n "$last" ] || { echo "no snapshot listed for $src"; exit 1; }
  echo "snapshot $last of $src"
done
if [ "${1:-}" = "--prove-append-only" ]; then
  if $k snapshot delete "$last" --delete >/tmp/delete.log 2>&1; then
    echo "FAIL: the primary deleted its own snapshot"; exit 1
  fi
  echo "ok: the primary cannot delete a snapshot"
fi
