# The guide's source

`PMC_Dada_PSA_Guides_20261006.html` one level up is generated: one file with a
front page and all fourteen guides inside it. **Edit these files, not the HTML.**

It supersedes `PMC_Dada_PSA_Guides_20261005.html`, which supersedes
`PMC_Dada_PSA_Guides_20260930.html`; both are kept beside it and still describe
the desk as it was on their dates. The 6 October edition changes the Service
Desk guide's *Tickets by email* and *Notes and emails* (the email in its own
frame, pictures pasted into it, the folded thread, oldest or newest first) and
the Staff guide's *What changed since 30 September*. A dated document is never
overwritten here; the new edition says on its own front page what it replaces.

- `g_*.py` hold each guide's words and try-it tools; `g_common.py` the helpers
  and `DATE`, the edition being built.
- `lib.js` holds the interactive tools; `chrome_one.js` the front page, the
  switching between guides, the contents rail and search across every guide.
- `shell.html` is the page, in the PMC 2026 theme.
- `img/*.jpg` are the 1280 px screenshots, `webp/*.webp` the 800 px ones the
  compact edition uses, and `spots.out.json` says where each tour's numbered
  hotspot sits on its picture, as a percentage.
- `build_one.py` embeds each screenshot once and writes the HTML.
- `build_compact.py` writes the compact edition (see below).
- `check_guide.py` opens a built file in a real Chromium and checks it.

Both files are self-contained: no CDN, no web font, no external request.
`check_guide.py` asserts that, so it cannot quietly stop being true.

## Building

```
python3 _source/build_one.py                       # the full edition
python3 _source/build_compact.py                   # the compact one
python3 _source/check_guide.py PMC_Dada_PSA_Guides_20261006.html
python3 _source/check_guide.py PMC_Dada_PSA_Guides_Compact_20261006.html
```

`build_one.py` takes `GUIDE_OUT` to write somewhere else, and `GUIDE_IMGDIR` /
`GUIDE_IMGEXT` / `GUIDE_IMGMIME` to use a different screenshot set (which is
how the compact build reuses it).

### Why the inputs are committed now

Until 5 October they were not. `build_one.py` read its screenshots and its
hotspot boxes out of the scratchpad of the session that first built the guide,
and that scratchpad is gone — so the words were in the repository, the recipe
was in the repository, and **the guide could not be rebuilt at all.** The
screenshots and the hotspot percentages were recovered losslessly out of the
30 September build and committed. Before any of this edition's words were
written, `build_one.py` rebuilt that file from the recovered inputs and the
result was byte for byte identical, which is what makes the recovery a fact
rather than a hope.

`boxes*.out.json` (the pixel measurements the percentages were computed from)
are still gone. `build_one.py` prefers them when they exist and falls back to
`spots.out.json`, so re-measuring a re-shot screen still works the old way.

## The compact edition

`PMC_Dada_PSA_Guides_Compact_20261006.html` is the same guide (924 KB in the
5 October edition),
for places that take files under 1 MB. Its screenshots are 800 px WebP, and the
whole page is gzipped inside the file and unpacked by the browser when opened
(Edge, Chrome, Firefox or Safari 16.4+; an older browser is told to download the
file and open it rather than shown a blank page).

`build_compact.py` does all of it in one command. It used to be four commands
and a hand-pasted wrapper, which is how the 30 September compact edition came to
exist with no recorded way to rebuild it.

It uses `webp/` as it stands rather than re-encoding, and the reason matters:
that directory holds the encode made from the **original PNG** screenshots,
and the repository only has the 1280 px JPEGs. Re-encoding a JPEG to WebP
spends bits on the JPEG's own artefacts, so the same 800 px at the same quality
comes out around 1.4 MB instead of 649 KB — over the whole budget. The pictures
did not change between editions, so reusing the bytes is both smaller and exact.

**When a screen is actually re-shot**, delete its stale `webp/<name>.webp` and
`build_compact.py` re-encodes (`webp.py`, or `webp.js` where Node has
Playwright). Expect the file to grow; re-shoot from PNG if the budget matters.

## The screenshots are the 30 September set

The words are current to 6 October. The pictures are not, and the guide says so
in three places rather than pretending otherwise: the front-page notice, the
footer, and `What changed since 30 September` in the Staff guide, which names
the five screens that now look different from their picture — the ticket page,
the board, Dispatch, the Schedule week and New ticket.

Re-shooting them needs the demonstration desk the originals came from (made-up
staff, tickets and supplier records). **That seed script was in the scratchpad
too and is gone**, so re-shooting means building the demo desk again — and
re-shooting only some screens would leave one guide showing two different
demonstration desks, with different ticket numbers and names, which is worse
than a slightly old picture. It is a job of its own.
