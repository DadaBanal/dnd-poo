#!/usr/bin/env bash
# The nightly off-site copy, on the R740xd (Path A, M3): Kopia's repository
# to Azure, new blobs only, after the primary's snapshot has landed. Does
# nothing until ICT has placed the storage key (cloud copies wait on the
# DPO's answer). M4 runs it from a timer on the R740xd.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
read -r -a compose <<<"${PMC_COMPOSE:-docker compose}"
"${compose[@]}" exec -T kopia-server sh /pmc/kopia/sync-offsite.sh
