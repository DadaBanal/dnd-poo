"""Setup > Email connector: what mail becomes on this desk (055).

The reference PSA has an Email Connector page per board with the mailbox,
its credential, parsing rules and exclusions. Here the mailbox and its
certificate live on the host (the pickup script), so the page holds the
decisions that belong to the desk: which board claims which address (053),
what must never open a ticket (the exclusions), and how the last week's
mail was placed. The intake table's subjects are not shown here: a subject
can carry a patient's words, and the page is for a system administrator
who is not a member of every board.
"""
from __future__ import annotations

import urllib.parse
from datetime import timedelta

from ... import intake
from .. import templates as t
from . import common

DISPOSITIONS = {"NEW_TICKET": "opened a ticket", "APPENDED": "added to a ticket", "DUPLICATE": "a duplicate", "UNCLASSIFIED": "opened nothing"}
RECENT = 30


def _back(**q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    return redirect("/admin/mail" + ("?" + urllib.parse.urlencode(q) if q else ""))


def index(ctx):
    from .. import Response
    common.require_sysadmin(ctx)
    q = ctx.request.query
    boards = ctx.conn.execute("SELECT board_id, display_name, is_unrouted, closed_reply_policy FROM board"
                              " WHERE COALESCE(inactive, 0) = 0 ORDER BY is_unrouted DESC, display_name").fetchall()
    claims: dict[str, list[str]] = {}
    for a, bid in sorted(intake.board_addresses(ctx.conn).items()):
        claims.setdefault(bid, []).append(a)
    addr_rows = "".join(
        f"<tr><td><a href='/admin/board/{t.esc(b['board_id'])}?tab=board'>{t.esc(b['display_name'])}</a>"
        + (" <span class=pill>unrouted queue</span>" if b["is_unrouted"] else "") + "</td>"
        f"<td>{t.esc(', '.join(claims.get(b['board_id'], [])))}{'' if claims.get(b['board_id']) else '<span class=muted>none: only the pickup task or the unrouted queue sends mail here</span>'}</td>"
        f"<td>{'Reopen' if (b['closed_reply_policy'] or 'REOPEN') == 'REOPEN' else 'New ticket'}</td></tr>" for b in boards)
    rules = intake.exclusions(ctx.conn)
    rule_rows = "".join(
        f"<tr><td>{t.esc(intake.EXCLUSION_KINDS[r['kind']])}</td><td><code>{t.esc(r['pattern'])}</code></td><td>{t.esc(r['note'] or '')}</td>"
        f"<td class=muted>{t.esc(r['created_at'])} · {t.esc(r['created_by'])}</td>"
        f"<td><form method=post action='/admin/mail/exclude/remove' class=inline><input type=hidden name=exclusion_id value='{r['exclusion_id']}'>"
        "<button class='ghost small' type=submit>Remove</button></form></td></tr>" for r in rules)
    since = (ctx.now - timedelta(days=7)).isoformat(sep=" ", timespec="minutes")
    counts = {r["disposition"]: r["n"] for r in ctx.conn.execute(
        "SELECT disposition, COUNT(*) AS n FROM intake_message WHERE received_at >= ? GROUP BY disposition", (since,))}
    routed = ctx.conn.execute("SELECT COUNT(*) FROM intake_message WHERE received_at >= ? AND to_address IS NOT NULL", (since,)).fetchone()[0]
    tiles = "".join(f"<div class=tile><div class=l>{t.esc(w)}</div><div class=n>{counts.get(k, 0)}</div></div>" for k, w in DISPOSITIONS.items())
    tiles += f"<div class=tile><div class=l>routed by a board's address</div><div class=n>{routed}</div></div>"
    recent = ctx.conn.execute(
        "SELECT i.received_at, i.from_address, i.to_address, i.channel, i.disposition, i.work_item_id,"
        "       (SELECT MIN(detail) FROM data_quality d WHERE d.subject_kind = 'intake_message' AND d.subject_id = i.message_id"
        "          AND d.code IN ('MAIL_LOOP_GUARD', 'MAIL_EXCLUDED', 'INTAKE_UNCLASSIFIED')) AS why"
        "  FROM intake_message i ORDER BY i.received_at DESC, i.message_id LIMIT ?", (RECENT,)).fetchall()

    def domain(addr):
        a = addr or ""
        return ("…@" + a.split("@", 1)[1]) if "@" in a else (a or "—")
    recent_rows = "".join(
        f"<tr><td class=muted>{t.esc(r['received_at'])}</td><td>{t.esc(domain(r['from_address']))}</td><td>{t.esc(r['to_address'] or '')}</td>"
        f"<td>{t.esc(r['channel'] or '')}</td><td>{t.esc(DISPOSITIONS.get(r['disposition'], r['disposition']))}"
        + (f" <a href='/ticket/{t.esc(r['work_item_id'])}'>{t.esc(r['work_item_id'])}</a>" if r["work_item_id"] else "")
        + (f"<div class=muted>{t.esc(r['why'])}</div>" if r["why"] else "") + "</td></tr>" for r in recent)
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + "<h1>Email connector</h1><p class=sub>The mailbox and its certificate live on the host, in the pickup task. "
              "What the desk decides is here: which board claims which address, what never opens a ticket, and how the "
              "last week's mail was placed. Senders are shown by domain only; subjects are not shown. <a href='/admin'>Setup</a></p>"
              "<div class=card><h3>" + t.icon("mail") + "Addresses</h3><p class=why>A board claims its address on its own page "
              "(the mail-policy card). Mail to an address nobody claims goes to the pickup task's board, else the unrouted queue.</p>"
              "<div class=tablewrap><table><thead><tr><th>Board</th><th>Intake address</th><th>Reply to a closed ticket</th></tr></thead><tbody>"
            + addr_rows + "</tbody></table></div></div>"
              "<div class=card><h3>" + t.icon("x") + "Never opens a ticket</h3><p class=why>Mail from an excluded address or "
              "domain, or whose subject contains an excluded phrase, is imported and recorded (nothing is dropped) and opens "
              "nothing; the intake table says why. Delivery-system senders and auto-replies are excluded by the desk itself.</p>"
              "<div class=tablewrap><table><thead><tr><th>Kind</th><th>Pattern</th><th>Note</th><th>Added</th><th></th></tr></thead><tbody>"
            + (rule_rows or "<tr><td colspan=5 class=muted>No exclusion yet.</td></tr>") + "</tbody></table></div>"
              "<form method=post action='/admin/mail/exclude' class=row style='margin-top:10px'>"
              "<div style='flex:0 0 160px'><label>Kind</label><select name=kind>" + "".join(f"<option value={k}>{t.esc(v)}</option>" for k, v in intake.EXCLUSION_KINDS.items())
            + "</select></div><div style='flex:1 1 220px'><label>Pattern</label><input name=pattern required maxlength=200 placeholder='newsletter@vendor.com · vendor.com · out of office'></div>"
              "<div style='flex:1 1 200px'><label>Note</label><input name=note maxlength=400 placeholder='why'></div>"
              "<div style='flex:0 0 auto;align-self:end'><button class=ghost type=submit>Exclude</button></div></form></div>"
              "<div class=card><h3>" + t.icon("inbox") + "The last seven days</h3>"
              f"<div class=tiles style='grid-template-columns:repeat(auto-fit,minmax(150px,1fr))'>{tiles}</div>"
              "<div class=tablewrap><table><thead><tr><th>Received</th><th>From</th><th>To</th><th>Mailbox</th><th>Became</th></tr></thead><tbody>"
            + (recent_rows or "<tr><td colspan=5 class=muted>No mail has arrived yet.</td></tr>") + "</tbody></table></div></div>")
    return Response(body=t.page("Email connector", body, user=ctx.user, active="admin"))


def exclude(ctx):
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    try:
        intake.add_exclusion(ctx.conn, f.get("kind", ""), f.get("pattern", ""), note=f.get("note"), at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except ValueError as exc:
        ctx.conn.rollback()
        return _back(err=str(exc))
    return _back(msg="Excluded. It applies from the next pickup.")


def exclude_remove(ctx):
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    try:
        eid = int(f.get("exclusion_id", ""))
    except ValueError:
        return _back(err="No such exclusion.")
    ok = intake.remove_exclusion(ctx.conn, eid, at=ctx.now, actor=ctx.user.id)
    ctx.conn.commit()
    return _back(msg="Removed." if ok else "No such exclusion.")
