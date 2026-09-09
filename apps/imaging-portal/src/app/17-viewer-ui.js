/* ===========================================================================
   PMC Viewer — the interface
   Opens over the worklist rather than in a new tab, so a clinician keeps their
   place. Needs no plugin on the server: it speaks Orthanc's own REST API, which
   means it still works on the day a viewer plugin fails to load.
   =========================================================================== */

const V = {
  open: false, study: null, series: [], panes: [], active: 0,
  layout: { r: 1, c: 1 }, tool: 'wl', overlay: true,
  notes: new Map(), selected: null,
  link: { scroll: false, wl: false },
  cine: { on: false, fps: 12, bounce: false, raf: 0, last: 0 },
  priors: [], busy: 0
};

/* W/L presets. The CT numbers are the conventional ones a radiographer at PMC
   already has in their head; for every other modality the file's own window is
   the only defensible default, so that is what is offered. */
const WL_PRESETS = {
  CT: [['Soft tissue', 40, 400], ['Lung', -600, 1500], ['Bone', 300, 1500], ['Brain', 40, 80],
    ['Abdomen', 60, 400], ['Mediastinum', 50, 350], ['Liver', 60, 160], ['Angio', 300, 600]],
  '*': []
};

const vq = s => document.querySelector(s);

/* ------------------------------------------------------------------ panes */

function makePane(i) {
  const el = document.createElement('div');
  el.className = 'pane';
  el.innerHTML = '<canvas></canvas><div class="pane__probe" hidden></div>';
  const canvas = el.querySelector('canvas');
  const pane = { i, el, canvas, serie: null, index: 0, zoom: null, panX: 0, panY: 0,
    rot: 0, flipH: false, flipV: false, invert: false, wc: 0, ww: 1, frame: null,
    fitted: true, draft: null, error: null, imgW: 1, imgH: 1, matrix: new DOMMatrix(),
    token: 0, sharpen: 0, loupe: null };
  el.addEventListener('pointerdown', e => onPointerDown(pane, e));
  el.addEventListener('wheel', e => onWheel(pane, e), { passive: false });
  el.addEventListener('contextmenu', e => e.preventDefault());
  el.addEventListener('dblclick', () => { fitPane(pane); paint(pane); });
  return pane;
}

function setLayoutGrid(r, c) {
  V.layout = { r, c };
  const grid = vq('#vwrGrid');
  grid.style.gridTemplateRows = `repeat(${r}, 1fr)`;
  grid.style.gridTemplateColumns = `repeat(${c}, 1fr)`;
  const want = r * c;
  while (V.panes.length > want) V.panes.pop().el.remove();
  while (V.panes.length < want) { const p = makePane(V.panes.length); V.panes.push(p); grid.append(p.el); }
  V.panes.forEach((p, i) => { p.i = i; });
  if (V.active >= want) V.active = 0;
  // Fill any empty pane with the next series, the way a hanging protocol would.
  V.panes.forEach((p, i) => { if (!p.serie && V.series[i]) assignSeries(p, V.series[i]); });
  $$('#vwrLayouts button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.layout === `${r}x${c}`)));
  V.panes.forEach(p => { p.fitted = true; paint(p); });
  updateFoot();
}

function fitPane(p) { p.fitted = true; p.panX = 0; p.panY = 0; p.zoom = null; }

async function assignSeries(pane, serie) {
  pane.serie = serie;
  pane.index = Math.min(pane.index, serie.frames.length - 1);
  const g = serie.geom;
  pane.wc = g.wc ?? 40; pane.ww = g.ww ?? 400;
  g.wcNow = pane.wc; g.wwNow = pane.ww;
  fitPane(pane);
  await showFrame(pane, pane.index);
  markSeriesList();
}

/** Load and paint one frame. Late answers are dropped, so fast scrolling
    cannot leave an older frame painted over a newer one. */
async function showFrame(pane, index) {
  if (!pane.serie) return;
  const n = pane.serie.frames.length;
  pane.index = Math.max(0, Math.min(n - 1, index));
  const token = ++pane.token;
  V.busy++;
  try {
    const frame = await loadFrame(pane.serie, pane.index);
    if (token !== pane.token) return;
    const f = pane.serie.frames[pane.index];
    pane.frame = frame; pane.error = null; pane.frameKey = `${f.instance}#${f.frame}`;
  } catch (e) {
    if (token !== pane.token) return;
    pane.frame = null; pane.error = `frame unavailable (${e.status || e.message})`;
  } finally { V.busy--; }
  // The pane says where it is, for a screen reader and for anything automating
  // this page -- the position is otherwise only painted into the canvas.
  pane.el.dataset.index = String(pane.index);
  pane.el.dataset.serie = pane.serie.id;
  pane.el.setAttribute('aria-label',
    `Series ${pane.serie.number || '?'}, image ${pane.index + 1} of ${pane.serie.frames.length}`);
  paint(pane);
  updateFoot();
  refreshNotes();
  prefetch(pane);
}

/** Warm the frames on either side, so a scroll does not wait on the network. */
function prefetch(pane) {
  if (!pane.serie) return;
  for (const d of [1, -1, 2, -2, 3, 4]) {
    const i = pane.index + d;
    if (i < 0 || i >= pane.serie.frames.length) continue;
    const f = pane.serie.frames[i];
    if (!FrameCache.has(f.instance, f.frame)) loadFrame(pane.serie, i).catch(() => {});
  }
}

const paint = p => paintPane(p);
const paintAll = () => V.panes.forEach(paint);
const activePane = () => V.panes[V.active] || V.panes[0];

/* ------------------------------------------------------------- interaction */

const TOOL_CURSOR = { pan: 'grab', zoom: 'zoom-in', wl: 'crosshair', stack: 'ns-resize',
  probe: 'crosshair', magnify: 'zoom-in' };

function setTool(t) {
  V.tool = t;
  $$('#vwrTools button[data-tool]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.tool === t)));
  vq('#vwrGrid').style.cursor = TOOL_CURSOR[t] || 'crosshair';
}

const SHAPE_TOOLS = { length: 2, angle: 3, rect: 2, ellipse: 2, arrow: 2 };

function onPointerDown(pane, e) {
  V.active = pane.i;
  paintAll();
  const rect = pane.el.getBoundingClientRect();
  const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
  // Right button is window/level and middle is pan, on every tool — the binding
  // every PACS workstation in this hospital already uses.
  const tool = e.button === 2 ? 'wl' : e.button === 1 ? 'pan' : V.tool;
  e.preventDefault();
  pane.el.setPointerCapture(e.pointerId);

  if (tool === 'probe') { probeAt(pane, sx, sy); }
  if (tool === 'magnify') { pane.loupe = { x: sx, y: sy }; paint(pane); }

  if (SHAPE_TOOLS[tool]) {
    const p = screenToImage(pane, sx, sy);
    if (pane.draft && pane.draft.type === 'angle' && pane.draft.pts.length === 2) {
      pane.draft.pts.push(p);
      notesFor(pane).push(pane.draft); pane.draft = null; paint(pane); refreshNotes(); return;
    }
    pane.draft = { type: tool, pts: [p, p] };
    paint(pane);
  } else if (tool === 'select') {
    V.selected = hitAnnotation(pane, sx, sy); paint(pane);
  }

  const start = { sx, sy, wc: pane.wc, ww: pane.ww, panX: pane.panX, panY: pane.panY,
    zoom: pane.zoom, index: pane.index };

  const move = ev => {
    const dx = ev.clientX - rect.left - start.sx, dy = ev.clientY - rect.top - start.sy;
    if (tool === 'wl') {
      // 1 px of drag = 1 unit of level, 2 of width: the ratio that makes a CT
      // window reachable in one gesture without overshooting a narrow one.
      setWindow(pane, start.wc + dy, Math.max(1, start.ww + dx * 2));
    } else if (tool === 'pan') {
      pane.panX = start.panX + dx; pane.panY = start.panY + dy; pane.fitted = false; paint(pane);
    } else if (tool === 'zoom') {
      pane.zoom = Math.max(0.05, start.zoom * Math.exp(-dy / 180)); pane.fitted = false; paint(pane);
    } else if (tool === 'stack') {
      stepFrame(pane, Math.round(dy / 6) - (pane.index - start.index));
    } else if (tool === 'probe') {
      probeAt(pane, ev.clientX - rect.left, ev.clientY - rect.top);
    } else if (tool === 'magnify') {
      pane.loupe = { x: ev.clientX - rect.left, y: ev.clientY - rect.top }; paint(pane);
    } else if (pane.draft) {
      pane.draft.pts[pane.draft.pts.length - 1] = screenToImage(pane, ev.clientX - rect.left, ev.clientY - rect.top);
      paint(pane);
    }
  };
  const up = () => {
    pane.el.removeEventListener('pointermove', move);
    pane.el.removeEventListener('pointerup', up);
    pane.el.removeEventListener('pointercancel', up);
    if (pane.draft) {
      const need = SHAPE_TOOLS[pane.draft.type];
      const [a, b] = pane.draft.pts;
      if (need === 2) {
        if (Math.hypot(b.x - a.x, b.y - a.y) < 2) pane.draft = null;   // a click, not a measurement
        else { const done = pane.draft; notesFor(pane).push(done); pane.draft = null;
               if (done.type === 'arrow') askLabel(pane, done); }
        paint(pane); refreshNotes();
      }
    }
    if (tool === 'wl' && pane.serie?.mode === 'rendered') reloadForWindow(pane);
    if (pane.loupe) { pane.loupe = null; paint(pane); }
    pane.el.querySelector('.pane__probe').hidden = true;
  };
  pane.el.addEventListener('pointermove', move);
  pane.el.addEventListener('pointerup', up);
  pane.el.addEventListener('pointercancel', up);
}

function probeAt(pane, sx, sy) {
  const box = pane.el.querySelector('.pane__probe');
  const p = screenToImage(pane, sx, sy);
  const v = pixelValue(pane, p.x, p.y);
  box.hidden = false;
  box.style.left = `${sx + 14}px`; box.style.top = `${sy + 14}px`;
  box.textContent = v
    ? `${Math.round(p.x)}, ${Math.round(p.y)}   ${fmt(v.value)} ${v.unit || ''}`.trim()
    : `${Math.round(p.x)}, ${Math.round(p.y)}   no pixel data on this path`;
}

function setWindow(pane, wc, ww) {
  const targets = V.link.wl ? V.panes.filter(p => p.serie) : [pane];
  for (const p of targets) { p.wc = wc; p.ww = ww; if (p.serie) { p.serie.geom.wcNow = Math.round(wc); p.serie.geom.wwNow = Math.round(ww); } }
  targets.forEach(paint);
  updateFoot();
}

/** A pane on the server-rendered path has to ask again for a new window. */
function reloadForWindow(pane) {
  const targets = V.link.wl ? V.panes.filter(p => p.serie?.mode === 'rendered') : [pane];
  for (const p of targets) {
    for (const f of p.serie.frames) FrameCache.map.delete(FrameCache.key(f.instance, f.frame));
    showFrame(p, p.index);
  }
}

function stepFrame(pane, delta) {
  if (!delta || !pane.serie) return;
  showFrame(pane, pane.index + delta);
  if (!V.link.scroll) return;
  // Two series of the same patient rarely start at the same slice, so stepping
  // both by the same count drifts them apart. When both carry a slice position,
  // follow the position instead -- Voyager calls this auto position matching,
  // and without it a side-by-side comparison is only coincidentally aligned.
  const here = framePosition(pane.serie, pane.index);
  for (const p of V.panes) {
    if (p === pane || !p.serie) continue;
    const there = here == null ? null : nearestByPosition(p.serie, here);
    showFrame(p, there == null ? p.index + delta : there);
  }
}

/** Distance along the slice normal, which is what "same level" means in DICOM. */
function framePosition(serie, i) {
  const f = serie.frames[i];
  const pos = dcmList(f?.inst?.MainDicomTags?.ImagePositionPatient);
  const o = serie.geom.orientation;
  if (pos.length !== 3) return null;
  if (!o) return pos[2];
  const n = [o[1] * o[5] - o[2] * o[4], o[2] * o[3] - o[0] * o[5], o[0] * o[4] - o[1] * o[3]];
  return pos[0] * n[0] + pos[1] * n[1] + pos[2] * n[2];
}
function nearestByPosition(serie, target) {
  let best = null, bestD = Infinity;
  for (let i = 0; i < serie.frames.length; i++) {
    const p = framePosition(serie, i);
    if (p == null) continue;
    const d = Math.abs(p - target);
    if (d < bestD) { bestD = d; best = i; }
  }
  return best;
}

function onWheel(pane, e) {
  e.preventDefault();
  V.active = pane.i;
  if (e.ctrlKey || e.metaKey) {                       // pinch-zoom on a trackpad
    pane.zoom = Math.max(0.05, (pane.zoom || 1) * Math.exp(-e.deltaY / 320));
    pane.fitted = false; paint(pane); return;
  }
  stepFrame(pane, e.deltaY > 0 ? 1 : -1);
}

/* -------------------------------------------------------------------- cine */

function cine(on) {
  V.cine.on = on ?? !V.cine.on;
  vq('#vwrCine').setAttribute('aria-pressed', String(V.cine.on));
  cancelAnimationFrame(V.cine.raf);
  if (!V.cine.on) return;
  let dir = 1;
  const tick = t => {
    if (!V.cine.on) return;
    if (t - V.cine.last >= 1000 / V.cine.fps) {
      V.cine.last = t;
      const p = activePane();
      if (p?.serie) {
        let next = p.index + dir;
        if (next >= p.serie.frames.length) { if (V.cine.bounce) { dir = -1; next = p.index - 1; } else next = 0; }
        if (next < 0) { if (V.cine.bounce) { dir = 1; next = 1; } else next = p.serie.frames.length - 1; }
        showFrame(p, next);
      }
    }
    V.cine.raf = requestAnimationFrame(tick);
  };
  V.cine.raf = requestAnimationFrame(tick);
}

/* ------------------------------------------------------------------- chrome */

function markSeriesList() {
  $$('#vwrSeries .vseries').forEach(el => {
    const on = V.panes.some(p => p.serie?.id === el.dataset.serie);
    el.setAttribute('aria-pressed', String(on));
    el.classList.toggle('is-active', activePane()?.serie?.id === el.dataset.serie);
  });
}

/** The measurements on the frame in front of you, with their values in words.
    A number drawn on a dark image at 12 px is not a number anyone can dictate
    from; this is the same value in text, and it is where one gets deleted. */
function refreshNotes() {
  const p = activePane();
  const list = (p && V.notes.get(noteKey(p))) || [];
  vq('#vwrNotes').innerHTML = list.length
    ? list.map((a, k) => `<button class="vprior" data-note="${k}" title="Remove">
        <b>${esc(a.type)}</b><span>${esc(annotationLabel(p, a))}</span></button>`).join('')
    : '<p class="vempty">None on this image.</p>';
  $$('#vwrNotes [data-note]').forEach(b => b.onclick = () => {
    list.splice(+b.dataset.note, 1); V.selected = null; paint(p); refreshNotes();
  });
}

function updateFoot() {
  const p = activePane();
  if (!p?.serie) { vq('#vwrFoot').textContent = ''; return; }
  const g = p.serie.geom;
  const bits = [
    `${p.index + 1} / ${p.serie.frames.length}`,
    `${p.serie.modality || ''} ${p.serie.desc}`.trim(),
    g.spacing ? `${fmt(g.spacing[1], 3)} × ${fmt(g.spacing[0], 3)} mm/px (${g.spacingFrom})` : 'no pixel spacing — measurements in pixels',
    MODE_LABEL[p.serie.mode] || p.serie.mode
  ];
  vq('#vwrFoot').innerHTML = bits.map(b => `<span>${esc(b)}</span>`).join('');
}

function buildSeriesList() {
  vq('#vwrSeries').innerHTML = V.series.map((se, k) => `
    <button class="vseries" data-serie="${esc(se.id)}" aria-pressed="false" title="${esc(se.desc)}">
      <span class="vseries__n">${esc(String(se.number || k + 1))}</span>
      <span class="vseries__b"><b>${esc(se.desc)}</b><span>${se.frames.length} image${se.frames.length === 1 ? '' : 's'} · ${esc(se.modality)}</span></span>
    </button>`).join('');
  $$('#vwrSeries .vseries').forEach(btn => btn.onclick = () => {
    const se = V.series.find(s => s.id === btn.dataset.serie);
    if (se) assignSeries(activePane(), se);
  });
  markSeriesList();
}

function buildPresets() {
  const mod = activePane()?.serie?.modality || '';
  const list = WL_PRESETS[mod] || WL_PRESETS['*'];
  const g = activePane()?.serie?.geom;
  vq('#vwrPresetList').innerHTML = [
    ...(g && g.wc != null ? [`<button data-wc="${g.wc}" data-ww="${g.ww}">From the file · ${g.wc}/${g.ww}</button>`] : []),
    ...list.map(([name, wc, ww]) => `<button data-wc="${wc}" data-ww="${ww}">${esc(name)} · ${wc}/${ww}</button>`),
    '<button data-auto="1">Auto — 2nd to 98th percentile</button>'
  ].join('');
  $$('#vwrPresetList button').forEach(b => b.onclick = () => {
    const p = activePane(); if (!p) return;
    if (b.dataset.auto) autoWindow(p); else setWindow(p, +b.dataset.wc, +b.dataset.ww);
    if (p.serie?.mode === 'rendered') reloadForWindow(p);
    vq('#vwrPresetPop').hidden = true;
  });
}

/** Window from the frame's own histogram — the only honest default when the
    file carries no WindowCenter and the modality has no conventional one. */
function autoWindow(pane) {
  const f = pane.frame;
  if (!f || f.kind !== 'pixels') { toast('Auto window needs the pixel data path', 'warn'); return; }
  const g = pane.serie.geom;
  const vals = Array.from(f.data).map(v => v * g.slope + g.intercept).sort((a, b) => a - b);
  const lo = vals[Math.floor(vals.length * 0.02)], hi = vals[Math.floor(vals.length * 0.98)];
  setWindow(pane, (lo + hi) / 2, Math.max(1, hi - lo));
}

/** An arrow with nothing written on it says only "look here". */
function askLabel(pane, note) {
  const dlg = vq('#noteDlg');
  const input = vq('#noteText');
  input.value = note.label || '';
  dlg.showModal();
  input.focus();
  vq('#noteSave').onclick = e => {
    e.preventDefault();
    note.label = input.value.trim();
    dlg.close(); paint(pane); refreshNotes();
  };
}

/* ------------------------------------------------------------------ export */

function exportPng() {
  const p = activePane();
  if (!p?.frame) { toast('Nothing to save yet', 'warn'); return; }
  p.canvas.toBlob(blob => {
    if (!blob) { toast('This browser refused the export', 'bad'); return; }
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${(V.study?.pid || 'image')}_${V.study?.dateRaw || ''}_se${p.serie?.number || 0}_im${p.index + 1}.png`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    toast('Saved — the overlay is burned in, so the file identifies itself', 'ok');
  }, 'image/png');
}

/* ------------------------------------------------------------------ priors */

async function loadPriors() {
  const s = V.study;
  if (!s?.pid) return;
  const box = vq('#vwrPriors');
  box.innerHTML = '<div class="skel" style="height:38px"></div>';
  try {
    // No OrderBy, ever: the ODBC index answers 500 to it. Sorted here instead.
    const rows = await API.post('tools/find', { Level: 'Study', Expand: true, Limit: 60,
      Query: { PatientID: s.pid },
      RequestedTags: ['ModalitiesInStudy', 'NumberOfStudyRelatedSeries', 'NumberOfStudyRelatedInstances'] });
    V.priors = rows.map(norm).filter(p => p.id !== s.id)
      .sort((a, b) => String(b.dateRaw).localeCompare(String(a.dateRaw)));
    box.innerHTML = V.priors.length
      ? V.priors.map(p => `<button class="vprior" data-study="${esc(p.id)}">
          <b>${esc(p.desc || p.mod.join('/') || 'Study')}</b><span>${esc(when(p.date))}</span></button>`).join('')
      : '<p class="vempty">No other study for this patient.</p>';
    $$('#vwrPriors .vprior').forEach(b => b.onclick = () => openPrior(b.dataset.study));
  } catch (e) {
    box.innerHTML = `<p class="vempty">Priors could not be read (${esc(e.status || e.message)}).</p>`;
  }
}

async function openPrior(studyId) {
  const prior = V.priors.find(p => p.id === studyId);
  if (!prior) return;
  if (V.panes.length < 2) setLayoutGrid(1, 2);
  const target = V.panes[1] === activePane() ? V.panes[0] : V.panes[1];
  V.active = target.i;
  target.el.classList.add('is-loading');
  try {
    const rows = await API.get(`studies/${studyId}/series`);
    rows.sort((a, b) => (+a.MainDicomTags?.SeriesNumber || 0) - (+b.MainDicomTags?.SeriesNumber || 0));
    const built = await buildSeries(rows[0]);
    built.priorOf = prior;
    await assignSeries(target, built);
    toast(`Comparing with ${when(prior.date)}`, 'ok');
  } catch (e) { toast(`Prior could not be opened (${e.status || e.message})`, 'bad'); }
  finally { target.el.classList.remove('is-loading'); }
}

/* ------------------------------------------------------- open, close, keys */

async function openViewer(study) {
  V.study = study;
  V.notes.clear(); FrameCache.clear();
  vq('#vwrName').textContent = study.name;
  vq('#vwrSub').textContent = [study.pid, study.sex, age(study.dob, study.date), study.desc, when(study.date)]
    .filter(Boolean).join('  ·  ');
  vq('#viewer').hidden = false;
  vq('#viewer').setAttribute('aria-hidden', 'false');
  document.body.classList.add('vwr-open');
  V.open = true;
  vq('#vwrSeries').innerHTML = '<div class="skel" style="height:56px"></div>'.repeat(3);
  setLayoutGrid(1, 1);
  setTool(V.tool);
  try {
    const rows = await API.get(`studies/${study.id}/series`);
    rows.sort((a, b) => (+a.MainDicomTags?.SeriesNumber || 0) - (+b.MainDicomTags?.SeriesNumber || 0));
    V.series = await Promise.all(rows.map(buildSeries));
    buildSeriesList();
    hangByModality();
    if (V.series[0]) await assignSeries(activePane(), V.series[0]);
    buildPresets();
    loadPriors();
    vq('#viewer').dataset.ready = '1';
  } catch (e) {
    vq('#vwrSeries').innerHTML = `<p class="vempty">Series could not be read (${esc(e.status || e.message)}).</p>`;
    vq('#viewer').dataset.ready = 'error';
  }
}

/** The layout a study of this kind is normally read in. Not a hanging protocol
    in the DICOM sense -- there is no protocol store here -- but the same idea,
    and better than starting every study in a single pane. */
function hangByModality() {
  const mod = V.series[0]?.modality || '';
  const n = V.series.length;
  const want = /^(XA|US|NM)$/.test(mod) ? [1, 1]
    : /^(CR|DX|MG)$/.test(mod) ? (n >= 2 ? [1, 2] : [1, 1])
    : n >= 4 ? [2, 2] : n >= 2 ? [1, 2] : [1, 1];
  setLayoutGrid(want[0], want[1]);
}

function closeViewer() {
  cine(false);
  V.open = false;
  vq('#viewer').hidden = true;
  vq('#viewer').setAttribute('aria-hidden', 'true');
  delete vq('#viewer').dataset.ready;
  document.body.classList.remove('vwr-open');
  FrameCache.clear();
}

function resetPane(p) {
  p.rot = 0; p.flipH = false; p.flipV = false; p.invert = false; p.sharpen = 0; p.loupe = null;
  const g = p.serie?.geom;
  if (g) setWindow(p, g.wc ?? 40, g.ww ?? 400);
  fitPane(p); paint(p);
}

/** True size: one millimetre of anatomy over one millimetre of glass. Needs the
    display's real pixel pitch, which the browser will not tell us — so it is
    measured once against a bank card and kept. Uncalibrated, it says so. */
function trueSize(p) {
  const g = p.serie?.geom;
  if (!g?.spacing) { toast('This series has no pixel spacing — true size is not defined', 'warn'); return; }
  const { value, calibrated } = pxPerMm();
  p.zoom = value * g.spacing[1];
  p.fitted = false; paint(p);
  toast(calibrated ? 'True size, against your calibrated display'
    : 'True size assuming a 96 dpi display — calibrate for a real 1:1', calibrated ? 'ok' : 'warn');
}

function viewerKey(e) {
  if (!V.open) return false;
  const p = activePane();
  const K = e.key;
  const stop = () => { e.preventDefault(); e.stopPropagation(); };
  if (K === 'Escape') { stop(); if (p?.draft) { p.draft = null; paint(p); } else closeViewer(); return true; }
  if (!p) return false;
  const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1, PageDown: 10, PageUp: -10 }[K];
  if (step) { stop(); stepFrame(p, step); return true; }
  if (K === 'Home') { stop(); showFrame(p, 0); return true; }
  if (K === 'End') { stop(); showFrame(p, (p.serie?.frames.length || 1) - 1); return true; }
  if (K === '+' || K === '=') { stop(); p.zoom *= 1.2; p.fitted = false; paint(p); return true; }
  if (K === '-') { stop(); p.zoom /= 1.2; p.fitted = false; paint(p); return true; }
  if (K === '0') { stop(); fitPane(p); paint(p); return true; }
  if (K === '1') { stop(); p.zoom = 1; p.fitted = false; paint(p); return true; }
  if (K === '9') { stop(); trueSize(p); return true; }
  const tools = { w: 'wl', p: 'pan', z: 'zoom', s: 'stack', x: 'probe', l: 'length',
    a: 'angle', o: 'ellipse', b: 'rect', m: 'magnify' };
  if (tools[K]) { stop(); setTool(tools[K]); return true; }
  if (K === 'i') { stop(); p.invert = !p.invert; paint(p); return true; }
  if (K === 'r') { stop(); p.rot = (p.rot + 90) % 360; p.fitted = true; paint(p); return true; }
  if (K === 'h') { stop(); p.flipH = !p.flipH; paint(p); return true; }
  if (K === 'v') { stop(); p.flipV = !p.flipV; paint(p); return true; }
  if (K === 'c') { stop(); cine(); return true; }
  if (K === 'e') { stop(); resetPane(p); return true; }
  if (K === 'g') { stop(); V.overlay = !V.overlay; paintAll(); return true; }
  if (K === '[' || K === ']') {
    stop();
    const k = V.series.findIndex(s => s.id === p.serie?.id);
    const next = V.series[k + (K === ']' ? 1 : -1)];
    if (next) assignSeries(p, next);
    return true;
  }
  if (K === 'Delete' || K === 'Backspace') {
    stop();
    const list = V.notes.get(noteKey(p));
    if (V.selected && list?.includes(V.selected)) { list.splice(list.indexOf(V.selected), 1); V.selected = null; paint(p); }
    else if (list?.length) { list.pop(); paint(p); }
    refreshNotes();
    return true;
  }
  return false;
}

/* ------------------------------------------------------------------- wiring */

function wireViewer() {
  vq('#vwrClose').onclick = closeViewer;
  $$('#vwrTools button[data-tool]').forEach(b => b.onclick = () => setTool(b.dataset.tool));
  $$('#vwrLayouts button').forEach(b => b.onclick = () => {
    const [r, c] = b.dataset.layout.split('x').map(Number); setLayoutGrid(r, c);
  });
  // Every data-act button in the viewer, not just the ones in #vwrActions:
  // Overlay and Clear live in the right-hand group and were dead until a test
  // went looking for them.
  $$('#viewer button[data-act]').forEach(b => b.onclick = () => {
    const p = activePane(); if (!p) return;
    ({ invert: () => { p.invert = !p.invert; paint(p); },
       rotate: () => { p.rot = (p.rot + 90) % 360; p.fitted = true; paint(p); },
       fliph:  () => { p.flipH = !p.flipH; paint(p); },
       flipv:  () => { p.flipV = !p.flipV; paint(p); },
       fit:    () => { fitPane(p); paint(p); },
       one:    () => { p.zoom = 1; p.fitted = false; paint(p); },
       truesize: () => trueSize(p),
       reset:  () => resetPane(p),
       sharpen: () => {
         if (p.frame && p.frame.kind !== 'pixels') { toast('Enhancement needs the pixel-data path', 'warn'); return; }
         p.sharpen = (p.sharpen + 1) % 3; p.offKey = null;
         b.setAttribute('aria-pressed', String(p.sharpen > 0));
         b.textContent = ['Enhance', 'Sharpen', 'Smooth'][p.sharpen]; paint(p);
       },
       overlay: () => { V.overlay = !V.overlay; b.setAttribute('aria-pressed', String(V.overlay)); paintAll(); },
       clear:  () => { V.notes.set(noteKey(p), []); V.selected = null; paint(p); refreshNotes(); }
    }[b.dataset.act] || (() => {}))();
  });
  vq('#vwrCine').onclick = () => cine();
  vq('#vwrFps').oninput = e => { V.cine.fps = +e.target.value; vq('#vwrFpsOut').textContent = `${V.cine.fps} fps`; };
  vq('#vwrBounce').onchange = e => { V.cine.bounce = e.target.checked; };
  vq('#vwrLinkScroll').onchange = e => { V.link.scroll = e.target.checked; };
  vq('#vwrLinkWl').onchange = e => { V.link.wl = e.target.checked; };
  vq('#vwrExport').onclick = exportPng;
  vq('#vwrPresets').onclick = () => {
    buildPresets();
    vq('#vwrPresetPop').hidden = !vq('#vwrPresetPop').hidden;
  };
  vq('#vwrTagsBtn').onclick = async () => {
    const p = activePane(); if (!p?.serie) return;
    const f = p.serie.frames[p.index];
    const dlg = vq('#tagDlg');
    vq('#tagBody').innerHTML = '<div class="skel" style="height:200px"></div>';
    dlg.showModal();
    const tags = await API.get(`instances/${f.instance}/simplified-tags`).catch(() => null);
    vq('#tagBody').innerHTML = tags
      ? `<table class="tagtable"><tbody>${Object.entries(tags)
          .map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(typeof v === 'object' ? JSON.stringify(v) : v)}</td></tr>`).join('')}</tbody></table>`
      : '<p class="vempty">This archive did not return tags for the frame.</p>';
  };
  vq('#vwrCalBtn').onclick = () => {
    const cur = store.get('viewer.pxPerMm', 96 / 25.4);
    vq('#calRange').value = String(Math.round(cur * 85.6));
    vq('#calCard').style.width = `${Math.round(cur * 85.6)}px`;
    vq('#calDlg').showModal();
  };
  vq('#calRange').oninput = e => { vq('#calCard').style.width = `${e.target.value}px`; };
  vq('#calSave').onclick = () => {
    store.set('viewer.pxPerMm', +vq('#calRange').value / 85.6);
    vq('#calDlg').close();
    toast('Display calibrated — true size is now real', 'ok');
  };
  vq('#calClear').onclick = () => { store.set('viewer.pxPerMm', null); vq('#calDlg').close(); toast('Calibration cleared'); };
  addEventListener('resize', () => { if (V.open) paintAll(); });
}
