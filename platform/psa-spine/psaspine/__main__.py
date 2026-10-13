"""Command line: init, import, report."""
from __future__ import annotations

import argparse
import getpass
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from . import db, register, reports, tickets, walkthrough


def _as_of(value: str | None) -> date:
    return date.fromisoformat(value) if value else date.today()


def _mb(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / 1024:.0f} KB" if n >= 1024 else f"{n} B"


DB_HELP = ("the SQLite file, or an ODBC connection string for the SQL Server desk "
           "(Driver=…;Server=…;Database=PMC_PSA;Trusted_Connection=yes;…)")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="psaspine", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="create and seed a spine database")
    pi.add_argument("database", help=DB_HELP)

    psp = sub.add_parser("schema-preview", help="SQL Server only: print the generated schema "
                         "script's plan (@Apply = 0) and change nothing")
    psp.add_argument("database", help=DB_HELP)

    pm = sub.add_parser("import", help="import the workstream register CSV")
    pm.add_argument("database", help=DB_HELP)
    pm.add_argument("register_csv")
    pm.add_argument("--run-id", default="run-1")
    pm.add_argument("--as-of")

    pt = sub.add_parser("import-tickets", help="import a desk export CSV")
    pt.add_argument("database", help=DB_HELP)
    pt.add_argument("export_csv")
    pt.add_argument("--run-id", default="desk-1")
    pt.add_argument("--as-of")

    pmail = sub.add_parser("import-mail",
                           help="import a drop of RFC 822 files as tickets "
                                "(idempotent; a re-run makes no second ticket)")
    pmail.add_argument("database", help=DB_HELP)
    pmail.add_argument("drop_dir")
    pwhy = sub.add_parser("mail-why", help="what intake did with a message, by a subject fragment or a sender:"
                                           " its disposition, ticket and findings, or that it never arrived")
    pwhy.add_argument("database", help=DB_HELP)
    pwhy.add_argument("--subject", help="a fragment of the subject, any case")
    pwhy.add_argument("--sender", help="the sender's address or domain, any case")
    pwhy.add_argument("--days", type=int, default=7, help="how far back (default 7)")
    pwho = sub.add_parser("who-sees", help="why a requester does or does not see a ticket on the portal:"
                                           " the address it was raised from, and the addresses the desk knows for them")
    pwho.add_argument("database", help=DB_HELP)
    pwho.add_argument("--ticket", required=True, help="e.g. PMC-000155")
    pwho.add_argument("--person", help="their sign-in name or any address of theirs, to test against it")
    pchk = sub.add_parser("portal-check", help="would the email link open this request for this person: asks the"
                                               " portal itself, signed in as them, with no mailbox and no browser."
                                               " Writes nothing")
    pchk.add_argument("database", help=DB_HELP)
    pchk.add_argument("--ticket", required=True, help="e.g. PMC-000397")
    pchk.add_argument("--person", help="their Windows name or an address of theirs (default: the requester)")
    pchk.add_argument("--portal-url", help="the portal's address (default: PSA_PORTAL_URL), e.g. https://help.example")
    phealth = sub.add_parser("mail-health", help="is mail becoming tickets at all: when a message last arrived,"
                                                 " what came of the ones since, and which addresses a board claims")
    phealth.add_argument("database", help=DB_HELP)
    phealth.add_argument("--days", type=int, default=2, help="how far back to count (default 2)")
    pcat = sub.add_parser("catalogue-health",
                          help="what the Type, Subtype and Item pickers hold on this desk, per board, and what"
                               " fills them if they are thin. Reads only; writes nothing")
    pcat.add_argument("database", help=DB_HELP)
    pcat.add_argument("--board", help="one board_id, instead of every board")
    pcan = sub.add_parser("add-cancelled",
                          help="give every board the closed >Cancelled status; moves tickets out of an open"
                               " 'Cancelled' and retires it. Shows what it would do unless --apply")
    pcan.add_argument("database", help=DB_HELP)
    pcan.add_argument("--board", help="one board_id, instead of every active board")
    pcan.add_argument("--apply", action="store_true", help="do it; without this nothing is written")
    pcan.add_argument("--actor", default="add-cancelled")
    pcmp = sub.add_parser("board-compare",
                          help="how one board is set up differently from another: settings, statuses, SLA targets,"
                               " members, addresses, emails, catalogue. Reads only; writes nothing")
    pcmp.add_argument("database", help=DB_HELP)
    pcmp.add_argument("board_a", help="the board that looks right, e.g. IT_HELP")
    pcmp.add_argument("board_b", help="the board that does not, e.g. PROCUREMENT")
    pretry = sub.add_parser("mail-retry", help="forget a message intake set aside (UNCLASSIFIED) so a fresh pickup"
                                               " sync imports it again, once the cause is put right")
    pretry.add_argument("database", help=DB_HELP)
    pretry.add_argument("--message-id", help="as mail-why printed it, e.g. <abc@yahoo.com>")
    pretry.add_argument("--all", action="store_true", dest="all_of_them",
                        help="every message intake set aside, not one; use once the cause is put right")
    pretry.add_argument("--days", type=int, help="with --all, only those that arrived in the last N days")
    pretry.add_argument("--actor", required=True)
    pretry.add_argument("--apply", action="store_true", help="do it; without this it only says what it would do")
    psys = sub.add_parser("set-sysadmin", help="grant (or with --off take back) the desk's sysadmin on a member"
                                               " record, so their normal Windows sign-in runs every Setup page")
    psys.add_argument("database", help=DB_HELP)
    psys.add_argument("--member", required=True, help="the sign-in name, e.g. dada.banal")
    psys.add_argument("--off", action="store_true", help="take it back instead")
    psys.add_argument("--actor", default="host", help="who is doing this, for the audit row (default host)")
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
    pw.add_argument("database", help=DB_HELP)

    ps = sub.add_parser("serve", help="run the Phase B fulfiller desk (pilot, LAN only)")
    ps.add_argument("database", help=DB_HELP)
    ps.add_argument("--host", default="127.0.0.1",
                    help="interface to bind; refuses 0.0.0.0 (default 127.0.0.1)")
    ps.add_argument("--port", type=int, default=8085,
                    help="port to listen on (default 8085; 8080 is the queue screens' on DND-SQL01)")
    ps.add_argument("--cert", help="PEM certificate: the desk then speaks HTTPS (with --key)")
    ps.add_argument("--key", help="PEM private key for --cert; readable by the task account only")

    pc = sub.add_parser("create-local-account",
                        help="create a sealed break-glass account (password read from a "
                             "no-echo prompt, never an argument)")
    pc.add_argument("database", help=DB_HELP)
    pc.add_argument("--username", required=True)
    pc.add_argument("--sysadmin", action="store_true",
                    help="grant cross-board admin; off by default")

    pk = sub.add_parser("create-api-token",
                        help="mint a machine API token for one board; printed ONCE, "
                             "stored only as a sha256")
    pk.add_argument("database", help=DB_HELP)
    pk.add_argument("--label", required=True,
                    help="what it is for, in words: 'orthanc monitoring'")
    pk.add_argument("--board", required=True, dest="board_id",
                    help="the one board this token may raise tickets onto")
    pk.add_argument("--scope", choices=("RAISE", "READ", "WRITE"), default="RAISE",
                    help="RAISE tickets and read its own (default); READ every ticket on the board and the "
                         "configurations; WRITE a note, a status or an owner as well")

    pb = sub.add_parser("backup",
                        help="escrow copy via SQLite's backup API (safe under WAL); "
                             "refuses to overwrite, proves the copy")
    pb.add_argument("database", help=DB_HELP)
    pb.add_argument("destination")

    pac = sub.add_parser("import-contacts",
                         help="upsert contacts under one company from an AD export "
                              "(scripts/Export-PmcAdContacts.ps1)")
    pac.add_argument("database", help=DB_HELP)
    pac.add_argument("export_csv")
    pac.add_argument("--company", required=True, dest="entity_id",
                     help="the company these people belong to, e.g. PMC")

    pdp = sub.add_parser("import-departments",
                         help="upsert the department list from a one-column CSV (Department); "
                              "a re-run adds and retires, never deletes")
    pdp.add_argument("database", help=DB_HELP)
    pdp.add_argument("export_csv")

    pbz = sub.add_parser("sync-bizbox",
                         help="mirror BizBox agreements, products, purchase orders and invoices, read-only, "
                              "from a folder of CSV exports or from PSA_BIZBOX_ODBC; preview unless --apply")
    pbz.add_argument("database", help=DB_HELP)
    pbz.add_argument("--map", required=True, dest="map_file",
                     help="the map file naming the BizBox views and columns (see bizbox/bizbox-map.sample.json)")
    src = pbz.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv-dir", help="a folder holding one <kind>.csv per kind the map names "
                                       "(product, purchase_order, po_line, invoice, and agreement if mapped)")
    src.add_argument("--odbc", action="store_true",
                     help="read the mapped views through the read-only connection string in PSA_BIZBOX_ODBC")
    pbz.add_argument("--apply", action="store_true", help="write; without it nothing is changed")

    pbp = sub.add_parser("bizbox-push",
                         help="13 Oct 2026: offer every APPROVED change to the BizBox writer. With "
                              "PSA_BIZBOX_WRITE_ODBC set the writer calls psa.sp_apply_change in BizBox (SQL01's "
                              "procedure, a login of its own); unset, nothing moves. Preview unless --apply")
    pbp.add_argument("database", help=DB_HELP)
    pbp.add_argument("--apply", action="store_true", help="call the writer; without this nothing is sent")
    pbc = sub.add_parser("bizbox-changes",
                         help="list the changes proposed to BizBox records as JSON, or close one with --decide "
                              "after it was done in BizBox; nothing here writes to BizBox")
    pbc.add_argument("database", help=DB_HELP)
    pbc.add_argument("--status", default="PENDING", choices=["PENDING", "APPLIED", "REJECTED", "CANCELLED"])
    pbc.add_argument("--decide", type=int, metavar="CHANGE_ID")
    pbc.add_argument("--as", dest="outcome", choices=["APPLIED", "REJECTED", "CANCELLED"])
    pbc.add_argument("--answer", default="", help="what BizBox said, or who applied it there")

    phl = sub.add_parser("import-holidays",
                         help="add holidays to a holiday list from a CSV (Date, Name, optional AllDay, "
                              "Start, End); a date already on the list is left alone")
    phl.add_argument("database", help=DB_HELP)
    phl.add_argument("holiday_list_id", help="the list's id, as Setup > Calendars shows it")
    phl.add_argument("export_csv")

    pcf = sub.add_parser("import-computers",
                         help="upsert configurations under one company from an AD "
                              "computers export (scripts/Export-PmcAdComputers.ps1)")
    pcf.add_argument("database", help=DB_HELP)
    pcf.add_argument("export_csv")
    pcf.add_argument("--company", required=True, dest="entity_id")

    prr = sub.add_parser("run-rules",
                         help="run time-based workflow events (ON_SCHEDULE, ON_SLA_THRESHOLD) "
                              "over every open ticket; the server runs this every minute")
    prr.add_argument("database", help=DB_HELP)

    pob = sub.add_parser("outbox-pending",
                         help="print due notifications as JSON for the Graph sender; "
                              "unresolvable or out-of-domain recipients are marked NO_SENDER")
    pob.add_argument("database", help=DB_HELP)
    pob.add_argument("--allowed-domain", action="append", required=True,
                     help="only addresses in this domain are released (repeatable)")
    pob.add_argument("--dry-run", action="store_true", help="change nothing (the sender's preview)")
    pob.add_argument("--portal-url",
                     help="https:// address of the requester portal for the link in requester "
                          "emails (else PSA_PORTAL_URL; never committed)")
    pob.add_argument("--channel", choices=("EMAIL", "TEAMS"), default="EMAIL",
                     help="which sender is asking: EMAIL (the Graph sender) or TEAMS (the webhook sender)")
    pob.add_argument("--desk-url",
                     help="https:// address of the desk at PMC, for the link in a member's email and on a "
                          "Teams card (else PSA_PUBLIC_URL)")
    pob.add_argument("--portal-away-url",
                     help="https:// address of the requester portal away from PMC, for a second link beside the "
                          "portal's in requester and approver emails (else PSA_PORTAL_AWAY_URL; empty = none)")
    pob.add_argument("--desk-away-url",
                     help="https:// address of the desk away from PMC (the published one behind the sign-in "
                          "gate), for a second link beside it (else PSA_DESK_AWAY_URL; empty = none)")
    pms = sub.add_parser("mail-setup",
                         help="058: one board's mail in one step - its intake addresses, the requester switch, "
                              "and the status and picked-up emails. Preview unless --apply")
    pms.add_argument("database", help=DB_HELP)
    pms.add_argument("--board", required=True, help="the board_id, e.g. IT_HELP")
    pms.add_argument("--addresses", help="the board's intake addresses, comma separated (replaces the list)")
    pms.add_argument("--email-requester", choices=("on", "off"), help="the board's requester switch")
    pms.add_argument("--moving-emails", choices=("on", "off"),
                     help="every status's email and the picked-up email, keeping their words")
    pms.add_argument("--actor", required=True, help="who this is done for, for the audit trail")
    pms.add_argument("--apply", action="store_true", help="write it; without this nothing is changed")
    pms.add_argument("--show", action="store_true",
                     help="afterwards, print every email the board sends a requester: on or off, subject and words")
    ppk = sub.add_parser("setup-pmc",
                         help="the PMC pack: hospital statuses on the help desk and procurement boards, and with "
                              "--with-catalogue its Areas, Subtypes and Items; adds only what is missing and never "
                              "brings back a retired or moved row. Preview unless --apply")
    ppk.add_argument("database", help=DB_HELP)
    ppk.add_argument("--helpdesk", default="IT_HELP", help="the help desk board_id (default IT_HELP)")
    ppk.add_argument("--procurement", help="the procurement board_id; omit to leave procurement alone")
    ppk.add_argument("--live", action="store_true", help="make the procurement board live (needs --owner and --deputy)")
    ppk.add_argument("--owner", help="the procurement board's owner (a member)")
    ppk.add_argument("--deputy", help="the procurement board's deputy (a member)")
    ppk.add_argument("--actor", required=True, help="who this is done for, for the audit trail")
    ppk.add_argument("--apply", action="store_true", help="write it; without this nothing is changed")
    ppk.add_argument("--with-catalogue", action="store_true",
                     help="also the pack's Areas, Subtypes, Items and pairs. Off unless asked: a live desk shapes its"
                          " own catalogue. Rows this desk retired or moved are listed as skip: and left alone")
    ppk.add_argument("--statuses-only", action="store_true",
                     help="the pack's statuses and nothing else (now the default; kept so older runbooks still work)")
    ptl = sub.add_parser("portal-tiles",
                         help="the PMC starter tiles on the requester portal (078): nine tiles with their smaller "
                              "tiles and questions, matched to the live catalogue by name. Adds only what is not "
                              "there and never changes a tile that is. Preview unless --apply")
    ptl.add_argument("database", help=DB_HELP)
    ptl.add_argument("--helpdesk", default="IT_HELP", help="the help desk board_id (default IT_HELP)")
    ptl.add_argument("--procurement", default="PROCUREMENT", help="the procurement board_id (default PROCUREMENT)")
    ptl.add_argument("--actor", required=True, help="who this is done for, for the audit trail")
    ptl.add_argument("--apply", action="store_true", help="write it; without this nothing is changed")
    pmw = sub.add_parser("mail-words",
                         help="12 Oct 2026: a board's own warm, plain words for its requester emails -- opened, "
                              "replied, closed, picked up and every status -- for the PMO Helpdesk or Procurement. "
                              "Keeps words the board already wrote unless --replace; never turns an email on or "
                              "off. Preview unless --apply")
    pmw.add_argument("database", help=DB_HELP)
    pmw.add_argument("--board", required=True, help="the board_id, e.g. IT_HELP or PROCUREMENT")
    pmw.add_argument("--words", required=True, choices=("HELPDESK", "PROCUREMENT"), help="which set of words")
    pmw.add_argument("--replace", action="store_true", help="also overwrite words the board already wrote")
    pmw.add_argument("--actor", required=True, help="who this is done for, for the audit trail")
    pmw.add_argument("--apply", action="store_true", help="write it; without this nothing is changed")
    ptf = sub.add_parser("ticket-fill",
                         help="12 Oct 2026: tickets filed under UNCLASSIFIED take PMC's company, and the portal tiles "
                              "that would leave a ticket with no Type > Subtype > Item are named. Never a department: "
                              "Dada's ruling (Part 77) is that one is set only at the door. Counts and tile names "
                              "only. Preview unless --apply")
    ptf.add_argument("database", help=DB_HELP)
    ptf.add_argument("--actor", required=True, help="who this is done for, for the audit trail")
    ptf.add_argument("--apply", action="store_true", help="write it; without this nothing is changed")
    ptt = sub.add_parser("ticket-topics",
                         help="what is usually ticketed: counts per board, the most used Type > Subtype > Item, and "
                              "how many summaries each portal tile's words would catch. Counts only: it never prints "
                              "a summary, a name or a reference. Writes nothing")
    ptt.add_argument("database", help=DB_HELP)
    ptt.add_argument("--days", type=int, default=180, help="how far back (default 180)")
    ptt.add_argument("--top", type=int, default=25, help="how many Type > Subtype > Item rows (default 25)")
    pas = sub.add_parser("add-status", help="one status on one board, nothing else. Preview unless --apply")
    pas.add_argument("database", help=DB_HELP)
    pas.add_argument("board_id")
    pas.add_argument("name", help="e.g. 'On Hold', or '>Cancelled' for a closed one")
    pas.add_argument("--escalation", default="NO_ESCALATION",
                     help="NO_ESCALATION holds the SLA clocks (default); NOT_RESPONDED, RESPONDED, RESOLUTION_PLAN, RESOLVED")
    pas.add_argument("--closed", action="store_true", help="a closed status")
    pas.add_argument("--portal", help="what the requester reads on the portal")
    pas.add_argument("--actor", required=True, help="who this is done for, for the audit trail")
    pas.add_argument("--apply", action="store_true", help="write it; without this nothing is changed")
    pcp = sub.add_parser("calendar-pending", help="059: due Outlook calendar writes as JSON for Sync-PsaCalendars.ps1")
    pcp.add_argument("database", help=DB_HELP)
    pcp.add_argument("--allowed-domain", action="append", required=True)
    pcp.add_argument("--desk-url", help="https:// address of the desk, for the link in a visit's event")
    pcp.add_argument("--dry-run", action="store_true")
    pcm = sub.add_parser("calendar-mark", help="059: record what the calendar sync did with one write")
    pcm.add_argument("database", help=DB_HELP)
    pcm.add_argument("--id", type=int, required=True)
    pcm.add_argument("--status", choices=("SENT", "FAILED"), required=True)
    pcm.add_argument("--event-id")
    pcb = sub.add_parser("calendar-members", help="059: the members whose Outlook calendars are synced, as JSON")
    pcb.add_argument("database", help=DB_HELP)
    pcb.add_argument("--allowed-domain", action="append", required=True)
    pci = sub.add_parser("calendar-busy", help="059: replace members' Outlook busy times from a JSON file")
    pci.add_argument("database", help=DB_HELP)
    pci.add_argument("--file", required=True)
    pci.add_argument("--from", dest="start", required=True, help="YYYY-MM-DD HH:MM")
    pci.add_argument("--to", dest="end", required=True, help="YYYY-MM-DD HH:MM")
    pcf = sub.add_parser("calendar-backfill", help="059: queue every future visit and block never written to Outlook")
    pcf.add_argument("database", help=DB_HELP)
    pcf.add_argument("--apply", action="store_true")
    pom = sub.add_parser("outbox-mark", help="record what the sender did with one notification")
    pom.add_argument("database", help=DB_HELP)
    pom.add_argument("--id", type=int, required=True)
    pom.add_argument("--status", choices=("SENT", "FAILED"), required=True)

    pau = sub.add_parser("attachments-usage",
                         help="what the attachment store holds, by month and board, and on disk")
    pau.add_argument("database", help=DB_HELP)
    pav = sub.add_parser("attachments-verify",
                         help="is the store whole: every live row has its file, every file a row")
    pav.add_argument("database", help=DB_HELP)
    pav.add_argument("--hashes", action="store_true",
                     help="also read every live file and check it against its name (slow)")
    pav.add_argument("--mark-missing", action="store_true",
                     help="record rows whose file is gone as removed (reason MISSING), audited")
    pap = sub.add_parser("attachments-purge",
                         help="remove files under the retention rule; PREVIEW unless --apply")
    pap.add_argument("database", help=DB_HELP)
    pap.add_argument("--withheld-days", type=int, required=True,
                     help="remove a withheld file this many days after its review")
    pap.add_argument("--closed-days", type=int, required=True,
                     help="remove any file this many days after its ticket closed")
    pap.add_argument("--apply", action="store_true", help="change something (default: preview)")
    pap.add_argument("--as-of", help="today, for a rehearsal (default: now)")

    pu = sub.add_parser("setup-board",
                        help="give a board the starter statuses, calendar and SLA "
                             "targets (adds what is missing, never overwrites)")
    pu.add_argument("database", help=DB_HELP)
    pu.add_argument("--board", required=True, dest="board_id")
    pu.add_argument("--admin", dest="admin", help="make this account the board's first "
                    "administrator, if it has no members yet (audited)")

    pba = sub.add_parser("board-admin", help="make an account the first administrator of a "
                         "board that has no members (a seeded board); audited")
    pba.add_argument("database", help=DB_HELP)
    pba.add_argument("--board", required=True, dest="board_id")
    pba.add_argument("--member", required=True)

    pr = sub.add_parser("report", help="write Annex B, dependency notices and the exception report")
    pr.add_argument("database", help=DB_HELP)
    pr.add_argument("--out", required=True)
    pr.add_argument("--as-of")
    pr.add_argument("--run-id", default="run-1")
    pr.add_argument("--eac-percent", type=float,
                    help="capacity uplift %% claimed; omitted leaves the paper unpriced")
    pr.add_argument("--capacity-hours", type=float,
                    help="declared available capacity per month — the uplift denominator")

    a = p.parse_args(argv)
    db.set_source({"import-mail": "INTAKE", "run-rules": "RULES", "sync-bizbox": "BIZBOX",
                   "bizbox-changes": "BIZBOX", "serve": "DESK"}.get(a.cmd, "CLI"))

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

    if a.cmd == "schema-preview":
        if db.backend_of(a.database) != "mssql":
            print("refused: the schema script is SQL Server's; a SQLite file has no preview to print",
                  file=sys.stderr)
            return 1
        from . import mssql
        conn = db.connect(a.database)
        try:
            for line in mssql.preview_port(conn):
                print(line)
        except RuntimeError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        finally:
            db.close(conn)
        return 0

    if a.cmd == "init":
        db.init(a.database).close()
        print(("ready: " if db.backend_of(a.database) == "mssql" else "created ") + db.describe(a.database))
        return 0

    conn = db.connect(a.database)
    try:
        return _run(conn, a)
    finally:
        # Closed on every road out. Windows cannot delete a file a process
        # still holds, which is how a test on DND-SQL01 found this (26 Sep).
        db.close(conn)


def _run(conn, a) -> int:
    """The commands that work on an open connection."""
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

    if a.cmd == "set-sysadmin":
        from . import members
        try:
            said = members.set_sysadmin(conn, a.member, not a.off, at=datetime.now(), actor=a.actor)
        except members.Refused as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 2
        conn.commit()
        print(said)
        print("sysadmins now: " + (", ".join(members.sysadmins(conn)) or "none"))
        return 0

    if a.cmd == "who-sees":
        row = conn.execute("SELECT t.requested_by, t.intake_source, t.board_id, w.name"
                           "  FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
                           " WHERE t.work_item_id = ?", (a.ticket,)).fetchone()
        if row is None:
            print(f"there is no ticket {a.ticket}")
            return 1
        raised = (row["requested_by"] or "").strip()
        print(f"{a.ticket} on {row['board_id']} was raised by: {raised or '(nobody: it has no requester)'}"
              f"  (came in by {row['intake_source'] or 'the desk'})")
        if not raised:
            print("A ticket with no requester is on nobody's portal. Set the Contact on the ticket.")
            return 0
        seen = [r["address"] for r in conn.execute("SELECT address FROM ticket_cc WHERE work_item_id = ?", (a.ticket,))]
        if seen:
            print("copied on it (they do NOT see it on the portal, by design): " + ", ".join(seen))
        if not a.person:
            print("Add --person <their sign-in name or address> to test whether they would see it.")
            return 0
        # The portal's own rule (075), so this cannot say one thing while the
        # portal does another: their addresses, and their Windows name on the
        # hospital's own mail domains.
        from .portal_check import person_user
        from .web import Config, Ctx
        from .web.views import portal as _portal
        user, _door = person_user(conn, a.person)
        addrs = _portal._identities(Ctx(conn=conn, request=None, user=user, config=Config(), now=datetime.now()))
        print(f"the desk knows these addresses for {a.person}: " + ", ".join(addrs))
        if raised.lower() in addrs:
            print(f"-> they DO see {a.ticket} on the portal.")
            return 0
        print(f"-> they do NOT see {a.ticket}: it was raised from {raised}, which is none of those.")
        print("   Put that address on their contact record (email or upn) and they see it at once,"
              " or change the ticket's Contact to them. The link in an email sent since 075 opens it for"
              " them anyway; portal-check proves it.")
        return 0

    if a.cmd == "portal-check":
        import os
        from . import portal_check
        url = (a.portal_url or os.environ.get("PSA_PORTAL_URL") or "").strip()
        if not url.lower().startswith("https://"):
            print("refused: give the portal's https address with --portal-url, or set PSA_PORTAL_URL", file=sys.stderr)
            return 2
        lines = portal_check.check(conn, a.ticket, person=a.person, portal_url=url)
        print("\n".join(lines))
        return 1 if lines[0].startswith("there is no ticket") else 0

    if a.cmd == "mail-health":
        from . import intake
        h = intake.health(conn, days=a.days)
        if not h["last"]:
            print("the desk has taken NO mail, ever. Nothing has reached it from a pickup.")
        else:
            L = h["last"]
            where = f" -> {L['work_item_id']}" if L["work_item_id"] else ""
            print(f"last message the desk took: {L['received_at']}  {L['disposition']}{where}"
                  f"  from {L['from_address'] or '-'} to {L['to_address'] or '-'}")
        print(f"in the last {h['days']} day(s): {h['total']} message(s)"
              + ("" if not h["by_disposition"] else "; " + ", ".join(f"{k} {v}" for k, v in sorted(h["by_disposition"].items()))))
        if h["errors"]:
            print(f"{h['errors']} message(s) were set aside with an error: `mail-why --sender <them>` says why for one")
        print("claimed addresses: " + (", ".join(f"{k} -> {v}" for k, v in sorted(h["claims"].items())) or "none"))
        if not h["total"]:
            print(r"NOTHING arrived in that window: the fault is before the desk. Check the pickup task and its log"
                  r" (D:\psa\mail-state\mail-pickup-<mailbox>.log), or run Repair-PsaMailPickup.ps1.")
        return 0

    if a.cmd == "add-cancelled":
        from . import setup as _setup
        from datetime import datetime as _dt
        boards = [a.board] if a.board else [r[0] for r in conn.execute(
            "SELECT board_id FROM board WHERE COALESCE(inactive, 0) = 0 ORDER BY board_id")]
        lines = []
        try:
            for b in boards:
                lines += _setup.ensure_cancelled(conn, b, at=_dt.now(), actor=a.actor, apply=a.apply)
            if a.apply:
                conn.commit()
            else:
                conn.rollback()
        except Exception as exc:                          # noqa: BLE001
            conn.rollback()
            print(f"refused, nothing written: {exc}", file=sys.stderr)
            return 2
        for line in lines:
            print(("done: " if a.apply else "would: ") + line)
        print(("" if lines else "every board already has >Cancelled. ")
              + ("Applied." if a.apply else "Nothing was written; add --apply to do it."))
        return 0
    if a.cmd == "board-compare":
        from . import setup as _setup
        try:
            c = _setup.board_compare(conn, a.board_a, a.board_b)
        except ValueError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 2
        na, nb = c["names"]
        print(f"{c['a']} ({na})  against  {c['b']} ({nb})")
        print("\nsettings that differ:" if c["settings"] else "\nsettings: the same")
        for label, x, y in c["settings"]:
            print(f"  {label:<30} {str(x if x is not None else '-'):<18} {y if y is not None else '-'}")
        print("\nset-up that differs, by count:" if c["parts"] else "\nset-up counts: the same")
        for label, x, y in c["parts"]:
            flag = "   <- none on " + c["b"] if not y and x else ("   <- none on " + c["a"] if not x and y else "")
            print(f"  {label:<30} {x:<18} {y}{flag}")
        if c["statuses_only_a"]:
            print(f"\nstatuses only {c['a']} has: " + ", ".join(c["statuses_only_a"]))
        if c["statuses_only_b"]:
            print(f"statuses only {c['b']} has: " + ", ".join(c["statuses_only_b"]))
        print(f"\ncatalogue pairs of its own: {c['a']} {c['own_pairs'][0]}, {c['b']} {c['own_pairs'][1]}")
        print("what each holds (differs for good reasons; context only): "
              + "; ".join(f"{label} {x} / {y}" for label, x, y in c["holds"]))
        print("\nThe board page is one piece of code for every board: a difference you can see is one of the"
              " lines above, or the person is not being recognised as a member at all (they then see the"
              " requester's page, My requests, with three links across the top).")
        return 0

    if a.cmd == "catalogue-health":
        from . import setup as _setup
        h = _setup.catalogue_health(conn)
        print(f"the tree: {h['types']} Type(s), {h['subtypes']} Subtype(s), {h['items']} Item(s),"
              f" {h['pairs']} Subtype x Item pair(s)"
              + (f" ({h['types_retired']} Type(s) retired)" if h["types_retired"] else ""))
        rows = [b for b in h["boards"] if not a.board or b["board_id"] == a.board]
        if a.board and not rows:
            print(f"refused: no board {a.board}", file=sys.stderr)
            return 2
        for b in rows:
            mark = "  THIN" if b["offered"] < _setup.THIN else ""
            print(f"  {b['board_id']:<14} {b['offered']:>4} pair(s) in its picker"
                  f" ({b['own']} its own), {len(b['types'])} Type(s), {b['subtypes']} Subtype(s){mark}")
            if b["types"]:
                shown = ", ".join(b["types"][:6])
                print(f"                 {shown}" + (", ..." if len(b["types"]) > 6 else ""))
        thin = [b["board_id"] for b in rows if b["offered"] < _setup.THIN]
        if thin:
            print(f"THIN: {', '.join(thin)} would open a picker with less than {_setup.THIN} pairs, so a"
                  " technician has nothing to classify with.")
            print("  Setup > Catalogue > Apply the template loads the seed's Areas, Subtypes and Items;"
                  " `psaspine setup-pmc <db> --actor <you> --apply` adds the hospital's own on top."
                  " Both add only what is missing.")
        else:
            print("every board's picker has something to classify with.")
        return 0

    if a.cmd == "mail-why":
        from . import intake
        since = (datetime.now() - timedelta(days=a.days)).isoformat(sep=" ", timespec="minutes")
        try:
            r = intake.why(conn, subject=a.subject, sender=a.sender, since=since)
        except ValueError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 2
        if not r["rows"]:
            print(f"intake saw no message matching that in the last {a.days} days: nothing arrived from the pickup."
                  r" Check the mailbox's pickup task is registered and its log (D:\psa\logs\PSA-Mail-<mailbox>.log).")
        for i in r["rows"]:
            where = (f" -> {i['work_item_id']} on {i['board_id']}" if i["work_item_id"] else "")
            print(f"{i['received_at']}  {i['disposition']:12}{where}  from {i['from_address'] or '-'} to {i['to_address'] or '-'}"
                  f"  subject: {i['subject'] or '-'}  (run {i['run_id']}; message-id {i['message_id']})")
            for f in i["findings"]:
                print(f"    {f}")
        if r["exclusion"]:
            print(f"an exclusion rule catches this sender: {r['exclusion']} (Setup > Email connector)")
        elif a.sender:
            print(f"no exclusion rule catches this sender ({r['exclusions']} rule(s) in all)")
        print("claimed addresses: " + (", ".join(f"{k} -> {v}" for k, v in sorted(r["claims"].items())) or "none"))
        return 0
    if a.cmd == "mail-retry":
        from . import intake
        since = ((datetime.now() - timedelta(days=a.days)).isoformat(sep=" ", timespec="minutes")
                 if getattr(a, "days", None) else None)
        if not a.all_of_them and not a.message_id:
            rows = intake.set_aside(conn, since=since)
            if not rows:
                print("nothing was set aside: there is nothing to retry")
                return 0
            print(f"{len(rows)} message(s) set aside. --message-id one of them, or --all for every one:")
            for r in rows[:50]:
                print(f"  {r['received_at']}  from {r['from_address'] or '-'} to {r['to_address'] or '-'}"
                      f"  subject: {r['subject'] or '(none)'}  {r['message_id']}")
            if len(rows) > 50:
                print(f"  ... and {len(rows) - 50} more")
            return 0
        if a.all_of_them:
            rows = intake.set_aside(conn, since=since)
            if not a.apply:
                print(f"would forget {len(rows)} set-aside message(s) so the next pickup imports them again."
                      " Nothing was changed; add --apply.")
                return 0
            done = intake.retry_all(conn, at=datetime.now(), actor=a.actor, since=since)
            conn.commit()
            print(f"{len(done)} message(s) forgotten. Now clear the delta link so the pickup reads back over them:"
                  r" Repair-PsaMailPickup.ps1 -Apply -ResetDelta")
            return 0
        from . import intake
        try:
            if not a.apply:
                row = conn.execute("SELECT disposition FROM intake_message WHERE message_id = ?", (a.message_id,)).fetchone()
                if row is None:
                    raise LookupError(f"intake never saw {a.message_id}")
                print(f"would forget {a.message_id} ({row['disposition']}); nothing changed without --apply")
                return 0
            print(intake.retry(conn, a.message_id, at=datetime.now(), actor=a.actor))
            conn.commit()
            return 0
        except (LookupError, ValueError) as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1
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
              f"{c['inline_skipped']} signature images skipped)"
              + (f"; {c['errors']} could not be placed (INTAKE_ERROR, see Setup > Email connector)" if c.get("errors") else ""))
        # Losslessness, stated the same way the other importers state it: every
        # file is accounted for by exactly one outcome.
        placed = (c["new"] + c["appended"] + c["duplicate"] + c["unclassified"]
                  + c["already_seen"])
        if placed != c["files"]:
            print("REFUSED: a message was neither placed nor counted", file=sys.stderr)
            return 1
        return 0

    if a.cmd == "import-departments":
        from . import departments
        try:
            c = departments.import_csv(conn, a.export_csv, at=datetime.now())
        except (LookupError, ValueError) as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        conn.commit()
        print(f"{c['rows']} names: {c['new']} new, {c['seen']} seen, {c['restored']} restored, "
              f"{c['retired']} retired")
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

    if a.cmd == "sync-bizbox":
        from . import bizbox
        try:
            mapping = bizbox.load_map(a.map_file)
            rows = bizbox.read_csv_dir(a.csv_dir, mapping) if a.csv_dir else bizbox.read_odbc(mapping)
            counts = bizbox.sync(conn, rows, at=datetime.now(), actor="cli", apply=a.apply)
        except bizbox.Refused as exc:
            conn.rollback()
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:                            # the store or the driver said no: a sentence, no traceback
            conn.rollback()
            print(f"failed: {type(exc).__name__}: {str(exc)[:300]}", file=sys.stderr)
            return 1
        for kind, c in counts.items():
            print(f"{kind}: {c['rows']} rows, {c['new']} new, {c['changed']} changed, {c['unchanged']} unchanged, "
                  f"{c['absent']} absent, {c['returned']} returned, {c['skipped']} skipped")
        print("applied" if a.apply else "preview only: nothing was written (add --apply)")
        return 0

    if a.cmd == "bizbox-push":
        from . import bizbox
        due = bizbox.pushable(conn)
        kinds = {}
        for ch in due:
            kinds[ch["kind"]] = kinds.get(ch["kind"], 0) + 1
        print(f"approved and waiting: {len(due)} change(s)" + (" (" + ", ".join(f"{k.lower()} {n}" for k, n in sorted(kinds.items())) + ")" if kinds else ""))
        if not a.apply:
            print("PREVIEW: nothing sent; re-run with --apply")
            conn.rollback()
            return 0
        try:
            writer = bizbox.writer_in_force()
        except bizbox.Refused as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        counts = bizbox.push(conn, writer, at=datetime.now(), actor=f"writer:{writer.name}")
        conn.commit()
        print(f"writer {writer.name}: {counts['applied']} applied, {counts['rejected']} refused by BizBox, "
              f"{counts['pending']} still waiting")
        return 0

    if a.cmd == "bizbox-changes":
        import json as _json
        from . import bizbox
        if a.decide is not None:
            if not a.outcome:
                print("refused: --decide needs --as APPLIED, REJECTED or CANCELLED", file=sys.stderr)
                return 1
            try:
                bizbox.decide(conn, a.decide, a.outcome, answer=a.answer, at=datetime.now(), actor="cli")
            except bizbox.Refused as exc:
                print(f"refused: {exc}", file=sys.stderr)
                return 1
            conn.commit()
            print(f"change {a.decide}: {a.outcome.lower()}")
            return 0
        rows = [dict(r) for r in bizbox.changes(conn, status=a.status)]
        print(_json.dumps(rows, indent=2, default=str))
        return 0

    if a.cmd == "import-holidays":
        from . import calendars
        try:
            c = calendars.import_csv(conn, a.holiday_list_id, a.export_csv, at=datetime.now())
        except (LookupError, ValueError) as exc:
            conn.rollback()
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        conn.commit()
        print(f"{c['rows']} rows: {c['new']} new, {c['seen']} seen")
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
        from . import paging, recurring, workflow
        c = workflow.sweep(conn, at=datetime.now())
        raised = recurring.raise_due(conn, at=datetime.now())
        failed = [r for r in raised if "error" in r]
        p = paging.tick(conn, at=datetime.now())
        conn.commit()
        print(f"{c['tickets']} tickets with timed rules: {c['acted']} actions taken, "
              f"{c['errors']} errors (see workflow_run); recurring: {len(raised) - len(failed)} raised, "
              f"{len(failed)} failed (see audit_event); pages: {p['open']} open, {p['sent']} repeated, "
              f"{p['ended']} ended, {p['escalated']} escalated")
        return 1 if c["errors"] or failed else 0

    if a.cmd == "outbox-pending":
        from . import channels, outbox
        try:
            if a.channel == "TEAMS":
                items = channels.pending_teams(conn, dry_run=a.dry_run, desk_url=a.desk_url,
                                               desk_away_url=a.desk_away_url)
            else:
                items = outbox.pending(conn, allowed_domains=tuple(a.allowed_domain),
                                       dry_run=a.dry_run, portal_url=a.portal_url,
                                       desk_url=a.desk_url, desk_away_url=a.desk_away_url,
                                       portal_away_url=a.portal_away_url)
        except ValueError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        print(outbox.as_json(items))
        return 0

    if a.cmd in ("calendar-pending", "calendar-mark", "calendar-members", "calendar-busy", "calendar-backfill"):
        import json as _json
        from . import calsync, outbox
        if a.cmd == "calendar-pending":
            print(outbox.as_json(calsync.pending(conn, allowed_domains=tuple(a.allowed_domain),
                                                 desk_url=a.desk_url or "", dry_run=a.dry_run)))
            return 0
        if a.cmd == "calendar-mark":
            ok = calsync.mark(conn, a.id, a.status, at=datetime.now(), event_id=a.event_id)
            return 0 if ok else 1
        if a.cmd == "calendar-members":
            print(outbox.as_json(calsync.members(conn, allowed_domains=tuple(a.allowed_domain))))
            return 0
        if a.cmd == "calendar-busy":
            with open(a.file, encoding="utf-8-sig") as fh:
                data = _json.load(fh)
            n = calsync.import_busy(conn, data.get("busy", []), members_read=data.get("members", []),
                                    start=a.start, end=a.end, at=datetime.now())
            print(f"{n} busy time(s) for {len(data.get('members', []))} member(s)")
            return 0
        n = calsync.backfill(conn, at=datetime.now())
        if a.apply:
            conn.commit()
            print(f"{n} visit(s) and block(s) queued for Outlook")
        else:
            conn.rollback()
            print(f"PREVIEW: {n} visit(s) and block(s) would be queued; re-run with --apply")
        return 0

    if a.cmd == "add-status":
        from . import setup as _setup
        try:
            done = _setup.add_status(conn, a.board_id, a.name, escalation=a.escalation, closed=a.closed,
                                     portal=a.portal, at=datetime.now(), actor=a.actor)
        except ValueError as exc:
            conn.rollback()
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        for line in done:
            print(("done: " if a.apply else "would: ") + line)
        if not done:
            print(f"nothing to add: {a.board_id} already has a status called {a.name!r}")
        if a.apply:
            conn.commit()
        else:
            conn.rollback()
            print("PREVIEW: nothing written; re-run with --apply")
        return 0

    if a.cmd == "setup-pmc":
        from . import pmc_pack
        try:
            added = pmc_pack.apply(conn, helpdesk=a.helpdesk, procurement=a.procurement, owner=a.owner,
                                   deputy=a.deputy, live=a.live, statuses_only=a.statuses_only,
                                   catalogue=a.with_catalogue,
                                   at=datetime.now(), actor=a.actor)
        except ValueError as exc:
            conn.rollback()
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        for line in added:
            print(line)
        adds = sum(not line.startswith("skip:") for line in added)
        skips = len(added) - adds
        print((f"{adds} thing(s) to add" if adds else "nothing to add: the pack is already there")
              + (f"; {skips} retired or moved row(s) left as this desk has them" if skips else ""))
        if a.apply:
            conn.commit()
            print("applied")
        else:
            conn.rollback()
            print("PREVIEW: nothing written; re-run with --apply")
        return 0

    if a.cmd == "ticket-topics":
        from . import portal_tiles
        since = (datetime.now() - timedelta(days=max(1, a.days))).strftime("%Y-%m-%d")
        for line in portal_tiles.topics(conn, since=since, top=max(1, a.top)):
            print(line)
        conn.rollback()
        return 0

    if a.cmd == "mail-words":
        from . import mail_words
        try:
            lines = mail_words.apply_words(conn, a.board, a.words, apply=a.apply, replace=a.replace,
                                           at=datetime.now(), actor=a.actor)
        except ValueError as exc:
            conn.rollback()
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        for line in lines:
            print(line)
        if a.apply:
            conn.commit()
            print("applied")
        else:
            conn.rollback()
        return 0

    if a.cmd == "ticket-fill":
        from . import board as _board, portal_tiles
        now = datetime.now()
        print("department: never filled in here (Dada, 12 Oct 2026: a department is set only at the door)")
        c = _board.fill_company(conn, apply=a.apply, at=now, actor=a.actor)
        if c["target"] == _board.UNKNOWN_ENTITY:
            print("company: no PMC company on this desk; nothing moved")
        else:
            print(f"company: {c['moved']} ticket(s) under {_board.UNKNOWN_ENTITY} -> {c['target']}")
        bare = portal_tiles.without_item(conn)
        print(f"portal tiles with no Type > Subtype > Item (set in Setup > Portal tiles): {len(bare)}")
        for label in bare:
            print(f"  - {label}")
        if a.apply:
            conn.commit()
            print("applied")
        else:
            conn.rollback()
            print("PREVIEW: nothing written; re-run with --apply")
        return 0

    if a.cmd == "portal-tiles":
        from . import portal_tiles
        try:
            lines = portal_tiles.seed_pmc(conn, helpdesk=a.helpdesk, procurement=a.procurement, apply=a.apply,
                                          at=datetime.now(), actor=a.actor)
        except ValueError as exc:
            conn.rollback()
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        for line in lines:
            print(line)
        if a.apply:
            conn.commit()
            print("applied")
        else:
            conn.rollback()
        return 0

    if a.cmd == "mail-setup":
        from . import intake, outbox
        now = datetime.now()
        b = conn.execute("SELECT board_id, display_name, notify_requester FROM board WHERE board_id = ?",
                         (a.board,)).fetchone()
        if b is None:
            print(f"refused: no board {a.board!r}", file=sys.stderr)
            return 1
        try:
            if a.addresses is not None:
                got = intake.set_addresses(conn, a.board, a.addresses, at=now, actor=a.actor)
                print(f"{b['display_name']}: intake {', '.join(got) or 'none'}")
            if a.email_requester:
                want = 1 if a.email_requester == "on" else 0
                if (b["notify_requester"] or 0) != want:
                    conn.execute("UPDATE board SET notify_requester = ? WHERE board_id = ?", (want, a.board))
                    db.audit(conn, at=now.isoformat(sep=" ", timespec="minutes"), actor=a.actor,
                             action="BOARD_CONFIG", subject_kind="board", subject_id=a.board,
                             detail=f"email the requester: {a.email_requester}")
                print(f"{b['display_name']}: email the requester {a.email_requester}")
            if a.moving_emails:
                n = outbox.set_all_status_mails(conn, a.board, enabled=a.moving_emails == "on", at=now, actor=a.actor)
                print(f"{b['display_name']}: {n} status and picked-up email(s) turned {a.moving_emails}")
        except ValueError as exc:
            conn.rollback()
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        if a.show:
            print(outbox.describe_board(conn, a.board))
        if a.apply:
            conn.commit()
            print("applied")
        else:
            conn.rollback()
            print("PREVIEW: nothing written; re-run with --apply")
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

    if a.cmd == "board-admin":
        from . import setup
        try:
            given = setup.first_admin(conn, a.board_id, a.member, actor="cli", at=datetime.now())
            conn.commit()
        except (LookupError, ValueError) as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        if not given:
            print(f"refused: {a.board_id} already has members; its administrators add more in "
                  "Setup, Members & roles", file=sys.stderr)
            return 1
        print(f"{a.board_id}: {a.member} is its first administrator (audited)")
        return 0

    if a.cmd == "setup-board":
        from . import setup
        try:
            r = setup.apply_starter(conn, a.board_id, actor="cli", at=datetime.now())
            if a.admin:
                if setup.first_admin(conn, a.board_id, a.admin, actor="cli", at=datetime.now()):
                    print(f"{a.board_id}: {a.admin} is its first administrator (audited)")
                else:
                    print(f"{a.board_id}: already has members; --admin ignored", file=sys.stderr)
            conn.commit()
        except (LookupError, ValueError) as exc:
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
        serve(a.database, host=a.host, port=a.port, cert=a.cert, key=a.key)
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
                                               at=datetime.now(), scope=a.scope)
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
