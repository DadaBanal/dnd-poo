# The PMC front door app (Path A, M2.3): the page, built once here, and the
# small server that serves it and its API at /pmc/. Node 24 LTS, pinned by
# digest; every package pinned by integrity hash in package-lock.json.

# Where official images come from (compose's PMC_LIBRARY): the digest pins the
# content, so a mirror serves the identical image.
ARG PMC_LIBRARY=docker.io/library

# ---- build: type-check, then bundle the page -------------------------------------
FROM ${PMC_LIBRARY}/node:24.21.0-trixie-slim@sha256:8ec5d7557396cfe32d21c3f9c13072355ceab22b584578ca4bb28af31120cffe AS build
WORKDIR /app
COPY package.json package-lock.json ./
# A build host behind a TLS-inspecting proxy passes its CA as the build secret
# "build-ca" (ci/run.sh does, when one is set); used for this step only.
# No package runs an install script.
RUN --mount=type=secret,id=build-ca \
    if [ -s /run/secrets/build-ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build-ca; fi; \
    npm ci --ignore-scripts --no-audit --no-fund
COPY tsconfig.json vite.config.ts ./
COPY src ./src
# The clickable sample (dist-demo/) is built too, so it is proven to build;
# it is not part of the image that runs.
RUN npx tsc --noEmit && npx vite build && npx vite build --mode demo && npm prune --omit=dev --ignore-scripts

# ---- run: the server, its three runtime packages and the built page ---------------
FROM ${PMC_LIBRARY}/node:24.21.0-trixie-slim@sha256:8ec5d7557396cfe32d21c3f9c13072355ceab22b584578ca4bb28af31120cffe
ENV NODE_ENV=production
WORKDIR /app
COPY --from=build /app/package.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY src/server ./src/server
COPY src/shared ./src/shared
USER node
EXPOSE 8080
# Node 24 runs the server's TypeScript as it is, with the types stripped.
CMD ["node", "src/server/main.ts"]
