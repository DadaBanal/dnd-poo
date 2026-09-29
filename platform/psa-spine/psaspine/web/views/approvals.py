"""Approvals (049): the card on a ticket, and the approver's page on the portal.

A technician asks (or the catalogue asks for them); the approver, signed in to
the portal, decides under Approvals with a reason. Nobody else can decide it,
and the desk can withdraw the question.
"""
from __future__ import annotations

import urllib.parse

from ... import approvals
from .. import templates as t
from . import common

CHIP = {"PENDING": "sla-warn", "APPROVED": "sla-ok", "DECLINED": "sla-bad", "WITHDRAWN": ""}


def _chip(status: str) -> str:
    return f"<span class='chip {CHIP.get(status, '')}'>{t.esc(approvals.STATUSES.get(status, status))}</span>"


def _board_of(ctx, work_item_id: str) -> str:
    from .. import HttpError
    row = ctx.conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?", (work_item_id,)).fetchone()
    if row is None:
        raise HttpError("404 Not Found", "No such ticket.")
    return row[0]


def ticket_card(ctx, tk, *, can_work: bool) -> str:
    wid = tk["work_item_id"]
    rows = approvals.for_ticket(ctx.conn, wid)
    items = "".join(
        f"<li>{_chip(r['status'])} {t.esc(r['approver'])} <span class=muted>· asked {t.esc(r['requested_at'])} by {t.esc(r['requested_by'])}</span>"
        + (f"<br><span class=muted>{t.esc(r['reason'])}</span>" if r["reason"] else "")
        + (f"<br>{t.esc(r['decided_at'])} · {t.esc(r['decided_by'])}" + (f": {t.esc(r['note'])}" if r["note"] else "")
           if r["decided_at"] else "") + "</li>" for r in rows)
    form = ""
    if can_work:
        p = approvals.pending(ctx.conn, wid)
        if p is not None:
            form = (f"<form method=post action='/ticket/{t.esc(wid)}/approval/withdraw' class=inline style='margin-top:8px'>"
                    f"<input type=hidden name=approval_id value={p['approval_id']}>"
                    "<button class='ghost small' type=submit>Withdraw the request</button></form>")
        elif tk["state"] not in approvals.CLOSED_STATES:
            suggested = approvals.approver_for(ctx.conn, wid) or ""
            form = (f"<form method=post action='/ticket/{t.esc(wid)}/approval/request' class=fields style='margin-top:8px'>"
                    f"<label>Ask for approval from</label><input name=approver value='{t.esc(suggested)}' placeholder='an email at the hospital' required>"
                    "<label>Why</label><input name=reason maxlength=500 placeholder='what they are approving'>"
                    "<div style='margin-top:8px'><button class=ghost type=submit>Ask</button></div></form>"
                    + ("" if suggested else "<p class=why style='margin:6px 0 0'>The requester's department names no approver yet "
                                             "(Setup › Departments), so type one.</p>"))
    return ("<div class=card data-pod=approval><h3>" + t.icon("check") + "Approval</h3>"
            + (f"<ul class=plain>{items}</ul>" if items else "<div class=muted>No approval asked for.</div>") + form + "</div>")


def _back(work_item_id: str, **q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    return redirect(f"/ticket/{work_item_id}" + ("?" + urllib.parse.urlencode(q) if q else ""))


def request(ctx, work_item_id):
    common.require_board(ctx, _board_of(ctx, work_item_id), need="WORK")
    f = ctx.request.form()
    try:
        approvals.request(ctx.conn, work_item_id, approver=f.get("approver"), reason=f.get("reason"), at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except approvals.Refused as exc:
        ctx.conn.rollback()
        return _back(work_item_id, err=str(exc))
    except Exception as exc:                                        # noqa: BLE001
        ctx.conn.rollback()
        return _back(work_item_id, err=f"Not asked: {exc}")
    return _back(work_item_id, msg="Approval asked for; the ticket waits on it")


def withdraw(ctx, work_item_id):
    common.require_board(ctx, _board_of(ctx, work_item_id), need="WORK")
    f = ctx.request.form()
    try:
        aid = int(f.get("approval_id", ""))
        row = approvals.get(ctx.conn, aid)
        if row is None or row["work_item_id"] != work_item_id:
            raise approvals.Refused("No such approval on this ticket.")
        approvals.withdraw(ctx.conn, aid, at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except (approvals.Refused, ValueError) as exc:
        ctx.conn.rollback()
        return _back(work_item_id, err=str(exc) if str(exc) else "No such approval.")
    return _back(work_item_id, msg="Approval request withdrawn")


# ------------------------------------------------------------ the portal

def _identities(ctx) -> list[str]:
    from .portal import _identities as ids
    return ids(ctx)


def portal_index(ctx):
    from .. import Response
    q = ctx.request.query
    ids = _identities(ctx)
    waiting = approvals.waiting_for(ctx.conn, ids)
    done = approvals.decided_by(ctx.conn, ids)
    rows = "".join(
        f"<div class=card><h3>{t.icon('check')}{t.esc(r['work_item_id'])} · {t.esc(r['summary'])}</h3>"
        f"<p class=muted>Raised by {t.esc(r['raised_by'] or 'the desk')} · {t.esc(r['board_name'])} · asked {t.esc(r['requested_at'])}"
        + (f"<br>{t.esc(r['reason'])}" if r["reason"] else "") + "</p>"
        f"<form method=post action='/my/approvals/{r['approval_id']}/decide' class=stack style='max-width:none'>"
        "<label>A reason or conditions (needed to decline)<input name=note maxlength=500></label>"
        "<div><button type=submit name=decision value=APPROVE>Approve</button> "
        "<button class='ghost danger' type=submit name=decision value=DECLINE>Decline</button></div></form></div>"
        for r in waiting)
    history = ""
    if done:
        history = ("<div class=card><h3>" + t.icon("clock") + "Decided</h3><ul class=plain>" + "".join(
            f"<li>{_chip(r['status'])} {t.esc(r['work_item_id'])} {t.esc(r['summary'])} <span class=muted>· {t.esc(r['decided_at'])}"
            + (f" · {t.esc(r['note'])}" if r["note"] else "") + "</span></li>" for r in done) + "</ul></div>")
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + "<h1>Approvals</h1><p class=sub>Requests that wait for your yes before the desk does the work. "
              "Your decision and your reason go on the request, where the person who raised it can read them.</p>"
            + (rows or "<div class=card><div class=empty>Nothing waits for you.</div></div>") + history)
    return Response(body=t.page("Approvals", body, user=ctx.user, active="approvals"))


def portal_decide(ctx, approval_id):
    from .. import redirect
    f = ctx.request.form()
    try:
        aid = int(approval_id)
        approvals.decide(ctx.conn, aid, f.get("decision", ""), identities=_identities(ctx), at=ctx.now, note=f.get("note"))
        ctx.conn.commit()
    except (approvals.Refused, ValueError) as exc:
        ctx.conn.rollback()
        return redirect("/my/approvals?" + urllib.parse.urlencode({"err": str(exc) or "No such approval."}))
    except Exception as exc:                                        # noqa: BLE001
        ctx.conn.rollback()
        return redirect("/my/approvals?" + urllib.parse.urlencode({"err": f"Not recorded: {exc}"}))
    word = "Approved" if f.get("decision") == "APPROVE" else "Declined"
    return redirect("/my/approvals?" + urllib.parse.urlencode({"msg": f"{word}. The desk and the requester have been told."}))
