# The browser tests: Playwright's own image (Chromium and its system libraries
# included), pinned by digest, with the test runner installed from the
# lockfile (every package pinned by integrity hash).
FROM mcr.microsoft.com/playwright:v1.63.0-noble@sha256:eff16c30e6f3f4af0a03fa4b706120d5e9b0891c344a27d64559aff5900a4a27

# certutil (libnss3-tools) puts the test CA in Chromium's certificate store
# before the tests run (tests/trust-ca.js), so the browser verifies the front
# door's certificate as a ward PC verifies PMC's, and caches what the front
# door lets it keep. Pinned; apt as in tests/Dockerfile (Ubuntu noble here).
RUN --mount=type=secret,id=build-ca,mode=0444 \
    set -eu; \
    opts=""; \
    if [ -s /run/secrets/build-ca ]; then \
      sed -i 's|http://|https://|g' /etc/apt/sources.list.d/*; \
      opts="-o Acquire::https::CaInfo=/run/secrets/build-ca"; \
      export https_proxy="${HTTPS_PROXY:-}"; \
    fi; \
    apt-get $opts update; \
    apt-get $opts install -y --no-install-recommends libnss3-tools=2:3.98-1ubuntu0.2; \
    sed -i 's|https://|http://|g' /etc/apt/sources.list.d/*; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /browser
COPY package.json package-lock.json ./

# A build host behind a TLS-inspecting proxy passes its CA as the build secret
# "build-ca" (ci/run.sh does, when one is set); used for this step only.
RUN --mount=type=secret,id=build-ca \
    if [ -s /run/secrets/build-ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build-ca; fi; \
    npm ci --ignore-scripts --no-audit --no-fund

COPY playwright.config.js ./
COPY tests ./tests
COPY measure ./measure

ENTRYPOINT ["npx", "playwright", "test"]
