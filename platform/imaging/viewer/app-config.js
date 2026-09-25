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

    // ---- the reading tools (M5.2), as configuration ------------------------
    // OHIF 3.13 ships the tools a reading room needs: window/level with
    // presets, zoom, pan, cine, length, bidirectional, angle, Cobb angle,
    // ellipse, rectangle and freehand regions with statistics, probe,
    // calibration, magnify, invert, rotate and flip, reference lines,
    // crosshairs, MPR and 3D layouts, capture, the tag browser, and a
    // study browser that lists the patient's other studies for comparison.
    // The keys below are the ones the 3.13.10 bundle reads (MEASURED,
    // 24 Sep 2026); what is not named keeps OHIF's default.

    // Window presets for CT, by number key (1-7; OHIF's own five plus two
    // that PMC's CT reading uses). MR and X-ray have no fixed presets: their
    // values are relative to the image.
    'cornerstone.windowLevelPresets': {
      $merge: {
        CT: [
          { id: 'ct-soft-tissue', description: 'Soft tissue', window: '400', level: '40' },
          { id: 'ct-lung', description: 'Lung', window: '1500', level: '-600' },
          { id: 'ct-bone', description: 'Bone', window: '2500', level: '480' },
          { id: 'ct-brain', description: 'Brain', window: '80', level: '40' },
          { id: 'ct-liver', description: 'Liver', window: '150', level: '90' },
          { id: 'ct-mediastinum', description: 'Mediastinum', window: '350', level: '50' },
          { id: 'ct-stroke', description: 'Stroke', window: '40', level: '40' },
        ],
      },
    },

    // Every study of the patient the viewer knows of, newest first, so a
    // prior is one drag away. (OHIF's default; said here so it stays.)
    'studyBrowser.studyMode': { $set: 'all' },

    // No first-visit tour. A ward PC is shared, and every new Windows profile
    // would start it again; the reading list's help page carries the keys.
    'ohif.tours': { $set: [] },
  },
  autoPlayCine: true,

  // The patient's name, ID, sex and age stay in the header while reading:
  // 'visible' shows them; the person can collapse them for a screenshot.
  showPatientInfo: 'visible',
  // Measurements are tracked without the "start tracking?" questions.
  measurementTrackingMode: 'simplified',

  // The worklist is the PMC front door app (/pmc/, M2.3); OHIF is the viewer
  // only. Its home link lands on / and the front door sends that to /pmc/.
  showStudyList: false,

  // PMC's mark and name in the viewer's header, in place of OHIF's logo, and a
  // way back to the reading list (README.md, Branding). The mark is the front
  // door's /brand/ file. whiteLabeling.createLogoComponentFn is the hook the
  // 3.13.10 header calls (MEASURED from the bundle, 24 Sep 2026).
  whiteLabeling: {
    createLogoComponentFn: (React) =>
      React.createElement(
        'a',
        {
          href: '/pmc/',
          // In the reading room the viewer is framed: the link leaves the
          // room, never loads the list inside the frame.
          target: '_top',
          title: 'Back to the PMC Imaging reading list',
          style: {
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            color: '#FFFFFF',
            textDecoration: 'none',
            whiteSpace: 'nowrap',
          },
        },
        React.createElement('img', {
          src: '/brand/pmc-mark-white.png',
          alt: '',
          width: 200,
          height: 183,
          style: { height: '26px', width: 'auto' },
        }),
        React.createElement(
          'b',
          {
            style: {
              fontFamily: '"Aptos Display", Aptos, "Segoe UI", system-ui, sans-serif',
              fontSize: '16px',
              fontWeight: 800,
              letterSpacing: '-0.01em',
            },
          },
          'PMC ',
          React.createElement('span', { style: { color: '#DBE6F6' } }, 'Imaging')
        )
      ),
  },

  // OHIF's own "investigational use" notice, shown once per browser session
  // (its default). Whether PMC keeps it is a governance decision for Dada.
  investigationalUseDialog: { option: 'always' },

  // Decoders run in web workers: one fewer than the PC's cores, 2 to 7.
  // OHIF's fixed 3 suited neither a 2-core ward PC nor an 8-core reading
  // room PC (INFERRED; the cloud build host has 4, so it measures 3 either way).
  maxNumberOfWebWorkers: Math.max(2, Math.min(7, (navigator.hardwareConcurrency || 4) - 1)),
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
