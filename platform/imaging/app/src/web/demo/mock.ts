// The clickable sample's stand-in for the front door: the app's own API,
// answered in the page from invented studies (data.ts), with the same
// rules the server applies (who sees what, who may claim and read, what a
// study someone else holds answers), the live feed, and where the pictures
// and the viewer page are. Installed by demo.tsx before the app mounts.
import {
  MODALITY_GROUPS, READERS, modalityGroups, seesEverything,
  type Me, type Role, type Studies, type Study, type StudyDetail,
} from '../../shared/api.ts';
import type { Sample } from '../links.ts';
import { KINDS, PEOPLE, kindOfUid, makeStudies, uidFor, type SampleStudy } from './data.ts';

const ROLE_KEY = 'pmc-sample-role';

export function chosenRole(): Role | undefined {
  try {
    const r = sessionStorage.getItem(ROLE_KEY);
    return r && r in PEOPLE ? (r as Role) : undefined;
  } catch {
    return undefined;
  }
}
export function chooseRole(role: Role | undefined): void {
  try {
    if (role) sessionStorage.setItem(ROLE_KEY, role);
    else sessionStorage.removeItem(ROLE_KEY);
  } catch {
    // a browser that keeps nothing: the choice lasts this page
  }
}

// The live feed the app listens to (api.ts, useLiveStudies): "hello" once
// connected, "studies" whenever something changes.
const feeds = new Set<(type: string) => void>();
const announce = () => feeds.forEach((fire) => fire('studies'));

class SampleEventSource extends EventTarget {
  readonly url: string;
  readyState = 1;
  onerror: ((e: Event) => void) | null = null;
  private fire = (type: string) => this.dispatchEvent(new Event(type));
  constructor(url: string | URL) {
    super();
    this.url = String(url);
    feeds.add(this.fire);
    setTimeout(() => this.fire('hello'), 60);
  }
  close(): void {
    feeds.delete(this.fire);
    this.readyState = 2;
  }
}

export interface Installed {
  me: Me;
  studies: SampleStudy[];
}

export function installSample(role: Role, now = Date.now()): Installed {
  const me = PEOPLE[role];
  const studies = makeStudies(now);
  const reader = READERS.includes(role);
  const everything = seesEverything(me.roles);
  const visible = (s: SampleStudy) => everything || s.labels.includes('referrer-shared');
  const pub = (s: SampleStudy): Study => {
    const { kind: _k, image: _i, series: _s, takenAt: _t, ...study } = s;
    void _k; void _i; void _s; void _t;
    return study;
  };
  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
  const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

  const RANGE_DAYS: Record<string, number | undefined> = { today: 1, '3d': 3, '7d': 7, '30d': 30, all: undefined };
  function list(p: URLSearchParams): Studies {
    const q = (p.get('q') ?? '').trim().toLowerCase();
    const codes = modalityGroups(p.get('mod') ?? undefined).flatMap((k) => [...MODALITY_GROUPS[k].codes] as string[]);
    const days = RANGE_DAYS[p.get('range') ?? '7d'];
    const since = Number(p.get('since') ?? 0);
    const limit = Number(p.get('limit') ?? 50);
    const sort = p.get('sort') ?? 'time';
    const dir = p.get('dir') ?? (sort === 'time' ? 'desc' : 'asc');
    const mine = p.get('mine') === '1';
    const unread = p.get('unread') === '1';
    const midnight = new Date(now);
    midnight.setHours(0, 0, 0, 0);
    let rows = studies.filter(visible);
    if (days) rows = rows.filter((s) => s.takenAt >= midnight.getTime() - (days - 1) * 86_400_000);
    if (codes.length) rows = rows.filter((s) => s.modalities.some((m) => codes.includes(m)));
    if (q) rows = rows.filter((s) => [s.patientName.replace('^', ' '), s.patientId, s.accession].some((v) => v.toLowerCase().includes(q)));
    if (mine) rows = rows.filter((s) => s.claim?.reader === me.username);
    if (unread) rows = rows.filter((s) => !s.read);
    const key = (s: SampleStudy): string | number => (sort === 'patient' ? s.patientName : sort === 'accession' ? s.accession : s.takenAt);
    rows.sort((a, b) => (key(a) < key(b) ? -1 : key(a) > key(b) ? 1 : 0) * (dir === 'asc' ? 1 : -1));
    const page = rows.slice(since, since + limit).map(pub);
    // Counted as the server counts: for everyone but a referrer, and not
    // for a search or for "claimed by me".
    const counted = everything && !q && !mine;
    return { studies: page, more: since + limit < rows.length, sortedBy: 'engine', ...(counted ? { total: rows.length } : {}) };
  }
  function detail(s: SampleStudy): StudyDetail {
    const priors = studies.filter((p) => p.patientId === s.patientId && p.takenAt < s.takenAt).slice(0, 50).map(pub);
    return { study: pub(s), series: s.series, priors };
  }

  const realFetch = window.fetch.bind(window);
  window.fetch = async (input, init) => {
    const href = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    const url = new URL(href, location.href);
    if (!url.pathname.startsWith('/pmc/api/')) return realFetch(input, init);
    await wait(40 + Math.random() * 110); // a server across the hospital's network
    const method = (init?.method ?? 'GET').toUpperCase();
    const path = url.pathname.slice('/pmc/api'.length);
    if (path === '/me') return json(me);
    if (path === '/studies' && method === 'GET') return json(list(url.searchParams));
    const m = /^\/studies\/([0-9.]+)(?:\/(claim|read|opened))?$/.exec(path);
    if (!m) return json({ error: 'not in the sample' }, 404);
    const s = studies.find((x) => x.studyUid === m[1]);
    if (!s || !visible(s)) return json({ error: 'not found' }, 404);
    if (!m[2]) return json(detail(s));
    if (m[2] === 'opened') return new Response(null, { status: 204 });
    if (!reader) return json({ error: 'readers only' }, 403);
    const held = s.claim !== null && s.claim.reader !== me.username;
    if (m[2] === 'claim') {
      if (method === 'POST') {
        if (held) return json({ claim: s.claim }, 409);
        s.claim = { reader: me.username, readerName: me.name, claimedAt: new Date().toISOString() };
      } else {
        if (s.claim?.reader !== me.username) return json({ error: 'not yours' }, 409);
        s.claim = null;
      }
    } else {
      if (method === 'POST') {
        if (held) return json({ claim: s.claim }, 409);
        s.claim = null;
        s.read = { reader: me.username, readerName: me.name, readAt: new Date().toISOString() };
      } else {
        if (s.read?.reader !== me.username) return json({ error: 'not yours' }, 409);
        s.read = null;
      }
    }
    announce();
    return json({ ok: true });
  };
  window.EventSource = SampleEventSource as unknown as typeof EventSource;

  // Pictures: the engine's own renders of the tests' synthetic studies, one
  // set per kind (sample/<kind>-<n>-<size>.jpg), and the viewer page.
  const byUid = new Map(studies.map((s) => [s.studyUid, s]));
  const thumb = (uid: string, size: number) => {
    const s = byUid.get(uid);
    const kind = s?.kind ?? kindOfUid(uid);
    if (!kind) return 'sample/none.jpg';
    return `sample/${kind.modality}-${(s?.image ?? 1) - 1}-${size > 96 ? 192 : 96}.jpg`;
  };
  window.__pmcSample = {
    thumb,
    seriesThumb: (uid, seriesUid) => {
      const s = byUid.get(uid);
      const j = s ? s.series.findIndex((x) => x.seriesUid === seriesUid) : 0;
      return s ? `sample/${s.kind.modality}-${s.image - 1}-s${Math.max(0, j)}-96.jpg` : thumb(uid, 96);
    },
    viewer: (uid, prior) => `demo-viewer.html?study=${encodeURIComponent(uid)}${prior ? `&prior=${encodeURIComponent(prior)}` : ''}`,
    site: { home: '#/', signOut: '?signout=1#/', brand: (file) => `brand/${file}` },
  } satisfies Sample;

  // Life: the two studies still arriving finish; every so often a new one
  // arrives, first with a few images, then whole.
  const finish = (s: SampleStudy) => {
    s.stable = true;
    s.instances = Math.max(s.instances, s.kind.instances[0]);
    s.lastUpdate = new Date().toISOString();
    announce();
  };
  studies.filter((s) => !s.stable).forEach((s, i) => setTimeout(() => finish(s), 20_000 + i * 15_000));
  let arrivals = 0;
  setInterval(() => {
    arrivals += 1;
    const kind = KINDS[(arrivals * 5) % KINDS.length] as (typeof KINDS)[number];
    const model = studies[arrivals % 10] as SampleStudy;
    const s: SampleStudy = {
      ...model,
      id: `sample-arrival-${arrivals}`,
      studyUid: uidFor(KINDS.indexOf(kind), 500 + arrivals),
      studyDate: dicomDate(new Date()),
      studyTime: dicomTime(new Date()),
      description: `${kind.modality} ${kind.descriptions[0] ?? ''}`.trim(),
      accession: `A26${String(900_000 + arrivals).padStart(6, '0')}`,
      modalities: [kind.modality],
      instances: 1,
      stable: false,
      lastUpdate: new Date().toISOString(),
      labels: [],
      claim: null,
      read: null,
      kind,
      image: 1,
      series: [{ seriesUid: `${uidFor(KINDS.indexOf(kind), 500 + arrivals)}.1`, number: 1, modality: kind.modality, description: kind.series[0] ?? '', instances: 1 }],
      takenAt: Date.now(),
    };
    studies.unshift(s);
    byUid.set(s.studyUid, s);
    announce();
    setTimeout(() => finish(s), 8_000);
  }, 45_000);

  return { me, studies };
}

const pad = (n: number) => String(n).padStart(2, '0');
const dicomDate = (d: Date) => `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`;
const dicomTime = (d: Date) => `${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
