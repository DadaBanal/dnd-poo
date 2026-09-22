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


def index(ctx):
    from .. import Response
    admin_boards = [r["board_id"] for r in ctx.conn.execute(
        "SELECT board_id FROM board_member WHERE member = ? AND access = 'ADMIN'"
        " ORDER BY board_id", (ctx.user.id,))]

    cards = []
    for bid in admin_boards:
        board = ctx.conn.execute("SELECT display_name FROM board WHERE board_id = ?",
                                (bid,)).fetchone()
        statuses = ctx.conn.execute(
            "SELECT name, escalation_status, is_closed, is_default, inactive"
            "  FROM board_status WHERE board_id = ? ORDER BY sort_order, name", (bid,)).fetchall()
        status_rows = "".join(
            f"<tr><td>{t.esc(s['name'])}</td><td>{t.esc(s['escalation_status'])}</td>"
            f"<td>{'closed' if s['is_closed'] else ''}"
            f"{' · default' if s['is_default'] else ''}"
            f"{' · retired' if s['inactive'] else ''}</td></tr>"
            for s in statuses) or "<tr><td colspan=3 class='muted'>No statuses yet.</td></tr>"

        esc_opts = "".join(f"<option>{e}</option>" for e in ESCALATIONS)
        members = ctx.conn.execute(
            "SELECT member, access FROM board_member WHERE board_id = ? ORDER BY member",
            (bid,)).fetchall()
        member_rows = "".join(
            f"<tr><td>{t.esc(m['member'])}</td><td>{t.esc(m['access'])}</td></tr>"
            for m in members)

        cards.append(
            f"<div class='card'><h3>{t.esc(board['display_name'])} — statuses</h3>"
            "<div class='tablewrap'><table><thead><tr><th>Name</th><th>Milestone</th>"
            f"<th>Flags</th></tr></thead><tbody>{status_rows}</tbody></table></div>"
            "<form method='post' action='/admin/status/add' "
            "style='display:flex;gap:8px;flex-wrap:wrap;align-items:end;margin-top:12px'>"
            f"<input type='hidden' name='board_id' value='{t.esc(bid)}'>"
            "<div><label>Name</label><input name='name' required></div>"
            f"<div><label>Milestone</label><select name='escalation'>{esc_opts}</select></div>"
            "<div><label>Closed?</label><select name='is_closed'>"
            "<option value='0'>no</option><option value='1'>yes</option></select></div>"
            "<button type='submit'>Add status</button></form>"
            "<h3 style='margin-top:18px'>Membership</h3>"
            "<div class='tablewrap'><table><thead><tr><th>Member</th><th>Access</th>"
            f"</tr></thead><tbody>{member_rows}</tbody></table></div>"
            "<form method='post' action='/admin/member/add' "
            "style='display:flex;gap:8px;flex-wrap:wrap;align-items:end;margin-top:12px'>"
            f"<input type='hidden' name='board_id' value='{t.esc(bid)}'>"
            "<div><label>Member</label><input name='member' required></div>"
            "<div><label>Access</label><select name='access'>"
            "<option>READ</option><option>WORK</option><option>ADMIN</option>"
            "</select></div><button type='submit'>Add member</button></form></div>")

    if ctx.user.is_sysadmin:
        cards.append(_local_accounts_card(ctx))
        cards.append(_config_overview_card(ctx))

    if not cards:
        cards.append("<div class='card'><div class='empty'>You administer no boards, "
                     "and are not a system administrator. Nothing to configure here.</div></div>")

    body = ("<h1>Admin</h1><p class='sub'>Configuration lives in data, not in a "
            "deployment (§12). Board settings take board admin; break-glass "
            "accounts take a system administrator.</p>" + "".join(cards))
    return Response(body=t.page("Admin", body, user=ctx.user, active="admin"))


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
            ctx.conn.commit()
        except Exception:
            ctx.conn.rollback()
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
