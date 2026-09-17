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
from dataclasses import dataclass, field
from datetime import datetime

from .. import db
from . import auth, router

SESSION_COOKIE = "psa_session"


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
    jwks: dict = field(default_factory=dict)     # {kid: {"n": int, "e": int}}

    @property
    def entra_configured(self) -> bool:
        return bool(self.entra_tenant and self.entra_client and self.jwks)

    @classmethod
    def from_env(cls) -> "Config":
        return cls(entra_tenant=os.environ.get("PSA_ENTRA_TENANT"),
                   entra_client=os.environ.get("PSA_ENTRA_CLIENT"))


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, str]
    headers: dict[str, str]
    cookies: http.cookies.SimpleCookie
    body: bytes

    @classmethod
    def from_environ(cls, environ) -> "Request":
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 0
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
            headers=headers, cookies=cookies, body=body)

    def form(self) -> dict[str, str]:
        return dict(urllib.parse.parse_qsl(self.body.decode("utf-8", "replace")))

    def bearer(self) -> str | None:
        value = self.headers.get("authorization", "")
        return value[7:] if value.lower().startswith("bearer ") else None


@dataclass
class Response:
    status: str = "200 OK"
    body: str = ""
    content_type: str = "text/html; charset=utf-8"
    headers: list[tuple[str, str]] = field(default_factory=list)

    def emit(self, start_response):
        raw = self.body.encode("utf-8")
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


def _session_cookie_value(token: str) -> str:
    c = http.cookies.SimpleCookie()
    c[SESSION_COOKIE] = token
    m = c[SESSION_COOKIE]
    m["path"] = "/"
    m["httponly"] = True
    m["samesite"] = "Lax"
    m["max-age"] = str(auth.SESSION_SECONDS)
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
    if token and config.entra_configured:
        return auth.verify_entra_token(token, config.jwks,
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
            conn.close()
        return response.emit(start_response)

    return application


def _route(conn, request: Request, config: Config, now: datetime) -> Response:
    # The two doors that do not require an established identity.
    from . import templates
    if request.path == "/login" and request.method == "POST":
        return _do_login(conn, request, config, now)
    if request.path == "/logout":
        return redirect("/login", set_cookie=_cleared_cookie())

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
    return redirect(next_url, set_cookie=_session_cookie_value(token))


# The PEP 3333 callable a production server or the tests import directly is built
# per database, so there is no module-level global connection to get wrong.
