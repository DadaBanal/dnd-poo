"""A person's session, seen from behind the front door: renewal and expiry.

This runner signs in at the front door as a person would (the stand-in
Entra ID's radiologist), then looks at the access token the front door hands
the engine. The test overlay shortens the clocks: the token lives 60 s and is
renewed at 40 s (on site: 5 min and 4 min).
"""

from __future__ import annotations

import time

import pytest
import requests

from frontdoor import BASE, DICOMWEB_JSON, claims, sign_in, token_of

RADIOLOGIST = "rad.test@pmc.test"


def engine_with(engine, token: str) -> int:
    """What the engine answers a person's search, given only their token."""
    return requests.get(f"{engine.url}/dicom-web/studies", timeout=30, headers={
        "Authorization": f"Bearer {token}", **DICOMWEB_JSON}).status_code


@pytest.fixture(scope="module")
def radiologist() -> requests.Session:
    return sign_in("radiologist", "/viewer")


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
