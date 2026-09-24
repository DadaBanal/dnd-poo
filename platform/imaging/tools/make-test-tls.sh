#!/usr/bin/env bash
# A throwaway certificate authority and a certificate for $PMC_HOSTNAME, for
# the off-prem build and its tests only. On a real site the certificate is the
# site's own (for PMC, the existing *.pmcne.ph wildcard), placed by hand in
# $PMC_SECRETS/tls/ as tls.crt and tls.key. This script never replaces an
# existing certificate.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dir="${PMC_SECRETS:-$here/secrets}/tls"
host="${PMC_HOSTNAME:?set PMC_HOSTNAME}"

if [[ -e "$dir/tls.crt" ]]; then
  echo "kept      tls.crt (not replaced)"
  exit 0
fi
mkdir -p "$dir"
chmod 700 "$dir"
cd "$dir"

openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -days 30 \
  -subj "/CN=PMC imaging test CA (throwaway)" \
  -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign" \
  -keyout ca.key -out ca.crt 2>/dev/null
openssl req -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes \
  -subj "/CN=$host" -keyout tls.key -out tls.csr 2>/dev/null
openssl x509 -req -in tls.csr -CA ca.crt -CAkey ca.key -CAcreateserial -days 30 \
  -extfile <(printf 'subjectAltName=DNS:%s\nextendedKeyUsage=serverAuth\n' "$host") \
  -out tls.crt 2>/dev/null
# Backups (M3): the R740xd's Kopia server, which the primary pins by the
# SHA-256 fingerprint of its certificate, and the Azure stand-in, addressed by
# its account's host name as Azure is.
issue() {  # issue <name> <dns names...>
  local name="$1"; shift
  local san; san="$(printf 'DNS:%s,' "$@")"
  openssl req -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes \
    -subj "/CN=$1" -keyout "$name.key" -out "$name.csr" 2>/dev/null
  openssl x509 -req -in "$name.csr" -CA ca.crt -CAkey ca.key -CAcreateserial -days 30 \
    -extfile <(printf 'subjectAltName=%s\nextendedKeyUsage=serverAuth\n' "${san%,}") \
    -out "$name.crt" 2>/dev/null
  rm -f "$name.csr"
  # Read by containers that run as other users; the 0700 folder guards them.
  chmod 644 "$name.crt" "$name.key"
}
issue kopia-server kopia-server
issue azurite azurite pmcoffsite.azurite
openssl x509 -in kopia-server.crt -noout -fingerprint -sha256 | cut -d= -f2 | tr -d : | tr 'A-F' 'a-f' > kopia-server.fp
rm -f tls.csr ca.srl ca.key
chmod 644 ca.crt tls.crt kopia-server.fp
chmod 600 tls.key
echo "generated test certificates for $host, the Kopia server and the Azure stand-in (30 days, throwaway CA)"
