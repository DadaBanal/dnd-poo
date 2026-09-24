"""PMC's identity at the front door (README.md, Branding): the logo files the
sign-in page, the app, the viewer and the signed-out page show, and the
sign-in page itself. What they look like is checked in the browser
(browser/tests/access.spec.js, home.spec.js, viewer.spec.js).
"""

from __future__ import annotations

import html
import re

import requests

from frontdoor import BASE, CA, PAGE_LOAD, SIGN_IN_PAGE

BRAND = ("pmc-lockup-white.png", "pmc-mark-white.png", "pmc-mark.png")


def test_the_logo_files_need_no_session_and_nothing_else_is_served_there():
    for name in BRAND:
        r = requests.get(f"{BASE}/brand/{name}", verify=CA, allow_redirects=False, timeout=30)
        assert r.status_code == 200, name
        assert r.headers["Content-Type"] == "image/png"
        assert r.content.startswith(b"\x89PNG\r\n\x1a\n")
        # Logos may be kept a day; images of patients never are (test_dicomweb).
        assert r.headers["Cache-Control"] == "public, max-age=86400"
        assert r.headers["X-Content-Type-Options"] == "nosniff"
    # Nothing but the logos: anything else there needs a session like the rest.
    r = requests.get(f"{BASE}/brand/README.md", verify=CA, allow_redirects=False, headers=PAGE_LOAD, timeout=30)
    assert r.status_code == 302
    # And they can only be read.
    r = requests.post(f"{BASE}/brand/pmc-mark.png", verify=CA, allow_redirects=False, timeout=30)
    assert r.status_code == 403


def test_the_sign_in_page_is_pmcs():
    r = requests.get(f"{BASE}/pmc/", verify=CA, headers=PAGE_LOAD, timeout=60)
    assert SIGN_IN_PAGE in r.url, r.url
    page = r.text
    # PMC's theme (identity/theme/pmc) on Keycloak's own page...
    assert re.search(r'href="/auth/resources/[^"]+/login/pmc/css/pmc\.css"', page)
    assert re.search(r'src="/auth/resources/[^"]+/login/pmc/js/pmc\.js"', page)
    assert re.search(r'rel="icon"[^>]*href="/auth/resources/[^"]+/login/pmc/img/pmc-mark\.png"', page)
    # ...the lock-up and the tagline in the brand panel (the realm's
    # displayNameHtml), and PMC's words.
    header = re.search(r'<header id="kc-header".*?</header>', page, re.S).group(0)
    assert 'src="/brand/pmc-lockup-white.png"' in header
    assert "Better Care. <i>For Every Life.</i>" in header
    title = re.search(r'<h1[^>]*id="kc-page-title"[^>]*>(.*?)</h1>', page, re.S).group(1)
    assert re.sub(r"<!--.*?-->|\s+", " ", title).strip() == "Sign in with your PMC Windows logon"
    assert "It is the username and password you use on PMC's computers." in html.unescape(page)
    # The Caps Lock note is there, empty, for js/pmc.js to fill.
    assert re.search(r'<p id="pmc-caps-lock" class="pmc-caps-lock" role="status" data-text="Caps Lock is on"></p>', page)
    # The form the tests (and people) use is still Keycloak's own.
    for field in ('id="kc-form-login"', 'id="username"', 'id="password"', 'id="kc-login"'):
        assert field in page, field
