/* ---- config (overridable by pmc-portal.config.json beside this file) ----- */
const DEFAULTS = {
  apiBase: '../',                       // this page lives at /pmc/, Orthanc's API is at /
  siteName: 'PMC Imaging',
  environment: 'Diagnostic archive',
  pageSize: 300,
  viewers: {
    // {orthancId} = Orthanc's study id, {studyUid} = StudyInstanceUID
    //
    // OHIF's route depends on which data source the plugin is configured for,
    // and getting it wrong opens an empty viewer. PMC-ORTHANC01 has
    // `OHIF.DataSource = dicom-web` (MEASURED, cutover handoff 2 Sep 2026), and
    // the DICOMweb route is `/viewer?StudyInstanceUIDs=` (VERIFIED 9 Sep 2026,
    // docs.ohif.org/configuration/url/). The DICOM-JSON route,
    // `/viewer/dicomjson?url=` (VERIFIED, same source), is what a server
    // configured for `dicom-json` needs -- put it in pmc-portal.config.json
    // there rather than changing this default.
    ohif:   'ohif/viewer?StudyInstanceUIDs={studyUid}',
    stone:  'stone-webviewer/index.html?study={studyUid}',
    osimis: 'osimis-viewer/app/index.html?study={orthancId}',
    explorer: 'ui/app/index.html'
  },
  features: { thumbnails: true, download: true, send: false }
};
let CFG = structuredClone(DEFAULTS);

// Which build of this page you are looking at. Filled in at build time; the date
// is the baseline date, not the day it was assembled, so the artifact stays
// reproducible. It is on the System screen because after an update the only
// honest way to know the new file landed is for the page to say so itself.
const PORTAL_BUILD = document.querySelector('meta[name="pmc-build"]')?.content || 'unknown';

