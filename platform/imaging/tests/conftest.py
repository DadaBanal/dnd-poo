"""Fixtures shared by the platform/imaging tests.

ci/run.sh runs the suite twice: once against a fresh engine, then again after
it has restarted the engine and its index (-m after_restart). The first run
writes what it stored to /results/ledger.json; the second checks it is all
still there.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import pytest

import synth
from engine import REJECTED, Engine

RESULTS = Path(os.environ.get("RESULTS_DIR", "/results"))

# The modalities the tests play. The AE titles are PMC's own, MEASURED in the
# record (Voyager audit, 31 Aug; the Azurion's screens, 8 Sep). SYN_* stand in
# for machines whose AE title the record does not hold.
MODALITIES = {
    "cathlab-qfr": "IENGINE_SCU",
    "ct-aquilion": "TM_CT_CMW_V3.00",
    "mr-sempra": "AN_WP179248",
    "cr-agfa-nx": "NX_DEFAULT",
    "dr-console": "CONSOLE1",
    "us-aplio": "SYN_US01",
    "echo-lab": "SYN_ECHO01",
    # The rest of PMC's machines (README: Every machine PMC has). Their AE
    # titles are not in the record, so these are the tests' own.
    "or-c-arm": "SYN_OEC01",
    "gamma-camera": "SYN_NM01",
    "bone-density": "SYN_DXA01",
    "dental-xray": "SYN_PX01",
    "eye-oct": "SYN_OCT01",
    "endoscopy": "SYN_ES01",
    "linac": "SYN_RT01",
}

# Which modality sends which kind of synthetic study (synth.KINDS).
SENDER = {
    "xa": "IENGINE_SCU",
    "ct": "TM_CT_CMW_V3.00",
    "mr": "AN_WP179248",
    "cr": "NX_DEFAULT",
    "dx": "CONSOLE1",
    "us": "SYN_ECHO01",
    "us-jpeg": "SYN_US01",
    "mg": "CONSOLE1",  # Voyager's records show CONSOLE1 sending CR and MG
    "rf": "SYN_OEC01",
    "nm": "SYN_NM01",
    "bmd": "SYN_DXA01",
    "px": "SYN_PX01",
    "opt": "SYN_OCT01",
    "es": "SYN_ES01",
    "rt": "SYN_RT01",
}


@pytest.fixture(scope="session")
def engine() -> Engine:
    return Engine()


@pytest.fixture(scope="session")
def run_id() -> str:
    # Keeps a rerun against the same volumes from colliding with earlier data.
    return uuid.uuid4().hex[:10].upper()


@pytest.fixture(scope="session")
def modalities(engine: Engine) -> dict[str, str]:
    """Register every test modality from this container's own address."""
    here = engine.my_address()
    for name, aet in MODALITIES.items():
        engine.register(name, aet, here, store=True, worklist=True)
    return MODALITIES


def _write(name: str, data: dict) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / name).write_text(json.dumps(data, indent=2, sort_keys=True))


@pytest.fixture(scope="session")
def ledger():
    """What this run left in the engine, for the after-restart check."""
    entries: dict = {"studies": {}, "worklists": {}, "modalities": sorted(MODALITIES)}
    yield entries
    if entries["studies"]:
        _write("ledger.json", entries)


@pytest.fixture(scope="session")
def sent(engine, modalities, run_id, ledger, measurements) -> dict[str, synth.Study]:
    """One study of every kind, each sent by its own modality, once per run."""
    studies = {}
    for kind in synth.KINDS:
        study = synth.Study(kind, run_id, SENDER[kind])
        started = time.perf_counter()
        statuses = engine.store(SENDER[kind], study.datasets)
        seconds = time.perf_counter() - started
        assert statuses != REJECTED and all(s == 0x0000 for s in statuses), f"{kind}: {statuses}"
        first = engine.instance_id(study.instance_uids[0])
        ledger["studies"][study.study_uid] = {
            "kind": kind,
            "instances": len(study.datasets),
            "first_instance": first,
            "first_instance_md5": engine.text(f"/instances/{first}/attachments/dicom/md5"),
        }
        measurements.setdefault("store_seconds", {})[kind] = round(seconds, 2)
        studies[kind] = study
    return studies


@pytest.fixture(scope="session")
def measurements():
    """Sizes and timings worth reporting. MEASURED on synthetic data only."""
    data: dict[str, dict] = {}
    yield data
    if data:
        _write(f"measurements-{os.environ.get('RUN_PHASE', 'first')}.json", data)
