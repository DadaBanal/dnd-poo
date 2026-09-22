"""The requester portal -- the surface the other four hundred people use.

Every other view in this package answers "which boards may this fulfiller see".
This one inverts that: a requester sees **their own tickets and nothing else**,
never a board, never a queue, never somebody else's request. The filter is
`ticket.requested_by`, applied at the query, for the same reason the board
filter is: an access rule the interface is trusted to honour is not an access
rule.

Two things it does that the fulfiller views deliberately do not:

  * **It reads `board_status.customer_description`, not `name`.** 006 added that
    column precisely for this: internally a status may be "Awaiting parts from
    vendor, PO raised"; on the portal it is "We are waiting on a delivery".
    Without it you either leak internal language to four hundred clinical staff
    or you write statuses too vague to be useful to the people working. Where a
    board has not written one, the portal says the lifecycle state rather than
    inventing a sentence.

  * **It warns about PHI before it is submitted, and still accepts it.** §6.1
    says a ticket references a patient record and never carries one. Refusing
    the submission would send the requester to the phone, where the same
    identifier travels with no record at all; so the detection flags it, the
    ticket is created, and the requester is told plainly what happened.
"""
from __future__ import annotations

from ... import numbering, phi, tickets
from .. import templates as t

# What a requester is allowed to see about their own ticket. Deliberately not
# the whole row: no internal status name, no owner, no commercial basis.
MINE = (
    "SELECT t.work_item_id, t.priority, t.state, t.opened_at, t.closed_at,"
    "       w.name AS summary, s.customer_description, s.name AS status_name"
    "  FROM ticket t"
    "  JOIN work_item w ON w.work_item_id = t.work_item_id"
    "  LEFT JOIN board_status s ON s.board_status_id = t.board_status_id")

# The two plain questions (§9: "it asks two questions -- who is affected and is
# a patient waiting -- and never shows a priority dropdown"). The wording is the
# requester's; the codes are the matrix's. Meanings follow the definitions the
# matrix in tickets.py is built from, which are INFERRED from the WS36 paper.
WHO_IS_AFFECTED = (
    ("I3", "Just me"),
    ("I2", "My ward or department, or several people"),
    ("I1", "The whole hospital, or a clinical service is down"),
)
PATIENT_WAITING = (
    ("U3", "No"),
    ("U2", "Yes, but we have a workaround"),
    ("U1", "Yes -- care has stopped, or there is a safety risk"),
)

FRIENDLY_STATE = {
    "NEW": "Received, not yet picked up",
    "TRIAGED": "Received and triaged",
    "IN_PROGRESS": "Someone is working on it",
    "WAITING_CLIENT": "Waiting on you",
    "WAITING_VENDOR": "Waiting on a supplier",
    "RESOLVED": "Resolved",
    "CLOSED": "Closed",
    "CANCELLED": "Cancelled",
}


def _identities(ctx) -> list[str]:
    """Who this person is, as a requester. Email first, because that is what
    intake writes into `requested_by` when a ticket arrives by mail."""
    out = []
    if ctx.user.email:
        out.append(ctx.user.email.lower())
    if ctx.user.id and ctx.user.id.lower() not in out:
        out.append(ctx.user.id.lower())
    return out


def _mine_clause(ctx) -> tuple[str, list]:
    ids = _identities(ctx)
    if not ids:
        return " WHERE 1 = 0", []
    return (" WHERE LOWER(t.requested_by) IN (%s)" % ",".join("?" * len(ids)), ids)


def _status_words(row) -> str:
    """What the requester reads. The board's own sentence if it wrote one."""
    if row["customer_description"]:
        return row["customer_description"]
    return FRIENDLY_STATE.get(row["state"], row["state"])


def index(ctx):
    from .. import Response
    clause, params = _mine_clause(ctx)
    rows = ctx.conn.execute(
        MINE + clause + " ORDER BY t.opened_at DESC", params).fetchall()

    if rows:
        items = "".join(
            "<tr>"
            f"<td><a href='/my/{t.esc(r['work_item_id'])}'>{t.esc(r['work_item_id'])}</a></td>"
            f"<td>{t.esc(r['summary'])}</td>"
            f"<td>{t.chip(_status_words(r))}</td>"
            f"<td class='muted'>{t.esc(r['opened_at'])}</td>"
            "</tr>" for r in rows)
        table = ("<div class='card'><div class='tablewrap'><table><thead><tr>"
                 "<th>Reference</th><th>What you asked for</th><th>Where it is</th>"
                 f"<th>Raised</th></tr></thead><tbody>{items}</tbody></table></div></div>")
    else:
        table = ("<div class='card'><div class='empty'>You have not raised "
                 "anything yet.</div></div>")

    body = ("<h1>Your requests</h1>"
            "<p class='sub'>Everything you have asked IT for, and where each one "
            "has got to.</p>" + _raise_form() + table)
    return Response(body=t.page("Your requests", body, user=ctx.user))


def _raise_form(error: str = "", notice: str = "") -> str:
    err = f"<div class='banner err'>{t.esc(error)}</div>" if error else ""
    note = f"<div class='banner ok'>{t.esc(notice)}</div>" if notice else ""
    return (err + note +
            "<div class='card'><h3>Raise a request</h3>"
            "<form class='stack' method='post' action='/my/new' style='max-width:none'>"
            "<label>What do you need? "
            "<input name='summary' required maxlength='200' "
            "placeholder='Printer in ward 3 is offline'></label>"
            + _radio_group("impact", "Who is affected?", WHO_IS_AFFECTED) +
            _radio_group("urgency", "Is a patient waiting?", PATIENT_WAITING) +
            "<label>Anything that would help us"
            "<textarea name='description' placeholder='Please do not include "
            "patient names or case numbers -- give us the record number if we "
            "need one.'></textarea></label>"
            "<div><button type='submit'>Send it</button></div></form></div>")


def _radio_group(name: str, legend: str, choices) -> str:
    """One required question. `required` on the first radio makes the browser
    insist on an answer; the server insists again, because a browser is not a
    control."""
    opts = "".join(
        f"<label style='font-weight:400;color:var(--ink)'>"
        f"<input type='radio' name='{name}' value='{code}' style='width:auto'"
        f"{' required' if i == 0 else ''}> {t.esc(text)}</label>"
        for i, (code, text) in enumerate(choices))
    return (f"<fieldset style='border:none;padding:0;margin:0'>"
            f"<legend style='font-size:13px;font-weight:600;color:var(--muted)'>"
            f"{t.esc(legend)}</legend>{opts}</fieldset>")


def detail(ctx, work_item_id):
    from .. import HttpError, Response
    clause, params = _mine_clause(ctx)
    row = ctx.conn.execute(
        MINE + clause + " AND t.work_item_id = ?", params + [work_item_id]).fetchone()
    if row is None:
        # 404 and not 403: somebody else's ticket is not theirs to learn exists.
        raise HttpError("404 Not Found", "No such request.")

    events = ctx.conn.execute(
        "SELECT occurred_at, kind, detail FROM ticket_event"
        "  WHERE work_item_id = ? AND kind IN ('INTAKE','INTAKE_REPLY','PORTAL_REPLY')"
        "  ORDER BY ticket_event_id", (work_item_id,)).fetchall()
    stream = "".join(
        f"<li><div>{t.esc(e['detail'])}</div>"
        f"<div class='meta'>{t.esc(e['occurred_at'])}</div></li>"
        for e in events) or "<li class='muted'>Nothing yet.</li>"

    body = (
        f"<h1>{t.esc(row['summary'])}</h1>"
        f"<p class='sub'>{t.esc(work_item_id)} &middot; "
        f"{t.chip(_status_words(row))} &middot; raised {t.esc(row['opened_at'])}</p>"
        f"<div class='card'><h3>What has happened</h3>"
        f"<ul class='stream'>{stream}</ul></div>"
        "<div class='card'><h3>Add something</h3>"
        f"<form class='stack' method='post' action='/my/{t.esc(work_item_id)}/reply' "
        "style='max-width:none'>"
        "<textarea name='body' required placeholder='No patient names or case "
        "numbers, please.'></textarea>"
        "<div><button type='submit'>Send</button></div></form></div>"
        "<p><a href='/my'>All your requests</a></p>")
    return Response(body=t.page(work_item_id, body, user=ctx.user))


def create(ctx):
    from .. import Response, redirect
    form = ctx.request.form()
    summary = form.get("summary", "").strip()
    description = form.get("description", "").strip()
    if not summary:
        return Response("400 Bad Request", t.page(
            "Your requests",
            "<h1>Your requests</h1>" + _raise_form(error="Tell us what you need."),
            user=ctx.user))
    impact = form.get("impact", "")
    urgency = form.get("urgency", "")
    if impact not in dict(WHO_IS_AFFECTED) or urgency not in dict(PATIENT_WAITING):
        return Response("400 Bad Request", t.page(
            "Your requests",
            "<h1>Your requests</h1>" + _raise_form(
                error="Please answer both questions: who is affected, and whether "
                      "a patient is waiting."),
            user=ctx.user))
    # Computed, never chosen: the requester answered two questions and the
    # matrix decides. There is no priority field for them to set.
    priority, priority_source = tickets.compute_priority(impact, urgency)

    board = ctx.conn.execute(
        "SELECT board_id FROM board WHERE is_unrouted = 1").fetchone()
    if board is None:
        return Response("503 Service Unavailable", t.page(
            "Your requests",
            "<h1>Your requests</h1>" + _raise_form(
                error="We cannot take requests right now -- no queue is configured. "
                      "Please ring the desk."),
            user=ctx.user))

    requester = (ctx.user.email or ctx.user.id or "").lower()
    stamp = ctx.now.isoformat(sep=" ", timespec="minutes")
    ticket_id = numbering.issue(ctx.conn, at=ctx.now)
    ctx.conn.execute(
        "INSERT INTO work_item (work_item_id, source, name, contract_basis)"
        " VALUES (?,'desk',?,'UNKNOWN')", (ticket_id, summary))
    ctx.conn.execute(
        "INSERT INTO ticket (work_item_id, board_id, path, impact, urgency,"
        " priority, priority_source, requested_by, requested_at, opened_at, state)"
        " VALUES (?,?,'INCIDENT',?,?,?,?,?,?,?,'NEW')",
        (ticket_id, board["board_id"], impact, urgency, priority, priority_source,
         requester, stamp, stamp))
    numbering.bind(ctx.conn, ticket_id)
    if description:
        ctx.conn.execute(
            "INSERT INTO ticket_event (work_item_id, occurred_at, kind, actor, detail)"
            " VALUES (?,?,'INTAKE',?,?)", (ticket_id, stamp, requester, description))

    # §6.1: flagged, counted, and the requester is told -- not refused. Refusing
    # sends the same identifier to the telephone, where nothing records it.
    findings = phi.scan_fields({"summary": summary, "description": description})
    for code, severity, detail in findings:
        ctx.conn.execute(
            "INSERT INTO data_quality (run_id, subject_kind, subject_id, code,"
            " detail, severity) VALUES (?,?,?,?,?,?)",
            ("portal", "ticket", ticket_id, code, detail, severity))
    ctx.conn.commit()

    if findings:
        return Response(body=t.page("Your requests", (
            "<h1>Your requests</h1>" + _raise_form(notice=(
                f"Raised as {ticket_id}. It looks like your message may contain "
                "patient details. We have flagged it so it can be removed -- next "
                "time, please give us the record number instead of the patient's "
                "details.")) ), user=ctx.user))
    return redirect(f"/my/{ticket_id}")


def reply(ctx, work_item_id):
    from .. import HttpError, redirect
    clause, params = _mine_clause(ctx)
    row = ctx.conn.execute(
        "SELECT t.work_item_id FROM ticket t" + clause + " AND t.work_item_id = ?",
        params + [work_item_id]).fetchone()
    if row is None:
        raise HttpError("404 Not Found", "No such request.")

    body = ctx.request.form().get("body", "").strip()
    if body:
        stamp = ctx.now.isoformat(sep=" ", timespec="minutes")
        requester = (ctx.user.email or ctx.user.id or "").lower()
        ctx.conn.execute(
            "INSERT INTO ticket_event (work_item_id, occurred_at, kind, actor, detail)"
            " VALUES (?,?,'PORTAL_REPLY',?,?)", (work_item_id, stamp, requester, body))
        for code, severity, detail in phi.scan_fields({"reply": body}):
            ctx.conn.execute(
                "INSERT INTO data_quality (run_id, subject_kind, subject_id, code,"
                " detail, severity) VALUES (?,?,?,?,?,?)",
                ("portal", "ticket", work_item_id, code, detail, severity))
        ctx.conn.commit()
    return redirect(f"/my/{work_item_id}")
