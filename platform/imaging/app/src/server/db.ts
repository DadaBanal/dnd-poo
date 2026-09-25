// PMC's own platform database (pg-platform, database "platform"): who is
// reading which study, which studies are read, and the audit record. Its
// schema is db/migrations, applied by dbmate before this server starts; this
// role may read and write claims and reads, and may only add to the audit
// record.
import { readFileSync } from 'node:fs';
import pg from 'pg';
import type { Claim, Done } from '../shared/api.ts';

const pool = new pg.Pool({
  host: process.env.PLATFORM_DB_HOST ?? 'pg-platform',
  database: 'platform',
  user: 'platform_app',
  password: readFileSync(process.env.PLATFORM_DB_PASSWORD_SECRET ?? '/run/secrets/platform-app-password', 'utf8').trim(),
  application_name: 'pmc-app',
  max: 5,
  connectionTimeoutMillis: 5_000,
  idleTimeoutMillis: 30_000,
});

export interface Person {
  username: string; // the Windows logon name
  name: string;
}

type Action = 'open' | 'claim' | 'release' | 'read' | 'unread';

async function audit(client: pg.PoolClient | pg.Pool, who: Person, action: Action, studyUid: string,
  detail: Record<string, unknown> = {}): Promise<void> {
  await client.query('INSERT INTO audit.event (actor, action, study_uid, detail) VALUES ($1, $2, $3, $4)',
    [who.username, action, studyUid, JSON.stringify(detail)]);
}

interface ClaimRow { study_uid: string; reader: string; reader_name: string; claimed_at: Date }
const toClaim = (c: ClaimRow): Claim => ({ reader: c.reader, readerName: c.reader_name, claimedAt: c.claimed_at.toISOString() });

export async function claimsFor(studyUids: string[]): Promise<Map<string, Claim>> {
  if (!studyUids.length) return new Map();
  const r = await pool.query<ClaimRow>(
    'SELECT study_uid, reader, reader_name, claimed_at FROM reading.claim WHERE study_uid = ANY($1)', [studyUids]);
  return new Map(r.rows.map((c) => [c.study_uid, toClaim(c)]));
}

export async function claimedBy(reader: string, limit: number): Promise<string[]> {
  const r = await pool.query<{ study_uid: string }>(
    'SELECT study_uid FROM reading.claim WHERE reader = $1 ORDER BY claimed_at DESC LIMIT $2', [reader, limit]);
  return r.rows.map((c) => c.study_uid);
}

// A study is claimed by one reader at a time. Claiming your own claim again
// is fine; someone else's is not.
export async function claim(studyUid: string, who: Person): Promise<{ ok: true; claim: Claim } | { ok: false; claim: Claim }> {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const inserted = await client.query<{ claimed_at: Date }>(
      `INSERT INTO reading.claim (study_uid, reader, reader_name) VALUES ($1, $2, $3)
       ON CONFLICT (study_uid) DO NOTHING RETURNING claimed_at`, [studyUid, who.username, who.name]);
    if (inserted.rowCount) await audit(client, who, 'claim', studyUid);
    const now = await client.query<ClaimRow>(
      'SELECT study_uid, reader, reader_name, claimed_at FROM reading.claim WHERE study_uid = $1', [studyUid]);
    await client.query('COMMIT');
    const current = toClaim(now.rows[0]!);
    return { ok: current.reader === who.username, claim: current };
  } catch (e) {
    await client.query('ROLLBACK');
    throw e;
  } finally {
    client.release();
  }
}

export async function release(studyUid: string, who: Person): Promise<boolean> {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const gone = await client.query('DELETE FROM reading.claim WHERE study_uid = $1 AND reader = $2',
      [studyUid, who.username]);
    if (gone.rowCount) await audit(client, who, 'release', studyUid);
    await client.query('COMMIT');
    return Boolean(gone.rowCount);
  } catch (e) {
    await client.query('ROLLBACK');
    throw e;
  } finally {
    client.release();
  }
}

// ---- read ------------------------------------------------------------------------
interface DoneRow { study_uid: string; reader: string; reader_name: string; read_at: Date }
const toDone = (d: DoneRow): Done => ({ reader: d.reader, readerName: d.reader_name, readAt: d.read_at.toISOString() });

export async function doneFor(studyUids: string[]): Promise<Map<string, Done>> {
  if (!studyUids.length) return new Map();
  const r = await pool.query<DoneRow>(
    'SELECT study_uid, reader, reader_name, read_at FROM reading.done WHERE study_uid = ANY($1)', [studyUids]);
  return new Map(r.rows.map((d) => [d.study_uid, toDone(d)]));
}

// The reader has finished with the study. Their own claim on it goes with it
// (a claim says "I am reading this"); someone else's claim stops this, as it
// stops a claim. A study already read stays read by whoever read it first.
export async function markRead(studyUid: string, who: Person):
  Promise<{ ok: true; read: Done } | { ok: false; claim: Claim }> {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const held = await client.query<ClaimRow>(
      'SELECT study_uid, reader, reader_name, claimed_at FROM reading.claim WHERE study_uid = $1 FOR UPDATE', [studyUid]);
    const holder = held.rows[0];
    if (holder && holder.reader !== who.username) {
      await client.query('ROLLBACK');
      return { ok: false, claim: toClaim(holder) };
    }
    const released = holder
      ? Boolean((await client.query('DELETE FROM reading.claim WHERE study_uid = $1', [studyUid])).rowCount)
      : false;
    const inserted = await client.query<{ read_at: Date }>(
      `INSERT INTO reading.done (study_uid, reader, reader_name) VALUES ($1, $2, $3)
       ON CONFLICT (study_uid) DO NOTHING RETURNING read_at`, [studyUid, who.username, who.name]);
    if (inserted.rowCount) await audit(client, who, 'read', studyUid, released ? { released: true } : {});
    else if (released) await audit(client, who, 'release', studyUid);
    const now = await client.query<DoneRow>(
      'SELECT study_uid, reader, reader_name, read_at FROM reading.done WHERE study_uid = $1', [studyUid]);
    await client.query('COMMIT');
    return { ok: true, read: toDone(now.rows[0]!) };
  } catch (e) {
    await client.query('ROLLBACK');
    throw e;
  } finally {
    client.release();
  }
}

// Only the reader who marked a study read can mark it unread.
export async function unread(studyUid: string, who: Person): Promise<boolean> {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const gone = await client.query('DELETE FROM reading.done WHERE study_uid = $1 AND reader = $2',
      [studyUid, who.username]);
    if (gone.rowCount) await audit(client, who, 'unread', studyUid);
    await client.query('COMMIT');
    return Boolean(gone.rowCount);
  } catch (e) {
    await client.query('ROLLBACK');
    throw e;
  } finally {
    client.release();
  }
}

export async function opened(studyUid: string, who: Person): Promise<void> {
  await audit(pool, who, 'open', studyUid);
}

export interface AuditEvent {
  at: string;
  actor: string;
  action: Action;
  studyUid: string | null;
}

export async function auditTrail(studyUid: string | undefined, limit: number): Promise<AuditEvent[]> {
  const r = await pool.query<{ at: Date; actor: string; action: Action; study_uid: string | null }>(
    `SELECT at, actor, action, study_uid FROM audit.event
     WHERE $1::text IS NULL OR study_uid = $1 ORDER BY id DESC LIMIT $2`, [studyUid ?? null, limit]);
  return r.rows.map((e) => ({ at: e.at.toISOString(), actor: e.actor, action: e.action, studyUid: e.study_uid }));
}
