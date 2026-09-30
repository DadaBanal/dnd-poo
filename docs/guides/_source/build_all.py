import base64, json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import g_common as C
import g_money, g_desk, g_work, g_admin, g_staff  # noqa: F401  (each appends to C.GUIDES)

S = pathlib.Path(__file__).parent
OUT = pathlib.Path("/home/user/dnd-poo/docs/guides")
OUT.mkdir(exist_ok=True)
shell = (S / "shell.html").read_text()
lib = (S / "lib.js").read_text()
idx = pathlib.Path("/home/user/dnd-poo/apps/imaging-portal/src/index.html").read_text()
LOGO_FULL = re.search(r'<img class="full" src="(data:image/png;base64,[^"]+)"', idx).group(1)
LOGO_MARK = re.search(r'<img class="mark" src="(data:image/png;base64,[^"]+)"', idx).group(1)

# hotspot positions, as a percentage of each screenshot
H = {"board": 780, "ticket": 900, "portal": 780, "fin-procurement": 780, "fin-invoice": 900, "fin-agreement": 900, "dispatch": 900,
     "rule": 900, "time-approve": 780, "sales-quote": 1100, "project": 900}
boxes = {}
for f in ("boxes.out.json", "boxes2.out.json"):
    boxes.update(json.loads((S / f).read_text()))
boxes["dispatch"][2] = {"n": 3, "x": 860, "y": 236, "w": 170, "h": 36}
SPOTS = {k: [{"n": b["n"], "x": round(100 * max(16, b["x"] + (0 if b["w"] < 200 else 14)) / 1280, 2), "y": round(100 * max(16, b["y"]) / H[k], 2)} for b in v]
         for k, v in boxes.items()}
ORDER = ["Staff", "PMC_Requests", "Service_Desk", "Dispatch_OnCall", "Change", "Scheduling", "Time", "Knowledge", "Companies_Configurations", "Projects", "Reports", "Finance", "Sales", "Setup"]
C.GUIDES.sort(key=lambda g: ORDER.index(g["slug"]))
TOURS = {}
for g in C.GUIDES:
    TOURS.update(g.get("tours", {}))


def uri(name):
    return "data:image/jpeg;base64," + base64.b64encode((S / "img" / f"{name}.jpg").read_bytes()).decode()


report = []
for g in C.GUIDES:
    C.USED.clear(); C.PICKS.clear()
    body = g["body"]()
    tours_here = sorted(set(re.findall(r'data-tour="([a-z0-9-]+)"', body)))
    for n in sorted(C.USED):
        body = body.replace(f"%%IMG:{n}%%", uri(n))
    for n in sorted(C.PICKS):
        body = body.replace(f"%%PICK:{n}%%", uri(n))
    data = {"spots": {k: SPOTS[k] for k in tours_here}, "tours": {k: TOURS[k] for k in tours_here},
            "quiz": g.get("quiz", []), "images": {n: uri(n) for n in sorted(C.PICKS)}}
    chips = ('<div class="roles" role="group" aria-label="Show sections for"><span>Show for</span>'
             '<button class="chip" data-role="all" aria-pressed="true">Everyone</button><button class="chip" data-role="R" aria-pressed="false">Ward staff</button>'
             '<button class="chip" data-role="T" aria-pressed="false">Technicians</button><button class="chip" data-role="M" aria-pressed="false">Managers</button>'
             '<button class="chip" data-role="A" aria-pressed="false">Administrators</button></div>') if g.get("chips") else ""
    toc_top = "" if g["slug"] == "Staff" else f'<a class="toc__back" href="{C.fname("Staff")}#library">← All guides</a>'
    foot = (f"{C.E(g['title'])} · Dada PSA · Premiere Medical Center Nueva Ecija · Dada IT · 30 September 2026. Screens are from a demonstration desk "
            "with made-up staff, tickets and supplier records; your boards, names and numbers will differ. SLA targets are set per board by its service manager. "
            f'<a href="{C.fname("Staff")}#library">All guides</a>')
    page = (shell.replace("%%TITLE%%", C.E(g["title"].replace(" (start here)", ""))).replace("%%SLUG%%", g["slug"])
            .replace("%%RAIL_TITLE%%", C.E(g["title"].replace(" (start here)", ""))).replace("%%RAIL_SUB%%", C.E(g["rail_sub"]))
            .replace("%%TOC_TOP%%", toc_top).replace("%%SEARCH_HINT%%", C.E(g["search"])).replace("%%CHIPS%%", chips)
            .replace("%%FOOT%%", foot).replace("%%LOGO_FULL%%", LOGO_FULL).replace("%%LOGO_MARK%%", LOGO_MARK)
            .replace("%%DATA%%", json.dumps(data).replace("</", "<\\/")).replace("%%BODY%%", body).replace("%%LIB%%", lib))
    left = re.findall(r"%%[A-Z_]+(?::[a-z0-9-]+)?%%", page)
    assert not left, (g["slug"], left[:5])
    dst = OUT / C.fname(g["slug"])
    dst.write_text(page)
    report.append((dst.name, round(dst.stat().st_size / 1e6, 2), len(C.USED | C.PICKS), len(tours_here),
                   body.count('class="widget"') + body.count('data-w="imgpick"'), body.count('class="s"')))
for r in report:
    print("%-52s %5.2f MB  %2d images  %d tours  %2d tools  %2d sections" % r)
print("total", round(sum(r[1] for r in report), 1), "MB")
