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
        "       b.closed_loop_required, b.calendar_id, c.name AS calendar_name"
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
    can_work = common.may_access_board(ctx, tk["board_id"], need="WORK")
    buttons = ""
    if can_work and tk["closed_loop_required"]:
        buttons = f"<a class=btn href='/ticket/{wid}/loop'>Close the loop</a>"
    header = (
        (f"<div class='banner ok'>{t.esc(msg)}</div>" if msg else "") +
        (f"<div class='banner err'>{t.esc(err)}</div>" if err else "") +
        "<div class=hdr><div class=grow>"
        f"<h1>{wid} · {t.esc(tk['summary'])}</h1>"
        f"<p class=sub>{t.esc(tk['board_name'])} · "
        f"{t.chip(tk['status_name'] or tk['state'].replace('_', ' ').title())} · "
        f"{t.badge(tk['priority'])} <span class=why>{t.esc(why)}</span></p></div>"
        f"<div>{buttons}</div></div>")

    # ----------------------------------------------------------- SLA strip
    states = common.clock_states(ctx.conn, work_item_id, now=ctx.now)
    if states:
        boxes = []
        for st in states:
            cls = {"MET": "done", "MISSED": "bad", "BAD": "bad", "WARN": "warn",
                   "PAUSED": "done"}.get(st["state"], "ok")
            colour = {"bad": "#b3261e", "warn": "#e0a000", "done": "#9aa4b1"}.get(cls, "#34a853")
            boxes.append(
                f"<div class='slabox {cls}'><div class=t>{t.esc(st['name'])} · target "
                f"{t.esc(common.fmt_minutes(st['target']))}</div>"
                f"<div class=v{' style=color:#b3261e' if cls == 'bad' else ''}>{t.esc(st['text'])}</div>"
                f"<div class=bar><i style='width:{int(st['fraction'] * 100)}%;background:{colour}'></i>"
                "</div></div>")
        strip = "<div class=slastrip>" + "".join(boxes) + "</div>"
    else:
        reason = common.no_clock_reason(ctx.conn, tk["board_id"], tk["source_ref"])
        strip = (f"<div class=note-ph>No SLA clock on this ticket: {t.esc(reason)}."
                 + (" A board administrator sets the board up on the Setup page."
                    if reason == "board not set up" else "") + "</div>")

    # --------------------------------------------------------- the notes
    events = ctx.conn.execute(
        "SELECT occurred_at, kind, actor, detail, note_flag FROM ticket_event"
        " WHERE work_item_id = ? ORDER BY ticket_event_id", (work_item_id,)).fetchall()
    time_rows = ctx.conn.execute(
        "SELECT worked_on, band_hours, performed_by, charge_method, note FROM time_entry"
        " WHERE work_item_id = ? ORDER BY time_entry_id", (work_item_id,)).fetchall()
    counts = {"ALL": len(events), "SYSTEM": sum(1 for e in events if not e["note_flag"])}
    for flag in FLAG_LABEL:
        counts[flag] = sum(1 for e in events if e["note_flag"] == flag)
    tabs = "".join(
        f"<a class='{'on' if tab == key else ''}' href='/ticket/{wid}?tab={key}'>"
        f"{label} {counts[key]}</a>"
        for key, label in (("ALL", "All"), ("DISCUSSION", "Discussion"), ("INTERNAL", "Internal"),
                           ("RESOLUTION", "Resolution"), ("SYSTEM", "System")))
    items = []
    for e in events:
        flag = e["note_flag"]
        if tab == "SYSTEM" and flag or tab in FLAG_LABEL and flag != tab:
            continue
        if flag:
            items.append(
                f"<div class='note {flag}'><div class=h><span class=av>{t.esc(_initials(e['actor']))}</span>"
                f"<b>{t.esc(e['actor'] or '—')}</b><span class='flag {flag}'>{FLAG_LABEL[flag]}</span>"
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
            "<div class=card><h3>Add a note</h3>"
            f"<form method=post action='/ticket/{wid}/note'>"
            "<textarea name=body required placeholder='No patient names or case numbers (§6.1).'></textarea>"
            "<div class=row style='margin-top:10px'>"
            "<div style='flex:0 0 auto'><label>Who can read it</label><div class=seg>"
            "<label><input type=radio name=flag value=DISCUSSION checked><span>Discussion</span></label>"
            "<label class=int><input type=radio name=flag value=INTERNAL><span>Internal</span></label>"
            "<label class=res><input type=radio name=flag value=RESOLUTION><span>Resolution</span></label>"
            "</div></div>" + time_block +
            "<div><label>And set status</label><select name=to_status>"
            + _options([("", "(no change)")] + status_pairs, "") +
            "</select></div><div style='flex:0 0 auto'><button type=submit>Save note</button></div>"
            "</div><p class=why style='margin:8px 0 0'>Discussion and Resolution notes are shown "
            "to the requester on their portal. Internal notes never leave the desk.</p></form></div>")

    left = (f"<div><div class=card><div class=tabs>{tabs}</div>{stream}</div>{composer}</div>")

    # ---------------------------------------------------------- right rail
    boards = ctx.conn.execute(
        "SELECT b.board_id, b.display_name FROM board b JOIN board_member m"
        " ON m.board_id = b.board_id WHERE m.member = ? AND m.access IN ('WORK','ADMIN')"
        " ORDER BY b.display_name", (ctx.user.id,)).fetchall()
    board_pairs = [(b["board_id"], b["display_name"]) for b in boards]
    if tk["board_id"] not in dict(board_pairs):
        board_pairs.insert(0, (tk["board_id"], tk["board_name"]))
    entities = ctx.conn.execute("SELECT entity_id, name FROM entity ORDER BY name").fetchall()
    dis = "" if can_work else " disabled"
    fields = (
        "<div class='card fields'><h3>Ticket</h3>"
        f"<form method=post action='/ticket/{wid}/update'>"
        f"<label>Board</label><select name=board_id{dis}>{_options(board_pairs, tk['board_id'])}</select>"
        f"<label>Status</label><select name=to_status{dis}>"
        f"{_options(([] if tk['board_status_id'] else [('', '(none)')]) + status_pairs, tk['board_status_id'] or '')}</select>"
        f"<label>Owner</label><input name=owner value='{t.esc(tk['owner'] or '')}'{dis}>"
        f"<label>Company</label><select name=entity_id{dis}>"
        f"{_options([(e['entity_id'], e['name']) for e in entities], tk['entity_id'] or '')}</select>"
        f"<label>Contact</label><input name=requested_by value='{t.esc(tk['requested_by'] or '')}'{dis}>"
        f"<label>Who is affected</label><select name=impact{dis}>{_options(WHO_IS_AFFECTED, tk['impact'])}</select>"
        f"<label>Is a patient waiting</label><select name=urgency{dis}>{_options(PATIENT_WAITING, tk['urgency'])}</select>"
        f"<label>Priority</label><div class=ro>{t.badge(tk['priority'])} from the matrix — never typed</div>"
        + ("<div style='margin-top:12px'><button type=submit>Save changes</button></div>" if can_work else "")
        + "</form></div>")

    total = sum(r["band_hours"] for r in time_rows)
    time_list = "".join(
        f"<dt>{t.esc(r['worked_on'])}</dt><dd>{t.esc(r['performed_by'])} · {r['band_hours']:g} h · "
        f"{t.esc(CHARGE_LABEL.get(r['charge_method'], r['charge_method']))}</dd>" for r in time_rows)
    time_card = (f"<div class=card><h3>Time · {total:g} h</h3>"
                 + (f"<dl class=kv>{time_list}</dl>" if time_list else "<div class=muted>None booked.</div>")
                 + (f"<p class=why>{t.esc(why_not)}</p>" if not may else "") + "</div>")
    commercial = (
        "<div class=card><h3>Commercial basis</h3><dl class=kv>"
        f"<dt>Contract basis</dt><dd>{t.esc(tk['contract_basis'])}</dd>"
        f"<dt>Path</dt><dd>{t.esc(tk['path'])}</dd>"
        f"<dt>Variation</dt><dd>{t.esc(tk['variation_id'] or '—')}</dd></dl></div>")
    details = (
        "<div class=card><h3>Details</h3><dl class=kv>"
        f"<dt>Opened</dt><dd>{t.esc(tk['opened_at'])}</dd>"
        f"<dt>Updated</dt><dd>{t.esc(common.human_age(tk['updated_at'] or tk['opened_at'], now=ctx.now))} ago</dd>"
        f"<dt>Source</dt><dd>{t.esc((tk['intake_source'] or '—').replace('_', '-').title())}</dd>"
        f"<dt>Desk ref</dt><dd>{t.esc(tk['external_ref'] or '—')}</dd>"
        f"<dt>Calendar</dt><dd>{t.esc(tk['calendar_name'] or '—')}</dd></dl></div>")

    body = header + strip + f"<div class=rail>{left}<div>{fields}{time_card}{commercial}{details}</div></div>"
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
                        to_status_id=f.get("to_status") or None)
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
        if to_board and to_board != tk["board_id"]:
            common.require_board(ctx, to_board, need="WORK")
            engine.move(ctx.conn, work_item_id, to_board, at=ctx.now, actor=ctx.user.id,
                        reason="moved on the ticket")
            changed.append(f"moved to {to_board}")
        impact = f.get("impact") if f.get("impact") in dict(WHO_IS_AFFECTED) else None
        urgency = f.get("urgency") if f.get("urgency") in dict(PATIENT_WAITING) else None
        changed += engine.update_fields(
            ctx.conn, work_item_id, at=ctx.now, actor=ctx.user.id,
            owner=f.get("owner"), entity_id=f.get("entity_id") or None,
            requested_by=f.get("requested_by"), impact=impact, urgency=urgency)
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
    v = values or {}
    boards = ctx.conn.execute(
        "SELECT b.board_id, b.display_name FROM board b JOIN board_member m"
        " ON m.board_id = b.board_id WHERE m.member = ? AND m.access IN ('WORK','ADMIN')"
        " ORDER BY b.is_unrouted, b.display_name", (ctx.user.id,)).fetchall()
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
        "<h1>New ticket</h1><p class=sub>For the desk: a call, a walk-up, something you saw. "
        "Priority is computed from the two questions, never chosen.</p>"
        "<div class=card><form method=post action='/ticket/new'><div class=grid2>"
        f"<div><label>Board</label><select name=board_id>{_options([(b['board_id'], b['display_name']) for b in boards], v.get('board_id', ''))}</select></div>"
        f"<div><label>Source</label><select name=source>{_options(SOURCES, v.get('source', 'PHONE'))}</select></div>"
        f"<div><label>Company</label><select name=entity_id>{_options([(e['entity_id'], e['name']) for e in entities], v.get('entity_id', 'PMC'))}</select></div>"
        f"<div><label>Contact</label><input name=requested_by value='{t.esc(v.get('requested_by', ''))}' placeholder='name or email of who asked'></div>"
        f"<div style='grid-column:1/-1'><label>Summary</label><input name=summary required value='{t.esc(v.get('summary', ''))}' placeholder='What is wrong, in one line'></div>"
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
            owner=f.get("owner", "").strip() or None, source=source, event_kind="OPENED")
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
