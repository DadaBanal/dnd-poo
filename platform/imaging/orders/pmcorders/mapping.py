"""A BizBox order row -> the DICOM Modality Worklist attributes a console reads.
Carried from the research proof, which checked each rule below against the
Worklists plugin 0.9.2 and a C-FIND from each console."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import uuid

# A fixed namespace, so an order always gets the same StudyInstanceUID: if the
# connector restarts, or an entry has to be recreated, the images still land
# on the study the order expects.
_PMC_NS = uuid.UUID("5b1c3f0e-9a7d-4c61-8f0e-2d6f3e9b8a10")

PRIORITY = {"STAT": "STAT", "URGENT": "HIGH", "ROUTINE": "ROUTINE", "LOW": "LOW"}


def study_uid_for(order_no: str) -> str:
    return "2.25." + str(uuid.uuid5(_PMC_NS, "pmc-order:" + order_no).int)


def _clean(s) -> str:
    # ^ and \ are DICOM delimiters; control characters never belong in a name.
    return re.sub(r"[\^\\\x00-\x1f]", " ", (s or "")).strip()


def person_name(last, first, middle=None) -> str:
    parts = [_clean(last), _clean(first), _clean(middle)]
    while parts and not parts[-1]:
        parts.pop()
    return "^".join(parts)[:64]


def da(d) -> str:
    return d.strftime("%Y%m%d") if d else ""


def tm(t) -> str:
    return t.strftime("%H%M%S") if t else ""


def problem(row: dict, stations: dict) -> str | None:
    """Why an order cannot go to a worklist as it stands, or None."""
    if row["section"] not in stations:
        return f"section {row['section']!r} has no console"
    if not 0 < len(row["order_no"] or "") <= 16:
        return "the order number is not 1 to 16 characters (DICOM's AccessionNumber)"
    return None


def worklist_tags(row: dict, stations: dict, issuer: str, aet: str) -> dict:
    station = stations[row["section"]]
    when = row["scheduled_at"]
    if isinstance(when, str):
        when = dt.datetime.fromisoformat(when)
    order_no = row["order_no"]
    return {
        # ISO_IR 100 (Latin-1) carries the n-tilde of Filipino names and is what
        # older consoles understand (MEASURED in the proof, T3b).
        "SpecificCharacterSet": "ISO_IR 100",
        "AccessionNumber": order_no,
        "ReferringPhysicianName": _clean(row.get("referring_doctor"))[:64],
        "PatientName": person_name(row["last_name"], row["first_name"], row.get("middle_name")),
        "PatientID": row["hospital_no"],
        "IssuerOfPatientID": issuer,
        "PatientBirthDate": da(row.get("birth_date")),
        "PatientSex": row["sex"] if row.get("sex") in ("M", "F", "O") else "",
        "AdmissionID": row.get("encounter_no") or "",
        "StudyInstanceUID": study_uid_for(order_no),
        "RequestedProcedureID": order_no,
        "RequestedProcedureDescription": _clean(row["procedure_desc"])[:64],
        "RequestedProcedureCodeSequence": [{
            "CodeValue": row["procedure_code"],
            "CodingSchemeDesignator": "99PMC",
            "CodeMeaning": _clean(row["procedure_desc"])[:64],
        }],
        "RequestedProcedurePriority": PRIORITY.get(row.get("priority") or "ROUTINE", "ROUTINE"),
        "ScheduledProcedureStepSequence": [{
            "Modality": station["modality"],
            # One entry per console. DICOM allows a multi-valued station AE
            # title, but the Worklists plugin with FilterIssuerAet matches a
            # console against it exactly, so "A\B" reaches neither (MEASURED
            # in the proof, T3c). The entries share the order's
            # StudyInstanceUID, so the engine removes them together.
            "ScheduledStationAETitle": aet,
            "ScheduledProcedureStepStartDate": da(when),
            "ScheduledProcedureStepStartTime": tm(when),
            "ScheduledProcedureStepID": order_no,
            "ScheduledProcedureStepDescription": _clean(row["procedure_desc"])[:64],
        }],
    }


def worklist_entries(row: dict, stations: dict, issuer: str) -> list[dict]:
    return [worklist_tags(row, stations, issuer, aet) for aet in stations[row["section"]]["aets"]]


def tags_hash(entries) -> str:
    return hashlib.sha256(json.dumps(entries, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
