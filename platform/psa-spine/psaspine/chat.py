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


class AlreadyOpen(Refused):
    """Chat round six: the person already has a chat open; `chat_id` is it."""

    def __init__(self, chat_id: int):
        super().__init__("You already have a chat open with the desk. It is still there: carry on in it.")
        self.chat_id = chat_id


def open_chat_of(conn: sqlite3.Connection, identities) -> int | None:
    """The chat this person has open (waiting or being answered), if any: the
    oldest, when an older store still holds more than one."""
    ids = sorted({(i or "").strip().lower() for i in identities if (i or "").strip()})
    if not ids:
        return None
    row = conn.execute("SELECT chat_id FROM chat_session WHERE status IN ('WAITING', 'ACTIVE') AND LOWER(requester) IN"
                       f" ({','.join('?' * len(ids))}) ORDER BY chat_id", ids).fetchone()
    return row["chat_id"] if row else None


def start(conn: sqlite3.Connection, *, requester: str, board_id: str, subject: str, first: str,
          at: datetime, same_person=()) -> tuple[int, list]:
    """A requester starts a chat. It waits in the board's queue. Returns the
    chat and the patient-detail findings on what they wrote.

    One open chat a person (chat round six; Dada, 8 Oct 2026: "a user can create
    a 100 chats at the same time thats not good"; confirmed: one at a time, and
    starting again takes them back to the one they have). `same_person` is every
    address the portal knows them by, so a second sign-in name is the same
    person. The check is inside the statement that makes the chat, so a burst of
    presses makes one; anything else raises AlreadyOpen with the chat they have."""
    requester = (requester or "").strip().lower()
    if not requester:
        raise Refused("Sign in to chat with the helpdesk.")
    if conn.execute("SELECT 1 FROM board WHERE board_id = ?", (board_id,)).fetchone() is None:
        raise Refused("No such helpdesk.")
    subject = " ".join((subject or "").split())[:200]
    first = _clean(first)
    if not subject:
        subject = " ".join(first.split())[:80]
    ids = sorted({requester} | {(i or "").strip().lower() for i in same_person if (i or "").strip()})
    cur = conn.execute("INSERT INTO chat_session (board_id, requester, subject, status, started_at, last_at)"
                       " SELECT ?, ?, ?, ?, ?, ? WHERE NOT EXISTS (SELECT 1 FROM chat_session WHERE status IN"
                       f" ('WAITING', 'ACTIVE') AND LOWER(requester) IN ({','.join('?' * len(ids))}))",
                       (board_id, requester, subject, WAITING, _stamp(at), _stamp(at), *ids))
    if cur.rowcount != 1 or not cur.lastrowid:
        raise AlreadyOpen(open_chat_of(conn, ids))
    chat_id = cur.lastrowid
    _line(conn, chat_id, requester, REQUESTER, first, at)
    _line(conn, chat_id, "desk", SYSTEM, welcome(conn, board_id), at)       # 072: the "please wait" line
    return chat_id, _scan(conn, chat_id, subject + "\n" + first)


# 072. Dada, 7 Oct 2026: "a message to the user ... before a ticket gets picked
# up like please wait ... similar to support chats". Confirmed: in the chat, the
# desk's words editable per board, and a live place in the queue until picked up.
DEFAULT_WELCOME = ("Thanks, you are in the queue. Someone from {board} will be with you shortly; please keep this "
                   "page open. Meanwhile, the ward, the room and the machine help us most.")


def welcome(conn: sqlite3.Connection, board_id: str) -> str:
    row = conn.execute("SELECT display_name, chat_welcome FROM board WHERE board_id = ?", (board_id,)).fetchone()
    words = (row["chat_welcome"] if row and row["chat_welcome"] else DEFAULT_WELCOME)
    return words.replace("{board}", row["display_name"] if row else "the helpdesk")


def position(conn: sqlite3.Connection, chat_id: int) -> int | None:
    """Where a waiting chat stands in its board's queue (1 is next); None once picked up."""
    c = conn.execute("SELECT board_id, status, started_at FROM chat_session WHERE chat_id = ?", (chat_id,)).fetchone()
    if c is None or c["status"] != WAITING:
        return None
    return conn.execute("SELECT COUNT(*) FROM chat_session WHERE board_id = ? AND status = 'WAITING'"
                        " AND (started_at < ? OR (started_at = ? AND chat_id <= ?))",
                        (c["board_id"], c["started_at"], c["started_at"], chat_id)).fetchone()[0]


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
        _line(conn, chat_id, sender, SYSTEM, f"{_name(conn, sender)} has joined the chat", at)
    return mid, findings


def _name(conn, member: str) -> str:
    try:
        from . import members
        return members.name_of(conn, member) or member
    except Exception:                                  # noqa: BLE001 - a name is a nicety, never a failure
        return member


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
    _line(conn, chat_id, member, SYSTEM, f"{_name(conn, member)} has joined the chat"
          + (f" (from {_name(conn, was)})" if was else ""), at)
    return f"picked up by {member}"


def close(conn: sqlite3.Connection, chat_id: int, *, by: str, at: datetime, closing: str | None = None,
          ask: bool = True) -> str:
    """End the chat. From the desk (074): an optional closing line, said first
    as the operator, and `ask` False to end it without asking the ward how the
    operator did. The ward's own End always asks."""
    c = get(conn, chat_id)
    if c is None:
        raise Refused("No such chat.")
    if c["status"] == CLOSED:
        return "nothing changed"
    closing = _clean(closing) if closing and closing.strip() else ""
    if closing:
        say(conn, chat_id, sender=by, kind=STAFF, body=closing, at=at)
        c = get(conn, chat_id)                         # a closing line on a waiting chat picks it up
    conn.execute("UPDATE chat_session SET status = ?, closed_at = ?, closed_by = ? WHERE chat_id = ?",
                 (CLOSED, _stamp(at), by, chat_id))
    if not ask:
        conn.execute("UPDATE chat_session SET ask_rating = 0 WHERE chat_id = ?", (chat_id,))
    _line(conn, chat_id, by, SYSTEM, f"{by} ended the chat", at)
    if c["work_item_id"]:
        _rest_to_ticket(conn, c, by=by, at=at)
    return "chat ended"


def _mark(conn, chat_id: int, work_item_id: str) -> int:
    """The line where the chat went onto its ticket; what came after it is not
    on the ticket yet."""
    row = conn.execute("SELECT MAX(message_id) FROM chat_message WHERE chat_id = ? AND sender_kind = 'SYSTEM'"
                       " AND (body = ? OR body = ?)",
                       (chat_id, f"Ticket {work_item_id} was raised from this chat",
                        f"This chat was added to ticket {work_item_id}")).fetchone()
    return row[0] or 0


def _rest_to_ticket(conn, c, *, by: str, at: datetime) -> None:
    """Dada, 7 Oct 2026: "also the chat is added on the ticket if ever right?".
    The chat stays open after it becomes a ticket, so what is said after that
    was only on the chat. Confirmed: when the chat ends, the rest of it goes on
    the ticket as one Discussion note (the ward's own words, so the ward may
    read it; no email), with the files sent in that part. Nothing is added when
    nothing more was said."""
    from . import board
    wid = c["work_item_id"]
    mark = _mark(conn, c["chat_id"], wid)
    rows = messages(conn, c["chat_id"], after=mark)
    if not any(m["sender_kind"] != SYSTEM for m in rows):
        return
    nth, _ = counts(conn, c["chat_id"])
    head = (f"The rest of the chat with {label(conn, c['requester'], nth)},"
            f" {rows[0]['sent_at'][11:16]}–{rows[-1]['sent_at'][11:16]}:")
    actor = c["picked_by"] or by
    board.add_note(conn, wid, body="\n".join([head] + [_said(m) for m in rows]), flag="DISCUSSION",
                   actor=actor, at=at, notify_requester=False)
    _files_to_ticket(conn, c["chat_id"], wid, member=actor, at=at, after=mark)


def messages(conn: sqlite3.Connection, chat_id: int, *, after: int = 0) -> list:
    return conn.execute("SELECT message_id, sender, sender_kind, body, sent_at FROM chat_message"
                        " WHERE chat_id = ? AND message_id > ? ORDER BY message_id", (chat_id, after)).fetchall()


def transcript(conn: sqlite3.Connection, chat_id: int) -> str:
    c = get(conn, chat_id)
    nth, total = counts(conn, chat_id)
    lines = [f"Chat with {_name(conn, c['requester'])} ({c['requester']}), their chat {nth} of {total},"
             f" started {c['started_at']}:"]
    lines += [_said(m) for m in messages(conn, chat_id)]
    return "\n".join(lines)


def _said(m) -> str:
    """One line of a transcript: when, who (the desk's own notices as "desk"), what."""
    who = "desk" if m["sender_kind"] == SYSTEM else m["sender"]
    return f"[{m['sent_at'][11:16]}] {who}: {m['body']}"


def queue(conn: sqlite3.Connection, boards, *, now: datetime) -> list:
    """The chats the desk sees: waiting and active ones on the person's boards,
    oldest waiting first, then the recently ended."""
    boards = sorted(boards)
    if not boards:
        return []
    marks = ",".join("?" * len(boards))
    return conn.execute(
        f"SELECT c.*, b.display_name AS board_name, {_COUNTS},"
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
    _files_to_ticket(conn, chat_id, wid, member=member, at=at)
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
    _files_to_ticket(conn, chat_id, work_item_id, member=member, at=at)
    _line(conn, chat_id, member, SYSTEM, f"This chat was added to ticket {work_item_id}", at)
    return work_item_id


# ====================================================== round two (072, 7 Oct 2026)
# Dada: "can we add reactions and emojis to the chat and also attachments and a
# survey at the end". Confirmed: Teams-style reactions and an emoji picker;
# pictures and files through the patient-details review; the requester rates
# the chat when it ends.

REACTIONS = ("\U0001F44D", "\u2764\ufe0f", "\U0001F604", "\U0001F62E", "\U0001F64F", "\u2705")   # like heart smile wow thanks done


def react(conn: sqlite3.Connection, chat_id: int, message_id: int, *, member: str, emoji: str, at: datetime) -> bool:
    """Put a reaction on a line, or take it off if it is there. Returns whether
    it is on now. Only the fixed set; a system line takes none."""
    if emoji not in REACTIONS:
        raise Refused("That reaction is not one of the set.")
    row = conn.execute("SELECT sender_kind FROM chat_message WHERE message_id = ? AND chat_id = ?",
                       (message_id, chat_id)).fetchone()
    if row is None or row["sender_kind"] == SYSTEM:
        raise Refused("No such message.")
    had = conn.execute("SELECT 1 FROM chat_reaction WHERE message_id = ? AND member = ? AND emoji = ?",
                       (message_id, member, emoji)).fetchone()
    if had:
        conn.execute("DELETE FROM chat_reaction WHERE message_id = ? AND member = ? AND emoji = ?",
                     (message_id, member, emoji))
    else:
        conn.execute("INSERT INTO chat_reaction (message_id, member, emoji, reacted_at) VALUES (?,?,?,?)",
                     (message_id, member, emoji, _stamp(at)))
    conn.execute("UPDATE chat_session SET last_at = ? WHERE chat_id = ?", (_stamp(at), chat_id))
    return not had


def reactions(conn: sqlite3.Connection, chat_id: int) -> dict:
    """{message_id: {emoji: [who, ...]}} for every line of the chat."""
    out: dict = {}
    for r in conn.execute("SELECT r.message_id, r.emoji, r.member FROM chat_reaction r JOIN chat_message m"
                          " ON m.message_id = r.message_id WHERE m.chat_id = ? ORDER BY r.reacted_at",
                          (chat_id,)):
        out.setdefault(r["message_id"], {}).setdefault(r["emoji"], []).append(r["member"])
    return out


def add_file(conn: sqlite3.Connection, chat_id: int, data: bytes, filename: str, *, sender: str, kind: str,
             caption: str | None = None, at: datetime) -> int:
    """A picture or file into the chat, as its own line. Kept in the tickets'
    store, by its hash, so the store's integrity check counts it as live. A
    requester's waits for review (PENDING); the desk's is cleared as sent."""
    import gzip
    import hashlib
    import os
    from . import attachments
    c = get(conn, chat_id)
    if c is None:
        raise Refused("No such chat.")
    if c["status"] == CLOSED:
        raise Refused("This chat has ended.")
    if not data:
        raise Refused("The file is empty.")
    if len(data) > attachments.MAX_BYTES:
        raise Refused(f"Files over {attachments.MAX_BYTES // (1024 * 1024)} MB are not kept.")
    media_type = attachments.sniff(data, filename)
    stored, encoding, _how = attachments.prepare(data, media_type)
    served = gzip.decompress(stored) if encoding == "GZIP" else stored
    sha = hashlib.sha256(served).hexdigest()
    path = attachments._path(attachments.store_dir(conn), sha)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        tmp.write_bytes(stored)
        os.replace(tmp, path)
        attachments.seal(path)
    name = attachments.safe_name(filename)
    words = (caption or "").strip()[:MAX_LINE] or f"sent {name}"
    mid = _line(conn, chat_id, sender, kind, words, at)
    staff = kind == STAFF
    cur = conn.execute(
        "INSERT INTO chat_file (chat_id, message_id, filename, media_type, size_received, size_stored, sha256,"
        " encoding, uploaded_by, uploaded_at, review_status, reviewed_by, reviewed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (chat_id, mid, name, media_type, len(data), len(stored), sha, encoding, sender, _stamp(at),
         "CLEARED" if staff else "PENDING", sender if staff else None, _stamp(at) if staff else None))
    if caption and kind == REQUESTER:
        _scan(conn, chat_id, caption)
    if staff and c["status"] == WAITING:
        conn.execute("UPDATE chat_session SET status = ?, picked_by = ?, picked_at = ? WHERE chat_id = ?",
                     (ACTIVE, sender, _stamp(at), chat_id))
    return cur.lastrowid


def files(conn: sqlite3.Connection, chat_id: int) -> dict:
    """{message_id: file row} for the chat."""
    return {r["message_id"]: r for r in conn.execute("SELECT * FROM chat_file WHERE chat_id = ?", (chat_id,))}


def read_file(conn: sqlite3.Connection, chat_id: int, file_id: int):
    """(row, bytes as served), checked against their hash."""
    import gzip
    import hashlib
    from . import attachments
    row = conn.execute("SELECT * FROM chat_file WHERE file_id = ? AND chat_id = ?", (file_id, chat_id)).fetchone()
    if row is None:
        raise LookupError("no such file")
    stored = attachments._path(attachments.store_dir(conn), row["sha256"]).read_bytes()
    data = gzip.decompress(stored) if row["encoding"] == "GZIP" else stored
    if hashlib.sha256(data).hexdigest() != row["sha256"]:
        raise IOError("the file does not match its hash; not served")
    return row, data


def review_file(conn: sqlite3.Connection, chat_id: int, file_id: int, decision: str, *, actor: str, at: datetime) -> str:
    if decision not in ("CLEARED", "WITHHELD"):
        raise Refused("Clear it or withhold it.")
    row = conn.execute("SELECT filename FROM chat_file WHERE file_id = ? AND chat_id = ?", (file_id, chat_id)).fetchone()
    if row is None:
        raise Refused("No such file.")
    conn.execute("UPDATE chat_file SET review_status = ?, reviewed_by = ?, reviewed_at = ? WHERE file_id = ?",
                 (decision, actor, _stamp(at), file_id))
    conn.execute("UPDATE chat_session SET last_at = ? WHERE chat_id = ?", (_stamp(at), chat_id))
    return f"{row['filename']} {'cleared' if decision == 'CLEARED' else 'withheld'}"


def _files_to_ticket(conn, chat_id: int, work_item_id: str, *, member: str, at: datetime, after: int = 0) -> None:
    """The chat's files go onto the ticket it became or joined, with the review
    they already had; a withheld one stays behind. `after`: only the files sent
    after that line (the rest of the chat, when it ends)."""
    from . import attachments
    for r in conn.execute("SELECT * FROM chat_file WHERE chat_id = ? AND review_status <> 'WITHHELD'"
                          " AND COALESCE(message_id, 0) > ? ORDER BY file_id", (chat_id, after)).fetchall():
        _, data = read_file(conn, chat_id, r["file_id"])
        out = attachments.add(conn, work_item_id, data, r["filename"], actor=r["uploaded_by"], at=at,
                              source="PORTAL" if r["review_status"] == "PENDING" else "DESK")
        if r["review_status"] == "CLEARED":
            attachments.review(conn, out["attachment_id"], "CLEARED", actor=member, at=at)


def asked(c) -> bool:
    """Whether the ward is asked to rate this chat (074). Before 074 there is no
    column, and every chat asked."""
    try:
        v = c["ask_rating"]
    except (IndexError, KeyError):
        return True
    return v is None or bool(v)


def operator_of(c) -> str | None:
    """Whom the chat's rating counts to: the operator who had it when it ended."""
    return c["picked_by"] or None


def ratings_by_operator(conn: sqlite3.Connection, boards, *, since: str | None = None) -> list:
    """Each operator's chat rating on these boards: (operator, average, count),
    best first. A chat nobody picked up counts to nobody."""
    boards = sorted(boards)
    if not boards:
        return []
    rows = conn.execute(
        "SELECT c.picked_by AS operator, AVG(CAST(s.score AS REAL)) AS avg, COUNT(*) AS n FROM chat_survey s"
        " JOIN chat_session c ON c.chat_id = s.chat_id"
        f" WHERE c.picked_by IS NOT NULL AND c.board_id IN ({','.join('?' * len(boards))})"
        + (" AND s.answered_at >= ?" if since else "") + " GROUP BY c.picked_by",
        [*boards, *([since] if since else [])]).fetchall()
    return sorted(((r["operator"], round(r["avg"], 2), r["n"]) for r in rows), key=lambda x: (-x[1], -x[2], x[0]))


def rating_of(conn: sqlite3.Connection, member: str) -> tuple[float | None, int]:
    """One operator's chat rating, every board: (average, count)."""
    row = conn.execute("SELECT AVG(CAST(s.score AS REAL)), COUNT(*) FROM chat_survey s JOIN chat_session c"
                       " ON c.chat_id = s.chat_id WHERE LOWER(c.picked_by) = LOWER(?)", (member,)).fetchone()
    return (round(row[0], 2) if row and row[1] else None), (row[1] if row else 0)


def answer_survey(conn: sqlite3.Connection, chat_id: int, *, score: int, comment: str | None, by: str,
                  at: datetime) -> list:
    """The requester rates an ended chat, once. Returns patient-detail findings
    on the comment (kept and counted, as every requester text)."""
    c = get(conn, chat_id)
    if c is None:
        raise Refused("No such chat.")
    if c["status"] != CLOSED:
        raise Refused("The chat is still going.")
    if not asked(c):
        raise Refused("This chat was ended without a rating.")
    if not isinstance(score, int) or not 1 <= score <= 5:
        raise Refused("A score is one to five.")
    if conn.execute("SELECT 1 FROM chat_survey WHERE chat_id = ?", (chat_id,)).fetchone():
        raise Refused("You have rated this chat already. Thank you.")
    comment = (comment or "").strip()[:1000] or None
    conn.execute("INSERT INTO chat_survey (chat_id, score, comment, answered_by, answered_at) VALUES (?,?,?,?,?)",
                 (chat_id, score, comment, by, _stamp(at)))
    _line(conn, chat_id, by, SYSTEM, f"Rated the chat {score} of 5", at)
    return _scan(conn, chat_id, comment) if comment else []


def survey_of(conn: sqlite3.Connection, chat_id: int):
    return conn.execute("SELECT * FROM chat_survey WHERE chat_id = ?", (chat_id,)).fetchone()


# Whose chat, and which of theirs (Dada, 7 Oct 2026: "instead of naming it as chat1 ...
# the name of the user and number so we know how many this person end user has done").
# Chat 3 is the person's third; the total is every chat they have started so far.
_COUNTS = ("(SELECT COUNT(*) FROM chat_session p WHERE p.requester = c.requester AND p.chat_id <= c.chat_id) AS nth,"
           " (SELECT COUNT(*) FROM chat_session p WHERE p.requester = c.requester) AS total")


def counts(conn: sqlite3.Connection, chat_id: int) -> tuple[int, int]:
    """(nth, total): this is the requester's nth chat of total so far."""
    row = conn.execute(f"SELECT {_COUNTS} FROM chat_session c WHERE c.chat_id = ?", (chat_id,)).fetchone()
    return (row["nth"], row["total"]) if row else (0, 0)


def label(conn: sqlite3.Connection, requester: str, nth: int) -> str:
    """'Jun Reyes · chat 3': the name the desk knows the chat by."""
    return f"{_name(conn, requester)} · chat {nth}"


def waiting(conn: sqlite3.Connection, boards) -> list:
    """The chats waiting for someone on these boards, oldest first."""
    return [c for c in live(conn, boards) if c["status"] == WAITING]


def _since(stamp: str, now: datetime | None) -> str:
    if now is None:
        return ""
    try:
        mins = max(0, int((now.replace(tzinfo=None) - datetime.fromisoformat(stamp[:19])).total_seconds() // 60))
    except ValueError:
        return ""
    if mins < 1:
        return "just now"
    if mins < 60:
        return f"{mins} min"
    if mins < 24 * 60:
        return f"{mins // 60} h {mins % 60:02d} min"
    return f"{mins // (24 * 60)} d {mins // 60 % 24} h"


def live(conn: sqlite3.Connection, boards, *, now: datetime | None = None) -> list[dict]:
    """The live chats on these boards for the banner and its quick view: waiting
    ones first, oldest first, then the ones being answered. Each carries whose
    it is and which of theirs, who has it, and its last line (the requester's or
    the desk's, never the desk's own notices)."""
    boards = sorted(boards)
    if not boards:
        return []
    rows = conn.execute(
        "SELECT c.chat_id, c.board_id, c.subject, c.requester, c.status, c.picked_by, c.started_at,"
        f" b.display_name AS board_name, b.restricted, m.body AS last_body, m.sender_kind AS last_kind, {_COUNTS}"
        " FROM chat_session c JOIN board b ON b.board_id = c.board_id"
        " LEFT JOIN chat_message m ON m.message_id = (SELECT MAX(x.message_id) FROM chat_message x"
        "  WHERE x.chat_id = c.chat_id AND x.sender_kind <> 'SYSTEM')"
        f" WHERE c.status <> 'CLOSED' AND c.board_id IN ({','.join('?' * len(boards))})"
        " ORDER BY CASE c.status WHEN 'WAITING' THEN 0 ELSE 1 END, c.started_at, c.chat_id LIMIT 30", boards).fetchall()
    out = []
    for r in rows:
        last = " ".join((r["last_body"] or "").split())
        out.append({
            "id": r["chat_id"], "board_id": r["board_id"], "subject": r["subject"], "who": r["requester"],
            "name": _name(conn, r["requester"]), "nth": r["nth"], "total": r["total"],
            "label": label(conn, r["requester"], r["nth"]), "board": r["board_name"], "status": r["status"],
            "with": _name(conn, r["picked_by"]) if r["picked_by"] else "", "picked_by": r["picked_by"] or "",
            "since": (r["started_at"] or "")[11:16],
            "waited": _since(r["started_at"] or "", now),
            # A restricted board's words stay on its own page, where the read is audited.
            "last": "" if r["restricted"] else (last[:90] + ("…" if len(last) > 90 else "")),
            "last_from": "" if r["restricted"] or not r["last_kind"] else ("desk" if r["last_kind"] == STAFF else "requester"),
        })
    return out


# ---------------------------------------------------------------- operators (073)
# Dada, 7 Oct 2026: "a chat operator member access ... only PMO Helpdesk members
# can use the chat". A board takes chats (Setup › Boards); a member answers them
# when ticked Chat operator (Setup › Members) and is on such a board able to work it.

def chat_boards(conn: sqlite3.Connection) -> list:
    """The boards that take chats from the portal, by name."""
    return conn.execute("SELECT board_id, display_name FROM board WHERE takes_chats = 1 AND COALESCE(inactive, 0) = 0"
                        " ORDER BY display_name").fetchall()


def operators(conn: sqlite3.Connection, board_id: str | None = None) -> list[str]:
    """Chat operators who work a board that takes chats (or that one board), and
    have not left. Empty on a store without 073's columns."""
    try:
        rows = conn.execute(
            "SELECT DISTINCT m.member FROM member m JOIN board_member bm ON LOWER(bm.member) = LOWER(m.member)"
            " JOIN board b ON b.board_id = bm.board_id WHERE m.chat_operator = 1 AND m.inactive_from IS NULL"
            " AND bm.access IN ('WORK', 'ADMIN') AND b.takes_chats = 1"
            + (" AND b.board_id = ?" if board_id else "") + " ORDER BY m.member",
            (board_id,) if board_id else ()).fetchall()
    except Exception:                                  # noqa: BLE001 - before 073 nobody answers chats
        return []
    return [r["member"] for r in rows]


def is_operator(conn: sqlite3.Connection, member: str | None) -> bool:
    row = conn.execute("SELECT chat_operator FROM member WHERE LOWER(member) = LOWER(?)", (member or "",)).fetchone()
    return bool(row and row["chat_operator"])


def operator_boards(conn: sqlite3.Connection, member: str | None, boards) -> set:
    """Of the boards a person can see, the ones whose chats they answer: none
    unless they are a chat operator, and only boards that take chats."""
    if not is_operator(conn, member):
        return set()
    takes = {r["board_id"] for r in chat_boards(conn)}
    return {b for b in boards if b in takes}


def _working_chat_boards(conn, member: str) -> list[str]:
    return [r["board_id"] for r in conn.execute(
        "SELECT bm.board_id FROM board_member bm JOIN board b ON b.board_id = bm.board_id"
        " WHERE LOWER(bm.member) = LOWER(?) AND bm.access IN ('WORK', 'ADMIN') AND b.takes_chats = 1",
        (member,)).fetchall()]


def set_operator(conn: sqlite3.Connection, member: str, on: bool, *, at: datetime, actor: str) -> str:
    """Tick or untick Chat operator on a member record, making the record if
    the person is known only from a membership. Given only to someone who can
    work a board that takes chats. Audited on the member's history."""
    from . import members
    if not members.exists(conn, member):
        raise Refused("No such member.")
    ident = next(x for x in members.identifiers(conn) if x.lower() == member.strip().lower())
    if on and not _working_chat_boards(conn, ident):
        names = ", ".join(r["display_name"] for r in chat_boards(conn)) or "no board yet"
        raise Refused(f"Only someone who works a board that takes chats can be a chat operator ({names}). "
                      "Put them on that board first.")
    stamp = _stamp(at)
    row = conn.execute("SELECT member, chat_operator, inactive_from FROM member WHERE LOWER(member) = LOWER(?)",
                       (ident,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO member (member, created_at, created_by, updated_at, updated_by) VALUES (?,?,?,?,?)",
                     (ident, stamp, actor, stamp, actor))
        row = conn.execute("SELECT member, chat_operator, inactive_from FROM member WHERE member = ?", (ident,)).fetchone()
    if on and row["inactive_from"]:
        raise Refused("They have left; bring them back on the desk first.")
    if bool(row["chat_operator"]) == bool(on):
        return f"{ident} is already " + ("a chat operator." if on else "not a chat operator.")
    conn.execute("UPDATE member SET chat_operator = ?, updated_at = ?, updated_by = ? WHERE member = ?",
                 (1 if on else 0, stamp, actor, row["member"]))
    members._audit(conn, at, actor, row["member"], "chat operator " + ("ticked" if on else "unticked"))
    return f"{ident} is " + ("now a chat operator." if on else "no longer a chat operator.")


def operator_since(conn: sqlite3.Connection, chat_id: int, member: str, *, now: datetime) -> datetime:
    """When this operator's time on the chat began: their pick-up, else their
    first line in it, else now. What the time entry window starts from when
    the chat becomes a ticket (Dada, 7 Oct 2026: "the operators time be
    recorded"; confirmed: pre-filled for the operator to confirm)."""
    c = get(conn, chat_id)
    stamps = []
    if c and c["picked_at"] and (c["picked_by"] or "").lower() == member.lower():
        stamps.append(c["picked_at"])
    row = conn.execute("SELECT MIN(sent_at) FROM chat_message WHERE chat_id = ? AND sender_kind = 'STAFF'"
                       " AND LOWER(sender) = LOWER(?)", (chat_id, member)).fetchone()
    if row and row[0]:
        stamps.append(row[0])
    if not stamps:
        return now
    first = datetime.fromisoformat(min(stamps)[:19])
    return min(first, now.replace(tzinfo=None))
