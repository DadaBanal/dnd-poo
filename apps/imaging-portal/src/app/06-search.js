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
  try { return await API.post('tools/find', body); }
  catch (e) {
    if (!(e instanceof ApiError) || e.status !== 400) throw e;
    // older index backends reject the optional keys — retry with the plain form
    const { RequestedTags, Limit, ...plain } = body;
    return API.post('tools/find', plain);
  }
}
function sortStudies() {
  const k = state.sort.key, dir = state.sort.dir;
  const val = s => k === 'date' ? (s.dateRaw + (s.raw.MainDicomTags?.StudyTime || ''))
    : k === 'name' ? s.name.toLowerCase() : k === 'mod' ? (s.mod[0] || '')
    : k === 'desc' ? s.desc.toLowerCase() : k === 'acc' ? s.acc : s.pid;
  state.studies.sort((a, b) => { const x = val(a), y = val(b); return x < y ? -dir : x > y ? dir : 0; });
}

