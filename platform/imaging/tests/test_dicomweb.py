"""The viewer's path: sorted search, DICOMweb query, frames and cached metadata."""

from __future__ import annotations

import time

import numpy as np
from libjpeg import decode as decode_jpeg_ls

from engine import multipart, wait_for

JSON = {"Accept": "application/dicom+json"}
FRAME_AS_STORED = {"Accept": 'multipart/related; type="application/octet-stream"; transfer-syntax=*'}
FRAME_UNCOMPRESSED = {"Accept": 'multipart/related; type="application/octet-stream"'}
INSTANCE_AS_STORED = {"Accept": 'multipart/related; type="application/dicom"; transfer-syntax=*'}


def _uids(study):
    ds = study.datasets[0]
    return str(ds.StudyInstanceUID), str(ds.SeriesInstanceUID), str(ds.SOPInstanceUID)


def test_server_side_sorting(engine, sent, run_id):
    # The index answers OrderBy. (The legacy archive's ODBC index answers it
    # with HTTP 500, which is why the portal must never send it there.)
    r = engine.request("POST", "/tools/find", json={
        "Level": "Study",
        "Query": {"AccessionNumber": f"S{run_id[:8]}*"},
        "Expand": True,
        "OrderBy": [{"Type": "DicomTag", "Key": "AccessionNumber", "Direction": "DESC"}],
    })
    assert r.status_code == 200, r.text
    accessions = [s["MainDicomTags"]["AccessionNumber"] for s in r.json()]
    assert len(accessions) == len(sent)
    assert accessions == sorted(accessions, reverse=True)


def test_qido_finds_a_study_by_modality_and_patient(engine, sent):
    xa = sent["xa"]
    r = engine.request("GET", "/dicom-web/studies", headers=JSON,
                       params={"ModalitiesInStudy": "XA", "PatientID": xa.patient_id})
    assert r.status_code == 200, r.text
    studies = r.json()
    assert [s["0020000D"]["Value"][0] for s in studies] == [xa.study_uid]


def test_cine_frames_come_back_as_stored_and_as_sent(engine, sent):
    xa = sent["xa"]
    study_uid, series_uid, sop_uid = _uids(xa)
    frames = xa.pixels[0]
    base = f"/dicom-web/studies/{study_uid}/series/{series_uid}/instances/{sop_uid}/frames"
    for number in (1, len(frames) // 2, len(frames)):
        # As stored: JPEG-LS straight from disk, nothing transcoded on the way out.
        r = engine.request("GET", f"{base}/{number}", headers=FRAME_AS_STORED)
        assert r.status_code == 200, r.text
        (headers, body), = multipart(r)
        assert "transfer-syntax=1.2.840.10008.1.2.4.80" in headers["content-type"]
        np.testing.assert_array_equal(decode_jpeg_ls(body), frames[number - 1])
        # Uncompressed, for a client that cannot decode: the same pixels.
        r = engine.request("GET", f"{base}/{number}", headers=FRAME_UNCOMPRESSED)
        assert r.status_code == 200, r.text
        (headers, body), = multipart(r)
        got = np.frombuffer(body, np.uint8).reshape(frames.shape[1:])
        np.testing.assert_array_equal(got, frames[number - 1])


def test_cine_fetch_timings(engine, sent, measurements):
    """Not a pass/fail: the numbers M2's viewer work starts from (synthetic run, this host)."""
    xa = sent["xa"]
    study_uid, series_uid, sop_uid = _uids(xa)
    base = f"/dicom-web/studies/{study_uid}/series/{series_uid}/instances/{sop_uid}"
    count = xa.pixels[0].shape[0]

    def timed(path, headers):
        started = time.perf_counter()
        r = engine.request("GET", path, headers=headers)
        assert r.status_code == 200, r.text
        return time.perf_counter() - started, len(r.content)

    whole_s, whole_bytes = timed(base, INSTANCE_AS_STORED)
    all_s, all_bytes = timed(f"{base}/frames/{','.join(map(str, range(1, count + 1)))}", FRAME_AS_STORED)
    each_s = sum(timed(f"{base}/frames/{n}", FRAME_AS_STORED)[0] for n in range(1, count + 1))
    measurements["xa_cine_fetch"] = {
        "frames": count,
        "whole_instance_ms": round(whole_s * 1000),
        "whole_instance_bytes": whole_bytes,
        "all_frames_one_request_ms": round(all_s * 1000),
        "all_frames_one_request_bytes": all_bytes,
        "frame_by_frame_total_ms": round(each_s * 1000),
    }


def test_series_metadata_is_cached_once_the_series_is_stable(engine, sent):
    xa = sent["xa"]
    study_uid, series_uid, _ = _uids(xa)
    series_id = [h["ID"] for h in engine.lookup(series_uid) if h["Type"] == "Series"][0]
    # 4301 is the DICOMweb plugin's metadata cache: one gzipped blob per
    # series, written when the series becomes stable.
    wait_for(lambda: "4301" in engine.get(f"/series/{series_id}/attachments"),
             timeout=120, what="the DICOMweb metadata cache of the stable series")
    r = engine.request("GET", f"/dicom-web/studies/{study_uid}/series/{series_uid}/metadata", headers=JSON)
    assert r.status_code == 200, r.text
    (instance,) = r.json()
    assert instance["00280008"]["Value"][0] == xa.pixels[0].shape[0]  # NumberOfFrames
