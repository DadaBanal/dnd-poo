"""Setting a board up, the way a Dada PSA service board is set up.

A PSA does not arrive with boards in it (Dada's direction, 9 Sep 2026 — see
`db.seed_catalogue`), so nothing here runs on `init`. A board administrator
applies it to a board they have created, from the board's setup screen or with
`psaspine setup-board`, and then edits every value it wrote. That is how
the reference PSA does it too: the Service Board setup table is where the statuses,
the SLA and the calendar are chosen, per board, by a person.

What it writes is a STARTER, not a decision:

- **Statuses** in Dada PSA's shape — each declares the SLA milestone it
  represents (`escalationStatus`), whether it closes the ticket, whether time
  may be entered in it, and what the requester is shown instead of the internal
  name. The names follow the reference PSA's common convention (New, In Progress,
  Waiting…, Resolved, >Closed) **[INFERRED — its own documentation is
  behind its University login and was not read]**.
- **Two calendars**: all hours, and a Monday-to-Saturday business day.
- **Three clocks per priority** — respond, resolution plan, resolve — the three
  timestamps the reference PSA stores on a ticket. Every target is written with
  `enforced = 0`: measured, reported, never promised. The minutes are
  placeholders for the Service Manager to replace **[INFERRED]**; they are the
  same shape as `seed/sample/sla_targets.csv` and nobody at PMC has signed them.

Re-applying is safe: it adds what is missing and never overwrites what an
administrator has already changed.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime

from . import db

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

CALENDARS = (
    ("ALL_HOURS", "All hours (24x7)", [("00:00", "24:00")] * 7),
    ("BUSINESS", "Business day (Mon-Sat 08:00-17:00)",
     [("08:00", "17:00")] * 6 + [(None, None)]),
)

# Dada, 6 Oct 2026: "add a >cancelled status". The '>' is the desk's mark of a
# closed status, as on >Closed: a request withdrawn or no longer needed ends
# here, closed, with no survey asked (survey.pending) and no time booked.
CANCELLED = ">Cancelled"
CANCELLED_WORDS = "Cancelled — closed without the work being done"

# name, escalation, default, closed, time entry allowed, on board, portal wording
STARTER_STATUSES = (
    ("New", "NOT_RESPONDED", 1, 0, 1, 1, "Received — waiting for someone to pick it up"),
    ("Assigned", "NOT_RESPONDED", 0, 0, 1, 1, "Assigned to a technician"),
    ("In Progress", "RESPONDED", 0, 0, 1, 1, "Someone is working on it"),
    ("Scheduled", "RESOLUTION_PLAN", 0, 0, 1, 1, "A fix is planned — we will tell you when"),
    ("Waiting on Requester", "NO_ESCALATION", 0, 0, 1, 1, "We need something from you"),
    ("Waiting on Vendor", "NO_ESCALATION", 0, 0, 1, 1, "Waiting on a supplier"),
    ("Awaiting approval", "NO_ESCALATION", 0, 0, 1, 1, "Waiting for an approval"),
    # Dada, 6 Oct 2026: "can u add a onhold status". Open, and like the
    # Waiting statuses it holds the SLA clocks (NO_ESCALATION).
    ("On Hold", "NO_ESCALATION", 0, 0, 1, 1, "On hold; we will tell you when it moves"),
    ("Resolved", "RESOLVED", 0, 0, 1, 1, "We think this is fixed — reply if it is not"),
    (">Cancelled", "RESOLVED", 0, 1, 0, 0, CANCELLED_WORDS),
    (">Closed", "RESOLVED", 0, 1, 0, 0, "Closed"),
)

# A change board's lifecycle (ITIL 4 change enablement; Dada PSA's Change
# Approvals module uses the same shape: pending approval, approved, scheduled,
# completed, rejected). The last column is requires_approval: a NORMAL change
# enters those statuses only once approved (itil.check_status_move).
CHANGE_STATUSES = (
    ("New", "NOT_RESPONDED", 1, 0, 1, 1, "Received - being assessed", 0),
    ("Assessing", "RESPONDED", 0, 0, 1, 1, "Being assessed for risk and impact", 0),
    ("Awaiting Approval", "NO_ESCALATION", 0, 0, 1, 1, "Waiting for approval", 0),
    ("Approved", "RESOLUTION_PLAN", 0, 0, 1, 1, "Approved - being scheduled", 1),
    ("Scheduled", "RESOLUTION_PLAN", 0, 0, 1, 1, "Scheduled - we will tell you the date", 1),
    ("Implementing", "RESOLUTION_PLAN", 0, 0, 1, 1, "Being carried out", 1),
    ("Implemented", "RESOLVED", 0, 0, 1, 1, "Done - reply if anything is wrong", 1),
    ("Backed Out", "RESOLVED", 0, 0, 1, 1, "Undone - it did not work as planned", 0),
    ("Declined", "RESOLVED", 0, 0, 0, 1, "Not approved", 0),
    (">Cancelled", "RESOLVED", 0, 1, 0, 0, CANCELLED_WORDS, 0),
    (">Closed", "RESOLVED", 0, 1, 0, 0, "Closed", 0),
)
# A project board. The reference PSA: "SLA timers do not run on project tickets"
# (VERIFIED 23 Sep 2026, docs.connectwise.com/ConnectWise_Documentation/090/020/
# 140/010/020), so neither profile below gets SLA targets.
PROJECT_STATUSES = (
    ("New", "NOT_RESPONDED", 1, 0, 1, 1, "Received", 0),
    ("Planning", "RESPONDED", 0, 0, 1, 1, "Being planned", 0),
    ("In Progress", "RESOLUTION_PLAN", 0, 0, 1, 1, "Under way", 0),
    ("On Hold", "NO_ESCALATION", 0, 0, 1, 1, "On hold", 0),
    ("Completed", "RESOLVED", 0, 0, 1, 1, "Completed", 0),
    (">Cancelled", "RESOLVED", 0, 1, 0, 0, CANCELLED_WORDS, 0),
    (">Closed", "RESOLVED", 0, 1, 0, 0, "Closed", 0),
)
PROFILE_STATUSES = {"SERVICE": tuple(s + (0,) for s in STARTER_STATUSES),
                    "CHANGE": CHANGE_STATUSES, "PROJECT": PROJECT_STATUSES}

# priority -> (respond, resolution plan, resolve), in minutes. Placeholders.
STARTER_TARGETS = {
    "P1": (15, 60, 240),
    "P2": (60, 240, 480),
    "P3": (240, 480, 1440),
    "P4": (480, 1440, 4320),
}
CLOCKS = ("RESPOND", "RESOLUTION_PLAN", "RESOLVE")
STARTER_NOTE = "starter placeholder: set by the Service Manager"


def status_id(board_id: str, name: str) -> str:
    return f"{board_id}.{re.sub(r'[^A-Z0-9]+', '_', name.upper()).strip('_') or 'STATUS'}"


def is_cancelled_name(name: str | None) -> bool:
    return (name or "").lstrip(">").strip().lower() == "cancelled"


def ensure_cancelled(conn: sqlite3.Connection, board_id: str, *, at: datetime, actor: str,
                     apply: bool = False) -> list[str]:
    """Give a board the closed >Cancelled status (6 Oct 2026). Returns what it
    did, or with apply=False what it would do; the caller commits.

    A board that already has a closed status called Cancelled is left alone.
    A board with an OPEN status called Cancelled (Procurement had one, from
    the 1 Oct pack) gets the closed one beside it; every ticket sitting in the
    open one is moved across through change_status, so it is closed the way
    any close is (clocks stopped, closed_at set, the event written), and the
    open one is then retired and renamed so the two cannot be confused.
    """
    from . import board as _board
    rows = conn.execute("SELECT board_status_id, name, is_closed, inactive FROM board_status"
                        " WHERE board_id = ?", (board_id,)).fetchall()
    if any(is_cancelled_name(r["name"]) and r["is_closed"] and not r["inactive"] for r in rows):
        return []
    taken = {r["board_status_id"] for r in rows}
    sid = status_id(board_id, CANCELLED)
    if sid in taken:
        sid = status_id(board_id, "CANCELLED_CLOSED")
    old = [r for r in rows if is_cancelled_name(r["name"]) and not r["is_closed"] and not r["inactive"]]
    stuck = []
    for r in old:
        stuck += [x[0] for x in conn.execute(
            "SELECT work_item_id FROM ticket WHERE board_status_id = ? AND closed_at IS NULL"
            " ORDER BY work_item_id", (r["board_status_id"],))]
    lines = [f"{board_id}: add {CANCELLED} (closed)"]
    for r in old:
        lines.append(f"{board_id}: retire the open status '{r['name']}' as 'Cancelled (open, retired)'")
    if stuck:
        lines.append(f"{board_id}: move {len(stuck)} ticket(s) from the open Cancelled to {CANCELLED}, which"
                     f" closes them: {', '.join(stuck[:20])}{' …' if len(stuck) > 20 else ''}")
    if not apply:
        return lines
    order = (conn.execute("SELECT MAX(sort_order) FROM board_status WHERE board_id = ? AND is_closed = 0",
                          (board_id,)).fetchone()[0] or 0) + 5
    conn.execute(
        "INSERT INTO board_status (board_status_id, board_id, name, customer_description, escalation_status,"
        " is_default, is_closed, time_entry_allowed, display_on_board, sort_order)"
        " VALUES (?,?,?,?, 'RESOLVED', 0, 1, 0, 0, ?)",
        (sid, board_id, CANCELLED, CANCELLED_WORDS, order))
    for wid in stuck:
        _board.change_status(conn, wid, sid, at=at, actor=actor)
    for r in old:
        conn.execute("UPDATE board_status SET inactive = 1, name = 'Cancelled (open, retired)'"
                     " WHERE board_status_id = ?", (r["board_status_id"],))
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="BOARD_SETUP",
             subject_kind="board", subject_id=board_id,
             detail=f"{CANCELLED} added; {len(stuck)} ticket(s) moved from the open Cancelled")
    return lines


ESCALATIONS = ("NOT_RESPONDED", "RESPONDED", "RESOLUTION_PLAN", "RESOLVED", "NO_ESCALATION")


def add_status(conn: sqlite3.Connection, board_id: str, name: str, *, escalation: str = "NO_ESCALATION",
               closed: bool = False, portal: str | None = None, at: datetime, actor: str) -> list[str]:
    """One status on one board and nothing else (SQL01, 6 Oct 2026: On Hold for
    PMO Helpdesk without the PMC pack, which would re-add the catalogue rows
    the 2 Oct Type restructure retired). Returns what it did, or [] when the
    board already has a status of that name; the caller commits or rolls back.

    An open status goes in after the board's other open ones, so the closed
    ones stay last on the list; it allows time and shows on the board."""
    if conn.execute("SELECT 1 FROM board WHERE board_id = ?", (board_id,)).fetchone() is None:
        raise ValueError(f"no board {board_id!r}")
    name = " ".join((name or "").split())[:60]
    if not name:
        raise ValueError("a status needs a name")
    if escalation not in ESCALATIONS:
        raise ValueError(f"escalation is one of {', '.join(ESCALATIONS)}")
    bare = name.lstrip(">").strip().lower()
    for r in conn.execute("SELECT name FROM board_status WHERE board_id = ?", (board_id,)):
        if r[0].lstrip(">").strip().lower() == bare:
            return []
    sid = status_id(board_id, name)
    if conn.execute("SELECT 1 FROM board_status WHERE board_status_id = ?", (sid,)).fetchone():
        sid = status_id(board_id, name + "_2")
    order = (conn.execute("SELECT MAX(sort_order) FROM board_status WHERE board_id = ? AND is_closed = ?",
                          (board_id, 1 if closed else 0)).fetchone()[0] or 0) + 5
    if not closed and escalation != "RESOLVED":
        # Before Resolved: a status that is still work reads above the one that ends it.
        first = conn.execute("SELECT MIN(sort_order) FROM board_status WHERE board_id = ? AND is_closed = 0"
                             " AND escalation_status = 'RESOLVED'", (board_id,)).fetchone()[0]
        if first is not None:
            order = first - 5
    conn.execute(
        "INSERT INTO board_status (board_status_id, board_id, name, customer_description, escalation_status,"
        " is_default, is_closed, time_entry_allowed, display_on_board, sort_order) VALUES (?,?,?,?,?,0,?,?,?,?)",
        (sid, board_id, name, portal, escalation, 1 if closed else 0, 0 if closed else 1, 0 if closed else 1, order))
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor, action="BOARD_SETUP",
             subject_kind="board", subject_id=board_id, detail=f"status added: {name} ({escalation})")
    return [f"{board_id}: add status '{name}' ({escalation}{', closed' if closed else ''}) as {sid}"]


def ensure_calendars(conn: sqlite3.Connection) -> None:
    for cal_id, name, week in CALENDARS:
        cols = ", ".join(f"{d}_start, {d}_end" for d in DAYS)
        values = [v for pair in week for v in pair]
        conn.execute(
            f"INSERT OR IGNORE INTO calendar (calendar_id, name, {cols})"
            f" VALUES (?,?,{','.join('?' * 14)})", [cal_id, name, *values])


def apply_starter(conn: sqlite3.Connection, board_id: str, *, actor: str,
                  at: datetime, profile: str | None = None) -> dict:
    from . import board as _board
    _board.ensure_time_vocabulary(conn)
    return _apply_starter(conn, board_id, actor=actor, at=at, profile=profile)


def _apply_starter(conn: sqlite3.Connection, board_id: str, *, actor: str,
                   at: datetime, profile: str | None = None) -> dict:
    """Give a board the statuses, calendar and SLA targets it needs to run.

    `profile` is SERVICE (the default), CHANGE or PROJECT (itil.PROFILES): which
    record types the board takes and which starter statuses it gets. Only a
    service board gets SLA targets. Record types are written only if the board
    has none yet.

    Adds only what is missing. A status an administrator renamed, a target they
    changed, a calendar they chose: all left exactly as they are.
    """
    from . import itil
    if conn.execute("SELECT 1 FROM board WHERE board_id = ?", (board_id,)).fetchone() is None:
        raise LookupError(f"no board {board_id!r}")
    profile = profile or itil.profile_of(conn, board_id) or "SERVICE"
    if profile not in itil.PROFILES:
        raise ValueError(f"unknown board kind {profile!r}")
    conn.execute("UPDATE board SET kind = ? WHERE board_id = ? AND kind IS NULL",
                 (profile, board_id))
    ensure_calendars(conn)
    types_set = False
    if not itil.boards_types(conn, board_id):
        itil.set_board_types(conn, board_id, itil.PROFILES[profile])
        types_set = True

    has_default = conn.execute(
        "SELECT 1 FROM board_status WHERE board_id = ? AND is_default = 1 AND inactive = 0",
        (board_id,)).fetchone() is not None
    added_statuses = 0
    for order, (name, esc, default, closed, effort, shown, portal, approval) in enumerate(
            PROFILE_STATUSES[profile], start=1):
        cur = conn.execute(
            "INSERT OR IGNORE INTO board_status (board_status_id, board_id, name,"
            " customer_description, escalation_status, is_default, is_closed,"
            " time_entry_allowed, display_on_board, sort_order, requires_approval)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (status_id(board_id, name), board_id, name, portal, esc,
             0 if has_default else default, closed, effort, shown, order * 10,
             approval or None))
        added_statuses += cur.rowcount

    added_targets = 0
    for priority, minutes in (STARTER_TARGETS.items() if profile == "SERVICE" else ()):
        for clock, target in zip(CLOCKS, minutes):
            cur = conn.execute(
                "INSERT OR IGNORE INTO sla_target (board_id, priority, clock,"
                " target_minutes, calendar, enforced, note)"
                " VALUES (?,?,?,?, 'CLINICAL_24x7', 0, ?)",
                (board_id, priority, clock, target, STARTER_NOTE))
            added_targets += cur.rowcount

    cur = conn.execute("UPDATE board SET calendar_id = 'ALL_HOURS'"
                       " WHERE board_id = ? AND calendar_id IS NULL", (board_id,))
    calendar_set = bool(cur.rowcount)

    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor,
             action="BOARD_SETUP", subject_kind="board", subject_id=board_id,
             detail=f"{profile.lower()} starter applied: {added_statuses} statuses, "
                    f"{added_targets} SLA targets{', calendar ALL_HOURS' if calendar_set else ''}"
                    f"{', record types ' + '/'.join(itil.PROFILES[profile]) if types_set else ''}")
    return {"board_id": board_id, "statuses": added_statuses, "profile": profile,
            "targets": added_targets, "calendar_set": calendar_set}


def readiness(conn: sqlite3.Connection, board_id: str) -> list[str]:
    """What this board still lacks before a ticket on it can run, in words.

    Empty means ready: a default status to land in, a closed status to finish
    in, and a calendar for the clocks. Targets are not required — a board with
    no targets runs, it simply measures nothing, and the board view says so.
    """
    missing = []
    q = lambda sql: conn.execute(sql, (board_id,)).fetchone() is not None  # noqa: E731
    if not q("SELECT 1 FROM board_status WHERE board_id = ? AND is_default = 1 AND inactive = 0"):
        missing.append("a default status for new tickets")
    if not q("SELECT 1 FROM board_status WHERE board_id = ? AND is_closed = 1 AND inactive = 0"):
        missing.append("a closed status")
    if not q("SELECT 1 FROM board WHERE board_id = ? AND calendar_id IS NOT NULL"):
        missing.append("a calendar for the SLA clocks")
    return missing


# ------------------------------------------------------------------ many boards

def board_id_for(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")[:40] or "BOARD"


def first_admin(conn: sqlite3.Connection, board_id: str, member: str, *, actor: str,
                at: datetime) -> bool:
    """Make `member` the ADMIN of a board that has no members yet.

    A board created through Setup gets its creator as administrator; a board
    the seed created (IT_HELP, UNROUTED) has nobody, and board access is
    membership only, never the sysadmin flag. So the first administrator of a
    seeded board is given here, by the CLI on the server or by a sysadmin in
    Setup, and only while the board has no members: after that, its own
    administrators manage its members. Audited as BOARD_MEMBER. Returns False
    when the board already has members."""
    if conn.execute("SELECT 1 FROM board WHERE board_id = ?", (board_id,)).fetchone() is None:
        raise LookupError(f"no board {board_id!r}")
    member = (member or "").strip()
    if not member:
        raise ValueError("a member name is needed")
    if conn.execute("SELECT 1 FROM board_member WHERE board_id = ? LIMIT 1", (board_id,)).fetchone():
        return False
    conn.execute("INSERT INTO board_member (board_id, member, access) VALUES (?,?,'ADMIN')",
                 (board_id, member))
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor,
             action="BOARD_MEMBER", subject_kind="board", subject_id=board_id,
             detail=f"first administrator {member} (the board had no members)")
    return True


def create_board(conn: sqlite3.Connection, *, display_name: str, fulfiller_group: str,
                 creator: str, at: datetime, board_id: str | None = None,
                 restricted: bool = False, closed_loop_required: bool = False,
                 description: str | None = None, copy_from: str | None = "starter",
                 profile: str = "SERVICE") -> str:
    """A new board, the way Dada PSA adds one to the Service Board setup table.

    `copy_from` is "starter" (the starter statuses, calendar and targets), the id
    of an existing board (its statuses, calendar and targets are copied, so a
    second board runs exactly like the first), or None (an empty board). The
    creator becomes its administrator. It is created not live: a board is live
    when it has an owner and a deputy, which the CHECK in 004 insists on.
    """
    display_name = (display_name or "").strip()
    if not display_name:
        raise ValueError("a board needs a name")
    bid = board_id_for(board_id or display_name)
    if conn.execute("SELECT 1 FROM board WHERE board_id = ?", (bid,)).fetchone():
        raise ValueError(f"a board {bid!r} already exists")
    conn.execute(
        "INSERT INTO board (board_id, display_name, phase, fulfiller_group, restricted,"
        " is_live, is_unrouted, closed_loop_required, description)"
        " VALUES (?,?, '2', ?, ?, 0, 0, ?, ?)",
        (bid, display_name, (fulfiller_group or "").strip() or "Unassigned",
         1 if restricted else 0, 1 if closed_loop_required else 0, description))
    conn.execute("INSERT INTO board_member (board_id, member, access) VALUES (?,?,'ADMIN')",
                 (bid, creator))
    if copy_from == "starter":
        apply_starter(conn, bid, actor=creator, at=at, profile=profile)
    elif copy_from:
        copy_setup(conn, copy_from, bid)
    conn.execute("UPDATE board SET kind = COALESCE(kind, ?) WHERE board_id = ?", (
        conn.execute("SELECT kind FROM board WHERE board_id = ?", (copy_from,)).fetchone()[0]
        if copy_from and copy_from != "starter" else profile, bid))
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=creator,
             action="BOARD_CREATE", subject_kind="board", subject_id=bid,
             detail=f"created {display_name!r} from {copy_from or 'nothing'}")
    return bid


def copy_setup(conn: sqlite3.Connection, from_board: str, to_board: str) -> None:
    """Copy statuses (re-keyed to the new board), SLA targets and the calendar."""
    if conn.execute("SELECT 1 FROM board WHERE board_id = ?", (from_board,)).fetchone() is None:
        raise LookupError(f"no board {from_board!r} to copy from")
    for s in conn.execute("SELECT * FROM board_status WHERE board_id = ?", (from_board,)).fetchall():
        conn.execute(
            "INSERT OR IGNORE INTO board_status (board_status_id, board_id, name,"
            " customer_description, escalation_status, is_default, is_closed,"
            " time_entry_allowed, display_on_board, sort_order, inactive, requires_approval)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (status_id(to_board, s["name"]), to_board, s["name"], s["customer_description"],
             s["escalation_status"], s["is_default"], s["is_closed"], s["time_entry_allowed"],
             s["display_on_board"], s["sort_order"], s["inactive"], s["requires_approval"]))
    # INSERT ... SELECT ... WHERE NOT EXISTS rather than INSERT OR IGNORE: the
    # same rows on both stores, in words both dialects run.
    conn.execute("INSERT INTO board_record_type (board_id, record_type, is_default)"
                 " SELECT ?, f.record_type, f.is_default FROM board_record_type f WHERE f.board_id = ?"
                 " AND NOT EXISTS (SELECT 1 FROM board_record_type x WHERE x.board_id = ?"
                 " AND x.record_type = f.record_type)",
                 (to_board, from_board, to_board))
    conn.execute(
        "INSERT INTO sla_target_type (board_id, record_type, priority, clock,"
        " target_minutes, calendar, attainment_percent, enforced, note)"
        " SELECT ?, f.record_type, f.priority, f.clock, f.target_minutes, f.calendar, f.attainment_percent,"
        " 0, 'copied from ' || f.board_id FROM sla_target_type f WHERE f.board_id = ?"
        " AND NOT EXISTS (SELECT 1 FROM sla_target_type x WHERE x.board_id = ? AND x.record_type = f.record_type"
        " AND x.priority = f.priority AND x.clock = f.clock)",
        (to_board, from_board, to_board))
    conn.execute(
        "INSERT INTO sla_target (board_id, priority, clock, target_minutes, calendar,"
        " attainment_percent, enforced, note) SELECT ?, f.priority, f.clock, f.target_minutes, f.calendar,"
        " f.attainment_percent, 0, 'copied from ' || f.board_id FROM sla_target f WHERE f.board_id = ?"
        " AND NOT EXISTS (SELECT 1 FROM sla_target x WHERE x.board_id = ? AND x.priority = f.priority"
        " AND x.clock = f.clock)",
        (to_board, from_board, to_board))
    conn.execute("UPDATE board SET calendar_id = (SELECT calendar_id FROM board WHERE board_id = ?)"
                 " WHERE board_id = ? AND calendar_id IS NULL", (from_board, to_board))


# ---------------------------------------------------- the Dada PSA template

def _sample(name: str) -> list[dict]:
    import csv
    with (db.SEED_DIR / "sample" / name).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def apply_template(conn: sqlite3.Connection, *, actor: str, at: datetime) -> dict:
    """Dada's design, on the ITIL model (direction of 23 Sep 2026):

    - **IT Help (IT_HELP) is the service board** and takes incidents, service
      requests, problems and events: ITIL's service desk is the one front door
      for incidents and requests, and the reference PSA's own ITIL example puts those
      four as Types on one board (schema/022). No Help/Request split.
    - **IT Change (IT_CHANGE)**, created if missing: changes, with the change
      lifecycle and approval gate (setup.CHANGE_STATUSES, itil.check_status_move).
    - **IT Projects (IT_PROJECTS)**, created if missing: projects, no SLA clocks.
    - Types, subtypes and item verbs are loaded whole. A catalogue item is loaded
      only when its default board exists; the rest are counted and wait for the
      board (Biomedical, Facilities, ...) to be created, then load on a re-run.
    - SLA targets from the sample replace starter placeholders. The old Request
      board's numbers become service-request targets on IT Help
      (sla_targets_by_type.csv), so merging the boards did not merge the SLAs.
      Every one is enforced = 0.

    Which record types each board takes is editable afterwards on its Setup
    page, so Dada's other phrasing (changes on every service board) is a tick.
    Re-running adds only what is missing and never overwrites.
    """
    created = []
    for bid, name, profile, desc in (
            ("IT_CHANGE", "IT Change", "CHANGE",
             "Changes to PMC's systems: assessed, approved by a change authority, "
             "scheduled, implemented or backed out."),
            ("IT_PROJECTS", "IT Projects", "PROJECT",
             "Projects: planned work with a start and an end. No SLA clocks.")):
        if conn.execute("SELECT 1 FROM board WHERE board_id = ?", (bid,)).fetchone() is None:
            create_board(conn, board_id=bid, display_name=name, profile=profile,
                         fulfiller_group="Dada IT + on-site Windows team", creator=actor,
                         at=at, description=desc, copy_from="starter")
            created.append(bid)
    for bid in ("IT_HELP",):
        if conn.execute("SELECT 1 FROM board WHERE board_id = ?", (bid,)).fetchone() and \
                not conn.execute("SELECT 1 FROM board_status WHERE board_id = ?", (bid,)).fetchone():
            apply_starter(conn, bid, actor=actor, at=at, profile="SERVICE")

    def blank(v):
        return v if (v or "").strip() else None

    for r in _sample("service_families.csv"):
        conn.execute("INSERT OR IGNORE INTO service_family (family_id, display_name, raw_name, note)"
                     " VALUES (?,?,?,?)", (r["family_id"], r["display_name"], blank(r["raw_name"]),
                                           blank(r["note"])))
    for r in _sample("service_components.csv"):
        conn.execute("INSERT OR IGNORE INTO service_component (component_id, family_id, display_name,"
                     " raw_name, is_draft, note) VALUES (?,?,?,?,?,?)",
                     (r["component_id"], r["family_id"], r["display_name"], blank(r["raw_name"]),
                      int(r["is_draft"]), blank(r["note"])))
    for r in _sample("service_actions.csv"):
        conn.execute("INSERT OR IGNORE INTO service_action (action_id, display_name, raw_name, kind,"
                     " implies_impact, note) VALUES (?,?,?,?,?,?)",
                     (r["action_id"], r["display_name"], blank(r["raw_name"]), r["kind"],
                      blank(r["implies_impact"]), blank(r["note"])))
    boards = {r[0] for r in conn.execute("SELECT board_id FROM board")}
    loaded, waiting = 0, {}
    for r in _sample("catalogue_items.csv"):
        if r["default_board_id"] not in boards:
            waiting[r["default_board_id"]] = waiting.get(r["default_board_id"], 0) + 1
            continue
        cur = conn.execute(
            "INSERT OR IGNORE INTO catalogue_item (catalogue_item_id, component_id, action_id,"
            " default_board_id, default_scope_item_id, default_contract_basis, clinical_impact,"
            " min_priority, restricted, is_draft, note) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (r["catalogue_item_id"], r["component_id"], r["action_id"], r["default_board_id"],
             blank(r["default_scope_item_id"]), r["default_contract_basis"],
             int(r["clinical_impact"]), blank(r["min_priority"]), int(r["restricted"]),
             int(r["is_draft"]), blank(r["note"])))
        loaded += cur.rowcount
    targets = 0
    sample_targets = [r for r in _sample("sla_targets.csv") if r["board_id"] in boards]
    # The starter's numbers are placeholders by its own label; Dada's workbook
    # numbers replace them. A target anyone has saved is never touched.
    for bid in {r["board_id"] for r in sample_targets}:
        conn.execute("DELETE FROM sla_target WHERE board_id = ? AND note = ?", (bid, STARTER_NOTE))
    for r in sample_targets:
        cur = conn.execute(
            "INSERT OR IGNORE INTO sla_target (board_id, priority, clock, target_minutes, calendar,"
            " attainment_percent, enforced, note) VALUES (?,?,?,?,?,?,0,?)",
            (r["board_id"], r["priority"], r["clock"], int(r["target_minutes"]), r["calendar"],
             float(r["attainment_percent"]) if r["attainment_percent"] else None,
             blank(r["note"]) or "from Dada's design workbook"))
        targets += cur.rowcount
    for r in _sample("sla_targets_by_type.csv"):
        if r["board_id"] not in boards:
            continue
        cur = conn.execute(
            "INSERT OR IGNORE INTO sla_target_type (board_id, record_type, priority, clock,"
            " target_minutes, calendar, attainment_percent, enforced, note)"
            " VALUES (?,?,?,?,?,?,?,0,?)",
            (r["board_id"], r["record_type"], r["priority"], r["clock"],
             int(r["target_minutes"]), r["calendar"],
             float(r["attainment_percent"]) if r["attainment_percent"] else None,
             blank(r["note"]) or "from Dada's design workbook"))
        targets += cur.rowcount
    db.audit(conn, at=at.isoformat(sep=" ", timespec="minutes"), actor=actor,
             action="CATALOGUE_TEMPLATE", subject_kind="catalogue", subject_id="Dada PSA",
             detail=f"boards created {created or '-'}; {loaded} items loaded; waiting {waiting or '-'}")
    return {"created": created, "items": loaded, "targets": targets, "waiting": waiting}


# What a picker needs before it is worth opening. A Type on its own classifies
# nothing: a ticket is classified by a pair, so pairs are what this counts.
THIN = 20


def catalogue_health(conn: sqlite3.Connection) -> dict:
    """What the Type, Subtype and Item pickers actually hold, per board.

    Dada, 2 Oct 2026: *"make sure the types subtypes and items have data in them
    already"*. The three selects on a ticket are drawn from live catalogue pairs
    and nothing else, so an empty tree is a desk on which nobody can classify a
    ticket. This reads the tree on the store it is given -- the live one, when it
    is asked on the host -- rather than trusting that a seed ever ran.

    Nothing is written. `thin` names the boards whose picker would open with less
    than `THIN` pairs, which is what a report should lead with.
    """
    def one(sql):
        return conn.execute(sql).fetchone()[0]
    out = {
        "types": one("SELECT COUNT(*) FROM service_family WHERE COALESCE(inactive, 0) = 0"),
        "types_retired": one("SELECT COUNT(*) FROM service_family WHERE COALESCE(inactive, 0) = 1"),
        "subtypes": one("SELECT COUNT(*) FROM service_component WHERE is_draft = 0"),
        "items": one("SELECT COUNT(*) FROM service_action WHERE COALESCE(inactive, 0) = 0"),
        "pairs": one("SELECT COUNT(*) FROM catalogue_item WHERE is_draft = 0"),
        "boards": [], "thin": [],
    }
    for b in conn.execute("SELECT board_id, display_name FROM board ORDER BY display_name").fetchall():
        offered = catalogue_choices(conn, b["board_id"])
        row = {"board_id": b["board_id"], "display_name": b["display_name"],
               "offered": len(offered),
               "own": sum(1 for c in offered if c["on_board"]),
               "types": sorted({c["type"] for c in offered}),
               "subtypes": len({(c["type"], c["subtype"]) for c in offered})}
        out["boards"].append(row)
        if row["offered"] < THIN:
            out["thin"].append(b["board_id"])
    return out


def catalogue_choices(conn: sqlite3.Connection, board_id: str | None = None) -> list[dict]:
    """Every live catalogue item as Type › Subtype › Item, for the pickers: a
    retired area, subtype, item or pair (Setup › Catalogue) is not offered.
    With a board, its own items first; the reference PSA scopes types per board,
    the record keeps one tree (§2.4), so every item is offered and the board's
    are marked."""
    rows = conn.execute(
        "SELECT i.catalogue_item_id, f.display_name AS type, c.display_name AS subtype,"
        "       a.display_name AS item, a.kind, i.default_board_id, i.min_priority,"
        "       i.clinical_impact"
        "  FROM catalogue_item i"
        "  JOIN service_component c ON c.component_id = i.component_id"
        "  JOIN service_family f ON f.family_id = c.family_id"
        "  JOIN service_action a ON a.action_id = i.action_id"
        " WHERE i.is_draft = 0 AND c.is_draft = 0 AND COALESCE(f.inactive, 0) = 0"
        "   AND COALESCE(a.inactive, 0) = 0"
        " ORDER BY f.display_name, c.display_name, a.display_name").fetchall()
    out = [dict(r) | {"label": f"{r['type']} › {r['subtype']} › {r['item']}",
                      "on_board": r["default_board_id"] == board_id} for r in rows]
    return sorted(out, key=lambda x: (not x["on_board"], x["label"])) if board_id else out


# ------------------------------------------------------- two boards, side by side
#
# Dada, 6 Oct 2026: "the procurement board does not look like the pmo helpdesk
# board". The board page is one piece of code for every board, so when two
# boards look different it is because they are set up differently -- or because
# the person looking is not seeing a board at all (a member the desk does not
# recognise is drawn the requester's shell, whose home is My requests). This
# answers the first question from the database, so it is MEASURED rather than
# guessed at, and says nothing it was not asked. It reads; it never writes.

# What a board's own row says, and how a person would name it. Names and free
# text are left out: they are meant to differ.
BOARD_SETTINGS = (("kind", "kind"), ("restricted", "restricted"), ("is_live", "live"),
                  ("is_unrouted", "the unrouted queue"), ("calendar_id", "calendar"),
                  ("owner", "owner"), ("deputy", "deputy"), ("notify_requester", "emails the requester"),
                  ("notify_owner", "emails the owner"), ("closed_reply_policy", "a reply to a closed ticket"),
                  ("reopen_within_days", "reopens within (days)"), ("auto_assign", "auto-assign"),
                  ("survey_enabled", "survey"), ("closed_loop_required", "closed loop"),
                  ("default_work_role_id", "default work role"), ("default_work_type_id", "default work type"))

# What hangs off a board, counted. The first group is its set-up; the second is
# what it holds, which differs for good reasons and is shown for context only.
BOARD_PARTS = (("board_status", "statuses", "COALESCE(inactive, 0) = 0"),
               ("sla_target", "SLA targets", None), ("board_record_type", "ticket types it takes", None),
               ("board_member", "members", None), ("board_role", "board roles named", None),
               ("board_team", "teams", None), ("board_intake_address", "email addresses it claims", None),
               ("status_mail", "per-status emails", None), ("mail_template", "email wordings", None),
               ("standard_note", "standard notes", None), ("ticket_template", "templates", None),
               ("workflow", "workflow rules", None), ("board_auto_assign", "auto-assign rules", None),
               ("department_board", "departments that raise to it", None), ("oncall_slot", "on-call shifts", None))
BOARD_HOLDS = (("ticket", "tickets", None), ("project", "projects", None), ("recurrence", "recurring tickets", None))


def board_compare(conn: sqlite3.Connection, a: str, b: str) -> dict:
    """How board `b` is set up differently from board `a`. Returns the two
    rows' settings that differ, the parts each has a different count of, the
    statuses one has that the other does not, the catalogue each offers, and
    what each holds. Raises ValueError for a board that does not exist.

    Plain SELECTs only, so it reads the same on the SQL Server store it will
    actually be run against (no PRAGMA, no catalogue views)."""
    rows = {}
    for bid in (a, b):
        r = conn.execute("SELECT * FROM board WHERE board_id = ?", (bid,)).fetchone()
        if r is None:
            raise ValueError(f"no board {bid!r}")
        rows[bid] = dict(r)
    settings = [(label, rows[a].get(col), rows[b].get(col)) for col, label in BOARD_SETTINGS
                if rows[a].get(col) != rows[b].get(col)]

    def count(table, where, bid):
        # Every table named above carries board_id (they were read off the
        # schema); a store that has not taken the migration that made one is
        # answered with None rather than an error.
        try:
            return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE board_id = ?"
                                + (f" AND {where}" if where else ""), (bid,)).fetchone()[0]
        except Exception:                                   # noqa: BLE001
            return None

    parts, holds = [], []
    for table, label, where in BOARD_PARTS:
        x, y = count(table, where, a), count(table, where, b)
        if x is not None and x != y:
            parts.append((label, x, y))
    for table, label, where in BOARD_HOLDS:
        x, y = count(table, where, a), count(table, where, b)
        if x is not None:
            holds.append((label, x, y))

    def names(bid):
        return {r[0] for r in conn.execute(
            "SELECT name FROM board_status WHERE board_id = ? AND COALESCE(inactive, 0) = 0", (bid,))}
    sa, sb = names(a), names(b)
    picker = {bid: catalogue_choices(conn, bid) for bid in (a, b)}
    return {"a": a, "b": b, "names": (rows[a]["display_name"], rows[b]["display_name"]),
            "settings": settings, "parts": parts, "holds": holds,
            "statuses_only_a": sorted(sa - sb), "statuses_only_b": sorted(sb - sa),
            "own_pairs": (sum(1 for c in picker[a] if c["on_board"]),
                          sum(1 for c in picker[b] if c["on_board"]))}
