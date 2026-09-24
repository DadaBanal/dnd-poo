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

export const Me = z.object({
  email: z.string(),
  name: z.string(),
  roles: z.array(z.enum(ROLES)),
});
export type Me = z.infer<typeof Me>;

// The worklist's filters. They live in the page's URL, so a view is a link.
export const RANGES = ['today', '3d', '7d', '30d', 'all'] as const;
export const SORTS = ['time', 'patient', 'accession'] as const;
// The groups a person filters by. "Other" is every modality not named here.
export const MODALITY_GROUPS = {
  xray: { label: 'X-ray', codes: ['CR', 'DX'] },
  ct: { label: 'CT', codes: ['CT'] },
  mr: { label: 'MR', codes: ['MR'] },
  us: { label: 'Ultrasound', codes: ['US'] },
  xa: { label: 'Cath lab', codes: ['XA', 'RF'] },
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
});
export type WorklistSearch = z.infer<typeof WorklistSearch>;

// What the server accepts: the same filters, flattened for a query string,
// plus paging.
export const StudiesQuery = z.object({
  q: z.string().trim().max(64).optional(),
  mod: z.string().optional(), // comma-separated group keys
  range: z.enum(RANGES).default('7d'),
  sort: z.enum(SORTS).default('time'),
  dir: z.enum(['asc', 'desc']).optional(),
  since: z.coerce.number().int().min(0).max(100_000).default(0),
  limit: z.coerce.number().int().min(1).max(200).default(50),
});
export type StudiesQuery = z.infer<typeof StudiesQuery>;

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
});
export type Study = z.infer<typeof Study>;

export const Studies = z.object({
  studies: z.array(Study),
  more: z.boolean(), // another page exists
  // "engine": the engine sorted every match. "page": this engine cannot sort,
  // so only the page shown is in order.
  sortedBy: z.enum(['engine', 'page']),
});
export type Studies = z.infer<typeof Studies>;
