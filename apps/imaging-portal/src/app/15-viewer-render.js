/* ===========================================================================
   PMC Viewer — painting
   Everything a pane shows is drawn onto one canvas: the image, the
   measurements and the corner overlay. That is deliberate. It means "Save
   image" is the canvas itself, so what is exported is exactly what was read,
   identifiers and window included — an exported frame that does not say whose
   it is has caused more trouble in this hospital than one that does.
   =========================================================================== */

/** The DICOM linear VOI LUT, PS3.3 C.11.2.1.2, as a lookup table.
    Building it once per window change turns the per-pixel cost into an index. */
function buildLut(pane, min, max) {
  const g = pane.serie.geom;
  const wc = pane.wc, ww = Math.max(1, pane.ww);
  const lo = wc - 0.5 - (ww - 1) / 2, span = ww - 1;
  const n = max - min + 1;
  const lut = new Uint8ClampedArray(n);
  for (let i = 0; i < n; i++) {
    const value = (i + min) * g.slope + g.intercept;
    let v = ((value - lo) / span) * 255;
    v = v <= 0 ? 0 : v >= 255 ? 255 : v;
    if (g.mono1) v = 255 - v;                 // MONOCHROME1: high stored value is black
    lut[i] = pane.invert ? 255 - v : v;
  }
  return { lut, min };
}

/** Turn a stored-value frame into an offscreen 8-bit canvas at 1:1. */
function paintPixels(pane, frame) {
  const { data, w, h, ch } = frame;
  const key = [pane.frameKey, pane.wc, pane.ww, pane.invert, pane.sharpen].join('|');
  if (pane.off && pane.offKey === key && pane.off.width === w && pane.off.height === h) return pane.off;
  const cv = pane.off || (pane.off = document.createElement('canvas'));
  if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
  const cx = cv.getContext('2d', { willReadFrequently: false });
  const img = cx.createImageData(w, h);
  const out = img.data;
  if (ch >= 3) {                              // colour: windowing does not apply
    for (let i = 0, p = 0; i < w * h; i++, p += 4) {
      out[p] = data[i * ch]; out[p + 1] = data[i * ch + 1]; out[p + 2] = data[i * ch + 2]; out[p + 3] = 255;
      if (pane.invert) { out[p] = 255 - out[p]; out[p + 1] = 255 - out[p + 1]; out[p + 2] = 255 - out[p + 2]; }
    }
  } else {
    let min = Infinity, max = -Infinity;
    for (let i = 0; i < data.length; i++) { const v = data[i]; if (v < min) min = v; if (v > max) max = v; }
    if (!Number.isFinite(min)) { min = 0; max = 1; }
    const { lut } = buildLut(pane, min, max);
    for (let i = 0, p = 0; i < w * h; i++, p += 4) {
      const g = lut[data[i] - min];
      out[p] = g; out[p + 1] = g; out[p + 2] = g; out[p + 3] = 255;
    }
  }
  if (pane.sharpen) convolve(img, KERNELS[pane.sharpen], w, h);
  cx.putImageData(img, 0, 0);
  pane.offKey = key;
  return cv;
}

/* Enhancement runs on the 8-bit result, never on the stored values: a sharpened
   pixel is no longer a measurement, and the probe and region statistics read the
   stored array, so they stay unaffected by whatever this does. */
const KERNELS = { 1: [0, -1, 0, -1, 5, -1, 0, -1, 0], 2: [1, 2, 1, 2, 4, 2, 1, 2, 1] };
function convolve(img, k, w, h) {
  const src = new Uint8ClampedArray(img.data);
  const out = img.data;
  const div = k.reduce((a, b) => a + b, 0) || 1;
  for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) {
    let acc = 0, n = 0;
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++, n++) {
      acc += src[((y + dy) * w + (x + dx)) * 4] * k[n];
    }
    const p = (y * w + x) * 4, v = acc / div;
    out[p] = out[p + 1] = out[p + 2] = v;
  }
}

/** Screen pixels per millimetre, if the display has been calibrated. */
function pxPerMm() {
  const cal = store.get('viewer.pxPerMm', null);
  return cal && cal > 0 ? { value: cal, calibrated: true }
    : { value: 96 / 25.4, calibrated: false };   // the CSS reference pixel, not this monitor
}

/** Build the pane transform: pan, rotate, flip, zoom, anisotropic spacing. */
function paneMatrix(pane, cw, ch) {
  const g = pane.serie.geom;
  const aspect = g.spacing ? g.spacing[0] / g.spacing[1] : 1;   // rows / columns
  const m = new DOMMatrix();
  m.translateSelf(cw / 2 + pane.panX, ch / 2 + pane.panY);
  m.rotateSelf(pane.rot);
  m.scaleSelf(pane.flipH ? -1 : 1, pane.flipV ? -1 : 1);
  m.scaleSelf(pane.zoom, pane.zoom * aspect);
  m.translateSelf(-pane.imgW / 2, -pane.imgH / 2);
  return m;
}
const screenToImage = (pane, x, y) => {
  const p = pane.matrix.inverse().transformPoint(new DOMPoint(x, y));
  return { x: p.x, y: p.y };
};
const imageToScreen = (pane, x, y) => {
  const p = pane.matrix.transformPoint(new DOMPoint(x, y));
  return { x: p.x, y: p.y };
};

/** The zoom at which the frame just fits, accounting for rotation and spacing. */
function fitZoom(pane, cw, ch) {
  const g = pane.serie.geom;
  const aspect = g.spacing ? g.spacing[0] / g.spacing[1] : 1;
  const w = pane.imgW, h = pane.imgH * aspect;
  const [bw, bh] = (pane.rot / 90) % 2 ? [h, w] : [w, h];
  return Math.min((cw - 16) / bw, (ch - 16) / bh) || 1;
}

const OVERLAY_FONT = '12px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';

/** Draw one pane end to end. Cheap enough to call on every interaction frame. */
function paintPane(pane) {
  const cv = pane.canvas, dpr = Math.min(devicePixelRatio || 1, 2);
  const cw = cv.clientWidth, ch = cv.clientHeight;
  if (!cw || !ch) return;
  if (cv.width !== Math.round(cw * dpr) || cv.height !== Math.round(ch * dpr)) {
    cv.width = Math.round(cw * dpr); cv.height = Math.round(ch * dpr);
  }
  const ctx = cv.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, cw, ch);

  const frame = pane.frame;
  if (!frame) {
    ctx.fillStyle = 'rgba(255,255,255,.45)'; ctx.font = OVERLAY_FONT; ctx.textAlign = 'center';
    ctx.fillText(pane.error || 'loading…', cw / 2, ch / 2);
    drawPaneChrome(pane, ctx, cw, ch);
    return;
  }
  pane.imgW = frame.w; pane.imgH = frame.h;
  if (pane.zoom == null) { pane.zoom = fitZoom(pane, cw, ch); pane.fitted = true; }
  if (pane.fitted) pane.zoom = fitZoom(pane, cw, ch);

  const src = frame.kind === 'pixels' ? paintPixels(pane, frame) : frame.img;
  const m = pane.matrix = paneMatrix(pane, cw, ch);

  ctx.save();
  ctx.setTransform(dpr * m.a, dpr * m.b, dpr * m.c, dpr * m.d, dpr * m.e, dpr * m.f);
  // Nearest-neighbour above 2x: a diagnostic reader wants to see the pixels, not
  // an interpolation of them. Below that, smoothing avoids a blocky downscale.
  ctx.imageSmoothingEnabled = pane.zoom < 2;
  ctx.imageSmoothingQuality = 'high';
  // A frame served by /preview or /rendered is already 8-bit; inverting it here
  // keeps the button honest on every path.
  if (frame.kind !== 'pixels' && pane.invert) ctx.filter = 'invert(1)';
  ctx.drawImage(src, 0, 0);
  ctx.filter = 'none';
  ctx.restore();

  drawAnnotations(pane, ctx);
  drawCrosshair(pane, ctx, cw, ch);
  if (pane.loupe) drawLoupe(pane, ctx, src, cw, ch);
  drawPaneChrome(pane, ctx, cw, ch);
}

/** A magnifier under the cursor: the pixels at 4x, without moving the view. */
function drawLoupe(pane, ctx, src, cw, ch) {
  const R = Math.min(96, Math.max(56, Math.min(cw, ch) / 5));
  const { x, y } = pane.loupe;
  const p = screenToImage(pane, x, y);
  ctx.save();
  ctx.beginPath(); ctx.arc(x, y, R, 0, Math.PI * 2); ctx.clip();
  ctx.fillStyle = '#000'; ctx.fillRect(x - R, y - R, R * 2, R * 2);
  const scale = 4;
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(src, x - p.x * scale, y - p.y * scale, pane.imgW * scale, pane.imgH * scale);
  ctx.restore();
  ctx.save();
  ctx.beginPath(); ctx.arc(x, y, R, 0, Math.PI * 2);
  ctx.strokeStyle = 'rgba(150,210,255,.9)'; ctx.lineWidth = 1.5; ctx.stroke();
  ctx.beginPath(); ctx.moveTo(x - 6, y); ctx.lineTo(x + 6, y); ctx.moveTo(x, y - 6); ctx.lineTo(x, y + 6);
  ctx.strokeStyle = 'rgba(255,255,255,.55)'; ctx.stroke();
  ctx.restore();
}

/** Corner text, scale bar, orientation letters, active-pane border. */
function drawPaneChrome(pane, ctx, cw, ch) {
  const s = V.study, g = pane.serie?.geom || {};
  ctx.save();
  ctx.font = OVERLAY_FONT;
  ctx.textBaseline = 'top';
  ctx.shadowColor = 'rgba(0,0,0,.9)'; ctx.shadowBlur = 3;
  const line = (text, x, y, align) => { ctx.textAlign = align; ctx.fillText(text, x, y); };

  if (V.overlay && s) {
    const n = pane.serie ? pane.serie.frames.length : 0;
    const tl = [s.name, `${s.pid}${s.sex ? '  ' + s.sex : ''}${age(s.dob, s.date) ? '  ' + age(s.dob, s.date) : ''}`,
      s.dob ? `DOB ${s.dob.slice(0, 4)}-${s.dob.slice(4, 6)}-${s.dob.slice(6, 8)}` : ''].filter(Boolean);
    const tr = [s.desc || '', s.acc ? `Acc ${s.acc}` : '', s.date ? s.date.toLocaleString() : ''].filter(Boolean);
    const bl = [`Se ${pane.serie?.number || '?'}  ${pane.serie?.desc || ''}`.trim(),
      `Im ${pane.index + 1} / ${n}`,
      [g.thickness ? `${g.thickness} mm` : '', g.kvp ? `${g.kvp} kV` : '', g.mas ? `${g.mas} mA` : ''].filter(Boolean).join('  ')]
      .filter(Boolean);
    const wl = pane.frame?.kind === 'pixels' || pane.serie?.mode === 'rendered'
      ? `W ${Math.round(pane.ww)}  L ${Math.round(pane.wc)}` : 'W/L fixed (preview)';
    const br = [wl, `Zoom ${Math.round(pane.zoom * 100)}%`,
      `${pane.serie?.modality || ''} · ${MODE_LABEL[pane.serie?.mode] || pane.serie?.mode || ''}`].filter(Boolean);

    ctx.fillStyle = 'rgba(255,255,255,.92)';
    tl.forEach((t, i) => line(t, 10, 8 + i * 15, 'left'));
    tr.forEach((t, i) => line(t, cw - 10, 8 + i * 15, 'right'));
    ctx.textBaseline = 'bottom';
    bl.forEach((t, i) => line(t, 10, ch - 8 - (bl.length - 1 - i) * 15, 'left'));
    br.forEach((t, i) => line(t, cw - 10, ch - 8 - (br.length - 1 - i) * 15, 'right'));
    ctx.textBaseline = 'top';
    drawOrientation(pane, ctx, cw, ch, g);
    drawScaleBar(pane, ctx, cw, ch, g);
  }
  ctx.restore();

  if (V.panes.length > 1) {
    ctx.save();
    ctx.strokeStyle = pane.i === V.active ? 'rgba(120,190,255,.95)' : 'rgba(255,255,255,.14)';
    ctx.lineWidth = pane.i === V.active ? 2 : 1;
    ctx.strokeRect(0.5, 0.5, cw - 1, ch - 1);
    ctx.restore();
  }
}
const MODE_LABEL = { pixels: 'pixel data', rendered: 'server rendered', preview: 'preview only',
  sample: 'SAMPLE DATA — not a patient', auto: '…' };

/** L/R/A/P/H/F at the edges, derived from ImageOrientationPatient. */
function drawOrientation(pane, ctx, cw, ch, g) {
  if (!g.orientation) return;
  const [rx, ry, rz, cx, cy, cz] = g.orientation;
  const letter = (x, y, z) => {
    const parts = [[x, 'L', 'R'], [y, 'P', 'A'], [z, 'H', 'F']]
      .filter(([v]) => Math.abs(v) > 0.2)
      .sort((a, b) => Math.abs(b[0]) - Math.abs(a[0]));
    return parts.map(([v, pos, neg]) => (v > 0 ? pos : neg)).join('').slice(0, 2);
  };
  // Image-space +x is the row direction, +y the column direction; the pane may
  // have rotated or flipped either of them, so ask the matrix rather than assume.
  const o = imageToScreen(pane, pane.imgW / 2, pane.imgH / 2);
  const px = imageToScreen(pane, pane.imgW, pane.imgH / 2);
  const py = imageToScreen(pane, pane.imgW / 2, pane.imgH);
  const marks = [
    [letter(rx, ry, rz), px.x - o.x, px.y - o.y],
    [letter(-rx, -ry, -rz), o.x - px.x, o.y - px.y],
    [letter(cx, cy, cz), py.x - o.x, py.y - o.y],
    [letter(-cx, -cy, -cz), o.x - py.x, o.y - py.y]
  ];
  ctx.fillStyle = 'rgba(150,210,255,.9)';
  for (const [text, dx, dy] of marks) {
    if (!text) continue;
    const len = Math.hypot(dx, dy) || 1;
    const x = cw / 2 + (dx / len) * (Math.min(cw, ch) / 2 - 22);
    const y = ch / 2 + (dy / len) * (Math.min(cw, ch) / 2 - 22);
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(text, x, y);
  }
  ctx.textBaseline = 'top';
}

/** A bar of a round number of millimetres — only when the pixels are calibrated. */
function drawScaleBar(pane, ctx, cw, ch, g) {
  if (!g.spacing) return;
  const pxPerMmX = pane.zoom / g.spacing[1];
  const want = Math.min(cw * 0.28, 180);
  const nice = [1, 2, 5, 10, 20, 50, 100, 200, 500];
  const mm = nice.reduce((best, n) => Math.abs(n * pxPerMmX - want) < Math.abs(best * pxPerMmX - want) ? n : best, nice[0]);
  const len = mm * pxPerMmX;
  if (!(len > 12 && len < cw * 0.6)) return;
  const x = cw / 2 - len / 2, y = ch - 26;
  ctx.strokeStyle = 'rgba(255,255,255,.9)'; ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(x, y - 4); ctx.lineTo(x, y + 4); ctx.moveTo(x, y); ctx.lineTo(x + len, y);
  ctx.moveTo(x + len, y - 4); ctx.lineTo(x + len, y + 4);
  ctx.stroke();
  ctx.fillStyle = 'rgba(255,255,255,.9)'; ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
  ctx.fillText(`${mm} mm`, cw / 2, y - 5);
  ctx.textBaseline = 'top';
}
