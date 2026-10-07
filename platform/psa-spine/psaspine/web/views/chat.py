"""Chat (071): the desk's queue and conversation, and the requester's side on
the portal. Dada, 7 Oct 2026: "can we do something to connectwise chat?";
confirmed: requester <-> desk, offered on the portal at any time, patient
details flagged and warned about, never blocked.

New lines arrive by a small poll of GET .../messages.json?after=<id> every few
seconds while the chat is open, appended in place, so what someone is typing is
never lost to a reload. Sending posts the form; with script on it is posted in
the background and the line appears at once.
"""
from __future__ import annotations

import json
import urllib.parse

from ... import chat
from .. import templates as t
from . import common

POLL_MS = 3000


def _back(path: str, **q):
    from .. import redirect
    q = {k: v for k, v in q.items() if v}
    return redirect(path + ("?" + urllib.parse.urlencode(q) if q else ""))


def _wants_json(ctx) -> bool:
    return ctx.request.query.get("js") == "1"


def _json(obj, status: str = "200 OK"):
    from .. import Response
    return Response(status, json.dumps(obj), content_type="application/json; charset=utf-8",
                    headers=[("Cache-Control", "no-store")])


def _lines_json(rows) -> list:
    return [{"id": r["message_id"], "who": r["sender"], "kind": r["sender_kind"], "body": r["body"],
             "at": r["sent_at"][11:16]} for r in rows]


def _bubbles(rows, *, me_kind: str) -> str:
    out = []
    for r in rows:
        if r["sender_kind"] == chat.SYSTEM:
            out.append(f"<div class='cl sys'>{t.esc(r['body'])} · {t.esc(r['sent_at'][11:16])}</div>")
        else:
            mine = " me" if r["sender_kind"] == me_kind else ""
            out.append(f"<div class='cl {r['sender_kind'].lower()}{mine}'><div class=cb>{t.esc(r['body'])}</div>"
                       f"<div class=cm>{t.esc(r['sender'])} · {t.esc(r['sent_at'][11:16])}</div></div>")
    return "".join(out)


_SCRIPT = """<script>(function(){
var box=document.getElementById('chatlog'),form=document.getElementById('chatsend');if(!box)return;
var url=box.dataset.poll,me=box.dataset.me,last=+box.dataset.last||0,busy=false;
function esc(s){return String(s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function add(m){if(m.id<=last)return;last=m.id;var d=document.createElement('div');
 if(m.kind==='SYSTEM'){d.className='cl sys';d.innerHTML=esc(m.body)+' · '+esc(m.at)}
 else{d.className='cl '+m.kind.toLowerCase()+(m.kind===me?' me':'');d.innerHTML='<div class=cb>'+esc(m.body)+'</div><div class=cm>'+esc(m.who)+' · '+esc(m.at)+'</div>'}
 box.appendChild(d);box.scrollTop=box.scrollHeight}
function poll(){if(busy||document.hidden)return;busy=true;
 fetch(url+'?after='+last,{credentials:'same-origin'}).then(function(r){return r.ok?r.json():null}).then(function(j){busy=false;if(!j)return;
  (j.messages||[]).forEach(add);var st=document.getElementById('chatstate');if(st&&j.status_words)st.textContent=j.status_words;
  if(j.status==='CLOSED'&&form){form.querySelectorAll('textarea,button').forEach(function(x){x.disabled=true})}}).catch(function(){busy=false})}
box.scrollTop=box.scrollHeight;setInterval(poll,""" + str(POLL_MS) + """);
if(form){var ta=form.querySelector('textarea');
 ta.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();form.requestSubmit?form.requestSubmit():form.submit()}});
 form.addEventListener('submit',function(e){if(!window.fetch)return;e.preventDefault();var v=ta.value.trim();if(!v)return;
  var fd=new URLSearchParams(new FormData(form));ta.value='';
  fetch(form.action+'?js=1',{method:'POST',body:fd,credentials:'same-origin',headers:{'Content-Type':'application/x-www-form-urlencoded'}})
   .then(function(r){return r.json()}).then(function(j){if(j.error){ta.value=v;alert(j.error)}
    var w=document.getElementById('chatwarn');if(w&&j.warn){w.hidden=false}poll()}).catch(function(){ta.value=v})})}
})()</script>"""

WARN = ("Please never type a patient's name or number in a chat. The ward, the room and the machine are all we need. "
        "Your message was sent; the desk will tidy it.")


def _status_words(c) -> str:
    if c["status"] == chat.WAITING:
        return "Waiting for someone from the desk to pick it up."
    if c["status"] == chat.ACTIVE:
        return f"{c['picked_by']} is with you."
    return "This chat has ended."


# ================================================================= the desk

def _load(ctx, chat_id, *, need: str = "READ"):
    from .. import HttpError
    c = chat.get(ctx.conn, int(chat_id)) if str(chat_id).isdigit() else None
    if c is None or not common.may_access_board(ctx, c["board_id"], need=need):
        raise HttpError("404 Not Found", "No such chat.")
    common.audit_restricted_read(ctx, c["board_id"], subject_id=f"chat {c['chat_id']}")
    return c


def index(ctx):
    """The queue: chats waiting for someone, then the ones being answered, then
    the last two days' ended ones, on the boards the person is on."""
    from .. import Response
    seen = common.board_ids_for(ctx)
    if not seen:                                      # a requester: their own side of it
        return _back("/my/chat")
    rows = chat.queue(ctx.conn, seen, now=ctx.now)
    q = ctx.request.query

    def row(r):
        state = {"WAITING": t.chip("Waiting"), "ACTIVE": t.chip("With " + (r["picked_by"] or "?")),
                 "CLOSED": t.chip("Ended")}[r["status"]]
        tk = (f"<a href='/ticket/{t.esc(r['work_item_id'])}'>{t.esc(r['work_item_id'])}</a>" if r["work_item_id"] else "")
        return (f"<tr{' class=chatwait' if r['status'] == 'WAITING' else ''}><td><a href='/chat/{r['chat_id']}'>Chat {r['chat_id']}</a></td>"
                f"<td><b>{t.esc(r['subject'])}</b></td><td>{t.esc(r['requester'])}</td><td>{t.esc(r['board_name'])}</td>"
                f"<td>{state}</td><td>{t.esc(r['started_at'][:16])}</td><td class=center>{r['lines']}</td><td>{tk}</td></tr>")
    waiting = sum(1 for r in rows if r["status"] == "WAITING")
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + f"<h1>Chat</h1><p class=sub>Ward staff start a chat from the portal. Pick one up to answer it; make it a "
              f"ticket, or add it to one, when it needs work. {waiting} waiting.</p>"
            + "<div class=card id=chatqueue><div class=tablewrap><table><thead><tr><th>Chat</th><th>About</th><th>Who</th>"
              "<th>Board</th><th>State</th><th>Started</th><th>Lines</th><th>Ticket</th></tr></thead><tbody>"
            + ("".join(row(r) for r in rows) or "<tr><td colspan=8 class=muted>No chats.</td></tr>")
            + "</tbody></table></div></div>")
    return Response(body=t.page("Chat", body, user=ctx.user, active="chat", live="chats"))


def detail(ctx, chat_id):
    from .. import Response
    c = _load(ctx, chat_id)
    can = common.may_access_board(ctx, c["board_id"], need="WORK")
    rows = chat.messages(ctx.conn, c["chat_id"])
    cid = c["chat_id"]
    q = ctx.request.query
    acts = ""
    if can and c["status"] != chat.CLOSED:
        if c["status"] == chat.WAITING or (c["picked_by"] or "").lower() != ctx.user.id.lower():
            acts += (f"<form method=post action='/chat/{cid}/pick' class=inline><button type=submit>"
                     + t.icon("check") + (" Pick it up" if c["status"] == chat.WAITING else " Take it over") + "</button></form> ")
        acts += (f"<form method=post action='/chat/{cid}/end' class=inline onsubmit=\"return confirm('End this chat?')\">"
                 "<button class=ghost type=submit>End the chat</button></form>")
    ticket_card = ""
    if c["work_item_id"]:
        ticket_card = (f"<div class=card><h3>{t.icon('ticket')}Ticket</h3><p><a href='/ticket/{t.esc(c['work_item_id'])}'>"
                       f"{t.esc(c['work_item_id'])}</a> carries this chat.</p></div>")
    elif can:
        ticket_card = (f"<div class=card id=chatticket><h3>{t.icon('ticket')}Make it a ticket</h3>"
                       f"<form method=post action='/chat/{cid}/ticket' class=stack style='max-width:none'>"
                       f"<label>Summary <input name=summary maxlength=200 value='{t.esc(c['subject'])}'></label>"
                       "<p class=why style='margin:0'>On this chat's board, for its requester, the chat as its description, "
                       "yours to work. The chat stays open.</p><div><button type=submit>Make a ticket</button></div></form>"
                       f"<h4 style='margin-top:14px'>Or add it to a ticket</h4><form method=post action='/chat/{cid}/attach' class=row>"
                       f"<div>{t.ticket_pick('work_item_id', 'Search a ticket, or type its number', required=True)}</div>"
                       "<div style='flex:0 0 auto'><button class=ghost type=submit>Add to the ticket</button></div></form></div>")
    send = ""
    if can and c["status"] != chat.CLOSED:
        send = (f"<form id=chatsend method=post action='/chat/{cid}/send' class=chatsend>"
                "<textarea name=body rows=2 required maxlength=2000 placeholder='Type a reply. Enter sends; Shift+Enter is a new line.'></textarea>"
                "<button type=submit>" + t.icon("arrow") + " Send</button></form>")
    last = rows[-1]["message_id"] if rows else 0
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + "<a class=backbtn href='/chat'>" + t.icon("left") + "<span class=lbl>Back to Chat</span></a>"
            f"<div class=hdr><div class=grow><h1>Chat {cid} · {t.esc(c['subject'])}</h1>"
            f"<p class=sub>{t.esc(c['requester'])} · {t.esc(c['board_name'])} · started {t.esc(c['started_at'][:16])} · "
            f"<span id=chatstate>{t.esc(_status_words(c))}</span></p></div><div>{acts}</div></div>"
            "<div class=grid2 style='grid-template-columns:minmax(0,2fr) minmax(0,1fr)'>"
            f"<div class=card><div id=chatlog class=chatlog data-poll='/chat/{cid}/messages.json' data-me='STAFF' data-last='{last}'>"
            + _bubbles(rows, me_kind=chat.STAFF) + "</div>" + send + "</div><div>" + ticket_card + "</div></div>" + _SCRIPT)
    return Response(body=t.page(f"Chat {cid}", body, user=ctx.user, active="chat"))


def messages_json(ctx, chat_id):
    c = _load(ctx, chat_id)
    after = ctx.request.query.get("after", "0")
    rows = chat.messages(ctx.conn, c["chat_id"], after=int(after) if after.isdigit() else 0)
    return _json({"status": c["status"], "status_words": _status_words(c), "messages": _lines_json(rows)})


def _act(ctx, chat_id, fn, ok):
    c = _load(ctx, chat_id, need="WORK")
    try:
        r = fn(c)
        ctx.conn.commit()
    except chat.Refused as exc:
        ctx.conn.rollback()
        return _back(f"/chat/{c['chat_id']}", err=str(exc))
    return ok(c, r)


def send(ctx, chat_id):
    body = ctx.request.form().get("body", "")
    if _wants_json(ctx):
        c = _load(ctx, chat_id, need="WORK")
        try:
            mid, _ = chat.say(ctx.conn, c["chat_id"], sender=ctx.user.id, kind=chat.STAFF, body=body, at=ctx.now)
            ctx.conn.commit()
        except chat.Refused as exc:
            ctx.conn.rollback()
            return _json({"error": str(exc)})
        return _json({"id": mid})
    return _act(ctx, chat_id, lambda c: chat.say(ctx.conn, c["chat_id"], sender=ctx.user.id, kind=chat.STAFF,
                                                 body=body, at=ctx.now), lambda c, r: _back(f"/chat/{c['chat_id']}"))


def pick(ctx, chat_id):
    return _act(ctx, chat_id, lambda c: chat.pick_up(ctx.conn, c["chat_id"], member=ctx.user.id, at=ctx.now),
                lambda c, r: _back(f"/chat/{c['chat_id']}", msg="You have the chat."))


def end(ctx, chat_id):
    return _act(ctx, chat_id, lambda c: chat.close(ctx.conn, c["chat_id"], by=ctx.user.id, at=ctx.now),
                lambda c, r: _back(f"/chat/{c['chat_id']}", msg="Chat ended."))


def make_ticket(ctx, chat_id):
    f = ctx.request.form()
    return _act(ctx, chat_id, lambda c: chat.to_ticket(ctx.conn, c["chat_id"], member=ctx.user.id,
                                                       summary=f.get("summary") or None, at=ctx.now),
                lambda c, wid: _back(f"/chat/{c['chat_id']}", msg=f"Ticket {wid} raised from the chat."))


def attach(ctx, chat_id):
    wid = (ctx.request.form().get("work_item_id", "") or "").strip().upper()

    def go(c):
        tk = ctx.conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?", (wid,)).fetchone()
        if tk is None or not common.may_access_board(ctx, tk["board_id"], need="WORK") \
                or not common.project_ticket_ok(ctx, wid):
            raise chat.Refused(f"No ticket {wid} that you work.")
        return chat.attach(ctx.conn, c["chat_id"], wid, member=ctx.user.id, at=ctx.now)
    return _act(ctx, chat_id, go, lambda c, r: _back(f"/chat/{c['chat_id']}", msg=f"Chat added to {r}."))


# ================================================================ the portal

def _mine(ctx, chat_id):
    from .. import HttpError
    from .portal import _identities
    c = chat.get(ctx.conn, int(chat_id)) if str(chat_id).isdigit() else None
    if c is None or c["requester"].lower() not in _identities(ctx):
        raise HttpError("404 Not Found", "No such chat.")
    return c


def my_index(ctx, *, error: str = ""):
    """The requester's chats and a box to start one. Offered at any time; a chat
    started out of hours waits until someone from the desk is in."""
    from .. import Response
    from .portal import _identities, _my_boards
    rows = chat.of_requester(ctx.conn, _identities(ctx))
    boards = list(_my_boards(ctx))
    if len(boards) > 1:
        who = ("<label>Who is this for? <select name=board_id required>"
               + "".join(f"<option value='{t.esc(b['board_id'])}'>{t.esc(b['display_name'])}</option>" for b in boards)
               + "</select></label>")
    elif boards:
        who = f"<input type=hidden name=board_id value='{t.esc(boards[0]['board_id'])}'>"
    else:
        who = ""
    lis = "".join(
        f"<tr><td><a href='/my/chat/{r['chat_id']}'>{t.esc(r['subject'])}</a></td><td>{t.esc(r['board_name'])}</td>"
        f"<td>{t.chip({'WAITING': 'Waiting', 'ACTIVE': 'Open', 'CLOSED': 'Ended'}[r['status']])}</td>"
        f"<td class=muted>{t.esc(r['started_at'][:16])}</td></tr>" for r in rows)
    body = ((f"<div class='banner err'>{t.esc(error)}</div>" if error else "")
            + "<h1>Chat with the helpdesk</h1><p class='sub'>Type what is wrong and someone from the desk will answer "
              "here. If it needs work, they will raise a request for you.</p>"
            + "<div class=card id=chatstart><h3>" + t.icon("note") + "Start a chat</h3>"
              "<form method=post action='/my/chat/new' class=stack style='max-width:none'>"
              "<label>What is it about? <input name=subject maxlength=200 placeholder='Printer on ward 3'></label>" + who
            + "<label>Your message <textarea name=body required maxlength=2000 placeholder='The ward or office, the room, "
              "the machine, and since when. Never a patient&#39;s details.'></textarea></label>"
              "<div><button type=submit>Start the chat</button></div></form></div>"
            + ("<div class=card><h3>Your chats</h3><div class=tablewrap><table><thead><tr><th>About</th><th>With</th>"
               f"<th>State</th><th>Started</th></tr></thead><tbody>{lis}</tbody></table></div></div>" if rows else ""))
    return Response("400 Bad Request" if error else "200 OK", t.page("Chat", body, user=ctx.user, active="chat"))


def my_start(ctx):
    from .portal import _my_boards
    f = ctx.request.form()
    boards = {b["board_id"] for b in _my_boards(ctx)}
    chosen = f.get("board_id", "")
    if chosen and chosen not in boards:
        return my_index(ctx, error="That is not one of the places your department can chat with.")
    if not chosen:
        if len(boards) == 1:
            chosen = next(iter(boards))
        elif boards:
            return my_index(ctx, error="Tell us who this is for.")
        else:
            row = ctx.conn.execute("SELECT board_id FROM board WHERE is_unrouted = 1").fetchone()
            if row is None:
                return my_index(ctx, error="Chat is not available right now. Please ring the desk.")
            chosen = row["board_id"]
    requester = (getattr(ctx.user, "email", None) or ctx.user.id or "").lower()
    try:
        cid, findings = chat.start(ctx.conn, requester=requester, board_id=chosen, subject=f.get("subject", ""),
                                   first=f.get("body", ""), at=ctx.now)
        ctx.conn.commit()
    except chat.Refused as exc:
        ctx.conn.rollback()
        return my_index(ctx, error=str(exc))
    return _back(f"/my/chat/{cid}", warn="1" if findings else "")


def my_detail(ctx, chat_id):
    from .. import Response
    c = _mine(ctx, chat_id)
    rows = chat.messages(ctx.conn, c["chat_id"])
    cid = c["chat_id"]
    warn = ctx.request.query.get("warn") == "1"
    send = ""
    if c["status"] != chat.CLOSED:
        send = (f"<form id=chatsend method=post action='/my/chat/{cid}/send' class=chatsend>"
                "<textarea name=body rows=2 required maxlength=2000 placeholder='Type a message. Enter sends.'></textarea>"
                "<button type=submit>Send</button></form>"
                f"<form method=post action='/my/chat/{cid}/end' style='margin-top:8px'>"
                "<button class=ghost type=submit>End the chat</button></form>")
    tk = (f"<p class=why>The desk raised request <a href='/my/{t.esc(c['work_item_id'])}'>{t.esc(c['work_item_id'])}</a> "
          "from this chat.</p>" if c["work_item_id"] else "")
    last = rows[-1]["message_id"] if rows else 0
    body = ("<a class=backbtn href='/my/chat'>" + t.icon("left") + "<span class=lbl>Your chats</span></a>"
            f"<h1>{t.esc(c['subject'])}</h1><p class='sub'>{t.esc(c['board_name'])} · "
            f"<span id=chatstate>{t.esc(_status_words(c))}</span></p>"
            f"<div id=chatwarn class='banner err'{'' if warn else ' hidden'}>{t.esc(WARN)}</div>" + tk
            + f"<div class=card><div id=chatlog class=chatlog data-poll='/my/chat/{cid}/messages.json' data-me='REQUESTER'"
              f" data-last='{last}'>" + _bubbles(rows, me_kind=chat.REQUESTER) + "</div>" + send + "</div>" + _SCRIPT)
    return Response(body=t.page("Chat", body, user=ctx.user, active="chat"))


def my_messages_json(ctx, chat_id):
    c = _mine(ctx, chat_id)
    after = ctx.request.query.get("after", "0")
    rows = chat.messages(ctx.conn, c["chat_id"], after=int(after) if after.isdigit() else 0)
    return _json({"status": c["status"], "status_words": _status_words(c), "messages": _lines_json(rows)})


def my_send(ctx, chat_id):
    c = _mine(ctx, chat_id)
    body = ctx.request.form().get("body", "")
    try:
        mid, findings = chat.say(ctx.conn, c["chat_id"], sender=c["requester"], kind=chat.REQUESTER, body=body, at=ctx.now)
        ctx.conn.commit()
    except chat.Refused as exc:
        ctx.conn.rollback()
        if _wants_json(ctx):
            return _json({"error": str(exc)})
        return _back(f"/my/chat/{c['chat_id']}")
    if _wants_json(ctx):
        return _json({"id": mid, "warn": bool(findings)})
    return _back(f"/my/chat/{c['chat_id']}", warn="1" if findings else "")


def my_end(ctx, chat_id):
    c = _mine(ctx, chat_id)
    chat.close(ctx.conn, c["chat_id"], by=c["requester"], at=ctx.now)
    ctx.conn.commit()
    return _back(f"/my/chat/{c['chat_id']}")
