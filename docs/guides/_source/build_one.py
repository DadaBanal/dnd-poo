"""Build the whole guide library as ONE html: a front page, and every guide inside it."""
import base64, json, pathlib, re, sys
S = pathlib.Path(__file__).parent
sys.path.insert(0, str(S))
import g_common as C
import g_money, g_desk, g_work, g_admin, g_staff  # noqa: F401

ORDER = ["Staff", "PMC_Requests", "Service_Desk", "Dispatch_OnCall", "Change", "Scheduling", "Time", "Knowledge",
         "Companies_Configurations", "Projects", "Reports", "Finance", "Sales", "Setup"]
C.GUIDES.sort(key=lambda g: ORDER.index(g["slug"]))
GROUPS = [("For everyone", ["Staff", "PMC_Requests"]),
          ("Working the desk", ["Service_Desk", "Dispatch_OnCall", "Change", "Scheduling", "Time", "Knowledge", "Companies_Configurations"]),
          ("Running the service", ["Projects", "Reports", "Finance", "Sales"]), ("Setting up", ["Setup"])]
ROLES = {"Staff": "R T M A", "PMC_Requests": "R", "Service_Desk": "T M", "Dispatch_OnCall": "T M", "Change": "T M", "Scheduling": "T M",
         "Time": "T M", "Knowledge": "T M", "Companies_Configurations": "T M", "Projects": "M T", "Reports": "M", "Finance": "M",
         "Sales": "M", "Setup": "A"}
import os
OUT = pathlib.Path(os.environ.get("GUIDE_OUT", "/home/user/dnd-poo/docs/guides/PMC_Dada_PSA_Guides_20260930.html"))
IMGDIR, IMGEXT, IMGMIME = os.environ.get("GUIDE_IMGDIR", "img"), os.environ.get("GUIDE_IMGEXT", "jpg"), os.environ.get("GUIDE_IMGMIME", "jpeg")

shell = (S / "shell.html").read_text()
lib = (S / "lib.js").read_text()
chrome = (S / "chrome_one.js").read_text()
head, rest = lib.split("/* ================= page chrome ================= */")
_, widgets = rest.split("/* ================= widgets ================= */")
widgets = widgets.replace("var Q=DATA.quiz||[]", "var Q=(DATA.quiz||{})[w.closest('.guide').dataset.guide]||[]")
widgets = widgets.replace("img.src=(DATA.images||{})[b.dataset.img]||img.src", "img.src=(DATA.images||{})[b.dataset.img]||img.src;img.dataset.img=b.dataset.img")
widgets = re.sub(r"apply\(\);\nif\(location\.hash\).*\n", "route();\n", widgets)
assert "route();" in widgets
head = head.replace('var SLUG=document.body.dataset.guide||"guide";\n', "")
js = head + chrome + "/* ================= widgets ================= */" + widgets

idx = pathlib.Path("/home/user/dnd-poo/apps/imaging-portal/src/index.html").read_text()
LOGO_FULL = re.search(r'<img class="full" src="(data:image/png;base64,[^"]+)"', idx).group(1)
LOGO_MARK = re.search(r'<img class="mark" src="(data:image/png;base64,[^"]+)"', idx).group(1)

H = {"board": 780, "ticket": 900, "portal": 780, "fin-procurement": 780, "fin-invoice": 900, "fin-agreement": 900, "dispatch": 900,
     "rule": 900, "time-approve": 780, "sales-quote": 1100, "project": 900}
boxes = {}
for f in ("boxes.out.json", "boxes2.out.json"):
    boxes.update(json.loads((S / f).read_text()))
boxes["dispatch"][2] = {"n": 3, "x": 860, "y": 236, "w": 170, "h": 36}
SPOTS = {k: [{"n": b["n"], "x": round(100 * max(16, b["x"] + (0 if b["w"] < 200 else 14)) / 1280, 2),
              "y": round(100 * max(16, b["y"]) / H[k], 2)} for b in v] for k, v in boxes.items()}
TOURS = {}
for g in C.GUIDES:
    TOURS.update(g.get("tours", {}))

images, views, quiz = set(), [], {}
slugs = "|".join(ORDER)
for g in C.GUIDES:
    C.USED.clear(); C.PICKS.clear()
    body = g["body"]()
    images |= C.USED | C.PICKS
    body = re.sub(r'src="%%(?:IMG|PICK):([a-z0-9-]+)%%"', r'data-img="\1"', body)
    body = re.sub(r'<section class="s" id="([\w-]+)"', lambda m: f'<section class="s" id="{g["slug"]}--{m.group(1)}"', body)
    body = re.sub(r'href="PMC_Dada_PSA_(' + slugs + r')_Guide_20260930\.html#library"', 'href="#/"', body)
    body = re.sub(r'href="PMC_Dada_PSA_(' + slugs + r')_Guide_20260930\.html"', r'href="#/\1"', body)
    if g["slug"] == "Staff":
        body = re.sub(r'<section class="s" id="Staff--library".*?</section>', "", body, flags=re.S)
        body = re.sub(r'<div class="pick"[\s\S]*?rules, email, audit\.</span></button></div>', "", body)
        body = body.replace("the module guides below go deep into each area", "the other guides, on the front page, go deep into each area")
    assert "%%" not in body and ".html" not in body.replace("html:", ""), g["slug"]
    title = g["title"].replace(" (start here)", "")
    views.append(f'<div class="guide" data-guide="{g["slug"]}" data-title="{C.E(title)}" data-sub="{C.E(g["rail_sub"])}" '
                 f'data-search="{C.E(g["search"])}" hidden>{body}'
                 f'<p style="margin-top:26px"><a class="w-btn ghost" style="display:inline-flex;align-items:center;text-decoration:none" href="#/">← All guides</a></p></div>')
    quiz[g["slug"]] = g.get("quiz", [])

by = {g["slug"]: g for g in C.GUIDES}
cards = ""
for name, members in GROUPS:
    cards += f'<div class="ggroup"><h2 style="margin:26px 0 10px">{C.E(name)}</h2><div class="library">'
    for s in members:
        g = by[s]
        cls = "fin" if g.get("kind") == "fin" else "req" if g.get("kind") == "req" else ""
        cards += (f'<a class="gcard {cls}" href="#/{s}" data-slug="{s}" data-roles="{ROLES[s]}"><b>{C.E(g["title"])}</b>'
                  f'<span>{C.E(g["blurb"])}</span><em>For {C.E(g["for"])} · <span class="gcount"></span></em>'
                  f'<div class="bar gprog" style="height:6px;margin-top:8px"><i style="width:0"></i></div></a>')
    cards += "</div></div>"
front = ('<div id="front"><div id="fronthome">'
         + C.HERO("Dada PSA, the PMC service desk", "Everything about the desk in one place. Start with the Staff guide, then open the guide for your work. "
                  "Every guide has tours of real screens, try-it tools that follow the desk's own rules, and a short check at the end.",
                  ["For every PMC staff member", "14 guides in one page", "Works offline, prints cleanly"])
         + '<a class="gcard req" href="#/Staff" data-slug="Staff" data-roles="R T M A" style="display:block;text-decoration:none;color:inherit;border:1px solid var(--line);'
           'border-left:6px solid var(--green);border-radius:var(--r-lg);padding:18px 20px;background:var(--paper);box-shadow:var(--shadow-2)">'
           '<b style="font-family:var(--font-display);font-size:20px">Start here: the Staff guide →</b><span style="display:block;color:var(--text-2);margin-top:4px">'
           'What Dada PSA is, how to ask for help, how the desk works, and where everything is. About 20 minutes.</span>'
           '<em style="font-style:normal;font-size:12.5px;color:var(--text-3)"><span class="gcount"></span></em><div class="bar gprog" style="height:6px;margin-top:8px"><i style="width:0"></i></div></a>'
         + '<p style="margin:22px 0 0;color:var(--text-2)">Pick who you are in the bar at the top to show just your guides.</p>'
         + cards + '</div><div id="results"></div></div>')

chips = ('<div class="roles" role="group" aria-label="Show guides for"><span>Show for</span>'
         '<button class="chip" data-role="all" aria-pressed="true">Everyone</button><button class="chip" data-role="R" aria-pressed="false">Ward staff</button>'
         '<button class="chip" data-role="T" aria-pressed="false">Technicians</button><button class="chip" data-role="M" aria-pressed="false">Managers</button>'
         '<button class="chip" data-role="A" aria-pressed="false">Administrators</button></div>')
data = {"spots": SPOTS, "tours": TOURS, "quiz": quiz, "images": {n: f"data:image/{IMGMIME};base64," + base64.b64encode((S / IMGDIR / f"{n}.{IMGEXT}").read_bytes()).decode() for n in sorted(images)},
        "guides": [{"slug": g["slug"], "title": g["title"].replace(" (start here)", "")} for g in C.GUIDES]}
foot = ("Dada PSA guides · Premiere Medical Center Nueva Ecija · Dada IT · 30 September 2026. Screens are from a demonstration desk with made-up staff, "
        "tickets and supplier records; your boards, names and numbers will differ. SLA targets are set per board by its service manager.")
page = (shell.replace("%%TITLE%%", "Dada PSA guides").replace('data-guide="%%SLUG%%"', "")
        .replace("<b>%%RAIL_TITLE%%</b><span>%%RAIL_SUB%%</span>", '<b id="railTitle">Dada PSA guides</b><span id="railSub"></span>')
        .replace("%%TOC_TOP%%", "").replace("%%SEARCH_HINT%%", "Search every guide").replace("%%CHIPS%%", chips)
        .replace("%%FOOT%%", foot).replace("%%LOGO_FULL%%", LOGO_FULL).replace("%%LOGO_MARK%%", LOGO_MARK)
        .replace("%%BODY%%", front + "".join(views))
        .replace("%%DATA%%", json.dumps(data).replace("</", "<\\/")).replace("%%LIB%%", js))
page = page.replace(".library a:hover{", ".gcard[hidden],.ggroup[hidden]{display:none!important}\n.search input{padding-right:84px}\n.search input::-webkit-search-cancel-button{display:none}\n.library a:hover{")
left = re.findall(r"%%[A-Z_]+(?::[a-z0-9-]+)?%%", page)
assert not left, left[:5]
OUT.write_text(page)
print(OUT.name, round(OUT.stat().st_size / 1e6, 2), "MB,", len(images), "unique images,", len(views), "guides,",
      page.count('class="s"'), "sections,", page.count('data-w="'), "tools")
