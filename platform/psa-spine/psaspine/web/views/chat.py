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

from ... import chat, live
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


# A small set of emoji for typing, picked to be read the same on every ward PC.
EMOJIS = ("😀", "😄", "😊", "🙂", "😉", "😅", "😂", "🙏", "👍", "👎", "👌", "👏", "🙌", "💪", "🤝", "👋",
          "❤️", "💙", "✅", "❌", "⚠️", "❓", "❗", "⏳", "🔧", "🖨️", "💻", "🖥️", "📞", "📧", "🔌", "📶",
          "🔒", "🔑", "📎", "📷", "🎉", "☕", "😮", "😕")


def _line_dicts(ctx, c, rows, *, viewer: str, desk: bool, base: str) -> list:
    """Each line as the page draws it, the same for the first draw and the poll:
    its words, its file (as this viewer may see it) and its reactions."""
    files = chat.files(ctx.conn, c["chat_id"])
    out = []
    for r in rows:
        d = {"id": r["message_id"], "who": r["sender"], "kind": r["sender_kind"], "body": r["body"],
             "at": r["sent_at"][11:16]}
        f = files.get(r["message_id"])
        if f is not None:
            if f["review_status"] == "WITHHELD" and not desk:
                d["file"] = {"withheld": True}
            else:
                d["file"] = {"id": f["file_id"], "name": f["filename"], "url": f"{base}/file/{f['file_id']}",
                             "image": f["media_type"].startswith("image/") and f["media_type"] != "image/svg+xml",
                             "status": f["review_status"]}
        out.append(d)
    return out


def _rx(ctx, c, viewer: str) -> dict:
    """{message_id: [{e, n, mine, who}]} in the fixed order of the set."""
    me = viewer.lower()
    out = {}
    for mid, by in chat.reactions(ctx.conn, c["chat_id"]).items():
        out[str(mid)] = [{"e": e, "n": len(by[e]), "mine": me in {w.lower() for w in by[e]}, "who": ", ".join(by[e])}
                         for e in chat.REACTIONS if e in by]
    return out


def _bubble(d, *, me_kind: str, rx: list, desk: bool, base: str) -> str:
    """One line, drawn on the server exactly as the page's script draws it."""
    if d["kind"] == chat.SYSTEM:
        return f"<div class='cl sys' data-mid='{d['id']}'>{t.esc(d['body'])} · {t.esc(d['at'])}</div>"
    mine = " me" if d["kind"] == me_kind else ""
    f = d.get("file")
    fhtml = ""
    if f and f.get("withheld"):
        fhtml = "<div class=cfile><i>A file the desk has held back.</i></div>"
    elif f:
        pend = (" <span class=chip>being checked</span>" if f["status"] == "PENDING" else
                " <span class='chip sla-warn'>withheld</span>" if f["status"] == "WITHHELD" else "")
        review = ""
        if desk and f["status"] == "PENDING":
            review = (f" <form method=post action='{base}/file/{f['id']}/review' class=inline>"
                      "<button class='ghost small' name=decision value=CLEARED type=submit>Clear</button>"
                      "<button class='ghost small danger' name=decision value=WITHHELD type=submit>Withhold</button></form>")
        pic = (f"<a href='{t.esc(f['url'])}' target=_blank rel=noopener><img class=cimg src='{t.esc(f['url'])}' "
               f"alt='{t.esc(f['name'])}' loading=lazy></a>" if f["image"] else "")
        fhtml = (f"<div class=cfile>{pic}<a href='{t.esc(f['url'])}?dl=1'>📎 {t.esc(f['name'])}</a>{pend}{review}</div>")
    body = "" if (f and d["body"].startswith("sent ")) else f"<div class=ctext>{t.esc(d['body'])}</div>"
    bar = "".join(f"<button type=button class='rx{' on' if x['mine'] else ''}' data-e='{x['e']}' title='{t.esc(x['who'])}'>"
                  f"{x['e']} {x['n']}</button>" for x in rx)
    return (f"<div class='cl {d['kind'].lower()}{mine}' data-mid='{d['id']}'><div class=cb>{body}{fhtml}</div>"
            f"<div class=cm>{t.esc(d['who'])} · {t.esc(d['at'])}</div>"
            f"<div class=cr>{bar}<button type=button class='rx add' title='React' aria-label='React'>☺+</button></div></div>")


def _conversation(ctx, c, rows, *, me_kind: str, viewer: str, desk: bool, base: str, can_send: bool) -> str:
    """The log, the reaction set, the send box (words, emoji, a file) and the script."""
    lines = _line_dicts(ctx, c, rows, viewer=viewer, desk=desk, base=base)
    rx = _rx(ctx, c, viewer)
    last = rows[-1]["message_id"] if rows else 0
    log = (f"<div id=chatlog class=chatlog data-poll='{base}/messages.json' data-base='{base}' data-me='{me_kind}'"
           f" data-desk='{1 if desk else 0}' data-last='{last}'>"
           + "".join(_bubble(d, me_kind=me_kind, rx=rx.get(str(d["id"]), []), desk=desk, base=base) for d in lines)
           + "</div>")
    # chat round six: "... is typing", filled by the poll, said aloud to a screen reader
    typing = f"<div id=chattyping class=chattyping aria-live=polite>{t.esc(_typing_words(c, desk))}</div>"
    picker = ("<div id=rxpick class=rxpick hidden>" + "".join(
        f"<button type=button data-e='{e}'>{e}</button>" for e in chat.REACTIONS) + "</div>")
    send = ""
    if can_send:
        send = (f"<form id=chatsend method=post action='{base}/send' class=chatsend enctype='multipart/form-data'>"
                "<div class=chattools><button type=button class='iconbtn emo' title='Emoji' aria-label='Emoji'>😊</button>"
                "<label class='iconbtn clip' title='Attach a picture or file' aria-label='Attach a picture or file'>"
                + t.icon("paperclip") + "<input type=file name=file hidden></label></div>"
                "<textarea name=body rows=2 maxlength=2000 placeholder='Type a message. Enter sends; Shift+Enter is a "
                "new line. Paste or drop a screenshot to send it.'></textarea>"
                "<button type=submit>" + t.icon("arrow") + " Send</button>"
                "<div id=emopick class=emopick hidden>" + "".join(
                    f"<button type=button>{e}</button>" for e in EMOJIS) + "</div></form>")
    return log + typing + picker + send + _SCRIPT


_SCRIPT = """<script>(function(){
var box=document.getElementById('chatlog'),form=document.getElementById('chatsend');if(!box)return;
var url=box.dataset.poll,base=box.dataset.base,me=box.dataset.me,desk=box.dataset.desk==='1',last=+box.dataset.last||0,busy=false;
function esc(s){return String(s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function bar(list){return (list||[]).map(function(x){return '<button type=button class="rx'+(x.mine?' on':'')+'" data-e="'+esc(x.e)+'" title="'+esc(x.who)+'">'+esc(x.e)+' '+x.n+'</button>'}).join('')+'<button type=button class="rx add" title="React" aria-label="React">\\u263a+</button>'}
function render(m,rx){var d=document.createElement('div');d.dataset.mid=m.id;
 if(m.kind==='SYSTEM'){d.className='cl sys';d.innerHTML=esc(m.body)+' \\u00b7 '+esc(m.at);return d}
 d.className='cl '+m.kind.toLowerCase()+(m.kind===me?' me':'');var f=m.file,fh='';
 if(f&&f.withheld){fh='<div class=cfile><i>A file the desk has held back.</i></div>'}
 else if(f){fh='<div class=cfile>'+(f.image?'<a href="'+esc(f.url)+'" target=_blank rel=noopener><img class=cimg src="'+esc(f.url)+'" alt="'+esc(f.name)+'"></a>':'')
  +'<a href="'+esc(f.url)+'?dl=1">\\ud83d\\udcce '+esc(f.name)+'</a>'+(f.status==='PENDING'?' <span class=chip>being checked</span>':'')
  +(desk&&f.status==='PENDING'?' <form method=post action="'+esc(base)+'/file/'+f.id+'/review" class=inline><button class="ghost small" name=decision value=CLEARED type=submit>Clear</button><button class="ghost small danger" name=decision value=WITHHELD type=submit>Withhold</button></form>':'')+'</div>'}
 var words=(f&&m.body.indexOf('sent ')===0)?'':'<div class=ctext>'+esc(m.body)+'</div>';
 d.innerHTML='<div class=cb>'+words+fh+'</div><div class=cm>'+esc(m.who)+' \\u00b7 '+esc(m.at)+'</div><div class=cr>'+bar(rx)+'</div>';return d}
function add(m,rx){if(m.id<=last)return;last=m.id;box.appendChild(render(m,rx));box.scrollTop=box.scrollHeight}
function poll(){if(busy||document.hidden)return;busy=true;
 fetch(url+'?after='+last,{credentials:'same-origin'}).then(function(r){return r.ok?r.json():null}).then(function(j){busy=false;if(!j)return;
  var rx=j.reactions||{};(j.messages||[]).forEach(function(m){add(m,rx[m.id])});
  box.querySelectorAll('.cl[data-mid]:not(.sys)').forEach(function(el){var b=el.querySelector('.cr');if(b)b.innerHTML=bar(rx[el.dataset.mid])});
  var st=document.getElementById('chatstate');if(st&&j.status_words)st.textContent=j.status_words;
  var ty=document.getElementById('chattyping');if(ty)ty.textContent=j.typing||'';
  var dk=document.getElementById('deskon');if(dk&&j.desk){dk.querySelector('.dtxt').textContent=j.desk.words;
   dk.querySelector('.pdot').className='pdot '+(j.desk.n?'p-online':'p-offline')}
  if(j.status==='CLOSED'){if(form){form.querySelectorAll('textarea,button,input').forEach(function(x){x.disabled=true})}
   var sv=document.getElementById('chatsurvey');if(sv&&!j.rated&&j.ask!==false){sv.hidden=false;
    var rt=sv.querySelector('.rwho');if(rt&&j.rate_title)rt.textContent=j.rate_title}}}).catch(function(){busy=false})}
/* 074: the quick view's End opens the chat with its end window up */
(function(){function up(){var ce=document.getElementById('chatend');if(ce&&ce.hasAttribute('data-autoopen')&&ce.showModal&&!ce.open)ce.showModal()}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',up);else up()})();
var pick=document.getElementById('rxpick'),target=null;
box.addEventListener('click',function(e){var b=e.target.closest('.rx');if(!b)return;var el=b.closest('.cl');if(!el)return;
 if(b.classList.contains('add')){target=el.dataset.mid;var r=b.getBoundingClientRect();pick.hidden=false;
  pick.style.left=(r.left+window.scrollX)+'px';pick.style.top=(r.bottom+window.scrollY+4)+'px';return}
 react(el.dataset.mid,b.dataset.e)});
if(pick)pick.addEventListener('click',function(e){var b=e.target.closest('button');if(!b||!target)return;pick.hidden=true;react(target,b.dataset.e)});
document.addEventListener('click',function(e){if(pick&&!pick.hidden&&!e.target.closest('#rxpick,.rx.add'))pick.hidden=true});
function react(mid,emo){var fd=new URLSearchParams();fd.set('message_id',mid);fd.set('emoji',emo);
 fetch(base+'/react?js=1',{method:'POST',body:fd,credentials:'same-origin',headers:{'Content-Type':'application/x-www-form-urlencoded'}}).then(function(){poll()})}
box.scrollTop=box.scrollHeight;setInterval(poll,""" + str(POLL_MS) + """);
if(form){var ta=form.querySelector('textarea'),fi=form.querySelector('input[type=file]'),emo=document.getElementById('emopick'),pinged=0;
 /* chat round six: while words go in, the other side reads "... is typing" (one small ping every few seconds) */
 ta.addEventListener('input',function(){var n=Date.now();if(!ta.value.trim()||n-pinged<2500)return;pinged=n;
  fetch(base+'/typing',{method:'POST',credentials:'same-origin'}).catch(function(){})});
 function sendFile(file){var fd=new FormData();fd.append('file',file,file.name||'screenshot.png');fd.append('body',ta.value.trim());ta.value='';
  fetch(form.action+'?js=1',{method:'POST',body:fd,credentials:'same-origin'}).then(function(r){return r.json()}).then(function(j){
   if(j.error)alert(j.error);var w=document.getElementById('chatwarn');if(w&&j.warn)w.hidden=false;poll()})}
 if(fi)fi.addEventListener('change',function(){if(fi.files&&fi.files[0])sendFile(fi.files[0]);fi.value=''});
 ta.addEventListener('paste',function(e){var it=(e.clipboardData||{}).items||[];for(var i=0;i<it.length;i++){if(it[i].kind==='file'){var f=it[i].getAsFile();if(f){e.preventDefault();sendFile(f);return}}}});
 box.addEventListener('dragover',function(e){e.preventDefault()});
 box.addEventListener('drop',function(e){e.preventDefault();var f=e.dataTransfer&&e.dataTransfer.files&&e.dataTransfer.files[0];if(f)sendFile(f)});
 form.querySelector('.emo').addEventListener('click',function(){emo.hidden=!emo.hidden});
 emo.addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;var s=ta.selectionStart||ta.value.length;
  ta.value=ta.value.slice(0,s)+b.textContent+ta.value.slice(ta.selectionEnd||s);ta.focus();ta.selectionStart=ta.selectionEnd=s+b.textContent.length});
 ta.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();form.requestSubmit?form.requestSubmit():form.submit()}});
 form.addEventListener('submit',function(e){if(!window.fetch)return;e.preventDefault();var v=ta.value.trim();if(!v)return;emo.hidden=true;
  var fd=new URLSearchParams();fd.set('body',v);ta.value='';pinged=0;
  fetch(form.action+'?js=1',{method:'POST',body:fd,credentials:'same-origin',headers:{'Content-Type':'application/x-www-form-urlencoded'}})
   .then(function(r){return r.json()}).then(function(j){if(j.error){ta.value=v;alert(j.error)}
    var w=document.getElementById('chatwarn');if(w&&j.warn){w.hidden=false}poll()}).catch(function(){ta.value=v})})}
})()</script>"""

WARN = ("Please never type a patient's name or number in a chat. The ward, the room and the machine are all we need. "
        "Your message was sent; the desk will tidy it.")


def _status_words(c, conn=None, *, desk: bool = False) -> str:
    """What the chat's state line says. Waiting, it gives the place in the queue,
    and the poll keeps it current (072, "please wait ... similar to support chats")."""
    if c["status"] == chat.WAITING:
        n = chat.position(conn, c["chat_id"]) if conn is not None else None
        if desk:
            return "Waiting to be picked up" + (f" · number {n} in the queue" if n else "") + "."
        return ("Please wait, someone will be with you shortly"
                + (f": you are number {n} in the queue" if n else "") + ".")
    if c["status"] == chat.ACTIVE:
        name = chat._name(conn, c["picked_by"]) if conn is not None else c["picked_by"]
        return f"{name} is with you." if not desk else f"With {name}."
    return "This chat has ended."


# ================================================================= the desk

def _desk_boards(ctx) -> set:
    """The boards whose chats this person answers (073): a chat operator's
    boards that take chats; nothing for anyone else."""
    return chat.operator_boards(ctx.conn, ctx.user.id, common.board_ids_for(ctx))


def _load(ctx, chat_id, *, need: str = "READ"):
    from .. import HttpError
    c = chat.get(ctx.conn, int(chat_id)) if str(chat_id).isdigit() else None
    if c is None or c["board_id"] not in _desk_boards(ctx) \
            or not common.may_access_board(ctx, c["board_id"], need=need):
        raise HttpError("404 Not Found", "No such chat.")
    common.audit_restricted_read(ctx, c["board_id"], subject_id=f"chat {c['chat_id']}")
    return c


def index(ctx):
    """The queue: chats waiting for someone, then the ones being answered, then
    the last two days' ended ones, on the boards the person is on."""
    from .. import Response
    if not common.board_ids_for(ctx):                 # a requester: their own side of it
        return _back("/my/chat")
    seen = _desk_boards(ctx)
    if not seen:
        names = ", ".join(r["display_name"] for r in chat.chat_boards(ctx.conn)) or "no board yet"
        body = ("<h1>Chat</h1><div class='banner err'>Chat is answered by chat operators on the boards that take chats "
                f"({t.esc(names)}). Ask a sysadmin to tick <b>Chat operator</b> on your member record in Setup › Members.</div>")
        return Response("403 Forbidden", t.page("Chat", body, user=ctx.user, active="chat"))
    rows = chat.queue(ctx.conn, seen, now=ctx.now)
    q = ctx.request.query

    def row(r):
        state = {"WAITING": t.chip("Waiting"), "ACTIVE": t.chip("With " + (r["picked_by"] or "?")),
                 "CLOSED": t.chip("Ended")}[r["status"]]
        tk = (f"<a href='/ticket/{t.esc(r['work_item_id'])}'>{t.esc(r['work_item_id'])}</a>" if r["work_item_id"] else "")
        sv = chat.survey_of(ctx.conn, r["chat_id"])
        tk += (f" <span title='{t.esc(sv['comment'] or '')}'>{'★' * sv['score']}</span>" if sv else "")
        name = chat.label(ctx.conn, r["requester"], r["nth"])
        return (f"<tr{' class=chatwait' if r['status'] == 'WAITING' else ''}><td><a href='/chat/{r['chat_id']}' "
                f"title='{r['total']} chat{'s' if r['total'] != 1 else ''} from {t.esc(r['requester'])} so far'><b>{t.esc(name)}</b></a>"
                f"<div class=muted>{t.esc(r['requester'])}</div></td>"
                f"<td>{t.esc(r['subject'])}</td><td>{t.esc(r['board_name'])}</td>"
                f"<td>{state}</td><td>{t.esc(r['started_at'][:16])}</td><td class=center>{r['lines']}</td><td>{tk}</td></tr>")
    waiting = sum(1 for r in rows if r["status"] == "WAITING")
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + f"<h1>Chat</h1><p class=sub>Ward staff start a chat from the portal. Pick one up to answer it; make it a "
              f"ticket, or add it to one, when it needs work. {waiting} waiting.</p>"
            + _presence_card(ctx)
            + "<div class=card id=chatqueue><div class=tablewrap><table><thead><tr><th>Who · their chat</th><th>About</th>"
              "<th>Board</th><th>State</th><th>Started</th><th>Lines</th><th>Ticket · rating</th></tr></thead><tbody>"
            + ("".join(row(r) for r in rows) or "<tr><td colspan=7 class=muted>No chats.</td></tr>")
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
        acts += "<button type=button class=ghost data-open=chatend>End the chat</button>"
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
    nth, total = chat.counts(ctx.conn, cid)
    name = chat.label(ctx.conn, c["requester"], nth)
    end_dlg = _end_dialog(ctx, c) if can and c["status"] != chat.CLOSED else ""
    rated = chat.survey_of(ctx.conn, cid)
    rating = (f" · rated {'★' * rated['score']}{'☆' * (5 - rated['score'])}"
              + (f" “{t.esc(rated['comment'])}”" if rated["comment"] else "") if rated
              else " · ended without a rating" if c["status"] == chat.CLOSED and not chat.asked(c) else "")
    body = ((f"<div class='banner ok'>{t.esc(q.get('msg', ''))}</div>" if q.get("msg") else "")
            + (f"<div class='banner err'>{t.esc(q.get('err', ''))}</div>" if q.get("err") else "")
            + "<a class=backbtn href='/chat'>" + t.icon("left") + "<span class=lbl>Back to Chat</span></a>"
            f"<div class=hdr><div class=grow><h1>{t.esc(name)} · {t.esc(c['subject'])}</h1>"
            f"<p class=sub>{t.esc(c['requester'])} · their chat {nth} of {total} · {t.esc(c['board_name'])}"
            f" · started {t.esc(c['started_at'][:16])} · "
            f"<span id=chatstate>{t.esc(_status_words(c, ctx.conn, desk=True))}</span>{rating}</p></div><div>{acts}</div></div>"
            "<div class=grid2 style='grid-template-columns:minmax(0,2fr) minmax(0,1fr)'>"
            "<div class=card>" + _conversation(ctx, c, rows, me_kind=chat.STAFF, viewer=ctx.user.id, desk=True,
                                                base=f"/chat/{cid}", can_send=can and c["status"] != chat.CLOSED)
            + "</div><div>" + ticket_card + "</div></div>" + end_dlg)
    return Response(body=t.page(name, body, user=ctx.user, active="chat"))


def _first(conn, who: str) -> str:
    n = chat._name(conn, who)
    return n.split(" ")[0] if " " in n else n


def _end_dialog(ctx, c) -> str:
    """Ending a chat from the desk (Dada, 7 Oct 2026: "option to close or end the
    chat and survey or how i did at the end"; confirmed: a small window, a
    closing message if wanted, and "Ask <name> how I did" ticked by default).
    Opened by End the chat, and by the quick view's End (…?end=1)."""
    cid = c["chat_id"]
    who = t.esc(_first(ctx.conn, c["requester"]))
    nth, _ = chat.counts(ctx.conn, cid)
    return (f"<dialog id=chatend class='card tedlg'{' data-autoopen' if ctx.request.query.get('end') == '1' else ''}>"
            f"<form method=post action='/chat/{cid}/end' class=stack style='max-width:none'>"
            f"<h3 style='margin:0'>{t.icon('note')} End the chat — {t.esc(chat.label(ctx.conn, c['requester'], nth))}</h3>"
            "<label>Closing message (optional) <textarea name=closing rows=2 maxlength=2000"
            " placeholder='Salamat po! Message us anytime.'></textarea></label>"
            f"<label class=tick><input type=checkbox name=ask value=1 checked> Ask {who} how I did (a rating at the end)</label>"
            "<input type=hidden name=asked value=1>"
            "<div class=tefoot><span class=grow></span><button type=button class=ghost data-close=chatend>Cancel</button>"
            "<button type=submit>End the chat</button></div></form></dialog>")


def _rate_title(conn, c) -> str:
    """The ward's rating card asks about the operator by name (074)."""
    op = chat.operator_of(c)
    return f"How did {chat._name(conn, op)} do?" if op else "How did we do?"


RATE_LEAD = "Paki-rate po ang tulong na natanggap ninyo."


def _poll(ctx, c, *, viewer: str, desk: bool, base: str):
    after = ctx.request.query.get("after", "0")
    rows = chat.messages(ctx.conn, c["chat_id"], after=int(after) if after.isdigit() else 0)
    out = {"status": c["status"], "status_words": _status_words(c, ctx.conn, desk=desk),
           "messages": _line_dicts(ctx, c, rows, viewer=viewer, desk=desk, base=base),
           "reactions": _rx(ctx, c, viewer), "rated": chat.survey_of(ctx.conn, c["chat_id"]) is not None,
           "ask": chat.asked(c), "rate_title": _rate_title(ctx.conn, c), "typing": _typing_words(c, desk)}
    if not desk:
        out["desk"] = desk_on(ctx.conn, c["board_id"])
    return _json(out)


def _typing_words(c, desk: bool) -> str:
    """Chat round six: what the other side is doing, in words; nothing once ended."""
    if c["status"] == chat.CLOSED:
        return ""
    who = live.who_is_typing(c["chat_id"], chat.REQUESTER if desk else chat.STAFF)
    return f"{who} is typing\u2026" if who else ""


def desk_on(conn, board_id: str | None = None) -> dict:
    """Chat round six, for the portal: how many of the desk's chat operators are
    on, and their first names (a busy one says so)."""
    on = [o for o in live.operators(conn, board_id) if o["on"]]
    names = [o["first"] + (" (busy)" if o["state"] == "BUSY" else "") for o in on]
    if not on:
        words = "Nobody from the helpdesk is online right now. Your chat waits until someone is in."
    else:
        words = f"{len(on)} helpdesk staff online now: " + ", ".join(names)
    return {"n": len(on), "names": names, "words": words}


def _desk_on_line(conn, board_id: str | None = None) -> str:
    d = desk_on(conn, board_id)
    return (f"<p id=deskon class=deskon><span class='pdot {'p-online' if d['n'] else 'p-offline'}' aria-hidden=true></span>"
            f" <span class=dtxt>{t.esc(d['words'])}</span></p>")


def typing(ctx, chat_id):
    """POST /chat/<id>/typing: the operator is typing in it."""
    c = _load(ctx, chat_id, need="WORK")
    if c["status"] != chat.CLOSED:
        live.typing(c["chat_id"], chat.STAFF, chat._name(ctx.conn, ctx.user.id))
    return _json({"ok": True})


def presence_set(ctx):
    """POST /chat/presence: an operator sets Busy or Away by hand, or back to
    automatic. Kept while the desk runs (live.py)."""
    from .. import HttpError
    if not chat.is_operator(ctx.conn, ctx.user.id):
        raise HttpError("403 Forbidden", "Presence is for chat operators.")
    f = ctx.request.form()
    live.set_manual(ctx.user.id, f.get("state"))
    if _wants_json(ctx):
        return _json({"state": live.state_of(ctx.user.id)})
    back = f.get("back", "/chat")
    return _back(back if back.startswith("/") and not back.startswith("//") else "/chat")


def _presence_card(ctx) -> str:
    """Chat round six, on the desk's Chat page: who is on, and your own setting."""
    ops = live.operators(ctx.conn)
    if not ops:
        return ""
    mine = live.manual_of(ctx.user.id) or "AUTO"
    dots = "".join(
        f"<span class=tp title='{t.esc(o['name'])} · {t.esc(o['word'])}'><i class='pdot p-{o['state'].lower()}'></i> "
        f"{t.esc(o['name'])}{' (you)' if o['member'].lower() == ctx.user.id.lower() else ''}"
        f" <span class=muted>· {t.esc(o['word'])}</span></span>" for o in ops)
    me = ""
    if chat.is_operator(ctx.conn, ctx.user.id):
        me = ("<form method=post action='/chat/presence' class=tme><span class=muted>You:</span>"
              + "".join(f"<button type=submit name=state value={k} class='ghost small{' on' if mine == k else ''}'>{w}</button>"
                        for k, w in (("AUTO", "Automatic"), ("BUSY", "Busy"), ("AWAY", "Away")))
              + "<input type=hidden name=back value='/chat'></form>"
              "<p class=why style='margin:4px 0 0'>Automatic is online while a desk page is open, away after five "
              "minutes without one. The In/Out board's Out or On leave shows instead.</p>")
    return f"<div class=card id=chatpresence><h3>Who is on</h3><div class=twho>{dots}</div>{me}</div>"


def messages_json(ctx, chat_id):
    c = _load(ctx, chat_id)
    return _poll(ctx, c, viewer=ctx.user.id, desk=True, base=f"/chat/{c['chat_id']}")


def _act(ctx, chat_id, fn, ok):
    c = _load(ctx, chat_id, need="WORK")
    try:
        r = fn(c)
        ctx.conn.commit()
    except chat.Refused as exc:
        ctx.conn.rollback()
        return _back(f"/chat/{c['chat_id']}", err=str(exc))
    return ok(c, r)


def _say_or_file(ctx, c, *, sender: str, kind: str):
    """A line, or a file with the words as its caption. Returns (id, findings)."""
    body = ctx.request.form().get("body", "")
    got = ctx.request.files("file")
    if got:
        from ... import attachments
        filename, data = got[0]
        try:
            return chat.add_file(ctx.conn, c["chat_id"], data, filename, sender=sender, kind=kind,
                                 caption=body or None, at=ctx.now), []
        except attachments.Refused as exc:
            raise chat.Refused(str(exc)) from None
    return chat.say(ctx.conn, c["chat_id"], sender=sender, kind=kind, body=body, at=ctx.now)


def send(ctx, chat_id):
    c = _load(ctx, chat_id, need="WORK")
    try:
        mid, _ = _say_or_file(ctx, c, sender=ctx.user.id, kind=chat.STAFF)
        ctx.conn.commit()
        live.stop_typing(c["chat_id"], chat.STAFF)
    except chat.Refused as exc:
        ctx.conn.rollback()
        return _json({"error": str(exc)}) if _wants_json(ctx) else _back(f"/chat/{c['chat_id']}", err=str(exc))
    return _json({"id": mid}) if _wants_json(ctx) else _back(f"/chat/{c['chat_id']}")


def react(ctx, chat_id):
    c = _load(ctx, chat_id)                       # reading the board is enough to react
    f = ctx.request.form()
    try:
        on = chat.react(ctx.conn, c["chat_id"], int(f.get("message_id") or 0), member=ctx.user.id,
                        emoji=f.get("emoji", ""), at=ctx.now)
        ctx.conn.commit()
    except chat.Refused as exc:
        ctx.conn.rollback()
        return _json({"error": str(exc)})
    return _json({"on": on})


def _serve(ctx, c, row, data, *, board_id: str):
    from .. import Response
    from . import files as file_views
    kind = file_views.view_kind(row["media_type"])
    inline = bool(kind) and ctx.request.query.get("dl") != "1"
    common.audit_restricted_read(ctx, board_id, subject_id=f"chat {c['chat_id']}",
                                 detail=f"chat file {row['file_id']} ({row['filename']})")
    ascii_name = row["filename"].encode("ascii", "replace").decode().replace("?", "_").replace('"', "_")
    disposition = (f'{"inline" if inline else "attachment"}; filename="{ascii_name}"; '
                   f"filename*=UTF-8''{urllib.parse.quote(row['filename'])}")
    csp = "default-src 'none'; frame-ancestors 'self'" if inline and kind == "pdf" else "sandbox"
    return Response(body=data, content_type=row["media_type"], headers=[
        ("Content-Disposition", disposition), ("Content-Security-Policy", csp), ("Cache-Control", "private, no-store")])


def _file(ctx, c, file_id):
    from .. import HttpError
    try:
        return chat.read_file(ctx.conn, c["chat_id"], int(file_id) if str(file_id).isdigit() else -1)
    except LookupError:
        raise HttpError("404 Not Found", "No such file.")
    except OSError:
        raise HttpError("404 Not Found", "That file is missing or damaged; it was not served.")


def file_download(ctx, chat_id, file_id):
    c = _load(ctx, chat_id)
    row, data = _file(ctx, c, file_id)
    return _serve(ctx, c, row, data, board_id=c["board_id"])


def file_review(ctx, chat_id, file_id):
    return _act(ctx, chat_id, lambda c: chat.review_file(ctx.conn, c["chat_id"], int(file_id) if str(file_id).isdigit() else -1,
                                                         ctx.request.form().get("decision", ""), actor=ctx.user.id,
                                                         at=ctx.now),
                lambda c, r: _back(f"/chat/{c['chat_id']}", msg=r[:1].upper() + r[1:] + "."))


def live_for(ctx) -> list[dict]:
    """The live chats on the person's boards, each marked with whether they may
    pick it up, for the banner and its quick view."""
    rows = chat.live(ctx.conn, _desk_boards(ctx), now=ctx.now)
    work = {}
    for r in rows:
        if r["board_id"] not in work:
            work[r["board_id"]] = common.may_access_board(ctx, r["board_id"], need="WORK")
        r["can"] = work[r["board_id"]]
        r["mine"] = r["can"] and r["status"] == chat.ACTIVE and r["picked_by"].lower() == ctx.user.id.lower()
    return rows


def waiting_json(ctx):
    """The banner every desk page runs: what waits (for the chime) and every
    live chat (for the quick view). The page's script draws them as data."""
    rows = live_for(ctx)
    keep = ("id", "subject", "who", "name", "nth", "total", "label", "board", "status", "with", "since", "waited",
            "last", "last_from", "can", "mine")
    me = ctx.user.id.lower()
    ops = [{"name": o["name"], "first": o["first"], "state": o["state"], "word": o["word"], "me": o["member"].lower() == me}
           for o in live.operators(ctx.conn)]
    return _json({"chats": [{k: r[k] for k in keep} for r in rows if r["status"] == chat.WAITING],
                  "live": [{k: r[k] for k in keep} for r in rows], "word": t.chat_ticker(rows)[0],
                  "operators": ops, "me": {"state": live.state_of(ctx.user.id), "manual": live.manual_of(ctx.user.id)}
                  if chat.is_operator(ctx.conn, ctx.user.id) else None})


def pick(ctx, chat_id):
    return _act(ctx, chat_id, lambda c: chat.pick_up(ctx.conn, c["chat_id"], member=ctx.user.id, at=ctx.now),
                lambda c, r: _back(f"/chat/{c['chat_id']}", msg="You have the chat."))


def end(ctx, chat_id):
    f = ctx.request.form()
    # The window posts `asked` with the tick; a bare post (an older page) asks, as before.
    ask = f.get("ask") == "1" or f.get("asked") != "1"
    return _act(ctx, chat_id, lambda c: chat.close(ctx.conn, c["chat_id"], by=ctx.user.id, at=ctx.now,
                                                   closing=f.get("closing"), ask=ask),
                lambda c, r: _back(f"/chat/{c['chat_id']}", msg="Chat ended." + (
                    f" {_first(ctx.conn, c['requester'])} is asked how you did." if ask else " No rating was asked.")))


def _clock_the_chat(ctx, c, wid: str) -> None:
    """The operator's time on the chat, ready on the ticket for them to confirm
    (Dada, 7 Oct 2026: "if the chat is converted into a ticket can it be that the
    operators time be recorded"; confirmed: pre-filled, the operator confirms).
    A stopped clock from their pick-up to now, with the chat named in its notes:
    the ticket's own time entry window opens on it, to save, correct or cancel.
    Nothing is booked until they save. A clock of theirs already on that ticket
    is left as it is, and the window opens on that one."""
    from ... import timers
    me = ctx.user.id
    if timers.for_ticket(ctx.conn, wid, me) is not None:
        return
    nth, _ = chat.counts(ctx.conn, c["chat_id"])
    since = chat.operator_since(ctx.conn, c["chat_id"], me, now=ctx.now)
    timer_id = timers.start(ctx.conn, wid, member=me, at=since)
    timers.note(ctx.conn, timer_id, member=me, text=f"Chat with {chat.label(ctx.conn, c['requester'], nth)}")
    timers.stop(ctx.conn, timer_id, member=me, at=ctx.now)


def _to_ticket_page(c, wid: str, msg: str):
    return _back(f"/ticket/{wid}", msg=msg, te="1")


def make_ticket(ctx, chat_id):
    f = ctx.request.form()

    def go(c):
        wid = chat.to_ticket(ctx.conn, c["chat_id"], member=ctx.user.id, summary=f.get("summary") or None, at=ctx.now)
        _clock_the_chat(ctx, c, wid)
        return wid
    return _act(ctx, chat_id, go, lambda c, wid: _to_ticket_page(
        c, wid, f"Ticket {wid} raised from the chat. Your time on the chat is in the time entry: check it and save."))


def attach(ctx, chat_id):
    wid = (ctx.request.form().get("work_item_id", "") or "").strip().upper()

    def go(c):
        tk = ctx.conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?", (wid,)).fetchone()
        if tk is None or not common.may_access_board(ctx, tk["board_id"], need="WORK") \
                or not common.project_ticket_ok(ctx, wid):
            raise chat.Refused(f"No ticket {wid} that you work.")
        r = chat.attach(ctx.conn, c["chat_id"], wid, member=ctx.user.id, at=ctx.now)
        _clock_the_chat(ctx, c, wid)
        return r
    return _act(ctx, chat_id, go, lambda c, r: _to_ticket_page(
        c, wid, f"Chat added to {r}. Your time on the chat is in the time entry: check it and save."))


# ================================================================ the portal

def _mine(ctx, chat_id):
    from .. import HttpError
    from .portal import _identities
    c = chat.get(ctx.conn, int(chat_id)) if str(chat_id).isdigit() else None
    if c is None or c["requester"].lower() not in _identities(ctx):
        raise HttpError("404 Not Found", "No such chat.")
    return c


# What to put in a chat, in the words the wards use (Dada, 7 Oct 2026: "a reminder
# what to add to the chats so the user will follow it ... as taglish"). Confirmed:
# a card beside the start-a-chat form.
PAALALA_TITLE = "Paalala bago mag-chat"
PAALALA_LEAD = "Para mas mabilis namin kayong matulungan, pakilagay po sa message:"
PAALALA = (
    ("Saan kayo", "ward o office, at ang room (hal. Ward 3, Nurse Station)"),
    ("Anong gamit", "PC name o asset tag na nakadikit sa unit, printer, o phone extension"),
    ("Ano ang nangyari", "ano ang ginagawa ninyo nung nagka-problema, at ang eksaktong error message"),
    ("Kailan pa", "kanina lang ba, o ilang araw na"),
    ("Ilan ang apektado", "kayo lang ba, o buong ward o office"),
    ("Paano kayo makokontak", "local o extension number"),
    ("Picture o screenshot", "ng error, puwede pong i-attach dito sa chat 📎"),
)
PAALALA_PHI = "Huwag po ilagay ang pangalan o anumang detalye ng pasyente."


# Chat round six. Dada, 8 Oct 2026: "a reminder that the chat stays just come
# back to this if you need to do anything".
CHAT_STAYS = ("Your chat stays here. You can leave this page and come back any time from Chat; the desk's replies "
              "will be waiting.")
CHAT_STAYS_TL = "Hindi po mawawala ang chat. Balikan lang dito kung may kailangan pa kayo."


def _chat_stays() -> str:
    return f"<p class='why chatstays' id=chatstays>💬 {t.esc(CHAT_STAYS)} <i>{t.esc(CHAT_STAYS_TL)}</i></p>"


def _paalala() -> str:
    return (f"<div class='card paalala' id=chatpaalala><h3>📝 {t.esc(PAALALA_TITLE)}</h3><p>{t.esc(PAALALA_LEAD)}</p><ul>"
            + "".join(f"<li><b>{t.esc(k)}</b> — {t.esc(v)}</li>" for k, v in PAALALA)
            + f"</ul><p class=paalalawarn>⚠️ <b>{t.esc(PAALALA_PHI)}</b></p></div>")


def my_index(ctx, *, error: str = ""):
    """The requester's chats and a box to start one. Offered at any time; a chat
    started out of hours waits until someone from the desk is in."""
    from .. import Response
    from .portal import _identities
    ids = _identities(ctx)
    rows = chat.of_requester(ctx.conn, ids)
    boards = list(chat.chat_boards(ctx.conn))          # 073: only the boards that take chats (PMO Helpdesk)
    open_id = chat.open_chat_of(ctx.conn, ids)          # chat round six: one at a time
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
    start = ("<div class=grid2 style='grid-template-columns:minmax(0,3fr) minmax(0,2fr);align-items:start'>"
             "<div class=card id=chatstart><h3>" + t.icon("note") + "Start a chat</h3>"
             "<form method=post action='/my/chat/new' class=stack style='max-width:none'>"
             "<label>What is it about? <input name=subject maxlength=200 placeholder='hal. Printer sa Ward 3, ayaw mag-print'></label>" + who
             + "<label>Your message <textarea name=body required maxlength=2000 rows=6 placeholder='Saan kayo (ward/office, room), "
               "anong gamit (PC name o asset tag), ano ang error, at kailan pa. Huwag po ilagay ang detalye ng pasyente.'>"
               "</textarea></label>"
               "<div><button type=submit>Start the chat</button></div></form></div>" + _paalala() + "</div>"
             if boards else "<div class='banner err' id=chatstart>Chat is not available right now. Please raise a request, "
                            "or ring the desk.</div>")
    start = start.replace("<form method=post action='/my/chat/new'", "<form method=post action='/my/chat/new' data-once")
    if open_id is not None:
        oc = chat.get(ctx.conn, open_id)
        start = ("<div class=grid2 style='grid-template-columns:minmax(0,3fr) minmax(0,2fr);align-items:start'>"
                 f"<div class=card id=chatopen><h3>{t.icon('note')}You have a chat open</h3>"
                 f"<p><b>{t.esc(oc['subject'])}</b> · {t.esc(_status_words(oc, ctx.conn))}</p>{_chat_stays()}"
                 f"<p><a class=btn href='/my/chat/{open_id}'>Continue the chat</a></p>"
                 "<p class=why style='margin:0'>One chat at a time: when this one ends, you can start another.</p></div>"
                 + _paalala() + "</div>")
    if boards:
        start = _desk_on_line(ctx.conn, boards[0]["board_id"] if len(boards) == 1 else None) + start
    body = ((f"<div class='banner err'>{t.esc(error)}</div>" if error else "")
            + "<h1>Chat with the helpdesk</h1><p class='sub'>Type what is wrong and someone from the desk will answer "
              "here. If it needs work, they will raise a request for you.</p>"
            + start
            + ("<div class=card><h3>Your chats</h3><div class=tablewrap><table><thead><tr><th>About</th><th>With</th>"
               f"<th>State</th><th>Started</th></tr></thead><tbody>{lis}</tbody></table></div></div>" if rows else ""))
    return Response("400 Bad Request" if error else "200 OK", t.page("Chat", body, user=ctx.user, active="chat"))


def my_start(ctx):
    f = ctx.request.form()
    boards = {b["board_id"] for b in chat.chat_boards(ctx.conn)}     # 073: only boards that take chats
    chosen = f.get("board_id", "")
    if chosen and chosen not in boards:
        return my_index(ctx, error="That is not a desk that takes chats.")
    if not chosen:
        if len(boards) == 1:
            chosen = next(iter(boards))
        elif boards:
            return my_index(ctx, error="Tell us who this is for.")
        else:
            return my_index(ctx, error="Chat is not available right now. Please raise a request, or ring the desk.")
    requester = (getattr(ctx.user, "email", None) or ctx.user.id or "").lower()
    from .portal import _identities
    try:
        cid, findings = chat.start(ctx.conn, requester=requester, board_id=chosen, subject=f.get("subject", ""),
                                   first=f.get("body", ""), at=ctx.now, same_person=_identities(ctx))
        ctx.conn.commit()
    except chat.AlreadyOpen as exc:                    # chat round six: back to the one they have
        ctx.conn.rollback()
        if exc.chat_id is not None:
            return _back(f"/my/chat/{exc.chat_id}", already="1")
        return my_index(ctx, error=str(exc))
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
    end_form = (f"<form method=post action='/my/chat/{cid}/end' style='margin-top:8px'>"
                "<button class=ghost type=submit>End the chat</button></form>" if c["status"] != chat.CLOSED else "")
    rated = chat.survey_of(ctx.conn, cid)
    if rated:
        survey = (f"<div class=card id=chatrated><b>You rated this chat {'★' * rated['score']}{'☆' * (5 - rated['score'])}.</b>"
                  " Thank you.</div>")
    elif not chat.asked(c):
        survey = ""
    else:
        # Shown when the chat ends: here at once if it has, else the poll reveals it.
        stars = "".join(f"<label class=star><input type=radio name=score value={n} required><span>{'★' * n}</span></label>"
                        for n in range(5, 0, -1))
        survey = (f"<div class=card id=chatsurvey{'' if c['status'] == chat.CLOSED else ' hidden'}><h3>{t.icon('star')}"
                  f"<span class=rwho>{t.esc(_rate_title(ctx.conn, c))}</span></h3><p class=why style='margin-top:0'>{t.esc(RATE_LEAD)}</p>"
                  f"<form method=post action='/my/chat/{cid}/survey' class=stack style='max-width:none'>"
                  f"<div class=stars role=radiogroup aria-label='One to five stars'>{stars}</div>"
                  "<label>Anything to add? <textarea name=comment maxlength=1000 rows=2></textarea></label>"
                  "<div><button type=submit>Send the rating</button></div></form></div>")
    tk = (f"<p class=why>The desk raised request <a href='/my/{t.esc(c['work_item_id'])}'>{t.esc(c['work_item_id'])}</a> "
          "from this chat.</p>" if c["work_item_id"] else "")
    body = ("<a class=backbtn href='/my/chat'>" + t.icon("left") + "<span class=lbl>Your chats</span></a>"
            f"<h1>{t.esc(c['subject'])}</h1><p class='sub'>{t.esc(c['board_name'])} · "
            f"<span id=chatstate class=chatstate>{t.esc(_status_words(c, ctx.conn))}</span></p>"
            + (_desk_on_line(ctx.conn, c["board_id"]) if c["status"] != chat.CLOSED else "")
            + ("<div class='banner ok' id=chatalready>You already have a chat open with the desk, so you are back in "
               "it. What you typed on the form was not sent: write it below.</div>"
               if ctx.request.query.get("already") == "1" and c["status"] != chat.CLOSED else "")
            + f"<div id=chatwarn class='banner err'{'' if warn else ' hidden'}>{t.esc(WARN)}</div>" + tk
            + "<div class=card>" + _conversation(ctx, c, rows, me_kind=chat.REQUESTER, viewer=c["requester"], desk=False,
                                                  base=f"/my/chat/{cid}", can_send=c["status"] != chat.CLOSED)
            + (_chat_stays() if c["status"] != chat.CLOSED else "")
            + end_form + "</div>" + survey)
    return Response(body=t.page("Chat", body, user=ctx.user, active="chat"))


def my_messages_json(ctx, chat_id):
    c = _mine(ctx, chat_id)
    return _poll(ctx, c, viewer=c["requester"], desk=False, base=f"/my/chat/{c['chat_id']}")


def my_send(ctx, chat_id):
    c = _mine(ctx, chat_id)
    try:
        mid, findings = _say_or_file(ctx, c, sender=c["requester"], kind=chat.REQUESTER)
        ctx.conn.commit()
        live.stop_typing(c["chat_id"], chat.REQUESTER)
    except chat.Refused as exc:
        ctx.conn.rollback()
        if _wants_json(ctx):
            return _json({"error": str(exc)})
        return _back(f"/my/chat/{c['chat_id']}")
    if _wants_json(ctx):
        return _json({"id": mid, "warn": bool(findings)})
    return _back(f"/my/chat/{c['chat_id']}", warn="1" if findings else "")


def my_typing(ctx, chat_id):
    """POST /my/chat/<id>/typing: the ward is typing in their chat."""
    c = _mine(ctx, chat_id)
    if c["status"] != chat.CLOSED:
        live.typing(c["chat_id"], chat.REQUESTER, chat._name(ctx.conn, c["requester"]))
    return _json({"ok": True})


def my_end(ctx, chat_id):
    c = _mine(ctx, chat_id)
    chat.close(ctx.conn, c["chat_id"], by=c["requester"], at=ctx.now)
    ctx.conn.commit()
    return _back(f"/my/chat/{c['chat_id']}")


def my_react(ctx, chat_id):
    c = _mine(ctx, chat_id)
    f = ctx.request.form()
    try:
        on = chat.react(ctx.conn, c["chat_id"], int(f.get("message_id") or 0), member=c["requester"],
                        emoji=f.get("emoji", ""), at=ctx.now)
        ctx.conn.commit()
    except chat.Refused as exc:
        ctx.conn.rollback()
        return _json({"error": str(exc)})
    return _json({"on": on})


def my_file(ctx, chat_id, file_id):
    """A file in the requester's own chat: theirs, or the desk's; never one held back."""
    from .. import HttpError
    c = _mine(ctx, chat_id)
    row, data = _file(ctx, c, file_id)
    if row["review_status"] == "WITHHELD":
        raise HttpError("404 Not Found", "No such file.")
    return _serve(ctx, c, row, data, board_id=c["board_id"])


def my_survey(ctx, chat_id):
    c = _mine(ctx, chat_id)
    f = ctx.request.form()
    try:
        score = int(f.get("score") or 0)
        findings = chat.answer_survey(ctx.conn, c["chat_id"], score=score, comment=f.get("comment"),
                                      by=c["requester"], at=ctx.now)
        ctx.conn.commit()
    except (chat.Refused, ValueError):
        ctx.conn.rollback()
        return _back(f"/my/chat/{c['chat_id']}")
    return _back(f"/my/chat/{c['chat_id']}", warn="1" if findings else "")
