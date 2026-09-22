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


def require_sysadmin(ctx):
    from .. import HttpError
    if not ctx.user.is_sysadmin:
        raise HttpError("403 Forbidden",
                        "This is a cross-board setting; a system administrator changes it.")


def ticket_sla(ctx, work_item_id: str, *, now: datetime) -> tuple[str, str]:
    """Worst open-clock state for a ticket: ('OK'|'WARN'|'BAD'|'NONE', label).

    Derived every time from the clocks, never read from a column — the same rule
    clocks.py holds to. A breached clock makes the ticket red; a clock past the
    warn fraction but not breached makes it amber; nothing open is neutral.
    """
    worst = "NONE"
    label = "—"
    order = {"NONE": 0, "OK": 1, "WARN": 2, "BAD": 3}
    for row in ctx.conn.execute(
            "SELECT clock_id, clock FROM ticket_clock"
            " WHERE work_item_id = ? AND stopped_at IS NULL", (work_item_id,)):
        st = clocks.state_of(ctx.conn, row["clock_id"], as_of=now)
        target = st["target_minutes"] or 1
        used = st["elapsed_minutes"]
        if st["breached"]:
            state = "BAD"
        elif used >= WARN_FRACTION * target:
            state = "WARN"
        else:
            state = "OK"
        if order[state] > order[worst]:
            worst = state
            remaining = st["remaining_minutes"]
            label = (f"{row['clock']} over by {-remaining}m" if remaining < 0
                     else f"{row['clock']} {remaining}m left")
    return worst, label


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
