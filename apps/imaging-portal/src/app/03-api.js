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

