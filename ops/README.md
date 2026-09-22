# ops — the estate, and the safety work that gates everything else

**Status: WRITTEN, NOT RUN.** No script in here has been executed. No
environment on the authoring account has a route to `DND-SQL01` or
`PMC-ORTHANC01` (MEASURED, 10 Sep 2026, `ENVIRONMENT.md`), so these are written
to be handed to a row that has one. Run each with no `-Apply` first and read the
plan.

## Why this folder exists

`platform/README.md` lists three things the "engine as code" work is gated on,
and names the first as **weeks 1-2 safety work: archive and index backups, a
patch window, the internet port-forwards closed**. It then records, flatly:

> None of that is done. The index has never been backed up.

That is the live risk in this programme, and it is the only item in the estate
plan that gets worse by waiting. Everything else under `platform/` is a
never-run skeleton that can sit safely; an unbacked index cannot.

This is not `apps/imaging-portal/scripts/`, which installs the portal. This is
the estate underneath it. Filing estate work under the portal would bury it.

## What is here

| Script | What it does | Gated on |
|---|---|---|
| `scripts/Backup-PmcImagingIndex.ps1` | First verified backup of the Orthanc index: `COPY_ONLY` full backup, `RESTORE VERIFYONLY WITH CHECKSUM`, manifest with a sha256. | A route to the index server, and a target volume that is not the database's. |
| `scripts/Backup-PmcOrthancArchive.ps1` | Verified copy of the study files to a separate volume. Never mirrors, so a study deleted at source is not deleted from the backup. | A route to the archive host, and somewhere with room. |

Run them **as a pair and record both**. An index with no pixels restores a
catalogue of nothing; pixels with no index restore a disk of unnamed files.

## What is deliberately not here

- **The port-forward closure.** Risk R3 — `platform/compose.yaml` records that
  5432 is among the ports currently forwarded from the internet on the UDM-SE.
  Closing a forward is a firewall change with a blast radius, not a script to
  run unattended, so it is a written change request in the handoff instead, with
  what breaks if it is wrong.
- **A schedule.** These take *a* backup. A retention rule, an offsite copy and a
  restore rehearsal are a backup regime, and none of them is decided yet. A
  backup nobody has ever restored is a hypothesis.
- **Anything that touches the live HIS.** It carries a 173-finding audit, `sa`
  enabled and the Domain firewall off. Nothing here goes near it.

## The conventions these follow

The same ones as the portal scripts, because the discipline is what makes them
safe to hand over:

- **Preview by default.** Nothing is written without `-Apply`.
- **Refuse rather than guess.** Both refuse a backup target on the same volume
  as the data. The index script refuses an IP address for the server, because
  the repository fence forbids internal addresses and a backup script is exactly
  the file somebody pastes into a ticket.
- **Verify the result, do not assume it.** The index backup is proved with
  `RESTORE VERIFYONLY`; the archive copy checks robocopy's exit code and fails
  loudly at 8 or above. The portal installer once reported success after a
  rollback because a 401 proved nothing, and that lesson is carried here.
- **Pure ASCII, Windows PowerShell 5.1.** Per `docs/handoffs/HANDOFF-TEMPLATE.md`.
  Note the 5.1 trap this programme has already paid for once:
  `ConvertFrom-Json` does not enumerate, so `@($text | ConvertFrom-Json)` wraps
  an array instead of unwrapping it.
