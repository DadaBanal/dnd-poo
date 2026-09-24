// The PMC front door app's server (Path A, M2.3): the worklist's API and the
// page itself, at /pmc/. It sits behind the front door, which signs people in
// and hands over each request's access token; nothing reaches it any other way.
import { readFileSync } from 'node:fs';
import { serve } from '@hono/node-server';
import { serveStatic } from '@hono/node-server/serve-static';
import { Hono, type Context } from 'hono';
import { streamSSE } from 'hono/streaming';
import { READERS, StudiesQuery, type Me } from '../shared/api.ts';
import { auditTrail, claim, claimedBy, claimsFor, opened, release } from './db.ts';
import { EngineError, changesSince, lastChange, visible, worklist } from './engine.ts';
import { bearer, person, signedIn } from './identity.ts';

const PORT = Number(process.env.PORT ?? 8080);
const API_KEY = readFileSync(process.env.API_KEY_SECRET ?? '/run/secrets/svc-platform-api-key', 'utf8').trim();
const STATIC = process.env.STATIC_DIR ?? './dist';
const ORIGIN = `https://${process.env.PMC_HOSTNAME ?? 'imaging.pmcne.ph'}`;
const UID = /^[0-9.]{1,64}$/;

// ---- what changed, for every open page ------------------------------------------
// One poll of the engine's change log for the whole server; each open page
// hears "the studies changed" and asks again with its own token. A claim made
// here is announced the same way.
type Listener = (version: number) => void;
const listeners = new Set<Listener>();
let version = 0;

function announce(): void {
  version += 1;
  for (const tell of listeners) tell(version);
}

async function watchChanges(): Promise<never> {
  let since = -1;
  let failing = false;
  for (;;) {
    try {
      if (since < 0) since = await lastChange(API_KEY);
      const { last, studies } = await changesSince(API_KEY, since);
      since = last;
      if (studies > 0) announce();
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
const api = new Hono<{ Variables: { me: Me } }>();

// For the container's own health check, from inside it; the front door does
// not route it without a session either way.
api.get('/health', (c) => c.json({ ok: true }));

api.use('*', signedIn);
api.use('*', async (c, next) => {
  const me = person(c);
  if (!me) return c.json({ error: 'not a front door token' }, 403);
  // A change is accepted only from this site's own pages. Browsers always say
  // where a POST or DELETE comes from; another site's page cannot pass.
  if (c.req.method !== 'GET' && c.req.header('Origin') !== ORIGIN) {
    return c.json({ error: 'not from this site' }, 403);
  }
  c.set('me', me);
  await next();
});

const fails = (c: Context, e: unknown, what: string) => {
  if (e instanceof EngineError && (e.status === 401 || e.status === 403)) {
    return c.json({ error: 'the engine refused' }, 403);
  }
  console.warn(`${what}: ${(e as Error).message}`);
  return c.json({ error: `${what} failed` }, 502);
};

api.get('/me', (c) => c.json(c.get('me')));

api.get('/studies', async (c) => {
  const me = c.get('me');
  const parsed = StudiesQuery.safeParse(c.req.query());
  if (!parsed.success) return c.json({ error: 'bad query' }, 400);
  try {
    const only = parsed.data.mine ? await claimedBy(me.username, 200) : undefined;
    const answer = await worklist(bearer(c), API_KEY, parsed.data, only);
    const claims = await claimsFor(answer.studies.map((s) => s.studyUid));
    for (const s of answer.studies) s.claim = claims.get(s.studyUid) ?? null;
    return c.json(answer);
  } catch (e) {
    return fails(c, e, 'worklist');
  }
});

// Claiming a study to read it: radiologists and cardiologists, and only a
// study the engine lets them see.
api.post('/studies/:uid/claim', async (c) => {
  const me = c.get('me');
  const uid = c.req.param('uid');
  if (!UID.test(uid)) return c.json({ error: 'not a study UID' }, 400);
  if (!me.roles.some((r) => READERS.includes(r))) return c.json({ error: 'only readers claim studies' }, 403);
  try {
    if (!(await visible(bearer(c), uid))) return c.json({ error: 'no such study' }, 404);
    const result = await claim(uid, me);
    if (!result.ok) return c.json({ error: 'claimed by someone else', claim: result.claim }, 409);
    announce();
    return c.json({ claim: result.claim });
  } catch (e) {
    return fails(c, e, 'claim');
  }
});

api.delete('/studies/:uid/claim', async (c) => {
  const uid = c.req.param('uid');
  if (!UID.test(uid)) return c.json({ error: 'not a study UID' }, 400);
  try {
    if (!(await release(uid, c.get('me')))) return c.json({ error: 'not your claim' }, 409);
    announce();
    return c.body(null, 204);
  } catch (e) {
    return fails(c, e, 'release');
  }
});

// The page says when a person opens a study from the worklist.
api.post('/studies/:uid/opened', async (c) => {
  const uid = c.req.param('uid');
  if (!UID.test(uid)) return c.json({ error: 'not a study UID' }, 400);
  try {
    await opened(uid, c.get('me'));
    return c.body(null, 204);
  } catch (e) {
    return fails(c, e, 'audit');
  }
});

// Who did what: ICT only.
api.get('/audit', async (c) => {
  if (!c.get('me').roles.includes('pmc-ict-admin')) return c.json({ error: 'ICT only' }, 403);
  const study = c.req.query('study');
  if (study !== undefined && !UID.test(study)) return c.json({ error: 'not a study UID' }, 400);
  try {
    return c.json({ events: await auditTrail(study, 200) });
  } catch (e) {
    return fails(c, e, 'audit');
  }
});

// Server-sent events: "the studies changed". A stream lasts ten minutes, then
// the page reconnects through the front door, so a stream never outlives a
// session by long.
api.get('/events', (c) => {
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
