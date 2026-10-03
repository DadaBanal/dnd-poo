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
    auth.create_local_account(conn, "tech", PASSWORD, at=at, is_sysadmin=True)
    conn.commit()
    conn.close()
    return wid


def main() -> int:
    from playwright.sync_api import sync_playwright
    tmp = tempfile.TemporaryDirectory()
    db_path = Path(tmp.name) / "desk.db"
    ref = build(db_path)
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
