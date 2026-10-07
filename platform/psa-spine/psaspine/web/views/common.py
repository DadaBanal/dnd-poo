"""What the views share, and the access rule that must never be bypassed.

The one load-bearing function here is `board_ids_for`. A restricted board is a
PHI-bearing board, and the acceptance test the record wrote and never ran (§11
test 5) is that a departmental fulfiller is PROVABLY excluded from it. So board
and ticket visibility is filtered by `board_member` at the query, for everyone,
including a break-glass sysadmin. A sysadmin flag unlocks the cross-board CONFIG
surfaces — calendars, floors, catalogue — and nothing about a restricted board's
tickets. That keeps the exclusion absolute rather than "absolute unless someone
is an admin", which is the version that leaks.
"""
from __future__ import annotations

from datetime import datetime

from ... import clocks, db

# Fraction of a target at which a still-running clock turns amber.
WARN_FRACTION = 0.8


def board_ids_for(ctx) -> set[str]:
    """The boards this user may see, ever. Membership only — never widened by the
    sysadmin flag, because a restricted board's contents are exactly what that
    flag must not reach."""
    return {r["board_id"] for r in ctx.conn.execute(
        "SELECT board_id FROM board_member WHERE member = ?", (ctx.user.id,))}


def project_board_ids(ctx) -> set[str]:
    """The project boards this person is on. A project board is its own setup
    table in the reference PSA, apart from service boards: its tickets are
    worked from Projects, never from the Service Board (Dada, 7 Oct 2026: "the
    project board isnt a service board")."""
    ids = board_ids_for(ctx)
    if not ids:
        return set()
    return {r[0] for r in ctx.conn.execute(
        f"SELECT board_id FROM board WHERE kind = 'PROJECT' AND board_id IN ({','.join('?' * len(ids))})", sorted(ids))}


def service_board_ids(ctx) -> set[str]:
    """The boards the Service Board shows: every board the person is on except project boards."""
    return board_ids_for(ctx) - project_board_ids(ctx)


def may_access_board(ctx, board_id: str, *, need: str = "READ") -> bool:
    rank = {"READ": 0, "WORK": 1, "ADMIN": 2}
    row = ctx.conn.execute(
        "SELECT access FROM board_member WHERE member = ? AND board_id = ?",
        (ctx.user.id, board_id)).fetchone()
    if row is None:
        return False
    return rank.get(row["access"], -1) >= rank[need]


def is_restricted(ctx, board_id: str) -> bool:
    row = ctx.conn.execute("SELECT restricted FROM board WHERE board_id = ?",
                           (board_id,)).fetchone()
    return bool(row and row["restricted"])


def audit_restricted_reads(ctx, board_ids, *, detail: str) -> None:
    """One RESTRICTED_READ row per restricted board a list touched, with the
    count: a report, a project's ticket list or an article's Used-on shows
    many tickets at once, and one row per board says which and how many."""
    counts: dict = {}
    for b in board_ids:
        counts[b] = counts.get(b, 0) + 1
    for b, n in sorted(counts.items()):
        audit_restricted_read(ctx, b, detail=f"{detail} {n} ticket(s)")


def audit_restricted_read(ctx, board_id: str, *, subject_id: str | None = None,
                          detail: str | None = None) -> None:
    """§6.1 requirement 4: every read of a restricted ticket is audited.

    In a hospital who looked is as material as who changed, and an access control
    that leaves no trace cannot answer the only question that matters after the
    fact — who saw this patient's ticket. Unrestricted boards write nothing: an
    audit log that records every printer fault is one nobody reads.

    This records a read that was ALLOWED. A refused one raises 404 above and is
    not a read at all; the board never appeared.
    """
    if not is_restricted(ctx, board_id):
        return
    db.audit(ctx.conn,
             at=ctx.now.isoformat(sep=" ", timespec="minutes"),
             actor=ctx.user.id,
             action="RESTRICTED_READ",
             subject_kind="ticket" if subject_id else "board",
             subject_id=subject_id or board_id,
             detail=detail or f"read on restricted board {board_id}"
                              f" via {ctx.user.via}")
    ctx.conn.commit()


def require_board(ctx, board_id: str, *, need: str = "READ",
                  subject_id: str | None = None):
    from .. import HttpError
    if not may_access_board(ctx, board_id, need=need):
        # 404, not 403: a fulfiller who is not on a restricted board should not
        # even learn the ticket exists. Absence is the honest answer.
        raise HttpError("404 Not Found", "No such ticket.")
    audit_restricted_read(ctx, board_id, subject_id=subject_id)


def module_level(ctx, module: str) -> str:
    levels = getattr(ctx.user, "modules", None)
    if levels is None:
        from ... import security
        return security.level(ctx.conn, ctx.user, module)
    return levels.get(module, "NONE")


def allows(ctx, module: str, need: str = "READ") -> bool:
    from ... import security
    return security.RANK[module_level(ctx, module)] >= security.RANK[need]


def require_module(ctx, module: str, need: str = "READ"):
    """The security role gate (040). 403 with the module and level in words, so
    the person knows what to ask their service manager for."""
    from .. import HttpError
    from ... import security
    if not allows(ctx, module, need):
        words = {"READ": "see", "WRITE": "change", "ADMIN": "administer"}[need]
        raise HttpError("403 Forbidden", f"Your security role does not let you {words} "
                                         f"{security.MODULES[module].lower()}. Ask your service manager.")


def require_sysadmin(ctx):
    from .. import HttpError
    if not ctx.user.is_sysadmin:
        raise HttpError("403 Forbidden",
                        "This is a cross-board setting; a system administrator changes it.")


CLOCK_ORDER = {"RESPOND": 0, "ACKNOWLEDGE": 1, "RESOLUTION_PLAN": 2, "RESOLVE": 3,
               "DECISION": 4}
CLOCK_NAME = {"RESPOND": "Respond", "RESOLUTION_PLAN": "Resolution plan",
              "RESOLVE": "Resolve", "ACKNOWLEDGE": "Acknowledge", "DECISION": "Decision"}


def fmt_minutes(m: int) -> str:
    m = abs(int(m))
    if m < 60:
        return f"{m}m"
    if m < 60 * 48:
        h, r = divmod(m, 60)
        return f"{h}h" + (f" {r:02d}m" if r and h < 10 else "")
    return f"{m // 1440}d"


def clock_states_many(conn, work_item_ids, *, now: datetime) -> dict[str, list[dict]]:
    """clock_states for many tickets in three queries, however many tickets.
    The board and dispatch use this; one ticket's screen uses the wrapper."""
    raw = clocks.states_many(conn, work_item_ids, as_of=now)
    return {wid: [_present(st) for st in sorted(sts, key=lambda s: CLOCK_ORDER.get(s["clock"], 9))]
            for wid, sts in raw.items()}


def clock_states(conn, work_item_id: str, *, now: datetime) -> list[dict]:
    """Every clock on a ticket, each with its own state, computed now.

    MET / MISSED for a stopped clock (inside or outside target), OK / WARN / BAD
    for a running one, PAUSED while a waiting status holds it. Never read from a
    stored flag: a flag goes stale the moment a target or a calendar is fixed.
    """
    return clock_states_many(conn, [work_item_id], now=now)[work_item_id]


def _present(st: dict) -> dict:
    if True:
        row = st
        target = st["target_minutes"] or 1
        used = st["elapsed_minutes"]
        left = st["remaining_minutes"]
        if st["stopped_at"]:
            state = "MISSED" if st["breached"] else "MET"
            short = fmt_minutes(used)
            text = (f"Missed by {fmt_minutes(-left)}" if st["breached"]
                    else f"Met in {fmt_minutes(used)}")
        elif st["paused"]:
            state, short, text = "PAUSED", "paused", f"Paused at {fmt_minutes(left)} left"
            if st["breached"]:
                state, text = "BAD", f"Breached by {fmt_minutes(-left)} (paused)"
        elif st["breached"]:
            state, short = "BAD", "-" + fmt_minutes(-left)
            text = f"Breached by {fmt_minutes(-left)}"
        else:
            state = "WARN" if used >= WARN_FRACTION * target else "OK"
            short, text = fmt_minutes(left), f"{fmt_minutes(left)} left"
        name = CLOCK_NAME.get(row["clock"], row["clock"])
        return {"clock": row["clock"], "name": name, "state": state, "short": short,
                "text": text, "target": st["target_minutes"], "used": used,
                "fraction": min(1.0, used / target),
                "title": f"{name}: {text} (target {fmt_minutes(st['target_minutes'])})"}


WORST = {"MET": 0, "PAUSED": 1, "OK": 2, "WARN": 3, "MISSED": 4, "BAD": 5}


def worst_state(states: list[dict]) -> str:
    """The row colour: the worst of the clocks. A missed clock stays red once
    stopped, because a breach that happened is not undone by closing it."""
    if not states:
        return "NONE"
    w = max(states, key=lambda s: WORST[s["state"]])["state"]
    return {"MET": "OK", "PAUSED": "OK", "OK": "OK", "WARN": "WARN",
            "MISSED": "BAD", "BAD": "BAD"}[w]


def ticket_sla(ctx, work_item_id: str, *, now: datetime) -> tuple[str, str]:
    """Worst open-clock state for a ticket: ('OK'|'WARN'|'BAD'|'NONE', label).
    Kept for the dispatch view and older callers."""
    states = [s for s in clock_states(ctx.conn, work_item_id, now=now)
              if s["state"] not in ("MET", "MISSED")]
    if not states:
        return "NONE", "—"
    worst = max(states, key=lambda s: WORST[s["state"]])
    label = f"{worst['clock']} {worst['text'].lower()}"
    return worst_state(states), label


def no_clock_reason(conn, board_id: str, source_ref) -> str:
    """Why a ticket has no clock, in words, instead of a bare 'no clock'."""
    if source_ref:
        return "imported"
    row = conn.execute("SELECT calendar_id, kind FROM board WHERE board_id = ?",
                       (board_id,)).fetchone()
    if row is not None and row["kind"] in ("CHANGE", "PROJECT"):
        return f"a {row['kind'].lower()} board runs no SLA clock"
    if row is None or row["calendar_id"] is None:
        return "board not set up"
    return "no target"


def human_age(opened_at: str, *, now: datetime) -> str:
    try:
        start = clocks.parse_instant(opened_at)
    except (ValueError, TypeError):
        return "—"
    minutes = int((now - start).total_seconds() // 60)
    if minutes < 0:
        return "—"
    if minutes < 60:
        return f"{minutes}m"
    if minutes < 60 * 48:
        return f"{minutes // 60}h"
    return f"{minutes // (60 * 24)}d"


def public_url(ctx) -> str:
    """The desk's address as a person types it: the deployment's public URL
    when one is named, else the host this request came to."""
    base = getattr(ctx.config, "public_url", None)
    if base:
        return base.rstrip("/")
    return f"{ctx.request.scheme}://{ctx.request.public_host}"


def owner_select(conn, board_ids, current: str | None = None, *, name: str = "owner",
                 blank: str = "(nobody: the board's queue)", attrs: str = "", me: str | None = None) -> str:
    """A select of the people who may take work: the WORK and ADMIN members of
    these boards who are not deactivated, by name. The current owner stays
    selectable, marked, if they no longer work the board; the blank choice
    leaves the ticket in the queue."""
    from ... import board as _board
    from ... import members as _members
    from .. import templates as t
    seen: dict[str, str] = {}
    for b in board_ids:
        for m in _board._working_members(conn, b):
            seen.setdefault(m.lower(), m)
    people = sorted(((_members.name_of(conn, m), m) for m in seen.values()), key=lambda x: x[0].lower())
    cur = (current or "").strip()
    opts = [f"<option value=''{' selected' if not cur else ''}>{t.esc(blank)}</option>"]
    if me and me.lower() in seen:
        # The signed-in person first: "take it myself" is the commonest choice.
        people = [(lbl, m) for lbl, m in people if m.lower() == me.lower()] + \
                 [(lbl, m) for lbl, m in people if m.lower() != me.lower()]
    for label, m in people:
        shown = label if label.lower() == m.lower() else f"{label} ({m})"
        if me and m.lower() == me.lower():
            shown = f"Me - {shown}"
        opts.append(f"<option value='{t.esc(m)}'{' selected' if m.lower() == cur.lower() else ''}>{t.esc(shown)}</option>")
    if cur and cur.lower() not in seen:
        opts.append(f"<option value='{t.esc(cur)}' selected>{t.esc(_members.name_of(conn, cur))} (not working this board)</option>")
    return f"<select name={name}{attrs}>" + "".join(opts) + "</select>"
