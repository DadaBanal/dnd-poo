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
footer{max-width:1100px;margin:0 auto;padding:8px 18px 30px;color:var(--muted);
  font-size:12px}
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
        ("my", "/my", "My requests"),
        ("board", "/", "Board"),
        ("dispatch", "/dispatch", "Dispatch"),
        ("oncall", "/oncall", "On-call"),
        ("uplift", "/uplift", "Uplift"),
        ("admin", "/admin", "Admin"),
    ]
    nav = "".join(
        f'<a href="{esc(href)}"{" style=text-decoration:underline" if key==active else ""}>'
        f'{esc(label)}</a>'
        for key, href, label in nav_items)
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
