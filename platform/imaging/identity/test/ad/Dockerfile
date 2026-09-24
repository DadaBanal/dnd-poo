# Tests only: a stand-in for PMC's Active Directory. Samba's AD domain
# controller from Debian, pinned to the exact package, with invented people
# and groups (provision.sh). It answers LDAPS with a certificate from the
# tests' throwaway CA. Never deployed.
ARG PMC_LIBRARY=docker.io/library
FROM ${PMC_LIBRARY}/debian:trixie-slim@sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a

# As backup/postgres: apt over http, checked against Debian's signing keys;
# behind a TLS-inspecting proxy, over https trusting its CA for this step.
RUN --mount=type=secret,id=build-ca,mode=0444 \
    set -eu; \
    opts=""; \
    if [ -s /run/secrets/build-ca ]; then \
      sed -i 's|http://|https://|g' /etc/apt/sources.list.d/*; \
      opts="-o Acquire::https::CaInfo=/run/secrets/build-ca"; \
      export https_proxy="${HTTPS_PROXY:-}"; \
    fi; \
    apt-get $opts update; \
    DEBIAN_FRONTEND=noninteractive apt-get $opts install -y --no-install-recommends \
      samba-ad-dc=2:4.22.11+dfsg-0+deb13u1 samba-ad-provision=2:4.22.11+dfsg-0+deb13u1; \
    sed -i 's|https://|http://|g' /etc/apt/sources.list.d/*; \
    rm -rf /var/lib/apt/lists/* /etc/samba/smb.conf; \
    samba --version

COPY provision.sh /pmc/provision.sh
ENTRYPOINT ["/bin/bash", "/pmc/provision.sh"]
