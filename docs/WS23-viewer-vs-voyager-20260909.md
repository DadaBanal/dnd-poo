# WS23 — the PMC viewer measured against Voyager

**Date:** 9 September 2026 · **Author:** Dada IT · **Status:** built, tested, not yet installed
**Supersedes nothing.** Companion to `docs/WS23-imaging-portal-repo-20260908.md`.

## Why this comparison exists

PMC is retiring Voyager. The cutover handoff records the intent in one line —
*"Repoint `pacs` when Voyager retires"* — and `Import-VoyagerArchive.ps1` is
already reading `F:\IntelliRADData\Studies` and posting into Orthanc, with a
real 25-Aug-2026 XA study proven visible on the new archive.
**MEASURED** from `docs/orthanc-cutover-handoff-20260902.md`, read 9 Sep 2026.

Voyager Imaging is a division of Intellirad Solutions. What PMC gives up when it
switches off is therefore a specific, documented product — not a vague "old
PACS" — and the replacement has to be measured against it rather than against a
feeling. That is what this file does.

## What Voyager ships

**VERIFIED 9 Sep 2026** from the vendor's own product page,
<https://www.intellirad.com.au/products/pacs-workstation/>, quoting its wording:

> Window & Level (including W/L presets) · Magnify, Zoom, Pan · Flip
> (Left/right, Top/Bottom), Rotate · Annotations · Image inversion ·
> Measurements, ROI, and Angles · True size image display (1:1) · Advanced
> comparison mode (with side by side, sheet mode, auto position matching) ·
> Cine, Tile or Stack mode · Multiple enhancement tools · Preemptive/Prefetching
> … · Modality defined image layout · Configurable desktop · Multiple criteria
> available for sorting of worklist entries · Customized worklist filters and
> searches · Image export · Supports dual monitor display · Integration to RIS
> (HL7) · Supports launching of third party applications such as 3D, digital
> dictation and orthopedic

Two viewers are offered, and the split matters:
**VERIFIED** from <https://cmi.voyagerpacs.com/> — a *Zero Foot Print Viewer*
("no download required", "Recommended for General Practitioners") and a
downloadable *DICOM Viewer* ("Recommended for Radiologist / Surgeon /
Specialist"). The zero-footprint tier is the one a PMC referrer actually uses,
and it is the tier this portal competes in.

## Line by line

| Voyager's own wording | PMC viewer | Note |
|---|---|---|
| Window & Level, incl. W/L presets | **Yes** | Drag on the image or right-drag on any tool. Presets from the file's own `WindowCenter`, the eight conventional CT windows, and an auto window from the 2nd–98th percentile of the actual frame. |
| Magnify | **Yes** | Loupe at 4×, nearest-neighbour, under the cursor. |
| Zoom, Pan | **Yes** | Wheel, drag, middle-drag, pinch. |
| Flip (L/R, T/B), Rotate | **Yes** | |
| Image inversion | **Yes** | Applied in the lookup table on the pixel path, so it costs nothing. |
| Annotations | **Yes** | Arrow with a typed label, listed in the sidebar. |
| Measurements, ROI, Angles | **Yes** | Length in mm from `PixelSpacing`; angle in degrees; rectangular and elliptical regions reporting mean ± SD, min, max and area. |
| True size image display (1:1) | **Yes, and further** | Voyager states 1:1. A browser cannot ask the monitor its pixel pitch, so ours is calibrated once against a bank card (85.6 mm) and kept. Until it is, the viewer *says* it is assuming 96 dpi rather than claiming true size. |
| Advanced comparison mode — side by side | **Yes** | Priors listed from the archive by `PatientID`; open one into the second pane. |
| — auto position matching | **Yes** | Linked scroll follows `ImagePositionPatient` projected on the slice normal, not the frame index. |
| — sheet mode | **No** | Named as a gap. |
| Cine, Tile or Stack | **Yes** | Cine with an fps control and bounce; tile layouts 1×1 / 1×2 / 2×2 / 2×3; stack on the wheel. |
| Multiple enhancement tools | **Partly** | Sharpen and smooth, on the rendered picture only — never on the values the measurements read. |
| Preemptive / prefetching | **Yes** | Frames either side of the current one are fetched ahead, four at a time. |
| Modality defined image layout | **Yes** | XA, US and NM open in one pane; CR, DX and MG side by side; CT and MR tile to 2×2 when the study has four series. |
| Configurable desktop / custom toolbar | **No** | Named as a gap. Low value for a referrer; real for a reporting radiologist. |
| Worklist sorting, filters, searches | **Yes** | Already in the portal, and it sorts in the browser because the ODBC index cannot order. |
| Image export | **Yes, and further** | PNG of the pane with the overlay burned in, so an exported frame identifies whose it is. |
| Dual monitor | **Partial** | Two browser windows work; there is no pane pop-out. Named as a gap. |
| RIS (HL7) integration | **Not here** | Server-side. Orthanc's Worklists plugin is loaded; nothing in this portal changes that. |
| Launch third-party apps | **Yes** | OHIF, Stone and Explorer 2 buttons are still built from the server's own `/plugins` list. |

## Where this viewer is ahead

1. **It reports Hounsfield units, and can prove it.** The viewer pulls the
   stored pixel array from `/instances/{id}/frames/{f}/numpy` and applies
   `RescaleSlope`/`RescaleIntercept` itself, so the probe and the region
   statistics are in the modality's own units. A test asserts the probe reads
   −100 HU where the stored value is 924 — the exact mistake this design is
   meant to make impossible.
2. **It says which data path it is on.** "pixel data", "server rendered",
   "preview only" or "SAMPLE DATA" is on screen at all times. When the archive
   cannot decode a series to an array, statistics are refused rather than
   invented from an 8-bit PNG.
3. **Window/level costs nothing.** On the pixel path the window is a lookup
   table rebuilt locally; a test asserts the drag sends **zero** further
   requests. Over a hospital link that is the difference between a usable
   window and a slideshow.
4. **It needs no plugin.** It speaks Orthanc's own REST API. On the day OHIF or
   Stone fails to load, the portal still shows images. Both plugin viewers stay,
   listed after it.
5. **It is one file.** 182 KB, no CDN, no web font, no external request, built
   from source with a hash the build refuses to deviate from.
6. **Cine is a button.** **MEASURED** from the handoff: on the evening of 1 Sep,
   Dada had OHIF's *layout* menu open looking for playback; cine is buried under
   More Tools. For coronary runs — PMC's highest-volume study — that is the
   first thing a reader needs.

## Where it is behind, plainly

- **No MPR, MIP or 3D.** Competitors in this class advertise them
  (MedDream, PostDICOM, DICOM Vision, evoViewer — **VERIFIED** 9 Sep 2026 from
  their product pages). Voyager's own answer is to launch a third-party 3D
  application from the workstation, and the handoff records that OHIF's volume
  tools are greyed for XA by design because they need a stack. `/series/{id}/numpy`
  would make MPR feasible; it is not built.
- **No sheet mode, no configurable toolbar, no pane pop-out.**
- **No reporting, dictation or key-image flagging.**
- **Not a regulated device.** Voyager is a listed medical device in Australia.
  This is a hospital-built front end to a hospital-owned archive. It must not be
  described as diagnostic-grade, and nothing here does.

## The blocker found while writing this

**MEASURED 9 Sep 2026** from `docs/orthanc-cutover-handoff-20260902.md`,
Addendum 3: the 2 Sep HTTPS cutover kept 8 plugins and dropped 23, and
**ServeFolders is on the dropped list**. The portal is served by ServeFolders.
As PMC-ORTHANC01 stands, writing the file changes nothing, because nothing
would serve it.

The one-line deployer now looks before it advises: it reports whether
`ServeFolders` is in the Plugins folder and whether `orthanc.json` carries a
`ServeFolders` section, and prints the block to add. It still changes nothing
itself. Restoring the DLL and adding the section is a deliberate, separate
change to a live clinical archive and belongs in its own window.
