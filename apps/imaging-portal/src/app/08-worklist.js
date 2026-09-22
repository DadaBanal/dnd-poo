/* ---- rendering the worklist --------------------------------------------- */
function paintSkeletons() {
  $('#metaLine').innerHTML = '<span class="skel" style="height:14px;width:190px;display:inline-block"></span>';
  $('#results').innerHTML = `<div class="grid">${'<div class="skel skel-card"></div>'.repeat(8)}</div>`;
}
function modBadges(mods) {
  if (!mods.length) return '<span class="badge badge--grey">—</span>';
  return mods.slice(0, 3).map(m => `<span class="badge badge--mod">${esc(m)}</span>`).join('');
}
function render() {
  const n = state.studies.length;
  $('#navCount').textContent = n > 999 ? '999+' : n;
  const scopeLabel = { today:'today', yesterday:'yesterday', '7':'the last 7 days', '30':'the last 30 days', all:'the whole archive' }[state.scope];
  $('#metaLine').innerHTML = n
    ? `<b>${n}</b> ${n === 1 ? 'study' : 'studies'} · ${state.q ? `matching “${esc(state.q)}”` : `from ${scopeLabel}`}
       · <span title="round trip to the archive">${state.took} ms</span>
       ${state.demo ? '<span class="demo-flag">Sample data</span>' : ''}`
    : '';
  if (!n) { renderEmpty(); return; }
  const out = state.layout === 'cards' ? cardsHtml() : tableHtml();
  const paint = () => { $('#results').innerHTML = out; wireResults(); };
  document.startViewTransition ? document.startViewTransition(paint) : paint();
}
function cardsHtml() {
  return `<div class="grid" role="list">${state.studies.map((s, i) => `
    <article class="card" role="listitem" tabindex="0" data-i="${i}" data-id="${esc(s.id)}">
      <div class="thumb" data-study="${esc(s.id)}" data-mod="${esc(s.mod[0] || '')}" data-seed="${i + 1}">
        <div class="thumb__ph">${esc(s.mod[0] || 'DCM')}</div>
        <img alt="" loading="lazy" decoding="async">
        <div class="thumb__badge">${modBadges(s.mod)}</div>
        ${s.nInst ? `<div class="thumb__n">${s.nInst} img</div>` : ''}
      </div>
      <div class="card__body">
        <div class="card__name" title="${esc(s.name)}">${esc(s.name)}</div>
        <div class="card__desc" title="${esc(s.desc)}">${esc(s.desc || 'No study description')}</div>
        <div class="card__foot">
          <span>${esc(when(s.date))}</span><span aria-hidden="true">·</span>
          <span class="id">${esc(s.pid || '—')}</span>
        </div>
      </div>
    </article>`).join('')}</div>`;
}
function th(key, label, extra = '') {
  const on = state.sort.key === key;
  return `<th class="sortable ${extra}" data-sort="${key}" ${on ? `aria-sort="${state.sort.dir === 1 ? 'ascending' : 'descending'}"` : ''}>
    ${label}<span class="arrow">${on ? (state.sort.dir === 1 ? '▲' : '▼') : '▾'}</span></th>`;
}
function tableHtml() {
  return `<div class="tablewrap"><table><thead><tr>
      ${th('name','Patient')}${th('pid','Patient ID')}${th('desc','Study')}${th('mod','Modality')}
      ${th('acc','Accession')}${th('date','Date')}<th class="right">Images</th>
    </tr></thead><tbody>${state.studies.map((s, i) => `
      <tr data-i="${i}" data-id="${esc(s.id)}" tabindex="0">
        <td class="name">${esc(s.name)}${s.sex ? ` <span style="color:var(--text-3);font-weight:400">${esc(s.sex)}${age(s.dob, s.date) ? ' · ' + age(s.dob, s.date) : ''}</span>` : ''}</td>
        <td class="mono">${esc(s.pid || '—')}</td>
        <td>${esc(s.desc || '—')}</td>
        <td>${modBadges(s.mod)}</td>
        <td class="mono">${esc(s.acc || '—')}</td>
        <td>${esc(when(s.date))}</td>
        <td class="right mono">${s.nInst || '—'}</td>
      </tr>`).join('')}</tbody></table></div>`;
}
function wireResults() {
  $$('#results .card, #results tbody tr').forEach(el => {
    el.addEventListener('click', () => openStudy(+el.dataset.i));
    el.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); openStudy(+el.dataset.i); } });
  });
  $$('#results thead th.sortable').forEach(el => el.addEventListener('click', () => {
    const k = el.dataset.sort;
    state.sort = { key: k, dir: state.sort.key === k ? -state.sort.dir : (k === 'date' ? -1 : 1) };
    sortStudies(); render();
  }));
  if (CFG.features.thumbnails) $$('#results .thumb').forEach(t => io.observe(t));
}
function renderEmpty() {
  const scoped = state.scope !== 'all';
  $('#results').innerHTML = `<div class="state">
    <svg><use href="#i-empty"/></svg>
    <h3>Nothing here yet</h3>
    <p>${state.q ? `No study matches <b>${esc(state.q)}</b>${scoped ? ' inside the selected dates' : ''}.`
       : `No studies were ${state.scope === 'today' ? 'acquired today' : 'found for this range'}.`}</p>
    ${scoped ? '<button class="btn btn--primary" id="widen">Search the whole archive</button>' : ''}
  </div>`;
  $('#widen')?.addEventListener('click', () => setScope('all'));
}
function renderError(e) {
  const auth = e instanceof ApiError && (e.status === 401 || e.status === 403);
  $('#metaLine').innerHTML = '';
  $('#results').innerHTML = `<div class="state state--error">
    <svg><use href="#i-alert"/></svg>
    <h3>${auth ? 'Not signed in' : 'The archive did not answer'}</h3>
    <p>${auth ? 'Your session with the imaging archive has expired. Reload the page and sign in again.'
      : `<span class="mono">${esc(e instanceof ApiError ? `HTTP ${e.status} · ${e.path}` : (e.message || e))}</span>`}</p>
    <div style="display:flex;gap:8px;margin-top:12px">
      <button class="btn btn--primary" onclick="location.reload()">Reload</button>
      <button class="btn" id="useDemo">Show sample data</button>
    </div></div>`;
  $('#useDemo')?.addEventListener('click', () => { goDemo(); loadStudies(); });
}
function showBanner(err) {
  const b = $('#banner');
  if (state.demo) {
    b.innerHTML = `<div class="banner"><svg><use href="#i-alert"/></svg>
      <div><b>Sample data.</b> This page could not reach an imaging archive on this address, so it is showing a
      generated dataset — no patient information is involved. Everything you click here behaves exactly as it will
      against PMC-ORTHANC01.</div></div>`;
    return;
  }
  b.innerHTML = err ? `<div class="banner"><svg><use href="#i-alert"/></svg>
    <div><b>Partial result.</b> One of the searches was refused by the archive
    (<span class="mono">HTTP ${esc(err.status || '?')}</span>). The studies below are what did come back.</div></div>` : '';
}

