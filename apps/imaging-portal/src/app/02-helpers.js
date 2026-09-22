/* ---- tiny helpers ------------------------------------------------------- */
const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pad = n => String(n).padStart(2, '0');
const ymd = d => `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}`;
const bytes = n => { if (!n && n !== 0) return '—'; const u = ['B','KB','MB','GB','TB']; let i = 0; n = +n;
  while (n >= 1024 && i < u.length-1) { n /= 1024; i++; } return `${n < 10 && i ? n.toFixed(1) : Math.round(n)} ${u[i]}`; };

/** DICOM PN "DELA CRUZ^JUAN^^^" -> "Dela Cruz, Juan" */
function personName(pn) {
  if (!pn) return '(no name)';
  const [fam = '', giv = '', mid = ''] = String(pn).split('^');
  const t = s => s.trim().replace(/\s+/g,' ').replace(/\S+/g, w => w[0].toUpperCase() + w.slice(1).toLowerCase());
  const left = t(fam), right = [t(giv), t(mid)].filter(Boolean).join(' ');
  return right ? `${left}, ${right}` : (left || String(pn));
}
/** DICOM DA + TM -> Date */
function dicomDate(da, tm) {
  if (!da || da.length < 8) return null;
  const d = new Date(+da.slice(0,4), +da.slice(4,6)-1, +da.slice(6,8),
    tm ? +tm.slice(0,2) || 0 : 0, tm ? +tm.slice(2,4) || 0 : 0, tm ? +tm.slice(4,6) || 0 : 0);
  return isNaN(d) ? null : d;
}
function when(d) {
  if (!d) return '—';
  const now = new Date(), day = 864e5;
  const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const diff = Math.floor((midnight - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / day);
  const hm = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  if (diff === 0) return `Today ${hm}`;
  if (diff === 1) return `Yesterday ${hm}`;
  if (diff < 7 && diff > 0) return `${d.toLocaleDateString(undefined,{weekday:'short'})} ${hm}`;
  return d.toLocaleDateString(undefined,{day:'2-digit', month:'short', year:'numeric'});
}
function age(dob, on) {
  if (!dob || dob.length < 8) return '';
  const b = dicomDate(dob); if (!b) return '';
  const ref = on || new Date();
  let a = ref.getFullYear() - b.getFullYear();
  if (ref.getMonth() < b.getMonth() || (ref.getMonth() === b.getMonth() && ref.getDate() < b.getDate())) a--;
  return a >= 0 && a < 130 ? `${a} y` : '';
}
function toast(msg, kind = '') {
  const el = document.createElement('div');
  el.className = `toast ${kind}`; el.textContent = msg;
  $('#toasts').append(el);
  setTimeout(() => { el.style.transition = 'opacity .25s, transform .25s'; el.style.opacity = '0'; el.style.transform = 'translateY(6px)';
    setTimeout(() => el.remove(), 260); }, kind === 'bad' ? 6000 : 3200);
}
const store = {
  get(k, d) { try { const v = localStorage.getItem('pmc.' + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('pmc.' + k, JSON.stringify(v)); } catch {} }
};

