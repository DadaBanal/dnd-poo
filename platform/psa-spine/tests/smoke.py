"""End-to-end smoke run of the PSA spine, the same on Linux and Windows.

The unit tests prove the parts. This proves the commands a person types: that
the whole path runs from a fresh database to reports, intake, escrow and a
desk that answers. CI used to run these steps as bash; the pilot host is
Windows, so they live here instead, standard library only, and CI and the host
run the same file:

    python tests/smoke.py                              # CI, Linux
    C:\\PMC\\Python312\\python.exe tests\\smoke.py         # DND-SQL01

Everything happens in a temporary directory that is removed afterwards. It
binds only to 127.0.0.1, reads only the synthetic fixtures, and opens no
connection to anything but the desk it starts itself. Exit 0 means every step
passed; each step prints PASS or FAIL with the reason.
"""
from __future__ import annotations

import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # platform/psa-spine
FIX = ROOT / "tests" / "fixtures"
AS_OF = "2026-09-09"

results: list[tuple[str, bool, str]] = []


def cli(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run `python -m psaspine ...` exactly as a person would."""
    proc = subprocess.run([sys.executable, "-m", "psaspine", *args], cwd=ROOT,
                          capture_output=True, text=True, timeout=120)
    if check and proc.returncode != 0:
        raise AssertionError(f"`psaspine {' '.join(args[:1])}` exited "
                             f"{proc.returncode}: {proc.stderr.strip()[-300:]}")
    return proc


def step(name: str):
    def wrap(fn):
        try:
            detail = fn() or ""
            results.append((name, True, detail))
        except Exception as exc:                            # noqa: BLE001
            results.append((name, False, f"{exc.__class__.__name__}: {exc}"))
        return fn
    return wrap


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        spine, out = t / "spine.db", t / "out"

        @step("register and desk export import, rows in = rows out")
        def _():
            cli("init", str(spine))
            r = cli("import", str(spine), str(FIX / "register-sample.csv"),
                    "--run-id", "ci", "--as-of", AS_OF)
            d = cli("import-tickets", str(spine), str(FIX / "desk-export-sample.csv"),
                    "--run-id", "desk", "--as-of", AS_OF)
            return f"{r.stdout.strip()} | {d.stdout.strip()}"

        @step("reports written")
        def _():
            cli("report", str(spine), "--out", str(out), "--run-id", "desk",
                "--as-of", AS_OF)
            stamp = AS_OF.replace("-", "")
            for name in ("AnnexB_Variation_Register", "Instrument_Exception_Report",
                         "Uplift_Evidence"):
                f = out / f"PMC_{name}_{stamp}.md"
                assert f.is_file(), f"missing {f.name}"
            n = len(list((out / "notices").glob("*.md")))
            assert n > 0, "no dependency notices written"
            return f"{n} dependency notices"

        @step("board engine walkthrough")
        def _():
            text = cli("walkthrough", str(spine)).stdout
            for marker in ("within target", "firing 4 of 4"):
                assert marker in text, f"walkthrough did not say {marker!r}"

        @step("email intake, and a re-run is a no-op")
        def _():
            mail = t / "mail.db"
            cli("init", str(mail))
            first = cli("import-mail", str(mail), str(FIX / "mail-drop"),
                        "--run-id", "m1", "--as-of", "2026-09-22").stdout
            assert "2 new, 1 appended" in first, first.strip()
            second = cli("import-mail", str(mail), str(FIX / "mail-drop"),
                         "--run-id", "m2", "--as-of", "2026-09-22").stdout
            assert ("0 new, 0 appended, 0 duplicate, 0 unclassified, 3 already seen"
                    in second), second.strip()
            return first.strip()

        @step("escrow backup proves its copy and refuses to overwrite")
        def _():
            dest = t / "escrow.db"
            ok = cli("backup", str(spine), str(dest))
            assert "integrity ok" in ok.stdout, ok.stdout.strip()
            again = cli("backup", str(spine), str(dest), check=False)
            assert again.returncode != 0, "second backup onto the same file succeeded"
            return ok.stdout.splitlines()[0].split(": ", 1)[-1]

        @step("desk boots on 127.0.0.1 and challenges an unauthenticated request")
        def _():
            desk = t / "desk.db"
            cli("init", str(desk))
            port = free_port()
            proc = subprocess.Popen(
                [sys.executable, "-m", "psaspine", "serve", str(desk),
                 "--host", "127.0.0.1", "--port", str(port)],
                cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            try:
                status = "unreachable"
                for _ in range(40):
                    if proc.poll() is not None:
                        raise AssertionError(f"desk exited {proc.returncode}: "
                                             f"{proc.stderr.read().strip()[-300:]}")
                    try:
                        urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
                        status = "200 without sign-in"
                        break
                    except urllib.error.HTTPError as exc:
                        body = exc.read().decode("utf-8", "replace")
                        status = str(exc.code) if "Break-glass" in body else "no sign-in page"
                        break
                    except OSError:
                        time.sleep(0.25)
                assert status == "401", f"unauthenticated GET / -> {status}"
                return f"GET / -> 401 on port {port}"
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()

        @step("desk refuses a public bind")
        def _():
            proc = cli("serve", str(spine), "--host", "0.0.0.0", "--port",
                       str(free_port()), check=False)
            assert proc.returncode != 0, "serve bound to 0.0.0.0"
            assert "refusing to bind" in proc.stderr, proc.stderr.strip()[-200:]

    width = max(len(n) for n, _, _ in results)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    failed = sum(not ok for _, ok, _ in results)
    print(f"\n{len(results) - failed} of {len(results)} steps passed "
          f"(Python {sys.version.split()[0]}, {sys.platform})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
