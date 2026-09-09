/* ---- thumbnails (lazy, throttled) --------------------------------------- */
const gate = (() => { let active = 0; const q = [];
  const next = () => { if (active >= 4 || !q.length) return; active++; const job = q.shift();
    job().finally(() => { active--; next(); }); };
  return fn => new Promise((res, rej) => { q.push(() => fn().then(res, rej)); next(); }); })();
const seenThumbs = new WeakSet();
const io = new IntersectionObserver(es => {
  for (const e of es) if (e.isIntersecting) { io.unobserve(e.target); fillThumb(e.target); }
}, { rootMargin: '220px' });
async function fillThumb(box) {
  if (seenThumbs.has(box)) return; seenThumbs.add(box);
  const id = box.dataset.study, mod = box.dataset.mod || '';
  const img = box.querySelector('img'); if (!img) return;
  const show = src => { img.onerror = () => { img.remove(); }; img.onload = () => img.classList.add('ready'); img.src = src; };
  if (state.demo) { show(Demo.thumb(mod || 'CR', box.dataset.seed || 1)); return; }
  try {
    const series = await gate(() => listChildren(`studies/${id}/series`));
    const withInst = series.find(s => s.Instances?.length);
    if (!withInst) return;
    const iid = withInst.Instances[Math.floor(withInst.Instances.length / 2)] || withInst.Instances[0];
    img.onerror = () => { img.onerror = () => img.remove(); img.src = API.url(`instances/${iid}/frames/0/preview`); };
    img.onload = () => img.classList.add('ready');
    img.src = API.url(`instances/${iid}/preview`);
  } catch { /* placeholder stays */ }
}

