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
           ends_on=None, budget_hours=None, description: str | None = None, at: datetime, actor: str) -> str:
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
    _audit(conn, at, actor, pid, f"project created: {name}")
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
    where = "parent_id IS ?" if row["parent_id"] is None else "parent_id = ?"
    sibs = conn.execute(f"SELECT phase_id, name FROM project_phase WHERE project_id = ? AND {where}"
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
