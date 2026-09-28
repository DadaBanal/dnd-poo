"""The Employee Portal door: *My requests* for someone the payroll portal has
already signed in (SQL01's handoff of 28 Sep 2026, decided by Dada; hardened
per SQL01's review of the same day before it reaches ward PCs).

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
  * let a refused POST sit in a tab's history: every refusal is audited and
    then answered with a redirect to a GET page, so Reload or Back-Forward on
    a shared ward PC cannot re-send another person's token;
  * send the token anywhere but the bridge: no proxy, no redirect followed;
  * open for anyone: the door is off until PSA_EMPLOYEE_PORTAL_ORIGINS names
    the https origins the form may come from, and nobody passes until their
    department has a board (Setup › Departments; PSA_EMPLOYEE_PORTAL_DEPARTMENTS
    only while that table is empty);
  * outlive the browser, or a shift: the cookie has no Max-Age and the session
    is good for two hours, not the desk's twelve;
  * sign in an admin preview, a record with no Windows username, one not
    shaped like a username, or a Windows account the AD import says is
    disabled.

Every outcome is audited: PORTAL_SSO, or PORTAL_SSO_REFUSED with the reason in
words. Standard library only.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from .. import db
from . import auth

ADLOGIN = re.compile(r"^[a-z0-9._-]{1,20}$")
# The bridge's own token shape (MEASURED in the portal-link handoff): 48 hex.
TOKEN = re.compile(r"^[0-9a-f]{48}$")
TIMEOUT = 5          # seconds; the bridge is on the same host
ME = "/api/portal/me"
MAX_ANSWER = 64 * 1024
SESSION_SECONDS = 2 * 60 * 60


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A redirect would carry the token to wherever it points. Refused.
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def bridge_get(url: str, headers: dict, timeout: float = TIMEOUT) -> tuple[int, dict | None]:
    """One GET to the bridge, straight (no proxy from the environment or the
    account's registry, no redirect followed, at most 64 KB read). Returns
    (status, JSON object or None). Raises on no answer at all (unreachable,
    slow), which the door reports as 'could not be checked'; anything the
    bridge did answer is a status."""
    req = urllib.request.Request(url, headers={**headers, "Accept": "application/json"})
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            raw = r.read(MAX_ANSWER + 1)
            status = r.status
    except urllib.error.HTTPError as exc:
        return exc.code, None
    if len(raw) > MAX_ANSWER:
        return status, None
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return status, None
    return status, body if isinstance(body, dict) else None


class Refused(Exception):
    def __init__(self, code: str, reason: str, *, who: str = "?", subject: str | None = None):
        super().__init__(reason)
        self.code, self.reason, self.who, self.subject = code, reason, who, subject


# The words the employee reads, by a fixed code the redirect carries. Each ends
# with the way in that always works.
REFUSALS = {
    "ended": ("401 Unauthorized", "Your Employee Portal session has ended. Sign in there again, "
                                  "or sign in here with your Windows account."),
    "origin": ("403 Forbidden", "This form was posted from a site that is not the Employee Portal."),
    "preview": ("403 Forbidden", "An admin preview cannot open My requests."),
    "not_linked": ("403 Forbidden", "Your employee record is not linked to a Windows account yet. "
                                    "Sign in here with your Windows account, or ask PMO to link it."),
    "disabled": ("403 Forbidden", "Your Windows account is disabled, so My requests cannot open. "
                                  "Ask the service desk."),
    "closed": ("403 Forbidden", "My requests is not open for your department yet."),
    "unchecked": ("503 Service Unavailable", "The Employee Portal could not be checked just now. Go "
                                             "back to the Employee Portal and open My requests again, "
                                             "or sign in here with your Windows account."),
}


def refusal_page(request, config):
    """GET /sso/portal?refused=<code>: the page a refused POST redirects to.
    Fixed words from a fixed code; nothing from the POST reaches it."""
    from . import Response, templates
    code = request.query.get("refused", "")
    status, words = REFUSALS.get(code, REFUSALS["unchecked"])
    body = ("<h1>My requests</h1>"
            f"<div class='banner err'>{templates.esc(words)}</div>"
            "<p><a class='btn' href='/login?next=/my'>Sign in with your Windows account "
            "instead</a></p>")
    return Response(status, templates.page("My requests", body, requester=True))


def departments_open(conn, config) -> set[str] | None:
    """The departments the door lets in: Setup › Departments' ticked rows, or,
    only while that table is empty, PSA_EMPLOYEE_PORTAL_DEPARTMENTS. Returns
    None when the table decides (then `department_boards` is the check)."""
    from .. import departments
    if departments.any_configured(conn):
        return None
    return config.employee_portal_department_set


def portal_login(conn, request, config, now):
    """POST /sso/portal on the portal host: the form field `token`."""
    from . import Response, redirect, _session_cookie_value, _norm_netloc
    from .. import departments

    # Off, or the wrong address: not there. Says nothing about why.
    if not config.employee_portal_origin_set or not config.is_portal_host(request):
        return Response("404 Not Found", "<h1>404 Not Found</h1><p>No such page.</p>")
    if request.method == "GET":
        return refusal_page(request, config)
    if request.method != "POST":
        return Response("405 Method Not Allowed", "<h1>405</h1><p>POST only.</p>")

    stamp = now.isoformat(sep=" ", timespec="minutes")

    def refused(exc: Refused):
        # Audited, then post-redirect-get: the token POST never stays in the
        # tab's history as the page on screen.
        db.audit(conn, at=stamp, actor=exc.who, action="PORTAL_SSO_REFUSED",
                 subject_kind="employee", subject_id=exc.subject or (exc.who if exc.who != "?" else None),
                 detail=exc.reason)
        conn.commit()
        return redirect("/sso/portal?refused=" + exc.code)

    # Its own Origin rule, stricter than the desk's: exactly one of the listed
    # https origins. An http origin means the token already travelled in the
    # clear, and is refused for that reason.
    origin = request.headers.get("origin", "")
    o = urllib.parse.urlsplit(origin) if origin else None
    if (not o or o.scheme.lower() != "https"
            or "https://" + _norm_netloc("https", o.netloc) not in config.employee_portal_origin_set):
        return refused(Refused("origin", "origin not allowed"
                               + (" (not https)" if o and o.scheme.lower() == "http" else "")))

    token = request.form().get("token", "").strip()
    if not token:
        return refused(Refused("ended", "no token"))
    if not TOKEN.match(token):
        # Checked before the bridge sees it: a stray CR/LF or a paragraph is
        # not a portal token and is not a bridge outage either.
        return refused(Refused("ended", "token not shaped like a portal token"))

    try:
        status, body = config.bridge_get(config.employee_portal_bridge.rstrip("/") + ME,
                                         {"x-pmc-portal-token": token}, TIMEOUT)
    except Exception as exc:                                 # noqa: BLE001 — no answer
        return refused(Refused("unchecked", f"bridge not answering ({exc.__class__.__name__})"))
    if status in (401, 403):
        return refused(Refused("ended", f"bridge answered {status}"))
    if status != 200 or not isinstance(body, dict):
        # A bridge fault is not the employee's session ending; sending them
        # back to sign in to the portal again cannot help.
        return refused(Refused("unchecked", f"bridge answered {status}"))
    # Read strictly: a bridge that stops sending a field must fail closed.
    if body.get("impersonated") is not False:
        return refused(Refused("preview", "admin preview" if body.get("impersonated")
                               else "bridge answer has no impersonated flag"))
    employee = body.get("employee") if isinstance(body.get("employee"), dict) else {}
    emp_key = str(employee.get("EmpKey") or "").strip()[:64] or None
    adlogin_raw = employee.get("ADLogin")
    department_raw = employee.get("Department")
    if not isinstance(adlogin_raw, str) or not adlogin_raw.strip():
        return refused(Refused("not_linked", "no ADLogin on the employee record", subject=emp_key))
    adlogin = adlogin_raw.strip().lower()
    if not ADLOGIN.match(adlogin):
        return refused(Refused("not_linked", "ADLogin is not shaped like a username", subject=emp_key))
    department = department_raw.strip() if isinstance(department_raw, str) else ""

    # The Windows door refuses a disabled account at LogonUser; the bridge
    # never re-checks AD for a live session, so this door reads what the AD
    # import knows. The exact account row, inactive or not, is looked at first.
    exact = conn.execute("SELECT contact_id, inactive FROM contact WHERE LOWER(sam_account) = ?"
                         " ORDER BY inactive LIMIT 1", (adlogin,)).fetchone()
    if exact is not None and exact["inactive"]:
        return refused(Refused("disabled", "AD account disabled", who=adlogin))

    opened = departments_open(conn, config)
    if opened is None:
        boards = departments.boards_for(conn, department)
        allowed = bool(boards)
    else:
        allowed = department in opened
    if not allowed:
        return refused(Refused("closed", f"department not open ({department or 'none on the record'})",
                               who=adlogin))

    contact = auth.contact_for_account(conn, adlogin)
    full_name = str(employee.get("FullName") or "").strip() if isinstance(employee.get("FullName"), str) else ""
    user = auth.User(id=adlogin,
                     name=full_name or (contact["display_name"] if contact else adlogin),
                     email=((contact["email"] or "").lower() or None) if contact else None,
                     via="portal", roles=auth.board_roles(conn, adlogin), department=department or None)
    db.audit(conn, at=stamp, actor=adlogin, action="PORTAL_SSO", subject_kind="employee",
             subject_id=adlogin, detail="employee portal"
             + (f", contact {contact['contact_id']}" if contact else ", no contact row")
             + (f", department {department}" if department else ""))
    conn.commit()

    # Always /my: the portal never sends `next`, and a `next` is one more thing
    # a request could carry into a header. Secure by rule (the token only ever
    # travels over https), no Max-Age (the browser's own session), two hours.
    session = auth.open_session(user, config.session_secret, lifetime=SESSION_SECONDS)
    return redirect("/my", set_cookie=_session_cookie_value(session, secure=True, persistent=False))
