"""The machine API: how monitoring, the archive and other systems raise tickets.

JSON over the same WSGI app, under /api/v1/, with its own authentication. Three
decisions shape it, and each is a place somebody could reasonably choose
otherwise:

  * **A local token, not Entra.** §6.2 is the strongest argument for building on
    premises: a desk that needs the WAN is unavailable exactly when it is most
    needed. The monitor raising "the WAN is down" cannot fetch an Entra token
    while the WAN is down. So machines hold a token -- 256 random bits, stored
    only as a sha256, shown once at creation, scoped to one board, and audited on
    every use. See schema/local/api_token.sql.

  * **Tokens only; no cookies.** The API never reads a session cookie, and the
    browser surfaces never read an API token. A cookie on an API is how a page on
    another site makes a signed-in browser raise tickets it never meant to; a
    token on the UI is how one leaked machine credential becomes a person.

  * **Priority is computed, never asserted.** The record's rule is that priority
    comes from impact x urgency and is never read from the caller. A machine
    answers the same two plain questions a nurse does -- how many people are
    affected, is care waiting -- and tickets.compute_priority decides. A caller
    that sends "priority": "P1" is refused in words, not silently obeyed.

Repeat firings collapse: a caller-chosen `dedup_key` holds one open ticket, and
a repeat is a note and a count on it (016). PHI is scanned here as everywhere
else, and the finding never repeats the value.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
from datetime import datetime

from .. import db, numbering, phi, tickets

TOKEN_PREFIX = "psa_"
OPEN_STATES = ("NEW", "TRIAGED", "IN_PROGRESS", "WAITING_CLIENT", "WAITING_VENDOR")
IMPACTS = ("I1", "I2", "I3")
URGENCIES = ("U1", "U2", "U3")
MAX_SUMMARY = 200


class ApiError(Exception):
    def __init__(self, status: str, message: str, **extra):
        super().__init__(message)
        self.status = status
        self.message = message
        self.extra = extra


def _sha256(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ------------------------------------------------------------ the credential

def create_token(conn: sqlite3.Connection, *, label: str, board_id: str,
                 at: datetime, created_by: str = "cli") -> tuple[str, str]:
    """Mint a token. Returns (token_id, token). The token is returned ONCE and
    never stored; lose it and you mint another and disable this one."""
    label = label.strip()
    if not label:
        raise ValueError("a token needs a label saying what it is for")
    if conn.execute("SELECT 1 FROM board WHERE board_id = ?",
                    (board_id,)).fetchone() is None:
        raise ValueError(f"no board {board_id!r}")
    token_id = "tok_" + secrets.token_hex(6)
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    stamp = at.isoformat(sep=" ", timespec="minutes")
    conn.execute(
        "INSERT INTO api_token (token_id, token_sha256, label, board_id, created_at,"
        " created_by, disabled) VALUES (?,?,?,?,?,?,0)",
        (token_id, _sha256(token), label, board_id, stamp, created_by))
    db.audit(conn, at=stamp, actor=created_by, action="API_TOKEN_CREATE",
             subject_kind="api_token", subject_id=token_id,
             detail=f"board={board_id} label={label}")
    return token_id, token


def authenticate(conn: sqlite3.Connection, authorization: str, *, at: datetime):
    """The token row for a valid bearer token, or ApiError 401.

    Every refusal carries the same message, so a caller probing for which
    tokens exist learns nothing from the difference between 'unknown' and
    'disabled'. The audit row, which only an administrator reads, does say which.
    """
    stamp = at.isoformat(sep=" ", timespec="minutes")
    value = authorization or ""
    if not value.lower().startswith("bearer "):
        raise ApiError("401 Unauthorized", "a bearer token is required")
    token = value[7:].strip()
    if not token.startswith(TOKEN_PREFIX):
        raise ApiError("401 Unauthorized", "a bearer token is required")

    digest = _sha256(token)
    row = conn.execute("SELECT * FROM api_token WHERE token_sha256 = ?",
                       (digest,)).fetchone()
    # compare_digest on the stored digest as well as the lookup, so a timing
    # difference in the index cannot be the only thing standing between a guess
    # and a match.
    if row is None or not hmac.compare_digest(row["token_sha256"], digest):
        db.audit(conn, at=stamp, actor="?", action="API_AUTH_REFUSED",
                 subject_kind="api_token", subject_id=None,
                 detail="unknown token")
        conn.commit()
        raise ApiError("401 Unauthorized", "a bearer token is required")
    if row["disabled"]:
        db.audit(conn, at=stamp, actor=row["token_id"], action="API_AUTH_REFUSED",
                 subject_kind="api_token", subject_id=row["token_id"],
                 detail="token disabled")
        conn.commit()
        raise ApiError("401 Unauthorized", "a bearer token is required")

    conn.execute("UPDATE api_token SET last_used_at = ? WHERE token_id = ?",
                 (stamp, row["token_id"]))
    return row


# ----------------------------------------------------------------- routing

def handle(conn: sqlite3.Connection, request, *, now: datetime):
    """Answer one /api/ request. Always JSON, always a status that means what
    it says -- a machine reading this has no human to interpret a 200 that
    carries an error in its body."""
    from . import Response
    try:
        token = authenticate(conn, request.headers.get("authorization", ""), at=now)
        parts = request.path.strip("/").split("/")          # api v1 tickets [id]
        if parts[:3] != ["api", "v1", "tickets"]:
            raise ApiError("404 Not Found", "no such endpoint")
        if len(parts) == 3 and request.method == "POST":
            status, payload = _create(conn, token, request, now=now)
        elif len(parts) == 4 and request.method == "GET":
            status, payload = _read(conn, token, parts[3])
        elif len(parts) in (3, 4):
            raise ApiError("405 Method Not Allowed",
                           f"{request.method} not allowed on {request.path}")
        else:
            raise ApiError("404 Not Found", "no such endpoint")
        conn.commit()
    except ApiError as exc:
        conn.rollback()
        headers = []
        if exc.status.startswith("401"):
            headers.append(("WWW-Authenticate", 'Bearer realm="psa"'))
        body = {"error": exc.message, **exc.extra}
        return Response(exc.status, json.dumps(body),
                        content_type="application/json; charset=utf-8",
                        headers=headers)
    return Response(status, json.dumps(payload),
                    content_type="application/json; charset=utf-8")


def _body(request) -> dict:
    ctype = request.headers.get("content-type", "")
    if "json" not in ctype.lower():
        raise ApiError("415 Unsupported Media Type", "send application/json")
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ApiError("400 Bad Request", "the body is not valid JSON")
    if not isinstance(data, dict):
        raise ApiError("400 Bad Request", "the body must be a JSON object")
    return data


def _create(conn, token, request, *, now: datetime):
    data = _body(request)

    if "priority" in data:
        raise ApiError(
            "422 Unprocessable Entity",
            "priority is computed from impact and urgency, never supplied; "
            "send impact (I1-I3) and urgency (U1-U3) instead",
            field="priority")

    summary = str(data.get("summary") or "").strip()
    if not summary:
        raise ApiError("422 Unprocessable Entity", "summary is required",
                       field="summary")
    if len(summary) > MAX_SUMMARY:
        raise ApiError("422 Unprocessable Entity",
                       f"summary is longer than {MAX_SUMMARY} characters",
                       field="summary")
    impact = str(data.get("impact") or "I3").upper()
    urgency = str(data.get("urgency") or "U3").upper()
    if impact not in IMPACTS:
        raise ApiError("422 Unprocessable Entity", "impact must be I1, I2 or I3",
                       field="impact")
    if urgency not in URGENCIES:
        raise ApiError("422 Unprocessable Entity", "urgency must be U1, U2 or U3",
                       field="urgency")
    description = str(data.get("description") or "").strip()
    dedup_key = str(data.get("dedup_key") or "").strip() or None

    board_id = token["board_id"]
    actor = f"api:{token['token_id']}"
    stamp = now.isoformat(sep=" ", timespec="minutes")

    # A repeat firing of an alert whose ticket is still open is a count on that
    # ticket, not a new one (016).
    if dedup_key:
        alert = conn.execute(
            "SELECT a.work_item_id, a.times, t.state FROM api_alert a"
            "  JOIN ticket t ON t.work_item_id = a.work_item_id"
            " WHERE a.board_id = ? AND a.dedup_key = ?",
            (board_id, dedup_key)).fetchone()
        if alert and alert["state"] in OPEN_STATES:
            times = alert["times"] + 1
            conn.execute(
                "UPDATE api_alert SET last_seen = ?, times = ?"
                " WHERE board_id = ? AND dedup_key = ?",
                (stamp, times, board_id, dedup_key))
            conn.execute(
                "INSERT INTO ticket_event (work_item_id, occurred_at, kind, actor, detail)"
                " VALUES (?,?,'API_REPEAT',?,?)",
                (alert["work_item_id"], stamp, actor,
                 f"alert {dedup_key!r} fired again ({times} times)"
                 + (f": {description}" if description else "")))
            _flag_phi(conn, alert["work_item_id"], summary, description)
            return "200 OK", {"id": alert["work_item_id"], "duplicate": True,
                              "times": times}

    ticket_id = tickets.open_ticket(
        conn, board_id=board_id, summary=summary, impact=impact, urgency=urgency,
        requested_by=actor, description=description or None, at=now)
    row = conn.execute("SELECT priority, priority_source FROM ticket"
                       " WHERE work_item_id = ?", (ticket_id,)).fetchone()
    priority, source = row["priority"], row["priority_source"]
    if dedup_key:
        # Replace any row pointing at a ticket that has since been resolved: a
        # fault that returns after being fixed is a new fault.
        conn.execute(
            "INSERT OR REPLACE INTO api_alert (board_id, dedup_key, work_item_id,"
            " first_seen, last_seen, times) VALUES (?,?,?,?,?,1)",
            (board_id, dedup_key, ticket_id, stamp, stamp))
    _flag_phi(conn, ticket_id, summary, description)
    return "201 Created", {"id": ticket_id, "duplicate": False,
                           "priority": priority, "priority_source": source}


def _flag_phi(conn, work_item_id: str, summary: str, description: str) -> None:
    for code, severity, detail in phi.scan_fields(
            {"summary": summary, "description": description}):
        conn.execute(
            "INSERT INTO data_quality (run_id, subject_kind, subject_id, code,"
            " detail, severity) VALUES (?,?,?,?,?,?)",
            ("api", "ticket", work_item_id, code, detail, severity))


def _read(conn, token, work_item_id: str):
    """A token reads only tickets it raised. Anything else is a 404, which is
    also what a ticket that does not exist is -- a caller cannot tell the two
    apart, and should not be able to."""
    row = conn.execute(
        "SELECT t.work_item_id, t.state, t.priority, t.opened_at, t.closed_at,"
        "       w.name AS summary"
        "  FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
        " WHERE t.work_item_id = ? AND t.requested_by = ?",
        (work_item_id, f"api:{token['token_id']}")).fetchone()
    if row is None:
        raise ApiError("404 Not Found", "no such ticket")
    return "200 OK", {"id": row["work_item_id"], "summary": row["summary"],
                      "state": row["state"], "priority": row["priority"],
                      "opened_at": row["opened_at"], "closed_at": row["closed_at"],
                      "open": row["state"] in OPEN_STATES}
