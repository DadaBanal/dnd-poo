# The guide's source

`PMC_Dada_PSA_Guides_20260930.html` one level up is generated: one file with a
front page and all fourteen guides inside it. It supersedes the fourteen
separate guide files of the same date (removed; they are in the history).
Edit these files, not the HTML.

- `g_*.py` hold each guide's words and try-it tools; `g_common.py` the helpers.
- `lib.js` holds the interactive tools; `chrome_one.js` the front page, the
  switching between guides, the contents rail and search across every guide.
- `shell.html` is the page, in the PMC 2026 theme.
- `build_one.py` embeds each screenshot once and writes the HTML. It reads the
  screenshots and hotspot positions from the session scratchpad it was built
  in; those come from a demonstration desk with made-up staff and records.

The file is self-contained: no CDN, no web font, no external request.

## The compact edition

`PMC_Dada_PSA_Guides_Compact_20260930.html` is the same guide at 936 KB, for
places that take files under 1 MB. Its screenshots are 800 px WebP
(`webp.js` re-encodes them in Chromium), and the page is gzipped inside the
file and unpacked by the browser when opened (Edge, Chrome, Firefox or
Safari 16.4+). Build it with `GUIDE_IMGDIR=webp GUIDE_IMGEXT=webp
GUIDE_IMGMIME=webp GUIDE_OUT=<inner.html> python3 build_one.py`, then gzip,
base64 and wrap the result in a page that decompresses it.
