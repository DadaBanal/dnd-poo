"""The ticket — one screen, laid out the way a ConnectWise technician expects.

Header: id, summary, board, status, priority and WHY it is that priority (the
matrix computed it; nobody typed it). Under it, one box per SLA clock —
Respond, Resolution plan, Resolve — with its target, where it stands, and a bar.

Left: the notes, each flagged the ConnectWise way — Discussion (the requester
reads it on the portal), Internal (shaded; never leaves the desk), Resolution
(the answer; the requester reads it) — with system events as quiet lines
between them, and tabs to filter by flag. Below: the note box, which also
books banded time and can move the status in the same action.

Right: the ticket's fields (board, status, owner, company, contact, the two
questions), what time has been booked, the commercial basis and the details.

Every change goes through the engine (board.add_note, board.update_fields,
board.change_status, board.move). This view never touches a clock itself.
"""
from __future__ import annotations

import re
import urllib.parse

from ... import board as engine
from ... import tickets
from .. import templates as t
from . import common
from .portal import PATIENT_WAITING, WHO_IS_AFFECTED

FLAG_LABEL = {"DISCUSSION": "Discussion", "INTERNAL": "Internal", "RESOLUTION": "Resolution"}
SOURCES = (("PHONE", "Phone"), ("WALK_UP", "Walk-up"), ("EMAIL", "Email (logged by hand)"),
           ("DESK", "Desk (seen by us)"))
CHARGE_LABEL = {"INCLUDED_IN_MONTHLY_FEE": "Included in monthly fee",
                "CAPACITY_UPLIFT": "Capacity uplift", "SEPARATE_CHARGE": "Separate charge",
                "PASS_THROUGH": "Pass-through", "NON_CHARGEABLE": "Non-chargeable"}


def _load(ctx, work_item_id):
    from .. import HttpError
    row = ctx.conn.execute(
        "SELECT t.*, w.name AS summary, w.contract_basis, w.variation_id,"
        "       w.entity_id, e.name AS entity, s.name AS status_name,"
        "       s.escalation_status, b.display_name AS board_name,"
        "       b.closed_loop_required, b.calendar_id, c.name AS calendar_name,"
        "       b.kind AS board_kind"
        "  FROM ticket t"
        "  JOIN work_item w ON w.work_item_id = t.work_item_id"
        "  LEFT JOIN entity e ON e.entity_id = w.entity_id"
        "  LEFT JOIN board_status s ON s.board_status_id = t.board_status_id"
        "  JOIN board b ON b.board_id = t.board_id"
        "  LEFT JOIN calendar c ON c.calendar_id = b.calendar_id"
        " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    if row is None:
        raise HttpError("404 Not Found", "No such ticket.")
    # subject_id names the ticket, so a restricted read is auditable to the
    # patient's ticket and not merely to the board (§6.1 requirement 4).
    common.require_board(ctx, row["board_id"], subject_id=work_item_id)
    return row


_STATUS_EVENT = re.compile(
    r"^(?P<frm>\S+) -> (?P<to>\S+) \((?P<esc>[A-Z_]+)\); stopped=(?P<stopped>.*?) "
    r"paused=(?P<paused>.*?) resumed=(?P<resumed>.*)$")


def _clocks_in(text: str) -> list[str]:
    return [common.CLOCK_NAME.get(c, c) for c in re.findall(r"'([A-Z_]+)'", text)]


def _system_line(conn, e) -> str:
    """A system event in words. The engine writes a precise record; a person
    reads 'moved New → In Progress · Respond clock stopped'."""
    detail = e["detail"] or e["kind"]
    if e["kind"] == "STATUS_CHANGE":
        m = _STATUS_EVENT.match(detail)
        if m:
            names = {r["board_status_id"]: r["name"] for r in conn.execute(
                "SELECT board_status_id, name FROM board_status WHERE board_status_id IN (?,?)",
                (m["frm"], m["to"]))}
            frm = names.get(m["frm"], m["frm"].replace("_", " ").title())
            to = names.get(m["to"], m["to"])
            bits = [f"moved {frm} → {to}"]
            for label, key in (("stopped", "stopped"), ("paused", "paused"), ("resumed", "resumed")):
                clocks_ = _clocks_in(m[key])
                if clocks_:
                    bits.append(f"{' and '.join(clocks_)} clock{'s' if len(clocks_) > 1 else ''} {label}")
            return " · ".join(bits)
    if e["kind"] == "IMPORTED":
        return "imported from the desk export"
    return detail


def _initials(name) -> str:
    parts = [p for p in (name or "?").replace("@", " ").replace(".", " ").split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def _ago(age: str) -> str:
    return age if age == "—" else f"{age} ago"


def _contact_list(conn, list_id: str, entity_id: str | None = None) -> str:
    """A <datalist> of active contacts as 'Name <email>', which is exactly the
    shape contacts.resolve() matches. Plain HTML: the browser offers the names
    as the user types, with no script."""
    sql = ("SELECT display_name, email FROM contact WHERE inactive = 0 AND email IS NOT NULL")
    params: list = []
    if entity_id and entity_id != "UNCLASSIFIED":
        sql += " AND entity_id = ?"
        params.append(entity_id)
    rows = conn.execute(sql + " ORDER BY display_name LIMIT 2000", params).fetchall()
    if not rows:
        return ""
    return (f"<datalist id={list_id}>" + "".join(
        f"<option value='{t.esc(r['display_name'])} &lt;{t.esc(r['email'])}&gt;'>" for r in rows)
        + "</datalist>")


def _catalogue_select(conn, board_id, selected, *, disabled="") -> str:
    """Type › Subtype › Item, grouped by Type (ConnectWise's three levels). The
    board's own items are listed first within each group."""
    from ... import setup
    choices = setup.catalogue_choices(conn, board_id)
    if not choices:
        return ""
    groups: dict[str, list] = {}
    for c in sorted(choices, key=lambda x: (x["type"], not x["on_board"], x["subtype"], x["item"])):
        groups.setdefault(c["type"], []).append(c)
    opts = ["<option value=''>(not classified)</option>"]
    for type_, items in groups.items():
        opts.append(f"<optgroup label='{t.esc(type_)}'>")
        for c in items:
            opts.append(f"<option value='{t.esc(c['catalogue_item_id'])}'"
                        f"{' selected' if c['catalogue_item_id'] == selected else ''}>"
                        f"{t.esc(c['subtype'])} › {t.esc(c['item'])}</option>")
        opts.append("</optgroup>")
    return (f"<label>Subtype › Item</label><select name=catalogue_item_id{disabled}>"
            + "".join(opts) + "</select>")


def _type_select(conn, board_id: str | None, selected: str | None, *, disabled: str = "",
                 blank: str | None = None) -> str:
    """The board's Types (ConnectWise's Types tab): Incident, Request, Problem,
    Event on a service board. With no board, every Type."""
    from ... import itil
    rows = [r["record_type"] for r in itil.boards_types(conn, board_id)] if board_id else []
    types = rows or list(itil.RECORD_TYPES)
    if selected and selected not in types:
        types.insert(0, selected)
    pairs = ([("", blank)] if blank else []) + [(x, itil.LABEL[x]) for x in types]
    return (f"<label>Type</label><select name=record_type{disabled}>"
            + _options(pairs, selected or "") + "</select>")


def _options(pairs, selected) -> str:
    return "".join(f"<option value='{t.esc(v)}'{' selected' if v == selected else ''}>"
                   f"{t.esc(label)}</option>" for v, label in pairs)


def detail(ctx, work_item_id):
    from .. import Response
    tk = _load(ctx, work_item_id)
    wid = t.esc(work_item_id)
    msg = ctx.request.query.get("msg", "")
    err = ctx.request.query.get("err", "")
    tab = ctx.request.query.get("tab", "ALL")

    # ------------------------------------------------------------ header
    why = ""
    if tk["priority_source"] == "MATRIX":
        who = dict(WHO_IS_AFFECTED).get(tk["impact"], tk["impact"])
        wait = dict(PATIENT_WAITING).get(tk["urgency"], tk["urgency"])
        why = f"computed: {who.lower()} × patient waiting: {wait.lower()}"
    else:
        why = f"set by {tk['priority_source'].replace('_', ' ').lower()}"
    from ... import itil
    parts = [itil.LABEL[tk["record_type"]]] if tk["record_type"] else ["Type not set"]
    if tk["catalogue_item_id"]:
        r = ctx.conn.execute(
            "SELECT c.display_name AS st, a.display_name AS it"
            "  FROM catalogue_item i JOIN service_component c ON c.component_id = i.component_id"
            "  JOIN service_action a ON a.action_id = i.action_id"
            " WHERE i.catalogue_item_id = ?", (tk["catalogue_item_id"],)).fetchone()
        parts += [r["st"], r["it"]] if r else [tk["catalogue_item_id"]]
    klass = " › ".join(parts)
    can_work = common.may_access_board(ctx, tk["board_id"], need="WORK")
    buttons = ""
    if can_work and tk["closed_loop_required"]:
        buttons = f"<a class=btn href='/ticket/{wid}/loop'>Close the loop</a>"
    header = (
        (f"<div class='banner ok toast'>{t.icon('check')} {t.esc(msg)}</div>" if msg else "") +
        (f"<div class='banner err toast'>{t.icon('alert')} {t.esc(err)}</div>" if err else "") +
        "<div class=hdr><div class=grow>"
        f"<h1>{wid} · {t.esc(tk['summary'])}</h1>"
        f"<p class=sub>{t.esc(tk['board_name'])} · "
        f"{t.chip(tk['status_name'] or tk['state'].replace('_', ' ').title())} · "
        f"{t.badge(tk['priority'])} <span class=why>{t.esc(why)}</span>"
        + (f" · <span class=pill>{t.esc(klass)}</span>" if klass else "") + "</p></div>"
        f"<div>{buttons}</div></div>")

    # ----------------------------------------------------------- SLA strip
    states = common.clock_states(ctx.conn, work_item_id, now=ctx.now)
    if states:
        boxes = []
        for st in states:
            cls = {"MET": "done", "MISSED": "bad", "BAD": "bad", "WARN": "warn",
                   "PAUSED": "done"}.get(st["state"], "ok")
            boxes.append(
                f"<div class='slabox {cls}'><div class=t>{t.esc(st['name'])} · target "
                f"{t.esc(common.fmt_minutes(st['target']))}</div>"
                f"<div class=v>{t.esc(st['text'])}</div>"
                f"<div class=bar><i style='width:{int(st['fraction'] * 100)}%'></i>"
                "</div></div>")
        strip = "<div class=slastrip>" + "".join(boxes) + "</div>"
    else:
        reason = common.no_clock_reason(ctx.conn, tk["board_id"], tk["source_ref"])
        strip = (f"<div class=note-ph>No SLA clock on this ticket: {t.esc(reason)}."
                 + (" A board administrator sets the board up on the Setup page."
                    if reason == "board not set up" else "") + "</div>")

    # --------------------------------------------------------- the notes
    events = ctx.conn.execute(
        "SELECT occurred_at, kind, actor, detail, note_flag, is_resolution FROM ticket_event"
        " WHERE work_item_id = ? ORDER BY ticket_event_id", (work_item_id,)).fetchall()

    def is_res(e):
        return e["note_flag"] == "RESOLUTION" or bool(e["is_resolution"])
    time_rows = ctx.conn.execute(
        "SELECT worked_on, band_hours, performed_by, charge_method, note FROM time_entry"
        " WHERE work_item_id = ? ORDER BY time_entry_id", (work_item_id,)).fetchall()
    counts = {"ALL": len(events), "SYSTEM": sum(1 for e in events if not e["note_flag"])}
    for flag in ("DISCUSSION", "INTERNAL"):
        counts[flag] = sum(1 for e in events if e["note_flag"] == flag)
    counts["RESOLUTION"] = sum(1 for e in events if is_res(e))
    tabs = "".join(
        f"<a class='{'on' if tab == key else ''}' href='/ticket/{wid}?tab={key}'>"
        f"{label} {counts[key]}</a>"
        for key, label in (("ALL", "All"), ("DISCUSSION", "Discussion"), ("INTERNAL", "Internal"),
                           ("RESOLUTION", "Resolution"), ("SYSTEM", "System")))
    items = []
    for e in events:
        flag = e["note_flag"]
        if tab == "SYSTEM" and flag:
            continue
        if tab == "RESOLUTION" and not is_res(e):
            continue
        if tab in ("DISCUSSION", "INTERNAL") and flag != tab:
            continue
        if flag:
            extra = ("<span class='flag RESOLUTION'>Resolution</span>"
                     if e["is_resolution"] and flag != "RESOLUTION" else "")
            items.append(
                f"<div class='note {flag}'><div class=h><span class=av>{t.esc(_initials(e['actor']))}</span>"
                f"<b>{t.esc(e['actor'] or '—')}</b><span class='flag {flag}'>{FLAG_LABEL[flag]}</span>{extra}"
                f"{t.esc(e['occurred_at'])} · {t.esc(e['kind'].replace('_', ' ').lower())}</div>"
                f"<div style='white-space:pre-wrap'>{t.esc(e['detail'])}</div></div>")
        else:
            items.append(f"<div class=sys>{t.esc(e['occurred_at'])} · {t.esc(e['actor'] or 'system')} · "
                         f"{t.esc(_system_line(ctx.conn, e))}</div>")
    stream = "".join(items) or "<div class=empty>Nothing here yet.</div>"

    statuses = ctx.conn.execute(
        "SELECT board_status_id, name FROM board_status"
        " WHERE board_id = ? AND inactive = 0 ORDER BY sort_order, name",
        (tk["board_id"],)).fetchall()
    status_pairs = [(s["board_status_id"], s["name"]) for s in statuses]
    may, why_not = engine.may_book_effort(ctx.conn, work_item_id)

    composer = ""
    if can_work:
        band_opts = "<option value=''>No time</option>" + "".join(
            f"<option value='{b:g}'>{b:g} h</option>" for b in engine.BANDS)
        charge_opts = "<option value=''>— choose —</option>" + "".join(
            f"<option value='{k}'>{t.esc(v)}</option>" for k, v in CHARGE_LABEL.items())
        time_block = (
            f"<div><label>Time</label><select name=hours>{band_opts}</select></div>"
            f"<div><label>Charged as</label><select name=charge>{charge_opts}</select></div>"
            if may else f"<div><label>Time</label><div class=ro>{t.esc(why_not)}</div></div>")
        composer = (
            "<div class=card><h3><svg class=ic aria-hidden=true><use href=#i-note></use></svg>Add a note</h3>"
            f"<form method=post action='/ticket/{wid}/note'>"
            "<textarea name=body required placeholder='No patient names or case numbers (§6.1).'></textarea>"
            "<div class=row style='margin-top:10px'>"
            "<div style='flex:0 0 auto'><label>Who can read it</label><div class=seg>"
            "<label><input type=radio name=flag value=DISCUSSION checked><span>Discussion</span></label>"
            "<label class=int><input type=radio name=flag value=INTERNAL><span>Internal</span></label>"
            "</div><label style='display:block;margin-top:6px;color:var(--ink);font-weight:500'>"
            "<input type=checkbox name=resolution value=1 style='width:auto'> Also the resolution"
            "</label></div>" + time_block +
            "<div><label>And set status</label><select name=to_status>"
            + _options([("", "(no change)")] + status_pairs, "") +
            "</select></div><div style='flex:0 0 auto'><button type=submit><svg class=ic aria-hidden=true><use href=#i-note></use></svg> Save note</button></div>"
            "</div><p class=why style='margin:8px 0 0'>Discussion notes, and the resolution when it "
            "is a Discussion note, are shown to the requester on their portal. Internal notes never "
            "leave the desk, even when they are the resolution.</p></form></div>")

    left = (f"<div><div class=card><div class=tabs>{tabs}</div>{stream}</div>{composer}</div>")

    # ---------------------------------------------------------- right rail
    boards = ctx.conn.execute(
        "SELECT b.board_id, b.display_name FROM board b JOIN board_member m"
        " ON m.board_id = b.board_id WHERE m.member = ? AND m.access IN ('WORK','ADMIN')"
        " AND COALESCE(b.inactive, 0) = 0 ORDER BY b.display_name", (ctx.user.id,)).fetchall()
    board_pairs = [(b["board_id"], b["display_name"]) for b in boards]
    if tk["board_id"] not in dict(board_pairs):
        board_pairs.insert(0, (tk["board_id"], tk["board_name"]))
    entities = ctx.conn.execute("SELECT entity_id, name FROM entity ORDER BY name").fetchall()
    dis = "" if can_work else " disabled"
    person = (ctx.conn.execute("SELECT * FROM contact WHERE contact_id = ?",
                               (tk["contact_id"],)).fetchone() if tk["contact_id"] else None)
    if person is not None:
        bits = " · ".join(t.esc(x) for x in (person["department"], person["title"],
                                              person["phone"]) if x)
        person_line = (f"<div class=why style='margin:4px 0 0'><a href='/contact/"
                       f"{t.esc(person['contact_id'])}'>{t.esc(person['display_name'])}</a>"
                       + (f" · {bits}" if bits else "")
                       + (" · <b>inactive</b>" if person["inactive"] else "") + "</div>")
    elif tk["requested_by"]:
        person_line = ("<div class=why style='margin:4px 0 0'>Not matched to a contact: "
                       "pick one from the list, or import contacts from AD.</div>")
    else:
        person_line = ""
    fields = (
        "<div class='card fields' data-pod=ticket><h3><svg class=ic aria-hidden=true><use href=#i-ticket></use></svg>Ticket</h3>"
        f"<form method=post action='/ticket/{wid}/update'>"
        f"<label>Board</label><select name=board_id{dis}>{_options(board_pairs, tk['board_id'])}</select>"
        f"<label>Status</label><select name=to_status{dis}>"
        f"{_options(([] if tk['board_status_id'] else [('', '(none)')]) + status_pairs, tk['board_status_id'] or '')}</select>"
        f"<label>Owner</label><input name=owner value='{t.esc(tk['owner'] or '')}'{dis}>"
        f"<label>Company</label><select name=entity_id{dis}>"
        f"{_options([(e['entity_id'], e['name']) for e in entities], tk['entity_id'] or '')}</select>"
        f"<label>Contact</label><input name=requested_by list=contacts-ticket "
        f"value='{t.esc(tk['requested_by'] or '')}'{dis}>"
        + _contact_list(ctx.conn, "contacts-ticket", tk["entity_id"]) + person_line
        + _type_select(ctx.conn, tk["board_id"], tk["record_type"], disabled=dis,
                       blank=None if tk["record_type"] else "(not set)")
        + _catalogue_select(ctx.conn, tk["board_id"], tk["catalogue_item_id"], disabled=dis) +
        f"<label>Who is affected</label><select name=impact{dis}>{_options(WHO_IS_AFFECTED, tk['impact'])}</select>"
        f"<label>Is a patient waiting</label><select name=urgency{dis}>{_options(PATIENT_WAITING, tk['urgency'])}</select>"
        f"<label>Priority</label><div class=ro>{t.badge(tk['priority'])} from the matrix — never typed</div>"
        + ("<div style='margin-top:12px'><button type=submit><svg class=ic aria-hidden=true><use href=#i-check></use></svg> Save changes</button></div>" if can_work else "")
        + "</form></div>")

    total = sum(r["band_hours"] for r in time_rows)
    time_list = "".join(
        f"<dt>{t.esc(r['worked_on'])}</dt><dd>{t.esc(r['performed_by'])} · {r['band_hours']:g} h · "
        f"{t.esc(CHARGE_LABEL.get(r['charge_method'], r['charge_method']))}</dd>" for r in time_rows)
    time_card = (f"<div class=card data-pod=time><h3><svg class=ic aria-hidden=true><use href=#i-clock></use></svg>Time · {total:g} h</h3>"
                 + (f"<dl class=kv>{time_list}</dl>" if time_list else "<div class=muted>None booked.</div>")
                 + (f"<p class=why>{t.esc(why_not)}</p>" if not may else "") + "</div>")
    commercial = (
        "<div class=card data-pod=commercial><h3><svg class=ic aria-hidden=true><use href=#i-briefcase></use></svg>Commercial basis</h3><dl class=kv>"
        f"<dt>Contract basis</dt><dd>{t.esc(tk['contract_basis'])}</dd>"
        f"<dt>Commercial path</dt><dd>{t.esc(tk['path'])}</dd>"
        f"<dt>Variation</dt><dd>{t.esc(tk['variation_id'] or '—')}</dd></dl></div>")
    details = (
        "<div class=card data-pod=details><h3><svg class=ic aria-hidden=true><use href=#i-info></use></svg>Details</h3><dl class=kv>"
        f"<dt>Opened</dt><dd>{t.esc(tk['opened_at'])}</dd>"
        f"<dt>Updated</dt><dd>{t.esc(_ago(common.human_age(tk['updated_at'] or tk['opened_at'], now=ctx.now)))}</dd>"
        f"<dt>Source</dt><dd>{t.esc((tk['intake_source'] or '—').replace('_', '-').title())}</dd>"
        f"<dt>Desk ref</dt><dd>{t.esc(tk['external_ref'] or '—')}</dd>"
        f"<dt>Calendar</dt><dd>{t.esc(tk['calendar_name'] or '—')}</dd></dl></div>")

    from . import configurations as cmdb_views
    configs = cmdb_views.ticket_card(ctx, tk, can_work=can_work)
    from . import files as file_views
    configs = (_change_card(ctx, tk, can_work=can_work) + _family_card(ctx, tk, can_work=can_work)
               + _tasks_card(ctx, tk, can_work=can_work)
               + file_views.ticket_card(ctx, tk, can_work=can_work) + _links_card(ctx, tk, can_work=can_work) + configs)
    # The side cards are pods: each user drags or folds them and the browser
    # remembers; data-order is the shipped layout that "Reset layout" restores.
    body = header + strip + (f"<div class=rail>{left}<div class=pods data-order='ticket,change,family,tasks,"
                             f"files,links,configurations,time,commercial,details'>{fields}{configs}{time_card}"
                             f"{commercial}{details}</div></div>")
    return Response(body=t.page(work_item_id, body, user=ctx.user, active="board"))


def _back(work_item_id, **q):
    from .. import redirect
    qs = urllib.parse.urlencode({k: v for k, v in q.items() if v})
    return redirect(f"/ticket/{work_item_id}" + (f"?{qs}" if qs else ""))


def change_status(ctx, work_item_id):
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    to_status = ctx.request.form().get("to_status", "")
    try:
        engine.change_status(ctx.conn, work_item_id, to_status, at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except (engine.NotOnThisBoard, LookupError) as exc:
        ctx.conn.rollback()
        return _back(work_item_id, err=str(exc))
    return _back(work_item_id)


def add_note(ctx, work_item_id):
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    f = ctx.request.form()
    hours = f.get("hours", "").strip()
    try:
        engine.add_note(ctx.conn, work_item_id, body=f.get("body", ""),
                        flag=f.get("flag", "DISCUSSION") or "DISCUSSION",
                        actor=ctx.user.id, at=ctx.now,
                        band_hours=float(hours) if hours else None,
                        charge_method=f.get("charge") or None,
                        to_status_id=f.get("to_status") or None,
                        resolution=f.get("resolution") == "1")
        ctx.conn.commit()
    except (ValueError, LookupError, engine.EffortRefused, engine.NotOnThisBoard) as exc:
        ctx.conn.rollback()
        return _back(work_item_id, err=f"Note not saved: {exc}")
    except Exception as exc:                                 # a gate trigger refused it
        ctx.conn.rollback()
        return _back(work_item_id, err=f"Note not saved: {exc}")
    return _back(work_item_id, msg="Note saved")


def update(ctx, work_item_id):
    """The right-hand panel. A board change is a move (one id, clocks intact);
    the rest are field edits; a status change goes through the one seam."""
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    f = ctx.request.form()
    changed = []
    try:
        to_board = f.get("board_id", tk["board_id"])
        want_type = f.get("record_type") if "record_type" in f else None
        if to_board and to_board != tk["board_id"]:
            common.require_board(ctx, to_board, need="WORK")
            engine.move(ctx.conn, work_item_id, to_board, at=ctx.now, actor=ctx.user.id,
                        reason="moved on the ticket", record_type=want_type or None)
            changed.append(f"moved to {to_board}")
            want_type = None                      # settled by the move
        impact = f.get("impact") if f.get("impact") in dict(WHO_IS_AFFECTED) else None
        urgency = f.get("urgency") if f.get("urgency") in dict(PATIENT_WAITING) else None
        changed += engine.update_fields(
            ctx.conn, work_item_id, at=ctx.now, actor=ctx.user.id,
            owner=f.get("owner"), entity_id=f.get("entity_id") or None,
            requested_by=f.get("requested_by"), impact=impact, urgency=urgency,
            catalogue_item_id=f.get("catalogue_item_id") if "catalogue_item_id" in f else None,
            record_type=want_type, **change_fields_from(f))
        to_status = f.get("to_status", "")
        now_status = ctx.conn.execute("SELECT board_status_id FROM ticket WHERE work_item_id = ?",
                                      (work_item_id,)).fetchone()[0]
        # After a move the old board's status is meaningless: only a status on
        # the ticket's current board is applied.
        if to_status and to_status != now_status and not (to_board != tk["board_id"]):
            engine.change_status(ctx.conn, work_item_id, to_status, at=ctx.now, actor=ctx.user.id)
            changed.append("status")
        ctx.conn.commit()
    except Exception as exc:                                 # noqa: BLE001
        ctx.conn.rollback()
        return _back(work_item_id, err=f"Not saved: {exc}")
    return _back(work_item_id, msg="Saved" if changed else "Nothing changed")


# ---------------------------------------------------------------- new ticket

def new_form(ctx, *, error: str = "", values: dict | None = None):
    from .. import Response
    # From a company or contact page the link carries who is asking.
    v = values or {k: ctx.request.query[k] for k in ("board_id", "entity_id", "requested_by")
                   if ctx.request.query.get(k)}
    # Starting from a template fills the form; its tasks are added on create.
    tpl_id = (values or {}).get("template_id") or ctx.request.query.get("template", "")
    tpl = ctx.conn.execute("SELECT * FROM ticket_template WHERE template_id = ? AND inactive = 0",
                           (tpl_id,)).fetchone() if tpl_id else None
    if tpl is not None and not values:
        v.update({k: tpl[k] or "" for k in ("summary", "record_type", "catalogue_item_id",
                                           "description")})
        v["board_id"] = tpl["board_id"]
        v["template_id"] = tpl["template_id"]
    boards = ctx.conn.execute(
        "SELECT b.board_id, b.display_name FROM board b JOIN board_member m"
        " ON m.board_id = b.board_id WHERE m.member = ? AND m.access IN ('WORK','ADMIN')"
        " AND COALESCE(b.inactive, 0) = 0 ORDER BY b.is_unrouted, b.display_name",
        (ctx.user.id,)).fetchall()
    if not boards:
        body = ("<h1>New ticket</h1><div class=card><div class=empty>You are not a working "
                "member of any board. To ask IT for something, use "
                "<a href='/my'>My requests</a>.</div></div>")
        return Response(body=t.page("New ticket", body, user=ctx.user, active="board"))
    entities = ctx.conn.execute("SELECT entity_id, name FROM entity ORDER BY is_covered DESC, name").fetchall()

    def radios(name, pairs, sel):
        return "".join(
            f"<label><input type=radio name={name} value='{k}' style='width:auto'"
            f"{' checked' if k == sel else ''} required> {t.esc(lab)}</label>" for k, lab in pairs)

    body = (
        (f"<div class='banner err'>{t.esc(error)}</div>" if error else "") +
        _template_picker(ctx, tpl["template_id"] if tpl is not None else "") +
        "<h1>New ticket</h1><p class=sub>For the desk: a call, a walk-up, something you saw. "
        "Priority is computed from the two questions, never chosen.</p>"
        "<div class=card><form method=post action='/ticket/new'>"
        + (f"<input type=hidden name=template_id value='{t.esc(v.get('template_id', ''))}'>"
           if v.get("template_id") else "") + "<div class=grid2>"
        f"<div><label>Board</label><select name=board_id>{_options([(b['board_id'], b['display_name']) for b in boards], v.get('board_id', ''))}</select></div>"
        f"<div><label>Source</label><select name=source>{_options(SOURCES, v.get('source', 'PHONE'))}</select></div>"
        f"<div><label>Company</label><select name=entity_id>{_options([(e['entity_id'], e['name']) for e in entities], v.get('entity_id', 'PMC'))}</select></div>"
        f"<div><label>Contact</label><input name=requested_by list=contacts-new value='{t.esc(v.get('requested_by', ''))}' placeholder='start typing a name, or an email'>"
        + _contact_list(ctx.conn, "contacts-new") + "</div>"
        f"<div style='grid-column:1/-1'><label>Summary</label><input name=summary required value='{t.esc(v.get('summary', ''))}' placeholder='What is wrong, in one line'></div>"
        + f"<div>{_type_select(ctx.conn, None, v.get('record_type', ''), blank='(the board default)')}</div><div></div>"
        + (f"<div style='grid-column:1/-1'>{_catalogue_select(ctx.conn, None, v.get('catalogue_item_id', ''))}</div>"
           if _catalogue_select(ctx.conn, None, "") else "") +
        "<div class=radiorow><label style='color:var(--muted);font-weight:600'>Who is affected?</label>"
        f"{radios('impact', WHO_IS_AFFECTED, v.get('impact', ''))}</div>"
        "<div class=radiorow><label style='color:var(--muted);font-weight:600'>Is a patient waiting?</label>"
        f"{radios('urgency', PATIENT_WAITING, v.get('urgency', ''))}</div>"
        "<div style='grid-column:1/-1'><label>Description</label><textarea name=description "
        f"placeholder='No patient names or case numbers.'>{t.esc(v.get('description', ''))}</textarea></div>"
        f"<div><label>Owner</label><input name=owner value='{t.esc(v.get('owner', ''))}' placeholder='leave blank for the board queue'></div>"
        "</div><div style='margin-top:14px'><button type=submit>Create ticket</button> "
        "<a class='btn ghost' href='/'>Cancel</a></div></form></div>")
    return Response(body=t.page("New ticket", body, user=ctx.user, active="board"))


def new_create(ctx):
    from .. import redirect
    from ... import phi
    f = ctx.request.form()
    board_id = f.get("board_id", "")
    if not common.may_access_board(ctx, board_id, need="WORK"):
        return new_form(ctx, error="Choose a board you work on.", values=f)
    summary = f.get("summary", "").strip()
    impact, urgency = f.get("impact", ""), f.get("urgency", "")
    source = f.get("source", "PHONE")
    if not summary:
        return new_form(ctx, error="A summary is required.", values=f)
    if impact not in dict(WHO_IS_AFFECTED) or urgency not in dict(PATIENT_WAITING):
        return new_form(ctx, error="Answer both questions: who is affected, and whether a "
                                   "patient is waiting.", values=f)
    if source not in dict(SOURCES):
        source = "DESK"
    entity_id = f.get("entity_id") or None
    if entity_id and ctx.conn.execute("SELECT 1 FROM entity WHERE entity_id = ?",
                                      (entity_id,)).fetchone() is None:
        entity_id = None
    description = f.get("description", "").strip()
    try:
        wid = tickets.open_ticket(
            ctx.conn, board_id=board_id, summary=summary, impact=impact, urgency=urgency,
            requested_by=f.get("requested_by", "").strip() or None, at=ctx.now,
            actor=ctx.user.id, description=description or None, entity_id=entity_id,
            owner=f.get("owner", "").strip() or None, source=source, event_kind="OPENED",
            catalogue_item_id=f.get("catalogue_item_id") or None,
            record_type=f.get("record_type") or None)
        tpl_id = f.get("template_id") or ""
        if tpl_id and ctx.conn.execute(
                "SELECT 1 FROM ticket_template WHERE template_id = ? AND board_id = ?",
                (tpl_id, board_id)).fetchone():
            from ... import tasks
            tasks.apply_template(ctx.conn, wid, tpl_id, actor=ctx.user.id, at=ctx.now)
        for code, severity, detail in phi.scan_fields({"summary": summary,
                                                       "description": description}):
            ctx.conn.execute(
                "INSERT INTO data_quality (run_id, subject_kind, subject_id, code, detail,"
                " severity) VALUES (?,?,?,?,?,?)", ("desk", "ticket", wid, code, detail, severity))
        ctx.conn.commit()
    except Exception as exc:                                 # noqa: BLE001
        ctx.conn.rollback()
        return new_form(ctx, error=f"Not created: {exc}", values=f)
    return redirect(f"/ticket/{wid}?msg=" + urllib.parse.quote(f"Created {wid}"))


# ------------------------------------------------------ change and links

AUTHORITY_LABEL = {"CHANGE_AUTHORITY": "Change authority", "CAB": "CAB",
                   "ECAB": "Emergency CAB", "CLIENT": "Client (PMC)"}


def _change_card(ctx, tk, *, can_work: bool) -> str:
    """ITIL change enablement on a Change: its type, risk, window and backout
    plan, the authorisation record, and (for a change authority who is not the
    owner) the decision form."""
    from ... import itil
    if tk["record_type"] != "CHANGE":
        return ""
    wid = t.esc(tk["work_item_id"])
    dis = "" if can_work else " disabled"
    decisions = ctx.conn.execute("SELECT * FROM change_approval WHERE work_item_id = ?"
                                 " ORDER BY approval_id", (tk["work_item_id"],)).fetchall()
    kind = tk["change_type"] or "NORMAL"
    last = decisions[-1]["decision"] if decisions else None
    state = {"STANDARD": "Pre-authorised (standard change)",
             "NORMAL": {"APPROVED": "Approved", "DECLINED": "Declined"}.get(
                 last, "Needs approval before Approved / Scheduled / Implementing"),
             "EMERGENCY": {"APPROVED": "Authorised after the fact"}.get(
                 last, "Going ahead; authorise afterwards before it closes")}[kind]
    log = "".join(
        f"<li><b>{t.esc(d['decision'].title())}</b> by {t.esc(d['decided_by'])} "
        f"({t.esc(AUTHORITY_LABEL.get(d['authority'], d['authority']))}) "
        f"<span class=muted>{t.esc(d['decided_at'])}</span>"
        + (f"<br><span class=muted>{t.esc(d['comment'])}</span>" if d["comment"] else "")
        + "</li>" for d in decisions) or "<li class=muted>No decision recorded.</li>"
    decide = ""
    owner = (tk["owner"] or "").lower()
    if kind != "STANDARD" and itil.may_authorise(ctx.conn, tk["board_id"], ctx.user.id) \
            and owner != (ctx.user.id or "").lower():
        decide = (
            f"<form method=post action='/ticket/{wid}/change/decide' class=fields "
            "style='margin-top:10px'><label>Record a decision</label>"
            "<select name=authority>" + _options(list(AUTHORITY_LABEL.items()), "CAB") +
            "</select><input name=comment placeholder='Reason or conditions (optional)'>"
            "<div class=row style='margin-top:8px'><div style='flex:0 0 auto'>"
            "<button type=submit name=decision value=APPROVED>Approve</button></div>"
            "<div style='flex:0 0 auto'><button class=ghost type=submit name=decision "
            "value=DECLINED>Decline</button></div></div></form>")
    elif kind != "STANDARD":
        decide = ("<p class=why>A change is authorised by the board's administrator or "
                  "Service Manager, never by its owner.</p>")
    return (
        "<div class=card data-pod=change><h3><svg class=ic aria-hidden=true><use href=#i-flag></use></svg>Change</h3>"
        f"<p><span class=pill>{t.esc(state)}</span></p>"
        f"<form method=post action='/ticket/{wid}/update' class=fields>"
        f"<input type=hidden name=board_id value='{t.esc(tk['board_id'])}'>"
        f"<label>Change type</label><select name=change_type{dis}>"
        + _options([("STANDARD", "Standard (pre-authorised)"), ("NORMAL", "Normal"),
                    ("EMERGENCY", "Emergency")], kind) + "</select>"
        f"<label>Risk</label><select name=change_risk{dis}>"
        + _options([("", "(not assessed)"), ("LOW", "Low"), ("MEDIUM", "Medium"),
                    ("HIGH", "High")], tk["change_risk"] or "") + "</select>"
        f"<label>Window starts</label><input name=planned_start{dis} placeholder='2026-09-26 22:00' "
        f"value='{t.esc(tk['planned_start'] or '')}'>"
        f"<label>Window ends</label><input name=planned_end{dis} placeholder='2026-09-26 23:30' "
        f"value='{t.esc(tk['planned_end'] or '')}'>"
        f"<label>Backout plan</label><textarea name=backout_plan{dis} "
        "placeholder='How it is undone if it fails'>"
        f"{t.esc(tk['backout_plan'] or '')}</textarea>"
        + ("<div style='margin-top:10px'><button type=submit>Save change details</button></div>"
           if can_work else "") + "</form>"
        f"<h3 style='margin-top:14px'>Authorisation</h3><ul class=plain>{log}</ul>{decide}</div>")


def _links_card(ctx, tk, *, can_work: bool) -> str:
    """Incident -> problem -> change. A linked ticket on a board this user cannot
    see is counted, never named."""
    from ... import itil
    wid = t.esc(tk["work_item_id"])
    mine = common.board_ids_for(ctx)
    items, hidden = [], 0
    for l in itil.links_of(ctx.conn, tk["work_item_id"]):
        if l["board_id"] not in mine or common.is_restricted(ctx, l["board_id"]):
            hidden += 1
            continue
        remove = ""
        if can_work and l["outgoing"]:
            remove = (f"<form method=post action='/ticket/{wid}/unlink' style='display:inline'>"
                      f"<input type=hidden name=linked_id value='{t.esc(l['other'])}'>"
                      "<button class='ghost small' type=submit title='Remove link'>×</button></form>")
        items.append(f"<li>{t.esc(l['reads'].capitalize())} "
                     f"<a href='/ticket/{t.esc(l['other'])}'>{t.esc(l['other'])}</a> "
                     f"<span class=muted>{t.esc(itil.LABEL.get(l['record_type'], ''))} · "
                     f"{t.esc(l['name'])}</span> {remove}</li>")
    add = ""
    if can_work:
        rels = [("CAUSED_BY", "Caused by problem"), ("FIXED_BY", "Fixed by change"),
                ("RELATED", "Related to")]
        add = (f"<form method=post action='/ticket/{wid}/link' class=row style='margin-top:8px'>"
               f"<div><select name=relation>{_options(rels, 'CAUSED_BY')}</select></div>"
               "<div><input name=linked_id placeholder='PMC-000123' required></div>"
               "<div style='flex:0 0 auto'><button class=ghost type=submit>Link</button></div></form>")
    body = (f"<ul class=plain>{''.join(items)}</ul>" if items else "<div class=muted>No links.</div>")
    if hidden:
        body += f"<p class=why>{hidden} more on boards you cannot see.</p>"
    return f"<div class=card data-pod=links><h3><svg class=ic aria-hidden=true><use href=#i-link></use></svg>Links</h3>{body}{add}</div>"


def _family_card(ctx, tk, *, can_work: bool) -> str:
    """ConnectWise's parent/child. A child shows its parent; a parent lists its
    children with their status. Tickets on boards this user cannot see are
    counted, never named."""
    from ... import family
    wid = t.esc(tk["work_item_id"])
    mine = common.board_ids_for(ctx)

    def visible(board_id):
        return board_id in mine and not common.is_restricted(ctx, board_id)
    body, forms = "", ""
    parent = family.parent_of(ctx.conn, tk["work_item_id"])
    if parent is not None:
        who = (f"<a href='/ticket/{t.esc(parent['work_item_id'])}'>{t.esc(parent['work_item_id'])}</a>"
               f" <span class=muted>{t.esc(parent['summary'])}</span>" if visible(parent["board_id"])
               else f"{t.esc(parent['work_item_id'])} <span class=muted>on a board you cannot see</span>")
        body = (f"<div>Child of {who}</div><p class=why>Closes when its parent closes.</p>")
        if can_work:
            forms = (f"<form method=post action='/ticket/{wid}/parent/remove'>"
                     "<button class=ghost type=submit>" + t.icon("x") + " Detach from parent</button></form>")
        return (f"<div class=card data-pod=family><h3>{t.icon('layers')}Parent</h3>{body}{forms}</div>")
    kids = family.children_of(ctx.conn, tk["work_item_id"])
    items, hidden = [], 0
    for k in kids:
        if not visible(k["board_id"]):
            hidden += 1
            continue
        remove = ""
        if can_work:
            remove = (f"<form method=post action='/ticket/{wid}/child/remove' style='display:inline'>"
                      f"<input type=hidden name=child_id value='{t.esc(k['work_item_id'])}'>"
                      "<button class='ghost small' type=submit title='Detach'>×</button></form>")
        items.append(f"<li><a href='/ticket/{t.esc(k['work_item_id'])}'>{t.esc(k['work_item_id'])}</a> "
                     f"{t.chip(k['status_name'] or k['state'].replace('_', ' ').title())} "
                     f"<span class=muted>{t.esc(k['summary'])}</span> {remove}</li>")
    if items:
        body = f"<ul class=plain>{''.join(items)}</ul><p class=why>Closing this ticket closes them.</p>"
    elif not kids:
        body = "<div class=muted>No children.</div>"
    if hidden:
        body += f"<p class=why>{hidden} more on boards you cannot see.</p>"
    if can_work and not tk["closed_at"]:
        forms = (f"<form method=post action='/ticket/{wid}/child/add' class=row style='margin-top:8px'>"
                 "<div><input name=child_id placeholder='Attach a child: PMC-000123' required></div>"
                 "<div style='flex:0 0 auto'><button class=ghost type=submit>" + t.icon("plus")
                 + " Attach</button></div></form>")
        if not kids:
            forms += (f"<form method=post action='/ticket/{wid}/parent/set' class=row style='margin-top:6px'>"
                      "<div><input name=parent_id placeholder='Make this a child of: PMC-000123' required></div>"
                      "<div style='flex:0 0 auto'><button class=ghost type=submit>" + t.icon("arrow")
                      + " Attach</button></div></form>")
    head = f"Children · {len(kids)}" if kids else "Children"
    return f"<div class=card data-pod=family><h3>{t.icon('layers')}{t.esc(head)}</h3>{body}{forms}</div>"


def _family_change(ctx, work_item_id, fn):
    """Run one parent/child change through the engine; both tickets must be on
    boards this user works."""
    from ... import family
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    try:
        msg = fn()
    except (family.Refused, ValueError, LookupError, PermissionError) as exc:
        return _back(work_item_id, err=f"Not changed: {exc}")
    ctx.conn.commit()
    return _back(work_item_id, msg=msg)


def _other_workable(ctx, other_id: str):
    row = ctx.conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?", (other_id,)).fetchone()
    if row is None:
        raise LookupError(f"no ticket {other_id!r}")
    if not common.may_access_board(ctx, row["board_id"], need="WORK"):
        raise PermissionError(f"{other_id} is on a board you do not work")


def child_add(ctx, work_item_id):
    from ... import family
    child = ctx.request.form().get("child_id", "").strip().upper()

    def go():
        _other_workable(ctx, child)
        family.attach(ctx.conn, work_item_id, child, actor=ctx.user.id, at=ctx.now)
        return f"{child} is now a child of this ticket"
    return _family_change(ctx, work_item_id, go)


def child_remove(ctx, work_item_id):
    from ... import family
    child = ctx.request.form().get("child_id", "").strip().upper()

    def go():
        row = ctx.conn.execute("SELECT parent_id FROM ticket WHERE work_item_id = ?", (child,)).fetchone()
        if row is None or row["parent_id"] != work_item_id:
            raise LookupError(f"{child} is not a child of this ticket")
        family.detach(ctx.conn, child, actor=ctx.user.id, at=ctx.now)
        return f"{child} detached"
    return _family_change(ctx, work_item_id, go)


def parent_set(ctx, work_item_id):
    from ... import family
    parent = ctx.request.form().get("parent_id", "").strip().upper()

    def go():
        _other_workable(ctx, parent)
        family.attach(ctx.conn, parent, work_item_id, actor=ctx.user.id, at=ctx.now)
        return f"Now a child of {parent}"
    return _family_change(ctx, work_item_id, go)


def parent_remove(ctx, work_item_id):
    from ... import family

    def go():
        if not family.detach(ctx.conn, work_item_id, actor=ctx.user.id, at=ctx.now):
            raise LookupError("this ticket has no parent")
        return "Detached from its parent"
    return _family_change(ctx, work_item_id, go)


def change_fields_from(f) -> dict:
    return {k: f.get(k) for k in ("change_type", "change_risk", "planned_start",
                                  "planned_end", "backout_plan") if k in f}


def decide_change(ctx, work_item_id):
    from ... import itil
    tk = _load(ctx, work_item_id)
    f = ctx.request.form()
    try:
        itil.decide(ctx.conn, work_item_id, decision=f.get("decision", ""),
                    authority=f.get("authority", ""), actor=ctx.user.id, at=ctx.now,
                    comment=f.get("comment"))
        ctx.conn.commit()
    except (ValueError, PermissionError, LookupError) as exc:
        ctx.conn.rollback()
        return _back(work_item_id, err=f"Not recorded: {exc}")
    return _back(work_item_id, msg=f"Change {f.get('decision', '').lower()}")


def link(ctx, work_item_id):
    from ... import itil
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    f = ctx.request.form()
    other = f.get("linked_id", "").strip().upper()
    target = ctx.conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?",
                              (other,)).fetchone()
    # Linking needs sight of the other ticket too: no linking blind into a
    # board, restricted or not, that this user is not on.
    if target is None or target["board_id"] not in common.board_ids_for(ctx):
        return _back(work_item_id, err=f"Not linked: no ticket {other} on your boards")
    try:
        itil.link(ctx.conn, work_item_id, other, f.get("relation", ""), actor=ctx.user.id,
                  at=ctx.now)
        ctx.conn.commit()
    except (ValueError, LookupError) as exc:
        ctx.conn.rollback()
        return _back(work_item_id, err=f"Not linked: {exc}")
    return _back(work_item_id, msg=f"Linked to {other}")


def unlink(ctx, work_item_id):
    from ... import itil
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    itil.unlink(ctx.conn, work_item_id, ctx.request.form().get("linked_id", ""),
                actor=ctx.user.id, at=ctx.now)
    ctx.conn.commit()
    return _back(work_item_id, msg="Link removed")


# ------------------------------------------------------------------ tasks

def _tasks_card(ctx, tk, *, can_work: bool) -> str:
    """ConnectWise's Tasks tab: the ticket's checklist, and templates to fill it."""
    from ... import tasks
    wid = t.esc(tk["work_item_id"])
    rows = tasks.tasks_of(ctx.conn, tk["work_item_id"])
    done, total = tasks.progress(ctx.conn, tk["work_item_id"])
    dis = "" if can_work else " disabled"
    items = "".join(
        f"<li><form method=post action='/ticket/{wid}/task/toggle' style='display:inline'>"
        f"<input type=hidden name=task_id value='{r['task_id']}'>"
        f"<input type=hidden name=done value='{0 if r['done_at'] else 1}'>"
        f"<button class='ghost small' type=submit{dis} aria-label='{'Reopen' if r['done_at'] else 'Done'}: "
        f"{t.esc(r['text'])}'>{'☑' if r['done_at'] else '☐'}</button></form> "
        + (f"<s>{t.esc(r['text'])}</s> <span class=muted>{t.esc(r['done_by'])}</span>" if r["done_at"]
           else t.esc(r["text"])) + "</li>" for r in rows)
    add = ""
    if can_work:
        tpls = ctx.conn.execute("SELECT template_id, name FROM ticket_template WHERE board_id = ?"
                                " AND inactive = 0 ORDER BY name", (tk["board_id"],)).fetchall()
        add = (f"<form method=post action='/ticket/{wid}/task/add' class=row style='margin-top:8px'>"
               "<div><input name=text required placeholder='Add a task'></div>"
               "<div style='flex:0 0 auto'><button class=ghost type=submit><svg class=ic aria-hidden=true><use href=#i-plus></use></svg> Add</button></div></form>")
        if tpls:
            add += (f"<form method=post action='/ticket/{wid}/template' class=row style='margin-top:6px'>"
                    "<div><select name=template_id>"
                    + _options([(x["template_id"], x["name"]) for x in tpls], "") +
                    "</select></div><div style='flex:0 0 auto'><button class=ghost type=submit>"
                    "Apply template</button></div></form>")
    head = f"Tasks · {done} of {total}" if total else "Tasks"
    return (f"<div class=card data-pod=tasks><h3><svg class=ic aria-hidden=true><use href=#i-checks></use></svg>{head}</h3>"
            + (f"<ul class=plain>{items}</ul>" if items else "<div class=muted>No tasks.</div>")
            + add + "</div>")


def task_add(ctx, work_item_id):
    from ... import tasks
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    try:
        tasks.add_task(ctx.conn, work_item_id, ctx.request.form().get("text", ""),
                       actor=ctx.user.id, at=ctx.now)
        ctx.conn.commit()
    except ValueError as exc:
        return _back(work_item_id, err=f"Not added: {exc}")
    return _back(work_item_id, msg="Task added")


def task_toggle(ctx, work_item_id):
    from .. import HttpError
    from ... import tasks
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    f = ctx.request.form()
    task_id = int(f["task_id"]) if f.get("task_id", "").isdigit() else -1
    row = ctx.conn.execute("SELECT work_item_id FROM ticket_task WHERE task_id = ?",
                           (task_id,)).fetchone()
    if row is None or row["work_item_id"] != work_item_id:
        raise HttpError("404 Not Found", "No such task on this ticket.")
    tasks.set_done(ctx.conn, task_id, f.get("done") == "1", actor=ctx.user.id, at=ctx.now)
    ctx.conn.commit()
    return _back(work_item_id, msg="Task updated")


def template_apply(ctx, work_item_id):
    from ... import tasks
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    tid = ctx.request.form().get("template_id", "")
    ok = ctx.conn.execute("SELECT 1 FROM ticket_template WHERE template_id = ? AND board_id = ?"
                          " AND inactive = 0", (tid, tk["board_id"])).fetchone()
    if not ok:
        return _back(work_item_id, err="Not applied: no such template on this board")
    n = tasks.apply_template(ctx.conn, work_item_id, tid, actor=ctx.user.id, at=ctx.now)
    ctx.conn.commit()
    return _back(work_item_id, msg=f"Template applied: {n} task(s)" if n
                 else "That template is already on this ticket")


def _template_picker(ctx, selected: str) -> str:
    """ConnectWise's "new ticket from template": a plain GET, so it works with no script."""
    rows = ctx.conn.execute(
        "SELECT tt.template_id, tt.name, b.display_name FROM ticket_template tt"
        "  JOIN board b ON b.board_id = tt.board_id JOIN board_member m ON m.board_id = tt.board_id"
        " WHERE m.member = ? AND m.access IN ('WORK','ADMIN') AND tt.inactive = 0"
        " ORDER BY b.display_name, tt.name", (ctx.user.id,)).fetchall()
    if not rows:
        return ""
    opts = _options([("", "(blank ticket)")] + [(r["template_id"], f"{r['display_name']}: {r['name']}")
                                                for r in rows], selected)
    return ("<form method=get action='/ticket/new' class=row style='float:right;margin-top:4px'>"
            f"<div><select name=template aria-label='Start from a template'>{opts}</select></div>"
            "<div style='flex:0 0 auto'><button class=ghost type=submit>Use template</button></div></form>")
