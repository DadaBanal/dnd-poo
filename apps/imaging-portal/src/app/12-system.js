/* ---- system ------------------------------------------------------------- */
async function loadSystem() {
  const s = state.system || {};
  const idx = s.DatabaseBackendPlugin || 'built-in SQLite';
  // Orthanc reports the index as the full path of the DLL providing it. A path
  // has nowhere to wrap, so it broke mid-filename on the live server. Show the
  // name and keep the path on hover, where it is still one copy away.
  const idxName = idx.split(/[\\/]/).pop() || idx;
  $('#sysKv').innerHTML = `
    <dt>Portal</dt><dd class="mono">${esc(PORTAL_BUILD)}</dd>
    <dt>Server</dt><dd>${esc(s.Name || '—')}</dd>
    <dt>Orthanc</dt><dd>${esc(s.Version || '—')} <span style="color:var(--text-3)">· REST API v${esc(s.ApiVersion ?? '—')}</span></dd>
    <dt>Index</dt><dd title="${esc(idx)}">${esc(idxName)} ${/odbc/i.test(idx) ? '<span class="badge badge--orange" style="margin-left:6px">no server-side ordering</span>' : ''}</dd>
    <dt>Storage</dt><dd>${esc(s.StorageAreaPlugin || 'local filesystem')}</dd>
    <dt>AE title</dt><dd class="mono">${esc(s.DicomAet || '—')} · port ${esc(s.DicomPort ?? '—')}</dd>
    <dt>Address</dt><dd class="mono">${esc(location.origin)}</dd>`;
  if (/odbc/i.test(idx)) {
    $('#sysKv').insertAdjacentHTML('afterend', `<div class="banner info" style="margin-top:14px">
      <svg><use href="#i-info"/></svg><div>This index cannot sort results inside the database, which is why the stock
      Orthanc screen returns an error on its landing page. This page asks only for what the index can answer and does the
      sorting in your browser, so it works today — and it will keep working unchanged after the index moves to
      PostgreSQL.</div></div>`);
  }
  const plugs = await Promise.all(state.plugins.map(id => API.get(`plugins/${id}`).catch(() => ({ ID: id }))));
  $('#pluginList').innerHTML = plugs.map(p => `
    <div class="row"><span class="dot"></span>
      <div class="row__main"><div class="row__t">${esc(p.ID)}</div><div class="row__s">${esc(p.Description || '')}</div></div>
      <span class="badge badge--soft">${esc(p.Version || '—')}</span></div>`).join('');
  const newest = state.studies[0];
  $('#viewerList').innerHTML = (state.viewers.length ? state.viewers.map(v => `
    <div class="row"><span class="dot"></span>
      <div class="row__main"><div class="row__t">${esc(v.label)}</div><div class="row__s">${esc(v.tpl)}</div></div>
      ${newest ? `<a class="btn btn--sm" target="_blank" rel="noopener"
        href="${esc(API.url(v.tpl.replace('{orthancId}', newest.id).replace('{studyUid}', encodeURIComponent(newest.uid))))}">
        <svg><use href="#i-open"/></svg>Test</a>` : ''}
    </div>`).join('') : '<p style="color:var(--text-3)">No viewer plugin is loaded on this server.</p>')
    + `<div class="banner info" style="margin-top:12px"><svg><use href="#i-info"/></svg>
       <div>Viewers are detected from the server's own plugin list — this page never offers a viewer that is not installed.
       “Test” opens the newest study so you can confirm the hand-off in one click.</div></div>`;
  const dw = state.plugins.includes('dicom-web');
  $('#ifaceList').innerHTML = `
    <div class="kv">
      <dt>DICOMweb (QIDO/WADO/STOW)</dt><dd class="mono">${dw ? esc(API.url('dicom-web/')) : 'not installed'}</dd>
      <dt>REST API</dt><dd class="mono">${esc(API.url(''))}</dd>
      <dt>DICOM C-STORE</dt><dd class="mono">${esc(s.DicomAet || '—')}@${esc(location.hostname)}:${esc(s.DicomPort ?? '—')}</dd>
    </div>
    <div class="banner info" style="margin-top:12px"><svg><use href="#i-info"/></svg>
      <div>Any viewer that speaks DICOMweb — OHIF, Weasis, a vendor workstation, a surgical or cathlab display — points at
      the address above and reads the same studies. Nothing in this page is a private interface.</div></div>`;
}

