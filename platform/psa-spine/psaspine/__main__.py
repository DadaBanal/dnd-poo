"""Command line: init, import, report."""
from __future__ import annotations

import argparse
import getpass
import sys
from datetime import date, datetime
from pathlib import Path

from . import db, register, reports, tickets, walkthrough


def _as_of(value: str | None) -> date:
    return date.fromisoformat(value) if value else date.today()


def _mb(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / 1024:.0f} KB" if n >= 1024 else f"{n} B"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="psaspine", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="create and seed a spine database")
    pi.add_argument("database")

    pm = sub.add_parser("import", help="import the workstream register CSV")
    pm.add_argument("database")
    pm.add_argument("register_csv")
    pm.add_argument("--run-id", default="run-1")
    pm.add_argument("--as-of")

    pt = sub.add_parser("import-tickets", help="import a desk export CSV")
    pt.add_argument("database")
    pt.add_argument("export_csv")
    pt.add_argument("--run-id", default="desk-1")
    pt.add_argument("--as-of")

    pmail = sub.add_parser("import-mail",
                           help="import a drop of RFC 822 files as tickets "
                                "(idempotent; a re-run makes no second ticket)")
    pmail.add_argument("database")
    pmail.add_argument("drop_dir")
    pmail.add_argument("--run-id", default="mail-1")
    pmail.add_argument("--channel", default="helpdesk",
                       help="which mailbox this drop came from; how the measured "
                            "double-creation becomes a number rather than an anecdote")
    pmail.add_argument("--board-id",
                       help="where a new ticket lands; defaults to the unrouted board")
    pmail.add_argument("--own-address", action="append", default=[],
                       help="the desk's own sending address (repeatable): mail from it "
                            "never opens a ticket, so the desk cannot answer itself")
    pmail.add_argument("--as-of")

    pw = sub.add_parser("walkthrough",
                        help="run the board engine end to end and narrate it")
    pw.add_argument("database")

    ps = sub.add_parser("serve", help="run the Phase B fulfiller desk (pilot, LAN only)")
    ps.add_argument("database")
    ps.add_argument("--host", default="127.0.0.1",
                    help="interface to bind; refuses 0.0.0.0 (default 127.0.0.1)")
    ps.add_argument("--port", type=int, default=8080)

    pc = sub.add_parser("create-local-account",
                        help="create a sealed break-glass account (password read from a "
                             "no-echo prompt, never an argument)")
    pc.add_argument("database")
    pc.add_argument("--username", required=True)
    pc.add_argument("--sysadmin", action="store_true",
                    help="grant cross-board admin; off by default")

    pk = sub.add_parser("create-api-token",
                        help="mint a machine API token for one board; printed ONCE, "
                             "stored only as a sha256")
    pk.add_argument("database")
    pk.add_argument("--label", required=True,
                    help="what it is for, in words: 'orthanc monitoring'")
    pk.add_argument("--board", required=True, dest="board_id",
                    help="the one board this token may raise tickets onto")

    pb = sub.add_parser("backup",
                        help="escrow copy via SQLite's backup API (safe under WAL); "
                             "refuses to overwrite, proves the copy")
    pb.add_argument("database")
    pb.add_argument("destination")

    pac = sub.add_parser("import-contacts",
                         help="upsert contacts under one company from an AD export "
                              "(scripts/Export-PmcAdContacts.ps1)")
    pac.add_argument("database")
    pac.add_argument("export_csv")
    pac.add_argument("--company", required=True, dest="entity_id",
                     help="the company these people belong to, e.g. PMC")

    pcf = sub.add_parser("import-computers",
                         help="upsert configurations under one company from an AD "
                              "computers export (scripts/Export-PmcAdComputers.ps1)")
    pcf.add_argument("database")
    pcf.add_argument("export_csv")
    pcf.add_argument("--company", required=True, dest="entity_id")

    prr = sub.add_parser("run-rules",
                         help="run time-based workflow events (ON_SCHEDULE, ON_SLA_THRESHOLD) "
                              "over every open ticket; the server runs this every minute")
    prr.add_argument("database")

    pob = sub.add_parser("outbox-pending",
                         help="print due notifications as JSON for the Graph sender; "
                              "unresolvable or out-of-domain recipients are marked NO_SENDER")
    pob.add_argument("database")
    pob.add_argument("--allowed-domain", action="append", required=True,
                     help="only addresses in this domain are released (repeatable)")
    pob.add_argument("--dry-run", action="store_true", help="change nothing (the sender's preview)")
    pob.add_argument("--portal-url",
                     help="https:// address of the requester portal for the link in requester "
                          "emails (else PSA_PORTAL_URL; never committed)")
    pom = sub.add_parser("outbox-mark", help="record what the sender did with one notification")
    pom.add_argument("database")
    pom.add_argument("--id", type=int, required=True)
    pom.add_argument("--status", choices=("SENT", "FAILED"), required=True)

    pau = sub.add_parser("attachments-usage",
                         help="what the attachment store holds, by month and board, and on disk")
    pau.add_argument("database")
    pav = sub.add_parser("attachments-verify",
                         help="is the store whole: every live row has its file, every file a row")
    pav.add_argument("database")
    pav.add_argument("--hashes", action="store_true",
                     help="also read every live file and check it against its name (slow)")
    pav.add_argument("--mark-missing", action="store_true",
                     help="record rows whose file is gone as removed (reason MISSING), audited")
    pap = sub.add_parser("attachments-purge",
                         help="remove files under the retention rule; PREVIEW unless --apply")
    pap.add_argument("database")
    pap.add_argument("--withheld-days", type=int, required=True,
                     help="remove a withheld file this many days after its review")
    pap.add_argument("--closed-days", type=int, required=True,
                     help="remove any file this many days after its ticket closed")
    pap.add_argument("--apply", action="store_true", help="change something (default: preview)")
    pap.add_argument("--as-of", help="today, for a rehearsal (default: now)")

    pu = sub.add_parser("setup-board",
                        help="give a board the starter statuses, calendar and SLA "
                             "targets (adds what is missing, never overwrites)")
    pu.add_argument("database")
    pu.add_argument("--board", required=True, dest="board_id")

    pr = sub.add_parser("report", help="write Annex B, dependency notices and the exception report")
    pr.add_argument("database")
    pr.add_argument("--out", required=True)
    pr.add_argument("--as-of")
    pr.add_argument("--run-id", default="run-1")
    pr.add_argument("--eac-percent", type=float,
                    help="capacity uplift %% claimed; omitted leaves the paper unpriced")
    pr.add_argument("--capacity-hours", type=float,
                    help="declared available capacity per month — the uplift denominator")

    a = p.parse_args(argv)

    if a.cmd == "backup":
        # Before connect(): a backup must not create the database it was asked
        # to copy, and must not open the destination as a spine.
        try:
            r = db.backup(a.database, a.destination)
        except (FileNotFoundError, FileExistsError, ValueError) as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        rows = ", ".join(f"{t} {n}" for t, n in r["counts"].items())
        print(f"{r['path']}: {r['bytes']} bytes, sha256 {r['sha256']}")
        print(f"integrity {r['integrity']}; rows: {rows}")
        if not r["ok"]:
            print(f"FAILED: the copy does not match the source {r['mismatched']}",
                  file=sys.stderr)
            return 1
        return 0

    if a.cmd == "init":
        db.init(a.database).close()
        print(f"created {a.database}")
        return 0

    conn = db.connect(a.database)
    if a.cmd == "import":
        as_of = _as_of(a.as_of)
        s = register.import_register(conn, a.register_csv, run_id=a.run_id, at=as_of.isoformat())
        print(f"{s['rows_in']} rows in, {s['rows_out']} work items out, {s['findings']} findings")
        if s["rows_in"] != s["rows_out"]:
            print("REFUSED: row count does not match — nothing may be silently dropped", file=sys.stderr)
            return 1
        return 0

    if a.cmd == "import-tickets":
        as_of = _as_of(a.as_of)
        s = tickets.import_tickets(conn, a.export_csv, run_id=a.run_id, at=as_of.isoformat())
        print(f"{s['rows_in']} rows in, {s['rows_out']} tickets out, {s['findings']} findings")
        if s["rows_in"] != s["rows_out"]:
            print("REFUSED: row count does not match — nothing may be silently dropped",
                  file=sys.stderr)
            return 1
        return 0

    if a.cmd == "import-mail":
        from . import intake
        as_of = _as_of(a.as_of)
        c = intake.import_drop(
            conn, a.drop_dir, run_id=a.run_id, channel=a.channel,
            board_id=a.board_id, own_addresses=a.own_address,
            at=datetime(as_of.year, as_of.month, as_of.day))
        print(f"{c['files']} files: {c['new']} new, {c['appended']} appended, "
              f"{c['duplicate']} duplicate, {c['unclassified']} unclassified, "
              f"{c['already_seen']} already seen ({c['phi_flagged']} PHI findings; "
              f"{c['loop_guarded']} auto-replies or bounces ignored; {c['reopened']} "
              f"closed tickets reopened; {c['reply_to_closed']} late replies as new tickets; "
              f"{c['files_kept']} files kept, {c['files_refused']} refused, "
              f"{c['inline_skipped']} signature images skipped)")
        # Losslessness, stated the same way the other importers state it: every
        # file is accounted for by exactly one outcome.
        placed = (c["new"] + c["appended"] + c["duplicate"] + c["unclassified"]
                  + c["already_seen"])
        if placed != c["files"]:
            print("REFUSED: a message was neither placed nor counted", file=sys.stderr)
            return 1
        return 0

    if a.cmd == "import-contacts":
        from . import contacts
        try:
            c = contacts.import_csv(conn, a.export_csv, entity_id=a.entity_id,
                                    at=datetime.now())
        except (LookupError, ValueError) as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        print(f"{c['rows']} rows: {c['new']} new, {c['updated']} updated, "
              f"{c['unchanged']} unchanged, {c['skipped']} skipped "
              f"({c['deactivated']} disabled in AD, {c['reactivated']} re-enabled)")
        for reason in c["reasons"]:
            print("  skipped " + reason, file=sys.stderr)
        if c["new"] + c["updated"] + c["unchanged"] + c["skipped"] != c["rows"]:
            conn.rollback()
            print("REFUSED: a row was neither placed nor counted", file=sys.stderr)
            return 1
        conn.commit()
        return 0

    if a.cmd == "import-computers":
        from . import configurations
        try:
            c = configurations.import_ad_computers(conn, a.export_csv, entity_id=a.entity_id,
                                                   at=datetime.now())
        except (LookupError, ValueError) as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        print(f"{c['rows']} rows: {c['new']} new, {c['updated']} updated, "
              f"{c['unchanged']} unchanged, {c['skipped']} skipped "
              f"({c['deactivated']} disabled in AD)")
        for reason in c["reasons"]:
            print("  skipped " + reason, file=sys.stderr)
        if c["new"] + c["updated"] + c["unchanged"] + c["skipped"] != c["rows"]:
            conn.rollback()
            print("REFUSED: a row was neither placed nor counted", file=sys.stderr)
            return 1
        conn.commit()
        return 0

    if a.cmd == "run-rules":
        from . import workflow
        c = workflow.sweep(conn, at=datetime.now())
        print(f"{c['tickets']} tickets with timed rules: {c['acted']} actions taken, "
              f"{c['errors']} errors (see workflow_run)")
        return 1 if c["errors"] else 0

    if a.cmd == "outbox-pending":
        from . import outbox
        try:
            items = outbox.pending(conn, allowed_domains=tuple(a.allowed_domain),
                                   dry_run=a.dry_run, portal_url=a.portal_url)
        except ValueError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        print(outbox.as_json(items))
        return 0

    if a.cmd == "outbox-mark":
        from . import outbox
        ok = outbox.mark(conn, a.id, a.status, at=datetime.now())
        if not ok:
            print(f"refused: notification {a.id} is not pending", file=sys.stderr)
        return 0 if ok else 1

    if a.cmd == "attachments-usage":
        from . import attachments
        u = attachments.usage(conn)
        print(f"{'month':7} {'board':16} {'files':>6} {'received':>10} {'stored':>10}"
              f" {'pending':>7} {'withheld':>8} {'purged':>6}")
        for r in u["rows"]:
            print(f"{r['month']:7} {r['board_id'][:16]:16} {r['files']:6d} {_mb(r['received']):>10}"
                  f" {_mb(r['stored']):>10} {r['pending']:7d} {r['withheld']:8d} {r['purged']:6d}")
        tt = u["totals"]
        print(f"total: {tt['files']} files ({tt['live']} live, {tt['distinct_live']} distinct);"
              f" {_mb(tt['received'])} received, {_mb(tt['stored'])} stored;"
              f" {tt['pending']} awaiting review, {tt['withheld']} withheld, {tt['purged']} removed")
        print(f"on disk: {u['disk']['files']} files, {_mb(u['disk']['bytes'])} in {u['store']}")
        return 0

    if a.cmd == "attachments-verify":
        from . import attachments
        v = attachments.verify(conn, check_hashes=a.hashes)
        print(f"store {v['store']}: {'present' if v['store_exists'] else 'NOT THERE'};"
              f" {v['live']} live file(s) expected, {v['present']} on disk")
        problems = 0
        for key, words in (("missing", "missing (a live row with no file)"),
                           ("orphans", "orphaned (a file no live row points at)"),
                           ("mismatched", "not matching their name")):
            n = len(v[key])
            if n:
                problems += n
                print(f"  {n} {words}: " + ", ".join(x[:12] for x in v[key][:10])
                      + (" ..." if n > 10 else ""))
        if v["partial"]:
            print(f"  {v['partial']} .part file(s) from an interrupted write")
        if v["recent_unindexed"]:
            print(f"  {v['recent_unindexed']} recent file(s) not yet indexed (within the grace period)")
        if a.mark_missing and v["missing"]:
            n = attachments.record_missing(conn, v["missing"], actor="cli", at=datetime.now())
            conn.commit()
            print(f"  recorded {n} row(s) as missing")
            problems -= len(v["missing"])
        if not a.hashes:
            print("  (contents not checked; add --hashes to read every file)")
        print("OK: the store is whole" if not problems else f"PROBLEMS: {problems}")
        return 0 if not problems else 1

    if a.cmd == "attachments-purge":
        from . import attachments
        as_of = _as_of(a.as_of)
        at = (datetime.now() if a.as_of is None
              else datetime(as_of.year, as_of.month, as_of.day))
        try:
            r = attachments.purge(conn, at=at, withheld_days=a.withheld_days,
                                  closed_days=a.closed_days, apply=a.apply)
        except (RuntimeError, ValueError) as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        head = "APPLIED" if r["applied"] else "PREVIEW"
        print(f"{head}: {r['due']} file(s) due -- {r['by_reason']['WITHHELD']} withheld before "
              f"{r['withheld_before']}, {r['by_reason']['CLOSED']} on tickets closed before "
              f"{r['closed_before']}; {len(r['tickets'])} ticket(s); {r['files_to_free']} file(s),"
              f" {_mb(r['bytes_to_free'])} to free; {r['orphans']} orphan(s)")
        for board_id, n in sorted(r["by_board"].items()):
            print(f"  {board_id}: {n}")
        if r["applied"]:
            print(f"removed {r['files_removed']} file(s) and {r['orphans_removed']} orphan(s),"
                  f" {_mb(r['bytes_freed'])} freed")
        else:
            print("nothing changed; re-run with --apply")
        return 0

    if a.cmd == "setup-board":
        from . import setup
        try:
            r = setup.apply_starter(conn, a.board_id, actor="cli", at=datetime.now())
            conn.commit()
        except LookupError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        print(f"{a.board_id}: added {r['statuses']} statuses, {r['targets']} SLA targets"
              + (", calendar ALL_HOURS" if r["calendar_set"] else ""))
        print("SLA targets are starter placeholders, enforced = 0. The Service Manager "
              "sets the real numbers on the Admin surface.", file=sys.stderr)
        missing = setup.readiness(conn, a.board_id)
        print("ready" if not missing else "still missing: " + "; ".join(missing))
        return 0

    if a.cmd == "walkthrough":
        print("\n".join(walkthrough.run(conn)))
        return 0

    if a.cmd == "serve":
        # Imported here so the rest of the CLI needs nothing under web/, and so a
        # deployment without the web tier still runs init/import/report.
        from .web.server import serve
        serve(a.database, host=a.host, port=a.port)
        return 0

    if a.cmd == "create-local-account":
        from .web import auth
        # The password is read here and nowhere else: a no-echo prompt, never an
        # argument, never an environment variable. That is the rule the whole
        # break-glass arrangement rests on.
        password = getpass.getpass("break-glass password: ")
        if password != getpass.getpass("confirm password: "):
            print("passwords did not match; nothing written", file=sys.stderr)
            return 1
        try:
            auth.create_local_account(conn, a.username, password,
                                      at=datetime.now(), is_sysadmin=a.sysadmin)
            conn.commit()
        except ValueError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        role = "sysadmin" if a.sysadmin else "board-scoped"
        print(f"created break-glass account {a.username!r} ({role}). It is sealed: "
              "seeded into no repository, audited on every use.")
        return 0

    if a.cmd == "create-api-token":
        from .web import api
        try:
            token_id, token = api.create_token(conn, label=a.label, board_id=a.board_id,
                                               at=datetime.now())
            conn.commit()
        except ValueError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        # Printed once, to stdout, and never again: the database holds only the
        # sha256. Lose it and mint another; do not look for it.
        print(f"token_id: {token_id}")
        print(f"token:    {token}")
        print("This is the only time the token is shown. It is stored as a sha256 "
              "and cannot be recovered.", file=sys.stderr)
        return 0

    if a.cmd == "report":
        as_of = _as_of(a.as_of)
        out = Path(a.out)
        (out / "notices").mkdir(parents=True, exist_ok=True)
        stamp = as_of.strftime("%Y%m%d")
        (out / f"PMC_AnnexB_Variation_Register_{stamp}.md").write_text(
            reports.annex_b(conn, as_of=as_of), encoding="utf-8")
        (out / f"PMC_Instrument_Exception_Report_{stamp}.md").write_text(
            reports.instrument_exceptions(conn, as_of=as_of), encoding="utf-8")
        (out / f"PMC_Import_DataQuality_{stamp}.md").write_text(
            reports.data_quality_summary(conn, a.run_id), encoding="utf-8")
        (out / f"PMC_Uplift_Evidence_{stamp}.md").write_text(
            reports.uplift_evidence(conn, as_of=as_of, capacity_hours=a.capacity_hours),
            encoding="utf-8")
        (out / f"PMC_Variation_Paper_{stamp}.md").write_text(
            reports.variation_paper(conn, as_of=as_of, eac_percent=a.eac_percent,
                                    capacity_hours=a.capacity_hours), encoding="utf-8")
        notices = reports.dependency_notices(conn, as_of=as_of)
        for name, body in notices.items():
            (out / "notices" / f"{name}.md").write_text(body, encoding="utf-8")
        print(f"wrote 5 reports and {len(notices)} dependency notices to {out}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
