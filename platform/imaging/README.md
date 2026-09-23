# platform/imaging — the Path A engine

**Status, 23 Sep 2026: milestone M1 is built and proven off-prem. Nothing is
deployed.** Dada's rule (23 Sep): nothing goes on-prem until the whole platform
is built, and the on-prem go is his. Deployment also stays gated on ADR-001
(still *Proposed*) and on the safety work in [`../README.md`](../README.md),
"What it is gated on".

This replaces the 6 Sep skeleton in `platform/`, which was never run.

## What M1 is

Two containers on a Docker network with no route out:

```
modality ── DICOM 4242 ──┐
                         ├──▶ orthanc ──▶ pg-index      the index (PostgreSQL 18.6)
viewer ── DICOMweb 8042 ─┘       │
                                 └──▶ orthanc-storage   the images, JPEG-LS lossless
```

No port is published to the host. The tests reach the engine from a container
on the same network, over DICOM and DICOMweb, as a modality or a viewer would.
Nothing is mocked. In M2 the front door joins this network and becomes the only
way in.

## Pinned

| Component | Version | Pinned by | Evidence |
|---|---|---|---|
| Engine: `orthancteam/orthanc:26.9.1` | Orthanc 1.13.0; DICOMweb 1.24; PostgreSQL index 11.0 (schema revision 11); Worklists 0.9.2; Housekeeper 1.13.0; GDCM plugin 1.8 (GDCM 3.0.24); DCMTK 3.7.0 | image digest | MEASURED from the running engine's `/system` and `/plugins`, 23 Sep 2026 |
| Index: `postgres:18.6-trixie` | 18.6. Data checksums on; built-in `C.UTF-8` collation, which no glibc update can reorder | image digest | MEASURED by `ci/run.sh` on every run |
| Test runner: `python:3.14-slim-trixie` | Python 3.14.7, pydicom 3.0.2, pynetdicom 3.0.4, pylibjpeg-libjpeg 2.4.0, pytest 9.1.1 | image digest, and a hash for every package | MEASURED |

The digests are in `compose.yaml` and `tests/Dockerfile`. Each was pulled from
Docker Hub on 23 Sep 2026 (MEASURED).

## What the tests prove

`ci/run.sh` runs 31 tests. All passed on 23 Sep 2026 (MEASURED, cloud build).
It starts from empty volumes and runs 26 tests. It then removes the containers,
starts new ones from the same volumes, and runs 5 more.

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
  batches, and never frame by frame. The M2 cine fix starts from this.

## Run it

```sh
tools/make-secrets.sh        # once: generates secrets/ (git-ignored); never overwrites
docker compose up -d --wait  # the engine, as project pmc-imaging
ci/run.sh                    # the tests, as project pmc-imaging-test, then removes it
KEEP=1 ci/run.sh             # the same, but leaves the test stack running
```

`ci/run.sh` runs as its own compose project with its own volumes, so it can
never touch a running engine's data. The same script runs in GitHub Actions
(`.github/workflows/imaging-platform.yml`).

## Where things live

- `orthanc/orthanc.json`: the engine's configuration. Each block says why.
- `compose.yaml`: images by digest, the network, volumes and secrets.
- `compose.test.yaml`: the test overlay. Stable age and worklist housekeeping
  drop to 5 s, and it adds the test runner.
- `secrets/`: generated by `tools/make-secrets.sh`, git-ignored. It holds the
  index password and the one HTTP user (`pmc-ops`) until single sign-on arrives
  in M2. The engine reads both as Docker secrets; neither is in any file in git.
- **Modality addresses** live in the engine's database, registered at runtime
  (`PUT /modalities/{name}`), never in git (CLAUDE.md). The tests register
  their own container's address. A registration tool that reads the private
  inventory comes with M3.
- **Site values** are compose variables with safe defaults. There is one today:
  `PMC_DICOM_AET`, the engine's AE title (default `PMC-IMAGING`).

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
- **Explorer 2 is off** until M2 decides the user-facing surface.
- **A worklist entry nobody performs is removed after 72 h.** A performed one
  goes as soon as its study is stable.
- **The Housekeeper runs on weekday nights and weekends**, Manila time.

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

- **M2:** the front door (nginx, TLS, HTTP/2), OHIF v3.13 as the one viewer,
  sign-in through Entra ID with roles from Microsoft 365 groups, and the portal
  cine fix.
- **M3:** the BizBox-to-worklist connector (against a mock BizBox), feed watch
  and alerts, backups (pgBackRest and restic) with a timed restore drill.
- **M4:** migration tooling, the runbook, and the on-prem package for the
  R740xd.
