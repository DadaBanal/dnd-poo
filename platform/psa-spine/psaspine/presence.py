"""The in/out board (057): where each member is right now, said by themselves.

The reference PSA's In/Out board is a list of members with In, Out, and a
note. Here: a state (in, out, on site, working remotely, on leave), a note
(where, or why), and when they expect to be back. Anyone with the Schedule
module sees the people who work the boards they see; a person sets only
their own line. Nothing here changes a ticket or a visit.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

STATES = {"IN": "In", "OUT": "Out", "ON_SITE": "On site", "REMOTE": "Working remotely", "LEAVE": "On leave"}


class Refused(ValueError):
    """A sentence for the person; nothing was written."""


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def set_state(conn: sqlite3.Connection, member: str, state: str, *, at: datetime, note=None, back_at=None) -> dict:
    if state not in STATES:
        raise Refused("A state is in, out, on site, working remotely or on leave.")
    m = (member or "").strip()
    if not m:
        raise Refused("Whose state?")
    n = " ".join(str(note or "").split())[:200] or None
    b = (back_at or "").strip() or None
    if b:
        try:
            b = datetime.fromisoformat(b.replace("T", " ")).isoformat(sep=" ", timespec="minutes")
        except ValueError:
            raise Refused("Back at is a date and time, e.g. 2026-10-01 14:00.")
    conn.execute("DELETE FROM member_presence WHERE LOWER(member) = LOWER(?)", (m,))
    conn.execute("INSERT INTO member_presence (member, state, note, back_at, set_at, set_by) VALUES (?,?,?,?,?,?)",
                 (m, state, n, b, _stamp(at), m))
    return {"member": m, "state": state, "note": n, "back_at": b}


def current(conn: sqlite3.Connection, member: str):
    return conn.execute("SELECT * FROM member_presence WHERE LOWER(member) = LOWER(?)", (member,)).fetchone()


def all_(conn: sqlite3.Connection, members) -> dict:
    """member (as given) -> the row, or None when nothing was ever said."""
    rows = {r["member"].lower(): r for r in conn.execute("SELECT * FROM member_presence")}
    return {m: rows.get(m.lower()) for m in members}


def word(row) -> str:
    """One short phrase for a chip: 'Out until 14:00', 'On site: ward 3'."""
    if row is None:
        return ""
    w = STATES[row["state"]]
    if row["back_at"]:
        w += " until " + (row["back_at"][11:] if row["back_at"][:10] == row["set_at"][:10] else row["back_at"])
    if row["note"]:
        w += ": " + row["note"]
    return w
