"""Who is at the desk, and are they allowed in.

Two ways in, and the split is the whole design:

  * **Entra SSO is the normal path, and the only one for all but the rota.**
    A signed-in browser arrives with a bearer token; we check its signature
    against Microsoft's published keys, then its expiry, audience and issuer.
    D3 is closed on this (see docs/WS36) and it is not reopened here.

  * **Break-glass local accounts are the WAN-down path, and only that.**
    §11 test 10 says the desk answers when the WAN is down, and Entra needs the
    cloud. So a small, sealed set of scrypt-hashed local accounts — held by
    whoever is on the on-call rota — is the fallback. Created only by the CLI,
    seeded into no repository, and every use audited at login.

Standard library only, like the rest of the engine. That constraint is load
bearing here: it is why the RS256 verification below is written out with
`pow()` rather than imported. It is also why that path is labelled NOT VERIFIED
against a real tenant — no environment on this account has a route to
login.microsoftonline.com, so it is written to be correct and proven against a
synthetic key in the tests, not against Entra itself. Read that the way the
SQL Server port is read: generated to be right, run against the real target by
somebody who has one.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime

from .. import db

# scrypt parameters. N is the CPU/memory cost; 2**15 is a deliberate, unhurried
# choice for a login that happens a handful of times a shift, not a bulk API.
SCRYPT_N = 1 << 15
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SCRYPT_SALT_BYTES = 16
# scrypt needs ~128*N*r bytes (≈33.5 MB at these parameters), which is over
# OpenSSL's 32 MB default ceiling; name the ceiling so the cost parameters, not
# a library default, decide what is allowed.
SCRYPT_MAXMEM = 64 * 1024 * 1024

# How long a browser session lasts. A shift, so a WAN outage in the middle of
# one does not log the on-call person out at the worst possible moment.
SESSION_SECONDS = 12 * 60 * 60


class Unauthenticated(Exception):
    """No valid identity on this request. The web layer turns this into a 401
    or a redirect to the Entra sign-in; it is never a 500."""


class AuthConfigError(Exception):
    """The deployment asked for a path it did not configure — Entra without a
    tenant, a session without a secret. A misconfiguration, refused loudly at
    the edge rather than failing open."""


@dataclass
class User:
    """Who is acting, and what they may do. `roles` are board-scoped access
    rows read from board_member; `is_sysadmin` is the cross-board flag a
    break-glass account may carry. `via` records which door they came through,
    because a break-glass session and an Entra session are not the same risk."""

    id: str
    name: str
    email: str | None = None
    via: str = "entra"                       # 'entra' | 'local'
    is_sysadmin: bool = False
    roles: dict[str, str] = field(default_factory=dict)   # board_id -> access


# ----------------------------------------------------------- password hashing

def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """'scrypt$N$r$p$salt_hex$hash_hex'. Never the password, never reversible.

    The parameters travel with the hash so a later, costlier choice can be made
    without stranding the accounts already created under the old one.
    """
    if not password:
        raise ValueError("a break-glass password may not be empty")
    salt = salt or os.urandom(SCRYPT_SALT_BYTES)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N,
                            r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_DKLEN,
                            maxmem=SCRYPT_MAXMEM)
    return (f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}$"
            f"{salt.hex()}${digest.hex()}")


def verify_password(password: str, stored: str) -> bool:
    """Recompute under the stored parameters and compare in constant time."""
    try:
        scheme, n, r, p, salt_hex, hash_hex = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    try:
        digest = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
                                n=int(n), r=int(r), p=int(p),
                                dklen=len(hash_hex) // 2, maxmem=SCRYPT_MAXMEM)
    except (ValueError, MemoryError):
        return False
    return hmac.compare_digest(digest.hex(), hash_hex)


# --------------------------------------------------------- local accounts

def create_local_account(conn: sqlite3.Connection, username: str, password: str, *,
                         at: datetime, is_sysadmin: bool = False,
                         created_by: str = "cli") -> None:
    """Write one sealed account. The only place a local account is born.

    Refuses a duplicate rather than overwriting: re-creating an existing
    break-glass account silently would be a way to swap a credential without a
    trace, which is the one thing this table exists to prevent.
    """
    username = username.strip()
    if not username:
        raise ValueError("a break-glass account needs a username")
    exists = conn.execute("SELECT 1 FROM local_account WHERE username = ?",
                          (username,)).fetchone()
    if exists:
        raise ValueError(f"local account {username!r} already exists; disable it, "
                         "do not overwrite it")
    stamp = at.isoformat(sep=" ", timespec="minutes")
    conn.execute(
        "INSERT INTO local_account (username, scrypt_hash, is_sysadmin, created_at,"
        " created_by, disabled) VALUES (?,?,?,?,?,0)",
        (username, hash_password(password), 1 if is_sysadmin else 0, stamp, created_by))
    db.audit(conn, at=stamp, actor=created_by, action="LOCAL_ACCOUNT_CREATE",
             subject_kind="local_account", subject_id=username,
             detail=f"is_sysadmin={1 if is_sysadmin else 0}")


def authenticate_local(conn: sqlite3.Connection, username: str, password: str, *,
                       at: datetime) -> User:
    """Verify a break-glass login, record it, and return who it is.

    Every outcome is auditable. A break-glass login that leaves no trace is the
    thing the whole arrangement exists to avoid, so a refused attempt is written
    down too — a wrong password on a sealed account is exactly the event a later
    reader wants to find.
    """
    stamp = at.isoformat(sep=" ", timespec="minutes")
    row = conn.execute("SELECT * FROM local_account WHERE username = ?",
                       (username.strip(),)).fetchone()
    if row is None or row["disabled"] or not verify_password(password, row["scrypt_hash"]):
        reason = ("no such account" if row is None else
                  "account disabled" if row["disabled"] else "bad password")
        db.audit(conn, at=stamp, actor=username.strip() or "?",
                 action="LOCAL_LOGIN_REFUSED", subject_kind="local_account",
                 subject_id=username.strip() or None, detail=reason)
        conn.commit()
        raise Unauthenticated(f"break-glass login refused: {reason}")

    conn.execute("UPDATE local_account SET last_login_at = ? WHERE username = ?",
                 (stamp, row["username"]))
    db.audit(conn, at=stamp, actor=row["username"], action="LOCAL_LOGIN",
             subject_kind="local_account", subject_id=row["username"],
             detail="break-glass session opened")
    conn.commit()
    return User(id=row["username"], name=row["username"], via="local",
                is_sysadmin=bool(row["is_sysadmin"]),
                roles=board_roles(conn, row["username"]))


def board_roles(conn: sqlite3.Connection, member: str) -> dict[str, str]:
    """board_id -> access ('READ'|'WORK'|'ADMIN') for every board this member is
    on. This is the access control on a restricted board, read at the query and
    never a hint the interface is trusted to honour."""
    return {r["board_id"]: r["access"] for r in conn.execute(
        "SELECT board_id, access FROM board_member WHERE member = ?", (member,))}


# ------------------------------------------------------------- session cookies
#
# A signed token the browser carries: base64url(payload).base64url(hmac). The
# secret is per-process and not persisted (see server startup), so every restart
# invalidates every session — which for a shift-length pilot is a feature, not a
# cost. compare_digest everywhere, because a timing oracle on a session check is
# a real one.

def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64u_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def sign_session(payload: dict, secret: bytes) -> str:
    body = _b64u(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    mac = _b64u(hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{mac}"


def read_session(token: str, secret: bytes, *, now: float | None = None) -> dict | None:
    """Return the payload if the signature holds and the session has not
    expired, else None. Never raises on a malformed cookie — a garbage cookie is
    an unauthenticated request, not a server error."""
    now = time.time() if now is None else now
    try:
        body, mac = token.split(".", 1)
    except ValueError:
        return None
    expected = _b64u(hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(mac, expected):
        return None
    try:
        payload = json.loads(_b64u_decode(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if float(payload.get("exp", 0)) < now:
        return None
    return payload


def open_session(user: User, secret: bytes, *, now: float | None = None) -> str:
    now = time.time() if now is None else now
    return sign_session(
        {"sub": user.id, "name": user.name, "email": user.email, "via": user.via,
         "sysadmin": user.is_sysadmin, "iat": int(now),
         "exp": int(now) + SESSION_SECONDS}, secret)


def user_from_session(conn: sqlite3.Connection, payload: dict) -> User:
    """Rebuild the acting user from a validated session payload, re-reading the
    board roles from the database rather than trusting the cookie for them — a
    cookie says who you are, the database says what you may touch."""
    return User(id=payload["sub"], name=payload.get("name", payload["sub"]),
                email=payload.get("email"), via=payload.get("via", "entra"),
                is_sysadmin=bool(payload.get("sysadmin")),
                roles=board_roles(conn, payload["sub"]))


# ----------------------------------------------------------------- Entra JWT
#
# NOT VERIFIED against a real tenant. The signature check is RS256 done by hand
# with pow(), because standard-library-only leaves no RSA import; it is proven
# against a synthetic key in the tests and never against Entra. A deployment
# sets PSA_ENTRA_TENANT and PSA_ENTRA_CLIENT, and supplies the signing keys
# through `jwks` — fetched once at startup from the tenant's OIDC discovery
# document by code that lives outside this module, so this stays testable
# without a network.


def _jwt_segments(token: str) -> tuple[dict, dict, bytes, bytes]:
    try:
        header_b64, claims_b64, sig_b64 = token.split(".")
    except ValueError:
        raise Unauthenticated("token is not a three-part JWT")
    header = json.loads(_b64u_decode(header_b64))
    claims = json.loads(_b64u_decode(claims_b64))
    signing_input = f"{header_b64}.{claims_b64}".encode("ascii")
    signature = _b64u_decode(sig_b64)
    return header, claims, signing_input, signature


def _rsa_pkcs1_sha256_verify(n: int, e: int, signing_input: bytes,
                             signature: bytes) -> bool:
    """RS256 verify with nothing but big integers.

    RSASSA-PKCS1-v1_5: raise the signature to the public exponent mod n, and the
    result must be the DER-wrapped SHA-256 of the signing input, padded with
    0x00 0x01 0xFF...0xFF 0x00. Everything here is public (n and e come from the
    JWKS), so no secret is handled and pow() is all that is needed.
    """
    k = (n.bit_length() + 7) // 8
    if len(signature) != k:
        return False
    sig_int = int.from_bytes(signature, "big")
    if sig_int >= n:
        return False
    em = pow(sig_int, e, n).to_bytes(k, "big")

    # DER prefix for SHA-256, from RFC 8017 §9.2 notes.
    der_prefix = bytes.fromhex("3031300d060960864801650304020105000420")
    digest = hashlib.sha256(signing_input).digest()
    expected_tail = der_prefix + digest
    # em = 0x00 || 0x01 || PS(0xFF...) || 0x00 || T
    if len(em) < len(expected_tail) + 11:
        return False
    if em[0] != 0x00 or em[1] != 0x01:
        return False
    ps_end = 2
    while ps_end < len(em) and em[ps_end] == 0xFF:
        ps_end += 1
    if ps_end < 10 or ps_end >= len(em) or em[ps_end] != 0x00:
        return False
    return hmac.compare_digest(em[ps_end + 1:], expected_tail)


def verify_entra_token(token: str, jwks: dict, *, tenant: str, client_id: str,
                       now: float | None = None,
                       leeway: int = 60) -> User:
    """Validate an Entra bearer token and return who it is, or raise.

    jwks is {kid: {"n": int, "e": int}} — the tenant's signing keys, already
    base64url-decoded to integers by the fetch code. Checks, in order: the key
    exists, the RS256 signature holds, the token is inside its validity window,
    the audience is our client, and the issuer is our tenant. Every failure is
    the same Unauthenticated, because the caller's job is to send the user to
    sign in again, not to learn which check failed.
    """
    now = time.time() if now is None else now
    header, claims, signing_input, signature = _jwt_segments(token)
    if header.get("alg") != "RS256":
        raise Unauthenticated(f"unexpected token algorithm {header.get('alg')!r}")

    key = jwks.get(header.get("kid"))
    if key is None:
        raise Unauthenticated("token signed by an unknown key")
    if not _rsa_pkcs1_sha256_verify(key["n"], key["e"], signing_input, signature):
        raise Unauthenticated("token signature does not verify")

    if float(claims.get("nbf", 0)) - leeway > now:
        raise Unauthenticated("token not yet valid")
    if float(claims.get("exp", 0)) + leeway < now:
        raise Unauthenticated("token has expired")

    aud = claims.get("aud")
    if aud != client_id and client_id not in (aud if isinstance(aud, list) else []):
        raise Unauthenticated("token audience is not this application")
    iss = claims.get("iss", "")
    if tenant not in iss:
        raise Unauthenticated("token issuer is not the configured tenant")

    return User(id=claims.get("oid") or claims.get("sub"),
                name=claims.get("name", claims.get("preferred_username", "")),
                email=claims.get("preferred_username") or claims.get("email"),
                via="entra")
