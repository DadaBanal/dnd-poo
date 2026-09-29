"""Channels beyond email (050): a card in a Teams channel.

A Teams channel is named on the desk by a short name (Setup › Integrations ›
Teams channels); the address it posts to, an incoming-webhook URL, lives only
on the host in a file the sender reads. The desk queues a card in the same
outbox as email, on its own channel, and `Send-PsaTeamsNotifications.ps1`
takes that channel and nothing else. A card carries the ticket number, the
board, the priority, the status and the owner, the rule's words, and a link
to the desk. Never the summary and never a note: a channel is outside the
sign-in, and §6.1 keeps a patient's words behind it.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime

from . import db

EMAIL, TEAMS = "EMAIL", "TEAMS"
CHANNELS = (EMAIL, TEAMS)
KINDS = ("TEAMS_WEBHOOK",)
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")


class Refused(ValueError):
    """A sentence for the person; nothing was written."""


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def targets(conn: sqlite3.Connection, *, active_only: bool = False) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM channel_target" + (" WHERE inactive = 0" if active_only else "")
                        + " ORDER BY inactive, target_id").fetchall()


def get(conn: sqlite3.Connection, target_id: str):
    return conn.execute("SELECT * FROM channel_target WHERE target_id = ?", (target_id or "",)).fetchone()


def add_target(conn: sqlite3.Connection, target_id: str, *, label: str, pages: bool = False,
               note: str | None = None, kind: str = "TEAMS_WEBHOOK", at: datetime, actor: str) -> str:
    """Name a channel. The name is what the host's webhook file is keyed by."""
    name = (target_id or "").strip().lower()
    if not _NAME.match(name):
        raise Refused("A channel name is 2 to 40 characters: lower-case letters, digits and hyphens, e.g. helpdesk-alerts.")
    if kind not in KINDS:
        raise Refused("The only channel kind so far is a Teams webhook.")
    label = " ".join((label or "").split())[:120]
    if not label:
        raise Refused("A channel needs a label people recognise, e.g. IT Helpdesk › Alerts.")
    if get(conn, name) is not None:
        raise Refused(f"There is already a channel named {name}.")
    conn.execute("INSERT INTO channel_target (target_id, kind, label, pages, note, inactive, created_at, created_by)"
                 " VALUES (?,?,?,?,?,0,?,?)", (name, kind, label, int(bool(pages)), (note or "").strip()[:500] or None,
                                              _stamp(at), actor))
    db.audit(conn, at=_stamp(at), actor=actor, action="CHANNEL", subject_kind="channel_target", subject_id=name,
             detail=f"added ({kind}, {label}){', carries pages' if pages else ''}")
    return name


def set_active(conn: sqlite3.Connection, target_id: str, active: bool, *, at: datetime, actor: str) -> bool:
    row = get(conn, target_id)
    if row is None:
        raise Refused("No such channel.")
    if bool(row["inactive"]) == (not active):
        return False
    conn.execute("UPDATE channel_target SET inactive = ? WHERE target_id = ?", (0 if active else 1, target_id))
    db.audit(conn, at=_stamp(at), actor=actor, action="CHANNEL", subject_kind="channel_target", subject_id=target_id,
             detail="turned on" if active else "turned off")
    return True


def set_pages(conn: sqlite3.Connection, target_id: str, pages: bool, *, at: datetime, actor: str) -> bool:
    row = get(conn, target_id)
    if row is None:
        raise Refused("No such channel.")
    if bool(row["pages"]) == bool(pages):
        return False
    conn.execute("UPDATE channel_target SET pages = ? WHERE target_id = ?", (int(bool(pages)), target_id))
    db.audit(conn, at=_stamp(at), actor=actor, action="CHANNEL", subject_kind="channel_target", subject_id=target_id,
             detail="carries pages" if pages else "no longer carries pages")
    return True


def queue_teams(conn: sqlite3.Connection, work_item_id: str, target_id: str, *, subject: str, body: str | None,
                at: datetime, event_id: str | None = None, page_id: int | None = None, actor: str = "desk") -> int:
    """One card for a channel, PENDING in the outbox. The target must be a
    channel the desk knows and has on; a rule pointing at nothing fails out
    loud, like a notify to nobody."""
    from .board import _event
    tgt = get(conn, target_id)
    if tgt is None or tgt["inactive"]:
        raise LookupError(f"Teams channel {target_id or '(none)'} is not set up or is off (Setup › Integrations)")
    stamp = _stamp(at)
    cur = conn.execute(
        "INSERT INTO notification (work_item_id, event_id, recipient, recipient_role, subject, body, created_at,"
        " status, channel, target_id, page_id) VALUES (?,?,?,?,?,?,?,'PENDING',?,?,?)",
        (work_item_id, event_id, target_id, "CHANNEL", subject, body, stamp, TEAMS, target_id, page_id))
    _event(conn, work_item_id, stamp, "NOTIFY", actor, f"card to the Teams channel queued: {target_id}")
    return cur.lastrowid


def card(conn: sqlite3.Connection, n: sqlite3.Row, *, desk_url: str | None = None) -> dict:
    """The Adaptive Card a channel shows, in the incoming-webhook envelope. No
    summary, no note: the words stay behind the sign-in."""
    tk = conn.execute(
        "SELECT t.priority, t.owner, b.display_name AS board_name, s.name AS status_name, t.state"
        "  FROM ticket t JOIN board b ON b.board_id = t.board_id"
        "  LEFT JOIN board_status s ON s.board_status_id = t.board_status_id WHERE t.work_item_id = ?",
        (n["work_item_id"],)).fetchone()
    facts = [{"title": "Ticket", "value": n["work_item_id"]}]
    if tk is not None:
        facts += [{"title": "Board", "value": tk["board_name"]},
                  {"title": "Priority", "value": tk["priority"] or "-"},
                  {"title": "Status", "value": tk["status_name"] or (tk["state"] or "").replace("_", " ").title()},
                  {"title": "Owner", "value": tk["owner"] or "unassigned"}]
    body = [{"type": "TextBlock", "size": "Medium", "weight": "Bolder", "wrap": True, "text": n["subject"]},
            {"type": "FactSet", "facts": facts}]
    if n["body"]:
        body.append({"type": "TextBlock", "wrap": True, "text": n["body"]})
    content = {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard",
               "version": "1.4", "body": body}
    if desk_url:
        content["actions"] = [{"type": "Action.OpenUrl", "title": "Open on the desk",
                               "url": f"{desk_url}/ticket/{n['work_item_id']}"}]
    return {"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive",
                                                "contentUrl": None, "content": content}]}


def pending_teams(conn: sqlite3.Connection, *, limit: int = 50, dry_run: bool = False,
                  desk_url: str | None = None) -> list[dict]:
    """What the Teams sender posts now: one card per row, keyed by the channel
    name the host resolves to a URL. A card whose channel is gone or off is
    marked NO_SENDER here, so it never sits PENDING for ever."""
    import os
    desk_url = (desk_url or os.environ.get("PSA_PUBLIC_URL") or "").rstrip("/")
    if desk_url and not desk_url.lower().startswith("https://"):
        raise ValueError("the desk address must be https://")
    out = []
    for n in conn.execute("SELECT * FROM notification WHERE status = 'PENDING' AND channel = ?"
                          " ORDER BY notification_id LIMIT ?", (TEAMS, limit)).fetchall():
        tgt = get(conn, n["target_id"])
        if tgt is None or tgt["inactive"]:
            if not dry_run:
                conn.execute("UPDATE notification SET status = 'NO_SENDER' WHERE notification_id = ?",
                             (n["notification_id"],))
            continue
        out.append({"id": n["notification_id"], "target": n["target_id"], "ticket": n["work_item_id"],
                    "card": card(conn, n, desk_url=desk_url or None)})
    if not dry_run:
        conn.commit()
    return out
