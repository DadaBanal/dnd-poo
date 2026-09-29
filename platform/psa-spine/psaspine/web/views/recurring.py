"""Setup › Recurring tickets (047): a board's template raised on a cadence.

A board administrator sets up the recurrences on their boards (a system
administrator on any): name, template, cadence, first due day, an owner or
the board's queue, the company, a contact, the machine. Run now raises one
straight away; Pause stops the series without losing it.
"""
from __future__ import annotations

import urllib.parse

from ... import recurring
from .. import templates as t
from . import common


def _back(path: str, **q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    return redirect(path + ("?" + urllib.parse.urlencode(q) if q else ""))


def _admin_boards(ctx) -> list[str]:
    if ctx.user.is_sysadmin:
        return [r[0] for r in ctx.conn.execute("SELECT board_id FROM board ORDER BY board_id")]
    return [r[0] for r in ctx.conn.execute(
        "SELECT board_id FROM board_member WHERE member = ? AND access = 'ADMIN' ORDER BY board_id", (ctx.user.id,))]


def _require(ctx) -> list[str]:
    from .. import HttpError
    boards = _admin_boards(ctx)
    if not boards:
        raise HttpError("403 Forbidden", "A board administrator sets up recurring tickets.")
    return boards


def index(ctx):
    from .. import Response
    boards = _require(ctx)
    q = ctx.request.query
    rows = recurring.all_(ctx.conn, boards=boards)
    marks = ",".join("?" * len(boards))
    templates = ctx.conn.execute(
        f"SELECT t.template_id, t.name, b.display_name FROM ticket_template t JOIN board b ON b.board_id = t.board_id"
        f" WHERE t.inactive = 0 AND t.board_id IN ({marks}) ORDER BY b.display_name, t.name", boards).fetchall()
    entities = ctx.conn.execute("SELECT entity_id, name FROM entity ORDER BY name").fetchall()
    trs = "".join(
        f"<tr{'' if r['active'] else ' style=opacity:.55'}><td><b>{t.esc(r['name'])}</b></td><td>{t.esc(r['board_name'])}</td>"
        f"<td>{t.esc(r['template_name'])}</td><td>{t.esc(recurring.cadence_words(r['cadence'], r['every_n']))}</td>"
        f"<td>{t.esc(r['next_due_on'])}</td><td>{t.esc(r['owner'] or 'the queue')}</td>"
        + (f"<td><a href='/ticket/{t.esc(r['last_work_item_id'])}'>{t.esc(r['last_work_item_id'])}</a> <span class=muted>{t.esc(r['last_raised_at'] or '')}</span></td>"
           if r["last_work_item_id"] else "<td class=muted>never</td>")
        + f"<td>{'Active' if r['active'] else 'Paused'}</td><td>"
          f"<form method=post action='/admin/recurring/run' class=inline><input type=hidden name=id value={r['recurrence_id']}>"
          "<button class='ghost small' type=submit>Run now</button></form> "
          f"<form method=post action='/admin/recurring/toggle' class=inline><input type=hidden name=id value={r['recurrence_id']}>"
          f"<input type=hidden name=active value={0 if r['active'] else 1}><button class='ghost small' type=submit>"
          f"{'Pause' if r['active'] else 'Resume'}</button></form></td></tr>"
        for r in rows)
    tpl_opts = "".join(f"<option value='{t.esc(x['template_id'])}'>{t.esc(x['display_name'])} · {t.esc(x['name'])}</option>" for x in templates)
    ent_opts = "".join(f"<option value='{t.esc(e['entity_id'])}'>{t.esc(e['name'])}</option>" for e in entities)
    cad_opts = "".join(f"<option value={k}{' selected' if k == 'MONTHLY' else ''}>{t.esc(recurring.cadence_words(k, 1))}</option>"
                       for k in recurring.CADENCES)
    form = ("<div class=card><h3>" + t.icon("plus") + "New recurrence</h3>"
            + ("<p class=why>No template is in use on your boards yet. A recurrence raises its ticket from a board template "
               "(Setup › the board › Templates).</p>" if not templates else
               "<form method=post action='/admin/recurring/add' class=grid2>"
               "<div><label>Name</label><input name=name required maxlength=120 placeholder='Monthly analyser check'></div>"
               f"<div><label>Template</label><select name=template_id>{tpl_opts}</select></div>"
               f"<div><label>Cadence</label><select name=cadence>{cad_opts}</select></div>"
               "<div><label>Every N (1 = every time)</label><input name=every_n inputmode=numeric value=1></div>"
               "<div><label>First due on</label><input type=date name=first_due_on required></div>"
               "<div><label>Owner (blank: the board's queue)</label><input name=owner placeholder='a member of the board'></div>"
               f"<div><label>Company</label><select name=entity_id>{ent_opts}</select></div>"
               "<div><label>Requester's email (optional)</label><input name=contact_email placeholder='a contact, so they see it on the portal'></div>"
               "<div><label>Machine (optional)</label><input name=configuration placeholder='a configuration, by name'></div>"
               "<div><label>Who is affected · patient waiting</label><div class=row>"
               "<select name=impact aria-label='Impact'><option value=I3 selected>Just me</option><option value=I2>A ward or department</option><option value=I1>The whole hospital</option></select>"
               "<select name=urgency aria-label='Urgency'><option value=U3 selected>No</option><option value=U2>Yes, with a workaround</option><option value=U1>Yes, care has stopped</option></select></div></div>"
               "<div><button type=submit>Create</button></div></form>") + "</div>")
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + "<h1>Recurring tickets</h1><p class=sub>A board template raised on a cadence: the monthly analyser check, the "
              "quarterly printer care, the yearly UPS test. The minute runner raises each one on its due day, with the "
              "template's tasks, and moves the due day on. A runner that was down raises it once, never once per missed "
              "period. <a href='/admin'>Setup</a></p>"
              "<div class=card><div class=tablewrap><table><thead><tr><th>Name</th><th>Board</th><th>Template</th><th>Cadence</th>"
              "<th>Next due</th><th>Owner</th><th>Last raised</th><th>State</th><th></th></tr></thead><tbody>"
            + (trs or "<tr><td colspan=9 class=muted>No recurring ticket yet.</td></tr>") + "</tbody></table></div></div>" + form)
    return Response(body=t.page("Recurring tickets", body, user=ctx.user, active="admin"))


def _lookup(ctx, f) -> dict:
    """The optional contact and machine, by the words a person types."""
    out = {"contact_id": None, "configuration_id": None}
    email = (f.get("contact_email") or "").strip()
    if email:
        row = ctx.conn.execute("SELECT contact_id FROM contact WHERE LOWER(email) = LOWER(?) AND inactive = 0", (email,)).fetchone()
        if row is None:
            raise recurring.Refused(f"No active contact has the address {email}.")
        out["contact_id"] = row[0]
    name = (f.get("configuration") or "").strip()
    if name:
        row = ctx.conn.execute("SELECT configuration_id FROM configuration WHERE LOWER(name) = LOWER(?)", (name,)).fetchone()
        if row is None:
            raise recurring.Refused(f"No configuration is named {name}.")
        out["configuration_id"] = row[0]
    return out


def add(ctx):
    boards = _require(ctx)
    f = ctx.request.form()
    try:
        tpl = ctx.conn.execute("SELECT board_id FROM ticket_template WHERE template_id = ?", (f.get("template_id", ""),)).fetchone()
        if tpl is None or tpl[0] not in boards:
            raise recurring.Refused("Pick a template on a board you administer.")
        extra = _lookup(ctx, f)
        rid = recurring.create(ctx.conn, name=f.get("name", ""), template_id=f.get("template_id", ""), cadence=f.get("cadence", ""),
                               first_due_on=f.get("first_due_on", ""), every_n=f.get("every_n", "1"), owner=f.get("owner"),
                               entity_id=f.get("entity_id"), impact=f.get("impact", "I3"), urgency=f.get("urgency", "U3"),
                               at=ctx.now, actor=ctx.user.id, **extra)
        ctx.conn.commit()
    except recurring.Refused as exc:
        ctx.conn.rollback()
        return _back("/admin/recurring", err=str(exc))
    return _back("/admin/recurring", msg=f"Recurrence #{rid} created; its first ticket is raised on its due day.")


def _owned(ctx, boards):
    f = ctx.request.form()
    try:
        rid = int(f.get("id", ""))
    except ValueError:
        raise recurring.Refused("No such recurrence.") from None
    row = recurring.get(ctx.conn, rid)
    if row is None or row["board_id"] not in boards:
        raise recurring.Refused("No such recurrence on a board you administer.")
    return row, f


def toggle(ctx):
    boards = _require(ctx)
    try:
        row, f = _owned(ctx, boards)
        recurring.set_active(ctx.conn, row["recurrence_id"], f.get("active") == "1", at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except recurring.Refused as exc:
        ctx.conn.rollback()
        return _back("/admin/recurring", err=str(exc))
    return _back("/admin/recurring", msg=f"{row['name']} {'resumed' if f.get('active') == '1' else 'paused'}")


def run(ctx):
    boards = _require(ctx)
    try:
        row, _f = _owned(ctx, boards)
        wid = recurring.run_now(ctx.conn, row["recurrence_id"], at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except recurring.Refused as exc:
        ctx.conn.rollback()
        return _back("/admin/recurring", err=str(exc))
    except Exception as exc:                                        # noqa: BLE001
        ctx.conn.rollback()
        return _back("/admin/recurring", err=f"Not raised: {exc}")
    return _back(f"/ticket/{wid}", msg=f"Raised now by {row['name']}")
