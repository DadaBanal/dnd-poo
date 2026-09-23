# The browser tests: Playwright's own image (Chromium and its system libraries
# included), pinned by digest, with the test runner installed from the
# lockfile (every package pinned by integrity hash).
FROM mcr.microsoft.com/playwright:v1.63.0-noble@sha256:eff16c30e6f3f4af0a03fa4b706120d5e9b0891c344a27d64559aff5900a4a27

WORKDIR /browser
COPY package.json package-lock.json ./

# A build host behind a TLS-inspecting proxy passes its CA as the build secret
# "build-ca" (ci/run.sh does, when one is set); used for this step only.
RUN --mount=type=secret,id=build-ca \
    if [ -s /run/secrets/build-ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build-ca; fi; \
    npm ci --ignore-scripts --no-audit --no-fund

COPY playwright.config.js ./
COPY tests ./tests

ENTRYPOINT ["npx", "playwright", "test"]
