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
                 A multi-frame instance under the cap is asked for WHOLE
                 instead, GET /instances/{id}/numpy, once: see loadRun.
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

   What the two numpy routes actually return was MEASURED 2026-09-23 on Orthanc
   1.13.0 (orthancteam/orthanc:26.9.1, SQLite, invented multi-frame data): .npy
   version 1.0, little-endian, C order, values from byte 128; the whole instance
   shaped (frames, rows, columns, samples), one frame (rows, columns, samples);
   frame k of the whole equal byte for byte to frame k asked for alone. rescale
   DEFAULTS TO TRUE -- float32 in modality units, twice the bytes of 16-bit data
   and four times 8-bit -- and compress=1 answers a zip (.npz), so both are
   always sent, as 0.
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
  // A whole instance is (frames, rows, columns, samples); one frame is (rows,
  // columns, samples), with no frame axis at all (MEASURED, above). Dropping that
  // third axis, as this once did, reads a colour frame's first third as a grey
  // picture -- so a frame axis is assumed only when there are four.
  const [n = 1, h = 1, w = 1, ch = 1] = shape.length >= 4 ? shape
    : shape.length === 3 ? [1, ...shape] : [1, shape[0], shape[1], 1];
  return { data: new Ctor(buf, start, n * h * w * ch), n, w, h, ch, dtype: descr };
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
  /** Read one entry and mark it used, so eviction drops what nobody is looking
      at rather than what happened to be fetched first. */
  touch(k) {
    const v = this.map.get(k);
    if (v !== undefined) { this.map.delete(k); this.map.set(k, v); }
    return v;
  },
  get(inst, f) {
    // A whole run answers for every frame in it, and it is stored values, which
    // a picture of the same frame may never displace.
    const run = this.touch(this.key(inst, '*'));
    return run ? runFrame(run, f) : this.touch(this.key(inst, f));
  },
  has(inst, f) { return this.map.has(this.key(inst, '*')) || this.map.has(this.key(inst, f)); },
  put(inst, f, val) {
    // Once the run is here, anything arriving late for one of its frames is
    // already held, as values. Storing it as well would count it twice.
    const run = f !== '*' && this.map.get(this.key(inst, '*'));
    if (run) return runFrame(run, f);
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
  /** A run is one allocation, so it is held, counted and evicted as ONE entry.
      Whatever was already held for that instance frame by frame goes, rather
      than being counted a second time. */
  putRun(inst, run) {
    for (const k of [...this.map.keys()]) if (k.startsWith(`${inst}#`)) this.dropKey(k);
    return this.put(inst, '*', run);
  },
  /** Drop one frame, keeping the byte count honest. */
  drop(inst, f) { this.dropKey(this.key(inst, f)); },
  dropKey(k) {
    const v = this.map.get(k);
    if (v === undefined) return;
    this.bytes -= this.size(v);
    this.map.delete(k);
  },
  clear() { this.map.clear(); this.bytes = 0; }
};

/** Frame k of a run: a view into it, not a copy, and the same object each time. */
function runFrame(run, k) {
  if (!(k >= 0 && k < run.n)) return undefined;
  const size = run.w * run.h * run.ch;
  return run.frames[k] ??= { kind: 'pixels', data: run.data.subarray(k * size, (k + 1) * size),
    w: run.w, h: run.h, ch: run.ch, dtype: run.dtype };
}

/** At most four frames in flight: more only queues them behind each other. A
    whole run goes to the front of the queue -- it is the one request that makes
    the rest of them unnecessary. */
const frameGate = (() => {
  let active = 0; const q = [];
  const next = () => { if (active >= 4 || !q.length) return; active++; q.shift()().finally(() => { active--; next(); }); };
  return (fn, first = false) => new Promise((res, rej) => { q[first ? 'unshift' : 'push'](() => fn().then(res, rej)); next(); });
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

/** Pictures on their way, by frame and window. */
const picturesInFlight = new Map();

/**
 * The fast path: a picture, windowed by the archive.
 *
 * MEASURED 9 Sep 2026 on PMC's cathlab archive, one XA frame: /rendered
 * answered in 2.3 s and /numpy in 24.6 s. Whatever the split between decode and
 * disk, asking for the array first means nothing is on screen for half a minute.
 * So the picture comes first, always, and the array arrives behind it.
 */
function loadRendered(serie, i) {
  const f = serie.frames[i];
  const q = serie.geom.wcNow != null && serie.geom.wwNow != null
    ? `?window-center=${serie.geom.wcNow}&window-width=${serie.geom.wwNow}` : '';
  // The pane and the prefetch running ahead of it ask for the same picture; it is
  // fetched once. Cine asks on every tick, so without this a slow archive would
  // see one frame queued a dozen times over.
  const key = `${f.instance}#${f.frame}${q}`;
  if (!picturesInFlight.has(key)) {
    picturesInFlight.set(key, fetchPicture(f, q).finally(() => picturesInFlight.delete(key)));
  }
  return picturesInFlight.get(key);
}

async function fetchPicture(f, q) {
  const framePath = `instances/${f.instance}/frames/${f.frame}`;
  try {
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
  // A frame of a multi-frame instance comes out of the whole run, not on its own.
  if (f.of > 1 && !Runs.skip.has(f.instance)) {
    const run = await loadRun(serie, f);
    if (run) return runFrame(run, f.frame);
  }
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

/* ---- a run is one file ---------------------------------------------------
   MEASURED by Dada, 9 Sep: cathlab cine "loads really slow, it's just frame
   after frame". One XA run at PMC is 56 frames in a SINGLE instance, and each
   frame asked for alone took 152 ms warm, where 12 fps needs one every 83 ms.
   So a multi-frame instance is asked for whole, once, and its frames are cut
   out of it here; cine, scrubbing and window/level are then local.

   Only under a cap, and the cap is HALF the frame cache: two panes can then
   each hold a run -- a run beside its prior -- without either one evicting the
   other while it plays. PMC's measured run, 56 x 1,478 KB = 81 MB, is under it.
   A run over 96 MB, or one whose size the tags do not give, stays one frame at
   a time, exactly as before.

   The picture still comes first. This starts only behind the frame on screen,
   because the record found a cold instance costs about 24 s whichever route
   asks for it (9 Sep), and one picture is 351 KB against 81 MB for the run.  */
const RUN_MAX_BYTES = FrameCache.maxBytes / 2;

const Runs = {
  inFlight: new Map(),        // instance id -> { job, ctl, frames, got, total, started }
  skip: new Set(),            // instance ids that go one frame at a time
  onChange: null,             // set by the interface: a run moved on, or landed
  /** The run on its way for this instance, once it has actually been asked for. */
  loading(inst) { const r = this.inFlight.get(inst); return r?.started ? r : null; },
  tell(r, now = false) {
    const t = performance.now();
    if (!now && t - (r.told || 0) < 200) return;   // one repaint per 200 ms, not one per network chunk
    r.told = t;
    this.onChange?.(r.inst);
  },
  /** The viewer is closing or opening another study: stop reading, forget refusals. */
  reset() {
    for (const r of this.inFlight.values()) r.ctl.abort();
    this.inFlight.clear();
    this.skip.clear();
  }
};

/** Bytes a whole instance's stored values will take, from its tags; 0 when they do not say. */
function runBytes(serie, f) {
  const g = serie.geom, t = g.tags || {};
  return g.rows * g.cols * f.of * Math.ceil((+t.BitsAllocated || 0) / 8) * (+t.SamplesPerPixel || 1);
}

/**
 * The whole of a multi-frame instance, or null to go one frame at a time.
 * Everyone asking for the same instance shares the one request.
 */
function loadRun(serie, f) {
  const known = Runs.inFlight.get(f.instance);
  if (known) return known.job;
  const r = { inst: f.instance, frames: f.of, got: 0, total: 0, started: false, ctl: new AbortController() };
  Runs.inFlight.set(f.instance, r);
  r.job = (async () => {
    try {
      // The size comes from the tags, asked for when the series was put in a
      // pane. They are normally in by now, and then nothing here waits -- which
      // matters: the run is queued before the prefetch behind it asks for four
      // pictures, rather than after them, a picture's round trip later.
      if (!serie.geomReady) await ensureGeometry(serie);
      const est = runBytes(serie, f);
      if (!est || est > RUN_MAX_BYTES) { Runs.skip.add(f.instance); return null; }
      r.started = true;
      Runs.tell(r, true);
      const buf = await frameGate(() => fetchRun(`instances/${f.instance}/numpy?rescale=0&compress=0`, r), true);
      const px = parseNpy(buf);
      if (px.n !== f.of) throw new Error(`the run holds ${px.n} frames and the listing said ${f.of}`);
      serie.pixelMode = 'yes';
      return FrameCache.putRun(f.instance, { kind: 'run', ...px, frames: [] });
    } catch (e) {
      if (r.ctl.signal.aborted) throw e;             // the viewer closed; there is nothing to fall back to
      // Refused, cut short, or not the shape the listing promised: go one frame
      // at a time, which is exactly what happened before runs existed, and do
      // not ask for this one whole again.
      Runs.skip.add(f.instance);
      return null;
    } finally {
      if (Runs.inFlight.get(f.instance) === r) Runs.inFlight.delete(f.instance);
      Runs.tell(r, true);
    }
  })();
  return r.job;
}

/**
 * Read a run as it arrives, into one buffer sized from Content-Length (MEASURED
 * present on 1.13.0), so the pane can say how far it has got and 81 MB is not
 * held twice while it is put back together.
 */
async function fetchRun(path, r) {
  const res = await fetch(API.url(path), { credentials: 'same-origin', signal: r.ctl.signal });
  if (!res.ok) { const e = new Error(`${res.status} on ${path}`); e.status = res.status; throw e; }
  // The estimate came from the tags; this is what the archive says it will
  // actually send, and it is held to the cap BEFORE the body is read.
  const encoded = !/^(identity)?$/i.test(res.headers.get('Content-Encoding') || '');
  const total = encoded ? 0 : +res.headers.get('Content-Length') || 0;
  if (total > RUN_MAX_BYTES + 4096) { res.body?.cancel().catch(() => {}); throw new Error(`the run is ${bytes(total)}, over the cap`); }
  if (!total || !res.body) return res.arrayBuffer();
  r.total = total;
  const out = new Uint8Array(total), reader = res.body.getReader();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    if (r.got + value.length > total) { reader.cancel().catch(() => {}); throw new Error('the archive sent more than it announced'); }
    out.set(value, r.got);
    r.got += value.length;
    Runs.tell(r);
  }
  if (r.got !== total) throw new Error(`the run arrived short: ${r.got} of ${total} bytes`);
  return out.buffer;
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
    // NumberOfFrames is in the listing's own MainDicomTags for a multi-frame
    // instance and absent for a single frame (MEASURED, 1.13.0, 23 Sep 2026).
    const n = Math.max(1, +inst.MainDicomTags?.NumberOfFrames || 1);
    for (let f = 0; f < n; f++) frames.push({ instance: inst.ID, frame: f, of: n, inst });   // frame f of n
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

/** Read the series' geometry once, when something actually needs it. Whoever
    asks while it is on its way waits for it, rather than being handed the
    placeholder -- the run's size check reads rows and columns from it. */
async function ensureGeometry(serie) {
  if (serie.tagsLoaded || !serie.frames.length) return serie.geomJob || serie.geom;
  serie.tagsLoaded = true;
  serie.geomJob = (async () => {
    const first = serie.frames[0];
    const tags = await API.get(`instances/${first.instance}/simplified-tags`).catch(() => ({}));
    const fresh = seriesGeometry(tags, serie.row.MainDicomTags || {});
    // Keep any window the user has already dialled in on this series.
    fresh.wcNow = serie.geom.wcNow; fresh.wwNow = serie.geom.wwNow;
    serie.geom = fresh;
    serie.geomReady = true;
    return fresh;
  })();
  return serie.geomJob;
}
