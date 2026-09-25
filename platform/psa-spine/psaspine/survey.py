"""The satisfaction survey (032): one answer per closed ticket, from its requester.

Asked on the portal once the ticket is closed (and by the closing email, when
the board sends them): a score of one to five and, if they like, a sentence.
The sentence is scanned for patient details like every other requester text
and the finding is counted, never the words dropped. Reports show the average.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from . import phi

CLOSED = ("RESOLVED", "CLOSED", "CANCELLED")


def pending(conn: sqlite3.Connection, work_item_id: str) -> bool:
    """Is the ticket closed, unmerged, and still unanswered?"""
    row = conn.execute("SELECT state, closed_at, merged_into FROM ticket WHERE work_item_id = ?",
                       (work_item_id,)).fetchone()
    if row is None or row["merged_into"] or not (row["closed_at"] or row["state"] in CLOSED):
        return False
    return conn.execute("SELECT 1 FROM survey_response WHERE work_item_id = ?",
                        (work_item_id,)).fetchone() is None


def answer(conn: sqlite3.Connection, work_item_id: str, *, score: int, comment: str | None,
           by: str, at: datetime) -> list:
    """Record the answer. Returns the PHI findings on the comment, already written."""
    from .board import _event
    if not isinstance(score, int) or not 1 <= score <= 5:
        raise ValueError("a score is one to five")
    if not pending(conn, work_item_id):
        raise ValueError("this ticket is not waiting for an answer")
    stamp = at.isoformat(sep=" ", timespec="minutes")
    comment = (comment or "").strip()[:1000] or None
    conn.execute("INSERT INTO survey_response (work_item_id, score, comment, answered_by, answered_at)"
                 " VALUES (?,?,?,?,?)", (work_item_id, score, comment, by, stamp))
    _event(conn, work_item_id, stamp, "SURVEY", by, f"satisfaction {score}/5"
           + (f": {comment[:200]}" if comment else ""))
    findings = phi.scan_fields({"survey": comment}) if comment else []
    for code, severity, detail in findings:
        conn.execute("INSERT INTO data_quality (run_id, subject_kind, subject_id, code, detail,"
                     " severity) VALUES (?,?,?,?,?,?)", ("survey", "ticket", work_item_id, code, detail, severity))
    return findings
