"""Setup › Members, a page per person, and My profile (053).

Everyone the desk knows, in one list; one page per person that holds the
record, the board memberships, the security role, the hours a week and the
break-glass account together, where before they were four pages and a
command line. Deactivation ends what points at the person and says what it
did. The list and the pages are a system administrator's; the profile is
the person's own.
"""
from __future__ import annotations

import urllib.parse

from ... import members, security, timesheets
from .. import templates as t
from . import common

ACCESS = (("READ", "Read"), ("WORK", "Work"), ("ADMIN", "Admin"))


def _back(path: str, **q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    return redirect(path + ("?" + urllib.parse.urlencode(q) if q else ""))


def _banners(q) -> str:
    return ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else ""))


def _load(ctx, member):
    from .. import HttpError
    row = members.get(ctx.conn, member)
    if row is None:
        raise HttpError("404 Not Found", "No such member.")
    return row


def _options(rows, key, label, selected) -> str:
    return "<option value=''>—</option>" + "".join(
        f"<option value='{t.esc(r[key])}'{' selected' if r[key] == selected else ''}>{t.esc(r[label])}</option>" for r in rows)


def _member_options(ctx, selected, *, not_me: str) -> str:
    return "<option value=''>—</option>" + "".join(
        f"<option value='{t.esc(m)}'{' selected' if selected and m.lower() == selected.lower() else ''}>{t.esc(members.name_of(ctx.conn, m))}"
        f"{' (' + t.esc(m) + ')' if members.name_of(ctx.conn, m) != m else ''}</option>"
        for m in members.identifiers(ctx.conn) if m.lower() != not_me.lower() and not members.is_inactive(ctx.conn, m))


# ------------------------------------------------------------ the list

def index(ctx):
    from .. import Response
    common.require_sysadmin(ctx)
    q = ctx.request.query
    show_inactive = q.get("inactive") == "1"
    rows = members.all_(ctx.conn, q=q.get("q", ""), include_inactive=show_inactive)
    trs = "".join(
        f"<tr{' style=opacity:.6' if r['inactive_from'] else ''}><td><a href='/admin/member/{urllib.parse.quote(r['member'])}'><b>{t.esc(r['display_name'])}</b></a>"
        + (f"<div class=muted>{t.esc(r['member'])}</div>" if r["display_name"] != r["member"] else "")
        + (f" <span class=pill>left {t.esc(r['inactive_from'])}</span>" if r["inactive_from"] else "")
        + (" <span class=pill>no record</span>" if not r["has_record"] else "") + "</td>"
        f"<td>{t.esc(r['title'] or '')}</td><td>{t.esc(r['email'] or '')}</td><td>{t.esc(r['role_name'] or 'the default role')}</td>"
        f"<td>{t.esc(', '.join(r['boards']) or '—')}</td><td class=num>{r['hours_per_week'] if r['hours_per_week'] is not None else ''}</td>"
        f"<td>{'sysadmin' if r['local_account'] and r['local_account']['is_sysadmin'] else ('break-glass' if r['local_account'] else '')}"
        f"{' (disabled)' if r['local_account'] and r['local_account']['disabled'] else ''}</td></tr>" for r in rows)
    body = (_banners(q) + "<h1>Members</h1><p class=sub>Everyone who works the desk: the record, the boards they are on, "
            "their role and their hours, one page each. A person signs in with the identifier; the record gives them a name "
            "the desk shows everywhere. <a href='/admin'>Setup</a></p>"
            "<div class=card><form method=get action='/admin/members' class='row schedbar'>"
            f"<div style='flex:1 1 260px'><input name=q value='{t.esc(q.get('q', ''))}' placeholder='Search members'></div>"
            f"<div style='flex:0 0 auto'><label><input type=checkbox name=inactive value=1{' checked' if show_inactive else ''}> Show who left</label></div>"
            "<div style='flex:0 0 auto'><button class=ghost type=submit>Search</button></div></form>"
            "<div class=tablewrap><table><thead><tr><th>Member</th><th>Title</th><th>Email</th><th>Security role</th><th>Boards</th>"
            "<th class=num>Hours / week</th><th>Account</th></tr></thead><tbody>"
            + (trs or "<tr><td colspan=7 class=muted>Nobody yet.</td></tr>") + "</tbody></table></div></div>"
            "<div class=card><h3>" + t.icon("plus") + "Add a member</h3><p class=why>The identifier is what the person signs in "
            "as: the AD account name (the part before the @), or the Entra object id. A person who has already signed in or "
            "been put on a board is in the list above; open their page instead.</p>"
            "<form method=post action='/admin/members/add' class=grid2>"
            "<div><label>Identifier</label><input name=member required maxlength=200 placeholder='jcruz'></div>"
            "<div><label>Name</label><input name=display_name maxlength=200 placeholder='Juan Cruz'></div>"
            "<div><label>Title</label><input name=title maxlength=200 placeholder='Service desk technician'></div>"
            "<div><label>Email</label><input name=email maxlength=200 placeholder='jcruz@pmcne.ph'></div>"
            "<div><label>Department</label><input name=department maxlength=200 placeholder='Information Technology'></div>"
            f"<div><label>Default board</label><select name=default_board_id>{_options(_boards(ctx), 'board_id', 'display_name', None)}</select></div>"
            "<div><button type=submit>Add</button></div></form></div>")
    return Response(body=t.page("Members", body, user=ctx.user, active="admin"))


def _boards(ctx):
    return ctx.conn.execute("SELECT board_id, display_name FROM board WHERE COALESCE(inactive, 0) = 0 ORDER BY display_name").fetchall()


def add(ctx):
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    try:
        ident = members.add(ctx.conn, f.get("member", ""), at=ctx.now, actor=ctx.user.id, display_name=f.get("display_name"),
                            title=f.get("title"), email=f.get("email"), department=f.get("department"),
                            default_board_id=f.get("default_board_id"))
        ctx.conn.commit()
    except members.Refused as exc:
        ctx.conn.rollback()
        return _back("/admin/members", err=str(exc))
    return _back(f"/admin/member/{urllib.parse.quote(ident)}", msg=f"{ident} added. Now put them on their boards.")


# ------------------------------------------------------------ one person

def detail(ctx, member):
    from .. import Response
    common.require_sysadmin(ctx)
    m = _load(ctx, member)
    q = ctx.request.query
    ident = m["member"]
    path = f"/admin/member/{urllib.parse.quote(ident)}"
    p = t.esc(path)
    active = m["active"]
    roles = [r for r in security.roles(ctx.conn) if not r["inactive"]]
    work_roles = ctx.conn.execute("SELECT work_role_id, name FROM work_role WHERE inactive = 0 ORDER BY sort_order, name").fetchall()
    record = (f"<div class=card><h3>" + t.icon("users") + "Record</h3>"
              + ("" if m["has_record"] else "<p class=why>This person has no record yet: the desk knows them from a board, a "
                                            "role or an account. Save once and it has one.</p>")
              + f"<form method=post action='{p}/save' class=grid2>"
              f"<div><label>Name</label><input name=display_name maxlength=200 value='{t.esc(m['display_name'] if m['display_name'] != ident else '')}'></div>"
              f"<div><label>Title</label><input name=title maxlength=200 value='{t.esc(m['title'] or '')}'></div>"
              f"<div><label>Email</label><input name=email maxlength=200 value='{t.esc(m['email'] or '')}'></div>"
              f"<div><label>Phone</label><input name=phone maxlength=32 value='{t.esc(m['phone'] or '')}'></div>"
              f"<div><label>Mobile</label><input name=mobile maxlength=32 value='{t.esc(m['mobile'] or '')}'></div>"
              f"<div><label>Department</label><input name=department maxlength=200 value='{t.esc(m['department'] or '')}'></div>"
              f"<div><label>Location</label><input name=location maxlength=200 value='{t.esc(m['location'] or '')}' placeholder='IT office, ward 3 store room'></div>"
              f"<div><label>Reports to</label><select name=reports_to>{_member_options(ctx, m['reports_to'], not_me=ident)}</select></div>"
              f"<div><label>Default board</label><select name=default_board_id>{_options(_boards(ctx), 'board_id', 'display_name', m['default_board_id'])}</select></div>"
              f"<div><label>Default work role</label><select name=work_role_id>{_options(work_roles, 'work_role_id', 'name', m['work_role_id'])}</select></div>"
              f"<div><label>Time approver</label><select name=time_approver>{_member_options(ctx, m['time_approver'], not_me=ident)}</select></div>"
              f"<div style='grid-column:1/-1'><label>Notes</label><textarea name=notes>{t.esc(m['notes'] or '')}</textarea></div>"
              "<div><button type=submit>Save</button></div></form>"
              + (f"<p class=muted style='margin-top:8px'>Updated {t.esc(m['updated_at'])} · {t.esc(m['updated_by'])}</p>" if m["updated_at"] else "")
              + "</div>")
    board_rows = "".join(
        f"<tr><td><a href='/admin/board/{t.esc(b['board_id'])}?tab=members'>{t.esc(b['display_name'])}</a></td>"
        f"<td><form method=post action='{p}/board' class=row style='margin:0'><input type=hidden name=board_id value='{t.esc(b['board_id'])}'>"
        "<div><select name=access aria-label='Access'>" + "".join(
            f"<option value={k}{' selected' if k == b['access'] else ''}>{v}</option>" for k, v in ACCESS)
        + "</select></div><div style='flex:0 0 auto'><button class='ghost small' type=submit>Set</button></div></form></td>"
        f"<td>{t.esc(b['team_name'] or '')}</td>"
        f"<td><form method=post action='{p}/board/remove' class=inline><input type=hidden name=board_id value='{t.esc(b['board_id'])}'>"
        "<button class='ghost small' type=submit>Take off</button></form></td></tr>" for b in m["boards"])
    on = {b["board_id"] for b in m["boards"]}
    add_opts = "".join(f"<option value='{t.esc(b['board_id'])}'>{t.esc(b['display_name'])}</option>"
                       for b in _boards(ctx) if b["board_id"] not in on)
    boards_card = ("<div class=card><h3>" + t.icon("board") + "Boards</h3>"
                   "<div class=tablewrap><table><thead><tr><th>Board</th><th>Access</th><th>Team</th><th></th></tr></thead><tbody>"
                   + (board_rows or "<tr><td colspan=4 class=muted>On no board: a requester until they are.</td></tr>") + "</tbody></table></div>"
                   + (f"<form method=post action='{p}/board' class=row style='margin-top:10px'><div><label>Put on</label><select name=board_id>{add_opts}</select></div>"
                      "<div style='flex:0 0 140px'><label>Access</label><select name=access>" + "".join(f"<option value={k}>{v}</option>" for k, v in ACCESS)
                      + "</select></div><div style='flex:0 0 auto;align-self:end'><button class=ghost type=submit>Add</button></div></form>"
                      if add_opts and active else "") + "</div>")
    role_opts = "<option value=''>The default role</option>" + "".join(
        f"<option value='{t.esc(r['role_id'])}'{' selected' if r['role_id'] == m['role_id'] else ''}>{t.esc(r['name'])}</option>" for r in roles)
    la = m["local_account"]
    account = ("none" if not la else ("sysadmin break-glass" if la["is_sysadmin"] else "break-glass")
               + (", disabled" if la["disabled"] else "") + f"; last sign-in {la['last_login_at'] or 'never'}")
    access_card = ("<div class=card><h3>" + t.icon("shield") + "Role, hours and account</h3><div class=grid2>"
                   f"<form method=post action='{p}/role' class=row><div><label>Security role</label><select name=role_id>{role_opts}</select></div>"
                   "<div style='flex:0 0 auto;align-self:end'><button class=ghost type=submit>Set</button></div></form>"
                   f"<form method=post action='{p}/capacity' class=row><div><label>Hours a week</label><input name=hours inputmode=decimal value='{m['hours_per_week']:g}'></div>"
                   "<div style='flex:0 0 auto;align-self:end'><button class=ghost type=submit>Set</button></div></form></div>"
                   f"<form method=post action='{p}/sysadmin' class=row style='margin-top:10px'><div><label>Desk sysadmin</label>"
                   f"<div class=why>{'Yes: runs every Setup page from their normal sign-in.' if m['is_sysadmin'] else 'No.'}</div></div>"
                   f"<div style='flex:0 0 auto;align-self:end'><input type=hidden name=on value='{0 if m['is_sysadmin'] else 1}'>"
                   f"<button class=ghost type=submit>{'Take off' if m['is_sysadmin'] else 'Make sysadmin'}</button></div></form>"
                   + _chat_operator_form(ctx, ident, p) +
                   f"<dl class=kv style='margin-top:10px'><dt>Break-glass account</dt><dd>{t.esc(account)}</dd>"
                   f"<dt>Calendar</dt><dd><a href='/calendar?{urllib.parse.urlencode({'member': ident})}'>Open their calendar</a>"
                   f"{' · feed on' if members.has_feed(ctx.conn, ident) else ''}</dd></dl></div>")
    if active:
        leave = ("<div class=card><h3>" + t.icon("x") + "Leaving</h3><p class=why>Ends the board memberships, the future on-call "
                 "slots, the departments they approve for, who reports to them, whose time they approve, and the break-glass "
                 "account, and lists what it did. Tickets, notes and time keep their name.</p>"
                 f"<form method=post action='{p}/deactivate'><button class=ghost type=submit>This person has left</button></form></div>")
    else:
        leave = (f"<div class='banner err'>Left on {t.esc(m['inactive_from'])}. Memberships were ended then.</div>"
                 f"<form method=post action='{p}/reactivate' style='margin-bottom:12px'><button class=ghost type=submit>Back on the desk</button></form>")
    trail = "".join(f"<li><span class=muted>{t.esc(r['occurred_at'])} · {t.esc(r['actor'])}</span> {t.esc(r['detail'] or '')}</li>"
                    for r in ctx.conn.execute("SELECT occurred_at, actor, detail FROM audit_event WHERE action = 'MEMBER'"
                                              " AND LOWER(subject_id) = LOWER(?) ORDER BY audit_id DESC", (ident,)).fetchall()[:20])
    history = "<div class=card><h3>" + t.icon("clock") + "History</h3><ul class=plain>" + (trail or "<li class=muted>Nothing yet.</li>") + "</ul></div>"
    body = (_banners(q) + f"<p class=crumbs><a href='/admin'>Setup</a> › <a href='/admin/members'>Members</a> › {t.esc(ident)}</p>"
            f"<h1>{t.esc(m['display_name'])}" + (f" <span class=muted style='font-size:.6em'>{t.esc(ident)}</span>" if m["display_name"] != ident else "")
            + (" <span class='chip sla-bad'>left</span>" if not active else "") + "</h1>"
            + leave + "<div class=grid2>" + record + boards_card + access_card + history + "</div>")
    return Response(body=t.page(m["display_name"], body, user=ctx.user, active="admin"))


def _chat_operator_form(ctx, ident: str, p: str) -> str:
    """073: the Chat operator tick (Dada, 7 Oct 2026: "a chat operator member
    access ... only PMO Helpdesk members can use the chat")."""
    from ... import chat
    if not ctx.conn.execute("SELECT 1 FROM board WHERE takes_chats = 1").fetchone() and not chat.is_operator(ctx.conn, ident):
        return ""
    on = chat.is_operator(ctx.conn, ident)
    avg, n = chat.rating_of(ctx.conn, ident)              # 074: how the wards rated their chats
    rated = (f" Rated {avg} / 5 by the wards over {n} chat{'s' if n != 1 else ''}." if n else "")
    names = ", ".join(r["display_name"] for r in chat.chat_boards(ctx.conn)) or "no board"
    return (f"<form method=post action='{p}/chat-operator' class=row id=chatoperator style='margin-top:10px'><div><label>Chat operator</label>"
            f"<div class=why>{'Yes: answers chats from the wards on ' + t.esc(names) + '.' if on else 'No. Only someone who works ' + t.esc(names) + ' can be one.'}"
            f"<span id=chatoprating>{t.esc(rated)}</span></div></div>"
            f"<div style='flex:0 0 auto;align-self:end'><input type=hidden name=on value='{0 if on else 1}'>"
            f"<button class=ghost type=submit>{'Untick' if on else 'Make chat operator'}</button></div></form>")


def chat_operator(ctx, member):
    from ... import chat
    common.require_sysadmin(ctx)
    m = _load(ctx, member)
    f = ctx.request.form()
    path = f"/admin/member/{urllib.parse.quote(m['member'])}"

    def go():
        try:
            return chat.set_operator(ctx.conn, m["member"], f.get("on") == "1", at=ctx.now, actor=ctx.user.id)
        except chat.Refused as exc:
            raise members.Refused(str(exc)) from exc
    return _try(ctx, path, go, lambda s: s)


def _try(ctx, path, fn, ok):
    try:
        out = fn()
        ctx.conn.commit()
    except (members.Refused, security.Refused, timesheets.Refused) as exc:
        ctx.conn.rollback()
        return _back(path, err=str(exc))
    return _back(path, msg=ok(out) if callable(ok) else ok)


def save(ctx, member):
    common.require_sysadmin(ctx)
    m = _load(ctx, member)
    f = ctx.request.form()
    path = f"/admin/member/{urllib.parse.quote(m['member'])}"
    return _try(ctx, path, lambda: members.save(ctx.conn, m["member"], at=ctx.now, actor=ctx.user.id,
                                                **{k: f.get(k) for k in members.FIELDS}),
                lambda changed: "Saved." if changed else "Nothing changed.")


def board(ctx, member):
    common.require_sysadmin(ctx)
    m = _load(ctx, member)
    f = ctx.request.form()
    path = f"/admin/member/{urllib.parse.quote(m['member'])}"
    return _try(ctx, path, lambda: members.set_membership(ctx.conn, m["member"], f.get("board_id", ""), f.get("access", ""),
                                                          at=ctx.now, actor=ctx.user.id), lambda s: s)


def board_remove(ctx, member):
    common.require_sysadmin(ctx)
    m = _load(ctx, member)
    f = ctx.request.form()
    path = f"/admin/member/{urllib.parse.quote(m['member'])}"
    return _try(ctx, path, lambda: members.set_membership(ctx.conn, m["member"], f.get("board_id", ""), None,
                                                          at=ctx.now, actor=ctx.user.id), lambda s: s)


def role(ctx, member):
    common.require_sysadmin(ctx)
    m = _load(ctx, member)
    f = ctx.request.form()
    path = f"/admin/member/{urllib.parse.quote(m['member'])}"
    return _try(ctx, path, lambda: security.assign(ctx.conn, m["member"], f.get("role_id") or None, at=ctx.now, actor=ctx.user.id),
                lambda s: s)


def capacity(ctx, member):
    common.require_sysadmin(ctx)
    m = _load(ctx, member)
    f = ctx.request.form()
    path = f"/admin/member/{urllib.parse.quote(m['member'])}"
    return _try(ctx, path, lambda: timesheets.set_capacity(ctx.conn, m["member"], f.get("hours"), at=ctx.now, actor=ctx.user.id),
                lambda h: f"{h:g} hours a week.")


def sysadmin(ctx, member):
    common.require_sysadmin(ctx)
    m = _load(ctx, member)
    f = ctx.request.form()
    path = f"/admin/member/{urllib.parse.quote(m['member'])}"
    return _try(ctx, path, lambda: members.set_sysadmin(ctx.conn, m["member"], f.get("on") == "1", at=ctx.now, actor=ctx.user.id),
                lambda s: s)


def deactivate(ctx, member):
    common.require_sysadmin(ctx)
    m = _load(ctx, member)
    path = f"/admin/member/{urllib.parse.quote(m['member'])}"
    return _try(ctx, path, lambda: members.deactivate(ctx.conn, m["member"], at=ctx.now, actor=ctx.user.id),
                lambda done: f"{m['display_name']} has left. " + ("; ".join(done) if done else "Nothing pointed at them."))


def reactivate(ctx, member):
    common.require_sysadmin(ctx)
    m = _load(ctx, member)
    path = f"/admin/member/{urllib.parse.quote(m['member'])}"
    return _try(ctx, path, lambda: members.reactivate(ctx.conn, m["member"], at=ctx.now, actor=ctx.user.id),
                f"{m['display_name']} is back. Put them on their boards.")


# ------------------------------------------------------------ my profile

def profile(ctx):
    """The person's own page: what the desk holds on them, the numbers they
    keep themselves, their boards and role, and the calendar feed."""
    from .. import HttpError, Response
    if getattr(ctx.user, "requester", False):
        raise HttpError("404 Not Found", "No such page.")
    m = members.get(ctx.conn, ctx.user.id)
    if m is None:
        raise HttpError("404 Not Found", "No such page.")
    q = ctx.request.query
    token = q.get("token", "")
    boards = "".join(f"<li>{t.esc(b['display_name'])} <span class=muted>{t.esc(b['access'].lower())}</span></li>" for b in m["boards"])
    feed = ""
    if token:
        feed = ("<div class='banner ok'>Your calendar feed address, shown once. Add it to your phone's calendar as a "
                "subscription:<br><code>" + t.esc(common.public_url(ctx) + "/calendar/feed/" + token + ".ics") + "</code></div>")
    body = (_banners(q) + feed + f"<h1>{t.esc(m['display_name'])}</h1><p class=sub>What the desk holds on you. Your service "
            "manager changes the rest in Setup › Members.</p><div class=grid2>"
            "<div class=card><dl class=kv>"
            f"<dt>Signs in as</dt><dd>{t.esc(m['member'])}</dd><dt>Title</dt><dd>{t.esc(m['title'] or '—')}</dd>"
            f"<dt>Email</dt><dd>{t.esc(m['email'] or '—')}</dd><dt>Department</dt><dd>{t.esc(m['department'] or '—')}</dd>"
            f"<dt>Location</dt><dd>{t.esc(m['location'] or '—')}</dd>"
            f"<dt>Reports to</dt><dd>{t.esc(members.name_of(ctx.conn, m['reports_to']) if m['reports_to'] else '—')}</dd>"
            f"<dt>Security role</dt><dd>{t.esc(m['role_name'] or 'the default role')}</dd>"
            f"<dt>Hours a week</dt><dd>{m['hours_per_week']:g}</dd>"
            f"<dt>Time approver</dt><dd>{t.esc(members.name_of(ctx.conn, m['time_approver']) if m['time_approver'] else 'any Timesheets administrator')}</dd>"
            f"<dt>Boards</dt><dd><ul class=plain>{boards or '<li class=muted>none</li>'}</ul></dd></dl></div>"
            "<div class=card><h3>" + t.icon("mail") + "How to reach you</h3>"
            "<form method=post action='/my/profile/save' class=grid2>"
            f"<div><label>Phone</label><input name=phone maxlength=32 value='{t.esc(m['phone'] or '')}'></div>"
            f"<div><label>Mobile</label><input name=mobile maxlength=32 value='{t.esc(m['mobile'] or '')}'></div>"
            "<div><button type=submit>Save</button></div></form>"
            "<h3 style='margin-top:16px'>" + t.icon("calendar") + "Calendar feed</h3><p class=why>A private address your phone's "
            "calendar can subscribe to: your visits, time off, meetings and on-call shifts. It names tickets and places, "
            "never what a ticket says. Making a new one stops the old one.</p>"
            f"<form method=post action='/my/profile/feed'><button class=ghost type=submit>{'New feed address' if members.has_feed(ctx.conn, m['member']) else 'Make a feed address'}</button></form>"
            f"<p style='margin-top:10px'><a href='/calendar'>Open my calendar</a> · <a href='/inout'>Say where I am</a></p></div></div>")
    return Response(body=t.page("My profile", body, user=ctx.user, active=""))


def profile_save(ctx):
    from .. import HttpError
    if getattr(ctx.user, "requester", False) or not members.exists(ctx.conn, ctx.user.id):
        raise HttpError("404 Not Found", "No such page.")
    f = ctx.request.form()
    return _try(ctx, "/my/profile", lambda: members.save(ctx.conn, ctx.user.id, at=ctx.now, actor=ctx.user.id,
                                                          phone=f.get("phone"), mobile=f.get("mobile")),
                lambda changed: "Saved." if changed else "Nothing changed.")


def profile_feed(ctx):
    from .. import HttpError, redirect
    if getattr(ctx.user, "requester", False) or not members.exists(ctx.conn, ctx.user.id):
        raise HttpError("404 Not Found", "No such page.")
    token = members.new_feed_token(ctx.conn, ctx.user.id, at=ctx.now)
    ctx.conn.commit()
    return redirect("/my/profile?" + urllib.parse.urlencode({"token": token}))
