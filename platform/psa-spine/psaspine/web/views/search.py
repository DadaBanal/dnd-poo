"""Search for the command palette and the ticket pickers: tickets, contacts and
machines, as JSON.

Cookie-authenticated like every other page (it is not under /api/, which is
token-only by design). It answers only from the boards the person is on, and a
restricted board's hits are a read of restricted data, so they are audited
per board with the count, exactly as the board view audits its list (§6.1
requirement 4). Nothing in the answer is more than the board view shows.

Dada, 5 Oct 2026: *"a search function wherein the ticket will be displayed on
all ticket fields"*. It used to match three things -- the ticket number, the
summary and the requester's address -- which meant the only reliable way to
find a ticket was to already know its number. It now matches every field a
person would search by, including the words of its notes, and that matters most
where a ticket has to be *named*: linking, merging, attaching a child, putting
one on a project or a visit all used to mean typing `PMC-000123` from memory.
"""
from __future__ import annotations

import json

from . import common

LIMIT = 8


def _like(needle: str) -> str:
    from .board import _like as like        # one escaping rule for the whole desk
    return like(needle)


def _note_words(ctx, work_item_id: str, needle: str) -> bool:
    """Whether the needle is in the *words* of one of this ticket's notes.

    A note written in the desk's editor, or arrived as an email's HTML (064), is
    stored as markup, so a SQL LIKE on it matches tag and attribute names: a
    search for "p" or "br" or "noopener" would return every rich note on the
    desk. `richtext.text` is the same function the PHI scan reads, so the answer
    here is the same answer that gate gets.

    The cost is one extra read of the notes of rows SQL already narrowed to a
    handful, and it only runs when the cheap fields did not already match.
    """
    from ... import richtext
    for (detail, fmt) in ctx.conn.execute(
            "SELECT detail, body_format FROM ticket_event WHERE work_item_id = ?"
            " AND note_flag IS NOT NULL", (work_item_id,)):
        if not detail:
            continue
        words = richtext.text(detail) if richtext.is_rich(fmt) else detail
        if needle in words.lower():
            return True
    return False


# Which field matched, in the order a person would expect to be told. The
# picker shows this under each hit, so a result that looks unrelated to what
# was typed explains itself ("found in a note") instead of looking like a bug.
def _why(ctx, row, q: str, like: str) -> str | None:
    needle = q.lower()
    for label, value in (("", row["work_item_id"]), ("", row["summary"]), ("requester", row["who"]),
                         ("company", row["company"]), ("status", row["status_name"]),
                         ("type", row["klass"])):
        if value and needle in str(value).lower():
            return label
    if row["note_hit"] is not None and _note_words(ctx, row["work_item_id"], needle):
        return "in a note"
    # Matched a column the picker does not show (owner, source ref, priority,
    # record type, a contact's email). Say nothing rather than guess.
    return "" if row["note_hit"] is None else None


def search(ctx):
    from .. import Response
    q = ctx.request.query.get("q", "").strip()
    out: dict = {"q": q, "tickets": [], "contacts": [], "configurations": []}
    boards = common.board_ids_for(ctx)
    if len(q) < 2 or not boards:
        return Response(body=json.dumps(out), content_type="application/json; charset=utf-8",
                        headers=[("Cache-Control", "no-store")])
    like = _like(q.lower())
    marks = ",".join("?" * len(boards))
    # Every field a person would search a ticket by. The note text is last on
    # purpose: it is the one clause that cannot use an index, so it is also the
    # one that decides this query's cost, and `_note_match` below throws away
    # the false positives it cannot avoid producing.
    fields = ("LOWER(t.work_item_id)", "LOWER(w.name)", "LOWER(t.requested_by)", "LOWER(t.owner)",
              "LOWER(t.source_ref)", "LOWER(t.record_type)", "LOWER(t.priority)", "LOWER(t.state)")
    where = " OR ".join(f"{f} LIKE ? ESCAPE '\\'" for f in fields)
    rows = ctx.conn.execute(
        "SELECT t.work_item_id, t.board_id, t.state, t.priority, w.name AS summary,"
        "       COALESCE((SELECT ct.display_name FROM contact ct WHERE ct.contact_id = t.contact_id),"
        "                t.requested_by) AS who,"
        "       (SELECT e.name FROM entity e WHERE e.entity_id = w.entity_id) AS company,"
        "       (SELECT s.name FROM board_status s WHERE s.board_status_id = t.board_status_id) AS status_name,"
        "       (SELECT c.display_name || ' / ' || a.display_name FROM catalogue_item i"
        "          JOIN service_component c ON c.component_id = i.component_id"
        "          JOIN service_action a ON a.action_id = i.action_id"
        "         WHERE i.catalogue_item_id = t.catalogue_item_id) AS klass,"
        "       (SELECT MIN(e2.ticket_event_id) FROM ticket_event e2"
        "         WHERE e2.work_item_id = t.work_item_id AND e2.note_flag IS NOT NULL"
        f"          AND LOWER(e2.detail) LIKE ? ESCAPE '\\') AS note_hit"
        f"  FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id WHERE t.board_id IN ({marks})"
        f"   AND ({where}"
        "        OR EXISTS (SELECT 1 FROM contact ct WHERE ct.contact_id = t.contact_id"
        "                    AND (LOWER(ct.display_name) LIKE ? ESCAPE '\\' OR LOWER(ct.email) LIKE ? ESCAPE '\\'))"
        "        OR EXISTS (SELECT 1 FROM entity e WHERE e.entity_id = w.entity_id"
        "                    AND LOWER(e.name) LIKE ? ESCAPE '\\')"
        "        OR EXISTS (SELECT 1 FROM board_status s WHERE s.board_status_id = t.board_status_id"
        "                    AND LOWER(s.name) LIKE ? ESCAPE '\\')"
        "        OR EXISTS (SELECT 1 FROM catalogue_item i"
        "                     JOIN service_component c ON c.component_id = i.component_id"
        "                     JOIN service_action a ON a.action_id = i.action_id"
        "                    WHERE i.catalogue_item_id = t.catalogue_item_id"
        "                      AND (LOWER(c.display_name) LIKE ? ESCAPE '\\'"
        "                           OR LOWER(a.display_name) LIKE ? ESCAPE '\\'))"
        "        OR EXISTS (SELECT 1 FROM ticket_event e3 WHERE e3.work_item_id = t.work_item_id"
        "                    AND e3.note_flag IS NOT NULL AND LOWER(e3.detail) LIKE ? ESCAPE '\\'))"
        " ORDER BY CASE WHEN t.state IN ('RESOLVED','CLOSED','CANCELLED') THEN 1 ELSE 0 END, t.opened_at DESC LIMIT ?",
        [like, *boards, *([like] * len(fields)), like, like, like, like, like, like, like, LIMIT]).fetchall()
    seen: dict[str, int] = {}
    for r in rows:
        where_hit = _why(ctx, r, q, like)
        if where_hit is None:
            continue          # the only hit was markup inside a rich note
        seen[r["board_id"]] = seen.get(r["board_id"], 0) + 1
        out["tickets"].append({"id": r["work_item_id"], "summary": r["summary"], "who": r["who"],
                               "state": r["state"], "priority": r["priority"], "where": where_hit})
    for bid, n in sorted(seen.items()):
        common.audit_restricted_read(ctx, bid, detail=f"search listed {n} ticket(s)")
    for c in ctx.conn.execute(
            "SELECT contact_id, display_name, department FROM contact WHERE inactive = 0 AND"
            " (LOWER(display_name) LIKE ? ESCAPE '\\' OR LOWER(email) LIKE ? ESCAPE '\\')"
            " ORDER BY display_name LIMIT ?", (like, like, LIMIT)):
        out["contacts"].append({"id": c["contact_id"], "name": c["display_name"],
                                "department": c["department"]})
    for m in ctx.conn.execute(
            "SELECT configuration_id, name, config_type FROM configuration WHERE status = 'ACTIVE'"
            " AND LOWER(name) LIKE ? ESCAPE '\\' ORDER BY name LIMIT ?", (like, LIMIT)):
        out["configurations"].append({"id": m["configuration_id"], "name": m["name"],
                                      "type": m["config_type"]})
    return Response(body=json.dumps(out), content_type="application/json; charset=utf-8",
                    headers=[("Cache-Control", "no-store")])
