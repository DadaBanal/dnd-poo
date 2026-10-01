"""The desk's schedule on each member's Outlook calendar, and their Outlook
busy times on the desk (059).

Dada, 1 Oct 2026: PMC's accounts are synced from AD to Microsoft 365, so a
member's desk visits and tasks should be on their real Outlook calendar, and
what is on their Outlook calendar should show on the desk.

The desk holds no credential. Every change to a visit or a block is queued
here (calendar_sync); `scripts/Sync-PsaCalendars.ps1` on DND-SQL01 asks
`psaspine calendar-pending` what is due, writes each event to the member's
calendar through Microsoft Graph, and reports back with `calendar-mark`.
It then reads each member's calendar for the next weeks and hands the busy
times back with `calendar-busy`. The same shape as mail pickup and the
notification sender.

What goes onto a calendar: for a visit, the ticket's reference, the board
and the place, the visit's status and a link to the ticket on the desk;
never the summary or a note (6.1: the words stay behind the sign-in, as the
.ics feed already does). For a block, its kind and its name, which staff
typed for that purpose. What comes back: busy, tentative, out of office or
working elsewhere, and when; never a subject, an attendee or a body. The
desk's own events come back tagged with the category "Dada PSA" and the
script leaves them out, so nothing echoes.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

CATEGORY = "Dada PSA"
SHOW_AS = {"busy": "BUSY", "tentative": "TENTATIVE", "oof": "OOF", "workingElsewhere": "WORKING_ELSEWHERE"}


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def queue(conn: sqlite3.Connection, kind: str, ref_id: int, action: str, *, member: str, at: datetime,
          event_id: str | None = None) -> None:
    """Something changed on a visit or a block. One unsent write per thing:
    a newer change replaces an unsent one. A removal of something never
    written cancels its unsent write and sends nothing."""
    pend = conn.execute("SELECT sync_id, action FROM calendar_sync WHERE kind = ? AND ref_id = ? AND member = ?"
                        " AND status = 'PENDING'", (kind, ref_id, member)).fetchall()
    if action == "DELETE" and not event_id:
        for p in pend:
            conn.execute("UPDATE calendar_sync SET status = 'SUPERSEDED' WHERE sync_id = ?", (p["sync_id"],))
        return
    for p in pend:
        conn.execute("UPDATE calendar_sync SET status = 'SUPERSEDED' WHERE sync_id = ?", (p["sync_id"],))
    conn.execute("INSERT INTO calendar_sync (kind, ref_id, member, action, event_id, created_at)"
                 " VALUES (?,?,?,?,?,?)", (kind, ref_id, member, action, event_id, _stamp(at)))


def visit_changed(conn, schedule_id: int, *, at: datetime, old_member: str | None = None,
                  old_event_id: str | None = None) -> None:
    """A visit was booked or changed. When it moved to another person, the old
    person's event goes and the new person's is written."""
    r = conn.execute("SELECT member, outlook_event_id FROM ticket_schedule WHERE schedule_id = ?",
                     (schedule_id,)).fetchone()
    if r is None:
        return
    if old_member and old_member.lower() != r["member"].lower():
        queue(conn, "VISIT", schedule_id, "DELETE", member=old_member, at=at, event_id=old_event_id)
        conn.execute("UPDATE ticket_schedule SET outlook_event_id = NULL WHERE schedule_id = ?", (schedule_id,))
    queue(conn, "VISIT", schedule_id, "UPSERT", member=r["member"], at=at)


def removed(conn, kind: str, row, *, at: datetime) -> None:
    key = "schedule_id" if kind == "VISIT" else "block_id"
    queue(conn, kind, row[key], "DELETE", member=row["member"], at=at, event_id=row["outlook_event_id"])


def backfill(conn, *, at: datetime) -> int:
    """Queue every visit and block from today on that has never been written
    (the first sync after 059 goes live). Returns how many."""
    today = at.strftime("%Y-%m-%d") + " 00:00"
    n = 0
    for r in conn.execute("SELECT schedule_id FROM ticket_schedule WHERE outlook_event_id IS NULL AND ends_at >= ?"
                          " AND done_at IS NULL", (today,)).fetchall():
        visit_changed(conn, r["schedule_id"], at=at)
        n += 1
    for r in conn.execute("SELECT block_id, member FROM schedule_block WHERE outlook_event_id IS NULL AND ends_at >= ?",
                          (today,)).fetchall():
        queue(conn, "BLOCK", r["block_id"], "UPSERT", member=r["member"], at=at)
        n += 1
    return n


def _mailbox(conn, member: str) -> str | None:
    from .outbox import address_for
    row = conn.execute("SELECT email FROM member WHERE LOWER(member) = LOWER(?) AND email IS NOT NULL", (member,)).fetchone()
    return (row["email"] if row else None) or address_for(conn, member)


def members(conn, *, allowed_domains: tuple[str, ...]) -> list[dict]:
    """Every active member who works a board, with the mailbox their calendar
    is in: who the sync reads busy times for."""
    allowed = tuple(d.lower().lstrip("@") for d in allowed_domains)
    out, seen = [], set()
    for r in conn.execute("SELECT DISTINCT bm.member FROM board_member bm LEFT JOIN member m ON LOWER(m.member) ="
                          " LOWER(bm.member) WHERE bm.access IN ('WORK', 'ADMIN') AND m.inactive_from IS NULL"
                          " ORDER BY bm.member"):
        m = r["member"]
        if m.lower() in seen:
            continue
        seen.add(m.lower())
        box = _mailbox(conn, m)
        if box and box.rsplit("@", 1)[-1].lower() in allowed:
            out.append({"member": m, "mailbox": box})
    return out


def pending(conn, *, allowed_domains: tuple[str, ...], desk_url: str = "", limit: int = 100,
            dry_run: bool = False) -> list[dict]:
    """What is due, as the script needs it. A write whose visit or block has
    gone is SUPERSEDED; a member with no mailbox in the allowed domains is
    NO_MAILBOX, never a guess."""
    allowed = tuple(d.lower().lstrip("@") for d in allowed_domains)
    desk_url = (desk_url or "").rstrip("/")
    out = []
    for s in conn.execute("SELECT * FROM calendar_sync WHERE status = 'PENDING' ORDER BY sync_id LIMIT ?",
                          (limit,)).fetchall():
        def mark(status):
            if not dry_run:
                conn.execute("UPDATE calendar_sync SET status = ? WHERE sync_id = ?", (status, s["sync_id"]))
        box = _mailbox(conn, s["member"])
        if not box or box.rsplit("@", 1)[-1].lower() not in allowed:
            mark("NO_MAILBOX")
            continue
        item = {"id": s["sync_id"], "action": s["action"], "mailbox": box, "event_id": s["event_id"]}
        if s["action"] == "UPSERT":
            if s["kind"] == "VISIT":
                v = conn.execute(
                    "SELECT s.*, t.board_id, b.display_name AS board, st.name AS status_name, l.name AS place"
                    "  FROM ticket_schedule s JOIN ticket t ON t.work_item_id = s.work_item_id"
                    "  JOIN board b ON b.board_id = t.board_id"
                    "  LEFT JOIN schedule_status st ON st.status_id = s.status_id"
                    "  LEFT JOIN service_location l ON l.location_id = s.location_id"
                    " WHERE s.schedule_id = ?", (s["ref_id"],)).fetchone()
                if v is None or v["member"].lower() != s["member"].lower():
                    mark("SUPERSEDED")
                    continue
                link = f"{desk_url}/ticket/{v['work_item_id']}" if desk_url else f"the desk, ticket {v['work_item_id']}"
                subject, body = event_words(conn, v, link)
                item.update({
                    "event_id": v["outlook_event_id"], "subject": subject, "body": body,
                    "start": v["starts_at"], "end": v["ends_at"],
                    "show_as": "tentative" if v["status_id"] == "TENTATIVE" else "busy",
                    "location": v["place"] or ""})
            else:
                b = conn.execute("SELECT * FROM schedule_block WHERE block_id = ?", (s["ref_id"],)).fetchone()
                if b is None:
                    mark("SUPERSEDED")
                    continue
                from .schedule import BLOCK_KINDS
                item.update({"event_id": b["outlook_event_id"],
                             "subject": f"{BLOCK_KINDS[b['kind']]}: {b['name']}",
                             "body": "From the Dada PSA schedule.", "start": b["starts_at"], "end": b["ends_at"],
                             "show_as": "oof" if b["kind"] == "TIME_OFF" else "busy", "location": ""})
            item["category"] = CATEGORY
        elif not s["event_id"]:
            mark("SUPERSEDED")
            continue
        out.append(item)
    if not dry_run:
        conn.commit()
    return out


def event_words(conn, v, link: str) -> tuple[str, str]:
    """What the Outlook appointment says, as the reference PSA's calendar sync
    writes a schedule entry (Dada, 1 Oct 2026: "what should go in outlook is
    the same as the outlook api or integration from connectwise"): the
    ticket number, the company and the summary in the subject; the summary,
    status, place and a link in the body. The one guard the record keeps: a
    ticket on a restricted board, or whose summary the PHI scan flags, goes
    by its number and board alone (6.1), so a patient's details never reach
    a calendar that syncs to a phone."""
    from . import phi
    row = conn.execute("SELECT w.name AS summary, e.name AS company, w.entity_id, b.restricted FROM ticket t"
                       "  JOIN work_item w ON w.work_item_id = t.work_item_id JOIN board b ON b.board_id = t.board_id"
                       "  LEFT JOIN entity e ON e.entity_id = w.entity_id WHERE t.work_item_id = ?",
                       (v["work_item_id"],)).fetchone()
    summary = (row["summary"] if row else "") or ""
    guarded = bool(row and row["restricted"]) or any(sev == "ERROR" for _, sev, _ in phi.scan(summary, field="summary"))
    status = f" Status: {v['status_name']}." if v["status_name"] else ""
    if guarded:
        subject = f"{v['work_item_id']} - {v['board']}" + (f" - {v['place']}" if v["place"] else "")
        body = f"A visit on ticket {v['work_item_id']} ({v['board']}).{status}\n\nOpen it on the desk: {link}\n\nThe ticket's words stay on the desk."
    else:
        from .board import UNKNOWN_ENTITY
        company = (row["company"] if row and row["entity_id"] != UNKNOWN_ENTITY else "") or ""
        subject = f"{v['work_item_id']} - " + (f"{company} - " if company else "") + summary
        body = (f"Ticket {v['work_item_id']} ({v['board']}): {summary}.{status}"
                + (f" Where: {v['place']}." if v["place"] else "") + f"\n\nOpen it on the desk: {link}")
    return subject[:255], body


def mark(conn, sync_id: int, status: str, *, at: datetime, event_id: str | None = None) -> bool:
    """What the script did with one write. A written event's id is kept on
    its visit or block, so the next change updates it in place."""
    if status not in ("SENT", "FAILED"):
        raise ValueError("status must be SENT or FAILED")
    s = conn.execute("SELECT * FROM calendar_sync WHERE sync_id = ? AND status = 'PENDING'", (sync_id,)).fetchone()
    if s is None:
        return False
    conn.execute("UPDATE calendar_sync SET status = ?, sent_at = ?, event_id = COALESCE(?, event_id) WHERE sync_id = ?",
                 (status, _stamp(at) if status == "SENT" else None, event_id, sync_id))
    if status == "SENT" and s["action"] == "UPSERT" and event_id:
        table, key = ("ticket_schedule", "schedule_id") if s["kind"] == "VISIT" else ("schedule_block", "block_id")
        conn.execute(f"UPDATE {table} SET outlook_event_id = ? WHERE {key} = ? AND LOWER(member) = LOWER(?)",
                     (event_id, s["ref_id"], s["member"]))
    conn.commit()
    return True


def import_busy(conn, items: list[dict], *, members_read: list[str], start: str, end: str, at: datetime) -> int:
    """Replace what the desk knows of these members' Outlook busy times in
    [start, end) with what the script read. Only the four Outlook states that
    mean someone is not free are kept; free time is not stored."""
    for m in members_read:
        conn.execute("DELETE FROM outlook_busy WHERE LOWER(member) = LOWER(?) AND starts_at < ? AND ends_at > ?",
                     (m, end, start))
    n = 0
    known = {m.lower(): m for m in members_read}
    for it in items:
        m = known.get(str(it.get("member", "")).lower())
        state = SHOW_AS.get(str(it.get("show_as", "")))
        s, e = str(it.get("start", ""))[:16].replace("T", " "), str(it.get("end", ""))[:16].replace("T", " ")
        if not m or not state or len(s) != 16 or len(e) != 16 or e <= s:
            continue
        conn.execute("INSERT INTO outlook_busy (member, starts_at, ends_at, show_as, pulled_at) VALUES (?,?,?,?,?)",
                     (m, s, e, state, _stamp(at)))
        n += 1
    conn.commit()
    return n


def busy(conn, people, lo: str, hi: str) -> list[dict]:
    """Outlook busy times for these people in [lo, hi)."""
    people = [p for p in people]
    if not people:
        return []
    q = ",".join("?" * len(people))
    return [dict(r) for r in conn.execute(
        f"SELECT member, starts_at, ends_at, show_as FROM outlook_busy WHERE LOWER(member) IN ({q})"
        " AND starts_at < ? AND ends_at > ? ORDER BY starts_at", (*[p.lower() for p in people], hi, lo))]
