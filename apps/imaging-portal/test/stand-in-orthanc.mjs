/**
 * A stand-in Orthanc, faithful to the one at PMC on the points that matter:
 *
 *  - it serves the portal from /pmc/ and its own REST API from /, so the page
 *    runs at exactly the same relative paths it will in production;
 *  - its index REFUSES `OrderBy` with HTTP 500, the way the ODBC index 1.3 does
 *    (OdbcIndex::HasFindSupport() returns false). That is the fault the portal
 *    exists to work around, so the tests must be able to see it;
 *  - one configured modality answers C-ECHO and one is silent, which is the
 *    measured state of azurion/voyager;
 *  - it serves real pixels: /rendered applies the VOI window server-side and
 *    /numpy hands back a genuine .npy buffer, so the viewer's two data paths are
 *    both exercised. Series 3 of every study answers 415 on /numpy, which is how
 *    a transfer syntax Orthanc cannot decode to an array behaves -- the viewer
 *    must fall back to /rendered rather than show nothing.
 *
 * Every request is recorded so a test can assert on what the page did NOT send.
 */
import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
import { deflateSync } from 'node:zlib';

const pad = n => String(n).padStart(2, '0');
const ymd = d => `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`;

/** A real 8x8 PNG, built here so the suite needs no binary fixture. */
function png(grey = 0x80) {
  const w = 8, h = 8;
  const raw = Buffer.concat(Array.from({ length: h }, () => Buffer.concat([Buffer.from([0]), Buffer.alloc(w * 3, grey)])));
  const crcTable = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
  const crc = b => { let c = 0xffffffff; for (const x of b) c = crcTable[(c ^ x) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  const chunk = (type, data) => { const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type, 'ascii'), data]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(td));
    return Buffer.concat([len, td, c]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}
const PREVIEW = png();

/* ---------------------------------------------------------------- pixels ---
   A synthetic 16-bit phantom, so the viewer's window/level, region statistics
   and pixel probe can be asserted against values known in advance rather than
   against "the picture looks different".

   Stored values follow the CT convention the viewer has to handle: the archive
   holds `stored`, and HU = stored * RescaleSlope + RescaleIntercept, with
   slope 1 and intercept -1024. So air (-1000 HU) is stored as 24, soft tissue
   (40 HU) as 1064, bone (800 HU) as 1824. The disc at the centre steps with the
   frame index, which is what lets a test prove the stack actually moved.       */
const PHANTOM = { rows: 96, cols: 96, slope: 1, intercept: -1024, wc: 40, ww: 400,
  spacing: '0.6\\0.6', thickness: '1.5' };

function phantomFrame(frame = 0) {
  const { rows, cols } = PHANTOM;
  const out = new Int16Array(rows * cols);
  const cx = (cols - 1) / 2, cy = (rows - 1) / 2;
  for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) {
    const r = Math.hypot(x - cx, y - cy);
    let hu;
    if (r > 42) hu = -1000;                       // air outside the phantom
    else if (r > 36) hu = 800;                    // bone-density ring
    else if (r < 8) hu = -100 + frame * 40;       // the disc that steps per frame
    else hu = 40;                                 // soft tissue
    out[y * cols + x] = hu - PHANTOM.intercept;   // store, do not window
  }
  return out;
}

/** Encode a greyscale 8-bit PNG. Same chunk writer as png(), one channel. */
function greyPng(pixels, w, h) {
  const raw = Buffer.alloc(h * (w + 1));
  for (let y = 0; y < h; y++) { raw[y * (w + 1)] = 0;
    for (let x = 0; x < w; x++) raw[y * (w + 1) + 1 + x] = pixels[y * w + x]; }
  const crcTable = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
  const crc = b => { let c = 0xffffffff; for (const x of b) c = crcTable[(c ^ x) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  const chunk = (type, data) => { const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type, 'ascii'), data]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(td));
    return Buffer.concat([len, td, c]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 0;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}

/** Apply the DICOM linear VOI LUT, exactly as PS3.3 C.11.2.1.2 states it. */
function windowTo8bit(stored, wc, ww) {
  const out = new Uint8Array(stored.length);
  const lo = wc - 0.5 - (ww - 1) / 2, span = ww - 1;
  for (let i = 0; i < stored.length; i++) {
    const hu = stored[i] * PHANTOM.slope + PHANTOM.intercept;
    let v = ((hu - lo) / span) * 255;
    out[i] = v <= 0 ? 0 : v >= 255 ? 255 : Math.round(v);
  }
  return out;
}

/** A .npy file, little-endian, shape (frame, height, width, channel). */
function npy(data, shape, descr) {
  const header = `{'descr': '${descr}', 'fortran_order': False, 'shape': (${shape.join(', ')}), }`;
  const prefixLen = 10;                                   // magic + version + uint16 length
  const padded = header + ' '.repeat((64 - ((prefixLen + header.length + 1) % 64)) % 64) + '\n';
  const head = Buffer.alloc(prefixLen);
  Buffer.from([0x93]).copy(head, 0); head.write('NUMPY', 1, 'ascii');
  head[6] = 1; head[7] = 0; head.writeUInt16LE(padded.length, 8);
  return Buffer.concat([head, Buffer.from(padded, 'latin1'), Buffer.from(data.buffer, data.byteOffset, data.byteLength)]);
}

/** 64 studies across eight modalities; a third of them dated today. */
function buildArchive() {
  const MODS = ['XA', 'CT', 'CR', 'US', 'MR', 'DX', 'NM', 'MG'];
  // Invented names only. Never copy real patient names out of the archive or the
  // record into a fixture: this file is committed. "Dela Cruz, Juan" is the
  // standing placeholder and also exercises the multi-word surname formatting.
  const NAMES = [['DELA CRUZ', 'JUAN'], ['SAMPLE', 'ALPHA'], ['SAMPLE', 'BRAVO'], ['TEST PATIENT', 'CHARLIE'],
    ['FIXTURE', 'DELTA'], ['FIXTURE', 'ECHO'], ['EXAMPLE', 'FOXTROT'], ['PLACEHOLDER', 'GOLF']];
  const DESC = { XA: 'Coronary angiography', CT: 'CT chest with contrast', CR: 'Chest PA', US: 'Whole abdomen ultrasound',
    MR: 'MRI lumbar spine', DX: 'Pelvis AP', NM: 'Bone scan', MG: 'Bilateral mammography' };
  const now = new Date(), studies = [];
  for (let i = 0; i < 64; i++) {
    const mod = MODS[i % MODS.length], [fam, giv] = NAMES[i % NAMES.length];
    const daysAgo = i < 21 ? 0 : i < 34 ? (i % 6) + 1 : (i % 90) + 8;
    const d = new Date(now.getTime() - daysAgo * 864e5);
    const id = `study-${String(i).padStart(3, '0')}`;
    const nSeries = 1 + (i % 4);
    studies.push({
      ID: id, Type: 'Study',
      MainDicomTags: { StudyDate: ymd(d), StudyTime: `${pad(8 + (i % 10))}${pad(i % 60)}00`,
        StudyDescription: DESC[mod], AccessionNumber: `ACC${String(100000 + i)}`,
        StudyInstanceUID: `1.2.826.0.1.3680043.8.498.${10000 + i}`, ReferringPhysicianName: 'LORIAGA^JOHNRICH' },
      PatientMainDicomTags: { PatientName: `${fam}^${giv}^^^`, PatientID: `PID${String(700000 + i)}`,
        PatientSex: i % 2 ? 'F' : 'M', PatientBirthDate: `19${60 + (i % 40)}0${1 + (i % 9)}15` },
      Series: Array.from({ length: nSeries }, (_, k) => `${id}-series-${k}`),
      RequestedTags: { ModalitiesInStudy: mod, NumberOfStudyRelatedSeries: String(nSeries),
        NumberOfStudyRelatedInstances: String(nSeries * 40) },
      _mod: mod
    });
  }
  return studies;
}

// Addresses are RFC 5737 documentation range on purpose.
const MODALITIES = {
  azurion: { AET: 'IENGINE_SCU', Host: '192.0.2.51', Port: 29536, _answers: true },
  voyager: { AET: 'AE-VOYAGER', Host: '192.0.2.93', Port: 104, _answers: false }
};
const PLUGINS = ['dicom-web', 'stone-webviewer', 'ohif', 'orthanc-explorer-2', 'odbc-index', 'gdcm', 'transfers'];
const PLUGIN_INFO = {
  'dicom-web': { Version: '1.24', Description: 'Implementation of DICOMweb' },
  'stone-webviewer': { Version: '3.0', Description: 'Stone Web viewer' },
  ohif: { Version: '1.8', Description: 'OHIF plugin' },
  'orthanc-explorer-2': { Version: '1.15.0', Description: 'Orthanc Explorer 2' },
  'odbc-index': { Version: '1.3', Description: 'ODBC index' },
  gdcm: { Version: '1.8', Description: 'GDCM decoder' },
  transfers: { Version: '1.7', Description: 'Transfers accelerator' }
};

export function startStandInOrthanc({ portalHtml, config = null, expandSupported = true,
                                     childExpandSupported = true } = {}) {
  const studies = buildArchive();
  const requests = [];
  const json = (res, body, code = 200) => { res.writeHead(code, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(body)); };

  const server = createServer(async (req, res) => {
    const url = new URL(req.url, 'http://localhost');
    const path = decodeURIComponent(url.pathname).replace(/^\/+/, '');
    let body = '';
    for await (const c of req) body += c;
    requests.push({ method: req.method, path, search: url.search, body });

    // --- the portal itself, served exactly where Orthanc's ServeFolders puts it
    if (path === 'pmc/' || path === 'pmc/index.html') {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }); return res.end(portalHtml);
    }
    if (path === 'pmc/pmc-portal.config.json') {
      // Optional. When the installer has not written one, ServeFolders 404s and
      // the page falls back to its built-in defaults -- expected, not a fault.
      if (!config) { res.writeHead(404, { 'Content-Type': 'text/plain' }); return res.end('not found'); }
      return json(res, config);
    }

    // --- Orthanc REST API
    if (path === 'system') return json(res, { Name: 'PMC-ORTHANC01 (stand-in)', Version: '1.13.0', ApiVersion: 21,
      DatabaseBackendPlugin: 'odbc-index', DicomAet: 'PMC-ORTHANC', DicomPort: 4242 });
    if (path === 'plugins') return json(res, PLUGINS);
    if (path.startsWith('plugins/')) { const id = path.slice(8);
      return json(res, { ID: id, ...(PLUGIN_INFO[id] || { Version: '?' }) }); }

    if (path === 'tools/find' && req.method === 'POST') {
      const q = JSON.parse(body || '{}');
      // The ODBC index cannot order in the database. Orthanc surfaces that as a 500.
      if ('OrderBy' in q) { res.writeHead(500, { 'Content-Type': 'text/plain' });
        return res.end("The database backend doesn't support ordering"); }
      const Q = q.Query || {};
      let out = studies.filter(s => {
        if (Q.StudyDate) {
          const [from, to] = Q.StudyDate.includes('-') ? Q.StudyDate.split('-') : [Q.StudyDate, Q.StudyDate];
          if (s.MainDicomTags.StudyDate < from || s.MainDicomTags.StudyDate > to) return false;
        }
        if (Q.ModalitiesInStudy && s._mod !== Q.ModalitiesInStudy) return false;
        const wild = (pat, val) => new RegExp('^' + String(pat).replace(/[.+^${}()|[\]\\]/g, '\\$&')
          .replace(/\*/g, '.*').replace(/\?/g, '.') + '$', 'i').test(val || '');
        if (Q.PatientName && !wild(Q.PatientName, s.PatientMainDicomTags.PatientName)) return false;
        if (Q.PatientID && !wild(Q.PatientID, s.PatientMainDicomTags.PatientID)) return false;
        if (Q.AccessionNumber && !wild(Q.AccessionNumber, s.MainDicomTags.AccessionNumber)) return false;
        if (Q.StudyInstanceUID && Q.StudyInstanceUID !== s.MainDicomTags.StudyInstanceUID) return false;
        return true;
      });
      if (q.Limit) out = out.slice(0, q.Limit);
      return json(res, out.map(({ _mod, ...s }) => (q.Expand ? s : s.ID)));
    }

    // A child listing is only expanded when ?expand is asked for. MEASURED 9 Sep
    // 2026: PMC's archive answers the bare form with ids, and code that reads
    // .ID off a string then requests `series//instances` and gets a bare 404.
    // `childExpandSupported: false` goes one worse and ignores ?expand entirely,
    // which is the shape the portal still has to survive.
    const expanded = () => childExpandSupported && url.searchParams.has('expand');

    let m;
    if ((m = path.match(/^studies\/([^/]+)\/series$/))) {
      const st = studies.find(s => s.ID === m[1]); if (!st) { res.writeHead(404); return res.end(); }
      if (!expanded()) return json(res, st.Series);
      return json(res, st.Series.map((sid, k) => ({ ID: sid, MainDicomTags: { SeriesNumber: String(k + 1),
        SeriesDescription: `${st._mod} series ${k + 1}`, Modality: st._mod },
        Instances: Array.from({ length: 40 }, (_, i) => `${sid}-inst-${i}`) })));
    }
    // Resolving one child by id, which is what the portal falls back to.
    if ((m = path.match(/^series\/(study-\d+-series-\d+)$/))) {
      const q = /^(study-\d+)-series-(\d+)$/.exec(m[1]);
      const st = studies.find(s => s.ID === q[1]); if (!st) { res.writeHead(404); return res.end(); }
      return json(res, { ID: m[1], MainDicomTags: { SeriesNumber: String(+q[2] + 1),
        SeriesDescription: `${st._mod} series ${+q[2] + 1}`, Modality: st._mod },
        Instances: Array.from({ length: 40 }, (_, i) => `${m[1]}-inst-${i}`) });
    }
    if ((m = path.match(/^instances\/(study-\d+-series-\d+-inst-\d+)$/))) {
      const q = /-inst-(\d+)$/.exec(m[1]);
      return json(res, { ID: m[1], IndexInSeries: +q[1] + 1,
        MainDicomTags: { InstanceNumber: String(+q[1] + 1) } });
    }
    // Every instance id carries its own coordinates: <study>-series-<k>-inst-<i>.
    const parseInst = id => { const q = /^(study-\d+)-series-(\d+)-inst-(\d+)$/.exec(id || '');
      return q ? { study: q[1], serie: +q[2], index: +q[3] } : null; };
    if ((m = path.match(/^series\/([^/]+)\/instances$/))) {
      const q = /^(study-\d+)-series-(\d+)$/.exec(m[1]); if (!q) { res.writeHead(404); return res.end(); }
      const st = studies.find(s => s.ID === q[1]); if (!st) { res.writeHead(404); return res.end(); }
      if (!expanded()) return json(res, Array.from({ length: 40 }, (_, i) => `${m[1]}-inst-${i}`));
      return json(res, Array.from({ length: 40 }, (_, i) => ({
        ID: `${m[1]}-inst-${i}`, IndexInSeries: i + 1,
        MainDicomTags: { InstanceNumber: String(i + 1), SOPInstanceUID: `1.2.826.0.1.3680043.8.498.9${q[2]}${String(i).padStart(3, '0')}`,
          ImagePositionPatient: `0\\0\\${(i * 1.5).toFixed(1)}`, ImageOrientationPatient: '1\\0\\0\\0\\1\\0' } })));
    }
    if ((m = path.match(/^instances\/([^/]+)\/(simplified-tags|tags)$/))) {
      const inst = parseInst(m[1]); if (!inst) { res.writeHead(404); return res.end(); }
      const st = studies.find(s => s.ID === inst.study); if (!st) { res.writeHead(404); return res.end(); }
      return json(res, { Modality: st._mod, Rows: String(PHANTOM.rows), Columns: String(PHANTOM.cols),
        PixelSpacing: PHANTOM.spacing, SliceThickness: PHANTOM.thickness, NumberOfFrames: '1',
        WindowCenter: String(PHANTOM.wc), WindowWidth: String(PHANTOM.ww),
        RescaleSlope: String(PHANTOM.slope), RescaleIntercept: String(PHANTOM.intercept),
        PhotometricInterpretation: 'MONOCHROME2', BitsAllocated: '16', BitsStored: '16', PixelRepresentation: '1',
        SamplesPerPixel: '1', ImageOrientationPatient: '1\\0\\0\\0\\1\\0',
        ImagePositionPatient: `0\\0\\${(inst.index * 1.5).toFixed(1)}`,
        SeriesDescription: `${st._mod} series ${inst.serie + 1}`, StudyDescription: st.MainDicomTags.StudyDescription,
        PatientName: st.PatientMainDicomTags.PatientName, PatientID: st.PatientMainDicomTags.PatientID,
        InstanceNumber: String(inst.index + 1), KVP: '120', XRayTubeCurrent: '200' });
    }
    if ((m = path.match(/^instances\/([^/]+)\/frames$/))) {
      if (!parseInst(m[1])) { res.writeHead(404); return res.end(); }
      return json(res, [0]);
    }
    if ((m = path.match(/^instances\/([^/]+)\/(?:frames\/(\d+)\/)?rendered$/))) {
      const inst = parseInst(m[1]); if (!inst) { res.writeHead(404); return res.end(); }
      const wc = url.searchParams.has('window-center') ? +url.searchParams.get('window-center') : PHANTOM.wc;
      const ww = url.searchParams.has('window-width') ? +url.searchParams.get('window-width') : PHANTOM.ww;
      const px = windowTo8bit(phantomFrame(inst.index), wc, ww);
      res.writeHead(200, { 'Content-Type': 'image/png', 'Cache-Control': 'no-store' });
      return res.end(greyPng(px, PHANTOM.cols, PHANTOM.rows));
    }
    if ((m = path.match(/^instances\/([^/]+)\/(?:frames\/(\d+)\/)?numpy$/))) {
      const inst = parseInst(m[1]); if (!inst) { res.writeHead(404); return res.end(); }
      // Series 3 stands in for a transfer syntax Orthanc will not decode to an
      // array. The viewer must notice and drop to the server-rendered path.
      if (inst.serie === 2) { res.writeHead(415, { 'Content-Type': 'text/plain' });
        return res.end('Cannot decode this image to a numpy array'); }
      res.writeHead(200, { 'Content-Type': 'application/octet-stream' });
      return res.end(npy(phantomFrame(inst.index), [1, PHANTOM.rows, PHANTOM.cols, 1], '<i2'));
    }
    if ((m = path.match(/^studies\/([^/]+)$/))) {
      const st = studies.find(s => s.ID === m[1]); if (!st) { res.writeHead(404); return res.end(); }
      const { _mod, ...rest } = st; return json(res, rest);
    }
    if (/^instances\/[^/]+\/(frames\/0\/)?preview$/.test(path)) {
      res.writeHead(200, { 'Content-Type': 'image/png' }); return res.end(PREVIEW);
    }
    if (path === 'modalities' && url.search === '?expand') {
      // Not every build honours ?expand; when it does not, the page must fall back.
      if (!expandSupported) { res.writeHead(404); return res.end(); }
      return json(res,
        Object.fromEntries(Object.entries(MODALITIES).map(([k, v]) => [k, { AET: v.AET, Host: v.Host, Port: v.Port }])));
    }
    if (path === 'modalities') return json(res, Object.keys(MODALITIES));
    if ((m = path.match(/^modalities\/([^/]+)\/echo$/)) && req.method === 'POST') {
      const mod = MODALITIES[m[1]];
      if (mod?._answers) { res.writeHead(200); return res.end(); }
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      return res.end(`DicomAssociation - connecting to AET "${mod?.AET}": TCP Initialization Error (Timeout)`);
    }
    if ((m = path.match(/^modalities\/([^/]+)$/))) {
      const mod = MODALITIES[m[1]]; if (!mod) { res.writeHead(404); return res.end(); }
      // The real Orthanc answers this with CHILD RESOURCES, not the settings --
      // the misread that caused the 8 Sep false alarm. Reproduced deliberately.
      return json(res, ['configuration', 'echo', 'find', 'move', 'store']);
    }
    if (path === 'statistics') return json(res, { CountStudies: studies.length, CountSeries: 189,
      CountInstances: 7560, TotalDiskSize: '3221225472' });
    if (path === 'changes' && url.search === '?last') return json(res, { Changes: studies.slice(0, 6).map((s, i) => ({
      ChangeType: i % 3 ? 'NewInstance' : 'StableStudy', ID: s.ID, Date: `${s.MainDicomTags.StudyDate}T${s.MainDicomTags.StudyTime}` })), Done: true });
    if (path === 'jobs') return json(res, [
      { ID: 'job-1', Type: 'DicomModalityStore', State: 'Success', Progress: 100 },
      { ID: 'job-2', Type: 'Archive', State: 'Running', Progress: 42 },
      { ID: 'job-3', Type: 'DicomMoveScu', State: 'Failure', Progress: 0 }]);

    res.writeHead(404, { 'Content-Type': 'text/plain' }); res.end('not found');
  });

  return new Promise(resolve => server.listen(0, '127.0.0.1', () => {
    const { port } = server.address();
    resolve({ origin: `http://127.0.0.1:${port}`, portalUrl: `http://127.0.0.1:${port}/pmc/`,
      requests, close: () => new Promise(r => server.close(r)) });
  }));
}

export const loadPortal = path => readFileSync(path, 'utf8');
