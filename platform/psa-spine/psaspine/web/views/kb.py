"""The knowledge base pages (039): search, read, write, publish, and the portal's Help.

Gated by the security role's KNOWLEDGE level: READ to search and read, WRITE to
write and publish, ADMIN to retire. A board's own articles are shown only to
the board's members, like its tickets. Requesters see REQUESTER articles that
are PUBLISHED, on the portal's Help page, and nothing else.
"""
from __future__ import annotations

import re
import urllib.parse

from ... import kbfiles, knowledge, phi, setup
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
    cats = knowledge.categories(ctx.conn)
    cat = q.get("category", "") if q.get("category", "") in {c["category_id"] for c in cats} else ""
    rows = knowledge.search(ctx.conn, q=q.get("q", ""), status=status or None, board_ids=common.board_ids_for(ctx),
                            category_id=cat or None)
    if not status:
        rows = [r for r in rows if r["status"] != "RETIRED"]
    trs = "".join(
        f"<tr><td><a href='/kb/{t.esc(r['article_id'])}'>{t.esc(r['article_id'])}</a></td>"
        f"<td><b>{t.esc(r['title'])}</b></td><td>{t.chip(STATUS_WORDS[r['status']])}</td>"
        f"<td>{t.esc(knowledge.AUDIENCES[r['audience']])}</td><td>{t.esc(r['board_name'] or 'Every board')}</td>"
        f"<td>{t.esc(r['category_name'] or '')}</td>"
        f"<td class=center>{r['uses']}</td><td class=muted>{t.esc(r['updated_at'])}</td></tr>" for r in rows)
    opts = "<option value=''>Drafts and published</option>" + "".join(
        f"<option value='{k}'{' selected' if k == status else ''}>{v}</option>" for k, v in STATUS_WORDS.items())
    cat_opts = ("<option value=''>Every category</option>" + "".join(
        f"<option value='{t.esc(c['category_id'])}'{' selected' if c['category_id'] == cat else ''}>{t.esc(c['name'])}</option>" for c in cats)
        if cats else "")
    write = ("<a class=btn href='/kb/new'>" + t.icon("plus") + " Write an article</a>"
             if common.allows(ctx, "KNOWLEDGE", "WRITE") else "")
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + "<h1>Knowledge</h1><p class=sub>Fixes written once and used again. A ticket offers the articles for its "
              "Subtype › Item and board first; link the one that helped, and its use count tells the desk which "
              "articles earn their keep. Articles for requesters appear on the portal's Help page once published.</p>"
            + "<div class=card><form method=get action='/kb' class='row schedbar'>"
              f"<div style='flex:1 1 260px'><input name=q value='{t.esc(q.get('q', ''))}' placeholder='Search titles and words'></div>"
              f"<div style='flex:0 0 200px'><select name=status>{opts}</select></div>"
            + (f"<div style='flex:0 0 200px'><select name=category aria-label='Category'>{cat_opts}</select></div>" if cat_opts else "")
            + "<div style='flex:0 0 auto'><button class=ghost type=submit>Search</button></div>"
              f"<div style='flex:0 0 auto'>{write}</div></form>"
              "<div class=tablewrap><table><thead><tr><th>Article</th><th>Title</th><th>Status</th><th>For</th><th>Board</th>"
              f"<th>Category</th><th>Uses</th><th>Updated</th></tr></thead><tbody>{trs or '<tr><td colspan=8 class=muted>No articles yet.</td></tr>'}"
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
    cats = knowledge.categories(ctx.conn)
    cat_field = ("<div><label>Category</label><select name=category_id><option value=''>(none)</option>" + "".join(
        f"<option value='{t.esc(c['category_id'])}'{' selected' if c['category_id'] == v.get('category_id') else ''}>{t.esc(c['name'])}</option>"
        for c in cats) + "</select></div>") if cats else ""
    action = f"/kb/{t.esc(row['article_id'])}/save" if row is not None else "/kb/new"
    return ((f"<div class='banner err'>{t.esc(error)}</div>" if error else "")
            + f"<div class=card><form method=post action='{action}' class=stack style='max-width:none'"
              " enctype='multipart/form-data'>"
              "<input type=file name=pics multiple accept='image/*' hidden class=kbpicsin>"
              "<input type=hidden name=pic_tokens value=''>"
              f"<label>Title<input name=title required maxlength=200 value='{t.esc(v.get('title') or '')}'"
              " placeholder='Label printer in a ward prints blank labels'></label>"
              "<div class=grid2>"
              f"<div><label>For</label><select name=audience>{aud}</select></div>"
              f"<div><label>Board</label><select name=board_id>{board_opts}</select></div>"
              f"<div{'' if cat_field else ' style=grid-column:1/-1'}><label>Subtype › Item</label><select name=catalogue_item_id>{pairs}</select></div>"
              f"{cat_field}</div>"
              "<label for=kbbody>The fix, step by step (Markdown: # heading, - list, **bold**, `code`; a picture from Files as "
              "![caption](file:3), a link as [words](https://…))</label>"
              f"<textarea id=kbbody name=body required data-kbpaste data-article='{t.esc(row['article_id']) if row is not None else ''}'"
              f" aria-describedby=kbpastehelp style='min-height:320px'>{t.esc(v.get('body') or '')}</textarea>"
              "<p id=kbpastehelp class=why style='margin:0'><b>Paste or drag a picture straight into the text</b> "
              "and it goes where the cursor is; it is kept when you save. Write what someone needs to fix it again: "
              "the symptom, the cause, the steps, how to check it worked. A ward, a room or a machine says it best; "
              "a patient never needs naming.</p>"
              "<div class=kbpreviewwrap><h4 id=kbpreviewh>Preview</h4><div id=kbpreview class='md kbpreview' role=region"
              " aria-labelledby=kbpreviewh></div></div>"
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
        raw = f.get("body", "")
        aid = knowledge.create(ctx.conn, title=f.get("title", ""), body=raw,
                               audience=f.get("audience", "INTERNAL"), board_id=f.get("board_id") or None,
                               catalogue_item_id=f.get("catalogue_item_id") or None, category_id=f.get("category_id") or None,
                               at=ctx.now, actor=ctx.user.id)
        # pictures pasted into the text: kept as the article's files, and the text
        # names them by number -- on version 1 itself, so creating is one version
        final = _paste_pictures(ctx, aid, f, raw)
        if final != raw:
            ctx.conn.execute("UPDATE kb_article SET body = ? WHERE article_id = ? AND version = 1", (final, aid))
            ctx.conn.execute("UPDATE kb_revision SET body = ? WHERE article_id = ? AND version = 1", (final, aid))
        ctx.conn.commit()
    except (knowledge.Refused, kbfiles.Refused) as exc:
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
    tickets = ctx.conn.execute("SELECT k.work_item_id, tk.board_id FROM kb_ticket k JOIN ticket tk"
                               " ON tk.work_item_id = k.work_item_id WHERE k.article_id = ? ORDER BY k.linked_at DESC",
                               (row["article_id"],)).fetchall()
    seen = common.board_ids_for(ctx)
    used = [r["work_item_id"] for r in tickets if r["board_id"] in seen]
    common.audit_restricted_reads(ctx, (r["board_id"] for r in tickets[:50] if r["board_id"] in seen),
                                  detail=f"article {row['article_id']} listed")
    revs = knowledge.revisions(ctx.conn, row["article_id"])
    history = "".join(f"<li>v{r['version']} · {t.esc(r['saved_at'])} · {t.esc(r['saved_by'])}</li>" for r in revs)
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "") + flag
            + f"<h1>{t.esc(row['title'])}</h1><p class=sub>{aid} · {t.chip(STATUS_WORDS[row['status']])} · "
              f"{t.esc(knowledge.AUDIENCES[row['audience']])} · {t.esc(row['board_name'] or 'Every board')} · "
            + (f"{t.esc(row['category_name'])} · " if row["category_name"] else "")
            + f"version {row['version']} · used on {row['uses']} ticket(s) · <a href='/kb'>Knowledge</a></p>"
            + actions + "<div class=card><div class=md>"
            + t.md_to_html(row["body"], file_url=kbfiles.resolver(ctx.conn, row["article_id"], portal=False, base=f"/kb/{aid}/file/"))
            + _pictures(kbfiles.unplaced(ctx.conn, row["article_id"], row["body"], portal=False), base=f"/kb/{aid}/file/",
                        desk=True)
            + "</div></div>" + _files_card(ctx, row, can_write=can_write)
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
        body = _paste_pictures(ctx, article_id, f, f.get("body", ""))
        what = knowledge.save(ctx.conn, article_id, title=f.get("title", ""), body=body,
                              audience=f.get("audience", "INTERNAL"), board_id=f.get("board_id") or None,
                              catalogue_item_id=f.get("catalogue_item_id") or None, category_id=f.get("category_id") or None,
                              at=ctx.now, actor=ctx.user.id)
        ctx.conn.commit()
    except (knowledge.Refused, kbfiles.Refused) as exc:
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
    return Response(body=t.page("Help", body, user=ctx.user, active="help"))


def portal_detail(ctx, article_id):
    from .. import HttpError, Response
    row = knowledge.get(ctx.conn, article_id)
    # The same rule as the list: a board's article is never portal content, so a
    # requester on no board cannot open one by guessing its sequential id.
    if row is None or row["status"] != "PUBLISHED" or row["audience"] != "REQUESTER" or row["board_id"] is not None:
        raise HttpError("404 Not Found", "No such help page.")
    shown = t.md_to_html(row["body"], file_url=kbfiles.resolver(ctx.conn, row["article_id"], portal=True,
                                                                 base=f"/my/help/{t.esc(row['article_id'])}/file/"))
    shown += _pictures(kbfiles.unplaced(ctx.conn, row["article_id"], row["body"], portal=True),
                       base=f"/my/help/{t.esc(row['article_id'])}/file/")
    files = [f for f in kbfiles.of_article(ctx.conn, row["article_id"]) if kbfiles.visible(f, portal=True)
             and not f["media_type"].startswith("image/")]
    downloads = ("<div class=card><h3>" + t.icon("paperclip") + "Files</h3><ul class=plain>" + "".join(
        f"<li><a href='/my/help/{t.esc(row['article_id'])}/file/{f['file_id']}'>{t.esc(f['caption'] or f['filename'])}</a></li>"
        for f in files) + "</ul></div>") if files else ""
    body = (f"<h1>{t.esc(row['title'])}</h1><div class=card><div class=md>{shown}</div></div>" + downloads
            + "<p><a href='/my/help'>All help</a> · <a href='/my'>Raise a request</a></p>")
    return Response(body=t.page(row["title"], body, user=ctx.user, active="help"))


_PASTE_TOKEN = re.compile(r"[a-z0-9]{6,32}")
_PASTE_REF = re.compile(r"!\[[^\]]*\]\(paste:[a-z0-9]{6,32}\)")


def _paste_pictures(ctx, article_id: str, f, body: str) -> str:
    """Pictures pasted or dropped into the article's text (Dada, 16 Oct 2026:
    like IT Glue). The page carries each as a `pics` file named by a token in
    `pic_tokens`, and the text calls it ![caption](paste:token). Each one the
    text still calls is kept as the article's file -- through the same review
    as any other -- and the text is rewritten to its number. A pasted picture
    taken back out of the text before saving is not kept."""
    files = ctx.request.files("pics") if ctx.request.is_multipart() else []
    tokens = [x for x in (f.get("pic_tokens") or "").split(",") if x]
    for (name, data), tok in zip(files, tokens):
        if not _PASTE_TOKEN.fullmatch(tok) or f"(paste:{tok})" not in body or not data:
            continue
        kept = kbfiles.add(ctx.conn, article_id, data, name or "picture.png", actor=ctx.user.id, at=ctx.now)
        body = body.replace(f"(paste:{tok})", f"(file:{kept['file_id']})")
    return _PASTE_REF.sub("", body)                    # a reference whose picture never arrived


def preview(ctx):
    """The text as it will read, for the editor's preview: the same renderer as
    the article itself, the saved pictures by their address and the pasted ones
    left for the page to fill in from what is still in the browser."""
    from .. import Response
    common.require_module(ctx, "KNOWLEDGE", "WRITE")
    f = ctx.request.form()
    body = (f.get("body") or "")[:200_000]
    aid = (f.get("article_id") or "").strip()
    known = None
    if aid:
        row = _load(ctx, aid)
        known = kbfiles.resolver(ctx.conn, row["article_id"], portal=False, base=f"/kb/{t.esc(row['article_id'])}/file/")
    pasted: dict[int, str] = {}

    def to_number(m):
        n = 2_000_000_000 + len(pasted)
        pasted[n] = m.group(1)
        return f"(file:{n})"
    body = re.sub(r"\(paste:([a-z0-9]{6,32})\)", to_number, body)

    def url(n: int):
        if n in pasted:
            return "about:blank#paste-" + pasted[n]
        return known(n) if known else None
    html_ = t.md_to_html(body, file_url=url)
    if aid:
        html_ += _pictures(kbfiles.unplaced(ctx.conn, row["article_id"], body, portal=False),
                           base=f"/kb/{t.esc(row['article_id'])}/file/", desk=True)
    return Response(body=html_ or "<p class=muted>Nothing written yet.</p>",
                    headers=[("Cache-Control", "no-store")])


def _pictures(rows, *, base: str, desk: bool = False) -> str:
    """The pictures on an article that its text does not place, shown after the
    text so a picture added is a picture seen (Dada, 16 Oct 2026: "it should
    work like how itglue field works"). The desk says when one still awaits
    its patient-information review, which the portal never shows."""
    if not rows:
        return ""
    figs = "".join(
        f"<figure class=kbfig><img src='{base}{r['file_id']}' alt='{t.esc(r['caption'] or r['filename'])}' class=kbimg loading=lazy>"
        + (f"<figcaption>{t.esc(r['caption'])}</figcaption>" if r["caption"] else "")
        + ("<figcaption class=muted>awaiting review: requesters see it once it is cleared</figcaption>"
           if desk and r["review_status"] == "PENDING" else "")
        + "</figure>" for r in rows)
    return f"<div class=kbpics>{figs}</div>"


# ------------------------------------------------------------ files (051)

FILE_WORDS = {"PENDING": "awaiting review", "CLEARED": "cleared", "WITHHELD": "withheld"}


def _size(n: int) -> str:
    return f"{n / 1024:.0f} KB" if n >= 1024 else f"{n} B"


def _files_card(ctx, row, *, can_write: bool) -> str:
    """The article's files: what each is, its review, how to show it in the
    text; upload and review for a writer, removal for an administrator."""
    aid = t.esc(row["article_id"])
    can_admin = common.allows(ctx, "KNOWLEDGE", "ADMIN")
    lines = []
    for f in kbfiles.of_article(ctx.conn, row["article_id"]):
        served = kbfiles.visible(f, portal=False)
        url = f"/kb/{aid}/file/{f['file_id']}"
        thumb = (f"<img src='{url}' alt='' class=kbthumb>" if served and f["media_type"].startswith("image/") else "")
        name = f"<a href='{url}'>{t.esc(f['filename'])}</a>" if served else t.esc(f["filename"])
        chip = {"PENDING": "sla-warn", "CLEARED": "sla-ok", "WITHHELD": "sla-bad"}[f["review_status"]]
        forms = ""
        if can_write:
            forms = (f"<form method=post action='/kb/{aid}/file/{f['file_id']}/review' class=inline>"
                     "<button class='ghost small' name=decision value=CLEAR type=submit>Clear</button> "
                     "<button class='ghost small' name=decision value=WITHHOLD type=submit>Withhold</button></form>")
        if can_admin:
            forms += (f" <form method=post action='/kb/{aid}/file/{f['file_id']}/remove' class=inline>"
                      "<button class='ghost small danger' type=submit>Remove</button></form>")
        lines.append(f"<li>{thumb}{name} <span class=muted>· {t.esc(f['media_type'])} · {_size(f['size_received'])} · "
                     f"{t.esc(f['uploaded_by'])} {t.esc(f['uploaded_at'])}</span> "
                     f"<span class='chip {chip}'>{FILE_WORDS[f['review_status']]}</span>"
                     + (f" <span class=muted>{t.esc(f['caption'])}</span>" if f["caption"] else "")
                     + (f"<br><code>![{t.esc(f['caption'] or f['filename'])}](file:{f['file_id']})</code>"
                        if f["media_type"].startswith("image/") else f"<br><code>[{t.esc(f['caption'] or f['filename'])}](file:{f['file_id']})</code>")
                     + (f"<br>{forms}" if forms else "") + "</li>")
    upload = ""
    if can_write:
        upload = (f"<form method=post action='/kb/{aid}/file' enctype='multipart/form-data' class=fields style='margin-top:10px'>"
                  "<label>Add a file</label><input type=file name=file required>"
                  "<label>Caption</label><input name=caption maxlength=200 placeholder='Where the switch is'>"
                  "<div style='margin-top:8px'><button class=ghost type=submit>Upload</button></div>"
                  "<p class=why style='margin:6px 0 0'>Pictures, PDFs, logs and Office documents. Every file waits for a "
                  "patient-information review before a requester can see it; the desk sees it at once. "
                  "Paste the code line under a file into the text to show it there.</p></form>")
    return ("<div class=card><h3>" + t.icon("paperclip") + "Files</h3>"
            + (f"<ul class=plain>{''.join(lines)}</ul>" if lines else "<div class=muted>No file yet.</div>") + upload + "</div>")


def _file_on(ctx, article_id, file_id):
    from .. import HttpError
    try:
        row = kbfiles.get(ctx.conn, int(file_id))
    except ValueError:
        row = None
    if row is None or row["article_id"] != article_id or row["removed_at"]:
        raise HttpError("404 Not Found", "No such file on this article.")
    return row


def _serve(ctx, row):
    """The file's bytes: inline when it is a picture, a download otherwise; never
    a page the browser runs."""
    from .. import HttpError, Response
    try:
        _, data = kbfiles.read(ctx.conn, row["file_id"])
    except kbfiles.Removed:
        raise HttpError("410 Gone", "That file was removed.")
    except (OSError, LookupError):
        raise HttpError("404 Not Found", "That file is missing or damaged; it was not served.")
    ascii_name = row["filename"].encode("ascii", "replace").decode().replace("?", "_").replace('"', "_")
    kind = "inline" if row["media_type"].startswith("image/") else "attachment"
    disposition = f'{kind}; filename="{ascii_name}"; ' + f"filename*=UTF-8''{urllib.parse.quote(row['filename'])}"
    return Response(body=data, content_type=row["media_type"], headers=[
        ("Content-Disposition", disposition), ("Content-Security-Policy", "sandbox"),
        ("Cache-Control", "private, no-store")])


def _back_to(article_id, **q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    return redirect(f"/kb/{article_id}" + ("?" + urllib.parse.urlencode(q) if q else ""))


def upload(ctx, article_id):
    common.require_module(ctx, "KNOWLEDGE", "WRITE")
    row = _load(ctx, article_id)
    files = ctx.request.files("file")
    caption = ctx.request.form().get("caption", "")
    if not files:
        return _back_to(article_id, err="Choose a file first.")
    kept = []
    try:
        for filename, data in files:
            r = kbfiles.add(ctx.conn, row["article_id"], data, filename, caption=caption, actor=ctx.user.id, at=ctx.now)
            kept.append(r["file_id"])
        ctx.conn.commit()
    except kbfiles.Refused as exc:
        ctx.conn.rollback()
        return _back_to(article_id, err=f"Not kept: {exc}")
    return _back_to(article_id, msg=f"File {', '.join(str(k) for k in kept)} added; show it in the text as ![caption](file:{kept[-1]})")


def file(ctx, article_id, file_id):
    from .. import HttpError
    common.require_module(ctx, "KNOWLEDGE")
    _load(ctx, article_id)
    row = _file_on(ctx, article_id, file_id)
    if not kbfiles.visible(row, portal=False):
        raise HttpError("404 Not Found", "No such file on this article.")
    return _serve(ctx, row)


def file_review(ctx, article_id, file_id):
    common.require_module(ctx, "KNOWLEDGE", "WRITE")
    _load(ctx, article_id)
    row = _file_on(ctx, article_id, file_id)
    decision = ctx.request.form().get("decision", "")
    try:
        r = kbfiles.review(ctx.conn, row["file_id"], decision, actor=ctx.user.id, at=ctx.now)
        ctx.conn.commit()
    except ValueError as exc:
        return _back_to(article_id, err=str(exc))
    return _back_to(article_id, msg=f"{r['filename']} {FILE_WORDS[r['review_status']]}")


def file_remove(ctx, article_id, file_id):
    common.require_module(ctx, "KNOWLEDGE", "ADMIN")
    _load(ctx, article_id)
    row = _file_on(ctx, article_id, file_id)
    kbfiles.remove(ctx.conn, row["file_id"], actor=ctx.user.id, at=ctx.now)
    ctx.conn.commit()
    return _back_to(article_id, msg=f"{row['filename']} removed")


def portal_file(ctx, article_id, file_id):
    from .. import HttpError
    row = knowledge.get(ctx.conn, article_id)
    if row is None or row["status"] != "PUBLISHED" or row["audience"] != "REQUESTER" or row["board_id"] is not None:
        raise HttpError("404 Not Found", "No such help page.")
    f = _file_on(ctx, article_id, file_id)
    if not kbfiles.visible(f, portal=True):
        raise HttpError("404 Not Found", "No such file on this help page.")
    return _serve(ctx, f)
