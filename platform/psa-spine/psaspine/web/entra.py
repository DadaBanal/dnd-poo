"""Entra sign-in for a browser: OpenID Connect, authorization code with PKCE.

The normal way in for the ~400 staff the portal serves and for every fulfiller
with an organisation account. The desk is registered in PMC's tenant as a
public client (no client secret exists, so none can leak), and the exchange is
protected by PKCE: the browser is sent to Microsoft with a code challenge, comes
back with a one-time code, and the desk trades the code for an ID token by
proving it holds the verifier. The ID token is verified here with the same
by-hand RS256 check the API tokens get (auth.verify_entra_token), against the
tenant's published keys, fetched when a key is first needed and again when an
unknown key id appears (Microsoft rotates them).

Two cookies are involved. `psa_entra` holds the state, nonce and verifier of a
sign-in in flight, signed with the process secret and dead in ten minutes; it
is set on /entra only. The session cookie is the same one a break-glass login
sets. Both are Secure when the desk speaks HTTPS, which the portal handoff
requires before anyone types an organisation password near it.

The network calls (the token endpoint, the keys) are two functions on Config
so the tests supply their own and never leave the process. NOT VERIFIED against
a real tenant from here; the handoff's last step is that sign-in.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import urllib.parse
import urllib.request

from .. import db
from . import auth

AUTHORITY = "https://login.microsoftonline.com/{tenant}/"
FLIGHT_COOKIE = "psa_entra"
FLIGHT_SECONDS = 600
SCOPE = "openid profile email"
TIMEOUT = 10


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64u_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# --------------------------------------------------------------- network

def http_get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def http_post_form(url: str, data: dict) -> dict:
    body = urllib.parse.urlencode(data).encode("ascii")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def keys_from_jwks(document: dict) -> dict:
    """The JWKS document -> {kid: {"n": int, "e": int}}, RSA keys only."""
    out = {}
    for k in document.get("keys", []):
        if k.get("kty") == "RSA" and k.get("kid") and k.get("n") and k.get("e"):
            out[k["kid"]] = {"n": int.from_bytes(_b64u_decode(k["n"]), "big"),
                             "e": int.from_bytes(_b64u_decode(k["e"]), "big")}
    return out


def ensure_key(config, kid: str | None) -> dict:
    """The tenant's keys, fetched if `kid` is not among the ones held."""
    if kid and kid not in config.jwks:
        url = AUTHORITY.format(tenant=config.entra_tenant) + "discovery/v2.0/keys"
        config.jwks.update(keys_from_jwks(config.http_get(url)))
    return config.jwks


# ---------------------------------------------------------- the flight

def _sign(payload: bytes, secret: bytes) -> str:
    return _b64u(payload) + "." + _b64u(hmac.new(secret, payload, hashlib.sha256).digest())


def _open(token: str, secret: bytes, *, now: float) -> dict | None:
    try:
        body_b64, sig_b64 = token.split(".")
        payload = _b64u_decode(body_b64)
    except (ValueError, TypeError):
        return None
    if not hmac.compare_digest(_b64u(hmac.new(secret, payload, hashlib.sha256).digest()), sig_b64):
        return None
    flight = json.loads(payload)
    if float(flight.get("exp", 0)) < now:
        return None
    return flight


def _cookie(value: str, *, secure: bool, max_age: int) -> str:
    parts = [f"{FLIGHT_COOKIE}={value}", "Path=/entra", "HttpOnly", "SameSite=Lax",
             f"Max-Age={max_age}"]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def redirect_uri(request, config) -> str:
    """Where Microsoft sends the browser back: the public URL the deployment
    named, else this request's own scheme and host. It must equal, byte for
    byte, the redirect URI registered on the app."""
    base = (config.public_url or f"{request.scheme}://{request.headers.get('host', '')}").rstrip("/")
    return base + "/entra/callback"


def start(request, config, *, now: float | None = None):
    """GET /entra/start?next=/…: send the browser to Microsoft."""
    from . import redirect
    now = time.time() if now is None else now
    next_url = request.query.get("next", "/") or "/"
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = "/"
    verifier = secrets.token_urlsafe(48)
    flight = {"state": secrets.token_urlsafe(24), "nonce": secrets.token_urlsafe(24),
              "verifier": verifier, "next": next_url, "exp": now + FLIGHT_SECONDS}
    challenge = _b64u(hashlib.sha256(verifier.encode("ascii")).digest())
    params = {
        "client_id": config.entra_client, "response_type": "code",
        "redirect_uri": redirect_uri(request, config), "response_mode": "query",
        "scope": SCOPE, "state": flight["state"], "nonce": flight["nonce"],
        "code_challenge": challenge, "code_challenge_method": "S256"}
    url = AUTHORITY.format(tenant=config.entra_tenant) + "oauth2/v2.0/authorize?" + urllib.parse.urlencode(params)
    cookie = _cookie(_sign(json.dumps(flight).encode("utf-8"), config.session_secret),
                     secure=request.secure, max_age=FLIGHT_SECONDS)
    return redirect(url, set_cookie=cookie)


def callback(conn, request, config, now, *, clock: float | None = None):
    """GET /entra/callback?code=…&state=…: the browser is back."""
    from . import Response, redirect, templates, _session_cookie_value
    clock = time.time() if clock is None else clock

    def refused(why: str):
        return Response("401 Unauthorized", templates.login_page(
            entra_configured=config.entra_configured, windows_domain=config.windows_domain,
            error=why, next_url="/"))

    raw = request.cookies.get(FLIGHT_COOKIE)
    flight = _open(raw.value, config.session_secret, now=clock) if raw else None
    if flight is None:
        return refused("The sign-in took too long or did not start here. Try again.")
    if request.query.get("error"):
        return refused("Microsoft did not sign you in: "
                       + request.query.get("error_description", request.query["error"])[:200])
    if not hmac.compare_digest(request.query.get("state", ""), flight["state"]):
        return refused("The sign-in did not match the one that started. Try again.")
    code = request.query.get("code", "")
    if not code:
        return refused("Microsoft sent no code back. Try again.")

    token_url = AUTHORITY.format(tenant=config.entra_tenant) + "oauth2/v2.0/token"
    try:
        answer = config.http_post(token_url, {
            "client_id": config.entra_client, "grant_type": "authorization_code",
            "code": code, "redirect_uri": redirect_uri(request, config),
            "code_verifier": flight["verifier"], "scope": SCOPE})
    except Exception as exc:                          # the WAN, most likely
        return refused(f"Entra could not be reached ({exc.__class__.__name__}). "
                       "The break-glass sign-in below still works.")
    id_token = answer.get("id_token") if isinstance(answer, dict) else None
    if not id_token:
        return refused("Microsoft answered without an ID token: "
                       + str(answer.get("error_description", answer.get("error", "")))[:200])
    try:
        header, claims, _, _ = auth._jwt_segments(id_token)
        jwks = ensure_key(config, header.get("kid"))
        user = auth.verify_entra_token(id_token, jwks, tenant=config.entra_tenant,
                                       client_id=config.entra_client, now=clock)
    except auth.Unauthenticated as exc:
        return refused(f"The ID token did not verify ({exc}).")
    except Exception as exc:                          # keys unreachable
        return refused(f"The tenant's signing keys could not be read ({exc.__class__.__name__}).")
    if not hmac.compare_digest(str(claims.get("nonce", "")), flight["nonce"]):
        return refused("The ID token was not issued for this sign-in.")

    stamp = now.isoformat(sep=" ", timespec="minutes")
    db.audit(conn, at=stamp, actor=user.id, action="ENTRA_LOGIN", subject_kind="entra_user",
             subject_id=user.email, detail=user.name)
    conn.commit()
    session = auth.open_session(user, config.session_secret, now=clock)
    resp = redirect(flight["next"], set_cookie=_session_cookie_value(session, secure=request.secure))
    resp.headers.append(("Set-Cookie", _cookie("", secure=request.secure, max_age=0)))
    return resp
