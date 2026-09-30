"""Setup > API tokens: mint, see, disable (gap 8's tokens, now on a page).

A token is a machine's credential for one board at one scope (RAISE, READ,
WRITE). Until now it was minted from the command line on the host and
never listed anywhere. Here a system administrator mints one (the token is
shown once and never stored; only its hash is), sees every token with its
board, scope, who made it and when it was last used, and disables one.
Disabling is the only undo: a lost token is disabled and a new one minted.
"""
from __future__ import annotations

import urllib.parse

from ... import db
from .. import api
from .. import templates as t
from . import common


def _back(**q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    return redirect("/admin/api-tokens" + ("?" + urllib.parse.urlencode(q) if q else ""))


def index(ctx):
    from .. import Response
    common.require_sysadmin(ctx)
    q = ctx.request.query
    rows = ctx.conn.execute("SELECT k.*, b.display_name AS board_name FROM api_token k JOIN board b ON b.board_id = k.board_id"
                            " ORDER BY k.disabled, k.created_at DESC").fetchall()
    shown = ""
    if q.get("token"):
        shown = ("<div class='banner ok'>The new token, shown once. Give it to the system that will use it and close this "
                 f"page:<br><code>{t.esc(q['token'])}</code></div>")
    trs = "".join(
        f"<tr{' style=opacity:.6' if r['disabled'] else ''}><td>{t.esc(r['token_id'])}</td><td><b>{t.esc(r['label'])}</b></td>"
        f"<td>{t.esc(r['board_name'])}</td><td><span class=pill>{t.esc(api.scope_of(r))}</span></td>"
        f"<td class=muted>{t.esc(r['created_at'])} · {t.esc(r['created_by'])}</td><td class=muted>{t.esc(r['last_used_at'] or 'never')}</td>"
        f"<td>{'disabled' if r['disabled'] else 'live'}</td>"
        f"<td><form method=post action='/admin/api-tokens/{t.esc(r['token_id'])}/toggle' class=inline>"
        f"<button class='ghost small' type=submit>{'Enable' if r['disabled'] else 'Disable'}</button></form></td></tr>" for r in rows)
    boards = ctx.conn.execute("SELECT board_id, display_name FROM board WHERE COALESCE(inactive, 0) = 0 ORDER BY display_name").fetchall()
    board_opts = "".join(f"<option value='{t.esc(b['board_id'])}'>{t.esc(b['display_name'])}</option>" for b in boards)
    scope_opts = "".join(f"<option value={s}{' selected' if s == 'RAISE' else ''}>{s}</option>" for s in api.SCOPES)
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "") + shown
            + "<h1>API tokens</h1><p class=sub>A machine's credential for one board at one scope: RAISE opens tickets and "
              "reads the ones it raised; READ lists and reads every ticket on the board and the configurations; WRITE adds "
              "a note, a status or an owner as well. The token is shown once when minted and never stored. A token for a "
              "restricted board is minted deliberately, and every read on that board is audited. <a href='/admin'>Setup</a></p>"
              "<div class=card><div class=tablewrap><table><thead><tr><th>Id</th><th>Label</th><th>Board</th><th>Scope</th>"
              "<th>Made</th><th>Last used</th><th>State</th><th></th></tr></thead><tbody>"
            + (trs or "<tr><td colspan=8 class=muted>No token yet.</td></tr>") + "</tbody></table></div></div>"
              "<div class=card><h3>" + t.icon("plus") + "Mint a token</h3>"
              "<form method=post action='/admin/api-tokens/new' class=grid2>"
              "<div><label>Label (what it is for)</label><input name=label required maxlength=200 placeholder='Orthanc monitoring'></div>"
              f"<div><label>Board</label><select name=board_id>{board_opts}</select></div>"
              f"<div><label>Scope</label><select name=scope>{scope_opts}</select></div>"
              "<div style='align-self:end'><button type=submit>Mint</button></div></form></div>")
    return Response(body=t.page("API tokens", body, user=ctx.user, active="admin"))


def create(ctx):
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    try:
        token_id, token = api.create_token(ctx.conn, label=f.get("label", ""), board_id=f.get("board_id", ""),
                                           scope=f.get("scope", "RAISE"), at=ctx.now, created_by=ctx.user.id)
        ctx.conn.commit()
    except ValueError as exc:
        ctx.conn.rollback()
        return _back(err=str(exc))
    return _back(token=token, msg=f"{token_id} minted.")


def toggle(ctx, token_id):
    from .. import HttpError
    common.require_sysadmin(ctx)
    row = ctx.conn.execute("SELECT token_id, disabled, label FROM api_token WHERE token_id = ?", (token_id,)).fetchone()
    if row is None:
        raise HttpError("404 Not Found", "No such token.")
    now_disabled = 0 if row["disabled"] else 1
    ctx.conn.execute("UPDATE api_token SET disabled = ? WHERE token_id = ?", (now_disabled, token_id))
    db.audit(ctx.conn, at=ctx.now.isoformat(sep=" ", timespec="minutes"), actor=ctx.user.id,
             action="API_TOKEN_DISABLE" if now_disabled else "API_TOKEN_ENABLE", subject_kind="api_token",
             subject_id=token_id, detail=row["label"])
    ctx.conn.commit()
    return _back(msg=f"{token_id} {'disabled' if now_disabled else 'enabled'}.")
