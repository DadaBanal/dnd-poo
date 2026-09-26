"""Run the WSGI app for the pilot with the standard library's own server.

`wsgiref.simple_server` is the pilot server and does not pretend to be more. It
is here because the whole web tier is zero-dependency by choice (D2), and the
value of a WSGI callable is that this launcher is the only thing that changes in
Phase C: the same `application` drops behind a production WSGI server with no edit to a
view. The stdlib's own warning that this server is not for production is left to
print — it is true, and hiding it would be the wrong kind of tidy.

It refuses to bind to a public interface. The pilot is LAN only and Dada IT
only; a bind to 0.0.0.0 is not a convenience here, it is a way to put an
unfinished desk on a hospital's network, so it is refused rather than warned
about.
"""
from __future__ import annotations

import sys
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from .. import db
from . import Config, make_app

# Interfaces the pilot will not bind to. 0.0.0.0 and :: reach every network the
# host is on; the pilot belongs on the loopback or a named LAN address a person
# typed on purpose.
PUBLIC_BINDS = {"0.0.0.0", "::", ""}


class ThreadedServer(ThreadingMixIn, WSGIServer):
    """One thread per request. wsgiref's default serves one request at a time,
    so a technician opening a big board made everyone else's click wait for it.
    Each request opens its own SQLite connection (WAL: readers never block), and
    the one piece of cross-request state, the workflow re-entrancy guard, is
    thread-local. Daemon threads: a stop is a stop."""
    daemon_threads = True


class QuietHandler(WSGIRequestHandler):
    """No line on stderr per request: a desk with forty people on it would
    otherwise write a log nobody reads, and that write is on the request path."""
    def log_message(self, format, *args):        # noqa: A002
        pass


def _refuse_if_taken(host: str, port: int) -> None:
    import socket
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, port))
    except OSError as exc:
        raise SystemExit(
            f"refusing to start: port {port} on {host} is already in use by another "
            f"service on this host ({exc.strerror or exc}). The desk never takes a port "
            "something else holds; choose a free one with --port.") from None
    finally:
        probe.close()


def serve(db_path: str, *, host: str = "127.0.0.1", port: int = 8080,
          config: Config | None = None) -> None:
    if host in PUBLIC_BINDS:
        raise SystemExit(
            f"refusing to bind to {host!r}: the Phase B pilot is LAN only and Dada "
            "IT only. Bind to 127.0.0.1, or to a specific LAN address you mean to "
            "expose, never to all interfaces.")

    # A port another service holds is refused in a sentence, before anything
    # else happens: on a host that runs the hospital's other services (the
    # queue screens on 8080 of DND-SQL01, MEASURED 26 Sep 2026) a bind that
    # fails half-way, or a port taken from something live, is the wrong start.
    _refuse_if_taken(host, port)

    config = config or Config.from_env()
    app = make_app(db_path, config=config)

    posture = ("Entra + break-glass" if config.entra_configured
               else "break-glass only (no Entra tenant configured)")
    print(f"PSA desk (Phase B pilot) on http://{host}:{port}", file=sys.stderr)
    print(f"  database: {db.describe(db_path)}", file=sys.stderr)
    print(f"  sign-in:  {posture}", file=sys.stderr)
    print("  wsgiref.simple_server is not a production server. Phase C puts the "
          "same app behind a real one.", file=sys.stderr)

    with make_server(host, port, app, server_class=ThreadedServer,
                     handler_class=QuietHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.", file=sys.stderr)
