// The clickable sample's studies: invented, the same every time (a seeded
// generator), spread over the last thirty days on PMC's kinds of machine.
// No patient exists: every name is SAMPLE, Patient NN, every ID SMP-…, and
// the pixels behind each row are the engine's own renders of the synthetic
// studies the tests store (README: Every machine PMC has).
import type { Claim, Done, Me, Role, Series, Study } from '../../shared/api.ts';

// One kind of study a machine makes, with what the sample shows for it.
export interface SampleKind {
  modality: string;
  descriptions: string[];
  instances: [number, number]; // a range
  series: string[]; // series descriptions, in order
  weight: number; // how often it comes up
  /** The engine's render of a synthetic study of this kind (sample/…). */
  images: number; // how many variants exist
}

export const KINDS: SampleKind[] = [
  { modality: 'CR', descriptions: ['Chest PA', 'Chest PA and lateral', 'Abdomen supine', 'Knee AP and lateral', 'Lumbar spine'], instances: [1, 3], series: ['PA', 'Lateral'], weight: 30, images: 3 },
  { modality: 'DX', descriptions: ['Chest AP, portable', 'Pelvis AP', 'Hand PA'], instances: [1, 2], series: ['AP'], weight: 12, images: 1 },
  { modality: 'CT', descriptions: ['Head plain', 'Chest with contrast', 'Abdomen and pelvis with contrast', 'KUB (stone protocol)', 'Head angiogram'], instances: [40, 700], series: ['Axial 5 mm', 'Axial 1 mm', 'Coronal'], weight: 14, images: 2 },
  { modality: 'MR', descriptions: ['Brain plain', 'Brain with contrast', 'Lumbar spine', 'Knee'], instances: [120, 400], series: ['T1 axial', 'T2 axial', 'FLAIR', 'T2 sagittal'], weight: 6, images: 1 },
  { modality: 'US', descriptions: ['Abdomen', 'Pelvis, transvaginal', 'Obstetric, second trimester', 'Thyroid', 'Echocardiogram, 2D with Doppler'], instances: [12, 60], series: ['B-mode', 'Colour Doppler'], weight: 14, images: 2 },
  { modality: 'MG', descriptions: ['Screening, bilateral', 'Diagnostic, left'], instances: [4, 6], series: ['R CC', 'L CC', 'R MLO', 'L MLO'], weight: 4, images: 1 },
  { modality: 'XA', descriptions: ['Coronary angiogram', 'Coronary angiogram and PCI', 'Peripheral angiogram'], instances: [6, 14], series: ['LAO caudal', 'RAO cranial', 'LAO cranial'], weight: 3, images: 1 },
  { modality: 'RF', descriptions: ['C-arm, ORIF femur', 'C-arm, spine fixation', 'Barium swallow'], instances: [2, 8], series: ['Run 1', 'Run 2'], weight: 3, images: 1 },
  { modality: 'NM', descriptions: ['Bone scan, whole body', 'Thyroid scan and uptake', 'Myocardial perfusion, stress and rest', 'Renal DMSA'], instances: [2, 6], series: ['Anterior', 'Posterior'], weight: 3, images: 1 },
  { modality: 'BMD', descriptions: ['Bone density, spine and hips'], instances: [2, 3], series: ['AP spine', 'Left hip'], weight: 2, images: 1 },
  { modality: 'PX', descriptions: ['Panoramic', 'Panoramic and lateral ceph'], instances: [1, 2], series: ['Panoramic'], weight: 3, images: 1 },
  { modality: 'OPT', descriptions: ['Macula OCT, both eyes', 'Optic disc OCT'], instances: [12, 49], series: ['OD', 'OS'], weight: 2, images: 1 },
  { modality: 'ES', descriptions: ['Gastroscopy', 'Colonoscopy', 'Bronchoscopy'], instances: [6, 24], series: ['Photographs'], weight: 3, images: 1 },
  { modality: 'RTIMAGE', descriptions: ['Portal image, AP', 'Portal images, AP and lateral'], instances: [1, 2], series: ['Portal'], weight: 1, images: 1 },
];

// The people in the sample: one of each role, and colleagues who claim and
// read studies too, so the list has every state on it.
export const PEOPLE: Record<Role, Me> = {
  'pmc-radiologist': { username: 'sample.rad', name: 'Sample Radiologist', email: '', roles: ['pmc-radiologist'] },
  'pmc-cardiologist': { username: 'sample.card', name: 'Sample Cardiologist', email: '', roles: ['pmc-cardiologist'] },
  'pmc-technologist': { username: 'sample.tech', name: 'Sample Technologist', email: '', roles: ['pmc-technologist'] },
  'pmc-referrer': { username: 'sample.ref', name: 'Sample Referrer', email: '', roles: ['pmc-referrer'] },
  'pmc-ict-admin': { username: 'sample.ict', name: 'Sample ICT', email: '', roles: ['pmc-ict-admin'] },
};
const COLLEAGUES = [
  { reader: 'colleague.one', readerName: 'A. Colleague' },
  { reader: 'colleague.two', readerName: 'B. Colleague' },
];

// mulberry32: small, fast, and the same numbers every visit.
function prng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const pad = (n: number, w: number) => String(n).padStart(w, '0');
const dicomDate = (d: Date) => `${d.getFullYear()}${pad(d.getMonth() + 1, 2)}${pad(d.getDate(), 2)}`;
const dicomTime = (d: Date) => `${pad(d.getHours(), 2)}${pad(d.getMinutes(), 2)}${pad(d.getSeconds(), 2)}`;

export interface SampleStudy extends Study {
  kind: SampleKind;
  image: number; // which render (sample/<modality>-<image>-<size>.jpg)
  series: Series[];
  takenAt: number; // epoch ms
}

// The sample's UIDs carry the kind, so the viewer page can tell what to show.
export const SAMPLE_ROOT = '1.2.826.0.1.3680043.10.999';
export const uidFor = (kindIndex: number, n: number) => `${SAMPLE_ROOT}.${kindIndex + 1}.${n}`;
export function kindOfUid(uid: string): SampleKind | undefined {
  const m = new RegExp(`^${SAMPLE_ROOT.replace(/\./g, '\\.')}\\.(\\d+)\\.`).exec(uid);
  return m ? KINDS[Number(m[1]) - 1] : undefined;
}

// Everything the sample holds, made once.
export function makeStudies(now = Date.now(), count = 110): SampleStudy[] {
  const rnd = prng(20260925);
  const pick = <T,>(xs: readonly T[]): T => xs[Math.floor(rnd() * xs.length)] as T;
  const between = (lo: number, hi: number) => lo + Math.floor(rnd() * (hi - lo + 1));
  const totalWeight = KINDS.reduce((s, k) => s + k.weight, 0);
  const kindByWeight = () => {
    let r = rnd() * totalWeight;
    for (const k of KINDS) {
      r -= k.weight;
      if (r <= 0) return k;
    }
    return KINDS[0] as SampleKind;
  };
  // Forty patients; a few have earlier studies, so the preview shows priors.
  const patients = Array.from({ length: 40 }, (_, i) => {
    const sex = pick(['M', 'F', 'F', 'M', 'O'] as const);
    const born = new Date(now - between(2, 88) * 365.25 * 86_400_000);
    return { id: `SMP-${pad(i + 1, 6)}`, name: `SAMPLE^Patient ${pad(i + 1, 2)}`, sex, birth: dicomDate(born) };
  });
  const out: SampleStudy[] = [];
  const counters = new Map<string, number>();
  for (let i = 0; i < count; i++) {
    const kind = kindByWeight();
    const kindIndex = KINDS.indexOf(kind);
    const n = (counters.get(kind.modality) ?? 0) + 1;
    counters.set(kind.modality, n);
    const patient = pick(patients);
    // Most of the list is this week, in working hours; a quarter is older,
    // up to thirty days, and a few older still (the priors).
    const daysAgo = i < count * 0.7 ? rnd() * 7 : i < count * 0.95 ? 7 + rnd() * 23 : 60 + rnd() * 400;
    const taken = new Date(now - daysAgo * 86_400_000);
    taken.setHours(between(6, 21), between(0, 59), between(0, 59), 0);
    if (taken.getTime() > now - 60_000) taken.setTime(now - 60_000 * between(2, 30));
    const instances = between(kind.instances[0], kind.instances[1]);
    const seriesCount = Math.min(kind.series.length, between(1, kind.series.length));
    let left = instances;
    const series: Series[] = kind.series.slice(0, seriesCount).map((desc, j) => {
      const share = j === seriesCount - 1 ? left : Math.max(1, Math.round(instances / seriesCount));
      left -= share;
      return { seriesUid: `${uidFor(kindIndex, n)}.${j + 1}`, number: j + 1, modality: kind.modality, description: desc, instances: Math.max(1, share) };
    });
    const arriving = i < 2; // the two newest are still coming in, minutes old
    if (arriving) taken.setTime(now - between(2, 6) * 60_000);
    out.push({
      id: `sample-${kind.modality.toLowerCase()}-${n}`,
      studyUid: uidFor(kindIndex, n),
      patientName: patient.name,
      patientId: patient.id,
      patientSex: patient.sex,
      patientBirthDate: patient.birth,
      studyDate: dicomDate(taken),
      studyTime: dicomTime(taken),
      description: `${kind.modality} ${pick(kind.descriptions)}`,
      accession: `A26${pad(1000 + i * 7 + between(0, 6), 6)}`,
      modalities: [kind.modality],
      instances: arriving ? Math.max(1, Math.floor(instances / 3)) : instances,
      stable: !arriving,
      lastUpdate: new Date(taken.getTime() + 300_000).toISOString(),
      labels: rnd() < 0.22 ? ['referrer-shared'] : [],
      claim: null,
      read: null,
      kind,
      image: between(1, kind.images),
      series,
      takenAt: taken.getTime(),
    });
  }
  out.sort((a, b) => b.takenAt - a.takenAt);
  // Some studies are already claimed or read by colleagues (never the two
  // still arriving), so the list shows every state.
  for (const [i, s] of out.entries()) {
    if (!s.stable || i < 3) continue;
    const r = rnd();
    const who = pick(COLLEAGUES);
    if (r < 0.12) s.claim = { ...who, claimedAt: new Date(s.takenAt + 900_000).toISOString() } satisfies Claim;
    else if (r < 0.45) s.read = { ...who, readAt: new Date(s.takenAt + 3_600_000).toISOString() } satisfies Done;
  }
  return out;
}
