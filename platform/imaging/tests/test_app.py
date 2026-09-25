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
    assert me == {"username": "rad.test", "name": "Test Radiologist", "email": "rad.test@pmc.test",
                  "roles": ["pmc-radiologist"]}


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


# ---- claims and the audit trail (the platform database) ---------------------------
ORIGIN = {"Origin": BASE}  # what a browser sends with every change from this site


def claim_url(uid: str) -> str:
    return f"{BASE}/pmc/api/studies/{uid}/claim"


def test_a_reader_claims_a_study_and_everyone_sees_who(radiologist, sent):
    uid = sent["ct"].study_uid
    r = radiologist.post(claim_url(uid), headers=ORIGIN, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["claim"]["reader"] == "rad.test"
    # Claiming it again changes nothing: it is still the radiologist's.
    assert radiologist.post(claim_url(uid), headers=ORIGIN, timeout=30).status_code == 200

    cardiologist = sign_in("cardiologist")
    seen = {s["studyUid"]: s for s in studies(cardiologist, range="all", limit=200)["studies"]}
    assert seen[uid]["claim"]["readerName"] == "Test Radiologist"
    # Someone else's claim can be neither taken nor released.
    taken = cardiologist.post(claim_url(uid), headers=ORIGIN, timeout=30)
    assert taken.status_code == 409
    assert taken.json()["claim"]["readerName"] == "Test Radiologist"
    assert cardiologist.delete(claim_url(uid), headers=ORIGIN, timeout=30).status_code == 409

    # "Claimed by me" is exactly the radiologist's claims.
    assert uids(studies(radiologist, range="all", mine="1")) == {uid}
    assert radiologist.delete(claim_url(uid), headers=ORIGIN, timeout=30).status_code == 204
    after = studies(radiologist, q=sent["ct"].patient_id, range="all")["studies"]
    assert after[0]["claim"] is None


def test_only_readers_claim_only_what_they_can_see_and_only_from_this_site(radiologist, sent):
    uid = sent["mr"].study_uid
    assert sign_in("referrer").post(claim_url(uid), headers=ORIGIN, timeout=30).status_code == 403
    # A change without this site's Origin is refused: another site's page
    # cannot claim studies in a signed-in person's name.
    assert radiologist.post(claim_url(uid), timeout=30).status_code == 403
    assert radiologist.post(claim_url(uid), headers={"Origin": "https://example.org"}, timeout=30).status_code == 403
    # A study the engine does not show this person does not exist for them.
    assert radiologist.post(claim_url("1.2.3.4.5"), headers=ORIGIN, timeout=30).status_code == 404
    assert radiologist.post(claim_url("not-a-uid"), headers=ORIGIN, timeout=30).status_code == 400


def test_ict_reads_who_opened_and_claimed_a_study(radiologist, sent, ledger):
    uid = sent["dx"].study_uid
    assert radiologist.post(f"{BASE}/pmc/api/studies/{uid}/opened", headers=ORIGIN, timeout=30).status_code == 204
    assert radiologist.post(claim_url(uid), headers=ORIGIN, timeout=30).status_code == 200
    assert radiologist.delete(claim_url(uid), headers=ORIGIN, timeout=30).status_code == 204
    assert radiologist.get(f"{BASE}/pmc/api/audit", timeout=30).status_code == 403
    trail = sign_in("ict").get(f"{BASE}/pmc/api/audit", params={"study": uid}, timeout=30).json()["events"]
    # Newest first.
    assert [(e["actor"], e["action"]) for e in trail] == [
        ("rad.test", "release"), ("rad.test", "claim"), ("rad.test", "open")]
    # The restart and the disaster drill look for this same trail again.
    ledger["audit"] = {"study": uid, "trail": [[e["actor"], e["action"]] for e in trail]}


# ---- the reading list, upgraded (M5.3): totals, read, the preview ------------------
def read_url(uid: str) -> str:
    return f"{BASE}/pmc/api/studies/{uid}/read"


def test_the_list_is_counted_for_readers_and_never_for_referrers(radiologist, sent):
    got = studies(radiologist, range="all", limit=1)
    assert got["more"] is True
    # Every study the filters match, whatever the page holds.
    assert got["total"] >= len(sent)
    assert studies(radiologist, range="all", mod="ct")["total"] >= 1
    # Not for a search (three questions merged), not for one's own claims, and
    # never for a referrer: the engine's count ignores the labels the search
    # respects, so it would count studies they cannot see.
    assert "total" not in studies(radiologist, q=sent["ct"].patient_id, range="all")
    assert "total" not in studies(radiologist, range="all", mine="1")
    assert "total" not in studies(sign_in("referrer"), range="all")


def test_a_reader_marks_a_study_read_and_the_unread_list_drops_it(radiologist, sent):
    uid = sent["us"].study_uid
    cardiologist = sign_in("cardiologist")
    # Claimed, then read: the claim goes with it (a claim says "I am reading
    # this"; read says "I have").
    assert radiologist.post(claim_url(uid), headers=ORIGIN, timeout=30).status_code == 200
    r = radiologist.post(read_url(uid), headers=ORIGIN, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["read"]["reader"] == "rad.test"
    # (The search is a wildcard: the JPEG ultrasound's patient ID matches too.)
    row = next(s for s in studies(cardiologist, q=sent["us"].patient_id, range="all")["studies"] if s["studyUid"] == uid)
    assert row["read"]["readerName"] == "Test Radiologist"
    assert row["claim"] is None
    assert uid not in uids(studies(radiologist, range="all", unread="1", limit=200))
    assert uid in uids(studies(radiologist, range="all", limit=200))
    # A study someone else holds cannot be marked read past them.
    other = sent["mr"].study_uid
    assert cardiologist.post(claim_url(other), headers=ORIGIN, timeout=30).status_code == 200
    refused = radiologist.post(read_url(other), headers=ORIGIN, timeout=30)
    assert refused.status_code == 409
    assert refused.json()["claim"]["readerName"] == "Test Cardiologist"
    assert cardiologist.delete(claim_url(other), headers=ORIGIN, timeout=30).status_code == 204
    # Only readers mark a study read, and only the reader who did can unmark it.
    assert sign_in("referrer").post(read_url(uid), headers=ORIGIN, timeout=30).status_code == 403
    assert cardiologist.delete(read_url(uid), headers=ORIGIN, timeout=30).status_code == 409
    assert radiologist.delete(read_url(uid), headers=ORIGIN, timeout=30).status_code == 204
    assert uid in uids(studies(radiologist, range="all", unread="1", limit=200))
    # The trail, newest first: the read took the claim with it.
    trail = sign_in("ict").get(f"{BASE}/pmc/api/audit", params={"study": uid}, timeout=30).json()["events"]
    assert [(e["actor"], e["action"]) for e in trail][:3] == [
        ("rad.test", "unread"), ("rad.test", "read"), ("rad.test", "claim")]


def test_a_study_preview_lists_its_series_and_the_patients_earlier_studies(radiologist, sent, engine, run_id,
                                                                            measurements):
    current = sent["cr"]
    # An older chest plate of the same patient: a prior, with an accession of
    # its own (the sorting test counts this run's S-prefixed accessions).
    prior = synth.Study("cr", run_id + "P", SENDER["cr"], patient_id=current.patient_id, scale=0.25,
                        accession=f"P{run_id[:8]}CR")
    for ds in prior.datasets:
        ds.StudyDate = ds.SeriesDate = ds.ContentDate = ds.AcquisitionDate = "20250106"
        ds.StudyDescription = "SYNTHETIC CR chest plate, a year earlier"
    statuses = engine.store(SENDER["cr"], prior.datasets)
    assert statuses != REJECTED and all(s == 0x0000 for s in statuses), statuses

    started = time.perf_counter()
    r = radiologist.get(f"{BASE}/pmc/api/studies/{current.study_uid}", timeout=30)
    preview_ms = (time.perf_counter() - started) * 1000
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["study"]["studyUid"] == current.study_uid
    assert got["study"]["patientId"] == current.patient_id
    assert [(s["modality"], s["seriesUid"], s["instances"]) for s in got["series"]] == [
        ("CR", current.series_uid, len(current.datasets))]
    assert [p["studyUid"] for p in got["priors"]] == [prior.study_uid]
    assert got["priors"][0]["studyDate"] == "20250106"
    assert got["priors"][0]["read"] is None

    # Its first image, small, through the front door and never cached; the
    # same for one series.
    thumb_url = f"{BASE}/dicom-web/studies/{current.study_uid}/thumbnail"
    started = time.perf_counter()
    thumb = radiologist.get(thumb_url, params={"viewport": "96,96"}, timeout=30)
    thumb_ms = (time.perf_counter() - started) * 1000
    assert thumb.status_code == 200
    assert thumb.headers["Content-Type"] == "image/jpeg"
    assert thumb.headers["Cache-Control"] == "no-store"
    assert thumb.content[:3] == b"\xff\xd8\xff"
    series = radiologist.get(f"{BASE}/dicom-web/studies/{current.study_uid}/series/{current.series_uid}/thumbnail",
                             params={"viewport": "96,96"}, timeout=30)
    assert series.status_code == 200 and series.headers["Content-Type"] == "image/jpeg"
    # A browser asking for an <img> lists image/avif, image/webp, image/*, ...
    # and the engine answers that list with 400 (MEASURED, 25 Sep 2026); the
    # front door asks the engine for a JPEG on the browser's behalf.
    as_browser = {"Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                  "Sec-Fetch-Dest": "image", "Sec-Fetch-Mode": "no-cors", "Sec-Fetch-Site": "same-origin"}
    img = radiologist.get(thumb_url, params={"viewport": "96,96"}, headers=as_browser, timeout=30)
    assert img.status_code == 200 and img.headers["Content-Type"] == "image/jpeg"

    # A study a referrer cannot see has neither a preview nor an image.
    referrer = sign_in("referrer")
    assert referrer.get(f"{BASE}/pmc/api/studies/{current.study_uid}", timeout=30).status_code == 404
    assert referrer.get(thumb_url, params={"viewport": "96,96"}, timeout=30).status_code in (403, 404)
    measurements["reading_list"] = {
        "preview_ms": round(preview_ms), "thumbnail_ms": round(thumb_ms), "thumbnail_bytes": len(thumb.content)}
