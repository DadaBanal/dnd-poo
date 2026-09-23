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
rm -f tls.csr ca.srl ca.key
chmod 644 ca.crt tls.crt
chmod 600 tls.key
echo "generated a test certificate for $host (30 days, throwaway CA)"
