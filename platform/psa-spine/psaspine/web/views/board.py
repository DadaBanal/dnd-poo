"""The Service Board — the list a fulfiller lives in, laid out as ConnectWise's.

Every ticket on the boards the user belongs to. Counters across the top (open,
breached, due within the hour, unassigned, mine) that are also one-click
filters; a filter bar; columns a technician expects — ticket, summary with the
last note under it, company, contact, board, status, priority, owner, age,
updated — and one chip per SLA clock (Respond, resolution Plan, reSolve), each
coloured by its own state. Worst SLA first unless a heading is clicked.

Everything is a plain GET query, so the back button, a bookmark and a page
refresh all work with no script. Colour carries SLA state and nothing else.

Bulk actions (status, owner, move board) go through the same engine seams a
single ticket uses — board.change_status, board.update_fields, board.move —
so a bulk change can never do what a one-ticket change is refused.
"""
from __future__ import annotations

import urllib.parse

from ... import board as engine
from .. import templates as t
from . import common

PRIORITY_ORDER = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}
OPEN_STATES = ("RESOLVED", "CLOSED", "CANCELLED")
SOURCES = ("EMAIL", "PHONE", "WALK_UP", "PORTAL", "API", "DESK", "IMPORT")
COLUMNS = (("id", "Ticket #"), ("summary", "Summary"), ("company", "Company"),
           ("contact", "Contact"), ("board", "Board"), ("status", "Status"),
           ("pri", "Pri"), ("owner", "Owner"), ("age", "Age"), ("updated", "Updated"),
           ("sla", "SLA"))
TILES = (("", "Open on my boards", ""), ("breached", "SLA breached", "bad"),
         ("due", "Due within 1 hour", "warn"), ("unassigned", "Unassigned", ""),
         ("mine", "Mine", ""))


def _is_mine(ctx, owner) -> bool:
    return bool(owner) and owner.lower() in {(ctx.user.id or "").lower(),
                                             (ctx.user.name or "").lower()}


def _load(ctx, boards):
    marks = ",".join("?" * len(boards))
    return ctx.conn.execute(
        "SELECT t.work_item_id, t.board_id, b.display_name AS board_name, t.priority,"
        "       t.state, t.owner, t.opened_at, t.updated_at,"
        "       COALESCE((SELECT ct.display_name FROM contact ct"
        "                  WHERE ct.contact_id = t.contact_id), t.requested_by) AS requested_by,"
        "       t.source_ref, t.intake_source, w.name AS summary, e.name AS entity,"
        "       e.entity_id, s.name AS status_name,"
        "       (SELECT f.display_name || ' › ' || c.display_name FROM catalogue_item i"
        "          JOIN service_component c ON c.component_id = i.component_id"
        "          JOIN service_family f ON f.family_id = c.family_id"
        "         WHERE i.catalogue_item_id = t.catalogue_item_id) AS klass,"
        "       (SELECT CASE e2.note_flag WHEN 'INTERNAL' THEN 'Internal: ' ELSE '' END"
        "               || e2.detail FROM ticket_event e2"
        "         WHERE e2.work_item_id = t.work_item_id AND e2.note_flag IS NOT NULL"
        "         ORDER BY e2.ticket_event_id DESC LIMIT 1) AS last_note"
        "  FROM ticket t"
        "  JOIN work_item w ON w.work_item_id = t.work_item_id"
        "  JOIN board b ON b.board_id = t.board_id"
        "  LEFT JOIN entity e ON e.entity_id = w.entity_id"
        "  LEFT JOIN board_status s ON s.board_status_id = t.board_status_id"
        f" WHERE t.board_id IN ({marks})", tuple(boards)).fetchall()


def index(ctx):
    boards = common.board_ids_for(ctx)
    if not boards:
        return _response(ctx, "<div class='card'><div class='empty'>You are not a "
                              "member of any board yet. An administrator adds you "
                              "on the Setup page.</div></div>")
    q = ctx.request.query
    f = {k: q.get(k, "") for k in ("board", "view", "owner", "pri", "src", "q",
                                   "tile", "sort", "dir", "msg")}
    f["view"] = f["view"] or "open"
    f["sort"] = f["sort"] or "sla"

    rows = []
    for r in _load(ctx, boards):
        states = common.clock_states(ctx.conn, r["work_item_id"], now=ctx.now)
        running = [s for s in states if s["state"] not in ("MET", "MISSED")]
        rows.append({"r": r, "states": states, "worst": common.worst_state(states),
                     "running_bad": any(s["state"] == "BAD" for s in running),
                     "due": any(s["state"] in ("OK", "WARN") and
                                s["target"] - s["used"] <= 60 for s in running),
                     "open": r["state"] not in OPEN_STATES})

    open_rows = [x for x in rows if x["open"]]
    counts = {"": len(open_rows),
              "breached": sum(x["running_bad"] for x in open_rows),
              "due": sum(x["due"] for x in open_rows),
              "unassigned": sum(not x["r"]["owner"] for x in open_rows),
              "mine": sum(_is_mine(ctx, x["r"]["owner"]) for x in open_rows)}

    shown = rows
    if f["view"] == "open":
        shown = [x for x in shown if x["open"]]
    elif f["view"] == "closed":
        shown = [x for x in shown if not x["open"]]
    if f["board"] in boards:
        shown = [x for x in shown if x["r"]["board_id"] == f["board"]]
    if f["owner"] == "me" or f["tile"] == "mine":
        shown = [x for x in shown if _is_mine(ctx, x["r"]["owner"])]
    elif f["owner"] == "none" or f["tile"] == "unassigned":
        shown = [x for x in shown if not x["r"]["owner"]]
    if f["tile"] == "breached":
        shown = [x for x in shown if x["running_bad"]]
    elif f["tile"] == "due":
        shown = [x for x in shown if x["due"]]
    if f["pri"] in PRIORITY_ORDER:
        shown = [x for x in shown if x["r"]["priority"] == f["pri"]]
    if f["src"] in SOURCES:
        shown = [x for x in shown if x["r"]["intake_source"] == f["src"]]
    if f["q"].strip():
        needle = f["q"].strip().lower()
        shown = [x for x in shown if any(needle in (v or "").lower() for v in (
            x["r"]["work_item_id"], x["r"]["summary"], x["r"]["requested_by"]))]

    shown = _sort(shown, f["sort"], f["dir"])

    # A list of a restricted board's tickets is a read of restricted data, so it
    # is audited too — once per board with the count (§6.1 requirement 4).
    seen: dict[str, int] = {}
    for x in shown:
        seen[x["r"]["board_id"]] = seen.get(x["r"]["board_id"], 0) + 1
    for bid, count in sorted(seen.items()):
        common.audit_restricted_read(ctx, bid, detail=f"listed {count} ticket(s) on the board view")

    body = ""
    if f["msg"]:
        body += f"<div class='banner ok'>{t.esc(f['msg'])}</div>"
    body += _tiles(f, counts) + _filters(ctx, boards, f)
    if not shown:
        body += "<div class='card'><div class='empty'>No tickets match.</div></div>"
        return _response(ctx, body)
    body += _table(ctx, boards, shown, f)
    return _response(ctx, body)


def _sort(rows, key, direction):
    fields = {
        "id": lambda x: x["r"]["work_item_id"],
        "summary": lambda x: (x["r"]["summary"] or "").lower(),
        "company": lambda x: (x["r"]["entity"] or "").lower(),
        "contact": lambda x: (x["r"]["requested_by"] or "").lower(),
        "board": lambda x: x["r"]["board_name"],
        "status": lambda x: x["r"]["status_name"] or x["r"]["state"],
        "pri": lambda x: PRIORITY_ORDER.get(x["r"]["priority"], 9),
        "owner": lambda x: (x["r"]["owner"] or "~").lower(),
        "age": lambda x: x["r"]["opened_at"] or "",
        "updated": lambda x: x["r"]["updated_at"] or x["r"]["opened_at"] or "",
        "sla": lambda x: (-common.WORST.get(max((s["state"] for s in x["states"]),
                                               key=lambda v: common.WORST[v], default="MET"), 0),
                          PRIORITY_ORDER.get(x["r"]["priority"], 9), x["r"]["opened_at"] or ""),
    }
    fn = fields.get(key, fields["sla"])
    # Newest first is the natural reading of "age" and "updated".
    reverse = (direction == "desc") != (key in ("age",))
    if key == "updated":
        reverse = direction != "asc"
    return sorted(rows, key=fn, reverse=reverse)


def _link(f, **over) -> str:
    params = {k: v for k, v in f.items() if v and k != "msg"}
    params.update({k: v for k, v in over.items()})
    params = {k: v for k, v in params.items() if v}
    return "/?" + urllib.parse.urlencode(params) if params else "/"


def _tiles(f, counts) -> str:
    out = []
    for key, label, cls in TILES:
        on = " on" if f["tile"] == key and (key or not any(
            f[k] for k in ("tile", "owner", "pri", "src", "q"))) else ""
        out.append(f"<a class='tile {cls}{on}' href='{t.esc(_link(f, tile=key, view='open'))}'>"
                   f"<div class=n>{counts[key]}</div><div class=l>{t.esc(label)}</div></a>")
    return "<div class=tiles>" + "".join(out) + "</div>"


def _options(pairs, selected) -> str:
    return "".join(f"<option value='{t.esc(v)}'{' selected' if v == selected else ''}>"
                   f"{t.esc(label)}</option>" for v, label in pairs)


def _filters(ctx, boards, f) -> str:
    board_rows = ctx.conn.execute(
        "SELECT board_id, display_name FROM board WHERE board_id IN (%s)"
        " ORDER BY display_name" % ",".join("?" * len(boards)), tuple(boards)).fetchall()
    board_opts = _options([("", "All my boards")] +
                          [(b["board_id"], b["display_name"]) for b in board_rows], f["board"])
    return (
        "<div class=card><form class=toolbar method=get action='/'>"
        f"<input type=hidden name=sort value='{t.esc(f['sort'])}'>"
        f"<div><label>Board</label><select name=board>{board_opts}</select></div>"
        "<div><label>Status</label><select name=view>"
        + _options([("open", "Open"), ("closed", "Closed"), ("all", "All")], f["view"]) +
        "</select></div><div><label>Owner</label><select name=owner>"
        + _options([("", "Anyone"), ("me", "Me"), ("none", "Unassigned")], f["owner"]) +
        "</select></div><div><label>Priority</label><select name=pri>"
        + _options([("", "Any")] + [(p, p) for p in PRIORITY_ORDER], f["pri"]) +
        "</select></div><div><label>Source</label><select name=src>"
        + _options([("", "Any")] + [(s, s.replace("_", "-").title()) for s in SOURCES], f["src"]) +
        "</select></div>"
        f"<div style='flex:1'><label>Search</label><input name=q value='{t.esc(f['q'])}' "
        "placeholder='ticket #, summary, contact'></div>"
        "<div style='min-width:0'><button type=submit>Filter</button></div></form></div>")


def _table(ctx, boards, shown, f) -> str:
    head = []
    for key, label in COLUMNS:
        on = f["sort"] == key
        nxt = "asc" if on and f["dir"] != "asc" else "desc" if on else ""
        arrow = (" ▲" if f["dir"] == "asc" else " ▼") if on else ""
        head.append(f"<th class='sort{' on' if on else ''}'>"
                    f"<a href='{t.esc(_link(f, sort=key, dir=nxt))}'>{t.esc(label)}{arrow}</a></th>")

    lines = []
    for x in shown:
        r = x["r"]
        wid = r["work_item_id"]
        cls = {"BAD": "s-bad", "WARN": "s-warn", "OK": "s-ok"}.get(x["worst"], "")
        sla = t.sla_chips(x["states"]) or (
            f"<span class=pill>{t.esc(common.no_clock_reason(ctx.conn, r['board_id'], r['source_ref']))}</span>")
        last = r["last_note"] or ""
        last = (last[:90] + "…") if len(last) > 90 else last
        lines.append(
            f"<tr class='{cls}'>"
            f"<td><input type=checkbox name=ids value='{t.esc(wid)}' form=bulk style='width:auto'></td>"
            f"<td><a href='/ticket/{t.esc(wid)}'>{t.esc(wid)}</a></td>"
            f"<td class=sum><a href='/ticket/{t.esc(wid)}' style='color:inherit'><b>{t.esc(r['summary'])}</b></a>"
            + (f"<div class=last><span class=pill>{t.esc(r['klass'])}</span></div>" if r["klass"] else "")
            + (f"<div class=last>{t.esc(last)}</div>" if last else "") + "</td>"
            f"<td title='{t.esc(r['entity'] or '')}'>{t.esc(r['entity_id'] or '—')}</td>"
            f"<td class=muted>{t.esc(r['requested_by'] or '—')}</td>"
            f"<td>{t.esc(r['board_name'])}</td>"
            f"<td>{t.esc(r['status_name'] or r['state'].replace('_', ' ').title())}</td>"
            f"<td>{t.badge(r['priority'])}</td>"
            f"<td>{t.esc(r['owner'] or '—')}</td>"
            f"<td>{t.esc(common.human_age(r['opened_at'], now=ctx.now))}</td>"
            f"<td class=muted>{t.esc(common.human_age(r['updated_at'] or r['opened_at'], now=ctx.now))}</td>"
            f"<td>{sla}</td></tr>")

    return (
        "<div class=card style='padding:10px'>" + _bulk_bar(ctx, boards, f) +
        "<div class=tablewrap><table class=grid><thead><tr>"
        "<th><input type=checkbox style='width:auto' "
        "onclick=\"document.querySelectorAll('input[name=ids]').forEach(c=>c.checked=this.checked)\"></th>"
        + "".join(head) + "</tr></thead><tbody>" + "".join(lines) + "</tbody></table></div>"
        f"<p class=sub style='margin:10px 0 0'>{len(shown)} ticket(s). "
        "R · P · S = Respond · Resolution plan · Resolve. Green on track or met, amber "
        "inside 20% of target, red breached, grey paused.</p></div>")


def _bulk_bar(ctx, boards, f) -> str:
    marks = ",".join("?" * len(boards))
    names = [r["name"] for r in ctx.conn.execute(
        f"SELECT DISTINCT name FROM board_status WHERE board_id IN ({marks})"
        " AND inactive = 0 ORDER BY sort_order, name", tuple(boards))]
    seen, status_opts = set(), ["<option value=''>(status)</option>"]
    for n in names:
        if n not in seen:
            seen.add(n)
            status_opts.append(f"<option>{t.esc(n)}</option>")
    work_boards = ctx.conn.execute(
        "SELECT b.board_id, b.display_name FROM board b JOIN board_member m"
        " ON m.board_id = b.board_id WHERE m.member = ? AND m.access IN ('WORK','ADMIN')"
        " AND COALESCE(b.inactive, 0) = 0 ORDER BY b.display_name", (ctx.user.id,)).fetchall()
    move_opts = "<option value=''>(board)</option>" + "".join(
        f"<option value='{t.esc(b['board_id'])}'>{t.esc(b['display_name'])}</option>"
        for b in work_boards)
    back = _link(f)
    return (
        "<form id=bulk method=post action='/bulk' class=bulk>"
        f"<input type=hidden name=back value='{t.esc(back)}'>"
        "<b>With ticked:</b> Status <select name=status>" + "".join(status_opts) + "</select>"
        " Assign <input name=owner placeholder='owner' style='width:130px;padding:4px 8px'>"
        f" Move to <select name=to_board>{move_opts}</select>"
        " <button type=submit>Apply</button></form>")


def bulk(ctx):
    """Apply one change to many tickets, each through the engine, each checked
    for access on its own board. What cannot be applied is counted and said."""
    from .. import redirect
    form = ctx.request.form()
    ids = ctx.request.form_list("ids")
    status_name = form.get("status", "").strip()
    owner = form.get("owner", "").strip()
    to_board = form.get("to_board", "").strip()
    back = form.get("back", "/")
    if not back.startswith("/") or back.startswith("//"):
        back = "/"
    done = skipped = 0
    for wid in ids:
        row = ctx.conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?",
                               (wid,)).fetchone()
        if row is None or not common.may_access_board(ctx, row["board_id"], need="WORK"):
            skipped += 1
            continue
        try:
            if to_board:
                if not common.may_access_board(ctx, to_board, need="WORK"):
                    raise PermissionError
                if to_board != row["board_id"]:
                    engine.move(ctx.conn, wid, to_board, at=ctx.now, actor=ctx.user.id,
                                reason="bulk move from the board")
            if owner:
                engine.update_fields(ctx.conn, wid, at=ctx.now, actor=ctx.user.id, owner=owner)
            if status_name:
                board_id = ctx.conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?",
                                            (wid,)).fetchone()["board_id"]
                st = ctx.conn.execute(
                    "SELECT board_status_id FROM board_status WHERE board_id = ? AND name = ?"
                    " AND inactive = 0", (board_id, status_name)).fetchone()
                if st is None:
                    raise LookupError
                engine.change_status(ctx.conn, wid, st["board_status_id"], at=ctx.now,
                                     actor=ctx.user.id)
            ctx.conn.commit()
            done += 1
        except Exception:                                  # noqa: BLE001
            ctx.conn.rollback()
            skipped += 1
    msg = f"Updated {done} ticket(s)" + (f"; {skipped} could not be changed" if skipped else "")
    sep = "&" if "?" in back else "?"
    return redirect(back + sep + urllib.parse.urlencode({"msg": msg}))


def _response(ctx, body: str):
    from .. import Response
    heading = ("<h1>Service Board</h1><p class='sub'>Every ticket on your boards, worst "
               "SLA first. Colour is the clock, not decoration.</p>")
    return Response(body=t.page("Service Board", heading + body, user=ctx.user, active="board"))
