"""The front door, as a person reaches it: sign in with a Windows logon from the
stand-in Active Directory.

The tests container is on the (sealed) edge network too, so it can do what a
browser does, and also look behind the front door at what the engine and the
front door app are handed.
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
from pathlib import Path

import requests

HOST = os.environ.get("PMC_HOSTNAME", "imaging.pmcne.test")
BASE = f"https://{HOST}"
CA = os.environ.get("TEST_CA_SECRET", "/run/secrets/test-ca")
PASSWORD_FILE = os.environ.get("TEST_USER_PASSWORD_SECRET", "/run/secrets/test-user-password")
COOKIE = "__Host-pmc-session"
# oauth2-proxy, asked directly on the engine network the way the front door
# asks it: this is where the front door gets the token it passes on.
SESSION_CHECK = "http://oauth2-proxy:4180/oauth2/auth"
DICOMWEB_JSON = {"Accept": "application/dicom+json"}

# The stand-in Active Directory's invented people, by Windows logon name
# (identity/test/ad/provision.sh).
PEOPLE = {
    "radiologist": "rad.test",
    "cardiologist": "card.test",
    "referrer": "ref.test",
    "ict": "ict.test",
    "nogroup": "none.test",
    "disabled": "off.test",
    "leaver": "gone.test",
    "lockout": "lock.test",
}
SIGN_IN_PAGE = "/auth/realms/pmc/"

# A browser loading a page says so; only a page load may start a sign-in.
PAGE_LOAD = {"Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"}


def attempt(who: str, path: str = "/pmc/", password: str | None = None) -> tuple[requests.Session, requests.Response]:
    """Ask for a page, and answer PMC's sign-in page as one of PEOPLE: their
    Windows logon name and a password (theirs, unless another is given)."""
    s = requests.Session()
    s.verify = CA
    r = s.get(BASE + path, headers=PAGE_LOAD, timeout=60)
    r.raise_for_status()
    assert SIGN_IN_PAGE in r.url, r.url
    form = re.search(r'<form\b[^>]*\bid="kc-form-login"[^>]*>', r.text)
    assert form, "no sign-in form"
    action = html.unescape(re.search(r'\baction="([^"]+)"', form.group(0)).group(1))
    if password is None:
        password = Path(PASSWORD_FILE).read_text().strip()
    r = s.post(action, data={"username": PEOPLE[who], "password": password, "credentialId": ""},
               headers=PAGE_LOAD, timeout=60)
    return s, r


def sign_in(who: str, path: str = "/pmc/") -> requests.Session:
    """Sign in at the front door as one of PEOPLE, with their Windows logon."""
    s, r = attempt(who, path)
    r.raise_for_status()
    assert r.url == BASE + path, r.url
    assert s.cookies.get(COOKIE), "no session cookie after signing in"
    return s


def token_of(session: requests.Session) -> str:
    """The access token the front door would hand the engine right now."""
    r = requests.get(SESSION_CHECK, timeout=30,
                     cookies={COOKIE: session.cookies.get(COOKIE)},
                     headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": HOST})
    assert r.status_code == 202, r.status_code
    return r.headers["X-Auth-Request-Access-Token"]


def claims(token: str) -> dict:
    """A JWT's claims, unverified: the other side does the verifying."""
    body = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
