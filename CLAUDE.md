# Working rules for this repository

This repo is **code**. The programme record — every finding, decision, handoff
and script — lives in the OneDrive folder `Documents/Claude` (`PMC_START_HERE.md`,
then `docs/programme-register-and-plan-2026-09-08.md`). Read that first; treat it
as decided and do not contradict it here without saying so.

## What may and may not be committed

Carried from the record's own PHI and credential fence:

- **Never**: patient identifiers or patient names; passwords, hashes, tokens,
  API keys or SMTP secrets; `.env`; a real `pmc-portal.config.json`; anything
  matching the record's inventory denylist (`*SOA*`, `CaseNo*`, `*_KEY_*`,
  `*.bak`, `*.hl7`, `bio_enrolment_map*`, …).
- **Not here either**: internal IP addresses and network topology. New code must
  add none. The portal needs none — it speaks only relative paths to the archive
  that serves it, and reads device addresses from Orthanc at runtime.
  *One inherited exception:* the sample-data fallback in
  `src/app/04-demo-archive.js` carries three placeholder hosts (`10.2.2.60/.61/.77`).
  They match no real device (MEASURED against the record) but they do sit inside
  PMC's subnet range. They are not changed here, because that would break the
  artifact's byte-identity with the build that was tested and is about to be
  installed. Change them in the same commit as the next deliberate re-baseline.
- **Fine**: hostnames and service names (`PMC-ORTHANC01`, `imaging.pmcne.ph`),
  AE titles, plugin and version numbers, counts and dates.

This repo is private. That is a control, not a licence to relax the above.

## Evidence language

Label claims **MEASURED** (read from a system, a file or the record),
**VERIFIED** (read today from a primary source, with the URL), **INFERRED**
(reasoning from those, so it can be challenged) or **NOT VERIFIED**. Never
present an inference as a measurement.

## The artifact rule

`apps/imaging-portal/dist/PMC_Imaging_Portal.html` goes onto a live clinical
archive. Therefore:

- Never hand-edit anything in `dist/`. It is generated; CI fails if it drifts.
- The build refuses to emit an artifact whose hash differs from the reference in
  `build/manifest.json`. When a change is deliberate: change `src/`, run
  `npm test`, run `npm run baseline`, and commit the manifest **with** the change
  so the diff shows both.
- The portal must stay self-contained — no CDN, no web font, no external request.
  The build enforces this; do not add an exception.
- The portal must never send `OrderBy`. The ODBC index answers HTTP 500 to it.
  There is a check for this; it is not optional.

## Naming

The record uses `WSnn-<slug>-YYYYMMDD.<ext>` for working documents and
`PMC_<Title>_YYYYMMDD.<ext>` for client-facing ones. `docs/` here follows the
first. Never overwrite a dated document; supersede it and say so in the header.
