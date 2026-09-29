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

from .. import db, itil, numbering, phi, tickets

TOKEN_PREFIX = "psa_"
# What a token may do (gap 8): RAISE tickets and read its own; READ everything on
# its board and the configurations; WRITE a note, a status or an owner as well.
SCOPES = ("RAISE", "READ", "WRITE")
RANK = {"RAISE": 0, "READ": 1, "WRITE": 2}
NOTE_FLAGS = ("INTERNAL", "DISCUSSION")
MAX_NOTE = 4000
LIST_LIMIT = 200
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
                 at: datetime, created_by: str = "cli", scope: str = "RAISE") -> tuple[str, str]:
    """Mint a token. Returns (token_id, token). The token is returned ONCE and
    never stored; lose it and you mint another and disable this one."""
    label = label.strip()
    if not label:
        raise ValueError("a token needs a label saying what it is for")
    if conn.execute("SELECT 1 FROM board WHERE board_id = ?",
                    (board_id,)).fetchone() is None:
        raise ValueError(f"no board {board_id!r}")
    if scope not in SCOPES:
        raise ValueError("scope is RAISE, READ or WRITE")
    token_id = "tok_" + secrets.token_hex(6)
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    stamp = at.isoformat(sep=" ", timespec="minutes")
    conn.execute(
        "INSERT INTO api_token (token_id, token_sha256, label, board_id, created_at,"
        " created_by, disabled, scope) VALUES (?,?,?,?,?,?,0,?)",
        (token_id, _sha256(token), label, board_id, stamp, created_by, scope))
    db.audit(conn, at=stamp, actor=created_by, action="API_TOKEN_CREATE",
             subject_kind="api_token", subject_id=token_id,
             detail=f"board={board_id} label={label} scope={scope}")
    return token_id, token


def scope_of(token) -> str:
    """A row from before the scope column reads as RAISE."""
    value = token["scope"] if "scope" in token.keys() else None
    return value or "RAISE"


def _need(token, scope: str) -> None:
    if RANK[scope_of(token)] < RANK[scope]:
        raise ApiError("403 Forbidden", f"this token's scope is {scope_of(token)}; {scope} is needed")


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
        parts = request.path.strip("/").split("/")          # api v1 tickets|configurations [id]
        if parts[:2] != ["api", "v1"] or len(parts) not in (3, 4) or parts[2] not in ("tickets", "configurations"):
            raise ApiError("404 Not Found", "no such endpoint")
        kind, method = parts[2], request.method
        if kind == "tickets":
            if len(parts) == 3 and method == "POST":
                status, payload = _create(conn, token, request, now=now)
            elif len(parts) == 3 and method == "GET":
                status, payload = _list(conn, token, request, now=now)
            elif len(parts) == 4 and method == "GET":
                status, payload = _read(conn, token, parts[3], now=now)
            elif len(parts) == 4 and method == "PATCH":
                status, payload = _update(conn, token, parts[3], request, now=now)
            else:
                raise ApiError("405 Method Not Allowed",
                               f"{request.method} not allowed on {request.path}")
        else:
            if method != "GET":
                raise ApiError("405 Method Not Allowed", f"{request.method} not allowed on {request.path}")
            status, payload = (_configs(conn, token, request) if len(parts) == 3
                               else _config(conn, token, parts[3]))
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
    if dedup_key and len(dedup_key) > 200:
        raise ApiError("400 Bad Request", "dedup_key is at most 200 characters")

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
        requested_by=actor, description=description or None, at=now, source="API",
        # A machine raised it: ITIL's Event, where the board takes Events.
        record_type=itil.fit(conn, board_id, "EVENT"))
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


# The description is the ticket's opening event (what the requester or the
# machine said); it has no column of its own. MIN() rather than LIMIT in the
# scalar subquery, so the same SQL runs on SQL Server.
TICKET_SQL = ("SELECT t.work_item_id, t.board_id, t.state, t.priority, t.owner, t.requested_by, t.opened_at,"
              "       t.updated_at, t.closed_at, w.name AS summary, d.detail AS description, s.name AS status_name"
              "  FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
              "  LEFT JOIN board_status s ON s.board_status_id = t.board_status_id"
              "  LEFT JOIN ticket_event d ON d.ticket_event_id = (SELECT MIN(e.ticket_event_id) FROM ticket_event e"
              "       WHERE e.work_item_id = t.work_item_id AND e.kind IN ('INTAKE', 'OPENED'))")


def _shape(row, *, full: bool) -> dict:
    out = {"id": row["work_item_id"], "summary": row["summary"], "state": row["state"],
           "priority": row["priority"], "opened_at": row["opened_at"], "closed_at": row["closed_at"],
           "open": row["state"] in OPEN_STATES}
    if full:
        out.update({"status": row["status_name"], "owner": row["owner"], "requested_by": row["requested_by"],
                    "updated_at": row["updated_at"], "description": row["description"], "board": row["board_id"]})
    return out


def _audit_read(conn, token, *, now: datetime, detail: str) -> None:
    """A token on a restricted board is a reader of it: every read is audited,
    as a person's is (6.1, requirement 4)."""
    r = conn.execute("SELECT restricted FROM board WHERE board_id = ?", (token["board_id"],)).fetchone()
    if r and r["restricted"]:
        db.audit(conn, at=now.isoformat(sep=" ", timespec="minutes"), actor=f"api:{token['token_id']}",
                 action="RESTRICTED_READ", subject_kind="board", subject_id=token["board_id"], detail=detail)


def _read(conn, token, work_item_id: str, *, now: datetime):
    """A RAISE token reads only tickets it raised; a READ or WRITE token any
    ticket on its board. Anything else is a 404, which is also what a ticket
    that does not exist is -- a caller cannot tell the two apart, and should
    not be able to."""
    full = RANK[scope_of(token)] >= RANK["READ"]
    if full:
        row = conn.execute(TICKET_SQL + " WHERE t.work_item_id = ? AND t.board_id = ?",
                           (work_item_id, token["board_id"])).fetchone()
    else:
        row = conn.execute(TICKET_SQL + " WHERE t.work_item_id = ? AND t.requested_by = ?",
                           (work_item_id, f"api:{token['token_id']}")).fetchone()
    if row is None:
        raise ApiError("404 Not Found", "no such ticket")
    if full:
        _audit_read(conn, token, now=now, detail=f"api read {work_item_id}")
    return "200 OK", _shape(row, full=full)


def _list(conn, token, request, *, now: datetime):
    """The board's tickets for a READ or WRITE token: open by default, or
    closed, or all; since a day; paged."""
    _need(token, "READ")
    q = request.query
    state = (q.get("state") or "open").lower()
    if state not in ("open", "closed", "all"):
        raise ApiError("400 Bad Request", "state is open, closed or all")
    limit = q.get("limit") or str(50)
    offset = q.get("offset") or "0"
    if not (limit.isdigit() and 1 <= int(limit) <= LIST_LIMIT) or not offset.isdigit():
        raise ApiError("400 Bad Request", f"limit is 1 to {LIST_LIMIT}, offset a whole number")
    since = (q.get("since") or "").strip()
    if since:
        try:
            datetime.strptime(since, "%Y-%m-%d")
        except ValueError:
            raise ApiError("400 Bad Request", "since is a day, YYYY-MM-DD")
    where, params = ["t.board_id = ?"], [token["board_id"]]
    marks = ",".join("?" * len(OPEN_STATES))
    if state == "open":
        where.append(f"t.state IN ({marks})")
        params += list(OPEN_STATES)
    elif state == "closed":
        where.append(f"t.state NOT IN ({marks})")
        params += list(OPEN_STATES)
    if since:
        where.append("COALESCE(t.updated_at, t.opened_at) >= ?")
        params.append(since)
    rows = conn.execute(TICKET_SQL + " WHERE " + " AND ".join(where)
                        + " ORDER BY t.opened_at DESC, t.work_item_id DESC LIMIT ? OFFSET ?",
                        params + [int(limit), int(offset)]).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM ticket t WHERE " + " AND ".join(where), params).fetchone()[0]
    _audit_read(conn, token, now=now, detail=f"api list {state} {len(rows)} ticket(s)")
    return "200 OK", {"tickets": [_shape(r, full=True) for r in rows], "count": len(rows), "total": total,
                      "offset": int(offset)}


def _update(conn, token, work_item_id: str, request, *, now: datetime):
    """A WRITE token adds a note, sets the status by name, or sets the owner,
    on a ticket of its board; each is applied the way the desk applies it, so
    the history, the clocks and the rules run the same."""
    from ..board import EffortRefused, add_note, change_status, update_fields
    _need(token, "WRITE")
    data = _body(request)
    row = conn.execute(TICKET_SQL + " WHERE t.work_item_id = ? AND t.board_id = ?",
                       (work_item_id, token["board_id"])).fetchone()
    if row is None:
        raise ApiError("404 Not Found", "no such ticket")
    allowed = {"note", "flag", "status", "owner"}
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ApiError("422 Unprocessable Entity", f"unknown field(s): {', '.join(unknown)}; send note, flag, status, owner",
                       field=unknown[0])
    if not any(k in data for k in ("note", "status", "owner")):
        raise ApiError("400 Bad Request", "nothing to change: send note, status or owner")
    actor = f"api:{token['token_id']}"
    applied = []
    note = str(data.get("note") or "").strip()
    if "note" in data and not note:
        raise ApiError("422 Unprocessable Entity", "note is empty", field="note")
    if len(note) > MAX_NOTE:
        raise ApiError("422 Unprocessable Entity", f"note is longer than {MAX_NOTE} characters", field="note")
    flag = str(data.get("flag") or "INTERNAL").upper()
    if flag not in NOTE_FLAGS:
        raise ApiError("422 Unprocessable Entity", "flag is INTERNAL or DISCUSSION", field="flag")
    status_id = None
    if "status" in data:
        name = str(data.get("status") or "").strip()
        st = conn.execute("SELECT board_status_id FROM board_status WHERE board_id = ? AND LOWER(name) = LOWER(?)"
                          " AND COALESCE(inactive, 0) = 0", (token["board_id"], name)).fetchone()
        if st is None:
            raise ApiError("422 Unprocessable Entity", f"no status named {name!r} on {token['board_id']}", field="status")
        status_id = st["board_status_id"]
    if "owner" in data:
        owner = str(data.get("owner") or "").strip()
        if owner and conn.execute("SELECT 1 FROM board_member WHERE board_id = ? AND LOWER(member) = LOWER(?)",
                                  (token["board_id"], owner)).fetchone() is None:
            raise ApiError("422 Unprocessable Entity", f"{owner!r} is not a member of {token['board_id']}", field="owner")
        applied += update_fields(conn, work_item_id, at=now, actor=actor, owner=owner)   # "" clears, as on the desk
    if note:
        try:
            add_note(conn, work_item_id, body=note, flag=flag, actor=actor, at=now)
        except (EffortRefused, ValueError) as exc:
            raise ApiError("422 Unprocessable Entity", str(exc), field="note")
        _flag_phi(conn, work_item_id, "", note)
        applied.append(f"{flag.lower()} note")
    if status_id:
        change_status(conn, work_item_id, status_id, at=now, actor=actor)
        applied.append(f"status {data['status']}")
    db.audit(conn, at=now.isoformat(sep=" ", timespec="minutes"), actor=actor, action="API_UPDATE",
             subject_kind="ticket", subject_id=work_item_id, detail="; ".join(applied) or "nothing changed")
    row = conn.execute(TICKET_SQL + " WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    return "200 OK", {**_shape(row, full=True), "applied": applied}


CONFIG_FIELDS = ("configuration_id", "name", "config_type", "status", "dns_name", "os_name", "os_version", "manufacturer",
                 "model", "serial_number", "location", "vendor", "purchased_on", "warranty_ends_on", "installed_on",
                 "agreement_id", "last_seen_at")


def _config_shape(row) -> dict:
    out = {k: row[k] for k in CONFIG_FIELDS}
    out["id"] = out.pop("configuration_id")
    out["type"] = out.pop("config_type")
    return out


def _configs(conn, token, request):
    """The configurations, for a READ or WRITE token: a machine is the desk's,
    not a board's, so any such token lists them; the person on it never comes
    with them."""
    _need(token, "READ")
    q = request.query
    limit = q.get("limit") or str(50)
    offset = q.get("offset") or "0"
    if not (limit.isdigit() and 1 <= int(limit) <= LIST_LIMIT) or not offset.isdigit():
        raise ApiError("400 Bad Request", f"limit is 1 to {LIST_LIMIT}, offset a whole number")
    where, params = ["1 = 1"], []
    if q.get("type"):
        where.append("config_type = ?")
        params.append(q["type"].upper())
    if q.get("status"):
        where.append("status = ?")
        params.append(q["status"].upper())
    if q.get("q"):
        needle = f"%{q['q'].strip()}%"
        where.append("(name LIKE ? OR dns_name LIKE ? OR serial_number LIKE ?)")
        params += [needle, needle, needle]
    sql_where = " WHERE " + " AND ".join(where)
    rows = conn.execute("SELECT * FROM configuration" + sql_where + " ORDER BY name LIMIT ? OFFSET ?",
                        params + [int(limit), int(offset)]).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM configuration" + sql_where, params).fetchone()[0]
    return "200 OK", {"configurations": [_config_shape(r) for r in rows], "count": len(rows), "total": total,
                      "offset": int(offset)}


def _config(conn, token, configuration_id: str):
    _need(token, "READ")
    row = conn.execute("SELECT * FROM configuration WHERE configuration_id = ?", (configuration_id,)).fetchone()
    if row is None:
        raise ApiError("404 Not Found", "no such configuration")
    return "200 OK", _config_shape(row)
