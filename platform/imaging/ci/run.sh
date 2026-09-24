#!/usr/bin/env bash
# Start the platform, test it, restart it from its volumes alone, test again;
# back it up, lose the primary and the R740xd, rebuild from the off-site copy
# alone, test again. The same script runs in the cloud build and in GitHub
# Actions.
#
#   ci/run.sh          run everything, then remove the test stack and its volumes
#   KEEP=1 ci/run.sh   leave the test stack running afterwards, to look around
#
# It runs as its own compose project (pmc-imaging-test) with its own throwaway
# secrets (.test-secrets/) and a test hostname, so it can never touch a real
# platform's volumes, secrets or certificate.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$here"

export PMC_SECRETS="$here/.test-secrets"
export PMC_HOSTNAME="imaging.pmcne.test"   # RFC 2606 .test: never a real site

project=pmc-imaging-test
compose=(docker compose -p "$project" -f compose.yaml -f compose.r740xd.yaml -f compose.test.yaml)
export PMC_COMPOSE="${compose[*]}" PMC_PROJECT="$project"
as_me=(--user "$(id -u):$(id -g)")

step() { printf '\n== %s\n' "$*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

finish() {
  local status=$?
  if [[ $status -ne 0 ]]; then
    step "logs (last 150 lines each)"
    "${compose[@]}" logs --no-color --tail 150 || true
  fi
  if [[ "${KEEP:-0}" != 1 ]]; then
    "${compose[@]}" --profile test down -v --remove-orphans >/dev/null 2>&1 || true
  fi
  exit "$status"
}
trap finish EXIT

step "throwaway secrets, a stand-in Entra ID and a test certificate for $PMC_HOSTNAME"
rm -rf "$PMC_SECRETS"
tools/make-secrets.sh --test
tools/make-test-tls.sh
PMC_KOPIA_SERVER_FINGERPRINT="$(cat "$PMC_SECRETS/tls/kopia-server.fp")"
export PMC_KOPIA_SERVER_FINGERPRINT

step "images: PostgreSQL with pgBackRest, the front door app, and the two test runners"
build=(docker build)
if [[ -n "${HTTPS_PROXY:-}" ]]; then
  # A build host behind a proxy (the cloud build): let the build reach it,
  # and trust its CA for the one install step.
  build+=(--network host --build-arg HTTPS_PROXY)
  ca="${PIP_CERT:-${SSL_CERT_FILE:-}}"
  if [[ -n "$ca" && -s "$ca" ]]; then build+=(--secret "id=build-ca,src=$ca"); fi
fi
"${build[@]}" --build-arg "PMC_LIBRARY=${PMC_LIBRARY:-docker.io/library}" -t pmc-imaging/postgres:local backup/postgres
"${build[@]}" --build-arg "PMC_LIBRARY=${PMC_LIBRARY:-docker.io/library}" -t pmc-imaging/app:local app
"${build[@]}" -t pmc-imaging/tests:local tests
"${build[@]}" -t pmc-imaging/browser:local browser

step "the platform, from empty volumes"
"${compose[@]}" --profile test down -v --remove-orphans >/dev/null 2>&1 || true
rm -rf .results
mkdir -p .results
"${compose[@]}" up -d --wait

step "the index: PostgreSQL 18.6, data checksums on, built-in C.UTF-8 collation"
sql() { "${compose[@]}" exec -T pg-index psql -U orthanc -d orthanc -Atc "$1"; }
version="$(sql 'show server_version')"
[[ "$version" == 18.6* ]] || fail "server_version is $version"
[[ "$(sql 'show data_checksums')" == on ]] || fail "data checksums are off"
locale="$(sql "select datlocprovider::text || ' ' || datlocale from pg_database where datname = current_database()")"
[[ "$locale" == "b C.UTF-8" ]] || fail "collation is $locale"
echo "ok: $version, checksums on, $locale"

step "the engine: index in PostgreSQL only, and no route out"
if "${compose[@]}" exec -T orthanc test -e /var/lib/orthanc/db/index; then
  fail "a SQLite index file exists beside the images"
fi
if "${compose[@]}" exec -T orthanc python3 -c \
    'import socket; socket.create_connection(("pypi.org", 443), timeout=5)' 2>/dev/null; then
  fail "the engine reached the internet"
fi
echo "ok: no SQLite index, no route out"

step "the platform database: the committed schema, and an audit record the app cannot change"
"${compose[@]}" run --rm --no-deps -v "$here/.results:/out" --entrypoint /bin/sh migrate -c \
  'DATABASE_URL="postgres://platform_owner:$(cat /run/secrets/platform-owner-password)@pg-platform:5432/platform?sslmode=disable" exec dbmate --schema-file /out/schema.sql dump'
diff -u db/schema.sql .results/schema.sql || fail "the platform database is not db/schema.sql (README: Regenerating db/schema.sql)"
psql_platform() { "${compose[@]}" exec -T pg-platform psql -U pmc -d platform -Atc "$1"; }
[[ "$(psql_platform "select has_table_privilege('platform_app', 'audit.event', 'UPDATE') or has_table_privilege('platform_app', 'audit.event', 'DELETE')")" == f ]] \
  || fail "the app's role may change or delete the audit record"
echo "ok: schema as committed; the app may only add to the audit record"

step "engine tests (DICOM, REST, DICOMweb, a person's session, the app's API) against a fresh engine"
"${compose[@]}" --profile test run --rm "${as_me[@]}" tests -m "not after_restart"

step "browser tests: sign-in, the front door, the worklist and the viewer"
"${compose[@]}" --profile test run --rm "${as_me[@]}" --entrypoint python tests seed.py
"${compose[@]}" --profile test run --rm "${as_me[@]}" browser

step "remove the containers, keep the volumes, start again"
"${compose[@]}" --profile test down --remove-orphans
"${compose[@]}" up -d --wait

step "after the restart"
RUN_PHASE=after_restart "${compose[@]}" --profile test run --rm "${as_me[@]}" tests -m after_restart
RUN_PHASE=after_restart "${compose[@]}" --profile test run --rm "${as_me[@]}" browser -g "cathlab run opens playing"

step "the nightly backup: both databases, then the engine's files, to the R740xd and off-site"
tools/backup.sh full --prove-append-only
# ICT makes the off-site container once, with its immutability policy, before
# the first copy; here the test makes it in the stand-in.
"${compose[@]}" exec -T azurite node /pmc/azure-standin-container.mjs
tools/offsite.sh

step "disaster: the primary and the R740xd are lost; rebuild from the off-site copy alone"
ci/restore-drill.sh

step "after the disaster: everything is back"
RUN_PHASE=after_disaster "${compose[@]}" --profile test run --rm "${as_me[@]}" tests -m after_restart
RUN_PHASE=after_disaster "${compose[@]}" --profile test run --rm "${as_me[@]}" browser -g "cathlab run opens playing"

step "measured on synthetic data, on this host"
cat .results/measurements-first.json .results/measurements-browser-first.json .results/measurements-access.json .results/measurements-drill.json
echo
step "PASS"
