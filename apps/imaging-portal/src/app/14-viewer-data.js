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
  max: 260, map: new Map(),
  key: (inst, f) => `${inst}#${f}`,
  get(inst, f) { return this.map.get(this.key(inst, f)); },
  has(inst, f) { return this.map.has(this.key(inst, f)); },
  put(inst, f, val) {
    this.map.set(this.key(inst, f), val);
    if (this.map.size > this.max) {
      const drop = this.map.size - this.max;
      let n = 0;
      for (const k of this.map.keys()) { if (n++ >= drop) break; this.map.delete(k); }
    }
    return val;
  },
  clear() { this.map.clear(); }
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
 * `serie.mode` is 'auto' until the first answer settles it, and is then never
 * re-probed — an archive that cannot decode one frame of a series cannot decode
 * the next one either, and retrying 40 times per scroll is how a viewer stalls.
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
  const framePath = `instances/${f.instance}/frames/${f.frame}`;

  // The sample dataset has no server behind it. It still produces stored values
  // rather than a picture, so nothing below this line behaves differently.
  if (state.demo) {
    serie.mode = 'sample';
    const m = /^(.*)-i(\d+)$/.exec(f.instance) || [, f.instance, '0'];
    return FrameCache.put(f.instance, f.frame, Demo.pixels(m[1], +m[2], serie.modality));
  }

  if (serie.mode === 'auto' || serie.mode === 'pixels') {
    try {
      const buf = await frameGate(() => fetchArrayBuffer(`${framePath}/numpy?rescale=0&compress=0`));
      const px = parseNpy(buf);
      serie.mode = 'pixels';
      return FrameCache.put(f.instance, f.frame, { kind: 'pixels', ...px });
    } catch (e) {
      if (serie.mode === 'pixels') throw e;      // settled path failing is a real fault
      serie.mode = 'rendered';                   // 415/404: this series is not decodable to an array
    }
  }
  if (serie.mode === 'rendered') {
    try {
      const q = serie.geom.wcNow != null && serie.geom.wwNow != null
        ? `?window-center=${serie.geom.wcNow}&window-width=${serie.geom.wwNow}` : '';
      const img = await frameGate(() => loadImageEl(API.url(`${framePath}/rendered${q}`)));
      return FrameCache.put(f.instance, f.frame, { kind: 'image', img, w: img.naturalWidth, h: img.naturalHeight });
    } catch { serie.mode = 'preview'; }
  }
  const img = await frameGate(() => loadImageEl(API.url(`instances/${f.instance}/preview`))
    .catch(() => loadImageEl(API.url(`${framePath}/preview`))));
  return FrameCache.put(f.instance, f.frame, { kind: 'image', img, w: img.naturalWidth, h: img.naturalHeight, flat: true });
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
    instances = await API.get(`series/${id}/instances`);
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
  // The geometry is read once, from the first instance. Within a series these
  // tags are constant in every archive PMC sends to; if that ever stops being
  // true the overlay will say so, because the per-frame tag panel reads its own.
  let tags = {};
  if (frames.length) tags = await API.get(`instances/${frames[0].instance}/simplified-tags`).catch(() => ({}));
  const geom = seriesGeometry(tags, seriesRow.MainDicomTags || {});
  return {
    id, row: seriesRow, frames, geom, mode: 'auto',
    number: +seriesRow.MainDicomTags?.SeriesNumber || 0,
    desc: seriesRow.MainDicomTags?.SeriesDescription || geom.seriesDesc || `Series ${seriesRow.MainDicomTags?.SeriesNumber || ''}`.trim(),
    modality: seriesRow.MainDicomTags?.Modality || geom.modality || ''
  };
}
