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
    # The URL staff type for the desk (https://desk.example); the Entra redirect
    # URI is built on it. Unset, the request's own scheme and host are used.
    # When a reverse proxy (IIS with ARR on DND-SQL01, MEASURED 27 Sep 2026)
    # fronts the desk, this is also what tells the desk the world is https:
    # cookies are Secure and HSTS is sent, derived from this setting and never
    # from a request header a client could write.
    public_url: str | None = None
    # The requester portal's own address (https://help.example). A request that
    # arrives for this host is a portal request: `/` goes to `/my`, the
    # technician pages answer 404, and sign-in returns to `/my`.
    portal_url: str | None = None
    # The two network calls the browser sign-in makes; tests hand in their own.
    http_get: "Callable[[str], dict]" = None
    http_post: "Callable[[str, dict], dict]" = None
    # The Employee Portal door (sso.py): the https origins its form may come
    # from (unset: the door is off), the bridge that vouches for a token, and
    # the departments the pilot has opened (unset: nobody passes). Comma lists.
    employee_portal_origins: str | None = None
    employee_portal_bridge: str = "http://127.0.0.1:4100"
    employee_portal_departments: str | None = None
    bridge_get: "Callable[[str, dict, float], tuple[int, dict | None]]" = None
    # The Windows sign-in: the domain to check against (PSA_WINDOWS_DOMAIN,
    # e.g. the NetBIOS name the host is joined to). Unset, the door is not shown.
    windows_domain: str | None = None
    windows_logon: "Callable[[str, str, str], tuple[bool, int]]" = None

    def __post_init__(self):
        from . import entra, sso
        self.http_get = self.http_get or entra.http_get_json
        self.http_post = self.http_post or entra.http_post_form
        self.bridge_get = self.bridge_get or sso.bridge_get

    @property
    def employee_portal_origin_set(self) -> set[str]:
        """The https origins the Employee Portal's form may be posted from,
        normalised. Anything not https in the list is dropped, not accepted."""
        out = set()
        for item in (self.employee_portal_origins or "").split(","):
            parts = _public_parts(item)
            if parts and parts[0] == "https":
                out.add("https://" + parts[1])
        return out

    @property
    def employee_portal_department_set(self) -> set[str]:
        return {d.strip() for d in (self.employee_portal_departments or "").split(",") if d.strip()}

    @property
    def entra_configured(self) -> bool:
        return bool(self.entra_tenant and self.entra_client)

    @property
    def windows_configured(self) -> bool:
        return bool(self.windows_domain)

    # ------------------------------------------------- the public addresses
    # Both URLs are optional and are read the same way: scheme and netloc,
    # lowercased, a default port dropped. Nothing else in them is used.

    @property
    def public_origins(self) -> set[str]:
        """The origins a browser form may legitimately be posted from: the desk's
        and the portal's public URLs. Behind a proxy the Host header the desk
        sees is the proxy's, so the same-host rule alone would refuse every
        sign-in; these are accepted in addition, and nothing else is."""
        out = set()
        for url in (self.public_url, self.portal_url):
            parts = _public_parts(url)
            if parts:
                out.add(parts[0] + "://" + parts[1])
        return out

    @property
    def public_https(self) -> bool:
        """The world reaches the desk over TLS, whether the desk speaks it or a
        proxy does. Then every cookie is Secure and HSTS is sent."""
        return any(p and p[0] == "https" for p in map(_public_parts, (self.public_url, self.portal_url)))

    def secure_cookie(self, request: "Request") -> bool:
        return request.secure or self.public_https

    def is_portal_host(self, request: "Request") -> bool:
        parts = _public_parts(self.portal_url)
        if not parts:
            return False
        got = _norm_netloc(parts[0], request.public_host)
        return bool(got) and got == parts[1]

    @classmethod
    def from_env(cls) -> "Config":
        return cls(entra_tenant=os.environ.get("PSA_ENTRA_TENANT"),
                   entra_client=os.environ.get("PSA_ENTRA_CLIENT"),
                   public_url=os.environ.get("PSA_PUBLIC_URL"),
                   portal_url=os.environ.get("PSA_PORTAL_URL"),
                   employee_portal_origins=os.environ.get("PSA_EMPLOYEE_PORTAL_ORIGINS"),
                   employee_portal_bridge=os.environ.get("PSA_EMPLOYEE_PORTAL_BRIDGE")
                   or "http://127.0.0.1:4100",
                   employee_portal_departments=os.environ.get("PSA_EMPLOYEE_PORTAL_DEPARTMENTS"),
                   windows_domain=os.environ.get("PSA_WINDOWS_DOMAIN"))


def _norm_netloc(scheme: str, netloc: str) -> str:
    netloc = (netloc or "").strip().lower()
    if scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]
    if scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]
    return netloc


def _public_parts(url: str | None) -> tuple[str, str] | None:
    """(scheme, netloc) of a configured public URL, or None when it is unset or
    not a URL. Anything after the netloc is ignored: these settings name a
    host, not a page."""
    if not url:
        return None
    parts = urllib.parse.urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return parts.scheme, _norm_netloc(parts.scheme, parts.netloc)


# The peer addresses a reverse proxy on the same host speaks from. A forwarded
# host header is believed from these and from nowhere else: a client on the
# LAN cannot claim to be the portal by writing a header.
LOOPBACK_PEERS = frozenset({"127.0.0.1", "::1", "::ffff:127.0.0.1"})


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, str]
    headers: dict[str, str]
    cookies: http.cookies.SimpleCookie
    body: bytes
    scheme: str = "http"
    remote_addr: str = ""
    query_string: str = ""

    def query_list(self, name: str) -> list[str]:
        """Every value of a repeated query key (checkboxes on a GET form)."""
        return [v for k, v in urllib.parse.parse_qsl(self.query_string) if k == name]

    @property
    def secure(self) -> bool:
        return self.scheme == "https"

    @property
    def forwarded_host(self) -> str | None:
        """The host the proxy was asked for, believed only from a loopback peer.
        IIS/ARR on DND-SQL01 sends `Host: 127.0.0.1:8085` and can be told to
        add X-Forwarded-Host (MEASURED 27 Sep 2026, part 8 of the runbook
        Reply); anything not on the loopback does not get to say this."""
        if self.remote_addr in LOOPBACK_PEERS:
            return self.headers.get("x-forwarded-host") or None
        return None

    @property
    def public_host(self) -> str:
        """The host this request was really made to: the forwarded one when a
        proxy on this machine says so, else the Host header."""
        return (self.forwarded_host or self.headers.get("host", "")).split(",", 1)[0].strip()

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
            path=(environ.get("PATH_INFO", "/") or "/").encode("latin-1", "replace").decode("utf-8", "replace"),
            query=dict(urllib.parse.parse_qsl(environ.get("QUERY_STRING", ""))),
            headers=headers, cookies=cookies, body=body,
            scheme=environ.get("wsgi.url_scheme", "http"),
            remote_addr=environ.get("REMOTE_ADDR", ""),
            query_string=environ.get("QUERY_STRING", ""))

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


def _session_cookie_value(token: str, *, secure: bool = False, persistent: bool = True) -> str:
    c = http.cookies.SimpleCookie()
    c[SESSION_COOKIE] = token
    m = c[SESSION_COOKIE]
    m["path"] = "/"
    m["httponly"] = True
    m["samesite"] = "Lax"
    if persistent:
        m["max-age"] = str(auth.SESSION_SECONDS)
    # else: no Max-Age, so the browser drops it when it closes (the Employee
    # Portal door, on a shared ward PC). The token inside still expires.
    if secure:
        # Over HTTPS the cookie is never sent in the clear; over the pilot's
        # plain LAN it cannot be marked so, or the browser would drop it.
        m["secure"] = True
    return m.OutputString()


def _cleared_cookie(*, secure: bool = False) -> str:
    c = http.cookies.SimpleCookie()
    c[SESSION_COOKIE] = ""
    m = c[SESSION_COOKIE]
    m["path"] = "/"
    m["max-age"] = "0"
    if secure:
        # A clear with different attributes is a different cookie to some
        # browsers; the one being cleared was Secure, so this one is too.
        m["secure"] = True
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
    from .. import live
    live.reset()            # chat round six: typing and presence belong to this app, from empty

    def application(environ, start_response):
        conn = db.connect(db_path)
        request = None
        try:
            request = Request.from_environ(environ)
            response = _route(conn, request, config, clock())
        except HttpError as exc:
            response = Response(exc.status, f"<h1>{exc.status}</h1><p>{exc.message}</p>")
        finally:
            db.close(conn)
            db.set_source(None)           # the request's audit source never outlives it
        if (request is not None and config.secure_cookie(request)
                and not any(k.lower() == "strict-transport-security" for k, _ in response.headers)):
            # The world reaches the desk over TLS (its own, or the proxy's, by
            # config): a browser that has seen the desk once never tries http
            # again for a year. No includeSubDomains: this host is one name
            # under pmcne.ph and decides nothing for the others.
            response.headers.append(("Strict-Transport-Security", "max-age=31536000"))
        return response.emit(start_response)

    return application


def _route(conn, request: Request, config: Config, now: datetime) -> Response:
    # The machine API authenticates by token and ONLY by token, and it is routed
    # before the browser's identity is resolved so that a session cookie can
    # never authorise an API call. A cookie on an API is how a page on another
    # site makes a signed-in browser raise tickets it never meant to.
    # The portal's own address serves the requester's pages and nothing else.
    # Decided before identity: a technician path on the portal host is not
    # there, for anyone, and the answer that reveals least is the plain 404.
    portal = config.is_portal_host(request)
    from .. import db as _db
    _db.set_source("API" if request.path.startswith("/api/") else ("PORTAL" if portal else "DESK"))
    if portal:
        if request.path == "/":
            return redirect("/my")
        if not _portal_path(request.path):
            return Response("404 Not Found", "<h1>404 Not Found</h1><p>No such page.</p>")

    # The Employee Portal door has its own Origin rule and its own answers; it
    # is routed before the desk's Origin check, like the API, and answers 404
    # anywhere but the portal host, or while it is off.
    if request.path == "/sso/portal":
        from . import sso
        return sso.portal_login(conn, request, config, now)      # GET: the refusal page

    if request.path.startswith("/api/"):
        from . import api
        return api.handle(conn, request, now=now)

    # A form posted from another site. The session cookie is SameSite=Lax, which
    # already keeps it off a cross-site POST; this refuses the request outright
    # as well, so the defence does not rest on one browser setting. The origin
    # must be this host's, or one of the two public addresses the deployment
    # named: behind the proxy the Host the desk sees is the proxy's own.
    if request.method == "POST":
        origin = request.headers.get("origin", "")
        host = request.headers.get("host", "")
        if origin and origin != "null" and host:
            o = urllib.parse.urlsplit(origin)
            same_host = o.netloc.lower() == host.lower()
            public = (o.scheme.lower() + "://" + _norm_netloc(o.scheme.lower(), o.netloc)
                      ) in config.public_origins
            if not (same_host or public):
                return Response("403 Forbidden", "<h1>403 Forbidden</h1>"
                                "<p>This form was posted from another site.</p>")

    # The two doors that do not require an established identity.
    from . import templates
    if request.path == "/login" and request.method == "POST":
        return _do_login(conn, request, config, now, portal=portal)
    if request.path == "/logout":
        return redirect("/login", set_cookie=_cleared_cookie(secure=config.secure_cookie(request)))
    if request.path in ("/entra/start", "/entra/callback") and request.method == "GET":
        from . import entra
        if not config.entra_configured:
            return Response("404 Not Found", "<h1>404</h1><p>Entra sign-in is not configured "
                            "on this desk.</p>")
        if request.path == "/entra/start":
            return entra.start(request, config)
        return entra.callback(conn, request, config, now)

    # A calendar feed is read by a phone's calendar app, which has no session:
    # the token in the path is the whole credential, and the view checks it.
    if request.path.startswith("/calendar/feed/") and request.method == "GET" and not portal:
        feed_user = auth.User(id="calendar-feed", name="calendar-feed", via="feed")
        feed_user.requester = True
        feed_user.modules = {}
        return router.dispatch(Ctx(conn=conn, request=request, user=feed_user, config=config, now=now))

    try:
        user = resolve_user(conn, request, config)
    except auth.Unauthenticated:
        if request.path == "/login":
            next_url = request.query.get("next", "/")
            return Response(body=templates.login_page(
                entra_configured=config.entra_configured, windows_domain=config.windows_domain,
                next_url=_portal_next(next_url) if portal else next_url, requester=portal))
        # Anything else, unauthenticated, becomes the sign-in page with a 401 so
        # a script gets a status and a browser gets a form.
        return Response("401 Unauthorized", templates.login_page(
            entra_configured=config.entra_configured, windows_domain=config.windows_domain,
            next_url=_portal_next(request.path) if portal else request.path, requester=portal))

    ctx = Ctx(conn=conn, request=request, user=user, config=config, now=now)
    from .. import priorities
    templates.set_priorities(priorities.table(conn))          # 060: the badges' words and colours
    # Who gets the requester's layout: everyone on the portal host, and anyone
    # who is on no board (a requester is not a fulfiller). Derived here, once,
    # so every page draws the same shell for the same person.
    from .views import common
    user.requester = portal or not common.board_ids_for(ctx)
    # The security role's level per module (040), read once, so the nav shows
    # only what the person may open and every view asks the same question.
    from .. import security
    user.modules = security.levels(conn, user)
    # 072: the live chats on this person's boards, so every desk page draws its
    # banner and quick view already filled (one indexed read; none for a requester).
    # 073: only a chat operator answers chats, and only on a board that takes them.
    user.live_chats, user.chat_operator = [], False
    if not user.requester and _db.table_exists(conn, "chat_session"):
        from .. import chat as _chat
        from .views.chat import live_for
        try:
            user.chat_operator = _chat.is_operator(conn, user.id)
        except Exception:                              # noqa: BLE001 - before 073 there is no tick: nobody answers,
            user.chat_operator = False                 # and every other page still opens
        user.live_chats = live_for(ctx) if user.chat_operator else []
        if user.chat_operator:                         # chat round six: a desk page of theirs is open
            from .. import live
            live.seen(user.id)
    conn.commit()
    return router.dispatch(ctx)


# What the portal host answers. Everything else there is a 404 before identity
# is even looked at. `/my` and below is the requester's surface; the rest is
# the way in and out.
_PORTAL_EXACT = frozenset({"/my", "/login", "/logout", "/entra/start", "/entra/callback",
                           "/sso/portal"})


def _portal_path(path: str) -> bool:
    return path in _PORTAL_EXACT or path.startswith("/my/")


def _portal_next(next_url: str) -> str:
    """Where a sign-in on the portal host lands: their requests, never a desk page."""
    return next_url if next_url == "/my" or next_url.startswith("/my/") else "/my"


def _do_login(conn, request: Request, config: Config, now: datetime, *,
              portal: bool = False) -> Response:
    from . import templates
    form = request.form()
    username = form.get("username", "")
    password = form.get("password", "")
    next_url = form.get("next", "/") or "/"
    if portal:
        next_url = _portal_next(next_url)
    door = form.get("door", "local")
    try:
        if door == "windows":
            if not config.windows_configured:
                raise auth.Unauthenticated("the Windows sign-in is not configured on this desk")
            user = auth.authenticate_windows(conn, username, password, at=now,
                                             domain=config.windows_domain,
                                             logon=config.windows_logon)
        else:
            user = auth.authenticate_local(conn, username, password, at=now)
    except auth.AuthConfigError as exc:
        return Response("401 Unauthorized", templates.login_page(
            entra_configured=config.entra_configured, windows_domain=config.windows_domain,
            error=str(exc), next_url=next_url, requester=config.is_portal_host(request)))
    except auth.Unauthenticated as exc:
        return Response("401 Unauthorized", templates.login_page(
            entra_configured=config.entra_configured, windows_domain=config.windows_domain,
            error=str(exc), next_url=next_url, requester=config.is_portal_host(request)))
    token = auth.open_session(user, config.session_secret)
    # Never redirect an open session to an absolute or off-site URL.
    if not next_url.startswith("/"):
        next_url = "/"
    return redirect(next_url, set_cookie=_session_cookie_value(token, secure=config.secure_cookie(request)))


# The PEP 3333 callable a production server or the tests import directly is built
# per database, so there is no module-level global connection to get wrong.
