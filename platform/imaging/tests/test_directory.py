"""Sign-in against PMC's Active Directory (here, its stand-in): AD decides.

The people and groups are invented (identity/test/ad/provision.sh). These
tests change the directory the way ICT's tools would, over LDAPS as its
administrator, and watch the platform follow: a role through a nested group,
a disabled account, someone guessing a password, and a leaver.
"""

from __future__ import annotations

import os
import ssl
import time
from pathlib import Path

import requests
from ldap3 import MODIFY_ADD, MODIFY_DELETE, Connection, Server, Tls

from frontdoor import BASE, CA, COOKIE, DICOMWEB_JSON, PASSWORD_FILE, SIGN_IN_PAGE, attempt, sign_in

AD_URL = os.environ.get("AD_URL", "ldaps://dc1.pmc.test:636")
AD_BASE = os.environ.get("AD_BASE", "DC=pmc,DC=test")
RADIOLOGISTS = f"CN=PMC Imaging Radiologists,OU=PMC Imaging,{AD_BASE}"


def server() -> Server:
    # LDAPS, with the domain controller's certificate checked against the CA.
    return Server(AD_URL, use_ssl=True, tls=Tls(ca_certs_file=CA, validate=ssl.CERT_REQUIRED))


def directory() -> Connection:
    """The stand-in AD, as its administrator."""
    password = Path(os.environ["AD_ADMIN_PASSWORD_SECRET"]).read_text().strip()
    return Connection(server(), user=f"CN=Administrator,CN=Users,{AD_BASE}", password=password,
                      auto_bind=True, raise_exceptions=True)


def account(ad: Connection, username: str):
    ad.search(AD_BASE, f"(sAMAccountName={username})", attributes=["badPwdCount", "lockoutTime"])
    assert len(ad.entries) == 1, username
    return ad.entries[0]


def me(session: requests.Session) -> dict:
    return session.get(f"{BASE}/pmc/api/me", timeout=30).json()


def test_a_role_can_come_through_a_nested_group():
    # card.test is in "Cathlab Team", which is itself in the cardiologists' group.
    assert me(sign_in("cardiologist"))["roles"] == ["pmc-cardiologist"]


def test_a_disabled_account_cannot_sign_in():
    s, r = attempt("disabled")
    assert not s.cookies.get(COOKIE)
    assert SIGN_IN_PAGE in r.url
    assert "disabled" in r.text.lower()


def test_guessing_at_the_sign_in_cannot_lock_the_windows_account():
    # Five wrong passwords, a little apart, as a person (or a script) would try.
    for _ in range(5):
        s, _r = attempt("lockout", password="not-the-password")
        assert not s.cookies.get(COOKIE)
        time.sleep(1.2)
    # Keycloak has stopped asking AD: even the right password is refused now.
    s, _r = attempt("lockout")
    assert not s.cookies.get(COOKIE)
    # AD counted no more than the five, well short of its own lockout (10 in
    # the stand-in), so the Windows account is not locked...
    entry = account(directory(), "lock.test")
    assert int(entry.badPwdCount.value or 0) <= 5
    assert not entry.lockoutTime.value or entry.lockoutTime.value.year == 1601
    # ...and it still works for everything else.
    Connection(server(), user=entry.entry_dn, password=Path(PASSWORD_FILE).read_text().strip(),
               auto_bind=True, raise_exceptions=True).unbind()


def test_a_leaver_loses_access_within_one_token_renewal(measurements):
    ad = directory()
    leaver = account(ad, "gone.test").entry_dn
    s = sign_in("leaver", "/viewer")

    def search() -> int:
        return s.get(f"{BASE}/dicom-web/studies?limit=1", headers=DICOMWEB_JSON, timeout=30).status_code

    assert search() == 200
    ad.modify(RADIOLOGISTS, {"member": [(MODIFY_DELETE, [leaver])]})
    removed = time.monotonic()
    try:
        # The session carries on until its token is next renewed (40 s here,
        # 4 min on site); the renewed token asks AD again.
        while search() == 200:
            assert time.monotonic() - removed < 150, "still admitted 150 s after leaving the group"
            time.sleep(2)
        measurements["access_ended_after_leaving_the_group_s"] = round(time.monotonic() - removed)
    finally:
        ad.modify(RADIOLOGISTS, {"member": [(MODIFY_ADD, [leaver])]})
