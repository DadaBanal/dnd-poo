#!/usr/bin/env bash
# The disaster drill (Path A, M3), for ci/run.sh's test project ONLY: it
# deletes the primary's and the R740xd's volumes. It refuses any other
# project.
#
# The primary and the R740xd are both lost; only the off-site copy survives
# (Azure; here its stand-in). Rebuild the site from that alone:
#   1. the engine's files and the database backups, from the off-site Kopia
#      copy (every file verified first);
#   2. both database clusters, from those backups, replaying every archived
#      write-ahead log segment;
#   3. the whole platform, started on what was restored.
# ci/run.sh then runs the after-restart checks: every study, every file's
# MD5, every modality, a pending order, sign-in, the audit trail.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
read -r -a compose <<<"${PMC_COMPOSE:?}"
project="${PMC_PROJECT:?}"
[[ "$project" == *-test ]] || { echo "refusing: $project is not a test project" >&2; exit 1; }

ms() { echo $(( ($(date +%s%N) - $1) / 1000000 )); }

echo "-- the primary and the R740xd are lost"
"${compose[@]}" --profile test down --remove-orphans
for volume in pg-index-data pg-platform-data orthanc-storage pgbackrest-repo backup-status \
    watch-state prometheus-data alertmanager-data kopia-repo kopia-config; do
  docker volume rm "${project}_${volume}" >/dev/null
done
echo "deleted: both database clusters, the engine's files, the database backups, the monitoring's state, the R740xd's copy"

echo "-- rebuild from the off-site copy"
t=$(date +%s%N)
"${compose[@]}" up -d --wait azurite
"${compose[@]}" --profile restore run --rm files-restore
files_ms=$(ms "$t")
t=$(date +%s%N)
for service in pg-index pg-platform; do
  "${compose[@]}" run --rm --no-deps --entrypoint /pmc/backup/pg-restore.sh "$service"
done
databases_ms=$(ms "$t")
t=$(date +%s%N)
"${compose[@]}" up -d --wait
start_ms=$(ms "$t")

# Archiving works again on the restored clusters (a new timeline).
for pair in pg-index:index pg-platform:platform; do
  "${compose[@]}" exec -T -u postgres "${pair%%:*}" pgbackrest --stanza="${pair##*:}" check
done

printf '{"files_restored_ms": %s, "databases_restored_ms": %s, "platform_started_ms": %s}\n' \
  "$files_ms" "$databases_ms" "$start_ms" | tee .results/measurements-drill.json
