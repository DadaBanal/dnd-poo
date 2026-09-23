"""The admin surface — the §12 fence made operable.

The fence says no rule, floor, SLA or board configuration is hard-coded: if PMC
cannot change it without a deployment, it is in the wrong place. Today all of it
is editable only by SQL, which is the same failure wearing a different hat. This
surface closes that hole for the things Phase B owns: board statuses, board
membership, and disabling a break-glass account.

Access splits the way the data does. Board statuses and membership are
board-scoped, so they take ADMIN on that board. Break-glass accounts are
cross-board, so disabling one takes the sysadmin flag — and creating one is not
here at all: that stays CLI-only, by the auth design, so no web path can mint a
credential.
"""
from __future__ import annotations

import re

from ... import db
from .. import templates as t
from . import common

ESCALATIONS = ("NOT_RESPONDED", "RESPONDED", "RESOLUTION_PLAN", "RESOLVED", "NO_ESCALATION")


def _slug(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_") or "STATUS"


def _admin_boards(ctx) -> list:
    return ctx.conn.execute(
        "SELECT b.board_id, b.display_name, b.calendar_id, b.restricted, b.is_unrouted"
        "  FROM board b JOIN board_member m ON m.board_id = b.board_id"
        " WHERE m.member = ? AND m.access = 'ADMIN' ORDER BY b.display_name",
        (ctx.user.id,)).fetchall()


def index(ctx):
    """Setup home: the boards this user administers, each with what it still
    lacks, and the cross-board cards for a system administrator."""
    from .. import Response
    from ... import setup
    msg = ctx.request.query.get("msg", "")
    rows = []
    for b in _admin_boards(ctx):
        missing = setup.readiness(ctx.conn, b["board_id"])
        n = ctx.conn.execute("SELECT COUNT(*) FROM ticket WHERE board_id = ?",
                             (b["board_id"],)).fetchone()[0]
        state = ("<span class='chip sla-ok'>ready</span>" if not missing else
                 "<span class='chip sla-warn'>needs: " + t.esc("; ".join(missing)) + "</span>")
        flags = (" <span class=pill>restricted</span>" if b["restricted"] else "") + \
                (" <span class=pill>unrouted queue</span>" if b["is_unrouted"] else "")
        rows.append(f"<tr><td><a href='/admin/board/{t.esc(b['board_id'])}'><b>"
                    f"{t.esc(b['display_name'])}</b></a>{flags}</td><td>{state}</td>"
                    f"<td>{n}</td><td><a class='btn ghost' href='/admin/board/{t.esc(b['board_id'])}'>"
                    "Set up</a></td></tr>")
    cards = []
    if rows:
        cards.append("<div class=card><h3>Your boards</h3><div class=tablewrap><table>"
                     "<thead><tr><th>Board</th><th>Setup</th><th>Tickets</th><th></th></tr></thead>"
                     "<tbody>" + "".join(rows) + "</tbody></table></div></div>")
    if ctx.user.is_sysadmin:
        cards.append(_local_accounts_card(ctx))
        cards.append(_config_overview_card(ctx))
    if not cards:
        cards.append("<div class='card'><div class='empty'>You administer no boards, "
                     "and are not a system administrator. Nothing to configure here.</div></div>")
    body = ((f"<div class='banner ok'>{t.esc(msg)}</div>" if msg else "") +
            "<h1>Setup</h1><p class='sub'>Configuration lives in data, not in a "
            "deployment (§12). Board settings take board admin; break-glass "
            "accounts take a system administrator. Every change is audited.</p>" + "".join(cards))
    return Response(body=t.page("Setup", body, user=ctx.user, active="admin"))


TABS = (("board", "Board"), ("statuses", "Statuses"), ("sla", "SLA"), ("members", "Members & roles"))
ROLES = ("SERVICE_MANAGER", "DISPATCH", "ON_CALL", "DUTY_MANAGER")
ESC_LABEL = {"NOT_RESPONDED": "Not responded", "RESPONDED": "Responded",
             "RESOLUTION_PLAN": "Resolution plan", "RESOLVED": "Resolved",
             "NO_ESCALATION": "Waiting (pauses resolve)"}


def board_setup(ctx, board_id):
    from .. import HttpError, Response
    from ... import setup
    common.require_board(ctx, board_id, need="ADMIN")
    b = ctx.conn.execute("SELECT * FROM board WHERE board_id = ?", (board_id,)).fetchone()
    if b is None:
        raise HttpError("404 Not Found", "No such board.")
    tab = ctx.request.query.get("tab", "statuses")
    msg = ctx.request.query.get("msg", "")
    bid = t.esc(board_id)
    tabs = "<div class=stabs>" + "".join(
        f"<a class='{'on' if tab == k else ''}' href='/admin/board/{bid}?tab={k}'>{v}</a>"
        for k, v in TABS) + "</div>"
    missing = setup.readiness(ctx.conn, board_id)
    ready = ("" if not missing else
             f"<div class=note-ph>This board still needs {t.esc('; '.join(missing))}. "
             f"<form class=inline method=post action='/admin/board/{bid}/starter'>"
             "<button type=submit style='padding:3px 10px;margin-left:6px'>Apply the starter setup</button>"
             "</form> It adds only what is missing and never overwrites a change.</div>")

    if tab == "board":
        cals = ctx.conn.execute("SELECT calendar_id, name FROM calendar ORDER BY name").fetchall()
        cal_opts = "<option value=''>(none — no clocks)</option>" + "".join(
            f"<option value='{t.esc(c['calendar_id'])}'{' selected' if c['calendar_id'] == b['calendar_id'] else ''}>"
            f"{t.esc(c['name'])}</option>" for c in cals)
        content = (
            "<div class=card><h3>Board</h3><dl class=kv>"
            f"<dt>Name</dt><dd>{t.esc(b['display_name'])}</dd>"
            f"<dt>Fulfiller group</dt><dd>{t.esc(b['fulfiller_group'])}</dd>"
            f"<dt>Restricted</dt><dd>{'yes — members only, every read audited' if b['restricted'] else 'no'}</dd>"
            f"<dt>Closed loop required</dt><dd>{'yes' if b['closed_loop_required'] else 'no'}</dd></dl>"
            f"<form method=post action='/admin/board/{bid}/calendar' class=row style='margin-top:14px'>"
            f"<div><label>Calendar the SLA clocks run on</label><select name=calendar_id>{cal_opts}</select></div>"
            "<div style='flex:0 0 auto'><button type=submit>Save</button></div></form>"
            f"<form method=post action='/admin/board/{bid}/starter' style='margin-top:14px'>"
            "<button class=ghost type=submit>Apply the starter setup</button> "
            "<span class=why>Adds any missing statuses, calendars and SLA targets. Never overwrites.</span>"
            "</form></div>")
    elif tab == "sla":
        targets = {(r["priority"], r["clock"]): r["target_minutes"] for r in ctx.conn.execute(
            "SELECT priority, clock, target_minutes FROM sla_target WHERE board_id = ?", (board_id,))}
        rows = "".join(
            f"<tr><td>{t.badge(p)}</td>" + "".join(
                f"<td><input name='t_{p}_{c}' value='{targets.get((p, c), '')}' inputmode=numeric "
                "style='width:100px'> min</td>" for c in setup.CLOCKS) + "</tr>"
            for p in ("P1", "P2", "P3", "P4"))
        content = (
            "<div class=card><h3>SLA targets</h3><div class=note-ph>Measured and reported, "
            "<b>not enforced or promised</b> (every target is enforced = 0). A blank cell means "
            "that clock does not start for that priority. Changes apply to tickets opened after "
            "saving; a ticket's priority change re-targets its running clocks.</div>"
            f"<form method=post action='/admin/board/{bid}/sla'><table class=edit><thead><tr>"
            "<th>Priority</th><th>Respond</th><th>Resolution plan</th><th>Resolve</th></tr></thead>"
            f"<tbody>{rows}</tbody></table><div style='margin-top:12px'>"
            "<button type=submit>Save targets</button></div></form></div>")
    elif tab == "members":
        members = ctx.conn.execute("SELECT member, access FROM board_member WHERE board_id = ?"
                                   " ORDER BY member", (board_id,)).fetchall()
        named = {r["role"]: r["member"] for r in ctx.conn.execute(
            "SELECT role, member FROM board_role WHERE board_id = ?", (board_id,))}
        member_rows = "".join(f"<tr><td>{t.esc(m['member'])}</td><td>{t.esc(m['access'])}</td></tr>"
                              for m in members)
        role_rows = "".join(
            f"<div><label>{t.esc(r.replace('_', ' ').title())}</label>"
            f"<input name='{r}' value='{t.esc(named.get(r, ''))}' placeholder='a named person'></div>"
            for r in ROLES)
        content = (
            "<div class=card><h3>Members</h3><div class=tablewrap><table><thead><tr><th>Member</th>"
            f"<th>Access</th></tr></thead><tbody>{member_rows}</tbody></table></div>"
            "<form method=post action='/admin/member/add' class=row style='margin-top:12px'>"
            f"<input type=hidden name=board_id value='{bid}'><input type=hidden name=back value='members'>"
            "<div><label>Member</label><input name=member required></div>"
            "<div><label>Access</label><select name=access><option>READ</option><option selected>WORK"
            "</option><option>ADMIN</option></select></div>"
            "<div style='flex:0 0 auto'><button type=submit>Add or change</button></div></form></div>"
            "<div class=card><h3>The four board roles</h3><p class=sub>ConnectWise's own: Service "
            "Manager, Dispatch, On-Call and Duty Manager (who is told when On-Call does not "
            "answer). The rota on the On-call page overrides the named On-Call.</p>"
            f"<form method=post action='/admin/board/{bid}/roles'><div class=grid2>{role_rows}</div>"
            "<div style='margin-top:12px'><button type=submit>Save roles</button></div></form></div>")
    else:
        statuses = ctx.conn.execute(
            "SELECT * FROM board_status WHERE board_id = ? ORDER BY inactive, sort_order, name",
            (board_id,)).fetchall()

        def cb(name, v):
            return f"<input type=checkbox name={name} value=1{' checked' if v else ''} style='width:auto'>"

        rows = []
        for st in statuses:
            sid = t.esc(st["board_status_id"])
            esc_opts = "".join(f"<option value='{k}'{' selected' if k == st['escalation_status'] else ''}>"
                               f"{t.esc(v)}</option>" for k, v in ESC_LABEL.items())
            rows.append(
                f"<tr{' style=opacity:.55' if st['inactive'] else ''}>"
                f"<td><form id='s_{sid}' method=post action='/admin/board/{bid}/status/save'>"
                f"<input type=hidden name=board_status_id value='{sid}'></form>"
                f"<input form='s_{sid}' name=sort_order value='{st['sort_order']}' style='width:60px'></td>"
                f"<td><input form='s_{sid}' name=name value='{t.esc(st['name'])}'></td>"
                f"<td><input form='s_{sid}' name=customer_description value='{t.esc(st['customer_description'] or '')}'></td>"
                f"<td><select form='s_{sid}' name=escalation_status>{esc_opts}</select></td>"
                + "".join(f"<td>{cb(n, st[c]).replace('<input', f'<input form=s_{sid}', 1)}</td>" for n, c in (
                    ("is_default", "is_default"), ("is_closed", "is_closed"),
                    ("time_entry_allowed", "time_entry_allowed"), ("display_on_board", "display_on_board"),
                    ("inactive", "inactive")))
                + f"<td><button form='s_{sid}' class=ghost type=submit style='padding:4px 10px'>Save</button></td></tr>")
        esc_opts = "".join(f"<option value='{k}'>{t.esc(v)}</option>" for k, v in ESC_LABEL.items())
        content = (
            "<div class=card><h3>Statuses</h3><div class=tablewrap><table class=edit><thead><tr>"
            "<th>Order</th><th>Name (desk)</th><th>Requester sees</th><th>SLA milestone</th>"
            "<th>Default</th><th>Closes</th><th>Time allowed</th><th>On board</th><th>Retired</th>"
            "<th></th></tr></thead><tbody>" + ("".join(rows) or
            "<tr><td colspan=10 class=muted>No statuses yet — apply the starter setup above.</td></tr>")
            + "</tbody></table></div><p class=sub style='margin:10px 0 0'>Statuses are retired, "
            "never deleted: tickets that sat in one keep their history.</p>"
            "<h3 style='margin-top:16px'>Add a status</h3>"
            f"<form method=post action='/admin/board/{bid}/status/add' class=row>"
            "<div><label>Name</label><input name=name required></div>"
            "<div><label>Requester sees</label><input name=customer_description></div>"
            f"<div><label>SLA milestone</label><select name=escalation>{esc_opts}</select></div>"
            "<div style='flex:0 0 auto'><label>Closes</label><select name=is_closed><option value=0>no"
            "</option><option value=1>yes</option></select></div>"
            "<div style='flex:0 0 auto'><button type=submit>Add status</button></div></form></div>")

    body = ((f"<div class='banner ok'>{t.esc(msg)}</div>" if msg else "") +
            f"<h1>Setup · {t.esc(b['display_name'])}</h1><p class=sub>The board's own vocabulary, "
            "as a ConnectWise service board setup table. <a href='/admin'>All boards</a></p>"
            + ready + tabs + content)
    return Response(body=t.page("Setup", body, user=ctx.user, active="admin"))


def _done(board_id, tab, msg):
    from .. import redirect
    import urllib.parse
    return redirect(f"/admin/board/{board_id}?" + urllib.parse.urlencode({"tab": tab, "msg": msg}))


def _audit(ctx, board_id, detail):
    db.audit(ctx.conn, at=ctx.now.isoformat(sep=" ", timespec="minutes"), actor=ctx.user.id,
             action="BOARD_CONFIG", subject_kind="board", subject_id=board_id, detail=detail)


def apply_starter(ctx, board_id):
    from ... import setup
    common.require_board(ctx, board_id, need="ADMIN")
    r = setup.apply_starter(ctx.conn, board_id, actor=ctx.user.id, at=ctx.now)
    ctx.conn.commit()
    return _done(board_id, "statuses", f"Starter applied: {r['statuses']} statuses, "
                                       f"{r['targets']} SLA targets added")


def save_calendar(ctx, board_id):
    common.require_board(ctx, board_id, need="ADMIN")
    cal = ctx.request.form().get("calendar_id") or None
    if cal and ctx.conn.execute("SELECT 1 FROM calendar WHERE calendar_id = ?", (cal,)).fetchone() is None:
        return _done(board_id, "board", "No such calendar")
    ctx.conn.execute("UPDATE board SET calendar_id = ? WHERE board_id = ?", (cal, board_id))
    _audit(ctx, board_id, f"calendar -> {cal or 'none'}")
    ctx.conn.commit()
    return _done(board_id, "board", "Calendar saved")


def save_status(ctx, board_id):
    common.require_board(ctx, board_id, need="ADMIN")
    f = ctx.request.form()
    sid = f.get("board_status_id", "")
    row = ctx.conn.execute("SELECT * FROM board_status WHERE board_status_id = ? AND board_id = ?",
                           (sid, board_id)).fetchone()
    if row is None:
        return _done(board_id, "statuses", "No such status on this board")
    esc = f.get("escalation_status") if f.get("escalation_status") in ESCALATIONS else row["escalation_status"]
    flags = {k: 1 if f.get(k) == "1" else 0 for k in
             ("is_default", "is_closed", "time_entry_allowed", "display_on_board", "inactive")}
    if flags["is_default"] and (flags["is_closed"] or flags["inactive"]):
        return _done(board_id, "statuses", "Not saved: the default status cannot close or be retired")
    try:
        order = int(f.get("sort_order", row["sort_order"]))
    except ValueError:
        order = row["sort_order"]
    name = f.get("name", "").strip() or row["name"]
    try:
        if flags["is_default"]:
            ctx.conn.execute("UPDATE board_status SET is_default = 0 WHERE board_id = ?", (board_id,))
        ctx.conn.execute(
            "UPDATE board_status SET name = ?, customer_description = ?, escalation_status = ?,"
            " is_default = ?, is_closed = ?, time_entry_allowed = ?, display_on_board = ?,"
            " inactive = ?, sort_order = ? WHERE board_status_id = ?",
            (name, f.get("customer_description", "").strip() or None, esc, flags["is_default"],
             flags["is_closed"], flags["time_entry_allowed"], flags["display_on_board"],
             flags["inactive"], order, sid))
        _audit(ctx, board_id, f"status {sid} saved: {name}, {esc}, {flags}")
        ctx.conn.commit()
    except Exception as exc:                                 # noqa: BLE001
        ctx.conn.rollback()
        return _done(board_id, "statuses", f"Not saved: {exc}")
    return _done(board_id, "statuses", f"Saved {name}")


def add_board_status(ctx, board_id):
    common.require_board(ctx, board_id, need="ADMIN")
    f = ctx.request.form()
    name = f.get("name", "").strip()
    esc = f.get("escalation", "")
    if not name or esc not in ESCALATIONS:
        return _done(board_id, "statuses", "A name and a milestone are required")
    order = (ctx.conn.execute("SELECT MAX(sort_order) FROM board_status WHERE board_id = ?",
                              (board_id,)).fetchone()[0] or 0) + 10
    try:
        ctx.conn.execute(
            "INSERT INTO board_status (board_status_id, board_id, name, customer_description,"
            " escalation_status, is_closed, sort_order) VALUES (?,?,?,?,?,?,?)",
            (f"{board_id}.{_slug(name)}", board_id, name,
             f.get("customer_description", "").strip() or None, esc,
             1 if f.get("is_closed") == "1" else 0, order))
        _audit(ctx, board_id, f"status added: {name} ({esc})")
        ctx.conn.commit()
    except Exception as exc:                                 # noqa: BLE001
        ctx.conn.rollback()
        return _done(board_id, "statuses", f"Not added: {exc}")
    return _done(board_id, "statuses", f"Added {name}")


def save_sla(ctx, board_id):
    from ... import setup
    common.require_board(ctx, board_id, need="ADMIN")
    f = ctx.request.form()
    changed = 0
    for p in ("P1", "P2", "P3", "P4"):
        for c in setup.CLOCKS:
            raw = f.get(f"t_{p}_{c}", "").strip()
            if not raw:
                cur = ctx.conn.execute("DELETE FROM sla_target WHERE board_id = ? AND priority = ?"
                                       " AND clock = ?", (board_id, p, c))
                changed += cur.rowcount
                continue
            try:
                minutes = int(raw)
                if minutes <= 0:
                    raise ValueError
            except ValueError:
                ctx.conn.rollback()
                return _done(board_id, "sla", f"Not saved: {p} {c} must be a whole number of minutes")
            cur = ctx.conn.execute(
                "UPDATE sla_target SET target_minutes = ?, note = 'set on the Setup page'"
                " WHERE board_id = ? AND priority = ? AND clock = ? AND target_minutes <> ?",
                (minutes, board_id, p, c, minutes))
            changed += cur.rowcount
            cur = ctx.conn.execute(
                "INSERT OR IGNORE INTO sla_target (board_id, priority, clock, target_minutes,"
                " calendar, enforced, note) VALUES (?,?,?,?,'CLINICAL_24x7',0,'set on the Setup page')",
                (board_id, p, c, minutes))
            changed += cur.rowcount
    _audit(ctx, board_id, f"SLA targets saved ({changed} change(s))")
    ctx.conn.commit()
    return _done(board_id, "sla", f"Saved: {changed} change(s)")


def save_roles(ctx, board_id):
    common.require_board(ctx, board_id, need="ADMIN")
    f = ctx.request.form()
    for role in ROLES:
        who = f.get(role, "").strip()
        if who:
            ctx.conn.execute("INSERT OR REPLACE INTO board_role (board_id, role, member)"
                             " VALUES (?,?,?)", (board_id, role, who))
        else:
            ctx.conn.execute("DELETE FROM board_role WHERE board_id = ? AND role = ?", (board_id, role))
    _audit(ctx, board_id, "board roles saved")
    ctx.conn.commit()
    return _done(board_id, "members", "Roles saved")


def _local_accounts_card(ctx) -> str:
    rows = ctx.conn.execute(
        "SELECT username, is_sysadmin, disabled, last_login_at FROM local_account"
        " ORDER BY username").fetchall()
    trs = []
    for r in rows:
        disable = ""
        if not r["disabled"]:
            disable = ("<form method='post' action='/admin/local/disable' "
                       "style='display:inline'>"
                       f"<input type='hidden' name='username' value='{t.esc(r['username'])}'>"
                       "<button class='ghost' type='submit'>Disable</button></form>")
        trs.append(
            f"<tr><td>{t.esc(r['username'])}</td>"
            f"<td>{'sysadmin' if r['is_sysadmin'] else ''}</td>"
            f"<td>{'disabled' if r['disabled'] else 'active'}</td>"
            f"<td class='muted'>{t.esc(r['last_login_at'] or 'never')}</td>"
            f"<td>{disable}</td></tr>")
    body = "".join(trs) or "<tr><td colspan=5 class='muted'>No break-glass accounts.</td></tr>"
    return ("<div class='card'><h3>Break-glass accounts</h3>"
            "<p class='sub'>Created only by <code>psaspine create-local-account</code>. "
            "Disable here; the web never creates one.</p>"
            "<div class='tablewrap'><table><thead><tr><th>Username</th><th>Role</th>"
            f"<th>State</th><th>Last login</th><th></th></tr></thead><tbody>{body}"
            "</tbody></table></div></div>")


def _config_overview_card(ctx) -> str:
    counts = {}
    for label, table in (("Calendars", "calendar"), ("Clinical floors", "clinical_floor"),
                         ("Catalogue items", "catalogue_item"), ("SLA targets", "sla_target")):
        counts[label] = ctx.conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
    rows = "".join(f"<dt>{t.esc(k)}</dt><dd>{v}</dd>" for k, v in counts.items())
    return ("<div class='card'><h3>Cross-board configuration</h3>"
            "<p class='sub'>Calendars, floors and the catalogue are cross-board and "
            "still edited by the CLI and seed today; the counts are here so the fence "
            "is visible. Full editing of these is the next slice.</p>"
            f"<dl class='kv'>{rows}</dl></div>")


def add_status(ctx):
    from .. import redirect
    f = ctx.request.form()
    board_id = f.get("board_id", "")
    common.require_board(ctx, board_id, need="ADMIN")
    name = f.get("name", "").strip()
    escalation = f.get("escalation", "")
    is_closed = 1 if f.get("is_closed") == "1" else 0
    if name and escalation in ESCALATIONS:
        status_id = f"{board_id}.{_slug(name)}"
        try:
            ctx.conn.execute(
                "INSERT INTO board_status (board_status_id, board_id, name,"
                " escalation_status, is_closed) VALUES (?,?,?,?,?)",
                (status_id, board_id, name, escalation, is_closed))
            ctx.conn.commit()
        except Exception:
            ctx.conn.rollback()
    return redirect("/admin")


def add_member(ctx):
    from .. import redirect
    f = ctx.request.form()
    board_id = f.get("board_id", "")
    common.require_board(ctx, board_id, need="ADMIN")
    member = f.get("member", "").strip()
    access = f.get("access", "READ")
    if member and access in ("READ", "WORK", "ADMIN"):
        try:
            ctx.conn.execute(
                "INSERT OR REPLACE INTO board_member (board_id, member, access)"
                " VALUES (?,?,?)", (board_id, member, access))
            _audit(ctx, board_id, f"member {member} -> {access}")
            ctx.conn.commit()
        except Exception:
            ctx.conn.rollback()
    if f.get("back") == "members":
        return _done(board_id, "members", f"{member} saved")
    return redirect("/admin")


def disable_local(ctx):
    from .. import redirect
    common.require_sysadmin(ctx)
    username = ctx.request.form().get("username", "").strip()
    if username:
        ctx.conn.execute("UPDATE local_account SET disabled = 1 WHERE username = ?",
                         (username,))
        db.audit(ctx.conn, at=ctx.now.isoformat(sep=" ", timespec="minutes"),
                 actor=ctx.user.id, action="LOCAL_ACCOUNT_DISABLE",
                 subject_kind="local_account", subject_id=username,
                 detail="disabled via admin surface")
        ctx.conn.commit()
    return redirect("/admin")
