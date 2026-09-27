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

# The whole stylesheet: one design system, self-contained by fence.
#
# Surfaces, not shadows: a ladder of four surfaces and hairline borders carries
# depth (the Linear pattern), with a soft shadow only on things that float --
# the command palette. Colour is semantic: green / amber / red carry an SLA
# clock's state and nothing else; one accent carries "this is the action".
# Light and dark follow the OS unless the person picks one (the toggle in the
# header, remembered in this browser). Every motion is 140-220 ms on an
# ease-out, and every one of them is off under prefers-reduced-motion.
#
# Modern CSS, used where it degrades cleanly: cross-document view transitions
# (Chromium, Safari 18.2+; other engines simply navigate), :has() for the
# bulk bar and selected rows, @starting-style for enter transitions,
# color-mix() with plain fallbacks declared first, sticky table headings.
STYLE = """
:root{color-scheme:light dark;
  --canvas:#f4f5f8; --surface:#ffffff; --surface-2:#f6f7fa; --surface-3:#eceef3;
  --ink:#15181e; --ink-2:#4a5260; --ink-3:#7a8290; --line:#e3e6ec; --line-2:#cbd1db;
  --accent:#3d63dd; --accent-2:#2f52c4; --on-accent:#ffffff;
  --ok:#1a7f37; --warn:#9a6700; --bad:#c62828; --chip:#eceef3;
  --shadow:0 14px 40px -16px rgb(20 24 34/.35); --glass:rgb(255 255 255/.78);
  --card:var(--surface); --muted:var(--ink-2);
  --ok-bg:#e7f6ec; --warn-bg:#fff4d6; --bad-bg:#fdeaea;
  --ok-bg:color-mix(in srgb,var(--ok) 14%,transparent);
  --warn-bg:color-mix(in srgb,var(--warn) 16%,transparent);
  --bad-bg:color-mix(in srgb,var(--bad) 13%,transparent);
  --accent-bg:#e9eefc; --accent-bg:color-mix(in srgb,var(--accent) 11%,transparent);
  --ring:rgb(61 99 221/.45); --ring:color-mix(in srgb,var(--accent) 45%,transparent);
  --r-sm:6px; --r:8px; --r-lg:12px; --hdr:52px;
  --s1:#2a78d6; --s2:#eb6834;
  --fast:140ms; --slow:220ms; --ease:cubic-bezier(.2,.7,.2,1);
  --font:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){DARKTOKENS}}
:root[data-theme=dark]{DARKTOKENS}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--canvas);color:var(--ink);font:14px/1.5 var(--font);
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
a{color:var(--accent);text-decoration:none;transition:color var(--fast) var(--ease)}
a:hover{text-decoration:underline;text-underline-offset:2px}
:focus-visible{outline:2px solid var(--ring);outline-offset:2px;border-radius:var(--r-sm)}
::selection{background:var(--accent-bg)}
h1{font-size:22px;font-weight:600;letter-spacing:-.4px;margin:0 0 4px;line-height:1.25}
h3{font-size:13px;font-weight:600;letter-spacing:.2px;color:var(--ink-2);text-transform:uppercase;margin:0 0 10px}
.sub{color:var(--ink-2);margin:0 0 18px}
main{max-width:1320px;margin:0 auto;padding:22px 20px}
footer{max-width:1320px;margin:0 auto;padding:8px 20px 36px;color:var(--ink-3);font-size:12px}

/* ---- header: sticky, frosted, one accent ------------------------------ */
header.top{position:sticky;top:0;z-index:20;height:var(--hdr);display:flex;align-items:center;gap:6px;
  padding:0 16px;background:var(--glass);border-bottom:1px solid var(--line);
  -webkit-backdrop-filter:saturate(160%) blur(14px);backdrop-filter:saturate(160%) blur(14px)}
header.top .brand{display:inline-flex;align-items:center;gap:8px;font-weight:650;letter-spacing:-.2px;color:var(--ink);margin-right:10px}
header.top .brand i{width:22px;height:22px;border-radius:7px;display:inline-block;
  background:linear-gradient(135deg,var(--accent),#7b93ff 60%,#9ad0ff);box-shadow:inset 0 0 0 1px rgb(255 255 255/.25)}
header.top nav{display:flex;gap:2px;overflow-x:auto;scrollbar-width:none;flex:1;min-width:0}
header.top nav::-webkit-scrollbar{display:none}
header.top nav a{position:relative;color:var(--ink-2);padding:6px 10px;border-radius:var(--r);white-space:nowrap;font-weight:500;
  transition:color var(--fast) var(--ease),background var(--fast) var(--ease)}
header.top nav a:hover{color:var(--ink);background:var(--surface-3);text-decoration:none}
header.top nav a.on{color:var(--ink)}
header.top nav a.on::after{content:"";position:absolute;left:10px;right:10px;bottom:-1px;height:2px;border-radius:2px;background:var(--accent)}
header.top .newbtn{background:var(--accent);color:var(--on-accent);padding:6px 12px;border-radius:var(--r);font-weight:600;
  margin-left:6px;white-space:nowrap;transition:background var(--fast) var(--ease),transform var(--fast) var(--ease)}
header.top .newbtn:hover{background:var(--accent-2);text-decoration:none;transform:translateY(-1px)}
header.top .who{margin-left:auto;display:inline-flex;align-items:center;gap:10px;color:var(--ink-3);font-size:12px;white-space:nowrap}
header.top .who a{color:var(--ink-3)}
header.top .who .glass{color:var(--warn);font-weight:600}
.iconbtn{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;border-radius:var(--r);
  border:1px solid transparent;background:transparent;color:var(--ink-2);cursor:pointer;padding:0;font:inherit;
  transition:background var(--fast) var(--ease),color var(--fast) var(--ease)}
.iconbtn:hover{background:var(--surface-3);color:var(--ink)}
.iconbtn svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.ic{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round;
  vertical-align:-3px;flex:0 0 auto}
h3 .ic{width:15px;height:15px;margin-right:7px;color:var(--ink-3);vertical-align:-2px}
header.top nav a .ic{width:15px;height:15px;margin-right:6px;vertical-align:-3px;opacity:.8}
button .ic,.btn .ic{width:15px;height:15px;margin:0 -2px}
.tile .ic{position:absolute;right:12px;top:12px;width:18px;height:18px;color:var(--ink-3);opacity:.7}
.tile{position:relative}
h1{text-wrap:balance} p,.sub,.why{text-wrap:pretty}
textarea{field-sizing:content;min-height:90px;max-height:50vh}
.card{container-type:inline-size}
@container (max-width:380px){.kv{grid-template-columns:1fr;gap:2px 0}.kv dt{margin-top:6px}}
.empty::before{content:"";display:block;width:36px;height:36px;margin:0 auto 8px;opacity:.45;
  background:currentColor;-webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 13h5l2 3h4l2-3h5M3 13l2.5-8h13L21 13v6H3z'/%3E%3C/svg%3E") center/contain no-repeat;
  mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 13h5l2 3h4l2-3h5M3 13l2.5-8h13L21 13v6H3z'/%3E%3C/svg%3E") center/contain no-repeat}
#nprog{position:fixed;left:0;top:0;height:2px;width:0;background:var(--accent);z-index:60;opacity:0;transition:width .4s var(--ease),opacity .2s}
#nprog.go{opacity:1;width:70%} #nprog.done{width:100%;opacity:0}
body>svg[hidden]{display:none}
.banner.toast{position:fixed;right:20px;bottom:20px;z-index:40;max-width:min(420px,calc(100vw - 40px));box-shadow:var(--shadow);
  background:var(--surface);border:1px solid var(--line-2);margin:0;padding:10px 40px 10px 14px;align-items:center}
.banner.toast::before{display:none}
.toast.ok{color:var(--ok)} .toast.err{color:var(--bad)}
.toast .x{position:absolute;right:6px;top:6px}
@starting-style{.toast{opacity:0;translate:0 8px}}
.toast{transition:opacity var(--slow) var(--ease),translate var(--slow) var(--ease)}
.toast.ok{animation:toast-out .35s var(--ease) 7s forwards}
@keyframes toast-out{to{opacity:0;translate:0 8px;visibility:hidden}}
[data-density=compact] table.grid td{padding:4px 10px}
[data-density=compact] table.grid td.sum .last{display:none}
[data-density=compact] .card{padding:12px 14px}
.densi{display:inline-flex;gap:2px;margin-right:auto}
.densi button{padding:3px 8px;font-size:12px}
.densi button[aria-pressed=true]{background:var(--surface-3);color:var(--ink);border-color:var(--line-2)}
@supports (animation-timeline:scroll()){
  header.top{animation:hdr-shadow linear both;animation-timeline:scroll();animation-range:0 80px}
  @keyframes hdr-shadow{to{box-shadow:0 8px 24px -16px rgb(20 24 34/.45)}}}
dialog#pal{position:fixed;inset:0;margin:0;padding:12vh 16px 0;width:100%;max-width:none;height:100%;max-height:none;
  border:none;background:transparent;display:flex;align-items:flex-start;justify-content:center;color:inherit}
dialog#pal:not([open]){display:none}
dialog#pal::backdrop{background:rgb(10 12 18/.35);-webkit-backdrop-filter:blur(3px);backdrop-filter:blur(3px)}
[popover]#keys{position:fixed;inset:auto 16px 16px auto;margin:0;padding:12px 14px;border:1px solid var(--line-2);border-radius:var(--r-lg);
  background:var(--surface);color:var(--ink);box-shadow:var(--shadow);font-size:12px;max-width:340px}
[popover]#keys::backdrop{background:transparent}
[popover]#keys dl{display:grid;grid-template-columns:auto 1fr;gap:6px 12px;margin:8px 0 0}
[popover]#keys dt{white-space:nowrap} [popover]#keys dd{margin:0;color:var(--ink-2)}
.pods .card[data-pod]{position:relative}
.pods .card[data-pod] h3{display:flex;align-items:center;gap:0;padding-right:56px;cursor:grab;user-select:none}
.pods .card[data-pod] h3:active{cursor:grabbing}
.pods .card[data-pod] .podctl{position:absolute;right:8px;top:10px;display:inline-flex;gap:2px;opacity:0;transition:opacity var(--fast) var(--ease)}
.pods .card[data-pod]:hover .podctl,.pods .card[data-pod]:focus-within .podctl{opacity:1}
.pods .card[data-pod] .podctl .iconbtn{width:26px;height:26px}
.pods .card[data-pod] .podctl .ic{width:14px;height:14px}
.pods .card.collapsed>*:not(h3):not(.podctl){display:none}
.pods .card.collapsed{padding-bottom:12px} .pods .card.collapsed h3{margin-bottom:0}
.pods .card.collapsed .podctl .fold .ic{transform:rotate(-90deg)}
.pods .card.dragging{opacity:.5} .pods .card.over{box-shadow:0 -2px 0 0 var(--accent)}
.pods .podreset{font-size:12px;color:var(--ink-3);text-align:right;margin:-6px 0 12px}
.pods .podreset button{padding:2px 8px;font-size:12px}
.views{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
.viewchip{display:inline-flex;align-items:center;gap:2px}
.viewchip .stab{padding:5px 12px;border-radius:999px;background:var(--surface);border:1px solid var(--line);color:var(--ink-2);font-weight:600}
.viewchip .stab:hover{border-color:var(--line-2);color:var(--ink);text-decoration:none}
.viewchip .stab.on{background:var(--ink);color:var(--canvas);border-color:var(--ink)}
.viewchip .iconbtn{width:22px;height:22px;opacity:0} .viewchip:hover .iconbtn,.viewchip:focus-within .iconbtn{opacity:1}
.pal-box li .st{font-size:11px;font-weight:700;border-radius:5px;padding:0 6px;margin-right:6px;background:var(--chip);color:var(--ink-3)}
.viz{width:100%;height:auto;display:block;font:11px var(--font)}
.viz .grid{stroke:var(--line);stroke-width:1} .viz .lbl{fill:var(--ink-3);font-size:11px} .viz .lbl.r{text-anchor:end} .viz .lbl.c{text-anchor:middle}
.viz .lbl.onbar{fill:#fff;font-weight:600} .viz .s1{fill:var(--s1)} .viz .s2{fill:var(--s2)}
.viz .line{fill:none;stroke:var(--s1);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.viz .dot{stroke:var(--surface);stroke-width:2} .viz .hit{fill:transparent} .viz .pt:hover .dot{r:6}
.viz path.s1:hover,.viz path.s2:hover,.viz .hbar:hover{opacity:.85}
.legend{display:flex;gap:14px;font-size:12px;color:var(--ink-2);margin-bottom:6px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.legend .s1{background:var(--s1)} .legend .s2{background:var(--s2)}
.tiles.six{grid-template-columns:repeat(6,1fr)} @media (max-width:1100px){.tiles.six{grid-template-columns:repeat(3,1fr)}} @media (max-width:640px){.tiles.six{grid-template-columns:repeat(2,1fr)}}
.stars{display:inline-flex;gap:4px} .stars label{cursor:pointer;color:var(--ink-3)} .stars label .ic{width:26px;height:26px}
.stars input{position:absolute;opacity:0;width:1px;height:1px} .stars label:hover .ic,.stars label:has(input:checked) .ic,.stars label:has(input:checked)~label .ic{color:var(--ink-3)}
.stars label:has(input:checked) .ic{fill:var(--warn);color:var(--warn)} .stars label:has(~ label input:checked) .ic{fill:var(--warn);color:var(--warn)}
.stars input:focus-visible+.ic{outline:2px solid var(--ring);border-radius:4px}
.dayrow{display:grid;grid-template-columns:160px 1fr;gap:8px 12px;align-items:start;padding:8px 0;border-bottom:1px solid var(--line)}
.dayrow:last-child{border-bottom:none} .dayrow .who{font-weight:600}
.slot{display:inline-block;margin:2px 6px 2px 0;padding:3px 10px;border-radius:999px;background:var(--accent-bg);font-size:12px}
.kbd{font:11px/1 var(--mono);padding:2px 5px;border:1px solid var(--line-2);border-bottom-width:2px;border-radius:5px;color:var(--ink-2);background:var(--surface)}

/* ---- surfaces ---------------------------------------------------------- */
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-lg);padding:16px 18px;margin-bottom:16px;
  transition:border-color var(--fast) var(--ease)}
.tiles{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:14px}
.tile{display:block;background:var(--surface);border:1px solid var(--line);border-radius:var(--r-lg);padding:12px 14px;color:inherit;
  transition:transform var(--fast) var(--ease),border-color var(--fast) var(--ease),background var(--fast) var(--ease)}
.tiles a.tile:hover{border-color:var(--line-2);background:var(--surface-2);transform:translateY(-1px);text-decoration:none}
.tile .n{font-size:26px;font-weight:650;letter-spacing:-.6px;font-variant-numeric:tabular-nums;line-height:1.1}
.tile .l{color:var(--ink-3);font-size:12px;margin-top:2px}
.tile.bad .n{color:var(--bad)} .tile.warn .n{color:var(--warn)}
.tile.on{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-bg)}
.empty{color:var(--ink-3);padding:28px;text-align:center}
.banner{display:flex;gap:10px;align-items:start;padding:10px 14px;border-radius:var(--r);margin-bottom:16px;border:1px solid transparent}
.banner::before{content:"";flex:0 0 8px;height:8px;border-radius:50%;margin-top:6px;background:currentColor}
.banner.err{background:var(--bad-bg);color:var(--bad)}
.banner.ok{background:var(--ok-bg);color:var(--ok)}
@starting-style{.banner{opacity:0;translate:0 -4px}}
.banner{transition:opacity var(--slow) var(--ease),translate var(--slow) var(--ease)}

/* ---- tables ------------------------------------------------------------ */
table{width:100%;border-collapse:separate;border-spacing:0;font-size:13px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--ink-3);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.5px;white-space:nowrap}
tr:last-child td{border-bottom:none}
.tablewrap{overflow:visible}
table.grid thead th{position:sticky;top:var(--hdr);background:var(--surface);z-index:2}
table.grid td{padding:8px 10px;white-space:nowrap;font-variant-numeric:tabular-nums}
table.grid td.sum{white-space:normal;min-width:220px}
table.grid td.wrap{white-space:normal;min-width:110px}
table.grid td:first-child,table.grid th:first-child{padding-left:12px;width:28px}
table.grid tbody tr{box-shadow:inset 3px 0 0 transparent;transition:background var(--fast) var(--ease),box-shadow var(--fast) var(--ease)}
table.grid tbody tr.s-bad{box-shadow:inset 3px 0 0 var(--bad)}
table.grid tbody tr.s-warn{box-shadow:inset 3px 0 0 var(--warn)}
table.grid tbody tr.s-ok{box-shadow:inset 3px 0 0 var(--ok)}
table.grid tbody tr:hover{background:var(--surface-2)}
table.grid tbody tr:has(input:checked){background:var(--accent-bg)}
table.grid tbody tr.cur{background:var(--surface-2);outline:2px solid var(--ring);outline-offset:-2px}
table.grid tbody tr a{color:var(--ink)}
table.grid tbody tr td:nth-child(2) a{font-family:var(--mono);font-size:12px;color:var(--accent)}
th.sort a{color:var(--ink-3)} th.sort.on a{color:var(--ink)}
.right{text-align:right}
.last{color:var(--ink-3);font-size:12px;margin-top:2px}
.pager{display:flex;gap:10px;align-items:center;justify-content:flex-end;padding:10px 4px 0;color:var(--ink-2);font-size:13px}
.bulk{display:none;gap:8px;align-items:center;background:var(--accent-bg);border:1px solid var(--line);
  border-radius:var(--r);padding:8px 12px;margin:0 0 10px;font-size:13px;flex-wrap:wrap}
.card:has(input[name=ids]:checked) .bulk{display:flex}
@supports not selector(:has(a)){.bulk{display:flex}}
.bulk select{width:auto;padding:4px 30px 4px 8px}
.bulk button{padding:4px 12px}
input[type=checkbox]{accent-color:var(--accent);width:15px;height:15px;margin:0;vertical-align:middle;cursor:pointer}

/* ---- chips, badges, clocks --------------------------------------------- */
.chip{display:inline-block;padding:1px 8px;border-radius:999px;background:var(--chip);color:var(--ink);font-size:12px;font-weight:600;white-space:nowrap}
.sla-ok{background:var(--ok-bg);color:var(--ok)} .sla-warn{background:var(--warn-bg);color:var(--warn)} .sla-bad{background:var(--bad-bg);color:var(--bad)}
.pri{font-weight:700} .pri-P1{color:var(--bad)} .pri-P2{color:var(--warn)}
.muted{color:var(--ink-2)} .why{font-size:12px;color:var(--ink-3)}
.badge{display:inline-block;min-width:28px;text-align:center;border-radius:6px;padding:1px 6px;font-weight:700;font-size:11.5px;color:#fff;letter-spacing:.2px}
.badge.P1{background:#c62828}.badge.P2{background:#b26a00}.badge.P3{background:var(--accent)}.badge.P4{background:#6b7785}
.sla3{display:inline-flex;gap:3px;white-space:nowrap}
.sla3 span{font-size:11px;font-weight:700;border-radius:5px;padding:1px 6px;font-variant-numeric:tabular-nums}
.m,.o{background:var(--ok-bg);color:var(--ok)} .w{background:var(--warn-bg);color:var(--warn)}
.b{background:var(--bad-bg);color:var(--bad)} .d{background:var(--chip);color:var(--ink-3)}
.pill{font-size:11px;border-radius:999px;padding:1px 8px;background:var(--chip);color:var(--ink-2);font-weight:600}
.pill.live{background:var(--ok-bg);color:var(--ok)}
.slastrip{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px}
.slabox{position:relative;border-radius:var(--r-lg);padding:12px 14px;border:1px solid var(--line);background:var(--surface);overflow:hidden}
.slabox::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--ok)}
.slabox.warn::before{background:var(--warn)} .slabox.bad::before{background:var(--bad)} .slabox.done::before{background:var(--line-2)}
.slabox .t{font-size:11px;color:var(--ink-3);text-transform:uppercase;letter-spacing:.5px}
.slabox .v{font-size:16px;font-weight:650;letter-spacing:-.2px;margin-top:2px}
.slabox.bad .v{color:var(--bad)}
.bar{height:6px;background:var(--surface-3);border-radius:4px;margin-top:8px;overflow:hidden}
.bar i{display:block;height:100%;border-radius:4px;background:var(--ok);transition:width .6s var(--ease)}
.slabox.warn .bar i{background:var(--warn)} .slabox.bad .bar i{background:var(--bad)} .slabox.done .bar i{background:var(--line-2)}

/* ---- forms ------------------------------------------------------------- */
form.stack{display:flex;flex-direction:column;gap:10px;max-width:440px}
label{font-size:12px;font-weight:600;color:var(--ink-2);letter-spacing:.1px}
input,select,textarea{font:inherit;color:var(--ink);padding:8px 10px;border:1px solid var(--line-2);border-radius:var(--r);
  background:var(--surface);width:100%;transition:border-color var(--fast) var(--ease),box-shadow var(--fast) var(--ease)}
input:hover,select:hover,textarea:hover{border-color:var(--ink-3)}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--ring)}
input::placeholder,textarea::placeholder{color:var(--ink-3)}
select{appearance:none;-webkit-appearance:none;padding-right:30px;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%237a8290' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 10px center}
textarea{min-height:90px;resize:vertical;line-height:1.5}
input[type=file]{padding:6px 8px;font-size:13px}
input[type=radio]{width:15px;height:15px;accent-color:var(--accent);margin:0 4px 0 0;vertical-align:-2px}
button,.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;font:inherit;font-weight:600;padding:8px 14px;border-radius:var(--r);
  border:1px solid var(--accent);background:var(--accent);color:var(--on-accent);cursor:pointer;line-height:1.3;
  transition:background var(--fast) var(--ease),border-color var(--fast) var(--ease),transform var(--fast) var(--ease),box-shadow var(--fast) var(--ease)}
button:hover,.btn:hover{background:var(--accent-2);border-color:var(--accent-2);text-decoration:none}
button:active,.btn:active{transform:scale(.985)}
button.ghost,.btn.ghost{background:var(--surface);color:var(--accent);border-color:var(--line-2)}
button.ghost:hover,.btn.ghost:hover{background:var(--surface-2);border-color:var(--accent)}
button.small{padding:1px 8px;line-height:20px;font-size:12px}
button[disabled]{opacity:.55;cursor:not-allowed}
button[aria-busy=true]{color:transparent;position:relative;pointer-events:none}
button[aria-busy=true]::after{content:"";position:absolute;width:14px;height:14px;border-radius:50%;border:2px solid var(--on-accent);
  border-right-color:transparent;animation:spin .7s linear infinite}
button.ghost[aria-busy=true]::after{border-color:var(--accent);border-right-color:transparent}
@keyframes spin{to{transform:rotate(360deg)}}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:end}
.row>div{flex:1;min-width:140px}
.fields label{display:block;margin-top:10px}
.fields .ro{padding:8px 10px;background:var(--surface-2);border-radius:var(--r);font-size:13px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px 16px}
.radiorow label{display:block;font-weight:500;color:var(--ink);margin:3px 0}
.toolbar{display:flex;gap:8px;align-items:end;flex-wrap:wrap}
.toolbar>div{min-width:130px}
.seg{display:inline-flex;border:1px solid var(--line-2);border-radius:var(--r);overflow:hidden;background:var(--surface)}
.seg label{position:relative;padding:0;font-weight:600;color:var(--ink-2);cursor:pointer;border-right:1px solid var(--line);margin:0}
.seg label:last-child{border-right:none}
.seg label span{display:block;padding:6px 12px;transition:background var(--fast) var(--ease),color var(--fast) var(--ease)}
.seg input{position:absolute;opacity:0;width:1px;height:1px;margin:0}
.seg input:focus-visible+span{outline:2px solid var(--ring);outline-offset:-2px}
.seg input:checked+span{background:var(--accent-bg);color:var(--accent)}
.seg label.int input:checked+span{background:var(--warn-bg);color:var(--warn)}
.seg label.res input:checked+span{background:var(--ok-bg);color:var(--ok)}
table.edit td{padding:5px 6px} table.edit input,table.edit select{padding:5px 7px;font-size:13px}
.inline{display:inline} .dispatch-route select{width:auto;min-width:130px}
.linkrow{display:inline-flex;gap:6px;flex-wrap:wrap;vertical-align:middle} .linkrow .btn{padding:2px 8px;font-size:12px}
ul.plain{list-style:none;padding:0;margin:0} ul.plain li{padding:7px 0;border-bottom:1px solid var(--line)} ul.plain li:last-child{border-bottom:none}
.kv{display:grid;grid-template-columns:auto 1fr;gap:5px 12px;font-size:13px} .kv dt{color:var(--ink-3)} .kv dd{margin:0}

/* ---- the ticket: notes, tabs, layout ----------------------------------- */
.rail{display:grid;grid-template-columns:minmax(0,2fr) minmax(300px,1fr);gap:16px;align-items:start}
.hdr{display:flex;align-items:start;gap:12px;flex-wrap:wrap} .hdr .grow{flex:1;min-width:0}
.tabs{display:flex;gap:2px;border-bottom:1px solid var(--line);margin-bottom:12px}
.tabs a{padding:7px 12px;color:var(--ink-2);border-bottom:2px solid transparent;margin-bottom:-1px;border-radius:var(--r-sm) var(--r-sm) 0 0;
  transition:color var(--fast) var(--ease),background var(--fast) var(--ease)}
.tabs a:hover{color:var(--ink);background:var(--surface-2);text-decoration:none}
.tabs a.on{color:var(--ink);border-color:var(--accent);font-weight:600}
.stabs{display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap}
.stabs a{padding:6px 14px;border-radius:999px;background:var(--surface);border:1px solid var(--line);color:var(--ink-2);font-weight:600;
  transition:background var(--fast) var(--ease),color var(--fast) var(--ease),border-color var(--fast) var(--ease)}
.stabs a:hover{border-color:var(--line-2);color:var(--ink);text-decoration:none}
.stabs a.on{background:var(--ink);color:var(--canvas);border-color:var(--ink)}
.stream{list-style:none;padding:0;margin:0} .stream li{padding:8px 0;border-bottom:1px solid var(--line)} .stream li:last-child{border-bottom:none}
.stream .meta{color:var(--ink-3);font-size:12px}
.note{position:relative;border:1px solid var(--line);border-radius:var(--r-lg);padding:10px 12px 10px 16px;margin-bottom:10px;background:var(--surface);overflow:hidden}
.note::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--accent)}
.note.INTERNAL{background:var(--warn-bg);border-color:transparent} .note.INTERNAL::before{background:var(--warn)}
.note.RESOLUTION{background:var(--ok-bg);border-color:transparent} .note.RESOLUTION::before{background:var(--ok)}
.note .h{display:flex;gap:8px;align-items:center;font-size:12px;color:var(--ink-3);margin-bottom:4px;flex-wrap:wrap}
.av{width:24px;height:24px;border-radius:50%;background:linear-gradient(135deg,var(--accent-bg),var(--surface-3));color:var(--accent);font-weight:700;
  font-size:11px;display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--line)}
.flag{font-size:11px;font-weight:700;border-radius:5px;padding:0 6px}
.flag.DISCUSSION{background:var(--accent-bg);color:var(--accent)} .flag.INTERNAL{background:var(--warn-bg);color:var(--warn)} .flag.RESOLUTION{background:var(--ok-bg);color:var(--ok)}
.sys{font-size:12px;color:var(--ink-3);padding:2px 0 8px 32px}
.note-ph{font-size:12px;color:var(--warn);background:var(--warn-bg);border-radius:var(--r);padding:8px 12px;margin-bottom:10px}
em{font-style:italic}

/* ---- command palette --------------------------------------------------- */
.pal-box{width:min(640px,100%);background:var(--surface);border:1px solid var(--line-2);border-radius:14px;box-shadow:var(--shadow);overflow:hidden;
  transition:opacity var(--fast) var(--ease),transform var(--fast) var(--ease)}
@starting-style{.pal-box{opacity:0;transform:translateY(-8px) scale(.98)}}
.pal-box input{border:none;border-bottom:1px solid var(--line);border-radius:0;padding:14px 16px;font-size:16px;background:transparent}
.pal-box input:focus{box-shadow:none;border-color:var(--line)}
.pal-box ul{list-style:none;margin:0;padding:6px;max-height:50vh;overflow:auto}
.pal-box li{display:flex;justify-content:space-between;gap:12px;padding:8px 10px;border-radius:var(--r);cursor:pointer;color:var(--ink)}
.pal-box li small{color:var(--ink-3)} .pal-box li.on,.pal-box li:hover{background:var(--accent-bg)}
.pal-box .hint{padding:6px 12px 10px;color:var(--ink-3);font-size:11px;border-top:1px solid var(--line);display:flex;gap:12px;flex-wrap:wrap}

/* ---- motion: page transitions, and none of it for those who ask ------- */
@media (prefers-reduced-motion:no-preference){
  @view-transition{navigation:auto}
  header.top{view-transition-name:hdr}
  ::view-transition-old(hdr),::view-transition-new(hdr){animation:none}
  ::view-transition-old(root){animation:160ms var(--ease) both vt-out}
  ::view-transition-new(root){animation:200ms var(--ease) both vt-in}
}
@keyframes vt-out{to{opacity:0}}
@keyframes vt-in{from{opacity:0;transform:translateY(4px)}}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{transition:none!important;animation:none!important;scroll-behavior:auto!important}}

/* ---- small screens ----------------------------------------------------- */
@media (max-width:1100px){.tablewrap{overflow-x:auto} table.grid thead th{position:static} table.grid td.wrap{white-space:nowrap}}
@media (max-width:900px){.tiles{grid-template-columns:repeat(2,1fr)}.slastrip{grid-template-columns:1fr}.grid2{grid-template-columns:1fr}.rail{grid-template-columns:1fr}}
@media (max-width:720px){main{padding:14px 12px}h1{font-size:19px}header.top .who span.name{display:none}.card{padding:12px 14px}.tile .n{font-size:22px}}
""".replace("DARKTOKENS", """
  --canvas:#0f1115; --surface:#161920; --surface-2:#1c2029; --surface-3:#232833;
  --ink:#eef0f4; --ink-2:#aeb5c2; --ink-3:#7d8594; --line:#262b36; --line-2:#343a47;
  --accent:#7b93ff; --accent-2:#94a7ff; --on-accent:#0b1020;
  --ok:#3fb950; --warn:#e3b341; --bad:#ff6b6b; --chip:#232833;
  --shadow:0 14px 40px -14px rgb(0 0 0/.7); --glass:rgb(22 25 32/.78);
  --s1:#3987e5; --s2:#d95926;
""")

# The one script. Progressive enhancement only: every page works with it off.
#   * a command palette (Ctrl/Cmd+K): pages, "new ticket", a ticket number,
#     and the rows on the board you are looking at;
#   * keyboard: / search, n new ticket, g then b/d/c/s to go, j/k/Enter/x on
#     the board, ? for the list, t theme, Esc closes;
#   * a form marks its button busy on submit and refuses a second submit;
#   * hovering a ticket link prefetches it, so the click lands on a warm cache;
#   * the theme toggle, remembered in this browser only.
SCRIPT = r"""
(function(){
"use strict";
var d=document,root=d.documentElement;
function $(s,c){return (c||d).querySelector(s)}function $$(s,c){return Array.prototype.slice.call((c||d).querySelectorAll(s))}
function inField(e){var t=e.target;return t&&(/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)||t.isContentEditable)}
/* theme */
function setTheme(t){try{if(t)localStorage.setItem("psa-theme",t);else localStorage.removeItem("psa-theme")}catch(e){}
  if(t)root.dataset.theme=t;else delete root.dataset.theme}
function toggleTheme(){var dark=root.dataset.theme?root.dataset.theme==="dark":matchMedia("(prefers-color-scheme: dark)").matches;setTheme(dark?"light":"dark")}
var tb=$("#theme");if(tb)tb.addEventListener("click",toggleTheme);
var po=$("#pal-open");if(po)po.addEventListener("click",function(){open("")});
/* busy buttons, no double submit */
d.addEventListener("submit",function(e){var f=e.target;if(f.dataset.sent){e.preventDefault();return}f.dataset.sent="1";
  var b=e.submitter||$("button[type=submit],button:not([type])",f);if(b){b.setAttribute("aria-busy","true")}
  setTimeout(function(){delete f.dataset.sent;if(b)b.removeAttribute("aria-busy")},8000)});
/* prefetch on hover intent */
var seen={};d.addEventListener("mouseover",function(e){var a=e.target.closest&&e.target.closest("a[href^='/ticket/'],a[href^='/?']");
  if(!a||seen[a.href])return;var h=a.href;var t=setTimeout(function(){if(seen[h])return;seen[h]=1;var l=d.createElement("link");l.rel="prefetch";l.href=h;d.head.appendChild(l)},70);
  a.addEventListener("mouseout",function(){clearTimeout(t)},{once:true})});
/* select all + count on the board */
var all=$("input[data-all]");if(all)all.addEventListener("change",function(){$$("input[name=ids]").forEach(function(c){c.checked=all.checked});count()});
function count(){var n=$$("input[name=ids]:checked").length;var c=$("[data-count]");if(c)c.textContent=n}
d.addEventListener("change",function(e){if(e.target.name==="ids")count()});
/* board rows: j/k/Enter/x */
var rows=$$("table.grid tbody tr"),cur=-1;
function go(i){if(!rows.length)return;if(cur>=0)rows[cur].classList.remove("cur");cur=Math.max(0,Math.min(rows.length-1,i));
  rows[cur].classList.add("cur");rows[cur].scrollIntoView({block:"nearest"})}
/* palette */
var pal=$("#pal"),pq=$("#pal-q"),pl=$("#pal-list"),items=[],sel=0;
var pages=[["Service Board","/","g b"],["Dispatch","/dispatch","g d"],["Companies","/companies","g c"],["On-call","/oncall",""],["Setup","/admin","g s"],["My requests","/my",""],["New ticket","/ticket/new","n"]];
function ticketFrom(q){var m=q.trim().match(/^(pmc|ito|pcsd)[- ]?0*(\d{1,6})$/i);if(!m)return null;var pre=m[1].toUpperCase();
  return pre==="PMC"?"PMC-"+("000000"+m[2]).slice(-6):pre+"-"+m[2]}
var remote={q:"",tickets:[],contacts:[],configurations:[]},rtimer=null;
function fetchRemote(q){if(q.trim().length<2){remote={q:q,tickets:[],contacts:[],configurations:[]};return}
  clearTimeout(rtimer);rtimer=setTimeout(function(){fetch("/search.json?q="+encodeURIComponent(q.trim()),{credentials:"same-origin"})
    .then(function(r){return r.ok?r.json():null}).then(function(j){if(!j||j.q!==q.trim()||!pal||!pal.open)return;remote=j;items=build(pq.value);render()})
    .catch(function(){})},120)}
function build(q){var ql=q.trim().toLowerCase(),out=[];var tk=ticketFrom(q);if(tk)out.push({t:"Open "+tk,s:"ticket",h:"/ticket/"+tk});
  pages.forEach(function(p){if(!ql||p[0].toLowerCase().indexOf(ql)>=0)out.push({t:p[0],s:p[2],h:p[1]})});
  if(ql.length>=2)rows.forEach(function(r){var a=$("a[href^='/ticket/']",r);if(!a)return;var txt=r.textContent.replace(/\s+/g," ").trim();
    if(txt.toLowerCase().indexOf(ql)>=0&&out.length<12)out.push({t:a.textContent+" · "+($("td.sum b",r)||{textContent:""}).textContent.slice(0,70),s:"on this board",h:a.getAttribute("href")})});
  if(remote.q===q.trim()&&ql.length>=2){var have={};out.forEach(function(o){have[o.h]=1});
    remote.tickets.forEach(function(x){if(!have["/ticket/"+x.id])out.push({t:x.id+" · "+(x.summary||"").slice(0,70),s:(x.who||"")+" · "+(x.state||"").toLowerCase(),h:"/ticket/"+x.id,st:x.priority})});
    remote.contacts.forEach(function(x){out.push({t:x.name,s:(x.department||"")+" · contact",h:"/contact/"+x.id})});
    remote.configurations.forEach(function(x){out.push({t:x.name,s:(x.type||"")+" · machine",h:"/configuration/"+x.id})})}
  [["Toggle light / dark","t","#theme"],["Compact rows","density","#compact"],["Comfortable rows","density","#comfortable"]].forEach(function(c){
    if(!ql||c[0].toLowerCase().indexOf(ql)>=0)out.push({t:c[0],s:c[1],h:c[2]})});return out.slice(0,16)}
function render(){pl.innerHTML="";items.forEach(function(it,i){var li=d.createElement("li");if(i===sel)li.className="on";
  li.innerHTML="<span></span><small></small>";li.firstChild.textContent=it.t;li.lastChild.textContent=it.s;
  if(it.st){var b=d.createElement("b");b.className="st";b.textContent=it.st;li.firstChild.insertBefore(b,li.firstChild.firstChild)}
  li.addEventListener("mousedown",function(e){e.preventDefault();choose(it)});pl.appendChild(li)})}
function choose(it){if(!it)return;if(it.h==="#theme"){toggleTheme();close();return}
  if(it.h==="#compact"||it.h==="#comfortable"){setDensity(it.h==="#compact"?"compact":"");close();return}location.href=it.h}
function open(q){if(!pal)return;if(!pal.open)pal.showModal();pq.value=q||"";items=build(pq.value);sel=0;render();pq.focus()}
function close(){if(!pal)return;if(pal.open)pal.close();pq.blur()}
if(pal){pq.addEventListener("input",function(){items=build(pq.value);sel=0;render();fetchRemote(pq.value)});
  pq.addEventListener("keydown",function(e){if(e.key==="ArrowDown"){sel=(sel+1)%items.length;render();e.preventDefault()}
    else if(e.key==="ArrowUp"){sel=(sel-1+items.length)%items.length;render();e.preventDefault()}
    else if(e.key==="Enter"){choose(items[sel]);e.preventDefault()}else if(e.key==="Escape"){close()}});
  pal.addEventListener("mousedown",function(e){if(e.target===pal)close()});
  pal.addEventListener("cancel",function(e){e.preventDefault();close()})}
/* toasts: a close button; the good news fades by itself (CSS) */
$$(".toast").forEach(function(t){var b=d.createElement("button");b.type="button";b.className="iconbtn x";b.setAttribute("aria-label","Dismiss");
  b.innerHTML='<svg class=ic aria-hidden=true><use href=#i-x></use></svg>';b.addEventListener("click",function(){t.remove()});t.appendChild(b)});
/* a thin progress bar while the next page is on its way */
var np=$("#nprog");
d.addEventListener("click",function(e){var a=e.target.closest&&e.target.closest("a[href]");if(!a||!np)return;
  if(a.target||a.hasAttribute("download")||e.metaKey||e.ctrlKey||a.host!==location.host||a.getAttribute("href").charAt(0)==="#")return;
  np.className="go"});
d.addEventListener("submit",function(){if(np)np.className="go"});
addEventListener("pageshow",function(){if(np)np.className=""});
/* pods: the ticket's side cards reorder by drag (or the arrows) and fold, remembered here */
(function(){var rail=$(".pods");if(!rail)return;var KEY="psa-pods";
  function state(){try{return JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){return {}}}
  function save(st){try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}}
  function pods(){return $$(".card[data-pod]",rail)}
  function ic(n){return '<svg class=ic aria-hidden=true><use href=#i-'+n+'></use></svg>'}
  function apply(){var st=state(),order=st.order||[];pods().sort(function(a,b){var i=order.indexOf(a.dataset.pod),j=order.indexOf(b.dataset.pod);
      return (i<0?99:i)-(j<0?99:j)}).forEach(function(c){rail.appendChild(c)});
    pods().forEach(function(c){c.classList.toggle("collapsed",!!(st.folded||{})[c.dataset.pod])});
    var r=$(".podreset",rail);if(r)r.style.display=(order.length||Object.keys(st.folded||{}).length)?"":"none"}
  function remember(){var st=state();st.order=pods().map(function(c){return c.dataset.pod});
    st.folded={};pods().forEach(function(c){if(c.classList.contains("collapsed"))st.folded[c.dataset.pod]=1});save(st);apply()}
  pods().forEach(function(c){c.draggable=true;var h=$("h3",c);if(!h)return;
    var ctl=d.createElement("span");ctl.className="podctl";
    ctl.innerHTML='<button type=button class="iconbtn mv" data-dir=-1 title="Move up" aria-label="Move up">'+ic("up")+'</button>'
      +'<button type=button class="iconbtn mv" data-dir=1 title="Move down" aria-label="Move down">'+ic("down")+'</button>'
      +'<button type=button class="iconbtn fold" title="Fold" aria-label="Fold or unfold" aria-expanded=true>'+ic("chevron")+'</button>';
    c.appendChild(ctl);
    $(".fold",ctl).addEventListener("click",function(){c.classList.toggle("collapsed");this.setAttribute("aria-expanded",String(!c.classList.contains("collapsed")));remember()});
    $$(".mv",ctl).forEach(function(b){b.addEventListener("click",function(){var dir=+b.dataset.dir,list=pods(),i=list.indexOf(c),j=i+dir;
      if(j<0||j>=list.length)return;rail.insertBefore(c,dir<0?list[j]:list[j].nextSibling);remember()})});
    c.addEventListener("dragstart",function(e){c.classList.add("dragging");e.dataTransfer.effectAllowed="move";e.dataTransfer.setData("text/plain",c.dataset.pod)});
    c.addEventListener("dragend",function(){c.classList.remove("dragging");pods().forEach(function(x){x.classList.remove("over")})});
    c.addEventListener("dragover",function(e){e.preventDefault();e.dataTransfer.dropEffect="move";c.classList.add("over")});
    c.addEventListener("dragleave",function(){c.classList.remove("over")});
    c.addEventListener("drop",function(e){e.preventDefault();var from=$(".card[data-pod='"+e.dataTransfer.getData("text/plain")+"']",rail);
      if(from&&from!==c)rail.insertBefore(from,c);remember()})});
  var reset=d.createElement("div");reset.className="podreset";reset.innerHTML='<button type=button class=ghost>Reset layout</button>';
  reset.style.display="none";rail.insertBefore(reset,rail.firstChild);
  $("button",reset).addEventListener("click",function(){save({});pods().forEach(function(c){c.classList.remove("collapsed")});
    var order=rail.dataset.order?rail.dataset.order.split(","):[];order.forEach(function(k){var c=$(".card[data-pod='"+k+"']",rail);if(c)rail.appendChild(c)});apply()});
  apply()})();
/* a standard note fills the note box and sets its flag; the words stay editable */
var sn=$("#stdnote");if(sn)sn.addEventListener("change",function(){var o=sn.options[sn.selectedIndex];if(!o||!o.value)return;
  var f=sn.closest("form"),ta=$("textarea[name=body]",f),fl=$("input[name=flag][value='"+o.dataset.flag+"']",f);
  if(ta){ta.value=o.dataset.body||"";ta.focus()}if(fl)fl.checked=true});
/* density: compact rows for the power user, remembered here */
function setDensity(v){try{v?localStorage.setItem("psa-density",v):localStorage.removeItem("psa-density")}catch(e){}
  if(v)root.dataset.density=v;else delete root.dataset.density;$$(".densi button").forEach(function(b){b.setAttribute("aria-pressed",String((b.dataset.density||"")===(v||"")))})}
try{setDensity(localStorage.getItem("psa-density")||"")}catch(e){}
$$(".densi button").forEach(function(b){b.addEventListener("click",function(){setDensity(b.dataset.density||"")})});
/* shortcuts */
var pend=null;
var requester=d.body.hasAttribute("data-requester");
d.addEventListener("keydown",function(e){
  if(requester)return;
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="k"){e.preventDefault();pal&&!pal.open?open(""):close();return}
  if(e.key==="Escape"){close();if(cur>=0){rows[cur].classList.remove("cur");cur=-1}return}
  if(inField(e)||e.ctrlKey||e.metaKey||e.altKey)return;
  if(pend){var k=pend;pend=null;var m={b:"/",d:"/dispatch",c:"/companies",s:"/admin"}[e.key];if(k==="g"&&m){location.href=m;e.preventDefault()}return}
  switch(e.key){case "/":{var q=$("input[name=q]");if(q){q.focus();q.select()}else open("");e.preventDefault();break}
    case "?":{var kk=$("#keys");if(kk&&kk.togglePopover)kk.togglePopover();else open("");break}case "n":location.href="/ticket/new";break;case "t":toggleTheme();break;
    case "g":pend="g";setTimeout(function(){pend=null},900);break;
    case "j":go(cur+1);e.preventDefault();break;case "k":go(cur-1);e.preventDefault();break;
    case "x":if(cur>=0){var c=$("input[name=ids]",rows[cur]);if(c){c.checked=!c.checked;count()}}break;
    case "Enter":if(cur>=0){var a=$("a[href^='/ticket/']",rows[cur]);if(a)location.href=a.getAttribute("href")}break}
});
})();
"""

# The icon set: two dozen 24-grid stroke icons drawn here (no icon font, no
# CDN), emitted once per page as <symbol>s and used by id. Same weight and
# corner as the rest of the type, so an icon reads as a word, not a sticker.
ICONS = {
    "board": "M4 5h16M4 12h16M4 19h10",
    "dispatch": "M4 12h13M13 6l6 6-6 6",
    "companies": "M4 21V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v16M14 9h5a1 1 0 0 1 1 1v11M8 8h2M8 12h2M8 16h2M4 21h16",
    "oncall": "M5 4h3l2 5-2.5 1.5a11 11 0 0 0 6 6L15 14l5 2v3a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2",
    "uplift": "M3 17l6-6 4 4 8-8M15 7h6v6",
    "setup": "M4 7h10M18 7h2M4 17h4M12 17h8M14 4v6M8 14v6",
    "my": "M20 21a8 8 0 0 0-16 0M12 13a4 4 0 1 0 0-8 4 4 0 0 0 0 8",
    "plus": "M12 5v14M5 12h14",
    "search": "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14M20 20l-4-4",
    "sun": "M12 3v2M12 19v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M3 12h2M19 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8",
    "ticket": "M3 8a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4zM13 6v12",
    "note": "M21 12a8 8 0 0 1-11.6 7.2L4 20l1.1-4.4A8 8 0 1 1 21 12",
    "lock": "M6 11V8a6 6 0 0 1 12 0v3M5 11h14v10H5z",
    "check": "M20 7 10 17l-5-5",
    "checks": "M3 12l5 5L18 7M8 17l1.5 1.5L21 7",
    "clock": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18M12 7v5l3 2",
    "paperclip": "M20 12l-8.5 8.5a5 5 0 0 1-7-7L13 5a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L15 7",
    "link": "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7L11.5 6.8M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1.5-1.5",
    "monitor": "M3 5h18v11H3zM8 20h8M12 16v4",
    "briefcase": "M3 8h18v12H3zM8 8V5h8v3M3 13h18",
    "info": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18M12 11v5M12 8h.01",
    "inbox": "M3 13h5l2 3h4l2-3h5M3 13l2.5-8h13L21 13v6H3z",
    "users": "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8",
    "tag": "M3 12V4h8l9 9-8 8zM7.5 8h.01",
    "alert": "M12 3 2 20h20zM12 10v4M12 17h.01",
    "flag": "M5 21V4M5 4h13l-2 4 2 4H5",
    "x": "M6 6l12 12M18 6 6 18",
    "filter": "M3 5h18l-7 8v6l-4-2v-4z",
    "arrow": "M5 12h14M13 6l6 6-6 6",
    "keyboard": "M3 6h18v12H3zM7 10h.01M11 10h.01M15 10h.01M7 14h10",
    "mail": "M3 6h18v12H3zM3 7l9 6 9-6",
    "bell": "M6 16V11a6 6 0 0 1 12 0v5l2 2H4zM10 21h4",
    "layers": "M12 3 2 8l10 5 10-5zM2 13l10 5 10-5M2 18l10 5 10-5",
    "building": "M3 21h18M5 21V4h14v17M9 8h2M13 8h2M9 12h2M13 12h2M9 16h2M13 16h2",
    "shield": "M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z",
    "rows": "M3 6h18M3 12h18M3 18h18",
    "chevron": "m6 9 6 6 6-6",
    "reports": "M4 20V10M10 20V4M16 20v-7M22 20H2",
    "calendar": "M3 5h18v16H3zM3 10h18M8 3v4M16 3v4",
    "star": "m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3 6.4 20.2l1.1-6.2L3 9.6l6.2-.9z",
    "grip": "M9 5h.01M15 5h.01M9 12h.01M15 12h.01M9 19h.01M15 19h.01",
    "up": "M12 19V5M5 12l7-7 7 7",
    "down": "M12 5v14M5 12l7 7 7-7",
    "sparkle": "M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6",
}


def icon(name: str, cls: str = "") -> str:
    """One icon by id from the page's sprite. Decorative: the word beside it
    carries the meaning, so it is hidden from assistive technology."""
    return (f'<svg class="ic {cls}" aria-hidden=true>' if cls else "<svg class=ic aria-hidden=true>") + \
        f"<use href=#i-{name}></use></svg>"


def h3(text: str, icon_name: str | None = None) -> str:
    return f"<h3>{icon(icon_name) if icon_name else ''}{esc(text)}</h3>"


def _sprite() -> str:
    return ('<svg hidden xmlns="http://www.w3.org/2000/svg">' + "".join(
        f'<symbol id="i-{k}" viewBox="0 0 24 24"><path d="{v}"/></symbol>' for k, v in ICONS.items())
        + "</svg>")


SPRITE = _sprite()
FAVICON = ("data:image/svg+xml," + "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
           "%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%233d63dd'/%3E"
           "%3Cstop offset='1' stop-color='%239ad0ff'/%3E%3C/linearGradient%3E%3C/defs%3E"
           "%3Crect width='32' height='32' rx='9' fill='url(%23g)'/%3E"
           "%3Cpath d='M9 11h14M9 16h14M9 21h8' stroke='white' stroke-width='3' stroke-linecap='round'/%3E%3C/svg%3E")

THEME_BOOT = ("<script>try{var t=localStorage.getItem('psa-theme');if(t)document.documentElement"
              ".dataset.theme=t}catch(e){}</script>")



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


def page(title: str, body: str, *, user=None, active: str = "", requester: bool | None = None) -> str:
    """The shell every page shares: header, nav, the acting user, the body.

    A break-glass session is marked in the corner, in amber, on every page. Who
    is at the desk and how they got in is not a detail to hunt for in a log when
    the desk is being run on the fallback path.
    """
    # The requester's shell: the person is on no board, or came to the portal's
    # own address. One entry, no New ticket button (the portal's form is on the
    # page), no command palette and no keyboard sheet: those are the
    # technician's tools, and their shortcuts would send a requester to desk
    # pages that answer 404 or "not a member".
    if requester is None:
        requester = user is not None and getattr(user, "requester", False)
    nav_items = [
        ("board", "/", "Service Board"),
        ("dispatch", "/dispatch", "Dispatch"),
        ("companies", "/companies", "Companies"),
        ("oncall", "/oncall", "On-call"),
        ("reports", "/reports", "Reports"),
        ("uplift", "/uplift", "Uplift"),
        ("admin", "/admin", "Setup"),
        ("my", "/my", "My requests"),
    ]
    if requester:
        nav_items = [("my", "/my", "My requests")]
        active = "my"
    nav = "".join(
        f'<a href="{esc(href)}"{" class=on aria-current=page" if key == active else ""}>'
        f'{icon("setup" if key == "admin" else key)}{esc(label)}</a>'
        for key, href, label in nav_items)
    nav += (f'<a class="newbtn" href="/ticket/new" title="New ticket (n)">{icon("plus")} New ticket</a>'
            if user is not None and not requester else "")
    who = ""
    if user is not None:
        glass = ('<span class="glass">break-glass</span> · ' if user.via == "local" else "")
        tools = ""
        if not requester:
            tools = ('<button class="iconbtn" id="pal-open" type="button" title="Search and commands (Ctrl+K)"'
                     ' aria-label="Search and commands"><span class=kbd>⌘K</span></button>'
                     '<button class="iconbtn" type="button" popovertarget="keys" title="Keyboard shortcuts (?)"'
                     f' aria-label="Keyboard shortcuts">{icon("keyboard")}</button>')
        who = (f'<div class="who">{glass}<span class=name>{esc(user.name)}</span>'
               f' · <a href="/logout">sign out</a>' + tools +
               f'<button class="iconbtn" id="theme" type="button" title="Light / dark (t)"'
               f' aria-label="Toggle light or dark">{icon("sun")}</button></div>')
    palette = ""
    if user is not None and not requester:
        palette = (
            '<dialog id="pal" aria-label="Commands"><div class="pal-box">'
            '<input id="pal-q" autocomplete="off" spellcheck="false" placeholder="Go to a page, open PMC-000123, or search this board…">'
            '<ul id="pal-list"></ul><div class=hint><span><span class=kbd>↑↓</span> move</span>'
            '<span><span class=kbd>↵</span> open</span><span><span class=kbd>esc</span> close</span></div></div></dialog>'
            '<div id="keys" popover><b>Keyboard</b><dl>'
            '<dt><span class=kbd>⌘</span> <span class=kbd>K</span></dt><dd>commands and search</dd>'
            '<dt><span class=kbd>/</span></dt><dd>search the board</dd>'
            '<dt><span class=kbd>n</span></dt><dd>new ticket</dd>'
            '<dt><span class=kbd>g</span> then <span class=kbd>b</span> <span class=kbd>d</span> <span class=kbd>c</span> <span class=kbd>s</span></dt>'
            '<dd>board, dispatch, companies, setup</dd>'
            '<dt><span class=kbd>j</span> <span class=kbd>k</span> <span class=kbd>x</span> <span class=kbd>↵</span></dt>'
            '<dd>down, up, tick, open a row</dd>'
            '<dt><span class=kbd>t</span></dt><dd>light / dark</dd>'
            '<dt><span class=kbd>esc</span></dt><dd>close</dd></dl></div>')
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        '<meta name=color-scheme content="light dark">'
        '<meta name=theme-color media="(prefers-color-scheme: light)" content="#f4f5f8">'
        '<meta name=theme-color media="(prefers-color-scheme: dark)" content="#0f1115">'
        f'<link rel=icon href="{FAVICON}">'
        f"<title>{esc(title)} · {'PMC IT help' if requester else 'PSA desk'}</title>{THEME_BOOT}"
        f"<style>{STYLE}</style></head><body{' data-requester' if requester else ''}>"
        f'<div id="nprog" aria-hidden="true"></div>{SPRITE}'
        f'<header class="top"><a class="brand" href="{"/my" if requester else "/"}"><i></i>'
        f'{"PMC IT help" if requester else "PSA desk"}</a>'
        f"<nav>{nav}</nav>{who}</header>"
        f"<main>{body}</main>"
        "<footer>PMC PSA spine — Phase B pilot. LAN only, Dada IT only. "
        "Kitameraki remains the system of record until dual-run ends.</footer>"
        f"{palette}<script>{SCRIPT}</script></body></html>")


def login_page(*, entra_configured: bool, error: str = "", next_url: str = "/",
               windows_domain: str | None = None) -> str:
    err = f'<div class="banner err">{esc(error)}</div>' if error else ""
    windows = ""
    if windows_domain:
        windows = (
            '<div class="card"><h1>Sign in</h1>'
            f'<p class="sub">Your Windows account, the one you use on your PC ({esc(windows_domain)}).</p>'
            '<form class="stack" method="post" action="/login">'
            '<input type="hidden" name="door" value="windows">'
            f'<input type="hidden" name="next" value="{esc(next_url)}">'
            "<label>Username<input name=username autocomplete=username autofocus></label>"
            "<label>Password<input name=password type=password "
            "autocomplete=current-password></label>"
            "<button type=submit>Sign in</button></form></div>")
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
        '<input type="hidden" name="door" value="local">'
        f'<input type="hidden" name="next" value="{esc(next_url)}">'
        f"<label>Username<input name=username autocomplete=username{'' if windows_domain else ' autofocus'}></label>"
        "<label>Password<input name=password type=password "
        "autocomplete=current-password></label>"
        "<button type=submit>Sign in</button></form></div>")
    body = err + windows + entra + glass
    return page("Sign in", body)
