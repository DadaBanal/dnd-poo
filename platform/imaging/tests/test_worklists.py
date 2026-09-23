"""Orders reach the right modality, and leave the worklist once performed."""

from __future__ import annotations

from pydicom.dataset import Dataset
from pydicom.uid import generate_uid

import synth
from engine import wait_for


def _order(run_id: str, suffix: str, modality: str, station: str, date: str) -> dict:
    accession = f"W{run_id[:8]}{suffix}"
    return {
        "Tags": {
            "PatientID": f"SYN-{run_id}-WL{suffix}",
            "PatientName": f"SYNTHETIC^WORKLIST{suffix}",
            "PatientBirthDate": "",
            "PatientSex": "O",
            "AccessionNumber": accession,
            "StudyInstanceUID": generate_uid(),
            "RequestedProcedureID": accession,
            "RequestedProcedureDescription": f"SYNTHETIC {modality} ORDER",
            "ScheduledProcedureStepSequence": [{
                "Modality": modality,
                "ScheduledStationAETitle": station,
                "ScheduledProcedureStepStartDate": date,
                "ScheduledProcedureStepStartTime": "080000",
                "ScheduledProcedureStepID": accession,
                "ScheduledProcedureStepDescription": f"SYNTHETIC {modality} ORDER",
            }],
        }
    }


def _query(date: str) -> Dataset:
    # What a console asks at the start of the day: today's entries. It leaves
    # its own AE title out, as the standard says a user-initiated query should.
    q = Dataset()
    q.PatientName = ""
    q.PatientID = ""
    q.AccessionNumber = ""
    q.StudyInstanceUID = ""
    q.RequestedProcedureDescription = ""
    step = Dataset()
    step.ScheduledStationAETitle = ""
    step.Modality = ""
    step.ScheduledProcedureStepStartDate = date
    step.ScheduledProcedureStepStartTime = ""
    step.ScheduledProcedureStepDescription = ""
    q.ScheduledProcedureStepSequence = [step]
    return q


def _accessions(engine, calling: str, date: str) -> list[str]:
    statuses, matches = engine.find_worklist(calling, _query(date))
    assert statuses and statuses[-1] == 0x0000, statuses
    return [str(m.AccessionNumber) for m in matches]


def test_an_order_is_performed_and_leaves_the_worklist(engine, modalities, run_id, ledger):
    today = synth._now().strftime("%Y%m%d")
    order = _order(run_id, "XA", "XA", "IENGINE_SCU", today)
    tags = order["Tags"]
    created = engine.post("/worklists/create", order)

    # The cathlab sees its order; the CT console, asking the same question, does not.
    assert tags["AccessionNumber"] in _accessions(engine, "IENGINE_SCU", today)
    assert tags["AccessionNumber"] not in _accessions(engine, "TM_CT_CMW_V3.00", today)

    # The procedure happens: the cathlab sends the run under the ordered UIDs.
    study = synth.Study("xa", run_id, "IENGINE_SCU", accession=tags["AccessionNumber"],
                        study_uid=tags["StudyInstanceUID"], patient_id=tags["PatientID"], scale=0.2)
    assert all(s == 0x0000 for s in engine.store("IENGINE_SCU", study.datasets))
    first = engine.instance_id(study.instance_uids[0])
    ledger["studies"][study.study_uid] = {
        "kind": "xa", "instances": len(study.datasets), "first_instance": first,
        "first_instance_md5": engine.text(f"/instances/{first}/attachments/dicom/md5"),
    }

    # Once the study is stable, the entry is gone: nobody can pick it twice.
    wait_for(lambda: engine.request("GET", f"/worklists/{created['ID']}").status_code == 404,
             timeout=180, what="the performed order to leave the worklist")
    assert tags["AccessionNumber"] not in _accessions(engine, "IENGINE_SCU", today)


def test_a_cancelled_order_is_withdrawn(engine, modalities, run_id):
    today = synth._now().strftime("%Y%m%d")
    order = _order(run_id, "CX", "CT", "TM_CT_CMW_V3.00", today)
    created = engine.post("/worklists/create", order)
    assert order["Tags"]["AccessionNumber"] in _accessions(engine, "TM_CT_CMW_V3.00", today)
    assert engine.request("DELETE", f"/worklists/{created['ID']}").status_code == 200
    assert order["Tags"]["AccessionNumber"] not in _accessions(engine, "TM_CT_CMW_V3.00", today)


def test_a_pending_order_is_left_for_the_restart_check(engine, modalities, run_id, ledger):
    today = synth._now().strftime("%Y%m%d")
    order = _order(run_id, "CP", "CT", "TM_CT_CMW_V3.00", today)
    created = engine.post("/worklists/create", order)
    assert order["Tags"]["AccessionNumber"] in _accessions(engine, "TM_CT_CMW_V3.00", today)
    ledger["worklists"][created["ID"]] = {
        "accession": order["Tags"]["AccessionNumber"], "station": "TM_CT_CMW_V3.00", "date": today,
    }
