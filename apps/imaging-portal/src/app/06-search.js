/* ---- the search --------------------------------------------------------- */
function scopeQuery(scope) {
  const now = new Date(), day = 864e5;
  if (scope === 'today') return ymd(now);
  if (scope === 'yesterday') return ymd(new Date(now - day));
  if (scope === '7')  return `${ymd(new Date(now - 6 * day))}-${ymd(now)}`;
  if (scope === '30') return `${ymd(new Date(now - 29 * day))}-${ymd(now)}`;
  return null;
}
/** Orthanc's find ANDs its criteria, so an "any field" search is a small fan-out. */
function queryPlan() {
  const base = {};
  const sd = scopeQuery(state.scope); if (sd) base.StudyDate = sd;
  if (state.mod) base.ModalitiesInStudy = state.mod;
  const term = state.q.trim();
  if (!term) return [base];
  const w = `*${term}*`;
  const plans = [{ ...base, PatientName: w.toUpperCase() }, { ...base, PatientID: w }, { ...base, AccessionNumber: w }];
  if (/^[\d.]+$/.test(term)) plans.push({ ...base, StudyInstanceUID: term });
  return plans;
}
let searchToken = 0;
async function loadStudies() {
  const token = ++searchToken;
  paintSkeletons();
  const t0 = performance.now();
  const plans = queryPlan();
  const seen = new Map();
  let degraded = null;
  try {
    const results = await Promise.all(plans.map(q => findStudies(q).catch(e => { degraded = e; return []; })));
    if (token !== searchToken) return;
    for (const arr of results) for (const s of arr) if (!seen.has(s.ID)) seen.set(s.ID, s);
    state.studies = [...seen.values()].map(norm);
    state.took = Math.round(performance.now() - t0);
    if (!state.studies.length && degraded) throw degraded;
    sortStudies(); state.cursor = -1; render(); showBanner(degraded);
  } catch (e) {
    if (token !== searchToken) return;
    renderError(e);
  }
}
async function findStudies(Query) {
  const body = { Level: 'Study', Expand: true, Query,
    RequestedTags: ['ModalitiesInStudy','NumberOfStudyRelatedSeries','NumberOfStudyRelatedInstances'],
    Limit: CFG.pageSize };
  let rows;
  try { rows = await API.post('tools/find', body); }
  catch (e) {
    // The ODBC index refuses what it calls the ExtendedFind keys. It answers 400
    // on some builds and 500 on others -- OrderBy is a MEASURED 500 here -- so
    // both get one retry with the plain form before the error is believed.
    if (!(e instanceof ApiError) || (e.status !== 400 && e.status !== 500)) throw e;
    const { RequestedTags, Limit, ...plain } = body;
    rows = await API.post('tools/find', plain);
  }
  return expandStudies(rows);
}

/**
 * `Expand: true` is a request, not a guarantee. An index that ignores it returns
 * bare id strings, and norm() on a string produces a row with no name, no date
 * and no id -- a worklist that looks broken rather than one that says why.
 * Resolve them instead, four at a time, and say so in the console.
 *
 * PMC's ODBC index DOES honour it (MEASURED 9 Sep 2026 on the cathlab archive:
 * /tools/find with Expand and Limit returned expanded objects), so this path
 * costs nothing there. It exists for the next index, not this one.
 */
async function expandStudies(rows) {
  if (!Array.isArray(rows) || !rows.length || typeof rows[0] !== 'string') return rows || [];
  console.warn(`[PMC] the index ignored Expand and returned ${rows.length} ids; resolving them`);
  const head = rows.slice(0, CFG.pageSize);
  const gate4 = (() => { let n = 0; const q = [];
    const next = () => { if (n >= 4 || !q.length) return; n++; q.shift()().finally(() => { n--; next(); }); };
    return fn => new Promise((res, rej) => { q.push(() => fn().then(res, rej)); next(); }); })();
  const got = await Promise.all(head.map(ID => gate4(() => API.get(`studies/${ID}`)).catch(() => null)));
  return got.filter(Boolean);
}
function sortStudies() {
  const k = state.sort.key, dir = state.sort.dir;
  const val = s => k === 'date' ? (s.dateRaw + (s.raw.MainDicomTags?.StudyTime || ''))
    : k === 'name' ? s.name.toLowerCase() : k === 'mod' ? (s.mod[0] || '')
    : k === 'desc' ? s.desc.toLowerCase() : k === 'acc' ? s.acc : s.pid;
  state.studies.sort((a, b) => { const x = val(a), y = val(b); return x < y ? -dir : x > y ? dir : 0; });
}

