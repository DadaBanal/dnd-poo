#!/bin/bash
# Tests only: the stand-in for PMC's Active Directory. Its first start makes
# the domain PMC.TEST with invented people and groups; every start then runs
# the domain controller, answering LDAPS as dc1.pmc.test. Nothing here is
# PMC's: the names are invented and the passwords are the test run's
# throwaway secrets.
#
#   OU=PMC Imaging   the five groups, one per role, as ICT will make them
#   CN=Users         the people; the sign-in's read-only bind account; and
#                    "Cathlab Team", a group inside the cardiologists' group,
#                    so a role can come through a nested group
#
# The people: rad.test (radiologist), card.test (cardiologist, through
# Cathlab Team), ref.test (referrer), ict.test (ICT), none.test (in no
# group), off.test (a radiologist whose account is disabled), gone.test (a
# radiologist the tests remove from the group) and lock.test (a radiologist
# the tests try to lock out).
set -euo pipefail

state=/var/lib/samba
secret() { tr -d '\n' < "/run/secrets/$1"; }

# Samba refuses a TLS key that others can read, and the secret is mounted
# world-readable (tools/make-secrets.sh explains why): keep a private copy.
mkdir -p "$state/private/pmc-tls"
install -m 600 /run/secrets/ad-tls-key "$state/private/pmc-tls/key.pem"
install -m 644 /run/secrets/ad-tls-cert "$state/private/pmc-tls/cert.pem"
install -m 644 /run/secrets/test-ca "$state/private/pmc-tls/ca.pem"

if [[ ! -e "$state/private/sam.ldb" ]]; then
  # user.NTACL instead of security.NTACL: the container needs no extra
  # privilege to store Windows ACLs (Samba 4.18 and later). No DNS service:
  # Docker's own resolves dc1.pmc.test. IPv4 only, as the test networks are.
  samba-tool domain provision --realm=PMC.TEST --domain=PMC --server-role=dc \
    --host-name=dc1 --dns-backend=NONE --use-rfc2307 \
    --adminpass="$(secret ad-admin-password)" \
    --option="server services = -dns -dnsupdate" \
    --option="interfaces = lo eth0" --option="bind interfaces only = yes" \
    --option="acl_xattr:security_acl_name = user.NTACL" \
    --option="tls enabled = yes" \
    --option="tls keyfile = $state/private/pmc-tls/key.pem" \
    --option="tls certfile = $state/private/pmc-tls/cert.pem" \
    --option="tls cafile = $state/private/pmc-tls/ca.pem" \
    >/tmp/provision.log 2>&1 || { cat /tmp/provision.log; exit 1; }
  # The configuration lives with the domain, so a new container finds both.
  cp /etc/samba/smb.conf "$state/smb.conf"

  # Test passwords are random rather than "complex", and never expire. AD's
  # own lockout stays on, at 10 bad passwords, as a real domain's would.
  samba-tool domain passwordsettings set --complexity=off --min-pwd-length=8 \
    --max-pwd-age=0 --account-lockout-threshold=10 \
    --account-lockout-duration=30 --reset-account-lockout-after=30 >/dev/null

  password="$(secret test-user-password)"
  person() {  # username, given name, surname
    samba-tool user create "$1" "$password" --given-name="$2" --surname="$3" \
      --mail-address="$1@pmc.test" >/dev/null
  }
  person rad.test Test Radiologist
  person card.test Test Cardiologist
  person ref.test Test Referrer
  person ict.test Test ICT
  person none.test Test Nogroup
  person off.test Test Disabled
  person gone.test Test Leaver
  person lock.test Test Lockout
  samba-tool user disable off.test >/dev/null
  samba-tool user create svc-pmc-imaging "$(secret ad-bind-password)" \
    --description="PMC imaging sign-in: reads the directory, never writes" >/dev/null

  samba-tool ou add "OU=PMC Imaging" >/dev/null
  for role in Radiologists Cardiologists Technologists Referrers "ICT Admins"; do
    samba-tool group add "PMC Imaging $role" --groupou="OU=PMC Imaging" >/dev/null
  done
  samba-tool group add "Cathlab Team" >/dev/null
  samba-tool group addmembers "PMC Imaging Radiologists" rad.test,off.test,gone.test,lock.test >/dev/null
  samba-tool group addmembers "Cathlab Team" card.test >/dev/null
  samba-tool group addmembers "PMC Imaging Cardiologists" "Cathlab Team" >/dev/null
  samba-tool group addmembers "PMC Imaging Referrers" ref.test >/dev/null
  samba-tool group addmembers "PMC Imaging ICT Admins" ict.test >/dev/null
  echo "stand-in AD: domain PMC.TEST provisioned with its invented people and groups"
fi

cp "$state/smb.conf" /etc/samba/smb.conf
exec samba --foreground --no-process-group --debug-stdout --debuglevel=1
