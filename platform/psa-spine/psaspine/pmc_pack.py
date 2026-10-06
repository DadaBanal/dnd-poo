"""The PMC pack: the statuses, Areas, Subtypes and Items that fit Premiere
Medical Center - Nueva Ecija, set on the live boards in one audited step.

Dada, 1 Oct 2026: "add statuses type and subtypes that is fit for pmc". The
desk ships empty on purpose (db.seed_catalogue: a PSA does not arrive with
somebody else's guesses), so this is a separate, named step that Dada asked
for, run by `psaspine setup-pmc` with a preview first.

What it does, and what it never does:
- It ADDS what is missing, by name. It never renames, retires or reorders
  anything already there, and a second run adds nothing.
- The ticket Types stay the board's ITIL kinds (Incident, Service request,
  Problem); what a ward sees as "the type of problem" is the Area and Subtype,
  and the Item says what is wrong or wanted. All of it is editable afterwards
  in Setup > Catalogue, and every status on the board's Statuses tab.
- The systems named are the ones in PMC's record (BizBox HIS and its PIS,
  MMS, FMS and Payroll modules; eClaims; the imaging portal; Microsoft 365;
  RemoteApp; Power BI). No patient detail, no address, no credential.
- Clinical systems carry the clinical flag and a priority floor, so a ward
  that cannot use BizBox is never queued behind a mouse.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

# ------------------------------------------------------------------ statuses
# name, escalation, closed, time entry allowed, shown on the board, portal words
HELPDESK_EXTRA = (
    ("Waiting on Parts", "NO_ESCALATION", 0, 1, 1, "We are waiting for a part to arrive"),
    ("Waiting on BizBox", "NO_ESCALATION", 0, 1, 1, "Raised with the BizBox support team; we will tell you when they answer"),
    ("Awaiting approval", "NO_ESCALATION", 0, 1, 1, "Waiting for an approval"),
    ("On Hold", "NO_ESCALATION", 0, 1, 1, "On hold; we will tell you when it moves"),
)
PROCUREMENT = (
    ("New", "NOT_RESPONDED", 0, 1, 1, "Received - waiting for Procurement to pick it up"),
    ("For Quotation", "RESPONDED", 0, 1, 1, "We are getting quotations from suppliers"),
    ("For Approval", "NO_ESCALATION", 0, 1, 1, "Waiting for approval of the purchase"),
    ("Approved", "RESOLUTION_PLAN", 0, 1, 1, "The purchase is approved"),
    ("PO Raised", "RESOLUTION_PLAN", 0, 1, 1, "A purchase order has been raised"),
    ("Ordered", "RESOLUTION_PLAN", 0, 1, 1, "Ordered from the supplier"),
    ("Delivered", "RESOLUTION_PLAN", 0, 1, 1, "Delivered to the hospital; being checked and received"),
    ("Issued", "RESOLVED", 0, 1, 1, "Issued to you - reply if anything is wrong"),
    (">Cancelled", "RESOLVED", 1, 0, 0, "Cancelled — closed without the work being done"),
    (">Closed", "RESOLVED", 1, 0, 0, "Closed"),
    # SQL01 added these live on 1 Oct 2026 (Dada: "add additional statuses subtype item to the bizbox one")
    ("Waiting on BizBox", "NO_ESCALATION", 0, 1, 1, "Raised with the BizBox support team; we will tell you when they answer"),
    ("For Receiving", "RESOLUTION_PLAN", 0, 1, 1, "Delivered; being received into stock"),
    ("For Payment", "RESOLUTION_PLAN", 0, 1, 1, "Received; the supplier's invoice is with Finance"),
    ("On Hold", "NO_ESCALATION", 0, 1, 1, "On hold; we will tell you when it moves"),
)

# ------------------------------------------------------------------ the catalogue
# Items: name -> (kind, implied impact). FAULT is something broken; REQUEST
# is something wanted.
ITEMS = {
    "Not working": ("FAULT", None),
    "Slow or freezing": ("FAULT", None),
    "Error message": ("FAULT", None),
    "Cannot log in": ("FAULT", None),
    "Down for the whole ward": ("FAULT", "I1"),
    "Wrong data or report": ("FAULT", None),
    "Damaged": ("FAULT", None),
    "New or install": ("REQUEST", None),
    "Move or change": ("REQUEST", None),
    "Access or permission": ("REQUEST", None),
    "Password reset or unlock": ("REQUEST", None),
    "Remove or decommission": ("REQUEST", None),
    "How do I": ("REQUEST", None),
    "Replace": ("REQUEST", None),
    "Purchase": ("REQUEST", None),
    "Quotation": ("REQUEST", None),
    "Repair by supplier": ("REQUEST", None),
    # BizBox procurement verbs (SQL01, 1 Oct 2026)
    "Amend": ("REQUEST", None),
    "Cancel": ("REQUEST", None),
    "Query": ("REQUEST", None),
    "Follow up": ("REQUEST", None),
    "Dispute": ("REQUEST", None),
    "Receive": ("REQUEST", None),
    "Short or wrong delivery": ("FAULT", None),
}
FAULTS = ("Not working", "Slow or freezing", "Error message")
SYSTEM = FAULTS + ("Cannot log in", "Down for the whole ward", "Wrong data or report",
                   "Access or permission", "Password reset or unlock", "How do I")
DEVICE = FAULTS + ("Damaged", "New or install", "Move or change", "Replace", "Remove or decommission")
BUY = ("Purchase", "Quotation", "Repair by supplier")

# Area -> [(subtype, items, clinical, priority floor for its faults)]
HELPDESK = {
    "Hospital systems (BizBox)": [
        ("BizBox HIS", SYSTEM, True, "P2"),
        ("BizBox PIS (PhilHealth)", SYSTEM, True, "P2"),
        ("PhilHealth eClaims", SYSTEM, True, "P2"),
        ("BizBox MMS (inventory)", SYSTEM, False, None),
        ("BizBox FMS (finance)", SYSTEM, False, None),
        ("Payroll", SYSTEM, False, None),
        ("Imaging portal", SYSTEM, True, "P2"),
        ("Power BI reports", SYSTEM, False, None),
    ],
    "Computers and devices": [
        ("Desktop or NUC computer", DEVICE, False, None),
        ("Laptop", DEVICE, False, None),
        ("Monitor", DEVICE, False, None),
        ("Printer", DEVICE + ("How do I",), False, None),
        ("Scanner", DEVICE, False, None),
        ("Label or barcode printer", DEVICE, False, None),
        ("Keyboard, mouse or cable", DEVICE, False, None),
        ("Phone or extension", DEVICE, False, None),
    ],
    "Accounts and email": [
        ("Windows account", ("Cannot log in", "Password reset or unlock", "New or install",
                             "Access or permission", "Remove or decommission"), False, None),
        ("Email and Teams", FAULTS + ("Cannot log in", "New or install", "Access or permission", "How do I"), False, None),
        ("Shared mailbox or folder", ("Access or permission", "New or install", "Not working"), False, None),
        ("RemoteApp", FAULTS + ("Cannot log in", "Access or permission"), False, None),
    ],
    "Network and internet": [
        ("Wi-Fi", FAULTS + ("Down for the whole ward", "Access or permission"), False, None),
        ("Network point or cable", FAULTS + ("New or install", "Move or change", "Damaged"), False, None),
        ("Internet", FAULTS + ("Down for the whole ward",), False, None),
    ],
    "CCTV and building systems": [
        ("CCTV", FAULTS + ("Damaged", "New or install", "Move or change", "Access or permission"), False, None),
    ],
}
PROCURE = {
    "Purchasing": [
        ("IT equipment", BUY, False, None),
        ("Software or licence", ("Purchase", "Quotation"), False, None),
        ("Consumables (toner, ink, cables)", ("Purchase",), False, None),
        ("Medical supplies", ("Purchase", "Quotation"), False, None),
        ("Furniture and fixtures", ("Purchase", "Quotation", "Repair by supplier"), False, None),
        ("Services and repairs", ("Repair by supplier", "Quotation"), False, None),
    ],
    "BizBox procurement": [
        ("Purchase order", ("New or install", "Amend", "Cancel", "Query", "Follow up"), False, None),
        ("Supplier invoice", ("New or install", "Dispute", "Query", "Follow up"), False, None),
        ("Receiving / delivery", ("Receive", "Short or wrong delivery", "Damaged", "Query"), False, None),
        ("Supplier / vendor", ("New or install", "Amend", "Query"), False, None),
        ("Product / item", ("New or install", "Amend", "Query"), False, None),
        ("Agreement / contract", ("New or install", "Amend", "Query"), False, None),
    ],
}


def _find(conn, table: str, key: str, name: str, extra: str = "", args=()):
    row = conn.execute(f"SELECT {key} FROM {table} WHERE LOWER(display_name) = LOWER(?){extra}",
                       (name, *args)).fetchone()
    return row[0] if row else None


def _add_statuses(conn, board_id: str, statuses, report: list[str]) -> None:
    from .setup import status_id
    have = {r["name"].lower(): r for r in conn.execute(
        "SELECT name, is_default FROM board_status WHERE board_id = ?", (board_id,))}
    order = (conn.execute("SELECT MAX(sort_order) FROM board_status WHERE board_id = ?", (board_id,)).fetchone()[0] or 0)
    has_default = any(r["is_default"] for r in have.values())
    has_closed = conn.execute("SELECT 1 FROM board_status WHERE board_id = ? AND is_closed = 1 AND inactive = 0",
                              (board_id,)).fetchone() is not None
    for name, esc, closed, effort, shown, portal in statuses:
        if name.lower() in have or name.lstrip(">").lower() in {n.lstrip(">") for n in have}:
            continue
        if closed and has_closed and name.lstrip(">").lower() == "closed":
            continue                              # the board's own closing status stays; >Cancelled is added
        order += 10
        default = 1 if (not has_default and esc == "NOT_RESPONDED") else 0
        has_default = has_default or bool(default)
        conn.execute(
            "INSERT INTO board_status (board_status_id, board_id, name, customer_description, escalation_status,"
            " is_default, is_closed, time_entry_allowed, display_on_board, sort_order)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (status_id(board_id, name), board_id, name, portal, esc, default, closed, effort, shown, order))
        report.append(f"status {board_id}: {name.lstrip('>')}")


def _add_catalogue(conn, board_id: str, tree: dict, report: list[str], *, at: datetime, actor: str) -> None:
    """Add the pack's Areas, Subtypes, Items and pairs that this desk has never
    had. A row this desk has retired, or a Subtype it has moved to another
    Area, is the desk's decision and is never brought back (SQL01, 6 Oct 2026:
    the 2 Oct restructure retired "Hospital systems (BizBox)" and moved its
    Subtypes; the pack would have rebuilt all 80 pairs). Each such row is
    listed as a skip, so the preview says why it is not added."""
    from . import catalogue as cat
    for area, subtypes in tree.items():
        row = conn.execute("SELECT family_id, COALESCE(inactive, 0) AS inactive FROM service_family"
                           " WHERE LOWER(display_name) = LOWER(?)", (area,)).fetchone()
        if row is not None and row["inactive"]:
            report.append(f"skip: area {area} is retired on this desk")
            continue
        fid = row["family_id"] if row else None
        if fid is None:
            fid = cat.add_area(conn, area, at=at, actor=actor)
            report.append(f"area: {area}")
        for sub, items, clinical, floor in subtypes:
            crow = conn.execute("SELECT component_id, is_draft FROM service_component"
                                " WHERE LOWER(display_name) = LOWER(?) AND family_id = ?", (sub, fid)).fetchone()
            if crow is not None and crow["is_draft"]:
                report.append(f"skip: subtype {area} > {sub} is retired on this desk")
                continue
            if crow is None and conn.execute("SELECT 1 FROM service_component WHERE LOWER(display_name) = LOWER(?)"
                                             " AND family_id <> ?", (sub, fid)).fetchone():
                report.append(f"skip: subtype {sub} sits under another area on this desk")
                continue
            cid = crow["component_id"] if crow else None
            if cid is None:
                cid = cat.add_subtype(conn, fid, sub, at=at, actor=actor)
                report.append(f"subtype: {area} > {sub}")
            for item in items:
                arow = conn.execute("SELECT action_id, COALESCE(inactive, 0) AS inactive FROM service_action"
                                    " WHERE LOWER(display_name) = LOWER(?)", (item,)).fetchone()
                if arow is not None and arow["inactive"]:
                    report.append(f"skip: item {item} is retired on this desk")
                    continue
                aid = arow["action_id"] if arow else None
                if aid is None:
                    kind, impact = ITEMS[item]
                    aid = cat.add_item(conn, item, kind=kind, implies_impact=impact, at=at, actor=actor)
                    report.append(f"item: {item}")
                if conn.execute("SELECT 1 FROM catalogue_item WHERE component_id = ? AND action_id = ?",
                                (cid, aid)).fetchone():
                    continue                      # there already, retired or not
                fault = ITEMS[item][0] == "FAULT"
                cat.associate(conn, cid, aid, board_id, clinical_impact=clinical and fault,
                              min_priority=floor if fault else None, at=at, actor=actor)
                report.append(f"pair: {sub} > {item} -> {board_id}")


def apply(conn: sqlite3.Connection, *, helpdesk: str = "IT_HELP", procurement: str | None = None,
          owner: str | None = None, deputy: str | None = None, live: bool = False,
          catalogue: bool = False, statuses_only: bool = False, at: datetime, actor: str) -> list[str]:
    """Add the PMC statuses to the help desk and (when named) the procurement
    board, and with catalogue=True the pack's catalogue too. The catalogue is
    asked for by name because a live desk reshapes its own (2 Oct restructure);
    statuses_only is kept for the older command line and wins. With live, the
    procurement board gets its owner and deputy and goes live. Returns one line
    per thing added, and one per retired or moved row it left alone ("skip:");
    the caller commits or rolls back."""
    from . import db
    report: list[str] = []
    for b in (helpdesk, procurement):
        if b and conn.execute("SELECT 1 FROM board WHERE board_id = ?", (b,)).fetchone() is None:
            raise ValueError(f"no board {b!r}")
    _add_statuses(conn, helpdesk, HELPDESK_EXTRA, report)
    with_catalogue = catalogue and not statuses_only
    if with_catalogue:
        _add_catalogue(conn, helpdesk, HELPDESK, report, at=at, actor=actor)
    if procurement:
        _add_statuses(conn, procurement, PROCUREMENT, report)
        if with_catalogue:
            _add_catalogue(conn, procurement, PROCURE, report, at=at, actor=actor)
        if live:
            if not (owner and deputy):
                raise ValueError("a live board needs an owner and a deputy")
            conn.execute("UPDATE board SET owner = ?, deputy = ?, is_live = 1 WHERE board_id = ?",
                         (owner, deputy, procurement))
            report.append(f"board {procurement}: live, owner {owner}, deputy {deputy}")
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="PMC_PACK",
             subject_kind="board", subject_id=helpdesk,
             detail=f"{sum(not r.startswith('skip:') for r in report)} added"
                    + (f"; procurement {procurement}" if procurement else ""))
    return report
