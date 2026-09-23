#!/usr/bin/env bash
# Start the engine, test it, restart it from its volumes alone, test again.
# The same script runs in the cloud build and in GitHub Actions.
#
#   ci/run.sh          run everything, then remove the test stack and its volumes
#   KEEP=1 ci/run.sh   leave the test stack running afterwards, to look around
#
# It runs as its own compose project (pmc-imaging-test), so it can never
# touch the volumes of a real engine, which runs as pmc-imaging.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$here"

compose=(docker compose -p pmc-imaging-test -f compose.yaml -f compose.test.yaml)
runner=("${compose[@]}" --profile test run --rm --user "$(id -u):$(id -g)" tests)

step() { printf '\n== %s\n' "$*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

finish() {
  local status=$?
  if [[ $status -ne 0 ]]; then
    step "engine and index logs (last 200 lines each)"
    "${compose[@]}" logs --no-color --tail 200 orthanc pg-index || true
  fi
  if [[ "${KEEP:-0}" != 1 ]]; then
    "${compose[@]}" --profile test down -v --remove-orphans >/dev/null 2>&1 || true
  fi
  exit "$status"
}
trap finish EXIT

step "secrets"
tools/make-secrets.sh

step "test runner image"
build=(docker build -t pmc-imaging/tests:local)
if [[ -n "${HTTPS_PROXY:-}" ]]; then
  # A build host behind a proxy (the cloud build): let the build reach it,
  # and trust its CA for the one install step.
  build+=(--network host --build-arg HTTPS_PROXY)
  ca="${PIP_CERT:-${SSL_CERT_FILE:-}}"
  if [[ -n "$ca" && -s "$ca" ]]; then build+=(--secret "id=build-ca,src=$ca"); fi
fi
"${build[@]}" tests

step "engine and index, from empty volumes"
"${compose[@]}" --profile test down -v --remove-orphans >/dev/null 2>&1 || true
mkdir -p .results
rm -f .results/*.json
"${compose[@]}" up -d --wait pg-index orthanc

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

step "tests against a fresh engine"
"${runner[@]}" -m "not after_restart"

step "remove the containers, keep the volumes, start again"
"${compose[@]}" --profile test down --remove-orphans
"${compose[@]}" up -d --wait pg-index orthanc

step "tests after the restart"
RUN_PHASE=after_restart "${runner[@]}" -m after_restart

step "measured on synthetic data, on this host"
cat .results/measurements-first.json
echo
step "PASS"
