"""The report writer pages (042): build, run, save, share and pin a report.

Gated by the security role's REPORTS level: READ to run saved and shared
reports and build one-off ones, WRITE to save and share, ADMIN to pin a report
to the Reports page for everyone. Every run is limited to the viewer's boards
by the dataset's own code (psaspine/reportwriter.py).
"""
from __future__ import annotations

import urllib.parse

from ... import reportwriter as rw
from .. import templates as t
from . import common


def _back(path: str, **q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    return redirect(path + ("?" + urllib.parse.urlencode(q) if q else ""))


def _table(result: dict) -> str:
    if not result["headers"]:
        return "<div class=muted>Nothing to show: you are on no board this dataset covers.</div>"
    head = "".join(f"<th>{t.esc(h)}</th>" for h in result["headers"])
    rows = "".join("<tr>" + "".join(
        f"<td class=num>{v}</td>" if isinstance(v, (int, float)) else f"<td>{t.esc(v if v is not None else '')}</td>"
        for v in r) + "</tr>" for r in result["rows"][:1000])
    more = (f"<p class=why>Showing 1,000 of {len(result['rows'])} rows on screen; the CSV has them all.</p>"
            if len(result["rows"]) > 1000 else "")
    cap = "<p class=why>Stopped at 5,000 rows; narrow the dates or the board.</p>" if result["capped"] else ""
    return (f"<div class=tablewrap><table><thead><tr>{head}</tr></thead><tbody>"
            f"{rows or '<tr><td class=muted>No rows.</td></tr>'}</tbody></table></div>" + more + cap)


def _builder(ctx, dataset: str, cols, group_by, filters, *, name: str = "") -> str:
    ds = rw.DATASETS[dataset]
    boards = [(b["board_id"], b["display_name"]) for b in ctx.conn.execute(
        "SELECT board_id, display_name FROM board ORDER BY display_name") if b["board_id"] in common.board_ids_for(ctx)]
    ds_opts = "".join(f"<option value='{k}'{' selected' if k == dataset else ''}>{v['label']}</option>" for k, v in rw.DATASETS.items())
    checks = "".join(
        f"<label><input type=checkbox name=col value='{k}'{' checked' if k in cols else ''}> {t.esc(lab)}</label>"
        for k, (_, lab) in ds["columns"].items())
    group = "<option value=''>(no grouping: one row each)</option>" + "".join(
        f"<option value='{k}'{' selected' if k == group_by else ''}>{t.esc(lab)}</option>" for k, (_, lab) in ds["columns"].items())
    board_opts = "<option value=''>All my boards</option>" + "".join(
        f"<option value='{t.esc(k)}'{' selected' if k == filters.get('board') else ''}>{t.esc(n)}</option>" for k, n in boards)
    can_save = common.allows(ctx, "REPORTS", "WRITE")
    save = ("<div class=grid2 style='margin-top:10px'><div><label>Save as</label><input name=name maxlength=120 "
            f"value='{t.esc(name)}' placeholder='Hours by member, last month'></div>"
            "<div style='align-self:end'><label><input type=checkbox name=shared value=1> Share with everyone who uses Reports</label> "
            "<button type=submit formmethod=post formaction='/reports/custom/new'>Save</button></div></div>" if can_save else "")
    return ("<div class=card><form method=get action='/reports/custom/run'>"
            f"<div class=grid2><div><label>Dataset</label><select name=dataset onchange='this.form.action=\"/reports/custom\";this.form.submit()'>{ds_opts}</select></div>"
            f"<div><label>Group by</label><select name=group>{group}</select></div></div>"
            f"<fieldset class=q style='margin-top:10px'><legend>Columns (when not grouped)</legend><div class=choices>{checks}</div></fieldset>"
            "<div class=grid2>"
            f"<div><label>Board</label><select name=board>{board_opts}</select></div>"
            + (f"<div><label>State</label><input name=state value='{t.esc(filters.get('state', ''))}' placeholder='e.g. CLOSED'></div>" if ds["state"] else "<div></div>")
            + f"<div><label>From</label><input type=date name=from value='{t.esc(filters.get('from', ''))}'></div>"
            f"<div><label>To</label><input type=date name=to value='{t.esc(filters.get('to', ''))}'></div></div>"
            "<div style='margin-top:10px'><button type=submit class=ghost>Run</button> "
            "<noscript><button type=submit formaction='/reports/custom' class=ghost>Change dataset</button></noscript></div>"
            + save + "</form></div>")


def _args(ctx):
    q = ctx.request.query
    dataset = q.get("dataset", "TICKETS") if q.get("dataset", "TICKETS") in rw.DATASETS else "TICKETS"
    cols = ctx.request.query_list("col")
    filters = {k: q.get(k, "") for k in ("board", "from", "to", "state") if q.get(k)}
    if filters.get("board") and filters["board"] not in common.board_ids_for(ctx):
        filters.pop("board")
    return dataset, cols, q.get("group") or None, filters


def index(ctx):
    from .. import Response
    common.require_module(ctx, "REPORTS")
    dataset, cols, group_by, filters = _args(ctx)
    ds = rw.DATASETS[dataset]
    if not cols and not group_by:
        cols = list(ds["columns"])[:5]
    saved = rw.visible(ctx.conn, ctx.user.id)
    can_pin = common.allows(ctx, "REPORTS", "ADMIN")
    rows = "".join(
        f"<tr><td><a href='/reports/custom/{r['report_id']}'><b>{t.esc(r['name'])}</b></a></td>"
        f"<td>{t.esc(rw.DATASETS[r['dataset']]['label'])}</td><td>{t.esc(r['owner'])}</td>"
        f"<td>{'shared' if r['shared'] else 'mine'}</td><td>{'pinned' if r['pinned'] else ''}"
        + (f" <form method=post action='/reports/custom/{r['report_id']}/pin' class=inline><button class='ghost small' type=submit>"
           f"{'Unpin' if r['pinned'] else 'Pin'}</button></form>" if can_pin else "") + "</td></tr>" for r in saved)
    q = ctx.request.query
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + "<h1>Report writer</h1><p class=sub>Pick a dataset, the columns or a grouping, and filters; run it, download it, "
              "save it, share it. Every report covers only the boards you are on. <a href='/reports'>Reports</a></p>"
            + _builder(ctx, dataset, cols, group_by, filters)
            + "<div class=card><h3>" + t.icon("rows") + "Saved reports</h3><div class=tablewrap><table><thead><tr><th>Name</th>"
              f"<th>Dataset</th><th>Owner</th><th>Seen by</th><th>Dashboard</th></tr></thead><tbody>"
              f"{rows or '<tr><td colspan=5 class=muted>None yet.</td></tr>'}</tbody></table></div></div>")
    return Response(body=t.page("Report writer", body, user=ctx.user, active="reports"))


def run_adhoc(ctx):
    from .. import Response
    common.require_module(ctx, "REPORTS")
    dataset, cols, group_by, filters = _args(ctx)
    try:
        result = rw.run(ctx.conn, dataset, cols, group_by, filters, boards=common.board_ids_for(ctx))
    except rw.Refused as exc:
        return _back("/reports/custom", err=str(exc), dataset=dataset)
    if ctx.request.query.get("format") == "csv":
        return _csv(result, "report")
    qs = ctx.request.query_string
    body = ("<h1>Report</h1><p class=sub><a href='/reports/custom'>Report writer</a> · "
            f"<a href='/reports/custom/run?{t.esc(qs)}&format=csv'>CSV</a></p>"
            + _builder(ctx, dataset, cols, group_by, filters) + "<div class=card>" + _table(result) + "</div>")
    return Response(body=t.page("Report", body, user=ctx.user, active="reports"))


def _csv(result, name):
    from .. import Response
    return Response(body=rw.as_csv(result), content_type="text/csv; charset=utf-8", headers=[
        ("Content-Disposition", f'attachment; filename="{name}.csv"'), ("Cache-Control", "no-store")])


def create(ctx):
    common.require_module(ctx, "REPORTS", "WRITE")
    f = ctx.request.form()
    cols = ctx.request.form_list("col")
    try:
        rid = rw.save(ctx.conn, name=f.get("name", ""), dataset=f.get("dataset", ""), columns=cols,
                      group_by=f.get("group") or None, filters={k: f.get(k, "") for k in ("board", "from", "to", "state")},
                      owner=ctx.user.id, shared=f.get("shared") == "1", at=ctx.now)
        ctx.conn.commit()
    except rw.Refused as exc:
        return _back("/reports/custom", err=f"Not saved: {exc}")
    return _back(f"/reports/custom/{rid}", msg="Saved")


def _load(ctx, report_id):
    from .. import HttpError
    row = rw.get(ctx.conn, int(report_id)) if str(report_id).isdigit() else None
    if row is None or not (row["shared"] or row["owner"].lower() == ctx.user.id.lower()):
        raise HttpError("404 Not Found", "No such report.")
    return row


def detail(ctx, report_id):
    from .. import Response
    common.require_module(ctx, "REPORTS")
    row = _load(ctx, report_id)
    cols, group_by, filters = rw.parts(row)
    filters = {k: v for k, v in filters.items() if k != "board" or v in common.board_ids_for(ctx)}
    result = rw.run(ctx.conn, row["dataset"], cols, group_by, filters, boards=common.board_ids_for(ctx))
    q = ctx.request.query
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + f"<h1>{t.esc(row['name'])}</h1><p class=sub>{t.esc(rw.DATASETS[row['dataset']]['label'])} · by {t.esc(row['owner'])}"
              f"{' · shared' if row['shared'] else ''} · <a href='/reports/custom/{row['report_id']}/csv'>CSV</a> · "
              "<a href='/reports/custom'>Report writer</a></p><div class=card>" + _table(result) + "</div>")
    return Response(body=t.page(row["name"], body, user=ctx.user, active="reports"))


def detail_csv(ctx, report_id):
    common.require_module(ctx, "REPORTS")
    row = _load(ctx, report_id)
    cols, group_by, filters = rw.parts(row)
    filters = {k: v for k, v in filters.items() if k != "board" or v in common.board_ids_for(ctx)}
    return _csv(rw.run(ctx.conn, row["dataset"], cols, group_by, filters, boards=common.board_ids_for(ctx)),
                f"report-{row['report_id']}")


def pin(ctx, report_id):
    common.require_module(ctx, "REPORTS", "ADMIN")
    row = _load(ctx, report_id)
    ctx.conn.execute("UPDATE report_def SET pinned = ?, shared = CASE WHEN ? = 1 THEN 1 ELSE shared END WHERE report_id = ?",
                     (0 if row["pinned"] else 1, 0 if row["pinned"] else 1, row["report_id"]))
    ctx.conn.commit()
    return _back("/reports/custom", msg="Unpinned" if row["pinned"] else "Pinned to the Reports page, and shared")


def pinned_cards(ctx) -> str:
    """The dashboard: every pinned report, run for this viewer, on the Reports page."""
    out = []
    for row in ctx.conn.execute("SELECT * FROM report_def WHERE pinned = 1 ORDER BY name").fetchall():
        cols, group_by, filters = rw.parts(row)
        try:
            result = rw.run(ctx.conn, row["dataset"], cols, group_by, filters, boards=common.board_ids_for(ctx))
        except rw.Refused:
            continue
        result = dict(result, rows=result["rows"][:12])
        out.append(f"<div class=card><h3>{t.icon('rows')}<a href='/reports/custom/{row['report_id']}'>{t.esc(row['name'])}</a></h3>"
                   + _table(result) + "</div>")
    return ("<div class=grid2>" + "".join(out) + "</div>") if out else ""
