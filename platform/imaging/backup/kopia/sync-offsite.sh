#!/bin/sh
# From the R740xd, copy the Kopia repository off-site to Azure (Path A, M3):
# new blobs only, never a deletion (no --delete), so the off-site copy only
# grows. ICT makes the container once, with an immutability policy, and this
# never makes one: a missing container fails the copy. Only when ICT has
# placed the storage key: cloud copies wait on the DPO's answer.
set -eu
if [ ! -s /run/secrets/backup-azure-key ]; then
  echo "off-site copy: not configured (no storage key); the R740xd copy stands alone"
  exit 0
fi
export KOPIA_PASSWORD="$(cat /run/secrets/kopia-repo-password)"
export AZURE_STORAGE_KEY="$(cat /run/secrets/backup-azure-key)"
kopia --config-file=/app/config/repository.config --log-dir=/app/config/logs \
  repository sync-to azure --container="${PMC_BACKUP_AZURE_KOPIA_CONTAINER:-kopia}" \
  --storage-account="${PMC_BACKUP_AZURE_ACCOUNT:?}" \
  ${PMC_BACKUP_AZURE_KOPIA_DOMAIN:+--storage-domain="$PMC_BACKUP_AZURE_KOPIA_DOMAIN"} \
  --no-progress
