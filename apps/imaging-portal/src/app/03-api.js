/* ---- the archive connection --------------------------------------------- */
class ApiError extends Error {
  constructor(status, body, path) { super(`${status} on ${path}`); this.status = status; this.body = body; this.path = path; }
}
const Live = {
  base: '/',
  url(p) { return new URL(String(p).replace(/^\//, ''), this.base).href; },
  async req(path, { method = 'GET', body, signal, timeout = 25000 } = {}) {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(new Error('timeout')), timeout);
    if (signal) signal.addEventListener('abort', () => ctl.abort(signal.reason), { once: true });
    try {
      const r = await fetch(this.url(path), {
        method, credentials: 'same-origin', signal: ctl.signal,
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined
      });
      if (!r.ok) throw new ApiError(r.status, (await r.text().catch(() => '')).slice(0, 400), path);
      const txt = await r.text();
      return txt ? JSON.parse(txt) : null;
    } finally { clearTimeout(t); }
  },
  get(p, o) { return this.req(p, o); },
  post(p, body, o) { return this.req(p, { ...o, method: 'POST', body }); }
};

/**
 * List child resources as OBJECTS, whatever shape the server answers with.
 *
 * MEASURED 9 Sep 2026 against PMC's cathlab archive: a bare GET of a child
 * route can come back as an array of bare id STRINGS rather than expanded
 * objects. Code that then reads `.ID` off a string gets undefined and asks for
 * `series//instances`, which is a 404 carrying no clue about what went wrong.
 * Asking for ?expand settles it on every build that honours the parameter; the
 * string form is still handled, because a listing that silently yields nothing
 * is the worst of the three outcomes.
 */
async function listChildren(path) {
  const rows = await API.get(`${path}?expand`);
  if (!Array.isArray(rows)) return [];
  if (!rows.length || typeof rows[0] !== 'string') return rows;
  // The server ignored ?expand. Resolve each id, four at a time; past the cap
  // return stubs rather than a thousand requests, and say so in the console.
  const kind = path.split('/').pop();               // 'series' or 'instances'
  const CAP = 400;
  if (rows.length > CAP) console.warn(`[PMC] ${path} returned ${rows.length} ids unexpanded; resolving the first ${CAP}`);
  const head = rows.slice(0, CAP), tail = rows.slice(CAP).map(ID => ({ ID }));
  const gate4 = (() => { let n = 0; const q = [];
    const next = () => { if (n >= 4 || !q.length) return; n++; q.shift()().finally(() => { n--; next(); }); };
    return fn => new Promise((res, rej) => { q.push(() => fn().then(res, rej)); next(); }); })();
  const got = await Promise.all(head.map(ID => gate4(() => API.get(`${kind}/${ID}`)).catch(() => ({ ID }))));
  return [...got, ...tail];
}

