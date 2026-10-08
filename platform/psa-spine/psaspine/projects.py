"""Projects (041): planned work with a manager, dates, budget and phases.

The reference PSA's project, kept to what a hospital IT team runs: a project
has phases (a work breakdown that may nest), phases may wait on others
(predecessors), and tickets are the work. A ticket is linked to one project and
optionally one phase; its time entries are the project's actual hours, so
budget against actual needs nobody to type a number twice.

**What may be unmade.** Dada, 5 Oct 2026: *"for projects they cant be deleted
edited any elements for the project cant do that"*. Work that happened is
history and is never deleted -- a project is cancelled or done, a phase is
done, and a phase with tickets or hours against it keeps them. But a *mistake*
is not history. A phase added with a typo, a predecessor pointing the wrong
way, a ticket linked to the wrong project: those could not be undone at all,
which made the plan a thing you got right first time or lived with. So
everything here can now be edited, and anything carrying no work can be
removed, each through an audited function that says what it refused and why.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime

from . import db

STATUSES = {"PLANNED": "Planned", "ACTIVE": "Active", "ON_HOLD": "On hold", "DONE": "Done", "CANCELLED": "Cancelled"}


class Refused(ValueError):
    """A sentence for the person; nothing was written."""


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def _day(value: str | None, what: str) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        raise Refused(f"{what}: write a date as YYYY-MM-DD.") from None


def _hours(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        h = round(float(value), 2)
    except (TypeError, ValueError):
        raise Refused("Budget hours are a number.") from None
    if h < 0 or h > 100_000:
        raise Refused("Budget hours are between 0 and 100,000.")
    return h


def _audit(conn, at, actor, subject, detail):
    db.audit(conn, at=_stamp(at), actor=actor, action="PROJECT", subject_kind="project", subject_id=subject,
             detail=detail)


def _next_id(conn) -> str:
    n = 0
    for (pid,) in conn.execute("SELECT project_id FROM project"):
        try:
            n = max(n, int(pid.split("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"PRJ-{n + 1:04d}"


def create(conn, *, name: str, manager: str | None = None, board_id: str | None = None, starts_on=None,
           ends_on=None, budget_hours=None, description: str | None = None, entity_id: str | None = None,
           at: datetime, actor: str) -> str:
    name = " ".join((name or "").split())[:200]
    if not name:
        raise Refused("A project needs a name.")
    s, e = _day(starts_on, "Start"), _day(ends_on, "End")
    if s and e and e < s:
        raise Refused("A project ends after it starts.")
    if board_id and not conn.execute("SELECT 1 FROM board WHERE board_id = ?", (board_id,)).fetchone():
        raise Refused("No such board.")
    pid = _next_id(conn)
    conn.execute("INSERT INTO project (project_id, name, board_id, manager, status, starts_on, ends_on, budget_hours,"
                 " description, created_at, created_by) VALUES (?,?,?,?, 'PLANNED', ?,?,?,?,?,?)",
                 (pid, name, board_id or None, (manager or "").strip() or None, s, e, _hours(budget_hours),
                  (description or "").strip() or None, _stamp(at), actor))
    if entity_id:                                   # the company (068)
        conn.execute("UPDATE project SET entity_id = ? WHERE project_id = ?", (entity_id, pid))
    _audit(conn, at, actor, pid, f"project created: {name}")
    if (manager or "").strip():                     # the manager is on the team, as the reference PSA puts them
        add_member(conn, pid, manager.strip(), role="PROJECT_MANAGER", at=at, actor=actor)
    return pid


def get(conn, project_id: str):
    return conn.execute("SELECT p.*, b.display_name AS board_name FROM project p LEFT JOIN board b"
                        " ON b.board_id = p.board_id WHERE p.project_id = ?", (project_id,)).fetchone()


def update(conn, project_id: str, *, at: datetime, actor: str, **fields) -> str:
    row = get(conn, project_id)
    if row is None:
        raise Refused("No such project.")
    new = {}
    if "name" in fields:
        new["name"] = " ".join((fields["name"] or "").split())[:200]
        if not new["name"]:
            raise Refused("A project needs a name.")
    if "manager" in fields:
        new["manager"] = (fields["manager"] or "").strip() or None
    if "status" in fields:
        if fields["status"] not in STATUSES:
            raise Refused("No such status.")
        new["status"] = fields["status"]
    if "starts_on" in fields:
        new["starts_on"] = _day(fields["starts_on"], "Start")
    if "ends_on" in fields:
        new["ends_on"] = _day(fields["ends_on"], "End")
    if "budget_hours" in fields:
        new["budget_hours"] = _hours(fields["budget_hours"])
    if "description" in fields:
        new["description"] = (fields["description"] or "").strip() or None
    if "entity_id" in fields:                       # the company (068)
        new["entity_id"] = (fields["entity_id"] or "").strip() or None
    if "board_id" in fields:
        b = (fields["board_id"] or "").strip() or None
        if b and not conn.execute("SELECT 1 FROM board WHERE board_id = ?", (b,)).fetchone():
            raise Refused("No such board.")
        new["board_id"] = b
    s = new.get("starts_on", row["starts_on"])
    e = new.get("ends_on", row["ends_on"])
    if s and e and e < s:
        raise Refused("A project ends after it starts.")
    changed = {k: v for k, v in new.items() if v != row[k]}
    if not changed:
        return "nothing changed"
    conn.execute(f"UPDATE project SET {', '.join(k + ' = ?' for k in changed)} WHERE project_id = ?",
                 [*changed.values(), project_id])
    words = "; ".join(f"{k} {row[k] if row[k] is not None else '-'} -> {v if v is not None else '-'}"
                      for k, v in changed.items() if k != "description") or "description changed"
    _audit(conn, at, actor, project_id, words)
    m = changed.get("manager")
    if m and not conn.execute("SELECT 1 FROM project_member WHERE project_id = ? AND LOWER(member) = LOWER(?)",
                              (project_id, m)).fetchone():
        add_member(conn, project_id, m, role="PROJECT_MANAGER", at=at, actor=actor)   # 068
    return words


def project_work(conn, project_id: str) -> dict:
    """What a project is carrying. The page shows these, and `remove` refuses on
    them, so a button is never offered that cannot work."""
    if get(conn, project_id) is None:
        raise Refused("No such project.")
    from . import bizbox
    return {
        "phases": conn.execute("SELECT COUNT(*) FROM project_phase WHERE project_id = ?",
                               (project_id,)).fetchone()[0],
        "tickets": conn.execute("SELECT COUNT(*) FROM project_ticket WHERE project_id = ?",
                                (project_id,)).fetchone()[0],
        "finance": len(bizbox.links(conn, "PROJECT", project_id)),
    }


def remove(conn, project_id: str, *, at: datetime, actor: str) -> str:
    """Take a project off the list entirely. Only one that never got going:
    no phases, no tickets, no BizBox record. A project with any of those is a
    record of work and is **cancelled**, not deleted -- its tickets keep their
    history and their hours. This exists for the project created by mistake,
    or twice, which until now stayed on the list for ever."""
    row = get(conn, project_id)
    if row is None:
        raise Refused("No such project.")
    w = project_work(conn, project_id)
    held = [f"{w[k]} {word}" for k, word in (("phases", "phase(s)"), ("tickets", "ticket(s)"),
                                             ("finance", "BizBox record(s)")) if w[k]]
    if held:
        raise Refused(f"{row['name']} has {', '.join(held)}. A project with work on it is cancelled, "
                      "not deleted, so its tickets keep their hours and their history: set its status to "
                      "Cancelled instead. To delete it, take those off it first.")
    conn.execute("DELETE FROM project WHERE project_id = ?", (project_id,))
    _audit(conn, at, actor, project_id, f"project removed: {row['name']} (it carried no phase, ticket or record)")
    return f"Project {row['name']} removed"


def _board_clause(boards) -> tuple[str, list]:
    """Limit a project's ticket figures to the boards the viewer may see, so a
    restricted board's tickets do not show through a project's count or hours."""
    if boards is None:
        return "", []
    boards = sorted(boards)
    if not boards:
        return " AND 1 = 0", []
    return f" AND t.board_id IN ({','.join('?' * len(boards))})", boards


def all_projects(conn, *, status: str | None = None, boards=None):
    clause, args = _board_clause(boards)
    sql = ("SELECT p.*, (SELECT COUNT(*) FROM project_ticket pt JOIN ticket t ON t.work_item_id = pt.work_item_id"
           f" WHERE pt.project_id = p.project_id{clause}) AS tickets FROM project p")
    rows = conn.execute(sql + (" WHERE p.status = ?" if status else "") + " ORDER BY p.status, p.starts_on, p.name",
                        args + ([status] if status else [])).fetchall()
    return rows


# ------------------------------------------------------------------ phases

def add_phase(conn, project_id: str, *, name: str, parent_id: int | None = None, starts_on=None, ends_on=None,
              budget_hours=None, at: datetime, actor: str) -> int:
    if get(conn, project_id) is None:
        raise Refused("No such project.")
    name = " ".join((name or "").split())[:200]
    if not name:
        raise Refused("A phase needs a name.")
    if parent_id is not None:
        parent = conn.execute("SELECT project_id FROM project_phase WHERE phase_id = ?", (parent_id,)).fetchone()
        if parent is None or parent[0] != project_id:
            raise Refused("The parent phase is not on this project.")
    s, e = _day(starts_on, "Start"), _day(ends_on, "End")
    if s and e and e < s:
        raise Refused("A phase ends after it starts.")
    order = (conn.execute("SELECT MAX(sort_order) FROM project_phase WHERE project_id = ?",
                          (project_id,)).fetchone()[0] or 0) + 10
    cur = conn.execute("INSERT INTO project_phase (project_id, parent_id, name, sort_order, starts_on, ends_on,"
                       " budget_hours, status, created_at) VALUES (?,?,?,?,?,?,?, 'OPEN', ?)",
                       (project_id, parent_id, name, order, s, e, _hours(budget_hours), _stamp(at)))
    _audit(conn, at, actor, project_id, f"phase added: {name}")
    return cur.lastrowid


def phases(conn, project_id: str, *, boards=None) -> list[dict]:
    """The phases in tree order, each with its depth, its predecessors and its
    actual hours (its tickets' time entries, on the boards given)."""
    rows = [dict(r) for r in conn.execute("SELECT * FROM project_phase WHERE project_id = ? ORDER BY sort_order",
                                          (project_id,))]
    actual = hours_by_phase(conn, project_id, boards=boards)
    deps: dict[int, list[int]] = {}
    for d in conn.execute("SELECT d.phase_id, d.depends_on FROM phase_dependency d JOIN project_phase p"
                          " ON p.phase_id = d.phase_id WHERE p.project_id = ?", (project_id,)):
        deps.setdefault(d["phase_id"], []).append(d["depends_on"])
    by_parent: dict = {}
    for r in rows:
        by_parent.setdefault(r["parent_id"], []).append(r)
    out: list[dict] = []

    def walk(parent, depth):
        for r in by_parent.get(parent, []):
            out.append(r | {"depth": depth, "actual_hours": actual.get(r["phase_id"], 0.0),
                            "depends_on": deps.get(r["phase_id"], [])})
            walk(r["phase_id"], depth + 1)
    walk(None, 0)
    return out


def _phase(conn, phase_id: int):
    return conn.execute("SELECT * FROM project_phase WHERE phase_id = ?", (phase_id,)).fetchone()


def _descendants(conn, phase_id: int) -> set[int]:
    """Every phase under this one, however deep. Used to refuse a move that
    would put a phase inside itself, which would strand the whole subtree."""
    out, todo = set(), [phase_id]
    while todo:
        cur = todo.pop()
        for (kid,) in conn.execute("SELECT phase_id FROM project_phase WHERE parent_id = ?", (cur,)):
            if kid not in out:
                out.add(kid)
                todo.append(kid)
    return out


def update_phase(conn, phase_id: int, *, at: datetime, actor: str, **fields) -> str:
    """Edit a phase: its name, its dates, its budget, or where it sits in the
    breakdown. Checks everything before it writes, so a refused edit leaves the
    phase exactly as it was."""
    row = _phase(conn, phase_id)
    if row is None:
        raise Refused("No such phase.")
    new = {}
    if "name" in fields:
        new["name"] = " ".join((fields["name"] or "").split())[:200]
        if not new["name"]:
            raise Refused("A phase needs a name.")
    if "starts_on" in fields:
        new["starts_on"] = _day(fields["starts_on"], "Start")
    if "ends_on" in fields:
        new["ends_on"] = _day(fields["ends_on"], "End")
    if "budget_hours" in fields:
        new["budget_hours"] = _hours(fields["budget_hours"])
    if "parent_id" in fields:
        parent = fields["parent_id"]
        if parent is not None:
            parent = int(parent)
            if parent == phase_id:
                raise Refused("A phase cannot sit inside itself.")
            up = _phase(conn, parent)
            if up is None or up["project_id"] != row["project_id"]:
                raise Refused("The parent phase is not on this project.")
            if parent in _descendants(conn, phase_id):
                raise Refused(f"{up['name']} is already inside {row['name']}; that would be a loop.")
        new["parent_id"] = parent
    s = new.get("starts_on", row["starts_on"])
    e = new.get("ends_on", row["ends_on"])
    if s and e and e < s:
        raise Refused("A phase ends after it starts.")
    changed = {k: v for k, v in new.items() if v != row[k]}
    if not changed:
        return "nothing changed"
    conn.execute(f"UPDATE project_phase SET {', '.join(k + ' = ?' for k in changed)} WHERE phase_id = ?",
                 [*changed.values(), phase_id])
    words = "; ".join(f"{k} {row[k] if row[k] is not None else '-'} -> {v if v is not None else '-'}"
                      for k, v in changed.items())
    _audit(conn, at, actor, row["project_id"], f"phase {row['name']}: {words}")
    return words


def phase_work(conn, phase_id: int) -> dict:
    """What a phase is carrying: child phases, tickets, booked hours, and the
    phases waiting on it. `remove_phase` refuses on any of it, and the page
    shows the same numbers so nobody presses a button that cannot work."""
    row = _phase(conn, phase_id)
    if row is None:
        raise Refused("No such phase.")
    kids = conn.execute("SELECT COUNT(*) FROM project_phase WHERE parent_id = ?", (phase_id,)).fetchone()[0]
    tks = conn.execute("SELECT COUNT(*) FROM project_ticket WHERE phase_id = ?", (phase_id,)).fetchone()[0]
    hours = conn.execute(
        f"SELECT COALESCE(SUM({_entry_hours()}), 0) FROM time_entry te JOIN project_ticket pt"
        "  ON pt.work_item_id = te.work_item_id WHERE pt.phase_id = ?", (phase_id,)).fetchone()[0]
    blocks = [r[0] for r in conn.execute(
        "SELECT p.name FROM phase_dependency d JOIN project_phase p ON p.phase_id = d.phase_id"
        " WHERE d.depends_on = ?", (phase_id,))]
    return {"children": kids, "tickets": tks, "hours": round(float(hours or 0), 2), "blocks": blocks}


def remove_phase(conn, phase_id: int, *, at: datetime, actor: str) -> str:
    """Take a phase off the plan. Only one carrying no work: a phase with
    tickets or booked hours is a record of what was done, and deleting it would
    silently take their phase off those tickets. Say so instead."""
    row = _phase(conn, phase_id)
    if row is None:
        raise Refused("No such phase.")
    w = phase_work(conn, phase_id)
    if w["children"]:
        raise Refused(f"{row['name']} has {w['children']} phase(s) inside it. Remove or move those first.")
    if w["tickets"]:
        raise Refused(f"{w['tickets']} ticket(s) are on {row['name']}. Move them to another phase "
                      "(or to no phase) first; removing it would take their phase off them silently.")
    if w["hours"]:
        raise Refused(f"{w['hours']:g} hours are booked against {row['name']}. Hours are a record of work "
                      "done and are not deleted; mark the phase done instead.")
    # Its own predecessors go with it, and so do the pointers at it, which is
    # the whole reason a wrong "waits on" was unfixable before.
    conn.execute("DELETE FROM phase_dependency WHERE phase_id = ? OR depends_on = ?", (phase_id, phase_id))
    conn.execute("DELETE FROM project_phase WHERE phase_id = ?", (phase_id,))
    freed = (", and " + ", ".join(w["blocks"]) + " no longer waits on it") if w["blocks"] else ""
    _audit(conn, at, actor, row["project_id"], f"phase removed: {row['name']}{freed}")
    return f"Phase {row['name']} removed{freed}"


def move_phase(conn, phase_id: int, direction: int, *, at: datetime, actor: str) -> str:
    """Up or down among its own brothers and sisters. `sort_order` existed from
    the start and nothing could change it, so the order phases were typed in was
    the order they stayed in."""
    row = _phase(conn, phase_id)
    if row is None:
        raise Refused("No such phase.")
    # IS NULL spelled out, not "IS ?": SQL Server has no null-safe equality,
    # and the adapter refuses it (MEASURED, CI run 75, 8 Oct 2026).
    if row["parent_id"] is None:
        sibs = conn.execute("SELECT phase_id, name FROM project_phase WHERE project_id = ? AND parent_id IS NULL"
                            " ORDER BY sort_order, phase_id", (row["project_id"],)).fetchall()
    else:
        sibs = conn.execute("SELECT phase_id, name FROM project_phase WHERE project_id = ? AND parent_id = ?"
                            " ORDER BY sort_order, phase_id", (row["project_id"], row["parent_id"])).fetchall()
    ids = [r["phase_id"] for r in sibs]
    i = ids.index(phase_id)
    j = i + (-1 if direction < 0 else 1)
    if j < 0 or j >= len(ids):
        return "nothing changed"
    ids[i], ids[j] = ids[j], ids[i]
    for order, pid in enumerate(ids, start=1):
        conn.execute("UPDATE project_phase SET sort_order = ? WHERE phase_id = ?", (order * 10, pid))
    _audit(conn, at, actor, row["project_id"],
           f"phase {row['name']} moved {'up' if direction < 0 else 'down'}")
    return f"{row['name']} moved {'up' if direction < 0 else 'down'}"


def set_phase_status(conn, phase_id: int, done: bool, *, at: datetime, actor: str) -> None:
    row = conn.execute("SELECT project_id, name FROM project_phase WHERE phase_id = ?", (phase_id,)).fetchone()
    if row is None:
        raise Refused("No such phase.")
    if done:
        waiting = conn.execute(
            "SELECT p.name FROM phase_dependency d JOIN project_phase p ON p.phase_id = d.depends_on"
            " WHERE d.phase_id = ? AND p.status <> 'DONE'", (phase_id,)).fetchone()
        if waiting:
            raise Refused(f"{row['name']} waits on {waiting[0]}, which is not done.")
    conn.execute("UPDATE project_phase SET status = ? WHERE phase_id = ?", ("DONE" if done else "OPEN", phase_id))
    _audit(conn, at, actor, row["project_id"], f"phase {'done' if done else 'reopened'}: {row['name']}")


def add_dependency(conn, phase_id: int, depends_on: int, *, at: datetime, actor: str) -> None:
    a = conn.execute("SELECT project_id, name FROM project_phase WHERE phase_id = ?", (phase_id,)).fetchone()
    b = conn.execute("SELECT project_id, name FROM project_phase WHERE phase_id = ?", (depends_on,)).fetchone()
    if a is None or b is None or a[0] != b[0]:
        raise Refused("Both phases must be on the same project.")
    if phase_id == depends_on:
        raise Refused("A phase cannot wait on itself.")
    # no cycles: depends_on must not already (transitively) wait on phase_id
    seen, todo = set(), [depends_on]
    while todo:
        cur = todo.pop()
        if cur == phase_id:
            raise Refused(f"{b['name']} already waits on {a['name']}; that would be a loop.")
        if cur in seen:
            continue
        seen.add(cur)
        todo += [r[0] for r in conn.execute("SELECT depends_on FROM phase_dependency WHERE phase_id = ?", (cur,))]
    if conn.execute("SELECT 1 FROM phase_dependency WHERE phase_id = ? AND depends_on = ?",
                    (phase_id, depends_on)).fetchone():
        return
    conn.execute("INSERT INTO phase_dependency (phase_id, depends_on) VALUES (?,?)", (phase_id, depends_on))
    _audit(conn, at, actor, a[0], f"{a['name']} waits on {b['name']}")


def remove_dependency(conn, phase_id: int, depends_on: int, *, at: datetime, actor: str) -> str:
    """Stop a phase waiting on another. This one mattered most: a predecessor
    set the wrong way round could not be undone, and `set_phase_status` refuses
    to mark a phase done while something it waits on is open -- so one wrong
    click left two phases that could never be finished."""
    a = _phase(conn, phase_id)
    b = _phase(conn, depends_on)
    if a is None or b is None:
        raise Refused("No such phase.")
    gone = conn.execute("DELETE FROM phase_dependency WHERE phase_id = ? AND depends_on = ?",
                        (phase_id, depends_on)).rowcount
    if not gone:
        return "nothing changed"
    _audit(conn, at, actor, a["project_id"], f"{a['name']} no longer waits on {b['name']}")
    return f"{a['name']} no longer waits on {b['name']}"


# ----------------------------------------------------------------- tickets

def link_ticket(conn, work_item_id: str, project_id: str | None, phase_id: int | None = None, *,
                at: datetime, actor: str) -> str:
    """Put a ticket on a project (and phase), move it, or (project None) take it off."""
    from .board import _event
    if conn.execute("SELECT 1 FROM ticket WHERE work_item_id = ?", (work_item_id,)).fetchone() is None:
        raise Refused("No such ticket.")
    before = conn.execute("SELECT project_id, phase_id FROM project_ticket WHERE work_item_id = ?",
                          (work_item_id,)).fetchone()
    if project_id is None:
        if before is None:
            return "nothing changed"
        conn.execute("DELETE FROM project_ticket WHERE work_item_id = ?", (work_item_id,))
        _event(conn, work_item_id, _stamp(at), "PROJECT", actor, f"taken off project {before['project_id']}")
        return f"taken off {before['project_id']}"
    if get(conn, project_id) is None:
        raise Refused("No such project.")
    if phase_id is not None:
        ph = conn.execute("SELECT project_id FROM project_phase WHERE phase_id = ?", (phase_id,)).fetchone()
        if ph is None or ph[0] != project_id:
            raise Refused("That phase is not on this project.")
    if before and before["project_id"] == project_id and before["phase_id"] == phase_id:
        return "nothing changed"
    conn.execute("DELETE FROM project_ticket WHERE work_item_id = ?", (work_item_id,))
    conn.execute("INSERT INTO project_ticket (work_item_id, project_id, phase_id, linked_at, linked_by)"
                 " VALUES (?,?,?,?,?)", (work_item_id, project_id, phase_id, _stamp(at), actor))
    words = f"on project {project_id}" + (f", phase {phase_id}" if phase_id else "")
    _event(conn, work_item_id, _stamp(at), "PROJECT", actor, words)
    return words


def tickets(conn, project_id: str):
    return conn.execute(
        "SELECT pt.*, w.name AS summary, t.board_id, t.state, t.priority, t.owner, ph.name AS phase_name"
        "  FROM project_ticket pt JOIN ticket t ON t.work_item_id = pt.work_item_id"
        "  JOIN work_item w ON w.work_item_id = t.work_item_id"
        "  LEFT JOIN project_phase ph ON ph.phase_id = pt.phase_id"
        " WHERE pt.project_id = ? ORDER BY pt.linked_at", (project_id,)).fetchall()


def of_ticket(conn, work_item_id: str):
    return conn.execute("SELECT pt.*, p.name AS project_name, ph.name AS phase_name FROM project_ticket pt"
                        " JOIN project p ON p.project_id = pt.project_id"
                        " LEFT JOIN project_phase ph ON ph.phase_id = pt.phase_id WHERE pt.work_item_id = ?",
                        (work_item_id,)).fetchone()


def _entry_hours():
    # the time entry's own hours where recorded (033), else its band (003)
    return "COALESCE(te.actual_hours, te.band_hours)"


def hours_by_phase(conn, project_id: str, *, boards=None) -> dict:
    clause, args = _board_clause(boards)
    out: dict = {}
    for r in conn.execute(
            f"SELECT pt.phase_id, SUM({_entry_hours()}) AS h FROM project_ticket pt"
            "  JOIN time_entry te ON te.work_item_id = pt.work_item_id"
            "  JOIN ticket t ON t.work_item_id = pt.work_item_id"
            f" WHERE pt.project_id = ?{clause} GROUP BY pt.phase_id", [project_id, *args]):
        out[r["phase_id"]] = float(r["h"] or 0)
    return out


def hours_by_project(conn, *, boards=None) -> dict[str, float]:
    """Actual hours for every project in one query (the list page)."""
    clause, args = _board_clause(boards)
    return {r["project_id"]: round(float(r["h"] or 0), 2) for r in conn.execute(
        f"SELECT pt.project_id, SUM({_entry_hours()}) AS h FROM project_ticket pt"
        "  JOIN time_entry te ON te.work_item_id = pt.work_item_id"
        "  JOIN ticket t ON t.work_item_id = pt.work_item_id"
        f" WHERE 1 = 1{clause} GROUP BY pt.project_id", args)}


def actual_hours(conn, project_id: str, *, boards=None) -> float:
    return round(sum(hours_by_phase(conn, project_id, boards=boards).values()), 2)


# ------------------------------------------------------------------ team (068)
# Dada, 7 Oct 2026: "adding project members have not yet added". The reference
# PSA's project has a team: each member with a role on this project, the dates
# they are on it and the hours planned for them. The team is who the project's
# tickets are offered to first, and what "My projects" reads.

ROLES = {"PROJECT_MANAGER": "Project manager", "TEAM_LEAD": "Team lead", "TEAM_MEMBER": "Team member",
         "ENGINEER": "Engineer", "CONSULTANT": "Consultant", "STAKEHOLDER": "Stakeholder"}


def team(conn, project_id: str) -> list:
    return conn.execute("SELECT * FROM project_member WHERE project_id = ? ORDER BY"
                        " CASE project_role WHEN 'PROJECT_MANAGER' THEN 0 WHEN 'TEAM_LEAD' THEN 1 ELSE 2 END, member",
                        (project_id,)).fetchall()


def add_member(conn, project_id: str, member: str, *, role: str = "TEAM_MEMBER", starts_on=None, ends_on=None,
               hours=None, at: datetime, actor: str) -> str:
    """Put a member on the project's team, or change their role, dates or hours
    if they are on it already. Returns a sentence for the page and the audit."""
    p = get(conn, project_id)
    if p is None:
        raise Refused("No such project.")
    member = (member or "").strip()
    if not member:
        raise Refused("Pick a member.")
    if role not in roles(conn, include_inactive=True):
        raise Refused("No such project role.")
    s, e = _day(starts_on, "Start"), _day(ends_on, "End")
    if s and e and e < s:
        raise Refused("A member's time on the project ends after it starts.")
    h = _hours(hours)
    before = conn.execute("SELECT * FROM project_member WHERE project_id = ? AND LOWER(member) = LOWER(?)",
                          (project_id, member)).fetchone()
    if before is None:
        conn.execute("INSERT INTO project_member (project_id, member, project_role, starts_on, ends_on, hours,"
                     " added_at, added_by) VALUES (?,?,?,?,?,?,?,?)",
                     (project_id, member, role, s, e, h, _stamp(at), actor))
        words = f"{member} joined the team as {roles(conn, include_inactive=True)[role].lower()}"
    else:
        new = {"project_role": role, "starts_on": s, "ends_on": e, "hours": h}
        changed = {k: v for k, v in new.items() if v != before[k]}
        if not changed:
            return "nothing changed"
        conn.execute(f"UPDATE project_member SET {', '.join(k + ' = ?' for k in changed)}"
                     " WHERE project_id = ? AND member = ?", [*changed.values(), project_id, before["member"]])
        words = f"{before['member']} on the team: " + "; ".join(
            f"{k.replace('project_', '')} {before[k] if before[k] is not None else '-'} -> {v if v is not None else '-'}"
            for k, v in changed.items())
    _audit(conn, at, actor, project_id, words)
    return words


def remove_member(conn, project_id: str, member: str, *, at: datetime, actor: str) -> str:
    """Take a member off the team. Their tickets, time and history stay theirs;
    only the place on the team goes."""
    row = conn.execute("SELECT member FROM project_member WHERE project_id = ? AND LOWER(member) = LOWER(?)",
                       (project_id, (member or "").strip())).fetchone()
    if row is None:
        return "nothing changed"
    conn.execute("DELETE FROM project_member WHERE project_id = ? AND member = ?", (project_id, row["member"]))
    words = f"{row['member']} left the team"
    _audit(conn, at, actor, project_id, words)
    return words


def projects_of(conn, member: str) -> set[str]:
    """Every project a person manages or is on the team of ("My projects")."""
    m = (member or "").strip().lower()
    return {r[0] for r in conn.execute(
        "SELECT project_id FROM project WHERE LOWER(COALESCE(manager, '')) = ? UNION"
        " SELECT project_id FROM project_member WHERE LOWER(member) = ?", (m, m))}


# ------------------------------------------------------- project tickets (068)
# Dada, 7 Oct 2026: tickets "can be created inside the project itself like
# connectwise". A project ticket is opened in a phase from the project, on the
# project's board, through the same door as every other ticket (tickets.
# open_ticket: one number sequence, the board's status, clocks and audit), and
# carries its own budget hours.

def open_ticket(conn, project_id: str, *, summary: str, phase_id: int | None = None, owner: str | None = None,
                budget_hours=None, description: str | None = None, starts_on=None, due_on=None,
                at: datetime, actor: str) -> str:
    from . import tickets as _tickets
    p = get(conn, project_id)
    if p is None:
        raise Refused("No such project.")
    if not p["board_id"]:
        raise Refused("Give the project a project board first: its tickets are opened there.")
    if not is_project_board(conn, p["board_id"]):
        raise Refused("This project is on a service board. Move it to a project board first, so its tickets "
                      "stay off the Service Board.")
    summary = " ".join((summary or "").split())[:200]
    if not summary:
        raise Refused("A ticket needs a summary.")
    if phase_id is not None:
        ph = _phase(conn, phase_id)
        if ph is None or ph["project_id"] != project_id:
            raise Refused("That phase is not on this project.")
    budget = _hours(budget_hours)
    sd, dd = _day(starts_on, "Start"), _day(due_on, "Due")
    if sd and dd and dd < sd:
        raise Refused("A ticket is due after it starts.")
    wid = _tickets.open_ticket(conn, board_id=p["board_id"], summary=summary, impact="I3", urgency="U3",
                               requested_by=None, at=at, actor=actor, description=(description or "").strip() or None,
                               entity_id=p["entity_id"] if "entity_id" in p.keys() else None,
                               owner=(owner or "").strip() or None, source="DESK")
    link_ticket(conn, wid, project_id, phase_id, at=at, actor=actor)
    who = (owner or "").strip()
    if who and not conn.execute("SELECT 1 FROM project_member WHERE project_id = ? AND LOWER(member) = LOWER(?)",
                                (project_id, who)).fetchone():
        add_member(conn, project_id, who, at=at, actor=actor)   # whoever has the work is on the team
    if budget is not None:
        conn.execute("UPDATE project_ticket SET budget_hours = ? WHERE work_item_id = ?", (budget, wid))
    if sd or dd:                                     # 069: the dates the Gantt draws
        conn.execute("UPDATE project_ticket SET starts_on = ?, due_on = ? WHERE work_item_id = ?", (sd, dd, wid))
    _audit(conn, at, actor, project_id, f"ticket {wid} opened in the project: {summary}")
    return wid


def set_ticket_budget(conn, work_item_id: str, budget_hours, *, at: datetime, actor: str) -> str:
    row = conn.execute("SELECT project_id, budget_hours FROM project_ticket WHERE work_item_id = ?",
                       (work_item_id,)).fetchone()
    if row is None:
        raise Refused("That ticket is not on a project.")
    b = _hours(budget_hours)
    if b == row["budget_hours"]:
        return "nothing changed"
    conn.execute("UPDATE project_ticket SET budget_hours = ? WHERE work_item_id = ?", (b, work_item_id))
    words = f"{work_item_id} budget {row['budget_hours'] if row['budget_hours'] is not None else '-'} -> {b if b is not None else '-'} h"
    _audit(conn, at, actor, row["project_id"], words)
    return words


def ticket_hours(conn, project_id: str) -> dict[str, float]:
    """Actual hours on each of the project's tickets (their time entries)."""
    return {r[0]: float(r[1] or 0) for r in conn.execute(
        f"SELECT pt.work_item_id, SUM({_entry_hours()}) FROM project_ticket pt JOIN time_entry te"
        " ON te.work_item_id = pt.work_item_id WHERE pt.project_id = ? GROUP BY pt.work_item_id", (project_id,))}


def percent_complete(conn, project_id: str, *, boards=None) -> int | None:
    """The share of the project's tickets that are closed, as the reference
    PSA's calculated % complete reads it. None while it has no tickets."""
    clause, args = _board_clause(boards)
    row = conn.execute("SELECT COUNT(*), SUM(CASE WHEN t.state IN ('RESOLVED', 'CLOSED') THEN 1 ELSE 0 END)"
                       " FROM project_ticket pt JOIN ticket t ON t.work_item_id = pt.work_item_id"
                       f" WHERE pt.project_id = ?{clause}", [project_id, *args]).fetchone()
    return round(100 * (row[1] or 0) / row[0]) if row[0] else None


# ------------------------------------------------------------------ notes (068)

def add_note(conn, project_id: str, body: str, *, at: datetime, actor: str) -> int:
    if get(conn, project_id) is None:
        raise Refused("No such project.")
    body = (body or "").strip()
    if not body:
        raise Refused("A note needs some words.")
    cur = conn.execute("INSERT INTO project_note (project_id, body, written_at, written_by) VALUES (?,?,?,?)",
                       (project_id, body[:8000], _stamp(at), actor))
    _audit(conn, at, actor, project_id, "note added")
    return cur.lastrowid


def notes(conn, project_id: str) -> list:
    return conn.execute("SELECT * FROM project_note WHERE project_id = ? ORDER BY note_id DESC", (project_id,)).fetchall()


# ================================================================ 069
# Dada, 7 Oct 2026: "add those missing ... except for the billing bit": the
# reference PSA's project contacts, health, closing, ticket predecessors and
# dates (which the Gantt draws), templates and Copy Project.

HEALTH = {"ON_TRACK": "On track", "AT_RISK": "At risk", "HIGH_RISK": "High risk", "OFF_TRACK": "Off track"}


def _col(row, name):
    return row[name] if name in row.keys() else None


def health(conn, project_id: str, *, today: date | None = None, boards=None) -> tuple[str, str, bool]:
    """(code, why, set_by_a_person). A person's setting wins; otherwise the
    desk reads it from budget and dates: over budget or past its end with work
    open is Off track; within 15% of budget, or within a week of its end with
    under 80% done, At risk; else On track."""
    p = get(conn, project_id)
    if p is None:
        raise Refused("No such project.")
    if _col(p, "health") in HEALTH:
        return p["health"], "set by a person", True
    st = status_of(conn, p)                         # 070: a status carries its own indicator
    if st["indicator"] != "ON_TRACK":
        return st["indicator"], f"its status is {st['name']}", False
    today = today or date.today()
    actual = actual_hours(conn, project_id, boards=boards)
    pct = percent_complete(conn, project_id, boards=boards)
    open_work = pct is not None and pct < 100
    if p["status"] in ("DONE", "CANCELLED"):
        return "ON_TRACK", "closed", False
    if p["budget_hours"] and actual > p["budget_hours"]:
        return "OFF_TRACK", f"{actual:g} h booked against a budget of {p['budget_hours']:g} h", False
    end = date.fromisoformat(p["ends_on"]) if p["ends_on"] else None
    if end and today > end and open_work:
        return "OFF_TRACK", f"past its end ({p['ends_on']}) with tickets open", False
    if p["budget_hours"] and actual > 0.85 * p["budget_hours"]:
        return "AT_RISK", f"{actual / p['budget_hours'] * 100:.0f}% of the budget booked", False
    if end and (end - today).days <= 7 and pct is not None and pct < 80:
        return "AT_RISK", f"ends {p['ends_on']} with {pct}% done", False
    return "ON_TRACK", "within budget and dates", False


def set_health(conn, project_id: str, code: str | None, *, at: datetime, actor: str) -> str:
    p = get(conn, project_id)
    if p is None:
        raise Refused("No such project.")
    code = code or None
    if code is not None and code not in HEALTH:
        raise Refused("No such health.")
    if _col(p, "health") == code:
        return "nothing changed"
    conn.execute("UPDATE project SET health = ? WHERE project_id = ?", (code, project_id))
    words = f"health {HEALTH.get(code, 'read by the desk') if code else 'read by the desk'}"
    _audit(conn, at, actor, project_id, words)
    return words


# ------------------------------------------------------------------ contacts

def contacts(conn, project_id: str) -> list:
    return conn.execute("SELECT pc.*, c.display_name, c.email, c.phone, c.department FROM project_contact pc"
                        " JOIN contact c ON c.contact_id = pc.contact_id WHERE pc.project_id = ?"
                        " ORDER BY c.display_name", (project_id,)).fetchall()


def add_contact(conn, project_id: str, contact_id: str, *, role: str | None = None, at: datetime, actor: str) -> str:
    if get(conn, project_id) is None:
        raise Refused("No such project.")
    c = conn.execute("SELECT contact_id, display_name FROM contact WHERE contact_id = ?",
                     ((contact_id or "").strip(),)).fetchone()
    if c is None:
        raise Refused("No such contact.")
    role = " ".join((role or "").split())[:200] or None
    before = conn.execute("SELECT role FROM project_contact WHERE project_id = ? AND contact_id = ?",
                          (project_id, c["contact_id"])).fetchone()
    if before is None:
        conn.execute("INSERT INTO project_contact (project_id, contact_id, role, added_at, added_by) VALUES (?,?,?,?,?)",
                     (project_id, c["contact_id"], role, _stamp(at), actor))
        words = f"contact {c['display_name']} added" + (f" as {role}" if role else "")
    elif before["role"] != role:
        conn.execute("UPDATE project_contact SET role = ? WHERE project_id = ? AND contact_id = ?",
                     (role, project_id, c["contact_id"]))
        words = f"contact {c['display_name']}: role {before['role'] or '-'} -> {role or '-'}"
    else:
        return "nothing changed"
    _audit(conn, at, actor, project_id, words)
    return words


def remove_contact(conn, project_id: str, contact_id: str, *, at: datetime, actor: str) -> str:
    n = conn.execute("DELETE FROM project_contact WHERE project_id = ? AND contact_id = ?",
                     (project_id, contact_id)).rowcount
    if not n:
        return "nothing changed"
    _audit(conn, at, actor, project_id, f"contact {contact_id} taken off")
    return "contact taken off"


# ------------------------------------------- ticket dates and predecessors

def set_ticket_plan(conn, work_item_id: str, *, starts_on=None, due_on=None, budget_hours="__keep__",
                    at: datetime, actor: str) -> str:
    """A project ticket's estimated start, required date and budget."""
    row = conn.execute("SELECT * FROM project_ticket WHERE work_item_id = ?", (work_item_id,)).fetchone()
    if row is None:
        raise Refused("That ticket is not on a project.")
    s, e = _day(starts_on, "Start"), _day(due_on, "Due")
    if s and e and e < s:
        raise Refused("A ticket is due after it starts.")
    new = {"starts_on": s, "due_on": e}
    if budget_hours != "__keep__":
        new["budget_hours"] = _hours(budget_hours)
    changed = {k: v for k, v in new.items() if v != _col(row, k)}
    if not changed:
        return "nothing changed"
    conn.execute(f"UPDATE project_ticket SET {', '.join(k + ' = ?' for k in changed)} WHERE work_item_id = ?",
                 [*changed.values(), work_item_id])
    words = f"{work_item_id}: " + "; ".join(f"{k} {_col(row, k) or '-'} -> {v if v is not None else '-'}"
                                             for k, v in changed.items())
    _audit(conn, at, actor, row["project_id"], words)
    return words


def ticket_predecessors(conn, work_item_id: str) -> list:
    """The tickets this one waits on, each with its state."""
    return conn.execute("SELECT d.depends_on, w.name AS summary, t.state FROM project_ticket_dependency d"
                        " JOIN ticket t ON t.work_item_id = d.depends_on JOIN work_item w ON w.work_item_id = t.work_item_id"
                        " WHERE d.work_item_id = ? ORDER BY d.depends_on", (work_item_id,)).fetchall()


def open_predecessors(conn, work_item_id: str) -> list[str]:
    return [r["depends_on"] for r in ticket_predecessors(conn, work_item_id)
            if r["state"] not in ("RESOLVED", "CLOSED", "CANCELLED")]


def add_ticket_dependency(conn, work_item_id: str, depends_on: str, *, at: datetime, actor: str) -> str:
    a = conn.execute("SELECT project_id FROM project_ticket WHERE work_item_id = ?", (work_item_id,)).fetchone()
    b = conn.execute("SELECT project_id FROM project_ticket WHERE work_item_id = ?", ((depends_on or "").strip(),)).fetchone()
    if a is None or b is None or a[0] != b[0]:
        raise Refused("Both tickets must be on the same project.")
    depends_on = depends_on.strip()
    if depends_on == work_item_id:
        raise Refused("A ticket cannot wait on itself.")
    # refuse a loop: depends_on must not already (however deep) wait on work_item_id
    seen, todo = set(), [depends_on]
    while todo:
        cur = todo.pop()
        if cur == work_item_id:
            raise Refused("That would make the two tickets wait on each other.")
        if cur in seen:
            continue
        seen.add(cur)
        todo += [r[0] for r in conn.execute("SELECT depends_on FROM project_ticket_dependency WHERE work_item_id = ?", (cur,))]
    if conn.execute("SELECT 1 FROM project_ticket_dependency WHERE work_item_id = ? AND depends_on = ?",
                    (work_item_id, depends_on)).fetchone():
        return "nothing changed"
    conn.execute("INSERT INTO project_ticket_dependency (work_item_id, depends_on) VALUES (?,?)", (work_item_id, depends_on))
    words = f"{work_item_id} waits on {depends_on}"
    _audit(conn, at, actor, a[0], words)
    return words


def remove_ticket_dependency(conn, work_item_id: str, depends_on: str, *, at: datetime, actor: str) -> str:
    row = conn.execute("SELECT project_id FROM project_ticket WHERE work_item_id = ?", (work_item_id,)).fetchone()
    n = conn.execute("DELETE FROM project_ticket_dependency WHERE work_item_id = ? AND depends_on = ?",
                     (work_item_id, depends_on)).rowcount
    if not n or row is None:
        return "nothing changed"
    words = f"{work_item_id} no longer waits on {depends_on}"
    _audit(conn, at, actor, row[0], words)
    return words


# ------------------------------------------------------------------ closing

def close(conn, project_id: str, status: str, *, ticket_status: str | None = None, close_tickets: bool = False,
          close_phases: bool = False, at: datetime, actor: str) -> list[str]:
    """Close a project the way the reference PSA's close dialog does: the
    project's status, and, if asked, its open phases done and its open tickets
    moved to a closed status (the one named where it is on the ticket's own
    board, else that board's first closed status). Returns what was done."""
    from . import board as _board
    if status not in ("DONE", "CANCELLED"):
        raise Refused("A project closes as Done or Cancelled.")
    if get(conn, project_id) is None:
        raise Refused("No such project.")
    said = []
    if close_tickets:
        for r in tickets(conn, project_id):
            if r["state"] in ("RESOLVED", "CLOSED", "CANCELLED"):
                continue
            target = None
            if ticket_status:
                ok = conn.execute("SELECT 1 FROM board_status WHERE board_status_id = ? AND board_id = ? AND is_closed = 1"
                                  " AND inactive = 0", (ticket_status, r["board_id"])).fetchone()
                target = ticket_status if ok else None
            if target is None:
                # the board's own closing status; >Cancelled only when the project itself is cancelled,
                # as the desk never closes work as cancelled on someone's behalf (067)
                from .setup import is_cancelled_name
                rows = conn.execute("SELECT board_status_id, name FROM board_status WHERE board_id = ? AND is_closed = 1"
                                    " AND inactive = 0 ORDER BY sort_order", (r["board_id"],)).fetchall()
                want_cancel = status == "CANCELLED"
                pick = [x for x in rows if is_cancelled_name(x["name"]) == want_cancel] or \
                       [x for x in rows if not is_cancelled_name(x["name"])]
                target = pick[0]["board_status_id"] if pick else None
            if target is None:
                said.append(f"{r['work_item_id']} left open: its board has no closed status")
                continue
            _board.change_status(conn, r["work_item_id"], target, at=at, actor=actor)
            said.append(f"{r['work_item_id']} closed")
    if close_phases:
        n = conn.execute("UPDATE project_phase SET status = 'DONE' WHERE project_id = ? AND status = 'OPEN'",
                         (project_id,)).rowcount
        if n:
            said.append(f"{n} phase(s) done")
    words = update(conn, project_id, status=status, at=at, actor=actor)
    if words != "nothing changed":
        said.append(words)
    return said


# -------------------------------------------------------------- templates

def is_template(row) -> bool:
    return bool(_col(row, "is_template"))


def set_template(conn, project_id: str, flag: bool, *, at: datetime, actor: str) -> str:
    p = get(conn, project_id)
    if p is None:
        raise Refused("No such project.")
    if flag and conn.execute("SELECT 1 FROM project_ticket WHERE project_id = ?", (project_id,)).fetchone():
        raise Refused("A project with tickets is work, not a template. Use Copy project to start a new one from it.")
    if bool(_col(p, "is_template")) == bool(flag):
        return "nothing changed"
    conn.execute("UPDATE project SET is_template = ? WHERE project_id = ?", (1 if flag else 0, project_id))
    words = "made a template" if flag else "no longer a template"
    _audit(conn, at, actor, project_id, words)
    return words


def plan_items(conn, project_id: str) -> list:
    return conn.execute("SELECT i.*, ph.name AS phase_name FROM project_plan_item i LEFT JOIN project_phase ph"
                        " ON ph.phase_id = i.phase_id WHERE i.project_id = ? ORDER BY i.sort_order, i.item_id",
                        (project_id,)).fetchall()


def add_plan_item(conn, project_id: str, *, summary: str, phase_id: int | None = None, budget_hours=None,
                  at: datetime, actor: str) -> int:
    p = get(conn, project_id)
    if p is None:
        raise Refused("No such project.")
    if not is_template(p):
        raise Refused("Planned tickets belong to a template; on a project, create the ticket itself.")
    summary = " ".join((summary or "").split())[:200]
    if not summary:
        raise Refused("A planned ticket needs a summary.")
    if phase_id is not None:
        ph = _phase(conn, phase_id)
        if ph is None or ph["project_id"] != project_id:
            raise Refused("That phase is not on this template.")
    order = (conn.execute("SELECT MAX(sort_order) FROM project_plan_item WHERE project_id = ?",
                          (project_id,)).fetchone()[0] or 0) + 10
    cur = conn.execute("INSERT INTO project_plan_item (project_id, phase_id, summary, budget_hours, sort_order, created_at)"
                       " VALUES (?,?,?,?,?,?)", (project_id, phase_id, summary, _hours(budget_hours), order, _stamp(at)))
    _audit(conn, at, actor, project_id, f"planned ticket added: {summary}")
    return cur.lastrowid


def remove_plan_item(conn, project_id: str, item_id: int, *, at: datetime, actor: str) -> str:
    n = conn.execute("DELETE FROM project_plan_item WHERE project_id = ? AND item_id = ?", (project_id, item_id)).rowcount
    if not n:
        return "nothing changed"
    _audit(conn, at, actor, project_id, "planned ticket removed")
    return "planned ticket removed"


def templates(conn) -> list:
    return conn.execute("SELECT * FROM project WHERE COALESCE(is_template, 0) = 1 ORDER BY name").fetchall()


def copy(conn, source_id: str, *, name: str, manager: str | None = None, board_id: str | None = None,
         starts_on=None, entity_id: str | None = None, copy_team: bool = True, at: datetime, actor: str) -> str:
    """A new project from a template (Apply template) or from another project
    (Copy project). The phases come across with their nesting, predecessors,
    budgets and dates (moved to the new start), and so do the team and the
    contacts. A template's planned tickets, or a project's tickets, are opened
    as new tickets in the matching phases, unassigned and with their budgets.
    Nothing on the source changes."""
    src = get(conn, source_id)
    if src is None:
        raise Refused("No such project or template.")
    board = board_id or src["board_id"]
    shift = None
    s = _day(starts_on, "Start")
    if s and src["starts_on"]:
        shift = date.fromisoformat(s) - date.fromisoformat(src["starts_on"])

    def moved(d):
        """A source date moved by the gap between the two starts."""
        return (date.fromisoformat(d) + shift).isoformat() if d and shift is not None else d
    ends = moved(src["ends_on"])
    pid = create(conn, name=name or f"{src['name']} (copy)", manager=manager if manager is not None else src["manager"],
                 board_id=board, starts_on=s or src["starts_on"], ends_on=ends, budget_hours=src["budget_hours"],
                 description=src["description"], entity_id=entity_id or _col(src, "entity_id"), at=at, actor=actor)
    mapping: dict[int, int] = {}
    for ph in phases(conn, source_id):
        new_id = add_phase(conn, pid, name=ph["name"], parent_id=mapping.get(ph["parent_id"]),
                           starts_on=moved(ph["starts_on"]), ends_on=moved(ph["ends_on"]),
                           budget_hours=ph["budget_hours"], at=at, actor=actor)
        mapping[ph["phase_id"]] = new_id
    for d in conn.execute("SELECT d.phase_id, d.depends_on FROM phase_dependency d JOIN project_phase p"
                          " ON p.phase_id = d.phase_id WHERE p.project_id = ?", (source_id,)).fetchall():
        if d[0] in mapping and d[1] in mapping:
            conn.execute("INSERT INTO phase_dependency (phase_id, depends_on) VALUES (?,?)", (mapping[d[0]], mapping[d[1]]))
    if copy_team:
        for m in team(conn, source_id):
            add_member(conn, pid, m["member"], role=m["project_role"], hours=m["hours"], at=at, actor=actor)
        for c in contacts(conn, source_id):
            add_contact(conn, pid, c["contact_id"], role=c["role"], at=at, actor=actor)
    work = ([(i["summary"], i["phase_id"], i["budget_hours"]) for i in plan_items(conn, source_id)] if is_template(src)
            else [(r["summary"], r["phase_id"], _col(r, "budget_hours")) for r in tickets(conn, source_id)])
    if work and not board:
        raise Refused("The new project needs a board for its tickets.")
    for summary, phase_id, budget in work:
        open_ticket(conn, pid, summary=summary, phase_id=mapping.get(phase_id), budget_hours=budget, at=at, actor=actor)
    _audit(conn, at, actor, pid, f"made from {'template' if is_template(src) else 'project'} {source_id}")
    return pid



# ===================================================== project boards (7 Oct)
# Dada, 7 Oct 2026: "the project board isnt a service board ... what will
# happen in there is that it will be a hodge podge of tickets". A project's
# tickets live on a project board (board.kind PROJECT): its own statuses, no SLA
# clocks, and never on the Service Board.

def is_project_board(conn, board_id: str | None) -> bool:
    if not board_id:
        return False
    row = conn.execute("SELECT kind FROM board WHERE board_id = ?", (board_id,)).fetchone()
    return bool(row) and row["kind"] == "PROJECT"


def project_boards(conn) -> list:
    return conn.execute("SELECT board_id, display_name FROM board WHERE kind = 'PROJECT'"
                        " AND COALESCE(inactive, 0) = 0 ORDER BY display_name").fetchall()


def to_project_board(conn, work_item_id: str, board_id: str, *, at: datetime, actor: str, reason: str) -> None:
    """Put one ticket on a project board: the board's own status, the Project
    record type, and its SLA clocks stopped, since a project board runs none.
    The ticket keeps its number, notes, time and files (board.move)."""
    from . import board as _board
    row = conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?", (work_item_id,)).fetchone()
    if row is None:
        raise Refused("No such ticket.")
    if row["board_id"] != board_id:
        try:
            _board.move(conn, work_item_id, board_id, at=at, actor=actor, reason=reason, record_type="PROJECT")
        except (_board.NotOnThisBoard, LookupError) as exc:
            raise Refused(str(exc)) from None
    conn.execute("UPDATE ticket_clock SET stopped_at = ? WHERE work_item_id = ? AND stopped_at IS NULL",
                 (_stamp(at), work_item_id))


def move_to_project_board(conn, project_id: str, board_id: str, *, at: datetime, actor: str) -> str:
    """A project made before project boards were kept apart, or put on a service
    board by mistake: the project and every one of its tickets move to a project
    board in one step. Nothing is lost; each ticket keeps its number and history."""
    p = get(conn, project_id)
    if p is None:
        raise Refused("No such project.")
    if not is_project_board(conn, board_id):
        raise Refused("Pick a project board.")
    n = 0
    for r in tickets(conn, project_id):
        if r["board_id"] != board_id:
            to_project_board(conn, r["work_item_id"], board_id, at=at, actor=actor,
                             reason=f"project {project_id} moved to its project board")
            n += 1
    conn.execute("UPDATE project SET board_id = ? WHERE project_id = ?", (board_id, project_id))
    words = f"moved to the project board {board_id}" + (f" with {n} ticket(s)" if n else "")
    _audit(conn, at, actor, project_id, words)
    return words


# ================================================ converting tickets (7 Oct)
# Dada, 7 Oct 2026: "you can convert a service ticket into a project ticket".
# The ticket keeps its number, notes, time, files and history; only where it
# lives and how it is clocked change.

def convert_to_project_ticket(conn, work_item_id: str, project_id: str, *, phase_id: int | None = None,
                              budget_hours=None, at: datetime, actor: str) -> str:
    """A service ticket becomes a project ticket: onto the project's board with
    the Project record type and the board's status, into the phase, its SLA
    clocks stopped."""
    p = get(conn, project_id)
    if p is None:
        raise Refused("No such project.")
    if is_template(p):
        raise Refused("A template holds planned tickets, not tickets.")
    if not is_project_board(conn, p["board_id"]):
        raise Refused("That project is not on a project board yet. Move it to one first.")
    t = conn.execute("SELECT board_id, state FROM ticket WHERE work_item_id = ?", (work_item_id,)).fetchone()
    if t is None:
        raise Refused("No such ticket.")
    if t["board_id"] == p["board_id"] and conn.execute(
            "SELECT 1 FROM project_ticket WHERE work_item_id = ? AND project_id = ?", (work_item_id, project_id)).fetchone():
        raise Refused("That ticket is already a project ticket on this project.")
    if phase_id is not None:
        ph = _phase(conn, phase_id)
        if ph is None or ph["project_id"] != project_id:
            raise Refused("That phase is not on this project.")
    prev = conn.execute("SELECT project_id FROM project_ticket WHERE work_item_id = ?", (work_item_id,)).fetchone()
    if prev and prev["project_id"] != project_id:      # its predecessors belonged to the other project
        conn.execute("DELETE FROM project_ticket_dependency WHERE work_item_id = ? OR depends_on = ?",
                     (work_item_id, work_item_id))
    to_project_board(conn, work_item_id, p["board_id"], at=at, actor=actor,
                     reason=f"converted to a project ticket on {project_id}")
    link_ticket(conn, work_item_id, project_id, phase_id, at=at, actor=actor)
    if budget_hours not in (None, ""):
        conn.execute("UPDATE project_ticket SET budget_hours = ? WHERE work_item_id = ?",
                     (_hours(budget_hours), work_item_id))
    words = f"service ticket {work_item_id} converted to a project ticket"
    _audit(conn, at, actor, project_id, words)
    return words


def convert_to_service_ticket(conn, work_item_id: str, board_id: str, *, record_type: str = "SERVICE_REQUEST",
                              at: datetime, actor: str) -> str:
    """A project ticket becomes a service ticket again: off the project, onto a
    service board as the record type named. Its stopped SLA clocks stay as they
    were: the time it spent as project work is not counted against a target."""
    from . import board as _board
    row = conn.execute("SELECT pt.project_id, t.board_id FROM project_ticket pt JOIN ticket t ON t.work_item_id ="
                       " pt.work_item_id WHERE pt.work_item_id = ?", (work_item_id,)).fetchone()
    if row is None:
        raise Refused("That ticket is not a project ticket.")
    if is_project_board(conn, board_id) or not conn.execute("SELECT 1 FROM board WHERE board_id = ?", (board_id,)).fetchone():
        raise Refused("Pick a service board.")
    try:
        _board.move(conn, work_item_id, board_id, at=at, actor=actor, record_type=record_type,
                    reason=f"converted from a project ticket on {row['project_id']}")
    except (_board.NotOnThisBoard, LookupError) as exc:
        raise Refused(str(exc)) from None
    conn.execute("DELETE FROM project_ticket_dependency WHERE work_item_id = ? OR depends_on = ?",
                 (work_item_id, work_item_id))
    link_ticket(conn, work_item_id, None, at=at, actor=actor)
    words = f"project ticket {work_item_id} converted to a service ticket on {board_id}"
    _audit(conn, at, actor, row["project_id"], words)
    return words


# ================================================== setup tables (070)
# The reference PSA keeps project statuses, project types and project roles as
# setup tables. The five statuses a project could hold before are seeded with
# their old codes as ids, so nothing already stored changes meaning.

# (id, name, indicator, default, closed, no time). No seed holds time: a status that
# does is an administrator's choice in Setup, never a change that arrives on its own.
SEED_STATUSES = (("PLANNED", "Planned", "ON_TRACK", 1, 0, 0), ("ACTIVE", "Active", "ON_TRACK", 0, 0, 0),
                 ("ON_HOLD", "On hold", "AT_RISK", 0, 0, 0), ("DONE", "Done", "ON_TRACK", 0, 1, 0),
                 ("CANCELLED", "Cancelled", "ON_TRACK", 0, 1, 0))


def ensure_vocabulary(conn) -> None:
    """Seed the setup tables the first time they are read (only into empty tables)."""
    if not conn.execute("SELECT 1 FROM project_status").fetchone():
        for i, (sid, name, ind, dflt, closed, no_time) in enumerate(SEED_STATUSES):
            conn.execute("INSERT INTO project_status (status_id, name, indicator, is_default, is_closed, no_time, sort_order)"
                         " VALUES (?,?,?,?,?,?,?)", (sid, name, ind, dflt, closed, no_time, (i + 1) * 10))
    if not conn.execute("SELECT 1 FROM project_role").fetchone():
        for i, (rid, name) in enumerate(ROLES.items()):
            conn.execute("INSERT INTO project_role (role_id, name, sort_order) VALUES (?,?,?)", (rid, name, (i + 1) * 10))
    if not conn.execute("SELECT 1 FROM project_type").fetchone():
        conn.execute("INSERT INTO project_type (type_id, name, is_default) VALUES ('GENERAL', 'General', 1)")


def statuses(conn, *, include_inactive: bool = False) -> list:
    ensure_vocabulary(conn)
    return conn.execute("SELECT * FROM project_status" + ("" if include_inactive else " WHERE inactive = 0")
                        + " ORDER BY sort_order, name").fetchall()


def types(conn, *, include_inactive: bool = False) -> list:
    ensure_vocabulary(conn)
    return conn.execute("SELECT * FROM project_type" + ("" if include_inactive else " WHERE inactive = 0")
                        + " ORDER BY name").fetchall()


def roles(conn, *, include_inactive: bool = False) -> dict[str, str]:
    ensure_vocabulary(conn)
    return {r["role_id"]: r["name"] for r in conn.execute(
        "SELECT role_id, name FROM project_role" + ("" if include_inactive else " WHERE inactive = 0")
        + " ORDER BY sort_order, name")}


def status_of(conn, p) -> dict:
    """A project's status row (its setup-table status, else the old code's seed)."""
    ensure_vocabulary(conn)
    sid = _col(p, "project_status_id") or p["status"]
    row = conn.execute("SELECT * FROM project_status WHERE status_id = ?", (sid,)).fetchone()
    return dict(row) if row else {"status_id": p["status"], "name": STATUSES.get(p["status"], p["status"]),
                                  "indicator": "ON_TRACK", "is_closed": int(p["status"] in ("DONE", "CANCELLED")),
                                  "no_time": 0}


def set_status(conn, project_id: str, status_id: str, *, at: datetime, actor: str) -> str:
    """Set a project's status from the setup table. project.status keeps the old
    code where the status is one of the seeds, else Done for a closed status and
    Active for an open one, so every older reader still reads it right."""
    ensure_vocabulary(conn)
    row = conn.execute("SELECT * FROM project_status WHERE status_id = ?", (status_id,)).fetchone()
    if row is None:
        raise Refused("No such project status.")
    p = get(conn, project_id)
    if p is None:
        raise Refused("No such project.")
    legacy = status_id if status_id in STATUSES else ("DONE" if row["is_closed"] else "ACTIVE")
    if (_col(p, "project_status_id") or p["status"]) == status_id:
        return "nothing changed"
    conn.execute("UPDATE project SET project_status_id = ?, status = ? WHERE project_id = ?", (status_id, legacy, project_id))
    words = f"status {status_of(conn, p)['name']} -> {row['name']}"
    _audit(conn, at, actor, project_id, words)
    return words


def save_status(conn, status_id: str | None, *, name: str, indicator: str = "ON_TRACK", is_default: bool = False,
                is_closed: bool = False, no_time: bool = False, inactive: bool = False, at: datetime, actor: str) -> str:
    """Add (status_id None) or change a project status in Setup."""
    ensure_vocabulary(conn)
    name = " ".join((name or "").split())[:100]
    if not name:
        raise Refused("A status needs a name.")
    if indicator not in HEALTH:
        raise Refused("No such status indicator.")
    if status_id is None:
        base = "".join(ch if ch.isalnum() else "_" for ch in name.upper())[:40].strip("_") or "STATUS"
        status_id, n = base, 1
        while conn.execute("SELECT 1 FROM project_status WHERE status_id = ?", (status_id,)).fetchone():
            n += 1
            status_id = f"{base}_{n}"
        order = (conn.execute("SELECT MAX(sort_order) FROM project_status").fetchone()[0] or 0) + 10
        conn.execute("INSERT INTO project_status (status_id, name, indicator, is_default, is_closed, no_time, inactive, sort_order)"
                     " VALUES (?,?,?,?,?,?,?,?)", (status_id, name, indicator, int(is_default), int(is_closed), int(no_time),
                                                   int(inactive), order))
    else:
        if conn.execute("SELECT 1 FROM project_status WHERE status_id = ?", (status_id,)).fetchone() is None:
            raise Refused("No such project status.")
        conn.execute("UPDATE project_status SET name = ?, indicator = ?, is_default = ?, is_closed = ?, no_time = ?,"
                     " inactive = ? WHERE status_id = ?", (name, indicator, int(is_default), int(is_closed), int(no_time),
                                                          int(inactive), status_id))
    if is_default:
        conn.execute("UPDATE project_status SET is_default = 0 WHERE status_id <> ?", (status_id,))
    db.audit(conn, at=_stamp(at), actor=actor, action="PROJECT_SETUP", subject_kind="project_status",
             subject_id=status_id, detail=f"status {name}")
    return status_id


def save_simple(conn, table: str, key: str | None, *, name: str, inactive: bool = False, is_default: bool | None = None,
                at: datetime, actor: str) -> str:
    """Add or change a project type or project role in Setup."""
    if table not in ("project_type", "project_role"):
        raise Refused("No such setup table.")
    ensure_vocabulary(conn)
    idcol = "type_id" if table == "project_type" else "role_id"
    name = " ".join((name or "").split())[:100]
    if not name:
        raise Refused("It needs a name.")
    if key is None:
        base = "".join(ch if ch.isalnum() else "_" for ch in name.upper())[:40].strip("_") or "ROW"
        key, n = base, 1
        while conn.execute(f"SELECT 1 FROM {table} WHERE {idcol} = ?", (key,)).fetchone():
            n += 1
            key = f"{base}_{n}"
        conn.execute(f"INSERT INTO {table} ({idcol}, name, inactive) VALUES (?,?,?)", (key, name, int(inactive)))
    else:
        if conn.execute(f"SELECT 1 FROM {table} WHERE {idcol} = ?", (key,)).fetchone() is None:
            raise Refused("No such row.")
        conn.execute(f"UPDATE {table} SET name = ?, inactive = ? WHERE {idcol} = ?", (name, int(inactive), key))
    if table == "project_type" and is_default is not None:
        conn.execute("UPDATE project_type SET is_default = CASE WHEN type_id = ? THEN ? ELSE 0 END",
                     (key, int(is_default))) if is_default else \
            conn.execute("UPDATE project_type SET is_default = 0 WHERE type_id = ?", (key,))
    db.audit(conn, at=_stamp(at), actor=actor, action="PROJECT_SETUP", subject_kind=table, subject_id=key, detail=name)
    return key


def set_type(conn, project_id: str, type_id: str | None, *, at: datetime, actor: str) -> str:
    p = get(conn, project_id)
    if p is None:
        raise Refused("No such project.")
    type_id = type_id or None
    if type_id and not conn.execute("SELECT 1 FROM project_type WHERE type_id = ?", (type_id,)).fetchone():
        raise Refused("No such project type.")
    if _col(p, "project_type_id") == type_id:
        return "nothing changed"
    conn.execute("UPDATE project SET project_type_id = ? WHERE project_id = ?", (type_id, project_id))
    _audit(conn, at, actor, project_id, f"type {type_id or '-'}")
    return f"type {type_id or 'none'}"


# ------------------------------------------------------------------ issues

def issues(conn, project_id: str) -> list:
    return conn.execute("SELECT * FROM project_issue WHERE project_id = ? ORDER BY status DESC, issue_id DESC",
                        (project_id,)).fetchall()


def add_issue(conn, project_id: str, *, summary: str, details: str | None = None, assigned_to: str | None = None,
              at: datetime, actor: str) -> int:
    if get(conn, project_id) is None:
        raise Refused("No such project.")
    summary = " ".join((summary or "").split())[:200]
    if not summary:
        raise Refused("An issue needs a summary.")
    cur = conn.execute("INSERT INTO project_issue (project_id, summary, details, assigned_to, raised_by, raised_at)"
                       " VALUES (?,?,?,?,?,?)", (project_id, summary, (details or "").strip() or None,
                                                 (assigned_to or "").strip() or None, actor, _stamp(at)))
    _audit(conn, at, actor, project_id, f"issue raised: {summary}")
    return cur.lastrowid


def set_issue_status(conn, project_id: str, issue_id: int, closed: bool, *, at: datetime, actor: str) -> str:
    row = conn.execute("SELECT summary, status FROM project_issue WHERE issue_id = ? AND project_id = ?",
                       (issue_id, project_id)).fetchone()
    if row is None:
        raise Refused("No such issue.")
    want = "CLOSED" if closed else "OPEN"
    if row["status"] == want:
        return "nothing changed"
    conn.execute("UPDATE project_issue SET status = ? WHERE issue_id = ?", (want, issue_id))
    words = f"issue {'closed' if closed else 'reopened'}: {row['summary']}"
    _audit(conn, at, actor, project_id, words)
    return words


def issue_to_ticket(conn, project_id: str, issue_id: int, *, phase_id: int | None = None, at: datetime, actor: str) -> str:
    """Turn an issue into a project ticket, as the reference PSA converts one; the issue closes and points at it."""
    row = conn.execute("SELECT * FROM project_issue WHERE issue_id = ? AND project_id = ?", (issue_id, project_id)).fetchone()
    if row is None:
        raise Refused("No such issue.")
    if row["work_item_id"]:
        raise Refused(f"That issue is already ticket {row['work_item_id']}.")
    wid = open_ticket(conn, project_id, summary=row["summary"], phase_id=phase_id, owner=row["assigned_to"],
                      description=row["details"], at=at, actor=actor)
    conn.execute("UPDATE project_issue SET work_item_id = ?, status = 'CLOSED' WHERE issue_id = ?", (wid, issue_id))
    _audit(conn, at, actor, project_id, f"issue made ticket {wid}: {row['summary']}")
    return wid
