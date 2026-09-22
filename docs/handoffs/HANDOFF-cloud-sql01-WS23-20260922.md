# HANDOFF-cloud-sql01-WS23-20260922

| Field | |
|---|---|
| **To** | SQL01 — and, for step 2 only, whichever row holds a route to `PMC-ORTHANC01`. This file does not guess which; see *Do NOT decide*. |
| **From** | Cloud Build. This session claims **no row** in the master manifest (`ENVIRONMENT.md`): it has a checkout and no route to anything, so it writes scripts and hands them over. |
| **Workstream** | WS23 (imaging estate) |
| **Bucket** | Take the first verified backup of the Orthanc index, and the first copy of the study files. One sitting. Nothing on the host survives an RDP logoff, so finish or report BLOCKED in the same session. |
| **Read first** | 1. `ops/README.md` 2. `ops/scripts/Backup-PmcImagingIndex.ps1` header 3. `platform/README.md` ("What it is gated on") |

## Why this is the first thing and not the fifth

`platform/README.md` records, flatly: **"None of that is done. The index has
never been backed up."** (MEASURED.) Everything else in the estate plan is a
never-run skeleton that can sit safely. An unbacked index cannot: it is the
thing that knows where every study is, and the archive now holds real patient
studies rather than the two it held when the plan was written.

## Do

Both scripts **preview by default**. Run each with no `-Apply` first, read the
plan it prints, and only then repeat with `-Apply`.

**1. The index (on / from SQL01).**

```
.\Backup-PmcImagingIndex.ps1 -ServerInstance <host\instance> -Database <name> -BackupDir <other-volume>
.\Backup-PmcImagingIndex.ps1 -ServerInstance <host\instance> -Database <name> -BackupDir <other-volume> -Apply
```

Name the host; the script refuses an IP, because the repository fence forbids
internal addresses. It also refuses a `-BackupDir` on the same volume as the
database files, and refuses to overwrite an existing backup.

It takes a `COPY_ONLY` full backup, then proves it with
`RESTORE VERIFYONLY ... WITH CHECKSUM`, then writes a manifest with a sha256.
`COPY_ONLY` is deliberate: there is no log chain today, and a `COPY_ONLY` backup
cannot become the base of one by accident, so taking it constrains no plan
adopted later.

**2. The study files (needs a route to the archive host).**

```
.\Backup-PmcOrthancArchive.ps1 -StudyDir <orthanc StorageDirectory> -BackupDir <other-volume>
.\Backup-PmcOrthancArchive.ps1 -StudyDir <orthanc StorageDirectory> -BackupDir <other-volume> -Apply
```

Preview runs `robocopy /L`, so the preview is the real file list. It never
mirrors: a study deleted at source is not deleted from the backup. It does not
stop Orthanc; completed study files are written once and not rewritten, so a
running copy is safe for them, and a study arriving mid-copy is corrected by the
next run. If you need a strictly point-in-time copy, stop the service and say so
in the reply.

**Run them as a pair and record both.** An index with no pixels restores a
catalogue of nothing; pixels with no index restore a disk of unnamed files.

**3. The port-forward (R3) — a change request, not a script.**

`platform/compose.yaml` records that **5432 is among the ports currently
forwarded from the internet on the UDM-SE**. That is a database port reachable
from the internet. Closing it is a firewall change with a blast radius, so it is
not automated here. What is needed back is: the current forward list, what each
one is for, and who asked for it. Then the closure can be argued per-port
instead of as one sweep that breaks something nobody remembered.

## Do NOT decide

These go to Dada, not to the row running this:

- **Which volume the backups live on, and whether it is offsite.** There is one
  Hyper-V host, it runs the only domain controller, and it has no host-level
  backup (MEASURED, `platform/README.md`). A backup on that host survives a
  database failure and not a host failure.
- **The retention rule and the schedule.** These scripts take *a* backup. A
  regime needs retention, an offsite copy and a restore rehearsal, and a backup
  nobody has ever restored is a hypothesis.
- **Which row owns `PMC-ORTHANC01`.** `ENVIRONMENT.md` says no cloud session has
  a route and does not say who does. Do not invent one; name it in the reply.
- **Whether any port-forward closes.** Bring the list back; the decision is not
  the operator's.
- **ADR-001.** Still *Proposed*. Nothing here depends on it, and taking these
  backups does not approve it.

## Fence

Hostnames only. No patient identifier, no credential, no key, no internal
address — the index script enforces the last one itself by refusing an IP for
`-ServerInstance`. Label everything reported back MEASURED / VERIFIED /
INFERRED / NOT VERIFIED.

## Done means

In the record, a reply appended to this file carrying:

- The index manifest (`<database>-<stamp>.bak.manifest.txt`) contents, or its
  path plus the sha256 line — **MEASURED**.
- `RESTORE VERIFYONLY` passed — **MEASURED**, quoting the line.
- The archive manifest, with the robocopy exit code and what it means —
  **MEASURED**.
- The UDM-SE forward list — **MEASURED**, hostnames and port numbers, no
  addresses.
- Anything refused or skipped, and why.

**NOT VERIFIED, and stated plainly:** neither script has ever been executed, and
neither has been syntax-checked under Windows PowerShell 5.1 — the authoring
environment has no PowerShell at all. They are written to the same conventions
as the portal installer, which was itself wrong twice before it was right. Read
the preview before trusting either.

| Written | 22 September 2026, 10:05 UTC |
|---|---|
| **Reply** | *(appended once by the receiver: DONE, BLOCKED or WITHDRAWN, plus an evidence pointer)* |
