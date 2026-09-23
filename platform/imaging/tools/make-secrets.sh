#!/usr/bin/env bash
# Generate the engine's secrets into platform/imaging/secrets/ (git-ignored).
#
# Idempotent: an existing secret is never overwritten, because the index was
# initialised with it. Prints no secret. Rotating one is a deliberate act:
# change it in PostgreSQL first, then replace the file.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dir="$here/secrets"
mkdir -p "$dir"
chmod 700 "$dir"

rand() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 40 || true; }

# The files are bind-mounted into containers that run as other users
# (postgres runs as uid 999), so they must be world-readable. The 0700
# directory is what keeps other host users out.
write() {
  local path="$1" content="$2"
  if [[ -e "$path" ]]; then
    echo "kept      ${path#"$here"/}"
    return
  fi
  umask 022
  printf '%s' "$content" >"$path"
  chmod 644 "$path"
  echo "generated ${path#"$here"/}"
}

write "$dir/pg-index-password" "$(rand)"

# The one HTTP user until the front door brings single sign-on (M2).
write "$dir/orthanc-users.json" "{\"RegisteredUsers\": {\"pmc-ops\": \"$(rand)\"}}"
