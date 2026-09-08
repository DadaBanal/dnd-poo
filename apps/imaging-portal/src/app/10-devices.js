/* ---- devices ------------------------------------------------------------ */
/** Orthanc answers /modalities with a list of names, and /modalities?expand with an
    object keyed by name — but not every build honours ?expand, so accept both. */
async function readModalities() {
  const byName = async names => Object.fromEntries(await Promise.all(
    names.map(async n => [n, await API.get(`modalities/${encodeURIComponent(n)}`).catch(() => ({}))])));
  let raw;
  try { raw = await API.get('modalities?expand'); }
  catch { raw = await API.get('modalities'); }
  if (Array.isArray(raw)) return byName(raw);
  if (raw && typeof raw === 'object') {
    const vals = Object.values(raw);
    if (vals.length && vals.every(v => typeof v === 'string')) return byName(vals);
    return raw;
  }
  return {};
}
async function loadDevices() {
  const wrap = $('#modalityList'); wrap.innerHTML = '<div class="skel" style="height:120px"></div>';
  let mods = {};
  try { mods = await readModalities(); }
  catch (e) { wrap.innerHTML = `<p style="color:var(--text-3)">Could not read the device list (${esc(e.status || e.message)}).</p>`; return; }
  const entries = Object.entries(mods);
  $('#devStats').innerHTML = `
    <div class="stat"><b>${entries.length}</b><span>Configured devices</span></div>
    <div class="stat g"><b id="devUp">—</b><span>Answering</span></div>
    <div class="stat o"><b>${esc(state.system?.DicomAet || '—')}</b><span>Our AE title</span></div>
    <div class="stat k"><b>${esc(state.system?.DicomPort ?? '—')}</b><span>DICOM port</span></div>`;
  wrap.innerHTML = entries.map(([id, m]) => `
    <div class="row" data-mod="${esc(id)}">
      <span class="dot idle"></span>
      <div class="row__main">
        <div class="row__t">${esc(m.AET || id)}</div>
        <div class="row__s">${esc(m.Host || '?')}:${esc(m.Port ?? '?')} · configured as “${esc(id)}”</div>
      </div>
      <span class="badge badge--grey js-status">not tested</span>
      <button class="btn btn--sm js-echo">Test</button>
    </div>`).join('') || '<p style="color:var(--text-3)">No imaging devices are configured yet.</p>';
  $$('#modalityList .js-echo').forEach(b => b.onclick = () => echo(b.closest('.row')));
  entries.forEach(([id]) => echo($(`#modalityList .row[data-mod="${CSS.escape(id)}"]`), true));
}
async function echo(row, quiet) {
  if (!row) return;
  const id = row.dataset.mod, badge = row.querySelector('.js-status'), dot = row.querySelector('.dot'), btn = row.querySelector('.js-echo');
  badge.className = 'badge badge--grey js-status'; badge.textContent = 'testing…'; dot.className = 'dot idle'; btn.disabled = true;
  const t0 = performance.now();
  try {
    await API.post(`modalities/${id}/echo`, {});
    const ms = Math.round(performance.now() - t0);
    badge.className = 'badge badge--green js-status'; badge.textContent = `answers · ${ms} ms`; dot.className = 'dot';
    if (!quiet) toast(`${id} answered in ${ms} ms`, 'ok');
  } catch (e) {
    badge.className = 'badge badge--orange js-status'; badge.textContent = 'no answer'; dot.className = 'dot warn';
    if (!quiet) toast(`${id} did not answer (${e.status || e.message})`, 'warn');
  } finally {
    btn.disabled = false;
    const up = $$('#modalityList .dot:not(.idle):not(.warn):not(.bad)').length;
    if ($('#devUp')) $('#devUp').textContent = up;
  }
}

