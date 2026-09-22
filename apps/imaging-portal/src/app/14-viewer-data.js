/* ===========================================================================
   PMC Viewer — the data half
   ---------------------------------------------------------------------------
   Orthanc will hand the same frame over in three different ways, and which one
   you can have depends on the transfer syntax and the plugins installed. The
   viewer asks for the best available and remembers the answer per series, so a
   study that cannot be decoded to an array still displays instead of failing:

     1. numpy    GET /instances/{id}/frames/{f}/numpy?rescale=0
                 The stored pixel values, verbatim. This is the only path that
                 can give a true Hounsfield readout, region statistics, or a
                 window/level drag that keeps up with the mouse, because the
                 windowing then happens here rather than over the network.
     2. rendered GET /instances/{id}/frames/{f}/rendered?window-center&window-width
                 Orthanc applies RescaleSlope/Intercept and the VOI window and
                 sends a PNG. Accurate, but one round trip per window change.
     3. preview  GET /instances/{id}/preview
                 Full dynamic range stretched to 8 bits. No windowing at all;
                 the last resort, and the viewer says so on screen.

   Endpoints and parameter names VERIFIED 2026-09-09 against Orthanc's published
   OpenAPI (orthanc.uclouvain.be/api/orthanc-openapi.json): `window-center`,
   `window-width`, `width`, `height`, `quality`, `smooth` on /rendered;
   `compress`, `rescale` on /numpy.
   =========================================================================== */

/** Parse a .npy buffer. Little-endian only, which is what Orthanc emits. */
function parseNpy(buf) {
  const b = new Uint8Array(buf);
  const magic = String.fromCharCode(...b.slice(1, 6));
  if (b[0] !== 0x93 || magic !== 'NUMPY') throw new Error('not a .npy buffer');
  const major = b[6];
  const dv = new DataView(buf);
  const headLen = major === 1 ? dv.getUint16(8, true) : dv.getUint32(8, true);
  const start = (major === 1 ? 10 : 12) + headLen;
  const header = new TextDecoder('latin1').decode(b.slice(major === 1 ? 10 : 12, start));
  const descr = (/'descr'\s*:\s*'([^']+)'/.exec(header) || [])[1];
  const shape = (/'shape'\s*:\s*\(([^)]*)\)/.exec(header) || [, ''])[1]
    .split(',').map(s => s.trim()).filter(Boolean).map(Number);
  const CTOR = { '<i2': Int16Array, '<u2': Uint16Array, '|u1': Uint8Array, '|i1': Int8Array,
    '<i4': Int32Array, '<u4': Uint32Array, '<f4': Float32Array, '<f8': Float64Array };
  const Ctor = CTOR[descr];
  if (!Ctor) throw new Error(`unsupported .npy dtype ${descr}`);
  // shape is (frame, height, width, channel); a single frame is what we asked for.
  const [, h = 1, w = 1, ch = 1] = shape.length >= 4 ? shape : [1, shape[0], shape[1], 1];
  return { data: new Ctor(buf, start, h * w * ch), w, h, ch, dtype: descr };
}

/** Multi-valued DICOM strings arrive as "40\\400"; the first value is the one. */
const dcm1 = v => (v === undefined || v === null || v === '') ? null : Number(String(v).split('\\')[0]);
const dcmList = v => String(v ?? '').split('\\').map(Number).filter(n => !Number.isNaN(n));

/** Everything about a series that does not change frame to frame. */
function seriesGeometry(tags, seriesTags = {}) {
  const spacing = dcmList(tags.PixelSpacing).length === 2 ? dcmList(tags.PixelSpacing)
    : dcmList(tags.ImagerPixelSpacing).length === 2 ? dcmList(tags.ImagerPixelSpacing) : null;
  return {
    modality: tags.Modality || seriesTags.Modality || '',
    rows: +tags.Rows || 0, cols: +tags.Columns || 0,
    // Row spacing first, per PS3.3 C.7.6.2 — the pair is (between rows, between columns).
    spacing,                                    // [mm between rows, mm between columns] or null
    spacingFrom: dcmList(tags.PixelSpacing).length === 2 ? 'PixelSpacing'
      : dcmList(tags.ImagerPixelSpacing).length === 2 ? 'ImagerPixelSpacing (detector plane)' : null,
    thickness: dcm1(tags.SliceThickness),
    slope: dcm1(tags.RescaleSlope) ?? 1,
    intercept: dcm1(tags.RescaleIntercept) ?? 0,
    rescaleKnown: tags.RescaleSlope !== undefined || tags.RescaleIntercept !== undefined,
    unit: (tags.RescaleType || (String(tags.Modality) === 'CT' ? 'HU' : '')) || '',
    wc: dcm1(tags.WindowCenter), ww: dcm1(tags.WindowWidth),
    mono1: String(tags.PhotometricInterpretation || '').trim() === 'MONOCHROME1',
    colour: +tags.SamplesPerPixel > 1,
    orientation: dcmList(tags.ImageOrientationPatient).length === 6 ? dcmList(tags.ImageOrientationPatient) : null,
    kvp: tags.KVP || '', mas: tags.XRayTubeCurrent || tags.Exposure || '',
    seriesDesc: tags.SeriesDescription || seriesTags.SeriesDescription || '',
    bodyPart: tags.BodyPartExamined || '', station: tags.StationName || '',
    tags
  };
}

/* ---- the frame cache ----------------------------------------------------
   A 96x96 phantom is nothing; a 512-slice CT held as Int16 is 256 MB, which a
   browser tab will not survive. So the cache is bounded and evicts the frames
   furthest from where the user is looking, not simply the oldest.            */
const FrameCache = {
  // Bounded by BYTES, not by a count of frames. MEASURED 9 Sep 2026 on PMC's
  // cathlab archive: one XA frame's stored values are 1,478 KB and a single run
  // is 56 frames, so a 260-frame cap would have been 384 MB of Int16Array in a
  // browser tab. A cap in megabytes holds a whole run and still cannot run away.
  maxBytes: 192 * 1024 * 1024,
  bytes: 0, map: new Map(),
  key: (inst, f) => `${inst}#${f}`,
  size(val) {
    if (val?.data?.byteLength) return val.data.byteLength;
    return (val?.w && val?.h) ? val.w * val.h : 0;    // a decoded picture, roughly
  },
  get(inst, f) {
    const k = this.key(inst, f), v = this.map.get(k);
    // Touch on read, so eviction drops what nobody is looking at rather than
    // what happened to be fetched first.
    if (v !== undefined) { this.map.delete(k); this.map.set(k, v); }
    return v;
  },
  has(inst, f) { return this.map.has(this.key(inst, f)); },
  put(inst, f, val) {
    const k = this.key(inst, f), old = this.map.get(k);
    // A picture must never displace the values for the same frame.
    if (old?.kind === 'pixels' && val?.kind !== 'pixels') return old;
    if (old) this.bytes -= this.size(old);
    this.map.delete(k);
    this.map.set(k, val);
    this.bytes += this.size(val);
    for (const key of this.map.keys()) {
      if (this.bytes <= this.maxBytes || this.map.size <= 1) break;
      if (key === k) continue;                       // never evict what was just asked for
      this.bytes -= this.size(this.map.get(key));
      this.map.delete(key);
    }
    return val;
  },
  /** Drop one frame, keeping the byte count honest. */
  drop(inst, f) {
    const k = this.key(inst, f), v = this.map.get(k);
    if (v === undefined) return;
    this.bytes -= this.size(v);
    this.map.delete(k);
  },
  clear() { this.map.clear(); this.bytes = 0; }
};

/** At most four frames in flight: more only queues them behind each other. */
const frameGate = (() => {
  let active = 0; const q = [];
  const next = () => { if (active >= 4 || !q.length) return; active++; q.shift()().finally(() => { active--; next(); }); };
  return fn => new Promise((res, rej) => { q.push(() => fn().then(res, rej)); next(); });
})();

async function fetchArrayBuffer(path, signal) {
  const r = await fetch(API.url(path), { credentials: 'same-origin', signal });
  if (!r.ok) { const e = new Error(`${r.status} on ${path}`); e.status = r.status; throw e; }
  return r.arrayBuffer();
}
function loadImageEl(src) {
  return new Promise((res, rej) => {
    const img = new Image();
    img.decoding = 'async';
    img.onload = () => res(img);
    img.onerror = () => rej(new Error(`image failed: ${src}`));
    img.src = src;
  });
}

/**
 * Fetch one frame in the best form this series allows.
 * The picture comes first and is never gated on the stored values; see
 * loadRendered and ensurePixels below for why, and for what it measured.
 */
async function loadFrame(serie, i) {
  const f = serie.frames[i];
  if (!f) return null;
  // A reconstructed plane is cut out of a volume already in memory. It never
  // touches the network, and it must not touch the shared frame cache either --
  // its "instance" is not an instance.
  if (serie.volume) return sliceVolume(serie, i);
  const hit = FrameCache.get(f.instance, f.frame);
  if (hit) return hit;

  // The sample dataset has no server behind it. It still produces stored values
  // rather than a picture, so nothing below this line behaves differently.
  if (state.demo) {
    serie.pixelMode = 'sample';
    const m = /^(.*)-i(\d+)$/.exec(f.instance) || [, f.instance, '0'];
    return FrameCache.put(f.instance, f.frame, Demo.pixels(m[1], +m[2], serie.modality));
  }
  return loadRendered(serie, i);
}

/**
 * The fast path: a picture, windowed by the archive.
 *
 * MEASURED 9 Sep 2026 on PMC's cathlab archive, one XA frame: /rendered
 * answered in 2.3 s and /numpy in 24.6 s. Whatever the split between decode and
 * disk, asking for the array first means nothing is on screen for half a minute.
 * So the picture comes first, always, and the array arrives behind it.
 */
async function loadRendered(serie, i) {
  const f = serie.frames[i];
  const framePath = `instances/${f.instance}/frames/${f.frame}`;
  try {
    const q = serie.geom.wcNow != null && serie.geom.wwNow != null
      ? `?window-center=${serie.geom.wcNow}&window-width=${serie.geom.wwNow}` : '';
    const img = await frameGate(() => loadImageEl(API.url(`${framePath}/rendered${q}`)));
    return FrameCache.put(f.instance, f.frame, { kind: 'image', img, w: img.naturalWidth, h: img.naturalHeight });
  } catch { /* fall through to the preview */ }
  const img = await frameGate(() => loadImageEl(API.url(`instances/${f.instance}/preview`))
    .catch(() => loadImageEl(API.url(`${framePath}/preview`))));
  return FrameCache.put(f.instance, f.frame, { kind: 'image', img, w: img.naturalWidth, h: img.naturalHeight, flat: true });
}

/**
 * The slow path, fetched behind the picture: the stored pixel values.
 *
 * This is what makes the Hounsfield probe, region statistics and a window/level
 * drag that costs no network possible. It is never waited on to put an image on
 * screen, never prefetched for frames nobody is looking at, and asked for once
 * per series before giving up -- a series the archive cannot decode to an array
 * will not start being able to on the next frame.
 */
async function ensurePixels(serie, i) {
  const f = serie.frames[i];
  if (!f || serie.volume || state.demo) return null;
  if (serie.pixelMode === 'no') return null;
  const hit = FrameCache.get(f.instance, f.frame);
  if (hit?.kind === 'pixels') return hit;
  const key = `${f.instance}#${f.frame}`;
  if (serie.pixelInFlight?.has(key)) return serie.pixelInFlight.get(key);
  if (!serie.pixelInFlight) serie.pixelInFlight = new Map();

  const job = (async () => {
    try {
      const buf = await frameGate(() =>
        fetchArrayBuffer(`instances/${f.instance}/frames/${f.frame}/numpy?rescale=0&compress=0`));
      const px = parseNpy(buf);
      serie.pixelMode = 'yes';
      // Do not let a picture already in the cache displace the values.
      return FrameCache.put(f.instance, f.frame, { kind: 'pixels', ...px });
    } catch (e) {
      // 415 and 404 mean this series is not decodable to an array, and settle it
      // for the whole series. Anything else might be transient, so the next
      // frame may still try -- but this frame stops claiming to be reading.
      if (e.status === 415 || e.status === 404) serie.pixelMode = 'no';
      else serie.pixelFailed = true;
      return null;
    } finally { serie.pixelInFlight.delete(key); }
  })();
  serie.pixelInFlight.set(key, job);
  return job;
}

/**
 * Build the frame list for a series: one entry per displayable frame, in the
 * order a radiologist expects to scroll them.
 *
 * A multi-frame instance (US cine, XA run) holds many frames behind one id, so
 * the stack is the flattened list, not the instance list.
 */
async function buildSeries(seriesRow) {
  const id = seriesRow.ID;
  let instances = [];
  try {
    instances = await listChildren(`series/${id}/instances`);
  } catch {
    instances = (seriesRow.Instances || []).map((iid, k) => ({ ID: iid, MainDicomTags: { InstanceNumber: String(k + 1) } }));
  }
  instances.sort((a, b) => (+a.MainDicomTags?.InstanceNumber || a.IndexInSeries || 0)
    - (+b.MainDicomTags?.InstanceNumber || b.IndexInSeries || 0));

  const frames = [];
  for (const inst of instances) {
    const n = Math.max(1, +inst.MainDicomTags?.NumberOfFrames || 1);
    for (let f = 0; f < n; f++) frames.push({ instance: inst.ID, frame: f, inst });
  }
  // The tags are NOT read here. MEASURED 9 Sep 2026: simplified-tags took 3.9 s
  // on one cathlab instance, and a study with eight runs would spend half a
  // minute on them before showing anything. The series list needs none of it, so
  // geometry loads when a series is actually put in a pane. See ensureGeometry.
  const geom = seriesGeometry({}, seriesRow.MainDicomTags || {});
  return {
    id, row: seriesRow, frames, geom, pixelMode: 'unknown', tagsLoaded: false,
    number: +seriesRow.MainDicomTags?.SeriesNumber || 0,
    desc: seriesRow.MainDicomTags?.SeriesDescription || geom.seriesDesc || `Series ${seriesRow.MainDicomTags?.SeriesNumber || ''}`.trim(),
    modality: seriesRow.MainDicomTags?.Modality || geom.modality || ''
  };
}

/** Read the series' geometry once, when something actually needs it. */
async function ensureGeometry(serie) {
  if (serie.tagsLoaded || !serie.frames.length) return serie.geom;
  serie.tagsLoaded = true;
  const first = serie.frames[0];
  const tags = state.demo
    ? await API.get(`instances/${first.instance}/simplified-tags`).catch(() => ({}))
    : await API.get(`instances/${first.instance}/simplified-tags`).catch(() => ({}));
  const fresh = seriesGeometry(tags, serie.row.MainDicomTags || {});
  // Keep any window the user has already dialled in on this series.
  fresh.wcNow = serie.geom.wcNow; fresh.wwNow = serie.geom.wwNow;
  serie.geom = fresh;
  return fresh;
}
