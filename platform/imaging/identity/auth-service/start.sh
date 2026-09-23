#!/bin/sh
# orthanc-auth-service (Path A, M2.2), with PMC's secrets read from Docker
# secrets and its log turned down. At its default level it writes every token
# it is asked about, bearer tokens included, to the log (MEASURED in 26.8.1:
# app.py logs the token value on /user/get-profile and /tokens/validate).
set -eu
USERS="{\"orthanc-engine\": \"$(cat /run/secrets/auth-service-password)\"}"
KEYCLOAK_CLIENT_SECRET="$(cat /run/secrets/admin-cli-client-secret)"
SECRET_KEY="$(cat /run/secrets/auth-service-secret-key)"
export USERS KEYCLOAK_CLIENT_SECRET SECRET_KEY

# The service reads Keycloak's realm key once, at start, and exits if it
# cannot: wait until the realm answers rather than fail on a slow start.
python3 - <<'PY'
import os, sys, time, urllib.request
url = os.environ["KEYCLOAK_URI"]
for _ in range(90):
    try:
        with urllib.request.urlopen(url, timeout=5) as answer:
            if answer.status == 200:
                sys.exit(0)
    except Exception:
        pass
    time.sleep(2)
sys.exit(f"auth-service: Keycloak's realm did not answer at {url} within 180 s")
PY

exec uvicorn pmc_quiet:app --app-dir /pmc --host 0.0.0.0 --port 8000 --log-level warning
