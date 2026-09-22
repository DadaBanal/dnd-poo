# WS23 — imaging, parked 9 Sep 2026, to resume Friday

**Status:** installed and working on PMC-ORTHANC01. Parked at Dada's direction to
finish the PSA/ticketing work first. This file exists so Friday is a build and
not a re-diagnosis.

## Where it got to

Live at `https://imaging.pmcne.ph/pmc/index.html`. Reading the real archive:
24 studies in the worklist, index detected as ODBC with the ordering caveat,
viewers detected from the server's own plugin list, build stamp on the System
screen. 46 of 46 browser checks pass. The pull request is green and mergeable.

## The one open complaint

**MEASURED by Dada, 9 Sep:** *"everything kinda loads really slow, it's just
frame after frame."*

That is the viewer fetching one frame per request, and the arithmetic says it
cannot be anything else:

| | |
|---|---|
| Frames in one XA run | 56, in a **single** multi-frame instance |
| `/frames/{n}/rendered` warm | 430 ms, 351 KB |
| `/frames/{n}/numpy` warm | 152 ms, 1,478 KB |
| Cine at 12 fps needs a frame every | 83 ms |

So playback asks for a frame every 83 ms and each takes 152 ms at best. It will
always lag, and scrolling a run is 56 round trips for what is physically one
file on disk.

## The fix, and why it is the right one

A multi-frame instance is **one file**. `GET /instances/{id}/numpy` returns every
frame in a single array — one request, one decode, one disk read, instead of 56
of each. After that, cine, scrubbing and window/level are local and instant.

- 56 frames × 1,478 KB ≈ **81 MB** for a run. That is one transfer on a LAN, and
  the frame cache is already bounded in megabytes (192 MB) rather than by frame
  count, so a run fits and a second run evicts the first.
- The slicing code already exists: `sliceVolume()` in `18-viewer-mpr.js` cuts
  planes out of exactly this shape. A multi-frame instance is the same problem
  with the axial plane only.
- Guard it: fetch the whole instance only when `NumberOfFrames > 1` and the
  estimated size is under a cap. Otherwise keep the per-frame path.
- Keep the progressive rule. The archive's picture still paints first, because a
  cold instance costs about 24 s whichever endpoint asks for it, and one frame is
  351 KB against 81 MB for the run.

## Also worth doing while in there

- **Prefetch further ahead on the rendered path.** ±4 frames is not enough for
  cine; a rolling window of the next 12 would cover the lag when the whole-run
  path is not taken.
- **Say what it is doing.** A run that is loading should say so, rather than
  looking like a viewer that is merely slow.

## Not to be repeated

The cold-instance cost is not the viewer's fault and not fixable in it: the
first touch of a large multi-frame file on this archive took 24.6 s and the
second took 152 ms. OHIF and Stone pay the same toll.
