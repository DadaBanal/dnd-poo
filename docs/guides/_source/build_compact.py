"""The compact edition: the same guide, small enough for a 1 MB upload limit.

Two reductions, in this order:

1. Each screenshot is 800 px WebP in `webp/`, which is where all the weight is.
   The words, the tours and the tools are untouched -- only the pictures get
   smaller.

   Those files are committed, and the build uses them as they are rather than
   re-encoding. That is not laziness: `webp/` holds the encode made on 30 Sep
   from the *original* PNG screenshots, and the repository only has the 1280 px
   JPEGs (recovered out of the full edition). Re-encoding a JPEG to WebP means
   spending bits on the JPEG's own artefacts, so the same 800 px at the same
   quality comes out at 1.4 MB instead of 649 KB -- more than the whole budget
   this edition exists for. Since the screenshots themselves did not change
   between editions, reusing the bytes is both smaller and exact.

   `webp.py` (or `webp.js`, where Node has Playwright) re-encodes from `img/`
   and is what to run when a screen is actually re-shot. Delete the stale
   `webp/<name>.webp` and it will be made again; expect the file to grow, and
   re-shoot from PNG if the budget matters.
2. The whole page is gzipped, base64'd, and wrapped in a tiny loader that
   unpacks it in the browser (`DecompressionStream`, so Edge, Chrome, Firefox
   or Safari 16.4+). A browser too old to do that is told to download the file
   and open it, rather than shown a blank page.

This script does the whole thing. It used to be four commands and a wrapper
pasted by hand, which is how the 30 Sep compact edition came to exist with no
way to rebuild it.
"""
import base64, gzip, os, pathlib, re, subprocess, sys

S = pathlib.Path(__file__).parent
sys.path.insert(0, str(S))
import g_common as C

HERE = pathlib.Path("/home/user/dnd-poo/docs/guides")
FULL = HERE / f"PMC_Dada_PSA_Guides_{C.DATE}.html"
OUT = pathlib.Path(os.environ.get("COMPACT_OUT", str(HERE / f"PMC_Dada_PSA_Guides_Compact_{C.DATE}.html")))
WEBP, WIDTH, Q = S / "webp", "800", "0.82"

# The loader, lifted verbatim from the 30 Sep compact edition so the two
# editions open the same way in the same browsers.
HEAD = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Dada PSA guides · PMC</title><style>body{margin:0;font:16px/1.5 "Aptos","Segoe UI",system-ui,sans-serif;'
        'background:#F4F6FA;color:#101820}#w{max-width:560px;margin:18vh auto;padding:24px;text-align:center}'
        '#w b{color:#0B3F8A;font-size:20px;display:block;margin-bottom:6px}</style></head><body><div id="w">'
        '<b>Dada PSA guides</b><span id="m">Opening…</span></div><script id="z" type="application/octet-stream">')
TAIL = ('</script><script>(async function(){var m=document.getElementById("m");try{if(!window.DecompressionStream)throw 0;'
        'var b=atob(document.getElementById("z").textContent),u=new Uint8Array(b.length);'
        'for(var i=0;i<b.length;i++)u[i]=b.charCodeAt(i);'
        'var t=await new Response(new Blob([u]).stream().pipeThrough(new DecompressionStream("gzip"))).text();'
        'document.open();document.write(t);document.close()}catch(e){m.textContent="This guide needs a current browser: '
        'open it in Microsoft Edge or Google Chrome. If it was opened inside OneDrive or Teams, download it first and open '
        'the downloaded file."}})();</script></body></html>')


def main() -> int:
    if not (S / "img").is_dir():
        print("no _source/img: the screenshots are missing", file=sys.stderr)
        return 1
    WEBP.mkdir(exist_ok=True)
    jpgs = sorted(p.stem for p in (S / "img").glob("*.jpg"))
    have = sorted(p.stem for p in WEBP.glob("*.webp"))
    missing = [n for n in jpgs if n not in set(have)]
    if missing:
        # Only what is missing would be re-encoded, but the encoder writes the
        # whole directory, so say plainly that it is about to.
        print(f"{len(missing)} screenshot(s) have no WebP ({', '.join(missing[:4])}"
              f"{'…' if len(missing) > 4 else ''}); re-encoding all {len(jpgs)} at {WIDTH} px", flush=True)
        try:
            subprocess.run(["node", str(S / "webp.js"), str(S / "img"), str(WEBP), WIDTH, Q],
                           check=True, cwd=S, capture_output=True)
        except (OSError, subprocess.CalledProcessError):
            # No Node, or no Playwright under it. The Python driver is what the
            # build session has; it drives the same Chromium the same way.
            subprocess.run([sys.executable, str(S / "webp.py"), str(S / "img"), str(WEBP), WIDTH, Q],
                           check=True, cwd=S)
    inner = pathlib.Path(os.environ.get("INNER", "/tmp/guide-compact-inner.html"))
    subprocess.run([sys.executable, str(S / "build_one.py")], check=True, cwd=S,
                   env=dict(os.environ, GUIDE_IMGDIR="webp", GUIDE_IMGEXT="webp",
                            GUIDE_IMGMIME="webp", GUIDE_OUT=str(inner)))
    body = inner.read_bytes()
    packed = base64.b64encode(gzip.compress(body, 9)).decode()
    OUT.write_text(HEAD + packed + TAIL)
    kb = OUT.stat().st_size / 1024
    print(f"{OUT.name} {kb:.0f} KB  (inner {len(body)/1e6:.2f} MB)")
    if kb > 1024:
        print("WARNING: over 1 MB, which is the limit this edition exists for", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
