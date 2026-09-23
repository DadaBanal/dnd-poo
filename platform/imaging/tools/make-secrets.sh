#!/usr/bin/env bash
# Generate the platform's secrets into $PMC_SECRETS (default: secrets/, which
# is git-ignored). ci/run.sh points PMC_SECRETS at a throwaway folder of its
# own, so a test run never touches a site's real secrets.
#
# Idempotent: an existing secret is never overwritten, because the index was
# initialised with it. Prints no secret. Rotating one is a deliberate act:
# change it in PostgreSQL first, then replace the file.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dir="${PMC_SECRETS:-$here/secrets}"
mkdir -p "$dir"
chmod 700 "$dir"

rand() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 40 || true; }

# The files are bind-mounted into containers that run as other users
# (postgres runs as uid 999), so they must be world-readable. The 0700
# directory is what keeps other host users out.
write() {
  local path="$1" content="$2"
  if [[ -e "$path" ]]; then
    echo "kept      $(basename "$path")"
    return
  fi
  umask 022
  printf '%s' "$content" >"$path"
  chmod 644 "$path"
  echo "generated $(basename "$path")"
}

write "$dir/pg-index-password" "$(rand)"

# The one HTTP user until sign-in arrives (M2.2).
users="$dir/orthanc-users.json"
if [[ -e "$users" ]]; then
  ops="$(sed -n 's/.*"pmc-ops": *"\([A-Za-z0-9]*\)".*/\1/p' "$users")"
else
  ops="$(rand)"
fi
write "$users" "{\"RegisteredUsers\": {\"pmc-ops\": \"$ops\"}}"

# M2.1 only: the front door presents that user to the engine. Removed when
# sign-in lands; never deployed.
write "$dir/front-engine-auth.conf" \
  "proxy_set_header Authorization \"Basic $(printf 'pmc-ops:%s' "$ops" | base64 -w0)\";"
