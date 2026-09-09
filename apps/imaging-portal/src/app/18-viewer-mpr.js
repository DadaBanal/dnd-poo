/* ===========================================================================
   PMC Viewer — multiplanar reconstruction
   ---------------------------------------------------------------------------
   Voyager's own answer to 3D on the workstation is to launch a third-party
   application; its zero-footprint viewer does not reslice. This does, for the
   one case that matters most here — a CT or MR stack — and it does it without
   a server, a plugin or a licence.

   The volume is stacked from the SAME per-frame numpy fetches the axial view
   already uses, in the order this viewer sorted the instances, rather than from
   /series/{id}/numpy in one request. That is deliberate: the series route
   returns the frames in an order Orthanc chooses, and a coronal image built on
   a wrong slice order is not obviously wrong on screen. Slower, and right.

   A reslice is a genuine series to everything downstream: window/level, the
   Hounsfield probe, regions and measurements all run unchanged, because the
   pseudo-series carries its own pixel spacing — column spacing across, slice
   spacing down.
   =========================================================================== */

const MPR_MAX_BYTES = 512 * 1024 * 1024;      // refuse outright above this
const MPR_WARN_BYTES = 96 * 1024 * 1024;      // say how big it is above this

/** Median gap between consecutive slices, in millimetres. */
function sliceSpacing(serie) {
  const gaps = [];
  for (let i = 1; i < serie.frames.length; i++) {
    const a = framePosition(serie, i - 1), b = framePosition(serie, i);
    if (a != null && b != null) gaps.push(Math.abs(b - a));
  }
  if (!gaps.length) return serie.geom.thickness || 1;
  gaps.sort((x, y) => x - y);
  return gaps[gaps.length >> 1] || serie.geom.thickness || 1;
}

/** Fetch every frame and stack it into one array, in this viewer's own order. */
async function buildVolume(serie, onProgress) {
  const n = serie.frames.length;
  await ensureGeometry(serie);
  const first = await ensurePixels(serie, 0);
  if (!first || first.kind !== 'pixels') throw new Error('this series is not on the pixel-data path');
  if (first.ch > 1) throw new Error('a colour series has no meaningful reslice');
  const { w, h } = first;
  const need = n * w * h * 2;
  if (need > MPR_MAX_BYTES) throw new Error(`the volume would be ${bytes(need)} — too large to hold in a browser tab`);
  const vol = new Int16Array(n * h * w);
  for (let i = 0; i < n; i++) {
    const f = await ensurePixels(serie, i);
    if (!f || f.kind !== 'pixels' || f.w !== w || f.h !== h) {
      throw new Error(`frame ${i + 1} does not match the first frame — this stack is not a volume`);
    }
    vol.set(f.data, i * h * w);
    if (onProgress && i % 8 === 0) onProgress(i + 1, n);
  }
  return { data: vol, F: n, H: h, W: w, dz: sliceSpacing(serie) };
}

/** A reslice presented as an ordinary series, so nothing downstream changes. */
function planeSeries(source, volume, plane) {
  const g = source.geom;
  const sp = g.spacing || [1, 1];              // [between rows, between columns]
  const count = plane === 'coronal' ? volume.H : volume.W;
  const across = plane === 'coronal' ? sp[1] : sp[0];
  return {
    id: `${source.id}:${plane}`,
    row: source.row,
    frames: Array.from({ length: count }, (_, i) => ({ instance: `${source.id}:${plane}`, frame: i, inst: {} })),
    volume, plane, source,
    sliceCache: new Map(),
    pixelMode: 'yes', tagsLoaded: true,
    number: source.number,
    desc: `${source.desc} — ${plane}`,
    modality: source.modality,
    geom: { ...g, spacing: [volume.dz, across],
      spacingFrom: `reconstructed (${fmt(across, 3)} mm across, ${fmt(volume.dz, 3)} mm between slices)`,
      orientation: null,                        // the source orientation no longer describes this plane
      wcNow: g.wcNow, wwNow: g.wwNow }
  };
}

/** Cut one plane out of the volume. Cheap: it is a strided copy, not a resample. */
function sliceVolume(serie, index) {
  const hit = serie.sliceCache.get(index);
  if (hit) return hit;
  const { data, F, H, W } = serie.volume;
  let out, w, h;
  if (serie.plane === 'coronal') {              // fixed row; across = columns, down = slices
    w = W; h = F;
    out = new Int16Array(w * h);
    for (let f = 0; f < F; f++) out.set(data.subarray(f * H * W + index * W, f * H * W + index * W + W), f * W);
  } else {                                      // sagittal: fixed column
    w = H; h = F;
    out = new Int16Array(w * h);
    for (let f = 0; f < F; f++) for (let y = 0; y < H; y++) out[f * w + y] = data[f * H * W + y * W + index];
  }
  const frame = { kind: 'pixels', data: out, w, h, ch: 1, dtype: '<i2' };
  if (serie.sliceCache.size > 140) serie.sliceCache.clear();
  serie.sliceCache.set(index, frame);
  return frame;
}

const MPR = { on: false, axial: null, coronal: null, sagittal: null, pos: { x: 0, y: 0, z: 0 } };

async function openMpr() {
  const p = activePane();
  const src = p?.serie;
  if (!src) return;
  if (src.plane) { toast('Already showing a reconstruction'); return; }
  if (src.frames.length < 8) { toast('A reconstruction needs a stack, not a handful of images', 'warn'); return; }
  if (src.pixelMode === 'no') { toast('Reconstruction needs the pixel-data path — this series is not on it', 'warn'); return; }
  const est = src.frames.length * (src.geom.rows || 512) * (src.geom.cols || 512) * 2;
  if (est > MPR_WARN_BYTES) toast(`Reading ${bytes(est)} of pixel data — this will take a moment`);
  vq('#vwrMpr').setAttribute('aria-pressed', 'true');
  vq('#vwrFoot').textContent = 'building the volume…';
  try {
    const volume = await buildVolume(src, (i, n) => { vq('#vwrFoot').textContent = `building the volume… ${i} / ${n}`; });
    MPR.on = true;
    MPR.axial = src;
    MPR.coronal = planeSeries(src, volume, 'coronal');
    MPR.sagittal = planeSeries(src, volume, 'sagittal');
    MPR.pos = { x: volume.W >> 1, y: volume.H >> 1, z: volume.F >> 1 };
    setLayoutGrid(1, 3);
    await assignSeries(V.panes[0], MPR.axial);
    await assignSeries(V.panes[1], MPR.coronal);
    await assignSeries(V.panes[2], MPR.sagittal);
    setTool('cross');
    await syncCrosshair();
    toast('Axial, coronal and sagittal. Click any pane to move the others.', 'ok');
  } catch (e) {
    MPR.on = false;
    vq('#vwrMpr').setAttribute('aria-pressed', 'false');
    toast(`No reconstruction: ${e.message}`, 'bad');
    updateFoot();
  }
}

function closeMpr() {
  if (!MPR.on) return;
  MPR.on = false;
  vq('#vwrMpr').setAttribute('aria-pressed', 'false');
  const src = MPR.axial;
  MPR.axial = MPR.coronal = MPR.sagittal = null;
  setLayoutGrid(1, 1);
  if (src) assignSeries(V.panes[0], src);
  setTool('wl');
}

/** Put every plane on the slice the crosshair names. */
async function syncCrosshair() {
  if (!MPR.on) return;
  const jobs = [];
  for (const pane of V.panes) {
    const s = pane.serie;
    if (!s) continue;
    if (s === MPR.axial && pane.index !== MPR.pos.z) jobs.push(showFrame(pane, MPR.pos.z));
    if (s === MPR.coronal && pane.index !== MPR.pos.y) jobs.push(showFrame(pane, MPR.pos.y));
    if (s === MPR.sagittal && pane.index !== MPR.pos.x) jobs.push(showFrame(pane, MPR.pos.x));
  }
  await Promise.all(jobs);
  paintAll();
}

/** A click in any plane names a point in the volume; the other two follow. */
function crosshairFrom(pane, ix, iy) {
  if (!MPR.on || !pane.serie) return;
  const s = pane.serie;
  const v = MPR.coronal.volume;
  const clamp = (n, hi) => Math.max(0, Math.min(hi - 1, Math.round(n)));
  if (s === MPR.axial) { MPR.pos.x = clamp(ix, v.W); MPR.pos.y = clamp(iy, v.H); MPR.pos.z = pane.index; }
  else if (s === MPR.coronal) { MPR.pos.x = clamp(ix, v.W); MPR.pos.z = clamp(iy, v.F); MPR.pos.y = pane.index; }
  else if (s === MPR.sagittal) { MPR.pos.y = clamp(ix, v.H); MPR.pos.z = clamp(iy, v.F); MPR.pos.x = pane.index; }
  else return;
  syncCrosshair();
}

/** Where the crosshair falls in this pane's own image coordinates. */
function crosshairIn(pane) {
  const s = pane.serie;
  if (!MPR.on || !s) return null;
  if (s === MPR.axial) return { x: MPR.pos.x, y: MPR.pos.y };
  if (s === MPR.coronal) return { x: MPR.pos.x, y: MPR.pos.z };
  if (s === MPR.sagittal) return { x: MPR.pos.y, y: MPR.pos.z };
  return null;
}

function drawCrosshair(pane, ctx, cw, ch) {
  const at = crosshairIn(pane);
  if (!at) return;
  const p = imageToScreen(pane, at.x + 0.5, at.y + 0.5);
  ctx.save();
  ctx.strokeStyle = 'rgba(255,214,102,.75)';
  ctx.lineWidth = 1;
  ctx.setLineDash([5, 5]);
  ctx.beginPath();
  ctx.moveTo(0, p.y); ctx.lineTo(cw, p.y);
  ctx.moveTo(p.x, 0); ctx.lineTo(p.x, ch);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.beginPath(); ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
  ctx.strokeStyle = 'rgba(255,214,102,.95)'; ctx.stroke();
  ctx.restore();
}
