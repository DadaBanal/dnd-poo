# PostgreSQL 18.6 (the official image, pinned by digest) with pgBackRest 2.59.1
# from the PostgreSQL project's own apt repository, pinned to the exact
# package. Both database clusters run this image, so each can archive its
# write-ahead log continuously and be restored to any second (Path A, M3).
ARG PMC_LIBRARY=docker.io/library
FROM ${PMC_LIBRARY}/postgres:18.6-trixie@sha256:86c951e05bf56c93d95d397747fb8820ac76cc3bedb78f43abd83eedbe3666ae

# Packages come from apt over http and are checked against the repositories'
# signing keys, as Debian does by default. A build host behind a
# TLS-inspecting proxy passes its CA as the build secret "build-ca" (ci/run.sh
# does, when one is set): then apt goes over https through the proxy, trusting
# that CA for this step only. apt fetches as its own unprivileged user, so the
# secret is mounted readable.
RUN --mount=type=secret,id=build-ca,mode=0444 \
    set -eu; \
    opts=""; \
    if [ -s /run/secrets/build-ca ]; then \
      sed -i 's|http://|https://|g' /etc/apt/sources.list.d/*; \
      opts="-o Acquire::https::CaInfo=/run/secrets/build-ca"; \
      export https_proxy="${HTTPS_PROXY:-}"; \
    fi; \
    apt-get $opts update; \
    apt-get $opts install -y --no-install-recommends pgbackrest=2.59.1-1.pgdg13+1; \
    sed -i 's|https://|http://|g' /etc/apt/sources.list.d/*; \
    rm -rf /var/lib/apt/lists/*; \
    mkdir -p /var/lib/pgbackrest /var/log/pgbackrest /var/spool/pgbackrest /etc/pgbackrest; \
    chown -R postgres:postgres /var/lib/pgbackrest /var/log/pgbackrest /var/spool/pgbackrest /etc/pgbackrest; \
    pgbackrest version
