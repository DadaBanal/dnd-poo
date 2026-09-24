# The BizBox connector (Path A, M3.2): Python 3.14, and its packages pinned by
# hash. mssql-python loads Microsoft's ODBC driver (mssql-python-odbc), which
# needs three system libraries (its README).
FROM python:3.14-slim-trixie@sha256:caaf356f40667c496d405780745b9ac25771c189a51dfcc42430d531ea09f8a2

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

# As backup/postgres: apt over http, checked against Debian's signing keys;
# behind a TLS-inspecting proxy, over https trusting its CA for this step only.
RUN --mount=type=secret,id=build-ca,mode=0444 \
    set -eu; \
    opts=""; \
    if [ -s /run/secrets/build-ca ]; then \
      sed -i 's|http://|https://|g' /etc/apt/sources.list.d/*; \
      opts="-o Acquire::https::CaInfo=/run/secrets/build-ca"; \
      export https_proxy="${HTTPS_PROXY:-}"; \
    fi; \
    apt-get $opts update; \
    apt-get $opts install -y --no-install-recommends \
      libltdl7=2.5.4-4 libkrb5-3=1.21.3-5+deb13u1 libgssapi-krb5-2=1.21.3-5+deb13u1; \
    sed -i 's|https://|http://|g' /etc/apt/sources.list.d/*; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /orders
COPY requirements.txt .
RUN --mount=type=secret,id=build-ca \
    if [ -s /run/secrets/build-ca ]; then export PIP_CERT=/run/secrets/build-ca; fi; \
    pip install --no-cache-dir --require-hashes -r requirements.txt

COPY pmcorders ./pmcorders
USER 10001:10001
EXPOSE 8080
CMD ["python", "-m", "pmcorders"]
