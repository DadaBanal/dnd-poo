/* ---- config (overridable by pmc-portal.config.json beside this file) ----- */
const DEFAULTS = {
  apiBase: '../',                       // this page lives at /pmc/, Orthanc's API is at /
  siteName: 'PMC Imaging',
  environment: 'Diagnostic archive',
  pageSize: 300,
  viewers: {
    // {orthancId} = Orthanc's study id, {studyUid} = StudyInstanceUID
    ohif:   'ohif/viewer/dicomjson?url=../studies/{orthancId}/ohif-dicom-json',
    stone:  'stone-webviewer/index.html?study={studyUid}',
    osimis: 'osimis-viewer/app/index.html?study={orthancId}',
    explorer: 'ui/app/index.html'
  },
  features: { thumbnails: true, download: true, send: false }
};
let CFG = structuredClone(DEFAULTS);

