# The test runner for platform/imaging: Python only. DICOM through pynetdicom,
# pixels through pydicom and libjpeg, REST and DICOMweb through requests.
FROM python:3.14-slim-trixie@sha256:caaf356f40667c496d405780745b9ac25771c189a51dfcc42430d531ea09f8a2

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

# mssql-python (the stand-in BizBox) loads Microsoft's ODBC driver, which needs
# three system libraries, pinned as orders/Dockerfile pins them. apt as there:
# over http, or through a TLS-inspecting proxy trusting its CA for this step.
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

WORKDIR /tests
COPY requirements.txt .

# Every package is pinned by hash. A build host behind a TLS-inspecting proxy
# passes its CA as the build secret "build-ca" (ci/run.sh does, when one is
# set); it is used for this step only and never stored in the image.
RUN --mount=type=secret,id=build-ca \
    if [ -s /run/secrets/build-ca ]; then export PIP_CERT=/run/secrets/build-ca; fi; \
    pip install --no-cache-dir --require-hashes -r requirements.txt

COPY *.py pytest.ini ./

ENTRYPOINT ["pytest"]
