#!/bin/bash
# Keycloak's start (Path A, M2.2). Reads PMC's secrets from Docker secrets into
# the environment that KC_DB_PASSWORD and the realm file's ${...} placeholders
# use, checks that every site value is set, trusts the CA behind PMC's domain
# controllers for LDAPS, then starts Keycloak. The realm file is imported only
# when the realm does not exist yet.
set -euo pipefail

secret() {
  local file="/run/secrets/$1"
  if [[ ! -s "$file" ]]; then echo "Keycloak: the secret $1 is missing" >&2; exit 1; fi
  cat "$file"
}

export KC_DB_PASSWORD="$(secret keycloak-db-password)"
export PMC_FRONT_DOOR_CLIENT_SECRET="$(secret front-door-client-secret)"
export PMC_ADMIN_CLI_CLIENT_SECRET="$(secret admin-cli-client-secret)"
export PMC_SVC_PLATFORM_API_KEY="$(secret svc-platform-api-key)"
# The read-only account ICT makes in PMC's Active Directory for the sign-in;
# placed by ICT, never generated.
export PMC_AD_BIND_PASSWORD="$(secret ad-bind-password)"

# LDAPS to the domain controllers is trusted only through the CA ICT names
# (secrets/tls/ad-ca.crt), never by skipping the check.
if [[ ! -s /run/secrets/ad-ca.pem ]]; then
  echo "Keycloak: the AD's CA certificate is missing (secrets/tls/ad-ca.crt)" >&2
  exit 1
fi
export KC_TRUSTSTORE_PATHS=/run/secrets/ad-ca.pem

for name in PMC_HOSTNAME PMC_ACCESS_TOKEN_SECONDS PMC_AD_URL PMC_AD_USERS_DN PMC_AD_GROUPS_DN \
    PMC_AD_BIND_DN PMC_AD_GROUP_RADIOLOGISTS PMC_AD_GROUP_CARDIOLOGISTS \
    PMC_AD_GROUP_TECHNOLOGISTS PMC_AD_GROUP_REFERRERS PMC_AD_GROUP_ICT_ADMINS; do
  if [[ -z "${!name:-}" ]]; then
    echo "Keycloak: $name is not set (see platform/imaging/README.md, Sign-in)" >&2
    exit 1
  fi
done

exec /opt/keycloak/bin/kc.sh start --import-realm
