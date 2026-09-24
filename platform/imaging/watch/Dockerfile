# The feed watch (Path A, M3.3): Node 24 and one file of JavaScript, no
# packages. It reads the engine, the domain controllers, the images'
# filesystem and the backups, and serves what it finds as metrics.
ARG PMC_LIBRARY=docker.io/library
FROM ${PMC_LIBRARY}/node:24.21.0-trixie-slim@sha256:8ec5d7557396cfe32d21c3f9c13072355ceab22b584578ca4bb28af31120cffe
WORKDIR /watch
COPY src ./src
# Its place in the engine's change feed survives a restart (a volume here).
RUN mkdir /state && chown node:node /state
USER node
EXPOSE 9100
CMD ["node", "src/main.mjs"]
