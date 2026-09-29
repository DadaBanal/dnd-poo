"""The knowledge base pages (039): search, read, write, publish, and the portal's Help.

Gated by the security role's KNOWLEDGE level: READ to search and read, WRITE to
write and publish, ADMIN to retire. A board's own articles are shown only to
the board's members, like its tickets. Requesters see REQUESTER articles that
are PUBLISHED, on the portal's Help page, and nothing else.
"""
from __future__ import annotations

import urllib.parse

from ... import knowledge, phi, setup
from .. import templates as t
from . import common

STATUS_WORDS = {"DRAFT": "Draft", "PUBLISHED": "Published", "RETIRED": "Retired"}


def _back(path: str, **q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    return redirect(path + ("?" + urllib.parse.urlencode(q) if q else ""))


def _visible(ctx, row) -> bool:
    return row is not None and (row["board_id"] is None or row["board_id"] in common.board_ids_for(ctx))


def _load(ctx, article_id):
    from .. import HttpError
    row = knowledge.get(ctx.conn, article_id)
    if not _visible(ctx, row):
        raise HttpError("404 Not Found", "No such article.")
    return row


def index(ctx):
    from .. import Response
    common.require_module(ctx, "KNOWLEDGE")
    q = ctx.request.query
    status = q.get("status", "") if q.get("status", "") in knowledge.STATUSES else ""
    rows = knowledge.search(ctx.conn, q=q.get("q", ""), status=status or None, board_ids=common.board_ids_for(ctx))
    if not status:
        rows = [r for r in rows if r["status"] != "RETIRED"]
    trs = "".join(
        f"<tr><td><a href='/kb/{t.esc(r['article_id'])}'>{t.esc(r['article_id'])}</a></td>"
        f"<td><b>{t.esc(r['title'])}</b></td><td>{t.chip(STATUS_WORDS[r['status']])}</td>"
        f"<td>{t.esc(knowledge.AUDIENCES[r['audience']])}</td><td>{t.esc(r['board_name'] or 'Every board')}</td>"
        f"<td class=center>{r['uses']}</td><td class=muted>{t.esc(r['updated_at'])}</td></tr>" for r in rows)
    opts = "<option value=''>Drafts and published</option>" + "".join(
        f"<option value='{k}'{' selected' if k == status else ''}>{v}</option>" for k, v in STATUS_WORDS.items())
    write = ("<a class=btn href='/kb/new'>" + t.icon("plus") + " Write an article</a>"
             if common.allows(ctx, "KNOWLEDGE", "WRITE") else "")
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + "<h1>Knowledge</h1><p class=sub>Fixes written once and used again. A ticket offers the articles for its "
              "Subtype › Item and board first; link the one that helped, and its use count tells the desk which "
              "articles earn their keep. Articles for requesters appear on the portal's Help page once published.</p>"
            + "<div class=card><form method=get action='/kb' class='row schedbar'>"
              f"<div style='flex:1 1 260px'><input name=q value='{t.esc(q.get('q', ''))}' placeholder='Search titles and words'></div>"
              f"<div style='flex:0 0 200px'><select name=status>{opts}</select></div>"
              "<div style='flex:0 0 auto'><button class=ghost type=submit>Search</button></div>"
              f"<div style='flex:0 0 auto'>{write}</div></form>"
              "<div class=tablewrap><table><thead><tr><th>Article</th><th>Title</th><th>Status</th><th>For</th><th>Board</th>"
              f"<th>Uses</th><th>Updated</th></tr></thead><tbody>{trs or '<tr><td colspan=7 class=muted>No articles yet.</td></tr>'}"
              "</tbody></table></div></div>")
    return Response(body=t.page("Knowledge", body, user=ctx.user, active="kb"))


def _form(ctx, row=None, *, error: str = "", values: dict | None = None) -> str:
    v = values or (dict(row) if row is not None else {"audience": "INTERNAL"})
    boards = [(b["board_id"], b["display_name"]) for b in ctx.conn.execute(
        "SELECT board_id, display_name FROM board WHERE COALESCE(inactive, 0) = 0 ORDER BY display_name")
        if b["board_id"] in common.board_ids_for(ctx)]
    board_opts = "<option value=''>Every board</option>" + "".join(
        f"<option value='{t.esc(k)}'{' selected' if k == v.get('board_id') else ''}>{t.esc(n)}</option>" for k, n in boards)
    pairs = "<option value=''>(any)</option>" + "".join(
        f"<option value='{t.esc(c['catalogue_item_id'])}'{' selected' if c['catalogue_item_id'] == v.get('catalogue_item_id') else ''}>"
        f"{t.esc(c['label'])}</option>" for c in setup.catalogue_choices(ctx.conn))
    aud = "".join(f"<option value='{k}'{' selected' if k == v.get('audience') else ''}>{t.esc(w)}</option>"
                  for k, w in knowledge.AUDIENCES.items())
    action = f"/kb/{t.esc(row['article_id'])}/save" if row is not None else "/kb/new"
    return ((f"<div class='banner err'>{t.esc(error)}</div>" if error else "")
            + f"<div class=card><form method=post action='{action}' class=stack style='max-width:none'>"
              f"<label>Title<input name=title required maxlength=200 value='{t.esc(v.get('title') or '')}'"
              " placeholder='Label printer in a ward prints blank labels'></label>"
              "<div class=grid2>"
              f"<div><label>For</label><select name=audience>{aud}</select></div>"
              f"<div><label>Board</label><select name=board_id>{board_opts}</select></div>"
              f"<div style='grid-column:1/-1'><label>Subtype › Item</label><select name=catalogue_item_id>{pairs}</select></div></div>"
              "<label>The fix, step by step (Markdown: # heading, - list, **bold**, `code`)"
              f"<textarea name=body required style='min-height:320px'>{t.esc(v.get('body') or '')}</textarea></label>"
              "<p class=why style='margin:0'>Write what someone needs to fix it again: the symptom, the cause, the steps, "
              "how to check it worked. A ward, a room or a machine says it best; a patient never needs naming.</p>"
              "<div><button type=submit>Save</button> <a class='btn ghost' href='/kb'>Cancel</a></div></form></div>")


def new_form(ctx):
    from .. import Response
    common.require_module(ctx, "KNOWLEDGE", "WRITE")
    return Response(body=t.page("Write an article", "<h1>Write an article</h1>" + _form(ctx), user=ctx.user, active="kb"))


def create(ctx):
    from .. import Response
    common.require_module(ctx, "KNOWLEDGE", "WRITE")
    f = ctx.request.form()
    if f.get("board_id") and f["board_id"] not in common.board_ids_for(ctx):
        return _back("/kb")
    try:
        aid = knowledge.create(ctx.conn, title=f.get("title", ""), body=f.get("body", ""),
                               audience=f.get("audience", "INTERNAL"), board_id=f.get("board_id") or None,
                               catalogue_item_id=f.get("catalogue_item_id") or None, at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except knowledge.Refused as exc:
        ctx.conn.rollback()
        return Response("400 Bad Request", t.page("Write an article", "<h1>Write an article</h1>" + _form(
            ctx, error=str(exc), values=dict(f)), user=ctx.user, active="kb"))
    return _back(f"/kb/{aid}", msg="Saved as a draft. Publish it when it is ready.")


def detail(ctx, article_id):
    from .. import Response
    common.require_module(ctx, "KNOWLEDGE")
    row = _load(ctx, article_id)
    q = ctx.request.query
    can_write = common.allows(ctx, "KNOWLEDGE", "WRITE")
    aid = t.esc(row["article_id"])
    actions = ""
    if can_write:
        acts = [f"<a class='btn ghost' href='/kb/{aid}/edit'>Edit</a>"]
        if row["status"] != "PUBLISHED":
            acts.append(f"<form method=post action='/kb/{aid}/status' class=inline><input type=hidden name=status value=PUBLISHED>"
                        "<button type=submit>Publish</button></form>")
        if row["status"] == "PUBLISHED":
            acts.append(f"<form method=post action='/kb/{aid}/status' class=inline><input type=hidden name=status value=DRAFT>"
                        "<button class=ghost type=submit>Back to draft</button></form>")
        if row["status"] != "RETIRED" and common.allows(ctx, "KNOWLEDGE", "ADMIN"):
            acts.append(f"<form method=post action='/kb/{aid}/status' class=inline><input type=hidden name=status value=RETIRED>"
                        "<button class=ghost type=submit>Retire</button></form>")
        actions = "<div class='row schedbar'>" + "".join(f"<div style='flex:0 0 auto'>{a}</div>" for a in acts) + "</div>"
    flagged = knowledge.flags(ctx.conn, row["article_id"])
    flag = ("<div class='banner err'>This article may name a patient (" + t.esc("; ".join(flagged))
            + "). Please rewrite it with the ward, room or machine instead.</div>") if flagged and can_write else ""
    tickets = ctx.conn.execute("SELECT k.work_item_id FROM kb_ticket k JOIN ticket tk ON tk.work_item_id = k.work_item_id"
                               " WHERE k.article_id = ? ORDER BY k.linked_at DESC", (row["article_id"],)).fetchall()
    seen = common.board_ids_for(ctx)
    used = [r["work_item_id"] for r in tickets if ctx.conn.execute(
        "SELECT board_id FROM ticket WHERE work_item_id = ?", (r["work_item_id"],)).fetchone()[0] in seen]
    revs = knowledge.revisions(ctx.conn, row["article_id"])
    history = "".join(f"<li>v{r['version']} · {t.esc(r['saved_at'])} · {t.esc(r['saved_by'])}</li>" for r in revs)
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "") + flag
            + f"<h1>{t.esc(row['title'])}</h1><p class=sub>{aid} · {t.chip(STATUS_WORDS[row['status']])} · "
              f"{t.esc(knowledge.AUDIENCES[row['audience']])} · {t.esc(row['board_name'] or 'Every board')} · "
              f"version {row['version']} · used on {row['uses']} ticket(s) · <a href='/kb'>Knowledge</a></p>"
            + actions + f"<div class=card><div class=md>{t.md_to_html(row['body'])}</div></div>"
            + "<div class=grid2><div class=card><h3>" + t.icon("note") + "Used on</h3>"
            + ("<ul class=plain>" + "".join(f"<li><a href='/ticket/{t.esc(w)}'>{t.esc(w)}</a></li>" for w in used[:50]) + "</ul>"
               if used else "<div class=muted>No ticket yet.</div>")
            + "</div><div class=card><h3>" + t.icon("clock") + "History</h3><ul class=plain>" + history + "</ul></div></div>")
    return Response(body=t.page(row["title"], body, user=ctx.user, active="kb"))


def edit_form(ctx, article_id):
    from .. import Response
    common.require_module(ctx, "KNOWLEDGE", "WRITE")
    row = _load(ctx, article_id)
    return Response(body=t.page("Edit article", f"<h1>Edit {t.esc(row['article_id'])}</h1>" + _form(ctx, row),
                                user=ctx.user, active="kb"))


def save(ctx, article_id):
    from .. import Response
    common.require_module(ctx, "KNOWLEDGE", "WRITE")
    row = _load(ctx, article_id)
    f = ctx.request.form()
    if f.get("board_id") and f["board_id"] not in common.board_ids_for(ctx):
        return _back(f"/kb/{article_id}", err="You are not on that board.")
    try:
        what = knowledge.save(ctx.conn, article_id, title=f.get("title", ""), body=f.get("body", ""),
                              audience=f.get("audience", "INTERNAL"), board_id=f.get("board_id") or None,
                              catalogue_item_id=f.get("catalogue_item_id") or None, at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except knowledge.Refused as exc:
        ctx.conn.rollback()
        return Response("400 Bad Request", t.page("Edit article", "<h1>Edit</h1>" + _form(
            ctx, row, error=str(exc), values=dict(f)), user=ctx.user, active="kb"))
    return _back(f"/kb/{article_id}", msg=f"Article {what}.")


def set_status(ctx, article_id):
    status = ctx.request.form().get("status", "")
    common.require_module(ctx, "KNOWLEDGE", "ADMIN" if status == "RETIRED" else "WRITE")
    _load(ctx, article_id)
    try:
        what = knowledge.set_status(ctx.conn, article_id, status, at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except knowledge.Refused as exc:
        return _back(f"/kb/{article_id}", err=str(exc))
    return _back(f"/kb/{article_id}", msg=f"Article {what}.")


def link_ticket(ctx, work_item_id):
    """POST /ticket/<id>/kb: this article helped with this ticket."""
    from .ticket import _back as ticket_back, _load as ticket_load
    common.require_module(ctx, "KNOWLEDGE")
    tk = ticket_load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    aid = (ctx.request.form().get("article_id", "") or "").strip().upper()
    row = knowledge.get(ctx.conn, aid)
    if not _visible(ctx, row) or row["status"] == "RETIRED":
        return ticket_back(work_item_id, err=f"No article {aid} to link")
    knowledge.link(ctx.conn, aid, work_item_id, at=ctx.now, actor=ctx.user.id)
    ctx.conn.commit()
    return ticket_back(work_item_id, msg=f"{aid} linked")


def ticket_card(ctx, tk, *, can_work: bool) -> str:
    """The Knowledge pod on a ticket: what was used, and what might help."""
    if not common.allows(ctx, "KNOWLEDGE"):
        return ""
    wid = t.esc(tk["work_item_id"])
    used = knowledge.linked(ctx.conn, tk["work_item_id"])
    used_ids = {r["article_id"] for r in used}
    ideas = [a for a in knowledge.suggest(ctx.conn, tk["work_item_id"], board_ids=common.board_ids_for(ctx))
             if a["article_id"] not in used_ids]
    rows = "".join(f"<li>✓ <a href='/kb/{t.esc(r['article_id'])}'>{t.esc(r['article_id'])}</a> {t.esc(r['title'])}</li>" for r in used)
    rows += "".join(
        f"<li><a href='/kb/{t.esc(a['article_id'])}'>{t.esc(a['article_id'])}</a> {t.esc(a['title'])}"
        + (f" <form method=post action='/ticket/{wid}/kb' style='display:inline'><input type=hidden name=article_id "
           f"value='{t.esc(a['article_id'])}'><button class='ghost small' type=submit>It helped</button></form>" if can_work else "")
        + "</li>" for a in ideas)
    add = (f"<form method=post action='/ticket/{wid}/kb' class=row style='margin-top:6px'>"
           "<div><input name=article_id placeholder='KB-0001' aria-label='Article to link'></div>"
           "<div style='flex:0 0 auto'><button class=ghost type=submit>Link</button></div></form>" if can_work else "")
    return (f"<div class=card data-pod=knowledge><h3>{t.icon('note')}Knowledge</h3>"
            + (f"<ul class=plain>{rows}</ul>" if rows else "<div class=muted>No article matches yet. <a href='/kb/new'>Write one</a>.</div>")
            + add + "</div>")


# ----------------------------------------------------------------- the portal

def portal_index(ctx):
    from .. import Response
    q = ctx.request.query.get("q", "")
    rows = knowledge.search(ctx.conn, q=q, status="PUBLISHED", audience="REQUESTER", board_ids=set())
    items = "".join(f"<li><a href='/my/help/{t.esc(r['article_id'])}'><b>{t.esc(r['title'])}</b></a></li>" for r in rows)
    body = ("<h1>Help</h1><p class=sub>Answers to the questions people ask most. If none fits, "
            "<a href='/my'>raise a request</a>.</p><div class=card>"
            f"<form method=get action='/my/help' class='row schedbar'><div style='flex:1 1 240px'><input name=q value='{t.esc(q)}'"
            " placeholder='Search the help'></div><div style='flex:0 0 auto'><button class=ghost type=submit>Search</button></div></form>"
            + (f"<ul class=plain>{items}</ul>" if items else "<div class=muted>Nothing here yet.</div>") + "</div>")
    return Response(body=t.page("Help", body, user=ctx.user))


def portal_detail(ctx, article_id):
    from .. import HttpError, Response
    row = knowledge.get(ctx.conn, article_id)
    if row is None or row["status"] != "PUBLISHED" or row["audience"] != "REQUESTER" or row["board_id"] is not None \
            and False:
        raise HttpError("404 Not Found", "No such help page.")
    body = (f"<h1>{t.esc(row['title'])}</h1><div class=card><div class=md>{t.md_to_html(row['body'])}</div></div>"
            "<p><a href='/my/help'>All help</a> · <a href='/my'>Raise a request</a></p>")
    return Response(body=t.page(row["title"], body, user=ctx.user))
