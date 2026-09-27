"""The Employee Portal door: *My requests* for someone the payroll portal has
already signed in (SQL01's handoff of 28 Sep 2026, decided by Dada).

The Employee Portal (`portal.pmcne.ph`, the payroll bridge) signs employees in
with their Windows account and holds the session as a token the page keeps in
sessionStorage. Its *My requests* entry posts that token here, top-level, in a
new tab. This door asks the bridge, server to server, who the token belongs to,
and if the answer is a real employee whose department the pilot has opened,
signs them in as the same person the Windows door would: the lower-case
sAMAccountName, which is what `/my` matches on.

What it will not do:
  * take the word of the browser: the token is checked with the bridge, never
    decoded or trusted here, and never logged, stored or echoed;
  * open for anyone: the door is off until PSA_EMPLOYEE_PORTAL_ORIGINS names
    the https origins the form may come from, and nobody passes until
    PSA_EMPLOYEE_PORTAL_DEPARTMENTS names their department (Dada's list; the
    DPO's §6.1 answer gates hospital-wide);
  * outlive the browser: the session cookie has no Max-Age, so closing the
    browser ends it on a shared ward PC;
  * sign in an admin preview (`impersonated`), or a record with no Windows
    username, or one that is not shaped like a username.

Every outcome is audited: PORTAL_SSO, or PORTAL_SSO_REFUSED with the reason in
words. Standard library only.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from .. import db
from . import auth

ADLOGIN = re.compile(r"^[a-z0-9._-]{1,20}$")
TIMEOUT = 5          # seconds; the bridge is on the same host
ME = "/api/portal/me"


def bridge_get(url: str, headers: dict, timeout: float = TIMEOUT) -> tuple[int, dict | None]:
    """One GET to the bridge: (status, JSON body or None). Raises on no answer
    (unreachable, slow, not JSON), which the door reports as 'could not be
    checked'; a refusal from the bridge is a status, not an exception."""
    req = urllib.request.Request(url, headers={**headers, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, None


class Refused(Exception):
    def __init__(self, status: str, message: str, reason: str):
        super().__init__(reason)
        self.status, self.message, self.reason = status, message, reason


# The words the employee reads. Each ends with the way in that always works.
ENDED = ("Your Employee Portal session has ended. Sign in there again, or sign in "
         "here with your Windows account.")
PREVIEW = "An admin preview cannot open My requests."
NOT_LINKED = ("Your employee record is not linked to a Windows account yet. Sign in "
              "here with your Windows account, or ask PMO to link it.")
NOT_OPEN = "My requests is not open for your department yet."
UNCHECKED = ("The Employee Portal could not be checked just now. Try again, or sign "
             "in here with your Windows account.")


def portal_login(conn, request, config, now):
    """POST /sso/portal on the portal host: the form field `token`."""
    from . import Response, redirect, _session_cookie_value, _norm_netloc, templates
    import urllib.parse

    # Off, or the wrong address: not there. Says nothing about why.
    if not config.employee_portal_origin_set or not config.is_portal_host(request):
        return Response("404 Not Found", "<h1>404 Not Found</h1><p>No such page.</p>")
    if request.method != "POST":
        return Response("405 Method Not Allowed", "<h1>405</h1><p>POST only.</p>")

    stamp = now.isoformat(sep=" ", timespec="minutes")

    def refused(exc: Refused, who: str = "?") -> Response:
        db.audit(conn, at=stamp, actor=who, action="PORTAL_SSO_REFUSED",
                 subject_kind="employee", subject_id=who if who != "?" else None,
                 detail=exc.reason)
        conn.commit()
        body = ("<h1>My requests</h1>"
                f"<div class='banner err'>{templates.esc(exc.message)}</div>"
                "<p><a class='btn' href='/login?next=/my'>Sign in with your Windows account "
                "instead</a></p>")
        return Response(exc.status, templates.page("My requests", body, requester=True))

    # Its own Origin rule, stricter than the desk's: exactly one of the listed
    # https origins. An http origin means the token already travelled in the
    # clear, and is refused for that reason.
    origin = request.headers.get("origin", "")
    o = urllib.parse.urlsplit(origin) if origin else None
    if (not o or o.scheme.lower() != "https"
            or "https://" + _norm_netloc("https", o.netloc) not in config.employee_portal_origin_set):
        return refused(Refused("403 Forbidden", "This form was posted from a site that is not the "
                               "Employee Portal.", "origin not allowed"
                               + (" (not https)" if o and o.scheme.lower() == "http" else "")))

    token = request.form().get("token", "").strip()
    if not token:
        return refused(Refused("401 Unauthorized", ENDED, "no token"))

    try:
        status, body = config.bridge_get(config.employee_portal_bridge.rstrip("/") + ME,
                                         {"x-pmc-portal-token": token}, TIMEOUT)
    except Exception as exc:                                 # noqa: BLE001 — no answer
        return refused(Refused("503 Service Unavailable", UNCHECKED,
                               f"bridge not answering ({exc.__class__.__name__})"))
    if status != 200 or not isinstance(body, dict):
        return refused(Refused("401 Unauthorized", ENDED, f"bridge answered {status}"))
    if body.get("impersonated"):
        return refused(Refused("403 Forbidden", PREVIEW, "admin preview"))
    employee = body.get("employee") if isinstance(body.get("employee"), dict) else {}
    adlogin = str(employee.get("ADLogin") or "").strip().lower()
    if not adlogin:
        return refused(Refused("403 Forbidden", NOT_LINKED, "no ADLogin on the employee record"))
    if not ADLOGIN.match(adlogin):
        return refused(Refused("403 Forbidden", NOT_LINKED, "ADLogin is not shaped like a username"),
                       who="?")
    department = str(employee.get("Department") or "").strip()
    if department not in config.employee_portal_department_set:
        return refused(Refused("403 Forbidden", NOT_OPEN, "department not open"), who=adlogin)

    contact = conn.execute(
        "SELECT contact_id, display_name, email FROM contact"
        " WHERE (LOWER(sam_account) = ? OR LOWER(upn) LIKE ?) AND inactive = 0"
        " ORDER BY CASE WHEN LOWER(sam_account) = ? THEN 0 ELSE 1 END LIMIT 1",
        (adlogin, adlogin + "@%", adlogin)).fetchone()
    full_name = str(employee.get("FullName") or "").strip()
    user = auth.User(id=adlogin,
                     name=full_name or (contact["display_name"] if contact else adlogin),
                     email=((contact["email"] or "").lower() or None) if contact else None,
                     via="portal", roles=auth.board_roles(conn, adlogin))
    db.audit(conn, at=stamp, actor=adlogin, action="PORTAL_SSO", subject_kind="employee",
             subject_id=adlogin, detail="employee portal"
             + (f", contact {contact['contact_id']}" if contact else ", no contact row"))
    conn.commit()

    next_url = request.form().get("next", "/my") or "/my"
    if not (next_url == "/my" or next_url.startswith("/my/")):
        next_url = "/my"
    session = auth.open_session(user, config.session_secret)
    # Secure by rule, not by request: the token only ever travels over https
    # (the origin rule above), and so does the cookie it becomes. No Max-Age:
    # the browser's own session, ended when it closes on a shared ward PC.
    return redirect(next_url, set_cookie=_session_cookie_value(session, secure=True, persistent=False))
