"""Detect patient identifiers in ticket text, and flag them without repeating them.

§6.1, requirement 1: a ticket references a patient record and never carries one,
and *"enforcement is a detection-and-flag at intake, not a promise in a policy"*.
This is that detection.

**The rule that governs every line below: a finding names the shape and the
field, never the value.** A detector that writes the PhilHealth number it found
into `data_quality.detail` has moved the identifier from one column to another
and called it compliance — and `detail` is read by reports, which are shared. So
the finding says *"a PhilHealth-shaped number appears in the summary"*, and the
number stays where it was, visible to whoever is already allowed to see the
ticket, for a human to deal with.

Detection is deliberately shape-based. A name detector is not something this can
do honestly — "Mr Cruz called about the printer" is a name in ticket text and no
regex settles whether it is a patient's — so what is detected here is structured
identifiers and the labels people put beside them. That is a floor, not a
ceiling, and it is labelled INFERRED where it is guessing.

Standard library only, like the rest of the engine.
"""
from __future__ import annotations

import re

# (code, severity, what it is, compiled pattern)
#
# ERROR is for a structured identifier: a shape that is an identifier or nothing.
# WARN is for a label that says an identifier is probably beside it — the words
# people actually type, measured from the message that prompted this file.
RULES: list[tuple[str, str, str, re.Pattern]] = [
    # PhilHealth identification numbers are 12 digits, commonly written
    # 12-345678901-2. Both shapes, and the bare run of twelve.
    ("PHI_PHILHEALTH_NUMBER", "ERROR", "a PhilHealth-shaped number",
     re.compile(r"\b\d{2}-\d{9}-\d\b|\b\d{12}\b")),

    # A case number beside its own label. 'CaseNo*' is on the record's own
    # inventory denylist, so the label is evidence in itself.
    ("PHI_CASE_NUMBER", "ERROR", "a case number",
     re.compile(r"\bcase\s*(?:no\.?|number|#)\s*[:#]?\s*\w+", re.I)),

    # Medical record / hospital / chart numbers, by label and value.
    ("PHI_RECORD_NUMBER", "ERROR", "a medical record number",
     re.compile(r"\b(?:mrn|hospital\s*(?:no\.?|number)|chart\s*(?:no\.?|number)|"
                r"patient\s*(?:no\.?|number)|hrn)\s*[:#]?\s*\w+", re.I)),

    # A date of birth, by label. The value shape alone is far too common to flag.
    ("PHI_DATE_OF_BIRTH", "WARN", "a date of birth",
     re.compile(r"\b(?:d\.?o\.?b\.?|date\s+of\s+birth)\b", re.I)),

    # A patient named as a patient. INFERRED: this is the label, not the name.
    ("PHI_PATIENT_NAME_LABEL", "WARN", "a patient named in the text",
     re.compile(r"\b(?:patient|px)\s*(?:name)?\s*[:#]\s*\w+|"
                r"\bpatient\s+(?:mr|mrs|ms|dr)\b", re.I)),

    # The scheme by name, which is how the measured message announced itself.
    # Not when it names a person's job or a hospital office (Dada, 6 Oct 2026):
    # a staff signature reading "Junior Philhealth Associate" held back every
    # requester email that quoted her reply, and a job title is not a patient.
    # A PhilHealth number beside it is still caught by the rule above.
    ("PHI_PHILHEALTH_MENTION", "WARN", "a PhilHealth reference",
     re.compile(r"\bphil\s*health\b(?!\W{0,3}(?:associates?|officers?|clerks?|staff|"
                r"section|department|dept|unit|office|coordinators?|supervisors?|head|"
                r"team|specialists?|assistants?|personnel|desk|in-?charge)\b)", re.I)),
]


def scan(text: str | None, *, field: str) -> list[tuple[str, str, str]]:
    """Findings for one field: (code, severity, detail).

    `detail` names the shape and the field and carries no matched text. Returns
    at most one finding per rule per field — a summary with three case numbers is
    one problem, not three.
    """
    if not text or not text.strip():
        return []
    found = []
    for code, severity, what, pattern in RULES:
        if pattern.search(text):
            found.append((code, severity,
                          f"{what} appears in the {field}; a ticket references a "
                          f"patient record and must not carry one (§6.1)"))
    return found


def scan_fields(fields: dict[str, str | None]) -> list[tuple[str, str, str]]:
    """Findings across several named fields, e.g. {'summary': ..., 'note': ...}."""
    out = []
    for field, text in fields.items():
        out.extend(scan(text, field=field))
    return out


def looks_clean(fields: dict[str, str | None]) -> bool:
    """True when nothing matched. Convenience for a caller that only wants the
    yes/no — the findings themselves are what get counted."""
    return not scan_fields(fields)
