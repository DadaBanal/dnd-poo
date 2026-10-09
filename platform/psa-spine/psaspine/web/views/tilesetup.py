"""Setup › Portal tiles (078): the tiles a requester chooses from on My requests.

Dada, 9 Oct 2026, confirmed before building: a Setup page, not tiles fixed in
the code. A system administrator adds a tile, gives it words, a picture, a
board and a Type › Subtype › Item, gives it smaller tiles one level deep, and
the questions it asks; renames, reorders and retires. The PMC starter set comes
from `psaspine portal-tiles` (preview first), and is edited here afterwards.
"""
from __future__ import annotations

import urllib.parse

from ... import portal_tiles as pt
from ... import setup
from .. import templates as t
from . import common


def _back(**q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    return redirect("/admin/portal-tiles" + ("?" + urllib.parse.urlencode(q) if q else ""))


def _try(ctx, fn, ok):
    try:
        out = fn()
        ctx.conn.commit()
    except (ValueError, LookupError) as exc:
        ctx.conn.rollback()
        return _back(err=str(exc))
    return _back(msg=ok(out) if callable(ok) else ok)


def _boards(ctx):
    return ctx.conn.execute("SELECT board_id, display_name FROM board WHERE is_live = 1 AND is_unrouted = 0"
                            " AND COALESCE(inactive, 0) = 0 ORDER BY display_name").fetchall()


def _pair_id(ctx, label: str) -> str | None:
    """The catalogue pair a typed 'Type › Subtype › Item' names. Empty: none."""
    label = " ".join((label or "").split())
    if not label:
        return None
    for c in setup.catalogue_choices(ctx.conn):
        if c["label"].lower() == label.lower():
            return c["catalogue_item_id"]
    raise ValueError(f"No live Type › Subtype › Item is called {label!r}. Pick one from the list as you type.")


def _int(v, default=0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def index(ctx):
    from .. import Response
    common.require_sysadmin(ctx)
    q = ctx.request.query
    banners = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
               + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else ""))
    head = ("<h1>Portal tiles</h1><p class=sub>What a requester chooses from on <a href='/my'>My requests</a>. A tile "
            "sends the request to its board with its Type › Subtype › Item already chosen, and asks its questions; "
            "a tile can open a row of smaller tiles, which take its board, Item and questions unless they say their "
            "own. Every department sees every tile. <b>Something else, or not sure</b> is always last: it is the "
            "plain form, routed by Setup › Departments as before. <a href='/admin'>Setup</a></p>")
    if not pt.available(ctx.conn):
        return Response(body=t.page("Portal tiles", banners + head + "<div class=card><p>Step 078 is not applied to "
                                    "this store yet, so the portal shows the plain form. Nothing here until it is.</p>"
                                    "</div>", user=ctx.user, active="admin"))
    boards = _boards(ctx)
    rows = pt.tiles(ctx.conn, all_rows=True)
    tops = [r for r in rows if r["parent_id"] is None]
    pairs = setup.catalogue_choices(ctx.conn)
    datalist = "<datalist id=pairs>" + "".join(f"<option value='{t.esc(c['label'])}'>" for c in pairs) + "</datalist>"
    field_opts = "".join(f"<option value={k}>{t.esc(v)}</option>" for k, v in pt.FIELD_TYPES.items())

    def board_select(current, blank):
        return ("<select name=board_id aria-label='Board'>" + f"<option value=''>{t.esc(blank)}</option>"
                + "".join(f"<option value='{t.esc(b['board_id'])}'{' selected' if b['board_id'] == current else ''}>"
                          f"{t.esc(b['display_name'])}</option>" for b in boards) + "</select>")

    def icon_select(current):
        return ("<select name=icon aria-label='Picture'>" + "".join(
            f"<option value={i}{' selected' if i == current else ''}>{i}</option>" for i in pt.ICONS) + "</select>")

    def tile_form(r, sub: bool):
        tid = r["tile_id"]
        return (f"<form method=post action='/admin/portal-tiles/tile/{tid}' class=row style='margin:0'>"
                f"<input type=hidden name=parent_id value='{r['parent_id'] or ''}'>"
                f"<div style='flex:0 0 auto'>{t.icon(r['icon'] or 'ticket')}</div>"
                f"<div style='flex:1 1 180px'><input name=label value='{t.esc(r['label'])}' maxlength={pt.LABEL_MAX} aria-label='Words on the tile'></div>"
                f"<div style='flex:1 1 200px'><input name=hint value='{t.esc(r['hint'] or '')}' maxlength={pt.HINT_MAX} placeholder='A line under it' aria-label='A line under it'></div>"
                f"<div style='flex:0 0 120px'>{icon_select(r['icon'])}</div>"
                f"<div style='flex:0 0 170px'>{board_select(r['board_id'], 'its parent board' if sub else 'no board')}</div>"
                f"<div style='flex:1 1 260px'><input name=pair list=pairs value='{t.esc(pt.pair_label(ctx.conn, r['catalogue_item_id']))}'"
                f" placeholder='{'its parent Item' if sub else 'Type › Subtype › Item'}' aria-label='Type, Subtype and Item'></div>"
                f"<div style='flex:0 0 70px'><input name=sort_order type=number value='{r['sort_order']}' aria-label='Order'></div>"
                "<div style='flex:0 0 auto'><button class='ghost small' type=submit>Save</button></div>"
                f"<div style='flex:0 0 auto'><button class='ghost small' type=submit name=inactive value='{0 if r['inactive'] else 1}'>"
                f"{'Restore' if r['inactive'] else 'Retire'}</button></div></form>")

    def question_rows(r):
        qs = pt.questions(ctx.conn, r["tile_id"], all_rows=True)
        rows_ = "".join(
            f"<tr{' style=opacity:.6' if x['inactive'] else ''}><td><form method=post action='/admin/portal-tiles/question/{x['question_id']}' class=row style='margin:0'>"
            f"<div><input name=label value='{t.esc(x['label'])}' maxlength=120 aria-label='Question'></div>"
            f"<div style='flex:0 0 auto'><label><input type=checkbox name=required value=1{' checked' if x['required'] else ''}> needed</label></div>"
            "<div style='flex:0 0 auto'><button class='ghost small' type=submit>Save</button></div>"
            f"<div style='flex:0 0 auto'><button class='ghost small' type=submit name=inactive value='{0 if x['inactive'] else 1}'>{'Restore' if x['inactive'] else 'Retire'}</button></div></form></td>"
            f"<td>{t.esc(pt.FIELD_TYPES[x['field_type']])}</td></tr>" for x in qs)
        add = (f"<form method=post action='/admin/portal-tiles/tile/{r['tile_id']}/question' class=row style='margin-top:6px'>"
               "<div style='flex:1 1 220px'><input name=label required maxlength=120 placeholder='What do you need? · How many? · Needed by'></div>"
               f"<div style='flex:0 0 150px'><select name=field_type aria-label='Answer'>{field_opts}</select></div>"
               "<div style='flex:0 0 auto'><label><input type=checkbox name=required value=1> needed</label></div>"
               "<div style='flex:0 0 auto'><button class='ghost small' type=submit>Ask</button></div></form>")
        return ("<div class=tablewrap style='margin-top:6px'><table class=compact><thead><tr><th>Question</th><th>Answer</th></tr></thead><tbody>"
                + (rows_ or "<tr><td colspan=2 class=muted>No question: the request form's own boxes are all it asks.</td></tr>")
                + "</tbody></table></div>" + add)

    def block(top):
        subs = [r for r in rows if r["parent_id"] == top["tile_id"]]
        sub_html = "".join(
            f"<div style='margin:10px 0 0 28px;padding-left:12px;border-left:2px solid var(--line)'{' class=muted' if s['inactive'] else ''}>"
            + tile_form(s, True) + question_rows(s) + "</div>" for s in subs)
        return (f"<div class=card{' style=opacity:.75' if top['inactive'] else ''}><h3>{t.icon(top['icon'] or 'ticket')}{t.esc(top['label'])}"
                + (" <span class=pill>retired</span>" if top["inactive"] else "")
                + (f" <span class=muted style='font-weight:400'>· {len(subs)} smaller tile(s)</span>" if subs else "") + "</h3>"
                + tile_form(top, False) + "<p class=why style='margin:6px 0 0'>Its questions"
                + (", asked for each smaller tile too" if subs else "") + ":</p>" + question_rows(top) + sub_html + "</div>")

    add = ("<div class=card><h3>" + t.icon("plus") + "Add a tile</h3>"
           "<form method=post action='/admin/portal-tiles/tile' class=row>"
           f"<div style='flex:1 1 180px'><label>Words on the tile</label><input name=label required maxlength={pt.LABEL_MAX} placeholder='Printer or scanner'></div>"
           f"<div style='flex:1 1 200px'><label>A line under it</label><input name=hint maxlength={pt.HINT_MAX} placeholder='Not printing, jammed, or not scanning'></div>"
           f"<div style='flex:0 0 120px'><label>Picture</label>{icon_select('ticket')}</div>"
           "<div style='flex:0 0 190px'><label>Inside</label><select name=parent_id><option value=''>a top tile</option>"
           + "".join(f"<option value={x['tile_id']}>{t.esc(x['label'])}</option>" for x in tops) + "</select></div>"
           f"<div style='flex:0 0 170px'><label>Board</label>{board_select(None, 'its parent board / none')}</div>"
           "<div style='flex:1 1 260px'><label>Type › Subtype › Item</label><input name=pair list=pairs placeholder='Type to find one'></div>"
           "<div style='flex:0 0 70px'><label>Order</label><input name=sort_order type=number value=100></div>"
           "<div style='flex:0 0 auto;align-self:end'><button type=submit>Add</button></div></form></div>")
    body = (banners + head + datalist + add + "".join(block(x) for x in tops)
            + ("" if tops else "<div class=card><p class=muted>No tile yet, so the portal shows the plain form. The PMC "
                                "starter set: <code>psaspine portal-tiles &lt;db&gt;</code> previews it, "
                                "<code>--apply</code> writes it.</p></div>"))
    return Response(body=t.page("Portal tiles", body, user=ctx.user, active="admin"))


def _fields(ctx, f) -> dict:
    return {"label": f.get("label", ""), "hint": f.get("hint"), "icon": f.get("icon"),
            "parent_id": f.get("parent_id") or None, "board_id": f.get("board_id") or None,
            "catalogue_item_id": _pair_id(ctx, f.get("pair", "")), "sort_order": _int(f.get("sort_order"))}


def tile_add(ctx):
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    return _try(ctx, lambda: pt.add_tile(ctx.conn, at=ctx.now, actor=ctx.user.id, **_fields(ctx, f)),
                f"Added: {' '.join(f.get('label', '').split())}")


def tile_save(ctx, tile_id):
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    inactive = None if f.get("inactive") is None else f.get("inactive") == "1"
    return _try(ctx, lambda: pt.save_tile(ctx.conn, _int(tile_id, -1), at=ctx.now, actor=ctx.user.id,
                                          inactive=inactive, **_fields(ctx, f)),
                lambda out: "Nothing changed" if out == "nothing changed" else "Saved")


def question_add(ctx, tile_id):
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    return _try(ctx, lambda: pt.add_question(ctx.conn, _int(tile_id, -1), label=f.get("label", ""),
                                             field_type=f.get("field_type", ""), required=f.get("required") == "1",
                                             at=ctx.now, actor=ctx.user.id), "Question added")


def question_save(ctx, question_id):
    common.require_sysadmin(ctx)
    f = ctx.request.form()
    inactive = None if f.get("inactive") is None else f.get("inactive") == "1"
    return _try(ctx, lambda: pt.save_question(ctx.conn, _int(question_id, -1), at=ctx.now, actor=ctx.user.id,
                                              label=f.get("label"),
                                              required=(f.get("required") == "1") if inactive is None else None,
                                              inactive=inactive),
                lambda out: "Nothing changed" if out == "nothing changed" else "Saved")
