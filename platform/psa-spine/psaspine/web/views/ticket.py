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
from ... import phi, tickets
from .. import templates as t
from . import common
from .portal import PATIENT_WAITING, WHO_IS_AFFECTED

FLAG_LABEL = {"DISCUSSION": "Discussion", "INTERNAL": "Internal", "RESOLUTION": "Resolution"}
SOURCES = (("PHONE", "Phone"), ("WALK_UP", "Walk-up"), ("EMAIL", "Email (logged by hand)"),
           ("DESK", "Desk (seen by us)"))
CHARGE_LABEL = {"INCLUDED_IN_MONTHLY_FEE": "Included in monthly fee",
                "CAPACITY_UPLIFT": "Capacity uplift", "SEPARATE_CHARGE": "Separate charge",
                "PASS_THROUGH": "Pass-through", "NON_CHARGEABLE": "Non-chargeable"}
# ConnectWise's bill options, in its words.
BILL_LABEL = {"NO_DEFAULT": "No default (the agreement decides)", "BILLABLE": "Billable",
              "DO_NOT_BILL": "Do not bill", "NO_CHARGE": "No charge"}


def _load(ctx, work_item_id):
    from .. import HttpError
    row = ctx.conn.execute(
        "SELECT t.*, w.name AS summary, w.contract_basis, w.variation_id,"
        "       w.entity_id, e.name AS entity, s.name AS status_name,"
        "       s.escalation_status, b.display_name AS board_name,"
        "       b.closed_loop_required, b.calendar_id, c.name AS calendar_name,"
        "       b.kind AS board_kind, b.notify_requester"
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
    if e["kind"] == "TIME":
        return "time entered: " + detail
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


def _time_fields(ctx, tk, *, prefix: str = "", compact: bool = False) -> str:
    """ConnectWise's time entry fields: date, start and end OR actual hours,
    deduct, work role, work type, bill option, and the spine's charge method.
    The same fields on the note composer and on the Time pod's own form."""
    defaults = engine.time_defaults(ctx.conn, board_id=tk["board_id"])
    roles = engine.work_roles(ctx.conn)
    types = engine.work_types(ctx.conn)
    today = ctx.now.date().isoformat()
    # The board's own default, else the first of each, as ConnectWise defaults them.
    role_opts = _options([(r["work_role_id"], r["name"]) for r in roles], defaults["work_role_id"] or "")
    type_opts = _options([(w["work_type_id"], w["name"]) for w in types], defaults["work_type_id"] or "")
    bill_opts = _options(list(BILL_LABEL.items()), "NO_DEFAULT")
    charge_opts = _options([("", "— choose —")] + list(CHARGE_LABEL.items()), "")
    return (
        f"<div class='timefields{' compact' if compact else ''}'>"
        f"<div><label>Date</label><input type=date name={prefix}worked_on value='{today}'></div>"
        f"<div><label>Start</label><input type=time name={prefix}start step=300></div>"
        f"<div><label>End</label><input type=time name={prefix}end step=300></div>"
        f"<div><label>Actual hours</label><input name={prefix}hours inputmode=decimal placeholder='or 1.5'></div>"
        f"<div><label>Deduct</label><input name={prefix}deduct inputmode=decimal placeholder='0'></div>"
        f"<div><label>Work role</label><select name={prefix}work_role>{role_opts}</select></div>"
        f"<div><label>Work type</label><select name={prefix}work_type>{type_opts}</select></div>"
        f"<div><label>Bill</label><select name={prefix}bill>{bill_opts}</select></div>"
        f"<div><label>Charged as</label><select name={prefix}charge>{charge_opts}</select></div>"
        "</div>")


def _time_from_form(f: dict, *, prefix: str = "") -> dict | None:
    """The time part of a posted form as add_time wants it, or None when no
    time was entered. A date with start and end times becomes two instants."""
    g = lambda k: (f.get(prefix + k) or "").strip()  # noqa: E731
    if not (g("start") or g("end") or g("hours")):
        return None
    day = g("worked_on") or None
    time = {"actual_hours": g("hours") or None, "hours_deduct": g("deduct") or 0,
            "work_role_id": g("work_role") or None, "work_type_id": g("work_type") or None,
            "billable_option": g("bill") or "NO_DEFAULT"}
    if g("start") or g("end"):
        if not day:
            raise engine.EffortRefused("a start and end time need the date")
        time["time_start"] = f"{day} {g('start')}" if g("start") else None
        time["time_end"] = f"{day} {g('end')}" if g("end") else None
    return time


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
    if tk["merged_into"]:
        msg = msg or ""
        err = err or ""
    buttons = ""
    if can_work and tk["closed_loop_required"]:
        buttons = f"<a class=btn href='/ticket/{wid}/loop'>Close the loop</a>"
    header = (
        (f"<div class='banner ok'>{t.icon('layers')} Merged into <a href='/ticket/{t.esc(tk['merged_into'])}'>"
         f"{t.esc(tk['merged_into'])}</a>; the work continues there.</div>" if tk["merged_into"] else "") +
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
        "SELECT te.*, r.name AS role_name, y.name AS type_name FROM time_entry te"
        " LEFT JOIN work_role r ON r.work_role_id = te.work_role_id"
        " LEFT JOIN work_type y ON y.work_type_id = te.work_type_id"
        " WHERE te.work_item_id = ? ORDER BY te.worked_on, te.time_entry_id", (work_item_id,)).fetchall()
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
    # ConnectWise's "Contact" tick on a note: a Discussion note emails the
    # requester unless the technician says not this one. Drawn only where the
    # board emails requesters at all.
    notify_tick = ("<label style='display:block;margin-top:6px;color:var(--ink);font-weight:500'>"
                   "<input type=checkbox name=notify value=1 checked style='width:auto'> Email the requester</label>"
                   if tk["notify_requester"] else "")
    if can_work:
        # ConnectWise's note carries its time entry; the fields are its.
        time_block = (
            "<details class=timeblock><summary>Time on this note</summary>"
            + _time_fields(ctx, tk, compact=True)
            + "<p class=why style='margin:6px 0 0'>Start and end, or the actual hours, not both; "
              "a deduction comes off. Kept to the quarter hour.</p></details>"
            if may else f"<div><label>Time</label><div class=ro>{t.esc(why_not)}</div></div>")
        from ... import canned
        std = canned.notes_for(ctx.conn, tk["board_id"])
        picker = ""
        if std:
            picker = ("<div class=row style='margin-bottom:8px'><div><label>Standard note</label>"
                      "<select id=stdnote><option value=''>(type your own)</option>" + "".join(
                          f"<option value='{n['note_id']}' data-flag='{n['flag']}' data-body='{t.esc(n['body'])}'>"
                          f"{t.esc(n['name'])}</option>" for n in std) + "</select></div></div>")
        composer = (
            "<div class=card data-pod=composer><h3><svg class=ic aria-hidden=true><use href=#i-note></use></svg>Add a note</h3>"
            f"<form method=post action='/ticket/{wid}/note'>" + picker +
            "<textarea name=body required placeholder='No patient names or case numbers (§6.1).'></textarea>"
            "<div class=row style='margin-top:10px'>"
            "<div style='flex:0 0 auto'><label>Who can read it</label><div class=seg>"
            "<label><input type=radio name=flag value=DISCUSSION checked><span>Discussion</span></label>"
            "<label class=int><input type=radio name=flag value=INTERNAL><span>Internal</span></label>"
            "</div><label style='display:block;margin-top:6px;color:var(--ink);font-weight:500'>"
            "<input type=checkbox name=resolution value=1 style='width:auto'> Also the resolution"
            "</label>" + notify_tick + "</div>"
            "<div><label>And set status</label><select name=to_status>"
            + _options([("", "(no change)")] + status_pairs, "") +
            "</select></div><div style='flex:0 0 auto'><button type=submit><svg class=ic aria-hidden=true><use href=#i-note></use></svg> Save note</button></div>"
            "</div>" + time_block +
            "<p class=why style='margin:8px 0 0'>Discussion notes, and the resolution when it "
            "is a Discussion note, are shown to the requester on their portal. Internal notes never "
            "leave the desk, even when they are the resolution.</p></form></div>")

    # Every card on the ticket is a pod, in one of two columns. The activity
    # stream and the note composer ship on the left, the rest on the right;
    # each user drags any card to either column, reorders, folds, and the
    # browser remembers. data-order on each column is the shipped layout that
    # "Reset layout" restores.
    left = (f"<div class=pods data-col=left data-order='stream,composer'>"
            f"<div class=card data-pod=stream><h3><svg class=ic aria-hidden=true><use href=#i-rows></use></svg>Activity</h3>"
            f"<div class=tabs>{tabs}</div>{stream}</div>{composer}</div>")

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

    # The Time pod is ConnectWise's Time tab: one row per entry with its date,
    # member, start–end, hours, deduct, work role and type, bill option, the
    # spine's charge method and the band it counts as; then its own Add time
    # form, with the note flags a ConnectWise time entry carries.
    actual_total = sum((r["actual_hours"] if r["actual_hours"] is not None else r["band_hours"])
                       for r in time_rows)
    band_total = sum(r["band_hours"] for r in time_rows)
    trs = "".join(
        f"<tr><td>{t.esc(r['worked_on'])}</td><td>{t.esc(r['performed_by'])}</td>"
        f"<td>{t.esc((r['time_start'] or '')[11:] + ('–' + r['time_end'][11:] if r['time_end'] else '') or '—')}</td>"
        f"<td class=num>{(r['actual_hours'] if r['actual_hours'] is not None else r['band_hours']):g}</td>"
        f"<td class=num>{(r['hours_deduct'] or 0):g}</td>"
        f"<td>{t.esc(r['role_name'] or '—')}</td><td>{t.esc(r['type_name'] or '—')}</td>"
        f"<td>{t.esc(BILL_LABEL.get(r['billable_option'] or 'NO_DEFAULT', '').split(' (')[0])}</td>"
        f"<td>{t.esc(CHARGE_LABEL.get(r['charge_method'], r['charge_method']))}</td>"
        f"<td class=num>{r['band_hours']:g}</td></tr>" for r in time_rows)
    time_table = (
        "<div class=tablewrap><table class=compact><thead><tr><th>Date</th><th>Member</th><th>Start–End</th>"
        "<th>Hours</th><th>Deduct</th><th>Work role</th><th>Work type</th><th>Bill</th><th>Charged as</th>"
        f"<th>Band</th></tr></thead><tbody>{trs}</tbody></table></div>"
        if trs else "<div class=muted>No time yet.</div>")
    time_form = ""
    if can_work and may:
        time_form = (
            f"<details class=timeblock><summary>{t.icon('plus')} Add time</summary>"
            f"<form method=post action='/ticket/{wid}/time'>" + _time_fields(ctx, tk)
            + "<div class=row style='margin-top:8px'><div><label>Notes</label>"
              "<textarea name=body rows=2 placeholder='What was done. No patient names or case numbers (§6.1).'></textarea></div>"
              "<div style='flex:0 0 auto'><label>Who can read the notes</label><div class=seg>"
              "<label><input type=radio name=flag value=DISCUSSION checked><span>Discussion</span></label>"
              "<label class=int><input type=radio name=flag value=INTERNAL><span>Internal</span></label>"
              "</div><label style='display:block;margin-top:6px;color:var(--ink);font-weight:500'>"
              "<input type=checkbox name=resolution value=1 style='width:auto'> Also the resolution</label>"
              + notify_tick + "</div>"
              "<div style='flex:0 0 auto'><button type=submit>" + t.icon("clock") + " Save time</button></div></div>"
              "<p class=why style='margin:6px 0 0'>Start and end, or the actual hours, not both; a deduction "
              "comes off; kept to the quarter hour. The band is the smallest of 0.5 / 2 / 4 / 8 / 20 h the "
              "hours fit in, and is what the capacity arithmetic counts.</p></form></details>")
    time_card = (f"<div class=card data-pod=time><h3><svg class=ic aria-hidden=true><use href=#i-clock></use></svg>"
                 f"Time · {actual_total:g} h" + (f" (band {band_total:g} h)" if time_rows else "") + "</h3>"
                 + time_table + time_form
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
               + _schedule_card(ctx, tk, can_work=can_work) + _tasks_card(ctx, tk, can_work=can_work)
               + file_views.ticket_card(ctx, tk, can_work=can_work) + _links_card(ctx, tk, can_work=can_work) + configs)
    body = header + strip + (f"<div class=rail>{left}<div class=pods data-col=right data-order='ticket,change,family,"
                             f"schedule,tasks,files,links,configurations,time,commercial,details'>{fields}{configs}{time_card}"
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
    try:
        engine.add_note(ctx.conn, work_item_id, body=f.get("body", ""),
                        flag=f.get("flag", "DISCUSSION") or "DISCUSSION",
                        actor=ctx.user.id, at=ctx.now,
                        time=_time_from_form(f),
                        charge_method=f.get("charge") or None,
                        to_status_id=f.get("to_status") or None,
                        resolution=f.get("resolution") == "1",
                        notify_requester=not tk["notify_requester"] or f.get("notify") == "1")
        # §6.1: a technician's note is an intake path too. Saved, and flagged by
        # shape, never by value; a Discussion note reaches the portal and mail.
        for code, severity, detail in phi.scan_fields({"note": f.get("body", "")}):
            ctx.conn.execute(
                "INSERT INTO data_quality (run_id, subject_kind, subject_id, code, detail,"
                " severity) VALUES (?,?,?,?,?,?)", ("desk", "ticket", work_item_id, code, detail, severity))
        ctx.conn.commit()
    except (ValueError, LookupError, engine.EffortRefused, engine.NotOnThisBoard) as exc:
        ctx.conn.rollback()
        return _back(work_item_id, err=f"Note not saved: {exc}")
    except Exception as exc:                                 # a gate trigger refused it
        ctx.conn.rollback()
        return _back(work_item_id, err=f"Note not saved: {exc}")
    return _back(work_item_id, msg="Note saved")


def add_time(ctx, work_item_id):
    """POST /ticket/<id>/time: ConnectWise's Add time. With notes it is a note
    that carries the time (one write, refused whole); without, a bare entry."""
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    f = ctx.request.form()
    body = f.get("body", "").strip()
    try:
        time = _time_from_form(f)
        if time is None:
            raise engine.EffortRefused("enter a start and end time, or the actual hours")
        if body:
            r = engine.add_note(ctx.conn, work_item_id, body=body,
                                flag=f.get("flag", "DISCUSSION") or "DISCUSSION",
                                actor=ctx.user.id, at=ctx.now, time=time,
                                charge_method=f.get("charge") or None,
                                resolution=f.get("resolution") == "1",
                                notify_requester=not tk["notify_requester"] or f.get("notify") == "1")
            hours = r["actual_hours"]
            for code, severity, detail in phi.scan_fields({"note": body}):
                ctx.conn.execute(
                    "INSERT INTO data_quality (run_id, subject_kind, subject_id, code, detail,"
                    " severity) VALUES (?,?,?,?,?,?)", ("desk", "ticket", work_item_id, code, detail, severity))
        else:
            values = engine.prepare_time(ctx.conn, work_item_id, charge_method=f.get("charge") or None,
                                         **time)
            engine.add_time(ctx.conn, work_item_id, at=ctx.now, actor=ctx.user.id,
                            charge_method=values["charge_method"], values=values)
            hours = values["actual_hours"]
        ctx.conn.commit()
    except (ValueError, LookupError, engine.EffortRefused, engine.NotOnThisBoard) as exc:
        ctx.conn.rollback()
        return _back(work_item_id, err=f"Time not saved: {exc}")
    except Exception as exc:                                 # a gate trigger refused it
        ctx.conn.rollback()
        return _back(work_item_id, err=f"Time not saved: {exc}")
    return _back(work_item_id, msg=f"Time saved: {hours:g} h")


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
    v = values or {k: ctx.request.query[k] for k in ("board_id", "entity_id", "requested_by", "configuration_id")
                   if ctx.request.query.get(k)}
    machine = None
    if v.get("configuration_id"):
        machine = ctx.conn.execute("SELECT configuration_id, name FROM configuration WHERE configuration_id = ?",
                                   (v["configuration_id"],)).fetchone()
        if machine is None:
            v.pop("configuration_id")
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
           if v.get("template_id") else "")
        + (f"<input type=hidden name=configuration_id value='{t.esc(machine['configuration_id'])}'>"
           f"<p class=why style='margin:0 0 8px'>{t.icon('monitor')} For the machine <b>{t.esc(machine['name'])}</b>; "
           "it is attached when the ticket is created.</p>" if machine else "") + "<div class=grid2>"
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
        if f.get("configuration_id"):
            from ... import configurations as cmdb
            try:
                cmdb.attach(ctx.conn, wid, f["configuration_id"], at=ctx.now, actor=ctx.user.id)
            except LookupError:
                pass                               # a machine that vanished is not a reason to lose the ticket
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
        body += f"<p class=why>{hidden} more not listed here: on a restricted board, or one you are not on. Open them from that board.</p>"
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
               else f"{t.esc(parent['work_item_id'])} <span class=muted>on a restricted board, or one you are not on</span>")
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
        body += f"<p class=why>{hidden} more not listed here: on a restricted board, or one you are not on. Open them from that board.</p>"
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
    if can_work and not tk["closed_at"] and not tk["merged_into"]:
        forms += (f"<form method=post action='/ticket/{wid}/merge' class=row style='margin-top:10px;"
                  "padding-top:10px;border-top:1px solid var(--line)'>"
                  "<div><input name=into placeholder='Duplicate? Merge into: PMC-000123' required></div>"
                  "<div style='flex:0 0 auto'><button class=ghost type=submit>" + t.icon("layers")
                  + " Merge</button></div>"
                  "<p class=why style='flex-basis:100%;margin:0'>This ticket closes; its notes, files and "
                  "links go to the other one. A Discussion note arrives as Internal unless both have the "
                  "same requester.</p></form>")
    head = f"Children · {len(kids)}" if kids else "Children"
    return f"<div class=card data-pod=family><h3>{t.icon('layers')}{t.esc(head)}</h3>{body}{forms}</div>"


def _schedule_card(ctx, tk, *, can_work: bool) -> str:
    from ... import schedule
    wid = t.esc(tk["work_item_id"])
    rows = schedule.entries_for(ctx.conn, tk["work_item_id"])
    items = "".join(
        f"<li><b>{t.esc(r['member'])}</b> · {t.esc(r['starts_at'])} → {t.esc(r['ends_at'][11:])}"
        + (f" <span class=muted>{t.esc(r['note'])}</span>" if r["note"] else "")
        + ((f" <form method=post action='/ticket/{wid}/schedule/remove' style='display:inline'>"
            f"<input type=hidden name=schedule_id value='{r['schedule_id']}'>"
            "<button class='ghost small' type=submit title='Cancel this visit'>×</button></form>")
           if can_work else "") + "</li>" for r in rows)
    add = ""
    if can_work and not tk["closed_at"]:
        start = ctx.now.replace(minute=0, second=0, microsecond=0)
        add = (f"<form method=post action='/ticket/{wid}/schedule/add' class=grid2 style='margin-top:8px'>"
               f"<div><label>Who</label><input name=member value='{t.esc(tk['owner'] or '')}' required></div>"
               "<div><label>Note</label><input name=note placeholder='Ward 3, bring toner'></div>"
               f"<div><label>From</label><input type=datetime-local name=starts_at value='{start.strftime('%Y-%m-%dT%H:%M')}' required></div>"
               f"<div><label>To</label><input type=datetime-local name=ends_at required></div>"
               "<div style='grid-column:1/-1'><button class=ghost type=submit>" + t.icon("calendar")
               + " Schedule the visit</button></div></form>")
    head = f"Schedule · {len(rows)}" if rows else "Schedule"
    return (f"<div class=card data-pod=schedule><h3>{t.icon('calendar')}{t.esc(head)}</h3>"
            + (f"<ul class=plain>{items}</ul>" if items else "<div class=muted>No visits booked.</div>")
            + add + "</div>")


def schedule_add(ctx, work_item_id):
    from ... import schedule
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    f = ctx.request.form()
    try:
        schedule.add(ctx.conn, work_item_id, member=f.get("member", ""),
                     starts_at=schedule.parse_local(f.get("starts_at", "")),
                     ends_at=schedule.parse_local(f.get("ends_at", "")), note=f.get("note"),
                     actor=ctx.user.id, at=ctx.now)
        ctx.conn.commit()
    except (schedule.Refused, LookupError) as exc:
        return _back(work_item_id, err=f"Not scheduled: {exc}")
    return _back(work_item_id, msg="Visit scheduled")


def schedule_remove(ctx, work_item_id):
    from ... import schedule
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    sid = ctx.request.form().get("schedule_id", "")
    row = ctx.conn.execute("SELECT work_item_id FROM ticket_schedule WHERE schedule_id = ?",
                           (sid,)).fetchone() if sid.isdigit() else None
    if row is None or row["work_item_id"] != work_item_id:
        return _back(work_item_id, err="No such visit on this ticket")
    schedule.remove(ctx.conn, int(sid), actor=ctx.user.id, at=ctx.now)
    ctx.conn.commit()
    return _back(work_item_id, msg="Visit cancelled")


def merge(ctx, work_item_id):
    from ... import family
    into = ctx.request.form().get("into", "").strip().upper()

    def go():
        _other_workable(ctx, into)
        r = family.merge(ctx.conn, work_item_id, into, actor=ctx.user.id, at=ctx.now)
        return (f"Merged into {into}: {r['notes']} note(s) copied, {r['files']} file(s) moved"
                + ("" if r["same_requester"] else "; Discussion notes arrived as Internal"))
    return _family_change(ctx, work_item_id, go)


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
