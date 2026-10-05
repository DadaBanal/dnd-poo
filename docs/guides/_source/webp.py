"""Re-encode the screenshots as WebP for the compact edition, in Chromium.

    python3 webp.py <jpg dir> <webp dir> <width> <quality>

The same canvas re-encode as `webp.js`, through Chromium's Python driver
instead of its Node one, because that is what is installed in the build
session. Either produces the same bytes; whichever is available wins, and
`build_compact.py` prefers this one.
"""
import pathlib
import sys

CODE = """([src, W, Q]) => new Promise(async res => {
  const i = new Image(); i.src = src; await i.decode();
  const w = Math.min(+W, i.naturalWidth), h = Math.round(i.naturalHeight * w / i.naturalWidth);
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const x = c.getContext('2d'); x.imageSmoothingQuality = 'high'; x.drawImage(i, 0, 0, w, h);
  res(c.toDataURL('image/webp', +Q));
})"""


def main(src_dir, out_dir, width, quality) -> int:
    import base64
    from playwright.sync_api import sync_playwright
    src_dir, out_dir = pathlib.Path(src_dir), pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    with sync_playwright() as pw:
        # The pre-installed Chromium, not the headless-shell Playwright would
        # rather download: this build session has no network for that, and the
        # canvas re-encode is identical in either.
        chrome = sorted(pathlib.Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome"))
        browser = pw.chromium.launch(executable_path=str(chrome[-1])) if chrome else pw.chromium.launch()
        page = browser.new_page()
        for jpg in sorted(src_dir.glob("*.jpg")):
            uri = "data:image/jpeg;base64," + base64.b64encode(jpg.read_bytes()).decode()
            out = page.evaluate(CODE, [uri, width, quality])
            data = base64.b64decode(out.split(",", 1)[1])
            (out_dir / (jpg.stem + ".webp")).write_bytes(data)
            total += len(data)
        browser.close()
    print(f"{width} {quality} total KB {round(total / 1024)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:5]))
