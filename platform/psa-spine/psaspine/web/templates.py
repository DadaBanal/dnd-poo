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
.dispatchwrap{display:grid;grid-template-columns:460px minmax(0,1fr);gap:14px;align-items:start}.dispatchwrap.folded{grid-template-columns:minmax(0,1fr)}.dispatchwrap.folded .stpanel{display:none}.dispatchwrap:not(.folded) .stshow{display:none}@media (max-width:1100px){.dispatchwrap{grid-template-columns:1fr}}.stpanel .sthead{display:flex;align-items:center;gap:8px}.stpanel .sthead h3{flex:1}.stfilter{gap:6px;margin:6px 0 8px;flex-wrap:wrap}.stfilter>div:first-child{flex:1 1 140px}.stpanel .tablewrap.stwrap{max-height:calc(100vh - 360px);min-height:200px;overflow:auto}table.sttable{font-size:12.5px}table.sttable th{position:sticky;top:0;background:var(--card);z-index:2}table.sttable td,table.sttable th{padding:5px 6px;white-space:nowrap}table.sttable td.stsum{white-space:normal;min-width:160px;max-width:260px}table.sttable tr[draggable=true]{cursor:grab}table.sttable tr.dragging{opacity:.4}table.sttable tbody tr:hover{background:var(--surface-2)}table.schedgrid.dispatch td.hr{border-left:1px solid var(--line);background-image:linear-gradient(90deg,transparent calc(50% - 1px),color-mix(in srgb,var(--line) 60%,transparent) calc(50% - 1px),color-mix(in srgb,var(--line) 60%,transparent) 50%,transparent 50%)}table.schedgrid.dispatch th.who .rname{display:block;font-size:13px;font-weight:600;color:var(--ink);text-transform:none;letter-spacing:0;white-space:normal;line-height:1.25}table.schedgrid.dispatch th.who{width:150px;max-width:150px;padding:6px 8px}table.schedgrid.dispatch thead th.whoh{width:150px}table.schedgrid.dispatch.week td.wk{min-width:150px;height:auto;padding:4px;vertical-align:top}table.schedgrid.dispatch.week{min-width:1100px}table.schedgrid.dispatch.week .sch{position:static;height:auto;margin:0 0 4px}table.schedgrid.dispatch.week .sch:hover{width:auto!important;min-width:0}.sch.visit{background:color-mix(in srgb,var(--accent) 20%,var(--surface));border:1px solid color-mix(in srgb,var(--accent) 50%,transparent);border-left:4px solid var(--accent)}.sch.visit.tentative{background:color-mix(in srgb,var(--accent) 6%,var(--surface));border-style:dashed;border-left-style:solid}.sch.visit.done{opacity:1;text-decoration:none;background:color-mix(in srgb,#1a7f37 18%,var(--surface));border-color:color-mix(in srgb,#1a7f37 50%,transparent);border-left-color:#1a7f37}.sch.visit.done>b::before{content:'\2713 '}.sch.block.outlook{background:repeating-linear-gradient(45deg,var(--surface-2) 0 5px,var(--surface) 5px 10px)}.sch .rz{position:absolute;top:0;right:0;width:8px;height:100%;cursor:ew-resize;border-radius:0 var(--r-sm) var(--r-sm) 0}.sch .rz:hover{background:color-mix(in srgb,var(--accent) 35%,transparent)}.sch.resizing{opacity:.85;z-index:3!important;min-width:0!important;height:78px!important}.dlegend .sch{display:inline-block;padding:1px 8px;margin:0 6px 0 0;font-size:11px;vertical-align:middle}.ctxmenu{position:absolute;z-index:120;min-width:190px;padding:4px;background:var(--card);border:1px solid var(--line);border-radius:10px;box-shadow:0 10px 28px rgba(0,0,0,.25);display:flex;flex-direction:column}.ctxmenu button{background:none;border:0;text-align:left;padding:7px 12px;border-radius:6px;font:inherit;font-weight:500;color:var(--ink);cursor:pointer;height:auto;min-width:0;justify-content:flex-start}.ctxmenu button:hover{background:var(--surface-2)}.ctxmenu button.danger{color:#c62828}.todolist{max-height:70vh;overflow:auto}.todo{padding:8px;border:1px solid var(--line);border-radius:var(--r-sm);margin:0 0 6px;background:var(--surface);font-size:12.5px}.todo[draggable=true]{cursor:grab}.todo.dragging,.sch.dragging{opacity:.4}table.schedgrid.dispatch{min-width:1260px}table.schedgrid.dispatch td.hr{min-width:78px;height:44px;position:relative;overflow:visible;padding:0}table.schedgrid.dispatch td.hr .sch{position:absolute;z-index:1;margin:0;height:78px;overflow:hidden;white-space:normal;word-break:normal;overflow-wrap:normal;box-sizing:border-box;line-height:1.3}table.schedgrid.dispatch td.hr .sch:hover{z-index:2;height:auto;min-height:78px;width:auto!important;min-width:150px}table.schedgrid.dispatch td.hr .sch.clash{outline:2px solid #c62828;outline-offset:-1px}.nowline{position:absolute;top:0;bottom:0;width:2px;background:#d32f2f;z-index:3;pointer-events:none}.util{display:block;margin-top:4px;height:6px;border-radius:3px;background:var(--line);overflow:hidden;width:72px}.util i{display:block;height:100%}.util.lo i{background:#c62828}.util.mid i{background:#c9a400}.util.hi i{background:#1a7f37}.utilt{display:block;font-size:10.5px;color:var(--ink-3);font-weight:400;text-transform:none;letter-spacing:0;margin-top:2px}table.schedgrid.dispatch td.now{background:color-mix(in srgb,var(--accent) 8%,transparent)}[data-slot].over{outline:2px dashed var(--accent);outline-offset:-2px;background:var(--accent-bg,#e9eefc)}.sch[draggable=true]{cursor:grab}.sch .acts{position:absolute;top:2px;right:2px;display:none;gap:2px}.sch:hover .acts{display:inline-flex}.sch .acts form{display:inline}.sch .acts .iconbtn.x{padding:0 4px;min-width:0;height:auto;line-height:1.3;font-size:12px}
[data-slot]{cursor:copy}.sch.outlook{background:var(--surface-3,#eceef3);border-style:dashed;color:var(--ink-2,#4a5260)}[data-slot]:hover{background:var(--accent-bg,#e9eefc)}
#slotdlg::backdrop,#whodlg::backdrop{background:rgb(0 0 0/.35)}
.dlghead{display:flex;align-items:center;justify-content:space-between;margin:0 0 8px}
.ticks{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:4px 12px;max-height:50vh;overflow:auto;padding:4px 0}
.ticks .tick{display:flex;align-items:center;gap:8px;padding:4px 6px;border-radius:var(--r-sm);font-weight:500} .ticks .tick:hover{background:var(--surface-3)}
.ticks .tick input{width:auto;margin:0}
:root{color-scheme:light dark;
  --canvas:#dfe5f1; --surface:#f3f6fc; --surface-2:#eaeff8; --surface-3:#dde4f1;
  --ink:#121726; --ink-2:#465068; --ink-3:#6e7891; --line:#cfd7e6; --line-2:#b9c3d8;
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
/* Part 80 (13 Oct 2026): a keyboard user jumps past the nav; a screen reader is told what an icon button does. */
.skip{position:absolute;left:-9999px;top:8px;z-index:1000;padding:8px 14px;border-radius:999px;background:var(--accent);color:#fff;font-weight:600}
.skip:focus{left:8px;outline:2px solid var(--ring);outline-offset:2px}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
main:focus{outline:none}
::selection{background:var(--accent-bg)}
h1{font-size:22px;font-weight:600;letter-spacing:-.4px;margin:0 0 4px;line-height:1.25}
h3{font-size:13px;font-weight:600;letter-spacing:.2px;color:var(--ink-2);text-transform:uppercase;margin:0 0 10px}
.sub{color:var(--ink-2);margin:0 0 18px}
/* Dada, 3 Oct 2026: "make the layout bigger so it fits the width of screen".
   A ward PC is 1920 wide and the desk was stopping at 1320, which left a third
   of the screen empty beside a ticket that wanted the room. It now uses what is
   there, with a gutter so nothing touches the edge, and still centres on the
   very wide screens where a line of text would otherwise run too far to read. */
main{max-width:min(2200px,100% - 40px);margin:0 auto;padding:22px 0}
footer{max-width:min(2200px,100% - 40px);margin:0 auto;padding:8px 0 36px;color:var(--ink-3);font-size:12px}
@media (max-width:760px){main,footer{max-width:100%;padding-left:14px;padding-right:14px}}

/* ---- header: sticky, frosted, one accent ------------------------------ */
header.top{position:sticky;top:0;z-index:20;height:var(--hdr);display:flex;align-items:center;gap:6px;
  padding:0 16px;background:var(--glass);border-bottom:1px solid var(--line);
  -webkit-backdrop-filter:saturate(160%) blur(14px);backdrop-filter:saturate(160%) blur(14px)}
header.top .brand{display:inline-flex;align-items:center;gap:8px;font-weight:650;letter-spacing:-.2px;color:var(--ink);margin-right:10px}
header.top .brand i{width:22px;height:22px;border-radius:7px;display:inline-block;
  background:linear-gradient(135deg,var(--accent),#7b93ff 60%,#9ad0ff);box-shadow:inset 0 0 0 1px rgb(255 255 255/.25)}
header.top nav{display:flex;gap:2px;overflow-x:auto;scrollbar-width:none;flex:1;min-width:0}
header.top nav.mega{overflow:visible;align-items:center}
header.top nav .grp{position:relative;display:inline-flex}
header.top nav button.top{position:relative;color:var(--ink-2);padding:6px 10px;border-radius:var(--r);white-space:nowrap;font-weight:500;font:inherit;font-weight:500;background:none;border:0;cursor:pointer;display:inline-flex;align-items:center;line-height:1.3}
header.top nav button.top:hover,header.top nav .grp.open button.top{color:var(--ink);background:var(--surface-3)}
header.top nav button.top.on{color:var(--ink)} header.top nav button.top.on::after{content:"";position:absolute;left:10px;right:10px;bottom:-1px;height:2px;border-radius:2px;background:var(--accent)}
header.top nav button.top .ic{width:15px;height:15px;margin-right:6px;vertical-align:-3px;opacity:.8} header.top nav button.top .ic.chev{width:12px;height:12px;margin:0 0 0 4px;opacity:.6}
header.top nav .panel{display:none;position:absolute;top:calc(100% + 8px);left:0;min-width:270px;padding:6px;z-index:40;background:var(--card);border:1px solid var(--line);border-radius:var(--r);box-shadow:0 14px 40px rgb(10 12 18/.18)}
header.top nav .grp:hover .panel,header.top nav .grp.open .panel,header.top nav .grp:focus-within .panel{display:grid}
header.top nav .panel a{display:grid;grid-template-columns:18px 1fr;column-gap:10px;align-items:center;padding:8px 10px;border-radius:var(--r-sm);color:var(--ink);white-space:nowrap;font-weight:500}
header.top nav .panel a .ic{width:16px;height:16px;opacity:.8;grid-column:1;grid-row:1/3;margin:0} header.top nav .panel a b{font-weight:600;grid-column:2;grid-row:1;line-height:1.3}
header.top nav .panel a .why{grid-column:2;grid-row:2;font-size:12px;color:var(--ink-3);margin:0;font-weight:400;line-height:1.3;display:block}
header.top nav .panel a:hover{background:var(--surface-3);text-decoration:none} header.top nav .panel a.on{background:color-mix(in srgb,var(--accent) 10%,transparent)}
header.top nav .panel.wide{grid-template-columns:repeat(2,minmax(220px,max-content));gap:2px 10px;padding:8px}
header.top nav .panel a i.mm{font-style:normal;font-size:10.5px;letter-spacing:.04em;font-variant-numeric:tabular-nums;color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:0 4px;margin-left:6px}
header.top nav .panel.wide3{grid-template-columns:repeat(3,minmax(200px,max-content));gap:2px 10px;padding:8px}
/* The open panel stays while the mouse crosses from the heading into it, and goes only when the mouse leaves the whole menu (Dada, 14 Oct 2026). */
header.top nav .panel::before{content:"";position:absolute;left:0;right:0;top:-12px;height:12px}
header.top nav .grp.hov .panel{display:grid}
header.top nav .grp.on>button.top::after{content:"";position:absolute;left:10px;right:10px;bottom:-1px;height:2px;border-radius:2px;background:var(--accent)}
header.top nav .grp.all{display:none}header.top nav .panel .col{display:flex;flex-direction:column;gap:2px}header.top nav .panel .modname{font-size:11.5px;text-transform:uppercase;letter-spacing:.4px;color:var(--ink-3);padding:10px 10px 4px;display:flex;align-items:center;gap:6px}header.top nav .panel .modname .ic{width:14px;height:14px;opacity:.7}@media (max-width:720px){header.top{padding:0 10px;gap:2px}header.top .brand{margin-right:4px}header.top .brand span{display:none}header.top nav.mega{overflow:visible;gap:0}header.top nav.mega.more{-webkit-mask-image:none;mask-image:none}header.top nav.mega>.grp:not(.all),header.top nav.mega>a.top,header.top nav.mega>a.newbtn{display:none}header.top nav .grp.all{display:inline-flex}header.top nav .grp.all .lbl{display:inline}header.top nav .grp{position:static}header.top nav .panel,header.top nav .panel.full{display:none;position:absolute;left:10px;right:10px;top:calc(100% + 4px);grid-template-columns:1fr;width:auto;min-width:0;max-height:calc(100vh - 70px);overflow:auto;padding:4px 6px 10px}header.top nav .grp.open .panel.full,header.top nav .grp:focus-within .panel.full{display:grid}}
.dispatchwrap>.card{min-width:0} .dispatchwrap .schedwrap{max-height:calc(100vh - 330px);min-height:220px;overflow:auto;position:relative}
table.schedgrid.dispatch thead th{position:sticky;top:0;background:var(--card);z-index:4} table.schedgrid.dispatch thead th:first-child{left:0;z-index:6}
table.schedgrid.dispatch th.who{position:sticky;left:0;background:var(--card);z-index:5;width:132px;max-width:132px}
table.schedgrid thead th.whoh{width:132px}
header.top nav::-webkit-scrollbar{display:none}
/* The menu never runs under the name and sign-out (Dada, 1 Oct): it tightens on
   narrower screens, drops its icons, and what still does not fit scrolls, with a
   fade at the edge so nothing looks cut off. */
@media (max-width:1700px){header.top nav a{padding:6px 7px;font-size:13.5px}
  /* nine modules since Configurations got its own (7 Oct 2026): below a wide screen the words stay
     and their small icons and chevrons go, so the bar never runs under the name beside it */
  header.top nav.mega>.grp:not(.all)>button.top{padding:6px 7px;font-size:13.5px}
  header.top nav.mega>.grp:not(.all)>button.top .ic,header.top nav.mega>a.top:not(.newbtn) .ic{display:none}}
/* narrower still (a 1280 ward PC): the module you are in keeps its word, the others are their icon, named on hover */
@media (min-width:721px) and (max-width:1360px){
  header.top nav.mega>.grp:not(.all):not(.on)>button.top .lbl,header.top nav.mega>a.top:not(.newbtn):not(.on) .lbl{display:none}
  header.top nav.mega>.grp:not(.all):not(.on)>button.top .ic:not(.chev),header.top nav.mega>a.top:not(.newbtn):not(.on) .ic{display:inline-block;margin-right:0}}
@media (max-width:1000px){header.top nav a.newbtn svg.ic{display:none}}
header.top nav.more{-webkit-mask-image:linear-gradient(to right,#000 calc(100% - 28px),transparent);
  mask-image:linear-gradient(to right,#000 calc(100% - 28px),transparent)}
header.top nav a{position:relative;color:var(--ink-2);padding:6px 10px;border-radius:var(--r);white-space:nowrap;font-weight:500;
  transition:color var(--fast) var(--ease),background var(--fast) var(--ease)}
header.top nav a:hover{color:var(--ink);background:var(--surface-3);text-decoration:none}
header.top nav a.on{color:var(--ink)}
header.top nav a.on::after{content:"";position:absolute;left:10px;right:10px;bottom:-1px;height:2px;border-radius:2px;background:var(--accent)}
header.top .newbtn{background:var(--accent);color:var(--on-accent);padding:6px 12px;border-radius:var(--r);font-weight:600;
  margin-left:6px;white-space:nowrap;transition:background var(--fast) var(--ease),transform var(--fast) var(--ease)}
header.top .newbtn:hover{background:var(--accent-2);text-decoration:none;transform:translateY(-1px)}
header.top .who{margin-left:12px;flex:0 0 auto;display:inline-flex;align-items:center;gap:10px;color:var(--ink-3);font-size:12px;white-space:nowrap}
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
[data-density=compact] table.grid td.sum .last{display:none}.came-inline{display:none}[data-density=compact] table.grid td.sum .came-inline{display:inline-flex;vertical-align:middle;margin-left:6px}[data-density=compact] table.grid td.sum .came-inline .pill{font-size:11px;padding:0 7px;line-height:18px}
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
/* a note as it was written: paragraphs, lists, a heading, a quote. The words are plain text in the database;
   only the reading of them is rendered, and nothing a person types can become a tag (see rich()). */
.rtx{font-size:var(--note-size,14.5px);line-height:1.55} .rtx p{margin:0 0 10px} .rtx p:last-child{margin-bottom:0}
.rtx ul,.rtx ol{margin:0 0 10px;padding-left:22px} .rtx li{margin:0 0 3px}
.rtx .rh{font-weight:650;margin:12px 0 4px;font-size:1.03em} .rtx .rh:first-child{margin-top:0}
.rtx .rq{margin:0 0 10px;padding:2px 0 2px 10px;border-left:3px solid var(--line-2);color:var(--ink-2)}
.rtx code{font-family:var(--mono);font-size:.92em;background:var(--surface-3);border-radius:4px;padding:1px 4px}
.rtx a{word-break:break-word}
iframe.mail{display:block;width:100%;border:0;margin:0;background:transparent;color-scheme:light dark;overflow:hidden}
:root[data-text=s]{--note-size:13px} :root[data-text=l]{--note-size:16.5px}
/* The editor's own toolbar, and the preview beside it. */
/* Dada, 3 Oct 2026: "it should also have one save button for all". The fields
   already save together -- they are one form -- but its Save sits at the foot
   of a long card, out of sight exactly while the dropdowns at the top are being
   used. So the moment anything in that form changes, a bar comes up and stays
   reachable, saying how many changes are waiting. It submits the same form and
   adds no second road to saving. */
.savebar{position:fixed;left:50%;transform:translate(-50%,120%);bottom:18px;z-index:60;
  display:flex;align-items:center;gap:12px;padding:9px 12px 9px 16px;border-radius:999px;
  border:1px solid var(--line-2);background:var(--surface);color:var(--ink);
  box-shadow:0 8px 30px rgba(0,0,0,.18);transition:transform .18s ease;max-width:calc(100% - 28px)}
.savebar.up{transform:translate(-50%,0)}
.savebar b{font-size:13px;font-weight:600;white-space:nowrap}
.savebar .muted{font-size:12.5px}
.savebar button{height:auto;padding:6px 14px;font-size:13px}
@media (prefers-reduced-motion:reduce){.savebar{transition:none}}
@media (max-width:620px){.savebar{left:14px;right:14px;transform:translateY(120%);max-width:none}
  .savebar.up{transform:translateY(0)}}
/* The stopwatch on a ticket (065). Deliberately unlike the SLA badges: this is
   one person's own time, not the hospital's clock, and the two must never be
   read as the same thing. */
.swatch{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:0 0 10px;padding:8px 10px;
  border:1px solid var(--line);border-radius:var(--r-sm);background:var(--surface-2)}
.swatch .tick{font-family:var(--mono);font-size:17px;font-variant-numeric:tabular-nums;letter-spacing:.5px}
.swatch.live{border-color:var(--accent)} .swatch.live .tick{color:var(--accent)}
.swatch.paused .tick{color:var(--ink-3)}
.swatch.done{border-color:var(--line-2)}
.swatch form{display:inline;margin:0} .swatch .muted{font-size:12.5px}
.swatch button.small,.swatch .small{padding:3px 10px;font-size:12.5px;height:auto;min-width:0}
@media (prefers-reduced-motion:no-preference){.swatch.live .tick{animation:swtick 2s ease-in-out infinite}}
@keyframes swtick{0%,100%{opacity:1}50%{opacity:.72}}
/* One frame around the toolbar and the box, as a Teams composer has: the
   border and the focus ring are the whole thing's, not the box's. */
.composer{border:1px solid var(--line-2);border-radius:var(--r);background:var(--surface);overflow:hidden;
  transition:border-color .12s,box-shadow .12s}
.composer:focus-within{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-bg,#e9eefc)}
.composer .edbar{margin:0;padding:5px 7px;border-bottom:1px solid var(--line);background:var(--surface-2)}
.composer .editor{border:0;border-radius:0;box-shadow:none;max-height:60vh}
.composer .editor:focus{border:0;box-shadow:none}
.composer textarea[name=body]{border:0;border-radius:0;min-height:120px;resize:vertical}
.composer textarea[name=body]:focus{box-shadow:none}
.edbar .g{display:flex;gap:2px;align-items:center}
.edbar{display:flex;flex-wrap:wrap;gap:2px;margin:0 0 6px;align-items:center}
.edbar .iconbtn{width:30px;height:28px;font-size:13px} .edbar .sep{width:1px;height:18px;background:var(--line);margin:0 5px}
.edbar .grow{flex:1} .edbar .tab{padding:3px 10px;border-radius:var(--r-sm);font-size:12.5px;font-weight:600;color:var(--ink-3);background:none;border:0;cursor:pointer}
.edbar .tab.on{background:var(--surface-3);color:var(--ink)} .edbar .iconbtn[disabled]{opacity:.35;cursor:default}
/* The note box itself: a page a person writes on, not a form field. */
.editor{min-height:120px;max-height:420px;overflow:auto;border:1px solid var(--line-2);border-radius:var(--r);
  padding:10px 12px;background:var(--surface);color:var(--ink);font-size:14.5px;line-height:1.55;outline:none}
.editor:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-bg,#e9eefc)}
/* "is-empty", not "empty": .empty is the desk's empty-state box, whose inbox
   picture and padding were drawn inside a blank note box (Dada's screenshot,
   6 Oct 2026). */
.editor.is-empty::before{content:attr(data-ph);color:var(--ink-3);pointer-events:none;display:block}
.editor img,.rtx img{max-width:100%;height:auto;border-radius:6px;vertical-align:middle}
.editor h3,.rtx h3{font-size:1.15em;margin:6px 0} .editor h4,.rtx h4{font-size:1.02em;margin:6px 0}
.editor pre,.rtx pre{font-family:var(--mono);font-size:.9em;background:var(--surface-3);border-radius:6px;padding:8px 10px;white-space:pre-wrap}
.rtx .tc-red{color:#c62828}.rtx .tc-orange{color:#c25e00}.rtx .tc-green{color:#1a7f37}.rtx .tc-blue{color:#2f52c4}.rtx .tc-purple{color:#7b3fbf}.rtx .tc-grey{color:#6b7280}
:root[data-theme=dark] .rtx .tc-red{color:#ff8a80}:root[data-theme=dark] .rtx .tc-orange{color:#ffb15c}:root[data-theme=dark] .rtx .tc-green{color:#6fdc8c}
:root[data-theme=dark] .rtx .tc-blue{color:#8fb0ff}:root[data-theme=dark] .rtx .tc-purple{color:#c9a2ff}:root[data-theme=dark] .rtx .tc-grey{color:#a3acba}
.rtx .fs-s{font-size:.85em}.rtx .fs-l{font-size:1.25em}.rtx .fs-xl{font-size:1.5em}
.rtx mark{color:inherit;border-radius:3px;padding:0 2px}.rtx .hl-yellow{background:#fff3a3}.rtx .hl-green{background:#c9f2d4}.rtx .hl-blue{background:#cfe3ff}.rtx .hl-pink{background:#ffd6e8}
:root[data-theme=dark] .rtx mark{color:#14171d}
.edbar .pop{position:relative} .edbar .pop>summary{list-style:none} .edbar .pop>summary::-webkit-details-marker{display:none}
.edbar .pop>.menu{position:absolute;z-index:30;top:32px;left:0;background:var(--surface);border:1px solid var(--line-2);border-radius:10px;
  box-shadow:0 12px 32px rgba(0,0,0,.18);padding:6px;display:grid;gap:4px;min-width:150px}
.edbar .pop>.menu.sw{grid-template-columns:repeat(6,26px);min-width:0} .edbar .pop>.menu.emo{grid-template-columns:repeat(8,30px);min-width:0}
.edbar .pop>.menu button{border:0;background:none;color:var(--ink);text-align:left;padding:5px 8px;border-radius:6px;cursor:pointer;font:inherit;font-size:13px}
.edbar .pop>.menu button:hover{background:var(--surface-3)} .edbar .pop>.menu.emo button{font-size:18px;padding:2px;text-align:center}
.edbar .swatch{width:22px;height:22px;border-radius:50%;border:2px solid var(--surface);box-shadow:0 0 0 1px var(--line-2);padding:0!important}
.edbar .iconbtn .aa{font-weight:800;border-bottom:3px solid #c62828;line-height:1;padding:0 2px}
.edbar .iconbtn .hl{background:#fff3a3;color:#14171d;border-radius:3px;padding:0 3px;font-weight:700}
.edhint{font-size:11.5px;color:var(--ink-3);padding:4px 10px;border-top:1px solid var(--line);background:var(--surface-2)}
.composer.drop{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-bg)}
.editor p{margin:0 0 10px} .editor p:last-child{margin-bottom:0}
.editor ul,.editor ol{margin:0 0 10px;padding-left:22px} .editor li{margin:0 0 3px}
.editor blockquote{margin:0 0 10px;padding:2px 0 2px 10px;border-left:3px solid var(--line-2);color:var(--ink-2)}
.editor code{font-family:var(--mono);font-size:.92em;background:var(--surface-3);border-radius:4px;padding:1px 4px}
.editor a{color:var(--accent)}
/* Dada, 2 Oct 2026: "the pods should remain fixed and just add an edit button to move the pods similar to
   connectwise". At rest a card sits still and its words select; Edit layout turns the handles on. */
:root.layedit .pods .card[data-pod]{outline:1px dashed var(--line-2);outline-offset:3px}
:root:not(.layedit) .pods .card[data-pod] h3{cursor:default}
.layedit-on{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:60;background:var(--accent);color:#fff;
  padding:8px 14px;border-radius:999px;box-shadow:var(--shadow);font-size:13px;display:flex;align-items:center;gap:10px}
.layedit-on button{background:#fff;color:#111;border:0;border-radius:999px;padding:3px 12px;cursor:pointer;font-weight:600}
.pods .card[data-pod] h3{display:flex;align-items:center;gap:0;padding-right:56px;cursor:grab;user-select:none}
/* Chrome's own stylesheet gives [draggable=true] user-select:none, so a draggable card made every word in it
   unselectable: a technician could not copy a ward's message out of a note (MEASURED 2 Oct 2026). The card is
   draggable only while the pointer is down on its heading (see the pods script), and its words say so. */
.pods .card[data-pod],.pods .card[data-pod] .podbody,.note,.note div{user-select:text;-webkit-user-select:text}
.note .h .copy{opacity:0;transition:opacity var(--fast) var(--ease)} .note:hover .copy,.note:focus-within .copy{opacity:1}
.note .h .copy.done{opacity:1;color:var(--ok,#1a7f37)}
.pods .card[data-pod] h3:active{cursor:grabbing}
.pods .card[data-pod] .podctl{position:absolute;right:8px;top:10px;display:none;gap:2px;opacity:0;transition:opacity var(--fast) var(--ease)}
:root.layedit .pods .card[data-pod] .podctl{display:inline-flex;opacity:1}
.pods .card[data-pod] .podctl .iconbtn{width:26px;height:26px}
.pods .card[data-pod] .podctl .ic{width:14px;height:14px}
.pods .card.collapsed>*:not(h3):not(.podctl){display:none}
.pods .card.collapsed{padding-bottom:12px} .pods .card.collapsed h3{margin-bottom:0}
.pods .card.collapsed .podctl .fold .ic{transform:rotate(-90deg)}
.pods .card.dragging{opacity:.5} .pods .card.over{box-shadow:0 -2px 0 0 var(--accent)}
.timefields{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px 10px;margin-top:8px}
.timefields.compact{grid-template-columns:repeat(3,minmax(0,1fr))} @container (min-width:640px){.timefields{grid-template-columns:repeat(5,minmax(0,1fr))}}
.timefields label{display:block} details.timeblock{margin-top:10px} details.timeblock>summary{cursor:pointer;font-weight:600;color:var(--ink-2);display:flex;align-items:center;gap:6px}
table.compact td,table.compact th{padding:4px 8px;font-size:12px} td.num{text-align:right;font-variant-numeric:tabular-nums}
td.center{text-align:center} th.colhead label{font-weight:600;white-space:nowrap} th.colhead input,td.center input{width:auto}
.pods{min-height:56px;border-radius:var(--r-lg);display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:0 14px;align-content:start}
.pods.over-col{outline:2px dashed var(--accent);outline-offset:4px}
/* a pod's size (Dada, 1 Oct 2026: "size the pods like small half medium full"): how much of its column it takes */
.pods>.card[data-pod]{grid-column:span 12;min-width:0} .pods>.card.sz-s{grid-column:span 4} .pods>.card.sz-half{grid-column:span 6} .pods>.card.sz-m{grid-column:span 8}
.pods>.podreset,.pods::after{grid-column:1/-1}
@media (max-width:900px){.pods>.card[data-pod]{grid-column:span 12}}
/* words stay readable whatever the width: a note never runs past a comfortable line */
.stream li>div:first-child,.card .prose,.card p.why,.card .note-body{max-width:80ch}
.pods .card[data-pod] h3{padding-right:196px}
/* a card's body: drag its bottom edge for the height you want (the reference PSA's pods scroll inside); hidden cards are the Pod configuration's */
.pods .card[data-pod]>.podbody{resize:vertical;overflow:auto;min-height:48px;padding-bottom:6px}
.pods .card.hidden{display:none}
.podlist li{display:flex;align-items:center;gap:8px;padding:4px 6px;border-radius:var(--r-sm)} .podlist li:hover{background:var(--surface-3)}
.podlist li .nm{flex:1} .podlist li .iconbtn{width:24px;height:24px} .podlist li .iconbtn .ic{width:13px;height:13px}
#poddlg::backdrop{background:rgb(0 0 0/.35)} #poddlg h4{margin:0 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:.3px;color:var(--ink-3)}
.pods:empty::after,.pods.blank::after{content:"Drop a card here";display:block;color:var(--ink-3);font-size:12px;text-align:center;padding:14px;border:1px dashed var(--line-2);border-radius:var(--r-lg)}
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
.slot.away{background:var(--warn-bg);color:var(--warn)}
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
.tablewrap{overflow:visible;max-width:100%}
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
.pdot{display:inline-block;width:9px;height:9px;border-radius:50%;background:#8a939d;vertical-align:middle;flex:0 0 auto}
.pdot.p-online{background:#1a7f37}.pdot.p-busy{background:#c62828}.pdot.p-away{background:#c9a400}
.twho{display:flex;flex-wrap:wrap;gap:4px 14px;padding:2px 0 6px;font-size:12.5px}.twho .tp{white-space:nowrap}
.tme{display:flex;flex-wrap:wrap;gap:4px;align-items:center;margin:0 0 8px}.tme button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.deskon{margin:4px 0 10px;font-size:13px;display:flex;gap:6px;align-items:center}
.chattyping{min-height:18px;font-size:12px;color:var(--ink-3);font-style:italic;padding:2px 6px}
.chatstays{margin:8px 0 0}
.plink{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px;margin:6px 0 2px} .plink input{flex:1 1 100%;font-size:12px} .plink input[hidden]{display:none}
.badge{display:inline-block;min-width:28px;text-align:center;border-radius:6px;padding:1px 6px;font-weight:700;font-size:11.5px;color:#fff;letter-spacing:.2px}
.badge.P1{background:#c62828}.badge.P2{background:#b26a00}.badge.P3{background:var(--accent)}.badge.P4{background:#6b7785}
.sla3{display:inline-flex;flex-wrap:wrap;gap:3px;white-space:nowrap}
table.grid td.sla{white-space:normal;min-width:92px;max-width:170px}
table.grid td.wrap{overflow-wrap:anywhere}
table.grid.cards td.muted.wrap{max-width:200px}
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
/* 9 Oct 2026: where a ticket came from, one colour each (Dada: "nicely colored designed badges"). The words
   stay in the page's ink, so they read in every theme; the colour is the tint, the edge and the icon. */
.pill.came{display:inline-flex;align-items:center;gap:4px;font-weight:600;color:var(--ink);
  background:color-mix(in srgb,var(--c) 16%,var(--surface));border:1px solid color-mix(in srgb,var(--c) 55%,transparent)}
.pill.came .ic{width:12px;height:12px;margin:0;opacity:1;color:var(--c)}
.came-chat{--c:#14b8a6}.came-portal{--c:#8b5cf6}.came-email{--c:#f59e0b}.came-desk{--c:#64748b}.came-other{--c:#9ca3af}
/* 080: the Configurations list (13 Oct 2026): the column chooser */
details.colpick{position:relative}details.colpick summary{list-style:none;cursor:pointer}details.colpick summary::-webkit-details-marker{display:none}
details.colpick .colmenu{position:absolute;right:0;top:calc(100% + 6px);z-index:30;min-width:200px;padding:10px 12px;background:var(--card);border:1px solid var(--line);border-radius:10px;box-shadow:0 10px 28px rgba(0,0,0,.25);display:flex;flex-direction:column;gap:4px}
details.colpick .colopt{display:flex;align-items:center;gap:6px;font-size:13px;white-space:nowrap}details.colpick .colmenu button{margin-top:6px;align-self:flex-start}
table.cfglist td,table.cfglist th{white-space:nowrap}table.cfglist td:nth-child(n+1){max-width:220px;overflow:hidden;text-overflow:ellipsis}
.hdr .acts .btn{margin-left:4px}
/* 080: the Tasks grid (13 Oct 2026) */
table.tgrid td.handle{width:18px;cursor:grab;color:var(--ink-3)}table.tgrid tr.dragging{opacity:.4}
table.tgrid td input{width:100%;min-width:80px;padding:3px 6px;font-size:12.5px;border:1px solid transparent;background:transparent}
table.tgrid td input:hover,table.tgrid td input:focus{border-color:var(--line-2);background:var(--surface)}
table.tgrid tr.tdone td input[name=text]{text-decoration:line-through;color:var(--ink-3)}
table.tgrid td.tacts{white-space:nowrap}table.tgrid td.tacts form{display:inline}table.tgrid .tick{font-size:15px;line-height:1}
table.tgrid details.tsched summary{display:inline-block;cursor:pointer;list-style:none}table.tgrid details.tsched form{margin-top:6px}
table.tgrid details.tsched form>*{margin:2px 0}.ttabs .tcount{font-size:11px;padding:0 6px;border-radius:999px;background:var(--surface-2);color:var(--ink-2)}
/* 080: the Procurement grids (13 Oct 2026): a cell edited in place, the bulk bar */
table.pgrid td.ecell input{width:100%;min-width:90px;padding:3px 6px;font-size:12.5px;border:1px solid transparent;background:transparent}
table.pgrid td.ecell input:hover,table.pgrid td.ecell input:focus{border-color:var(--line-2);background:var(--surface)}
table.pgrid td.ecell input.edited{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 10%,var(--surface))}
table.pgrid td.ecell select{width:100%;min-width:110px;padding:3px 6px;font-size:12.5px;border:1px solid transparent;background:transparent}
table.pgrid td.ecell select:hover,table.pgrid td.ecell select:focus{border-color:var(--line-2);background:var(--surface)}
table.pgrid td.ecell select.edited{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 10%,var(--surface))}
form[data-record] dd>select,form[data-record] dd>input{width:100%;max-width:440px}
form[data-record] dd>select[data-was]:not([data-was='']),form[data-record] dd>input[data-was]{border-color:var(--line)}
dialog.review{position:fixed;inset:0;margin:auto;width:min(760px,94vw);max-height:90vh;overflow:auto;padding:20px 22px;border:1px solid var(--line-2);border-radius:16px;background:var(--card);color:var(--ink);box-shadow:0 24px 60px rgb(10 12 18/.35)}
dialog.review:not([open]){display:none}
dialog.review::backdrop{background:rgb(10 12 18/.4);-webkit-backdrop-filter:blur(2px);backdrop-filter:blur(2px)}
dialog.review h2{margin:0 0 10px;display:flex;align-items:center;gap:8px;font-size:18px}
dialog.review .tablewrap table{width:auto;min-width:min(100%,520px)}
dialog.review table td.arrow{color:var(--ink-3);text-align:center;padding:0 10px}
dialog.review .acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
dialog.review .acts form{display:inline}
.home2{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:start}@media (max-width:900px){.home2{grid-template-columns:1fr}}
.bar{height:6px;border-radius:3px;background:var(--line);overflow:hidden;min-width:60px}.bar i{display:block;height:100%;background:var(--accent);border-radius:3px}
.bulkbar{background:var(--surface-2);border-radius:var(--r);padding:8px 10px}
.pill.dept{display:inline-flex;align-items:center;gap:4px;font-weight:600;color:var(--ink);--c:#0ea5e9;
  background:color-mix(in srgb,var(--c) 14%,var(--surface));border:1px solid color-mix(in srgb,var(--c) 50%,transparent)}
.pill.dept .ic{width:12px;height:12px;margin:0;opacity:1;color:var(--c)}
a.pill.came:hover{text-decoration:none;background:color-mix(in srgb,var(--c) 28%,var(--surface))}
/* 078: the portal's tiles (Dada, 9 Oct 2026). Not .tile, which is the desk's figure tiles. */
.helptiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px;margin:0 0 12px}
.htile{display:flex;gap:12px;align-items:flex-start;background:var(--surface);border:1px solid var(--line);border-radius:var(--r-lg);padding:14px 16px;color:inherit;min-height:72px;transition:border-color .15s,background .15s,transform .15s}
.htile:hover,.htile:focus-visible{border-color:var(--accent);background:var(--surface-2);transform:translateY(-1px);text-decoration:none}
.htile .ic{width:26px;height:26px;flex:0 0 26px;color:var(--accent)} .htile b{display:block;font-size:14px;color:var(--ink)}
.htile span{display:block;color:var(--ink-3);font-size:12px;margin-top:3px;line-height:1.35} .htile.else{border-style:dashed}
@media (prefers-reduced-motion:reduce){.htile{transition:none}.htile:hover{transform:none}}
fieldset.q{border:none;padding:0;margin:0 0 12px} fieldset.q legend{font-size:13px;font-weight:600;color:var(--muted);margin-bottom:6px;padding:0}
.choices{display:flex;flex-wrap:wrap;gap:8px 22px}
.choices label{display:inline-flex;align-items:center;gap:6px;font-weight:400;color:var(--ink);font-size:13px;letter-spacing:0;cursor:pointer}
.choices input[type=radio]{margin:0;width:auto;flex:0 0 auto}
.schedwrap{overflow-x:auto;max-width:100%} .schedbar{justify-content:flex-start;gap:8px;margin-bottom:10px;flex-wrap:wrap}
table.schedgrid{width:100%;table-layout:fixed;border-collapse:collapse;min-width:760px}
table.schedgrid thead th{font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:var(--ink-3);text-align:left;padding:6px 4px;border-bottom:1px solid var(--line)}
table.schedgrid thead th:first-child{width:90px}
table.schedgrid th.who{white-space:nowrap;vertical-align:top;text-align:left;font-size:12px;color:var(--ink-2);padding:8px 4px;overflow:hidden;text-overflow:ellipsis}
table.schedgrid td{vertical-align:top;padding:4px;border-bottom:1px solid var(--line);overflow:hidden}
table.schedgrid .today{background:color-mix(in srgb,var(--accent) 6%,transparent)}
.sch{display:block;position:relative;font-family:inherit;font-size:12px;line-height:1.35;padding:4px 6px;overflow-wrap:anywhere;margin:0 0 4px;border-radius:var(--r-sm);border:1px solid var(--line-2);background:var(--surface);color:var(--ink);text-decoration:none}
.sch.visit{border-left:3px solid var(--accent)} .sch.visit:hover{background:var(--surface-2);text-decoration:none}
.sch.tentative{border-style:dashed;border-left-style:solid} .sch.done{opacity:.6;text-decoration:line-through}
.sch.block{background:var(--surface-2);color:var(--ink-2);padding-right:20px} .sch.time_off{border-left:3px solid var(--warn)} .sch.meeting,.sch.activity{border-left:3px solid var(--ink-3)}
.sch form.inline{position:absolute;top:2px;right:2px} .sch .iconbtn.x{padding:0 4px;min-width:0;height:auto;line-height:1}
.weekrow{display:flex;flex-wrap:wrap;gap:8px 16px;margin-top:10px} .weekrow .day{white-space:nowrap}
.weekrow .daylbl{display:inline-block;width:30px;color:var(--ink-2);font-size:12px;font-weight:600}
.weekrow input{width:64px;display:inline-block;padding:4px 6px}
details.tip{display:inline-block;position:relative;vertical-align:middle;margin-left:4px}
details.tip>summary{list-style:none;cursor:help;display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border-radius:50%;
  border:1px solid var(--line-2);background:var(--surface-2);color:var(--ink-2);font-size:12px;font-weight:700;line-height:1}
details.tip>summary::-webkit-details-marker{display:none}
details.tip>summary:hover,details.tip[open]>summary{background:var(--accent);border-color:var(--accent);color:var(--on-accent)}
details.tip>.tipbody{position:absolute;z-index:30;left:0;top:24px;width:min(360px,calc(100vw - 48px));padding:12px 14px;border:1px solid var(--line-2);
  border-radius:var(--r-lg);background:var(--surface);color:var(--ink);box-shadow:var(--shadow);font-size:13px;font-weight:400;line-height:1.5;letter-spacing:0}
details.tip>.tipbody p{margin:6px 0 0} details.tip>.tipbody b{color:var(--ink)}
details.tip>.tipbody .sample{padding:8px 10px;border-radius:var(--r);background:var(--surface-2);color:var(--ink-2);font-style:italic}
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
label .req{color:var(--bad,#c0392b);margin-left:2px;font-weight:700}
details.multipick{border:1px solid var(--line);border-radius:var(--r-sm,6px);background:var(--surface);margin-bottom:8px} details.multipick>summary{cursor:pointer;padding:6px 10px;list-style:none;font-size:13.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis} details.multipick>summary::after{content:'▾';float:right;color:var(--ink-3)} details.multipick .opts{max-height:220px;overflow:auto;padding:4px 10px 8px;border-top:1px solid var(--line)} details.multipick label.pick{display:flex;gap:6px;align-items:center;font-weight:400;color:var(--ink);margin:4px 0} details.multipick label.pick input{width:auto}
dialog.tedlg{width:min(980px,96vw);max-height:96vh;overflow:auto;padding:0;border:1px solid var(--line-2);border-radius:16px;
  resize:both;min-width:min(560px,96vw);min-height:420px;max-width:100vw}
dialog.tedlg[open]{display:flex;flex-direction:column}
dialog.tedlg .teform{flex:1;display:flex;flex-direction:column;min-height:0}
dialog.tedlg .composer{flex:1;display:flex;flex-direction:column;min-height:180px}
dialog.tedlg .composer .editor{flex:1;max-height:none;min-height:120px}
dialog.tedlg.max{width:calc(100vw - 24px)!important;height:calc(100vh - 24px)!important;max-height:none;left:12px!important;top:12px!important;margin:0}
dialog.tedlg.moved{margin:0}
.tehead[data-drag]{cursor:move;user-select:none;touch-action:none} .tehead[data-drag] button{cursor:pointer}
.tewin{display:inline-flex;gap:2px}
dialog.tedlg::backdrop{background:rgba(10,14,24,.45);backdrop-filter:blur(3px)}
dialog.tedlg .teform{padding:16px 18px} .tehead{display:flex;gap:14px;align-items:center;margin:-16px -18px 14px;padding:14px 18px;
  border-bottom:1px solid var(--line);background:linear-gradient(90deg,var(--accent-bg),transparent)}
.tehead>div:first-child{flex:1} .teclock{display:inline-flex;flex-direction:column;align-items:flex-end}
.teclock .tick{font-family:var(--mono);font-size:22px;letter-spacing:.04em;color:var(--accent)}
.temember{display:flex;gap:10px;align-items:baseline;margin-bottom:6px} .temember label{margin:0} .temember .ro{color:var(--ink);font-weight:600;background:none;border:0;padding:0}
.teflags{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:10px 0 0} .teflags label.tick{display:inline-flex;gap:5px;align-items:center;margin:0;font-weight:500;color:var(--ink)}
.teflags label.tick input{width:auto} .teflags .tesep{width:1px;height:20px;background:var(--line)} .teflags .grow{flex:1}
.tefoot{display:flex;gap:8px;align-items:center;margin:14px -18px -16px;padding:12px 18px;border-top:1px solid var(--line);background:var(--surface-2)} .tefoot .grow{flex:1}
.btn.clockbtn{display:inline-flex;gap:6px;align-items:center} .btn.clockbtn.on{background:var(--accent);color:var(--on-accent)}
.btn.clockbtn .tick{font-family:var(--mono);letter-spacing:.03em}
@media (prefers-reduced-motion:no-preference){.btn.clockbtn.on{animation:clockglow 2.4s ease-in-out infinite}}
@keyframes clockglow{0%,100%{box-shadow:0 0 0 0 color-mix(in srgb,var(--accent) 45%,transparent)}50%{box-shadow:0 0 0 6px color-mix(in srgb,var(--accent) 0%,transparent)}}
a.backbtn{display:inline-flex;align-items:center;gap:6px;font-size:13px;color:var(--ink2);text-decoration:none;margin:0 0 6px;padding:3px 10px 3px 6px;border:1px solid var(--line);border-radius:999px} a.backbtn:hover{color:var(--ink);border-color:var(--ink2)} a.backbtn .ic{width:15px;height:15px}
dialog.viewer{width:min(96vw,1200px);max-width:none;height:min(92vh,900px);max-height:none;padding:0;border:0;border-radius:var(--r);background:var(--card);color:var(--fg);overflow:hidden}
dialog.viewer:not([open]){display:none} dialog.viewer::backdrop{background:rgba(14,21,32,.85);-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px)}
@supports not ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){dialog.viewer::backdrop{background:#0E1520}}
@media (prefers-reduced-transparency:reduce){dialog.viewer::backdrop{background:#0E1520;-webkit-backdrop-filter:none;backdrop-filter:none}}
dialog.viewer{box-shadow:0 12px 32px rgba(0,0,0,.22)!important;-webkit-backdrop-filter:none!important;backdrop-filter:none!important}
dialog.viewer .vbar .iconbtn svg,dialog.viewer .vbar .ic{width:16px;height:16px}
dialog.viewer .vsize,dialog.viewer .vpos{font-size:12px;white-space:nowrap;font-variant-numeric:tabular-nums}
dialog.viewer [data-vprev][hidden],dialog.viewer [data-vnext][hidden]{display:none}
dialog.viewer .vbar{display:flex;align-items:center;gap:8px;padding:8px 12px;border-bottom:1px solid var(--line)} dialog.viewer .vbar .grow{flex:1}
dialog.viewer .vname{font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
dialog.viewer .vbody{height:calc(100% - 46px);display:flex;align-items:center;justify-content:center;background:var(--bg)}
dialog.viewer .vbody img{max-width:100%;max-height:100%;object-fit:contain} dialog.viewer .vbody iframe{width:100%;height:100%;border:0;background:#fff}
h1.sumline .sumedit{width:26px;height:26px;vertical-align:middle;opacity:.55} h1.sumline .sumedit:hover{opacity:1}
h1.sumline .sumform{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-top:4px;font-size:14px;font-weight:400} h1.sumline .sumform input{flex:1;min-width:220px;font-size:16px} h1.sumline .sumform[hidden]{display:none}
.tabs{display:flex;gap:2px;border-bottom:1px solid var(--line);margin-bottom:12px}
.tabs a{padding:7px 12px;color:var(--ink-2);border-bottom:2px solid transparent;margin-bottom:-1px;border-radius:var(--r-sm) var(--r-sm) 0 0;
  transition:color var(--fast) var(--ease),background var(--fast) var(--ease)}
.tabs a:hover{color:var(--ink);background:var(--surface-2);text-decoration:none}
.tabs a.on{color:var(--ink);border-color:var(--accent);font-weight:600}
.tabs{flex-wrap:wrap}.tabs a.order{margin-left:auto;display:inline-flex;align-items:center;gap:5px;font-size:12.5px;white-space:nowrap}
.tabs a.order .ic{width:14px;height:14px}
.rptlist li{padding:8px 0;border-top:1px solid var(--line)}.rptlist li:first-child{border-top:0}.rptlist a.rpt{display:block;color:inherit;text-decoration:none}.rptlist a.rpt:hover b{color:var(--accent);text-decoration:underline}
.rptframe{display:block;width:100%;height:75vh;min-height:420px;border:1px solid var(--line);border-radius:10px;background:var(--surface);margin-top:10px}
.stabs{display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap}
.stabs a{padding:6px 14px;border-radius:999px;background:var(--surface);border:1px solid var(--line);color:var(--ink-2);font-weight:600;
  transition:background var(--fast) var(--ease),color var(--fast) var(--ease),border-color var(--fast) var(--ease)}
.stabs a:hover{border-color:var(--line-2);color:var(--ink);text-decoration:none}
.stabs a.on{background:var(--ink);color:var(--canvas);border-color:var(--ink)}
/* The document screen (SQL01, 14 Oct 2026): a document, not a row in a spreadsheet. */
.dochead{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;flex-wrap:wrap;margin-bottom:6px}
.dochead h1{margin-bottom:4px}.dochead .sub{margin-bottom:8px}
.docbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding-top:4px}
.doc{display:flex;flex-direction:column;gap:14px}.doc>.card{margin:0}
.dochead .crumbs{margin:0 0 10px;color:var(--ink-3);font-size:12.5px}.dochead .crumbs a{color:var(--ink-2)}
/* Job 02: a breadcrumb link is a control, not text in a sentence, so it gets a 24px hit area (WCAG 2.5.8; MEASURED 15px on the document pages before) */
.crumbs a{display:inline-block;min-height:24px;line-height:24px}
.docsearch input{min-width:260px}
.mmsbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 14px}.mmsbar .state{margin-left:auto;color:var(--ink-3);font-size:12.5px}
.pickers{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px 16px;margin:0 0 14px}
.pickers label{display:block;font-size:12px;color:var(--ink-3);margin:0 0 3px}.pickers .ro{padding:8px 10px;background:var(--surface-2);border-radius:var(--r);font-size:13px;min-height:34px;box-sizing:border-box}
.pickers select,.pickers input{width:100%;box-sizing:border-box}
@media (max-width:900px){.pickers{grid-template-columns:repeat(2,minmax(0,1fr))}}@media (max-width:520px){.pickers{grid-template-columns:1fr}}
table.doclines td.ecell input{width:100%;min-width:70px;box-sizing:border-box}table.doclines td.num.ecell input{text-align:right;max-width:120px}
table.doclines tr.addrow td{background:color-mix(in srgb,var(--accent) 5%,transparent)}table.doclines tr.addrow input{width:100%;box-sizing:border-box;min-width:70px}
table.doclines tr.addnote td{color:var(--ink-3);font-size:12px;border-bottom:0}
.mmsfoot{display:flex;gap:14px 22px;align-items:center;flex-wrap:wrap;border-top:1px solid var(--line);padding-top:12px;margin-top:12px}
.mmsfoot .nums{display:flex;gap:18px;flex-wrap:wrap}.mmsfoot .tot .l{color:var(--ink-3);font-size:12.5px}.mmsfoot .tot b{font-variant-numeric:tabular-nums}
.mmsfoot .appr{color:var(--ink-2);font-size:12.5px}.mmsfoot .acts{margin-left:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap}.mmsfoot .acts .why input{min-width:220px}
.docfields label{display:block;font-size:12px;color:var(--ink-3);margin:0 0 3px}
.docfields .ro{padding:8px 10px;background:var(--surface-2);border-radius:var(--r);font-size:13px;min-height:34px;box-sizing:border-box}
.docfields select,.docfields input{width:100%;box-sizing:border-box}
table.doclines td.num,table.doclines th.num,table.doclist td.num,table.doclist th.num,.totals .n{font-variant-numeric:tabular-nums}
table.doclines tr.total td{border-top:2px solid var(--line-2)}
.totals{display:flex;gap:22px;flex-wrap:wrap}.totals>div{min-width:90px}
.totals .n{font-size:20px;font-weight:650;letter-spacing:-.3px;line-height:1.15}.totals .l{font-size:12px;color:var(--ink-3);margin-top:2px}
.path{list-style:none;display:flex;gap:0;padding:0;margin:10px 0 10px;flex-wrap:wrap;counter-reset:step}
.path li{position:relative;flex:1 1 150px;padding:22px 12px 0 0;font-size:12.5px;min-width:0}
.path li::before{content:"";position:absolute;left:0;top:3px;width:9px;height:9px;border-radius:50%;border:2px solid var(--line-2);background:var(--surface);box-sizing:content-box;z-index:1}
.path li::after{content:"";position:absolute;left:16px;right:2px;top:8px;height:2px;background:var(--line)}
.path li:last-child::after{display:none}
.path li.done::before{background:var(--ok);border-color:var(--ok)}.path li.done::after{background:var(--ok)}
.path li.now::before{background:var(--accent);border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-bg)}
.path li.bad::before{background:var(--bad);border-color:var(--bad)}
.path li b{display:block;color:var(--ink)}.path li span{display:block;color:var(--ink-3);overflow-wrap:anywhere}
.doc-approval .batch+.batch{margin-top:14px;padding-top:12px;border-top:1px solid var(--line)}
.doc-approval .arrow{color:var(--ink-3);padding:0 4px}
.code{font-size:11px;letter-spacing:.3px}
.better{display:inline-block;font-size:9.5px;letter-spacing:.6px;padding:1px 6px;border-radius:999px;background:color-mix(in srgb,var(--accent) 14%,transparent);color:var(--accent);font-weight:700;vertical-align:middle}
.banner.warn{background:color-mix(in srgb,var(--warn,#e3b341) 14%,transparent);color:var(--ink);border-color:color-mix(in srgb,var(--warn,#e3b341) 50%,transparent)}
.doclines td.onhand{white-space:nowrap}
tr[data-href]{cursor:pointer}tr[data-href]:hover td{background:var(--surface-2)}
/* The slip: what a department accepts in place of the printed form. */
.slip{max-width:860px;margin:0 auto;background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:28px 32px;color:var(--ink)}
.slip header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;border-bottom:2px solid var(--ink);padding-bottom:12px;margin-bottom:16px}
.slip .kicker{font-size:12px;letter-spacing:.6px;text-transform:uppercase;color:var(--ink-3)}
.slip h1{margin:2px 0 0;font-size:26px;letter-spacing:-.4px}.slip .stamp{text-align:right;font-size:12px;color:var(--ink-3)}.slip .stamp b{display:block;color:var(--ink);font-size:13px}
.slip dl.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px 18px;margin:0 0 18px}
.slip dl.facts div{min-width:0}.slip dt{font-size:11.5px;color:var(--ink-3);text-transform:uppercase;letter-spacing:.4px}.slip dd{margin:2px 0 0;font-size:14px}
.slip table{width:100%;border-collapse:collapse;font-size:13px}.slip th,.slip td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left}
.slip th{font-size:11.5px;color:var(--ink-3);text-transform:uppercase;letter-spacing:.4px}.slip td.num,.slip th.num{text-align:right;font-variant-numeric:tabular-nums}
.slip tr.total td{border-top:2px solid var(--ink);border-bottom:0}.slip .tot{text-align:right;margin:10px 0 0;font-size:14px}
.slip section h2{font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:var(--ink-3);margin:18px 0 6px}.slip section ul{margin:0;padding-left:18px;font-size:12.5px}
.slip .sigs{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin-top:40px}
.slip .sig{border-top:1px solid var(--ink);padding-top:6px;font-size:12px;color:var(--ink-2)}
.slip footer{max-width:none;margin:22px 0 0;padding:10px 0 0;border-top:1px solid var(--line);font-size:11.5px;color:var(--ink-3)}
@media (max-width:640px){.slip{padding:18px 16px}.slip .sigs{grid-template-columns:1fr 1fr}}
/* Printing a document or its slip (and only those pages): the shell goes, black on white. */
@media print{body:has(.slip,.doc) :is(header.top,footer,.skip,.noprint,#nprog,.stabs,.backbtn,.banner,dialog,[popover],#chatticker,#chatlive,.ticker,.tpanel,.toast){display:none!important}
  body:has(.slip,.doc){background:#fff!important;color:#000}body:has(.slip,.doc) main{max-width:none!important;padding:0!important;margin:0!important}
  body:has(.slip,.doc) main h1:not(.sumline){background:none!important;-webkit-background-clip:initial!important;background-clip:initial!important;color:#000!important}
  body:has(.doc) .card{border:1px solid #999;box-shadow:none;background:#fff;break-inside:avoid;color:#000}body:has(.doc) a{color:inherit;text-decoration:none}
  .slip,.slip *{color:#000!important}.slip dt,.slip th,.slip .kicker,.slip .stamp,.slip .sig,.slip footer{color:#444!important}
  .slip{max-width:none;border:0;padding:0;background:#fff}.slip th,.slip td{border-bottom-color:#bbb}.slip header{border-bottom-color:#000}.slip .sig{border-top-color:#000}}
.stream{list-style:none;padding:0;margin:0} .stream li{padding:8px 0;border-bottom:1px solid var(--line)} .stream li:last-child{border-bottom:none}
.athread{max-height:28rem;overflow:auto;margin:8px 0 12px;padding:0 12px;border:1px solid var(--line);border-radius:var(--r-sm)} h4.afiles{margin:12px 0 4px;display:flex;align-items:center;gap:6px} details.acontext{margin-top:10px} details.acontext>summary{cursor:pointer;font-weight:600;color:var(--ink-2)} details.acontext>summary::marker{color:var(--ink-3)}
.stream .meta{color:var(--ink-3);font-size:12px}
.stream li.by-req,.stream li.by-staff{border:0;border-left:4px solid var(--accent);border-radius:var(--r-md,8px);padding:8px 12px;margin:0 0 8px;background:var(--accent-bg)} .stream li.by-req{border-left-color:var(--req);background:var(--req-bg)}
.note{position:relative;border:1px solid var(--line);border-radius:var(--r-lg);padding:10px 12px 10px 16px;margin-bottom:10px;background:var(--surface);overflow:hidden}
.note::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--accent)}
.note.INTERNAL{background:var(--warn-bg);border-color:transparent} .note.INTERNAL::before{background:var(--warn)}
.note.RESOLUTION{background:var(--ok-bg);border-color:transparent} .note.RESOLUTION::before{background:var(--ok)}
:root{--req:#0e8a8a;--req-bg:color-mix(in srgb,#0e8a8a 10%,transparent)}
:root[data-theme=dark]{--req:#3cc6c6}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--req:#3cc6c6}}
.note.by-req{background:var(--req-bg);border-color:color-mix(in srgb,var(--req) 30%,transparent)} .note.by-req::before{background:var(--req);width:4px}
.note.by-staff.DISCUSSION::before{width:4px}
.note.by-req .av{color:var(--req);background:color-mix(in srgb,var(--req) 16%,var(--surface))}
span.who{font-size:10.5px;font-weight:700;letter-spacing:.02em;text-transform:uppercase;border-radius:999px;padding:1px 8px}
.who.staff{color:var(--accent);background:var(--accent-bg)} .who.req{color:var(--req);background:var(--req-bg)}
.wholegend{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;color:var(--ink-3);margin-left:12px}
.wholegend i{width:10px;height:10px;border-radius:3px;display:inline-block;margin-left:6px} .wholegend i.staff{background:var(--accent)} .wholegend i.req{background:var(--req)}
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

/* ---- the 6 Oct 2026 look (Dada: "add futuristic design on the whole
   ticketing board and transitions") ----------------------------------------
   Light from behind, edges that catch it, things that rise into place. Only
   colour, opacity and transform move, nothing is blurred, and every effect is
   off for a reader who asks for less motion: ward PCs are old, and a clinical
   desk is read before it is admired. */
:root{--c1:34 211 238;--c2:139 92 246;--c2b:124 58 237;--c3:99 102 241;--ck:150 165 255;--ck0:148 163 255;--ck1:170 185 255;--ck2:180 195 255;--ck3:130 150 255;--ck4:120 140 255;--ck5:110 140 255;--ckl:60 80 150;--ckl1:70 90 160;--ckl2:80 110 240;--lc1:#0891b2;--lc1r:8 145 178;--lc2:#7c3aed;--lc3:#06b6d4;--lc3r:6 182 212;--dk-accent:#8ea2ff}
:root{--glow:color-mix(in srgb,var(--accent) 38%,transparent);--aur1:color-mix(in srgb,var(--accent) 13%,transparent);
  --aur2:color-mix(in srgb,var(--teal) 10%,transparent);--aur3:color-mix(in srgb,var(--neon2) 9%,transparent);
  --edge:linear-gradient(135deg,color-mix(in srgb,var(--accent) 34%,var(--line)),var(--line) 38%,var(--line) 70%,color-mix(in srgb,var(--teal) 26%,var(--line)))}
body{background:
  radial-gradient(1100px 520px at 0% -8%,var(--aur1),transparent 62%),
  radial-gradient(900px 480px at 100% -4%,var(--aur2),transparent 60%),
  radial-gradient(800px 600px at 50% 110%,var(--aur3),transparent 65%),var(--canvas);background-repeat:no-repeat}
header.top{border-bottom:0!important;box-shadow:0 1px 0 var(--line)}
header.top::after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:2px;pointer-events:none;
  background:linear-gradient(90deg,transparent,var(--accent) 22%,var(--teal) 52%,var(--neon2) 78%,transparent);opacity:.75}
.card{border:1px solid transparent;background:linear-gradient(var(--surface),var(--surface)) padding-box,var(--edge) border-box;
  transition:box-shadow var(--slow) var(--ease),transform var(--slow) var(--ease)}
.card:hover{box-shadow:0 18px 42px -26px var(--glow)}
main button[type=submit]:not(.ghost):not(.iconbtn):not(.tab):not(.small):not(.danger),main .btn:not(.ghost):not(.top){
  background-image:linear-gradient(135deg,var(--accent),color-mix(in srgb,var(--accent) 70%,var(--neon2)));border-color:transparent;
  transition:box-shadow var(--fast) var(--ease),transform var(--fast) var(--ease),filter var(--fast) var(--ease)}
main button[type=submit]:not(.ghost):not(.iconbtn):not(.tab):not(.small):not(.danger):hover,main .btn:not(.ghost):not(.top):hover{box-shadow:0 6px 20px -6px var(--glow);filter:brightness(1.06)}
main button[type=submit]:not(.ghost):not(.iconbtn):not(.tab):not(.small):not(.danger):active,main .btn:not(.ghost):not(.top):active{transform:scale(.98)}
:focus-visible{box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 18%,transparent)}
table.grid tbody tr:hover{background:linear-gradient(90deg,color-mix(in srgb,var(--accent) 10%,transparent),transparent 70%);box-shadow:inset 3px 0 0 var(--accent)}
.bar i{background-image:linear-gradient(90deg,color-mix(in srgb,currentColor 0%,transparent),rgb(255 255 255/.28))}
.slabox{background:linear-gradient(160deg,color-mix(in srgb,var(--accent) 6%,var(--surface)),var(--surface) 60%)}
h1{letter-spacing:-.01em}
.note{transition:transform var(--fast) var(--ease),box-shadow var(--fast) var(--ease)}
.note:hover{box-shadow:0 10px 26px -20px var(--glow)}
dialog.tedlg::backdrop{backdrop-filter:none;background:rgba(10,14,24,.55)}
@media (prefers-reduced-motion:no-preference){
  .pods>.card,main>.card,.rail .card,.slastrip .slabox{animation:rise .24s var(--ease) both}
  .pods>.card:nth-child(2),.slastrip .slabox:nth-child(2){animation-delay:.03s}
  .pods>.card:nth-child(3),.slastrip .slabox:nth-child(3){animation-delay:.06s}
  .pods>.card:nth-child(4){animation-delay:.09s} .pods>.card:nth-child(5){animation-delay:.12s}
  .pods>.card:nth-child(n+6){animation-delay:.14s}
  table.grid tbody tr{animation:fadein .2s var(--ease) both}
  /* notes do not rise: the pod editor keeps the page still by measuring them (browser check, 6 Oct) */
  dialog[open]{animation:pop .18s var(--ease) both}
}
@keyframes rise{from{opacity:0;transform:translateY(6px)}}
@keyframes fadein{from{opacity:0}}
@keyframes pop{from{opacity:0;transform:translateY(8px) scale(.985)}}

/* ---- "more futuristic and modern" (Dada, 6 Oct 2026, the second pass) ----
   The same desk, drawn as a control surface: a faint dot grid under deep
   light, a glass bar, rounder fields that light up when used, pill buttons,
   numbers that glow. Still only colour, opacity and transform; the grid is a
   fixed layer, so scrolling does not repaint it. */
:root{--r-sm:8px;--r:11px;--r-lg:16px;--teal:#14b8a6;--violet:#8b5cf6}

header.top{background:color-mix(in srgb,var(--surface) 72%,transparent)}
header.top .brand i{background:conic-gradient(from 210deg,var(--accent),var(--teal),var(--violet),var(--accent));
  box-shadow:0 0 16px -2px var(--glow),inset 0 0 0 1px rgb(255 255 255/.3)}
header.top .brand{font-weight:700;letter-spacing:-.3px}
header.top nav button.top,header.top nav a.top{border-radius:999px}
header.top nav button.top:hover,header.top nav .grp.open button.top,header.top nav a.top:hover{background:color-mix(in srgb,var(--accent) 12%,transparent);color:var(--ink);text-decoration:none}
header.top nav button.top.on,header.top nav a.top.on{color:var(--accent);background:linear-gradient(135deg,color-mix(in srgb,var(--accent) 18%,transparent),color-mix(in srgb,var(--teal) 10%,transparent));
  box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--accent) 30%,transparent)}
header.top nav button.top.on::after{display:none}
header.top nav .panel{border-radius:16px;box-shadow:0 24px 60px -20px rgb(0 0 0/.45),0 0 0 1px color-mix(in srgb,var(--accent) 14%,transparent)}
main h1:not(.sumline),main .hdr h1 .sumtext{background:linear-gradient(92deg,var(--ink) 20%,var(--accent) 70%,var(--teal));
  -webkit-background-clip:text;background-clip:text;color:transparent}
h1.sumline{font-size:24px} h1.sumline>:first-child{color:var(--accent)}
.card{border-radius:var(--r-lg);box-shadow:inset 0 1px 0 rgb(255 255 255/.05),0 1px 2px rgb(0 0 0/.04)}
.card h3{letter-spacing:.08em}
.tile{border-radius:var(--r-lg);border:1px solid transparent;
  background:linear-gradient(160deg,color-mix(in srgb,var(--accent) 9%,var(--surface)),var(--surface) 58%) padding-box,var(--edge) border-box;
  transition:transform var(--slow) var(--ease),box-shadow var(--slow) var(--ease)}
.tiles a.tile:hover{transform:translateY(-2px);box-shadow:0 16px 36px -22px var(--glow);background:linear-gradient(160deg,color-mix(in srgb,var(--accent) 14%,var(--surface)),var(--surface) 60%) padding-box,var(--edge) border-box}
.tile .n{font-size:30px;font-weight:750;letter-spacing:-1px}
.tile .ic{width:32px;height:32px;padding:7px;border-radius:50%;opacity:1;color:var(--accent);top:10px;right:10px;
  background:color-mix(in srgb,var(--accent) 12%,transparent);box-shadow:0 0 18px -6px var(--glow)}
input,select,textarea{border-radius:var(--r);background-color:color-mix(in srgb,var(--surface-2) 55%,var(--surface));
  transition:border-color var(--fast) var(--ease),box-shadow var(--fast) var(--ease),background-color var(--fast) var(--ease)}
input:focus,select:focus,textarea:focus{border-color:var(--accent);background-color:var(--surface);
  box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 16%,transparent),0 0 22px -8px var(--glow);outline:none}
main button,main .btn{border-radius:999px}
main .iconbtn,main .edbar .iconbtn,main .edbar summary{border-radius:8px}
.bar{height:6px;border-radius:99px;background:color-mix(in srgb,var(--ink) 8%,transparent)}
.bar i{border-radius:99px}
.slabox{border-radius:var(--r-lg)}
.slabox:not(.done):not(.bad):not(.warn) .bar i{box-shadow:0 0 12px -1px var(--ok)}
.slabox.warn .bar i{box-shadow:0 0 12px -1px var(--warn)} .slabox.bad .bar i{box-shadow:0 0 12px -1px var(--bad)}
.slabox .v{font-size:19px;font-weight:700;letter-spacing:-.3px}
.note{border-radius:14px}
.av{background:linear-gradient(135deg,color-mix(in srgb,var(--accent) 30%,var(--surface)),color-mix(in srgb,var(--teal) 22%,var(--surface)))}
table.grid tbody tr:hover td:nth-child(2) a{text-shadow:0 0 12px var(--glow)}
.tabs a.on{position:relative}
.tabs a.on::after{box-shadow:0 0 10px var(--glow)}
*{scrollbar-width:thin;scrollbar-color:color-mix(in srgb,var(--accent) 45%,transparent) transparent}
::-webkit-scrollbar{width:9px;height:9px} ::-webkit-scrollbar-thumb{background:color-mix(in srgb,var(--accent) 40%,transparent);border-radius:9px;border:2px solid transparent;background-clip:padding-box}
:root[data-theme=dark] body,:root:not([data-theme=light]) body{--aur1:color-mix(in srgb,var(--accent) 18%,transparent);--aur2:color-mix(in srgb,var(--teal) 13%,transparent)}
@media (prefers-color-scheme:light){:root:not([data-theme=dark]) body{--aur1:color-mix(in srgb,var(--accent) 13%,transparent);--aur2:color-mix(in srgb,var(--teal) 10%,transparent)}}
:root[data-theme=light] body{--aur1:color-mix(in srgb,var(--accent) 13%,transparent);--aur2:color-mix(in srgb,var(--teal) 10%,transparent)}
@media (prefers-reduced-motion:no-preference){
  .tile{animation:rise .26s var(--ease) both} .tile:nth-child(2){animation-delay:.04s} .tile:nth-child(3){animation-delay:.08s}
  .tile:nth-child(4){animation-delay:.12s} .tile:nth-child(5){animation-delay:.16s}
  header.top .brand i{animation:hue 12s linear infinite}
}
@keyframes hue{to{filter:hue-rotate(360deg)}}

/* ---- the control-room look (Dada, 6 Oct 2026, third pass: "still so much
   white and there are dots ... load a better gui") --------------------------
   Dark by default; deep navy under two coloured glows; panels of tinted glass
   with a lit top edge; neon cyan-to-violet for what can be pressed; the top bar
   floats; system lines become a timeline. The light theme is a cool frost,
   never plain white. Colour, opacity and transform only. */
:root{--neon1:#22d3ee;--neon2:#8b5cf6;--neon:linear-gradient(135deg,var(--neon1),var(--neon2))}
:root[data-theme=dark]{--glass-bg:rgb(17 23 41/.66);--glass-line:rgb(var(--ck0)/.14);--hi:rgb(255 255 255/.06);--accent:var(--dk-accent);
  --glow:rgb(var(--ck5)/.45)}
:root[data-theme=light]{--glass-bg:rgb(246 249 255/.78);--glass-line:rgb(var(--ckl1)/.16);--hi:rgb(255 255 255/.7);--glow:rgb(var(--ckl2)/.32)}
:root[data-theme=dark] body{background:
  radial-gradient(1000px 600px at 8% -10%,rgb(var(--c3)/.30),transparent 60%),
  radial-gradient(900px 560px at 100% 0%,rgb(var(--c1)/.18),transparent 62%),
  radial-gradient(900px 700px at 60% 120%,rgb(var(--c2)/.22),transparent 60%),
  linear-gradient(180deg,#070a14,#0a1022 60%,#080b16);background-attachment:fixed}
:root[data-theme=light] body{background:
  radial-gradient(1000px 600px at 8% -10%,rgb(var(--c3)/.20),transparent 60%),
  radial-gradient(900px 560px at 100% 0%,rgb(var(--c1)/.16),transparent 62%),
  linear-gradient(180deg,#e4e9f5,#dbe2f0);background-attachment:fixed}
/* the bar floats */
header.top{margin:10px 14px 0;border-radius:18px;top:10px;background:var(--glass-bg)!important;
  box-shadow:0 10px 40px -18px rgb(0 0 0/.55),inset 0 1px 0 var(--hi),0 0 0 1px var(--glass-line)!important}
header.top::after{left:18px;right:18px;bottom:0;border-radius:2px}
/* glass panels */
.card,.tile,.slabox,.note:not(.INTERNAL):not(.by-req),dialog.tedlg,header.top nav .panel{
  background:var(--glass-bg)!important;border:1px solid var(--glass-line)!important;
  box-shadow:inset 0 1px 0 var(--hi),0 18px 50px -30px rgb(0 0 0/.6)!important}
.card:hover{box-shadow:inset 0 1px 0 var(--hi),0 22px 60px -28px var(--glow)!important}
/* a window sits over the page: solid, so nothing behind it reads through */
/* so does everything else that floats over the page: menus, tips, toasts, the palette.
   The sticky header is nearly solid too, since the page scrolls beneath it and there is no blur */
header.top nav .panel,.edbar .pop>.menu,details.tip>.tipbody,.banner.toast,[popover]#keys,.pal-box{
  background:var(--surface)!important;box-shadow:0 24px 60px -18px rgb(0 0 0/.65),0 0 0 1px var(--glass-line)!important}
header.top{background:color-mix(in srgb,var(--surface) 96%,transparent)!important}
/* the menu bar's fade-out edge is a mask, and a mask clips everything inside it: lift it
   while a menu is open, or the menu is cut off at the bar's edge */
header.top nav:has(.grp:hover),header.top nav:has(.grp.open),header.top nav:has(.grp:focus-within){
  -webkit-mask-image:none!important;mask-image:none!important}
dialog.tedlg{background:var(--surface)!important;box-shadow:inset 0 1px 0 var(--hi),0 30px 80px -20px rgb(0 0 0/.7),0 0 0 1px var(--glass-line)!important}
.tiles a.tile:hover{box-shadow:inset 0 1px 0 var(--hi),0 18px 46px -20px var(--glow)!important}
.note.by-req{border:1px solid color-mix(in srgb,var(--req) 35%,transparent)!important}
/* neon for what is pressed */
main button[type=submit]:not(.ghost):not(.iconbtn):not(.tab):not(.small):not(.danger),main .btn:not(.ghost):not(.top),.btn.clockbtn.on{
  background:var(--neon)!important;color:#fff!important;border:0!important;box-shadow:0 8px 24px -10px var(--glow)}
main button.ghost,main .btn.ghost{background:transparent;border:1px solid var(--glass-line);color:var(--ink)}
main button.ghost:hover,main .btn.ghost:hover{border-color:var(--neon1);box-shadow:0 0 0 3px rgb(var(--c1)/.12)}
header.top nav button.top.on,header.top nav a.top.on{color:#fff;background:var(--neon)!important;box-shadow:0 6px 20px -8px var(--glow)}
:root[data-theme=light] header.top nav button.top.on,:root[data-theme=light] header.top nav a.top.on{color:#fff}
header.top nav button.top.on .ic{opacity:1}
/* fields of glass */
input,select,textarea{background-color:color-mix(in srgb,var(--glass-bg) 60%,transparent)!important;border-color:var(--glass-line)}
input:focus,select:focus,textarea:focus{border-color:var(--neon1)!important;box-shadow:0 0 0 3px rgb(var(--c1)/.18),0 0 24px -8px rgb(var(--c1)/.6)!important}
/* titles */
main h1:not(.sumline),main .hdr h1 .sumtext{background:linear-gradient(92deg,var(--ink) 15%,var(--neon1) 60%,var(--neon2));
  -webkit-background-clip:text;background-clip:text;color:transparent}
h1.sumline>:first-child{color:var(--neon1)}
.tile .n{background:linear-gradient(180deg,var(--ink),color-mix(in srgb,var(--ink) 65%,var(--neon1)));-webkit-background-clip:text;background-clip:text;color:transparent}
.tile .ic{color:var(--neon1);background:rgb(var(--c1)/.12);box-shadow:0 0 22px -6px rgb(var(--c1)/.7)}
/* SLA, neon */
.slabox:not(.done):not(.bad):not(.warn) .bar i{background:linear-gradient(90deg,#10b981,var(--neon1))!important;box-shadow:0 0 14px rgb(var(--c1)/.6)}
.slabox.bad .bar i{background:linear-gradient(90deg,#f43f5e,#fb7185)!important;box-shadow:0 0 14px rgb(244 63 94/.6)}
.slabox.warn .bar i{background:linear-gradient(90deg,#f59e0b,#fcd34d)!important;box-shadow:0 0 14px rgb(245 158 11/.55)}
.slabox::before{width:3px!important}
/* activity: system lines as a timeline */
.sys{position:relative;padding:4px 0 8px 40px!important;margin:0}
.sys::before{content:"";position:absolute;left:19px;top:0;bottom:0;width:2px;background:linear-gradient(var(--glass-line),var(--glass-line))}
.sys::after{content:"";position:absolute;left:15px;top:9px;width:10px;height:10px;border-radius:50%;background:var(--canvas);
  border:2px solid var(--neon1);box-shadow:0 0 10px rgb(var(--c1)/.6)}
/* the board's rows */
table.grid thead th{background:transparent!important;color:var(--ink-3)}
table.grid tbody tr:hover{background:linear-gradient(90deg,rgb(var(--c1)/.10),rgb(var(--c2)/.06) 60%,transparent)!important;box-shadow:inset 3px 0 0 var(--neon1)!important}
/* chips glow softly */
.who.staff{background:rgb(var(--c3)/.18)} .who.req{background:rgb(20 184 166/.18)}
.backbtn{background:var(--glass-bg);border-color:var(--glass-line)!important;box-shadow:inset 0 1px 0 var(--hi)}
footer{opacity:.75}

/* ---- depth (Dada, 6 Oct 2026: "dont you think the design is too flat").
   Three heights, each lit from above: the canvas; cards, with a lit top edge,
   a soft fall-off and a real shadow; and what floats (menus, windows, the bar),
   frosted and highest. Fields sit recessed into the card. Blur only on those
   small floating areas, never on the page. Gradients and shadows only. */
:root[data-theme=dark]{
  --l1:linear-gradient(180deg,rgb(30 38 66/.94),rgb(16 21 38/.94));
  --l1-edge:linear-gradient(180deg,rgb(var(--ck1)/.30),rgb(var(--ck1)/.07) 40%,rgb(var(--ck1)/.04));
  --l1-shadow:inset 0 1px 0 rgb(255 255 255/.07),0 1px 2px rgb(0 0 0/.45),0 22px 44px -18px rgb(0 0 0/.75);
  --l1-hover:inset 0 1px 0 rgb(255 255 255/.09),0 1px 2px rgb(0 0 0/.45),0 26px 56px -18px rgb(0 0 0/.8),0 0 0 1px rgb(var(--ck4)/.18);
  --l2-bg:rgb(20 26 46/.86);
  --l2-shadow:inset 0 1px 0 rgb(255 255 255/.10),0 0 0 1px rgb(var(--ck1)/.16),0 30px 70px -20px rgb(0 0 0/.85),0 10px 24px -12px rgb(0 0 0/.6);
  --well:rgb(6 9 20/.55);--well-shadow:inset 0 1px 2px rgb(0 0 0/.5),inset 0 0 0 1px rgb(var(--ck)/.10)}
:root[data-theme=light]{
  --l1:linear-gradient(180deg,#fdfdff,#eff3fb);
  --l1-edge:linear-gradient(180deg,rgb(255 255 255/1),rgb(var(--ckl1)/.16) 45%,rgb(var(--ckl1)/.22));
  --l1-shadow:inset 0 1px 0 #fff,0 1px 2px rgb(30 40 90/.08),0 18px 36px -18px rgb(30 40 90/.32);
  --l1-hover:inset 0 1px 0 #fff,0 1px 2px rgb(30 40 90/.08),0 24px 48px -18px rgb(30 40 90/.38),0 0 0 1px rgb(var(--ckl2)/.18);
  --l2-bg:rgb(250 251 255/.88);
  --l2-shadow:inset 0 1px 0 #fff,0 0 0 1px rgb(var(--ckl1)/.16),0 30px 70px -22px rgb(30 40 90/.45),0 8px 20px -10px rgb(30 40 90/.2);
  --well:rgb(255 255 255/.75);--well-shadow:inset 0 1px 2px rgb(30 40 90/.10),inset 0 0 0 1px rgb(var(--ckl1)/.14)}
/* the canvas: deeper glows, and a vignette so the middle reads brightest */
:root[data-theme=dark] body{background:
  radial-gradient(1200px 700px at 10% -15%,rgb(var(--c3)/.38),transparent 60%),
  radial-gradient(1000px 600px at 105% -5%,rgb(var(--c1)/.22),transparent 62%),
  radial-gradient(1100px 800px at 55% 125%,rgb(var(--c2)/.30),transparent 60%),
  radial-gradient(140% 100% at 50% 40%,transparent 55%,rgb(0 0 0/.45)),
  linear-gradient(180deg,#060912,#0a1022 55%,#070a15);background-attachment:fixed}
/* level 1: cards and tiles */
.card,.tile,.slabox{
  background:var(--l1) padding-box,var(--l1-edge) border-box!important;border:1px solid transparent!important;
  box-shadow:var(--l1-shadow)!important}
.card:hover{box-shadow:var(--l1-hover)!important}
.tiles a.tile:hover{box-shadow:var(--l1-hover),0 16px 40px -18px var(--glow)!important}
/* tiles say what they mean before they are read */
.tile.bad{background:linear-gradient(180deg,rgb(244 63 94/.20),transparent 70%) padding-box,var(--l1) padding-box,
  linear-gradient(180deg,rgb(251 113 133/.55),rgb(244 63 94/.08)) border-box!important}
.tile.warn{background:linear-gradient(180deg,rgb(245 158 11/.18),transparent 70%) padding-box,var(--l1) padding-box,
  linear-gradient(180deg,rgb(252 211 77/.5),rgb(245 158 11/.08)) border-box!important}
.tile.on{background:linear-gradient(180deg,rgb(var(--c1)/.16),transparent 70%) padding-box,var(--l1) padding-box,
  var(--neon) border-box!important}
.tile.bad .ic{color:#fb7185;background:rgb(244 63 94/.14);box-shadow:0 0 22px -6px rgb(244 63 94/.8)}
.tile.warn .ic{color:#fcd34d;background:rgb(245 158 11/.14);box-shadow:0 0 22px -6px rgb(245 158 11/.8)}
.tile .n{font-size:30px;letter-spacing:-.02em}
/* level 2: what floats, frosted */
header.top,header.top nav .panel,.edbar .pop>.menu,details.tip>.tipbody,.banner.toast,[popover]#keys,.pal-box,dialog.tedlg{
  background:var(--l2-bg)!important;box-shadow:var(--l2-shadow)!important}
@supports ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){
  header.top,header.top nav .panel,.edbar .pop>.menu,details.tip>.tipbody,.banner.toast,[popover]#keys,.pal-box,dialog.tedlg{
    -webkit-backdrop-filter:blur(20px) saturate(1.5);backdrop-filter:blur(20px) saturate(1.5)}}
@supports not ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){
  header.top nav .panel,.edbar .pop>.menu,details.tip>.tipbody,.banner.toast,[popover]#keys,.pal-box,dialog.tedlg{background:var(--surface)!important}}
dialog.tedlg .tehead{background:linear-gradient(180deg,rgb(255 255 255/.05),transparent)}
/* fields sit into the card */
input:not([type=checkbox]):not([type=radio]):not([type=range]),select,textarea,.multipick,.editor{
  background-color:var(--well)!important;box-shadow:var(--well-shadow)}
/* buttons that can be pressed look it */
main button[type=submit]:not(.ghost):not(.iconbtn):not(.tab):not(.small):not(.danger),main .btn:not(.ghost):not(.top),.btn.clockbtn.on{
  box-shadow:inset 0 1px 0 rgb(255 255 255/.35),inset 0 -2px 0 rgb(0 0 0/.18),0 10px 26px -10px var(--glow)!important}
main button.ghost,main .btn.ghost,.backbtn{
  background:linear-gradient(180deg,rgb(255 255 255/.07),rgb(255 255 255/.01))!important;
  box-shadow:inset 0 1px 0 var(--hi),0 1px 2px rgb(0 0 0/.25)}
:root[data-theme=light] main button.ghost,:root[data-theme=light] main .btn.ghost,:root[data-theme=light] .backbtn{
  background:linear-gradient(180deg,#fff,#eef2fa)!important;box-shadow:inset 0 1px 0 #fff,0 1px 2px rgb(30 40 90/.12)}
/* the active tab is lit */
.tabs a.on,.tabs a[aria-current]{text-shadow:0 0 18px var(--glow)}
/* notes inside a card sit one step up from it */
.note{box-shadow:inset 0 1px 0 var(--hi),0 6px 16px -10px rgb(0 0 0/.5)!important}

/* ---- light, with depth (Dada, 6 Oct 2026: "the light theme is still too flat").
   Light reads flat when the page and its cards are nearly the same pale. So: a
   deeper, coloured canvas; white cards that stand off it on a three-step
   shadow; a crisp edge; a header band on tables; fields with a defined well;
   colour carried by the glows and accents rather than by grey. */
:root[data-theme=light]{
  --l1:linear-gradient(180deg,#ffffff,#f7f9fe);
  --l1-edge:linear-gradient(180deg,#ffffff,rgb(var(--ckl)/.20) 40%,rgb(var(--ckl)/.30));
  --l1-shadow:inset 0 1px 0 #fff,0 1px 1px rgb(20 30 70/.06),0 4px 10px -3px rgb(20 30 70/.10),0 26px 50px -22px rgb(30 40 110/.42);
  --l1-hover:inset 0 1px 0 #fff,0 1px 1px rgb(20 30 70/.06),0 6px 14px -4px rgb(20 30 70/.12),0 32px 60px -22px rgb(50 60 170/.48),0 0 0 1px rgb(var(--ckl2)/.22);
  --l2-bg:rgb(255 255 255/.86);
  --l2-shadow:inset 0 1px 0 #fff,0 0 0 1px rgb(var(--ckl)/.18),0 34px 80px -24px rgb(30 40 110/.5),0 10px 24px -10px rgb(30 40 110/.22);
  --well:#f3f6fc;--well-shadow:inset 0 1px 2px rgb(20 30 70/.10),inset 0 0 0 1px rgb(var(--ckl)/.20)}
:root[data-theme=light] body{background:
  radial-gradient(1100px 650px at 6% -12%,rgb(var(--c3)/.34),transparent 60%),
  radial-gradient(1000px 600px at 104% -6%,rgb(var(--c1)/.30),transparent 60%),
  radial-gradient(1100px 760px at 60% 125%,rgb(168 85 247/.22),transparent 60%),
  linear-gradient(180deg,#d6ddee,#cdd6ea 60%,#d3d9ec);background-attachment:fixed}
/* the theme menu */
.thememenu{position:absolute;z-index:120;min-width:180px;padding:6px;background:var(--card);border:1px solid var(--line);border-radius:12px;
  box-shadow:0 10px 28px rgba(0,0,0,.25);display:flex;flex-direction:column;gap:2px}
.thememenu button{display:flex;align-items:center;gap:10px;background:none;border:0;text-align:left;padding:7px 10px;border-radius:8px;font:inherit;
  font-weight:500;color:var(--ink);cursor:pointer;height:auto;min-width:0;justify-content:flex-start}
.thememenu button:hover{background:var(--surface-2)}.thememenu button.on{background:var(--accent-bg);font-weight:600}
.thememenu .sw{width:18px;height:18px;border-radius:50%;border:1px solid rgb(0 0 0/.15);flex:0 0 auto}
.thememenu h5{margin:6px 10px 2px;font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-3)}.thememenu .sw.dark{background:linear-gradient(135deg,#0a1022,#3b4a8a)}.thememenu .sw.light{background:linear-gradient(135deg,#ffffff,#c9d4ee)}.thememenu .sw.classic{background:linear-gradient(135deg,#3d63dd,#22d3ee)}
.thememenu .sw.peach{background:linear-gradient(135deg,#ffd9c2,#e8734a)}.thememenu .sw.purple{background:linear-gradient(135deg,#e2d4ff,#7c4ddb)}
.thememenu .sw.pink{background:linear-gradient(135deg,#ffd6e8,#d8408a)}
:root[data-theme=light] header.top{box-shadow:var(--l2-shadow)!important}
:root[data-theme=light] header.top::after{opacity:1}
:root[data-theme=light] main h1:not(.sumline){background:linear-gradient(92deg,#0f1630 20%,var(--lc1) 62%,var(--lc2));
  -webkit-background-clip:text;background-clip:text;color:transparent}
/* tables: a band for the header, lines that can be seen, a row that answers the pointer */
:root[data-theme=light]{--thead:linear-gradient(180deg,#eef2fb,#e6ebf7);--thead-ink:#4a5578}
:root[data-theme=light] table.grid thead th{background:var(--thead)!important;color:var(--thead-ink);
  box-shadow:inset 0 -1px 0 rgb(var(--ckl)/.22)}
:root[data-theme=light] table.grid tbody td{border-color:rgb(var(--ckl)/.13)!important}
:root[data-theme=light] table.grid tbody tr:hover{background:linear-gradient(90deg,rgb(var(--c1)/.12),rgb(var(--c2b)/.06) 60%,transparent)!important}
/* tiles carry their colour further */
:root[data-theme=light] .tile.bad{background:linear-gradient(160deg,rgb(244 63 94/.18),transparent 65%) padding-box,var(--l1) padding-box,
  linear-gradient(180deg,rgb(244 63 94/.55),rgb(244 63 94/.15)) border-box!important}
:root[data-theme=light] .tile.warn{background:linear-gradient(160deg,rgb(245 158 11/.20),transparent 65%) padding-box,var(--l1) padding-box,
  linear-gradient(180deg,rgb(245 158 11/.6),rgb(245 158 11/.15)) border-box!important}
:root[data-theme=light] .tile.on{background:linear-gradient(160deg,rgb(var(--c1)/.18),rgb(var(--c2b)/.08) 60%,transparent) padding-box,var(--l1) padding-box,
  var(--neon) border-box!important}
:root[data-theme=light] .tile .ic{background:rgb(var(--lc1r)/.12);color:var(--lc1);box-shadow:0 6px 16px -6px rgb(var(--lc1r)/.6)}
:root[data-theme=light] .tile.bad .ic{background:rgb(244 63 94/.12);color:#e11d48;box-shadow:0 6px 16px -6px rgb(244 63 94/.6)}
:root[data-theme=light] .tile.warn .ic{background:rgb(245 158 11/.14);color:#d97706;box-shadow:0 6px 16px -6px rgb(245 158 11/.6)}
:root[data-theme=light] .tile .n{background:linear-gradient(180deg,#0f1630,#3b4a7a);-webkit-background-clip:text;background-clip:text;color:transparent}
/* card titles get a hairline under them, so a card has a head and a body */
:root[data-theme=light] .card>h2:first-child,:root[data-theme=light] .card>.cardhead:first-child{
  padding-bottom:10px;margin-bottom:12px;box-shadow:0 1px 0 rgb(var(--ckl)/.14)}
/* fields and quiet buttons with an edge you can see */
:root[data-theme=light] input:not([type=checkbox]):not([type=radio]):not([type=range]),:root[data-theme=light] select,
:root[data-theme=light] textarea,:root[data-theme=light] .multipick{border-color:transparent!important}
:root[data-theme=light] input:focus,:root[data-theme=light] select:focus,:root[data-theme=light] textarea:focus{
  background-color:#fff!important;box-shadow:0 0 0 1px var(--lc3),0 0 0 4px rgb(var(--lc3r)/.18)!important}
:root[data-theme=light] main button.ghost,:root[data-theme=light] main .btn.ghost,:root[data-theme=light] .backbtn{
  border:1px solid rgb(var(--ckl)/.22)!important;box-shadow:inset 0 1px 0 #fff,0 1px 2px rgb(20 30 70/.10),0 4px 10px -6px rgb(20 30 70/.25)}
/* notes: the two voices read as coloured paper on white */
:root[data-theme=light] .note{box-shadow:inset 0 1px 0 rgb(255 255 255/.8),0 1px 2px rgb(20 30 70/.06),0 10px 22px -14px rgb(30 40 110/.35)!important}
:root[data-theme=light] footer{color:#56607e}
/* pale on pale shows through even under blur: floating layers in light are near solid */
:root[data-theme=light] header.top nav .panel,:root[data-theme=light] .edbar .pop>.menu,:root[data-theme=light] details.tip>.tipbody,
:root[data-theme=light] .banner.toast,:root[data-theme=light] [popover]#keys,:root[data-theme=light] .pal-box,:root[data-theme=light] dialog.tedlg{
  background:#fff!important}

/* ---- dark, with the same depth (Dada, 6 Oct 2026: "it didnt apply on the dark
   mode"). The light pass's band, edges and shadows had no dark twin, and dark
   cards sat too near the canvas to stand off it. A darker canvas, lighter
   cards with a brighter lit edge, and every light-only rule given its pair. */
:root[data-theme=dark]{
  --l1:linear-gradient(180deg,rgb(38 47 82/.96),rgb(22 28 50/.96));
  --l1-edge:linear-gradient(180deg,rgb(var(--ck2)/.42),rgb(var(--ck)/.12) 35%,rgb(var(--ck)/.08));
  --l1-shadow:inset 0 1px 0 rgb(255 255 255/.10),0 1px 1px rgb(0 0 0/.5),0 6px 14px -4px rgb(0 0 0/.55),0 30px 60px -22px rgb(0 0 0/.9);
  --l1-hover:inset 0 1px 0 rgb(255 255 255/.12),0 1px 1px rgb(0 0 0/.5),0 8px 18px -4px rgb(0 0 0/.6),0 34px 70px -22px rgb(0 0 0/.95),0 0 0 1px rgb(var(--ck3)/.30),0 0 40px -12px var(--glow);
  --well:rgb(5 7 16/.70);--well-shadow:inset 0 2px 4px rgb(0 0 0/.55),inset 0 0 0 1px rgb(var(--ck)/.16)}
:root[data-theme=dark] body{background:
  radial-gradient(1200px 700px at 8% -15%,rgb(var(--c3)/.34),transparent 60%),
  radial-gradient(1000px 600px at 105% -5%,rgb(var(--c1)/.20),transparent 62%),
  radial-gradient(1100px 800px at 55% 125%,rgb(var(--c2)/.28),transparent 60%),
  radial-gradient(140% 100% at 50% 40%,transparent 50%,rgb(0 0 0/.55)),
  linear-gradient(180deg,#04060c,#070b18 55%,#05070f);background-attachment:fixed}
:root[data-theme=dark]{--thead:linear-gradient(180deg,rgb(50 60 100/.55),rgb(36 44 76/.55));--thead-ink:#aab4d6}
:root[data-theme=dark] table.grid thead th{background:var(--thead)!important;color:var(--thead-ink);
  box-shadow:inset 0 -1px 0 rgb(var(--ck)/.22)}
:root[data-theme=dark] table.grid tbody td{border-color:rgb(var(--ck)/.12)!important}
:root[data-theme=dark] .card>h2:first-child,:root[data-theme=dark] .card>.cardhead:first-child{
  padding-bottom:10px;margin-bottom:12px;box-shadow:0 1px 0 rgb(var(--ck)/.14)}
:root[data-theme=dark] main button.ghost,:root[data-theme=dark] main .btn.ghost,:root[data-theme=dark] .backbtn{
  border:1px solid rgb(var(--ck)/.26)!important;
  background:linear-gradient(180deg,rgb(255 255 255/.09),rgb(255 255 255/.02))!important;
  box-shadow:inset 0 1px 0 rgb(255 255 255/.10),0 1px 2px rgb(0 0 0/.5),0 6px 14px -8px rgb(0 0 0/.7)}
:root[data-theme=dark] input:focus,:root[data-theme=dark] select:focus,:root[data-theme=dark] textarea:focus{
  background-color:rgb(8 12 26/.9)!important;box-shadow:0 0 0 1px var(--neon1),0 0 0 4px rgb(var(--c1)/.20),0 0 24px -6px rgb(var(--c1)/.6)!important}
:root[data-theme=dark] .tile.bad{background:linear-gradient(160deg,rgb(244 63 94/.28),transparent 65%) padding-box,var(--l1) padding-box,
  linear-gradient(180deg,rgb(251 113 133/.7),rgb(244 63 94/.15)) border-box!important}
:root[data-theme=dark] .tile.warn{background:linear-gradient(160deg,rgb(245 158 11/.26),transparent 65%) padding-box,var(--l1) padding-box,
  linear-gradient(180deg,rgb(252 211 77/.65),rgb(245 158 11/.15)) border-box!important}
:root[data-theme=dark] .tile.on{background:linear-gradient(160deg,rgb(var(--c1)/.24),rgb(var(--c2)/.12) 60%,transparent) padding-box,var(--l1) padding-box,
  var(--neon) border-box!important}
:root[data-theme=dark] .note{box-shadow:inset 0 1px 0 rgb(255 255 255/.06),0 1px 2px rgb(0 0 0/.5),0 12px 26px -14px rgb(0 0 0/.8)!important}
:root[data-theme=dark] header.top nav .panel,:root[data-theme=dark] .edbar .pop>.menu,:root[data-theme=dark] details.tip>.tipbody,
:root[data-theme=dark] .banner.toast,:root[data-theme=dark] [popover]#keys,:root[data-theme=dark] .pal-box,:root[data-theme=dark] dialog.tedlg{
  background:#181e36!important}

/* ---- the effects, back on top (Dada, 6 Oct 2026: "the glowing when hovered
   was removed ... and all the other effects"). The depth layers above wrote
   their resting shadows per theme, which out-ranked the plain :hover rules of
   the control-room pass. Every hover and focus glow is restated here, last and
   per theme, so a later resting style can never quietly win again. */
:root[data-theme] .card{transition:box-shadow .22s var(--ease),border-color .22s var(--ease)}
:root[data-theme=dark] .card:hover{box-shadow:var(--l1-hover),0 0 0 1px rgb(var(--c1)/.30),0 0 46px -10px rgb(var(--c1)/.35)!important}
:root[data-theme=light] .card:hover{box-shadow:var(--l1-hover),0 0 0 1px rgb(var(--lc3r)/.35),0 0 46px -12px rgb(var(--lc3r)/.45)!important}
:root[data-theme] .tiles a.tile:hover{box-shadow:var(--l1-hover),0 0 0 1px rgb(var(--c1)/.45),0 18px 50px -14px rgb(var(--c1)/.55)!important}
:root[data-theme] .tiles a.tile.bad:hover{box-shadow:var(--l1-hover),0 0 0 1px rgb(244 63 94/.55),0 18px 50px -14px rgb(244 63 94/.6)!important}
:root[data-theme] .tiles a.tile.warn:hover{box-shadow:var(--l1-hover),0 0 0 1px rgb(245 158 11/.55),0 18px 50px -14px rgb(245 158 11/.6)!important}
:root[data-theme] .tile:hover .ic{transform:scale(1.08);box-shadow:0 0 28px -4px currentColor}
:root[data-theme] main button.ghost:hover,:root[data-theme] main .btn.ghost:hover,:root[data-theme] .backbtn:hover{
  border-color:var(--neon1)!important;color:var(--ink);
  box-shadow:0 0 0 3px rgb(var(--c1)/.18),0 0 22px -4px rgb(var(--c1)/.55),inset 0 1px 0 var(--hi)!important}
:root[data-theme] main button[type=submit]:not(.ghost):not(.iconbtn):not(.tab):not(.small):not(.danger):hover:not([disabled]),
:root[data-theme] main .btn:not(.ghost):not(.top):hover{filter:brightness(1.1) saturate(1.1);
  box-shadow:inset 0 1px 0 rgb(255 255 255/.4),inset 0 -2px 0 rgb(0 0 0/.18),0 0 0 3px rgb(var(--c2)/.20),0 14px 34px -8px var(--glow),0 0 30px -6px rgb(var(--c1)/.55)!important}
:root[data-theme] header.top nav button.top:hover,:root[data-theme] header.top nav a.top:hover{
  color:var(--ink);background:rgb(var(--c1)/.10);box-shadow:0 0 0 1px rgb(var(--c1)/.25),0 0 18px -6px rgb(var(--c1)/.6)}
:root[data-theme] header.top nav button.top.on:hover,:root[data-theme] header.top nav a.top.on:hover{box-shadow:0 8px 26px -6px var(--glow),0 0 22px -4px rgb(var(--c1)/.6)!important}
:root[data-theme] header.top nav .panel a:hover{background:linear-gradient(90deg,rgb(var(--c1)/.14),rgb(var(--c2)/.08));
  box-shadow:inset 3px 0 0 var(--neon1)}
:root[data-theme] table.grid tbody tr:hover{background:linear-gradient(90deg,rgb(var(--c1)/.14),rgb(var(--c2)/.07) 60%,transparent)!important;
  box-shadow:inset 3px 0 0 var(--neon1),0 0 24px -12px rgb(var(--c1)/.6)!important}
:root[data-theme] input:not([type=checkbox]):not([type=radio]):not([type=range]):hover:not(:focus),:root[data-theme] select:hover:not(:focus),
:root[data-theme] textarea:hover:not(:focus){box-shadow:var(--well-shadow),0 0 0 1px rgb(var(--c1)/.35)}
:root[data-theme] .tabs a:hover{color:var(--ink);text-shadow:0 0 14px var(--glow)}
:root[data-theme] .slabox:hover .bar i{filter:brightness(1.15)}
:root[data-theme] .note:hover{box-shadow:inset 0 1px 0 var(--hi),0 0 0 1px rgb(var(--c1)/.22),0 14px 30px -14px rgb(var(--c1)/.35)!important}
@media (prefers-reduced-motion:no-preference){
  :root[data-theme] .tile .ic{transition:transform .2s var(--ease),box-shadow .2s var(--ease)}
  :root[data-theme] main button,:root[data-theme] main .btn,:root[data-theme] .backbtn,:root[data-theme] header.top nav .top{
    transition:transform .16s var(--ease),box-shadow .2s var(--ease),filter .16s var(--ease),border-color .2s var(--ease),background .2s var(--ease)}
  :root[data-theme] .tiles a.tile:hover{transform:translateY(-2px)}
}

/* a time entry in the activity reads as a booking, not a grey system line */
.sys.time{color:var(--ink)!important}
.sys.time .ic{width:14px;height:14px;vertical-align:-2px;margin-right:6px;color:var(--neon1)}
.sys.time b{color:var(--neon1)}
.sys.time::after{border-color:var(--neon2)!important;box-shadow:0 0 10px rgb(var(--c2)/.7)!important}
label b.req{color:var(--bad,#e5484d)}

/* ---- projects (068): the tab bar, the work plan's ticket rows, the ticket board, % complete */
.ptabs{position:sticky;top:76px;z-index:5;display:flex;gap:4px;flex-wrap:wrap;margin:10px 0 12px;padding:6px;border-radius:14px;
  background:var(--l2-bg,var(--surface));box-shadow:var(--l2-shadow,none)}
.ptabs a{padding:6px 12px;border-radius:999px;color:var(--ink-2);text-decoration:none;font-weight:600;font-size:13.5px}
.ptabs a:hover{color:var(--ink);background:rgb(var(--c1)/.10)}
/* the ticket's tabs (7 Oct 2026), the project bar's shape, not sticky: the ticket keeps its own sticky save bar */
.ttabs{display:flex;gap:4px;flex-wrap:wrap;margin:8px 0 12px;padding:6px;border-radius:14px;
  background:var(--l2-bg,var(--surface));box-shadow:var(--l2-shadow,none)}
.ttabs a{padding:6px 12px;border-radius:999px;color:var(--ink-2);text-decoration:none;font-weight:600;font-size:13.5px}
.ttabs a:hover{color:var(--ink);background:rgb(var(--c1)/.10)}
tr.cfgoff td{opacity:.55} tr.cfgoff:hover td{opacity:.9}
/* chat (071): the conversation, its own side on the right, the desk's lines in the desk's blue */
.chatlog{display:flex;flex-direction:column;gap:8px;max-height:60vh;min-height:220px;overflow-y:auto;padding:4px 2px 10px}
.chatlog .cl{max-width:78%;align-self:flex-start}
.chatlog .cl.me{align-self:flex-end}
.chatlog .cb{padding:8px 12px;border-radius:14px;background:var(--surface-2);color:var(--ink);white-space:pre-wrap;overflow-wrap:anywhere}
.chatlog .cl.staff .cb{background:color-mix(in srgb,var(--accent) 16%,var(--surface-2))}
.chatlog .cl.me .cb{border-bottom-right-radius:4px} .chatlog .cl:not(.me) .cb{border-bottom-left-radius:4px}
.chatlog .cm{font-size:11.5px;color:var(--ink-3);margin:2px 6px 0}
.chatlog .cl.me .cm{text-align:right}
.chatlog .cl.sys{align-self:center;max-width:none;font-size:12px;color:var(--ink-3)}
.chatsend{display:flex;gap:8px;align-items:flex-end;border-top:1px solid var(--line);padding-top:10px}
.chatsend textarea{flex:1;min-height:44px;resize:vertical}
tr.chatwait td:first-child{border-left:3px solid var(--accent)}
/* 072: reactions, files, emoji, survey */
.chatlog .cr{display:flex;gap:4px;flex-wrap:wrap;margin:3px 4px 0;min-height:0}
.chatlog .cl.me .cr{justify-content:flex-end}
.chatlog .rx{font:inherit;font-size:12.5px;line-height:1;padding:3px 7px;border-radius:999px;border:1px solid var(--line);
  background:var(--surface);color:var(--ink-2);cursor:pointer}
.chatlog .rx.on{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 14%,var(--surface))}
.chatlog .rx.add{opacity:0;transition:opacity .15s} .chatlog .cl:hover .rx.add,.chatlog .rx.add:focus{opacity:.8}
.rxpick,.emopick{position:absolute;z-index:30;display:flex;flex-wrap:wrap;gap:2px;padding:6px;background:var(--card);
  border:1px solid var(--line);border-radius:12px;box-shadow:0 10px 30px rgb(10 12 18/.2)}
.rxpick[hidden],.emopick[hidden]{display:none}
.rxpick button,.emopick button{font-size:20px;line-height:1;padding:5px;border:0;background:none;border-radius:8px;cursor:pointer}
.rxpick button:hover,.emopick button:hover{background:var(--surface-3)}
.emopick{bottom:56px;left:0;width:min(360px,90vw)}
.chatsend{position:relative;flex-wrap:wrap}
.chattools{display:flex;gap:2px;align-self:center} .chattools .iconbtn{font-size:18px;cursor:pointer}
.chatlog .cfile{margin-top:4px} .chatlog .cimg{display:block;max-width:min(320px,100%);max-height:240px;border-radius:10px;margin-bottom:4px}
.stars{display:flex;flex-direction:row-reverse;justify-content:flex-end;gap:6px;flex-wrap:wrap}
.stars .star input{position:absolute;opacity:0} .stars .star span{font-size:20px;padding:4px 8px;border:1px solid var(--line);border-radius:10px;cursor:pointer;color:#e0a800}
.stars .star input:checked+span{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 14%,transparent)}
/* the banner: waiting chats running right to left; still for anyone who asks for less motion */
/* Drawn by the server already filled when chats wait, so it is there from the first paint and nothing below it
   jumps when the page loads (MEASURED: a banner that arrived late moved a card 52px under a technician's eye). */
.ticker{position:relative;display:flex;align-items:center;gap:12px;margin:10px 16px 0;padding:8px 14px;min-height:56px;box-sizing:border-box;
  border-radius:14px;font-size:18px;background:color-mix(in srgb,var(--accent) 18%,var(--surface));
  border:2px solid color-mix(in srgb,var(--accent) 55%,transparent);box-shadow:0 2px 10px color-mix(in srgb,var(--accent) 18%,transparent)}
.ticker[hidden]{display:none}
.ticker .tlabel{white-space:nowrap;color:var(--ink);font-size:18px;letter-spacing:.01em}
.ticker .tview{flex:1;min-width:0;overflow:hidden;white-space:nowrap;-webkit-mask-image:linear-gradient(90deg,transparent,#000 4%,#000 96%,transparent);mask-image:linear-gradient(90deg,transparent,#000 4%,#000 96%,transparent)}
.ticker .ttrack{display:inline-block;padding-left:100%;animation:tick var(--tdur,18s) linear infinite}
.ticker:hover .ttrack{animation-play-state:paused}
.ticker .ttrack a{margin-right:56px;color:var(--ink);font-weight:500}
.ticker .ttrack a b{font-weight:700}
.ticker .btn,.ticker .iconbtn{flex:0 0 auto;white-space:nowrap}
.ticker .iconbtn{font-size:22px;width:40px;height:40px}
.ticker .tsound.off{opacity:.45}
/* the quick view: the live chats, opened from the banner, over the page rather than pushing it */
.ticker .tpanel{position:absolute;right:10px;top:calc(100% + 6px);z-index:60;width:min(560px,calc(100vw - 32px));max-height:min(60vh,520px);
  overflow:auto;padding:6px 12px 10px;border-radius:14px;font-size:14px;background:var(--surface);border:1px solid var(--line);
  box-shadow:0 12px 32px rgba(0,0,0,.22)}
.ticker .tpanel[hidden]{display:none}
.ticker .tpanel h4{margin:10px 0 4px;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-2)}
.ticker .trow{display:flex;align-items:flex-start;gap:10px;padding:8px 0;border-top:1px solid var(--line)}
.ticker .trow .grow{flex:1;min-width:0}
.ticker .trow .tlast{margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--ink-2)}
.ticker .tfoot{margin:8px 0 0}
.ticker .trow .btn.small{padding:1px 10px;line-height:20px;font-size:12px}
@media (max-width:760px){.ticker{font-size:15px;gap:8px;padding:6px 10px}.ticker .tlabel{display:none}.ticker .topen{display:none}}
@keyframes tick{from{transform:translateX(0)}to{transform:translateX(-100%)}}
@media (prefers-reduced-motion:reduce){.ticker .ttrack{animation:none;padding-left:0}}
.paalala ul{margin:6px 0 8px;padding-left:18px} .paalala li{margin:4px 0;line-height:1.4}
.paalala .paalalawarn{max-width:none;margin:8px 0 0;padding:8px 10px;border-radius:10px;background:color-mix(in srgb,#e0a800 16%,var(--surface));color:var(--ink)}
tr.planticket td{font-size:13.5px;color:var(--ink-2)} tr.planticket td .ic{width:13px;height:13px;vertical-align:-2px;color:var(--neon1,var(--accent))}
tr.planhead td{padding-top:12px}
.planess{display:flex;gap:12px;overflow-x:auto;padding-bottom:6px}
.plane{flex:0 0 250px;background:rgb(127 127 127/.06);border-radius:12px;padding:8px}
.plane h4{margin:2px 4px 8px;font-size:12.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--ink-3)}
.pcard{display:flex;flex-direction:column;gap:3px;padding:9px 10px;margin-bottom:8px;border-radius:10px;text-decoration:none;
  color:var(--ink);background:var(--surface);box-shadow:var(--l1-shadow,0 1px 2px rgb(0 0 0/.2));border:1px solid var(--line)}
.pcard:hover{border-color:var(--neon1,var(--accent))}
.pcard span{font-size:12px}
.pbar{display:inline-block;width:70px;height:6px;border-radius:999px;background:rgb(127 127 127/.25);vertical-align:middle;overflow:hidden}
.pbar i{display:block;height:100%;background:var(--neon,var(--accent))}
tr.popen td{padding-top:0;border-top:0}

/* ---- the Gantt (069): one row per phase and dated ticket, bars on a day scale, today marked */
.gantt{display:flex;flex-direction:column;gap:4px;overflow-x:auto}
.gantt .grow{display:grid;grid-template-columns:minmax(220px,32%) 1fr;align-items:center;gap:10px;min-width:640px}
.gantt .glabel{font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gantt .grow.phase .glabel{font-weight:700}
.gantt .gtrack{position:relative;height:18px;border-radius:6px;background:rgb(127 127 127/.08)}
.gantt .gticks{height:16px;background:none}
.gantt .gticks span{position:absolute;top:0;font-size:11px;color:var(--ink-3);transform:translateX(-2px);white-space:nowrap}
.gantt .gbar{position:absolute;top:3px;height:12px;border-radius:6px;background:var(--neon,var(--accent));box-shadow:0 0 12px -2px rgb(var(--c1)/.6)}
.gantt .grow.ticket .gbar{background:linear-gradient(90deg,var(--neon2),#a78bfa);height:10px;top:4px}
.gantt .grow.done .gbar{opacity:.4;box-shadow:none}
.gantt .gtoday{position:absolute;top:-3px;bottom:-3px;width:2px;background:#f43f5e;border-radius:2px;z-index:1}

/* ---- motion that does not lag (Dada, 6 Oct 2026: "animations are welcome
   and transitions as long as they dont lag it"). transform and opacity only,
   so the GPU does it; each runs once; none on a list that can be long. */
@media (prefers-reduced-motion:no-preference){
  main button,main .btn,.tile,.backbtn{transition:transform .16s var(--ease),box-shadow .2s var(--ease),filter .16s var(--ease)}
  main button:hover:not([disabled]),main .btn:hover,.backbtn:hover{transform:translateY(-1px)}
  main button:active:not([disabled]),main .btn:active{transform:translateY(0) scale(.98)}
  .bar i{transform-origin:left;animation:barin .7s var(--ease) both}
  dialog[open]{animation:pop .2s var(--ease) both}
  dialog[open]::backdrop{animation:fadein .2s ease both}
  header.top{animation:drop .32s var(--ease) both}
  .sys::after{animation:pulse 2.4s ease-in-out 1}
  .tabs a{transition:color .15s var(--ease)}
}
@keyframes barin{from{transform:scaleX(0)}}
@keyframes drop{from{opacity:0;transform:translateY(-8px)}}
@keyframes pulse{50%{transform:scale(1.35)}}

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
@media (max-width:720px){main{padding:14px 12px}h1{font-size:19px}header.top .who span.name,header.top .who .sep{display:none}.card{padding:12px 14px}.tile .n{font-size:22px}}
/* a laptop: with every module on, the words no longer fit; the current page keeps its word, the rest show an icon and a title */
@media (max-width:1400px){header.top nav a.top,header.top nav button.top{padding:6px 7px;font-size:13.5px}header.top nav button.top .ic.chev{display:none}}
@media (max-width:1000px){header.top nav a .lbl{display:none} header.top nav a.on .lbl{display:inline} header.top nav a .ic{margin-right:0}
  header.top nav a.on .ic{margin-right:6px}}
@media (max-width:1180px){header.top nav button.top .lbl,header.top nav a.top .lbl,header.top nav button.top .ic.chev{display:none}header.top nav button.top.on .lbl,header.top nav a.top.on .lbl{display:inline}header.top nav button.top .ic,header.top nav a.top .ic{margin-right:0}header.top nav button.top.on .ic,header.top nav a.top.on .ic{margin-right:6px}}
/* a technician's phone (gap 5, 29 Sep): one column, thumb-sized controls, the board as a list of cards, and a
   quick bar on the ticket. Nothing is a separate app; the same page reads its width and its pointer. */
.sm-only{display:none} .quick{display:none} header.top #pal-open .ic{display:none}
.md img.kbimg{display:block;max-width:100%;height:auto;margin:8px 0;border:1px solid var(--line);border-radius:var(--r)} .kbthumb{width:56px;height:42px;object-fit:cover;border-radius:6px;border:1px solid var(--line);vertical-align:middle;margin-right:6px}
@media (pointer:coarse){button,.btn,.iconbtn,select,input:not([type=checkbox]):not([type=radio]){min-height:40px}
  input[type=checkbox],input[type=radio]{width:20px;height:20px}.iconbtn{width:40px}header.top nav a{min-height:40px}}
@media (max-width:640px){
  html{-webkit-text-size-adjust:100%}input,select,textarea{font-size:16px}
  main{padding:12px 10px 84px}h1{font-size:18px;overflow-wrap:anywhere}.sub{margin-bottom:12px}
  .tiles,.tiles.six{grid-template-columns:repeat(2,1fr);gap:8px}.tile{padding:10px 12px}.tile .n{font-size:20px}
  form.toolbar{display:grid;grid-template-columns:1fr 1fr;gap:8px;align-items:end}form.toolbar>div{min-width:0}form.toolbar>div.wide{grid-column:1/-1}
  form.toolbar select,form.toolbar input{width:100%}.tablewrap>table:not(.cards){min-width:720px}.tablewrap>table:not(.cards) td{white-space:nowrap;max-width:260px;overflow:hidden;text-overflow:ellipsis}.tablewrap>table:not(.cards) td:has(form){max-width:none;overflow:visible}
  .sm-hide{display:none!important}.sm-only{display:block}
  table.grid.cards td.sum{min-width:0;white-space:normal;overflow-wrap:anywhere}table.grid td,table.grid th{padding:8px 6px}
  table.grid td.sum .meta{font-family:var(--mono);font-size:11.5px;color:var(--ink-2);margin-top:2px}
  table.grid.cards{display:block}table.grid.cards thead{display:none}table.grid.cards tbody{display:block}
  table.grid.cards tr{display:grid;grid-template-columns:24px minmax(0,1fr) auto;gap:4px 8px;align-items:start;padding:10px 8px 10px 6px;border-bottom:1px solid var(--line)}
  table.grid.cards td{display:block;padding:0;border:0;white-space:normal;width:auto}
  table.grid.cards td:first-child{grid-row:1/3;padding-left:0;width:auto}table.grid.cards td.sum{grid-column:2}
  table.grid.cards td:last-child{grid-column:2/4;padding-top:2px}table.grid.cards td:last-child .chip{margin:0 4px 4px 0}
  header.top nav a .lbl,header.top nav a.on .lbl{display:none}header.top .who .sep,header.top .who [popovertarget=keys]{display:none}
  header.top nav button.top .lbl{display:none}header.top nav button.top .ic{margin-right:0}header.top nav .panel{left:auto;right:0}
  header.top #pal-open .kbd{display:none}header.top #pal-open .ic{display:block}
  .tabs{overflow-x:auto;flex-wrap:nowrap;scrollbar-width:none}.tabs a{white-space:nowrap;padding:7px 10px}
  .hdr{flex-direction:column;gap:6px}.slastrip{grid-template-columns:1fr 1fr}.slastrip .slabox:last-child:nth-child(odd){grid-column:1/-1}
  .rail{gap:10px}.pods .card{padding:12px}.card{padding:12px}
  form.stack{max-width:none}.row>div{min-width:120px}
  .pager{justify-content:space-between;flex-wrap:wrap}.banner.toast{left:10px;right:10px;bottom:76px;max-width:none}
  .quick{display:flex;position:fixed;left:0;right:0;bottom:0;z-index:30;background:var(--glass);backdrop-filter:blur(12px);
    border-top:1px solid var(--line);padding:6px 6px calc(6px + env(safe-area-inset-bottom));justify-content:space-around}
  .quick a{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;min-width:56px;min-height:46px;
    font-size:11px;color:var(--ink-2);text-decoration:none;border-radius:var(--r)}.quick a:active{background:var(--surface-3)}
  .quick a .ic{width:20px;height:20px;stroke-width:1.9}
}
/* a phone: the nav links keep their icon and lose their words, so the header never overlaps itself (SQL01, part 15) */
@media (max-width:480px){header.top{gap:4px}header.top .brand{margin-right:4px}header.top nav a{padding:6px 8px}header.top nav a .lbl{display:none}
  header.top nav a .ic{margin-right:0}header.top nav a.on::after{left:6px;right:6px}header.top .who{gap:6px}header.top .newbtn{padding:6px 8px}}

/* the tints (8 Oct 2026; Dada: "a peach mode a purple mode and a pink mode ... there is a dark mode and
   light mode of it ... the rest of the buttons the tables and headers match"). A tint is a colour cast over
   either mode: the hues the chrome reads (--c1 --c2 --c3 the glows and rows, --ck the dark edges, --ckl the
   light edges, --lc1 --lc2 the light accents, --neon1 --neon2 the titles and the active module, --accent the
   buttons and links) change; the ink and the status colours do not. Without a tint every token holds its
   old value, so the two classic themes are untouched. */
:root[data-tint=peach]{--c2b:230 120 70;--ck0:255 190 160;--ck1:255 190 160;--ck2:255 205 180;--ck3:255 170 130;--ck4:255 170 130;--ck5:255 150 100;--ckl1:150 80 50;--lc3:#c8552c;--lc3r:200 85 44;--c1:255 150 100;--c2:240 110 80;--c3:230 120 70;--neon1:#ffb38a;--neon2:#f0705a;--teal:#f0a070;--violet:#e07a4f;
  --accent:#d9663a;--accent-2:#bf5330;--dk-accent:#ffab80;--s1:#d9663a;--s2:#f0a070;
  --ckl:150 80 50;--ckl2:230 120 70;--lc1:#c8552c;--lc1r:200 85 44;--lc2:#d9663a;--ck:255 190 160}
:root[data-tint=purple]{--c2b:124 77 219;--ck0:200 180 255;--ck1:200 180 255;--ck2:215 200 255;--ck3:180 150 255;--ck4:180 150 255;--ck5:170 120 255;--ckl1:90 60 160;--lc3:#7c4ddb;--lc3r:124 77 219;--c1:170 120 255;--c2:139 92 246;--c3:124 77 219;--neon1:#c9a2ff;--neon2:#8b5cf6;--teal:#b07ff5;--violet:#7c4ddb;
  --accent:#7c4ddb;--accent-2:#6539bf;--dk-accent:#c3a4ff;--s1:#7c4ddb;--s2:#b07ff5;
  --ckl:90 60 160;--ckl2:124 77 219;--lc1:#7c4ddb;--lc1r:124 77 219;--lc2:#6539bf;--ck:200 180 255}
:root[data-tint=pink]{--c2b:216 64 138;--ck0:255 180 215;--ck1:255 180 215;--ck2:255 200 225;--ck3:255 150 200;--ck4:255 150 200;--ck5:255 120 180;--ckl1:160 60 110;--lc3:#c7357a;--lc3r:199 53 122;--c1:255 120 180;--c2:240 96 122;--c3:216 64 138;--neon1:#ff9ecb;--neon2:#f0607a;--teal:#f58ab8;--violet:#d8408a;
  --accent:#d8408a;--accent-2:#bb2f74;--dk-accent:#ff9ccc;--s1:#d8408a;--s2:#f58ab8;
  --ckl:160 60 110;--ckl2:216 64 138;--lc1:#c7357a;--lc1r:199 53 122;--lc2:#d8408a;--ck:255 180 215}
/* light, tinted: the frost takes the colour */
:root[data-theme=light][data-tint=peach]{--thead:linear-gradient(180deg,#fbeee6,#f6e1d4);--thead-ink:#7a4a36;--canvas:#f6e6dc;--surface:#fff6f0;--surface-2:#fbeae0;--surface-3:#f3d9c9;--line:#ebcfbf;--line-2:#dbb49e;
  --glass-bg:rgb(255 246 240/.80);--glass-line:rgb(200 110 70/.18);--glow:rgb(230 120 70/.32);
  --l1:linear-gradient(180deg,#fffaf6,#fdf0e8);--l1-edge:linear-gradient(180deg,#fff,rgb(200 110 70/.22) 40%,rgb(200 110 70/.32));
  --l2-bg:rgb(255 248 243/.88);--well:#fdf1ea;--well-shadow:inset 0 1px 2px rgb(120 60 30/.10),inset 0 0 0 1px rgb(200 110 70/.20)}
:root[data-theme=light][data-tint=peach] body{background:
  radial-gradient(1100px 650px at 6% -12%,rgb(255 150 100/.40),transparent 60%),radial-gradient(900px 560px at 100% 0%,rgb(255 200 140/.36),transparent 62%),
  radial-gradient(900px 700px at 60% 120%,rgb(240 120 90/.22),transparent 60%),linear-gradient(180deg,#f9e9df,#f3dccd);background-attachment:fixed}
:root[data-theme=light][data-tint=purple]{--thead:linear-gradient(180deg,#f1ebfb,#e8def6);--thead-ink:#5a4280;--canvas:#ebe4f7;--surface:#f8f5fe;--surface-2:#efe8fa;--surface-3:#e2d8f3;--line:#d8cbee;--line-2:#c2aee3;
  --glass-bg:rgb(248 245 254/.80);--glass-line:rgb(120 80 200/.18);--glow:rgb(130 90 220/.34);
  --l1:linear-gradient(180deg,#fdfbff,#f3eefc);--l1-edge:linear-gradient(180deg,#fff,rgb(120 80 200/.22) 40%,rgb(120 80 200/.32));
  --l2-bg:rgb(250 247 255/.88);--well:#f4effc;--well-shadow:inset 0 1px 2px rgb(60 30 120/.10),inset 0 0 0 1px rgb(120 80 200/.20)}
:root[data-theme=light][data-tint=purple] body{background:
  radial-gradient(1100px 650px at 6% -12%,rgb(150 100 255/.40),transparent 60%),radial-gradient(900px 560px at 100% 0%,rgb(200 150 255/.34),transparent 62%),
  radial-gradient(900px 700px at 60% 120%,rgb(110 70 220/.24),transparent 60%),linear-gradient(180deg,#ece4f8,#e2d7f2);background-attachment:fixed}
:root[data-theme=light][data-tint=pink]{--thead:linear-gradient(180deg,#fbe9f1,#f5dce7);--thead-ink:#7d3a5c;--canvas:#f8e3ec;--surface:#fff5f9;--surface-2:#fbe8f0;--surface-3:#f3d4e2;--line:#edc9d8;--line-2:#dfa9c2;
  --glass-bg:rgb(255 245 249/.80);--glass-line:rgb(210 70 140/.18);--glow:rgb(220 80 150/.32);
  --l1:linear-gradient(180deg,#fffafc,#fdeef4);--l1-edge:linear-gradient(180deg,#fff,rgb(210 70 140/.22) 40%,rgb(210 70 140/.32));
  --l2-bg:rgb(255 247 251/.88);--well:#fcf0f5;--well-shadow:inset 0 1px 2px rgb(120 30 70/.10),inset 0 0 0 1px rgb(210 70 140/.20)}
:root[data-theme=light][data-tint=pink] body{background:
  radial-gradient(1100px 650px at 6% -12%,rgb(255 110 170/.40),transparent 60%),radial-gradient(900px 560px at 100% 0%,rgb(255 170 210/.36),transparent 62%),
  radial-gradient(900px 700px at 60% 120%,rgb(240 90 140/.22),transparent 60%),linear-gradient(180deg,#f9e4ee,#f3d6e3);background-attachment:fixed}
/* dark, tinted: the night takes the colour; cards a shade warmer or cooler than the canvas, edges lit in the tint */
:root[data-theme=dark][data-tint=peach]{--thead:linear-gradient(180deg,rgb(110 62 46/.60),rgb(70 40 30/.60));--thead-ink:#e8c3b0;--accent:var(--dk-accent);--glass-bg:rgb(44 26 20/.70);--glass-line:rgb(255 190 160/.16);--glow:rgb(255 150 100/.42);
  --l1:linear-gradient(180deg,rgb(78 46 36/.96),rgb(46 26 20/.96));--l2-bg:rgb(42 24 18/.88);--well:rgb(18 8 5/.70);
  --chip:#3a2420;--surface-2:#3b2520;--surface-3:#4a2f28;--line:#4e322a;--line-2:#6a4538}
:root[data-theme=dark][data-tint=peach] body{background:
  radial-gradient(1200px 700px at 8% -15%,rgb(255 140 90/.34),transparent 60%),radial-gradient(1000px 600px at 105% -5%,rgb(255 200 140/.18),transparent 62%),
  radial-gradient(1100px 800px at 55% 125%,rgb(230 100 70/.30),transparent 60%),radial-gradient(140% 100% at 50% 40%,transparent 50%,rgb(0 0 0/.55)),
  linear-gradient(180deg,#0c0604,#1a0d08 55%,#0e0705);background-attachment:fixed}
:root[data-theme=dark][data-tint=purple]{--thead:linear-gradient(180deg,rgb(80 56 130/.60),rgb(50 34 86/.60));--thead-ink:#cdbbee;--accent:var(--dk-accent);--glass-bg:rgb(30 20 50/.70);--glass-line:rgb(200 180 255/.16);--glow:rgb(170 120 255/.42);
  --l1:linear-gradient(180deg,rgb(56 40 92/.96),rgb(30 20 54/.96));--l2-bg:rgb(28 18 48/.88);--well:rgb(9 5 20/.70);
  --chip:#2a1f44;--surface-2:#2c2048;--surface-3:#392a5c;--line:#3e2f62;--line-2:#56427f}
:root[data-theme=dark][data-tint=purple] body{background:
  radial-gradient(1200px 700px at 8% -15%,rgb(150 100 255/.36),transparent 60%),radial-gradient(1000px 600px at 105% -5%,rgb(200 150 255/.18),transparent 62%),
  radial-gradient(1100px 800px at 55% 125%,rgb(110 70 220/.32),transparent 60%),radial-gradient(140% 100% at 50% 40%,transparent 50%,rgb(0 0 0/.55)),
  linear-gradient(180deg,#07040e,#0f0820 55%,#09051a);background-attachment:fixed}
:root[data-theme=dark][data-tint=pink]{--thead:linear-gradient(180deg,rgb(120 50 90/.60),rgb(76 30 56/.60));--thead-ink:#eebcd2;--accent:var(--dk-accent);--glass-bg:rgb(48 20 36/.70);--glass-line:rgb(255 180 215/.16);--glow:rgb(255 120 180/.42);
  --l1:linear-gradient(180deg,rgb(86 40 62/.96),rgb(50 22 38/.96));--l2-bg:rgb(46 20 34/.88);--well:rgb(20 6 14/.70);
  --chip:#3e1f30;--surface-2:#402032;--surface-3:#522a42;--line:#573047;--line-2:#78436a}
:root[data-theme=dark][data-tint=pink] body{background:
  radial-gradient(1200px 700px at 8% -15%,rgb(255 110 170/.34),transparent 60%),radial-gradient(1000px 600px at 105% -5%,rgb(255 170 210/.18),transparent 62%),
  radial-gradient(1100px 800px at 55% 125%,rgb(240 90 140/.30),transparent 60%),radial-gradient(140% 100% at 50% 40%,transparent 50%,rgb(0 0 0/.55)),
  linear-gradient(180deg,#0d0409,#1c0a14 55%,#10060c);background-attachment:fixed}

/* ---- PMC Vitals Console (14 Oct 2026, SQL01's brief: "build the chrome to PMC Vitals Console") ----
   The house design system, from its project/tokens.json (px, not the Power BI points), on the Procurement
   pages: dark chrome as the constant, white cards on canvas, Grape owns selection, every numeric column in Consolas at 13px right-aligned, uppercase only on labels and column
   headers, no icon over 16px. Scoped by body.vitals so the rest of the desk and its personal themes are
   unchanged until Dada decides otherwise. Values are the design system's tokens, swapped per theme.
   Version 7 (15 Oct 2026, Dada: "lift it"): glass - chrome.glass behind a glass-blur backdrop - on fixed
   chrome and overlays only (the top bar, the menus, the keyboard card, the scrims behind the palette and the
   viewer), never on a table, a list or a card; both fallbacks swap it for chrome.glass.solid. Three
   elevations: shadow-card at rest, shadow-raised on a hovered link card, shadow-overlay on what floats. */
body.vitals{--v-canvas:#F1F4F8;--v-surface:#FFFFFF;--v-sunken:#F7F9FB;--v-ink:#16202B;--v-muted:#5A6674;--v-rule:#D7DEE7;
  --v-accent:#6D3BD1;--v-accent2:#C24A12;--v-good:#0F7A3D;--v-warn:#A15C00;--v-bad:#C1122E;
  --v-chrome:#0E1520;--v-chrome-up:#131C29;--v-chrome-rule:#24334A;--v-on-dark:#FFFFFF;--v-on-dark-muted:#93A3B5;--v-rail-active:#1C2839;
  --v-accent-on-chrome:#A98BFF;--v-shadow:0 2px 6px rgba(22,32,43,.10);--v-shadow-raised:0 4px 12px rgba(22,32,43,.14);
  --v-shadow-overlay:0 12px 32px rgba(0,0,0,.22);--v-glass:rgba(14,21,32,.85);--v-glass-solid:#0E1520;--v-blur:12px;--glow:transparent;--hi:transparent;
  --v-sans:"Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
  --v-mono:Consolas,"Cascadia Mono","SF Mono","Courier New",monospace;
  --canvas:var(--v-canvas);--surface:var(--v-surface);--card:var(--v-surface);--surface-2:var(--v-sunken);--surface-3:var(--v-sunken);
  --ink:var(--v-ink);--ink-2:var(--v-muted);--ink-3:var(--v-muted);--muted:var(--v-muted);--line:var(--v-rule);--line-2:var(--v-rule);
  --accent:var(--v-accent);--accent-2:var(--v-accent);--on-accent:#FFFFFF;--ok:var(--v-good);--warn:var(--v-warn);--bad:var(--v-bad);
  --shadow:var(--v-shadow);--glass:var(--v-chrome);--r:8px;--r-sm:6px;--r-lg:8px;--font:var(--v-sans);--mono:var(--v-mono);
  background:var(--v-canvas) none!important;color:var(--v-ink);font:13px/20px var(--v-sans)}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]) body.vitals{--v-canvas:#0E1520;--v-surface:#131C29;--v-sunken:#182333;--v-ink:#FFFFFF;
  --v-muted:#93A3B5;--v-rule:#24334A;--v-accent:#A98BFF;--v-accent2:#FF9A62;--v-good:#3FCB86;--v-warn:#FFC14D;--v-bad:#FF6B6B;--on-accent:#0E1520;color-scheme:dark}}
:root[data-theme=dark] body.vitals{--v-canvas:#0E1520;--v-surface:#131C29;--v-sunken:#182333;--v-ink:#FFFFFF;
  --v-muted:#93A3B5;--v-rule:#24334A;--v-accent:#A98BFF;--v-accent2:#FF9A62;--v-good:#3FCB86;--v-warn:#FFC14D;--v-bad:#FF6B6B;--on-accent:#0E1520;color-scheme:dark}
/* the chrome: the top bar in chrome.glass in both themes over a 1px chrome.rule hairline */
/* !important only where the desk's own floating glass bar and glass cards set theirs that way */
body.vitals header.top{border:0!important;border-bottom:1px solid var(--v-chrome-rule)!important;
  margin:0!important;border-radius:0!important;top:0!important;box-shadow:none!important;
  --ink:var(--v-on-dark);--ink-2:var(--v-on-dark-muted);--ink-3:var(--v-on-dark-muted);--surface-3:var(--v-rail-active);--line:var(--v-chrome-rule);
  --accent:var(--v-accent-on-chrome);color:var(--v-on-dark)}
body.vitals header.top .brand{color:var(--v-on-dark);font-weight:600}
body.vitals header.top .brand i{display:none;box-shadow:none}
body.vitals header.top nav button.top.on::after{left:50%;right:auto;width:20px;margin-left:-10px;height:3px;border-radius:0;bottom:-1px;background:var(--v-accent-on-chrome)}
/* the menus hang from the bar in the same glass, so their text takes the onDark inks */
body.vitals header.top .panel{--ink:var(--v-on-dark);--ink-2:var(--v-on-dark-muted);--ink-3:var(--v-on-dark-muted);--muted:var(--v-on-dark-muted);
  --surface-3:var(--v-rail-active);--line:var(--v-chrome-rule);--accent:var(--v-accent-on-chrome);color:var(--v-on-dark);
  border:1px solid var(--v-chrome-rule)!important;box-shadow:var(--v-shadow-overlay)!important}
body.vitals header.top .panel a.on{box-shadow:inset 3px 0 0 var(--v-accent-on-chrome)}
/* glass: fixed chrome and overlays only; the solid fallback where blur is missing or unwanted */
body.vitals header.top,body.vitals header.top nav .panel,body.vitals [popover]#keys{background:var(--v-glass)!important;
  -webkit-backdrop-filter:blur(var(--v-blur))!important;backdrop-filter:blur(var(--v-blur))!important}
body.vitals dialog#pal::backdrop,body.vitals dialog.viewer::backdrop{background:var(--v-glass);-webkit-backdrop-filter:blur(var(--v-blur));backdrop-filter:blur(var(--v-blur))}
@supports not ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){
  body.vitals header.top,body.vitals header.top nav .panel,body.vitals [popover]#keys{background:var(--v-glass-solid)!important}
  body.vitals dialog#pal::backdrop,body.vitals dialog.viewer::backdrop{background:var(--v-glass-solid)}}
@media (prefers-reduced-transparency:reduce){
  body.vitals header.top,body.vitals header.top nav .panel,body.vitals [popover]#keys{background:var(--v-glass-solid)!important;
    -webkit-backdrop-filter:none!important;backdrop-filter:none!important}
  body.vitals dialog#pal::backdrop,body.vitals dialog.viewer::backdrop{background:var(--v-glass-solid);-webkit-backdrop-filter:none;backdrop-filter:none}}
body.vitals [popover]#keys{--ink:var(--v-on-dark);--ink-2:var(--v-on-dark-muted);--line-2:var(--v-chrome-rule);color:var(--v-on-dark);
  border:1px solid var(--v-chrome-rule)!important;box-shadow:var(--v-shadow-overlay)!important}
/* what floats but holds a list stays a flat surface, lifted by shadow-overlay */
body.vitals .pal-box,body.vitals .ticker .tpanel,body.vitals dialog.viewer{background:var(--v-surface)!important;border:1px solid var(--v-rule)!important;
  box-shadow:var(--v-shadow-overlay)!important;-webkit-backdrop-filter:none!important;backdrop-filter:none!important}
/* fields: flat on the surface, the focus ring the desk already draws. The edge is ink.muted, not rule: a field's edge
   is what marks it as a field, and rule measured 1.34:1 there against WCAG 1.4.11's 3:1 (job 01 review, 15 Oct);
   ink.muted is 5.85:1 on the light surface and 6.65:1 on the dark one (tokens.json). :root outranks the light
   theme's transparent field edge, which otherwise left the light Vitals fields with no edge at all. */
:root body.vitals input:not([type=checkbox]):not([type=radio]):not([type=range]),:root body.vitals select,:root body.vitals textarea{
  background-color:var(--v-surface)!important;border:1px solid var(--v-muted)!important;border-radius:6px;box-shadow:none}
:root body.vitals input:focus,:root body.vitals select:focus,:root body.vitals textarea:focus{border-color:var(--v-accent)!important;
  box-shadow:0 0 0 3px color-mix(in srgb,var(--v-accent) 30%,transparent)!important;outline:none}
:root body.vitals input:not([type=checkbox]):not([type=radio]):not([type=range]):hover:not(:focus),:root body.vitals select:hover:not(:focus),
:root body.vitals textarea:hover:not(:focus){box-shadow:none;border-color:var(--v-muted)}
body.vitals header.top::after{display:none!important}
body.vitals .pal-box input{border:0;border-bottom:1px solid var(--v-rule)}
body.vitals .ic,body.vitals svg.ic{max-width:16px;max-height:16px}
/* type: page-title 27/32 600; card titles and section labels; uppercase only on labels and column headers */
body.vitals h1{font:600 27px/32px var(--v-sans);letter-spacing:0;color:var(--v-ink)}
body.vitals h3{font:600 12px/16px var(--v-sans);letter-spacing:.06em;text-transform:uppercase;color:var(--v-muted)}
body.vitals .card,body.vitals .tile,body.vitals dialog:not(.viewer),body.vitals .slabox{background:var(--v-surface)!important;border:1px solid var(--v-rule)!important;
  border-radius:8px;box-shadow:var(--v-shadow)!important;-webkit-backdrop-filter:none!important;backdrop-filter:none!important}
body.vitals .card:hover{box-shadow:var(--v-shadow)!important}
body.vitals a.card:hover,body.vitals a.tile:hover{box-shadow:var(--v-shadow-raised)!important}
body.vitals .card,body.vitals .tile{transition:none!important}
body.vitals tr.total td:first-child b{font-family:var(--v-sans);font-weight:600}
body.vitals .card{padding:16px}
body.vitals table th{font:600 12px/16px var(--v-sans);letter-spacing:.06em;text-transform:uppercase;color:var(--v-muted)}
body.vitals table td{padding-top:6px;padding-bottom:6px}
body.vitals table tbody tr:nth-child(even){background:var(--v-sunken)}
/* every number a reader compares: Consolas, table-numeric 13/20, right-aligned, digits aligned */
body.vitals td.num,body.vitals th.num,body.vitals .num{font-family:var(--v-mono);font-size:13px;line-height:20px;text-align:right;font-variant-numeric:tabular-nums}
body.vitals th.num{font-family:var(--v-sans);font-size:12px}
body.vitals td.num b,body.vitals .tot b,body.vitals .tile .n{font-family:var(--v-mono);font-variant-numeric:tabular-nums}
body.vitals .tile .n{font-weight:700}
body.vitals .tile .l,body.vitals .tot .l,body.vitals label{font:600 12px/16px var(--v-sans);color:var(--v-muted)}
/* BETTER is a note, not a selection: ink.muted on a surface.sunken pill (Grape owns selection only) */
body.vitals .better{text-transform:uppercase;letter-spacing:.06em;background:var(--v-sunken);color:var(--v-muted);border:1px solid var(--v-rule)}
/* break-glass in status.warning - the onDark value, since the bar is chrome in both themes - not Ember */
body.vitals header.top .who .glass{color:#FFC14D}
/* no glow anywhere: the menu words take the tick, not a halo, and the bar no shadow in the light theme */
body.vitals header.top nav .top:hover,body.vitals header.top nav .top:focus-visible,body.vitals header.top nav .grp.open .top,
body.vitals header.top .newbtn,body.vitals header.top .newbtn:hover{box-shadow:none!important}
:root body.vitals header.top{box-shadow:none!important}
/* no glow on a hovered card either: the desk's themed hover ring is out; a link card lifts to shadow-raised */
:root[data-theme] body.vitals .card:hover,:root[data-theme] body.vitals .tile:hover{box-shadow:var(--v-shadow)!important}
:root[data-theme] body.vitals a.card:hover,:root[data-theme] body.vitals a.tile:hover{box-shadow:var(--v-shadow-raised)!important}
/* at 800px the menu keeps its width and the primary action its words; the account block gives way first:
   the name truncates, the gaps close, the shortcut hint goes (SQL01's review of 7d037f5) */
body.vitals header.top nav.mega{flex:1 0 auto}
body.vitals header.top nav.mega>a.newbtn{flex-shrink:0;white-space:nowrap}
body.vitals header.top .who{flex:0 1 auto;min-width:0}
body.vitals header.top .who>*{flex-shrink:0}
body.vitals header.top .who .name{flex-shrink:1;min-width:2ch;overflow:hidden;text-overflow:ellipsis}
@media (max-width:1100px){body.vitals header.top .who{gap:4px;margin-left:6px}body.vitals header.top .who .kbd,body.vitals header.top .who .sep{display:none}}
body.vitals table th{white-space:nowrap}
body.vitals .stabs a.on,body.vitals .chip.on{background:var(--v-accent);color:var(--on-accent)}
body.vitals main h1:not(.sumline){background:none!important;-webkit-background-clip:initial!important;background-clip:initial!important;
  color:var(--v-ink)!important;-webkit-text-fill-color:currentColor}
body.vitals header.top nav button.top.on,body.vitals header.top nav a.top.on{background:none!important;box-shadow:none!important;color:var(--v-on-dark)!important;font-weight:600}
body.vitals header.top nav a.top.on::after{content:"";position:absolute;left:50%;width:20px;margin-left:-10px;height:3px;bottom:-1px;background:var(--v-accent-on-chrome)}
body.vitals header.top nav a.top{position:relative}
body.vitals main button[type=submit]:not(.ghost):not(.iconbtn):not(.tab):not(.small):not(.danger),body.vitals main .btn:not(.ghost):not(.top),
body.vitals header.top .btn:not(.ghost){background:var(--v-accent)!important;background-image:none!important;color:var(--on-accent)!important;border:0!important;box-shadow:none!important;border-radius:6px}
body.vitals main button.ghost,body.vitals main .btn.ghost,body.vitals .backbtn{background:var(--v-surface)!important;background-image:none!important;
  border:1px solid var(--v-rule)!important;box-shadow:none!important;color:var(--v-ink)!important;border-radius:6px}
body.vitals .ticker{background:var(--v-chrome-up)!important;border:1px solid var(--v-chrome-rule)!important;box-shadow:none!important;border-radius:8px;
  color:var(--v-on-dark);min-height:44px;padding:6px 12px;--ink:var(--v-on-dark);--ink-2:var(--v-on-dark-muted);-webkit-backdrop-filter:none!important;backdrop-filter:none!important}
body.vitals .ticker .tlabel{font:600 13px/20px var(--v-sans);color:var(--v-on-dark)}
body.vitals .ticker .btn{font-size:13px;padding:4px 10px}
body.vitals .ticker .iconbtn{color:var(--v-on-dark-muted)}
body.vitals main::before,body.vitals::before,body.vitals::after{display:none!important}
/* the primary action never goes blank (job 02 review, 15 Oct: MEASURED at 800px, New ticket was a 24x12 pill with
   its words hidden by the nav's <=1000px rule and its plus by another): it keeps its words down to a phone, where
   the plus stands in for them and the title still names it. To make the room, the keyboard-sheet button goes below
   1000px as the 800px note above intended - the sheet still opens on ? (MEASURED: the bar overflowed 800px by 25px) */
@media (max-width:1000px){header.top nav a.newbtn .lbl,header.top nav a.newbtn.on .lbl{display:inline}
  header.top .who [popovertarget=keys]{display:none}}
@media (max-width:480px){header.top nav a.newbtn .lbl,header.top nav a.newbtn.on .lbl{display:none}
  header.top nav a.newbtn svg.ic{display:inline-block}}
/* the error page: the same card, the code small and muted, the sentence, a way back */
body.vitals .errpage{max-width:560px;margin:clamp(24px,8vh,80px) auto 32px;display:flex;flex-direction:column;gap:8px}
body.vitals .errpage .errcode{margin:0;font:600 12px/16px var(--v-mono);letter-spacing:.06em;color:var(--v-muted)}
body.vitals .errpage h1,body.vitals .errpage p{margin:0}
body.vitals .errpage .errback{margin-top:8px}
/* the sign-in page: one card on the canvas under the glass bar; the break-glass note in status.warning */
body.vitals .signin{display:flex;justify-content:center;padding-block:clamp(24px,10vh,96px) 32px}
body.vitals .signcard{width:min(400px,100%);padding:28px 28px 20px!important;display:flex;flex-direction:column;gap:12px}
body.vitals .signcard h1{margin:0}
body.vitals .signcard .sub{margin:0;color:var(--v-muted)}
body.vitals .signcard .glassnote{color:var(--v-warn);font-weight:600}
body.vitals .signcard form.stack{display:flex;flex-direction:column;gap:14px;margin:4px 0 0}
body.vitals .signcard .field{display:flex;flex-direction:column;gap:6px}
body.vitals .signcard .field label{color:var(--v-ink)}
body.vitals .signcard input{width:100%;min-height:36px;font:14px/20px var(--v-sans)}
body.vitals .signcard button[type=submit],body.vitals .signcard .btn.wide{width:100%;min-height:36px;justify-content:center;font-weight:600}
body.vitals .signcard .or{display:flex;align-items:center;gap:10px;margin:2px 0;color:var(--v-muted);font-size:12px}
body.vitals .signcard .or::before,body.vitals .signcard .or::after{content:"";flex:1;border-top:1px solid var(--v-rule)}
body.vitals .signcard .alt{margin:4px 0 0;padding-top:12px;border-top:1px solid var(--v-rule);font-size:12px;text-align:center}
body.vitals .signcard .alt a{color:var(--v-muted);display:inline-block;min-height:24px;line-height:24px}
body.vitals .signcard .banner.err{margin:0}
""".replace("DARKTOKENS", """
  --canvas:#080b14; --surface:#0f1320; --surface-2:#141a29; --surface-3:#1b2234;
  --ink:#eef1f8; --ink-2:#b0b8c9; --ink-3:#7f889b; --line:#1e2638; --line-2:#2b3551;
  --accent:#7f8cff; --accent-2:#9aa6ff; --on-accent:#0b1020;
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
var TINTS=["peach","purple","pink"];
function setTheme(t){try{if(t)localStorage.setItem("psa-theme",t);else localStorage.removeItem("psa-theme")}catch(e){}
  if(t)root.dataset.theme=t;else delete root.dataset.theme}
function setTint(c){if(TINTS.indexOf(c)<0)c="";try{if(c)localStorage.setItem("psa-tint",c);else localStorage.removeItem("psa-tint")}catch(e){}
  if(c)root.dataset.tint=c;else delete root.dataset.tint}
function curTheme(){return root.dataset.theme||(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light")}
function toggleTheme(){setTheme(curTheme()==="dark"?"light":"dark")}
/* the theme menu (8 Oct 2026): a mode, dark or light, and a colour, classic, peach, purple or pink; each colour has both modes.
   Escape or a click away closes it; t still flips the mode and keeps the colour */
var tb=$("#theme"),tm=null;function closeTheme(){if(tm){tm.remove();tm=null;if(tb)tb.setAttribute("aria-expanded","false")}}
function themeMenu(){var m=d.createElement("div");m.className="thememenu";m.setAttribute("role","menu");
  function head(t){var h=d.createElement("h5");h.textContent=t;m.appendChild(h)}
  function item(key,label,on,fn){var b=d.createElement("button");b.type="button";b.dataset.theme=key;if(on)b.className="on";
    var sw=d.createElement("i");sw.className="sw "+key;b.appendChild(sw);b.appendChild(d.createTextNode(label));
    b.addEventListener("click",function(){fn();paint()});m.appendChild(b)}
  function paint(){$$("button",m).forEach(function(b){var k=b.dataset.theme;b.classList.toggle("on",k===curTheme()||k===(root.dataset.tint||"classic"))})}
  head("Mode");item("dark","Dark",curTheme()==="dark",function(){setTheme("dark")});item("light","Light",curTheme()==="light",function(){setTheme("light")});
  head("Colour");var cur=root.dataset.tint||"classic";
  [["classic","Classic"],["peach","Peach"],["purple","Purple"],["pink","Pink"]].forEach(function(o){item(o[0],o[1],cur===o[0],function(){setTint(o[0]==="classic"?"":o[0])})});
  return m}
if(tb)tb.addEventListener("click",function(e){e.stopPropagation();if(tm){closeTheme();return}var m=themeMenu();
  var r=tb.getBoundingClientRect();m.style.top=(r.bottom+window.scrollY+6)+"px";m.style.left=Math.max(8,r.right+window.scrollX-190)+"px";
  d.body.appendChild(m);tm=m;tb.setAttribute("aria-expanded","true");var f=m.querySelector("button.on")||m.querySelector("button");if(f)f.focus()});
d.addEventListener("click",function(e){if(tm&&!tm.contains(e.target))closeTheme()});d.addEventListener("keydown",function(e){if(e.key==="Escape")closeTheme()});
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
var pages=[["Service Board","/","g b"],["Dispatch","/dispatch","g d"],["Schedule","/schedule",""],["Timesheets","/time",""],["Companies","/companies","g c"],["On-call","/oncall",""],["Setup","/admin","g s"],["My requests","/my",""],["New ticket","/ticket/new","n"]];
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
/* pods: every card on the ticket sits in one of two columns; drag it to either column (or use the
   arrows: up, down, and across), fold it, and this browser remembers. Reset restores the shipped layout. */
(function(){var cols=$$(".rail .pods");if(!cols.length)return;var KEY="psa-pods";
  function state(){var st;try{st=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){st={}}
    if(!st.cols&&st.order){st.cols={right:st.order};delete st.order}      /* the one-column layout of before: that was the right column */
    st.cols=st.cols||{};st.folded=st.folded||{};st.sizes=st.sizes||{};st.hidden=st.hidden||{};st.heights=st.heights||{};return st}
  var SIZES=["full","m","half","s"],SIZEWORD={full:"Full width",m:"Medium (two thirds)",half:"Half",s:"Small (a third)"};
  function sizeOf(p){return SIZES.filter(function(z){return z!=="full"&&p.classList.contains("sz-"+z)})[0]||"full"}
  function setSize(p,z){SIZES.forEach(function(x){p.classList.remove("sz-"+x)});if(z!=="full")p.classList.add("sz-"+z);
    var b=$(".size",p);if(b){b.title="Size: "+SIZEWORD[z]+" (click for the next)";b.setAttribute("aria-label",b.title);$(".szw",b).textContent={full:"F",m:"M",half:"½",s:"S"}[z]}}
  function save(st){try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}}
  function colOf(name){return cols.filter(function(c){return c.dataset.col===name})[0]}
  function pods(c){return $$(".card[data-pod]",c)}
  function all(){return cols.reduce(function(a,c){return a.concat(pods(c))},[])}
  function byKey(k){return all().filter(function(c){return c.dataset.pod===k})[0]}
  function ic(n){return '<svg class=ic aria-hidden=true><use href=#i-'+n+'></use></svg>'}
  function customised(st){return Object.keys(st.folded).length>0||Object.keys(st.sizes).length>0||Object.keys(st.hidden).length>0||Object.keys(st.heights).length>0||cols.some(function(c){var want=(st.cols[c.dataset.col]||[]).join(),
    shipped=(c.dataset.order||"").split(",").filter(function(k){return byKey(k)}).join();return want&&want!==shipped})}
  /* Hold the reader's place. Moving a card in the DOM is what a re-order IS,
     but the browser cannot anchor a scroll to a node that moves, so the page
     jumped to the top on every fold, resize and height bump (MEASURED in
     Chromium, 3 Oct 2026: scrollY 294 -> 0 on one click). Worse, re-appending
     a card closes any native dropdown inside it, which is why the selects
     "broke" while the pods were being edited. So: move nothing that is already
     where it belongs, and when something must move, put the view back where
     the person left it -- anchored on the card they are editing, so it stays
     under the pointer even if what is above it changed height. */
  function jump(to){
    /* INSTANT, never smooth. The stylesheet asks for smooth scrolling, which is
       right when a person clicks a link and wrong here: an animated restore
       glides the page while the layout is still settling, and scrollY read
       mid-flight is not where the page will land. That is what made a pod edit
       "re-orient" and drift (MEASURED in Chromium, 3 Oct 2026: a single click
       logged an animation climbing 294, 340, 385 ... and ending at 52). */
    var was=root.style.scrollBehavior;root.style.scrollBehavior="auto";
    try{window.scrollTo({top:to,left:0,behavior:"instant"})}catch(e){window.scrollTo(0,to)}
    root.style.scrollBehavior=was}
  /* Two kinds of hold, and the difference matters.
     An IN-PLACE change -- fold, resize, a height bump -- may change the height
     of things above the card, so the card is the anchor: it stays under the
     eye that is editing it.
     A REORDER -- the arrows, the swap, a drag -- moves the card ON PURPOSE,
     and chasing it is wrong: a card sent to the top of its column would drag
     the whole page to the top with it (MEASURED in Chromium, 3 Oct 2026:
     scrollY 700 -> 0 on one Move up). There the viewport is the anchor; the
     card moves and the page does not. Pass null for that. */
  function hold(anchor,fn){
    var y=window.scrollY||window.pageYOffset;
    var top=anchor&&anchor.getBoundingClientRect?anchor.getBoundingClientRect().top:null;
    fn();
    if(top!==null&&anchor.getBoundingClientRect){
      var now=anchor.getBoundingClientRect().top;
      if(Math.abs(now-top)>0.5)jump((window.scrollY||window.pageYOffset)+(now-top));
      /* The card is the anchor, so the card staying put is the whole job. If the
         browser's own scroll anchoring already held it (scrollY moved, the card did
         not), putting the old scrollY back would undo that and move the card
         (MEASURED in Chromium, 7 Oct 2026: the Reset layout bar appearing above
         the pods moved a card 52px). */
      return}
    if((window.scrollY||window.pageYOffset)!==y)jump(y)}
  function apply(){var st=state();
    /* a card only crosses columns when it is actually in the wrong one */
    cols.forEach(function(c){(st.cols[c.dataset.col]||[]).forEach(function(k){var p=byKey(k);
      if(p&&p.parentNode!==c)c.appendChild(p)})});
    /* and within a column, nothing is touched unless the order really differs.
       A card the saved layout does not name stays where the server put it,
       after the named ones. */
    cols.forEach(function(c){
      var names=(st.cols[c.dataset.col]||[]);
      var want=names.map(byKey).filter(function(p){return p&&p.parentNode===c});
      var cur=pods(c);
      var rest=cur.filter(function(p){return want.indexOf(p)<0});
      var order=want.concat(rest);
      var same=order.length===cur.length&&order.every(function(p,i){return p===cur[i]});
      if(!same)order.forEach(function(p){c.appendChild(p)})});
    all().forEach(function(p){p.classList.toggle("collapsed",!!st.folded[p.dataset.pod]);setSize(p,st.sizes[p.dataset.pod]||"full");
      p.classList.toggle("hidden",!!st.hidden[p.dataset.pod]);var pb=$(":scope>.podbody",p);if(pb)pb.style.height=st.heights[p.dataset.pod]?st.heights[p.dataset.pod]+"px":"";
      var sw=$(".swap",p);if(sw){var here=p.parentNode.dataset.col,to=here==="left"?"right":"left";$("use",sw).setAttribute("href","#i-"+to);
        sw.title="Move to the "+to+" column";sw.setAttribute("aria-label",sw.title)}});
    cols.forEach(function(c){c.classList.toggle("blank",pods(c).length===0)});
    var r=$(".podreset");if(r)r.style.display=customised(st)?"":"none"}
  function remember(anchor){var st=state();st.cols={};cols.forEach(function(c){st.cols[c.dataset.col]=pods(c).map(function(p){return p.dataset.pod})});
    st.folded={};all().forEach(function(p){if(p.classList.contains("collapsed"))st.folded[p.dataset.pod]=1});
    st.sizes={};all().forEach(function(p){var z=sizeOf(p);if(z!=="full")st.sizes[p.dataset.pod]=z});
    st.hidden={};all().forEach(function(p){if(p.classList.contains("hidden"))st.hidden[p.dataset.pod]=1});
    st.heights={};all().forEach(function(p){var pb=$(":scope>.podbody",p),h=pb&&parseInt(pb.style.height,10);if(h)st.heights[p.dataset.pod]=h});
    save(st);hold(anchor,apply)}
  function dropInto(from,target,before){if(!from||from===before)return;
    hold(null,function(){if(before)target.insertBefore(from,before);else target.appendChild(from)});remember(null)}
  all().forEach(function(c){var h3=$(":scope>h3",c);if(h3&&!$(":scope>.podbody",c)){var pb=d.createElement("div");pb.className="podbody";
    Array.prototype.slice.call(c.childNodes).forEach(function(n){if(n!==h3&&!(n.classList&&n.classList.contains("podctl")))pb.appendChild(n)});c.appendChild(pb);
    pb.addEventListener("mouseup",function(){if(pb.style.height)setTimeout(function(){remember(c)},0)})}});
  all().forEach(function(c){var h=$("h3",c);if(!h)return;
    /* not draggable at rest: see the note in the stylesheet. The heading is the handle. */
    c.draggable=false;
    h.addEventListener("mousedown",function(){if(root.classList.contains("layedit"))c.draggable=true});
    d.addEventListener("mouseup",function(){c.draggable=false});
    c.addEventListener("dragend",function(){c.draggable=false});
    var ctl=d.createElement("span");ctl.className="podctl";
    ctl.innerHTML='<button type=button class="iconbtn mv" data-dir=-1 title="Move up" aria-label="Move up">'+ic("up")+'</button>'
      +'<button type=button class="iconbtn mv" data-dir=1 title="Move down" aria-label="Move down">'+ic("down")+'</button>'
      +'<button type=button class="iconbtn swap" title="Move to the other column" aria-label="Move to the other column">'+ic("right")+'</button>'
      +'<button type=button class="iconbtn hless" title="Shorter (the rest scrolls inside)" aria-label="Shorter">'+ic("minus")+'</button>'
      +'<button type=button class="iconbtn hmore" title="Taller" aria-label="Taller">'+ic("plus")+'</button>'
      +'<button type=button class="iconbtn size" title="Size" aria-label="Size"><b class=szw>F</b></button>'
      +'<button type=button class="iconbtn fold" title="Fold" aria-label="Fold or unfold" aria-expanded=true>'+ic("chevron")+'</button>';
    c.appendChild(ctl);
    $(".size",ctl).addEventListener("click",function(){var i=SIZES.indexOf(sizeOf(c));
      hold(c,function(){setSize(c,SIZES[(i+1)%SIZES.length])});remember(c)});
    /* the reference PSA's plus and minus on a pod: the height in steps of 80px, from where it stands; below 48px it is as good as folded */
    var STEP=80;function bump(dir){var pb=$(":scope>.podbody",c);if(!pb)return;var h=parseInt(pb.style.height,10)||pb.getBoundingClientRect().height;
      h=Math.max(48,Math.round(h+dir*STEP));pb.style.height=h+"px";remember(c)}
    $(".hless",ctl).addEventListener("click",function(){bump(-1)});$(".hmore",ctl).addEventListener("click",function(){bump(1)});
    $(".fold",ctl).addEventListener("click",function(){var b=this;
      hold(c,function(){c.classList.toggle("collapsed");
        b.setAttribute("aria-expanded",String(!c.classList.contains("collapsed")))});remember(c)});
    $(".swap",ctl).addEventListener("click",function(){var here=c.parentNode.dataset.col,other=colOf(here==="left"?"right":"left");if(other)dropInto(c,other,null)});
    $$(".mv",ctl).forEach(function(b){b.addEventListener("click",function(){var dir=+b.dataset.dir,col=c.parentNode,list=pods(col),i=list.indexOf(c),j=i+dir;
      if(j<0||j>=list.length)return;
      hold(null,function(){col.insertBefore(c,dir<0?list[j]:list[j].nextSibling)});remember(null)})});
    c.addEventListener("dragstart",function(e){c.classList.add("dragging");e.dataTransfer.effectAllowed="move";e.dataTransfer.setData("text/plain",c.dataset.pod)});
    c.addEventListener("dragend",function(){c.classList.remove("dragging");all().forEach(function(x){x.classList.remove("over")});cols.forEach(function(x){x.classList.remove("over-col")})});
    c.addEventListener("dragover",function(e){e.preventDefault();e.stopPropagation();e.dataTransfer.dropEffect="move";c.classList.add("over")});
    c.addEventListener("dragleave",function(){c.classList.remove("over")});
    c.addEventListener("drop",function(e){e.preventDefault();e.stopPropagation();dropInto(byKey(e.dataTransfer.getData("text/plain")),c.parentNode,c)})});
  cols.forEach(function(col){
    col.addEventListener("dragover",function(e){e.preventDefault();e.dataTransfer.dropEffect="move";col.classList.add("over-col")});
    col.addEventListener("dragleave",function(e){if(!col.contains(e.relatedTarget))col.classList.remove("over-col")});
    col.addEventListener("drop",function(e){e.preventDefault();col.classList.remove("over-col");dropInto(byKey(e.dataTransfer.getData("text/plain")),col,null)})});
  var rail=cols[0].parentNode,reset=d.createElement("div");reset.className="podreset";reset.innerHTML='<button type=button class=ghost>Reset layout</button>';
  reset.style.display="none";reset.style.gridColumn="1/-1";rail.insertBefore(reset,rail.firstChild);
  var dlg=$("#poddlg");if(dlg){
    function fill(){var on=$("[data-list=on]",dlg),off=$("[data-list=off]",dlg);on.innerHTML="";off.innerHTML="";
      all().forEach(function(p){var li=d.createElement("li");li.dataset.pod=p.dataset.pod;var nm=$("h3",p)?$("h3",p).textContent.trim():p.dataset.pod;
        var hid=p.classList.contains("hidden");
        li.innerHTML='<input type=checkbox '+(hid?"":"checked")+' aria-label="Show '+nm.replace(/"/g,"")+'"><span class=nm>'+nm.replace(/[<>&]/g,"")+'</span>'
          +(hid?"":'<button type=button class="iconbtn up" title="Up">'+ic("up")+'</button><button type=button class="iconbtn dn" title="Down">'+ic("down")+'</button>');
        (hid?off:on).appendChild(li)})}
    dlg.addEventListener("click",function(e){var b=e.target.closest("button");if(!b)return;var li=b.closest("li");
      if(b.classList.contains("up")&&li&&li.previousElementSibling)li.parentNode.insertBefore(li,li.previousElementSibling);
      else if(b.classList.contains("dn")&&li&&li.nextElementSibling)li.parentNode.insertBefore(li.nextElementSibling,li);
      else if(b.classList.contains("podsave")){var seen={};
        $$("li",dlg).forEach(function(l){var p=byKey(l.dataset.pod);if(!p)return;p.classList.toggle("hidden",!$("input",l).checked)});
        /* the Displayed order becomes the order within each column */
        cols.forEach(function(c){$$("li",$("[data-list=on]",dlg)).forEach(function(l){var p=byKey(l.dataset.pod);if(p&&p.parentNode===c)c.appendChild(p)});
          pods(c).filter(function(p){return p.classList.contains("hidden")}).forEach(function(p){c.appendChild(p)})});
        remember();dlg.close()}
      else if(b.classList.contains("podreset-all")){$("button",reset).click();dlg.close()}});
    dlg.addEventListener("change",function(e){if(e.target.type==="checkbox"){var li=e.target.closest("li"),p=byKey(li.dataset.pod);if(p){p.classList.toggle("hidden",!e.target.checked);fill()}}});
    d.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("[data-open=poddlg]");if(b)fill()},true)}
  $("button",reset).addEventListener("click",function(){save({});all().forEach(function(c){c.classList.remove("collapsed","hidden");setSize(c,"full");var pb=$(":scope>.podbody",c);if(pb)pb.style.height=""});
    cols.forEach(function(c){(c.dataset.order||"").split(",").forEach(function(k){var p=byKey(k);if(p)c.appendChild(p)})});apply()});
  apply()})();
/* Type, then Subtype, then Item. The third select is the answer and the only
   one with a name; these two narrow what it offers. Every choice comes from an
   option the server sent, read off its own data attributes, so this can never
   offer a pair the catalogue does not hold. With no script the third select is
   the whole picker, grouped and labelled in full, as it was before. */
(function(){
function fill(sel,list,blank){
  while(sel.firstChild)sel.removeChild(sel.firstChild);
  var o=d.createElement("option");o.value="";o.textContent=blank;sel.appendChild(o);
  list.forEach(function(x){var e=d.createElement("option");e.value=x.v;e.textContent=x.t;sel.appendChild(e)})}
function uniq(rows,key){var seen={},out=[];rows.forEach(function(r){if(!seen[r[key]]){seen[r[key]]=1;out.push(r[key])}});return out}
$$("select.cat-item").forEach(function(item){
  var box=item.closest("form")||d,ts=$(".cat-type",box),ss=$(".cat-sub",box);
  if(!ts||!ss)return;
  var all=[];
  $$("option",item).forEach(function(o){
    if(!o.value)return;
    all.push({v:o.value,f:o.dataset.f||"",s:o.dataset.s||"",i:o.dataset.i||o.textContent,t:o.textContent})});
  if(!all.length)return;
  function showItems(){
    var f=ts.value,sub=ss.value,was=item.value;
    var rows=all.filter(function(r){return(!f||r.f===f)&&(!sub||r.s===sub)});
    fill(item,rows.map(function(r){return{v:r.v,t:(f&&sub)?r.i:r.t}}),"(not classified)");
    item.value=rows.some(function(r){return r.v===was})?was:""}
  function showSubs(keep){
    var f=ts.value,rows=all.filter(function(r){return!f||r.f===f});
    var was=ss.value;
    fill(ss,uniq(rows,"s").map(function(x){return{v:x,t:x}}),f?"(any subtype)":"(pick a type first)");
    ss.value=(keep&&rows.some(function(r){return r.s===was}))?was:"";
    showItems()}
  fill(ts,uniq(all,"f").map(function(x){return{v:x,t:x}}),"(any type)");
  var cur=all.filter(function(r){return r.v===item.value})[0];
  if(cur){ts.value=cur.f;showSubs(false);ss.value=cur.s;showItems();item.value=cur.v}
  else showSubs(false);
  ts.addEventListener("change",function(){showSubs(false)});
  ss.addEventListener("change",showItems);
  if(item.required){ts.required=true;ss.required=true}
  ts.hidden=false;ss.hidden=false})})();
/* One Save, always reachable. The ticket's own fields are already one form;
   this only makes its Save impossible to lose behind a scroll, and names how
   many changes are waiting so nobody saves wondering what they changed.
   Discard reloads the page, which is the honest undo: whatever is stored is
   what comes back. */
(function(){var f=$("form[data-savebar]");if(!f)return;
var bar=null,label=null;
/* What "changed" means, per kind of control. A select has no defaultValue, so
   comparing to one counted every select on the page as changed and the bar
   read "9 changes not saved" for a single edit (MEASURED in Chromium, 3 Oct
   2026). A select's own mark is the option the server sent as selected. */
function moved(el){
  if(el.type==="checkbox"||el.type==="radio")return el.checked!==el.defaultChecked;
  if(el.tagName==="SELECT"){
    var o=el.options[el.selectedIndex];
    return !!o&&!o.defaultSelected;
  }
  return el.value!==el.defaultValue}
function changed(){var n=0;
  $$("input,select,textarea",f).forEach(function(el){
    if(el.type==="hidden"||el.disabled||!el.name)return;
    if(moved(el))n++});
  return n}
function build(){if(bar)return bar;
  bar=d.createElement("div");bar.className="savebar";bar.setAttribute("role","status");
  label=d.createElement("b");bar.appendChild(label);
  var save=d.createElement("button");save.type="submit";save.textContent="Save changes";
  save.setAttribute("form",f.id||(f.id="ticketfields"));bar.appendChild(save);
  var undo=d.createElement("button");undo.type="button";undo.className="ghost";
  undo.textContent="Discard";undo.addEventListener("click",function(){location.reload()});
  bar.appendChild(undo);
  d.body.appendChild(bar);return bar}
function show(){var n=changed();
  if(!n){if(bar)bar.classList.remove("up");return}
  build();label.textContent=n===1?"1 change not saved":n+" changes not saved";
  bar.classList.add("up")}
f.addEventListener("input",show);f.addEventListener("change",show);
f.addEventListener("submit",function(){if(bar)bar.classList.remove("up")})})();
/* The stopwatch counts in front of the person it belongs to (065). The server
   sends the seconds it had when the page was drawn; this only paints the one
   that is running, so a reload and a tick never disagree about the total. */
(function(){var els=$$("b.tick[data-run]");if(!els.length)return;
var n=+els[0].dataset.tick||0;
function paint(){var h=Math.floor(n/3600),m=Math.floor(n%3600/60),s=n%60,txt=h+":"+String(m).padStart(2,"0")+":"+String(s).padStart(2,"0");
  els.forEach(function(el){el.textContent=txt})}
setInterval(function(){n++;paint()},1000);paint()})();
/* The time entry window: Close keeps the clock running; a window asked for
   by Start opens by itself; End empty means "now" on Save. */
$$("[data-close]").forEach(function(b){var dl=d.getElementById(b.dataset.close);if(dl)b.addEventListener("click",function(){dl.close()})});
/* The board's numbers count up once on arrival; skipped for reduced motion. */
(function(){if(!window.matchMedia||matchMedia("(prefers-reduced-motion: reduce)").matches||!window.requestAnimationFrame)return;
  $$(".tile .n").forEach(function(el){var to=parseInt(el.textContent,10);if(!(to>1)||to>9999||String(to)!==el.textContent.trim())return;
    var t0=null;function step(t){if(t0===null)t0=t;var k=Math.min(1,(t-t0)/500),e=1-Math.pow(1-k,3);el.textContent=String(Math.round(to*e));
      if(k<1)requestAnimationFrame(step)}el.textContent="0";requestAnimationFrame(step)})})();
/* A link to a window (the phone's quick bar "Note" is #composer) opens it. */
d.addEventListener("click",function(e){var a=e.target.closest&&e.target.closest("a[href*='#']");if(!a)return;
  var id=a.getAttribute("href").split("#")[1],dl=id&&d.getElementById(id);
  if(dl&&dl.tagName==="DIALOG"&&dl.showModal&&a.pathname===location.pathname){e.preventDefault();dl.showModal()}});
(function(){var id=location.hash.slice(1),dl=id&&d.getElementById(id);if(dl&&dl.tagName==="DIALOG"&&dl.showModal)dl.showModal()})();
/* Actual hours follows Start and End as they are typed, as the reference PSA's time entry does (Dada, 7 Oct 2026:
   2 h beside 09:30-11:30 was refused as "not both"); the desk reads the span when both are given. */
$$(".timefields").forEach(function(tf){var q=function(n){return tf.querySelector("[name$='"+n+"']")};
  var st=q("start"),en=q("end"),hr=q("hours"),de=q("deduct");if(!st||!en||!hr)return;
  function fill(){if(!st.value||!en.value)return;var a=st.value.split(":"),b=en.value.split(":");
    var m=(+b[0]*60+ +b[1])-(+a[0]*60+ +a[1]);if(m<=0)return;
    var h=m/60-(parseFloat(de&&de.value)||0);hr.value=h>0?String(Math.round(h*100)/100):""}
  [st,en,de].forEach(function(x){if(x)x.addEventListener("input",fill)});fill()});
/* Move the window by its title bar; the corner resizes it (CSS resize);
   the square makes it fill the screen and back. */
(function(){$$("dialog.tedlg").forEach(function(dl){var bar=dl.querySelector("[data-drag]");if(!bar)return;
  bar.addEventListener("pointerdown",function(e){if(e.button!==0||e.target.closest("button,a,input,select"))return;
    if(dl.classList.contains("max"))return;
    var r=dl.getBoundingClientRect(),dx=e.clientX-r.left,dy=e.clientY-r.top;
    dl.classList.add("moved");dl.style.left=r.left+"px";dl.style.top=r.top+"px";dl.style.right="auto";dl.style.bottom="auto";
    bar.setPointerCapture(e.pointerId);
    function mv(ev){var x=Math.max(0,Math.min(innerWidth-80,ev.clientX-dx)),y=Math.max(0,Math.min(innerHeight-60,ev.clientY-dy));
      dl.style.left=x+"px";dl.style.top=y+"px"}
    function up(){bar.removeEventListener("pointermove",mv);bar.removeEventListener("pointerup",up)}
    bar.addEventListener("pointermove",mv);bar.addEventListener("pointerup",up)});
  var mx=dl.querySelector("[data-max]");if(mx)mx.addEventListener("click",function(){dl.classList.toggle("max")})})})();
(function(){var dl=d.getElementById("tedlg");if(!dl||!dl.showModal)return;
  if(dl.hasAttribute("data-autoopen")){dl.showModal();var ed=dl.querySelector(".editor");if(ed)setTimeout(function(){ed.focus()},60);
    try{var u=new URL(location.href);u.searchParams.delete("te");u.searchParams.delete("msg");history.replaceState(null,"",u.pathname+u.search)}catch(e){}}})();
/* A visit's To follows its From. Moving the start of a visit and leaving the
   end behind it is how a form ends up refusing to submit with nothing said;
   the end keeps whatever length the person had set, and an end they have
   dragged out themselves is never shortened. */
d.addEventListener("change",function(e){
  var from=e.target;if(!from||from.name!=="starts_at"||from.type!=="datetime-local")return;
  var f=from.form;if(!f)return;var to=f.querySelector("input[name=ends_at]");if(!to)return;
  var a=new Date(from.value),b=new Date(to.value);
  if(isNaN(a))return;
  var span=(!isNaN(b)&&b>a)?0:(from.dataset.span?+from.dataset.span:3600000);
  if(!isNaN(b)&&b>a)return;                       /* already sound: leave it */
  var end=new Date(a.getTime()+(span||3600000));
  var p=function(n){return String(n).padStart(2,"0")};
  to.value=end.getFullYear()+"-"+p(end.getMonth()+1)+"-"+p(end.getDate())+
           "T"+p(end.getHours())+":"+p(end.getMinutes())});
/* Text size: the three the reader can choose between, kept in this browser. */
(function(){var KEY="psa-text",SIZES=["s","","l"],NAMES={s:"Small","":"Normal",l:"Large"};
function get(){try{return localStorage.getItem(KEY)||""}catch(e){return ""}}
function put(v){try{v?localStorage.setItem(KEY,v):localStorage.removeItem(KEY)}catch(e){}}
function show(v){if(v)root.dataset.text=v;else root.removeAttribute("data-text");
  var b=d.getElementById("textsize");if(b){b.title="Text size: "+NAMES[v]+" (click for the next)";b.setAttribute("aria-label",b.title)}}
show(get());
d.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("#textsize");if(!b)return;
  var i=SIZES.indexOf(get());var next=SIZES[(i+1)%SIZES.length];put(next);show(next)})})();

/* Edit layout: the cards sit still until this is on (the reference PSA's own shape). */
(function(){function off(){root.classList.remove("layedit");var n=$(".layedit-on");if(n)n.parentNode.removeChild(n);
  $$("[data-layedit]").forEach(function(b){b.classList.remove("on");b.setAttribute("aria-pressed","false")})}
d.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("[data-layedit]");
  if(b){if(root.classList.contains("layedit")){off();return}
    root.classList.add("layedit");b.classList.add("on");b.setAttribute("aria-pressed","true");
    var bar=d.createElement("div");bar.className="layedit-on";
    bar.innerHTML='Moving cards: drag a heading, or use its arrows. <button type=button>Done</button>';
    bar.querySelector("button").addEventListener("click",off);d.body.appendChild(bar);return}
  if(root.classList.contains("layedit")&&e.target.closest&&e.target.closest(".layedit-on"))return});
d.addEventListener("keydown",function(e){if(e.key==="Escape"&&root.classList.contains("layedit"))off()})})();

/* The note editor (064). A technician writes the way they write a Teams
   message, and pastes out of Outlook or Word. What is typed goes up in the
   form's own textarea, so a browser with no JavaScript still works and still
   submits; what the server stores is rebuilt by richtext.clean whatever
   arrives, so nothing here is a gate, only a convenience. */
(function(){
var KEEP={B:1,STRONG:1,I:1,EM:1,U:1,S:1,STRIKE:1,DEL:1,CODE:1,BR:1,A:1,P:1,DIV:1,UL:1,OL:1,LI:1,BLOCKQUOTE:1,PRE:1,H3:1,H4:1};
var SAME={STRONG:"B",EM:"I",STRIKE:"S",DEL:"S",DIV:"P",H1:"H3",H2:"H3",H5:"H4",H6:"H4"};
/* A paste is rebuilt the same way the server rebuilds it: nodes are made here,
   never a string of HTML parsed, and only these tags are made at all. */
function rebuild(node,into){
  for(var n=node.firstChild;n;n=n.nextSibling){
    if(n.nodeType===3){into.appendChild(d.createTextNode(n.nodeValue));continue}
    if(n.nodeType!==1)continue;
    var tag=SAME[n.tagName]||n.tagName;
    if(tag==="SCRIPT"||tag==="STYLE"||tag==="TITLE")continue;
    if(tag==="BR"){into.appendChild(d.createElement("br"));continue}
    /* the desk's own marks survive (a kept draft, or a paste from another note): only the classes
       the server's NOTE_SPAN / NOTE_MARK allow, never a style */
    if(tag==="SPAN"||tag==="MARK"){var ok=(n.className||"").split(/\s+/).filter(function(c){return tag==="MARK"?
        /^hl-(yellow|green|blue|pink)$/.test(c):/^(tc-(red|orange|green|blue|purple|grey)|fs-(s|l|xl))$/.test(c)});
      if(ok.length){var mk=d.createElement(tag.toLowerCase());mk.className=ok.join(" ");rebuild(n,mk);into.appendChild(mk);continue}}
    if(!KEEP[tag]){rebuild(n,into);continue}
    var el=d.createElement(tag.toLowerCase());
    if(tag==="A"){var h=n.getAttribute("href")||"";if(!/^(https?:\/\/|mailto:)/i.test(h)){rebuild(n,into);continue}
      el.href=h;el.target="_blank";el.rel="noopener noreferrer"}
    rebuild(n,el);into.appendChild(el)}
  return into}
/* What the browser's own commands write -- <font color>, <font size>, a span
   with a background -- becomes the desk's fixed classes before it is sent, so
   the server never sees a colour it did not offer (richtext NOTE_SPAN/MARK). */
var TC={"#c62828":"tc-red","#c25e00":"tc-orange","#1a7f37":"tc-green","#2f52c4":"tc-blue","#7b3fbf":"tc-purple","#6b7280":"tc-grey"};
var HL={"#fff3a3":"hl-yellow","#c9f2d4":"hl-green","#cfe3ff":"hl-blue","#ffd6e8":"hl-pink"};
var FS={"1":"fs-s","2":"fs-s","4":"fs-l","5":"fs-l","6":"fs-xl","7":"fs-xl"};
function hexOf(c){c=(c||"").trim().toLowerCase();if(c.charAt(0)==="#")return c.length===4?"#"+c[1]+c[1]+c[2]+c[2]+c[3]+c[3]:c;
  var m=c.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);if(!m)return "";
  return "#"+[m[1],m[2],m[3]].map(function(x){return("0"+(+x).toString(16)).slice(-2)}).join("")}
function unwrap(el){var p=el.parentNode;while(el.firstChild)p.insertBefore(el.firstChild,el);p.removeChild(el)}
function wrapIn(el,tag,cls){var w=d.createElement(tag);w.className=cls;el.parentNode.insertBefore(w,el);while(el.firstChild)w.appendChild(el.firstChild);el.parentNode.removeChild(el)}
function tidy(ed){var c=ed.cloneNode(true);
  $$("img",c).forEach(function(i){if(i.dataset.pic){i.setAttribute("src","cid:"+i.dataset.pic);i.removeAttribute("data-pic")}else i.parentNode.removeChild(i)});
  $$("font,span",c).reverse().forEach(function(el){
    var col=hexOf(el.getAttribute("color")||el.style.color),bg=hexOf(el.style.backgroundColor),sz=el.getAttribute("size");
    if(el.tagName==="SPAN"&&/^(tc|fs)-/.test(el.className))return;
    var cls=TC[col]||"",hl=HL[bg]||"",fs=FS[sz]||"";
    if(hl){var m=d.createElement("mark");m.className=hl;el.parentNode.insertBefore(m,el);m.appendChild(el)}
    if(cls||fs)wrapIn(el,"span",[cls,fs].filter(Boolean).join(" "));else unwrap(el)});
  $$("mark",c).forEach(function(m){if(!/^hl-/.test(m.className))unwrap(m)});
  return c.innerHTML}
function sync(ed){var f=ed.closest("form"),ta=f&&f.querySelector("textarea[name=body]");if(!ta)return;
  var plain=f.classList.contains("plain");
  ta.value=plain?ta.value:tidy(ed);
  var fmt=f.querySelector("[name=body_format]");if(fmt)fmt.value=plain?"":"HTML";
  ed.classList.toggle("is-empty",!ed.textContent.trim()&&!ed.querySelector("img,br+br"))}
/* Pictures and GIFs: pasted, dropped or picked, each added to the form's own
   file field and drawn in the note where it went; the note names it by a
   token the server turns into the stored file's Content-ID. */
var MAXPICS=9*1024*1024;
function addPics(ed,files){var f=ed.closest("form");if(!f)return;var inp=f.querySelector("input.edpics"),tok=f.querySelector("[name=pic_tokens]");
  if(!inp||!tok||!window.DataTransfer)return;
  var dt=new DataTransfer(),total=0,list=tok.value?tok.value.split(","):[];
  Array.prototype.forEach.call(inp.files,function(x){dt.items.add(x);total+=x.size});
  Array.prototype.forEach.call(files,function(file){
    if(!/^image\//.test(file.type))return;
    if(total+file.size>MAXPICS){alert("That picture is too big to add: one note carries up to 9 MB of pictures.");return}
    total+=file.size;dt.items.add(file);
    var t="p"+(list.length+1)+"-"+Math.random().toString(36).slice(2,8);list.push(t);
    var img=d.createElement("img");img.src=URL.createObjectURL(file);img.dataset.pic=t;img.alt=file.name||"picture";
    var sel=window.getSelection();
    if(sel&&sel.rangeCount&&ed.contains(sel.anchorNode)){var r=sel.getRangeAt(0);r.collapse(false);r.insertNode(img);r.setStartAfter(img);sel.removeAllRanges();sel.addRange(r)}
    else ed.appendChild(img)});
  inp.files=dt.files;tok.value=list.join(",");sync(ed)}
function editorOf(el){var f=el.closest("form");return f?f.querySelector(".editor"):null}
$$(".editor").forEach(function(ed){
  var f=ed.closest("form"),ta=f&&f.querySelector("textarea[name=body]");
  if(!ta)return;
  ta.style.display="none";ta.removeAttribute("required");ed.classList.add("is-empty");
  var box=ed.closest(".composer");
  ed.addEventListener("dragover",function(e){if(e.dataTransfer&&Array.prototype.some.call(e.dataTransfer.types||[],function(x){return x==="Files"})){e.preventDefault();box&&box.classList.add("drop")}});
  ed.addEventListener("dragleave",function(){box&&box.classList.remove("drop")});
  ed.addEventListener("drop",function(e){box&&box.classList.remove("drop");var fl=e.dataTransfer&&e.dataTransfer.files;
    if(fl&&fl.length){e.preventDefault();addPics(ed,fl)}});
  var pick=f.querySelector("input.edpick");
  if(pick)pick.addEventListener("change",function(){if(pick.files.length){ed.focus();addPics(ed,pick.files)}pick.value=""});
  ed.addEventListener("input",function(){sync(ed)});
  ed.addEventListener("blur",function(){sync(ed)});
  /* Outlook and Word paste a document; only the writer's words and marks are taken. */
  ed.addEventListener("paste",function(e){
    var dt=e.clipboardData;if(!dt)return;e.preventDefault();
    var pasted=Array.prototype.filter.call(dt.files||[],function(x){return /^image\//.test(x.type)});
    if(pasted.length&&!dt.getData("text/plain")){addPics(ed,pasted);return}
    var html=dt.getData("text/html"),frag;
    if(html){var box=d.createElement("div");box.innerHTML="";
      var parsed=new DOMParser().parseFromString(html,"text/html");
      frag=rebuild(parsed.body,d.createDocumentFragment())}
    else{frag=d.createDocumentFragment();
      (dt.getData("text/plain")||"").split("\n").forEach(function(line,i){
        if(i)frag.appendChild(d.createElement("br"));frag.appendChild(d.createTextNode(line))})}
    var sel=window.getSelection();if(!sel||!sel.rangeCount){ed.appendChild(frag);sync(ed);return}
    var r=sel.getRangeAt(0);r.deleteContents();r.insertNode(frag);
    sel.collapseToEnd();sync(ed)});
  /* A form that submits before a blur still carries what is in the editor. */
  f.addEventListener("submit",function(){sync(ed)});
});
/* A toolbar button keeps the focus on the words it acts on. Without this the
   selection is gone before the command runs, and Bold did nothing (MEASURED
   in a browser, 2 Oct 2026). */
d.addEventListener("mousedown",function(e){if(e.target.closest&&e.target.closest(".edbar [data-do],.edbar summary"))e.preventDefault()});
d.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest(".edbar [data-do]");if(!b)return;
  e.preventDefault();var ed=editorOf(b);if(!ed)return;
  var what=b.dataset.do,arg=b.dataset.arg||"",pop=b.closest("details.pop");if(pop)pop.open=false;
  if(what==="image"){var pk=b.closest("form").querySelector("input.edpick");if(pk)pk.click();return}
  if(d.activeElement!==ed&&!ed.contains(window.getSelection().anchorNode))ed.focus();
  try{
    if(what==="block")d.execCommand("formatBlock",false,arg);
    else if(what==="size")d.execCommand("fontSize",false,arg);
    else if(what==="color"){d.execCommand("styleWithCSS",false,false);
      if(arg==="auto")d.execCommand("removeFormat",false,null);else d.execCommand("foreColor",false,arg)}
    else if(what==="hilite"){d.execCommand("styleWithCSS",false,true);
      d.execCommand("hiliteColor",false,arg==="none"?"transparent":arg);d.execCommand("styleWithCSS",false,false)}
    else if(what==="emoji")d.execCommand("insertText",false,arg);
    else if(what==="quote")d.execCommand("formatBlock",false,"blockquote");
    else if(what==="code"){var sel=String(window.getSelection()||"");
      if(sel){var c=d.createElement("code");c.textContent=sel;
        var r=window.getSelection().getRangeAt(0);r.deleteContents();r.insertNode(c)}}
    else if(what==="link"){var url=window.prompt("Address (https:// or mailto:)","https://");
      if(url&&/^(https?:\/\/|mailto:)/i.test(url))d.execCommand("createLink",false,url)}
    else d.execCommand(what,false,null);
  }catch(err){}
  sync(ed)});
d.addEventListener("click",function(e){$$(".edbar details.pop[open]").forEach(function(p){if(!p.contains(e.target))p.open=false})});
/* Rich or Plain: the same note, written either way. */
d.addEventListener("click",function(e){var t=e.target.closest&&e.target.closest(".edbar [data-plain]");if(!t)return;
  e.preventDefault();var f=t.closest("form"),ed=f.querySelector(".editor"),ta=f.querySelector("textarea[name=body]");
  var plain=t.dataset.plain==="1";
  $$("[data-plain]",t.closest(".edbar")).forEach(function(x){x.classList.toggle("on",x===t)});
  f.classList.toggle("plain",plain);
  $$(".edbar [data-do]",f).forEach(function(x){x.disabled=plain});
  if(plain){ta.value=ed.textContent;ta.style.display="";ta.setAttribute("required","required");ed.style.display="none";ta.focus()}
  else{ta.style.display="none";ta.removeAttribute("required");ed.style.display="";ed.focus()}
  sync(ed)});
/* a window's draft outlives a refused Save (Dada, 6 Oct 2026: "time entries when saved isnt saving anywhere").
   On submit the window's fields and its note are kept in this tab; if the desk sends the page back with an
   error, the same window reopens with them in place. Anything else that comes back clears it. Nothing leaves
   the browser, and it is gone when the tab closes. */
(function(){var key="psa-draft:"+location.pathname,q=location.search,ss;try{ss=sessionStorage}catch(e){return}
  $$("dialog.tedlg form").forEach(function(f){f.addEventListener("submit",function(e){
    var s=e.submitter;if(s&&s.getAttribute("formaction"))return;   /* Cancel and discard keep nothing */
    var dl=f.closest("dialog"),ed=$(".editor",f),v={};
    $$("input,select,textarea",f).forEach(function(x){if(!x.name||x.type==="hidden"||x.type==="file")return;
      if(x.type==="radio"||x.type==="checkbox"){if(x.checked)v[x.name+"="+x.value]=1}else v[x.name]=x.value});
    try{ss.setItem(key,JSON.stringify({dlg:dl.id,html:ed?tidy(ed):"",v:v}))}catch(_){}})});
  var raw;try{raw=ss.getItem(key)}catch(e){}if(!raw)return;
  if(!/[?&]err=/.test(q)){try{ss.removeItem(key)}catch(e){}return}
  var dr;try{dr=JSON.parse(raw)}catch(e){return}var dl=d.getElementById(dr.dlg);if(!dl)return;var f=$("form",dl);
  $$("input,select,textarea",f).forEach(function(x){if(!x.name||x.type==="hidden"||x.type==="file")return;
    if(x.type==="radio"||x.type==="checkbox")x.checked=!!dr.v[x.name+"="+x.value];
    else if(dr.v[x.name]!==undefined&&dr.v[x.name]!=="")x.value=dr.v[x.name]});
  /* the note comes back through rebuild, as a paste does: only the editor's own tags and classes */
  var ed=$(".editor",f);if(ed&&dr.html){var parsed=new DOMParser().parseFromString(dr.html,"text/html");
    ed.textContent="";ed.appendChild(rebuild(parsed.body,d.createDocumentFragment()));sync(ed)}
  if(!dl.open&&dl.showModal)dl.showModal();
  var bad=$("select:invalid,input:invalid",f);if(bad)bad.focus()})();
})();

/* Copy on a note: the ward's own words, as written, for a reply or a search. */
d.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("button.copy[data-copy]");if(!b)return;
var note=b.closest(".note");if(!note)return;var body=note.querySelector("div:last-child");if(!body)return;
var text=body.innerText;
function done(){b.classList.add("done");b.title="Copied";setTimeout(function(){b.classList.remove("done");b.title="Copy this note"},1200)}
if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(text).then(done,fallback)}else{fallback()}
function fallback(){var ta=d.createElement("textarea");ta.value=text;ta.setAttribute("readonly","");
  ta.style.cssText="position:fixed;left:-9999px";d.body.appendChild(ta);ta.select();
  try{d.execCommand("copy");done()}catch(err){}d.body.removeChild(ta)}});
/* 076: Copy the requester's link -- asked for, copied, and shown selected if the browser will not copy.
   The page stays: the busy mark and the top bar that every submit starts are put back when it answers. */
d.addEventListener("submit",function(e){var f=e.target;if(!f.matches||!f.matches("form[data-plink-form]")||e.defaultPrevented)return;
var box=d.querySelector("[data-plinkbox]");if(!box||!window.fetch)return;e.preventDefault();
var out=box.querySelector("input"),said=box.querySelector("[data-plinksaid]"),btn=box.querySelector("button");
function show(t){said.textContent=t}
function done(){delete f.dataset.sent;if(btn)btn.removeAttribute("aria-busy");var bar=d.getElementById("nprog");if(bar)bar.className=""}
function pick(){out.hidden=false;out.focus();out.select();show(" Select it and copy.")}
fetch(f.action,{method:"POST",credentials:"same-origin",headers:{"Accept":"application/json"}})
.then(function(r){return r.json()}).then(function(j){done();if(!j.link){show(" "+(j.error||"No link."));return}
  out.value=j.link;out.hidden=false;
  if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(j.link).then(function(){show(" Copied. Paste it into your reply.")},pick)}else{pick()}})
.catch(function(){done();f.submit()})});
/* chat round six: a form marked data-once sends once; its button is given back if the browser returns to the page */
d.addEventListener("submit",function(e){var f=e.target;if(!f.matches||!f.matches("form[data-once]")||e.defaultPrevented)return;
setTimeout(function(){$$("button[type=submit],button:not([type])",f).forEach(function(b){b.disabled=true})},0)});
addEventListener("pageshow",function(){$$("form[data-once] button").forEach(function(b){b.disabled=false})});
/* a button with data-open opens that dialog; data-tick ticks every box in its form, or none */
d.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("[data-open]");if(b){var dl=d.getElementById(b.dataset.open);
  /* a phase's + Ticket opens the project ticket window with that phase picked (068) */
  if(dl&&b.dataset.phase!==undefined){var ps=dl.querySelector("select[name=phase_id]");if(ps)ps.value=b.dataset.phase}
  /* a work plan ticket's Plan fills the plan window with that ticket's dates, budget and number (069) */
  if(dl&&b.dataset.plan!==undefined){var put=function(n,v){var x=dl.querySelector("[name="+n+"]");if(x)x.value=v||""};
    put("work_item_id",b.dataset.plan);put("starts_on",b.dataset.starts);put("due_on",b.dataset.due);put("budget_hours",b.dataset.budget);
    put("depends_on","");var dep=dl.querySelector("select[name=depends_on]");
    if(dep)Array.prototype.forEach.call(dep.options,function(o){o.disabled=o.value===b.dataset.plan});
    $$("[data-fill]",dl).forEach(function(x){x.textContent=x.dataset.fill==="wid"?b.dataset.plan:(b.dataset.summary||"")})}
  if(dl&&dl.showModal){dl.showModal();return}}
  var k=e.target.closest&&e.target.closest("[data-tick]");if(k&&k.form){$$("input[type=checkbox]",k.form).forEach(function(c){c.checked=k.dataset.tick==="1"})}});
/* the departments grid: a row or column box ticks its line */
var dg=$("#deptgrid");if(dg){dg.addEventListener("change",function(e){var b=e.target;
  if(b.dataset.row!==undefined){$$("input[name=tick]",dg).forEach(function(c){if(c.value.split("|")[0]===b.dataset.row)c.checked=b.checked})}
  if(b.dataset.col!==undefined){$$("input[name=tick]",dg).forEach(function(c){if(c.value.split("|")[1]===b.dataset.col)c.checked=b.checked})}})}
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

/* ---- naming a ticket: fill a field's own datalist from /search.json -------
   Nine forms used to want PMC-000123 typed from memory (templates.ticket_pick).
   The browser draws the dropdown and handles the keyboard; all this does is
   keep the <option>s current. With this script off the field is the plain text
   input it has always been, and the form posts exactly what it posted before. */
$$("input[data-tickpick]").forEach(function(inp){
  var dl=d.getElementById(inp.getAttribute("list")); if(!dl)return;
  var skip=(inp.dataset.not||"").toUpperCase(),timer=null,last="";
  function fill(list){
    dl.innerHTML="";
    list.forEach(function(x){
      if(skip&&String(x.id).toUpperCase()===skip)return;       /* never offer itself */
      var o=d.createElement("option");o.value=x.id;
      /* The label is what the dropdown reads out: the summary, who it is for,
         and -- when the match was somewhere the label does not show -- where it
         was found, so a hit that looks unrelated explains itself. */
      var bits=[(x.summary||"").slice(0,70)];
      if(x.who)bits.push(x.who);
      if(x.state)bits.push(String(x.state).toLowerCase().replace(/_/g," "));
      if(x.where)bits.push(x.where);
      o.label=bits.filter(Boolean).join(" \u00b7 ");
      dl.appendChild(o)})}
  inp.addEventListener("input",function(){
    var q=inp.value.trim();
    /* Once it holds a whole ticket number there is nothing left to look up. */
    if(q.length<2||/^[A-Za-z]{2,10}-\d{4,}$/.test(q)){if(q.length<2)fill([]);return}
    if(q===last)return; last=q;
    clearTimeout(timer);
    timer=setTimeout(function(){
      fetch("/search.json?q="+encodeURIComponent(q),{credentials:"same-origin"})
        .then(function(r){return r.ok?r.json():null})
        .then(function(j){if(j&&j.q===q&&j.tickets)fill(j.tickets)})
        .catch(function(){})},140)});
  /* A typed number is a number whatever its case: pmc-1 is PMC-000001. */
  inp.addEventListener("change",function(){
    var m=inp.value.trim().match(/^([A-Za-z]{2,10})[- ]?0*(\d{1,6})$/);
    if(!m)return; var pre=m[1].toUpperCase();
    inp.value=pre==="PMC"?"PMC-"+("000000"+m[2]).slice(-6):pre+"-"+m[2]});
});

/* ---- an email in its sandbox (templates.mail_frame) -----------------------
   The frame is same-origin (never allow-scripts), so the page can read how tall
   the email is and give the frame exactly that: no inner scrollbar, no gap.
   It is measured when it loads, when a picture in it loads, when its fold is
   opened or shut, and when its width changes (a card resized or unfolded).
   The theme and the text size follow the page's own, because the email's
   document has no stylesheet of ours to read them from. */
function mailDoc(f){try{return f.contentDocument}catch(e){return null}}
/* The email's own height, not the frame's: the root's scrollHeight is never
   less than the frame it sits in, so fitting to it only ever grows -- and,
   with the frame watched for size, grew without end (6 Oct 2026). The root's
   box is as tall as what is in it; the body's scrollHeight catches a float
   that hangs out of it. Within a pixel is left alone, so a fit settles. */
function mailFit(f){var md=mailDoc(f);if(!md||!md.documentElement||!md.body)return;
  var h=Math.ceil(Math.max(md.documentElement.getBoundingClientRect().height,md.body.scrollHeight));
  if(h>0&&Math.abs(f.getBoundingClientRect().height-h)>1)f.style.height=h+"px"}
function mailTheme(f){var md=mailDoc(f);if(!md||!md.documentElement)return;var r=md.documentElement;
  if(root.dataset.theme)r.dataset.theme=root.dataset.theme;else r.removeAttribute("data-theme");
  var sz=getComputedStyle(root).getPropertyValue("--note-size").trim();
  if(sz)r.style.setProperty("--size",sz);else r.style.removeProperty("--size");mailFit(f)}
function mailWire(f){if(f.dataset.wired)return;f.dataset.wired="1";
  /* Nothing is listened for inside the email: a sandbox without scripts
     runs no listener there, ours included. Its body is watched for size
     from out here, which covers the fold and a picture arriving alike. */
  function ready(){var md=mailDoc(f);if(!md||!md.body)return;mailTheme(f);
    if(window.ResizeObserver){var ro=new ResizeObserver(function(){mailFit(f)});ro.observe(md.body);ro.observe(f)}
    else[300,1000,3000].forEach(function(t){setTimeout(function(){mailFit(f)},t)})}
  f.addEventListener("load",ready);
  var md=mailDoc(f);if(md&&md.readyState==="complete"&&md.body&&md.body.firstChild)ready()}
function mailAll(){$$("iframe.mail").forEach(mailWire)}
mailAll();
if(window.MutationObserver){
  new MutationObserver(function(){$$("iframe.mail").forEach(mailTheme)})
    .observe(root,{attributes:true,attributeFilter:["data-theme","data-text"]});
  new MutationObserver(function(ms){for(var i=0;i<ms.length;i++)if(ms[i].addedNodes.length){mailAll();break}})
    .observe(d.body,{childList:true,subtree:true})}
})();
// Back (Dada, 6 Oct 2026: "add a back button"). Every desk page notes itself
// in this tab's trail; a page that only reloads itself (a ticket after a save,
// a board with ?msg=) replaces its own entry rather than adding one, so Back
// goes to where the person came from -- the board, a search, Dispatch -- and
// never to the same ticket a save ago. Without the trail it goes to the board.
(function(){var K="psa_trail",tr=[];try{tr=JSON.parse(sessionStorage.getItem(K)||"[]")}catch(e){}
  if(!Array.isArray(tr))tr=[];
  var here=location.pathname+location.search,path=location.pathname;
  var name=(document.title||"").split(" · ")[0];
  var last=tr[tr.length-1];
  if(last&&last.p===path)tr[tr.length-1]={u:here,p:path,n:name};else tr.push({u:here,p:path,n:name});
  if(tr.length>30)tr=tr.slice(-30);
  try{sessionStorage.setItem(K,JSON.stringify(tr))}catch(e){}
  document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("[data-print]");if(b){e.preventDefault();window.print()}});
  // a list row opens its document (SQL01, 14 Oct 2026); a control inside the row keeps its own click
  document.addEventListener("click",function(e){var tr=e.target.closest&&e.target.closest("tr[data-href]");if(!tr)return;
    if(e.button!==0||e.target.closest("a,button,input,select,label,form"))return;
    try{if(window.getSelection&&String(window.getSelection()).length)return}catch(x){}
    if(e.metaKey||e.ctrlKey){window.open(tr.getAttribute("data-href"),"_blank");return}
    location.href=tr.getAttribute("data-href")});
  document.querySelectorAll("[data-back]").forEach(function(a){
    var prev=tr.length>1?tr[tr.length-2]:null;
    if(prev){a.href=prev.u.replace(/([?&])(msg|err)=[^&]*&?/g,"$1").replace(/[?&]$/,"");
      var l=a.querySelector(".lbl");if(l&&prev.n)l.textContent="Back to "+prev.n;a.title="Back to "+(prev.n||"the last page")}
    a.addEventListener("click",function(){tr.pop();try{sessionStorage.setItem(K,JSON.stringify(tr))}catch(e){}})})})();
// A filter applies the moment it is picked (Dada, 1 Oct 2026: "when the
// drop down is picked it updates automatically"): a select or a checkbox in
// a GET form sends the form; the button stays for the keyboard and for text.
document.addEventListener('change',function(e){var el=e.target;if(!el||!el.form||!/^get$/i.test(el.form.method))return;
if(el.tagName!=='SELECT'&&!(el.tagName==='INPUT'&&(el.type==='checkbox'||el.type==='date')))return;
if(el.hasAttribute('data-manual')||el.form.hasAttribute('data-manual'))return;
if(el.form.requestSubmit)el.form.requestSubmit();else el.form.submit()});
// The menu's modules: a click opens one and closes the others; Escape or a
// click outside closes; hover opens too, for a mouse.
document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('header.top nav .grp>button.top');
var open=document.querySelectorAll('header.top nav .grp.open');
if(!b){open.forEach(function(g){g.classList.remove('open');g.querySelector('button.top').setAttribute('aria-expanded','false')});return}
var g=b.parentNode,was=g.classList.contains('open');open.forEach(function(x){if(x!==g){x.classList.remove('open');x.querySelector('button.top').setAttribute('aria-expanded','false')}});
g.classList.toggle('open',!was);b.setAttribute('aria-expanded',String(!was))});
document.addEventListener('keydown',function(e){if(e.key!=='Escape')return;document.querySelectorAll('header.top nav .grp.open').forEach(function(g){g.classList.remove('open');g.querySelector('button.top').setAttribute('aria-expanded','false');g.querySelector('button.top').focus()})});
// Hover intent (Dada, 14 Oct 2026): a panel opened by hover stays open for a
// third of a second after the mouse leaves its menu, so crossing into the
// panel or passing a gap never closes it; it closes once the mouse has left
// the heading and the panel together.
(function(){var tm={};document.querySelectorAll('header.top nav .grp').forEach(function(g,i){
  g.addEventListener('pointerenter',function(e){if(e.pointerType&&e.pointerType!=='mouse')return;clearTimeout(tm[i]);g.classList.add('hov')});
  g.addEventListener('pointerleave',function(e){if(e.pointerType&&e.pointerType!=='mouse')return;clearTimeout(tm[i]);tm[i]=setTimeout(function(){g.classList.remove('hov')},320)})});
  document.addEventListener('click',function(){document.querySelectorAll('header.top nav .grp.hov:not(.open)').forEach(function(g){g.classList.remove('hov')})},true)})();
// The top menu fades at its right edge only when it has more than fits.
(function(){var n=document.querySelector('header.top nav');if(!n)return;
function f(){n.classList.toggle('more',n.scrollWidth>n.clientWidth+2&&n.scrollLeft+n.clientWidth<n.scrollWidth-2)}
f();addEventListener('resize',f);n.addEventListener('scroll',f,{passive:true})})();
// Drag and drop, as the reference PSA's Dispatch Portal: a ticket card
// dropped on a person's hour books it; a visit or a task dropped on another
// person, hour or day moves it. Each drop is one ordinary form post.
(function(){if(!('draggable' in document.createElement('div')))return;var cur=null;
function post(url,fields){var f=document.createElement('form');f.method='post';f.action=url;
Object.keys(fields).forEach(function(k){var i=document.createElement('input');i.type='hidden';i.name=k;i.value=fields[k];f.appendChild(i)});
document.body.appendChild(f);f.submit()}
document.addEventListener('dragstart',function(e){var el=e.target.closest&&e.target.closest('[data-drag]');if(!el||el.getAttribute('draggable')!=='true')return;
cur=el.getAttribute('data-drag');el.classList.add('dragging');try{e.dataTransfer.setData('text/plain',cur);e.dataTransfer.effectAllowed='move'}catch(x){}});
document.addEventListener('dragend',function(e){var el=e.target.closest&&e.target.closest('[data-drag]');if(el)el.classList.remove('dragging');
document.querySelectorAll('[data-slot].over').forEach(function(s){s.classList.remove('over')})});
document.addEventListener('dragover',function(e){var s=e.target.closest&&e.target.closest('[data-slot]');if(!s||!cur)return;e.preventDefault();
try{e.dataTransfer.dropEffect='move'}catch(x){}s.classList.add('over')});
document.addEventListener('dragleave',function(e){var s=e.target.closest&&e.target.closest('[data-slot]');if(s&&!(e.relatedTarget&&s.contains(e.relatedTarget)))s.classList.remove('over')});
document.addEventListener('drop',function(e){var s=e.target.closest&&e.target.closest('[data-slot]');if(!s||!cur)return;e.preventDefault();
var p=s.getAttribute('data-slot').split('|'),d=cur.split('|'),back=location.pathname+location.search;cur=null;
var dlg=document.getElementById('slotdlg');if(dlg){var b=dlg.querySelector('input[name=back]');if(b&&b.value)back=b.value}
if(d[0]==='ticket'){var tm=p[2]||'09:00',h=parseInt(tm.slice(0,2),10);
post('/schedule/slot',{what:'visit',member:p[0],work_item_id:d[1],starts_at:p[1]+'T'+tm,ends_at:p[1]+'T'+(h+1<10?'0':'')+Math.min(h+1,23)+tm.slice(2),back:back});return}
var f={kind:d[0],id:d[1],member:p[0],back:back};if(p[2])f.starts_at=p[1]+'T'+p[2];else f.day=p[1];post('/schedule/move',f)});})();
// The Dispatch Portal's hands (8 Oct 2026): a right-click on a visit for Open,
// Done, Acknowledge and Delete; a double-click opens the ticket; the right
// edge dragged changes when it ends; the Service Tickets table folds and
// filters as you type. Each action is one ordinary form post.
(function(){var menu=null;function post(url,fields){var f=document.createElement('form');f.method='post';f.action=url;
Object.keys(fields).forEach(function(k){var i=document.createElement('input');i.type='hidden';i.name=k;i.value=fields[k];f.appendChild(i)});
document.body.appendChild(f);f.submit()}
function close(){if(menu){menu.remove();menu=null}}
function back(){var dlg=document.getElementById('slotdlg'),b=dlg&&dlg.querySelector('input[name=back]');return(b&&b.value)||(location.pathname+location.search)}
/* 9 Oct 2026 (Dada: "when changing a schedule there is no modify"): the Edit window, the same on Dispatch, the
   Schedule and the calendars. Filled from /schedule/item.json and drawn with textContent; Save is a plain post. */
function ref(c){if(c.dataset.menu){var p=c.dataset.menu.split('|');return p[3]==='1'&&p[2]!=='1'?['visit',p[1]]:null}
 var d=(c.dataset.drag||'').split('|');return(d[0]==='visit'||d[0]==='block')&&d[1]?[d[0],d[1]]:null}
function el(tag,attrs,txt){var x=document.createElement(tag);Object.keys(attrs||{}).forEach(function(k){x.setAttribute(k,attrs[k])});if(txt!=null)x.textContent=txt;return x}
function field(form,label,input){var l=el('label',null,label+' ');l.appendChild(input);form.appendChild(l);return input}
function pick(name,options,value,blank){var s=el('select',{name:name});if(blank!=null)s.appendChild(el('option',{value:''},blank));
 options.forEach(function(o){var op=el('option',{value:o[0]},o[1]);if(o[0]===value)op.selected=true;s.appendChild(op)});return s}
function fetchItem(r,then){fetch('/schedule/item.json?kind='+r[0]+'&id='+encodeURIComponent(r[1]),{credentials:'same-origin'})
 .then(function(x){return x.json()}).then(function(j){if(j.error){alert(j.error);return}then(j)})}
function openEdit(r){fetchItem(r,function(j){var old=document.getElementById('schedit');if(old)old.remove();
 var dl=el('dialog',{id:'schedit','class':'card',style:'max-width:520px;width:95%'}),
     f=el('form',{method:'post',action:j.kind==='visit'?'/schedule/edit':'/schedule/block/edit','class':'stack'});f.style.maxWidth='none';
 dl.appendChild(el('h3',null,j.kind==='visit'?'Edit the visit \u00b7 '+j.ticket:'Edit \u00b7 '+(j.name||'')));
 if(j.kind==='visit'&&j.summary)f.appendChild(el('p',{'class':'why'},j.summary));
 f.appendChild(el('input',{type:'hidden',name:'id',value:String(j.id)}));f.appendChild(el('input',{type:'hidden',name:'back',value:back()}));
 field(f,j.kind==='visit'?'Technician':'Person',pick('member',j.choices.members,j.member));
 if(j.kind==='block'){field(f,'Kind',pick('block_kind',j.choices.kinds,j.block_kind));field(f,'What',el('input',{name:'name',maxlength:'120',value:j.name}))}
 field(f,'Starts',el('input',{type:'datetime-local',name:'starts_at',value:j.starts_at,required:'',step:'900'}));
 field(f,'Ends',el('input',{type:'datetime-local',name:'ends_at',value:j.ends_at,required:'',step:'900'}));
 if(j.kind==='visit'){field(f,'Status',pick('status_id',j.choices.statuses,j.status_id));
  field(f,'Where',pick('location_id',j.choices.locations,j.location_id,'\u2014'));
  var n=el('textarea',{name:'note',rows:'2',maxlength:'400'});n.value=j.note;field(f,'Notes',n)}
 var ok=el('label',null,' Allow a double booking');ok.insertBefore(el('input',{type:'checkbox',name:'allow_conflict',value:'1'}),ok.firstChild);f.appendChild(ok);
 var row=el('div',{'class':'row'});row.style.gap='8px';var sv=el('button',{type:'submit'},'Save');var cn=el('button',{type:'button','class':'ghost'},'Cancel');
 cn.addEventListener('click',function(){dl.close();dl.remove()});row.appendChild(sv);row.appendChild(cn);f.appendChild(row);
 dl.appendChild(f);document.body.appendChild(dl);dl.showModal();var first=f.querySelector('select,input:not([type=hidden])');if(first)first.focus()})}
function tomorrow(r){fetchItem(r,function(j){var d=new Date(j.starts_at.slice(0,10)+'T12:00');d.setDate(d.getDate()+1);
 post('/schedule/move',{kind:j.kind,id:j.id,day:d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate()),back:back()})})}
document.addEventListener('contextmenu',function(e){var c=e.target.closest&&e.target.closest('.sch.visit[data-menu],.sch[data-drag]');if(!c)return;
 var r=ref(c);if(!c.dataset.menu&&!r)return;e.preventDefault();close();
 var m=document.createElement('div');m.className='ctxmenu';m.setAttribute('role','menu');
 function item(label,fn,cls){var b=document.createElement('button');b.type='button';b.textContent=label;if(cls)b.className=cls;b.addEventListener('click',function(){close();fn()});m.appendChild(b)}
 if(r){item('Edit\u2026',function(){openEdit(r)});item('Move to tomorrow',function(){tomorrow(r)})}
 if(!c.dataset.menu){m.style.left=Math.min(e.pageX,window.scrollX+document.documentElement.clientWidth-210)+'px';m.style.top=e.pageY+'px';
  document.body.appendChild(m);menu=m;var f0=m.querySelector('button');if(f0)f0.focus();return}
 var p=c.dataset.menu.split('|');
 item('Open ticket '+p[0],function(){location.href='/ticket/'+p[0]});
 if(p[3]==='1'){item(p[2]==='1'?'Reopen the visit':'Mark done',function(){post('/ticket/'+p[0]+'/schedule/done',{schedule_id:p[1],back:back()})});
  if(p[4]==='1')item('Acknowledge',function(){post('/ticket/'+p[0]+'/schedule/ack',{schedule_id:p[1],back:back()})});
  item('Delete the visit',function(){if(confirm('Cancel this visit? The ticket stays.'))post('/ticket/'+p[0]+'/schedule/remove',{schedule_id:p[1],back:back()})},'danger')}
 m.style.left=Math.min(e.pageX,window.scrollX+document.documentElement.clientWidth-210)+'px';m.style.top=e.pageY+'px';document.body.appendChild(m);menu=m;var f=m.querySelector('button');if(f)f.focus()});
document.addEventListener('click',function(e){if(menu&&!menu.contains(e.target))close()});
document.addEventListener('keydown',function(e){if(e.key==='Escape')close()});
document.addEventListener('dblclick',function(e){var c=e.target.closest&&e.target.closest('.sch.visit[data-menu],.sch[data-drag]');
 if(!c||e.target.closest('a,button,form,.rz'))return;var r=ref(c);if(r){openEdit(r);return}
 if(c.dataset.menu)location.href='/ticket/'+c.dataset.menu.split('|')[0]});
/* the right edge: half-hour steps, measured against the hour cell the chip starts in */
var rz=null;function pad(n){return(n<10?'0':'')+n}
/* a hovered visit is drawn wider to show its words; its handle stays where the visit ends, so the edge
   does not run from the pointer reaching for it (found by the browser check, 8 Oct 2026) */
document.addEventListener('mouseover',function(e){if(rz)return;var c=e.target.closest&&e.target.closest('table.schedgrid.dispatch td.hr .sch.visit');if(!c)return;
 var h=c.querySelector('.rz'),td=c.closest('td'),m=/width:\s*calc\(([\d.]+) \* 100%/.exec(c.getAttribute('style')||'');if(!h||!td||!m)return;
 h.style.left=Math.max(0,parseFloat(m[1])*td.getBoundingClientRect().width-4-(c.offsetWidth-c.clientWidth)-h.offsetWidth)+'px';h.style.right='auto'});
document.addEventListener('mousedown',function(e){var h=e.target.closest&&e.target.closest('.sch.visit .rz');if(!h||e.button!==0)return;e.preventDefault();e.stopPropagation();
 h.style.left='';h.style.right='';
 var c=h.closest('.sch'),td=c.closest('td'),span=(c.dataset.span||'|').split('|'),hourW=td.getBoundingClientRect().width;
 /* its width from its own times, not the box: a hovered chip is drawn wider to show its words */
 var w0=Math.max(0.5,(new Date(span[1])-new Date(span[0]))/3600000)*hourW-4;
 rz={c:c,x0:e.clientX,w0:w0,hourW:hourW,start:span[0],end:span[1],sid:(c.dataset.menu||'').split('|')[1]};
 c.classList.add('resizing');c.setAttribute('draggable','false')});
document.addEventListener('mousemove',function(e){if(!rz)return;rz.c.style.setProperty('width',Math.max(rz.hourW/2-4,rz.w0+(e.clientX-rz.x0))+'px','important')});
document.addEventListener('mouseup',function(e){if(!rz)return;var r=rz;rz=null;r.c.classList.remove('resizing');r.c.setAttribute('draggable','true');
 var hours=Math.max(0.5,Math.round((r.w0+(e.clientX-r.x0)+4)/r.hourW*2)/2),s=new Date(r.start),d=new Date(s.getTime()+hours*3600000);
 var ends=d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate())+'T'+pad(d.getHours())+':'+pad(d.getMinutes());
 if(ends===r.end||!r.sid){r.c.style.removeProperty('width');return}post('/schedule/resize',{id:r.sid,ends_at:ends,back:back()})});
/* the tickets panel: fold it to give the grid the width, remembered; filter rows as you type */
var wrap=document.querySelector('.dispatchwrap');if(wrap){var KEY='psa-dispatch-fold';
 function fold(v){wrap.classList.toggle('folded',v);try{localStorage.setItem(KEY,v?'1':'0')}catch(x){}}
 try{if(localStorage.getItem(KEY)==='1')wrap.classList.add('folded')}catch(x){}
 wrap.addEventListener('click',function(e){if(e.target.closest('.stfold'))fold(true);else if(e.target.closest('.stshow'))fold(false)});
 var q=document.getElementById('stsearch');if(q)q.addEventListener('input',function(){var v=q.value.trim().toLowerCase();
  wrap.querySelectorAll('table.sttable tbody tr[data-q]').forEach(function(tr){tr.hidden=!!v&&tr.dataset.q.indexOf(v)<0})})}})();
// Click a time: a cell marked data-slot="member|YYYY-MM-DD[|HH:MM]" opens the
// add dialog with the person and the time filled in. A click on a chip, a
// link or a button inside the cell does what it always did. (9 Oct 2026: a
// chip's own body is left alone too, so a double-click on a visit opens its
// Edit window instead of the Add one underneath; found by the browser check.)
(function(){var d=document.getElementById('slotdlg');if(!d||!d.showModal)return;var f=d.querySelector('form');
function pad(n){return(n<10?'0':'')+n}
function show(){var w=(f.querySelector('input[name=what]:checked')||{}).value||'visit';
d.querySelectorAll('[data-for]').forEach(function(el){var on=el.getAttribute('data-for').split(' ').indexOf(w)>=0;el.style.display=on?'':'none';
el.querySelectorAll('input,select').forEach(function(i){i.disabled=!on})});
var t=f.querySelector('input[name=work_item_id]');if(t)t.required=(w==='visit');var s=f.querySelector('input[name=summary]');if(s)s.required=(w==='ticket')}
f.addEventListener('change',function(e){if(e.target.name==='what')show();
if(e.target.name==='starts_at'){var a=f.starts_at.value,b=f.ends_at.value;if(a&&(!b||b<=a)){var x=new Date(a);x.setHours(x.getHours()+1);
f.ends_at.value=x.getFullYear()+'-'+pad(x.getMonth()+1)+'-'+pad(x.getDate())+'T'+pad(x.getHours())+':'+pad(x.getMinutes())}}});
d.querySelector('[data-close]').addEventListener('click',function(){d.close()});
document.addEventListener('click',function(e){var c=e.target.closest&&e.target.closest('[data-slot]');if(!c)return;
if(e.target.closest('a,button,form,input,select,label,.sch'))return;var p=c.getAttribute('data-slot').split('|'),tm=p[2]||'09:00';
var sel=f.querySelector('select[name=member]');if(sel){var o=[].find.call(sel.options,function(x){return x.value.toLowerCase()===p[0].toLowerCase()});if(o)sel.value=o.value}
var h=parseInt(tm.slice(0,2),10),e2=pad(Math.min(h+1,23))+tm.slice(2);f.starts_at.value=p[1]+'T'+tm;f.ends_at.value=p[1]+'T'+e2;
var ti=d.querySelector('[data-slot-title]');if(ti)ti.textContent='Add on '+p[1]+' at '+tm;show();d.showModal()});
show()})();
// Files: a picture, a PDF or a text file opens in the page's viewer instead
// of saving. The link itself still opens the file, so nothing depends on this.
// Previous and Next (and the arrow keys) step through every viewable file on
// the page in page order, the chat's pictures and a ticket's files alike (the
// PMO Helpdesk's ask, 14 Oct 2026); Escape closes. A page with no viewer markup
// (the chat) gets the same dialog, cloned from the page's <template>.
(function(){var list=[],at=0;
function dlg(){var d=document.getElementById('viewer');if(d)return d;var tp=document.getElementById('viewertpl');if(!tp)return null;
 d=tp.content.firstElementChild.cloneNode(true);document.body.appendChild(d);wire(d);return d}
function wire(d){if(d.dataset.wired)return;d.dataset.wired='1';
 d.querySelector('[data-close]').addEventListener('click',function(){d.close()});
 var p=d.querySelector('[data-vprev]'),n=d.querySelector('[data-vnext]');if(p)p.addEventListener('click',function(){step(-1)});if(n)n.addEventListener('click',function(){step(1)});
 d.addEventListener('close',function(){d.querySelector('.vbody').innerHTML=''});
 d.addEventListener('click',function(e){if(e.target===d)d.close()});
 d.addEventListener('keydown',function(e){if(e.key==='ArrowLeft'){e.preventDefault();step(-1)}else if(e.key==='ArrowRight'){e.preventDefault();step(1)}})}
function show(i){var d=dlg(),a=list[i];if(!a)return;at=i;
 var kind=a.getAttribute('data-view'),href=a.getAttribute('href'),body=d.querySelector('.vbody');
 d.querySelector('.vname').textContent=a.getAttribute('data-name')||a.textContent;
 var sz=d.querySelector('.vsize');if(sz)sz.textContent=a.getAttribute('data-size')?' · '+a.getAttribute('data-size'):'';
 var pos=d.querySelector('.vpos');if(pos)pos.textContent=list.length>1?' · '+(i+1)+' of '+list.length:'';
 var p=d.querySelector('[data-vprev]'),n=d.querySelector('[data-vnext]');if(p){p.disabled=list.length<2;p.hidden=list.length<2}if(n){n.disabled=list.length<2;n.hidden=list.length<2}
 d.querySelector('[data-vdl]').href=href+(href.indexOf('?')<0?'?':'&')+'dl=1';d.querySelector('[data-vopen]').href=href;
 body.innerHTML='';var el;if(kind==='image'){el=document.createElement('img');el.alt=a.getAttribute('data-name')||a.textContent}
 else{el=document.createElement('iframe');el.title=a.getAttribute('data-name')||a.textContent;if(kind==='text')el.setAttribute('sandbox','')}
 el.src=href;body.appendChild(el);if(!d.open)d.showModal()}
function step(k){if(list.length<2)return;show((at+k+list.length)%list.length)}
document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[data-view]');if(!a)return;
 var d=dlg();if(!d||!d.showModal)return;e.preventDefault();
 var seen={};list=[].slice.call(document.querySelectorAll('a[data-view]')).filter(function(x){var h=x.getAttribute('href');if(seen[h])return false;seen[h]=1;return true});
 var i=list.findIndex(function(x){return x.getAttribute('href')===a.getAttribute('href')});show(i<0?0:i)});
var d0=document.getElementById('viewer');if(d0)wire(d0)})();
// The ticket summary: the pencil swaps the words for a one-line form.
document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('[data-edit]');if(!b)return;
var h=b.closest('h1.sumline');if(!h)return;var f=h.querySelector('.sumform'),t=h.querySelector('.sumtext'),p=h.querySelector('.sumedit');
var on=b.getAttribute('data-edit')==='summary';f.hidden=!on;t.hidden=on;p.hidden=on;if(on){var i=f.querySelector('input');i.focus();i.select()}});
document.addEventListener('keydown',function(e){if(e.key!=='Escape')return;var f=e.target.closest&&e.target.closest('.sumform');
if(f){var c=f.querySelector('[data-edit=cancel]');if(c)c.click()}});
// Real time: a page marked data-live asks /live for a stamp every ten
// seconds while it is on screen, and reloads when the stamp moves. While the
// person is typing it does not reload: it says so, and they choose.
(function(){var m=document.querySelector('main[data-live]');if(!m)return;
var scope=m.getAttribute('data-live'),last=null,dirty=false,bar=null;
document.addEventListener('input',function(e){if(e.target&&e.target.closest&&e.target.closest('form'))dirty=true},true);
function busy(){var a=document.activeElement;return dirty||(a&&/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName))||document.querySelector('dialog[open]')}
function tell(){if(bar)return;bar=document.createElement('div');bar.setAttribute('role','status');
bar.style.cssText='position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:60;background:var(--accent,#2563eb);color:#fff;padding:8px 14px;border-radius:999px;box-shadow:0 6px 20px rgba(0,0,0,.25);font-size:14px';
bar.innerHTML='Something changed. <button type=button style="margin-left:8px;background:#fff;color:#111;border:0;border-radius:999px;padding:3px 10px;cursor:pointer">Refresh</button>';
bar.querySelector('button').addEventListener('click',function(){location.reload()});document.body.appendChild(bar)}
function tick(){if(document.hidden)return;fetch('/live?scope='+encodeURIComponent(scope),{credentials:'same-origin',cache:'no-store'})
.then(function(r){return r.ok?r.text():null}).then(function(s){if(s===null)return;if(last===null){last=s;return}
if(s!==last){last=s;if(busy())tell();else location.reload()}}).catch(function(){})}
setInterval(tick,10000);tick();document.addEventListener('visibilitychange',function(){if(!document.hidden)tick()})})();
/* 072: the banner of waiting chats on every desk page, and a chime when a new one comes
   (Dada, 7 Oct 2026: "a moving banner like moving from right to left ... and a sound or a chime").
   The chime is made here (Web Audio), no sound file; it is on unless the person turns it off. */
(function(){var tk=document.getElementById('chatticker');if(!tk||!window.fetch)return;
var track=tk.querySelector('.ttrack'),word=tk.querySelector('.tlabel'),snd=tk.querySelector('.tsound'),btn=tk.querySelector('.tlive'),
 tn=tk.querySelector('.tn'),panel=document.getElementById('chatlive'),KEY='psa-chat-chime',SEEN='psa-chat-seen',ac=null;
function on(){try{return localStorage.getItem(KEY)!=='off'}catch(e){return true}}
var VIT=document.body.classList.contains('vitals');
function paint(){snd.classList.toggle('off',!on());if(VIT){snd.innerHTML='<svg class=ic aria-hidden=true><use href="#i-bell"/></svg>';snd.setAttribute('aria-pressed',on()?'true':'false')}else snd.textContent=on()?'🔔':'🔕'}
snd.addEventListener('click',function(){try{localStorage.setItem(KEY,on()?'off':'on')}catch(e){}paint();if(on())chime()});
function ctx(){if(!ac){var A=window.AudioContext||window.webkitAudioContext;if(!A)return null;ac=new A()}if(ac.state==='suspended')ac.resume();return ac}
document.addEventListener('pointerdown',function(){if(on())ctx()},{once:true});
/* 073 (Dada, 7 Oct 2026: "a more audible one a different beep or alert"; confirmed: a louder phone-style ring,
   again every 30 s while a chat waits). A desk phone's ring: two tones trilled fast, in two bursts, played twice,
   through a compressor so it is loud without clipping. Made here, no sound file. */
function chime(){var a=ctx();if(!a)return;var t=a.currentTime,cmp=a.createDynamicsCompressor(),out=a.createGain();
 cmp.threshold.value=-12;cmp.ratio.value=4;out.gain.value=0.9;cmp.connect(out);out.connect(a.destination);
 [0,.55,1.4,1.95].forEach(function(b){var o=a.createOscillator(),g=a.createGain(),s=t+b,i;o.type='square';
  for(i=0;i<9;i++)o.frequency.setValueAtTime(i%2?1400:1100,s+i*.05);
  g.gain.setValueAtTime(0.0001,s);g.gain.exponentialRampToValueAtTime(0.55,s+.015);g.gain.setValueAtTime(0.55,s+.42);
  g.gain.exponentialRampToValueAtTime(0.0001,s+.45);o.connect(g);g.connect(cmp);o.start(s);o.stop(s+.46)})}
/* one ring across the person's open tabs: whichever tab rings first says so, and the others keep quiet */
var RANG='psa-chat-rang',REPEAT=30000;
function rangAgo(){try{return Date.now()-(+localStorage.getItem(RANG)||0)}catch(e){return 1e9}}
function ring(fresh){if(!on()||tk.hidden)return;if(rangAgo()<(fresh?3000:REPEAT-2000))return;
 try{localStorage.setItem(RANG,String(Date.now()))}catch(e){}chime()}
function seen(){try{return JSON.parse(sessionStorage.getItem(SEEN)||'[]')}catch(e){return[]}}
function remember(ids){try{sessionStorage.setItem(SEEN,JSON.stringify(ids.slice(-200)))}catch(e){}}
/* the quick view (Dada, 7 Oct 2026: "a quick view of the live chats"): opens over the page, Escape or a click away closes it */
function open(v){panel.hidden=!v;btn.setAttribute('aria-expanded',v?'true':'false')}
btn.addEventListener('click',function(e){e.stopPropagation();open(panel.hidden)});
document.addEventListener('click',function(e){if(!panel.hidden&&!panel.contains(e.target)&&!btn.contains(e.target))open(false)});
document.addEventListener('keydown',function(e){if(e.key==='Escape'&&!panel.hidden){open(false);btn.focus()}});
var first=true,HID='psa-chat-hidden',lastL=null;
/* drawn from the data with textContent, never from markup (the desk's rule for anything a person typed) */
function el(tag,cls,txt){var e=document.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e}
function tip(c){return c.total+' chat'+(c.total!==1?'s':'')+' from '+c.name+' so far'}
function state(c){return c.status==='WAITING'?(c.waited?'waiting '+c.waited:'since '+c.since):'with '+c['with']}
function link(c){var a=el('a');a.href='/chat/'+c.id;a.title=tip(c);return a}
function drawTicker(lv,cs){var shown=cs.length?cs:lv;track.textContent='';
 shown.forEach(function(c){var a=link(c);a.dataset.id=c.id;if(!VIT)a.appendChild(document.createTextNode('💬 '));a.appendChild(el('b',null,c.label));
  a.appendChild(document.createTextNode(' — '+c.subject+' · '+c.board+' · '+state(c)));track.appendChild(a)});
 if(cs.length>1){var n=el('a',null,cs.length+' chats waiting');n.href='/chat';track.appendChild(n)}}
function row(c){var r=el('div','trow'),g=el('div','grow'),a=link(c);r.dataset.id=c.id;a.appendChild(el('b',null,c.label));g.appendChild(a);
 g.appendChild(document.createTextNode(' '));g.appendChild(el('span','muted',c.subject+' · '+c.board+' · '+state(c)));
 if(c.last){var l=el('div','tlast');l.appendChild(el('span','muted',(c.last_from==='desk'?'Desk':c.name.split(' ')[0])+':'));
  l.appendChild(document.createTextNode(' '+c.last));g.appendChild(l)}
 r.appendChild(g);
 if(c.status==='WAITING'&&c.can){var f=el('form');f.method='post';f.action='/chat/'+c.id+'/pick';var b=el('button','small','Pick up');b.type='submit';f.appendChild(b);r.appendChild(f)}
 else if(c.mine){var e=el('a','btn ghost small','End');e.href='/chat/'+c.id+'?end=1';r.appendChild(e)}
 return r}
/* chat round six: who is on, and your own Busy / Away, at the top of the quick view */
function drawWho(ops,me){if(!ops||!ops.length)return;var w=el('div','twho');
 ops.forEach(function(o){var s=el('span','tp');s.title=o.name+' \u00b7 '+o.word;s.appendChild(el('i','pdot p-'+o.state.toLowerCase()));
  s.appendChild(document.createTextNode(' '+o.first+(o.me?' (you)':'')+' \u00b7 '+o.word));w.appendChild(s)});
 panel.appendChild(el('h4',null,'Who is on'));panel.appendChild(w);if(!me)return;
 var f=el('form','tme');f.method='post';f.action='/chat/presence';f.appendChild(el('span','muted','You:'));
 [['AUTO','Automatic'],['BUSY','Busy'],['AWAY','Away']].forEach(function(p){var b=el('button','ghost small'+((me.manual||'AUTO')===p[0]?' on':''),p[1]);
  b.type='submit';b.name='state';b.value=p[0];f.appendChild(b)});
 var bk=el('input');bk.type='hidden';bk.name='back';bk.value=location.pathname+location.search;f.appendChild(bk);panel.appendChild(f)}
function drawPanel(lv,j){panel.textContent='';drawWho(j&&j.operators,j&&j.me);
 [['Waiting',function(c){return c.status==='WAITING'}],['In progress',function(c){return c.status!=='WAITING'}]].forEach(function(p){
  var some=lv.filter(p[1]);if(!some.length)return;panel.appendChild(el('h4',null,p[0]+' ('+some.length+')'));some.forEach(function(c){panel.appendChild(row(c))})});
 if(!lv.length)panel.appendChild(el('p','muted','No live chats.'));
 var f=el('p','tfoot'),a=el('a',null,'Open the Chat queue');a.href='/chat';f.appendChild(a);panel.appendChild(f)}
function hidden(){try{return JSON.parse(sessionStorage.getItem(HID)||'[]')}catch(e){return[]}}
function ids(){return Array.prototype.map.call(panel.querySelectorAll('.trow[data-id]'),function(r){return +r.dataset.id})}
tk.querySelector('.tclose').addEventListener('click',function(){open(false);tk.hidden=true;
 try{sessionStorage.setItem(HID,JSON.stringify(ids()))}catch(e){}});
/* polled in a background tab too: the ring matters most when the desk page is not the one in front */
function look(){fetch('/chat/waiting.json',{credentials:'same-origin'}).then(function(r){return r.ok?r.json():null}).then(function(j){
 if(!j)return;var lv=j.live||[],cs=j.chats||[];
 var key=JSON.stringify([lv,j.operators,j.me]);if(key!==lastL){drawTicker(lv,cs);drawPanel(lv,j);lastL=key}
 word.textContent=(VIT?'':'💬 ')+(j.word||'');tn.textContent=lv.length;
 if(!lv.length){open(false);tk.hidden=true;first=false;return}
 var old=seen(),fresh=cs.filter(function(c){return old.indexOf(c.id)<0});
 var hid=hidden();if(lv.every(function(c){return hid.indexOf(c.id)>=0})){tk.hidden=true;remember(old.concat(fresh.map(function(c){return c.id})));first=false;return}
 track.style.setProperty('--tdur',Math.max(12,8+(cs.length||lv.length)*6)+'s');tk.hidden=false;
 if(fresh.length)ring(true);else if(cs.length)ring(false);remember(old.concat(fresh.map(function(c){return c.id})));first=false}).catch(function(){})}
paint();look();setInterval(look,8000);document.addEventListener('visibilitychange',function(){if(!document.hidden)look()})})();
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
    "minus": "M5 12h14",
    "search": "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14M20 20l-4-4",
    "sun": "M12 3v2M12 19v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M3 12h2M19 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8",
    "ticket": "M3 8a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4zM13 6v12",
    "note": "M21 12a8 8 0 0 1-11.6 7.2L4 20l1.1-4.4A8 8 0 1 1 21 12",
    "lock": "M6 11V8a6 6 0 0 1 12 0v3M5 11h14v10H5z",
    "check": "M20 7 10 17l-5-5",
    "checks": "M3 12l5 5L18 7M8 17l1.5 1.5L21 7",
    "clock": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18M12 7v5l3 2",
    "paperclip": "M20 12l-8.5 8.5a5 5 0 0 1-7-7L13 5a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L15 7",
    "copy": "M9 9h10v10H9zM5 15V5h10",
    "link": "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7L11.5 6.8M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1.5-1.5",
    "monitor": "M3 5h18v11H3zM8 20h8M12 16v4",
    "briefcase": "M3 8h18v12H3zM8 8V5h8v3M3 13h18",
    "info": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18M12 11v5M12 8h.01",
    "inbox": "M3 13h5l2 3h4l2-3h5M3 13l2.5-8h13L21 13v6H3z",
    "users": "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8",
    "tag": "M3 12V4h8l9 9-8 8zM7.5 8h.01",
    "cart": "M3 4h2l2.4 11.2a1 1 0 0 0 1 .8h9.8a1 1 0 0 0 1-.8L21 8H6.5M9 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2M17 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2",
    "alert": "M12 3 2 20h20zM12 10v4M12 17h.01",
    "flag": "M5 21V4M5 4h13l-2 4 2 4H5",
    "x": "M6 6l12 12M18 6 6 18",
    "trash": "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6",
    "filter": "M3 5h18l-7 8v6l-4-2v-4z",
    "arrow": "M5 12h14M13 6l6 6-6 6",
    "keyboard": "M3 6h18v12H3zM7 10h.01M11 10h.01M15 10h.01M7 14h10",
    "mail": "M3 6h18v12H3zM3 7l9 6 9-6",
    "chat": "M4 5h16v11H9l-5 4zM8 10h8",
    "portal": "M3 4h18v16H3zM3 9h18M6.5 6.5h.01M9.5 6.5h.01",
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
    "left": "M19 12H5M12 5l-7 7 7 7",
    "image": "M4 5h16v14H4zM4 15l4-4 4 4 3-3 5 5M15.5 9.5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0",
    "right": "M5 12h14M12 5l7 7-7 7",
    "edit": "M4 20h4l11-11-4-4L4 16zM13 7l4 4",
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

# Dark unless this browser chose light (Dada, 6 Oct 2026: "there are still so
# much white ... this doesnt look futuristic and modern at all"). The toggle
# still flips it, and the choice is remembered per browser.
# Dada, 8 Oct 2026: "add a peach mode a purple mode and a pink mode apart from
# the dark mode and light mode". A tint is the light theme with a colour cast
# over it (data-tint), so every light rule holds and only the tokens change.
TINTS = ("peach", "purple", "pink")
THEME_BOOT = ("<script>try{var r=document.documentElement,t=localStorage.getItem('psa-theme')||'dark',c=localStorage.getItem('psa-tint')||'';"
              "if(t==='peach'||t==='purple'||t==='pink'){c=t;t='light'}r.dataset.theme=t;if(c)r.dataset.tint=c}"
              "catch(e){document.documentElement.dataset.theme='dark'}</script>")



def esc(value) -> str:
    """The one rule. Everything user- or data-derived passes through here before
    it reaches the page."""
    return html.escape("" if value is None else str(value), quote=True)

# ------------------------------------------------------- naming a ticket
#
# Dada, 5 Oct 2026, about linking tickets to each other and to a project:
# *"a dropdown for the tickets would be nice or a search function wherein the
# ticket will be displayed on all ticket fields"*.
#
# Nine forms on this desk used to ask a person to type `PMC-000123` from
# memory: link a related ticket, attach a child, make this a child of, merge
# into, the board's two bulk fields, put a ticket on a project, and the two
# ways of booking a visit. Typing a number from memory is how a ticket gets
# linked to the wrong ticket, and there was nothing in the field to stop it.
#
# This is one control for all nine. It is a text input with a `datalist`, so
# the browser draws its own dropdown with its own keyboard handling and nothing
# here reimplements a listbox. The list is filled from `/search.json` as the
# person types -- the same endpoint the command palette uses, which answers
# only from the boards they are on and audits a restricted board's hits.
#
# **With scripting off it is the plain text input it always was**, so no form
# that worked before stops working. That is also why the ticket number stays
# the value: the form posts exactly what it posted before, and no view had to
# learn a new shape.


def ticket_pick(name: str, placeholder: str = "", *, required: bool = False, value: str = "",
                exclude: str = "", style: str = "") -> str:
    """One field that names a ticket. `exclude` is a ticket the list leaves out
    (a ticket cannot be linked to itself, and offering it is a trap)."""
    pid = "tp" + str(abs(hash((name, placeholder, exclude))) % 10_000_000)
    return (f'<input name={name} list="{pid}" data-tickpick'
            + (f' data-not="{esc(exclude)}"' if exclude else "")
            + f' value="{esc(value)}" placeholder="{esc(placeholder or "Ticket number, or search")}"'
              f' autocomplete=off spellcheck=false{" required" if required else ""}'
            + (f' style="{style}"' if style else "") + f'><datalist id="{pid}"></datalist>')




# ----------------------------------------------------------------- rich text
#
# Dada, 2 Oct 2026: "can we have a text editor so we can properly edit the
# replies or add font themes to it". A note is still plain text in the
# database, which is what the PHI scan reads, what an email carries and what
# the portal shows; the marks a person types are rendered when it is read.
#
# The reading happens in two steps: `blocks()` turns the words into plain data
# (paragraphs, lists, and runs of text that are bold or code or a link), and
# `rich()` turns that data into HTML. The note composer's preview asks for the
# data and builds the nodes itself, so no HTML string is ever handed to a
# browser to parse. Nothing a person writes can become a tag either way.
_B = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", re.S)                    # **bold**
_I = re.compile(r"(?<![\*\w])\*(?=\S)([^\*\n]+?)(?<=\S)\*(?![\*\w])")   # *italic*
_C = re.compile(r"`([^`\n]+)`")                                         # `code`
_URL = re.compile(r"(?<![\w@])(https?://[^\s<>\"]+[^\s<>\".,;:!?)\]])")
_MARK = re.compile(_C.pattern + "|" + _B.pattern + "|" + _I.pattern + "|" + _URL.pattern)


def _runs(line: str) -> list:
    """One line as runs: {"s": the words} with "b", "i", "c" or "a" when the
    writer marked them. Code first, so a mark inside backticks stays the
    characters they typed."""
    out, at = [], 0
    for m in _MARK.finditer(line):
        if m.start() > at:
            out.append({"s": line[at:m.start()]})
        code, bold, ital, url = m.group(1), m.group(2), m.group(3), m.group(4)
        if code is not None:
            out.append({"s": code, "c": 1})
        elif bold is not None:
            out.append({"s": bold, "b": 1})
        elif ital is not None:
            out.append({"s": ital, "i": 1})
        else:
            out.append({"s": url, "a": url})
        at = m.end()
    if at < len(line):
        out.append({"s": line[at:]})
    return out or [{"s": ""}]


def blocks(text) -> list:
    """The words as plain data. A bullet is a dash AND a space: a line like
    "-LESTER M. BALLESTEROS" is a name, not a list (MEASURED against a real
    note, 2 Oct 2026). Anything unmarked stays exactly as it was typed, line
    breaks and all, so a note written before any of this reads as it did."""
    out: list = []
    para: list = []

    def shut():
        if para:
            lines = list(para)
            para.clear()
            out.append({"k": "p", "lines": lines})

    for raw in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        bare = raw.strip()
        if not bare:
            shut()
            continue
        ol = re.match(r"^(\d{1,3})[.)]\s+(.*)$", bare)
        if bare.startswith(("- ", "* ")) or ol:
            shut()
            kind = "ol" if ol else "ul"
            item = _runs((ol.group(2) if ol else bare[2:]).strip())
            if out and out[-1].get("k") == kind:
                out[-1]["items"].append(item)
            else:
                out.append({"k": kind, "items": [item]})
            continue
        if bare.startswith("#") and bare.lstrip("#").startswith(" "):
            shut()
            out.append({"k": "h", "lines": [_runs(bare.lstrip("#").strip())]})
            continue
        if bare.startswith("> "):
            shut()
            out.append({"k": "q", "lines": [_runs(bare[2:].strip())]})
            continue
        para.append(_runs(raw.rstrip()))
    shut()
    return out


INTAKE_KINDS = ("INTAKE", "INTAKE_REPLY")


def is_email_note(body_format, kind=None) -> bool:
    """Whether a note is an email's own HTML: 'EMAIL' from 6 Oct 2026, and the
    'HTML' intake stored for the day before that, which is the same thing
    cleaned under the stricter profile."""
    f = (body_format or "").upper()
    return f == "EMAIL" or (f == "HTML" and kind in INTAKE_KINDS)


EMOJI = ("👍", "👌", "🙏", "😊", "😀", "😅", "😮", "😢", "❤️", "🎉", "✅", "❌", "⚠️", "⏳", "📞", "📧",
         "🖨️", "💻", "🖥️", "🔧", "🔌", "📶", "🔒", "📎")
COLOURS = (("tc-red", "#c62828", "Red"), ("tc-orange", "#c25e00", "Orange"), ("tc-green", "#1a7f37", "Green"),
           ("tc-blue", "#2f52c4", "Blue"), ("tc-purple", "#7b3fbf", "Purple"), ("tc-grey", "#6b7280", "Grey"))
HIGHLIGHTS = (("hl-yellow", "#fff3a3", "Yellow"), ("hl-green", "#c9f2d4", "Green"),
              ("hl-blue", "#cfe3ff", "Blue"), ("hl-pink", "#ffd6e8", "Pink"))


def note_editor(*, placeholder: str, required: bool = True, rows_hint: str = "", text: str = "") -> str:
    """The note box the desk writes in, as a Teams reply box is laid out
    (Dada, 6 Oct 2026: "add extra options for fonts add image attachment gif
    just like when u reply to teams"): a style and a size, bold, italic,
    underline and strikethrough, a text colour and a highlight from a fixed
    palette, lists, a quote, code, a link, an emoji, and a picture or a GIF
    pasted, dropped or attached. One component, on the note composer and in
    the time entry window, so the two never drift apart.

    What goes up is still `body` (HTML) and `body_format`; pictures go up as
    `pics` files with `pic_tokens` naming each, and the note refers to them by
    Content-ID, exactly as an email's inline picture does. Nothing here
    fetches from outside the desk: the emoji are characters, and a GIF is a
    file the technician has."""
    b = lambda do, label, inner, arg="": (  # noqa: E731
        f"<button type=button class=iconbtn data-do={do}" + (f" data-arg='{arg}'" if arg else "")
        + f" title='{esc(label)}' aria-label='{esc(label)}'>{inner}</button>")
    styles = "".join(f"<button type=button data-do=block data-arg={a}>{lab}</button>" for a, lab in (
        ("p", "Paragraph"), ("h3", "<b style='font-size:1.1em'>Heading</b>"), ("h4", "<b>Subheading</b>"),
        ("pre", "<span style='font-family:var(--mono)'>Monospaced</span>")))
    sizes = "".join(f"<button type=button data-do=size data-arg={a}>{lab}</button>" for a, lab in (
        ("2", "<span style='font-size:12px'>Small</span>"), ("3", "Normal"),
        ("5", "<span style='font-size:18px'>Large</span>"), ("6", "<span style='font-size:22px'>Huge</span>")))
    colours = "".join(f"<button type=button class=swatch data-do=color data-arg='{hexv}' title='{n}' aria-label='{n}'"
                      f" style='background:{hexv}'></button>" for _, hexv, n in COLOURS)
    colours += "<button type=button data-do=color data-arg=auto title='Automatic' style='grid-column:1/-1;text-align:center'>Automatic</button>"
    lights = "".join(f"<button type=button class=swatch data-do=hilite data-arg='{hexv}' title='{n}' aria-label='{n} highlight'"
                     f" style='background:{hexv}'></button>" for _, hexv, n in HIGHLIGHTS)
    lights += "<button type=button data-do=hilite data-arg=none title='No highlight' style='grid-column:span 2;text-align:center'>None</button>"
    emoji = "".join(f"<button type=button data-do=emoji data-arg='{e}' aria-label='{e}'>{e}</button>" for e in EMOJI)
    pop = lambda label, face, menu, cls="": (  # noqa: E731
        f"<details class=pop><summary class=iconbtn title='{esc(label)}' aria-label='{esc(label)}'>{face}</summary>"
        f"<div class='menu {cls}'>{menu}</div></details>")
    return (
        "<input type=hidden name=body_format value=HTML>"
        "<input type=file name=pics multiple accept='image/*' hidden class=edpics>"
        "<input type=hidden name=pic_tokens value=''>"
        "<input type=file accept='image/*' multiple hidden class=edpick>"
        "<div class=composer>"
        "<div class=edbar role=toolbar aria-label='Formatting'>"
        "<span class=g>" + pop("Paragraph style", "<b style='font-size:12px'>¶</b>", styles)
        + pop("Text size", "<b style='font-size:12px'>A<span style='font-size:9px'>A</span></b>", sizes) + "</span>"
        "<span class=sep></span><span class=g>"
        + b("bold", "Bold (Ctrl+B)", "<b>B</b>") + b("italic", "Italic (Ctrl+I)", "<i>I</i>")
        + b("underline", "Underline (Ctrl+U)", "<u>U</u>") + b("strikeThrough", "Strikethrough", "<s>S</s>")
        + pop("Font colour", "<span class=aa>A</span>", colours, "sw")
        + pop("Highlight", "<span class=hl>ab</span>", lights, "sw") + "</span>"
        "<span class=sep></span><span class=g>"
        + b("insertUnorderedList", "Bulleted list", "&bull;&#8211;") + b("insertOrderedList", "Numbered list", "<b>1.</b>")
        + b("quote", "Quote", "&ldquo;") + b("code", "Code", "<b style='font-family:var(--mono)'>&lt;&gt;</b>") + "</span>"
        "<span class=sep></span><span class=g>"
        + b("link", "Link", icon("link"))
        + pop("Emoji", "<span style='font-size:15px'>☺</span>", emoji, "emo")
        + b("image", "Picture or GIF: attach one, or paste or drop it in", icon("image"))
        + b("removeFormat", "Clear formatting", icon("x")) + "</span>"
        "<span class=grow></span>"
        "<button type=button class='tab on' data-plain=0 title='Write with formatting'>Rich</button>"
        "<button type=button class=tab data-plain=1 title='Write as plain text'>Plain</button></div>"
        # `text` starts the box with words already in it, as plain text (073: a chat's time entry).
        f"<div class=editor contenteditable=true role=textbox aria-multiline=true aria-label='The note' data-ph='{esc(placeholder)}'>{esc(text)}</div>"
        f"<textarea name=body{' required' if required else ''} placeholder='{esc(placeholder)}'>{esc(text)}</textarea>"
        "<div class=edhint>Paste or drop a screenshot or a GIF straight in. Pictures are kept with the ticket's files and "
        "checked for patient details before a requester sees them." + (f" {esc(rows_hint)}" if rows_hint else "") + "</div>"
        "</div>")


def note_html(detail, body_format=None, *, email: bool = False, kind=None, images=None,
              label: str = "") -> str:
    """A note as it should be read, whichever way it was written (064).

    'HTML' means it was written in the desk's editor and was rebuilt by
    `richtext.clean` before it was stored; it is cleaned again here, because a
    thing read out of a database is a thing from outside. An email's own HTML
    is drawn in its sandbox (`mail_frame`). Anything else is the plain text it
    always was, and reads exactly as it did.

    `email=True` is for a note going out *in* an email: no frame, no stylesheet,
    the spacing written inline (`richtext.email_inline`)."""
    from .. import richtext
    if email:
        if richtext.is_rich(body_format):
            prof = "email" if is_email_note(body_format, kind) else "note"
            return richtext.email_inline(richtext.clean(detail, limit=richtext.READ_MAX, profile=prof))
        return rich(detail, email=True)
    if is_email_note(body_format, kind):
        return mail_frame(detail, images=images, label=label)
    if richtext.is_rich(body_format):
        # READ_MAX, not MAX: re-reading a stored note under a typed note's
        # bound would cut a long one off mid-sentence.
        # A picture pasted into the note is named by Content-ID, as an email's
        # is, and drawn only as this reader may see it (6 Oct 2026).
        html = richtext.clean(detail, limit=richtext.READ_MAX)
        return richtext.resolve_images(html, images) if "cid:" in html else html
    return rich(detail)


def mail_frame(detail, *, images=None, label: str = "") -> str:
    """An email as its sender laid it out, in a sandbox (6 Oct 2026).

    The three layers the research names (see richtext's email profile): the
    gate rebuilt it; this frame keeps its layout and the desk's stylesheet out
    of each other's way -- the desk's paragraph spacing is what put a blank
    line between every line of an Outlook signature; and the frame's own policy
    lets it load nothing but pictures from this desk. The sandbox never gets
    `allow-scripts`. The page sizes the frame to its content (SCRIPT); without
    scripting it is a frame of a sensible height that scrolls."""
    from .. import richtext
    html = richtext.clean(detail, limit=richtext.READ_MAX, profile="email")
    if "<details>" not in html:
        # Stored before today: the gate had dropped the ids and classes the
        # quote markers use, but the bold From:/Sent: header Outlook writes is
        # still there, and is enough to fold the quoted thread now.
        html = richtext.fold(html, profile="email", limit=richtext.READ_MAX) or html
    html = richtext.resolve_images(html, images)
    # A first guess at the height, so the page does not jump when the script
    # fits it: a line per paragraph, list item, heading, rule or break (not a
    # wrapping div or a table row, whose lines are already counted, and not a
    # paragraph the gate emptied), each picture at its own stated height, and
    # the fold's pill. Measured on an Outlook reply: 310 guessed, 295 drawn.
    head = html.split("<details>", 1)[0]
    lines = len(re.findall(r"<(?:p|br|li|h3|h4|hr)\b", head)) - head.count("<p></p>")
    pics = 0
    for tag in re.findall(r"<img\b[^>]*>", head):
        h = re.search(r'\bheight="(\d{1,4})"', tag)
        pics += min(400, int(h.group(1))) if h else 100
    height = max(28, min(1200, 22 * max(1, lines) + pics + (36 if "<details>" in html else 0)))
    return ('<iframe class=mail sandbox="allow-popups allow-popups-to-escape-sandbox allow-same-origin"'
            f' referrerpolicy=no-referrer title="{esc(label or "The email as it was sent")}"'
            f' style="height:{height}px" srcdoc="{esc(richtext.mail_document(html))}"></iframe>')


def desk_images(conn, work_item_id: str):
    """What the desk may see of an email's pictures: any file on the ticket the
    email named, unless it was withheld for patient information or purged.
    A Pending file shows, as it does on the Files card; reviewing it is the
    desk's job."""
    from .. import attachments
    known = attachments.by_content_id(conn, work_item_id)

    def resolve(cid):
        r = known.get(str(cid).lower())
        if r is None:
            return None, None                     # a signature logo intake did not keep
        if r["purged_at"]:
            return None, f"picture {r['filename']}: removed under the retention rule"
        if r["review_status"] == "WITHHELD":
            return None, f"picture {r['filename']}: withheld for patient information"
        if not str(r["media_type"] or "").startswith("image/"):
            return None, f"{r['filename']}: on the Files card"
        return f"/ticket/{work_item_id}/file/{r['attachment_id']}", None
    return resolve


def rich(text, *, email: bool = False) -> str:
    """`blocks()` as safe HTML. `email` adds the inline styles a mail client
    needs, because an email carries no stylesheet."""
    P = ' style="margin:0 0 12px;font-size:15px;line-height:1.55;color:#1f2430"' if email else ""
    UL = ' style="margin:0 0 12px;padding-left:22px"' if email else ""
    LI = ' style="margin:0 0 4px;font-size:15px;line-height:1.5;color:#1f2430"' if email else ""
    H = (' style="margin:14px 0 6px;font-size:16px;font-weight:650;color:#1f2430"' if email else ' class="rh"')
    Q = (' style="margin:0 0 12px;padding:2px 0 2px 12px;border-left:3px solid #d5dae6;color:#3b4454"' if email
         else ' class="rq"')

    def run(r):
        body = esc(r["s"])
        if r.get("c"):
            return "<code>%s</code>" % body
        if r.get("b"):
            return "<b>%s</b>" % body
        if r.get("i"):
            return "<i>%s</i>" % body
        if r.get("a"):
            return '<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>' % (esc(r["a"]), body)
        return body

    def line(rs):
        return "".join(run(r) for r in rs)

    out = []
    for b in blocks(text):
        if b["k"] == "p":
            out.append("<p%s>%s</p>" % (P, "<br>".join(line(l) for l in b["lines"])))
        elif b["k"] == "h":
            out.append("<div%s>%s</div>" % (H, line(b["lines"][0])))
        elif b["k"] == "q":
            out.append("<div%s>%s</div>" % (Q, line(b["lines"][0])))
        else:
            out.append("<%s%s>%s</%s>" % (b["k"], UL,
                                          "".join("<li%s>%s</li>" % (LI, line(i)) for i in b["items"]), b["k"]))
    return "".join(out) or ("<p%s></p>" % P)


def _inline(text: str, file_url=None) -> str:
    """Escape, then the two inline shapes the reports actually emit: **bold** and
    `code`. Escaping first is what keeps this safe — the markers are literal
    characters html.escape leaves alone, so the regex sees only them.

    051: an article may show an image, ![caption](file:N), and link,
    [text](https://…) or [text](file:N). `file_url` says what file N is to
    this reader (its address, or None: then the caption stands in). The tags
    are parked as placeholders while the emphasis runs, so an address never
    grows an <em>."""
    out = esc(text)
    parked: list[str] = []

    def park(html_: str) -> str:
        parked.append(html_)
        return f"\x00{len(parked) - 1}\x00"

    def img(m):
        alt, n = m.group(1), int(m.group(2))
        url = file_url(n) if file_url else None
        if not url:
            return park(f"<span class=muted>[image not shown: {alt or 'file ' + str(n)}]</span>")
        return park(f'<img src="{esc(url)}" alt="{alt}" class=kbimg loading=lazy>')

    def link(m):
        words, target = m.group(1), m.group(2)
        if target.startswith("file:"):
            url = file_url(int(target[5:])) if file_url else None
            if not url:
                return park(f"<span class=muted>[{words}: file not shown]</span>")
            return park(f'<a href="{esc(url)}">{words}</a>')
        return park(f'<a href="{target}" rel="noopener noreferrer">{words}</a>')

    out = re.sub(r"!\[([^\]]*)\]\(file:(\d+)\)", img, out)
    out = re.sub(r"\[([^\]]+)\]\((https://[^\s)]+|file:\d+)\)", link, out)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    # Emphasis last, after **bold** has consumed its pairs. Word-bounded so a
    # snake_case name or an arithmetic * is left alone.
    out = re.sub(r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", out)
    out = re.sub(r"(?<![\w])_(?!\s)([^_\n]+?)(?<!\s)_(?![\w])", r"<em>\1</em>", out)
    return re.sub(r"\x00(\d+)\x00", lambda m: parked[int(m.group(1))], out) if parked else out


def md_to_html(md: str, *, file_url=None) -> str:
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
            out.append("<p>" + "<br>".join(_inline(p, file_url) for p in para) + "</p>")
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
            out.append(f"<h{level}>{_inline(m.group(2), file_url)}</h{level}>")
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
            head_html = "".join(f"<th>{_inline(c, file_url)}</th>" for c in header)
            rows_html = "".join(
                "<tr>" + "".join(f"<td>{_inline(c, file_url)}</td>" for c in r) + "</tr>"
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


_PRIO: dict[str, dict] = {}


def set_priorities(table: dict[str, dict]) -> None:
    """060: the Priority setup table for this request: each code's name and
    colour, so every badge says the hospital's word for it."""
    global _PRIO
    _PRIO = dict(table or {})


def priority_name(code: str) -> str:
    r = _PRIO.get(code)
    return r["name"] if r else (code or "")


def badge(priority) -> str:
    from ..priorities import PAINT
    p = priority if priority in ("P1", "P2", "P3", "P4") else ""
    r = _PRIO.get(p)
    style = f' style="background:{PAINT.get(r["color"], "")}"' if r and r.get("color") in PAINT else ""
    title = f' title="{esc(r["name"])}"' if r else ""
    return f'<span class="badge {p}"{style}{title}>{esc(priority or "—")}</span>'


# One chip per Dada PSA clock: Respond, resolution Plan, reSolve.
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

QUICK_KEYS = ("board", "dispatch", "schedule", "time")


def _quick_default(nav_items) -> str:
    """The phone's bottom bar for the desk (gap 5): the first sections the
    person may see, and a new ticket. CSS shows it under 640 px only."""
    items = [(href, key, label) for key, href, label in nav_items if key in QUICK_KEYS][:4]
    items.append(("/ticket/new", "plus", "New"))
    return "<nav class=quick aria-label='Sections'>" + "".join(
        f"<a href='{esc(href)}'>{icon({'schedule': 'calendar', 'time': 'clock'}.get(key, key))}"
        f"<span>{esc(label if key != 'board' else 'Board')}</span></a>" for href, key, label in items) + "</nav>"


def chat_ticker(live) -> tuple[str, str]:
    """The banner's word and its running line (072, 7 Oct 2026). Chats waiting
    run across it; with none waiting, the ones being answered do. Each is known
    by whose it is and which of theirs: "Jun Reyes · chat 3"."""
    waiting = [c for c in live if c["status"] == "WAITING"]
    shown = waiting or list(live)
    out = []
    for c in shown:
        tail = (f" · waiting {c['waited']}" if c["waited"] else f" · since {c['since']}") if c["status"] == "WAITING" \
            else f" · with {c['with']}"
        out.append(f"<a href='/chat/{c['id']}' data-id='{c['id']}' title='{c['total']} chat{'s' if c['total'] != 1 else ''}"
                   f" from {esc(c['name'])} so far'>💬 <b>{esc(c['label'])}</b> — {esc(c['subject'])}"
                   f" · {esc(c['board'])}{esc(tail)}</a>")
    if len(waiting) > 1:
        out.append(f"<a href='/chat'>{len(waiting)} chats waiting</a>")
    return ("New chat" if waiting else "Live chats"), "".join(out)


def chat_panel(live) -> str:
    """The banner's quick view: every live chat on the person's boards, waiting
    first with Pick up, then who has the rest, each with its last line."""
    def row(c):
        pick = (f"<form method=post action='/chat/{c['id']}/pick'><button type=submit class=small>Pick up</button></form>"
                if c["status"] == "WAITING" and c.get("can") else
                # 074: End on a chat that is yours opens it with its end window up
                f"<a class='btn ghost small' href='/chat/{c['id']}?end=1'>End</a>" if c.get("mine") else "")
        state = (f"waiting {c['waited']}" if c["waited"] else f"since {c['since']}") if c["status"] == "WAITING" \
            else f"with {c['with']}"
        last = (f"<div class=tlast><span class=muted>{'Desk' if c['last_from'] == 'desk' else esc(c['name'].split(' ')[0])}:</span>"
                f" {esc(c['last'])}</div>" if c["last"] else "")
        return (f"<div class=trow data-id='{c['id']}'><div class=grow><a href='/chat/{c['id']}' title='{c['total']} chat"
                f"{'s' if c['total'] != 1 else ''} from {esc(c['name'])} so far'><b>{esc(c['label'])}</b></a>"
                f" <span class=muted>{esc(c['subject'])} · {esc(c['board'])} · {esc(state)}</span>{last}</div>{pick}</div>")
    waiting = [row(c) for c in live if c["status"] == "WAITING"]
    going = [row(c) for c in live if c["status"] != "WAITING"]
    return ((f"<h4>Waiting ({len(waiting)})</h4>" + "".join(waiting) if waiting else "")
            + (f"<h4>In progress ({len(going)})</h4>" + "".join(going) if going else "")
            + ("" if live else "<p class=muted>No live chats.</p>")
            + "<p class=tfoot><a href='/chat'>Open the Chat queue</a></p>")


def _chat_banner(user, *, vitals: bool = False) -> str:
    """Drawn by the server already filled, so it is there from the first paint
    and nothing below it moves when the page loads. On a PMC Vitals Console
    page the glyphs are the desk's 16px stroke icons, never emoji (the design
    system forbids them; its script keeps to that on body.vitals too)."""
    live = getattr(user, "live_chats", None) or []
    word, items = chat_ticker(live)
    out = _chat_banner_html(live, word, items)
    if vitals:
        out = out.replace("💬 ", "").replace(">🔔<", ">" + icon("bell") + "<")
    return out


def _chat_banner_html(live, word, items) -> str:
    return ("<div id=chatticker class=ticker" + ("" if live else " hidden") + " role=status aria-live=polite>"
            f"<b class=tlabel>💬 {esc(word)}</b><div class=tview><div class=ttrack>{items}</div></div>"
            f"<button type=button class='btn tlive' aria-expanded=false aria-controls=chatlive><span>Live chats (<span class=tn>{len(live)}</span>) ▾</span></button>"
            "<a class='btn topen' href='/chat'>Open Chat</a>"
            "<button type=button class='iconbtn tsound' title='Chime on or off' aria-label='Chime on or off'>🔔</button>"
            "<button type=button class='iconbtn tclose' title='Hide until the next new chat' aria-label='Hide'>✕</button>"
            f"<div id=chatlive class=tpanel role=dialog aria-label='Live chats' hidden>{chat_panel(live)}</div></div>")


def viewer_html() -> str:
    """The file viewer's dialog (views/files.viewer_dialog, and the script's copy
    for a page without one): Previous, Next, the name, the size, the place in
    the list, Download, Open in a tab, Close."""
    return ("<dialog id=viewer class=viewer aria-label='File viewer'><div class=vbar>"
            "<button type=button class='iconbtn' data-vprev title='Previous (left arrow)' aria-label='Previous file'>" + icon("left") + "</button>"
            "<button type=button class='iconbtn' data-vnext title='Next (right arrow)' aria-label='Next file'>" + icon("right") + "</button>"
            "<b class=vname></b><span class='vsize muted'></span><span class='vpos muted' aria-live=polite></span>"
            "<span class=grow></span><a class='btn ghost small' data-vdl href='#'>Download</a> "
            "<a class='btn ghost small' data-vopen href='#' target=_blank rel=noopener>Open in a tab</a> "
            "<button type=button class='iconbtn' data-close title='Close (Esc)' aria-label='Close'>" + icon("x") + "</button></div>"
            "<div class=vbody></div></dialog>")


def _vitals(active: str) -> bool:
    """The pages built to the PMC Vitals Console design system: Procurement's
    (every page whose menu key is the area's or one of its modules)."""
    return active in VITALS_KEYS


VITALS_KEYS = frozenset({"signin", "error", "procurement", "popurchreq", "popo", "porr", "postockreq", "poexpreq", "poissue", "poexpissue", "pocount",
                         "poitems", "postock", "pomoves", "powh", "podrugs", "poreports", "pochanges"})


# BizBox's own module numbers beside its modules in the menu, measured from appsysModules (SQL01, Part 104).
# Warehouses and Drugs are submodules of MM02, so they carry none: showing one would be inventing it.
MM_BADGE = {"poitems": "MM02", "popurchreq": "MM03", "popo": "MM04", "postockreq": "MM06", "poissue": "MM07",
            "poexpreq": "MM08", "poexpissue": "MM09", "pocount": "MM12", "porr": "MM20"}


def page(title: str, body: str, *, user=None, active: str = "", requester: bool | None = None,
         quick: str | None = None, live: str | None = None) -> str:
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
    # The menu as the reference PSA's modules: a few words across the top,
    # each opening its pages (Dada, 1 Oct 2026: "the menu cuts off use the
    # connectwise menu or do a proper mega menu"). A module with one page is
    # a plain link. Hover or click opens a panel; Escape or a click outside
    # closes it; the keyboard walks it.
    groups = [
        ("service", "Service Desk", [
            ("board", "/", "Service Board", "Every ticket, by board"),
            ("dispatch", "/dispatch", "Dispatch", "Who is where today; drag to book"),
            ("schedule", "/schedule", "Schedule", "The week, by person"),
            ("calendar", "/calendar", "Calendar", "Mine or anyone's: day, week, month"),
            ("chat", "/chat", "Chat", "Ward staff waiting to talk to the desk"),
            ("oncall", "/oncall", "On-call", "Who answers after hours"),
            ("kb", "/kb", "Knowledge", "Articles for the desk and the wards")]),
        ("companies", "Companies", [
            ("companies", "/companies", "Companies", "Departments, suppliers, contacts"),
            ("sales", "/sales", "Sales", "Opportunities and quotes")]),
        # Dada, 7 Oct 2026: "there should also be a configurations menu". Its own
        # module across the bar, with the pages a technician reaches for.
        ("configurations", "Configurations", [
            ("configurations", "/configurations", "Configurations", "Every machine, printer and device, and what they are"),
            ("cfgnew", "/configurations#cfgnew", "New configuration", "A device Active Directory does not know"),
            ("cfgcsv", "/configurations/maintenance.csv", "Maintenance record", "Every ticket on every machine, as CSV")]
         + ([("cfgtypes", "/admin/configuration-types", "Configuration types", "Types, statuses and their questions"),
             ("cfgint", "/admin/integrations", "Integrations", "Where configurations come from")]
            if user is not None and getattr(user, "is_sysadmin", False) else [])),
        ("projects", "Projects", [("projects", "/projects", "Projects", "")]),
        ("time", "Time", [("time", "/time", "Time", "")]),
        ("finance", "Finance", [("finance", "/finance", "Finance", "")]),
        # 13 Oct 2026: BizBox's MMS as its own Procurement module (Dada).
        # 14 Oct 2026: BizBox's MMS module list, as its catalogue names them, each
        # shown per the member's module rights (SQL01's review; Dada: "the side
        # bar should be placed on the top"). What the desk does not carry yet
        # says so on its page rather than hiding.
        ("procurement", "Procurement", [
            ("procurement", "/procurement", "Overview", "What BizBox's MMS holds, what moved, what waits"),
            ("popurchreq", "/procurement?tab=purchase_req", "Purchase Requisitions", "Raised here, approved here, created in BizBox"),
            ("popo", "/procurement?tab=purchase_order", "Purchase Orders", "Every order, as a document"),
            ("porr", "/procurement?tab=invoice", "Receiving", "BizBox's receiving reports"),
            ("postockreq", "/procurement?tab=stock_req", "Stock Requisitions", "Stock on hand at the source as you pick"),
            ("poexpreq", "/procurement?tab=expense_req", "Expense Requisitions", "The screen 655 people hold, on the desk"),
            ("poissue", "/procurement?tab=stock_issuance", "Stock Issuances", "Issued from a warehouse to a department"),
            ("poexpissue", "/procurement?tab=expense_issuance", "Expense Issuances", "Issued against an expense requisition"),
            ("pocount", "/procurement?tab=physical_count", "Physical Count", "Counted against what the ledger says"),
            ("poitems", "/procurement?tab=product", "Items", "Every item BizBox has"),
            ("postock", "/procurement?tab=stock", "Stock on hand", "What each warehouse holds, from the ledger"),
            ("pomoves", "/procurement?tab=movement", "Movements", "The item ledger by window"),
            ("powh", "/procurement?tab=warehouse", "Warehouses", "The 73 warehouses in their groups"),
            ("podrugs", "/procurement?tab=medicine", "Drugs", "Every item BizBox marks as a medicine"),
            ("poreports", "/procurement?tab=reports", "Reports", "The report server's reports, as PDF or Excel"),
            ("pochanges", "/procurement?tab=changes", "Changes", "What waits for approval or the push")]),
        ("reports", "Reports", [
            ("reports", "/reports", "Reports", "KPIs, monthly charts, the writer"),
            ("uplift", "/uplift", "Uplift", "The programme's evidence")]),
        ("admin", "Setup", [("admin", "/admin", "Setup", "")]),
        ("my", "My requests", [("my", "/my", "My requests", "")]),
    ]
    levels = getattr(user, "modules", None) or {}
    gate = {"schedule": "SCHEDULE", "projects": "PROJECTS", "kb": "KNOWLEDGE", "reports": "REPORTS",
            "finance": "FINANCE", "sales": "FINANCE", "time": "TIME", "calendar": "SCHEDULE",
            "procurement": "PROCUREMENT", "pochanges": "PROCUREMENT", "poreports": "PROCUREMENT", "podrugs": "PROC_DRUG",
            "postock": "PROC_ITEM", "pomoves": "PROC_ITEM", "popurchreq": "PROC_PURCHREQ", "popo": "PROC_PO", "porr": "PROC_RR",
            "postockreq": "PROC_STOCKREQ", "poexpreq": "PROC_EXPREQ", "poissue": "PROC_ISSUE", "poexpissue": "PROC_EXPISSUE",
            "pocount": "PROC_COUNT", "poitems": "PROC_ITEM", "powh": "PROC_ITEM"}     # 086: one module per entry
    groups = [(g, label, [pg for pg in pages if pg[0] not in gate or levels.get(gate[pg[0]], "READ") != "NONE"])
              for g, label, pages in groups]
    # 073: the desk's Chat is for chat operators (Dada, 7 Oct 2026).
    if not getattr(user, "chat_operator", False):
        groups = [(g, label, [pg for pg in pages if pg[0] != "chat"]) for g, label, pages in groups]
    groups = [g for g in groups if g[2]]
    if requester:
        groups = [("my", "My requests", [("my", "/my", "My requests", "")]),
                  ("chat", "Chat", [("chat", "/my/chat", "Chat with the helpdesk", "")]),
                  ("approvals", "Approvals", [("approvals", "/my/approvals", "Approvals", "")]),
                  ("help", "Help", [("help", "/my/help", "Help", "")])]
        if active not in ("help", "approvals", "chat"):
            active = "my"
    nav_items = [(key, href, name) for _, _, pages in groups for key, href, name, _ in pages]   # the phone's quick bar
    icons = {"admin": "setup", "schedule": "grip", "projects": "layers", "kb": "note", "finance": "tag", "sales": "briefcase",
             "help": "note", "time": "clock", "approvals": "check", "service": "ticket", "configurations": "monitor",
             "chat": "note", "cfgnew": "plus", "cfgcsv": "reports", "cfgtypes": "setup", "cfgint": "link",
             "procurement": "cart", "pochanges": "checks", "poreports": "reports", "podrugs": "tag", "postock": "layers", "pomoves": "rows",
             "popurchreq": "note", "popo": "cart", "porr": "inbox", "postockreq": "note", "poexpreq": "note", "poissue": "arrow", "poexpissue": "arrow",
             "pocount": "checks", "poitems": "tag", "powh": "building"}

    def one(key, href, label, cls="", current=False):
        return (f'<a href="{esc(href)}" title="{esc(label)}" class="{cls}{" on" if current else ""}"'
                f'{" aria-current=page" if current else ""}>{icon(icons.get(key, key))}<span class=lbl>{esc(label)}</span></a>')

    # A mega menu (Dada, 1 Oct 2026: "do a mega menu instead or side menu
    # whichever fits best"): the modules across the bar, each a word that
    # opens its pages beneath it on hover, click or keyboard, so every page
    # is one hover away and the pages keep their full width (a side rail
    # would take it from the Dispatch grid and the tables). A module with
    # one page is a plain link. The module that holds the page is underlined.
    def panel(g, label, pages):
        links = "".join(
            f'<a href="{esc(href)}" role=menuitem{" class=on aria-current=page" if key == active else ""}>'
            f'{icon(icons.get(key, key))}<b>{esc(name)}</b>' + (f'<i class=mm title="BizBox module {MM_BADGE[key]}">{MM_BADGE[key]}</i>' if key in MM_BADGE else "")
            + (f'<span class=why>{esc(blurb)}</span>' if blurb else "") + '</a>'
            for key, href, name, blurb in pages)
        on = any(pg[0] == active for pg in pages)
        return (f'<div class="grp{" on" if on else ""}"><button type=button class="top{" on" if on else ""}" title="{esc(label)}" aria-haspopup=true'
                f' aria-expanded=false>{icon(icons.get(g, g))}<span class=lbl>{esc(label)}</span>{icon("chevron", "chev")}</button>'
                f'<div class="panel{" wide3" if len(pages) > 9 else " wide" if len(pages) > 4 else ""}" role=menu aria-label="{esc(label)}">{links}</div></div>')
    if requester:                                 # three pages: plain links, no menu to open
        nav = "".join(one(pg[0], pg[1], pg[2], cls="top", current=pg[0] == active) for _, _, pages in groups for pg in pages)
    else:
        nav = "".join(panel(g, label, pages) if len(pages) > 1 else one(pages[0][0], pages[0][1], label, cls="top", current=pages[0][0] == active)
                      for g, label, pages in groups)
        # On a phone the words do not fit across: one Menu button opens every
        # module stacked, the same pages (CSS swaps the two by width).
        cols = "".join(
            f'<div class=col><div class=modname>{icon(icons.get(g, g))}{esc(label)}</div>' + "".join(
                f'<a href="{esc(href)}" role=menuitem{" class=on aria-current=page" if key == active else ""}>'
                f'{icon(icons.get(key, key))}<b>{esc(name)}</b>' + (f'<span class=why>{esc(blurb)}</span>' if blurb else "") + '</a>'
                for key, href, name, blurb in pages) + '</div>'
            for g, label, pages in groups)
        nav += (f'<div class="grp all"><button type=button class="top" aria-haspopup=true aria-expanded=false>{icon("rows")}'
                f'<span class=lbl>Menu</span></button><div class="panel full" role=menu aria-label="Menu">{cols}</div></div>')
    if active == "signin":                        # the sign-in page: the bar and the brand, no menu to a page it cannot open
        nav = ""
    nav += (f'<a class="newbtn" href="/ticket/new" title="New ticket (n)">{icon("plus")}<span class=lbl>New ticket</span></a>'
            if user is not None and not requester else "")
    who = ""
    if user is not None:
        glass = ('<span class="glass">break-glass</span> · ' if user.via == "local" else "")
        tools = ""
        if not requester:
            tools = ('<button class="iconbtn" id="pal-open" type="button" title="Search and commands (Ctrl+K)"'
                     f' aria-label="Search and commands">{icon("search")}<span class=kbd>⌘K</span></button>'
                     '<button class="iconbtn" type="button" popovertarget="keys" title="Keyboard shortcuts (?)"'
                     f' aria-label="Keyboard shortcuts">{icon("keyboard")}</button>')
        shown_name = esc(user.name) if requester else f'<a href="/my/profile" title="My profile">{esc(user.name)}</a>'
        who = (f'<div class="who">{glass}<span class=name>{shown_name}</span>'
               f'<span class=sep> · </span><a href="/logout">sign out</a>' + tools +
               f'<button class="iconbtn" id="textsize" type="button" title="Text size"'
               f' aria-label="Text size"><b style="font-size:13px;letter-spacing:-.5px">Aa</b></button>'
               f'<button class="iconbtn" id="theme" type="button" title="Theme: dark or light, and classic, peach, purple or pink (t flips dark and light)"'
               f' aria-label="Theme" aria-haspopup="menu" aria-expanded="false">{icon("sun")}</button></div>')
    palette = ""
    if user is not None and not requester:
        palette = (
            '<dialog id="pal" aria-label="Commands"><div class="pal-box">'
            '<input id="pal-q" aria-label="Search" autocomplete="off" spellcheck="false" placeholder="Go to a page, open PMC-000123, or search this board…">'
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
        f"<title>{esc(title)} · {'PMC Requests' if requester else 'Dada PSA'}</title>{THEME_BOOT}"
        f"<style>{STYLE}</style></head><body{' data-requester' if requester else ''}{' class=vitals' if _vitals(active) else ''}>"
        f'<div id="nprog" aria-hidden="true"></div>{SPRITE}'
        '<a class=skip href="#main">Skip to content</a>'
        f'<header class="top"><a class="brand" href="{"/my" if requester else "/"}"><i></i>'
        f'<span>{"PMC Requests" if requester else "Dada PSA"}</span></a>'
        f"<nav class=mega aria-label='Main'>{nav}</nav>{who}</header>"
        # 072: waiting chats run across the top of every desk page, right to left,
        # with a chime (Dada, 7 Oct 2026). Filled by the script from /chat/waiting.json.
        + (_chat_banner(user, vitals=_vitals(active))
           if user is not None and not requester else "")
        + (f"<main id=main tabindex=-1 data-live='{esc(live)}'>" if live else "<main id=main tabindex=-1>") + f"{body}</main>"
        + (quick if quick is not None else (_quick_default(nav_items) if user is not None and not requester else ""))
        + ("<footer>PMC Requests — a request reaches the department it is for.</footer>" if requester else
           "<footer>PMC PSA spine — Phase B pilot. LAN only, Dada IT only. "
           "Kitameraki remains the system of record until dual-run ends.</footer>")
        +
        f"{palette}<template id=viewertpl>{viewer_html()}</template><script>{SCRIPT}</script></body></html>")


def error_page(status: str, message: str = "", *, user=None, requester: bool | None = None) -> str:
    """One error template in the desk's chrome (SQL01's review of 7d037f5: a
    403 or 404 was a bare heading in the browser's serif, no landmarks, no way
    back). The bar, the sentence the view already says, and a way back."""
    code, _, words = status.partition(" ")
    words = words or "Error"
    if requester is None:
        requester = user is not None and getattr(user, "requester", False)
    home = ("/my", "Back to my requests") if requester else ("/", "Back to the board")
    body = (f'<section class="errpage card" aria-labelledby=err-title><p class=errcode>{esc(code)}</p>'
            f'<h1 id=err-title>{esc(words)}</h1>'
            + (f'<p>{esc(message)}</p>' if message else "")
            + f'<p class=errback><a class="btn ghost" href="{home[0]}">{home[1]}</a></p></section>')
    return page(words, body, user=user, requester=requester, active="error")


def login_page(*, entra_configured: bool, error: str = "", next_url: str = "/",
               windows_domain: str | None = None, requester: bool = False, door: str = "") -> str:
    """The sign-in page. On the portal host it wears the requester's brand
    (PMC Requests), so a ward's first sight of its own address is not the
    product's name (SQL01, part 14).

    15 Oct 2026 (SQL01's review of 7d037f5; Dada: "we can do better on the
    login screen"): one plain *Sign in* for everyone, built to the PMC Vitals
    Console tokens, both fields named by a <label for>. The break-glass door's
    wording - the on-call rota's, when the WAN is down - shows only on its own
    route (`/login?door=local`) or after a sign-in through Microsoft fails;
    the ordinary page links to it in one muted line. Where the desk has no
    Windows or Entra sign-in, the local door is the only one and is just
    *Sign in*."""
    other = bool(windows_domain or entra_configured)   # is there a door besides the local one
    glass = door == "local" and other
    err = f'<div class="banner err" role=alert>{esc(error)}</div>' if error else ""
    nxt = f'<input type="hidden" name="next" value="{esc(next_url)}">'
    from urllib.parse import quote
    q = esc(quote(next_url, safe="/"))

    def fields(which: str) -> str:
        return (f'<form class="stack" method="post" action="/login"><input type="hidden" name="door" value="{which}">{nxt}'
                '<div class=field><label for=si-user>Username</label>'
                '<input id=si-user name=username autocomplete=username autocapitalize=none spellcheck=false required autofocus></div>'
                '<div class=field><label for=si-pass>Password</label>'
                '<input id=si-pass name=password type=password autocomplete=current-password required></div>'
                '<button type=submit>Sign in</button></form>')
    if glass:
        card = ('<h1>Break-glass sign in</h1>'
                '<p class="sub glassnote">For the on-call rota, when the WAN is down. Every use is audited.</p>'
                + err + fields("local")
                + f'<p class=alt><a href="/login?next={q}">Back to sign in</a></p>')
    else:
        sub = (f'With your Windows account, the one you use on your PC ({esc(windows_domain)}).' if windows_domain
               else "With your organisation account." if entra_configured else "With your desk account.")
        card = '<h1>Sign in</h1>' + f'<p class=sub>{sub}</p>' + err
        if windows_domain or not entra_configured:
            card += fields("windows" if windows_domain else "local")
        if entra_configured:
            card += (('<p class=or><span>or</span></p>' if windows_domain else "")
                     + f'<a class="btn{" ghost" if windows_domain else ""} wide" href="/entra/start?next={q}">'
                     "Sign in with Microsoft Entra</a>")
        if other and not requester:
            card += f'<p class=alt><a href="/login?door=local&amp;next={q}">Other ways to sign in</a></p>'
    body = f'<section class="signin" aria-labelledby=si-title><div class="card signcard">{card}</div></section>'
    body = body.replace("<h1>", "<h1 id=si-title>", 1)
    return page("Sign in", body, requester=requester, active="signin")
