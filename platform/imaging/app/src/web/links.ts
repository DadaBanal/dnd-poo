// Where the page sends people and images: the viewer, and the engine's
// thumbnails, all on this origin and by relative path. The page never learns
// an engine address.
import type { Study } from '../shared/api.ts';
import { markOpened } from './api.ts';

// The viewer lives in one named window, which stays on the second screen; the
// next study opens in that same window.
export const VIEWER_WINDOW = 'pmc-viewer';

export const viewerUrl = (s: Study) => `/viewer?StudyInstanceUIDs=${encodeURIComponent(s.studyUid)}`;

// Two studies side by side, the current one and a prior, in OHIF's compare
// layout: a hanging protocol named in the address, which the 3.13.10 bundle
// reads (MEASURED, 25 Sep 2026).
export const compareUrl = (s: Study, prior: Study) =>
  `/viewer?StudyInstanceUIDs=${encodeURIComponent(s.studyUid)},${encodeURIComponent(prior.studyUid)}&hangingProtocolId=@ohif/hpCompare`;

export function openViewer(s: Study, url = viewerUrl(s)): void {
  markOpened(s.studyUid);
  window.open(url, VIEWER_WINDOW);
}

// The engine renders a study's or a series' first image small, through the
// front door (the person's own session; never cached, like every image).
export const thumbnailUrl = (studyUid: string, size = 96) =>
  `/dicom-web/studies/${encodeURIComponent(studyUid)}/thumbnail?viewport=${size},${size}`;
export const seriesThumbnailUrl = (studyUid: string, seriesUid: string, size = 96) =>
  `/dicom-web/studies/${encodeURIComponent(studyUid)}/series/${encodeURIComponent(seriesUid)}/thumbnail?viewport=${size},${size}`;
