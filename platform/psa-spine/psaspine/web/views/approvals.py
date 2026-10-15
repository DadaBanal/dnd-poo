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


def _mine(ctx, approval_id):
    """The approval, if this person is the one asked; otherwise 404, so somebody
    else's request is not theirs to learn exists."""
    from .. import HttpError
    try:
        row = approvals.get(ctx.conn, int(approval_id))
    except ValueError:
        row = None
    ids = {i.lower() for i in _identities(ctx) if i}
    if row is None or (row["approver"] or "").lower() not in ids:
        raise HttpError("404 Not Found", "No such approval.")
    return row


def _files(ctx, work_item_id: str):
    """What the approver may open (PMO, 15 Oct 2026): files cleared by review,
    and the ones they added themselves. Never a withheld or unchecked file --
    the enhancement gives them no more than that."""
    ids = [i.lower() for i in _identities(ctx) if i]
    return ctx.conn.execute(
        "SELECT * FROM attachment WHERE work_item_id = ? AND review_status <> 'WITHHELD' AND purged_at IS NULL"
        " AND (review_status = 'CLEARED' OR LOWER(uploaded_by) IN (%s))"
        " ORDER BY attachment_id" % ",".join("?" * len(ids) or ["NULL"]),
        [work_item_id] + ids).fetchall()


def _pictures(ctx, aid: int, work_item_id: str, shared):
    """An email's pictures in the thread: the visible files shown in place, a
    short line where any other one sits (the portal's own rule)."""
    from ... import attachments
    known = attachments.by_content_id(ctx.conn, work_item_id)
    visible = {str(f["attachment_id"]) for f in shared}

    def resolve(cid):
        r = known.get(str(cid).lower())
        if r is None:
            return None, None
        if str(r["attachment_id"]) in visible and str(r["media_type"] or "").startswith("image/"):
            return f"/my/approvals/{aid}/file/{r['attachment_id']}", None
        if r["review_status"] == "WITHHELD" or r["purged_at"]:
            return None, "a picture that is not shown here"
        return None, "a picture, shown here once it has been checked"
    return resolve


def _thread(ctx, r, shared) -> str:
    """The whole request as the approver needs it to decide (PMO, 15 Oct 2026,
    "Buong Ticket Thread sa Approval View"): the original request and every
    entry the requester can read -- their words, the desk's Discussion and
    Resolution notes, never an Internal note or a system event -- with the
    approval asks and withdrawals, in time order, each with who and when."""
    wid, aid = r["work_item_id"], r["approval_id"]
    events = ctx.conn.execute(
        "SELECT occurred_at, kind, actor, detail, note_flag, is_resolution, body_format, ticket_event_id FROM ticket_event"
        "  WHERE work_item_id = ?"
        "    AND (kind IN ('INTAKE','INTAKE_REPLY','PORTAL_REPLY')"
        "         OR note_flag IN ('DISCUSSION','RESOLUTION'))"
        "    AND (note_flag IS NULL OR note_flag <> 'INTERNAL')"
        "  ORDER BY ticket_event_id", (wid,)).fetchall()
    asked = approvals.for_ticket(ctx.conn, wid)
    approvers = {(a["approver"] or "").lower() for a in asked}
    raised_by = r["raised_by"] or "the requester"
    pictures = _pictures(ctx, aid, wid, shared)
    entries = []
    for e in events:
        if e["kind"] in ("INTAKE", "INTAKE_REPLY", "PORTAL_REPLY"):
            who, cls = raised_by, "by-req"
        elif (e["actor"] or "").lower() in approvers:
            who, cls = e["actor"], "by-staff"
        else:
            who = r["board_name"] + (" — resolution" if e["note_flag"] == "RESOLUTION" or e["is_resolution"] else "")
            cls = "by-staff"
        label = "Email" if e["kind"] in ("INTAKE", "INTAKE_REPLY") else ""
        entries.append((str(e["occurred_at"] or ""), 0, e["ticket_event_id"],
                        f"<li class={cls}><div class=rtx>{t.note_html(e['detail'], e['body_format'], kind=e['kind'], images=pictures, label=label)}</div>"
                        f"<div class=meta>{t.esc(who)} &middot; {t.esc(e['occurred_at'])}</div></li>"))
    for a in asked:
        words = f"Approval asked of {a['approver']}" + (f": {a['reason']}" if a["reason"] else "")
        entries.append((str(a["requested_at"] or ""), 1, a["approval_id"],
                        f"<li class=by-staff><div>{t.icon('check')}{t.esc(words)}</div>"
                        f"<div class=meta>{t.esc(a['requested_by'])} &middot; {t.esc(a['requested_at'])}</div></li>"))
        if a["status"] == "WITHDRAWN":
            entries.append((str(a["decided_at"] or ""), 1, a["approval_id"],
                            f"<li class=by-staff><div>The desk withdrew the request to {t.esc(a['approver'])}</div>"
                            f"<div class=meta>{t.esc(a['decided_by'])} &middot; {t.esc(a['decided_at'])}</div></li>"))
    entries.sort(key=lambda x: (x[0], x[1], x[2]))
    stream = "".join(x[3] for x in entries) or "<li class=muted>Nothing written on the request yet.</li>"
    n = len(entries)
    return (f"<details class=acontext open><summary>The request and what has happened"
            f" <span class=muted>({n} {'entry' if n == 1 else 'entries'})</span></summary>"
            f"<div class=athread tabindex=0 role=region aria-label='The request {t.esc(wid)} and what has happened'>"
            f"<ul class=stream>{stream}</ul></div></details>")


def _files_block(r, shared) -> str:
    if not shared:
        return ""
    from . import files as _f
    aid = r["approval_id"]
    return ("<h4 class=afiles>" + t.icon("paperclip") + "Files</h4><ul class=plain>" + "".join(
        "<li>" + _f.file_link(f"/my/approvals/{aid}/file/{f['attachment_id']}", f) + "</li>" for f in shared) + "</ul>")


def _add_file(aid: int) -> str:
    return (f"<label for=afile-{aid}>Add a file to your decision, if it helps <span class=muted>(optional)</span></label>"
            f"<input id=afile-{aid} type=file name=file multiple>"
            "<p class=why style='margin:0'>Up to 10 MB each. It goes on the request, and the desk checks it"
            " for patient information before anyone else can open it.</p>")


def portal_index(ctx):
    from .. import Response
    from . import files as _f
    q = ctx.request.query
    ids = _identities(ctx)
    waiting = approvals.waiting_for(ctx.conn, ids)
    done = approvals.decided_by(ctx.conn, ids)
    cards, viewable = [], False
    for r in waiting:
        shared = _files(ctx, r["work_item_id"])
        viewable = viewable or any(_f.view_kind(f["media_type"]) for f in shared)
        cards.append(
            f"<div class=card><h3>{t.icon('check')}{t.esc(r['work_item_id'])} · {t.esc(r['summary'])}</h3>"
            f"<p class=muted>Raised by {t.esc(r['raised_by'] or 'the desk')} · {t.esc(r['board_name'])} · asked {t.esc(r['requested_at'])}"
            + (f"<br>{t.esc(r['reason'])}" if r["reason"] else "") + "</p>"
            + _thread(ctx, r, shared) + _files_block(r, shared) +
            f"<form method=post action='/my/approvals/{r['approval_id']}/decide' class=stack style='max-width:none'"
            " enctype='multipart/form-data'>"
            f"<label for=anote-{r['approval_id']}>A reason or conditions (needed to decline)</label>"
            f"<input id=anote-{r['approval_id']} name=note maxlength=500>" + _add_file(r["approval_id"]) +
            "<div><button type=submit name=decision value=APPROVE>Approve</button> "
            "<button class='ghost danger' type=submit name=decision value=DECLINE>Decline</button></div></form></div>")
    rows = "".join(cards) + (_f.viewer_dialog() if viewable else "")
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
        row = approvals.decide(ctx.conn, aid, f.get("decision", ""), identities=_identities(ctx), at=ctx.now, note=f.get("note"))
        # PMO, 15 Oct 2026 (request 2): a file with the decision. Kept only once
        # the decision is, as the approver's own, awaiting the desk's review.
        refused = _keep_files(ctx, row["work_item_id"], row["approver"])
        ctx.conn.commit()
    except (approvals.Refused, ValueError) as exc:
        ctx.conn.rollback()
        return redirect("/my/approvals?" + urllib.parse.urlencode({"err": str(exc) or "No such approval."}))
    except Exception as exc:                                        # noqa: BLE001
        ctx.conn.rollback()
        return redirect("/my/approvals?" + urllib.parse.urlencode({"err": f"Not recorded: {exc}"}))
    word = "Approved" if f.get("decision") == "APPROVE" else "Declined"
    q = {"msg": f"{word}. The desk and the requester have been told."}
    if refused:
        q["err"] = " ".join(refused)
    return redirect("/my/approvals?" + urllib.parse.urlencode(q))


def _keep_files(ctx, work_item_id: str, approver: str) -> list[str]:
    """The files sent with a decision. Returns a sentence per file not kept."""
    from ... import attachments
    refused = []
    for filename, data in ctx.request.files("file"):
        if not filename and not data:
            continue                                                # the empty field a browser sends
        try:
            attachments.add(ctx.conn, work_item_id, data, filename, actor=approver, at=ctx.now, source="PORTAL")
        except attachments.Refused as exc:
            refused.append(f"{attachments.safe_name(filename)} was not kept: {exc}.")
    return refused


def portal_file(ctx, approval_id, attachment_id):
    """A file on the request, for the person asked to approve it: only what
    `_files` lists, so a withheld or unchecked file is a 404 here too."""
    from .. import HttpError
    from . import files as _f
    row = _mine(ctx, approval_id)
    match = [x for x in _files(ctx, row["work_item_id"]) if str(x["attachment_id"]) == str(attachment_id)]
    if not match:
        raise HttpError("404 Not Found", "No such file.")
    board_id = _board_of(ctx, row["work_item_id"])
    return _f.serve(ctx, match[0], board_id=board_id)
