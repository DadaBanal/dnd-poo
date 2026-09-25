// What the front door app's server and its page say to each other. One set of
// schemas, checked on both sides.
import { z } from 'zod';

export const ROLES = [
  'pmc-radiologist',
  'pmc-cardiologist',
  'pmc-technologist',
  'pmc-referrer',
  'pmc-ict-admin',
] as const;
export type Role = (typeof ROLES)[number];

// Who may claim a study to read it, and mark it read.
export const READERS: readonly Role[] = ['pmc-radiologist', 'pmc-cardiologist'];

// Only a referrer's view is cut to a label (identity/auth-service/
// permissions.json: every other role is authorized for every label, and the
// authorization service merges a person's roles). So anyone with any other
// role sees every study, and can be given totals (engine.ts, count).
export const seesEverything = (roles: readonly Role[]): boolean => roles.some((r) => r !== 'pmc-referrer');

// A person is their Windows logon name (AD's sAMAccountName), which every AD
// account has; email is shown when AD has one.
export const Me = z.object({
  username: z.string(),
  name: z.string(),
  email: z.string(),
  roles: z.array(z.enum(ROLES)),
});
export type Me = z.infer<typeof Me>;

// The worklist's filters. They live in the page's URL, so a view is a link.
export const RANGES = ['today', '3d', '7d', '30d', 'all'] as const;
export const SORTS = ['time', 'patient', 'accession'] as const;
// The groups a person filters by: one for each kind of machine PMC has
// (README: Every machine PMC has), by the DICOM modality codes each sends.
// A study whose codes are in no group (a report, a scanned page) is listed,
// but no chip picks it out.
export const MODALITY_GROUPS = {
  xray: { label: 'X-ray', codes: ['CR', 'DX'] },
  ct: { label: 'CT', codes: ['CT'] },
  mr: { label: 'MR', codes: ['MR'] },
  us: { label: 'Ultrasound', codes: ['US'] },
  mg: { label: 'Mammography', codes: ['MG'] },
  xa: { label: 'Cath lab', codes: ['XA'] },
  rf: { label: 'Fluoroscopy', codes: ['RF'] },
  nm: { label: 'Nuclear medicine', codes: ['NM', 'PT', 'BMD'] },
  dental: { label: 'Dental', codes: ['PX', 'IO'] },
  eye: { label: 'Eye', codes: ['OP', 'OPT', 'OPV', 'OPM'] },
  endo: { label: 'Endoscopy', codes: ['ES', 'XC'] },
  rt: { label: 'Radiotherapy', codes: ['RTIMAGE', 'RTDOSE', 'RTSTRUCT', 'RTPLAN', 'RTRECORD'] },
} as const;
export type ModalityGroup = keyof typeof MODALITY_GROUPS;
export const GROUP_KEYS = Object.keys(MODALITY_GROUPS) as ModalityGroup[];

// A modality filter in a URL reads "mod=ct,xa": known group keys only.
export function modalityGroups(mod: string | undefined): ModalityGroup[] {
  return (mod ?? '').split(',').filter((k): k is ModalityGroup => (GROUP_KEYS as string[]).includes(k));
}

export const WorklistSearch = z.object({
  q: z.string().trim().max(64).optional().catch(undefined),
  mod: z.string().max(64).optional().catch(undefined),
  range: z.enum(RANGES).optional().catch(undefined),
  sort: z.enum(SORTS).optional().catch(undefined),
  dir: z.enum(['asc', 'desc']).optional().catch(undefined),
  mine: z.enum(['1']).optional().catch(undefined), // only the studies I have claimed
  unread: z.enum(['1']).optional().catch(undefined), // only studies nobody has marked read
});
export type WorklistSearch = z.infer<typeof WorklistSearch>;

// The reading room's address: the same filters, and the study on screen.
export const RoomSearch = WorklistSearch.extend({
  study: z.string().regex(/^[0-9.]{1,64}$/).optional().catch(undefined),
});
export type RoomSearch = z.infer<typeof RoomSearch>;

// What the server accepts: the same filters, flattened for a query string,
// plus paging.
export const StudiesQuery = z.object({
  q: z.string().trim().max(64).optional(),
  mod: z.string().optional(), // comma-separated group keys
  range: z.enum(RANGES).default('7d'),
  sort: z.enum(SORTS).default('time'),
  dir: z.enum(['asc', 'desc']).optional(),
  mine: z.enum(['1']).optional(),
  unread: z.enum(['1']).optional(),
  since: z.coerce.number().int().min(0).max(100_000).default(0),
  limit: z.coerce.number().int().min(1).max(200).default(50),
});
export type StudiesQuery = z.infer<typeof StudiesQuery>;

// A reader's claim on a study, so no study is read twice.
export const Claim = z.object({
  reader: z.string(), // the reader's Windows logon name
  readerName: z.string(),
  claimedAt: z.string(),
});
export type Claim = z.infer<typeof Claim>;

// A study read: the reader said so from the reading list, once it was
// reported where PMC's reports live (BizBox today). A read study is no longer
// claimed.
export const Done = z.object({
  reader: z.string(),
  readerName: z.string(),
  readAt: z.string(),
});
export type Done = z.infer<typeof Done>;

export const Study = z.object({
  id: z.string(), // the engine's own ID for the study
  studyUid: z.string(),
  patientName: z.string(),
  patientId: z.string(),
  patientSex: z.string(),
  patientBirthDate: z.string(),
  studyDate: z.string(), // YYYYMMDD
  studyTime: z.string(), // HHMMSS
  description: z.string(),
  accession: z.string(),
  modalities: z.array(z.string()),
  instances: z.number(),
  stable: z.boolean(), // false while images are still arriving
  lastUpdate: z.string(),
  labels: z.array(z.string()),
  claim: Claim.nullable(),
  read: Done.nullable(),
});
export type Study = z.infer<typeof Study>;

// One series of a study, for the preview pane.
export const Series = z.object({
  seriesUid: z.string(),
  number: z.number().nullable(),
  modality: z.string(),
  description: z.string(),
  instances: z.number(),
});
export type Series = z.infer<typeof Series>;

// A study in full, for the preview pane: itself, its series in order, and
// the same patient's earlier studies (priors), newest first.
export const StudyDetail = z.object({
  study: Study,
  series: z.array(Series),
  priors: z.array(Study),
});
export type StudyDetail = z.infer<typeof StudyDetail>;

export const AuditEvent = z.object({
  at: z.string(),
  actor: z.string(),
  action: z.enum(['open', 'claim', 'release', 'read', 'unread']),
  studyUid: z.string().nullable(),
});
export const AuditTrail = z.object({ events: z.array(AuditEvent) });

export const Studies = z.object({
  studies: z.array(Study),
  more: z.boolean(), // another page exists
  // "engine": the engine sorted every match. "page": this engine cannot sort,
  // so only the page shown is in order.
  sortedBy: z.enum(['engine', 'page']),
  // Every study the filters match, when the engine counted for this person
  // (not for a search, nor for "claimed by me", nor for a referrer).
  total: z.number().int().nonnegative().optional(),
});
export type Studies = z.infer<typeof Studies>;
