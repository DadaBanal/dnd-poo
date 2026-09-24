"""The PMC front door app (M2.3) from behind the front door: its API.

What a browser cannot see: the app believes only tokens Keycloak signed, the
worklist is the engine's answer to the person's own token, and a new study
reaches an open page within seconds.
"""

from __future__ import annotations

import base64
import json
import time

import pytest
import requests

import synth
from conftest import SENDER
from engine import REJECTED
from frontdoor import BASE, CA, PAGE_LOAD, sign_in, token_of

APP = "http://app:8080"  # the app itself, on the engine network


@pytest.fixture(scope="module")
def radiologist() -> requests.Session:
    return sign_in("radiologist")


def studies(session: requests.Session, **params) -> dict:
    r = session.get(f"{BASE}/pmc/api/studies", params=params, timeout=60)
    assert r.status_code == 200, (r.status_code, r.text[:200])
    return r.json()


def uids(answer: dict) -> set[str]:
    return {s["studyUid"] for s in answer["studies"]}


def test_the_address_people_are_given_opens_the_worklist(radiologist):
    r = radiologist.get(f"{BASE}/", headers=PAGE_LOAD, timeout=60, allow_redirects=False)
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/pmc/")
    page = radiologist.get(f"{BASE}/pmc/", headers=PAGE_LOAD, timeout=60)
    assert page.status_code == 200
    assert '<div id="root">' in page.text
    # The page runs only its own scripts: stricter than the viewer.
    csp = page.headers["Content-Security-Policy"]
    assert "script-src 'self';" in csp
    assert "unsafe-eval" not in csp


def test_the_app_knows_who_is_signed_in(radiologist):
    me = radiologist.get(f"{BASE}/pmc/api/me", timeout=30).json()
    assert me == {"email": "rad.test@pmc.test", "name": "Test Radiologist", "roles": ["pmc-radiologist"]}


def test_without_a_session_the_api_answers_401_never_a_sign_in_page():
    r = requests.get(f"{BASE}/pmc/api/studies", verify=CA, allow_redirects=False, timeout=30)
    assert r.status_code == 401


def test_the_app_believes_only_tokens_keycloak_signed(radiologist):
    token = token_of(radiologist)
    ask = lambda t: requests.get(f"{APP}/pmc/api/me", timeout=30,  # noqa: E731
                                 headers={"Authorization": f"Bearer {t}"} if t else {}).status_code
    assert ask(token) == 200
    # The same claims with no signature at all, and with a broken one.
    head = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    unsigned = f"{head}.{token.split('.')[1]}."
    tampered = token[:-6] + ("AAAAAA" if not token.endswith("AAAAAA") else "BBBBBB")
    assert ask(unsigned) == 401
    assert ask(tampered) == 401
    assert ask(None) == 401


def test_the_worklist_is_the_engines_answer_newest_first(radiologist, sent):
    got = studies(radiologist, range="all", limit=200)
    assert got["sortedBy"] == "engine"  # the PostgreSQL index sorted it
    for study in sent.values():
        assert study.study_uid in uids(got)
    moments = [s["studyDate"] + s["studyTime"] for s in got["studies"]]
    assert moments == sorted(moments, reverse=True)


def test_the_worklist_filters_by_kind_and_finds_by_patient_id_or_accession(radiologist, sent):
    ct = studies(radiologist, mod="ct", range="today")
    assert sent["ct"].study_uid in uids(ct)
    assert all("CT" in s["modalities"] for s in ct["studies"])
    assert uids(studies(radiologist, q=sent["mr"].patient_id, range="all")) == {sent["mr"].study_uid}
    assert uids(studies(radiologist, q=sent["dx"].accession, range="all")) == {sent["dx"].study_uid}


def test_a_referrer_sees_only_studies_shared_with_referrers(engine, sent):
    shared = engine.study_id(sent["dx"].study_uid)
    engine.request("PUT", f"/studies/{shared}/labels/referrer-shared").raise_for_status()
    try:
        got = studies(sign_in("referrer"), range="all", limit=200)
        assert sent["dx"].study_uid in uids(got)
        assert sent["xa"].study_uid not in uids(got)
        assert all("referrer-shared" in s["labels"] for s in got["studies"])
    finally:
        engine.request("DELETE", f"/studies/{shared}/labels/referrer-shared")


def test_a_new_study_reaches_an_open_page_within_seconds(radiologist, engine, modalities, run_id, measurements):
    with radiologist.get(f"{BASE}/pmc/api/events", stream=True, timeout=(10, 60),
                         headers={"Accept": "text/event-stream"}) as stream:
        assert stream.status_code == 200
        assert stream.headers["Content-Type"].startswith("text/event-stream")
        lines = stream.iter_lines(decode_unicode=True)
        next(line for line in lines if line == "event: hello")

        # Its own accession and patient ID, so no other test's search finds it.
        study = synth.Study("cr", run_id, SENDER["cr"], scale=0.1,
                            accession=f"LIVE{run_id[:8]}", patient_id=f"LIVE-{run_id}")
        sent_at = time.monotonic()
        statuses = engine.store(SENDER["cr"], study.datasets)
        assert statuses != REJECTED and all(s == 0x0000 for s in statuses), statuses
        next(line for line in lines if line == "event: studies")
        announced = time.monotonic() - sent_at

    measurements["app"] = {"new_study_announced_after_s": round(announced, 1)}
    assert announced < 15
    assert study.study_uid in uids(studies(radiologist, q=study.patient_id, range="all"))
