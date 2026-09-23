# platform/imaging — the Path A platform

**Status, 23 Sep 2026: M1 (the engine) and M2.1 (the front door and the
viewer) are built and proven off-prem. Nothing is deployed.** Dada's rule
(23 Sep): nothing goes on-prem until the whole platform is built, and the
on-prem go is his. Deployment also stays gated on ADR-001 (still *Proposed*)
and on the safety work in [`../README.md`](../README.md), "What it is gated
on".

This replaces the 6 Sep skeleton in `platform/`, which was never run.

## What is built

```
                          edge network              engine network (no route out)
person ── HTTPS 443 ──▶  front (nginx) ──┬──▶ viewer (OHIF, static files)
                                         └──▶ orthanc ──▶ pg-index      the index
modality ── DICOM 4242 ────────────────────▶    │
                                                └──▶ orthanc-storage   the images
```

- **M1, the engine:** Orthanc and its PostgreSQL index, on a network with no
  route out.
- **M2.1, the front door and the viewer:** one origin over TLS and HTTP/2.
  `/viewer?StudyInstanceUIDs=…` is OHIF; `/dicom-web/` is the engine's DICOMweb,
  read-only and never cached. Nothing else of the engine is routed. OHIF's own
  study list stands in as the worklist until the PMC front door app (M2.3).

**Not built yet: sign-in (M2.2).** Until then the front door presents the one
engine account (`pmc-ops`) to the engine for every visitor. Anyone who reaches
port 443 can read images. That is fine for the off-prem build and must never be
deployed. M2.2 replaces it with Entra ID sign-in and per-role permissions.

No port is published to the host in the build. The tests run in containers:
one on the engine network plays the modalities, and one on the edge network is
a person at a PC, with Chromium, who can reach the front door and nothing else.
Nothing is mocked.

## Pinned

| Component | Version | Pinned by | Evidence |
|---|---|---|---|
| Engine: `orthancteam/orthanc:26.9.1` | Orthanc 1.13.0; DICOMweb 1.24; PostgreSQL index 11.0 (schema revision 11); Worklists 0.9.2; Housekeeper 1.13.0; GDCM plugin 1.8 (GDCM 3.0.24); DCMTK 3.7.0 | image digest | MEASURED from the running engine's `/system` and `/plugins`, 23 Sep 2026 |
| Index: `postgres:18.6-trixie` | 18.6. Data checksums on; built-in `C.UTF-8` collation, which no glibc update can reorder | image digest | MEASURED by `ci/run.sh` on every run |
| Viewer: `ohif/app:v3.13.10` | OHIF 3.13.10, served only through the front door | image digest | MEASURED: the option names in `viewer/app-config.js` were read from this image's bundle |
| Front door: `nginx:1.30.5` (trixie) | nginx 1.30.5, TLS 1.3, HTTP/2 | image digest | MEASURED by the browser tests |
| Test runner: `python:3.14-slim-trixie` | Python 3.14.7, pydicom 3.0.2, pynetdicom 3.0.4, pylibjpeg-libjpeg 2.4.0, pytest 9.1.1 | image digest, and a hash for every package | MEASURED |
| Browser runner: `mcr.microsoft.com/playwright:v1.63.0-noble` | Playwright 1.63.0, Chromium | image digest, and an integrity hash for every package | MEASURED |

The digests are in `compose.yaml`, `tests/Dockerfile` and `browser/Dockerfile`.
Each was pulled on 23 Sep 2026 (MEASURED). The official images (`postgres`,
`nginx`) gave the same digest from Docker Hub and from its public mirror, so
`PMC_LIBRARY` can point at a mirror without changing what runs.

## What the tests prove

`ci/run.sh` runs 39 tests. All passed on 23 Sep 2026 (MEASURED, cloud build,
3 min 25 s). It starts from empty volumes and runs 26 engine tests and 7 browser
tests. It then removes the containers, starts new ones from the same volumes,
and runs 5 engine tests and 1 browser test again.

| Property | Test |
|---|---|
| The engine is the configured one: versions, PostgreSQL index, no SQLite index file, exact plugin set, JPEG-LS ingest, never overwrite, never recycle | `test_engine.py`, `ci/run.sh` |
| Nothing on the engine network can reach the internet | `ci/run.sh` |
| A modality is admitted only if its AE title is registered, it calls this engine's AE title, and it connects from its registered address. A store-only modality cannot search. REST refuses a caller without credentials | `test_engine.py` |
| Every uncompressed arrival (XA cine, signed 16-bit CT, MR, CR, DR, RGB ultrasound) is stored as JPEG-LS and decodes identical to what was sent, every pixel of every frame | `test_ingest.py` |
| An arrival that is already lossy (JPEG ultrasound) is kept byte for byte, not re-encoded | `test_ingest.py` |
| A resend is accepted and leaves one copy. Six modalities sending at once all succeed | `test_ingest.py` |
| Server-side sorting (`OrderBy`) works, which the legacy ODBC index answers with HTTP 500 | `test_dicomweb.py` |
| QIDO-RS finds by modality and patient. WADO-RS returns cine frames as stored (JPEG-LS) or uncompressed, both pixel-exact. Series metadata is cached once the series is stable | `test_dicomweb.py` |
| An order reaches only its own modality's worklist and leaves it once the study has arrived and is stable. A cancelled order is withdrawn | `test_worklists.py` |
| After the restart, every study, every file (MD5), every registered modality and a pending order are still there, and the engine still takes studies | `test_after_restart.py` |
| The front door answers only for the site name, over TLS 1.3 and HTTP/2, and sends plain HTTP to HTTPS | `browser/tests/viewer.spec.js` |
| A cathlab run opens already playing. A CT series opens and every slice arrives. An ultrasound run that arrived as JPEG plays as sent. No console errors | `browser/tests/viewer.spec.js` |
| Every request the viewer makes goes to the front door and nowhere else, and every DICOMweb answer says `no-store` | `browser/tests/viewer.spec.js` |
| From where people sit, the engine cannot be reached by name. Its REST API is not routed. DICOMweb refuses writes | `browser/tests/viewer.spec.js` |

All test data is synthetic (`tests/synth.py`). Pixels are drawn from formulas,
patients are invented, and each file carries `PatientIdentityRemoved=YES`.
The AE titles the tests play are PMC's own, as MEASURED in the record.

## Measured on synthetic data (one run, cloud build host, 4 CPU)

- **JPEG-LS saving:** synthetic images were stored at 38–61% of their raw pixel
  size. That figure says nothing about PMC's images. The record MEASURED 30–37%
  smaller on PMC's own files.
- **A 59-frame cathlab run (512×512):**
  - whole instance, one request: 52 ms;
  - all frames, one request: 42 ms;
  - frame by frame, 59 requests: 1,030 ms in total.

  INFERRED: a viewer should fetch a cine run in one request, or in a few large
  batches, and never frame by frame. The fix for the live portal's cine
  complaint starts from this.
- **Through the browser** (headless Chromium, software rendering, same host):
  - the 59-frame run showed its first image about 6–9 s after the link opened,
    then played;
  - the 40-slice CT showed its first slice in about 4.5–7.5 s, with every slice
    loaded by then.

  These include OHIF's own start-up and a CPU-rendered canvas, so a ward PC
  with a GPU should do better. That is NOT VERIFIED: it is measured on PMC
  hardware in M4.

## Run it

```sh
tools/make-secrets.sh        # once: generates secrets/ (git-ignored); never overwrites
                             # and put the site's certificate in secrets/tls/
docker compose up -d --wait  # the platform, as project pmc-imaging
ci/run.sh                    # the tests, as project pmc-imaging-test, then removes it
KEEP=1 ci/run.sh             # the same, but leaves the test stack running
```

`ci/run.sh` runs as its own compose project, with its own volumes, its own
throwaway secrets (`.test-secrets/`) and a test hostname (`imaging.pmcne.test`,
from the reserved `.test` domain). So it can never touch a real platform's data,
secrets or certificate. The same script runs in GitHub Actions
(`.github/workflows/imaging-platform.yml`). Where Docker Hub rate-limits
anonymous pulls, run it with `PMC_LIBRARY=public.ecr.aws/docker/library`.

## Where things live

- `orthanc/orthanc.json`: the engine's configuration. Each block says why.
- `compose.yaml`: images by digest, the network, volumes and secrets.
- `compose.test.yaml`: the test overlay. Stable age and worklist housekeeping
  drop to 5 s, the edge network is sealed, and it adds the two test runners.
- `front/`: the front door. `nginx.conf` logs paths only, never query strings,
  because a DICOMweb query can carry a patient ID or name.
  `templates/front.conf.template` holds the routes, TLS and security headers.
- `viewer/`: OHIF's configuration (`app-config.js`) and the server block that
  serves its files inside its own container.
- `browser/`: the browser tests (Playwright).
- `secrets/`: generated by `tools/make-secrets.sh`, git-ignored. It holds the
  index password, the one HTTP user (`pmc-ops`) until sign-in arrives in M2.2,
  the front door's copy of that user's credential (removed in M2.2) and the TLS
  certificate. The containers read them as Docker secrets; none is in any file
  in git.
- **Modality addresses** live in the engine's database, registered at runtime
  (`PUT /modalities/{name}`), never in git (CLAUDE.md). The tests register
  their own container's address. A registration tool that reads the private
  inventory comes with M3.
- **Site values** are compose variables with safe defaults, none of them
  secret:
  - `PMC_HOSTNAME`: the front door's name (default `imaging.pmcne.ph`);
  - `PMC_DICOM_AET`: the engine's AE title (default `PMC-IMAGING`);
  - `PMC_SECRETS`: where the secrets are (default `./secrets`);
  - `PMC_LIBRARY`: where the official images come from (default Docker Hub).
- **The TLS certificate** is the site's own; for PMC, the existing `*.pmcne.ph`
  wildcard. It goes in `secrets/tls/` as `tls.crt` and `tls.key`.
  `tools/make-test-tls.sh` makes a throwaway one for tests and never replaces
  an existing certificate.

## Choices made here

These are INFERRED, not decided by anyone but this build. Argue with them.

- **An AE title alone is not an identity.** `DicomCheckModalityHost` is on, so
  a modality must connect from its registered address. On-prem this needs Docker
  to pass through each modality's real source address. Docker's default port
  publishing does that (INFERRED), but it is NOT VERIFIED on the R740xd; M4
  checks it.
- **C-ECHO is open to anyone**, so a technologist can test a link without ICT.
- **A resend never replaces what is stored** (`OverwriteInstances: Never`, the
  default).
- **The extra index tags are fixed now**, before the first study. Changing them
  later makes the Housekeeper re-read every file: 6.3 TB after the migration.
- **PostgreSQL `Lock` is off.** A lock held by a killed container's dead session
  can block the very restart that would recover it. Compose runs one engine.
- **Explorer 2 is off** until M2.2 decides ICT's admin surface.
- **A worklist entry nobody performs is removed after 72 h.** A performed one
  goes as soon as its study is stable.
- **The Housekeeper runs on weekday nights and weekends**, Manila time.
- **Cathlab runs open playing.** OHIF 3.13 turns the cine player on by itself
  only for `OT` and `US` (MEASURED from its bundle). `viewer/app-config.js`
  adds `XA` and `RF` and sets `autoPlayCine`, so a coronary run plays the
  moment it opens, which answers Dada's 1 Sep search for playback.
- **The browser may talk to the front door and nothing else**
  (`connect-src 'self'`). The policy also allows `'unsafe-eval'`, because the
  viewer's image decoders fail without it (MEASURED: every frame failed to
  decode).
- **Images stay off disks on the way through.** DICOMweb answers carry
  `Cache-Control: no-store`, and the front door is barred from spilling a
  response to a temp file.
- **OHIF's own study list** is on until the PMC front door app (M2.3) replaces
  it.
- **OHIF's "investigational use" notice** is left at OHIF's default: once per
  browser session. Whether PMC keeps it is a governance decision for Dada.

## Open

- **The AE title the modalities call today** is NOT VERIFIED here. Migration
  either sets `PMC_DICOM_AET` to it or re-points every modality.
- **The DICOMweb plugin in this image logs a warning** (MEASURED): "compiled
  against Orthanc SDK <= 1.5.6. STOW and WADO chunked transfers will be entirely
  stored in RAM". That matters for large STOW uploads, which is how migration
  may load studies. M4 measures memory under a large STOW before relying on it.
- **Orthanc's performance options are at their defaults**, which it logs at
  start. Tune them after measuring at PMC's volume (about 82 studies a day; CT
  up to about 1,700 images a study), not before.
- **Concurrency:** `DicomThreadsCount` is 4 (the default). Six simultaneous
  senders passed; larger bursts are not measured.
- **DICOM from the modalities on-prem:** the engine sits on a network with no
  route out, which also means port 4242 cannot be published from it. M4 gives
  the engine a second, DICOM-only network for the modalities.

## Regenerating `tests/requirements.txt`

It is generated from `tests/requirements.in` with a hash for every package.
The image installs with `--require-hashes`. To change a version, edit
`requirements.in`, then regenerate:

```sh
uv pip compile --generate-hashes --python-version 3.14 \
  --python-platform x86_64-manylinux_2_28 --no-header --no-annotate \
  -o requirements.txt requirements.in
```

## Next

- **M2.2:** sign-in through Entra ID with roles from Microsoft 365 groups.
  Keycloak brokers to Entra, oauth2-proxy keeps the session, and
  orthanc-auth-service checks every call. A stand-in Entra runs in the tests.
  This removes the engine account from the front door.
- **M2.3:** the PMC front door app at `/pmc/`: the worklist, which opens the
  viewer.
- **M2.4:** the cine fix for the live WS23 portal, prepared and tested here. It
  is deployed only on Dada's go.
- **M3:** the BizBox-to-worklist connector (against a mock BizBox), feed watch
  and alerts, backups (pgBackRest and restic) with a timed restore drill.
- **M4:** migration tooling, the runbook, and the on-prem package for the
  R740xd.
