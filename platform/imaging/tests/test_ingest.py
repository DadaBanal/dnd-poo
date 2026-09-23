"""What a modality sends is what the archive keeps: bit-exact, or exactly as sent."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest
from pydicom.uid import JPEGBaseline8Bit

import synth
from conftest import SENDER
from engine import REJECTED

JPEG_LS_LOSSLESS = "1.2.840.10008.1.2.4.80"
UNCOMPRESSED_KINDS = [k for k in synth.KINDS if k != "us-jpeg"]


@pytest.mark.parametrize("kind", UNCOMPRESSED_KINDS)
def test_uncompressed_arrivals_are_kept_as_jpeg_ls_and_decode_bit_exact(engine, sent, kind, measurements):
    study = sent[kind]
    stored_bytes = 0
    for dataset, original in zip(study.datasets, study.pixels):
        oid = engine.instance_id(str(dataset.SOPInstanceUID))
        assert oid, f"{kind}: instance not in the archive"
        kept = engine.stored_file(oid)
        assert kept.file_meta.TransferSyntaxUID == JPEG_LS_LOSSLESS, kind
        # The whole point of "lossless": every pixel, every frame, identical.
        np.testing.assert_array_equal(kept.pixel_array, original, err_msg=kind)
        stored_bytes += int(engine.text(f"/instances/{oid}/attachments/dicom/size"))
    measurements.setdefault("jpeg_ls_on_synthetic_pixels", {})[kind] = {
        "raw_pixel_bytes": study.raw_pixel_bytes,
        "stored_file_bytes": stored_bytes,
        "stored_as_pct_of_raw": round(100 * stored_bytes / study.raw_pixel_bytes, 1),
    }


def test_lossy_arrivals_are_kept_exactly_as_sent(engine, sent):
    # Re-encoding lossy pixels would lose more; they are stored byte for byte.
    study = sent["us-jpeg"]
    sent_dataset = study.datasets[0]
    kept = engine.stored_file(engine.instance_id(str(sent_dataset.SOPInstanceUID)))
    assert kept.file_meta.TransferSyntaxUID == JPEGBaseline8Bit
    assert kept.PixelData == sent_dataset.PixelData


def test_a_resend_is_harmless(engine, sent):
    # Modalities resend. The engine accepts it and keeps one copy.
    study = sent["cr"]
    statuses = engine.store(SENDER["cr"], study.datasets)
    assert statuses != REJECTED and all(s in (0x0000, 0xB000, 0xB007) for s in statuses), statuses
    study_id = engine.study_id(study.study_uid)
    assert len(engine.get(f"/studies/{study_id}/instances")) == len(study.datasets)


def test_six_modalities_sending_at_once(engine, modalities, run_id, ledger):
    # A busy morning: every department sends in the same minute.
    plan = {"ct": 0.25, "mr": 0.5, "cr": 0.3, "dx": 0.3, "us": 0.5, "xa": 0.2}
    studies = {kind: synth.Study(kind, run_id + "P", SENDER[kind], scale=scale) for kind, scale in plan.items()}
    with ThreadPoolExecutor(max_workers=len(studies)) as pool:
        results = dict(zip(studies, pool.map(
            lambda kind: engine.store(SENDER[kind], studies[kind].datasets), studies)))
    for kind, statuses in results.items():
        assert statuses != REJECTED and all(s == 0x0000 for s in statuses), f"{kind}: {statuses}"
    for kind, study in studies.items():
        for uid in study.instance_uids:
            assert engine.instance_id(uid), f"{kind}: {uid} missing"
        first = engine.instance_id(study.instance_uids[0])
        ledger["studies"][study.study_uid] = {
            "kind": kind,
            "instances": len(study.datasets),
            "first_instance": first,
            "first_instance_md5": engine.text(f"/instances/{first}/attachments/dicom/md5"),
        }
