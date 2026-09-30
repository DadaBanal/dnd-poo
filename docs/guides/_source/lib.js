(function(){
"use strict";
var $=function(s,r){return (r||document).querySelector(s)}, $$=function(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))};
function store(k,v){try{if(v===undefined)return localStorage.getItem(k);localStorage.setItem(k,v)}catch(e){return null}}
function el(tag,attrs,kids){var e=document.createElement(tag);if(attrs)for(var k in attrs){if(k==="text")e.textContent=attrs[k];else if(k==="html")e.innerHTML=attrs[k];else if(k.slice(0,2)==="on")e.addEventListener(k.slice(2),attrs[k]);else e.setAttribute(k,attrs[k])}(kids||[]).forEach(function(c){if(c!=null)e.appendChild(typeof c==="string"?document.createTextNode(c):c)});return e}
function esc(s){return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}
function cfg(w){var s=$("script.cfg",w);try{return s?JSON.parse(s.textContent):{}}catch(e){return {}}}
function money(n,cur){return (cur||"PHP")+" "+Number(n||0).toLocaleString("en-PH",{minimumFractionDigits:2,maximumFractionDigits:2})}
function r2(n){return Math.round((n+Number.EPSILON)*100)/100}
var DATA={};try{DATA=JSON.parse($("#guide-data").textContent)}catch(e){}
var SLUG=document.body.dataset.guide||"guide";

/* ================= page chrome ================= */
var sections=$$("section.s"), toc=$("#toc"), group="";
sections.forEach(function(s){
  if(s.dataset.group!==group){group=s.dataset.group;toc.appendChild(el("div",{"class":"toc__group","data-group":group,text:group}))}
  var a=el("a",{href:"#"+s.id,"data-id":s.id},[el("span",{text:s.dataset.title}),el("i",{"class":"tick"})]);toc.appendChild(a);
});
var links=$$("a[data-id]",toc);
var done={};try{done=JSON.parse(store("pmc-guide-done-"+SLUG)||"{}")||{}}catch(e){done={}}
function paintDone(){
  var vis=sections.filter(function(s){return !s.hidden}),n=vis.filter(function(s){return done[s.id]}).length;
  $("#progText").textContent=n+" of "+vis.length+" sections read";
  $("#progBar").style.width=(vis.length?Math.round(100*n/vis.length):0)+"%";
  links.forEach(function(a){a.classList.toggle("done",!!done[a.dataset.id])});
  sections.forEach(function(s){var b=$(".done-btn",s);if(b){b.setAttribute("aria-pressed",String(!!done[s.id]));b.lastChild.textContent=done[s.id]?"Read":"Mark as read"}});
}
sections.forEach(function(s){var b=$(".done-btn",s);if(b)b.addEventListener("click",function(){done[s.id]=!done[s.id];store("pmc-guide-done-"+SLUG,JSON.stringify(done));paintDone()})});
var role=store("pmc-guide-role")||"all",q="",hasRoles=!!$("[data-role]");
if(!hasRoles)role="all";
function apply(){
  var words=q.toLowerCase().split(/\s+/).filter(Boolean),shown=0;
  sections.forEach(function(s){
    var okRole=role==="all"||!s.dataset.roles||(" "+s.dataset.roles+" ").indexOf(" "+role+" ")>=0;
    var text=(s.dataset.text||(s.dataset.text=s.textContent.toLowerCase()));
    s.hidden=!(okRole&&words.every(function(w){return text.indexOf(w)>=0}));if(!s.hidden)shown++;
  });
  links.forEach(function(a){a.hidden=document.getElementById(a.dataset.id).hidden});
  $$(".toc__group").forEach(function(g){g.style.display=sections.some(function(s){return s.dataset.group===g.dataset.group&&!s.hidden})?"":"none"});
  $("#empty").style.display=shown?"none":"block";
  $("#qn").textContent=words.length?shown+" found":"";
  $$("[data-role]").forEach(function(b){b.setAttribute("aria-pressed",String(b.dataset.role===role))});
  mark(words);paintDone();
}
function mark(words){
  $$("mark.hl").forEach(function(m){var p=m.parentNode;p.replaceChild(document.createTextNode(m.textContent),m);p.normalize()});
  if(!words.length)return;
  var re=new RegExp("("+words.map(function(w){return w.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")}).join("|")+")","gi");
  sections.filter(function(s){return !s.hidden}).forEach(function(s){
    var w=document.createTreeWalker(s,NodeFilter.SHOW_TEXT,{acceptNode:function(n){return n.parentNode.closest("script,style,button,select,option,textarea,.tour__txt,.widget")?NodeFilter.FILTER_REJECT:(re.test(n.nodeValue)?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_SKIP)}}),list=[],n;
    while((n=w.nextNode()))list.push(n);
    list.forEach(function(t){re.lastIndex=0;var sp=document.createElement("span");sp.innerHTML=esc(t.nodeValue).replace(re,"<mark class=hl>$1</mark>");while(sp.firstChild)t.parentNode.insertBefore(sp.firstChild,t);t.parentNode.removeChild(t)});
  });
}
$$("[data-role]").forEach(function(b){b.addEventListener("click",function(){role=(role===b.dataset.role&&b.closest(".pick"))?"all":b.dataset.role;store("pmc-guide-role",role);apply();if(b.closest(".pick")){var f=sections.filter(function(s){return !s.hidden})[0];if(f)f.scrollIntoView()}})});
var tq;$("#q").addEventListener("input",function(e){clearTimeout(tq);tq=setTimeout(function(){q=e.target.value.trim();apply()},160)});
if("IntersectionObserver" in window){var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting)links.forEach(function(a){a.classList.toggle("on",a.dataset.id===e.target.id)})})},{rootMargin:"-30% 0px -60% 0px"});sections.forEach(function(s){io.observe(s)})}
var rail=$("#rail"),scrim=$("#scrim");function menu(o){rail.classList.toggle("open",o);scrim.classList.toggle("show",o)}
$("#menuBtn").addEventListener("click",function(){menu(!rail.classList.contains("open"))});scrim.addEventListener("click",function(){menu(false)});
$$("a",toc).forEach(function(a){a.addEventListener("click",function(){menu(false)})});
$("#themeBtn").addEventListener("click",function(){var cur=document.documentElement.dataset.theme||(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"),nx=cur==="dark"?"light":"dark";document.documentElement.dataset.theme=nx;store("pmc-guide-theme",nx)});
$("#printBtn").addEventListener("click",function(){window.print()});
var tt=$("#totop");window.addEventListener("scroll",function(){tt.classList.toggle("show",scrollY>900)},{passive:true});tt.addEventListener("click",function(){scrollTo(0,0)});

/* lightbox */
var lb=$("#lb");
document.addEventListener("click",function(e){var sh=e.target.closest(".shot");if(!sh||sh.closest(".tour")||e.target.closest("button"))return;
  var img=$("img",sh),fig=sh.closest("figure"),cap=fig&&$("figcaption",fig);$("#lbImg").src=img.src;$("#lbImg").alt=img.alt;$("#lbCap").textContent=cap?cap.textContent:img.alt;
  if(lb.showModal)lb.showModal();else window.open(img.src)});
$("#lbClose").addEventListener("click",function(){lb.close()});lb.addEventListener("click",function(e){if(e.target===lb)lb.close()});

/* hotspot tours */
$$(".tour").forEach(function(tour){
  var key=tour.dataset.tour,spots=(DATA.spots||{})[key]||[],txt=(DATA.tours||{})[key]||[],shot=$(".shot",tour),cur=0,btns=[];
  spots.forEach(function(sp,i){var b=el("button",{"class":"spot","aria-label":"Point "+sp.n+": "+((txt[i]||[""])[0]),text:String(sp.n)});b.style.left=sp.x+"%";b.style.top=sp.y+"%";b.addEventListener("click",function(){show(i)});shot.appendChild(b);btns.push(b)});
  function show(i){cur=(i+btns.length)%btns.length;btns.forEach(function(b,j){b.classList.toggle("on",j===cur)});$(".tour__n",tour).textContent=cur+1;var t=txt[cur]||["",""];var box=$(".tour__txt",tour);box.innerHTML="";box.appendChild(el("b",{text:t[0]}));box.appendChild(el("span",{text:t[1]}))}
  $$(".tour__nav button",tour).forEach(function(b){b.addEventListener("click",function(){show(cur+Number(b.dataset.d))})});
  if(btns.length)show(0);
});

/* ================= widgets ================= */
var W={};

/* chooser: .opt[data-k] -> template[data-k] or data-t text */
W.chooser=function(w){var out=$(".out",w);$$(".opt",w).forEach(function(b){b.addEventListener("click",function(){
  $$(".opt",w).forEach(function(x){x.setAttribute("aria-pressed",String(x===b))});
  var t=b.dataset.k&&$('template[data-k="'+b.dataset.k+'"]',w);out.innerHTML="";
  if(t)out.appendChild(t.content.cloneNode(true));else{out.appendChild(el("b",{text:b.textContent.trim()+". "}));out.appendChild(document.createTextNode(b.dataset.t||""))}
})})};

/* priority matrix */
W.prio=function(w){
  var M={I1U1:"P1",I1U2:"P2",I1U3:"P3",I2U1:"P2",I2U2:"P3",I2U3:"P4",I3U1:"P3",I3U2:"P4",I3U3:"P4"};
  var T={P1:"respond in 15 minutes, a plan in 1 hour, resolved in 4 hours",P2:"respond in 1 hour, a plan in 4 hours, resolved in 8 hours",P3:"respond in 4 hours, a plan in 8 hours, resolved in 1 day",P4:"respond in 8 hours, a plan in 1 day, resolved in 3 days"};
  var C={P1:"#C62828",P2:"#C66A00",P3:"#1F5BB0",P4:"#6B7684"},pick={};
  $$(".opts[data-k]",w).forEach(function(g){$$(".opt",g).forEach(function(b){b.addEventListener("click",function(){$$(".opt",g).forEach(function(x){x.setAttribute("aria-pressed",String(x===b))});pick[g.dataset.k]=b.dataset.v;go()})})});
  function go(){$$("td[data-c]",w).forEach(function(td){td.classList.remove("hit")});var tx=$(".prioTxt",w);
    if(!pick.i||!pick.u){tx.textContent=pick.i||pick.u?"Now answer the other question.":"Answer both questions.";return}
    var p=M[pick.i+pick.u],o=$(".big",w);o.textContent=p;o.style.background=C[p];tx.innerHTML="";
    tx.appendChild(el("b",{text:"This request is "+p+"."}));tx.appendChild(el("small",{text:"With the starter targets that means: "+T[p]+". Your board's service manager may set different targets, and the clocks run on the board's working hours."}));
    var c=$('td[data-c="'+pick.i+pick.u+'"]',w);if(c)c.classList.add("hit")}
};

/* image picker */
W.imgpick=function(w){var img=$("img",w),cap=$("figcaption",w);function show(b){$$(".opt",w).forEach(function(x){x.setAttribute("aria-pressed",String(x===b))});img.src=(DATA.images||{})[b.dataset.img]||img.src;img.alt=b.textContent.trim();if(cap)cap.textContent=b.dataset.cap||""}
  $$(".opt",w).forEach(function(b){b.addEventListener("click",function(){show(b)})});var f=$(".opt",w);if(f)show(f)};

/* state machine stepper */
W.stepper=function(w){var c=cfg(w),box=$(".out",w)||w.appendChild(el("div",{"class":"w-out"})),cur=c.start,hist=[c.start];
  function render(){var s=c.states[cur];box.innerHTML="";
    box.appendChild(el("div",{},[el("span",{"class":"st "+(s.tone||"blue"),text:s.label})," ",el("span",{text:s.text||""})]));
    var mv=el("div",{"class":"moves"});
    (s.next||[]).forEach(function(n){var need=n[2],inp=null;
      if(need){inp=el("input",{type:"text",placeholder:need,style:"min-width:220px"});mv.appendChild(inp)}
      var b=el("button",{"class":"w-btn"+(n[3]?" ghost":""),text:n[1],onclick:function(){if(inp&&!inp.value.trim()){msg.textContent=n[4]||"This move needs: "+need+".";msg.style.display="block";inp.focus();return}cur=n[0];hist.push(cur);render()}});mv.appendChild(b)});
    if(!(s.next||[]).length)mv.appendChild(el("span",{"class":"muted",style:"color:var(--text-3);font-size:13.5px",text:s.end||"This is where it ends. Nothing moves it from here."}));
    var reset=el("button",{"class":"w-btn ghost",text:"Start again",onclick:function(){cur=c.start;hist=[c.start];render()}});mv.appendChild(reset);
    box.appendChild(mv);var msg=el("div",{"class":"w-out err",style:"display:none"});box.appendChild(msg);
    var tr=el("div",{"class":"trail"});hist.forEach(function(h,i){if(i)tr.appendChild(el("span",{text:"→"}));tr.appendChild(el("span",{"class":"st "+(c.states[h].tone||"blue"),text:c.states[h].label}))});box.appendChild(tr)}
  render()};

/* permission levels for one module */
W.perm=function(w){var c=cfg(w),rank={NONE:0,READ:1,WRITE:2,ADMIN:3},sel=$("select",w),out=$(".out",w);
  function go(){var lv=sel.value,ul=el("table",{"class":"wt"});ul.appendChild(el("tr",{},[el("th",{text:"What"}),el("th",{text:"At "+lv})]));
    c.actions.forEach(function(a){var ok=rank[lv]>=rank[a[1]];ul.appendChild(el("tr",{},[el("td",{text:a[0]}),el("td",{"class":ok?"can":"cannot",text:ok?"Yes":"No, needs "+a[1]})]))});
    out.innerHTML="";if(lv==="NONE")out.appendChild(el("p",{style:"margin:0 0 6px",text:c.none||"The module is not shown at all."}));out.appendChild(ul)}
  sel.addEventListener("change",go);go()};

/* security role matrix */
W.roles=function(w){var c=cfg(w),sel=$("select",w),out=$(".out",w),L={NONE:"Not shown",READ:"Look",WRITE:"Add and edit",ADMIN:"Everything, and the module's own setup"};
  function go(){var r=c.roles[sel.value],t=el("table",{"class":"wt"});t.appendChild(el("tr",{},[el("th",{text:"Module"}),el("th",{text:"Level"}),el("th",{text:"Means"})]));
    Object.keys(c.modules).forEach(function(m){var lv=r[m]||"NONE";t.appendChild(el("tr",{},[el("td",{text:c.modules[m]}),el("td",{},[el("span",{"class":"st "+({NONE:"grey",READ:"blue",WRITE:"green",ADMIN:"amber"})[lv],text:lv})]),el("td",{text:L[lv]})]))});
    out.innerHTML="";out.appendChild(t)}sel.addEventListener("change",go);go()};

/* quote calculator */
W.quote=function(w){var tb=$("tbody",w),tax=$(".tax",w),out=$(".out",w);
  function row(d,q,p){var tr=el("tr",{},[el("td",{},[el("input",{type:"text",value:d})]),el("td",{},[el("input",{type:"number",value:q,min:"0",step:"any"})]),el("td",{},[el("input",{type:"number",value:p,min:"0",step:"any"})]),el("td",{"class":"n"}),el("td",{},[el("button",{"class":"w-btn ghost",text:"×","aria-label":"Remove line",onclick:function(){tr.remove();go()}})])]);tb.appendChild(tr);$$("input",tr).forEach(function(i){i.addEventListener("input",go)})}
  (cfg(w).lines||[]).forEach(function(l){row(l[0],l[1],l[2])});
  $(".add",w).addEventListener("click",function(){row("New line",1,0);go()});tax.addEventListener("input",go);
  function go(){var sub=0,n=0;$$("tr",tb).forEach(function(tr){var i=$$("input",tr),qv=Number(i[1].value||0),pv=Number(i[2].value||0),lt=Math.round(qv*pv*10000)/10000;sub+=lt;n++;tr.lastChild.previousSibling.textContent=money(lt)});
    sub=Math.round(sub*10000)/10000;var tv=Number(tax.value||0),tot=r2(sub*(1+tv/100));out.innerHTML="";
    out.appendChild(el("div",{},[el("b",{text:"Subtotal "}),money(sub)," · ",el("b",{text:"Tax "+tv+"% "}),money(tot-sub)," · ",el("b",{text:"Total "}),el("span",{style:"font-size:18px;font-weight:700",text:money(tot)})]));
    out.appendChild(el("div",{style:"font-size:13px;color:var(--text-3);margin-top:4px",text:n?"The same arithmetic the desk uses: each line is quantity × unit price; the total is the subtotal plus tax, to the centavo.":"A quote with no lines cannot be sent."}))}
  go()};

/* pipeline */
W.pipeline=function(w){var c=cfg(w),P={LEAD:10,QUALIFIED:40,PROPOSAL:70,WON:100,LOST:0},N={LEAD:"Lead",QUALIFIED:"Qualified",PROPOSAL:"Proposal sent",WON:"Won",LOST:"Lost"},tb=$("tbody",w),out=$(".out",w);
  c.rows.forEach(function(r){var s=el("select",{});Object.keys(N).forEach(function(k){var o=el("option",{value:k,text:N[k]});if(k===r[2])o.selected=true;s.appendChild(o)});var a=el("input",{type:"number",value:r[1],min:"0"});
    var tr=el("tr",{},[el("td",{text:r[0]}),el("td",{},[a]),el("td",{},[s]),el("td",{"class":"n"})]);tb.appendChild(tr);s.addEventListener("change",go);a.addEventListener("input",go)});
  function go(){var by={},tot=0,wt=0;$$("tr",tb).forEach(function(tr){var amt=Number($("input",tr).value||0),st=$("select",tr).value,wv=amt*P[st]/100;tr.lastChild.textContent=P[st]+"% · "+money(wv);by[st]=by[st]||{n:0,a:0,w:0};by[st].n++;by[st].a+=amt;by[st].w+=wv;if(st!=="WON"&&st!=="LOST"){tot+=amt;wt+=wv}});
    var t=el("table",{"class":"wt"});t.appendChild(el("tr",{},[el("th",{text:"Stage"}),el("th",{text:"Count"}),el("th",{text:"Amount"}),el("th",{text:"Weighted"})]));
    Object.keys(N).forEach(function(k){var b=by[k]||{n:0,a:0,w:0};t.appendChild(el("tr",{},[el("td",{text:N[k]+" ("+P[k]+"%)"}),el("td",{"class":"n",text:String(b.n)}),el("td",{"class":"n",text:money(b.a)}),el("td",{"class":"n",text:money(b.w)})]))});
    out.innerHTML="";out.appendChild(t);out.appendChild(el("p",{style:"margin:8px 0 0"},[el("b",{text:"Open pipeline: "}),money(tot)+", weighted "+money(wt)+"."]))}
  go()};

/* time entry */
W.timecalc=function(w){var s=$(".start",w),e=$(".end",w),d=$(".deduct",w),out=$(".out",w),B=[0.5,2,4,8,20];
  function mins(v){var p=(v||"").split(":");return p.length<2?null:Number(p[0])*60+Number(p[1])}
  function go(){var a=mins(s.value),b=mins(e.value),ded=Number(d.value||0);out.className="w-out out";
    if(a==null||b==null){out.textContent="Give a start and an end.";return}
    if(b<=a){out.className="w-out out err";out.textContent="The end is before the start. Time that runs past midnight is two entries, one per day.";return}
    var raw=(b-a)/60-ded,h=Math.floor(raw/0.25+0.5+1e-9)*0.25;if(h<=0){out.className="w-out out err";out.textContent="Refused: the time comes to nothing once the deduction is taken off.";return}
    if(h>20){out.className="w-out out err";out.textContent="Over 20 hours in one entry is refused: split it across the days it was worked.";return}
    var band=B.filter(function(x){return h<=x})[0];out.className="w-out out ok";out.innerHTML="";
    out.appendChild(el("div",{},[el("b",{text:h.toFixed(2)+" hours "}),"recorded ("+raw.toFixed(2)+" actual, kept to the quarter hour, half up). ",el("b",{text:"Band: "+band+" h"}),", the smallest band the hours fit in."]))}
  [s,e,d].forEach(function(i){i.addEventListener("input",go)});go()};

/* utilisation */
W.util=function(w){var h=$(".hours",w),c=$(".cap",w),out=$(".out",w);function go(){var hv=Number(h.value||0),cv=Number(c.value||40),p=cv?Math.round(100*hv/cv):0;out.innerHTML="";out.appendChild(el("div",{},[el("b",{text:p+"% "}),"utilisation: "+hv+" hours recorded against "+cv+" expected."]));var bar=el("div",{"class":"bar"+(p>100?" over":"")},[el("i",{style:"width:"+Math.min(p,100)+"%"})]);out.appendChild(bar)}[h,c].forEach(function(i){i.addEventListener("input",go)});go()};

/* SLA clocks as statuses change */
W.clocks=function(w){var c=cfg(w),STOP={RESPOND:["RESPONDED","RESOLUTION_PLAN","RESOLVED"],PLAN:["RESOLUTION_PLAN","RESOLVED"],RESOLVE:["RESOLVED"]},NAMES={RESPOND:"Respond",PLAN:"Resolution plan",RESOLVE:"Resolve"},st,hist,out=$(".out",w),mv=$(".moves",w);
  function reset(){st={RESPOND:"run",PLAN:"run",RESOLVE:"run"};hist=[c.statuses[0][0]];render()}
  function to(s){var esc=s[1];Object.keys(st).forEach(function(k){if(st[k]==="met")return;if(STOP[k].indexOf(esc)>=0)st[k]="met";else if(esc==="NO_ESCALATION"&&k!=="RESPOND")st[k]="paus";else st[k]="run"});hist.push(s[0]);render()}
  function render(){out.innerHTML="";var g=el("div",{"class":"clocks3"});Object.keys(st).forEach(function(k){g.appendChild(el("div",{},[el("b",{text:NAMES[k]}),el("span",{"class":st[k],text:{run:"Running",paus:"Paused",met:"Met, stopped"}[st[k]]})]))});out.appendChild(g);
    var tr=el("div",{"class":"trail"});hist.forEach(function(h,i){if(i)tr.appendChild(el("span",{text:"→"}));tr.appendChild(el("span",{"class":"st blue",text:h}))});out.appendChild(tr)}
  c.statuses.slice(1).forEach(function(s){mv.appendChild(el("button",{"class":"w-btn ghost",text:s[0],onclick:function(){to(s)}}))});mv.appendChild(el("button",{"class":"w-btn",text:"Start again",onclick:reset}));reset()};

/* paging timeline */
W.paging=function(w){var sl=$(".min",w),ack=$(".ack",w),dm=$(".dm",w),out=$(".out",w),lab=$(".minlab",w),E=5,MX=3;
  function go(){var m=Number(sl.value),a=ack.value===""?null:Number(ack.value),hasDm=dm.checked,ev=[];lab.textContent=m+" min";
    var t,att=0,end=null;for(t=0;t<=60;t+=E){if(a!=null&&a<=t&&a<=m){end=["ack",a];break}if(att<MX){ev.push([t,"Page "+(att+1)+" of "+MX+" to the on-call: an email and a Teams card"]);att++}else{end=["ex",t];break}}
    if(end&&end[0]==="ack")ev.push([end[1],"The on-call acknowledges on the ticket. The page ends."]);
    if(end&&end[0]==="ex"){ev.push([end[1],"Unanswered after "+MX+" pages: the page is exhausted."]);
      if(hasDm){var d=0;for(t=end[1];t<=end[1]+E*MX;t+=E){if(d<MX){ev.push([t,"Page "+(d+1)+" of "+MX+" to the duty manager"]);d++}else{ev.push([t,"The duty manager's page is exhausted too. Nobody further is paged; the ticket says so."]);break}}}
      else ev.push([end[1],"No duty manager on the rota now: the ticket records that there was nobody to escalate to."])}
    var ul=el("ul",{"class":"tl"});ev.forEach(function(e){var li=el("li",{"class":e[0]<=m?(e[1].indexOf("exhausted")>=0?"bad":"done"):"future"},[el("b",{text:"Minute "+e[0]+": "}),e[1]]);ul.appendChild(li)});out.innerHTML="";out.appendChild(ul)}
  [sl,ack,dm].forEach(function(i){i.addEventListener("input",go);i.addEventListener("change",go)});go()};

/* workflow rule builder */
W.rule=function(w){var f=function(n){return $("."+n,w)},out=$(".out",w);
  function go(){var ev=f("ev"),md=f("md"),fd=f("fd"),op=f("op"),val=f("val"),ac=f("ac"),ch=f("ch"),ro=f("ro"),tm=f("tm");
    var notify=["NOTIFY","ESCALATE"].indexOf(ac.value)>=0;ch.disabled=!notify;ro.disabled=!notify;tm.disabled=!(notify&&ch.value==="TEAMS");
    var cond=fd.value?(" and "+fd.options[fd.selectedIndex].text.toLowerCase()+" "+op.options[op.selectedIndex].text+(["IS_NULL","IS_NOT_NULL"].indexOf(op.value)>=0?"":" "+(val.value||"…"))):"";
    var act=ac.options[ac.selectedIndex].text.toLowerCase()+(notify?" the "+ro.options[ro.selectedIndex].text.toLowerCase()+" "+ch.options[ch.selectedIndex].text:"");
    var errs=[];if(notify&&ch.value==="TEAMS"&&!tm.value)errs.push("A Teams notification needs a channel (Setup › Integrations › Teams channels).");
    if(fd.value&&["IS_NULL","IS_NOT_NULL"].indexOf(op.value)<0&&!val.value.trim())errs.push("Give the value to compare with, e.g. P1.");
    out.className="w-out out"+(errs.length?" err":"");out.innerHTML="";
    out.appendChild(el("p",{style:"margin:0 0 6px"},[el("b",{text:"The rule reads: "}),"When "+ev.options[ev.selectedIndex].text.toLowerCase()+cond+", "+act+". Runs "+md.options[md.selectedIndex].text.toLowerCase()+"."]));
    errs.forEach(function(x){out.appendChild(el("div",{text:"Not saved: "+x}))});
    if(!errs.length)out.appendChild(el("div",{style:"font-size:13.5px;color:var(--text-2)",text:"Saved, it starts switched off. Press Test against open tickets to see how many open tickets it would match now; only a rule whose every event is tested can be switched on, and editing it switches it off again."}))}
  $$("select,input",w).forEach(function(i){i.addEventListener("input",go);i.addEventListener("change",go)});go()};

/* email template preview */
W.tpl=function(w){var s=$(".subj",w),b=$(".body",w),out=$(".out",w),V={ticket:"PMC-000123",board:"PMO Helpdesk",actor:"bob",when:"2026-10-02 09:00 to 10:00"},OK=["ticket","board","actor","when"];
  function fill(t){return t.replace(/\{([^{}]*)\}/g,function(m,k){return V.hasOwnProperty(k)?V[k]:m})}
  function go(){var bad=[];(s.value+" "+b.value).replace(/\{([^{}]*)\}/g,function(m,k){if(OK.indexOf(k)<0&&bad.indexOf("{"+k+"}")<0)bad.push("{"+k+"}")});out.innerHTML="";
    if(!s.value.trim()||!b.value.trim()){out.className="w-out out err";out.textContent="Not saved: an email needs a subject and a body.";return}
    if(bad.length){out.className="w-out out err";out.textContent="Not saved: a placeholder is {ticket}, {board}, {actor} or {when}; not "+bad.join(", ")+".";return}
    out.className="w-out out ok";out.appendChild(el("div",{},[el("b",{text:"Subject: "}),"[PMC-000123] "+fill(s.value)]));out.appendChild(el("div",{style:"white-space:pre-wrap;margin-top:6px",text:fill(b.value)}));
    out.appendChild(el("div",{style:"font-size:13px;color:var(--text-3);margin-top:6px",text:"The sender adds the reference to the subject, and the portal link below the body."}))}
  [s,b].forEach(function(i){i.addEventListener("input",go)});go()};

/* auto-assign */
W.assign=function(w){var tb=$("tbody",w),mode=$(".mode",w),rule=$(".rule",w),pair=$(".pair",w),has=$(".has",w),lead=$(".lead",w),out=$(".out",w);
  function members(){return $$("tr",tb).map(function(tr){var i=$$("input,select",tr);return {name:tr.dataset.m,access:i[0].value,open:Number(i[1].value||0),active:i[2].checked}})}
  function go(){var ms=members(),working=ms.filter(function(m){return m.active&&(m.access==="WORK"||m.access==="ADMIN")}),who=null,why="";
    if(has.checked){who=null;why="The ticket arrived with an owner, so it keeps that owner. Auto-assign only fills an empty owner."}
    else{if(rule.value&&pair.value==="PRINTER"){var r=working.filter(function(m){return m.name===rule.value})[0];if(r){who=r.name;why="The rule for Printer › Failure names "+r.name+", who works the board."}else why="The rule names "+rule.value+", who no longer works the board (or reads only), so the board's mode decides. "}
      if(!who){if(mode.value==="LEAST_LOADED"&&working.length){working.sort(function(a,b){return a.open-b.open||a.name.localeCompare(b.name)});who=working[0].name;why+="Least loaded: "+who+" has the fewest open tickets on the board ("+working[0].open+"); a tie goes by name."}
        else if(mode.value==="TEAM_LEADER"){var l=working.filter(function(m){return m.name===lead.value})[0];if(l){who=l.name;why+="The default team's leader, "+l.name+"."}else why+="The team leader does not work the board now, so nobody is assigned."}
        else why+=mode.value==="OFF"?"The mode is Nobody: the ticket waits in the queue.":"Nobody works the board."}}
    out.className="w-out out"+(who?" ok":"");out.innerHTML="";out.appendChild(el("div",{},[el("b",{text:who?"Goes to "+who+". ":"Nobody is assigned. "}),why]))}
  $$("input,select",w).forEach(function(i){i.addEventListener("input",go);i.addEventListener("change",go)});go()};

/* report builder */
W.report=function(w){var c=cfg(w),ds=$(".ds",w),cols=$(".cols",w),grp=$(".grp",w),out=$(".out",w);
  Object.keys(c.datasets).forEach(function(k){ds.appendChild(el("option",{value:k,text:c.datasets[k].label}))});
  function load(){var d=c.datasets[ds.value];cols.innerHTML="";grp.innerHTML="";grp.appendChild(el("option",{value:"",text:"(no grouping)"}));
    d.cols.forEach(function(x,i){var cb=el("input",{type:"checkbox"});cb.checked=i<4;cols.appendChild(el("label",{style:"display:inline-flex;gap:6px;align-items:center;margin:4px 12px 4px 0;font-weight:500"},[cb,x]));cb.addEventListener("change",go);grp.appendChild(el("option",{value:x,text:x}))});go()}
  function go(){var d=c.datasets[ds.value],chosen=$$("input",cols).map(function(cb,i){return cb.checked?d.cols[i]:null}).filter(Boolean),g=grp.value,t=el("table",{"class":"wt"}),hd=g?[g,"Count"].concat(d.hours?["Hours"]:[]):chosen;
    t.appendChild(el("tr",{},hd.map(function(h){return el("th",{text:h})})));for(var i=0;i<3;i++)t.appendChild(el("tr",{},hd.map(function(){return el("td",{style:"color:var(--text-3)",text:"…"})})));
    out.innerHTML="";out.appendChild(el("div",{style:"font-size:13.5px"},[el("b",{text:d.label+": "}),g?"one row per "+g.toLowerCase()+", with a count"+(d.hours?" and the sum of hours":"")+".":"one row per record, "+chosen.length+" column(s). Filter by board, a date range on "+d.date+(d.state?", and a state":"")+"."]));out.appendChild(t);
    out.appendChild(el("div",{style:"font-size:13px;color:var(--text-3);margin-top:6px",text:"Rows only ever come from boards you are a member of."}))}
  ds.addEventListener("change",load);grp.addEventListener("change",go);load()};

/* patient-detail checker */
W.phi=function(w){var ta=$("textarea",w),out=$(".out",w),R=[["ERROR","a PhilHealth-shaped number",/\b\d{2}-\d{9}-\d\b|\b\d{12}\b/],["ERROR","a case number",/\bcase\s*(?:no\.?|number|#)\s*[:#]?\s*\w+/i],["ERROR","a medical record number",/\b(?:mrn|hospital\s*(?:no\.?|number)|chart\s*(?:no\.?|number)|patient\s*(?:no\.?|number)|hrn)\s*[:#]?\s*\w+/i],["WARN","a date of birth",/\b(?:d\.?o\.?b\.?|date\s+of\s+birth)\b/i],["WARN","a patient named in the text",/\b(?:patient|px)\s*(?:name)?\s*[:#]\s*\w+|\bpatient\s+(?:mr|mrs|ms|dr)\b/i],["WARN","a PhilHealth reference",/\bphil\s*health\b/i]];
  function go(){var v=ta.value,f=R.filter(function(r){return r[2].test(v)});out.innerHTML="";
    if(!v.trim()){out.className="w-out out";out.textContent="Type a request above.";return}
    if(!f.length){out.className="w-out out ok";out.textContent="Nothing looks like a patient's details. Good: the ward, room and machine are all the desk needs.";return}
    out.className="w-out out err";out.appendChild(el("b",{text:"The desk would flag this for the author to tidy: "}));out.appendChild(document.createTextNode(f.map(function(r){return r[1]+(r[0]==="ERROR"?"":" (a warning)")}).join("; ")+". Nothing is deleted, and the request still goes through; take it out now and nobody has to tidy it later."))}
  ta.addEventListener("input",go);go()};

/* agreement coverage */
W.cover=function(w){var c=cfg(w),tb=$("tbody",w),amt=$(".amt",w),out=$(".out",w),W2={INVOICE:"Invoices",PURCHASE_ORDER:"Purchase orders",PRODUCT:"Products"};
  c.items.forEach(function(it){var cb=el("input",{type:"checkbox"});cb.checked=!!it[4];tb.appendChild(el("tr",{},[el("td",{},[cb]),el("td",{text:W2[it[0]].replace(/s$/,"")}),el("td",{text:it[1]}),el("td",{text:it[2]}),el("td",{"class":"n",text:it[3]==null?"—":money(it[3])})]));cb.addEventListener("change",go)});
  amt.addEventListener("input",go);
  function go(){var by={INVOICE:[0,0],PURCHASE_ORDER:[0,0],PRODUCT:[0,0]};$$("tr",tb).forEach(function(tr,i){if($("input",tr).checked){var it=c.items[i];by[it[0]][0]++;by[it[0]][1]+=it[3]||0}});
    var g=el("div",{"class":"clocks3",style:"grid-template-columns:repeat(4,1fr)"});["INVOICE","PURCHASE_ORDER"].forEach(function(k){g.appendChild(el("div",{},[el("b",{text:W2[k]}),el("span",{text:String(by[k][0])}),el("div",{style:"font-size:13px",text:money(by[k][1])})]))});
    g.appendChild(el("div",{},[el("b",{text:"Products"}),el("span",{text:String(by.PRODUCT[0])})]));g.appendChild(el("div",{},[el("b",{text:"Agreed amount"}),el("span",{text:money(Number(amt.value||0))})]));
    out.innerHTML="";out.appendChild(g);var inv=by.INVOICE[1],a=Number(amt.value||0);
    if(a)out.appendChild(el("p",{style:"margin:8px 0 0"},[el("b",{text:"Invoiced against it so far: "}),money(inv)+" of "+money(a)+" ("+Math.round(100*inv/a)+"%)."]))}
  go()};

/* two-way BizBox changes */
W.twoway=function(w){var c=cfg(w),recs=c.records,sw=$$(".switch button",w),rsel=$(".rec",w),fsel=$(".fld",w),val=$(".val",w),why=$(".why2",w),out=$(".log",w),msg=$(".msg",w),mirror=$(".mirror",w),on=false,changes=[],id=0;
  Object.keys(recs).forEach(function(k){rsel.appendChild(el("option",{value:k,text:recs[k].label}))});
  function fields(){fsel.innerHTML="";Object.keys(recs[rsel.value].fields).forEach(function(f){fsel.appendChild(el("option",{value:f,text:recs[rsel.value].fields[f][0]}))});showMirror()}
  function showMirror(){var r=recs[rsel.value],t=el("table",{"class":"wt"});t.appendChild(el("tr",{},[el("th",{text:"Field"}),el("th",{text:"In BizBox"}),el("th",{text:"On the desk (the mirror)"})]));
    Object.keys(r.fields).forEach(function(f){t.appendChild(el("tr",{},[el("td",{text:r.fields[f][0]}),el("td",{text:r.biz[f]}),el("td",{text:r.desk[f]})]))});mirror.innerHTML="";mirror.appendChild(t)}
  sw.forEach(function(b){b.addEventListener("click",function(){on=b.dataset.on==="1";sw.forEach(function(x){x.setAttribute("aria-pressed",String(x===b))});$(".runw",w).disabled=!on;say(on?"Planned: the write path is on. Press Run the writer and each pending change is offered to BizBox.":"Today: no write path. A proposal waits; nothing can reach BizBox by accident.","")})});
  function say(t,k){msg.className="w-out msg"+(k?" "+k:"");msg.textContent=t}
  $(".prop",w).addEventListener("click",function(){var r=recs[rsel.value],f=fsel.value,v=val.value.trim();
    if(!why.value.trim())return say("Refused: say why, so the person who applies it in BizBox knows.","err");
    if(!v)return say("Refused: give the new value.","err");
    if(v===r.biz[f])return say("Refused: that is the value BizBox already has.","err");
    if(changes.some(function(x){return x.rec===rsel.value&&x.f===f&&x.st==="PENDING"}))return say("Refused: a change to "+r.fields[f][0].toLowerCase()+" is already pending; cancel it first.","err");
    id++;changes.unshift({id:id,rec:rsel.value,f:f,old:r.biz[f],nv:v,why:why.value.trim(),st:"PENDING",ans:""});say("Change #"+id+" recorded. BizBox has not changed; it waits.","ok");render()});
  $(".runw",w).addEventListener("click",function(){var n=0;changes.forEach(function(x){if(x.st!=="PENDING")return;n++;
      if(/^x/i.test(x.nv)){x.st="REJECTED";x.ans="BizBox refused: not a value it accepts"}else{x.st="APPLIED";x.ans="BizBox accepted it";recs[x.rec].biz[x.f]=x.nv}});
    say(n?"The writer offered "+n+" change(s) to BizBox. The desk records BizBox's own answer on each. (Try a value starting with x to see a refusal.)":"Nothing pending.",n?"ok":"");render()});
  $(".sync",w).addEventListener("click",function(){Object.keys(recs).forEach(function(k){var r=recs[k];Object.keys(r.biz).forEach(function(f){r.desk[f]=r.biz[f]})});say("Sync ran (read-only, as it always does): the mirror now shows BizBox's own values.","ok");render()});
  function render(){var t=el("table",{"class":"wt"});t.appendChild(el("tr",{},["#","Record","Field","From → to","Why","State",""].map(function(h){return el("th",{text:h})})));
    changes.forEach(function(x){var r=recs[x.rec],acts=el("td");
      if(x.st==="PENDING"){acts.appendChild(el("button",{"class":"w-btn ghost",text:"Cancel",onclick:function(){x.st="CANCELLED";x.ans="cancelled by the person";render()}}));
        acts.appendChild(el("button",{"class":"w-btn ghost",style:"margin-left:6px",text:"Done in BizBox by hand",onclick:function(){x.st="APPLIED";x.ans="applied in BizBox by hand, marked with bizbox-changes --decide";r.biz[x.f]=x.nv;render()}}))}
      var tone={PENDING:"amber",APPLIED:"green",REJECTED:"red",CANCELLED:"grey"}[x.st],word={PENDING:"Waiting for BizBox",APPLIED:"Applied",REJECTED:"Refused",CANCELLED:"Cancelled"}[x.st];
      t.appendChild(el("tr",{},[el("td",{text:"#"+x.id}),el("td",{text:r.label}),el("td",{text:r.fields[x.f][0]}),el("td",{text:x.old+" → "+x.nv}),el("td",{text:x.why}),el("td",{},[el("span",{"class":"st "+tone,text:word}),x.ans?el("div",{style:"font-size:12px;color:var(--text-3)",text:x.ans}):null]),acts]))});
    out.innerHTML="";if(changes.length)out.appendChild(t);else out.appendChild(el("div",{style:"color:var(--text-3);font-size:14px",text:"No change proposed yet."}));showMirror()}
  rsel.addEventListener("change",fields);fields();render();say("Today: no write path. A proposal waits; nothing can reach BizBox by accident.","")};

/* recurrence */
W.recur=function(w){var f=$(".first",w),cad=$(".cad",w),n=$(".every",w),out=$(".out",w),M={MONTHLY:1,QUARTERLY:3,YEARLY:12};
  function adv(d,c,k,anchor){if(c==="DAILY"){var x=new Date(d);x.setDate(x.getDate()+k);return x}if(c==="WEEKLY"){var y=new Date(d);y.setDate(y.getDate()+7*k);return y}
    var mo=M[c]*k,yy=d.getFullYear()+Math.floor((d.getMonth()+mo)/12),mm=(d.getMonth()+mo)%12,last=new Date(yy,mm+1,0).getDate();return new Date(yy,mm,Math.min(anchor,last))}
  function fmt(d){return d.toLocaleDateString("en-GB",{weekday:"short",day:"numeric",month:"short",year:"numeric"})}
  function go(){var p=(f.value||"").split("-");if(p.length<3){out.textContent="Pick the first due day.";return}var d=new Date(Number(p[0]),Number(p[1])-1,Number(p[2])),anchor=d.getDate(),k=Math.max(1,Number(n.value||1)),ul=el("ul",{"class":"tl"});
    for(var i=0;i<6;i++){ul.appendChild(el("li",{"class":i?"future":"done",text:fmt(d)+(i?"":" (first)")}));d=adv(d,cad.value,k,anchor)}
    out.innerHTML="";out.appendChild(el("div",{style:"font-size:13.5px"},[el("b",{text:"The next six tickets. "}),"A monthly series set on the 31st lands on the 30th or 28th in a short month and returns to the 31st after. A runner that was down raises the ticket once and moves on, never once per missed period."]));out.appendChild(ul)}
  [f,cad,n].forEach(function(i){i.addEventListener("input",go);i.addEventListener("change",go)});go()};

/* warranty */
W.warranty=function(w){var d=$(".ends",w),out=$(".out",w);function go(){var p=(d.value||"").split("-");if(p.length<3){out.textContent="Pick the date the warranty ends.";return}
  var e=new Date(Number(p[0]),Number(p[1])-1,Number(p[2])),t=new Date();t.setHours(0,0,0,0);var days=Math.round((e-t)/864e5);out.innerHTML="";
  var s=days<0?["Expired","red",(-days)+" days ago"]:days<=90?["Expiring","amber","in "+days+" days"]:["Covered","green",days+" days left"];
  out.appendChild(el("div",{},[el("span",{"class":"st "+s[1],text:s[0]})," ",s[2]+". The Configurations tiles count machines whose warranty has ended and whose warranty ends within 90 days."]))}d.addEventListener("input",go);go()};

/* booking conflicts */
W.conflict=function(w){var s=$(".s",w),e=$(".e",w),al=$(".allow",w),out=$(".out",w),BK=[[540,600,"visit","PMC-000012 at the Laboratory"],[780,1020,"off","time off (afternoon leave)"]];
  function mins(v){var p=(v||"").split(":");return Number(p[0])*60+Number(p[1])}
  function go(){var a=mins(s.value),b=mins(e.value);out.className="w-out out";if(!(b>a)){out.className="w-out out err";out.textContent="The end is before the start.";return}
    var hit=BK.filter(function(k){return a<k[1]&&b>k[0]});var off=hit.filter(function(k){return k[2]==="off"})[0],vis=hit.filter(function(k){return k[2]==="visit"})[0];
    if(off){out.className="w-out out err";out.textContent="Refused: carol has "+off[3]+" then. Time off is never overridden: a person on leave is not dispatched.";return}
    if(vis&&!al.checked){out.className="w-out out err";out.textContent="Refused: it overlaps carol's visit to "+vis[3]+" (09:00–10:00). Tick Allow a double booking to book it anyway.";return}
    out.className="w-out out ok";out.textContent=vis?"Booked, and recorded as an allowed double booking alongside "+vis[3]+".":"Booked. carol gets an email if the board sends owner emails, and acknowledges it on the ticket."}
  [s,e,al].forEach(function(i){i.addEventListener("input",go);i.addEventListener("change",go)});go()};

/* in/out word */
W.inout=function(w){var st=$(".state",w),note=$(".note",w),back=$(".back",w),out=$(".out",w),S={IN:"In",OUT:"Out",ON_SITE:"On site",REMOTE:"Working remotely",LEAVE:"On leave"};
  function go(){var today=new Date(),td=today.toISOString().slice(0,10),x=S[st.value],b=(back.value||"").replace("T"," ");
    if(b)x+=" until "+(b.slice(0,10)===td?b.slice(11,16):b.slice(0,16));if(note.value.trim())x+=": "+note.value.trim().replace(/\s+/g," ").slice(0,200);
    out.innerHTML="";out.appendChild(el("div",{},["Under your name on Schedule: ",el("b",{text:x})]))}[st,note,back].forEach(function(i){i.addEventListener("input",go);i.addEventListener("change",go)});go()};

/* knowledge visibility */
W.kbvis=function(w){var a=$(".aud",w),s=$(".stat",w),b=$(".brd",w),f=$(".file",w),out=$(".out",w);
  function go(){var desk=s.value!=="RETIRED"||"filter",req=a.value==="REQUESTER"&&s.value==="PUBLISHED"&&b.value==="";
    var t=el("table",{"class":"wt"});t.appendChild(el("tr",{},[el("th",{text:""}),el("th",{text:"The desk"}),el("th",{text:"A requester on Help"})]));
    function cell(ok,why){return el("td",{"class":ok?"can":"cannot",text:(ok?"Sees it":"Does not")+(why?" · "+why:"")})}
    t.appendChild(el("tr",{},[el("td",{text:"The article"}),cell(true,s.value==="RETIRED"?"under the Retired filter":"in Knowledge"),cell(req,req?"":a.value!=="REQUESTER"?"desk-only article":s.value!=="PUBLISHED"?"not published":"a board's own article")]));
    var fd=f.value!=="WITHHELD",fr=req&&f.value==="CLEARED";t.appendChild(el("tr",{},[el("td",{text:"Its picture"}),cell(fd,f.value==="PENDING"?"while it waits for review":""),cell(fr,f.value==="PENDING"?"until it is cleared":f.value==="WITHHELD"?"withheld from everyone":"")]));
    out.innerHTML="";out.appendChild(t)}[a,s,b,f].forEach(function(i){i.addEventListener("change",go)});go()};

/* markdown preview */
W.md=function(w){var ta=$("textarea",w),out=$(".mdprev",w);function inl(t){return esc(t).replace(/\*\*(.+?)\*\*/g,"<b>$1</b>").replace(/`(.+?)`/g,"<code>$1</code>").replace(/\[(.+?)\]\((https?:[^)]+)\)/g,"<a href=\"$2\" target=_blank rel=noopener>$1</a>").replace(/!\[(.+?)\]\(file:(\d+)\)/g,"<span class=st>picture $2: $1</span>")}
  function go(){var h="",inList=false;ta.value.split("\n").forEach(function(l){var m;if((m=l.match(/^(#{1,3})\s+(.*)/))){if(inList){h+="</ul>";inList=false}h+="<h3>"+inl(m[2])+"</h3>"}else if((m=l.match(/^\s*[-*]\s+(.*)/))){if(!inList){h+="<ul>";inList=true}h+="<li>"+inl(m[1])+"</li>"}else if(l.trim()){if(inList){h+="</ul>";inList=false}h+="<p>"+inl(l)+"</p>"}});if(inList)h+="</ul>";out.innerHTML=h||"<span style='color:var(--text-3)'>The article appears here.</span>"}
  ta.addEventListener("input",go);go()};

/* project budget */
W.budget=function(w){var b=$(".bud",w),a=$(".act",w),out=$(".out",w);function go(){var bv=Number(b.value||0),av=Number(a.value||0),p=bv?Math.round(100*av/bv):0;out.innerHTML="";
  out.appendChild(el("div",{},[el("span",{"class":"st "+(p>100?"red":p>=80?"amber":"green"),text:av.toFixed(2)+" of "+bv.toFixed(2)+" h · "+p+"%"})," "+(p>100?"Over budget: the actual hours come from the linked tickets' time entries.":"Actual hours come from the time entries on the project's tickets; nobody types them twice.")]));
  out.appendChild(el("div",{"class":"bar"+(p>100?" over":"")},[el("i",{style:"width:"+Math.min(p,100)+"%"})]))}[b,a].forEach(function(i){i.addEventListener("input",go)});go()};

/* portal status wording */
W.portal=function(w){var sel=$("select",w),out=$(".out",w);function go(){var o=sel.options[sel.selectedIndex];out.innerHTML="";out.appendChild(el("div",{},["On PMC Requests the requester reads: ",el("b",{text:"“"+o.dataset.p+"”"})]))}sel.addEventListener("change",go);go()};

/* quiz */
W.quiz=function(w){var Q=DATA.quiz||[],score=0,answered=0,sc=el("div",{"class":"score",text:"Score: 0 of "+Q.length});
  Q.forEach(function(q,i){var d=el("div",{"class":"qq"},[el("b",{text:(i+1)+". "+q[0]}),el("div",{"class":"opts"}),el("div",{"class":"why",text:q[3]})]);
    q[1].forEach(function(o,j){$(".opts",d).appendChild(el("button",{"class":"opt",text:o,onclick:function(e){if(d.classList.contains("answered"))return;d.classList.add("answered");answered++;$$(".opt",d)[q[2]].classList.add("right");if(j===q[2])score++;else e.target.classList.add("wrong");
      sc.textContent="Score: "+score+" of "+Q.length+(answered===Q.length?(score===Q.length?". Every one right.":". Read the explanations and try the section again."):"")}}))});w.appendChild(d)});w.appendChild(sc)};

$$("[data-w]").forEach(function(w){var f=W[w.dataset.w];if(f)try{f(w)}catch(e){console.error("widget "+w.dataset.w,e)}});
apply();
if(location.hash){var h=document.getElementById(location.hash.slice(1));if(h&&h.hidden){role="all";apply()}}
})();
