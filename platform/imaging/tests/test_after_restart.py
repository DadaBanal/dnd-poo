"""After ci/run.sh restarts the engine and its index, nothing is lost and it still works."""

from __future__ import annotations

import json

import pytest

import synth
from conftest import RESULTS
from frontdoor import BASE, sign_in
from test_worklists import _accessions

pytestmark = pytest.mark.after_restart


@pytest.fixture(scope="module")
def before() -> dict:
    return json.loads((RESULTS / "ledger.json").read_text())


def test_every_study_is_still_there_with_every_instance(engine, before):
    assert before["studies"], "the first run recorded nothing"
    for uid, entry in before["studies"].items():
        study_id = engine.study_id(uid)
        assert study_id, f"{entry['kind']} study {uid} is gone"
        assert len(engine.get(f"/studies/{study_id}/instances")) == entry["instances"], entry["kind"]


def test_every_file_is_unchanged(engine, before):
    for entry in before["studies"].values():
        md5 = engine.text(f"/instances/{entry['first_instance']}/attachments/dicom/md5")
        assert md5 == entry["first_instance_md5"], entry["kind"]


def test_registered_modalities_survived(engine, before):
    # Kept in the index (DicomModalitiesInDatabase), not in a file.
    assert set(before["modalities"]) <= set(engine.get("/modalities"))


def test_a_pending_order_survived(engine, before, modalities):
    assert before["worklists"], "the first run left no pending order"
    for worklist_id, entry in before["worklists"].items():
        assert engine.request("GET", f"/worklists/{worklist_id}").status_code == 200
        assert entry["accession"] in _accessions(engine, entry["station"], entry["date"])


def test_the_engine_still_takes_studies(engine, modalities, run_id):
    study = synth.Study("cr", run_id, "NX_DEFAULT", scale=0.25)
    assert all(s == 0x0000 for s in engine.store("NX_DEFAULT", study.datasets))
    assert engine.instance_id(study.instance_uids[0])


def test_the_audit_trail_survived(before):
    # Kept in PMC's platform database, not the engine's index: the disaster
    # drill restores it from the off-site copy of its backups alone.
    audit = before["audit"]
    trail = sign_in("ict").get(f"{BASE}/pmc/api/audit", params={"study": audit["study"]}, timeout=30).json()["events"]
    assert [[e["actor"], e["action"]] for e in trail] == audit["trail"]
