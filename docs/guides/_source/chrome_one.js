/* ================= one file: a front page and every guide ================= */
var views=$$(".guide"),front=$("#front"),toc=$("#toc"),cur=null,sections=[],links=[],q="",role=store("pmc-guide-role")||"all";
var GUIDES=DATA.guides||[];
function gdone(slug){try{return JSON.parse(store("pmc-guide-done-"+slug)||"{}")||{}}catch(e){return {}}}
function loadImages(root){$$("img[data-img]",root).forEach(function(i){if(!i.getAttribute("src")){var u=(DATA.images||{})[i.dataset.img];if(u)i.src=u}})}
function secList(v){return $$("section.s",v)}

function paintDone(){
  if(!cur){var all=0,read=0;views.forEach(function(v){var d=gdone(v.dataset.guide),ss=secList(v);all+=ss.length;read+=ss.filter(function(s){return d[s.id]}).length});
    $("#progText").textContent=read+" of "+all+" sections read, in every guide";$("#progBar").style.width=(all?Math.round(100*read/all):0)+"%";
    $$(".gcard").forEach(function(c){var v=$('.guide[data-guide="'+c.dataset.slug+'"]'),d=gdone(c.dataset.slug),ss=secList(v),n=ss.filter(function(s){return d[s.id]}).length;
      $(".gprog i",c).style.width=(ss.length?Math.round(100*n/ss.length):0)+"%";$(".gcount",c).textContent=n?n+" of "+ss.length+" read":ss.length+" sections"});return}
  var d=gdone(cur.dataset.guide),vis=sections.filter(function(s){return !s.hidden}),n=vis.filter(function(s){return d[s.id]}).length;
  $("#progText").textContent=n+" of "+vis.length+" sections read";$("#progBar").style.width=(vis.length?Math.round(100*n/vis.length):0)+"%";
  links.forEach(function(a){a.classList.toggle("done",!!d[a.dataset.id])});
  sections.forEach(function(s){var b=$(".done-btn",s);if(b){b.setAttribute("aria-pressed",String(!!d[s.id]));b.lastChild.textContent=d[s.id]?"Read":"Mark as read"}});
}
views.forEach(function(v){secList(v).forEach(function(s){var b=$(".done-btn",s);if(b)b.addEventListener("click",function(){var d=gdone(v.dataset.guide);d[s.id]=!d[s.id];store("pmc-guide-done-"+v.dataset.guide,JSON.stringify(d));paintDone()})})});

function buildToc(){
  toc.innerHTML="";
  if(!cur){toc.appendChild(el("div",{"class":"toc__group",text:"The guides"}));
    GUIDES.forEach(function(g){toc.appendChild(el("a",{href:"#/"+g.slug},[el("span",{text:g.title})]))});links=[];return}
  toc.appendChild(el("a",{"class":"toc__back",href:"#/"},["← All guides"]));
  var group="";sections.forEach(function(s){
    if(s.dataset.group!==group){group=s.dataset.group;toc.appendChild(el("div",{"class":"toc__group","data-group":group,text:group}))}
    toc.appendChild(el("a",{href:"#/"+cur.dataset.guide+"/"+s.id.split("--")[1],"data-id":s.id},[el("span",{text:s.dataset.title}),el("i",{"class":"tick"})]))});
  links=$$("a[data-id]",toc);
  var i=GUIDES.map(function(g){return g.slug}).indexOf(cur.dataset.guide),nx=GUIDES[i+1];
  if(nx)toc.appendChild(el("a",{"class":"toc__back",href:"#/"+nx.slug,style:"margin-top:14px"},["Next guide: "+nx.title+" →"]));
}
var io="IntersectionObserver" in window?new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting)links.forEach(function(a){a.classList.toggle("on",a.dataset.id===e.target.id)})})},{rootMargin:"-30% 0px -60% 0px"}):null;
if(io)views.forEach(function(v){secList(v).forEach(function(s){io.observe(s)})});

function route(){
  var m=location.hash.match(/^#\/([A-Za-z_]+)(?:\/([\w-]+))?/),slug=m&&m[1],sec=m&&m[2],v=slug&&$('.guide[data-guide="'+slug+'"]');
  var was=cur;cur=v||null;
  views.forEach(function(x){x.hidden=x!==cur});front.hidden=!!cur;
  sections=cur?secList(cur):[];
  $("#railTitle").textContent=cur?cur.dataset.title:"Dada PSA guides";$("#railSub").textContent=cur?cur.dataset.sub:"Staff guides · September 2026";
  document.title=(cur?cur.dataset.title+" · ":"")+"Dada PSA guides · PMC";
  $("#q").placeholder=cur?cur.dataset.search:"Search every guide: invoice, page, timesheet…";
  $(".roles").style.display=cur?"none":"";
  loadImages(cur||front);buildToc();q=$("#q").value.trim();apply();
  var target=sec&&cur&&document.getElementById(slug+"--"+sec);
  if(target){target.hidden=false;target.scrollIntoView({behavior:"instant",block:"start"});
    var imgs=$$("img[src]",cur).filter(function(i){return !i.complete});
    if(imgs.length)Promise.all(imgs.map(function(i){return new Promise(function(r){i.addEventListener("load",r,{once:true});i.addEventListener("error",r,{once:true})})})).then(function(){target.scrollIntoView({behavior:"instant",block:"start"})})}
  else if(was!==cur)scrollTo({top:0,behavior:"instant"});
  menu(false);
}

function apply(){
  var words=q.toLowerCase().split(/\s+/).filter(Boolean);
  $$(".gcard").forEach(function(c){c.hidden=!(role==="all"||(" "+c.dataset.roles+" ").indexOf(" "+role+" ")>=0)});
  $$(".ggroup").forEach(function(g){g.hidden=!$$(".gcard",g).some(function(c){return !c.hidden})});
  $$("[data-role]").forEach(function(b){b.setAttribute("aria-pressed",String(b.dataset.role===role))});
  var res=$("#results");
  if(!cur){res.innerHTML="";$("#qn").textContent="";$("#fronthome").hidden=!!words.length;if(!words.length){mark([]);paintDone();return}
    var hits=[];views.forEach(function(v){secList(v).forEach(function(s){var t=(s.dataset.text||(s.dataset.text=s.textContent.toLowerCase()));if(words.every(function(w){return t.indexOf(w)>=0}))hits.push([v,s])})});
    $("#qn").textContent=hits.length+" found";
    res.appendChild(el("h2",{text:hits.length?"Found in "+hits.length+" section"+(hits.length>1?"s":""):"Nothing matches that. Try a shorter word."}));
    var list=el("div",{"class":"library"});hits.forEach(function(h){list.appendChild(el("a",{href:"#/"+h[0].dataset.guide+"/"+h[1].id.split("--")[1]},[el("b",{text:h[1].dataset.title}),el("span",{text:h[0].dataset.title}),el("em",{text:h[1].dataset.group})]))});
    res.appendChild(list);paintDone();return}
  var shown=0;sections.forEach(function(s){var t=(s.dataset.text||(s.dataset.text=s.textContent.toLowerCase()));s.hidden=!words.every(function(w){return t.indexOf(w)>=0});if(!s.hidden)shown++});
  links.forEach(function(a){a.hidden=document.getElementById(a.dataset.id).hidden});
  $$(".toc__group",toc).forEach(function(g){if(!g.dataset.group)return;g.style.display=sections.some(function(s){return s.dataset.group===g.dataset.group&&!s.hidden})?"":"none"});
  $("#empty").style.display=shown?"none":"block";$("#qn").textContent=words.length?shown+" found":"";
  mark(words);paintDone();
}
function mark(words){
  $$("mark.hl").forEach(function(m){var p=m.parentNode;p.replaceChild(document.createTextNode(m.textContent),m);p.normalize()});
  if(!words.length||!cur)return;
  var re=new RegExp("("+words.map(function(w){return w.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")}).join("|")+")","gi");
  sections.filter(function(s){return !s.hidden}).forEach(function(s){
    var w=document.createTreeWalker(s,NodeFilter.SHOW_TEXT,{acceptNode:function(n){return n.parentNode.closest("script,style,button,select,option,textarea,.tour__txt,.widget")?NodeFilter.FILTER_REJECT:(re.test(n.nodeValue)?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_SKIP)}}),list=[],n;
    while((n=w.nextNode()))list.push(n);
    list.forEach(function(t){re.lastIndex=0;var sp=document.createElement("span");sp.innerHTML=esc(t.nodeValue).replace(re,"<mark class=hl>$1</mark>");while(sp.firstChild)t.parentNode.insertBefore(sp.firstChild,t);t.parentNode.removeChild(t)});
  });
}
$$("[data-role]").forEach(function(b){b.addEventListener("click",function(){role=b.dataset.role;store("pmc-guide-role",role);apply()})});
var tq;$("#q").addEventListener("input",function(e){clearTimeout(tq);tq=setTimeout(function(){q=e.target.value.trim();apply()},160)});
var rail=$("#rail"),scrim=$("#scrim");function menu(o){rail.classList.toggle("open",o);scrim.classList.toggle("show",o)}
$("#menuBtn").addEventListener("click",function(){menu(!rail.classList.contains("open"))});scrim.addEventListener("click",function(){menu(false)});
$("#themeBtn").addEventListener("click",function(){var c=document.documentElement.dataset.theme||(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"),nx=c==="dark"?"light":"dark";document.documentElement.dataset.theme=nx;store("pmc-guide-theme",nx)});
$("#printBtn").addEventListener("click",function(){window.print()});
var tt=$("#totop");window.addEventListener("scroll",function(){tt.classList.toggle("show",scrollY>900)},{passive:true});tt.addEventListener("click",function(){scrollTo(0,0)});
window.addEventListener("hashchange",function(){$("#q").value="";q="";route()});

/* lightbox */
var lb=$("#lb");
document.addEventListener("click",function(e){var sh=e.target.closest(".shot");if(!sh||sh.closest(".tour")||e.target.closest("button"))return;
  var img=$("img",sh),fig=sh.closest("figure"),cap=fig&&$("figcaption",fig);$("#lbImg").src=img.src;$("#lbImg").alt=img.alt;$("#lbCap").textContent=cap?cap.textContent:img.alt;
  if(lb.showModal)lb.showModal();else window.open(img.src)});
$("#lbClose").addEventListener("click",function(){lb.close()});lb.addEventListener("click",function(e){if(e.target===lb)lb.close()});

/* hotspot tours */
$$(".tour").forEach(function(tour){
  var key=tour.dataset.tour,spots=(DATA.spots||{})[key]||[],txt=(DATA.tours||{})[key]||[],shot=$(".shot",tour),cur2=0,btns=[];
  spots.forEach(function(sp,i){var b=el("button",{"class":"spot","aria-label":"Point "+sp.n+": "+((txt[i]||[""])[0]),text:String(sp.n)});b.style.left=sp.x+"%";b.style.top=sp.y+"%";b.addEventListener("click",function(){show(i)});shot.appendChild(b);btns.push(b)});
  function show(i){cur2=(i+btns.length)%btns.length;btns.forEach(function(b,j){b.classList.toggle("on",j===cur2)});$(".tour__n",tour).textContent=cur2+1;var t=txt[cur2]||["",""];var box=$(".tour__txt",tour);box.innerHTML="";box.appendChild(el("b",{text:t[0]}));box.appendChild(el("span",{text:t[1]}))}
  $$(".tour__nav button",tour).forEach(function(b){b.addEventListener("click",function(){show(cur2+Number(b.dataset.d))})});
  if(btns.length)show(0);
});

