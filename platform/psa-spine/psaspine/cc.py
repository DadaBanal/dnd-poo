"""Cc on a ticket (061): who else hears about it.

Dada, 1 Oct 2026: "can we add a cc on the tickets". In the reference PSA a
ticket carries a Cc list beside its contact; the email connector fills it
from the mail's Cc header and the requester's emails copy them. Here:

- an email's Cc addresses are kept on the ticket it opens, and a reply's new
  ones are added; never the sender (they are the requester), never one of
  the desk's own addresses (the loop guard's list);
- a person edits the list on the ticket, comma separated, each one checked;
- every requester email (opened, status, picked up, updated, closed) goes to
  them as Cc, only within the sender's allowed domains; the sender script
  gets them as `cc` beside `to`.

Every change is one line in the ticket's history. No words of the ticket are
stored here, only addresses, and the Cc'd see the same words the requester
does: never the summary, never a note (§6.1).
"""
from __future__ import annotations

import email.utils
import re
import sqlite3
from datetime import datetime

_ADDRESS = re.compile(r"^[a-z0-9._%+'-]+@[a-z0-9-]+(\.[a-z0-9-]+)+$")


def of(conn: sqlite3.Connection, work_item_id: str) -> list[str]:
    return [r["address"] for r in conn.execute(
        "SELECT address FROM ticket_cc WHERE work_item_id = ? ORDER BY address", (work_item_id,))]


def parse(text: str | None) -> list[str]:
    """Addresses as a person writes them: commas, semicolons, spaces or new
    lines between them, any case. Each one is checked; the first bad one is
    the error."""
    out: list[str] = []
    for a in re.split(r"[\s,;]+", (text or "").lower()):
        if not a or a in out:
            continue
        if not _ADDRESS.match(a) or len(a) > 200:
            raise ValueError(f"{a} does not look like an email address")
        out.append(a)
    return out


def set_(conn: sqlite3.Connection, work_item_id: str, text: str | None, *, at: datetime, actor: str) -> str | None:
    """The list as typed on the ticket replaces what is there. Returns the
    history line, or None when nothing changed."""
    from .board import _event
    wanted = parse(text)
    before = of(conn, work_item_id)
    if sorted(wanted) == before:
        return None
    stamp = at.isoformat(sep=" ", timespec="minutes")
    conn.execute("DELETE FROM ticket_cc WHERE work_item_id = ?", (work_item_id,))
    for a in wanted:
        conn.execute("INSERT INTO ticket_cc (work_item_id, address, source, added_at, added_by) VALUES (?,?,?,?,?)",
                     (work_item_id, a, "DESK", stamp, actor))
    line = f"cc {', '.join(before) or '-'} -> {', '.join(sorted(wanted)) or '-'}"
    _event(conn, work_item_id, stamp, "UPDATED", actor, line)
    return line


def add_from_message(conn: sqlite3.Connection, work_item_id: str, message, *, sender: str,
                     own_addresses, at: datetime) -> list[str]:
    """The Cc addresses of an email, onto its ticket. The sender is the
    requester, not a Cc; the desk's own addresses never are."""
    from .board import _event
    from .intake import _decode
    skip = {(sender or "").lower()} | {a.lower() for a in own_addresses} | set(of(conn, work_item_id))
    added: list[str] = []
    for raw in message.get_all("Cc", []):
        for _, addr in email.utils.getaddresses([_decode(raw)]):
            a = (addr or "").strip().lower()
            if not a or a in skip or a in added or not _ADDRESS.match(a) or len(a) > 200:
                continue
            added.append(a)
    if not added:
        return []
    stamp = at.isoformat(sep=" ", timespec="minutes")
    for a in added:
        conn.execute("INSERT INTO ticket_cc (work_item_id, address, source, added_at, added_by) VALUES (?,?,?,?,?)",
                     (work_item_id, a, "EMAIL", stamp, "intake"))
    _event(conn, work_item_id, stamp, "UPDATED", "intake", "cc from the email: " + ", ".join(added))
    return added
