"""Hit the running desk and print what it answered, for the CI boot check.

Prints '401' only when the desk returns the sign-in page unauthenticated —
which proves it booted, routed, and ran the auth edge, not merely that a socket
opened. Anything else prints a marker the CI step will fail on.
"""
import sys
import urllib.error
import urllib.request

url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8137/"
try:
    urllib.request.urlopen(url, timeout=5)
    print("200-no-auth")           # booted but did not challenge — a failure
except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", "replace")
    print(exc.code if "Break-glass" in body else "no-login-page")
except Exception as exc:                                   # noqa: BLE001
    print(f"unreachable:{exc.__class__.__name__}")
