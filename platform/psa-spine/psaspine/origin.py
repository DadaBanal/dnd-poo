"""Where a ticket came from: Chat, Portal, Email, Desk or Other.

Dada, 9 Oct 2026: "chat tickets differ from regular ticketing can we do a
separation if the tickets came from chat rather than numbering?" Confirmed
before building: every ticket keeps its PMC- number (one sequence, D4); a
badge on the ticket and on every board row, a "Came from" filter on the
Service Board, and Reports split the same way. A Chat ticket is one an
operator made from a live chat or attached a chat to.

No schema step: a chat already names its ticket (`chat_session.work_item_id`,
071), so this reads that link and `ticket.intake_source` (018), and works on
every ticket ever raised. A ticket made from a chat is written PORTAL in
`intake_source` (it is the requester's own door), so the chat link is checked
first.
"""
from __future__ import annotations

from . import db

BUCKETS = {"CHAT": "Chat", "PORTAL": "Portal", "EMAIL": "Email", "DESK": "Desk", "OTHER": "Other"}
_DESKISH = ("DESK", "PHONE", "WALK_UP")
_OTHER = ("API", "IMPORT")
_RAW_WORDS = {"PHONE": "Phone", "WALK_UP": "Walk-up", "API": "API", "IMPORT": "Import"}


def bucket(intake_source: str | None, chat_id) -> str:
    if chat_id:
        return "CHAT"
    if intake_source == "PORTAL":
        return "PORTAL"
    if intake_source == "EMAIL":
        return "EMAIL"
    if intake_source in _OTHER:
        return "OTHER"
    return "DESK"


def _chats(conn) -> bool:
    return db.table_exists(conn, "chat_session")


def of(conn, rows) -> dict[str, dict]:
    """For (work_item_id, intake_source[, portal tile label]) rows: where each
    came from, as {"key", "label", "chat_id"}. One query for all of them."""
    rows = list(rows)
    ids = [r[0] for r in rows]
    chat: dict[str, int] = {}
    if ids and _chats(conn):
        for i in range(0, len(ids), 500):
            part = ids[i:i + 500]
            for r in conn.execute("SELECT work_item_id, MIN(chat_id) AS chat_id FROM chat_session"
                                  " WHERE work_item_id IN (%s) GROUP BY work_item_id" % ",".join("?" * len(part)),
                                  part):
                chat[r["work_item_id"]] = r["chat_id"]
    out = {}
    for r in rows:
        wid, src = r[0], r[1]
        tile = r[2] if len(r) > 2 else None
        key = bucket(src, chat.get(wid))
        if key == "CHAT":
            label = f"Chat #{chat[wid]}"
        elif key == "PORTAL" and tile:
            label = "Portal tile"
        elif src in _RAW_WORDS:
            label = _RAW_WORDS[src]
        else:
            label = BUCKETS[key]
        out[wid] = {"key": key, "label": label, "chat_id": chat.get(wid), "tile": tile}
    return out


def one(conn, work_item_id: str) -> dict:
    row = conn.execute("SELECT work_item_id, intake_source FROM ticket WHERE work_item_id = ?",
                       (work_item_id,)).fetchone()
    if row is None:
        return {"key": "DESK", "label": "Desk", "chat_id": None, "tile": None}
    tile = None
    if db.column_exists(conn, "ticket", "portal_tile_id"):
        r = conn.execute("SELECT p.label FROM ticket t JOIN portal_tile p ON p.tile_id = t.portal_tile_id"
                         " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
        tile = r[0] if r else None
    return of(conn, [(row[0], row[1], tile)])[work_item_id]


def where(conn, key: str, alias: str = "t") -> tuple[str, list]:
    """A WHERE clause for one bucket, on the ticket alias given."""
    has = (f"EXISTS (SELECT 1 FROM chat_session cs WHERE cs.work_item_id = {alias}.work_item_id)"
           if _chats(conn) else "1 = 0")
    src = f"{alias}.intake_source"
    if key == "CHAT":
        return has, []
    if key == "PORTAL":
        return f"({src} = 'PORTAL' AND NOT {has})", []
    if key == "EMAIL":
        return f"({src} = 'EMAIL' AND NOT {has})", []
    if key == "OTHER":
        return f"({src} IN ('API', 'IMPORT') AND NOT {has})", []
    return f"(({src} IS NULL OR {src} IN ('DESK', 'PHONE', 'WALK_UP')) AND NOT {has})", []
