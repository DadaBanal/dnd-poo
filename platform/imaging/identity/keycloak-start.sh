#!/bin/bash
# Keycloak's start (Path A, M2.2). Reads PMC's secrets from Docker secrets into
# the environment that KC_DB_PASSWORD and the realm files' ${...} placeholders
# use, checks that every site value is set, then starts Keycloak. The realm
# files are imported only when their realm does not exist yet.
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
# Issued by Entra ID for PMC's app registration; placed by ICT, never generated.
export PMC_ENTRA_CLIENT_SECRET="$(secret entra-client-secret)"
# Test runs only: the password of the stand-in Entra's invented users.
if [[ -s /run/secrets/test-user-password ]]; then
  export PMC_TEST_USER_PASSWORD="$(cat /run/secrets/test-user-password)"
fi

for name in PMC_HOSTNAME PMC_ENTRA_CLIENT_ID PMC_ENTRA_AUTHORIZATION_URL \
    PMC_ENTRA_TOKEN_URL PMC_ENTRA_JWKS_URL PMC_ENTRA_USERINFO_URL PMC_ENTRA_ISSUER \
    PMC_ENTRA_GROUP_RADIOLOGISTS PMC_ENTRA_GROUP_CARDIOLOGISTS \
    PMC_ENTRA_GROUP_TECHNOLOGISTS PMC_ENTRA_GROUP_REFERRERS PMC_ENTRA_GROUP_ICT_ADMINS; do
  if [[ -z "${!name:-}" ]]; then
    echo "Keycloak: $name is not set (see platform/imaging/README.md, Sign-in)" >&2
    exit 1
  fi
done

exec /opt/keycloak/bin/kc.sh start --import-realm
