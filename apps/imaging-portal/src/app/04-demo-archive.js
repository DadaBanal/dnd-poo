/* ---- sample archive (used when nothing answers, or with ?demo=1) --------- */
const Demo = (() => {
  const MOD = ['XA','CT','CR','US','MR','DX','NM','MG'];
  const DESC = {
    XA: ['Coronary angiography','PCI — LAD','Left heart catheterisation','Peripheral angiogram','PTCA + stent'],
    CT: ['CT chest with contrast','CT stonogram','CT head plain','CT whole abdomen','CT angiogram — aorta'],
    CR: ['Chest PA','Chest PA + lateral','Abdomen supine','Pelvis AP'],
    US: ['Whole abdomen ultrasound','2D echo with Doppler','KUB ultrasound','Pelvic ultrasound'],
    MR: ['MRI lumbosacral spine','MRI brain plain','MRI knee'],
    DX: ['Chest DX','Extremity DX — wrist'],
    NM: ['Myocardial perfusion scan'],
    MG: ['Screening mammography']
  };
  const rnd = (seed => () => (seed = seed * 16807 % 2147483647) / 2147483647)(20260906);
  const pick = a => a[Math.floor(rnd() * a.length)];
  const studies = [];
  const now = new Date();
  for (let i = 0; i < 46; i++) {
    const m = i < 16 ? 'XA' : pick(MOD);
    const back = i < 10 ? 0 : i < 16 ? 1 : Math.floor(rnd() * 40);
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() - back,
      8 + Math.floor(rnd() * 10), Math.floor(rnd() * 60));
    const id = `demo-${String(i).padStart(3,'0')}`;
    const nSeries = m === 'XA' ? 3 + Math.floor(rnd()*8) : 1 + Math.floor(rnd()*4);
    studies.push({
      ID: id, Type: 'Study',
      MainDicomTags: {
        StudyDate: ymd(d), StudyTime: `${pad(d.getHours())}${pad(d.getMinutes())}00`,
        StudyDescription: pick(DESC[m]), AccessionNumber: `ACC${26000 + i * 7}`,
        StudyInstanceUID: `1.2.826.0.1.3680043.10.999.${1000 + i}.${d.getTime()}`,
        InstitutionName: 'Premiere Medical Center Nueva Ecija',
        ReferringPhysicianName: 'SAMPLE^REFERRER'
      },
      PatientMainDicomTags: {
        PatientName: `DEMO^PATIENT^${String(i + 1).padStart(2,'0')}`,
        PatientID: `PMC-${240000 + i * 13}`,
        PatientBirthDate: `${1945 + Math.floor(rnd()*55)}${pad(1+Math.floor(rnd()*12))}${pad(1+Math.floor(rnd()*28))}`,
        PatientSex: rnd() > .5 ? 'M' : 'F'
      },
      RequestedTags: {
        ModalitiesInStudy: m,
        NumberOfStudyRelatedSeries: String(nSeries),
        NumberOfStudyRelatedInstances: String(m === 'XA' ? nSeries * (40 + Math.floor(rnd()*90)) : nSeries * (1 + Math.floor(rnd()*140)))
      },
      Series: Array.from({ length: nSeries }, (_, s) => `${id}-s${s}`),
      IsStable: true, LastUpdate: d.toISOString().replace(/[-:]/g,'').slice(0,15)
    });
  }
  // procedural thumbnails so the sample looks like imaging without being anyone's scan
  const cache = new Map();
  function thumb(mod, seed = 1) {
    const key = mod + seed; if (cache.has(key)) return cache.get(key);
    const c = document.createElement('canvas'); c.width = 320; c.height = 240;
    const x = c.getContext('2d');
    const g = x.createRadialGradient(160, 96, 10, 160, 120, 210);
    g.addColorStop(0, '#4a5563'); g.addColorStop(.55, '#1d242e'); g.addColorStop(1, '#05070a');
    x.fillStyle = g; x.fillRect(0, 0, 320, 240);
    let s = seed * 9301 + 49297; const r = () => ((s = s * 9301 + 49297) % 233280) / 233280;
    if (mod === 'XA' || mod === 'MR') {
      x.strokeStyle = 'rgba(230,238,248,.55)';
      for (let i = 0; i < 7; i++) {
        x.beginPath(); x.lineWidth = .8 + r() * 2.6;
        let px = 40 + r() * 240, py = 20 + r() * 60;
        x.moveTo(px, py);
        for (let k = 0; k < 5; k++) { px += (r() - .45) * 70; py += 22 + r() * 26; x.quadraticCurveTo(px + 18, py - 12, px, py); }
        x.stroke();
      }
    } else if (mod === 'CT' || mod === 'NM') {
      x.strokeStyle = 'rgba(220,232,246,.42)'; x.lineWidth = 1.4;
      x.beginPath(); x.ellipse(160, 122, 88, 70, 0, 0, 7); x.stroke();
      x.beginPath(); x.ellipse(132, 118, 28, 34, .3, 0, 7); x.stroke();
      x.beginPath(); x.ellipse(190, 118, 28, 34, -.3, 0, 7); x.stroke();
    } else {
      x.strokeStyle = 'rgba(226,236,248,.40)'; x.lineWidth = 1.2;
      for (let i = 0; i < 9; i++) { x.beginPath(); x.moveTo(70, 60 + i * 16); x.quadraticCurveTo(160, 44 + i * 16, 250, 62 + i * 16); x.stroke(); }
      x.beginPath(); x.moveTo(160, 40); x.lineTo(160, 200); x.stroke();
    }
    for (let i = 0; i < 2600; i++) { x.fillStyle = `rgba(255,255,255,${r() * .05})`; x.fillRect(r() * 320, r() * 240, 1, 1); }
    x.font = '600 13px system-ui'; x.fillStyle = 'rgba(255,255,255,.55)'; x.fillText('SAMPLE', 12, 226);
    const url = c.toDataURL('image/jpeg', .72); cache.set(key, url); return url;
  }

  /* A synthetic 16-bit slice. The sample dataset is not a picture of an image:
     it is stored values with a rescale, so the viewer's window/level, region
     statistics and pixel probe run down exactly the same code path they will on
     a real archive -- and every number on screen is arithmetic on invented data. */
  const frameCacheDemo = new Map();
  function demoPixels(seriesId, index, mod) {
    const key = `${seriesId}#${index}`;
    if (frameCacheDemo.has(key)) return frameCacheDemo.get(key);
    const w = 256, h = 256, data = new Int16Array(w * h);
    const INTERCEPT = -1024;
    let s = (index + 1) * 7919 + seriesId.length * 104729;
    const r = () => ((s = (s * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
    const cx = 128, cy = 132, bodyRx = 104, bodyRy = 88;
    const nodX = 92 + index * 1.4, nodY = 104 + Math.sin(index / 3) * 8;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const e = ((x - cx) / bodyRx) ** 2 + ((y - cy) / bodyRy) ** 2;
      let hu;
      if (e > 1) hu = -1000;                                              // air
      else if (e > 0.86) hu = 380 + r() * 120;                            // body wall and ribs
      else if (mod === 'CT' || mod === 'NM' || mod === 'MR') {
        const lungL = ((x - 88) / 42) ** 2 + ((y - 120) / 56) ** 2;
        const lungR = ((x - 170) / 42) ** 2 + ((y - 120) / 56) ** 2;
        hu = (lungL < 1 || lungR < 1) ? -780 + r() * 90 : 42 + r() * 22;
        if ((x - 128) ** 2 / 400 + (y - 178) ** 2 / 260 < 1) hu = 130;    // spine
        if ((x - nodX) ** 2 + (y - nodY) ** 2 < 46) hu = 60 + index * 6;  // the thing that moves
      } else {
        hu = 30 + r() * 40 + Math.sin(y / 9 + index / 4) * 55;            // soft, layered
        if (Math.abs(x - 128) < 4) hu = 300;
      }
      data[y * w + x] = Math.round(hu) - INTERCEPT;
    }
    const out = { kind: 'pixels', data, w, h, ch: 1, dtype: '<i2' };
    if (frameCacheDemo.size > 90) frameCacheDemo.clear();
    frameCacheDemo.set(key, out);
    return out;
  }
  return {
    base: 'demo://', url: () => '',
    studies, thumb, pixels: demoPixels,
    async req(path, opts = {}) {
      await new Promise(r => setTimeout(r, 70 + Math.random() * 120));
      const p = String(path).replace(/^\//, '');
      if (p === 'system') return { Name: 'PMC-ORTHANC01 (sample)', Version: '1.13.0', ApiVersion: 21,
        DatabaseVersion: 6, DatabaseBackendPlugin: 'odbc-index', StorageAreaPlugin: null,
        DicomAet: 'PMCORTHANC', DicomPort: 4242, IsHttpServerSecure: true, PluginsEnabled: true };
      if (p === 'plugins') return ['dicom-web','stone-webviewer','ohif','orthanc-explorer-2','odbc-index','gdcm','transfers'];
      if (p.startsWith('plugins/')) { const id = p.split('/')[1];
        return { ID: id, Version: { 'dicom-web':'1.24','stone-webviewer':'3.0','ohif':'1.8','orthanc-explorer-2':'1.15.0','odbc-index':'1.3','gdcm':'1.7','transfers':'1.7' }[id] || '1.0',
          Description: id, RootUri: id === 'ohif' ? '/ohif/' : id === 'stone-webviewer' ? '/stone-webviewer/' : null };
      }
      if (p === 'statistics') return { CountPatients: 41, CountStudies: studies.length, CountSeries: 214,
        CountInstances: 18422, TotalDiskSize: String(96 * 1024 ** 3), TotalDiskSizeMB: 98304 };
      // RFC 5737 documentation addresses. They matched no real device even
      // before, but they sat inside PMC's own subnet range; the repository fence
      // says new code carries no internal topology, and a sample dataset is new
      // code every time it is read. The real addresses come from Orthanc at
      // runtime and are never written down here.
      if (p === 'modalities?expand' || p === 'modalities') return {
        azurion:  { AET: 'AZURION',  Host: '192.0.2.61', Port: 104, Manufacturer: 'Generic' },
        voyager:  { AET: 'VOYAGER',  Host: '192.0.2.60', Port: 104, Manufacturer: 'Generic' },
        pacsview: { AET: 'PMCVIEW1', Host: '192.0.2.77', Port: 11112, Manufacturer: 'Generic' }
      };
      if (/^modalities\/.+\/echo$/.test(p)) { if (p.includes('azurion')) throw new ApiError(500, 'no answer', p); return null; }
      if (p.startsWith('changes')) return { Changes: studies.slice(0, 12).map((s, i) => ({
        Seq: 9000 - i, ChangeType: i % 3 ? 'NewStudy' : 'StableStudy', ResourceType: 'Study', ID: s.ID,
        Date: `${s.MainDicomTags.StudyDate}T${s.MainDicomTags.StudyTime}` })), Done: true, Last: 9000 };
      if (p.startsWith('jobs')) return [
        { ID: 'j1', Type: 'Archive', State: 'Success', Progress: 100, CreationTime: '20260906T081200' },
        { ID: 'j2', Type: 'DicomModalityStore', State: 'Success', Progress: 100, CreationTime: '20260906T074500' },
        { ID: 'j3', Type: 'Media', State: 'Running', Progress: 42, CreationTime: '20260906T092000' }];
      if (p === 'tools/find') {
        const q = opts.body?.Query || {}; let out = studies.slice();
        if (q.StudyDate) { const [a, b] = q.StudyDate.split('-'); out = out.filter(s => {
          const d = s.MainDicomTags.StudyDate; return b ? d >= a && d <= b : d === a; }); }
        if (q.ModalitiesInStudy) out = out.filter(s => s.RequestedTags.ModalitiesInStudy === q.ModalitiesInStudy);
        for (const [k, v] of Object.entries(q)) {
          if (['StudyDate','ModalitiesInStudy'].includes(k)) continue;
          const rx = new RegExp(String(v).replace(/[.+?^${}()|[\]\\]/g,'\\$&').replace(/\*/g,'.*'), 'i');
          out = out.filter(s => rx.test(s.MainDicomTags[k] ?? s.PatientMainDicomTags[k] ?? ''));
        }
        return out;
      }
      const m = p.match(/^studies\/([^/]+)\/series(?:\?.*)?$/);
      if (m) { const st = studies.find(s => s.ID === m[1]); if (!st) throw new ApiError(404, '', p);
        return st.Series.map((sid, i) => ({ ID: sid, MainDicomTags: { SeriesNumber: String(i + 1),
          SeriesDescription: i === 0 ? 'Scout / survey' : `Acquisition ${i}`,
          Modality: st.RequestedTags.ModalitiesInStudy },
          Instances: Array.from({ length: 3 }, (_, k) => `${sid}-i${k}`) })); }
      const mi = p.match(/^series\/([^/]+)\/instances(?:\?.*)?$/);
      if (mi) return Array.from({ length: 24 }, (_, k) => ({ ID: `${mi[1]}-i${k}`, IndexInSeries: k + 1,
        MainDicomTags: { InstanceNumber: String(k + 1), NumberOfFrames: '1',
          SOPInstanceUID: `1.2.826.0.1.3680043.10.999.${mi[1].length}.${k}` } }));
      const mt = p.match(/^instances\/(.+?)-i(\d+)\/(?:simplified-)?tags$/);
      if (mt) { const st = studies.find(x => mt[1].startsWith(x.ID));
        const mod = st?.RequestedTags.ModalitiesInStudy || 'CT';
        return { Modality: mod, Rows: '256', Columns: '256', PixelSpacing: '0.72\\0.72',
          SliceThickness: '2.5', NumberOfFrames: '1', WindowCenter: '40', WindowWidth: '400',
          RescaleSlope: '1', RescaleIntercept: '-1024', PhotometricInterpretation: 'MONOCHROME2',
          BitsAllocated: '16', BitsStored: '16', PixelRepresentation: '1', SamplesPerPixel: '1',
          ImageOrientationPatient: '1\\0\\0\\0\\1\\0',
          ImagePositionPatient: `0\\0\\${(+mt[2] * 2.5).toFixed(1)}`,
          SeriesDescription: 'Sample acquisition', StudyDescription: st?.MainDicomTags.StudyDescription || '',
          PatientName: st?.PatientMainDicomTags.PatientName || '', KVP: '120', XRayTubeCurrent: '180' }; }
      const m2 = p.match(/^studies\/([^/]+)$/);
      if (m2) { const st = studies.find(s => s.ID === m2[1]); if (!st) throw new ApiError(404, '', p); return st; }
      throw new ApiError(404, 'not in the sample dataset', p);
    },
    get(p, o) { return this.req(p, o); },
    post(p, body, o) { return this.req(p, { ...o, body }); }
  };
})();

let API = Live;                 // swapped for Demo when nothing answers
const state = {
  demo: false, view: 'worklist', layout: store.get('layout', 'cards'),
  scope: store.get('scope', 'today'), mod: null, q: '',
  studies: [], cursor: -1, sort: { key: 'date', dir: -1 },
  system: null, plugins: [], viewers: [], took: 0, scopeTouched: false
};
