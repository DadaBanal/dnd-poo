"""HTML, built from strings, with the one rule that keeps that safe: every value
that reaches the page goes through `esc()`.

No templating engine, because a templating engine is a dependency and the portal
is self-contained by fence (§8.3, and the artifact rule in CLAUDE.md). No
external stylesheet, no web font, no script from a CDN — the one <style> block is
inline and everything the pages need is in it. A ward PC with a locked-down
browser and no internet renders these exactly as a developer's does.

The SLA colour is semantic, not decorative: green / amber / red carries whether a
clock is inside target, close, or breached, and nothing else uses those three.
"""
from __future__ import annotations

import html
import re

# The whole stylesheet. Theme-aware enough to be read on a bright ward monitor
# and a dim night-shift one, but committed to one clean look rather than chasing
# a system preference the pilot browsers may not report.
STYLE = """
:root{
  --bg:#f6f7f9; --card:#ffffff; --ink:#1a1f27; --muted:#5b6675; --line:#dde2e8;
  --accent:#1f6feb; --accent-ink:#ffffff;
  --ok:#137333; --ok-bg:#e6f4ea; --warn:#8a6100; --warn-bg:#fef7e0;
  --bad:#b3261e; --bad-bg:#fce8e6; --chip:#eef1f5;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
header.top{background:var(--ink);color:#fff;padding:10px 18px;display:flex;
  align-items:center;gap:18px;flex-wrap:wrap}
header.top .brand{font-weight:600;letter-spacing:.2px}
header.top nav{display:flex;gap:14px;flex-wrap:wrap}
header.top nav a{color:#c9d4e3}
header.top nav a:hover{color:#fff}
header.top .who{margin-left:auto;color:#9fb0c4;font-size:12px}
header.top .who .glass{color:#ffd27d}
main{max-width:1100px;margin:0 auto;padding:22px 18px}
h1{font-size:20px;margin:0 0 4px}
.sub{color:var(--muted);margin:0 0 18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
  padding:16px 18px;margin-bottom:18px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);
  vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;
  letter-spacing:.4px}
tr:last-child td{border-bottom:none}
.tablewrap{overflow-x:auto}
.chip{display:inline-block;padding:1px 8px;border-radius:20px;background:var(--chip);
  color:var(--ink);font-size:12px;font-weight:600;white-space:nowrap}
.sla-ok{background:var(--ok-bg);color:var(--ok)}
.sla-warn{background:var(--warn-bg);color:var(--warn)}
.sla-bad{background:var(--bad-bg);color:var(--bad)}
.pri{font-weight:700}
.pri-P1{color:var(--bad)} .pri-P2{color:var(--warn)}
.muted{color:var(--muted)}
form.stack{display:flex;flex-direction:column;gap:10px;max-width:420px}
label{font-size:13px;font-weight:600;color:var(--muted)}
input,select,textarea{font:inherit;padding:8px 10px;border:1px solid var(--line);
  border-radius:8px;background:#fff;width:100%}
textarea{min-height:90px;resize:vertical}
button,.btn{font:inherit;font-weight:600;padding:8px 14px;border-radius:8px;
  border:1px solid var(--accent);background:var(--accent);color:var(--accent-ink);
  cursor:pointer}
button.ghost,.btn.ghost{background:#fff;color:var(--accent)}
.rail{display:grid;grid-template-columns:2fr 1fr;gap:18px}
@media(max-width:720px){.rail{grid-template-columns:1fr}}
.kv{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;font-size:13px}
.kv dt{color:var(--muted)}
.kv dd{margin:0}
.stream{list-style:none;padding:0;margin:0}
.stream li{padding:8px 0;border-bottom:1px solid var(--line)}
.stream li:last-child{border-bottom:none}
.stream .meta{color:var(--muted);font-size:12px}
.banner{padding:10px 14px;border-radius:8px;margin-bottom:16px}
.banner.err{background:var(--bad-bg);color:var(--bad)}
.banner.ok{background:var(--ok-bg);color:var(--ok)}
.empty{color:var(--muted);padding:20px;text-align:center}
.right{text-align:right}
footer{max-width:1320px;margin:0 auto;padding:8px 18px 30px;color:var(--muted);
  font-size:12px}
main{max-width:1320px}
header.top nav a.on{color:#fff;border-bottom:2px solid #4c8dff;padding-bottom:2px}
header.top .newbtn{background:#1f6feb;color:#fff;padding:4px 10px;border-radius:6px;font-weight:600}
.tiles{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:14px}
.tile{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 14px}
.tile .n{font-size:22px;font-weight:700}
.tile .l{color:var(--muted);font-size:12px}
.tile.bad .n{color:var(--bad)} .tile.warn .n{color:var(--warn)}
.toolbar{display:flex;gap:8px;align-items:end;flex-wrap:wrap}
.toolbar>div{min-width:130px}
.bulk{display:flex;gap:8px;align-items:center;background:#eef4ff;border:1px solid #c9dafc;
  border-radius:8px;padding:8px 12px;margin:0 0 10px;font-size:13px}
.bulk select{width:auto;padding:4px 8px}
.bulk button{padding:4px 12px}
table.grid td{padding:7px 8px;white-space:nowrap}
table.grid td.sum{white-space:normal;min-width:260px}
table.grid tbody tr{border-left:4px solid transparent}
table.grid tbody tr.s-bad{box-shadow:inset 4px 0 0 var(--bad)}
table.grid tbody tr.s-warn{box-shadow:inset 4px 0 0 #e0a000}
table.grid tbody tr.s-ok{box-shadow:inset 4px 0 0 #34a853}
table.grid tbody tr:hover{background:#f7f9fc}
th.sort a{color:var(--muted)} th.sort.on a{color:var(--ink)}
.badge{display:inline-block;min-width:28px;text-align:center;border-radius:6px;padding:1px 6px;
  font-weight:700;font-size:12px;color:#fff}
.badge.P1{background:#b3261e}.badge.P2{background:#c77700}.badge.P3{background:#1f6feb}.badge.P4{background:#6b7785}
.sla3{display:inline-flex;gap:3px;white-space:nowrap}
.sla3 span{font-size:11px;font-weight:700;border-radius:4px;padding:1px 5px}
.m{background:#e6f4ea;color:#137333}.o{background:#e6f4ea;color:#137333}
.w{background:#fef7e0;color:#8a6100}.b{background:#fce8e6;color:#b3261e}.d{background:#eef1f5;color:#8a94a3}
.last{color:var(--muted);font-size:12px}
.hdr{display:flex;align-items:start;gap:12px;flex-wrap:wrap}
.hdr .grow{flex:1}
.slastrip{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px}
.slabox{border-radius:10px;padding:10px 14px;border:1px solid var(--line);background:#fff}
.slabox .t{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px}
.slabox .v{font-size:16px;font-weight:700}
.slabox.ok{border-left:5px solid #34a853}.slabox.warn{border-left:5px solid #e0a000}
.slabox.bad{border-left:5px solid #b3261e}.slabox.done{border-left:5px solid #9aa4b1}
.bar{height:6px;background:#eef1f5;border-radius:4px;margin-top:6px;overflow:hidden}
.bar i{display:block;height:100%}
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--line);margin-bottom:10px}
.tabs a{padding:6px 12px;color:var(--muted);border-bottom:2px solid transparent}
.tabs a.on{color:var(--ink);border-color:var(--accent);font-weight:600}
.note{border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin-bottom:10px;background:#fff}
.note.INTERNAL{background:#fffbea;border-color:#f3e1a1}
.note.RESOLUTION{background:#f1f9f3;border-color:#bfe3c8}
.note .h{display:flex;gap:8px;align-items:center;font-size:12px;color:var(--muted);margin-bottom:4px}
.av{width:24px;height:24px;border-radius:50%;background:#dbe6fb;color:#1f4fa8;font-weight:700;
  font-size:11px;display:inline-flex;align-items:center;justify-content:center}
.flag{font-size:11px;font-weight:700;border-radius:4px;padding:0 6px}
.flag.DISCUSSION{background:#e8f0fe;color:#1f4fa8}.flag.INTERNAL{background:#fdefc3;color:#7a5a00}
.flag.RESOLUTION{background:#d7f0dd;color:#137333}
.sys{font-size:12px;color:var(--muted);padding:2px 0 8px 32px}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.seg label{padding:6px 12px;font-weight:600;color:var(--muted);cursor:pointer;border-right:1px solid var(--line)}
.seg label:last-child{border-right:none}
.seg label.on{background:#e8f0fe;color:#1f4fa8}
.seg label.on.int{background:#fdefc3;color:#7a5a00}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:end}
.row>div{flex:1;min-width:140px}
.fields label{display:block;margin-top:8px}
.fields .ro{padding:8px 10px;background:#f6f7f9;border-radius:8px;font-size:13px}
.why{font-size:12px;color:var(--muted)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px 16px}
.radiorow label{display:block;font-weight:500;color:var(--ink);margin:3px 0}
.stabs{display:flex;gap:6px;margin-bottom:14px}
.stabs a{padding:6px 14px;border-radius:8px;background:#fff;border:1px solid var(--line);color:var(--muted);font-weight:600}
.stabs a.on{background:var(--ink);color:#fff;border-color:var(--ink)}
table.edit td{padding:5px 6px}
table.edit input,table.edit select{padding:5px 7px;font-size:13px}
.pill{font-size:11px;border-radius:10px;padding:1px 7px;background:#eef1f5;color:#5b6675;font-weight:600}
.note-ph{font-size:12px;color:#8a6100;background:#fef7e0;border-radius:8px;padding:8px 12px;margin-bottom:10px}
.tiles a.tile{color:inherit;display:block}
.tiles a.tile:hover{border-color:var(--accent);text-decoration:none}
.tile.on{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.seg input{position:absolute;opacity:0;width:1px;height:1px;margin:0}
.seg input:focus-visible+span{outline:2px solid var(--accent);outline-offset:-2px}
.seg label{position:relative}
.seg input:checked+span{background:#e8f0fe;color:#1f4fa8}
.seg label{padding:0}
.seg label span{display:block;padding:6px 12px}
.seg label.int input:checked+span{background:#fdefc3;color:#7a5a00}
.seg label.res input:checked+span{background:#d7f0dd;color:#137333}
.inline{display:inline}
.dispatch-route select{width:auto;min-width:130px}
em{font-style:italic}
@media(max-width:900px){.tiles{grid-template-columns:repeat(2,1fr)}.slastrip{grid-template-columns:1fr}.grid2{grid-template-columns:1fr}}
"""


def esc(value) -> str:
    """The one rule. Everything user- or data-derived passes through here before
    it reaches the page."""
    return html.escape("" if value is None else str(value), quote=True)


def _inline(text: str) -> str:
    """Escape, then the two inline shapes the reports actually emit: **bold** and
    `code`. Escaping first is what keeps this safe — the markers are literal
    characters html.escape leaves alone, so the regex sees only them."""
    out = esc(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    # Emphasis last, after **bold** has consumed its pairs. Word-bounded so a
    # snake_case name or an arithmetic * is left alone.
    out = re.sub(r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", out)
    out = re.sub(r"(?<![\w])_(?!\s)([^_\n]+?)(?<!\s)_(?![\w])", r"<em>\1</em>", out)
    return out


def md_to_html(md: str) -> str:
    """Just enough Markdown for the reports this repo generates: ATX headings,
    GitHub pipe tables, horizontal rules, bullet lists, bold, code and
    paragraphs. Not a general parser — a renderer for a known, tested shape, so
    the uplift evidence is a first-class screen (§7) rather than an export."""
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    para: list[str] = []

    def flush_para():
        if para:
            out.append("<p>" + "<br>".join(_inline(p) for p in para) + "</p>")
            para.clear()

    def is_sep(row: str) -> bool:
        return bool(re.fullmatch(r"\|[\s:|-]+\|", row.strip())) and "-" in row

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_para()
            i += 1
            continue

        if stripped in ("---", "***", "___"):
            flush_para()
            out.append("<hr>")
            i += 1
            continue

        m = re.match(r"(#{1,6})\s+(.*)", stripped)
        if m:
            flush_para()
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # A pipe table: header row, separator, then body rows.
        if stripped.startswith("|") and i + 1 < len(lines) and is_sep(lines[i + 1]):
            flush_para()
            header = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2
            body = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                body.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head_html = "".join(f"<th>{_inline(c)}</th>" for c in header)
            rows_html = "".join(
                "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>"
                for r in body)
            out.append("<div class='tablewrap'><table><thead><tr>" + head_html +
                       "</tr></thead><tbody>" + rows_html + "</tbody></table></div>")
            continue

        if re.match(r"[*-]\s+", stripped):
            flush_para()
            items = []
            while i < len(lines) and re.match(r"[*-]\s+", lines[i].strip()):
                items.append("<li>" + _inline(re.sub(r"^[*-]\s+", "", lines[i].strip())) + "</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue

        para.append(stripped)
        i += 1

    flush_para()
    return "".join(out)


def badge(priority) -> str:
    p = priority if priority in ("P1", "P2", "P3", "P4") else ""
    return f'<span class="badge {p}">{esc(priority or "—")}</span>'


# One chip per ConnectWise clock: Respond, resolution Plan, reSolve.
CLOCK_LETTER = {"RESPOND": "R", "RESOLUTION_PLAN": "P", "RESOLVE": "S",
                "ACKNOWLEDGE": "A", "DECISION": "D"}
_CHIP = {"MET": "m", "OK": "o", "WARN": "w", "BAD": "b", "PAUSED": "d", "MISSED": "b"}


def sla_chips(states: list[dict]) -> str:
    """Three small chips, one per clock, each coloured by its own state. Built
    from common.clock_states, never from a stored flag."""
    if not states:
        return ""
    out = []
    for st in states:
        letter = CLOCK_LETTER.get(st["clock"], "?")
        text = {"MET": "✓", "MISSED": "✗", "PAUSED": "paused"}.get(st["state"], st["short"])
        out.append(f'<span class="{_CHIP.get(st["state"], "o")}" title="{esc(st["title"])}">'
                   f'{letter} {esc(text)}</span>')
    return '<span class="sla3">' + "".join(out) + "</span>"


def sla_class(state: str) -> str:
    return {"OK": "sla-ok", "WARN": "sla-warn", "BAD": "sla-bad"}.get(state, "")


def chip(text: str, cls: str = "") -> str:
    classes = "chip" + (f" {cls}" if cls else "")
    return f'<span class="{classes}">{esc(text)}</span>'


def page(title: str, body: str, *, user=None, active: str = "") -> str:
    """The shell every page shares: header, nav, the acting user, the body.

    A break-glass session is marked in the corner, in amber, on every page. Who
    is at the desk and how they got in is not a detail to hunt for in a log when
    the desk is being run on the fallback path.
    """
    nav_items = [
        ("board", "/", "Service Board"),
        ("dispatch", "/dispatch", "Dispatch"),
        ("companies", "/companies", "Companies"),
        ("oncall", "/oncall", "On-call"),
        ("uplift", "/uplift", "Uplift"),
        ("admin", "/admin", "Setup"),
        ("my", "/my", "My requests"),
    ]
    nav = "".join(
        f'<a href="{esc(href)}"{" class=on" if key == active else ""}>{esc(label)}</a>'
        for key, href, label in nav_items)
    nav += '<a class="newbtn" href="/ticket/new">+ New ticket</a>' if user is not None else ""
    who = ""
    if user is not None:
        glass = ('<span class="glass">break-glass</span> · ' if user.via == "local" else "")
        who = (f'<div class="who">{glass}{esc(user.name)}'
               f' · <a href="/logout" style="color:#9fb0c4">sign out</a></div>')
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        f"<title>{esc(title)} · PSA desk</title><style>{STYLE}</style></head><body>"
        f'<header class="top"><span class="brand">PSA desk</span>'
        f"<nav>{nav}</nav>{who}</header>"
        f"<main>{body}</main>"
        "<footer>PMC PSA spine — Phase B pilot. LAN only, Dada IT only. "
        "Kitameraki remains the system of record until dual-run ends.</footer>"
        "</body></html>")


def login_page(*, entra_configured: bool, error: str = "", next_url: str = "/") -> str:
    err = f'<div class="banner err">{esc(error)}</div>' if error else ""
    entra = ""
    if entra_configured:
        entra = (
            '<div class="card"><h1>Sign in with Entra</h1>'
            '<p class="sub">The normal way in. Your organisation account.</p>'
            f'<a class="btn" href="/entra/start?next={esc(next_url)}">Continue with Entra</a>'
            "</div>")
    glass = (
        '<div class="card"><h1>Break-glass sign in</h1>'
        '<p class="sub">For the on-call rota, when the WAN is down. Every use is '
        "audited.</p>"
        '<form class="stack" method="post" action="/login">'
        f'<input type="hidden" name="next" value="{esc(next_url)}">'
        "<label>Username<input name=username autocomplete=username autofocus></label>"
        "<label>Password<input name=password type=password "
        "autocomplete=current-password></label>"
        "<button type=submit>Sign in</button></form></div>")
    body = err + entra + glass
    return page("Sign in", body)
