# The guide library's source

The fourteen `PMC_Dada_PSA_*_Guide_20260930.html` files one level up are
generated. Edit these files, not the HTML.

- `g_*.py` hold each guide's words and try-it tools; `g_common.py` the helpers.
- `lib.js` is the one script every guide carries (search, progress, tours,
  and the interactive tools); `shell.html` the page, in the PMC 2026 theme.
- `build_all.py` embeds the screenshots and writes the HTML. It reads the
  screenshots and hotspot positions from the session scratchpad it was built
  in; those come from a demonstration desk with made-up staff and records.

Every guide is self-contained: no CDN, no web font, no external request.
