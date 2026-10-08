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
    pmc_pack.apply(conn, helpdesk="IT_HELP", catalogue=True, at=at, actor="t")
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
    # 070: a project sits on a project board, apart from the Service Board.
    conn.execute("INSERT OR REPLACE INTO board_member (board_id, member, access) VALUES ('IT_PROJECTS', 'tech', 'ADMIN')")
    prj = projects.create(conn, name="Ward 3 refresh", board_id="IT_PROJECTS", at=at, actor="tech")
    ph_a = projects.add_phase(conn, prj, name="Survey", at=at, actor="tech")
    ph_b = projects.add_phase(conn, prj, name="Instal", at=at, actor="tech")      # a typo
    ph_c = projects.add_phase(conn, prj, name="Handover", at=at, actor="tech")
    projects.add_dependency(conn, ph_b, ph_c, at=at, actor="tech")                # the wrong way round
    survey = tickets.open_ticket(conn, board_id="IT_HELP", summary="Survey the Ward 3 network points",
                                 impact="I3", urgency="U3", requested_by=None, at=at)
    projects.convert_to_project_ticket(conn, survey, prj, phase_id=ph_a, at=at, actor="tech")   # 070
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
    # 071: a ward requester (on no board) with a chat waiting on IT Help
    from psaspine import chat
    auth.create_local_account(conn, "nurse7", PASSWORD, at=at)
    chat.start(conn, requester="nurse7", board_id="IT_HELP", subject="Teams phone silent",
               first="The Teams phone on ward 7 does not ring.", at=at)
    # 073: IT Help takes chats and tech answers them
    conn.execute("UPDATE board SET takes_chats = 1 WHERE board_id = 'IT_HELP'")
    chat.set_operator(conn, "tech", True, at=at, actor="tech")
    conn.commit()
    conn.close()
    return wid, mail, noted, prj, ph_b, emailed


def main() -> int:
    from test_spine import _png  # noqa: F401  (a real picture for the chat check)
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

            # --- a menu over the page is solid and not clipped (Dada, 6 Oct 2026:
            # the Service Desk menu read through to the page beneath it) ------
            page.locator("header.top nav .grp:not(.all)").first.hover()
            page.wait_for_timeout(400)
            menu = page.evaluate("""() => { const p=document.querySelector('header.top nav .grp:hover .panel');
                if (!p) return null; const r=p.getBoundingClientRect();
                const top=document.elementFromPoint(r.left + r.width/2, r.top + r.height - 12);
                const cs=getComputedStyle(p), m=cs.backgroundColor.match(/[\d.]+/g).map(Number);
                const blur=parseFloat(((cs.backdropFilter||cs.webkitBackdropFilter||'').match(/blur\(([\d.]+)px/)||[0,0])[1]);
                return [cs.backgroundColor, !!top && p.contains(top), m.length < 4 ? 1 : m[3], blur] }""")
            note(bool(menu) and menu[1], "an open menu is drawn whole, not cut off by the bar", str(menu))
            # solid, or frosted hard enough that nothing beneath can be read
            note(bool(menu) and (menu[2] >= 0.99 or (menu[2] >= 0.8 and menu[3] >= 12)),
                 "and the page does not read through it", str(menu))
            page.mouse.move(5, 600)
            # --- what answers the pointer still glows (Dada, 6 Oct 2026: "the glowing
            # when hovered was removed ... and all the other effects": a later resting
            # style had out-ranked every :hover) -----------------------------------
            page.mouse.move(700, 880)
            page.wait_for_timeout(300)
            for what, sel in (("a board tile", ".tiles a.tile"), ("a card", ".card"),
                              ("a board row", "table.grid tbody tr"),
                              ("the Filter button", "main button[type=submit]:not(.ghost)")):
                el = page.locator(sel).first
                if not el.count():
                    note(False, f"{what} lights up under the pointer", "not on the page")
                    continue
                rest = el.evaluate("e => getComputedStyle(e).boxShadow")
                el.hover()
                page.wait_for_timeout(350)
                lit = el.evaluate("e => getComputedStyle(e).boxShadow")
                note(lit != rest, f"{what} lights up under the pointer", f"{rest[:60]} -> {lit[:60]}")
                page.mouse.move(700, 880)
                page.wait_for_timeout(250)

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
            ph = page.evaluate("""() => { const e = document.querySelector('#composer .editor');
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
                # Dada, 6 Oct 2026: "time entries when saved isnt saving anywhere".
                # (1) Charged as starts on Included and holds nothing up ("remove the charge as dependency")
                save = page.locator("#tedlg .tefoot button[type=submit]:not([formaction])")
                ch = page.evaluate("() => { const c=document.querySelector('#tedlg select[name=charge]');"
                                   " return [c.value, c.required] }")
                note(ch == ["INCLUDED_IN_MONTHLY_FEE", False],
                     "Charged as starts on Included in monthly fee and is not required", str(ch))
                # (2) any minute is a time: a clock started at :27 may end at :40
                start0 = page.locator("#tedlg input[name=start]").input_value()
                hh, mm = (int(x) for x in start0.split(":"))
                odd = f"{(hh + (mm + 13) // 60) % 24:02d}:{(mm + 13) % 60:02d}"
                page.locator("#tedlg input[name=end]").fill(odd)
                note(page.evaluate("() => document.querySelector('#tedlg input[name=end]').validity.valid"),
                     "an end 13 minutes after the clock's start is a valid time", f"{start0} -> {odd}")
                # (3) a Save the desk refuses brings the window back with the note in it
                page.locator("#tedlg input[name=start]").fill("10:00")
                page.locator("#tedlg input[name=end]").fill("09:00")
                save.click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(700)
                back = page.evaluate("() => [document.getElementById('tedlg').open,"
                                     " document.querySelector('#tedlg .editor').innerText,"
                                     " document.querySelector('#tedlg select[name=charge]').value]")
                note("Time not saved" in page.locator("body").inner_text() and back[0]
                     and "Swapped the toner" in back[1] and bool(back[2]),
                     "a Save the desk refuses reopens the window with the note and choices kept", str(back)[:120])
                page.locator("#tedlg input[name=start]").fill(start0)
                page.locator("#tedlg input[name=end]").fill("")
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
                # scroll down to a pod rather than to a fixed offset: the page's
                # height changes with the layout, and a pod that is not in view
                # must fail the check, never skip it
                idx = page.evaluate("""() => {
                  const cs=[...document.querySelectorAll('.pods .card[data-pod]')];
                  // not the Ticket card: folding it would hide the cascade checked below
                  const i = cs.findIndex((c, n) => n > 0 && !c.querySelector('select.cat-type'));
                  if (i < 0) return -1;
                  scrollTo({top: Math.max(0, cs[i].getBoundingClientRect().top + scrollY - 200),
                            behavior:'instant'});
                  return i }""")
                page.wait_for_timeout(250)
                if idx < 0 or page.evaluate("window.scrollY") < 50:
                    note(False, f"{what}: the page stays where the reader left it",
                         "no pod below the fold to test with")
                    continue
                # The design (templates.js `hold`): an in-place change keeps the
                # card itself under the eye, so the page may scroll to hold it
                # when something above it changes height; a reorder keeps the
                # page still and lets the card move. Each is measured as promised.
                card = page.locator(".pods .card[data-pod]").nth(idx)
                y0 = page.evaluate("window.scrollY")
                t0 = card.evaluate("c => c.getBoundingClientRect().top")
                card.locator(btn).click()
                page.wait_for_timeout(600)
                y1 = page.evaluate("window.scrollY")
                if what == "move up":
                    note(abs(y1 - y0) <= 4, f"{what}: the page stays where the reader left it",
                         f"scrollY {y0} -> {y1}")
                else:
                    t1 = card.evaluate("c => c.getBoundingClientRect().top")
                    note(abs(t1 - t0) <= 4, f"{what}: the card stays where the reader left it",
                         f"card top {t0:.0f} -> {t1:.0f}px (scrollY {y0} -> {y1})")
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
            # 070: every tab is its own page (Dada, 7 Oct 2026: "load each tab on its own page").
            page.goto(f"{base}/project/{prj}", wait_until="domcontentloaded")
            page.wait_for_timeout(400)
            tabs = page.locator("nav.ptabs a")
            hrefs = [tabs.nth(i).get_attribute("href") for i in range(tabs.count())]
            note(len(hrefs) >= 12 and len(set(hrefs)) == len(hrefs), "the project's tabs are links, one page each", str(hrefs))
            bad = []
            for h in hrefs:
                page.goto(base + h, wait_until="domcontentloaded")
                cur = page.locator("nav.ptabs a[aria-current=page]")
                if cur.count() != 1 or cur.get_attribute("href") != h or "Traceback" in page.content():
                    bad.append(h)
            note(not bad, "and each opens on its own, its tab marked", str(bad))
            page.goto(f"{base}/project/{prj}", wait_until="domcontentloaded")
            txt = page.locator("body").inner_text()
            note(page.locator(f"form[action='/project/{prj}/remove']").count() == 0
                 and "cancelled" in txt.lower(),
                 "a project with work on it offers Cancelled, not Remove")
            page.goto(f"{base}/project/{prj}/workplan", wait_until="domcontentloaded")
            page.wait_for_timeout(400)
            txt = page.locator("body").inner_text()
            note(page.locator("form[action$='/phase/unwait'] button").count() >= 1,
                 "a predecessor set the wrong way round can be taken off")
            note("kept:" in txt, "a phase carrying work says why, instead of a dead Remove button",
                 next((l.strip() for l in txt.splitlines() if "kept:" in l), ""))
            page.goto(f"{base}/project/{prj}/tickets", wait_until="domcontentloaded")
            note(page.locator("form[action$='/ticket/unlink'] button").count() == 1,
                 "a project ticket can be unlinked from the Tickets tab")
            page.goto(f"{base}/project/{prj}/workplan?phase={ph_b}", wait_until="domcontentloaded")
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

            # --- a project's own tickets and team (068; Dada, 7 Oct 2026) ------
            page.goto(f"{base}/project/{prj}/workplan", wait_until="domcontentloaded")
            page.wait_for_timeout(400)
            plus = page.locator(f"button[data-open=ptdlg][data-phase='{ph_b}']")
            note(plus.count() == 1, "each phase offers + Ticket")
            if plus.count():
                plus.click()
                page.wait_for_timeout(300)
                picked = page.evaluate("() => [document.getElementById('ptdlg').open,"
                                       " document.querySelector('#ptdlg select[name=phase_id]').value]")
                note(picked == [True, str(ph_b)], "and opens the project ticket window with that phase picked", str(picked))
                page.fill("#ptdlg input[name=summary]", "Hand the ward its new PCs")
                page.fill("#ptdlg input[name=budget_hours]", "3")
                page.locator("#ptdlg .tefoot button[type=submit]").click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(500)
                note("created in the project" in page.locator("body").inner_text(), "the ticket is created inside the project")
                page.goto(f"{base}/project/{prj}/workplan", wait_until="domcontentloaded")
                note("Hand the ward its new PCs" in page.locator("#plan").inner_text(),
                     "and sits under its phase in the work plan")
                page.goto(f"{base}/project/{prj}/tickets", wait_until="domcontentloaded")
                note(page.locator("#pboard .pcard").count() >= 2, "and is on the project's ticket board")
                page.goto(f"{base}/", wait_until="domcontentloaded")
                page.wait_for_timeout(400)
                note("Hand the ward its new PCs" not in page.locator("body").inner_text()
                     and "Survey the Ward 3 network points" not in page.locator("body").inner_text(),
                     "project tickets never show on the Service Board")
                page.goto(f"{base}/projects", wait_until="domcontentloaded")
                grp = page.locator("[data-pboard=IT_PROJECTS]")
                note(grp.count() == 1 and "Ward 3 refresh" in grp.inner_text()
                     and "Hand the ward its new PCs" in grp.inner_text(),
                     "the project board holds the project, and the project holds its tickets")
            page.goto(f"{base}/project/{prj}/team", wait_until="domcontentloaded")
            page.locator("#team select[name=member]").select_option(index=0)
            page.locator("#team select[name=role]").select_option("ENGINEER")
            page.locator("#team input[name=hours]").fill("8")
            page.locator("#team button[type=submit]").first.click()
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(400)
            note("joined the team" in page.locator("body").inner_text() or "on the team" in page.locator("body").inner_text(),
                 "a member is added to the project's team with a role and hours")
            # --- 069: plan a ticket's dates, see it on the Gantt; the close window --
            page.goto(f"{base}/project/{prj}/workplan", wait_until="domcontentloaded")
            plan = page.locator("button[data-open=ptplan]").first
            note(plan.count() == 1, "each project ticket in the work plan offers Plan")
            if plan.count():
                want = plan.get_attribute("data-plan")
                plan.click()
                page.wait_for_timeout(300)
                got = page.evaluate("() => [document.getElementById('ptplan').open,"
                                    " document.querySelector('#ptplan [name=work_item_id]').value]")
                note(got == [True, want], "Plan opens its window filled with that ticket", f"{got} vs {want}")
                page.fill("#ptplan input[name=starts_on]", "2026-10-08")
                page.fill("#ptplan input[name=due_on]", "2026-10-10")
                page.locator("#ptplan .tefoot button[type=submit]").click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(400)
                page.goto(f"{base}/project/{prj}/gantt", wait_until="domcontentloaded")
                note(page.locator("#pgantt .grow.ticket .gbar").count() >= 1,
                     "and the dated ticket is drawn on the Gantt")
            close_btn = page.locator("button[data-open=pclose]")
            note(close_btn.count() == 1, "an open project offers Close project")
            if close_btn.count():
                close_btn.click()
                page.wait_for_timeout(300)
                note(page.evaluate("() => document.getElementById('pclose').open"), "which opens the close window")
                page.locator("#pclose [data-close=pclose]").first.click()
            # 070: an issue raised on the Issues tab
            page.goto(f"{base}/project/{prj}/issues", wait_until="domcontentloaded")
            page.fill("#pissues input[name=summary]", "Switch delivery slipped a week")
            page.locator("#pissues button[type=submit]").last.click()
            page.wait_for_load_state("domcontentloaded")
            note("Issue raised" in page.locator("body").inner_text() and "/issues" in page.url,
                 "an issue is raised and the Issues tab comes back", page.url)
            # 070: a service ticket offers Convert to project ticket
            page.goto(f"{base}/ticket/{ref}", wait_until="domcontentloaded")
            note(page.locator("[data-pod=project] button", has_text="Convert to project ticket").count() == 1,
                 "a service ticket's Project pod offers Convert to project ticket")
            page.goto(f"{base}/admin/projects", wait_until="domcontentloaded")
            note(page.locator("#pstatuses input[name=name]").count() >= 5, "Setup › Projects lists the project statuses")
            page.goto(f"{base}/projects", wait_until="domcontentloaded")
            page.wait_for_timeout(300)
            note("open ticket(s)" in page.locator("body").inner_text(), "the projects list shows each project's open tickets")

            # --- the ticket's tabs, each its own page (Dada, 7 Oct 2026) ------
            page.goto(f"{base}/ticket/{ref}", wait_until="domcontentloaded")
            tt = page.locator("nav.ttabs a")
            threfs = [tt.nth(i).get_attribute("href") for i in range(tt.count())]
            note(len(threfs) == 11, "a ticket shows the reference PSA's tabs, billing left out", str(threfs))
            bad = []
            for h in threfs:
                page.goto(base + h, wait_until="domcontentloaded")
                cur = page.locator("nav.ttabs a[aria-current=page]")
                if cur.count() != 1 or cur.get_attribute("href") != h:
                    bad.append(h)
            note(not bad, "and each opens on its own page, its tab marked", str(bad))
            page.goto(f"{base}/ticket/{ref}/configurations", wait_until="domcontentloaded")
            note(page.locator("#tconfigs").count() == 1, "the Configurations tab is there")
            page.goto(f"{base}/", wait_until="domcontentloaded")
            grp = page.locator("nav .grp", has=page.locator("button[title=Configurations]"))
            note(grp.count() == 1, "Configurations is a menu of its own across the bar")
            if grp.count():
                grp.locator("button").click()
                page.wait_for_timeout(200)
                note(grp.locator("a[href='/configurations#cfgnew']").is_visible(), "and it opens to New configuration")
                page.keyboard.press("Escape")
                page.mouse.move(5, 600)                 # leave the pointer off the bar for what follows

            # --- chat, live both ways (071; Dada, 7 Oct 2026) -----------------
            cid = 1
            # 073: count the rings (one compressor per ring), from a clean slate
            page.add_init_script("(() => { const A = window.AudioContext; if (!A) return; window.__rings = 0;"
                                 " const f = A.prototype.createDynamicsCompressor;"
                                 " A.prototype.createDynamicsCompressor = function () { window.__rings++; return f.call(this); }; })()")
            page.evaluate("() => { try { localStorage.removeItem('psa-chat-rang') } catch (e) {} }")
            page.goto(f"{base}/", wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            rings = page.evaluate("() => window.__rings || 0")
            note(rings >= 1, "a waiting chat rings, the louder phone-style ring", f"{rings} ring(s)")
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            note(page.evaluate("() => window.__rings || 0") == 0, "and not again on the next page within 30 seconds")
            tk = page.locator("#chatticker")
            note(tk.is_visible() and "Teams phone silent" in tk.inner_text(),
                 "a waiting chat runs across the top of the desk page")
            x0 = page.evaluate("() => new DOMMatrix(getComputedStyle(document.querySelector('#chatticker .ttrack')).transform).m41")
            page.wait_for_timeout(700)
            x1 = page.evaluate("() => new DOMMatrix(getComputedStyle(document.querySelector('#chatticker .ttrack')).transform).m41")
            note(x1 < x0, "moving from right to left", f"{x0:.0f} -> {x1:.0f}px")
            note(tk.locator(".tsound").count() == 1, "with its chime switch beside it")
            h = tk.bounding_box()["height"] if tk.is_visible() else 0
            note(h >= 54, "the banner is twice the size it was", f"{h:.0f}px tall")
            note(" · chat 1" in tk.inner_text(), "the chat goes by its person and which of theirs, not its number",
                 tk.inner_text()[:120])
            tk.locator(".tlive").click()
            page.wait_for_timeout(200)
            lv = page.locator("#chatlive")
            note(lv.is_visible() and "Teams phone silent" in lv.inner_text() and lv.locator("button", has_text="Pick up").count() == 1,
                 "Live chats opens a quick view with the waiting chat and Pick up")
            if os.environ.get("PSA_SHOTS"):
                page.screenshot(path=os.path.join(os.environ["PSA_SHOTS"], "chat-quickview.png"))
            page.keyboard.press("Escape")
            page.wait_for_timeout(150)
            note(not lv.is_visible(), "and Escape closes it")
            page.goto(f"{base}/chat", wait_until="domcontentloaded")
            note("Teams phone silent" in page.locator("#chatqueue").inner_text(), "the desk sees the waiting chat")
            page.goto(f"{base}/chat/{cid}", wait_until="domcontentloaded")
            ward = browser.new_context().new_page()
            ward.goto(f"{base}/login", wait_until="domcontentloaded")
            ward.fill("input[name=username]", "nurse7")
            ward.fill("input[name=password]", PASSWORD)
            ward.click("button[type=submit]")
            ward.wait_for_load_state("domcontentloaded")
            ward.goto(f"{base}/my/chat", wait_until="domcontentloaded")
            pa = ward.locator("#chatpaalala")
            pt = pa.inner_text().lower() if pa.count() else ""
            note(pa.is_visible() and "paalala" in pt and "pasyente" in pt,
                 "the ward reads the Taglish reminder of what to put in a chat, beside the box", pt[:160] or ward.url)
            if os.environ.get("PSA_SHOTS"):                    # a look at it by eye, when asked for
                ward.screenshot(path=os.path.join(os.environ["PSA_SHOTS"], "chat-paalala.png"), full_page=True)
            ward.goto(f"{base}/my/chat/{cid}", wait_until="domcontentloaded")
            note("number 1 in the queue" in ward.locator("#chatstate").inner_text()
                 and "you are in the queue" in ward.locator("#chatlog").inner_text(),
                 "the ward reads 'please wait' and its place in the queue", ward.locator("#chatstate").inner_text())
            page.fill("#chatsend textarea", "On my way to ward 7.")
            page.keyboard.press("Enter")
            page.wait_for_timeout(600)
            note(page.url.endswith(f"/chat/{cid}") and "On my way to ward 7." in page.locator("#chatlog").inner_text(),
                 "Enter sends, and the line appears without the page reloading", page.url)
            ward.wait_for_timeout(4500)
            note("On my way to ward 7." in ward.locator("#chatlog").inner_text(),
                 "the requester sees it arrive by itself")
            note("is with you" in ward.locator("#chatstate").inner_text() and "has joined the chat" in
                 ward.locator("#chatlog").inner_text(), "and that someone has joined, without a reload")
            ward.fill("#chatsend textarea", "Thank you, I am at the nurses' station.")
            ward.keyboard.press("Enter")
            page.wait_for_timeout(4500)
            note("I am at the nurses' station" in page.locator("#chatlog").inner_text(),
                 "and the desk sees the reply arrive by itself")
            # 072: a reaction, an emoji, a picture, and the rating at the end
            line = page.locator("#chatlog .cl.requester").last
            line.hover()
            line.locator(".rx.add").click()
            page.locator("#rxpick button").first.click()
            page.wait_for_timeout(800)
            note(line.locator(".rx.on").count() == 1, "a reaction goes on the line and is marked as mine")
            ward.wait_for_timeout(4000)
            note(ward.locator("#chatlog .cl.requester .rx:not(.add)").count() >= 1,
                 "and the requester sees it come by itself")
            ward.locator("#chatsend .emo").click()
            ward.locator("#emopick button").first.click()
            note(len(ward.locator("#chatsend textarea").input_value()) > 0, "the emoji button puts an emoji in the box")
            ward.fill("#chatsend textarea", "")
            ward.set_input_files("#chatsend input[type=file]", files=[{"name": "error.png", "mimeType": "image/png",
                                                                       "buffer": _png(60, 40)}])
            page.wait_for_timeout(4500)
            note(page.locator("#chatlog img.cimg").count() == 1, "a picture from the ward shows in the desk's chat")
            note(page.locator("#chatlog .cfile form[action$='/review']").count() == 1, "with Clear and Withhold beside it")
            ward.locator("form[action$='/end'] button").click()
            ward.wait_for_load_state("domcontentloaded")
            note(ward.locator("#chatsurvey").is_visible(), "ending the chat asks the requester how we did")
            rwho = ward.locator("#chatsurvey .rwho").inner_text().lower()
            note(rwho.startswith("how did ") and "we do" not in rwho, "naming the operator who had it (074)", rwho)
            ward.locator("#chatsurvey .star span").first.click()
            ward.locator("#chatsurvey button[type=submit]").click()
            ward.wait_for_load_state("domcontentloaded")
            note("You rated this chat" in ward.locator("body").inner_text(), "and the rating is kept")
            ward.context.close()
            # 073: Make a ticket opens the ticket on the operator's time, ready to confirm
            page.goto(f"{base}/chat/{cid}", wait_until="domcontentloaded")
            page.locator("form[action$='/ticket'] button[type=submit]").click()
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(400)
            te = page.locator("#tedlg")
            note("/ticket/" in page.url and te.is_visible(), "Make a ticket opens the new ticket's time entry window", page.url)
            note(te.locator("input[name=start]").input_value() != "" and te.locator("input[name=end]").input_value() != ""
                 and "Chat with" in te.locator("textarea[name=body]").input_value(),
                 "with the start, the end and the chat already filled in",
                 te.locator("input[name=start]").input_value() + "-" + te.locator("input[name=end]").input_value())
            # 074: a new chat from the ward, picked up, then ended from the quick view without asking
            ward = browser.new_context().new_page()
            ward.goto(f"{base}/login", wait_until="domcontentloaded")
            ward.fill("input[name=username]", "nurse7")
            ward.fill("input[name=password]", PASSWORD)
            ward.click("button[type=submit]")
            ward.wait_for_load_state("domcontentloaded")
            ward.goto(f"{base}/my/chat", wait_until="domcontentloaded")
            ward.fill("#chatstart input[name=subject]", "Mouse not working")
            ward.fill("#chatstart textarea[name=body]", "Ward 7 nurses' station PC, the mouse stopped.")
            ward.click("#chatstart button[type=submit]")
            ward.wait_for_load_state("domcontentloaded")
            cid2 = ward.url.rstrip("/").rsplit("/", 1)[-1]
            page.goto(f"{base}/chat/{cid2}", wait_until="domcontentloaded")
            page.locator(f"main form[action='/chat/{cid2}/pick'] button").click()
            page.wait_for_load_state("domcontentloaded")
            page.goto(f"{base}/", wait_until="domcontentloaded")
            page.locator("#chatticker .tlive").click()
            page.wait_for_timeout(200)
            end = page.locator(f"#chatlive a[href='/chat/{cid2}?end=1']")
            note(end.count() == 1, "the quick view has End beside the chat that is mine")
            if end.count():
                end.click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(200)
            dlg = page.locator("#chatend")
            note(dlg.is_visible() and dlg.locator("input[name=ask]").is_checked(),
                 "and opens the chat with its end window up, Ask how I did ticked")
            dlg.locator("textarea[name=closing]").fill("Salamat po! Message us anytime.")
            dlg.locator("input[name=ask]").uncheck()
            dlg.locator("button[type=submit]").click()
            page.wait_for_load_state("domcontentloaded")
            ward.reload(wait_until="domcontentloaded")
            note("Salamat po!" in ward.locator("#chatlog").inner_text() and ward.locator("#chatsurvey").count() == 0,
                 "unticked, the ward reads the closing line and is not asked to rate")
            ward.context.close()

            # --- the Dispatch Portal (8 Oct 2026) -------------------------------
            today = datetime.now().date().isoformat()
            page.goto(f"{base}/dispatch?day={today}", wait_until="domcontentloaded")
            page.evaluate("() => { try { localStorage.removeItem('psa-dispatch-fold') } catch (e) {} }")
            page.reload(wait_until="domcontentloaded")
            rows = page.locator("#stickets table.sttable tbody tr[data-drag]")
            note(rows.count() >= 1, "Service Tickets lists the open tickets as a table", f"{rows.count()} rows")
            names = page.locator("table.schedgrid.dispatch th.who .rname").all_inner_texts()
            note("tech" in [n.strip().lower() for n in names] and all(n == n.strip() and not n.isupper() for n in names),
                 "resources are rows with their names, as written", str(names))
            first = rows.first
            tid = first.get_attribute("data-drag").split("|")[1]
            first.drag_to(page.locator(f"td[data-slot='tech|{today}|09:00']"))
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(300)
            chip = page.locator(f"table.schedgrid.dispatch .sch.visit[data-menu^='{tid}|']")
            note(chip.count() == 1 and "msg=" in page.url, "a ticket dragged onto an hour books a visit", page.url)
            if os.environ.get("PSA_SHOTS"):
                page.screenshot(path=os.path.join(os.environ["PSA_SHOTS"], "dispatch-day.png"))
            chip.click(button="right")
            page.wait_for_timeout(150)
            menu = page.locator(".ctxmenu")
            note(menu.is_visible() and "Mark done" in menu.inner_text() and "Delete the visit" in menu.inner_text(),
                 "a right-click offers Open, Done and Delete")
            page.keyboard.press("Escape")
            page.wait_for_timeout(100)
            note(page.locator(".ctxmenu").count() == 0, "and Escape closes it")
            # the right edge dragged one hour to the right: the visit ends an hour later
            rz = chip.locator(".rz")
            box, cell = rz.bounding_box(), page.locator(f"td[data-slot='tech|{today}|09:00']").bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.mouse.down()
            page.mouse.move(box["x"] + box["width"] / 2 + cell["width"], box["y"] + box["height"] / 2, steps=6)
            page.mouse.up()
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(300)
            chip = page.locator(f"table.schedgrid.dispatch .sch.visit[data-menu^='{tid}|']")
            note(chip.count() == 1 and chip.get_attribute("data-span").endswith("T11:00"),
                 "its right edge dragged changes when it ends", chip.get_attribute("data-span") if chip.count() else page.url)
            page.locator(".stfold").click()
            note(page.locator(".dispatchwrap.folded").count() == 1 and not page.locator("#stickets").is_visible(),
                 "the tickets fold away to give the grid the width")
            page.locator(".stshow").click()
            note(page.locator("#stickets").is_visible(), "and come back")
            page.locator(".schedbar a", has_text="Week").click()
            page.wait_for_load_state("domcontentloaded")
            note(page.locator("table.schedgrid.dispatch.week").count() == 1
                 and page.locator(f"table.schedgrid.dispatch.week .sch.visit[data-menu^='{tid}|']").count() >= 1,
                 "Week shows the seven days with the visit on its day")
            if os.environ.get("PSA_SHOTS"):
                page.screenshot(path=os.path.join(os.environ["PSA_SHOTS"], "dispatch-week.png"))

            # --- the themes (8 Oct 2026): a mode and a colour, each colour in both modes
            page.goto(f"{base}/", wait_until="domcontentloaded")
            page.locator("#theme").click()
            page.wait_for_timeout(150)
            menu = page.locator(".thememenu")
            note(menu.is_visible() and menu.locator("button").count() == 6 and menu.locator("h5").count() == 2,
                 "the theme button opens a menu: a mode and a colour")
            menu.locator("button[data-theme=peach]").click()
            page.wait_for_timeout(150)
            state = lambda: page.evaluate("() => [document.documentElement.dataset.theme, document.documentElement.dataset.tint || '',"  # noqa: E731
                                          " getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()]")
            got = state()
            note(got[0] == "dark" and got[1] == "peach" and got[2] == "#ffab80", "Peach over dark keeps the dark mode and takes the peach accent", str(got))
            if os.environ.get("PSA_SHOTS"):
                page.screenshot(path=os.path.join(os.environ["PSA_SHOTS"], "theme-peach-dark.png"))
            menu.locator("button[data-theme=light]").click()
            page.wait_for_timeout(150)
            got = state()
            note(got[0] == "light" and got[1] == "peach" and got[2] == "#d9663a", "Light keeps the colour and takes its light accent", str(got))
            if os.environ.get("PSA_SHOTS"):
                page.screenshot(path=os.path.join(os.environ["PSA_SHOTS"], "theme-peach-light.png"))
            page.keyboard.press("Escape")
            page.reload(wait_until="domcontentloaded")
            got = state()
            note(got[0] == "light" and got[1] == "peach", "and both are remembered", str(got))
            for tint in ("purple", "pink"):
                for mode in ("dark", "light"):
                    page.locator("#theme").click()
                    page.wait_for_timeout(100)
                    page.locator(f".thememenu button[data-theme={tint}]").click()
                    page.locator(f".thememenu button[data-theme={mode}]").click()
                    page.wait_for_timeout(100)
                    if os.environ.get("PSA_SHOTS"):
                        page.screenshot(path=os.path.join(os.environ["PSA_SHOTS"], f"theme-{tint}-{mode}.png"))
                    page.keyboard.press("Escape")
            # the chrome follows the colour: the active module, a submit button, a table header, a tile
            hues = page.evaluate("""() => { const c = s => getComputedStyle(s); const q = s => document.querySelector(s);
                return [c(q('header.top nav .top.on')).backgroundImage, c(q('main button[type=submit]')||q('main .btn')).backgroundImage,
                        c(q('table.grid thead th')).backgroundImage, c(q('.tile .ic')).color] }""")
            blue = ("99, 102, 241", "34, 211, 238", "238, 242, 251", "8, 145, 178", "61, 99, 221", "142, 162, 255")
            note(not any(b in h for h in hues for b in blue) and all("255, 158, 203" in h for h in hues[:2]),
                 "the active module, buttons, table headers and tiles carry the pink, none the classic blue", str(hues)[:200])
            page.keyboard.press("t")
            page.wait_for_timeout(100)
            got = state()
            note(got[0] == "dark" and got[1] == "pink", "t flips the mode and keeps the colour", str(got))
            page.locator("#theme").click()
            page.wait_for_timeout(100)
            page.locator(".thememenu button[data-theme=classic]").click()
            page.locator(".thememenu button[data-theme=dark]").click()
            page.keyboard.press("Escape")
            note(page.evaluate("() => document.documentElement.dataset.tint || ''") == "", "Classic takes the colour off")

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
                # where the summary is now: opening the fold can nudge the page
                # (scroll anchoring), and a person clicks the line they see
                xy = page.evaluate("""() => { const f = document.querySelector('iframe.mail'),
                    r = f.getBoundingClientRect(),
                    s = f.contentDocument.querySelector('summary').getBoundingClientRect();
                    return [r.left + f.clientLeft + s.left + 8, r.top + f.clientTop + s.top + s.height / 2] }""")
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
