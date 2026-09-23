"""A person's session, seen from behind the front door: renewal and expiry.

This runner signs in at the front door as a person would (the stand-in
Entra ID's radiologist), then looks at the access token the front door hands
the engine. The test overlay shortens the clocks: the token lives 60 s and is
renewed at 40 s (on site: 5 min and 4 min).
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
import time
from pathlib import Path

import pytest
import requests

HOST = os.environ.get("PMC_HOSTNAME", "imaging.pmcne.test")
BASE = f"https://{HOST}"
CA = os.environ.get("TEST_CA_SECRET", "/run/secrets/test-ca")
PASSWORD_FILE = os.environ.get("TEST_USER_PASSWORD_SECRET", "/run/secrets/test-user-password")
RADIOLOGIST = "rad.test@pmc.test"
COOKIE = "__Host-pmc-session"
# oauth2-proxy, asked directly on the engine network the way the front door
# asks it: this is where the front door gets the token it passes on.
SESSION_CHECK = "http://oauth2-proxy:4180/oauth2/auth"
DICOMWEB_JSON = {"Accept": "application/dicom+json"}

# A browser loading a page says so; only a page load may start a sign-in.
PAGE_LOAD = {"Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"}


def sign_in(user: str) -> requests.Session:
    """Sign in at the front door as `user`, through the stand-in Entra ID."""
    s = requests.Session()
    s.verify = CA
    r = s.get(f"{BASE}/viewer", headers=PAGE_LOAD, timeout=60)
    r.raise_for_status()
    assert "/auth/realms/entra-sim/" in r.url, r.url
    form = re.search(r'<form\b[^>]*\bid="kc-form-login"[^>]*>', r.text)
    assert form, "no sign-in form at the stand-in Entra ID"
    action = html.unescape(re.search(r'\baction="([^"]+)"', form.group(0)).group(1))
    password = Path(PASSWORD_FILE).read_text().strip()
    r = s.post(action, data={"username": user, "password": password, "credentialId": ""},
               headers=PAGE_LOAD, timeout=60)
    r.raise_for_status()
    assert r.url == f"{BASE}/viewer", r.url
    assert s.cookies.get(COOKIE), "no session cookie after signing in"
    return s


def token_of(session: requests.Session) -> str:
    """The access token the front door would hand the engine right now."""
    r = requests.get(SESSION_CHECK, timeout=30,
                     cookies={COOKIE: session.cookies.get(COOKIE)},
                     headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": HOST})
    assert r.status_code == 202, r.status_code
    return r.headers["X-Auth-Request-Access-Token"]


def claims(token: str) -> dict:
    """A JWT's claims, unverified: the engine's side does the verifying."""
    body = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))


def engine_with(engine, token: str) -> int:
    """What the engine answers a person's search, given only their token."""
    return requests.get(f"{engine.url}/dicom-web/studies", timeout=30, headers={
        "Authorization": f"Bearer {token}", **DICOMWEB_JSON}).status_code


@pytest.fixture(scope="module")
def radiologist() -> requests.Session:
    return sign_in(RADIOLOGIST)


def test_the_engine_is_handed_the_persons_own_short_lived_token(engine, radiologist):
    token = token_of(radiologist)
    c = claims(token)
    assert c["email"] == RADIOLOGIST
    assert "pmc-radiologist" in c["realm_access"]["roles"]
    # 60 s in the test overlay; 300 s on site (PMC_ACCESS_TOKEN_SECONDS).
    assert c["exp"] - c["iat"] == 60
    assert engine_with(engine, token) == 200


def test_a_session_outlives_its_token_and_the_engine_refuses_the_old_one(
        engine, radiologist, measurements):
    first = token_of(radiologist)
    expires = claims(first)["exp"]
    time.sleep(max(0.0, expires - time.time()) + 2)

    # The person carries on: the front door renews the token on the way in.
    r = radiologist.get(f"{BASE}/dicom-web/studies", headers=DICOMWEB_JSON, timeout=60)
    assert r.status_code == 200, r.status_code
    renewed = token_of(radiologist)
    assert renewed != first
    assert claims(renewed)["exp"] > expires
    assert engine_with(engine, renewed) == 200

    # The expired token itself is refused. The engine's authorization plugin
    # caches what it has checked, so measure how long it takes.
    deadline = expires + 180
    while engine_with(engine, first) == 200 and time.time() < deadline:
        time.sleep(2)
    refused_after = round(time.time() - expires)
    measurements["session"] = {
        "token_seconds": 60,
        "expired_token_refused_after_s": refused_after,
    }
    assert engine_with(engine, first) in (401, 403), \
        f"an expired token was still accepted {refused_after} s after it expired"
