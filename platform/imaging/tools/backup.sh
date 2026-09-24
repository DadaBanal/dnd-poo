#!/usr/bin/env bash
# The nightly backup on the primary (Path A, M3). M4 runs it from a timer;
# ci/run.sh runs it before the disaster drill.
#
#   1. each database cluster: a pgBackRest backup into the local repository
#      (full on Sundays, differential otherwise), then a check that forces
#      the current write-ahead log out to the archive
#   2. one Kopia snapshot of the engine's files and that repository, to the
#      R740xd, which accepts new snapshots and refuses deletions
#
#   tools/backup.sh [full|diff] [--prove-append-only]
#
# PMC_COMPOSE is the compose command for this site (default: docker compose).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
read -r -a compose <<<"${PMC_COMPOSE:-docker compose}"
type="${1:-}"
[[ -n "$type" ]] || { [[ "$(date +%u)" == 7 ]] && type=full || type=diff; }

for pair in pg-index:index pg-platform:platform; do
  service="${pair%%:*}" stanza="${pair##*:}"
  "${compose[@]}" exec -T -u postgres "$service" pgbackrest --stanza="$stanza" --type="$type" backup
  "${compose[@]}" exec -T -u postgres "$service" pgbackrest --stanza="$stanza" check
done
"${compose[@]}" --profile backup run --rm files-backup "${2:-}"
