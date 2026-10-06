"""Drive the real desk in a real Chromium and see what a technician sees.

    python tests/browsercheck.py          # needs playwright and a chromium

The unit suite proves the HTML a view returns. It cannot prove that a person
can click the thing: a `required` field the page never filled, a select that
does not open, a button that does nothing. Those are browser facts, so this
asks a browser. It is not part of `python -m unittest`, because CI has no
chromium; it is run by hand before a release and when a technician says a
screen misbehaves.

Dada, 3 Oct 2026: "picking using drop downs have issues when being clicked",
"there is an issue with scheduling". Those are interaction faults, and no
amount of reading the HTML proves them either way: they happen in a browser or
they do not. So this starts a desk on a throwaway database, signs in, and
clicks the things he is clicking, reporting every console error on the way.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # platform/psa-spine
sys.path.insert(0, str(ROOT))

PASSWORD = "Sm0ke-Test-Only-Not-A-Real-Secret"
findings: list[str] = []


def note(ok: bool, what: str, detail: str = "") -> None:
    findings.append(f"{'PASS' if ok else 'FAIL'}  {what}" + (f"\n        {detail}" if detail else ""))
    print(findings[-1], flush=True)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def build(db_path: Path) -> str:
    """A desk with the catalogue, one board and one ticket to open."""
    from datetime import datetime as dt
    from psaspine import db, setup, pmc_pack, tickets
    from psaspine.web import auth
    conn = db.init(str(db_path))
    at = dt(2026, 10, 3, 9, 0)
    setup.apply_starter(conn, "IT_HELP", actor="t", at=at)
    setup.apply_template(conn, actor="t", at=at)
    pmc_pack.apply(conn, helpdesk="IT_HELP", at=at, actor="t")
    conn.execute("INSERT OR IGNORE INTO member (member, display_name, email, is_sysadmin)"
                 " VALUES ('tech', 'Tech Person', 'tech@pmcne.ph', 1)")
    conn.execute("INSERT OR REPLACE INTO board_member (board_id, member, access)"
                 " VALUES ('IT_HELP', 'tech', 'ADMIN')")
    wid = tickets.open_ticket(conn, board_id="IT_HELP", summary="Printer in Ward 3 will not print",
                              impact="I2", urgency="U2", requested_by=None, at=at)
    # A ticket that arrived as an Outlook email, so a browser can be asked
    # whether the page shows the sender's formatting or the markup of it
    # (5 Oct 2026). Only the HTML door writes body_format='HTML' here; the
    # gate still rebuilds it, so the script and the pixel never get stored.
    mail = tickets.open_ticket(
        conn, board_id="IT_HELP", summary="Teams phone not ringing on Ward 3",
        impact="I3", urgency="U3", requested_by="reyes@pmcne.ph", at=at, source="EMAIL",
        description='<p>The Teams phone on <b>Ward 3</b> is not ringing.</p>'
                    '<p><a href="https://portal.pmcne.ph/x">Portal</a></p>'
                    '<script>window.BROKE_IN = 1</script>'
                    '<p><img src="https://tracker.example.net/pixel.gif"></p>',
        description_format="HTML")
    # A ticket whose only clue is a word inside a note, and a project with a
    # typo'd phase and a predecessor set the wrong way round (5 Oct 2026): the
    # two things a browser has to answer for -- does the ticket picker find it,
    # and can the plan be corrected.
    from psaspine import board, projects
    noted = tickets.open_ticket(conn, board_id="IT_HELP", summary="Teams phone silent",
                                impact="I3", urgency="U3", requested_by="cruz@pmcne.ph", at=at)
    board.add_note(conn, noted, body="The handset flashes amber when a call lands.",
                   flag="DISCUSSION", actor="tech", at=at, notify_requester=False)
    prj = projects.create(conn, name="Ward 3 refresh", board_id="IT_HELP", at=at, actor="tech")
    ph_a = projects.add_phase(conn, prj, name="Survey", at=at, actor="tech")
    ph_b = projects.add_phase(conn, prj, name="Instal", at=at, actor="tech")      # a typo
    ph_c = projects.add_phase(conn, prj, name="Handover", at=at, actor="tech")
    projects.add_dependency(conn, ph_b, ph_c, at=at, actor="tech")                # the wrong way round
    projects.link_ticket(conn, wid, prj, ph_a, at=at, actor="tech")
    # An Outlook reply as it really arrives (6 Oct 2026): a signature laid out
    # in a table, a confidentiality footer, a screenshot pasted inline by
    # Content-ID, the whole quoted thread underneath -- and a script and a
    # tracking pixel, which must come to nothing.
    from psaspine import attachments, richtext
    sys.path.insert(0, str(ROOT / "tests"))
    from test_spine import _png
    fixture = (ROOT / "tests" / "fixtures" / "outlook_reply_signature.html").read_text()
    fixture = fixture.replace('<p class=MsoNormal>Thank you po<o:p></o:p></p>',
                              '<p class=MsoNormal>Thank you po, the screen shows this:<o:p></o:p></p>'
                              '<p class=MsoNormal><img width=120 height=120 src="cid:shot1@pmcne.ph"></p>')
    fixture = fixture.replace("</div></body>", "<script>window.parent.BROKE_OUT=1</script></div></body>")
    emailed = tickets.open_ticket(conn, board_id="IT_HELP", summary="Teams phone on Ward 3",
                                  impact="I3", urgency="U3", requested_by="rosa.mendoza@pmcne.ph", at=at,
                                  source="EMAIL", description=richtext.fold(fixture, profile="email"),
                                  description_format="EMAIL")
    attachments.add(conn, emailed, _png(120, 120), "image001.png", actor="rosa.mendoza@pmcne.ph", at=at,
                    source="EMAIL", content_id="shot1@pmcne.ph")
    board.add_note(conn, emailed, body="LATER-NOTE: checked the handset", flag="INTERNAL", actor="tech",
                   at=datetime(2026, 10, 3, 10, 0))
    auth.create_local_account(conn, "tech", PASSWORD, at=at, is_sysadmin=True)
    conn.commit()
    conn.close()
    return wid, mail, noted, prj, ph_b, emailed


def main() -> int:
    from playwright.sync_api import sync_playwright
    tmp = tempfile.TemporaryDirectory()
    db_path = Path(tmp.name) / "desk.db"
    os.environ["PSA_ATTACHMENT_DIR"] = str(Path(tmp.name) / "files")    # build() keeps a file too
    ref, mailref, noted, prj, ph_b, emailed = build(db_path)
    port = free_port()
    env = dict(os.environ, PSA_ATTACHMENT_DIR=str(Path(tmp.name) / "files"))
    proc = subprocess.Popen([sys.executable, "-m", "psaspine", "serve", str(db_path),
                             "--host", "127.0.0.1", "--port", str(port)],
                            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            break
        except OSError:
            time.sleep(0.25)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
            page = browser.new_page()
            errors: list[str] = []
            page.on("console", lambda m: errors.append(f"{m.type}: {m.text}") if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
            outside: list[str] = []
            page.on("request", lambda r: outside.append(r.url)
                    if not r.url.startswith((base, "data:", "about:")) else None)

            page.goto(f"{base}/login", wait_until="domcontentloaded")
            page.fill("input[name=username]", "tech")
            page.fill("input[name=password]", PASSWORD)
            page.click("button[type=submit]")
            page.wait_for_load_state("domcontentloaded")
            note("login" not in page.url, "sign in", page.url)

            page.goto(f"{base}/ticket/{ref}", wait_until="domcontentloaded")
            page.wait_for_timeout(400)
            note(page.locator("select.cat-item").count() == 1, "the ticket page has the Item select")

            # --- the cascade, clicked the way a person clicks it ----------
            ts, ss, item = page.locator("select.cat-type"), page.locator("select.cat-sub"), page.locator("select.cat-item")
            note(ts.is_visible(), "Type select is visible (the script unhid it)")
            note(ss.is_visible(), "Subtype select is visible")
            before = item.locator("option").count()
            ts.select_option(label="Hospital systems (BizBox)")
            page.wait_for_timeout(200)
            subs = ss.locator("option").count()
            note(subs > 1, "picking a Type fills Subtype", f"{subs} subtype option(s)")
            narrowed = item.locator("option").count()
            note(0 < narrowed < before, "picking a Type narrows Item", f"{before} -> {narrowed}")
            ss.select_option(label="BizBox HIS")
            page.wait_for_timeout(200)
            final = item.locator("option").count()
            note(0 < final <= narrowed, "picking a Subtype narrows Item further", f"{narrowed} -> {final}")
            labels = item.locator("option").all_inner_texts()
            note(any("Not working" == x.strip() for x in labels),
                 "the Item options read as the item alone once narrowed", str(labels[:4]))

            # does the picked classification survive a save?
            item.select_option(index=1)
            picked = item.input_value()
            page.locator("button[type=submit]:has-text('Save changes')").first.click()
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(400)
            kept = page.locator("select.cat-item").input_value()
            note(kept == picked, "the classification survives Save changes", f"picked {picked!r}, kept {kept!r}")
            note(page.locator("select.cat-type").input_value() != "",
                 "and the Type select comes back showing the saved pair's Type",
                 page.locator("select.cat-type").input_value())

            # --- how many Save buttons does one ticket show? --------------
            saves = page.locator("button[type=submit]").all_inner_texts()
            note(True, f"{len(saves)} submit button(s) on the ticket page",
                 ", ".join(sorted({s.strip() for s in saves if s.strip()}))[:400])

            # --- scheduling -----------------------------------------------
            form = page.locator("form#schedadd")
            if form.count():
                starts = form.locator("input[name=starts_at]").input_value()
                ends = form.locator("input[name=ends_at]").input_value()
                note(bool(ends), "the schedule form's To is prefilled",
                     f"From={starts!r} To={ends!r}")
                # move the From and see whether the To keeps up
                form.locator("input[name=starts_at]").fill("2026-10-09T14:00")
                form.locator("input[name=starts_at]").dispatch_event("change")
                page.wait_for_timeout(200)
                moved = form.locator("input[name=ends_at]").input_value()
                note(moved.startswith("2026-10-09T15"), "moving From carries To with it",
                     f"From=2026-10-09T14:00 -> To={moved!r}")
                # and now book it exactly as a person would
                form.locator("select[name=member]").select_option(index=1)
                form.locator("button[type=submit]").click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(500)
                booked = page.locator("[data-pod=schedule] li").count()
                note(booked > 0, "the visit is booked by filling nothing but Who",
                     f"{booked} visit(s) listed")
            else:
                note(False, "the schedule form is on the page")

            # --- the status dropdown, which is the one that used to 500 -----
            page.goto(f"{base}/ticket/{ref}", wait_until="domcontentloaded")
            page.wait_for_timeout(300)
            st = page.locator("form#ticketfields select[name=to_status]").first
            if st.count():
                vals = st.locator("option").evaluate_all(
                    "os => os.filter(o => o.value && !o.disabled).map(o => o.value)")
                now = st.input_value()
                pick = next((v for v in vals if v != now), None)
                if pick is None:
                    note(False, "the status select offers somewhere to move to", str(vals))
                    pick = now
                st.select_option(pick)
                page.locator("button[type=submit]:has-text('Save changes')").first.click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(300)
                body = page.content()
                msg = ""
                for sel in (".flash", ".msg", ".err", "[role=alert]"):
                    if page.locator(sel).count():
                        msg = page.locator(sel).first.inner_text()[:200]
                        break
                ok = ("Internal Server Error" not in body
                      and "Traceback" not in body
                      and page.locator("form#ticketfields").count() > 0)
                note(ok, "picking a status and saving does not take the desk down",
                     msg or page.url)
            else:
                note(False, "the status select is on the page")

            # --- one Save, always reachable --------------------------------
            page.goto(f"{base}/ticket/{ref}", wait_until="domcontentloaded")
            page.wait_for_timeout(300)
            bar = page.locator(".savebar")
            note(bar.count() == 0 or not bar.first.is_visible() or "up" not in (bar.first.get_attribute("class") or ""),
                 "no save bar until something is changed")
            page.locator("select[name=impact]").select_option(index=1)
            page.wait_for_timeout(250)
            cls = page.locator(".savebar").first.get_attribute("class") or ""
            note("up" in cls, "changing a field raises the save bar", cls)
            note("change" in (page.locator(".savebar b").first.inner_text() or "").lower(),
                 "and it says how many changes are waiting",
                 page.locator(".savebar b").first.inner_text())

            # --- the time entry window (065; 6 Oct 2026) --------------------
            # Dada: "time entry clock like connectwise clicking it launches the
            # time entry or discussion window ... it logs the current time".
            ph = page.evaluate("""() => { const e = document.querySelector('[data-pod=composer] .editor');
                const b = getComputedStyle(e, '::before'); return [b.content, b.backgroundImage, b.width] }""")
            note("Type a note" in ph[0] and ph[1] == "none",
                 "an empty note box shows its words, not the empty-state inbox", str(ph))
            start = page.locator(".hdr form[action$='/timer/start'] button")
            note(start.count() == 1, "the ticket's header carries the time entry clock")
            if start.count():
                start.click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(900)
                dlg = page.locator("dialog#tedlg[open]")
                note(dlg.count() == 1, "one click starts the clock and opens the time entry window")
                st_v = page.locator("#tedlg input[name=start]").input_value()
                note(bool(st_v), "the start is already logged", st_v)
                tick = page.locator("#tedlg b.tick")
                first = tick.first.inner_text()
                page.wait_for_timeout(1600)
                note(tick.first.inner_text() != first, "and its clock counts up on its own",
                     f"{first} -> {tick.first.inner_text()}")
                # moved by its title bar, and made larger (Dada, 6 Oct 2026)
                r0 = page.evaluate("() => { const r = document.getElementById('tedlg').getBoundingClientRect(); return [r.left, r.top, r.width] }")
                hb = page.locator("#tedlg .tehead h3").bounding_box()
                page.mouse.move(hb["x"] + 20, hb["y"] + 8)
                page.mouse.down()
                page.mouse.move(hb["x"] - 80, hb["y"] - 60, steps=6)
                page.mouse.up()
                r1 = page.evaluate("() => { const r = document.getElementById('tedlg').getBoundingClientRect(); return [r.left, r.top, r.width] }")
                note(r1[0] < r0[0] - 50 and r1[1] < r0[1] - 30, "the window moves by its title bar", f"{r0[:2]} -> {r1[:2]}")
                page.locator("#tedlg [data-max]").click()
                page.wait_for_timeout(200)
                r2 = page.evaluate("() => document.getElementById('tedlg').getBoundingClientRect().width")
                note(r2 > r0[2] + 100, "and the square makes it larger", f"{r0[2]:.0f}px -> {r2:.0f}px")
                page.locator("#tedlg [data-max]").click()
                note(page.evaluate("() => getComputedStyle(document.getElementById('tedlg')).resize") == "both",
                     "its corner resizes it")
                ed = page.locator("#tedlg .editor")
                ed.click()
                page.keyboard.type("Swapped the toner ")
                page.keyboard.down("Shift")
                for _ in range(6):
                    page.keyboard.press("ArrowLeft")
                page.keyboard.up("Shift")
                page.locator("#tedlg details.pop summary[title='Font colour']").click()
                page.locator("#tedlg button[data-do=color][data-arg='#c62828']").click()
                page.wait_for_timeout(150)
                sent = page.evaluate("() => document.querySelector('#tedlg textarea[name=body]').value")
                note('class="tc-red"' in sent and "color" not in sent.replace("tc-red", ""),
                     "a colour picked in the toolbar goes up as the desk's own class", sent[:120])
                page.locator("#tedlg select[name=charge]").select_option(index=1)
                page.locator("#tedlg .tefoot button[type=submit]:not([formaction])").click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(500)
                note("Time saved" in page.locator("body").inner_text(), "Save stops the clock and books the time",
                     page.url)
                note(page.locator(".hdr form[action$='/timer/start']").count() == 1,
                     "and the clock is free for the next job")
                note(page.locator(".rtx .tc-red").count() >= 1, "the red word reads red on the ticket")

            # --- editing the pods must not move the page -------------------
            # Dada, 3 Oct 2026: "when editing pods it resets the screen or
            # re-orients and doesn't stay, it goes back up".
            page.goto(f"{base}/ticket/{ref}", wait_until="domcontentloaded")
            page.wait_for_timeout(400)
            page.locator("[data-layedit]").first.click()
            page.wait_for_timeout(250)
            for what, btn in (("size", ".podctl .size"), ("fold", ".podctl .fold"),
                              ("taller", ".podctl .hmore"),
                              ("move up", ".podctl .mv[data-dir='-1']")):
                page.evaluate("window.scrollTo({top:700,behavior:'instant'})")
                page.wait_for_timeout(250)
                idx = page.evaluate("""() => {
                  const cs=[...document.querySelectorAll('.pods .card[data-pod]')];
                  return cs.findIndex(c => { const r=c.getBoundingClientRect();
                    return r.top > 80 && r.top < innerHeight-40 }) }""")
                if idx < 0:
                    continue
                y0 = page.evaluate("window.scrollY")
                page.locator(".pods .card[data-pod]").nth(idx).locator(btn).click()
                page.wait_for_timeout(600)
                y1 = page.evaluate("window.scrollY")
                note(abs(y1 - y0) <= 4, f"{what}: the page stays where the reader left it",
                     f"scrollY {y0} -> {y1}")
            # and the cascade still answers after the pods have been moved about
            ts2 = page.locator("select.cat-type")
            if ts2.count():
                # the ticket already carries a pair, so the cascade opens
                # narrowed to it; widen it first, then narrow and measure
                ts2.select_option("")
                page.wait_for_timeout(250)
                n_all = page.locator("select.cat-item option").count()
                ts2.select_option(label="Hospital systems (BizBox)")
                page.wait_for_timeout(250)
                n1 = page.locator("select.cat-item option").count()
                note(0 < n1 < n_all, "the dropdowns still narrow after editing the pods",
                     f"all {n_all} -> {n1}")

            # --- an email on the ticket reads as the sender wrote it -------
            # Dada, 3 Oct 2026: "can we make html from emails or render the
            # full emails on the tickets". A unit test proves the HTML; only a
            # browser proves the page shows bold rather than the word "<b>".
            # Since 6 Oct 2026 an email is drawn in its own frame (below), so
            # these look inside it.
            page.goto(f"{base}/ticket/{mailref}", wait_until="load")
            page.wait_for_timeout(600)
            seen = page.evaluate("""() => { const f = document.querySelector('iframe.mail');
                const d = f ? f.contentDocument : document;
                return {b: d.querySelectorAll('b').length, said: d.body.innerText,
                        links: d.querySelectorAll("a[href^='https://portal.pmcne.ph']").length,
                        imgs: d.querySelectorAll('img').length} }""")
            note(seen["b"] >= 1, "an email's formatting is formatting on the page, not markup",
                 seen["said"][:80])
            note("<b>" not in seen["said"] and "[cid:" not in seen["said"],
                 "and no tag or cid: reference is read out as words", seen["said"][:80])
            note(seen["links"] == 1, "the sender's link is a link, written once")
            note(seen["imgs"] == 0,
                 "no image is fetched from the page, so nothing phones the sender home",
                 f"{seen['imgs']} img element(s)")
            note(page.evaluate("() => !window.BROKE_IN"),
                 "a script in the email never ran")

            # --- naming a ticket without typing its number ------------------
            # Dada, 5 Oct 2026: "a dropdown for the tickets would be nice ...
            # a search function wherein the ticket will be displayed on all
            # ticket fields". The datalist is filled by a fetch, so only a
            # browser can say whether the dropdown actually has anything in it.
            page.goto(f"{base}/ticket/{ref}", wait_until="domcontentloaded")
            page.wait_for_timeout(400)
            picks = page.locator("input[data-tickpick]")
            note(picks.count() == 4, "the link and family fields are pickers, not number boxes",
                 f"{picks.count()} picker(s)")
            note(page.locator(f"input[data-tickpick][data-not='{ref}']").count() == 4,
                 "and each leaves this ticket out of its own list")
            inp = picks.first
            opts = page.locator("#" + inp.get_attribute("list") + " option")
            inp.fill("amber")                 # a word only in the other ticket's NOTE
            page.wait_for_timeout(900)
            vals = [opts.nth(i).get_attribute("value") for i in range(opts.count())]
            labs = [opts.nth(i).get_attribute("label") for i in range(opts.count())]
            note(noted in vals, "a word that is only inside a note fills the dropdown", str(vals))
            note(any("in a note" in (x or "") for x in labs),
                 "and the option says where it was found", str(labs))
            note(ref not in vals, "the ticket you are on is never offered to itself", str(vals))
            inp.fill("noopener")              # markup, not words
            page.wait_for_timeout(900)
            note(opts.count() == 0, "a tag or attribute name fills it with nothing",
                 f"{opts.count()} option(s)")

            # --- a project's plan can be corrected --------------------------
            # Dada, 5 Oct 2026: "for projects they cant be deleted edited any
            # elements for the project cant do that".
            page.goto(f"{base}/project/{prj}", wait_until="domcontentloaded")
            page.wait_for_timeout(400)
            txt = page.locator("body").inner_text()
            note(page.locator("form[action$='/phase/unwait'] button").count() >= 1,
                 "a predecessor set the wrong way round can be taken off")
            note("kept:" in txt, "a phase carrying work says why, instead of a dead Remove button",
                 next((l.strip() for l in txt.splitlines() if "kept:" in l), ""))
            note(page.locator("form[action$='/ticket/unlink'] button").count() == 1,
                 "a linked ticket can be unlinked here")
            note(page.locator(f"form[action='/project/{prj}/remove']").count() == 0
                 and "cancelled" in txt.lower(),
                 "a project with work on it offers Cancelled, not Remove")
            page.goto(f"{base}/project/{prj}?phase={ph_b}", wait_until="domcontentloaded")
            page.wait_for_timeout(400)
            card = page.locator("#edit-phase")
            note(card.count() == 1, "Edit brings up that phase's own form")
            if card.count():
                card.locator("input[name=name]").fill("Install")
                card.locator("button[type=submit]").first.click()
                page.wait_for_timeout(700)
                note("Install" in page.locator("body").inner_text(), "and the rename saves", page.url)
                page.locator("form[action$='/phase/unwait'] button").first.click()
                page.wait_for_timeout(700)
                note("no longer waits on" in page.locator("body").inner_text(),
                     "the wrong predecessor comes off, so both phases can finish", page.url)

            # --- an email as its sender laid it out (6 Oct 2026) -------------
            # Dada: "HTML is or emails are not rendering properly on the ticket
            # viewer", "images are not rendering on the ticket", and "search on
            # github whats the best renderer". Sanitizer, sandboxed srcdoc frame,
            # a policy that fetches nothing: only a browser can prove the last
            # two, and the frame's height.
            page.goto(f"{base}/ticket/{emailed}", wait_until="load")
            page.wait_for_timeout(1200)
            frame_el = page.locator("iframe.mail").first
            note(frame_el.count() == 1, "the email is drawn in its own sandboxed frame")
            if frame_el.count():
                sb = frame_el.get_attribute("sandbox") or ""
                note("allow-scripts" not in sb and "allow-same-origin" in sb,
                     "the sandbox never allows scripts", sb)
                # The email is read the way the desk itself reads it: through
                # the page, which shares the frame's origin. Playwright's own
                # frame calls (click, bounding_box, element evaluate) leave a
                # helper in the frame that the sandbox then refuses, logging
                # errors that are the harness's, not the desk's (MEASURED,
                # 6 Oct 2026); none of them is used here.
                def inmail(js: str):
                    return page.evaluate("() => { const d = document.querySelector('iframe.mail')"
                                         ".contentDocument; return (" + js + ")(d) }")
                # The email's own height is its root's box, not its scrollHeight:
                # that is never less than the frame, so comparing against it
                # passed while the frame grew 120 px a second (6 Oct 2026).
                fit = """() => { const f = document.querySelector('iframe.mail'), d = f.contentDocument;
                    return [f.getBoundingClientRect().height,
                            Math.ceil(Math.max(d.documentElement.getBoundingClientRect().height,
                                               d.body.scrollHeight))] }"""
                h_el, h_doc = page.evaluate(fit)
                note(abs(h_el - h_doc) <= 2 and h_el > 80,
                     "the frame is exactly as tall as the email: no inner scrollbar, no gap",
                     f"frame {h_el:.0f}px, email {h_doc}px")
                page.wait_for_timeout(1500)
                h_later = page.evaluate(fit)[0]
                note(abs(h_later - h_el) <= 1, "and it stays that tall: the fit settles, it does not creep",
                     f"{h_el:.0f}px, then {h_later:.0f}px 1.5 s later")
                note(page.evaluate("() => !window.BROKE_OUT"), "a script in the email never ran")
                # a line holding a picture is as tall as the picture, so only
                # the lines of words are measured
                tops = inmail("""d => [...d.querySelectorAll('p')].slice(0,8)
                                  .map(p => [Math.round(p.getBoundingClientRect().top),
                                             !!p.querySelector('img')])""")
                gaps = [b[0] - a[0] for a, b in zip(tops, tops[1:]) if b[0] > a[0] and not a[1]]
                note(bool(gaps) and max(gaps) <= 40,
                     "the lines sit as Outlook shows them, not a blank line apart", f"gaps {gaps}")
                cells = inmail("d => d.querySelectorAll('table td').length")
                note(cells >= 2, "the signature is laid out as its table", f"{cells} cells")
                pic = inmail("""d => { const i = d.querySelector('img');
                                 return i ? [i.complete && i.naturalWidth > 0, i.getAttribute('src')] : null }""")
                note(bool(pic and pic[0]), "the picture pasted into the email shows where the sender put it",
                     pic[1] if pic else "no <img>")
                note(inmail("d => d.querySelectorAll('details').length === 1 && !d.querySelector('details').open"),
                     "the quoted earlier messages are folded away")
                before = h_el
                # clicked as a person clicks: a mouse at a point on the page,
                # with the email scrolled into view first
                page.evaluate("() => document.querySelector('iframe.mail').scrollIntoView({block: 'center'})")
                page.wait_for_timeout(300)
                before = page.evaluate(fit)[0]
                xy = page.evaluate("""() => { const f = document.querySelector('iframe.mail'),
                    r = f.getBoundingClientRect(),
                    s = f.contentDocument.querySelector('summary').getBoundingClientRect();
                    return [r.left + f.clientLeft + s.left + 8, r.top + f.clientTop + s.top + s.height / 2] }""")
                page.mouse.click(*xy)
                page.wait_for_timeout(500)
                after, after_doc = page.evaluate(fit)
                note(after > before + 40 and abs(after - after_doc) <= 2, "opening the fold grows the frame to fit",
                     f"{before:.0f}px -> {after:.0f}px (email {after_doc}px)")
                page.mouse.click(*xy)
                page.wait_for_timeout(500)
                shut = page.evaluate(fit)[0]
                note(abs(shut - before) <= 2, "and closing it gives the room back", f"{after:.0f}px -> {shut:.0f}px")
                page.mouse.click(*xy)                              # open again for the dark check below
                page.wait_for_timeout(300)
                page.evaluate("() => { document.documentElement.dataset.theme = 'dark' }")
                page.wait_for_timeout(300)
                ink = inmail("d => getComputedStyle(d.body).color")
                note(ink.replace(" ", "") in ("rgb(228,231,238)",),
                     "the dark theme reaches inside the frame", ink)
                page.evaluate("() => { document.documentElement.dataset.theme = 'light' }")
            note(not [u for u in outside if "tracker" in u or "example.net" in u],
                 "nothing in the email fetched anything from outside the desk",
                 " | ".join(outside[:3]))

            # --- oldest first or newest first -----------------------------
            # Dada, 6 Oct 2026: "add a way to sort messages by earliest first".
            page.goto(f"{base}/ticket/{emailed}", wait_until="domcontentloaded")
            order_link = page.locator(".tabs a.order")
            note(order_link.count() == 1 and "Oldest first" in order_link.inner_text(),
                 "the Activity card says which way it reads")
            # the email sits in a frame, so its words are not in the page's
            # text; compare where the frame and the later note are drawn
            order_js = """() => {
              const f = document.querySelector('[data-pod=stream] iframe.mail');
              const n = [...document.querySelectorAll('[data-pod=stream] *')]
                .find(e => e.children.length === 0 && e.textContent.includes('LATER-NOTE'));
              return f && n ? [Math.round(f.getBoundingClientRect().top),
                               Math.round(n.getBoundingClientRect().top)] : null }"""
            where = page.evaluate(order_js)
            note(bool(where) and where[0] < where[1], "oldest first to begin with", str(where))
            order_link.click()
            page.wait_for_load_state("domcontentloaded")
            where = page.evaluate(order_js)
            note(bool(where) and where[1] < where[0], "one click turns it newest first", str(where))
            page.goto(f"{base}/ticket/{emailed}", wait_until="domcontentloaded")
            note("Newest first" in page.locator(".tabs a.order").inner_text(),
                 "and the browser remembers it on the next visit")
            page.locator(".tabs a.order").click()                  # leave it as it was found
            page.wait_for_load_state("domcontentloaded")

            note(not errors, "no console errors anywhere above",
                 " | ".join(errors[:5]) if errors else "")
            browser.close()
    finally:
        proc.terminate()
        try:
            out = proc.stdout.read() if proc.stdout else ""
            if out.strip():
                print("\n--- server said ---")
                print(out[-4000:])
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        tmp.cleanup()

    bad = [f for f in findings if f.startswith("FAIL")]
    print("\n" + "=" * 60)
    print(f"{len(findings) - len(bad)} passed, {len(bad)} failed")
    for f in bad:
        print(f)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
