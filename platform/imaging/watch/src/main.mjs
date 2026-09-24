// The feed watch (Path A, M3.3): what ICT should hear about before a
// radiologist does. It serves Prometheus metrics on :9100/metrics, which
// monitor/rules.yml turns into alerts:
//
//   - when each registered modality last sent a study (the engine's
//     StableStudy changes), and how long each may stay silent;
//   - whether the engine answers;
//   - whether each domain controller answers LDAPS with a certificate the
//     platform trusts, and when that certificate expires;
//   - when the site's own certificate expires;
//   - free space where the images are;
//   - the newest database backup of each cluster (pgBackRest's backup.info)
//     and the newest nightly snapshot to the R740xd.
//
// It only reads. Node 24, no packages. It keeps its place in the engine's
// change feed, and when each modality was last heard, in /state, so a restart
// does not make every feed look new.
import { X509Certificate } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, readdirSync, renameSync, statfsSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { connect } from 'node:tls';

const ENGINE = process.env.ENGINE_URL ?? 'http://orthanc:8042';
const API_KEY = readFileSync(process.env.API_KEY_SECRET ?? '/run/secrets/svc-platform-api-key', 'utf8').trim();
const STATE = process.env.STATE_DIR ?? '/state';
const STORAGE = process.env.STORAGE_PATH ?? '/storage';
const REPO = process.env.PGBACKREST_REPO ?? '/pgbackrest';
const SNAPSHOT_STATUS = process.env.SNAPSHOT_STATUS ?? '/status/snapshot.json';
const SITE_CERT = process.env.SITE_CERT ?? '/run/secrets/tls-certificate';
const AD_CA = process.env.AD_CA ?? '/run/secrets/ad-ca.pem';
const AD_URLS = (process.env.PMC_AD_URL ?? '').split(/\s+/).filter(Boolean);
const POLL_MS = Number(process.env.POLL_SECONDS ?? '5') * 1000;
const CHECK_MS = Number(process.env.CHECK_SECONDS ?? '30') * 1000;

// How long a modality may stay silent: PMC_FEED_SILENCE for all (default
// 24h), and PMC_FEED_SILENCE_OVERRIDES for some, by registered name:
// "cathlab-qfr=72h,mr-sempra=48h". Units s, m, h, d.
function seconds(text) {
  const m = /^(\d+(?:\.\d+)?)([smhd])$/.exec(text.trim());
  if (!m) throw new Error(`not a duration: ${text}`);
  return Number(m[1]) * { s: 1, m: 60, h: 3600, d: 86400 }[m[2]];
}
const SILENCE = seconds(process.env.PMC_FEED_SILENCE || '24h');
const OVERRIDES = new Map((process.env.PMC_FEED_SILENCE_OVERRIDES ?? '').split(',').filter((p) => p.trim())
  .map((pair) => {
    const [name, duration] = pair.split('=');
    return [name.trim(), seconds(duration ?? '')];
  }));

const now = () => Date.now() / 1000;

// ---- state ------------------------------------------------------------------
function load() {
  try {
    return JSON.parse(readFileSync(`${STATE}/watch.json`, 'utf8'));
  } catch {
    return { seq: -1, lastStudy: {} }; // lastStudy: by AE title, in seconds
  }
}
const state = load();
function save() {
  mkdirSync(STATE, { recursive: true });
  writeFileSync(`${STATE}/watch.json.tmp`, JSON.stringify(state));
  renameSync(`${STATE}/watch.json.tmp`, `${STATE}/watch.json`);
}

// ---- the engine -------------------------------------------------------------
async function engine(path, as = 'json') {
  const r = await fetch(ENGINE + path, {
    headers: { 'api-key': API_KEY, Accept: as === 'json' ? 'application/json' : 'text/plain' },
    signal: AbortSignal.timeout(15_000),
  });
  if (!r.ok) throw new Error(`GET ${path}: HTTP ${r.status}`);
  return as === 'json' ? r.json() : r.text();
}

const seen = new Map(); // studies seen since start, by AE title
let modalities = {}; // registered name -> { AET }

// A study is complete once the engine calls it stable: then ask one of its
// instances which modality sent it.
async function stableStudy(id) {
  const study = await engine(`/studies/${id}`);
  const series = await engine(`/series/${study.Series[0]}`);
  const aet = (await engine(`/instances/${series.Instances[0]}/metadata/RemoteAET`, 'text')).trim();
  if (!aet) return;
  state.lastStudy[aet] = now();
  seen.set(aet, (seen.get(aet) ?? 0) + 1);
}

async function followChanges() {
  if (state.seq < 0) {
    // First start: begin at the end of the feed, not at its beginning.
    state.seq = (await engine('/changes?last')).Last;
    save();
  }
  for (;;) {
    const page = await engine(`/changes?since=${state.seq}&limit=500`);
    for (const change of page.Changes) {
      if (change.ChangeType !== 'StableStudy') continue;
      try {
        await stableStudy(change.ID);
      } catch (e) {
        quietly('study', e); // deleted since, or not sent over DICOM
      }
    }
    state.seq = page.Last;
    save();
    if (page.Done) return;
  }
}

async function readModalities() {
  modalities = await engine('/modalities?expand');
  // A modality registered since the last look gets its silence counted from
  // now, not from the beginning of time.
  let changed = false;
  for (const m of Object.values(modalities)) {
    if (state.lastStudy[m.AET] === undefined) {
      state.lastStudy[m.AET] = now();
      changed = true;
    }
  }
  if (changed) save();
}

// ---- checks -----------------------------------------------------------------
const health = {
  engineUp: 0,
  directory: new Map(), // url -> { up, expiry }
  siteCertExpiry: undefined,
  storage: undefined, // { free, size }
  backups: [], // { stanza, type, stop }
  snapshot: undefined, // seconds
};

function probeTls(url, ca) {
  const u = new URL(url);
  const host = u.hostname;
  const port = Number(u.port || 636);
  return new Promise((resolve) => {
    const socket = connect({ host, port, servername: host, ca, timeout: 5_000 }, () => {
      const cert = socket.getPeerX509Certificate();
      const expiry = cert ? Date.parse(cert.validTo) / 1000 : undefined;
      const up = socket.authorized ? 1 : 0;
      socket.end();
      resolve({ up, expiry });
    });
    socket.on('error', () => resolve({ up: 0 }));
    socket.on('timeout', () => {
      socket.destroy();
      resolve({ up: 0 });
    });
  });
}

// pgBackRest's backup.info: one line per backup under [backup:current],
// label={json}, with the type and when it finished.
function readBackups() {
  const found = [];
  const dir = `${REPO}/backup`;
  if (!existsSync(dir)) return found;
  for (const stanza of readdirSync(dir)) {
    let text;
    try {
      text = readFileSync(`${dir}/${stanza}/backup.info`, 'utf8');
    } catch {
      continue;
    }
    let current = false;
    for (const line of text.split('\n')) {
      if (line.startsWith('[')) {
        current = line.trim() === '[backup:current]';
        continue;
      }
      const eq = line.indexOf('=');
      if (!current || eq < 0) continue;
      try {
        const info = JSON.parse(line.slice(eq + 1));
        if (!info['backup-error']) found.push({ stanza, type: info['backup-type'], stop: info['backup-timestamp-stop'] });
      } catch {
        // not a backup line
      }
    }
  }
  return found;
}

async function check() {
  try {
    await engine('/system');
    health.engineUp = 1;
  } catch (e) {
    health.engineUp = 0;
    quietly('engine', e);
  }
  const ca = existsSync(AD_CA) ? readFileSync(AD_CA) : undefined;
  for (const url of AD_URLS) health.directory.set(url, await probeTls(url, ca));
  try {
    health.siteCertExpiry = new X509Certificate(readFileSync(SITE_CERT)).validToDate.getTime() / 1000;
  } catch (e) {
    quietly('certificate', e);
  }
  try {
    const fs = statfsSync(STORAGE);
    health.storage = { free: fs.bavail * fs.bsize, size: fs.blocks * fs.bsize };
  } catch (e) {
    quietly('storage', e);
  }
  try {
    health.backups = readBackups();
  } catch (e) {
    quietly('backups', e);
  }
  try {
    health.snapshot = JSON.parse(readFileSync(SNAPSHOT_STATUS, 'utf8')).finished;
  } catch {
    health.snapshot = undefined; // no snapshot yet
  }
}

// One log line per kind of failure until it recovers, not one per attempt.
const failing = new Set();
function quietly(kind, e) {
  if (!failing.has(kind)) console.error(`watch: ${kind}: ${e?.message ?? e}`);
  failing.add(kind);
}

// ---- metrics ----------------------------------------------------------------
const esc = (v) => String(v).replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n');
function render() {
  const out = [];
  const metric = (name, type, help, samples) => {
    out.push(`# HELP ${name} ${help}`, `# TYPE ${name} ${type}`);
    for (const [labels, value] of samples) {
      if (value === undefined || Number.isNaN(value)) continue;
      const l = Object.entries(labels).map(([k, v]) => `${k}="${esc(v)}"`).join(',');
      out.push(`${name}${l ? `{${l}}` : ''} ${value}`);
    }
  };
  const feeds = Object.entries(modalities).map(([name, m]) => [{ modality: name, aet: m.AET }, m.AET, name]);
  metric('pmc_feed_last_study_timestamp_seconds', 'gauge',
    'When the modality last sent a study the engine holds as stable.',
    feeds.map(([labels, aet]) => [labels, state.lastStudy[aet]]));
  metric('pmc_feed_silence_threshold_seconds', 'gauge',
    'How long the modality may stay silent before ICT hears of it.',
    feeds.map(([labels, , name]) => [labels, OVERRIDES.get(name) ?? SILENCE]));
  metric('pmc_feed_studies_total', 'counter', 'Studies seen from the modality since the watch started.',
    feeds.map(([labels, aet]) => [labels, seen.get(aet) ?? 0]));
  metric('pmc_engine_up', 'gauge', 'Whether the engine answered.', [[{}, health.engineUp]]);
  metric('pmc_directory_up', 'gauge', 'Whether the domain controller answered LDAPS with a trusted certificate.',
    [...health.directory].map(([url, d]) => [{ server: url }, d.up]));
  metric('pmc_directory_certificate_expiry_timestamp_seconds', 'gauge',
    "When the domain controller's LDAPS certificate expires.",
    [...health.directory].map(([url, d]) => [{ server: url }, d.expiry]));
  metric('pmc_site_certificate_expiry_timestamp_seconds', 'gauge', "When the site's certificate expires.",
    [[{}, health.siteCertExpiry]]);
  metric('pmc_storage_free_bytes', 'gauge', 'Free space where the images are.', [[{}, health.storage?.free]]);
  metric('pmc_storage_size_bytes', 'gauge', 'Size of the filesystem where the images are.',
    [[{}, health.storage?.size]]);
  const newest = new Map();
  for (const b of health.backups) {
    const key = `${b.stanza}\u0000${b.type}`;
    if ((newest.get(key)?.stop ?? 0) < b.stop) newest.set(key, b);
  }
  metric('pmc_backup_last_success_timestamp_seconds', 'gauge',
    "When the cluster's newest backup of this type finished (pgBackRest).",
    [...newest.values()].map((b) => [{ stanza: b.stanza, type: b.type }, b.stop]));
  metric('pmc_snapshot_last_success_timestamp_seconds', 'gauge',
    "When the newest nightly snapshot to the R740xd finished.", [[{}, health.snapshot]]);
  metric('pmc_watch_up', 'gauge', 'The watch itself.', [[{}, 1]]);
  return `${out.join('\n')}\n`;
}

// ---- run --------------------------------------------------------------------
async function loop(what, every, fn) {
  try {
    await fn();
    failing.delete(what);
  } catch (e) {
    quietly(what, e);
  }
  setTimeout(() => loop(what, every, fn), every);
}

createServer((req, res) => {
  if (req.url === '/metrics') {
    res.writeHead(200, { 'Content-Type': 'text/plain; version=0.0.4; charset=utf-8' });
    res.end(render());
  } else if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('ok\n');
  } else {
    res.writeHead(404);
    res.end();
  }
}).listen(9100, () => console.log('watch: serving metrics on :9100'));

loop('modalities', CHECK_MS, readModalities);
loop('changes', POLL_MS, followChanges);
loop('checks', CHECK_MS, check);
