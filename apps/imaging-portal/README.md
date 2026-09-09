# PMC Imaging — the portal

The imaging worklist for Premiere Medical Center Nueva Ecija. Orthanc serves it
itself, so it appears at `https://imaging.pmcne.ph/pmc/` alongside everything
already there. Same origin as the archive, which is why **the page never sees,
asks for or stores a password** — the browser reuses the sign-in the user already
has.

Four screens — **Worklist**, **Study**, **Devices**, **Activity / System** — and
a **viewer**. It speaks only Orthanc's published REST API: `/tools/find`,
`/studies/…`, `/series/…/instances`, `/instances/…/simplified-tags`,
`/instances/…/frames/…/{numpy,rendered,preview}`, `/modalities`, `/changes`,
`/jobs`, `/statistics`, `/plugins`, `/system`. When the engine underneath is
replaced, the front end keeps working.

## The viewer

Built in, so it needs no plugin: on the day OHIF or Stone fails to load, the
portal still shows images. The plugin viewers are still offered, detected from
the server's own `/plugins` list, listed after it.

It asks Orthanc for the frame in the best form the archive can give, and says on
screen which one it got:

| Path | Endpoint | What it buys |
|---|---|---|
| **pixel data** | `/instances/{id}/frames/{f}/numpy?rescale=0` | The stored values. Window/level is then a local lookup table and costs no network at all; the probe reports true Hounsfield units; region statistics are real. |
| **server rendered** | `/instances/{id}/frames/{f}/rendered?window-center=&window-width=` | Orthanc applies the rescale and the window. Accurate, one round trip per window change. |
| **preview only** | `/instances/{id}/preview` | Full range stretched to 8 bits. No windowing. The last resort, and it is labelled. |

Endpoints and parameter names **VERIFIED 9 Sep 2026** against Orthanc's own
OpenAPI (<https://orthanc.uclouvain.be/api/orthanc-openapi.json>). `/numpy`
needs Orthanc 1.11.0+; PMC-ORTHANC01 runs **1.13.0** (MEASURED, cutover handoff
2 Sep 2026).

Window/level with presets · magnifier · zoom, pan, fit, 1:1 and calibrated true
size · invert, rotate, flip · sharpen and smooth · length, angle, rectangular and
elliptical regions with mean ± SD · pixel probe in Hounsfield units · cine with
fps and bounce · tile layouts · stack on the wheel · prior studies side by side
with position-matched linked scroll · modality-defined opening layout · every
DICOM tag on the frame · PNG export with the overlay burned in.

**MPR.** A CT or MR stack reslices into coronal and sagittal planes, with a
crosshair that drives all three from one point. The volume is stacked from the
same per-frame fetches the axial view uses, in this viewer's own sorted order,
because `/series/{id}/numpy` returns frames in an order Orthanc chooses and a
wrong slice order does not look wrong. Each reslice carries its own pixel
spacing, so measurements and the Hounsfield probe are correct on it.

Statistics are **refused, not invented**, when the pane is on the rendered or
preview path: an 8-bit PNG has no Hounsfield units in it, and neither does a
volume stacked out of one. What this viewer does *not* do — MIP, volume
rendering, fusion, reporting — is named in
`docs/WS23-viewer-vs-voyager-20260909.md`, next to what Voyager does.

## The two constraints that shape everything

**1. It never sends `OrderBy`.** The ODBC index plugin 1.3 hard-codes no
ordering (`OdbcIndex::HasFindSupport()` returns `false`), so any `/tools/find`
carrying `OrderBy` comes back HTTP 500 — that is why the stock Explorer 2 landing
page shows an empty study list. This page asks the index only for what it can
answer (a date window, a modality, a name) and sorts in the browser. It therefore
works today, and will keep working unchanged after the index moves to PostgreSQL
(ADR-001), at which point it simply gets faster. There is a check for this.

**2. It is self-contained.** No CDN, no web font, no external request of any
kind — the hospital LAN has no route out. The build fails if anything external
creeps in.

## Layout

```
src/index.html          the shell, with three build tokens
src/styles/*.css        ordered fragments -> one <style>
src/app/*.js            ordered fragments -> one <script type="module">
src/assets/favicon.png  inlined as a data: URI at build time
build/manifest.json     the assembly order and the reference hash
build/build.mjs         assemble + verify
build/payload.mjs       installer payload + hash; also verifies an installer
build/oneliner.mjs      one-line PowerShell deployer, hash-gated
build/package.mjs       the deployment zip: page, installer, probe, instructions
scripts/*.ps1           what an operator runs on PMC-ORTHANC01
build/baseline.mjs      deliberately move the reference hash
test/stand-in-orthanc.mjs  a fake Orthanc that refuses OrderBy, like the real one
test/checks.mjs         24 checks driven through Chromium
dist/                   the artifact. Generated. Never hand-edit.
```

`src/` began as a **lossless** split of the artifact signed off on 6 Sep 2026 —
concatenating the fragments reproduced it byte for byte, and the build asserted
that on every run so refactoring could not silently change what reaches the
archive.

**It has since diverged once, deliberately.** A security review found that an
absolute `?api=` moved the whole data plane to another host while the address bar
still read `imaging.pmcne.ph`. The parameter is now same-origin only. The
artifact is therefore **101,154 bytes, sha256 `439667d3…d6f13`** — no longer the
6 Sep build. Everything else about the gate is unchanged: the build still refuses
any output that does not match the recorded reference.

## Commands

```bash
npm run build            # assemble dist/PMC_Imaging_Portal.html, verify it
npm run check            # verify only; fails if dist/ is stale (this is what CI runs)
npm test                 # build, then run the 24 browser checks
npm run payload          # emit dist/payload.gz.b64 and the sha256 an installer needs
npm run verify-installer <installer.ps1>   # what does that installer ACTUALLY carry?
npm run baseline         # after a deliberate change: move the reference hash
```

`verify-installer` exists because the deliverables copy of the portal and the
payload inside the installer queued for PMC-ORTHANC01 are **not the same file**
(100,449 bytes here versus 101,090 recorded for the installer). Run it against
the real `.ps1` and it will say, in one line, which build is about to be pasted
onto the archive.

## Testing

`test/checks.mjs` drives the **built** artifact in Chromium against
`test/stand-in-orthanc.mjs` — a stand-in Orthanc faithful on the points that
matter: 64 studies, real PNG previews, an index that answers HTTP 500 to
`OrderBy`, one modality that answers C-ECHO and one that is silent, and
`/modalities/{name}` returning **child resources** rather than settings (the
misread that caused a false alarm and a forced restart of a live archive on
8 Sep 2026).

The suite covers the behaviour the portal was signed off on, plus the three
faults this code has actually hit: previews painting behind their placeholder,
`/modalities` answering with either shape, and that child-resource read.

### One thing worth knowing before you write another check

`document.body.dataset.ready = '1'` is set as soon as `boot()` finishes, but
`render()` hands the DOM write to `document.startViewTransition()`, which is
asynchronous. On a browser with View Transitions the flag beats the paint by
roughly 100 ms. **Do not treat `data-ready` as "the worklist is on screen"** —
in a test, or in any monitoring probe. Wait for the skeletons to clear as well.
This is a property of the shipped artifact, not a defect, and it is not changed
here: the artifact stays byte-identical to the one that was signed off.

## Which build is running

The page carries its own identity: a `pmc-build` meta tag holding the baseline
date and a twelve-character hash of the source fragments, shown on the System
screen. The date is the **baseline** date, not the day someone ran the build, so
the artifact stays byte-reproducible from the manifest alone. It is there because
after an update the only honest way to know the new file landed is for the page
to say so.

Nothing updates itself. The page makes no external request, and nothing on the
server polls for a new version. An update is a person running the installer
again; it replaces one file and, because ServeFolders reads that file on every
request, needs no service restart.

## Configuration

Optional. The installer writes `pmc-portal.config.json` next to the page; every
key overrides a built-in default. See `config/pmc-portal.config.example.json`.
**No credential belongs in that file** — the portal is same-origin and never
handles one. The real file is git-ignored.

Viewer buttons are built from the server's own `/plugins` list, so the page never
offers a viewer that is not installed.

The OHIF launch URL was **INFERRED**; it is now **MEASURED and VERIFIED**. OHIF's
route follows the plugin's `OHIF.DataSource`, and pointing one route at the other
opens an empty viewer:

| `OHIF.DataSource` | Route |
|---|---|
| `dicom-web` — what PMC-ORTHANC01 is set to (MEASURED, cutover handoff 2 Sep 2026) | `ohif/viewer?StudyInstanceUIDs={studyUid}` |
| `dicom-json` | `ohif/viewer/dicomjson?url=../studies/{orthancId}/ohif-dicom-json` |

Both routes **VERIFIED 9 Sep 2026** against OHIF's own documentation
(<https://docs.ohif.org/configuration/url/>, <https://v3-docs.ohif.org/configuration/datasources/dicom-json/>);
`RouterBasename` defaults to `/ohif/` (<https://orthanc.uclouvain.be/book/plugins/ohif.html>).
The first is the built-in default; a server configured the other way sets it in
`pmc-portal.config.json`, and a check covers that.
