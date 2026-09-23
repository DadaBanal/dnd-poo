# WS23 — cathlab cine: a run is one file

**Date:** 23 September 2026, 15:55 UTC · **Workstream:** WS23 · **Machine:** a
cloud checkout with a local Docker engine and no route to any PMC system ·
**Follows** `docs/WS23-imaging-parked-20260909.md`, which is not edited: this is
the build it asked for. **Supersedes nothing.**
**Status:** built and tested here. **Not installed.** It goes on-prem only when
Dada says so.

Labels as `CLAUDE.md`: **MEASURED**, **VERIFIED**, **INFERRED**, **NOT VERIFIED**.

## The complaint, and the change

**MEASURED by Dada, 9 Sep:** cathlab cine *"loads really slow, it's just frame
after frame"* — 56 frames in one instance, 152 ms a frame warm, where 12 fps
needs one every 83 ms. The recorded fix is now in `apps/imaging-portal/`:

- A multi-frame instance is asked for **whole**, `GET /instances/{id}/numpy?rescale=0&compress=0`,
  once, and its frames are cut out of it in the page. Cine, scrubbing and
  window/level on it then send nothing.
- **The picture still comes first.** The run is asked for only once the first
  frame's picture is on screen, and — once the tags have given its size — ahead
  of the pictures prefetched behind it, not a round trip after them.
- **Only under a cap of 96 MB**, estimated as rows × columns × frames × bytes per
  sample × samples from the tags, and held again to the archive's own
  `Content-Length` before the body is read. Otherwise, and whenever the run is
  refused, cut short or not the shape the listing promised: one frame per
  request, exactly as before.
- **Cine prefetch on the rendered path** is the next twelve frames in the
  direction of play, not four either side, and a picture already on its way is
  never asked for twice.
- **It says what it is doing:** `server rendered · loading 56-frame run · 42%`,
  then `pixel data`.
- Found while measuring, and fixed in the same parser: one frame comes back with
  **three** axes, not four (below), and the parser dropped the third — so a
  colour frame on the per-frame path was read as a third of a grey one.
  **INFERRED** from the code and the measured shape; there is no colour fixture.

The artifact is deliberately re-baselined: **214,350 bytes, sha256
`0c093dd88d83e9b5fe155e01048a096aaa57a7bf8a08ceff04b9e75cb00b08ed`**
(was 203,442 bytes, `035cbfa3…b9e`). The installer's `$ExpectedHash` moves with
it. **MEASURED: 55 of 55 browser checks pass**, nine of them new.

## Why 96 MB

Half the frame cache, which is bounded at 192 MB (MEASURED in the source). A run
is held as one entry, so a cap equal to the cache would let one run fill it, and
two panes — a run beside its prior — would push each other out as they were
used, each coming back as another whole download. At half, each pane holds one. PMC's measured run, 56 × 1,478 KB ≈ 81 MB, is under
it. **INFERRED:** at that frame size a run over about 66 frames is not; how many
of PMC's runs are that long is **NOT VERIFIED**.

## What `/instances/{id}/numpy` does on Orthanc 1.13.0 — MEASURED 23 Sep 2026

`orthancteam/orthanc:26.9.1@sha256:d2705f2c56547e55ce9bc2250fd22d05d326493b3f3d9fa191ecb7db8ca6b5a2`,
which reports **Orthanc 1.13.0**, SQLite index, plugins `orthanc-explorer-2`
1.15.0 and `gdcm` 1.8. A throwaway container on a private Docker network with no
published port, authentication off, fed invented pydicom data and removed
afterwards, with its network. Nine instances: 8-bit, 16-bit unsigned, 16-bit
signed with a rescale, RGB, a single frame, and RLE, JPEG-LS and JPEG 2000 runs,
none of them square.

| Question | Answer |
|---|---|
| Header | `.npy` 1.0, little-endian, C order, values from byte 128 |
| Whole instance | `(frames, rows, columns, samples)` — e.g. `(59, 512, 480, 1)`, `(12, 128, 160, 3)`; a single-frame instance `(1, rows, columns, 1)` |
| One frame, `/frames/{k}/numpy` | `(rows, columns, samples)` — **three axes**, no frame axis |
| dtype, `rescale=0` | the stored type: `u1`, `u2`, `i2`; RGB `u1` with 3 samples |
| `rescale` default | **true**: float32 in modality units, twice the bytes of 16-bit data and four times 8-bit; RGB unaffected |
| `compress=1` | a **zip** (`.npz`, one deflated member `arr_0`), `Content-Type: application/octet-stream`, no `Content-Encoding` |
| `Content-Length` | present on every 200 |
| Frame k of the whole vs frame k alone | identical byte for byte, first, middle and last, and equal to the source pixels — uncompressed 8/16-bit, signed, RGB, RLE and JPEG-LS |
| `NumberOfFrames` | in the instance's `MainDicomTags`, and in `series/{id}/instances?expand`, when over 1; absent for a single frame |
| Frame out of range | HTTP 400, "Parameter out of range" |
| A syntax it cannot decode (the JPEG 2000 run) | HTTP **500** "Not implemented yet" on **both** routes — not 415 |

Timing, same host, warm, container to container over a Docker bridge — **not
PMC's archive or network**. Five whole requests; three rounds of all frames.
MB here are 1,048,576 bytes, as in the code and the record.

| Run | Whole, one request | One frame at a time | Four at a time |
|---|---|---|---|
| 30 × 240 × 256, 8-bit, 1.8 MB | 8–10 ms | 53–88 ms | 38–45 ms |
| 59 × 512 × 480, 16-bit, 27.7 MB | 85–152 ms | 202–223 ms | 72–88 ms |
| 20 × 256 × 320, RLE, 3.1 MB | 12–22 ms | 40–54 ms | 25–36 ms |
| 56 × 860 × 860, 16-bit, 79 MB | 326–386 ms | 384–430 ms | 152–191 ms |

**INFERRED.** Here a single frame costs 2–7 ms, so one whole request is not
faster in wall time than four frames at a time. What it saves is requests: one
instead of 56. That wins exactly where each request is expensive, and at PMC it
is — 152 ms a frame, warm (MEASURED, 9 Sep). This does **not** reproduce the
other 23 Sep measurement's 42–56 ms against ~1,000 ms; the per-request cost there
was evidently higher than here. **NOT VERIFIED:** the whole-run time on
PMC-ORTHANC01.

## Not verified, and what to watch when it is installed

- **The route on PMC's own runs.** PMC's XA transfer syntax is not known here,
  and JPEG Lossless — a likely one — could not be encoded with the tools at hand.
  RLE and JPEG-LS decoded whole and matched. If the whole route fails there, the
  viewer falls back to one frame at a time after a single refused request.
- **Server memory — INFERRED** from the full `Content-Length` it announces up
  front: Orthanc builds the whole `.npy` before sending it, so an 81 MB run costs
  the archive at least that much while it is served, per reader opening a run.
- **Thin links — INFERRED.** 81 MB is one transfer on the LAN and a long one
  from outside it. The picture still paints first and cine prefetches pictures
  meanwhile, but the run takes as long as 81 MB takes.
- **Three or more panes of runs — INFERRED.** Beyond two PMC-size runs the cache
  is full, and they push each other out; each comes back as one more request.
- **500, not 415 — MEASURED above.** For a syntax it cannot decode, 1.13.0
  answers 500 on `/numpy`. The per-frame path treats 500 as transient and asks
  again on the next frame shown; the stand-in's undecodable series still answers
  415. Both predate this change and are not altered by it.

## Before and after installing

- **Before:** on the archive, time one XA run with
  `GET /instances/{id}/numpy?rescale=0&compress=0` — the status, the seconds and
  the bytes. The readiness probe times one frame of each route; it does not yet
  time a whole run.
- **After:** open an XA study and press play. The footer says
  `loading N-frame run`, counts up, then `pixel data`; playing it again sends
  nothing. The System screen shows the build stamp `2026-09-23 · …`.
