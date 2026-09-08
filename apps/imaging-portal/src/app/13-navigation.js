/* ---- navigation --------------------------------------------------------- */
const TITLES = { worklist:['Worklist','studies held in the imaging archive'], devices:['Devices','imaging equipment that sends to this archive'],
  activity:['Activity','what has arrived and what is running'], system:['System','what this platform is made of'] };
function go(view) {
  state.view = view;
  $$('.nav__item').forEach(b => b.setAttribute('aria-current', b.dataset.view === view ? 'page' : 'false'));
  $$('.view').forEach(v => v.classList.toggle('is-active', v.id === 'view-' + view));
  $('#viewTitle').textContent = TITLES[view][0];
  $('#viewSub').textContent = TITLES[view][1];
  $('#toolbar').hidden = view !== 'worklist';
  if (view === 'devices') loadDevices();
  if (view === 'activity') loadActivity();
  if (view === 'system') loadSystem();
}
$$('.nav__item').forEach(b => b.onclick = () => go(b.dataset.view));
function setScope(sc) {
  state.scope = sc; state.scopeTouched = true; store.set('scope', sc);
  $$('#scopeChips .chip').forEach(c => c.setAttribute('aria-pressed', String(c.dataset.scope === sc)));
  loadStudies();
}
$$('#scopeChips .chip').forEach(c => c.onclick = () => setScope(c.dataset.scope));
$('#viewCards').onclick = () => setLayout('cards');
$('#viewTable').onclick = () => setLayout('table');
function setLayout(l) {
  state.layout = l; store.set('layout', l);
  $('#viewCards').setAttribute('aria-pressed', String(l === 'cards'));
  $('#viewTable').setAttribute('aria-pressed', String(l === 'table'));
  render();
}
$('#refreshBtn').onclick = () => { if (state.view === 'worklist') loadStudies(); else go(state.view); };
$('#kbdBtn').onclick = () => $('#kbdDlg').showModal();

/* search box */
let typing;
$('#q').addEventListener('input', e => {
  state.q = e.target.value;
  clearTimeout(typing);
  typing = setTimeout(() => {
    if (state.q.trim() && state.scope !== 'all' && !state.scopeTouched) {
      state.scope = 'all';
      $$('#scopeChips .chip').forEach(c => c.setAttribute('aria-pressed', String(c.dataset.scope === 'all')));
      toast('Searching the whole archive');
    }
    loadStudies();
  }, 260);
});

/* theme */
function setTheme(t) {
  document.documentElement.dataset.theme = t; store.set('theme', t);
  $('#themeBtn').innerHTML = `<svg><use href="#i-${t === 'dark' ? 'sun' : 'moon'}"/></svg>`;
}
$('#themeBtn').onclick = () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');

/* keyboard */
function markCursor() {
  $$('#results .card, #results tbody tr').forEach((el, i) => el.classList.toggle('is-cursor', i === state.cursor));
  const el = $$('#results .card, #results tbody tr')[state.cursor];
  el?.scrollIntoView({ block: 'nearest' });
}
let gKey = false;
document.addEventListener('keydown', e => {
  const typingNow = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName);
  if (e.key === '/' && !typingNow) { e.preventDefault(); $('#q').focus(); $('#q').select(); return; }
  if (typingNow) { if (e.key === 'Escape') e.target.blur(); return; }
  if (sheet.open) {
    if (e.key === 'v') { e.preventDefault(); $('#sheetFoot a')?.click(); }
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); openStudy(Math.min(openIndex + 1, state.studies.length - 1)); }
    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); openStudy(Math.max(openIndex - 1, 0)); }
    return;
  }
  if (gKey) { gKey = false; const map = { '1':'worklist','2':'devices','3':'activity','4':'system' }; if (map[e.key]) { go(map[e.key]); return; } }
  if (e.key === 'g') { gKey = true; setTimeout(() => gKey = false, 900); return; }
  if (e.key === 'r') { e.preventDefault(); $('#refreshBtn').click(); }
  if (e.key === 't') setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
  if (e.key === '?') $('#kbdDlg').showModal();
  if (state.view !== 'worklist' || !state.studies.length) return;
  if (e.key === 'j' || e.key === 'ArrowDown') { e.preventDefault(); state.cursor = Math.min(state.cursor + 1, state.studies.length - 1); markCursor(); }
  if (e.key === 'k' || e.key === 'ArrowUp')   { e.preventDefault(); state.cursor = Math.max(state.cursor - 1, 0); markCursor(); }
  if (e.key === 'Enter' && state.cursor >= 0) { e.preventDefault(); openStudy(state.cursor); }
  if (e.key === 'v' && state.cursor >= 0) { const s = state.studies[state.cursor]; const l = viewerLinks(s)[0]; if (l) window.open(l.href, '_blank', 'noopener'); }
  if (e.key === 'd' && state.cursor >= 0) location.href = API.url(`studies/${state.studies[state.cursor].id}/archive`);
});

