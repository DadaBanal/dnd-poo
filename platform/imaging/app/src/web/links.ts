// Where the page sends people and images: the viewer, and the engine's
// thumbnails, all on this origin and by relative path. The page never learns
// an engine address.
//
// The clickable sample (demo.tsx) stands in for the front door: it says
// where its pictures and its viewer page are, and where home and sign-out
// go. On the platform nothing is installed and the paths below apply.
import type { Study } from '../shared/api.ts';
import { markOpened } from './api.ts';

export interface Sample {
  thumb(studyUid: string, size: number): string;
  seriesThumb(studyUid: string, seriesUid: string, size: number): string;
  viewer(studyUid: string, priorUid?: string): string;
  site: { home: string; signOut: string; brand: (file: string) => string };
}
declare global {
  interface Window {
    __pmcSample?: Sample;
  }
}
const sample = (): Sample | undefined => (typeof window === 'undefined' ? undefined : window.__pmcSample);

export const site = {
  home: () => sample()?.site.home ?? '/pmc/',
  signOut: () => sample()?.site.signOut ?? '/oauth2/sign_out',
  brand: (file: string) => sample()?.site.brand(file) ?? `/brand/${file}`,
};

// The viewer lives in one named window, which stays on the second screen; the
// next study opens in that same window.
export const VIEWER_WINDOW = 'pmc-viewer';

export const viewerFrameUrl = (studyUid: string) =>
  sample()?.viewer(studyUid) ?? `/viewer?StudyInstanceUIDs=${encodeURIComponent(studyUid)}`;
export const viewerUrl = (s: Study) => viewerFrameUrl(s.studyUid);

// Two studies side by side, the current one and a prior, in OHIF's compare
// layout: a hanging protocol named in the address, which the 3.13.10 bundle
// reads (MEASURED, 25 Sep 2026).
export const compareUrl = (s: Study, prior: Study) =>
  sample()?.viewer(s.studyUid, prior.studyUid)
  ?? `/viewer?StudyInstanceUIDs=${encodeURIComponent(s.studyUid)},${encodeURIComponent(prior.studyUid)}&hangingProtocolId=@ohif/hpCompare`;

export function openViewer(s: Study, url = viewerUrl(s)): void {
  markOpened(s.studyUid);
  window.open(url, VIEWER_WINDOW);
}

// The engine renders a study's or a series' first image small, through the
// front door (the person's own session; never cached, like every image).
export const thumbnailUrl = (studyUid: string, size = 96) =>
  sample()?.thumb(studyUid, size) ?? `/dicom-web/studies/${encodeURIComponent(studyUid)}/thumbnail?viewport=${size},${size}`;
export const seriesThumbnailUrl = (studyUid: string, seriesUid: string, size = 96) =>
  sample()?.seriesThumb(studyUid, seriesUid, size)
  ?? `/dicom-web/studies/${encodeURIComponent(studyUid)}/series/${encodeURIComponent(seriesUid)}/thumbnail?viewport=${size},${size}`;
