/** @type {AppTypes.Config} */
//
// PMC's viewer: OHIF 3.13.10, configured only here (Path A, M2). Versioned in
// git, mounted into the stock image, which is pinned by digest in compose.yaml.
//
// The option names below are the ones the 3.13.10 bundle reads (MEASURED from
// the image, 23 Sep 2026), starting from OHIF's own secure default config.

window.config = {
  name: 'pmc',
  // Served at the root of the front door's origin; the viewer's address is
  // /viewer?StudyInstanceUIDs=<uid>.
  routerBasename: null,
  extensions: [],
  modes: [],

  // Cine: a cathlab or echo run opens already playing. For coronary runs that
  // is the first thing a reader needs, and on 1 Sep Dada was hunting for
  // playback in OHIF's layout menu (MEASURED, WS23). Two settings do it:
  //   autoCineModalities  which modalities open with the cine player on.
  //     OHIF 3.13's default is ['OT', 'US'] (MEASURED from the bundle): it
  //     leaves out XA, so a cathlab run opened as a still. RF is fluoroscopy.
  //   autoPlayCine        with the player on, start playing at once.
  customizationService: {
    autoCineModalities: { $set: ['XA', 'RF', 'US', 'OT'] },
  },
  autoPlayCine: true,

  // M2.1: OHIF's own study list stands in as the worklist. It goes off when
  // the PMC front door (/pmc/) arrives in M2.3.
  showStudyList: true,

  // OHIF's own "investigational use" notice, shown once per browser session
  // (its default). Whether PMC keeps it is a governance decision for Dada.
  investigationalUseDialog: { option: 'always' },

  maxNumberOfWebWorkers: 3,
  showWarningMessageForCrossOrigin: false,
  showCPUFallbackMessage: true,
  showLoadingIndicator: true,
  strictZSpacingForVolumeViewport: true,
  groupEnabledModesFirst: true,
  // HTTP/2 at the front door lets the viewer keep many requests in flight.
  maxNumRequests: {
    interaction: 100,
    thumbnail: 5,
    prefetch: 25,
  },
  showErrorDetails: 'production',

  defaultDataSourceName: 'pmc',
  dataSources: [
    {
      namespace: '@ohif/extension-default.dataSourcesModule.dicomweb',
      sourceName: 'pmc',
      configuration: {
        friendlyName: 'PMC imaging engine',
        name: 'pmc',
        // Same origin, relative: the viewer never learns an engine address.
        wadoUriRoot: '/wado',
        qidoRoot: '/dicom-web',
        wadoRoot: '/dicom-web',
        qidoSupportsIncludeField: true,
        imageRendering: 'wadors',
        thumbnailRendering: 'wadors',
        enableStudyLazyLoad: true,
        supportsFuzzyMatching: false,
        supportsWildcard: true,
        staticWado: false,
        singlepart: 'bulkdata,video',
        bulkDataURI: {
          enabled: true,
          relativeResolution: 'studies',
        },
        omitQuotationForMultipartRequest: true,
        dicomUploadEnabled: false,
      },
    },
  ],
};
