"""Reports: the Service Manager's month, as charts drawn in the page.

Inline SVG, no library, no external request (the fence). The colour rules are
the data-viz method's: two categorical hues for opened and closed, one hue for
a magnitude, status colour reserved for SLA state and nothing else; text in
the page's ink, never a series colour; a legend for two series and direct
labels where they fit; every mark carries its value as a tooltip; and a table
under the charts, because a chart is a picture of a table, not a replacement.
"""
from __future__ import annotations

import csv
import io

from ... import metrics
from .. import templates as t
from . import common

MONTHS = (3, 6, 12)


def _args(ctx):
    boards = common.board_ids_for(ctx)
    q = ctx.request.query
    months = int(q.get("months", "6")) if q.get("months", "6").isdigit() else 6
    months = months if months in MONTHS else 6
    board = q.get("board", "") if q.get("board", "") in boards else None
    return boards, months, board


def _bar_path(x: float, y: float, w: float, h: float, r: float = 3) -> str:
    """A bar with rounded top corners, flat on the baseline."""
    if h <= 0:
        return ""
    r = min(r, w / 2, h)
    return (f"M{x:.1f},{y + h:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
            f"H{x + w - r:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} V{y + h:.1f} Z")


def _month_label(k: str) -> str:
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return names[int(k[5:7]) - 1]


def chart_opened_closed(m: dict) -> str:
    keys = m["months"]
    W, H, L, B, T = 640, 220, 34, 28, 14
    top = max([m["opened"][k] for k in keys] + [m["closed"][k] for k in keys] + [1])
    step = max(1, 10 ** (len(str(top)) - 1))
    ymax = ((top + step - 1) // step) * step
    plot_h = H - T - B
    group_w = (W - L - 10) / len(keys)
    bar_w = max(6, (group_w - 10) / 2 - 1)
    parts = [f'<svg class="viz" viewBox="0 0 {W} {H}" role="img" aria-label="Tickets opened and closed by month">']
    for i in range(5):
        v = ymax * i / 4
        y = T + plot_h - plot_h * i / 4
        parts.append(f'<line x1="{L}" x2="{W - 10}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>'
                     f'<text x="{L - 6}" y="{y + 4:.1f}" class="lbl r">{int(v)}</text>')
    for gi, k in enumerate(keys):
        x0 = L + gi * group_w + 5
        for si, (series, key) in enumerate((("opened", "Opened"), ("closed", "Closed"))):
            v = m[series][k]
            h = plot_h * v / ymax if ymax else 0
            x = x0 + si * (bar_w + 2)
            parts.append(f'<path class="s{si + 1}" d="{_bar_path(x, T + plot_h - h, bar_w, h)}">'
                         f'<title>{_month_label(k)} {k[:4]}: {v} {key.lower()}</title></path>')
            if h > 14:
                parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{T + plot_h - h + 12:.1f}" '
                             f'class="lbl c onbar">{v}</text>')
        parts.append(f'<text x="{x0 + group_w / 2 - 5:.1f}" y="{H - 8}" class="lbl c">'
                     f'{_month_label(k)}</text>')
    parts.append("</svg>")
    legend = ('<div class=legend><span><i class=s1></i>Opened</span>'
              '<span><i class=s2></i>Closed</span></div>')
    return legend + "".join(parts)


def chart_met(m: dict) -> str:
    keys = m["months"]
    W, H, L, B, T = 640, 200, 34, 28, 14
    plot_h = H - T - B
    xs = [L + 20 + i * (W - L - 40) / max(1, len(keys) - 1) for i in range(len(keys))]
    parts = [f'<svg class="viz" viewBox="0 0 {W} {H}" role="img" aria-label="Resolve clock met, per cent by month">']
    for pct in (0, 50, 100):
        y = T + plot_h - plot_h * pct / 100
        parts.append(f'<line x1="{L}" x2="{W - 10}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>'
                     f'<text x="{L - 6}" y="{y + 4:.1f}" class="lbl r">{pct}%</text>')
    pts = [(xs[i], T + plot_h - plot_h * m["resolve_met"][k] / 100)
           for i, k in enumerate(keys) if m["resolve_met"][k] is not None]
    if len(pts) >= 2:
        parts.append('<polyline class="line s1" points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + '"/>')
    for i, k in enumerate(keys):
        v = m["resolve_met"][k]
        parts.append(f'<text x="{xs[i]:.1f}" y="{H - 8}" class="lbl c">{_month_label(k)}</text>')
        if v is None:
            continue
        y = T + plot_h - plot_h * v / 100
        parts.append(f'<g class="pt"><rect x="{xs[i] - 14:.1f}" y="{T}" width="28" height="{plot_h}" class="hit"/>'
                     f'<circle cx="{xs[i]:.1f}" cy="{y:.1f}" r="4" class="dot s1"/>'
                     f'<text x="{xs[i]:.1f}" y="{y - 9:.1f}" class="lbl c">{v}%</text>'
                     f'<title>{_month_label(k)} {k[:4]}: {v}% of resolve clocks met</title></g>')
    parts.append("</svg>")
    return "".join(parts)


def chart_bars(pairs: list[tuple[str, int]], label: str, *, names=None) -> str:
    pairs = pairs[:8]
    if not pairs:
        return "<div class=muted>Nothing in this period.</div>"
    W, row = 640, 24
    H = 8 + row * len(pairs)
    top = max(n for _, n in pairs) or 1
    lab_w = 180
    parts = [f'<svg class="viz" viewBox="0 0 {W} {H}" role="img" aria-label="{t.esc(label)}">']
    for i, (k, n) in enumerate(pairs):
        y = 8 + i * row
        name = (names or {}).get(k, k)
        w = (W - lab_w - 60) * n / top
        parts.append(f'<text x="{lab_w - 8}" y="{y + 15}" class="lbl r">{t.esc(str(name))[:28]}</text>'
                     f'<rect x="{lab_w}" y="{y + 3}" width="{w:.1f}" height="16" rx="3" class="s1 hbar">'
                     f'<title>{t.esc(str(name))}: {n}</title></rect>'
                     f'<text x="{lab_w + w + 6:.1f}" y="{y + 15}" class="lbl">{n}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _tile(n, label, *, unit="", cls="") -> str:
    shown = "—" if n is None else f"{n}{unit}"
    return f"<div class='tile {cls}'><div class=n>{t.esc(shown)}</div><div class=l>{t.esc(label)}</div></div>"


def index(ctx):
    from .. import Response
    from ... import itil
    boards, months, board = _args(ctx)
    m = metrics.desk(ctx.conn, boards, now=ctx.now, months=months, board=board)
    names = {r["board_id"]: r["display_name"] for r in ctx.conn.execute(
        "SELECT board_id, display_name FROM board WHERE board_id IN (%s)" % ",".join("?" * len(boards)),
        tuple(boards))} if boards else {}
    controls = (
        "<div class=card><form method=get class=toolbar action='/reports'>"
        "<div><label>Period</label><select name=months>" + "".join(
            f"<option value={n}{' selected' if n == months else ''}>Last {n} months</option>" for n in MONTHS)
        + "</select></div><div><label>Board</label><select name=board><option value=''>All my boards</option>"
        + "".join(f"<option value='{t.esc(b)}'{' selected' if b == board else ''}>{t.esc(names[b])}</option>"
                  for b in sorted(names, key=lambda b: names[b]))
        + "</select></div><div style='min-width:0'><button type=submit>" + t.icon("filter") + " Show</button></div>"
        f"<div style='min-width:0;margin-left:auto'><a class='btn ghost' href='/reports.csv?months={months}"
        f"{'&board=' + t.esc(board) if board else ''}'>" + t.icon("arrow") + " CSV</a></div></form></div>")
    fmt = lambda mins: None if mins is None else (f"{mins // 60}h {mins % 60:02d}m" if mins >= 60 else f"{mins}m")  # noqa: E731
    tiles = ("<div class='tiles six'>"
             + _tile(m["opened_total"], "Opened in period") + _tile(m["closed_total"], "Closed in period")
             + _tile(m["backlog"], "Open now")
             + _tile(m["resolve_met_total"], "Resolve clock met", unit="%",
                     # None is "nothing closed yet", uncoloured; 0 is every clock missed
                     cls="" if m["resolve_met_total"] is None or m["resolve_met_total"] >= 80 else "warn")
             + _tile(fmt(m["median_respond"]), "Median time to respond")
             + _tile(fmt(m["median_resolve"]), "Median time to resolve") + "</div>")
    sat = ""
    if m["satisfaction"] is not None:
        sat = (f"<div class=card><h3>{t.icon('sparkle')}Satisfaction</h3><div class=n style='font-size:26px;font-weight:650'>"
               f"{m['satisfaction']} / 5</div><div class=why>{m['satisfaction_n']} answer(s) in the period.</div></div>")
    table = ("<div class=tablewrap><table><thead><tr><th>Month</th><th class=right>Opened</th><th class=right>Closed</th>"
             "<th class=right>Respond met</th><th class=right>Resolve met</th></tr></thead><tbody>" + "".join(
                 f"<tr><td>{_month_label(k)} {k[:4]}</td><td class=right>{m['opened'][k]}</td>"
                 f"<td class=right>{m['closed'][k]}</td>"
                 f"<td class=right>{'—' if m['respond_met'][k] is None else str(m['respond_met'][k]) + '%'}</td>"
                 f"<td class=right>{'—' if m['resolve_met'][k] is None else str(m['resolve_met'][k]) + '%'}</td></tr>"
                 for k in m["months"]) + "</tbody></table></div>")
    body = (
        "<h1>Reports</h1><p class=sub>The month as the Service Manager sees it, computed now from the "
        "tickets and their clocks; nothing here is a stored figure.</p>" + controls + tiles
        + "<div class=grid2>"
        f"<div class=card><h3>{t.icon('board')}Opened and closed, by month</h3>{chart_opened_closed(m)}</div>"
        f"<div class=card><h3>{t.icon('clock')}Resolve clock met, by month</h3>{chart_met(m)}"
        "<p class=why>Share of closed tickets whose resolve clock stopped inside its target, in working time.</p></div>"
        f"<div class=card><h3>{t.icon('layers')}Opened, by board</h3>{chart_bars(m['by_board'], 'Opened by board')}</div>"
        f"<div class=card><h3>{t.icon('tag')}Opened, by Type</h3>"
        f"{chart_bars(m['by_type'], 'Opened by type', names=itil.LABEL)}</div>"
        f"<div class=card><h3>{t.icon('mail')}Opened, by source</h3>"
        f"{chart_bars(m['by_source'], 'Opened by source', names={s: s.replace('_', '-').title() for s, _ in m['by_source']})}</div>"
        f"<div class=card><h3>{t.icon('alert')}Opened, by priority</h3>{chart_bars(m['by_priority'], 'Opened by priority')}</div>"
        "</div>" + sat
        + f"<div class=card><h3>{t.icon('rows')}The table</h3>{table}</div>")
    return Response(body=t.page("Reports", body, user=ctx.user, active="reports"))


def export_csv(ctx):
    from .. import Response
    boards, months, board = _args(ctx)
    m = metrics.desk(ctx.conn, boards, now=ctx.now, months=months, board=board)
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\r\n").writerows(metrics.csv_rows(m))
    return Response(body=buf.getvalue(), content_type="text/csv; charset=utf-8", headers=[
        ("Content-Disposition", f'attachment; filename="psa-reports-{months}m.csv"'),
        ("Cache-Control", "no-store")])
