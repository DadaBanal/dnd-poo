"""Setup > Audit: the audit trail the desk has always written, read (054).

Every change writes audit_event: who, when, what, on which record, and
since 054 where from (the desk, the portal, the API, the mail pickup, the
rules runner, a command on the host). This page is the first thing an
inspection asks for: filter by person, action, record, source and date;
export the answer as CSV. A system administrator's page. A row about a
ticket on a restricted board the reader is not a member of shows its
number and the action, never its detail (section 6.1: the contents of a
restricted board stay with its members).
"""
from __future__ import annotations

import csv
import io
import urllib.parse

from ... import db
from .. import templates as t
from . import common

PAGE = 200
MAX_EXPORT = 20000


def _filters(ctx) -> tuple[list[str], list, dict]:
    q = ctx.request.query
    f = {k: (q.get(k, "") or "").strip() for k in ("actor", "action", "kind", "subject", "source", "since", "until", "text")}
    where, params = ["1 = 1"], []
    if f["actor"]:
        where.append("LOWER(a.actor) = LOWER(?)"); params.append(f["actor"])
    if f["action"]:
        where.append("a.action = ?"); params.append(f["action"])
    if f["kind"]:
        where.append("a.subject_kind = ?"); params.append(f["kind"])
    if f["subject"]:
        where.append("a.subject_id = ?"); params.append(f["subject"])
    if f["source"]:
        if f["source"] == "UNKNOWN":
            where.append("a.source IS NULL")
        else:
            where.append("a.source = ?"); params.append(f["source"])
    if f["since"]:
        where.append("a.occurred_at >= ?"); params.append(f["since"])
    if f["until"]:
        where.append("a.occurred_at < ?"); params.append(f["until"] + " 24:00")
    if f["text"]:
        where.append("a.detail LIKE ?"); params.append(f"%{f['text']}%")
    return where, params, f


def _rows(ctx, where, params, *, limit: int, offset: int = 0):
    return ctx.conn.execute(
        "SELECT a.*, b.board_id AS ticket_board, b.restricted AS ticket_restricted"
        "  FROM audit_event a"
        "  LEFT JOIN ticket tk ON a.subject_kind IN ('ticket', 'work_item') AND tk.work_item_id = a.subject_id"
        "  LEFT JOIN board b ON b.board_id = tk.board_id"
        " WHERE " + " AND ".join(where) + " ORDER BY a.audit_id DESC LIMIT ? OFFSET ?",
        (*params, limit, offset)).fetchall()


def _masked(ctx, row, boards) -> bool:
    return bool(row["ticket_restricted"]) and row["ticket_board"] not in boards


def index(ctx):
    from .. import Response
    common.require_sysadmin(ctx)
    q = ctx.request.query
    where, params, f = _filters(ctx)
    try:
        page = max(int(q.get("page", "1")), 1)
    except ValueError:
        page = 1
    rows = _rows(ctx, where, params, limit=PAGE + 1, offset=(page - 1) * PAGE)
    more = len(rows) > PAGE
    rows = rows[:PAGE]
    total = ctx.conn.execute("SELECT COUNT(*) FROM audit_event a WHERE " + " AND ".join(where), params).fetchone()[0]
    boards = common.board_ids_for(ctx)
    actions = [r[0] for r in ctx.conn.execute("SELECT DISTINCT action FROM audit_event ORDER BY action")]
    kinds = [r[0] for r in ctx.conn.execute("SELECT DISTINCT subject_kind FROM audit_event ORDER BY subject_kind")]

    def opts(values, chosen, *, words=None):
        return "<option value=''>Any</option>" + "".join(
            f"<option value='{t.esc(v)}'{' selected' if v == chosen else ''}>{t.esc((words or {}).get(v, v))}</option>" for v in values)

    trs = "".join(
        f"<tr><td class=muted>{t.esc(r['occurred_at'])}</td><td>{t.esc(r['actor'])}</td>"
        f"<td><span class=pill>{t.esc(r['action'])}</span></td>"
        f"<td>{t.esc(r['subject_kind'])}{' · ' + t.esc(r['subject_id']) if r['subject_id'] else ''}"
        + (" <span class=pill>restricted</span>" if r["ticket_restricted"] else "") + "</td>"
        f"<td>{t.esc(r['source'] or '')}</td>"
        f"<td>{'<span class=muted>(a restricted board you are not on)</span>' if _masked(ctx, r, boards) else t.esc(r['detail'] or '')}"
        + (f"<br><b>Override:</b> {t.esc(r['override_reason'])}" if r["override_reason"] and not _masked(ctx, r, boards) else "") + "</td></tr>"
        for r in rows)
    keep = {k: v for k, v in f.items() if v}
    qs = lambda **k: urllib.parse.urlencode({**keep, **k})
    nav = ((f"<a class='btn ghost' href='/admin/audit?{qs(page=page - 1)}'>‹ Newer</a> " if page > 1 else "")
           + (f"<a class='btn ghost' href='/admin/audit?{qs(page=page + 1)}'>Older ›</a>" if more else ""))
    body = ("<h1>Audit</h1><p class=sub>Every change the desk has written since it started: who, when, what, on which "
            "record, and where from. Filter, then export the answer. A row about a ticket on a restricted board you are "
            "not a member of shows its number and the action, never its words. <a href='/admin'>Setup</a></p>"
            "<div class=card><form method=get action='/admin/audit' class=grid2>"
            f"<div><label>Who</label><input name=actor value='{t.esc(f['actor'])}' placeholder='a member, intake, rules'></div>"
            f"<div><label>Action</label><select name=action>{opts(actions, f['action'])}</select></div>"
            f"<div><label>Record kind</label><select name=kind>{opts(kinds, f['kind'])}</select></div>"
            f"<div><label>Record</label><input name=subject value='{t.esc(f['subject'])}' placeholder='PMC-000123, IT_HELP, jcruz'></div>"
            f"<div><label>Source</label><select name=source>{opts(list(db.SOURCES) + ['UNKNOWN'], f['source'], words={'UNKNOWN': 'Unknown (before 054)'})}</select></div>"
            f"<div><label>Words in the detail</label><input name=text value='{t.esc(f['text'])}'></div>"
            f"<div><label>From</label><input type=date name=since value='{t.esc(f['since'])}'></div>"
            f"<div><label>To</label><input type=date name=until value='{t.esc(f['until'])}'></div>"
            "<div class=row><button type=submit>Show</button> "
            f"<a class='btn ghost' href='/admin/audit.csv?{qs()}'>CSV</a></div></form></div>"
            f"<div class=card><p class=muted>{total} row(s) match; showing {len(rows)} from {(page - 1) * PAGE + 1 if rows else 0}.</p>"
            "<div class=tablewrap><table><thead><tr><th>When</th><th>Who</th><th>Action</th><th>Record</th><th>Source</th><th>Detail</th></tr></thead><tbody>"
            + (trs or "<tr><td colspan=6 class=muted>Nothing matches.</td></tr>") + "</tbody></table></div>"
            f"<div class=row style='margin-top:10px'>{nav}</div></div>")
    return Response(body=t.page("Audit", body, user=ctx.user, active="admin"))


def export(ctx):
    from .. import Response
    common.require_sysadmin(ctx)
    where, params, f = _filters(ctx)
    rows = _rows(ctx, where, params, limit=MAX_EXPORT)
    boards = common.board_ids_for(ctx)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["occurred_at", "actor", "action", "subject_kind", "subject_id", "source", "detail", "override_reason"])
    for r in rows:
        masked = _masked(ctx, r, boards)
        w.writerow([r["occurred_at"], r["actor"], r["action"], r["subject_kind"], r["subject_id"] or "", r["source"] or "",
                    "(a restricted board you are not on)" if masked else (r["detail"] or ""),
                    "" if masked else (r["override_reason"] or "")])
    db.audit(ctx.conn, at=ctx.now.isoformat(sep=" ", timespec="minutes"), actor=ctx.user.id, action="AUDIT_EXPORT",
             subject_kind="audit", detail=f"{len(rows)} row(s); filters " + (", ".join(f"{k}={v}" for k, v in f.items() if v) or "none"))
    ctx.conn.commit()
    return Response(body=out.getvalue(), content_type="text/csv; charset=utf-8",
                    headers=[("Content-Disposition", f"attachment; filename=audit-{ctx.now.date().isoformat()}.csv")])
