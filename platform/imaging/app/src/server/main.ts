// The PMC front door app's server (Path A, M2.3): the worklist's API and the
// page itself, at /pmc/. It sits behind the front door, which signs people in
// and hands over each request's access token; nothing reaches it any other way.
import { readFileSync } from 'node:fs';
import { serve } from '@hono/node-server';
import { serveStatic } from '@hono/node-server/serve-static';
import { Hono } from 'hono';
import { streamSSE } from 'hono/streaming';
import { StudiesQuery } from '../shared/api.ts';
import { EngineError, changesSince, lastChange, worklist } from './engine.ts';
import { bearer, person, signedIn } from './identity.ts';

const PORT = Number(process.env.PORT ?? 8080);
const API_KEY = readFileSync(process.env.API_KEY_SECRET ?? '/run/secrets/svc-platform-api-key', 'utf8').trim();
const STATIC = process.env.STATIC_DIR ?? './dist';

// ---- what changed, for every open page ------------------------------------------
// One poll of the engine's change log for the whole server; each open page
// hears "the studies changed" and asks again with its own token.
type Listener = (version: number) => void;
const listeners = new Set<Listener>();
let version = 0;

async function watchChanges(): Promise<never> {
  let since = -1;
  let failing = false;
  for (;;) {
    try {
      if (since < 0) since = await lastChange(API_KEY);
      const { last, studies } = await changesSince(API_KEY, since);
      since = last;
      if (studies > 0) {
        version += 1;
        for (const tell of listeners) tell(version);
      }
      if (failing) console.log('change log: the engine answers again');
      failing = false;
    } catch (e) {
      // Said once, not every two seconds; the pages fall back to refreshing
      // every minute meanwhile.
      if (!failing) console.warn(`change log: ${(e as Error).message}; retrying`);
      failing = true;
    }
    await new Promise((r) => setTimeout(r, failing ? 10_000 : 2_000));
  }
}

// ---- the API --------------------------------------------------------------------
const api = new Hono();

// For the container's own health check, from inside it; the front door does
// not route it without a session either way.
api.get('/health', (c) => c.json({ ok: true }));

api.use('*', signedIn);

api.get('/me', (c) => {
  const me = person(c);
  return me ? c.json(me) : c.json({ error: 'not a front door token' }, 403);
});

api.get('/studies', async (c) => {
  if (!person(c)) return c.json({ error: 'not a front door token' }, 403);
  const parsed = StudiesQuery.safeParse(c.req.query());
  if (!parsed.success) return c.json({ error: 'bad query' }, 400);
  try {
    return c.json(await worklist(bearer(c), API_KEY, parsed.data));
  } catch (e) {
    if (e instanceof EngineError && (e.status === 401 || e.status === 403)) {
      return c.json({ error: 'the engine refused' }, 403);
    }
    console.warn(`worklist: ${(e as Error).message}`);
    return c.json({ error: 'the engine did not answer' }, 502);
  }
});

// Server-sent events: "the studies changed". A stream lasts ten minutes, then
// the page reconnects through the front door, so a stream never outlives a
// session by long.
api.get('/events', (c) => {
  if (!person(c)) return c.json({ error: 'not a front door token' }, 403);
  // The front door must pass each event on at once, not buffer it.
  c.header('X-Accel-Buffering', 'no');
  return streamSSE(c, async (stream) => {
    const tell: Listener = (v) => void stream.writeSSE({ event: 'studies', data: String(v), id: String(v) });
    listeners.add(tell);
    stream.onAbort(() => {
      listeners.delete(tell);
    });
    await stream.writeSSE({ event: 'hello', data: String(version), retry: 3_000 });
    const until = Date.now() + 10 * 60_000;
    while (!stream.aborted && Date.now() < until) {
      await stream.sleep(25_000);
      if (!stream.aborted) await stream.write(': keep-alive\n\n');
    }
    listeners.delete(tell);
  });
});

// ---- the page -------------------------------------------------------------------
const app = new Hono();

// Built files carry a content hash in their name, so they never change; the
// page itself is checked every time, so a new build shows at the next load.
app.use('/pmc/*', async (c, next) => {
  await next();
  if (c.req.path.startsWith('/pmc/api/')) return;
  c.header('Cache-Control', c.req.path.startsWith('/pmc/assets/') ? 'public, max-age=31536000, immutable' : 'no-cache');
});
app.route('/pmc/api', api);
app.use('/pmc/*', serveStatic({ root: STATIC, rewriteRequestPath: (p) => p.replace(/^\/pmc/, '') }));
// Any other page under /pmc/ is the app itself; it reads the URL.
app.get('/pmc/*', serveStatic({ root: STATIC, path: 'index.html' }));

serve({ fetch: app.fetch, port: PORT, hostname: '0.0.0.0' }, () => {
  console.log(`PMC front door app on :${PORT}`);
});
void watchChanges();
