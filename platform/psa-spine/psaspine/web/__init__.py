"""The WSGI application, and everything a request needs before a view runs.

PEP 3333 to the letter, so `wsgiref.validate.validator()` wraps `application`
in the tests and proves conformance, and so the same callable drops behind a
production server in Phase C with no code change. `wsgiref.simple_server` runs
it for the pilot — LAN only, Dada IT only — and that server is not production
and does not pretend to be.

Standard library only. The app opens one sqlite connection per request and
closes it; wsgiref.simple_server is single-threaded, so there is no sharing to
get wrong, and a per-request connection is the honest shape to grow from.

Identity is resolved once, at the edge, in one order:
  1. a valid session cookie  → the user it names, roles re-read from the database
  2. an Entra bearer token   → verified, if Entra is configured
  3. neither                 → Unauthenticated, which becomes the sign-in page
Every view runs with a real `User` or does not run at all.
"""
from __future__ import annotations

import http.cookies
import os
import secrets
import sqlite3
import urllib.parse
from typing import Callable
from dataclasses import dataclass, field
from datetime import datetime

from .. import db
from . import auth, router

SESSION_COOKIE = "psa_session"
# The largest request body read at all: one attachment at its limit plus the
# multipart framing and the form's other fields. Anything bigger is refused
# before a byte of it is read, so a large upload cannot fill memory.
MAX_BODY = 10 * 1024 * 1024 + 256 * 1024


class HttpError(Exception):
    def __init__(self, status: str, message: str = ""):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class Config:
    """What the deployment chose. The session secret is per-process and not
    persisted: every restart invalidates every session, which for a shift-length
    pilot is a feature. Entra is optional — without a tenant, the desk still
    answers on the break-glass path, which is exactly the WAN-down posture."""

    session_secret: bytes = field(default_factory=lambda: secrets.token_bytes(32))
    entra_tenant: str | None = None
    entra_client: str | None = None
    jwks: dict = field(default_factory=dict)     # {kid: {"n": int, "e": int}}, fetched as needed
    # The URL staff type (https://desk.example:8443); the Entra redirect URI is
    # built on it. Unset, the request's own scheme and host are used.
    public_url: str | None = None
    # The two network calls the browser sign-in makes; tests hand in their own.
    http_get: "Callable[[str], dict]" = None
    http_post: "Callable[[str, dict], dict]" = None

    def __post_init__(self):
        from . import entra
        self.http_get = self.http_get or entra.http_get_json
        self.http_post = self.http_post or entra.http_post_form

    @property
    def entra_configured(self) -> bool:
        return bool(self.entra_tenant and self.entra_client)

    @classmethod
    def from_env(cls) -> "Config":
        return cls(entra_tenant=os.environ.get("PSA_ENTRA_TENANT"),
                   entra_client=os.environ.get("PSA_ENTRA_CLIENT"),
                   public_url=os.environ.get("PSA_PUBLIC_URL"))


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, str]
    headers: dict[str, str]
    cookies: http.cookies.SimpleCookie
    body: bytes
    scheme: str = "http"

    @property
    def secure(self) -> bool:
        return self.scheme == "https"

    @classmethod
    def from_environ(cls, environ) -> "Request":
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 0
        if length > MAX_BODY:
            raise HttpError("413 Content Too Large",
                            "That is too large to send. Files over 10 MB are not kept.")
        body = environ["wsgi.input"].read(length) if length > 0 else b""
        headers = {k[5:].replace("_", "-").lower(): v
                   for k, v in environ.items() if k.startswith("HTTP_")}
        if "CONTENT_TYPE" in environ:
            headers["content-type"] = environ["CONTENT_TYPE"]
        cookies = http.cookies.SimpleCookie()
        if "HTTP_COOKIE" in environ:
            cookies.load(environ["HTTP_COOKIE"])
        return cls(
            method=environ.get("REQUEST_METHOD", "GET").upper(),
            path=environ.get("PATH_INFO", "/") or "/",
            query=dict(urllib.parse.parse_qsl(environ.get("QUERY_STRING", ""))),
            headers=headers, cookies=cookies, body=body,
            scheme=environ.get("wsgi.url_scheme", "http"))

    def _multipart(self):
        """(fields, files) of a multipart/form-data body, parsed with the
        standard library's email package (the cgi module is gone in 3.13).
        files is a list of (field name, filename, bytes); a file input left
        empty is not a file."""
        cached = getattr(self, "_parsed", None)
        if cached is not None:
            return cached
        import email.parser
        import email.policy
        fields: dict[str, str] = {}
        files: list[tuple[str, str, bytes]] = []
        head = ("Content-Type: " + self.headers.get("content-type", "") + "\r\n\r\n").encode("latin-1")
        message = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(head + self.body)
        if message.is_multipart():
            for part in message.iter_parts():
                name = part.get_param("name", header="content-disposition")
                if not name:
                    continue
                payload = part.get_payload(decode=True) or b""
                filename = part.get_filename()
                if filename is not None:
                    if payload:
                        files.append((name, filename, payload))
                else:
                    fields[name] = payload.decode(part.get_content_charset() or "utf-8", "replace")
        self._parsed = (fields, files)
        return self._parsed

    def is_multipart(self) -> bool:
        return self.headers.get("content-type", "").lower().startswith("multipart/form-data")

    def form(self) -> dict[str, str]:
        if self.is_multipart():
            return dict(self._multipart()[0])
        return dict(urllib.parse.parse_qsl(self.body.decode("utf-8", "replace")))

    def files(self, name: str = "file") -> list[tuple[str, bytes]]:
        """The (filename, bytes) of every file posted under `name`."""
        if not self.is_multipart():
            return []
        return [(fn, data) for field_name, fn, data in self._multipart()[1] if field_name == name]

    def form_list(self, name: str) -> list[str]:
        """Every value of a repeated field — the ticked rows of a bulk action."""
        return [v for k, v in urllib.parse.parse_qsl(self.body.decode("utf-8", "replace"))
                if k == name]

    def bearer(self) -> str | None:
        value = self.headers.get("authorization", "")
        return value[7:] if value.lower().startswith("bearer ") else None


@dataclass
class Response:
    status: str = "200 OK"
    body: str | bytes = ""
    content_type: str = "text/html; charset=utf-8"
    headers: list[tuple[str, str]] = field(default_factory=list)

    def emit(self, start_response):
        raw = self.body if isinstance(self.body, bytes) else self.body.encode("utf-8")
        headers = [("Content-Type", self.content_type),
                   ("Content-Length", str(len(raw))),
                   # The portal speaks to nothing external; say so to the browser.
                   ("Referrer-Policy", "same-origin"),
                   ("X-Content-Type-Options", "nosniff"),
                   *self.headers]
        start_response(self.status, headers)
        return [raw]


def redirect(location: str, *, set_cookie: str | None = None) -> Response:
    headers = [("Location", location)]
    if set_cookie is not None:
        headers.append(("Set-Cookie", set_cookie))
    return Response("303 See Other", "", headers=headers)


@dataclass
class Ctx:
    """One argument every view takes: the connection, the request, who is acting,
    and the deployment config. Views never touch the environ."""

    conn: sqlite3.Connection
    request: Request
    user: auth.User
    config: Config
    now: datetime


def _session_cookie_value(token: str, *, secure: bool = False) -> str:
    c = http.cookies.SimpleCookie()
    c[SESSION_COOKIE] = token
    m = c[SESSION_COOKIE]
    m["path"] = "/"
    m["httponly"] = True
    m["samesite"] = "Lax"
    m["max-age"] = str(auth.SESSION_SECONDS)
    if secure:
        # Over HTTPS the cookie is never sent in the clear; over the pilot's
        # plain LAN it cannot be marked so, or the browser would drop it.
        m["secure"] = True
    return m.OutputString()


def _cleared_cookie() -> str:
    c = http.cookies.SimpleCookie()
    c[SESSION_COOKIE] = ""
    m = c[SESSION_COOKIE]
    m["path"] = "/"
    m["max-age"] = "0"
    return m.OutputString()


def resolve_user(conn, request: Request, config: Config) -> auth.User:
    """Identity at the edge, in order. Raises Unauthenticated when there is none."""
    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie is not None:
        payload = auth.read_session(cookie.value, config.session_secret)
        if payload:
            return auth.user_from_session(conn, payload)
    token = request.bearer()
    # A psa_ token is a machine credential and is only valid under /api/. It is
    # not an Entra token and is never tried as one, so one leaked machine
    # credential cannot become a person on the desk.
    if token and not token.startswith("psa_") and config.entra_configured:
        from . import entra
        header = auth._jwt_segments(token)[0]
        try:
            jwks = entra.ensure_key(config, header.get("kid"))
        except Exception as exc:
            raise auth.Unauthenticated(f"the tenant's keys could not be read ({exc.__class__.__name__})")
        return auth.verify_entra_token(token, jwks,
                                       tenant=config.entra_tenant,
                                       client_id=config.entra_client)
    raise auth.Unauthenticated("no session and no bearer token")


def make_app(db_path: str, *, config: Config | None = None, clock=datetime.now):
    """Build the WSGI callable over a database file. `clock` is injectable so a
    test can pin 'now' without patching the module."""
    config = config or Config.from_env()

    def application(environ, start_response):
        conn = db.connect(db_path)
        try:
            request = Request.from_environ(environ)
            response = _route(conn, request, config, clock())
        except HttpError as exc:
            response = Response(exc.status, f"<h1>{exc.status}</h1><p>{exc.message}</p>")
        finally:
            db.close(conn)
        return response.emit(start_response)

    return application


def _route(conn, request: Request, config: Config, now: datetime) -> Response:
    # The machine API authenticates by token and ONLY by token, and it is routed
    # before the browser's identity is resolved so that a session cookie can
    # never authorise an API call. A cookie on an API is how a page on another
    # site makes a signed-in browser raise tickets it never meant to.
    if request.path.startswith("/api/"):
        from . import api
        return api.handle(conn, request, now=now)

    # A form posted from another site. The session cookie is SameSite=Lax, which
    # already keeps it off a cross-site POST; this refuses the request outright
    # as well, so the defence does not rest on one browser setting.
    if request.method == "POST":
        origin = request.headers.get("origin", "")
        host = request.headers.get("host", "")
        if origin and origin != "null" and host and \
                urllib.parse.urlsplit(origin).netloc.lower() != host.lower():
            return Response("403 Forbidden", "<h1>403 Forbidden</h1>"
                            "<p>This form was posted from another site.</p>")

    # The two doors that do not require an established identity.
    from . import templates
    if request.path == "/login" and request.method == "POST":
        return _do_login(conn, request, config, now)
    if request.path == "/logout":
        return redirect("/login", set_cookie=_cleared_cookie())
    if request.path in ("/entra/start", "/entra/callback") and request.method == "GET":
        from . import entra
        if not config.entra_configured:
            return Response("404 Not Found", "<h1>404</h1><p>Entra sign-in is not configured "
                            "on this desk.</p>")
        if request.path == "/entra/start":
            return entra.start(request, config)
        return entra.callback(conn, request, config, now)

    try:
        user = resolve_user(conn, request, config)
    except auth.Unauthenticated:
        if request.path == "/login":
            return Response(body=templates.login_page(
                entra_configured=config.entra_configured,
                next_url=request.query.get("next", "/")))
        # Anything else, unauthenticated, becomes the sign-in page with a 401 so
        # a script gets a status and a browser gets a form.
        return Response("401 Unauthorized", templates.login_page(
            entra_configured=config.entra_configured, next_url=request.path))

    ctx = Ctx(conn=conn, request=request, user=user, config=config, now=now)
    return router.dispatch(ctx)


def _do_login(conn, request: Request, config: Config, now: datetime) -> Response:
    from . import templates
    form = request.form()
    username = form.get("username", "")
    password = form.get("password", "")
    next_url = form.get("next", "/") or "/"
    try:
        user = auth.authenticate_local(conn, username, password, at=now)
    except auth.Unauthenticated as exc:
        return Response("401 Unauthorized", templates.login_page(
            entra_configured=config.entra_configured,
            error=str(exc), next_url=next_url))
    token = auth.open_session(user, config.session_secret)
    # Never redirect an open session to an absolute or off-site URL.
    if not next_url.startswith("/"):
        next_url = "/"
    return redirect(next_url, set_cookie=_session_cookie_value(token, secure=request.secure))


# The PEP 3333 callable a production server or the tests import directly is built
# per database, so there is no module-level global connection to get wrong.
