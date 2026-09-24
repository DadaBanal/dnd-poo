#!/usr/bin/env bash
# Generate the platform's secrets into $PMC_SECRETS (default: secrets/, which
# is git-ignored). ci/run.sh points PMC_SECRETS at a throwaway folder of its
# own, so a test run never touches a site's real secrets.
#
#   tools/make-secrets.sh          the platform's own secrets
#   tools/make-secrets.sh --test   also the stand-in Active Directory's (tests only)
#
# Idempotent: an existing secret is never overwritten, because databases and
# Keycloak were initialised with it. Prints no secret. Rotating one is a
# deliberate act: change it where it is used first, then replace the file.
#
# One secret is NOT generated: ad-bind-password, the password of the
# read-only account ICT makes in PMC's Active Directory for the sign-in. ICT
# places it here, with the certificate of the CA behind the domain
# controllers' LDAPS in tls/ad-ca.crt; Keycloak will not start without them.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dir="${PMC_SECRETS:-$here/secrets}"
mkdir -p "$dir"
chmod 700 "$dir"

rand() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c "${1:-40}" || true; }

# The files are bind-mounted into containers that run as other users
# (postgres runs as uid 999), so they must be world-readable. The 0700
# directory is what keeps other host users out.
write() {
  local path="$dir/$1" content="$2"
  if [[ -e "$path" ]]; then
    echo "kept      $1"
    return
  fi
  umask 022
  printf '%s' "$content" >"$path"
  chmod 644 "$path"
  echo "generated $1"
}

# Databases.
write pg-index-password "$(rand)"
write pg-platform-password "$(rand)"
write keycloak-db-password "$(rand)"
# PMC's platform database: the role that owns its schema (the migrations) and
# the role the front door app uses (grants only).
write platform-owner-password "$(rand)"
write platform-app-password "$(rand)"

# Sign-in. oauth2-proxy wants a cookie secret of exactly 32 bytes.
write front-door-client-secret "$(rand)"
write front-door-cookie-secret "$(rand 32)"
write admin-cli-client-secret "$(rand)"

# Between the engine and orthanc-auth-service, and the auth service's own key
# for share links.
write auth-service-password "$(rand)"
write auth-service-secret-key "$(rand 64)"

# The platform's own services (connector, monitoring, tests) call the engine
# with this API key, as the Keycloak user svc-platform.
write svc-platform-api-key "$(rand 48)"
# Backups (M3). The Kopia repository's password encrypts every backup of the
# engine's files and databases: escrow it off both hosts, or no backup can be
# read. The primary's own password may add snapshots, never delete them.
write kopia-repo-password "$(rand 48)"
write kopia-client-password "$(rand)"
write kopia-control-password "$(rand)"

# The off-site storage account's key is Azure's to issue and ICT's to place.
# Until then this is an empty file, and the off-site copy stays off (cloud
# copies wait on the DPO's answer). The tests use a stand-in's key.
if [[ "${1:-}" == "--test" ]]; then
  write backup-azure-key "$(rand 88)"
else
  write backup-azure-key ""
fi
if [[ "${1:-}" == "--test" ]]; then
  # The stand-in Active Directory in tests: its administrator, the sign-in's
  # read-only account, and the one password its invented people share.
  write ad-admin-password "$(rand)"
  write ad-bind-password "$(rand)"
  write test-user-password "$(rand 24)"
fi
