"""The Service Board — the list a fulfiller lives in, laid out as Dada PSA's.

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
from ... import itil
from .. import templates as t
from . import common

PRIORITY_ORDER = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}
OPEN_STATES = ("RESOLVED", "CLOSED", "CANCELLED")
SOURCES = ("EMAIL", "PHONE", "WALK_UP", "PORTAL", "API", "DESK", "IMPORT")
COLUMNS = (("id", "Ticket #"), ("summary", "Summary"), ("company", "Company"),
           ("contact", "Contact"), ("board", "Board"), ("status", "Status"),
           ("pri", "Pri"), ("owner", "Owner"), ("age", "Age"), ("updated", "Updated"),
           ("sla", "SLA"))
TILES = (("", "Open on my boards", "", "inbox"), ("breached", "SLA breached", "bad", "alert"),
         ("due", "Due within 1 hour", "warn", "clock"), ("unassigned", "Unassigned", "", "users"),
         ("mine", "Mine", "", "my"))


def _is_mine(ctx, owner) -> bool:
    return bool(owner) and owner.lower() in {(ctx.user.id or "").lower(),
                                             (ctx.user.name or "").lower()}


# On a phone (gap 5) the row keeps the summary, the priority and the clocks; the
# rest folds into a line under the summary, so the list reads as cards.
SM_HIDE = {"id", "company", "contact", "board", "status", "owner", "age", "updated"}
PAGE = 100
CLOSED_STATES_SQL = "('RESOLVED','CLOSED','CANCELLED')"
# Sort keys SQL can order by; "sla" needs the clocks and is sorted in Python.
ORDER_SQL = {
    "id": "t.work_item_id", "summary": "w.name COLLATE NOCASE",
    "company": "e.name COLLATE NOCASE", "contact": "requested_by COLLATE NOCASE",
    "board": "b.display_name COLLATE NOCASE", "status": "COALESCE(s.name, t.state)",
    "pri": "t.priority", "owner": "COALESCE(t.owner, '~') COLLATE NOCASE",
    "age": "t.opened_at", "updated": "COALESCE(t.updated_at, t.opened_at)",
}
SELECT = (
    "SELECT t.work_item_id, t.board_id, b.display_name AS board_name, t.priority,"
    "       t.state, t.owner, t.opened_at, t.updated_at,"
    "       COALESCE((SELECT ct.display_name FROM contact ct"
    "                  WHERE ct.contact_id = t.contact_id), t.requested_by) AS requested_by,"
    "       t.source_ref, t.intake_source, w.name AS summary, e.name AS entity,"
    "       e.entity_id, s.name AS status_name,"
    "       t.record_type, t.customer_updated, t.parent_id,"
    "       (SELECT COUNT(*) FROM ticket ch WHERE ch.parent_id = t.work_item_id) AS children,"
    "       (SELECT c.display_name || ' › ' || a.display_name FROM catalogue_item i"
    "          JOIN service_component c ON c.component_id = i.component_id"
    "          JOIN service_action a ON a.action_id = i.action_id"
    "         WHERE i.catalogue_item_id = t.catalogue_item_id) AS klass,"
    "       (SELECT CASE e2.note_flag WHEN 'INTERNAL' THEN 'Internal: ' ELSE '' END"
    "               || e2.detail FROM ticket_event e2"
    "         WHERE e2.work_item_id = t.work_item_id AND e2.note_flag IS NOT NULL"
    "         ORDER BY e2.ticket_event_id DESC LIMIT 1) AS last_note,"
    # The preview is 90 escaped characters of the last note. A note written in
    # the desk's editor, or arrived as an email's HTML (064), would spend all 90
    # of them on its own opening tags, so the row needs to know which it is.
    "       (SELECT e2.body_format FROM ticket_event e2"
    "         WHERE e2.work_item_id = t.work_item_id AND e2.note_flag IS NOT NULL"
    "         ORDER BY e2.ticket_event_id DESC LIMIT 1) AS last_note_format")
FROM = (
    "  FROM ticket t"
    "  JOIN work_item w ON w.work_item_id = t.work_item_id"
    "  JOIN board b ON b.board_id = t.board_id"
    "  LEFT JOIN entity e ON e.entity_id = w.entity_id"
    "  LEFT JOIN board_status s ON s.board_status_id = t.board_status_id")


def _like(needle: str) -> str:
    """A contains-match with every wildcard escaped: SQLite's two, and '[',
    which SQL Server's LIKE reads as a character class."""
    return "%" + (needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                  .replace("[", "\\[")) + "%"


def _where(ctx, boards, f, tile_ids: dict[str, set]) -> tuple[str, list]:
    """The filter bar as SQL. Only what SQL can decide; the two clock tiles
    (breached, due) arrive as the ids the tile counts found."""
    where = ["t.board_id IN (%s)" % ",".join("?" * len(boards))]
    params: list = list(boards)
    if f["view"] == "open":
        where.append(f"t.state NOT IN {CLOSED_STATES_SQL}")
    elif f["view"] == "closed":
        where.append(f"t.state IN {CLOSED_STATES_SQL}")
    if f["board"] in boards:
        where.append("t.board_id = ?")
        params.append(f["board"])
    if f["owner"] == "me" or f["tile"] == "mine":
        where.append("LOWER(t.owner) IN (?, ?)")
        params += [(ctx.user.id or "").lower(), (ctx.user.name or "").lower()]
    elif f["owner"] == "none" or f["tile"] == "unassigned":
        where.append("(t.owner IS NULL OR t.owner = '')")
    if f["tile"] in ("breached", "due"):
        ids = sorted(tile_ids[f["tile"]])
        where.append("t.work_item_id IN (%s)" % (",".join("?" * len(ids)) or "NULL"))
        params += ids
    if f["pri"] in PRIORITY_ORDER:
        where.append("t.priority = ?")
        params.append(f["pri"])
    if f["type"] in itil.RECORD_TYPES:
        where.append("t.record_type = ?")
        params.append(f["type"])
    elif f["type"] == "none":
        where.append("t.record_type IS NULL")
    if f["src"] in SOURCES:
        where.append("t.intake_source = ?")
        params.append(f["src"])
    needle = f["q"].strip()
    if needle:
        like = _like(needle.lower())
        where.append("(LOWER(t.work_item_id) LIKE ? ESCAPE '\\' OR LOWER(w.name) LIKE ? ESCAPE '\\'"
                     " OR LOWER(t.requested_by) LIKE ? ESCAPE '\\' OR EXISTS (SELECT 1 FROM contact ct"
                     " WHERE ct.contact_id = t.contact_id AND LOWER(ct.display_name) LIKE ? ESCAPE '\\'))")
        params += [like, like, like, like]
    return " WHERE " + " AND ".join(where), params


def _tile_counts(ctx, boards) -> tuple[dict, dict[str, set]]:
    """The five counters over every open ticket on the user's boards, and the
    ids behind the two that need the clocks. One query for the tickets, three
    for their clocks, however many there are."""
    marks = ",".join("?" * len(boards))
    rows = ctx.conn.execute(
        f"SELECT work_item_id, owner FROM ticket WHERE board_id IN ({marks})"
        f" AND state NOT IN {CLOSED_STATES_SQL}", tuple(boards)).fetchall()
    states = common.clock_states_many(ctx.conn, [r["work_item_id"] for r in rows], now=ctx.now)
    breached, due = set(), set()
    for r in rows:
        running = [s for s in states[r["work_item_id"]] if s["state"] not in ("MET", "MISSED")]
        if any(s["state"] == "BAD" for s in running):
            breached.add(r["work_item_id"])
        if any(s["state"] in ("OK", "WARN") and s["target"] - s["used"] <= 60 for s in running):
            due.add(r["work_item_id"])
    counts = {"": len(rows), "breached": len(breached), "due": len(due),
              "unassigned": sum(not r["owner"] for r in rows),
              "mine": sum(_is_mine(ctx, r["owner"]) for r in rows)}
    return counts, {"breached": breached, "due": due}


def _page_of(ctx, boards, f, tile_ids) -> tuple[list, int]:
    """The rows of one page, sorted, with the clocks of those rows only, and the
    total that matched. Two steps on purpose: the ids of the page first, sorted
    and limited on plain columns, then the full row (last note, contact,
    classification) for those ids alone. SQL sorts every column but SLA; an SLA
    sort of open tickets sorts on the clocks of what matched (hundreds), while
    an SLA sort of closed history reads as newest first."""
    where, params = _where(ctx, boards, f, tile_ids)
    page = max(int(f["page"]), 1) if f["page"].isdigit() else 1
    offset = (page - 1) * PAGE
    total = ctx.conn.execute("SELECT COUNT(*)" + FROM + where, params).fetchone()[0]
    key, direction = f["sort"], f["dir"]
    if key == "sla" and f["view"] == "open":
        ids = [r[0] for r in ctx.conn.execute(
            "SELECT t.work_item_id, t.priority, t.opened_at" + FROM + where, params)]
        states = common.clock_states_many(ctx.conn, ids, now=ctx.now)
        meta = {r[0]: r for r in ctx.conn.execute(
            "SELECT t.work_item_id, t.priority, t.opened_at" + FROM + where, params)}
        ranked = sorted(ids, key=lambda wid: (
            -common.WORST.get(max((s["state"] for s in states[wid]),
                                  key=lambda v: common.WORST[v], default="MET"), 0),
            PRIORITY_ORDER.get(meta[wid][1], 9), meta[wid][2] or ""),
            reverse=(direction == "desc"))
        page_ids = ranked[offset:offset + PAGE]
    else:
        if key not in ORDER_SQL:
            key, direction = "updated", direction or "desc"
        desc = (direction == "desc") != (key == "age") if key != "updated" else direction != "asc"
        tiebreak = "" if ORDER_SQL[key] == "t.work_item_id" else ", t.work_item_id"
        order = (f" ORDER BY {ORDER_SQL[key]} {'DESC' if desc else 'ASC'}{tiebreak}"
                 " LIMIT ? OFFSET ?")
        page_ids = [r[0] for r in ctx.conn.execute(
            "SELECT t.work_item_id, COALESCE((SELECT ct.display_name FROM contact ct"
            " WHERE ct.contact_id = t.contact_id), t.requested_by) AS requested_by"
            + FROM + where + order, params + [PAGE, offset])]
        states = common.clock_states_many(ctx.conn, page_ids, now=ctx.now)
    if not page_ids:
        return [], total
    by_id = {r["work_item_id"]: r for r in ctx.conn.execute(
        SELECT + FROM + " WHERE t.work_item_id IN (%s)" % ",".join("?" * len(page_ids)),
        page_ids)}
    return [_item(by_id[wid], states[wid]) for wid in page_ids], total


def _item(r, states) -> dict:
    running = [s for s in states if s["state"] not in ("MET", "MISSED")]
    return {"r": r, "states": states, "worst": common.worst_state(states),
            "running_bad": any(s["state"] == "BAD" for s in running),
            "due": any(s["state"] in ("OK", "WARN") and s["target"] - s["used"] <= 60
                       for s in running),
            "open": r["state"] not in OPEN_STATES}


def index(ctx):
    boards = common.board_ids_for(ctx)
    if not boards:
        # On no board, this person is a requester: their page is their requests.
        # (A fulfiller who is not yet on a board is added on Setup by an admin.)
        from .. import redirect
        return redirect("/my")
    q = ctx.request.query
    f = {k: q.get(k, "") for k in ("board", "view", "owner", "pri", "src", "type", "q",
                                   "tile", "sort", "dir", "msg", "page")}
    f["view"] = f["view"] or "open"
    f["sort"] = f["sort"] or "sla"

    counts, tile_ids = _tile_counts(ctx, boards)
    shown, total = _page_of(ctx, boards, f, tile_ids)

    # A list of a restricted board's tickets is a read of restricted data, so it
    # is audited too — once per board with the count (§6.1 requirement 4).
    seen: dict[str, int] = {}
    for x in shown:
        seen[x["r"]["board_id"]] = seen.get(x["r"]["board_id"], 0) + 1
    for bid, count in sorted(seen.items()):
        common.audit_restricted_read(ctx, bid, detail=f"listed {count} ticket(s) on the board view")

    body = ""
    if f["msg"]:
        body += f"<div class='banner ok toast'>{t.icon('check')} {t.esc(f['msg'])}</div>"
    body += _views(ctx, f) + _tiles(f, counts) + _filters(ctx, boards, f)
    if not shown:
        body += "<div class='card'><div class='empty'>No tickets match.</div></div>"
        return _response(ctx, body)
    body += _table(ctx, boards, shown, f, total)
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
    params = {k: v for k, v in f.items() if v and k not in ("msg", "page")}
    params.update({k: v for k, v in over.items()})
    params = {k: v for k, v in params.items() if v}
    return "/?" + urllib.parse.urlencode(params) if params else "/"


def _views(ctx, f) -> str:
    """Dada PSA's My views: the person's own named filters, as chips above
    the counters, with the current filter savable in one field."""
    from ... import canned
    # The query as typed or clicked, not the board's defaults, so a view saved
    # from this URL matches this URL.
    current = canned.clean_query(urllib.parse.urlencode(ctx.request.query))
    chips = []
    for v in canned.views_for(ctx.conn, ctx.user.id):
        on = " on" if v["query"] == current else ""
        chips.append(f"<span class=viewchip><a class='stab{on}' href='/?{t.esc(v['query'])}'>{t.esc(v['name'])}</a>"
                     f"<form method=post action='/views/delete' class=inline><input type=hidden name=view_id "
                     f"value='{v['view_id']}'><button class='iconbtn x' type=submit title='Forget this view' "
                     "aria-label='Forget this view'>" + t.icon("x") + "</button></form></span>")
    save = ("<form method=post action='/views/save' class=inline style='margin-left:auto'>"
            f"<input type=hidden name=query value='{t.esc(current)}'>"
            "<input name=name placeholder='Save this view as…' maxlength=60 required "
            "style='width:180px;padding:4px 8px;display:inline-block'> "
            "<button class='ghost small' type=submit>Save</button></form>") if current else ""
    if not chips and not save:
        return ""
    return "<div class=views>" + "".join(chips) + save + "</div>"


def view_save(ctx):
    from .. import redirect
    from ... import canned
    f = ctx.request.form()
    try:
        canned.save_view(ctx.conn, member=ctx.user.id, name=f.get("name", ""),
                         query=f.get("query", ""), at=ctx.now)
        ctx.conn.commit()
    except ValueError as exc:
        return redirect("/?" + urllib.parse.urlencode({"msg": f"Not saved: {exc}"}))
    q = canned.clean_query(f.get("query", ""))
    return redirect("/?" + q + ("&" if q else "") + urllib.parse.urlencode({"msg": "View saved"}))


def view_delete(ctx):
    from .. import redirect
    from ... import canned
    vid = ctx.request.form().get("view_id", "")
    if vid.isdigit():
        canned.delete_view(ctx.conn, member=ctx.user.id, view_id=int(vid))
        ctx.conn.commit()
    return redirect("/?" + urllib.parse.urlencode({"msg": "View forgotten"}))


def _tiles(f, counts) -> str:
    out = []
    for key, label, cls, ic in TILES:
        on = " on" if f["tile"] == key and (key or not any(
            f[k] for k in ("tile", "owner", "pri", "src", "type", "q"))) else ""
        out.append(f"<a class='tile {cls}{on}' href='{t.esc(_link(f, tile=key, view='open'))}'>{t.icon(ic)}"
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
        + _options([("", "Any")] + [(p, f"{p} · {t.priority_name(p)}") for p in PRIORITY_ORDER], f["pri"]) +
        "</select></div><div><label>Type</label><select name=type>"
        + _options([("", "Any")] + [(k, v) for k, v in itil.LABEL.items()]
                   + [("none", "Not set")], f["type"]) +
        "</select></div><div><label>Source</label><select name=src>"
        + _options([("", "Any")] + [(s, s.replace("_", "-").title()) for s in SOURCES], f["src"]) +
        "</select></div>"
        f"<div class=wide style='flex:1'><label>Search</label><input name=q value='{t.esc(f['q'])}' "
        "placeholder='ticket #, summary, contact'></div>"
        f"<div style='min-width:0'><button type=submit>{t.icon('filter')} Filter</button></div></form></div>")


def _pager(f, shown: int, total: int) -> str:
    page = max(int(f["page"]), 1) if f["page"].isdigit() else 1
    first = (page - 1) * PAGE + 1
    last = first + shown - 1
    dens = ("<span class=densi><button type=button class=ghost data-density='' aria-pressed=true>Comfortable</button>"
            "<button type=button class=ghost data-density=compact aria-pressed=false>Compact</button></span>")
    if total <= PAGE:
        return f"{dens}{total} ticket(s)."
    prev_ = (f"<a class='btn ghost' href='{t.esc(_link(f, page=str(page - 1)))}'>‹ Previous</a> "
             if page > 1 else "")
    next_ = (f" <a class='btn ghost' href='{t.esc(_link(f, page=str(page + 1)))}'>Next ›</a>"
             if last < total else "")
    return f"{dens}{prev_}Showing {first}–{last} of {total}{next_}"


def _table(ctx, boards, shown, f, total: int) -> str:
    head = []
    for key, label in COLUMNS:
        on = f["sort"] == key
        nxt = "asc" if on and f["dir"] != "asc" else "desc" if on else ""
        arrow = (" ▲" if f["dir"] == "asc" else " ▼") if on else ""
        head.append(f"<th class='sort{' on' if on else ''}{' sm-hide' if key in SM_HIDE else ''}'>"
                    f"<a href='{t.esc(_link(f, sort=key, dir=nxt))}'>{t.esc(label)}{arrow}</a></th>")

    from ... import members as _members
    names: dict[str, str] = {}

    def who(m: str) -> str:
        # A person's name, not their sign-in: an email address as owner made the
        # column wide enough to push the SLA chips off the card (Dada, 1 Oct).
        if m.lower() not in names:
            n = _members.name_of(ctx.conn, m)
            if n == m and "@" in m:
                n = m.split("@", 1)[0]
            names[m.lower()] = n
        return names[m.lower()]

    # The reference PSA's Resources column: who is scheduled on each ticket.
    res: dict[str, list[str]] = {}
    ids = [x["r"]["work_item_id"] for x in shown]
    if ids:
        for r in ctx.conn.execute("SELECT work_item_id, member FROM ticket_schedule WHERE work_item_id IN (%s)"
                                  " ORDER BY starts_at" % ",".join("?" * len(ids)), ids):
            lst = res.setdefault(r["work_item_id"], [])
            if r["member"].lower() not in {m.lower() for m in lst}:
                lst.append(r["member"])
    lines = []
    from ... import richtext
    for x in shown:
        r = x["r"]
        wid = r["work_item_id"]
        cls = {"BAD": "s-bad", "WARN": "s-warn", "OK": "s-ok"}.get(x["worst"], "")
        sla = t.sla_chips(x["states"]) or (
            f"<span class=pill>{t.esc(common.no_clock_reason(ctx.conn, r['board_id'], r['source_ref']))}</span>")
        last = r["last_note"] or ""
        if richtext.is_rich(r["last_note_format"]):
            last = " ".join(richtext.text(last).split())
        last = (last[:90] + "…") if len(last) > 90 else last
        lines.append(
            f"<tr class='{cls}'>"
            f"<td><input type=checkbox name=ids value='{t.esc(wid)}' form=bulk aria-label='Tick {t.esc(wid)}'></td>"
            f"<td class=sm-hide><a href='/ticket/{t.esc(wid)}'>{t.esc(wid)}</a></td>"
            f"<td class=sum><a href='/ticket/{t.esc(wid)}' style='color:inherit'><b>{t.esc(r['summary'])}</b></a>"
            f"<div class='sm-only meta'>{t.esc(wid)} · {t.esc(r['status_name'] or r['state'].replace('_', ' ').title())}"
            f" · {t.esc(r['owner'] or 'unassigned')} · {t.esc(common.human_age(r['opened_at'], now=ctx.now))}</div>"
            + (" <span class='chip sla-warn' title='The requester has written since the desk last did'>"
               "customer updated</span>" if r["customer_updated"] else "")
            + "<div class=last><span class=pill>" + t.esc(" › ".join(
                [itil.LABEL.get(r["record_type"], "Type not set")] + ([r["klass"]] if r["klass"] else [])))
            + "</span>"
            + (f" <span class=pill title='Closes when its parent closes'>child of {t.esc(r['parent_id'])}</span>"
               if r["parent_id"] else "")
            + (f" <span class=pill>{r['children']} child{'ren' if r['children'] != 1 else ''}</span>"
               if r["children"] else "")
            + (" <span class=pill title='Scheduled on it'>" + t.esc(", ".join(who(m) for m in res[wid])) + "</span>"
               if res.get(wid) else "")
            + "</div>"
            + (f"<div class=last>{t.esc(last)}</div>" if last else "") + "</td>"
            f"<td class=sm-hide title='{t.esc(r['entity'] or '')}'>{t.esc(r['entity_id'] or '—')}</td>"
            f"<td class='muted wrap sm-hide'>{t.esc(r['requested_by'] or '—')}</td>"
            f"<td class='wrap sm-hide'>{t.esc(r['board_name'])}</td>"
            f"<td class=sm-hide>{t.esc(r['status_name'] or r['state'].replace('_', ' ').title())}</td>"
            f"<td>{t.badge(r['priority'])}</td>"
            f"<td class='wrap sm-hide' title='{t.esc(r['owner'] or '')}'>{t.esc(who(r['owner']) if r['owner'] else '—')}</td>"
            f"<td class=sm-hide>{t.esc(common.human_age(r['opened_at'], now=ctx.now))}</td>"
            f"<td class='muted sm-hide'>{t.esc(common.human_age(r['updated_at'] or r['opened_at'], now=ctx.now))}</td>"
            f"<td class=sla>{sla}</td></tr>")

    return (
        "<div class=card style='padding:10px'>" + _bulk_bar(ctx, boards, f) +
        "<div class=tablewrap><table class='grid cards'><thead><tr>"
        "<th><input type=checkbox data-all aria-label='Select every ticket on this page'></th>"
        + "".join(head) + "</tr></thead><tbody>" + "".join(lines) + "</tbody></table></div>"
        f"<div class=pager>{_pager(f, len(shown), total)}</div>"
        "<p class=sub style='margin:10px 0 0'>R · P · S = Respond · Resolution plan · Resolve. "
        "Green on track or met, amber inside 20% of target, red breached, grey paused.</p></div>")


def _bulk_bar(ctx, boards, f) -> str:
    marks = ",".join("?" * len(boards))
    names = [r["name"] for r in ctx.conn.execute(
        f"SELECT name, MIN(sort_order) AS first_order FROM board_status WHERE board_id IN ({marks})"
        " AND inactive = 0 GROUP BY name ORDER BY first_order, name", tuple(boards))]
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
        "<b><span data-count>0</span> ticked:</b> Status <select name=status>" + "".join(status_opts) + "</select>"
        " Assign " + common.owner_select(ctx.conn, [b["board_id"] for b in work_boards], None, me=ctx.user.id,
                                         blank="(leave the owner)", attrs=" style='padding:4px 8px'") +
        f" Move to <select name=to_board>{move_opts}</select>"
        " Attach to parent " + t.ticket_pick('parent', 'search or number', style='width:190px;padding:4px 8px') +
        " Merge into " + t.ticket_pick('merge_into', 'search or number', style='width:190px;padding:4px 8px') +
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
    parent = form.get("parent", "").strip().upper()
    merge_into = form.get("merge_into", "").strip().upper()
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
            if merge_into and merge_into != wid:
                from ... import family
                mrow = ctx.conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?",
                                        (merge_into,)).fetchone()
                if mrow is None or not common.may_access_board(ctx, mrow["board_id"], need="WORK"):
                    raise PermissionError
                family.merge(ctx.conn, wid, merge_into, at=ctx.now, actor=ctx.user.id)
            if parent and parent != wid:
                from ... import family
                prow = ctx.conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?",
                                        (parent,)).fetchone()
                if prow is None or not common.may_access_board(ctx, prow["board_id"], need="WORK"):
                    raise PermissionError
                family.attach(ctx.conn, parent, wid, at=ctx.now, actor=ctx.user.id)
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
    return Response(body=t.page("Service Board", heading + body, user=ctx.user, active="board", live="board"))
