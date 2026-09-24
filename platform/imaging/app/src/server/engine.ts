// The engine (Orthanc), as the front door app's server sees it. A person's
// worklist is asked for with that person's own access token, so the engine's
// authorization plugin decides what they see: a referrer's search comes back
// cut to the studies shared with referrers, whatever this code asks for.
import { MODALITY_GROUPS, modalityGroups, type Study, type Studies, type StudiesQuery } from '../shared/api.ts';

const ENGINE = process.env.ENGINE_URL ?? 'http://orthanc:8042';
const TIMEOUT_MS = 30_000;

export class EngineError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function call(path: string, auth: Record<string, string>, init: RequestInit = {}): Promise<unknown> {
  const r = await fetch(ENGINE + path, {
    ...init,
    headers: { Accept: 'application/json', ...auth, ...(init.headers as Record<string, string> | undefined) },
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!r.ok) throw new EngineError(r.status, `${init.method ?? 'GET'} ${path}: ${r.status}`);
  return r.json();
}

export const asPerson = (token: string) => ({ Authorization: `Bearer ${token}` });
export const asService = (apiKey: string) => ({ 'api-key': apiKey });

// ---- sorting ------------------------------------------------------------------
// Only an index that can sort (the PostgreSQL index: HasExtendedFind) is ever
// sent OrderBy. The legacy ODBC index answers it with HTTP 500 (CLAUDE.md).
let canSort: boolean | undefined;

export async function engineCanSort(apiKey: string): Promise<boolean> {
  if (canSort === undefined) {
    const system = (await call('/system', asService(apiKey))) as { Capabilities?: { HasExtendedFind?: boolean } };
    canSort = system.Capabilities?.HasExtendedFind === true;
  }
  return canSort;
}

// ---- the worklist -------------------------------------------------------------
// Manila's calendar date, as DICOM writes dates.
function manilaDate(daysAgo: number): string {
  const d = new Date(Date.now() - daysAgo * 86_400_000);
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Manila', year: 'numeric', month: '2-digit', day: '2-digit' })
    .format(d).replaceAll('-', '');
}

const RANGE_DAYS = { today: 0, '3d': 2, '7d': 6, '30d': 29 } as const;

function modalityFilter(mod: string | undefined): string | undefined {
  const codes = modalityGroups(mod).flatMap((k) => MODALITY_GROUPS[k].codes);
  return codes.length ? codes.join('\\') : undefined;
}

type Order = { Type: 'DicomTag'; Key: string; Direction: 'ASC' | 'DESC' };

function orderBy(q: StudiesQuery): Order[] {
  const dir = (fallback: 'asc' | 'desc') => ((q.dir ?? fallback) === 'asc' ? 'ASC' : 'DESC');
  switch (q.sort) {
    case 'patient':
      return [{ Type: 'DicomTag', Key: 'PatientName', Direction: dir('asc') },
        { Type: 'DicomTag', Key: 'StudyDate', Direction: 'DESC' }];
    case 'accession':
      return [{ Type: 'DicomTag', Key: 'AccessionNumber', Direction: dir('asc') }];
    default:
      return [{ Type: 'DicomTag', Key: 'StudyDate', Direction: dir('desc') },
        { Type: 'DicomTag', Key: 'StudyTime', Direction: dir('desc') }];
  }
}

interface FoundStudy {
  ID: string;
  IsStable?: boolean;
  LastUpdate?: string;
  Labels?: string[];
  MainDicomTags?: Record<string, string>;
  PatientMainDicomTags?: Record<string, string>;
  RequestedTags?: Record<string, string>;
}

function toStudy(s: FoundStudy): Study {
  const tags = s.MainDicomTags ?? {};
  const patient = s.PatientMainDicomTags ?? {};
  const requested = s.RequestedTags ?? {};
  return {
    id: s.ID,
    studyUid: tags.StudyInstanceUID ?? '',
    patientName: patient.PatientName ?? '',
    patientId: patient.PatientID ?? '',
    patientSex: patient.PatientSex ?? '',
    patientBirthDate: patient.PatientBirthDate ?? '',
    studyDate: tags.StudyDate ?? '',
    studyTime: tags.StudyTime ?? '',
    description: tags.StudyDescription ?? '',
    accession: tags.AccessionNumber ?? '',
    modalities: (requested.ModalitiesInStudy ?? '').split('\\').filter(Boolean),
    instances: Number(requested.NumberOfStudyRelatedInstances ?? 0),
    stable: s.IsStable ?? false,
    lastUpdate: s.LastUpdate ?? '',
    labels: s.Labels ?? [],
    claim: null, // the platform database's, merged in by the caller
  };
}

async function find(token: string, query: Record<string, string>, q: StudiesQuery, sorted: boolean,
  since: number, limit: number): Promise<FoundStudy[]> {
  const body: Record<string, unknown> = {
    Level: 'Study',
    Query: query,
    Expand: true,
    RequestedTags: ['ModalitiesInStudy', 'NumberOfStudyRelatedInstances'],
    CaseSensitive: false,
    Since: since,
    Limit: limit,
  };
  if (sorted) body.OrderBy = orderBy(q);
  return (await call('/tools/find', asPerson(token), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })) as FoundStudy[];
}

function sortPage(rows: Study[], q: StudiesQuery): Study[] {
  const asc = (q.dir ?? (q.sort === 'time' ? 'desc' : 'asc')) === 'asc';
  const key = (s: Study) =>
    q.sort === 'patient' ? s.patientName : q.sort === 'accession' ? s.accession : s.studyDate + s.studyTime;
  return rows.sort((a, b) => (asc ? 1 : -1) * key(a).localeCompare(key(b)));
}

// A search box matches a patient's name, their patient ID or the accession
// number: three questions to the engine, merged. Without a search, one
// question, one page at a time. `only` limits the answer to those studies
// (a reader's own claims).
export async function worklist(token: string, apiKey: string, q: StudiesQuery, only?: string[]): Promise<Studies> {
  const sorted = await engineCanSort(apiKey);
  const base: Record<string, string> = {};
  if (only) {
    if (!only.length) return { studies: [], more: false, sortedBy: 'engine' };
    base.StudyInstanceUID = only.join('\\');
  }
  if (q.range !== 'all') base.StudyDate = `${manilaDate(RANGE_DAYS[q.range])}-`;
  const modalities = modalityFilter(q.mod);
  if (modalities) base.ModalitiesInStudy = modalities;

  let found: FoundStudy[];
  let more: boolean;
  if (q.q) {
    const term = `*${q.q.replace(/[*?\\]/g, '')}*`;
    const answers = await Promise.all(['PatientName', 'PatientID', 'AccessionNumber'].map((field) =>
      find(token, { ...base, [field]: term }, q, sorted, 0, q.limit + 1)));
    const byId = new Map(answers.flat().map((s) => [s.ID, s]));
    found = [...byId.values()];
    more = answers.some((a) => a.length > q.limit);
  } else {
    found = await find(token, base, q, sorted, q.since, q.limit + 1);
    more = found.length > q.limit;
  }
  let studies = found.map(toStudy);
  if (q.q || !sorted) studies = sortPage(studies, q);
  return { studies: studies.slice(0, q.limit), more, sortedBy: sorted && !q.q ? 'engine' : 'page' };
}

// Whether this person may see this study at all: the engine answers with
// the person's own token, so a study they cannot see is simply not found.
export async function visible(token: string, studyUid: string): Promise<boolean> {
  const found = (await call('/tools/find', asPerson(token), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ Level: 'Study', Query: { StudyInstanceUID: studyUid }, Limit: 1 }),
  })) as unknown[];
  return found.length > 0;
}

// ---- what changed ---------------------------------------------------------------
// The engine's change log, read with the platform's own key. Only the fact
// that something changed leaves this server, never what: each page asks
// again, with its own person's token.
export async function lastChange(apiKey: string): Promise<number> {
  const r = (await call('/changes?last', asService(apiKey))) as { Last: number };
  return r.Last;
}

export async function changesSince(apiKey: string, since: number): Promise<{ last: number; studies: number }> {
  const r = (await call(`/changes?since=${since}&limit=200`, asService(apiKey))) as {
    Changes: { ChangeType: string; ResourceType: string }[];
    Last: number;
  };
  const studies = r.Changes.filter((c) =>
    ['NewStudy', 'StableStudy', 'UpdatedAttachment', 'Deleted'].includes(c.ChangeType)).length;
  return { last: r.Last, studies };
}
