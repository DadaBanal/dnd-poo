# dnd-poo — PMC imaging platform

Source for Premiere Medical Center Nueva Ecija's imaging front end, and the
config-as-code for the platform underneath it.

Two things live here:

| Path | What it is | Status |
|---|---|---|
| [`apps/imaging-portal/`](apps/imaging-portal/) | **PMC Imaging** — the worklist and DICOM viewer Orthanc serves at `https://imaging.pmcne.ph/pmc/index.html`. One self-contained HTML file, built from source, 45 browser checks. | Installed 9 Sep 2026 (WS23). The address is the file, not the folder. |
| [`platform/imaging/`](platform/imaging/) | Path A, the modern build: the imaging engine (Orthanc 1.13.0 on a PostgreSQL 18.6 index), a TLS front door, the OHIF viewer, sign-in through Entra ID with per-role access, and PMC's own worklist app, all as versioned code pinned by digest, with synthetic DICOM, test runners that act as the modalities, and a browser that signs in as each role. | **M1, M2.1, M2.2 and the worklist (M2.3, first part) built and proven off-prem** (67 tests, 24 Sep 2026). Not deployed: nothing goes on-prem until the whole platform is built, and deployment stays gated on ADR-001. The rest of M2.3, then M3 and M4, to come. |
| [`platform/`](platform/) | The 6 Sep skeleton of the same, superseded by `platform/imaging/`. Its README keeps the deployment gates. | Superseded. Never run. |
| [`platform/psa-spine/`](platform/psa-spine/) | The commercial half of a PSA — agreements, the nine scope items, the Annex B variation register, notices, client dependencies. Produces the variation register, the dependency notices and the instrument exception report. | Built and tested (158 tests, 10 Sep 2026). Since then: the service catalogue, the ticket, the board engine, the desk import, the generated SQL Server port and the uplift report. Measured against the real register: 35 rows in, 35 out. |

## Why this repo exists

Everything in the imaging programme so far has shipped as a hand-maintained file
plus a pasted PowerShell script. That is recorded as risk **R14** — *"all change
by pasted scripts"* — and it has already cost something concrete: the portal HTML
in `deliverables/` and the payload inside the installer that is queued to run on
the archive **are not the same file** (see `docs/WS23-imaging-portal-repo-20260908.md`).

Here, the artifact is *built* from source, its hash is *computed*, and both are
checked by CI. The two cannot drift apart again.

It is also the `config in Git` line of the 12-week Path A roadmap (weeks 2–5),
which had no work started anywhere.

## Quick start

```bash
cd apps/imaging-portal
npm run build          # assemble the single-file artifact into dist/
npm test               # build, then drive it in Chromium against a stand-in Orthanc
npm run payload        # emit the installer payload + sha256

platform/imaging/ci/run.sh   # the platform: start, test, restart, test again (Docker)
```

## Ground rules

Every session finds its row in [`ENVIRONMENT.md`](ENVIRONMENT.md) first; handoffs
between sessions use [`docs/handoffs/`](docs/handoffs/HANDOFF-TEMPLATE.md);
architecture decisions live in [`docs/adr/`](docs/adr/).

See [`CLAUDE.md`](CLAUDE.md). Short version: no patient identifiers, no
credentials, no internal IP addresses in this repo; label MEASURED vs INFERRED;
never edit `dist/` by hand.

The authoritative record for the programme is the OneDrive `Documents/Claude`
folder, not this repo. This repo holds code and the decisions code depends on.
