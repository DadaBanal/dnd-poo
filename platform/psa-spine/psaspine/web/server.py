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


def tls_context(cert: str, key: str):
    """TLS for the desk from a certificate and its key, both PEM. TLS 1.2 at
    least; the cipher choice is the standard library's current default. The
    key file is read once here, at start, and should be readable by the task
    account alone (the handoff sets that)."""
    import os
    import ssl
    for label, path in (("certificate", cert), ("key", key)):
        if not os.path.isfile(path):
            raise SystemExit(f"refusing to start: the {label} file {path!r} does not exist")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        ctx.load_cert_chain(cert, key)
    except ssl.SSLError as exc:
        raise SystemExit(f"refusing to start: the certificate and key do not load ({exc.reason or exc}). "
                         "Both must be PEM; the handoff shows the export from the Windows store.") from None
    return ctx


def build(db_path: str, *, host: str = "127.0.0.1", port: int = 8085,
          config: Config | None = None, cert: str | None = None, key: str | None = None):
    """The server, ready to serve_forever(); serve() prints and runs it, and the
    tests run it on a port of their own."""
    if host in PUBLIC_BINDS:
        raise SystemExit(
            f"refusing to bind to {host!r}: the Phase B pilot is LAN only and Dada "
            "IT only. Bind to 127.0.0.1, or to a specific LAN address you mean to "
            "expose, never to all interfaces.")
    if bool(cert) != bool(key):
        raise SystemExit("refusing to start: --cert and --key go together")

    # A port another service holds is refused in a sentence, before anything
    # else happens: on a host that runs the hospital's other services (the
    # queue screens on 8080 of DND-SQL01, MEASURED 26 Sep 2026) a bind that
    # fails half-way, or a port taken from something live, is the wrong start.
    _refuse_if_taken(host, port)

    ctx = tls_context(cert, key) if cert else None     # refused before any socket is opened
    config = config or Config.from_env()
    app = make_app(db_path, config=config)
    httpd = make_server(host, port, app, server_class=ThreadedServer, handler_class=QuietHandler)
    if ctx is not None:
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        # wsgiref reads this to say wsgi.url_scheme = https, which is what
        # marks the session cookie Secure and builds the Entra redirect URI.
        httpd.base_environ["HTTPS"] = "on"
    return httpd


def serve(db_path: str, *, host: str = "127.0.0.1", port: int = 8085,
          config: Config | None = None, cert: str | None = None, key: str | None = None) -> None:
    config = config or Config.from_env()
    httpd = build(db_path, host=host, port=port, config=config, cert=cert, key=key)
    scheme = "https" if cert else "http"
    doors = [d for d, on in (("Windows account", config.windows_configured),
                             ("Entra", config.entra_configured)) if on]
    posture = " + ".join(doors + ["break-glass"]) if doors else \
        "break-glass only (no Windows domain and no Entra tenant configured)"
    print(f"PSA desk (Phase B pilot) on {scheme}://{host}:{port}", file=sys.stderr)
    print(f"  database: {db.describe(db_path)}", file=sys.stderr)
    print(f"  sign-in:  {posture}", file=sys.stderr)
    if not cert:
        print("  plain HTTP: the pilot's LAN only. The requester portal and Entra sign-in "
              "wait for --cert and --key.", file=sys.stderr)
    print("  wsgiref.simple_server is not a production server. Phase C puts the "
          "same app behind a real one.", file=sys.stderr)

    with httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.", file=sys.stderr)
