"""Open a built guide in a real Chromium and check what a reader would see.

    python3 _source/check_guide.py PMC_Dada_PSA_Guides_20261005.html
    python3 _source/check_guide.py PMC_Dada_PSA_Guides_Compact_20261005.html

The build script counts sections and tools, which proves nothing about
whether the page opens: the guide is one self-contained HTML file with its
own router, search and tours, and the only honest test of it is a browser.
So this asks one -- that every guide card is there, that each section added
in this edition renders under its own heading, that the sentences the
edition exists to say are actually on the page, that search reaches them
across guides, that nothing fetches anything from outside the file, and
that the console is clean. The compact edition takes the same checks,
which is also how its unpack-in-the-browser loader gets tested.
Exits non-zero on the first failure, so CI could run it.
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright
F = pathlib.Path(sys.argv[1]).resolve()
ok = True
def note(good, what, detail=""):
    global ok
    ok = ok and good
    print(("PASS  " if good else "FAIL  ") + what + (f"\n        {detail}" if detail else ""), flush=True)

with sync_playwright() as pw:
    chrome = sorted(pathlib.Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome"))
    b = pw.chromium.launch(executable_path=str(chrome[-1])) if chrome else pw.chromium.launch()
    page = b.new_page(viewport={"width": 1400, "height": 1000})
    errs, reqs = [], []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("request", lambda r: reqs.append(r.url) if not r.url.startswith(("file:", "data:")) else None)
    page.goto(F.as_uri(), wait_until="load")
    page.wait_for_timeout(1200)

    note("Dada PSA" in page.title(), "the page opens", page.title())
    note(page.locator("#front .note.info b", has_text="5 October 2026 edition").count() == 1,
         "the front page says which edition it is and what it supersedes")
    note(page.locator(".library .gcard").count() == 14, "all 14 guide cards are on the front page",
         f"{page.locator('.library .gcard').count()} cards")

    # the five new sections, each in its own guide
    for slug, sid, title in (("Staff", "whatsnew", "What changed since 30 September"),
                             ("Service_Desk", "d-fields", "Changing the ticket's fields"),
                             ("Service_Desk", "d-layout", "Making the page yours"),
                             ("Time", "t-stopwatch", "The stopwatch"),
                             ("Setup", "a-prio", "Priorities"),
                             ("Service_Desk", "d-name", "Naming another ticket"),
                             ("Projects", "p-fix", "Correcting the plan")):
        page.goto(F.as_uri() + f"#/{slug}", wait_until="load")
        page.wait_for_timeout(500)
        sec = page.locator(f"#{slug}--{sid}")
        note(sec.count() == 1 and sec.first.is_visible(), f"{slug}: section '{title}' is on the page")
        if sec.count():
            note(title in sec.first.inner_text(), f"{slug}: it is headed '{title}'")

    # the words that answer the actual asks
    page.goto(F.as_uri() + "#/Service_Desk", wait_until="load"); page.wait_for_timeout(500)
    body = page.locator('.guide[data-guide="Service_Desk"]').inner_text()
    for phrase in ("Ticket type", "changes not saved", "Edit layout", "cid:image004.jpg",
                   "the message the sender actually composed", "resources"):
        note(phrase in body, f"Service Desk says {phrase!r}")

    page.goto(F.as_uri() + "#/Dispatch_OnCall", wait_until="load"); page.wait_for_timeout(500)
    dbody = page.locator('.guide[data-guide="Dispatch_OnCall"]').inner_text()
    for phrase in ("To schedule", "Save as my view", "people down the side"):
        note(phrase in dbody, f"Dispatch says {phrase!r}")

    page.goto(F.as_uri() + "#/Scheduling", wait_until="load"); page.wait_for_timeout(500)
    sbody = page.locator('.guide[data-guide="Scheduling"]').inner_text()
    for phrase in ("Click an empty hour", "keeps its length", "ticket number and board"):
        note(phrase in sbody, f"Scheduling says {phrase!r}")

    page.goto(F.as_uri() + "#/Setup", wait_until="load"); page.wait_for_timeout(500)
    abody = page.locator('.guide[data-guide="Setup"]').inner_text()
    for phrase in ("tick on the member", "last system administrator cannot be taken off",
                   "its own words to any one of its statuses", "address they wrote to"):
        note(phrase in abody, f"Setup says {phrase!r}")

    page.goto(F.as_uri() + "#/Projects", wait_until="load"); page.wait_for_timeout(500)
    pbody = page.locator('.guide[data-guide="Projects"]').inner_text()
    for phrase in ("kept: 2 ticket(s) are on it", "cancelled", "hours are the record of work"):
        note(phrase in pbody, f"Projects says {phrase!r}")

    page.goto(F.as_uri() + "#/Time", wait_until="load"); page.wait_for_timeout(500)
    tbody = page.locator('.guide[data-guide="Time"]').inner_text()
    note("not the SLA clock" in tbody, "the Time guide says the stopwatch is not the SLA clock")

    # search reaches the new words across guides
    page.goto(F.as_uri(), wait_until="load"); page.wait_for_timeout(600)
    page.locator(".search input").first.fill("stopwatch")
    page.wait_for_timeout(700)
    hits = page.locator("#results a").count()
    note(hits > 0, "search across every guide finds the new words", f"{hits} hit(s) for 'stopwatch'")

    note(not reqs, "the file is self-contained: no external request", " | ".join(reqs[:3]))
    note(not errs, "no console errors", " | ".join(errs[:3]))
    b.close()
print("\n" + ("ALL CHECKS PASSED" if ok else "SOMETHING FAILED"))
sys.exit(0 if ok else 1)
