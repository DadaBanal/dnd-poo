"""Would this person's email link open this request? Asked on the host, of the
portal itself, with no mailbox and no browser (076).

SQL01, 8 Oct 2026: the only way to prove a "See your request" link was to click
it in somebody's mailbox, which nobody on the host can do. This puts the
question to the same code a browser reaches: it signs the person in the way the
portal's doors would (a Windows name, or an address as Entra gives it), asks the
portal's own router for the request's pages on the portal's address, and reads
the answers. Everything it touches on the way is rolled back: the key a first
email would make is never kept. A read by key is not written to the audit trail
at all, because it is the check and not a person, and on SQL Server even a
rolled-back insert would use up a number in the trail's sequence. The session it
uses is signed with a throwaway secret and never leaves the process.

What it reports is MEASURED from the code that serves the page, on this store.
It does not prove the network path from a ward PC (DNS, the proxy, TLS); a
browser on the hospital network proves that, and 401 from the address proves
the desk is answering.
"""
from __future__ import annotations

import http.cookies
import secrets
from datetime import datetime


class _NoCommit:
    """The connection, except that nothing it is asked to commit is kept."""

    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def commit(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def mask(link: str | None) -> str:
    """A link as it may be printed or pasted into a handoff: the key cut to its
    first four characters. A whole key opens the request to anyone signed in."""
    if not link:
        return ""
    head, sep, key = link.partition("?k=")
    return head + (sep + key[:4] + "..." if sep and key else sep)


def person_user(conn, person: str):
    """The person as the portal's doors would sign them in: a Windows name as
    the Windows door does (their contact's address, if the desk has one), an
    address as Entra gives it."""
    from .web import auth
    who = (person or "").strip()
    if "\\" in who:
        who = who.split("\\", 1)[1]
    if "@" in who:
        return auth.User(id=who.lower(), name=who, email=who.lower(), via="entra"), "an address (as Entra signs them in)"
    name = who.lower()
    contact = auth.contact_for_account(conn, name)
    email = ((contact["email"] or "").lower() or None) if contact else None
    return (auth.User(id=name, name=contact["display_name"] if contact else name, email=email, via="windows"),
            "their Windows name" + (f" (their contact's address: {email})" if email else " (no contact row with an address)"))


def _ask(conn, config, user, path: str, query: str, now: datetime):
    """One GET to the portal's address as this person: (status, body)."""
    from . import db
    from .web import HttpError, Request, SESSION_COOKIE, _route, auth
    from urllib.parse import parse_qsl, urlsplit
    cookies = http.cookies.SimpleCookie()
    cookies[SESSION_COOKIE] = auth.open_session(user, config.session_secret)
    host = urlsplit(config.portal_url).netloc
    request = Request(method="GET", path=path, query=dict(parse_qsl(query)), headers={"host": host},
                      cookies=cookies, body=b"", scheme="https", query_string=query)
    try:
        response = _route(conn, request, config, now)
        return response.status, response.body if isinstance(response.body, str) else ""
    except HttpError as exc:
        return exc.status, exc.message
    finally:
        db.set_source(None)


def check(conn, ticket: str, *, person: str | None = None, portal_url: str,
          now: datetime | None = None) -> list[str]:
    """The report, line by line. Writes nothing: every change is rolled back."""
    from .web import Config
    from .web.views import portal
    from . import tickets
    now = now or datetime.now()
    out: list[str] = []
    row = conn.execute("SELECT t.requested_by, t.intake_source, t.board_id, t.portal_key, w.name"
                       "  FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
                       " WHERE t.work_item_id = ?", (ticket,)).fetchone()
    if row is None:
        return [f"there is no ticket {ticket}"]
    raised = (row["requested_by"] or "").strip()
    out.append(f"{ticket} on {row['board_id']} was raised by: {raised or '(nobody: it has no requester)'}"
               f"  (came in by {row['intake_source'] or 'the desk'})")
    had_key = bool(row["portal_key"])
    proxy = _NoCommit(conn)
    from . import db as _db
    real_audit, _db.audit = _db.audit, (lambda *a, **k: None)
    try:
        key = tickets.portal_key(proxy, ticket)
        base = portal_url.rstrip("/")
        link = f"{base}/my/{ticket}?k={key}"
        out.append("its email link: " + mask(link) + ("" if had_key else
                   "   (no key yet: none of its emails was sent with one. The next requester email about it"
                   " makes this key; the one shown here is only for this check and is not kept.)"))
        _emails(conn, ticket, key, out)
        config = Config(portal_url=base)          # its own session secret, made fresh, never kept
        if not config.is_portal_host(_host_request(base)):
            out.append(f"refused: {base} is not an address the portal answers on")
            return out
        who = person or raised
        if not who:
            out.append("A ticket with no requester is on nobody's portal. Set the Contact on the ticket.")
            return out
        user, door = person_user(proxy, who)
        out.append(f"as {who}, signed in by {door}:")
        from .web import Ctx, Request
        ids = portal._identities(Ctx(conn=proxy, request=_host_request(base), user=user, config=config, now=now))
        out.append("  the portal knows them as: " + ", ".join(ids))
        plain, _ = _ask(proxy, config, user, f"/my/{ticket}", "", now)
        keyed, _ = _ask(proxy, config, user, f"/my/{ticket}", f"k={key}", now)
        wrong, _ = _ask(proxy, config, user, f"/my/{ticket}", "k=" + secrets.token_urlsafe(18), now)
        listed_status, listing = _ask(proxy, config, user, "/my", "", now)
        listed = listed_status.startswith("200") and f"/my/{ticket}" in listing
        out.append(f"  {base}/my/{ticket}  (the link in an email sent before 075, or typed) -> {plain}"
                   + ("  theirs by address" if plain.startswith("200") else "  not theirs by any address the desk holds"))
        out.append(f"  {mask(link)}  (the email link) -> {keyed}"
                   + ("  opens by the link" if keyed.startswith("200") else "  DOES NOT OPEN"))
        out.append(f"  the same with a wrong key -> {wrong}" + ("  (as it must)" if wrong.startswith("404") else
                                                                 ("  (theirs by address anyway)" if plain.startswith("200")
                                                                  else "  WRONG: a wrong key must not open it")))
        out.append(f"  Your requests ({base}/my) -> {listed_status}, "
                   + ("lists it" if listed else "does not list it"))
        if keyed.startswith("200") and not plain.startswith("200"):
            out.append("-> the email link opens it for them. A link without the key (every email sent before 075)"
                       " does not: send them the link from the ticket's Copy the requester's link, or let them"
                       " press Send me a fresh link on the page that says No such request.")
        elif plain.startswith("200"):
            out.append("-> they see it, with or without the key.")
        else:
            out.append("-> it does not open for them by any link. Hand back with this output.")
    finally:
        _db.audit = real_audit
        conn.rollback()
    out.append("Nothing was written: every change this check made was rolled back.")
    return out


def _host_request(base: str):
    from .web import Request
    from urllib.parse import urlsplit
    return Request(method="GET", path="/", query={}, headers={"host": urlsplit(base).netloc},
                   cookies=http.cookies.SimpleCookie(), body=b"", scheme="https")


def _emails(conn, ticket: str, key: str, out: list[str]) -> None:
    """What the requester was sent about it, and the link each email carried
    where the sender kept it (076)."""
    from . import db, outbox
    rows = conn.execute("SELECT * FROM notification WHERE work_item_id = ? AND recipient_role IN (?, ?)"
                        " ORDER BY notification_id", (ticket, outbox.REQUESTER, outbox.STATUS)).fetchall()
    if not rows:
        out.append("requester emails about it: none")
        return
    kept = db.column_exists(conn, "notification", "portal_link")
    sent = [r for r in rows if r["status"] == "SENT"]
    out.append(f"requester emails about it: {len(rows)} ({len(sent)} sent; the last queued {rows[-1]['created_at']})")
    if not kept:
        out.append("  the link each email carried is not kept on this store yet (076 is not applied)")
        return
    for r in rows[-5:]:
        carried = r["portal_link"]
        if carried:
            ok = carried.endswith("?k=" + key)
            said = mask(carried) + ("  (this ticket's key)" if ok else "  (NOT this ticket's key)")
        else:
            said = "not kept (sent before 076, or without a portal address)"
        out.append(f"  #{r['notification_id']} {r['status']} {r['created_at']}: {said}")
