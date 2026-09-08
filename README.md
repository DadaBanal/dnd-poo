# dnd-poo — PMC imaging platform

Source for Premiere Medical Center Nueva Ecija's imaging front end, and the
config-as-code for the platform underneath it.

Two things live here:

| Path | What it is | Status |
|---|---|---|
| [`apps/imaging-portal/`](apps/imaging-portal/) | **PMC Imaging** — the worklist Orthanc serves at `https://imaging.pmcne.ph/pmc/`. One self-contained HTML file, built from source, 24 browser checks. | Built and tested. **Not yet installed on the server** (WS23). |
| [`platform/`](platform/) | Path A "engine as code": Orthanc + PostgreSQL index + OHIF + Keycloak as versioned config. | **Skeleton. Never run.** Gated on ADR-001 and a Linux host. |

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
```

## Ground rules

See [`CLAUDE.md`](CLAUDE.md). Short version: no patient identifiers, no
credentials, no internal IP addresses in this repo; label MEASURED vs INFERRED;
never edit `dist/` by hand.

The authoritative record for the programme is the OneDrive `Documents/Claude`
folder, not this repo. This repo holds code and the decisions code depends on.
