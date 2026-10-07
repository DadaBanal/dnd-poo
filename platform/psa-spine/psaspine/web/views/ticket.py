"""The ticket — one screen, laid out the way a Dada PSA technician expects.

Header: id, summary, board, status, priority and WHY it is that priority (the
matrix computed it; nobody typed it). Under it, one box per SLA clock —
Respond, Resolution plan, Resolve — with its target, where it stands, and a bar.

Left: the notes, each flagged the Dada PSA way — Discussion (the requester
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
from datetime import timedelta

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
# Dada PSA's bill options, in its words.
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
    _remember_back(ctx)          # where the form came from (a ticket tab, Dispatch), set afresh each request
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


REQ = " <span class=req title='Required' aria-hidden=true>*</span>"
REQUIRED_SAY = ("Company, Ticket type and the Type › Subtype › Item are required"
                " (Dada, 6 Oct 2026); fill them in and save again")


def _catalogue_select(conn, board_id, selected, *, disabled="", required: bool = False) -> str:
    """Type, then Subtype, then Item: three dependent selects, as the reference
    PSA asks them (SQL01's spec to WS36, 2 Oct 2026). Picking a Type shows its
    Subtypes; picking a Subtype shows its Items; what is submitted is still the
    one `catalogue_item_id` the third carries, so nothing behind this changed.

    The third select holds every live pair, each option carrying its Type and
    Subtype, and it is the only one with a name. That is deliberate: with no
    script at all the page still shows one working dropdown, grouped by Type and
    labelled in full, exactly as it was before today. The script reads those two
    attributes to fill the first two selects and to narrow what the third
    offers; it never invents a choice the server did not send.
    """
    from ... import setup
    choices = setup.catalogue_choices(conn, board_id)
    if selected and all(c["catalogue_item_id"] != selected for c in choices):
        # A pair retired in Setup › Catalogue stays on the ticket that carries
        # it: offered here as itself, marked, so a save does not silently clear it.
        kept = conn.execute(
            "SELECT i.catalogue_item_id, f.display_name AS type, c.display_name AS subtype,"
            "       a.display_name || ' (retired)' AS item, a.kind, i.default_board_id"
            "  FROM catalogue_item i JOIN service_component c ON c.component_id = i.component_id"
            "  JOIN service_family f ON f.family_id = c.family_id"
            "  JOIN service_action a ON a.action_id = i.action_id WHERE i.catalogue_item_id = ?",
            (selected,)).fetchone()
        if kept is not None:
            choices = choices + [dict(kept) | {"on_board": kept["default_board_id"] == board_id}]
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
                        f" data-f='{t.esc(c['type'])}' data-s='{t.esc(c['subtype'])}'"
                        f" data-i='{t.esc(c['item'])}'"
                        f"{' selected' if c['catalogue_item_id'] == selected else ''}>"
                        f"{t.esc(c['subtype'])} › {t.esc(c['item'])}</option>")
        opts.append("</optgroup>")
    # The two narrowing selects carry no name: they are not part of the form's
    # answer, only of how a person reaches it. `hidden` until the script has
    # filled them, so a page without one never shows two empty boxes.
    star, req = (REQ, " required") if required and not disabled else ("", "")
    return (f"<label>Type{star}</label><select class=cat-type aria-label='Type'"
            f" hidden{disabled}></select>"
            f"<label>Subtype{star}</label><select class=cat-sub aria-label='Subtype'"
            f" hidden{disabled}></select>"
            f"<label>Item{star}</label>"
            f"<select name=catalogue_item_id class=cat-item{disabled}{req}>"
            + "".join(opts) + "</select>")


def _type_select(conn, board_id: str | None, selected: str | None, *, disabled: str = "",
                 blank: str | None = None, required: bool = False) -> str:
    """The board's Types (Dada PSA's Types tab): Incident, Request, Problem,
    Event on a service board. With no board, every Type."""
    from ... import itil
    rows = [r["record_type"] for r in itil.boards_types(conn, board_id)] if board_id else []
    types = rows or list(itil.RECORD_TYPES)
    if selected and selected not in types:
        types.insert(0, selected)
    pairs = ([("", blank)] if blank else []) + [(x, itil.LABEL[x]) for x in types]
    # "Ticket type", not "Type": the catalogue cascade below it already owns the
    # word Type (service_family), and two fields labelled the same confused the
    # ward (SQL01's #3 to WS36, 2 Oct 2026). This one is the ITIL record kind --
    # Incident, Request, Problem, Event -- so it is the ticket's type; the
    # cascade stays Type -> Subtype -> Item.
    if required and not disabled:
        return (f"<label>Ticket type{REQ}</label><select name=record_type required>"
                + _options([("", "(choose one)")] + [p for p in pairs if p[0]], selected or "") + "</select>")
    return (f"<label>Ticket type</label><select name=record_type{disabled}>"
            + _options(pairs, selected or "") + "</select>")


def _time_fields(ctx, tk, *, prefix: str = "", compact: bool = False,
                 prefill: dict | None = None) -> str:
    """Dada PSA's time entry fields: date, start and end OR actual hours,
    deduct, work role, work type, bill option, and the spine's charge method.
    The same fields on the note composer and on the Time pod's own form.

    `prefill` is what a stopped stopwatch measured (065): the date, the start
    and the end it actually ran between. They arrive filled in rather than
    recalled, and the technician may still correct any of them before saving,
    because the timer is evidence and the entry is the claim.
    """
    defaults = engine.time_defaults(ctx.conn, board_id=tk["board_id"])
    roles = engine.work_roles(ctx.conn)
    types = engine.work_types(ctx.conn)
    today = ctx.now.date().isoformat()
    p = prefill or {}
    worked_on = p.get("worked_on") or today
    at_start, at_end = p.get("time_start", ""), p.get("time_end", "")
    # The board's own default, else the first of each, as Dada PSA defaults them.
    role_opts = _options([(r["work_role_id"], r["name"]) for r in roles], defaults["work_role_id"] or "")
    type_opts = _options([(w["work_type_id"], w["name"]) for w in types], defaults["work_type_id"] or "")
    bill_opts = _options(list(BILL_LABEL.items()), "NO_DEFAULT")
    charge_opts = _options(list(CHARGE_LABEL.items()), engine.DEFAULT_CHARGE)
    return (
        f"<div class='timefields{' compact' if compact else ''}'>"
        f"<div><label>Date</label><input type=date name={prefix}worked_on value='{t.esc(worked_on)}'></div>"
        # Any minute is a valid time. A 5-minute step counted from the value the
        # box arrived with (a clock started at 16:27) made 16:40 "invalid", and
        # the browser then refused Save without a word on the page (Dada, 6 Oct
        # 2026: "time entries when saved isnt saving anywhere"). The desk keeps
        # the entry to the quarter hour itself.
        f"<div><label>Start</label><input type=time name={prefix}start step=60 value='{t.esc(at_start)}'></div>"
        f"<div><label>End</label><input type=time name={prefix}end step=60 value='{t.esc(at_end)}'></div>"
        f"<div><label>Actual hours</label><input name={prefix}hours inputmode=decimal placeholder='or 1.5'></div>"
        f"<div><label>Deduct</label><input name={prefix}deduct inputmode=decimal placeholder='0'></div>"
        f"<div><label>Work role</label><select name={prefix}work_role>{role_opts}</select></div>"
        f"<div><label>Work type</label><select name={prefix}work_type>{type_opts}</select></div>"
        f"<div><label>Bill</label><select name={prefix}bill>{bill_opts}</select></div>"
        # Charged as starts on Included in monthly fee and holds nothing up
        # (Dada, 6 Oct 2026: "remove the charge as dependency"; a blank one had
        # refused the Save after the notes were typed).
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


def _raised_by(ctx, work_item_id: str) -> str:
    """047: the recurrence that raised this ticket, if one did."""
    row = ctx.conn.execute("SELECT r.name FROM ticket tk JOIN recurrence r ON r.recurrence_id = tk.recurrence_id"
                           " WHERE tk.work_item_id = ?", (work_item_id,)).fetchone()
    return f"<dt>Raised by</dt><dd>the recurrence {t.esc(row[0])}</dd>" if row else ""


def _quick_bar(wid: str, person, can_work: bool) -> str:
    """The phone's bottom bar (gap 5): the board, a note, the ticket card, and a
    call to the contact when the desk knows their number. CSS shows it under
    640 px only; on a desk it is not there."""
    phone = (person["phone"] or "").strip() if person is not None else ""
    tel = re.sub(r"[^0-9+]", "", phone)
    items = [("/", "board", "Board")]
    if can_work:
        items += [(f"/ticket/{wid}#composer", "note", "Note"), (f"/ticket/{wid}#ticketcard", "ticket", "Ticket")]
    if tel and len(tel) >= 5:
        items.append((f"tel:{tel}", "oncall", "Call"))
    return "<nav class=quick aria-label='Quick actions'>" + "".join(
        f"<a href='{t.esc(href)}'>{t.icon(ic)}<span>{label}</span></a>" for href, ic, label in items) + "</nav>"


ORDER_COOKIE = "psa_order"


def detail(ctx, work_item_id):
    from .. import Response
    tk = _load(ctx, work_item_id)
    wid = t.esc(work_item_id)
    msg = ctx.request.query.get("msg", "")
    err = ctx.request.query.get("err", "")
    tab = ctx.request.query.get("tab", "ALL")
    # Oldest first or newest first (Dada, 6 Oct 2026: "add a way to sort
    # messages by earliest first then to the newest on tickets"). The URL says
    # which when someone just chose; otherwise the choice this browser made
    # last time, kept in a cookie for a year; otherwise oldest first, the way
    # the desk has always read and the way a conversation is told.
    chosen = ctx.request.query.get("order", "")
    remembered = ctx.request.cookies.get(ORDER_COOKIE)
    order = (chosen if chosen in ("old", "new") else
             remembered.value if remembered is not None and remembered.value in ("old", "new") else "old")

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
    # The reference PSA's Owner and Resources: the owner is the point of contact;
    # the resources are the people scheduled on it (its schedule entries). The
    # owner defaults to the first resource scheduled and can always be changed.
    from ... import members as _members, resources as _resources
    resources = _resources.everyone(ctx.conn, work_item_id)
    resources_line = (" · <span class=pill title='The people on this ticket: assigned, or with a visit booked'>resources: "
                      + t.esc(", ".join(_members.name_of(ctx.conn, m) for m in resources)) + "</span>" if resources else "")
    if can_work and not tk["closed_at"]:
        me_owner = (tk["owner"] or "").lower() == ctx.user.id.lower()
        buttons += ("" if me_owner else
                    f" <form method=post action='/ticket/{wid}/update' class=inline><input type=hidden name=owner value='{t.esc(ctx.user.id)}'>"
                    "<button class='ghost' type=submit title='Take ownership; no visit is booked'>Assign me</button></form>")
        buttons += (" <a class='btn ghost' href='#schedadd' title='Book yourself a time on it; it becomes yours if "
                    "nobody has it'>Schedule me</a>")
    # The reference PSA's Screen Layout gear and its Pod Configuration
    # (VERIFIED 1 Oct 2026 against the vendor's and three integrators' guides:
    # a gear on the ticket, Pod Configuration, Available and Displayed, drag
    # to arrange). Which cards show, in what order, at what size and height
    # is this person's own and lives in their browser; the dialog's lists are
    # built from the cards on the page.
    if can_work:
        buttons += (" <button type=button class='btn ghost' data-open=composer title='A note with no time: a reply,"
                    " an update, a question'>" + t.icon("note") + " New note</button>")
    buttons += "%%TEBUTTON%%"
    buttons += (" <button type=button class='iconbtn' data-layedit aria-pressed=false"
                " title='Edit layout: move the cards about' aria-label='Edit layout'>" + t.icon("grip") + "</button>"
                " <button type=button class='iconbtn' data-open=poddlg title='Screen layout: which cards show, and where'"
                " aria-label='Screen layout'>" + t.icon("setup") + "</button>")
    pod_dialog = (
        "<dialog id=poddlg class=card style='max-width:640px;width:95%'><form method=dialog class=dlghead>"
        "<h3 style='margin:0'>" + t.icon("setup") + "Pod configuration</h3>"
        "<button type=submit class=iconbtn aria-label=Close>" + t.icon("x") + "</button></form>"
        "<p class=why>Tick the cards you want on this ticket screen and put them in order. To move one about, close "
        "this and press <b>Edit layout</b> beside it: the cards sit still until you do, so a stray drag cannot move "
        "one while you are reading. Yours alone, in this browser.</p><div class=grid2><div><h4>Displayed</h4><ul class='plain podlist' data-list=on></ul></div>"
        "<div><h4>Available</h4><ul class='plain podlist' data-list=off></ul></div></div>"
        "<p class=row style='margin-top:12px;gap:8px'><button type=button class=podsave>Save</button>"
        "<button type=button class='ghost podreset-all'>Reset layout</button></p></dialog>")
    header = (
        (f"<div class='banner ok'>{t.icon('layers')} Merged into <a href='/ticket/{t.esc(tk['merged_into'])}'>"
         f"{t.esc(tk['merged_into'])}</a>; the work continues there.</div>" if tk["merged_into"] else "") +
        (f"<div class='banner ok toast'>{t.icon('check')} {t.esc(msg)}</div>" if msg else "") +
        (f"<div class='banner err toast'>{t.icon('alert')} {t.esc(err)}</div>" if err else "") +
        "<a class=backbtn data-back href='/' title='Back to the Service Board'>" + t.icon("left")
        + "<span class=lbl>Back to the Service Board</span></a>"
        "<div class=hdr><div class=grow>"
        f"<h1 class=sumline>{wid}<span class=sumtext> · {t.esc(tk['summary'])}</span>"
        + (f" <button type=button class='iconbtn sumedit' data-edit=summary title='Edit the summary'>{t.icon('edit')}</button>"
           f"<form method=post action='/ticket/{wid}/update' class='inline sumform' hidden>"
           f"<input name=summary required maxlength=200 value='{t.esc(tk['summary'])}' aria-label='Summary'>"
           f" <button type=submit>Save</button> <button type=button class=ghost data-edit=cancel>Cancel</button></form>"
           if can_work and not tk["merged_into"] else "")
        + "</h1>"
        f"<p class=sub>{t.esc(tk['board_name'])} · "
        f"{t.chip(tk['status_name'] or tk['state'].replace('_', ' ').title())} · "
        f"{t.badge(tk['priority'])} <span class=why>{t.esc(t.priority_name(tk['priority']))} · {t.esc(why)}</span>"
        + (f" · <span class=pill>{t.esc(klass)}</span>" if klass else "")
        + resources_line + "</p></div>"
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
        "SELECT ticket_event_id, occurred_at, kind, actor, detail, note_flag, is_resolution, body_format FROM ticket_event"
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
    # Time entries have a tab of their own (6 Oct 2026): the booking line, and
    # the note an entry was written with.
    timed = {r["ticket_event_id"] for r in time_rows if r["ticket_event_id"]}
    is_time = lambda e: e["kind"] == "TIME" or e["ticket_event_id"] in timed  # noqa: E731
    counts["TIME"] = sum(1 for e in events if e["kind"] == "TIME")
    tabs = "".join(
        f"<a class='{'on' if tab == key else ''}' href='/ticket/{wid}?tab={key}'>"
        f"{label} {counts[key]}</a>"
        for key, label in (("ALL", "All"), ("DISCUSSION", "Discussion"), ("INTERNAL", "Internal"),
                           ("RESOLUTION", "Resolution"), ("TIME", "Time"), ("SYSTEM", "System")))
    tabs += ("<span class=wholegend aria-hidden=true><i class=staff></i>PMO staff<i class=req></i>Requester</span>")
    flip = "new" if order == "old" else "old"
    tabs += (f"<a class=order href='/ticket/{wid}?tab={t.esc(tab)}&amp;order={flip}' data-order='{order}'"
             f" title='{'Oldest first: click for newest first' if order == 'old' else 'Newest first: click for oldest first'}'"
             f" aria-label='Sort the activity {'newest' if order == 'old' else 'oldest'} first'>"
             + t.icon("up" if order == "new" else "down")
             + f"<span>{'Oldest first' if order == 'old' else 'Newest first'}</span></a>")
    def _fmt(row):
        try:
            return row["body_format"]
        except (KeyError, IndexError):
            return None                      # a store that has not taken 064 yet

    # An email's inline pictures, by Content-ID, as this desk may see them (066).
    pictures = t.desk_images(ctx.conn, work_item_id)
    is_staff = _members.staff_test(ctx.conn)
    items = []
    for e in (reversed(events) if order == "new" else events):
        flag = e["note_flag"]
        if tab == "SYSTEM" and flag:
            continue
        if tab == "RESOLUTION" and not is_res(e):
            continue
        if tab in ("DISCUSSION", "INTERNAL") and flag != tab:
            continue
        if tab == "TIME" and not is_time(e):
            continue
        if flag:
            extra = ("<span class='flag RESOLUTION'>Resolution</span>"
                     if e["is_resolution"] and flag != "RESOLUTION" else "")
            # Who wrote it, by colour and in words (6 Oct 2026): PMO staff in
            # the desk's blue, the requester's side in teal. An Internal note
            # keeps its amber; only staff write those.
            # The person who asked is the requester on their own ticket, even
            # when they are staff; anyone else the desk knows is staff, by
            # whichever door their words came in.
            staff = (is_staff(e["actor"])
                     and (e["actor"] or "").strip().lower() != (tk["requested_by"] or "").strip().lower())
            who = "staff" if staff else "req"
            items.append(
                f"<div class='note {flag} by-{who}'><div class=h><span class=av>{t.esc(_initials(e['actor']))}</span>"
                f"<b>{t.esc(e['actor'] or '—')}</b>"
                f"<span class='who {who}'>{'PMO staff' if staff else 'Requester'}</span>"
                f"<span class='flag {flag}'>{FLAG_LABEL[flag]}</span>{extra}"
                f"{t.esc(e['occurred_at'])} · {t.esc(e['kind'].replace('_', ' ').lower())}"
                "<button type=button class='iconbtn copy' data-copy title='Copy this note' aria-label='Copy this note'>"
                + t.icon("copy") + "</button></div>"
                f"<div class=rtx>{t.note_html(e['detail'], _fmt(e), kind=e['kind'], images=pictures, label='Email from ' + (e['actor'] or 'the requester'))}</div></div>")
        elif e["kind"] == "TIME":
            # A booking reads as one, not as a grey system line among the emails.
            items.append(f"<div class='sys time'>{t.icon('clock')}<b>Time entry</b> · {t.esc(e['occurred_at'])} · "
                         f"{t.esc(e['actor'] or 'system')} · {t.esc(_system_line(ctx.conn, e))}</div>")
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
    # Dada PSA's "Contact" tick on a note: a Discussion note emails the
    # requester unless the technician says not this one. Drawn only where the
    # board emails requesters at all.
    notify_tick = ("<label style='display:block;margin-top:6px;color:var(--ink);font-weight:500'>"
                   "<input type=checkbox name=notify value=1 checked style='width:auto'> Email the requester</label>"
                   if tk["notify_requester"] else "")
    if can_work:
        # Dada PSA's note carries its time entry; the fields are its.
        time_block = (
            "<details class=timeblock><summary>Time on this note</summary>"
            + _time_fields(ctx, tk, compact=True)
            + "<p class=why style='margin:6px 0 0'>Start and end fill in the actual hours; a start and the "
              "actual hours fill in the end. A deduction comes off. Kept to the quarter hour.</p></details>"
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
            # A window, not a card on the page (Dada, 6 Oct 2026: "add note is
            # still there that is redundant"): the reference PSA's New Note,
            # beside its New Time Entry, moved and resized the same way. A note
            # with no time still needs a home -- a reply to a ward -- so it
            # opens from the header instead of sitting under the activity.
            "<dialog id=composer class='card tedlg notedlg'>"
            f"<form method=post action='/ticket/{wid}/note' class='noting teform' enctype='multipart/form-data'>"
            "<div class=tehead data-drag title='Drag to move'><div><h3 style='margin:0'>" + t.icon("note") + " New note</h3>"
            f"<div class=muted style='font-size:12.5px'>{wid} · {t.esc(tk['summary'])}</div></div>"
            "<span class=tewin><button type=button class=iconbtn data-close=composer aria-label='Close' title='Close; what you typed stays'>"
            "<b style='font-size:16px;line-height:1'>&#8211;</b></button>"
            "<button type=button class=iconbtn data-max=composer aria-label='Make the window larger' title='Larger / smaller'>"
            "<b style='font-size:14px;line-height:1'>&#9634;</b></button></span></div>" + picker
            # A note is written the way a Teams reply is (064; fonts, colours,
            # pictures and GIFs 6 Oct 2026): one editor component, shared with
            # the time entry window. Nothing is stored until richtext.clean has
            # rebuilt it, and pictures go through the files' review.
            + t.note_editor(placeholder="Type a note. What you found, what you did, what is next. The ward, room and "
                            "machine say it best; a patient never needs naming (§6.1).") +
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
            "leave the desk, even when they are the resolution.</p></form></dialog>")

    # Every card on the ticket is a pod, in one of two columns. The activity
    # stream and the note composer ship on the left, the rest on the right;
    # each user drags any card to either column, reorders, folds, and the
    # browser remembers. data-order on each column is the shipped layout that
    # "Reset layout" restores.
    left = (f"<div class=pods data-col=left data-order='stream'>"
            f"<div class=card data-pod=stream><h3><svg class=ic aria-hidden=true><use href=#i-rows></use></svg>Activity</h3>"
            f"<div class=tabs>{tabs}</div>{stream}</div></div>")

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
    from ... import cc as _cc
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
        "<div class='card fields' data-pod=ticket id=ticketcard><h3><svg class=ic aria-hidden=true><use href=#i-ticket></use></svg>Ticket</h3>"
        # data-savebar: these fields are one save, and the bar that follows the
        # page down submits this very form (Dada, 3 Oct 2026: "one save button
        # for all"). It adds no second way to save; it only keeps the one.
        f"<form id=ticketfields data-savebar method=post action='/ticket/{wid}/update'>"
        f"<label>Board</label><select name=board_id{dis}>{_options(board_pairs, tk['board_id'])}</select>"
        f"<label>Status</label><select name=to_status{dis}>"
        f"{_options(([] if tk['board_status_id'] else [('', '(none)')]) + status_pairs, tk['board_status_id'] or '')}</select>"
        f"<label>Owner</label>" + common.owner_select(ctx.conn, [tk["board_id"]], tk["owner"], attrs=dis, me=ctx.user.id)
        + _resource_picker(ctx, tk, can_work=can_work)
        + ("<input type=hidden name=fields value=1>" if can_work else "")
        + f"<label>Company{REQ if can_work else ''}</label><select name=entity_id{dis}{' required' if can_work else ''}>"
        f"{_options([('', '(choose a company)')] + [(e['entity_id'], e['name']) for e in entities], tk['entity_id'] or '')}</select>"
        f"<label>Contact</label><input name=requested_by list=contacts-ticket "
        f"value='{t.esc(tk['requested_by'] or '')}'{dis}>"
        + _contact_list(ctx.conn, "contacts-ticket", tk["entity_id"]) + person_line
        + f"<label>Cc</label><input name=cc value='{t.esc(', '.join(_cc.of(ctx.conn, work_item_id)))}'"
          f" placeholder='addresses, separated by commas' title='They get the emails the requester gets'{dis}>"
        + _type_select(ctx.conn, tk["board_id"], tk["record_type"], disabled=dis,
                       blank=None if tk["record_type"] else "(not set)", required=can_work)
        + _catalogue_select(ctx.conn, tk["board_id"], tk["catalogue_item_id"], disabled=dis, required=can_work) +
        f"<label>Who is affected</label><select name=impact{dis}>{_options(WHO_IS_AFFECTED, tk['impact'])}</select>"
        f"<label>Is a patient waiting</label><select name=urgency{dis}>{_options(PATIENT_WAITING, tk['urgency'])}</select>"
        f"<label>Priority</label><div class=ro>{t.badge(tk['priority'])} "
        + ("set by hand" if tk["priority_source"] == "OVERRIDE" else "from the matrix") + "</div>"
        + (f"<select name=priority aria-label='Change the priority'{dis}>"
           + _options([("", "Keep it as it is")]
                      + ([("MATRIX", "Give it back to the matrix")] if tk["priority_source"] == "OVERRIDE" else [])
                      + [(p, f"Set it to {t.priority_name(p)}") for p in ("P1", "P2", "P3", "P4")], "")
           + "</select><input name=priority_reason maxlength=200 placeholder='why (optional)'"
           f"{dis} style='margin-top:6px'>" if can_work else "")
        + ("<div style='margin-top:12px'><button type=submit><svg class=ic aria-hidden=true><use href=#i-check></use></svg> Save changes</button></div>" if can_work else "")
        + "</form></div>")

    # The Time pod is Dada PSA's Time tab: one row per entry with its date,
    # member, start–end, hours, deduct, work role and type, bill option, the
    # spine's charge method and the band it counts as; then its own Add time
    # form, with the note flags a Dada PSA time entry carries.
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
    # The time entry window (Dada, 6 Oct 2026: "time entry clock like
    # connectwise clicking it launches the time entry or discussion window ...
    # when clicking it logs the current time it has start and finish and thats
    # where u enter discussions"). The clock in the header starts this
    # person's timer (065) -- the moment is logged on the server, so a reload
    # or a closed window loses nothing -- and opens the window; Save stops it,
    # fills in the end, and the notes go on the ticket with the time. The
    # stopwatch still is not the SLA.
    te_button, te_dialog, run = "", "", None
    if can_work and may:
        from ... import timers as _timers
        run = _timers.for_ticket(ctx.conn, wid, ctx.user.id)
        te_dialog = _time_dialog(ctx, tk, run, status_pairs=status_pairs, notify_tick=bool(tk["notify_requester"]))
        if run is None:
            te_button = (f"<form method=post action='/ticket/{wid}/timer/start' class=inline>"
                         "<input type=hidden name=open value=1>"
                         "<button type=submit class='btn clockbtn' title='Start the clock and open a time entry'>"
                         + t.icon("clock") + "<span>New time entry</span></button></form>")
        else:
            secs = _timers.elapsed_seconds(run, now=ctx.now)
            live = not run["stopped_at"] and not run["paused_at"]
            te_button = ("<button type=button class='btn clockbtn on' data-open=tedlg title='Your time entry: open it'>"
                         + t.icon("clock") + f"<b class=tick data-tick='{secs}'{' data-run=1' if live else ''}>"
                         f"{_timers.clock(secs)}</b></button>")
    time_form = ""
    if can_work and may:
        time_form = ("<p class=row style='gap:8px;margin:10px 0 0'>" + te_button.replace("New time entry", "Start a time entry")
                     + ("<button type=button class='ghost' data-open=tedlg data-te-manual=1 title='Type the times in yourself'>"
                        + t.icon("plus") + " Enter time by hand</button>" if run is None else "") + "</p>")
    stopwatch = ""
    time_card = (f"<div class=card data-pod=time><h3><svg class=ic aria-hidden=true><use href=#i-clock></use></svg>"
                 f"Time · {actual_total:g} h" + (f" (band {band_total:g} h)" if time_rows else "") + "</h3>"
                 + stopwatch + time_table + time_form
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
        f"<dt>Desk ref</dt><dd>{t.esc(tk['external_ref'] or '—')}</dd>" + _raised_by(ctx, work_item_id) +
        f"<dt>Calendar</dt><dd>{t.esc(tk['calendar_name'] or '—')}</dd></dl></div>")

    from . import configurations as cmdb_views
    configs = cmdb_views.ticket_card(ctx, tk, can_work=can_work)
    from . import files as file_views
    from . import approvals as approvals_view
    configs = (_change_card(ctx, tk, can_work=can_work) + approvals_view.ticket_card(ctx, tk, can_work=can_work)
               + _family_card(ctx, tk, can_work=can_work)
               + _schedule_card(ctx, tk, can_work=can_work) + _tasks_card(ctx, tk, can_work=can_work)
               + file_views.ticket_card(ctx, tk, can_work=can_work) + _links_card(ctx, tk, can_work=can_work) + configs)
    from . import finance as finance_views, kb as kb_views
    from . import projects as project_views
    configs += (project_views.ticket_card(ctx, tk, can_work=can_work) + kb_views.ticket_card(ctx, tk, can_work=can_work)
                + finance_views.ticket_card(ctx, tk, can_work=can_work))
    header = header.replace("%%TEBUTTON%%", (" " + te_button) if te_button else "")
    from . import paging as paging_view
    body = te_dialog + composer + header + _tab_bar(wid, "") + strip + paging_view.banner(ctx, tk, can_work=can_work) + pod_dialog + (
        f"<div class=rail>{left}<div class=pods data-col=right data-order='ticket,time,change,approval,family,"
                             f"schedule,tasks,files,links,configurations,project,knowledge,finance,commercial,details'>{fields}{time_card}{configs}"
                             f"{commercial}{details}</div></div>")
    headers = []
    if chosen in ("old", "new"):
        # Remembered in this browser, like the layout and the text size; a
        # different browser on another ward PC keeps its own.
        headers.append(("Set-Cookie", f"{ORDER_COOKIE}={chosen}; Path=/ticket; Max-Age=31536000; SameSite=Lax"
                        + ("; Secure" if ctx.config.secure_cookie(ctx.request) else "")))
    return Response(body=t.page(work_item_id, body, user=ctx.user, active="board", quick=_quick_bar(wid, person, can_work), live=f"ticket:{work_item_id}"),
                    headers=headers)


def _back(work_item_id, **q):
    """Back to the ticket, or to where the form said (`back`: the Dispatch
    board or a calendar, which carry the same visit actions)."""
    from .. import redirect
    to = (_BACK.get() or "").strip()
    qs = urllib.parse.urlencode({k: v for k, v in q.items() if v})
    if to.startswith("/") and not to.startswith("//"):
        return redirect(to + ("&" if "?" in to else "?") + qs if qs else to)
    return redirect(f"/ticket/{work_item_id}" + (f"?{qs}" if qs else ""))


import contextvars as _cv
_BACK: _cv.ContextVar = _cv.ContextVar("psa_back", default="")


def _remember_back(ctx) -> None:
    try:
        _BACK.set(ctx.request.form().get("back", "") if ctx.request.method == "POST" else "")
    except Exception:                                        # noqa: BLE001 - a GET, or no body
        _BACK.set("")


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


_PIC_TOKEN = re.compile(r"p\d{1,3}-[a-z0-9]{3,12}")


def _note_pictures(ctx, work_item_id: str, f, body: str) -> str:
    """The pictures and GIFs a note carries (6 Oct 2026), stored as the
    ticket's files -- through the same review as any other file -- and the
    note's tokens turned into their Content-IDs. A picture taken out of the
    note before it was sent is not kept."""
    from ... import attachments
    import uuid
    files = ctx.request.files("pics") if ctx.request.is_multipart() else []
    tokens = [x for x in (f.get("pic_tokens") or "").split(",") if x]
    for (name, data), tok in zip(files, tokens):
        if not _PIC_TOKEN.fullmatch(tok) or f'cid:{tok}"' not in body or not data:
            continue
        cid = f"note-{uuid.uuid4().hex[:16]}@desk"
        try:
            attachments.add(ctx.conn, work_item_id, data, name or "picture", actor=ctx.user.id, at=ctx.now,
                            source="DESK", content_id=cid)
        except attachments.Refused as exc:
            raise ValueError(f"picture {attachments.safe_name(name or 'picture')}: {exc}")
        body = body.replace(f'cid:{tok}"', f'cid:{cid}"')
    return body


def add_note(ctx, work_item_id):
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    f = ctx.request.form()
    try:
        body = _note_pictures(ctx, work_item_id, f, f.get("body", ""))
        engine.add_note(ctx.conn, work_item_id, body=body,
                        body_format=f.get("body_format") or None,
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
    """POST /ticket/<id>/time: Dada PSA's Add time. With notes it is a note
    that carries the time (one write, refused whole); without, a bare entry."""
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    f = dict(ctx.request.form())
    from ... import timers as _timers
    tid = int(f["timer_id"]) if (f.get("timer_id") or "").isdigit() else None
    try:
        if tid is not None and not (f.get("end") or f.get("hours")):
            # Save is the end of the job: the clock stops now and its times are
            # the entry's, unless the person typed their own.
            stopped = _timers.stop(ctx.conn, tid, member=ctx.user.id, at=ctx.now)
            f["end"] = stopped["time_end"]
            f["start"] = f.get("start") or stopped["time_start"]
            f["worked_on"] = f.get("worked_on") or stopped["worked_on"]
            sh, sm = (int(x) for x in f["start"].split(":"))
            eh, em = (int(x) for x in f["end"].split(":"))
            if 0 <= (eh * 60 + em) - (sh * 60 + sm) < 8:
                # A job the clock measured at under eight minutes would round to
                # no time at all; it is booked as the smallest entry there is,
                # one quarter hour from its start.
                mm = sm + 15
                f["end"] = f"{(sh + mm // 60) % 24:02d}:{mm % 60:02d}"
        body = _note_pictures(ctx, work_item_id, f, f.get("body", "")).strip()
        if body and f.get("body_format") == "HTML" and not re.sub(r"<[^>]+>|&nbsp;|\s", "", body) and "<img" not in body:
            body = ""                                # an editor left empty is no note
        time = _time_from_form(f)
        if time is None:
            raise engine.EffortRefused("enter a start and end time, or the actual hours")
        if body:
            r = engine.add_note(ctx.conn, work_item_id, body=body, body_format=f.get("body_format") or None,
                                to_status_id=f.get("to_status") or None,
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
            if f.get("to_status"):
                engine.change_status(ctx.conn, work_item_id, f["to_status"], at=ctx.now, actor=ctx.user.id)
        if tid is not None:
            entry = ctx.conn.execute("SELECT MAX(time_entry_id) FROM time_entry WHERE work_item_id = ?",
                                     (work_item_id,)).fetchone()[0]
            if entry is not None:
                _timers.spend(ctx.conn, tid, entry)
        if f.get("notify_resources") == "1":
            from ... import outbox, resources as _resources
            for m in _resources.everyone(ctx.conn, work_item_id):
                outbox.queue_resource(ctx.conn, work_item_id, m, at=ctx.now, actor=ctx.user.id, note=True)
        ctx.conn.commit()
    except (ValueError, LookupError, engine.EffortRefused, engine.NotOnThisBoard) as exc:
        ctx.conn.rollback()
        return _back(work_item_id, err=f"Time not saved: {exc}")
    except Exception as exc:                                 # a gate trigger refused it
        ctx.conn.rollback()
        return _back(work_item_id, err=f"Time not saved: {exc}")
    return _back(work_item_id, msg=f"Time saved: {hours:g} h")


def timer(ctx, work_item_id, action):
    """POST /ticket/<id>/timer/<action>: the stopwatch, which is not the SLA.

    Dada, 3 Oct 2026: the reference PSA keeps a clock on the ticket for time
    entries, apart from the SLA. 065 is that clock. Start, pause, resume and
    stop belong to the person who pressed them; `stop` leaves the Add time
    form open with the measured times already in it, so the hours are what the
    job took rather than what anyone remembers it taking.
    """
    from ... import timers
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    f = ctx.request.form()
    me = ctx.user.id
    try:
        if action == "start":
            timers.start(ctx.conn, work_item_id, member=me, at=ctx.now)
            msg = "Timer started"
        elif action == "pause":
            timers.pause(ctx.conn, int(f.get("timer_id", "0")), member=me, at=ctx.now)
            msg = "Timer paused"
        elif action == "resume":
            timers.resume(ctx.conn, int(f.get("timer_id", "0")), member=me, at=ctx.now)
            msg = "Timer running again"
        elif action == "stop":
            r = timers.stop(ctx.conn, int(f.get("timer_id", "0")), member=me, at=ctx.now)
            msg = f"Timer stopped at {timers.clock(r['seconds'])} — check the time and save it"
        elif action == "discard":
            timers.discard(ctx.conn, int(f.get("timer_id", "0")), member=me)
            msg = "Time entry cancelled; no time was recorded"
        elif action == "note":
            timers.note(ctx.conn, int(f.get("timer_id", "0")), member=me, text=f.get("note", ""))
            msg = "Noted"
        else:
            return _back(work_item_id, err=f"no such timer action: {action}")
        ctx.conn.commit()
    except (ValueError, LookupError, timers.NotYours, timers.AlreadyRunning) as exc:
        ctx.conn.rollback()
        return _back(work_item_id, err=str(exc))
    # The clock in the header starts the timer and opens the time entry window.
    return _back(work_item_id, msg=msg, te="1" if action == "start" and f.get("open") == "1" else "")


def _time_dialog(ctx, tk, run, *, status_pairs, notify_tick: bool) -> str:
    """The reference PSA's Time Entry window: who and when across the top (the
    start already logged, the end filled in on Save), the work role, type and
    bill option, then the notes in the desk's own editor with the
    Discussion / Internal / Resolution ticks and who is emailed, and the
    status. One form, one Save; the window can be closed and reopened while
    the clock keeps running."""
    from ... import members as _members, timers as _timers
    wid = t.esc(tk["work_item_id"])
    prefill, secs, live = {}, 0, False
    if run is not None:
        secs = _timers.elapsed_seconds(run, now=ctx.now)
        live = not run["stopped_at"] and not run["paused_at"]
        prefill = {"worked_on": run["started_at"][:10], "time_start": run["started_at"][11:16],
                   "time_end": run["stopped_at"][11:16] if run["stopped_at"] else ""}
    clock = (f"<span class=teclock><b class=tick data-tick='{secs}'{' data-run=1' if live else ''}>{_timers.clock(secs)}</b>"
             f"<span class=muted>{'running' if live else ('paused' if run is not None and run['paused_at'] else 'stopped' if run is not None else 'no clock')}</span></span>"
             if run is not None else "<span class=teclock><span class=muted>Typed in by hand</span></span>")
    member = t.esc(_members.name_of(ctx.conn, ctx.user.id))
    return (
        "<dialog id=tedlg class='card tedlg'" + (" data-autoopen" if ctx.request.query.get("te") == "1" else "") + ">"
        f"<form method=post action='/ticket/{wid}/time' enctype='multipart/form-data' class=teform>"
        + (f"<input type=hidden name=timer_id value='{run['timer_id']}'>" if run is not None else "")
        # The title bar moves the window and its corner resizes it (Dada, 6 Oct
        # 2026: "make sure the time entry window can be moved or made larger");
        # the square makes it fill the screen, the bar hides it with the clock
        # still running.
        + "<div class=tehead data-drag title='Drag to move'><div><h3 style='margin:0'>" + t.icon("clock") + " Time entry</h3>"
        f"<div class=muted style='font-size:12.5px'>{wid} · {t.esc(tk['summary'])}</div></div>" + clock
        + "<span class=tewin><button type=button class=iconbtn data-close=tedlg aria-label='Minimise; the clock keeps running'"
          " title='Minimise; the clock keeps running'><b style='font-size:16px;line-height:1'>&#8211;</b></button>"
          "<button type=button class=iconbtn data-max=tedlg aria-label='Make the window larger' title='Larger / smaller'>"
          "<b style='font-size:14px;line-height:1'>&#9634;</b></button></span></div>"
        f"<div class=temember><label>Member</label><div class=ro>{member}</div></div>"
        + _time_fields(ctx, tk, prefill=prefill)
        + ("<p class=why style='margin:4px 0 10px'>Leave <b>End</b> empty and Save stops the clock now and fills it in.</p>"
           if run is not None and not run["stopped_at"] else "")
        + "<label>Notes</label>"
        + t.note_editor(placeholder="What was done, and what is next. Ticked Discussion, the requester reads it; "
                                    "a patient never needs naming (§6.1).", required=False,
                        text=(run["note"] or "") if run is not None else "")
        + "<div class=teflags><span class=seg>"
          "<label><input type=radio name=flag value=DISCUSSION checked><span>Discussion</span></label>"
          "<label class=int><input type=radio name=flag value=INTERNAL><span>Internal</span></label></span>"
          "<label class=tick><input type=checkbox name=resolution value=1> Resolution</label>"
          "<span class=tesep></span><span class=muted>Email:</span>"
        + ("<label class=tick><input type=checkbox name=notify value=1 checked> Contact</label>" if notify_tick else "")
        + "<label class=tick><input type=checkbox name=notify_resources value=1> Resources</label>"
          "<span class=grow></span><label style='margin:0'>Status</label><select name=to_status style='width:auto'>"
        + _options([("", "(no change)")] + status_pairs, "") + "</select></div>"
        + "<div class=tefoot><span class=grow></span>"
        # Cancel is the end of this entry, not a pause (Dada, 6 Oct 2026: "on
        # the time entry cancel also is discard"): the clock is thrown away and
        # nothing is booked. Minimise, above, is the way to step away.
        + (f"<button type=submit formaction='/ticket/{wid}/timer/discard' formnovalidate class=ghost"
           " onclick=\"return confirm('Cancel this time entry? The clock is thrown away and no time is recorded.')\">"
           "Cancel</button>" if run is not None else "<button type=button class=ghost data-close=tedlg>Cancel</button>")
        + "<button type=submit>" + t.icon("check") + " Save time entry</button></div></form></dialog>")


def _resource_picker(ctx, tk, *, can_work: bool) -> str:
    """Resources (067): tick every member who is on this ticket besides the
    owner. People with a visit booked are shown ticked and fixed: they are on
    it because of the visit, and come off when the visit does."""
    from ... import board as _board, members as _members, resources as _resources, schedule as _schedule
    wid = tk["work_item_id"]
    picked = {m.lower() for m in _resources.assigned(ctx.conn, wid)}
    booked = {r["member"].lower() for r in _schedule.entries_for(ctx.conn, wid)}
    people = {m.lower(): m for m in _board._working_members(ctx.conn, tk["board_id"])}
    for m in _resources.assigned(ctx.conn, wid):
        people.setdefault(m.lower(), m)
    rows = sorted(people.values(), key=lambda m: _members.name_of(ctx.conn, m).lower())
    names = [_members.name_of(ctx.conn, m) for m in rows if m.lower() in picked | booked]
    dis = "" if can_work else " disabled"
    on_board = _board_lower(ctx, tk)
    bits = []
    for m in rows:
        k = m.lower()
        fixed = k in booked and k not in picked
        attrs = (" checked" if k in picked or k in booked else "") + (" disabled title='Booked on a visit'" if fixed else dis)
        bits.append(f"<label class=pick><input type=checkbox name=resources value='{t.esc(m)}'{attrs}>"
                    f" {t.esc(_members.name_of(ctx.conn, m))}"
                    + (" <span class=muted>(visit booked)</span>" if k in booked else "")
                    + ("" if k in on_board else " <span class=muted>(not on this board)</span>") + "</label>")
    opts = "".join(bits)
    return ("<label>Resources</label>"
            + ("<input type=hidden name=resources_shown value=1>" if can_work else "")
            + "<details class=multipick><summary>" + (t.esc(", ".join(names)) if names else "<span class=muted>Nobody else</span>")
            + "</summary><div class=opts>" + (opts or "<span class=muted>Nobody works this board yet.</span>")
            + "</div></details>")


def _board_lower(ctx, tk) -> set[str]:
    from ... import board as _board
    return {m.lower() for m in _board._working_members(ctx.conn, tk["board_id"])}


def _missing_required(ctx, f, board_id: str | None) -> list[str]:
    """Which of the five required fields a posted form left empty (6 Oct 2026).
    The Item is required only where there is an Item to choose."""
    from ... import setup
    missing = []
    if not (f.get("entity_id") or "").strip():
        missing.append("Company")
    if not (f.get("record_type") or "").strip():
        missing.append("Ticket type")
    if not (f.get("catalogue_item_id") or "").strip() and setup.catalogue_choices(ctx.conn, board_id):
        missing.append("Type › Subtype › Item")
    return missing


def update(ctx, work_item_id):
    """The right-hand panel. A board change is a move (one id, clocks intact);
    the rest are field edits; a status change goes through the one seam."""
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    f = ctx.request.form()
    changed = []
    if f.get("fields") == "1":
        # The Ticket card's own Save (it carries fields=1). Assign me, the
        # summary pencil and the other one-field forms post without it and are
        # not held to the card's required fields.
        missing = _missing_required(ctx, f, f.get("board_id") or tk["board_id"])
        if missing:
            return _back(work_item_id, err=f"Not saved: {', '.join(missing)} still empty. {REQUIRED_SAY}.")
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
            record_type=want_type, priority=f.get("priority") or None,
            priority_reason=f.get("priority_reason"),
            summary=f.get("summary") if "summary" in f else None, **change_fields_from(f))
        if f.get("resources_shown") == "1":
            from ... import board as _bd, resources as _resources
            allowed = {m.lower() for m in _bd._working_members(ctx.conn, tk["board_id"])}
            line = _resources.set_(ctx.conn, work_item_id, ctx.request.form_list("resources"),
                                   at=ctx.now, actor=ctx.user.id, allowed=allowed)
            if line:
                changed.append(line)
        if "cc" in f:
            from ... import cc as _cc
            line = _cc.set_(ctx.conn, work_item_id, f.get("cc"), at=ctx.now, actor=ctx.user.id)
            if line:
                changed.append(line)
        if any("item" in c or "catalogue" in c for c in changed):
            from ... import approvals as _appr
            if _appr.maybe_request(ctx.conn, work_item_id, at=ctx.now, actor=ctx.user.id) == "REQUESTED":
                changed.append("approval asked for")
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
                "member of any board. To ask for something, use "
                "<a href='/my'>My requests</a>.</div></div>")
        return Response(body=t.page("New ticket", body, user=ctx.user, active="board"))
    entities = ctx.conn.execute("SELECT entity_id, name FROM entity ORDER BY is_covered DESC, name").fetchall()

    def radios(name, pairs, sel):
        return "<div class=choices>" + "".join(
            f"<label><input type=radio name={name} value='{k}'"
            f"{' checked' if k == sel else ''} required> {t.esc(lab)}</label>" for k, lab in pairs) + "</div>"

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
        "<input type=hidden name=fields value=1>"
        f"<div><label>Company{REQ}</label><select name=entity_id required>{_options([('', '(choose a company)')] + [(e['entity_id'], e['name']) for e in entities], v.get('entity_id', 'PMC'))}</select></div>"
        f"<div><label>Contact</label><input name=requested_by list=contacts-new value='{t.esc(v.get('requested_by', ''))}' placeholder='start typing a name, or an email'>"
        + _contact_list(ctx.conn, "contacts-new") + "</div>"
        f"<div style='grid-column:1/-1'><label>Summary</label><input name=summary required value='{t.esc(v.get('summary', ''))}' placeholder='What is wrong, in one line'></div>"
        + f"<div>{_type_select(ctx.conn, None, v.get('record_type', ''), required=True)}</div><div></div>"
        + (f"<div style='grid-column:1/-1'>{_catalogue_select(ctx.conn, None, v.get('catalogue_item_id', ''), required=True)}</div>"
           if _catalogue_select(ctx.conn, None, "") else "") +
        "<div class=radiorow><label style='color:var(--muted);font-weight:600'>Who is affected?</label>"
        f"{radios('impact', WHO_IS_AFFECTED, v.get('impact', ''))}</div>"
        "<div class=radiorow><label style='color:var(--muted);font-weight:600'>Is a patient waiting?</label>"
        f"{radios('urgency', PATIENT_WAITING, v.get('urgency', ''))}</div>"
        "<div style='grid-column:1/-1'><label>Description</label><textarea name=description "
        f"placeholder='The ward or office, the room, the machine, and since when.'>{t.esc(v.get('description', ''))}</textarea></div>"
        + "<div><label>Owner</label>" + common.owner_select(ctx.conn, [b["board_id"] for b in boards], v.get("owner"), me=ctx.user.id)
        + "</div>"
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
    if f.get("fields") == "1":
        missing = _missing_required(ctx, f, board_id)
        if missing:
            return new_form(ctx, error=f"Not created: {', '.join(missing)} still empty. {REQUIRED_SAY}.", values=f)
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
        if f.get("catalogue_item_id"):
            from ... import approvals as _appr
            _appr.maybe_request(ctx.conn, wid, at=ctx.now, actor=ctx.user.id)
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
               f"<div>{t.ticket_pick('linked_id', 'Search a ticket, or type its number', required=True, exclude=wid)}</div>"
               "<div style='flex:0 0 auto'><button class=ghost type=submit>Link</button></div></form>")
    body = (f"<ul class=plain>{''.join(items)}</ul>" if items else "<div class=muted>No links.</div>")
    if hidden:
        body += f"<p class=why>{hidden} more not listed here: on a restricted board, or one you are not on. Open them from that board.</p>"
    return f"<div class=card data-pod=links><h3><svg class=ic aria-hidden=true><use href=#i-link></use></svg>Links</h3>{body}{add}</div>"


def _family_card(ctx, tk, *, can_work: bool) -> str:
    """Dada PSA's parent/child. A child shows its parent; a parent lists its
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
                 f"<div>{t.ticket_pick('child_id', 'Attach a child: search or type a number', required=True, exclude=wid)}</div>"
                 "<div style='flex:0 0 auto'><button class=ghost type=submit>" + t.icon("plus")
                 + " Attach</button></div></form>")
        if not kids:
            forms += (f"<form method=post action='/ticket/{wid}/parent/set' class=row style='margin-top:6px'>"
                      f"<div>{t.ticket_pick('parent_id', 'Make this a child of: search or type a number', required=True, exclude=wid)}</div>"
                      "<div style='flex:0 0 auto'><button class=ghost type=submit>" + t.icon("arrow")
                      + " Attach</button></div></form>")
    if can_work and not tk["closed_at"] and not tk["merged_into"]:
        forms += (f"<form method=post action='/ticket/{wid}/merge' class=row style='margin-top:10px;"
                  "padding-top:10px;border-top:1px solid var(--line)'>"
                  f"<div>{t.ticket_pick('into', 'Duplicate? Merge into: search or type a number', required=True, exclude=wid)}</div>"
                  "<div style='flex:0 0 auto'><button class=ghost type=submit>" + t.icon("layers")
                  + " Merge</button></div>"
                  "<p class=why style='flex-basis:100%;margin:0'>This ticket closes; its notes, files and "
                  "links go to the other one. A Discussion note arrives as Internal unless both have the "
                  "same requester.</p></form>")
    head = f"Children · {len(kids)}" if kids else "Children"
    return f"<div class=card data-pod=family><h3>{t.icon('layers')}{t.esc(head)}</h3>{body}{forms}</div>"


def _schedule_card(ctx, tk, *, can_work: bool) -> str:
    """The Schedule pod: the ticket's visits in the reference PSA's shape, each
    with its status, where, lead, done and acknowledged, and the actions on it."""
    from ... import schedule
    wid = t.esc(tk["work_item_id"])
    rows = schedule.entries_for(ctx.conn, tk["work_item_id"])
    statuses, places = schedule.statuses(ctx.conn), schedule.locations(ctx.conn)

    def opts(pairs, sel, blank=None):
        return ((f"<option value=''>{t.esc(blank)}</option>" if blank is not None else "")
                + "".join(f"<option value='{t.esc(k)}'{' selected' if k == sel else ''}>{t.esc(v)}</option>"
                          for k, v in pairs))

    def act(action, sid, label, cls="ghost small", title=""):
        return (f"<form method=post action='/ticket/{wid}/schedule/{action}' style='display:inline'>"
                f"<input type=hidden name=schedule_id value='{sid}'>"
                f"<button class='{cls}' type=submit title='{t.esc(title or label)}'>{label}</button></form>")

    items = []
    for r in rows:
        chips = (f"{t.chip(r['status_name'])}" if r["status_name"] else "")
        chips += f" <span class=muted>{t.esc(r['location_name'])}</span>" if r["location_name"] else ""
        chips += " <span class=pill>lead</span>" if r["is_lead"] else ""
        chips += " <span class='pill live'>done</span>" if r["done_at"] else ""
        chips += " <span class=pill>acknowledged</span>" if r["acknowledged_at"] else ""
        chips += " <span class='pill warn'>double booked</span>" if r["conflict_allowed"] else ""
        line = (f"<li{' style=opacity:.65' if r['done_at'] else ''}><b>{t.esc(r['member'])}</b> · "
                f"{t.esc(r['starts_at'])} → {t.esc(r['ends_at'][11:])} {chips}"
                + (f"<div class=muted>{t.esc(r['note'])}</div>" if r["note"] else ""))
        if can_work:
            sid = r["schedule_id"]
            buttons = []
            if not r["acknowledged_at"] and r["member"].lower() == ctx.user.id.lower():
                buttons.append(act("ack", sid, "Acknowledge", title="I have seen this visit"))
            buttons.append(act("done", sid, "Reopen" if r["done_at"] else "Done"))
            if not r["is_lead"]:
                buttons.append(act("lead", sid, "Make lead"))
            buttons.append(act("remove", sid, "×", title="Cancel this visit"))
            line += "<div class=row style='gap:4px;margin-top:4px'>" + "".join(buttons) + "</div>"
            if not r["done_at"]:
                line += (f"<details style='margin-top:4px'><summary class=muted>Move or change</summary>"
                         f"<form method=post action='/ticket/{wid}/schedule/update' class=grid2 style='margin-top:6px'>"
                         f"<input type=hidden name=schedule_id value='{sid}'>"
                         "<div><label>Who</label>" + common.owner_select(ctx.conn, [tk["board_id"]], r["member"], me=ctx.user.id, name="member",
                                                                          blank="(as it is)") + "</div>"
                         f"<div><label>Status</label><select name=status_id>{opts([(x['status_id'], x['name']) for x in statuses], r['status_id'])}</select></div>"
                         f"<div><label>From</label><input type=datetime-local name=starts_at value='{t.esc(r['starts_at'].replace(' ', 'T'))}'></div>"
                         f"<div><label>To</label><input type=datetime-local name=ends_at value='{t.esc(r['ends_at'].replace(' ', 'T'))}'></div>"
                         f"<div><label>Where</label><select name=location_id>{opts([(x['location_id'], x['name']) for x in places], r['location_id'] or '', '(not said)')}</select></div>"
                         f"<div><label>Note</label><input name=note value='{t.esc(r['note'] or '')}'></div>"
                         "<div style='grid-column:1/-1'><label><input type=checkbox name=allow_conflict value=1> "
                         "Allow a double booking</label> <button class=ghost type=submit>Save</button></div></form></details>")
        items.append(line + "</li>")
    add = ""
    if can_work and not tk["closed_at"]:
        start = ctx.now.replace(minute=0, second=0, microsecond=0)
        # To is `required`, so leaving it empty made the button do nothing at
        # all: the browser blocks the submit on a field the page never filled,
        # and a technician sees a dead button (MEASURED in Chromium, 3 Oct
        # 2026, after Dada: "there is an issue with scheduling"). An hour is
        # what a visit is unless someone says otherwise, and the script below
        # keeps To following From.
        end = start + timedelta(hours=1)
        add = (f"<form method=post action='/ticket/{wid}/schedule/add' class=grid2 style='margin-top:8px' id=schedadd>"
               "<div><label>Who</label>" + common.owner_select(ctx.conn, [tk["board_id"]], tk["owner"] or ctx.user.id, me=ctx.user.id,
                                                               name="member", blank="(pick a person)", attrs=" required")
               + "</div>"
               f"<div><label>Status</label><select name=status_id>{opts([(x['status_id'], x['name']) for x in statuses], schedule.default_status(ctx.conn))}</select></div>"
               f"<div><label>From</label><input type=datetime-local name=starts_at value='{start.strftime('%Y-%m-%dT%H:%M')}' required></div>"
               f"<div><label>To</label><input type=datetime-local name=ends_at value='{end.strftime('%Y-%m-%dT%H:%M')}' required></div>"
               f"<div><label>Where</label><select name=location_id>{opts([(x['location_id'], x['name']) for x in places], '', '(not said)')}</select></div>"
               "<div><label>Note</label><input name=note placeholder='Ward 3, bring toner'></div>"
               "<div style='grid-column:1/-1'><label><input type=checkbox name=allow_conflict value=1> "
               "Allow a double booking</label> <button class=ghost type=submit>" + t.icon("calendar")
               + " Schedule the visit</button> <a class=muted href='/schedule'>Week view</a></div></form>")
    head = f"Schedule · {len(rows)}" if rows else "Schedule"
    return (f"<div class=card data-pod=schedule><h3>{t.icon('calendar')}{t.esc(head)}</h3>"
            + (f"<ul class=plain>{''.join(items)}</ul>" if items else "<div class=muted>No visits booked.</div>")
            + add + "</div>")


def _schedule_form(ctx) -> dict:
    from ... import schedule
    f = ctx.request.form()
    return {"member": f.get("member", ""),
            "starts_at": schedule.parse_local(f["starts_at"]) if f.get("starts_at") else None,
            "ends_at": schedule.parse_local(f["ends_at"]) if f.get("ends_at") else None,
            "status_id": f.get("status_id") or None, "location_id": f.get("location_id", None),
            "note": f.get("note"), "allow_conflict": f.get("allow_conflict") == "1"}


def schedule_add(ctx, work_item_id):
    from ... import schedule
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    try:
        v = _schedule_form(ctx)
        if v["starts_at"] is None or v["ends_at"] is None:
            raise schedule.Refused("a visit needs a from and a to")
        schedule.add(ctx.conn, work_item_id, member=v["member"], starts_at=v["starts_at"], ends_at=v["ends_at"],
                     note=v["note"], actor=ctx.user.id, at=ctx.now, status_id=v["status_id"],
                     location_id=v["location_id"] or None, allow_conflict=v["allow_conflict"])
        ctx.conn.commit()
    except (schedule.Refused, LookupError) as exc:
        ctx.conn.rollback()
        return _back(work_item_id, err=f"Not scheduled: {exc}")
    return _back(work_item_id, msg="Visit scheduled")


def _visit_of(ctx, work_item_id):
    sid = ctx.request.form().get("schedule_id", "")
    row = ctx.conn.execute("SELECT work_item_id FROM ticket_schedule WHERE schedule_id = ?",
                           (sid,)).fetchone() if sid.isdigit() else None
    return int(sid) if row is not None and row["work_item_id"] == work_item_id else None


def schedule_update(ctx, work_item_id):
    from ... import schedule
    _remember_back(ctx)
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    sid = _visit_of(ctx, work_item_id)
    if sid is None:
        return _back(work_item_id, err="No such visit on this ticket")
    try:
        v = _schedule_form(ctx)
        what = schedule.update(ctx.conn, sid, actor=ctx.user.id, at=ctx.now, member=v["member"],
                               starts_at=v["starts_at"], ends_at=v["ends_at"], status_id=v["status_id"],
                               location_id=v["location_id"], note=v["note"], allow_conflict=v["allow_conflict"])
        ctx.conn.commit()
    except schedule.Refused as exc:
        ctx.conn.rollback()
        return _back(work_item_id, err=f"Not changed: {exc}")
    return _back(work_item_id, msg=f"Visit: {what}")


def schedule_done(ctx, work_item_id):
    from ... import schedule
    _remember_back(ctx)
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    sid = _visit_of(ctx, work_item_id)
    if sid is None:
        return _back(work_item_id, err="No such visit on this ticket")
    done = not ctx.conn.execute("SELECT done_at FROM ticket_schedule WHERE schedule_id = ?", (sid,)).fetchone()[0]
    schedule.set_done(ctx.conn, sid, done, actor=ctx.user.id, at=ctx.now)
    ctx.conn.commit()
    return _back(work_item_id, msg="Visit done" if done else "Visit reopened")


def schedule_ack(ctx, work_item_id):
    from ... import schedule
    _remember_back(ctx)
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    sid = _visit_of(ctx, work_item_id)
    if sid is None:
        return _back(work_item_id, err="No such visit on this ticket")
    try:
        schedule.acknowledge(ctx.conn, sid, member=ctx.user.id, at=ctx.now)
        ctx.conn.commit()
    except schedule.Refused as exc:
        return _back(work_item_id, err=str(exc))
    return _back(work_item_id, msg="Visit acknowledged")


def schedule_lead(ctx, work_item_id):
    from ... import schedule
    _remember_back(ctx)
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    sid = _visit_of(ctx, work_item_id)
    if sid is None:
        return _back(work_item_id, err="No such visit on this ticket")
    schedule.make_lead(ctx.conn, sid, actor=ctx.user.id, at=ctx.now)
    ctx.conn.commit()
    return _back(work_item_id, msg="Lead changed")


def schedule_remove(ctx, work_item_id):
    from ... import schedule
    _remember_back(ctx)
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    sid = _visit_of(ctx, work_item_id)
    if sid is None:
        return _back(work_item_id, err="No such visit on this ticket")
    schedule.remove(ctx.conn, sid, actor=ctx.user.id, at=ctx.now)
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
    """Dada PSA's Tasks tab: the ticket's checklist, and templates to fill it."""
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
    """Dada PSA's "new ticket from template": a plain GET, so it works with no script."""
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


# ============================================================ ticket tabs
# Dada, 7 Oct 2026: "there should be tabs on each ticket similar to
# connectwise", then "all but billing". The reference PSA's Service Ticket Tabs
# (MEASURED, docs.connectwise.com ConnectWise_Documentation/060/010/010):
# Ticket, Tasks, Configurations, Products, Activity, Time, Expenses, Schedule,
# Attachments, Open Tickets, Finance, Audit Trail, Survey, RMA, Conversions.
# Products, Expenses, RMA and Conversions are billing and sales, left out on
# Dada's word. /ticket/<id> stays the Ticket tab exactly as it was; every other
# tab is its own page at /ticket/<id>/<tab>, and its forms come back to it.

TICKET_TABS = (("", "Ticket"), ("tasks", "Tasks"), ("configurations", "Configurations"), ("activity", "Activity"),
               ("time", "Time"), ("schedule", "Schedule"), ("attachments", "Attachments"), ("open", "Open tickets"),
               ("finance", "Finance"), ("audit", "Audit trail"), ("survey", "Survey"))


def _tab_bar(wid: str, current: str) -> str:
    return ("<nav class='tabs ttabs' aria-label='Ticket tabs'>" + "".join(
        f"<a href='/ticket/{wid}" + (f"/{key}" if key else "") + "'"
        + (" class=on aria-current=page" if key == current else "") + f">{label}</a>" for key, label in TICKET_TABS)
        + "</nav>")


def tab(ctx, work_item_id, tab):
    """GET /ticket/<id>/<tab>: one of the reference PSA's ticket tabs, on its own page."""
    from .. import HttpError, Response
    pages = {"tasks": _ttab_tasks, "configurations": _ttab_configurations, "activity": _ttab_activity,
             "time": _ttab_time, "schedule": _ttab_schedule, "attachments": _ttab_attachments, "open": _ttab_open,
             "finance": _ttab_finance, "audit": _ttab_audit, "survey": _ttab_survey}
    if tab not in pages:
        raise HttpError("404 Not Found", "No such tab.")
    tk = _load(ctx, work_item_id)
    wid = t.esc(work_item_id)
    can_work = common.may_access_board(ctx, tk["board_id"], need="WORK")
    q = ctx.request.query
    body = pages[tab](ctx, tk, can_work)
    # every form on the tab comes back to it (`back`, read by _load / _back)
    body = re.sub(r"(<form method=post action='/ticket/" + re.escape(wid) + r"/[^']*'[^>]*>)",
                  lambda m: m.group(1) + f"<input type=hidden name=back value='/ticket/{wid}/{tab}'>", body)
    head = ((f"<div class='banner ok toast'>{t.icon('check')} {t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err toast'>{t.icon('alert')} {t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + "<a class=backbtn data-back href='/' title='Back to the Service Board'>" + t.icon("left")
            + "<span class=lbl>Back to the Service Board</span></a>"
            f"<div class=hdr><div class=grow><h1 class=sumline>{wid}<span class=sumtext> · {t.esc(tk['summary'])}</span></h1>"
            f"<p class=sub>{t.esc(tk['board_name'])} · {t.chip(tk['status_name'] or tk['state'].replace('_', ' ').title())} · "
            f"{t.badge(tk['priority'])} · {t.esc(tk['entity'] or 'no company')}</p></div></div>" + _tab_bar(wid, tab))
    label = dict(TICKET_TABS)[tab]
    return Response(body=t.page(f"{work_item_id} · {label}", head + body, user=ctx.user, active="board",
                                live=f"ticket:{work_item_id}"))


def _ttab_tasks(ctx, tk, can_work) -> str:
    return _tasks_card(ctx, tk, can_work=can_work)


def _ttab_schedule(ctx, tk, can_work) -> str:
    return _schedule_card(ctx, tk, can_work=can_work)


def _ttab_attachments(ctx, tk, can_work) -> str:
    from . import files as file_views
    return file_views.ticket_card(ctx, tk, can_work=can_work)


def _ttab_finance(ctx, tk, can_work) -> str:
    from . import finance as finance_views
    return (finance_views.ticket_card(ctx, tk, can_work=can_work)
            or "<div class=card><div class=muted>Finance needs the Finance module on your role.</div></div>")


def _ttab_configurations(ctx, tk, can_work) -> str:
    """The reference PSA's Configurations tab: the ticket's configurations, and
    the company's others greyed beside them, each attachable in one click."""
    wid = t.esc(tk["work_item_id"])
    attached = ctx.conn.execute(
        "SELECT c.*, ct.display_name AS contact_name FROM ticket_configuration tc"
        " JOIN configuration c ON c.configuration_id = tc.configuration_id"
        " LEFT JOIN contact ct ON ct.contact_id = c.contact_id WHERE tc.work_item_id = ? ORDER BY c.name",
        (tk["work_item_id"],)).fetchall()
    ids = {r["configuration_id"] for r in attached}
    others = [r for r in ctx.conn.execute(
        "SELECT c.*, ct.display_name AS contact_name FROM configuration c LEFT JOIN contact ct ON ct.contact_id = c.contact_id"
        " WHERE c.entity_id = ? AND c.status = 'ACTIVE'"
        " ORDER BY CASE WHEN c.contact_id = ? THEN 0 ELSE 1 END, c.name LIMIT 500",
        (tk["entity_id"] or "", tk["contact_id"])).fetchall() if r["configuration_id"] not in ids]

    def row(r, on):
        act = ""
        if can_work:
            act = (f"<form method=post action='/ticket/{wid}/config/{'remove' if on else 'add'}' class=inline>"
                   f"<input type=hidden name=configuration_id value='{t.esc(r['configuration_id'])}'>"
                   f"<button class='ghost small' type=submit>{'Detach' if on else 'Attach'}</button></form>")
        return (f"<tr class='{'' if on else 'cfgoff'}'><td><a href='/configuration/{t.esc(r['configuration_id'])}'>"
                f"{t.esc(r['name'])}</a></td><td>{t.esc((r['config_type'] or '').title())}</td>"
                f"<td>{t.esc((r['status'] or '').title())}</td><td>{t.esc(r['contact_name'] or '')}</td>"
                f"<td>{t.esc(r['serial_number'] or '')}</td><td>{t.esc(r['model'] or '')}</td><td>{act}</td></tr>")
    trs = "".join(row(r, True) for r in attached) + "".join(row(r, False) for r in others)
    new = (f"<p style='margin:10px 0 0'><a class='btn ghost' href='/configurations#cfgnew'>" + t.icon("plus")
           + " New configuration</a></p>" if can_work else "")
    return ("<div class=card id=tconfigs><h3>" + t.icon("monitor") + f"Configurations · {len(attached)} attached</h3>"
            "<p class=why style='margin-top:0'>Attached configurations are in full; the company's other machines are "
            "greyed, the contact's first.</p><div class=tablewrap><table><thead><tr><th>Configuration</th><th>Type</th>"
            "<th>Status</th><th>Contact</th><th>Serial</th><th>Model</th><th></th></tr></thead><tbody>"
            + (trs or "<tr><td colspan=7 class=muted>No configurations for this company yet.</td></tr>")
            + "</tbody></table></div>" + new + "</div>")


def _ttab_activity(ctx, tk, can_work) -> str:
    """Every note and email on the ticket, newest first. (The reference PSA's
    Activity tab lists CRM activities, which this desk does not keep; its
    notes and emails are the nearest thing, so they are what is here.)"""
    rows = ctx.conn.execute(
        "SELECT occurred_at, kind, actor, note_flag, is_resolution, detail, body_format FROM ticket_event"
        " WHERE work_item_id = ? AND note_flag IS NOT NULL ORDER BY ticket_event_id DESC", (tk["work_item_id"],)).fetchall()
    trs = "".join(
        f"<tr><td>{t.esc(r['occurred_at'])}</td><td>{t.esc(r['actor'] or '')}</td>"
        f"<td><span class='flag {t.esc(r['note_flag'])}'>{t.esc(FLAG_LABEL.get(r['note_flag'], r['note_flag']))}</span>"
        + (" <span class='flag RESOLUTION'>Resolution</span>" if r["is_resolution"] and r["note_flag"] != "RESOLUTION" else "")
        + f"</td><td>{t.esc(r['kind'].replace('_', ' ').lower())}</td>"
        f"<td>{t.esc(richtext_plain(r['detail'])[:200])}</td></tr>" for r in rows)
    return ("<div class=card id=tactivity><h3>" + t.icon("rows") + f"Activity · {len(rows)}</h3>"
            "<div class=tablewrap><table><thead><tr><th>When</th><th>Who</th><th>Note</th><th>How</th><th>What</th></tr></thead>"
            f"<tbody>{trs or '<tr><td colspan=5 class=muted>No notes yet.</td></tr>'}</tbody></table></div>"
            f"<p class=why>Read or write the full notes on the <a href='/ticket/{t.esc(tk['work_item_id'])}'>Ticket</a> tab.</p></div>")


def richtext_plain(html_text) -> str:
    """A note's words, without its markup, for one line of a list."""
    text = re.sub(r"<[^>]+>", " ", html_text or "")
    import html as _html
    return " ".join(_html.unescape(text).split())


def _ttab_time(ctx, tk, can_work) -> str:
    wid = t.esc(tk["work_item_id"])
    rows = ctx.conn.execute(
        "SELECT te.*, r.name AS role_name, y.name AS type_name FROM time_entry te"
        " LEFT JOIN work_role r ON r.work_role_id = te.work_role_id"
        " LEFT JOIN work_type y ON y.work_type_id = te.work_type_id"
        " WHERE te.work_item_id = ? ORDER BY te.worked_on DESC, te.time_entry_id DESC", (tk["work_item_id"],)).fetchall()
    hours = lambda r: r["actual_hours"] if r["actual_hours"] is not None else r["band_hours"]  # noqa: E731
    trs = "".join(
        f"<tr><td>{t.esc(r['worked_on'])}</td><td>{t.esc(r['performed_by'])}</td>"
        f"<td>{t.esc((r['time_start'] or '')[11:] + ('–' + r['time_end'][11:] if r['time_end'] else '') or '—')}</td>"
        f"<td class=num>{hours(r):g}</td><td class=num>{(r['hours_deduct'] or 0):g}</td>"
        f"<td>{t.esc(r['role_name'] or '—')}</td><td>{t.esc(r['type_name'] or '—')}</td>"
        f"<td>{t.esc(CHARGE_LABEL.get(r['charge_method'], r['charge_method']))}</td>"
        f"<td>{t.esc(richtext_plain(r['note'])[:120])}</td></tr>" for r in rows)
    total = sum(hours(r) for r in rows)
    return ("<div class=card id=ttime><h3>" + t.icon("clock") + f"Time · {total:g} h</h3><div class=tablewrap><table>"
            "<thead><tr><th>Date</th><th>Member</th><th>Start–End</th><th>Hours</th><th>Deduct</th><th>Work role</th>"
            "<th>Work type</th><th>Charged as</th><th>Notes</th></tr></thead>"
            f"<tbody>{trs or '<tr><td colspan=9 class=muted>No time yet.</td></tr>'}</tbody></table></div>"
            + (f"<p style='margin:10px 0 0'><a class='btn ghost' href='/ticket/{wid}'>" + t.icon("clock")
               + " New time entry (on the Ticket tab, with the clock)</a></p>" if can_work else "") + "</div>")


def _ttab_open(ctx, tk, can_work) -> str:
    """Open Tickets: the company's other open tickets (and the contact's), on
    the boards the viewer may see, as the reference PSA's Open Tickets tab."""
    seen = common.board_ids_for(ctx)
    if not seen:
        return "<div class=card><div class=muted>No boards.</div></div>"
    marks = ",".join("?" * len(seen))
    rows = ctx.conn.execute(
        "SELECT t.work_item_id, w.name AS summary, b.display_name AS board, s.name AS status, t.owner, t.opened_at,"
        " t.contact_id, t.priority FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
        " JOIN board b ON b.board_id = t.board_id LEFT JOIN board_status s ON s.board_status_id = t.board_status_id"
        f" WHERE t.board_id IN ({marks}) AND t.closed_at IS NULL AND t.merged_into IS NULL AND t.work_item_id <> ?"
        " AND ((w.entity_id IS NOT NULL AND w.entity_id = ?) OR (t.contact_id IS NOT NULL AND t.contact_id = ?))"
        " ORDER BY CASE WHEN t.contact_id = ? THEN 0 ELSE 1 END, t.opened_at DESC LIMIT 200",
        [*sorted(seen), tk["work_item_id"], tk["entity_id"], tk["contact_id"], tk["contact_id"]]).fetchall()
    trs = "".join(
        f"<tr><td><a href='/ticket/{t.esc(r['work_item_id'])}'>{t.esc(r['work_item_id'])}</a></td><td>{t.esc(r['summary'])}</td>"
        f"<td>{t.badge(r['priority'])}</td><td>{t.esc(r['board'])}</td><td>{t.esc(r['status'] or '')}</td>"
        f"<td>{t.esc(r['owner'] or 'unassigned')}</td><td>{t.esc((r['opened_at'] or '')[:10])}</td>"
        f"<td>{'this contact' if tk['contact_id'] and r['contact_id'] == tk['contact_id'] else ''}</td></tr>" for r in rows)
    return ("<div class=card id=topen><h3>" + t.icon("ticket") + f"Open tickets · {t.esc(tk['entity'] or 'this company')} · {len(rows)}</h3>"
            "<div class=tablewrap><table><thead><tr><th>Ticket</th><th>Summary</th><th>Priority</th><th>Board</th><th>Status</th>"
            f"<th>Owner</th><th>Opened</th><th></th></tr></thead><tbody>"
            f"{trs or '<tr><td colspan=8 class=muted>No other open tickets for this company.</td></tr>'}</tbody></table></div></div>")


def _ttab_audit(ctx, tk, can_work) -> str:
    """Audit Trail: every change on the ticket, newest first: its system
    events, and the audit records naming it."""
    wid = tk["work_item_id"]
    rows = [(r["occurred_at"], r["actor"] or "system", _system_line(ctx.conn, r), r["kind"].replace("_", " ").title())
            for r in ctx.conn.execute(
                "SELECT ticket_event_id, occurred_at, kind, actor, detail, note_flag FROM ticket_event"
                " WHERE work_item_id = ? AND note_flag IS NULL", (wid,)).fetchall()]
    rows += [(r["occurred_at"], r["actor"] or "system", r["detail"] or "", (r["action"] or "").replace("_", " ").title())
             for r in ctx.conn.execute("SELECT occurred_at, actor, action, detail FROM audit_event"
                                       " WHERE subject_kind = 'ticket' AND subject_id = ?", (wid,)).fetchall()]
    rows.sort(key=lambda x: x[0] or "", reverse=True)
    trs = "".join(f"<tr><td>{t.esc(a)}</td><td>{t.esc(b)}</td><td>{t.esc(d)}</td><td>{t.esc(c)}</td></tr>" for a, b, c, d in rows)
    return ("<div class=card id=taudit><h3>" + t.icon("setup") + f"Audit trail · {len(rows)}</h3><div class=tablewrap><table>"
            "<thead><tr><th>When</th><th>Who</th><th>Type</th><th>What</th></tr></thead>"
            f"<tbody>{trs or '<tr><td colspan=4 class=muted>Nothing yet.</td></tr>'}</tbody></table></div></div>")


def _ttab_survey(ctx, tk, can_work) -> str:
    from ... import survey
    row = ctx.conn.execute("SELECT * FROM survey_response WHERE work_item_id = ?", (tk["work_item_id"],)).fetchone()
    q = survey.question(ctx.conn, tk["work_item_id"])
    if row:
        body = (f"<dl class=kv><dt>Question</dt><dd>{t.esc(q)}</dd><dt>Score</dt><dd>{'★' * row['score']}{'☆' * (5 - row['score'])}"
                f" ({row['score']} of 5)</dd><dt>Comment</dt><dd>{t.esc(row['comment'] or '—')}</dd>"
                f"<dt>Answered</dt><dd>{t.esc(row['answered_by'])} · {t.esc(row['answered_at'])}</dd></dl>")
    elif survey.pending(ctx.conn, tk["work_item_id"]):
        body = f"<div class=muted>Waiting for the requester to answer: “{t.esc(q)}”</div>"
    else:
        body = "<div class=muted>The survey is offered to the requester once the ticket is closed.</div>"
    return "<div class=card id=tsurvey><h3>" + t.icon("star") + "Survey</h3>" + body + "</div>"
