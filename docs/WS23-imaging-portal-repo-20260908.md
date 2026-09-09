# WS23 — the imaging portal becomes a built artifact

**Date:** 8 September 2026 · **Workstream:** WS23 (imaging platform redesign +
portal UI) · **Scope:** VARIATION · **Machine:** claude.ai/code cloud container
(no LAN, no local files — read-and-draft only) · **Repo:** `DadaBanal/dnd-poo`,
private, branch `claude/imaging-app-build-nqhh6f`

Every claim below is labelled **MEASURED** (read from a file or a run in this
session), **INFERRED** (reasoning, so it can be challenged) or **NOT VERIFIED**
(could not be checked from here — do not act on it as fact).

---

## 1. What changed

The portal existed as one hand-maintained 100 KB HTML file in `deliverables/`,
delivered by pasting an 80 KB PowerShell installer that carries it as gzip+base64
with a hand-pinned sha256. It is now built from source, with tests and CI.

- `apps/imaging-portal/src/` — the artifact split into an HTML shell, 8 CSS
  fragments, 15 JS fragments and the favicon. **MEASURED: the split is lossless.**
  Re-joining the fragments in manifest order reproduces the original byte for
  byte — 100,449 bytes, sha256 `c6d21731…3b30f4` **as at 8 Sep**. The build asserted this on every
  run and refuses to emit anything else, so the file that goes onto the archive
  is provably the file that was signed off on 6 Sep.
- `build/build.mjs` — assembles, and **enforces the self-contained rule**: it
  fails on any external `src`/`href`, `@import`, extra `<link>` or `<script src>`.
  That constraint was previously only a convention.
- `test/` — a stand-in Orthanc plus **24 browser checks, all passing** (MEASURED,
  Chromium 1.56.1). They cover what the portal was signed off on ("21 of 21",
  6 Sep) plus the three faults this code has actually hit.
- `build/payload.mjs` — emits the installer payload and its hash *from the build*,
  and verifies what an existing installer really contains.
- `.github/workflows/imaging-portal.yml` — CI runs the drift check, the browser
  checks, and publishes the artifact + hash. **NOT VERIFIED: never executed** (no
  Actions run has happened yet).

## 1a. SUPERSEDED — the artifact changed on 9 Sep

The hashes in section 2 describe the **6 Sep** build. A security fix on 9 Sep
(cross-origin `?api=` ignored; see `WS36`-era commits) deliberately re-baselined
the artifact to **101,154 bytes, sha256 `439667d3…d6f13`**. The comparison below
is still the right method; only the left-hand number has moved.

## 2. Finding — the deliverables portal and the installer payload are different files

**MEASURED.** `deliverables/PMC_Imaging_Portal_20260906.html` is **100,449 bytes**,
sha256 `c6d21731224a0d7270955c1d1142cb5e613980c20ab1a7d1ba893b42403b30f4`.

**MEASURED (from the record).** `docs/_INDEX.md` states the installer
`Install-PmcImagingPortal-OnServer-20260907.ps1` carries a **101,090-byte**
payload checked against sha256 `5a19bcb5ae4cb4c49e8e4121c49985bec3efe1e3beb5b99a4b7629e251373cb6`.

They differ by 641 bytes and the hashes do not match. Line endings do not explain
it: the deliverables file is LF-only, and restoring CRLF on every one of its 1,407
lines would give 101,856, not 101,090.

**INFERRED.** The 7 Sep installer probably embeds a later revision than the copy
saved to `deliverables/` — its own description mentions per-server viewer
resolution and a Test button. That is a reasonable story, not a measurement.

**NOT VERIFIED.** I could not read the `.ps1` from here — the M365 connector
refuses `application/octet-stream`. So *which* build is queued to be pasted onto
PMC-ORTHANC01 is, as of now, an open question.

**This is worth settling before WS23's install runs**, because the thing being
pasted onto a live clinical archive is not the thing the record describes as
tested. One command answers it, on any machine that has both files:

```bash
cd apps/imaging-portal && npm run build
node build/payload.mjs "/path/to/Install-PmcImagingPortal-OnServer-20260907.ps1"
```

It prints the installer's real payload size and hash beside this build's, says
MATCH or DIFFERENT, and on DIFFERENT writes the installer's own payload to
`dist/installer-payload.html` so the two can be diffed. It reads the file and
changes nothing.

Whatever the answer, the class of problem is now closed: the hash is computed by
the build, never typed.

## 3. Finding — `data-ready` is not a "loaded" signal

**MEASURED.** `render()` ends with

```js
document.startViewTransition ? document.startViewTransition(paint) : paint();
```

`startViewTransition()` defers the DOM write. `boot()` sets
`document.body.dataset.ready = '1'` as soon as it returns, so on a View-Transitions
browser the flag is set roughly **100 ms before the worklist paints** (measured:
flag at 81 ms, cards at 182 ms).

No user sees this — it is a tenth of a second. It matters for anything that
*watches* the page: a check keyed on `data-ready` will read a screen full of
skeletons and conclude the worklist is empty. It cost four false failures while
writing the suite here.

**Deliberately not fixed.** Changing it would change the artifact, and the
artifact must stay identical to the one that was tested and is about to be
installed. The tests wait for the skeletons to clear instead, and it is written
down in the app README. If a monitoring probe is ever built for the portal, it
must do the same.

## 3a. Finding — the artifact's sample data carries PMC-range addresses

**MEASURED.** The sample-data fallback baked into the artifact
(`src/app/04-demo-archive.js`) lists three devices at `10.2.2.60`, `10.2.2.61`
and `10.2.2.77`. Every LAN browser that loads the page with the archive
unreachable renders them.

**MEASURED.** None of the three matches a device in the record — Orthanc is
`.240` on 10.2.3, the Azurion `.251` on 10.2.3, Voyager `.193` on 10.2.2. So they
are fabricated placeholders, not a disclosure of real infrastructure.

**INFERRED.** They were chosen to look plausible. The cost is that they sit inside
PMC's own subnet range, so a reader cannot tell at a glance that they are fake,
and a future reader may take them for an inventory.

**Not changed**, for the same reason as §3: it would break byte-identity with the
build that was tested and is queued for installation. Worth folding into the next
deliberate change, alongside anything else that needs a re-baseline. Documentation
addresses (RFC 5737, `192.0.2.0/24`) are the right choice — the test fixtures here
use them.

## 4. Governance — this repo is a new surface

**MEASURED.** `dnd-poo` appears nowhere in the OneDrive record. The only Git
reference anywhere in it is the Path A roadmap line *"wk 2–5 engine as code …
config in Git"* and the principle *"configuration as versioned code"*.

So: putting imaging code in a GitHub repo is a **new decision**, not a
continuation of a recorded one — even though it is the natural home for the
"config in Git" milestone and directly reduces risk **R14** (*"all change by
pasted scripts"*). The repo is **private** (MEASURED, GitHub API, `visibility:
private`, created 8 Sep 2026, owner DadaBanal, 0 forks).

Two things follow, both for Dada:

1. **The record should name it**, or it becomes a second undocumented surface —
   the exact failure that WS30 exists to stop. A row in
   `deliverables/PMC_Workstream_Register_20260908.csv` under WS23 is enough.
2. **The record's PHI and credential fence applies here too.** `CLAUDE.md` in the
   repo carries it, with one addition: **no internal IP addresses**. The portal
   needs none — it speaks relative paths and reads device addresses from Orthanc
   at runtime — so none are committed. `platform/.env` is git-ignored and no real
   value is in `.env.example`.

## 5. Also added — `platform/`, the Path A skeleton

Path A was decided 6 Sep. Weeks 2–5 are *"engine as code"*, and **MEASURED: no
work on it exists anywhere in the record** — no repo, no Dockerfile, no compose
file, no Keycloak realm, no OHIF v3 deployment.

`platform/` now holds a compose skeleton (Orthanc + PostgreSQL index + OHIF +
Keycloak) and `orthanc.json` as versioned config. **It has never been run, no
image digest is pinned, and nothing in it is validated.** It is gated on ADR-001,
on a Linux host existing, and on the weeks 1–2 safety work — none of which is
true. It is there to be argued with in a diff, not deployed. `platform/README.md`
says so in its first line.

## 6. What this does not touch

Nothing on any PMC server. This container has no LAN route and no local files;
it is the *read-and-draft* surface in the register's own tooling table. WS23's
next action is unchanged and is still Dada's: **one paste of the installer into
an elevated PowerShell on PMC-ORTHANC01** — after §2 is settled.

Unchanged and still open, from the record, in the record's own priority order:

1. **The Orthanc index has never been backed up**, and it now holds real patient
   studies. `scripts/sql/Provision-OrthancBackupJobs.sql` is written and not run.
   This outranks everything here.
2. Feed `D:/Orthanc/worklists` from the BizBox schedule — the Philips half is
   already done and tests green, so the archive answers every worklist query with
   zero entries. Cheapest remaining clinical win.
3. Windows Update policy on PMC-ORTHANC01, still unset after one dirty shutdown.
4. ADR-001 — still *Proposed*.

## 7. Files written

```
README.md · CLAUDE.md · .gitignore · .github/workflows/imaging-portal.yml
apps/imaging-portal/  README.md, package.json, .gitignore
  src/index.html, src/styles/*.css (8), src/app/*.js (15), src/assets/favicon.png
  build/manifest.json, build/build.mjs, build/payload.mjs, build/baseline.mjs
  test/stand-in-orthanc.mjs, test/checks.mjs
  config/pmc-portal.config.example.json
  dist/PMC_Imaging_Portal.html  (generated; identical to the 6 Sep artifact)
platform/  README.md, compose.yaml, orthanc/orthanc.json, .env.example, .gitignore
docs/WS23-imaging-portal-repo-20260908.md  (this file)
```
