"""Chat (071): a requester and the desk, live.

Dada, 7 Oct 2026: "can we do something to connectwise chat?". Confirmed with
Dada before building: requester <-> desk, offered on the portal at any time,
patient details flagged and warned about, never blocked.

The reference PSA's Chat (INFERRED from its product pages; the Chat docs are
behind sign-in, NOT VERIFIED): a requester starts a chat from the portal, it
waits in a queue for the board, a technician picks it up and replies, and the
chat becomes a ticket (the transcript its first note) or joins an existing one.

Every line a requester writes is scanned for patient details like every other
requester text (§6.1): kept, the finding counted for the desk to tidy, and the
requester reminded. Refusing the line would send the same words to the phone,
where nothing records them.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from . import phi

WAITING, ACTIVE, CLOSED = "WAITING", "ACTIVE", "CLOSED"
REQUESTER, STAFF, SYSTEM = "REQUESTER", "STAFF", "SYSTEM"
MAX_LINE = 2000


class Refused(ValueError):
    """A chat action that cannot be done, in words for the person."""


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="seconds")


def get(conn: sqlite3.Connection, chat_id: int):
    return conn.execute("SELECT c.*, b.display_name AS board_name FROM chat_session c JOIN board b"
                        " ON b.board_id = c.board_id WHERE c.chat_id = ?", (chat_id,)).fetchone()


def _line(conn, chat_id: int, sender: str, kind: str, body: str, at: datetime) -> int:
    cur = conn.execute("INSERT INTO chat_message (chat_id, sender, sender_kind, body, sent_at) VALUES (?,?,?,?,?)",
                       (chat_id, sender, kind, body, _stamp(at)))
    conn.execute("UPDATE chat_session SET last_at = ? WHERE chat_id = ?", (_stamp(at), chat_id))
    return cur.lastrowid


def _scan(conn, chat_id: int, body: str) -> list:
    """§6.1: flag and count, never refuse."""
    findings = phi.scan_fields({"chat": body})
    for code, severity, detail in findings:
        conn.execute("INSERT INTO data_quality (run_id, subject_kind, subject_id, code, detail, severity)"
                     " VALUES (?,?,?,?,?,?)", ("chat", "chat", str(chat_id), code, detail, severity))
    return findings


def _clean(body: str | None) -> str:
    body = (body or "").strip()
    if not body:
        raise Refused("Type a message first.")
    return body[:MAX_LINE]


def start(conn: sqlite3.Connection, *, requester: str, board_id: str, subject: str, first: str,
          at: datetime) -> tuple[int, list]:
    """A requester starts a chat. It waits in the board's queue. Returns the
    chat and the patient-detail findings on what they wrote."""
    requester = (requester or "").strip().lower()
    if not requester:
        raise Refused("Sign in to chat with the helpdesk.")
    if conn.execute("SELECT 1 FROM board WHERE board_id = ?", (board_id,)).fetchone() is None:
        raise Refused("No such helpdesk.")
    subject = " ".join((subject or "").split())[:200]
    first = _clean(first)
    if not subject:
        subject = " ".join(first.split())[:80]
    cur = conn.execute("INSERT INTO chat_session (board_id, requester, subject, status, started_at, last_at)"
                       " VALUES (?,?,?,?,?,?)", (board_id, requester, subject, WAITING, _stamp(at), _stamp(at)))
    chat_id = cur.lastrowid
    _line(conn, chat_id, requester, REQUESTER, first, at)
    return chat_id, _scan(conn, chat_id, subject + "\n" + first)


def say(conn: sqlite3.Connection, chat_id: int, *, sender: str, kind: str, body: str, at: datetime) -> tuple[int, list]:
    """One line from either side. A closed chat takes no more lines."""
    c = get(conn, chat_id)
    if c is None:
        raise Refused("No such chat.")
    if c["status"] == CLOSED:
        raise Refused("This chat has ended. Start a new one, or reply on the ticket.")
    if kind not in (REQUESTER, STAFF):
        raise Refused("No such sender.")
    body = _clean(body)
    mid = _line(conn, chat_id, sender, kind, body, at)
    findings = _scan(conn, chat_id, body) if kind == REQUESTER else []
    if kind == STAFF and c["status"] == WAITING:           # answering it picks it up
        conn.execute("UPDATE chat_session SET status = ?, picked_by = ?, picked_at = ? WHERE chat_id = ?",
                     (ACTIVE, sender, _stamp(at), chat_id))
    return mid, findings


def pick_up(conn: sqlite3.Connection, chat_id: int, *, member: str, at: datetime) -> str:
    c = get(conn, chat_id)
    if c is None:
        raise Refused("No such chat.")
    if c["status"] == CLOSED:
        raise Refused("This chat has ended.")
    if c["status"] == ACTIVE and (c["picked_by"] or "").lower() == member.lower():
        return "nothing changed"
    was = c["picked_by"]
    conn.execute("UPDATE chat_session SET status = ?, picked_by = ?, picked_at = ? WHERE chat_id = ?",
                 (ACTIVE, member, _stamp(at), chat_id))
    _line(conn, chat_id, member, SYSTEM, f"{member} has joined the chat" + (f" (from {was})" if was else ""), at)
    return f"picked up by {member}"


def close(conn: sqlite3.Connection, chat_id: int, *, by: str, at: datetime) -> str:
    c = get(conn, chat_id)
    if c is None:
        raise Refused("No such chat.")
    if c["status"] == CLOSED:
        return "nothing changed"
    conn.execute("UPDATE chat_session SET status = ?, closed_at = ?, closed_by = ? WHERE chat_id = ?",
                 (CLOSED, _stamp(at), by, chat_id))
    _line(conn, chat_id, by, SYSTEM, f"{by} ended the chat", at)
    return "chat ended"


def messages(conn: sqlite3.Connection, chat_id: int, *, after: int = 0) -> list:
    return conn.execute("SELECT message_id, sender, sender_kind, body, sent_at FROM chat_message"
                        " WHERE chat_id = ? AND message_id > ? ORDER BY message_id", (chat_id, after)).fetchall()


def transcript(conn: sqlite3.Connection, chat_id: int) -> str:
    c = get(conn, chat_id)
    lines = [f"Chat {chat_id} with {c['requester']}, started {c['started_at']}:"]
    for m in messages(conn, chat_id):
        who = "desk" if m["sender_kind"] == SYSTEM else m["sender"]
        lines.append(f"[{m['sent_at'][11:16]}] {who}: {m['body']}")
    return "\n".join(lines)


def queue(conn: sqlite3.Connection, boards, *, now: datetime) -> list:
    """The chats the desk sees: waiting and active ones on the person's boards,
    oldest waiting first, then the recently ended."""
    boards = sorted(boards)
    if not boards:
        return []
    marks = ",".join("?" * len(boards))
    return conn.execute(
        "SELECT c.*, b.display_name AS board_name,"
        " (SELECT COUNT(*) FROM chat_message m WHERE m.chat_id = c.chat_id) AS lines"
        " FROM chat_session c JOIN board b ON b.board_id = c.board_id"
        f" WHERE c.board_id IN ({marks}) AND (c.status <> 'CLOSED' OR c.closed_at >= ?)"
        " ORDER BY CASE c.status WHEN 'WAITING' THEN 0 WHEN 'ACTIVE' THEN 1 ELSE 2 END, c.started_at",
        [*boards, _stamp(now - timedelta(days=2))]).fetchall()


def of_requester(conn: sqlite3.Connection, identities) -> list:
    ids = [i.lower() for i in identities if i]
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    return conn.execute("SELECT c.*, b.display_name AS board_name FROM chat_session c JOIN board b ON b.board_id ="
                        f" c.board_id WHERE LOWER(c.requester) IN ({marks}) ORDER BY c.chat_id DESC LIMIT 50",
                        ids).fetchall()


def to_ticket(conn: sqlite3.Connection, chat_id: int, *, member: str, summary: str | None = None,
              impact: str = "I3", urgency: str = "U3", at: datetime) -> str:
    """The chat becomes a ticket on its board: the requester's, the transcript
    its description, the technician its owner. The chat stays open."""
    from . import tickets
    c = get(conn, chat_id)
    if c is None:
        raise Refused("No such chat.")
    if c["work_item_id"]:
        raise Refused(f"This chat is already ticket {c['work_item_id']}.")
    wid = tickets.open_ticket(conn, board_id=c["board_id"], summary=(summary or c["subject"])[:200],
                              impact=impact, urgency=urgency, requested_by=c["requester"], at=at, actor=member,
                              description=transcript(conn, chat_id), owner=member, source="PORTAL")
    conn.execute("UPDATE chat_session SET work_item_id = ? WHERE chat_id = ?", (wid, chat_id))
    _line(conn, chat_id, member, SYSTEM, f"Ticket {wid} was raised from this chat", at)
    return wid


def attach(conn: sqlite3.Connection, chat_id: int, work_item_id: str, *, member: str, at: datetime) -> str:
    """The chat joins an existing ticket: the transcript goes on as a Discussion
    note, so the requester reads it on the portal too (no email for it)."""
    from . import board
    c = get(conn, chat_id)
    if c is None:
        raise Refused("No such chat.")
    if c["work_item_id"]:
        raise Refused(f"This chat is already on ticket {c['work_item_id']}.")
    if conn.execute("SELECT 1 FROM ticket WHERE work_item_id = ?", (work_item_id,)).fetchone() is None:
        raise Refused("No such ticket.")
    board.add_note(conn, work_item_id, body=transcript(conn, chat_id), flag="DISCUSSION", actor=member, at=at,
                   notify_requester=False)
    conn.execute("UPDATE chat_session SET work_item_id = ? WHERE chat_id = ?", (work_item_id, chat_id))
    _line(conn, chat_id, member, SYSTEM, f"This chat was added to ticket {work_item_id}", at)
    return work_item_id
