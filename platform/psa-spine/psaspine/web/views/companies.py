"""Companies and contacts, as ConnectWise lays them out.

Companies lists every company the desk serves. A company page shows its
contacts and its open tickets, and a contact page shows one person and the
tickets that name them. A fulfiller starts from "who is this?" as often as from
"what is broken?", and in ConnectWise both are one click from anywhere.

Two fences:

  * **Fulfillers only.** Contacts are staff details. A requester on the portal
    (a user with no board) gets a 404 here, the same answer as a page that does
    not exist.
  * **Restricted boards stay on their boards.** The ticket lists here show only
    unrestricted boards the user belongs to. A restricted ticket is read on its
    own board, where the read is audited (§6.1 requirement 4); a company page is
    not a side door round that. The page says how many were left out.
"""
from __future__ import annotations

import urllib.parse

from ... import contacts as directory
from .. import templates as t
from . import common

CLOSED = ("RESOLVED", "CLOSED", "CANCELLED")


def _fulfiller(ctx) -> list[str]:
    from .. import HttpError
    boards = sorted(common.board_ids_for(ctx))
    if not boards:
        raise HttpError("404 Not Found", "No such page.")
    return boards


def _open_boards(ctx, boards: list[str]) -> tuple[list[str], int]:
    """Split the user's boards into those listed here and the restricted count."""
    marks = ",".join("?" * len(boards))
    rows = ctx.conn.execute(
        f"SELECT board_id, restricted FROM board WHERE board_id IN ({marks})", boards).fetchall()
    shown = [r["board_id"] for r in rows if not r["restricted"]]
    return shown, len(rows) - len(shown)


def _tickets(ctx, boards: list[str], *, where: str, params: list) -> tuple[str, int]:
    """Open tickets on the listed boards, plus how many on restricted boards were
    left out. Returns the table HTML and the left-out count."""
    shown, _ = _open_boards(ctx, boards)
    marks = ",".join("?" * len(boards))
    hidden = ctx.conn.execute(
        f"SELECT COUNT(*) c FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
        f" JOIN board b ON b.board_id = t.board_id"
        f" WHERE t.board_id IN ({marks}) AND b.restricted = 1"
        f" AND t.state NOT IN ('RESOLVED','CLOSED','CANCELLED') AND {where}",
        boards + params).fetchone()["c"]
    if not shown:
        return "<div class=muted>No tickets on the boards you can see.</div>", hidden
    marks = ",".join("?" * len(shown))
    rows = ctx.conn.execute(
        "SELECT t.work_item_id, w.name AS summary, b.display_name AS board_name,"
        "       s.name AS status_name, t.priority, t.owner, t.opened_at, t.requested_by"
        "  FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
        "  JOIN board b ON b.board_id = t.board_id"
        "  LEFT JOIN board_status s ON s.board_status_id = t.board_status_id"
        f" WHERE t.board_id IN ({marks}) AND t.state NOT IN ('RESOLVED','CLOSED','CANCELLED')"
        f"   AND {where} ORDER BY t.priority, t.opened_at LIMIT 200",
        shown + params).fetchall()
    if not rows:
        return "<div class=muted>No open tickets.</div>", hidden
    body = "".join(
        f"<tr><td><a href='/ticket/{t.esc(r['work_item_id'])}'>{t.esc(r['work_item_id'])}</a></td>"
        f"<td>{t.esc(r['summary'])}</td><td>{t.esc(r['board_name'])}</td>"
        f"<td>{t.esc(r['status_name'] or '—')}</td><td>{t.badge(r['priority'])}</td>"
        f"<td>{t.esc(r['owner'] or '—')}</td>"
        f"<td>{t.esc(common.human_age(r['opened_at'], now=ctx.now))}</td></tr>" for r in rows)
    return ("<div class=tablewrap><table><thead><tr><th>Ticket #</th><th>Summary</th>"
            "<th>Board</th><th>Status</th><th>Pri</th><th>Owner</th><th>Age</th></tr></thead>"
            f"<tbody>{body}</tbody></table></div>"), hidden


def _hidden_note(hidden: int) -> str:
    if not hidden:
        return ""
    return (f"<p class=why>{hidden} more on restricted boards. Those are read on "
            "their own board, where each read is recorded.</p>")


def _contact_table(rows) -> str:
    if not rows:
        return "<div class=muted>No contacts. Import them from AD: psaspine import-contacts.</div>"
    body = "".join(
        f"<tr><td><a href='/contact/{t.esc(c['contact_id'])}'>{t.esc(c['display_name'])}</a>"
        + (" <span class=chip>inactive</span>" if c["inactive"] else "") + "</td>"
        f"<td>{t.esc(c['entity_id'])}</td><td>{t.esc(c['department'] or '—')}</td>"
        f"<td>{t.esc(c['title'] or '—')}</td><td>{t.esc(c['email'] or '—')}</td>"
        f"<td>{t.esc(c['phone'] or '—')}</td></tr>" for c in rows)
    return ("<div class=tablewrap><table><thead><tr><th>Name</th><th>Company</th>"
            "<th>Department</th><th>Title</th><th>Email</th><th>Phone</th></tr></thead>"
            f"<tbody>{body}</tbody></table></div>")


def index(ctx):
    """Every company, with its contact count and its open tickets on the boards
    this user can see (restricted boards are counted on their own boards)."""
    from .. import Response
    boards = _fulfiller(ctx)
    shown, _ = _open_boards(ctx, boards)
    marks = ",".join("?" * len(shown)) or "''"
    rows = ctx.conn.execute(
        "SELECT e.entity_id, e.name, e.is_covered,"
        " (SELECT COUNT(*) FROM contact c WHERE c.entity_id = e.entity_id"
        "   AND c.inactive = 0) AS contacts,"
        " (SELECT COUNT(*) FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
        f"   WHERE w.entity_id = e.entity_id AND t.board_id IN ({marks})"
        "   AND t.state NOT IN ('RESOLVED','CLOSED','CANCELLED')) AS open_tickets"
        " FROM entity e ORDER BY e.entity_id = 'UNCLASSIFIED', e.name", shown).fetchall()
    body_rows = "".join(
        f"<tr><td><a href='/company/{t.esc(r['entity_id'])}'>{t.esc(r['entity_id'])}</a></td>"
        f"<td>{t.esc(r['name'])}</td>"
        f"<td>{'Covered' if r['is_covered'] else '<span class=muted>Not covered</span>'}</td>"
        f"<td>{r['contacts']}</td><td>{r['open_tickets']}</td></tr>" for r in rows)
    body = (
        "<h1>Companies</h1><p class=sub>Who the desk serves. Covered means an executed "
        "instrument covers the company's work; the catch-all holds tickets whose company "
        "intake could not tell.</p>"
        "<div class=card><div class=tablewrap><table><thead><tr><th>Code</th><th>Company</th>"
        "<th>Agreement</th><th>Contacts</th><th>Open tickets</th></tr></thead>"
        f"<tbody>{body_rows}</tbody></table></div></div>"
        "<p><a href='/contacts'>Search all contacts →</a></p>")
    return Response(body=t.page("Companies", body, user=ctx.user, active="companies"))


def detail(ctx, entity_id: str):
    from .. import HttpError, Response
    boards = _fulfiller(ctx)
    company = ctx.conn.execute("SELECT * FROM entity WHERE entity_id = ?", (entity_id,)).fetchone()
    if company is None:
        raise HttpError("404 Not Found", "No such company.")
    q = ctx.request.query.get("q", "").strip()
    people = directory.search(ctx.conn, q, entity_id=entity_id, include_inactive=True)
    table, hidden = _tickets(ctx, boards, where="w.entity_id = ?", params=[entity_id])
    new_link = "/ticket/new?" + urllib.parse.urlencode({"entity_id": entity_id})
    body = (
        f"<h1>{t.esc(company['name'])} <span class=muted>· {t.esc(company['entity_id'])}</span></h1>"
        f"<p class=sub>{'Covered by an executed instrument.' if company['is_covered'] else 'Not covered by an executed instrument.'}"
        f" <a href='{t.esc(new_link)}'>+ New ticket for this company</a></p>"
        "<div class=card><h3>Open tickets</h3>" + table + _hidden_note(hidden) + "</div>"
        "<div class=card><h3>Contacts</h3>"
        f"<form method=get class=row style='margin-bottom:10px'><div><input name=q value='{t.esc(q)}' "
        "placeholder='name, email or department'></div><div style='flex:0 0 auto'>"
        "<button type=submit>Search</button></div></form>" + _contact_table(people) + "</div>")
    return Response(body=t.page(company["name"], body, user=ctx.user, active="companies"))


def contacts_index(ctx):
    from .. import Response
    _fulfiller(ctx)
    q = ctx.request.query.get("q", "").strip()
    people = directory.search(ctx.conn, q, include_inactive=bool(ctx.request.query.get("all")))
    body = (
        "<h1>Contacts</h1><p class=sub>The people who ask, from Active Directory. A new "
        "ticket from one of these addresses is filed under the person and their company "
        "automatically.</p><div class=card>"
        f"<form method=get class=row style='margin-bottom:10px'><div><input name=q value='{t.esc(q)}' "
        "placeholder='name, email or department'></div>"
        "<div style='flex:0 0 auto'><label style='display:inline'><input type=checkbox name=all value=1"
        + (" checked" if ctx.request.query.get("all") else "") + "> include inactive</label></div>"
        "<div style='flex:0 0 auto'><button type=submit>Search</button></div></form>"
        + _contact_table(people) + "</div>")
    return Response(body=t.page("Contacts", body, user=ctx.user, active="companies"))


def contact_detail(ctx, contact_id: str):
    from .. import HttpError, Response
    boards = _fulfiller(ctx)
    c = ctx.conn.execute(
        "SELECT c.*, e.name AS entity_name FROM contact c JOIN entity e"
        " ON e.entity_id = c.entity_id WHERE c.contact_id = ?", (contact_id,)).fetchone()
    if c is None:
        raise HttpError("404 Not Found", "No such contact.")
    table, hidden = _tickets(ctx, boards, where="t.contact_id = ?", params=[contact_id])
    new_link = "/ticket/new?" + urllib.parse.urlencode(
        {"entity_id": c["entity_id"], "requested_by": c["email"] or c["display_name"]})
    kv = "".join(
        f"<dt>{label}</dt><dd>{t.esc(c[key] or '—')}</dd>" for label, key in (
            ("Department", "department"), ("Title", "title"), ("Office", "office"),
            ("Email", "email"), ("Phone", "phone"), ("Sign-in", "upn"),
            ("Source", "source"), ("Last synced", "last_synced_at")))
    status = "<span class=chip>inactive: disabled in AD</span>" if c["inactive"] else ""
    body = (
        f"<h1>{t.esc(c['display_name'])} {status}</h1>"
        f"<p class=sub><a href='/company/{t.esc(c['entity_id'])}'>{t.esc(c['entity_name'])}</a>"
        + ("" if c["inactive"] else f" · <a href='{t.esc(new_link)}'>+ New ticket for this contact</a>")
        + "</p>"
        f"<div class=rail><div><div class=card><h3>Open tickets</h3>{table}{_hidden_note(hidden)}</div></div>"
        f"<div><div class=card><h3>Contact</h3><dl class=kv>{kv}</dl></div></div></div>")
    return Response(body=t.page(c["display_name"], body, user=ctx.user, active="companies"))
