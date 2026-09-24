#!/bin/sh
# Disaster recovery (Path A, M3): the primary and the R740xd are both lost.
# Connect READ-ONLY to the off-site copy in Azure, verify every file of every
# snapshot, then restore the latest snapshot of each source into /restore
# (new, empty volumes):
#   /restore/engine-files       the engine's DICOM files
#   /restore/database-backups   the pgBackRest repository, to restore both
#                               clusters from (ci/restore-drill.sh)
# Needs the repository password and the storage key, which are escrowed off
# both hosts.
set -eu
export KOPIA_PASSWORD="$(cat /run/secrets/kopia-repo-password)"
export AZURE_STORAGE_KEY="$(cat /run/secrets/backup-azure-key)"
k="kopia --config-file=/tmp/restore.config --log-dir=/tmp/logs"
$k repository connect azure --readonly --container="${PMC_BACKUP_AZURE_KOPIA_CONTAINER:-kopia}" \
  --storage-account="${PMC_BACKUP_AZURE_ACCOUNT:?}" \
  ${PMC_BACKUP_AZURE_KOPIA_DOMAIN:+--storage-domain="$PMC_BACKUP_AZURE_KOPIA_DOMAIN"} \
  --override-hostname=dr-host --override-username=restore
$k snapshot verify --verify-files-percent=100 --file-parallelism=4
for name in engine-files database-backups; do
  id=$($k snapshot list "orthanc@pmc-primary:/sources/$name" --json | tr -d '\n ' | grep -o '"id":"[0-9a-f]*"' | tail -1 | cut -d'"' -f4)
  [ -n "$id" ] || { echo "no off-site snapshot of $name"; exit 1; }
  $k snapshot restore "$id" "/restore/$name" --no-progress
  echo "restored $name from off-site snapshot $id"
done
