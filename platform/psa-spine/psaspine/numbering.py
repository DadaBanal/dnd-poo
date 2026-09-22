"""Issue a ticket number from the one sequence, and bind it to its ticket.

D4, closed. One sequence across every board (014 says why), the prefix read from
a row rather than compiled in (§12), and a number never reused — a reused ticket
number is a reference pointing at two different tickets, which is worse than a
gap, and gaps are fine.

Two steps on purpose. `issue()` takes a number; `bind()` says what it became.
A caller that issues a number and then fails leaves a row with no `issued_to`,
which reads as exactly what happened — a number spent and abandoned — instead of
silently disappearing and leaving an unexplained hole in the sequence.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime


def settings(conn: sqlite3.Connection) -> tuple[str, int]:
    row = conn.execute(
        "SELECT prefix, padding FROM ticket_numbering WHERE id = 1").fetchone()
    if row is None:
        raise LookupError("no ticket numbering row; 014 seeds exactly one")
    return row["prefix"], row["padding"]


def format_number(number: int, prefix: str, padding: int) -> str:
    return f"{prefix}-{number:0{padding}d}"


def issue(conn: sqlite3.Connection, *, at: datetime) -> str:
    """Take the next number in the sequence and return it formatted.

    The INTEGER PRIMARY KEY is the sequence: SQLite hands out max+1, and the
    generated SQL Server copy uses IDENTITY, which is the same promise. Nothing
    here computes the next number itself, because two callers computing max+1 at
    once is how a sequence issues one number twice.
    """
    prefix, padding = settings(conn)
    cur = conn.execute(
        "INSERT INTO ticket_number (issued_at, issued_to) VALUES (?, NULL)",
        (at.isoformat(sep=" ", timespec="minutes"),))
    return format_number(cur.lastrowid, prefix, padding)


def bind(conn: sqlite3.Connection, ticket_id: str) -> None:
    """Record which ticket a number became. Idempotent."""
    prefix, padding = settings(conn)
    if not ticket_id.startswith(f"{prefix}-"):
        return                      # an imported id; it was never ours to issue
    try:
        number = int(ticket_id.split("-", 1)[1])
    except (IndexError, ValueError):
        return
    conn.execute("UPDATE ticket_number SET issued_to = ? WHERE number = ?",
                 (ticket_id, number))


def unbound(conn: sqlite3.Connection) -> list[int]:
    """Numbers issued that never became a ticket. A number to report, not to
    reclaim — reclaiming one is how a reference starts pointing at two things."""
    return [r["number"] for r in conn.execute(
        "SELECT number FROM ticket_number WHERE issued_to IS NULL ORDER BY number")]
