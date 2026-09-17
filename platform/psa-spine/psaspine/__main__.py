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
