/* ===========================================================================
   PMC Viewer — measurement and interrogation
   Annotations are held in IMAGE space, so zooming, panning, rotating or
   flipping cannot move a measurement relative to the anatomy it was drawn on.
   Statistics are computed from stored values through RescaleSlope/Intercept,
   and are simply refused when the pane is running on a rendered PNG — an 8-bit
   PNG has no Hounsfield units in it, and a number invented from one would be
   worse than no number.
   =========================================================================== */

const noteKey = pane => `${pane.serie?.id}#${pane.index}`;
const notesFor = pane => {
  const k = noteKey(pane);
  if (!V.notes.has(k)) V.notes.set(k, []);
  return V.notes.get(k);
};

/** Stored value -> the modality's own units (HU for CT), plus how to say it. */
function pixelValue(pane, ix, iy) {
  const f = pane.frame;
  if (!f || f.kind !== 'pixels') return null;
  const x = Math.floor(ix), y = Math.floor(iy);
  if (x < 0 || y < 0 || x >= f.w || y >= f.h) return null;
  const g = pane.serie.geom;
  const stored = f.ch >= 3 ? f.data[(y * f.w + x) * f.ch] : f.data[y * f.w + x];
  // x and y travel with the value: the readout used to round the cursor for
  // display and floor it for sampling, so on a pixel boundary it named one
  // pixel and reported its neighbour's number.
  return { x, y, stored, value: stored * g.slope + g.intercept, unit: g.unit };
}

/** Millimetres between two image-space points, or null when uncalibrated. */
function mmBetween(pane, a, b) {
  const sp = pane.serie.geom.spacing;
  if (!sp) return null;
  return Math.hypot((b.x - a.x) * sp[1], (b.y - a.y) * sp[0]);
}

/** Mean, SD, min, max and area over a region, in the modality's units. */
function regionStats(pane, test, bounds) {
  const f = pane.frame;
  const g = pane.serie.geom;
  const x0 = Math.max(0, Math.floor(bounds.x0)), x1 = Math.min((f?.w ?? 0) - 1, Math.ceil(bounds.x1));
  const y0 = Math.max(0, Math.floor(bounds.y0)), y1 = Math.min((f?.h ?? 0) - 1, Math.ceil(bounds.y1));
  const areaPx = Math.max(0, (bounds.x1 - bounds.x0)) * Math.max(0, (bounds.y1 - bounds.y0));
  if (!f || f.kind !== 'pixels') return { n: 0, pixels: false, areaPx };
  let n = 0, sum = 0, sumsq = 0, min = Infinity, max = -Infinity;
  for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
    if (!test(x + 0.5, y + 0.5)) continue;
    const stored = f.ch >= 3 ? f.data[(y * f.w + x) * f.ch] : f.data[y * f.w + x];
    const v = stored * g.slope + g.intercept;
    n++; sum += v; sumsq += v * v;
    if (v < min) min = v; if (v > max) max = v;
  }
  if (!n) return { n: 0, pixels: true, areaPx };
  const mean = sum / n;
  return { n, pixels: true, mean, sd: Math.sqrt(Math.max(0, sumsq / n - mean * mean)), min, max, areaPx, unit: g.unit };
}

const fmt = (v, d = 1) => (Math.abs(v) >= 1000 ? Math.round(v) : Number(v.toFixed(d)));

/** The label a finished annotation carries. */
function annotationLabel(pane, a) {
  const g = pane.serie.geom;
  const areaMm = (px) => g.spacing ? `${fmt(px * g.spacing[0] * g.spacing[1] / 100, 2)} cm²` : `${Math.round(px)} px²`;
  const statLine = st => !st.pixels ? 'pixel data not loaded'
    : !st.n ? 'empty'
    : `${fmt(st.mean)} ± ${fmt(st.sd)} ${st.unit || ''}`.trim() + `  (${fmt(st.min, 0)}…${fmt(st.max, 0)})`;
  if (a.type === 'length') {
    const mm = mmBetween(pane, a.pts[0], a.pts[1]);
    return mm == null ? `${Math.round(Math.hypot(a.pts[1].x - a.pts[0].x, a.pts[1].y - a.pts[0].y))} px (uncalibrated)`
      : mm >= 10 ? `${fmt(mm / 10, 2)} cm` : `${fmt(mm)} mm`;
  }
  if (a.type === 'angle' && a.pts.length >= 3) {
    const [p0, p1, p2] = a.pts;
    const sp = g.spacing || [1, 1];
    const v1 = { x: (p0.x - p1.x) * sp[1], y: (p0.y - p1.y) * sp[0] };
    const v2 = { x: (p2.x - p1.x) * sp[1], y: (p2.y - p1.y) * sp[0] };
    const cos = (v1.x * v2.x + v1.y * v2.y) / ((Math.hypot(v1.x, v1.y) * Math.hypot(v2.x, v2.y)) || 1);
    return `${fmt(Math.acos(Math.max(-1, Math.min(1, cos))) * 180 / Math.PI)}°`;
  }
  if (a.type === 'rect') {
    const [p, q] = a.pts;
    const b = { x0: Math.min(p.x, q.x), x1: Math.max(p.x, q.x), y0: Math.min(p.y, q.y), y1: Math.max(p.y, q.y) };
    const st = regionStats(pane, () => true, b);
    return `${areaMm((b.x1 - b.x0) * (b.y1 - b.y0))}  ${statLine(st)}`;
  }
  if (a.type === 'ellipse') {
    const [p, q] = a.pts;
    const cx = (p.x + q.x) / 2, cy = (p.y + q.y) / 2;
    const rx = Math.abs(q.x - p.x) / 2, ry = Math.abs(q.y - p.y) / 2;
    const b = { x0: cx - rx, x1: cx + rx, y0: cy - ry, y1: cy + ry };
    const inside = (x, y) => ((x - cx) / (rx || 1)) ** 2 + ((y - cy) / (ry || 1)) ** 2 <= 1;
    const st = regionStats(pane, inside, b);
    return `${areaMm(Math.PI * rx * ry)}  ${statLine(st)}`;
  }
  if (a.type === 'text' || a.type === 'arrow') return a.label || '';
  return '';
}

const NOTE_COLOUR = 'rgba(126, 231, 135, .95)';
const NOTE_ACTIVE = 'rgba(255, 214, 102, .98)';

function drawAnnotations(pane, ctx) {
  const list = V.notes.get(noteKey(pane)) || [];
  const all = pane.draft ? [...list, pane.draft] : list;
  if (!all.length) return;
  ctx.save();
  ctx.font = '12px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
  ctx.textBaseline = 'bottom';
  ctx.textAlign = 'left';
  ctx.shadowColor = 'rgba(0,0,0,.9)'; ctx.shadowBlur = 3;
  ctx.lineWidth = 1.6;
  for (const a of all) {
    const on = a === pane.draft || a === V.selected;
    ctx.strokeStyle = on ? NOTE_ACTIVE : NOTE_COLOUR;
    ctx.fillStyle = ctx.strokeStyle;
    const S = a.pts.map(p => imageToScreen(pane, p.x, p.y));
    ctx.beginPath();
    if (a.type === 'length' && S.length > 1) {
      ctx.moveTo(S[0].x, S[0].y); ctx.lineTo(S[1].x, S[1].y);
    } else if (a.type === 'angle' && S.length > 1) {
      ctx.moveTo(S[0].x, S[0].y); ctx.lineTo(S[1].x, S[1].y);
      if (S[2]) ctx.lineTo(S[2].x, S[2].y);
    } else if (a.type === 'rect' && S.length > 1) {
      ctx.rect(Math.min(S[0].x, S[1].x), Math.min(S[0].y, S[1].y), Math.abs(S[1].x - S[0].x), Math.abs(S[1].y - S[0].y));
    } else if (a.type === 'ellipse' && S.length > 1) {
      ctx.ellipse((S[0].x + S[1].x) / 2, (S[0].y + S[1].y) / 2,
        Math.abs(S[1].x - S[0].x) / 2, Math.abs(S[1].y - S[0].y) / 2, 0, 0, Math.PI * 2);
    } else if (a.type === 'arrow' && S.length > 1) {
      ctx.moveTo(S[0].x, S[0].y); ctx.lineTo(S[1].x, S[1].y);
      const ang = Math.atan2(S[1].y - S[0].y, S[1].x - S[0].x);
      for (const t of [2.6, -2.6]) {
        ctx.moveTo(S[1].x, S[1].y);
        ctx.lineTo(S[1].x + Math.cos(ang + t) * 9, S[1].y + Math.sin(ang + t) * 9);
      }
    }
    ctx.stroke();
    for (const p of S) { ctx.beginPath(); ctx.arc(p.x, p.y, 2.6, 0, Math.PI * 2); ctx.fill(); }
    const text = a.type === 'text' ? (a.label || '') : annotationLabel(pane, a);
    if (text) {
      const anchor = S[S.length - 1];
      const w = ctx.measureText(text).width;
      ctx.fillStyle = 'rgba(0,0,0,.55)';
      ctx.fillRect(anchor.x + 6, anchor.y - 16, w + 8, 16);
      ctx.fillStyle = on ? NOTE_ACTIVE : NOTE_COLOUR;
      ctx.fillText(text, anchor.x + 10, anchor.y - 3);
    }
  }
  ctx.restore();
}

/** Which annotation, if any, is under the cursor — for select and delete. */
function hitAnnotation(pane, sx, sy) {
  const list = V.notes.get(noteKey(pane)) || [];
  for (let i = list.length - 1; i >= 0; i--) {
    const S = list[i].pts.map(p => imageToScreen(pane, p.x, p.y));
    if (S.some(p => Math.hypot(p.x - sx, p.y - sy) < 8)) return list[i];
    for (let k = 1; k < S.length; k++) {
      const a = S[k - 1], b = S[k];
      const l2 = (b.x - a.x) ** 2 + (b.y - a.y) ** 2 || 1;
      const t = Math.max(0, Math.min(1, ((sx - a.x) * (b.x - a.x) + (sy - a.y) * (b.y - a.y)) / l2));
      if (Math.hypot(sx - (a.x + t * (b.x - a.x)), sy - (a.y + t * (b.y - a.y))) < 6) return list[i];
    }
  }
  return null;
}
