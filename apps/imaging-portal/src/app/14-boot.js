/* ---- boot --------------------------------------------------------------- */
const VIEWER_META = {
  ohif:               { label: 'Open in OHIF',            key: 'ohif',   rank: 1 },
  'stone-webviewer':  { label: 'Open in Stone viewer',    key: 'stone',  rank: 2 },
  'osimis-web-viewer':{ label: 'Open in Osimis viewer',   key: 'osimis', rank: 3 },
  'orthanc-explorer-2':{ label: 'Open in Orthanc Explorer', key: 'explorer', rank: 9 }
};
function goDemo() {
  state.demo = true; API = Demo; Live.base = location.href;
  Demo.url = p => String(p);
  state.system = { Name: 'PMC-ORTHANC01 (sample)', Version: '1.13.0', ApiVersion: 21, DatabaseBackendPlugin: 'odbc-index',
    DicomAet: 'PMCORTHANC', DicomPort: 4242 };
  state.plugins = ['dicom-web','stone-webviewer','ohif','orthanc-explorer-2','odbc-index','gdcm','transfers'];
  resolveViewers();
  $('#railEnv').textContent = 'Sample data';
  $('#healthDot').className = 'dot warn'; $('#healthText').textContent = 'sample dataset';
}
function resolveViewers() {
  state.viewers = state.plugins
    .filter(id => VIEWER_META[id] && CFG.viewers[VIEWER_META[id].key])
    .map(id => ({ id, label: VIEWER_META[id].label, rank: VIEWER_META[id].rank, tpl: CFG.viewers[VIEWER_META[id].key] }))
    .sort((a, b) => a.rank - b.rank);
}
async function boot() {
  setTheme(store.get('theme', matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
  $$('#scopeChips .chip').forEach(c => c.setAttribute('aria-pressed', String(c.dataset.scope === state.scope)));
  setLayout(state.layout);
  // optional site config written by the installer
  try { const r = await fetch('pmc-portal.config.json', { cache: 'no-store' });
    if (r.ok) { const j = await r.json(); CFG = { ...CFG, ...j, viewers: { ...CFG.viewers, ...(j.viewers || {}) },
      features: { ...CFG.features, ...(j.features || {}) } }; } } catch {}
  const params = new URLSearchParams(location.search);
  Live.base = new URL(params.get('api') || CFG.apiBase, location.href).href;
  $('#railEnv').textContent = CFG.environment;
  if (params.get('demo') === '1' || location.protocol === 'file:' || window.PMC_DEMO === true) { goDemo(); }
  else {
    try {
      state.system = await Live.get('system', { timeout: 8000 });
      state.plugins = await Live.get('plugins').catch(() => []);
      resolveViewers();
      $('#healthDot').className = 'dot';
      $('#healthText').textContent = `${state.system.Name || 'archive'} · ${state.system.Version}`;
    } catch (e) {
      console.warn('[PMC] no archive on', Live.base, e);
      goDemo();
    }
  }
  const modList = ['XA','CT','CR','DX','US','MR','MG','NM'];
  $('#modChips').innerHTML = modList.map(m => `<button class="chip chip--mod" data-mod="${m}" aria-pressed="false">${m}</button>`).join('');
  $$('#modChips .chip').forEach(c => c.onclick = () => {
    state.mod = state.mod === c.dataset.mod ? null : c.dataset.mod;
    $$('#modChips .chip').forEach(x => x.setAttribute('aria-pressed', String(x.dataset.mod === state.mod)));
    loadStudies();
  });
  await loadStudies();
  document.body.dataset.ready = '1';
}
boot();
