# HANDOFF-cloud-sql01-WS36-20260923

| Field | |
|---|---|
| **To** | SQL01 — a Claude Code session running **on** `DND-SQL01`, not a cloud session viewed from it. |
| **From** | Cloud Build. MEASURED 23 Sep 2026: this session executes on a cloud VM (hostname `vm`, Ubuntu 24.04); the Claude app on `DND-SQL01` only displays it. No route to `PMC_SS` or `PMC-ORTHANC01`. |
| **Workstream** | WS36 (PSA ticketing) and WS23 (imaging portal), plus the waiting WS23 backup handoff |
| **Bucket** | Stand up the SQL01 row as one real local session that serves **both** builds, prove its routes, and pick up the handoff already queued for it. One sitting. |
| **Read first** | 1. `CLAUDE.md` 2. `ENVIRONMENT.md` 3. this file 4. `docs/handoffs/HANDOFF-cloud-sql01-WS23-20260922.md` |

## Step 0 — for the person at the keyboard (not for Claude)

1. On `DND-SQL01`, in the Claude app, start a **new Claude Code session that runs on this
   computer** (a local folder), not in the cloud environment `dnd`. Exact menu wording is
   NOT VERIFIED.
2. If there is no clone yet, in PowerShell:
   ```
   git clone https://github.com/dadabanal/dnd-poo.git
   cd dnd-poo
   git fetch origin claude/psa-ticketing-build claude/imaging-app-build-nqhh6f
   git worktree add ..\dnd-poo-imaging claude/imaging-app-build-nqhh6f
   ```
   One clone, two folders: `dnd-poo` holds the ticketing branch and `dnd-poo-imaging`
   the imaging branch, so neither build switches branches under the other.
   Clone onto a volume that is **not** the SQL Server data volume.
3. Open that folder as the session's working directory and paste the message below.

## The opening message to paste

> You are the SQL01 row. Read CLAUDE.md, then ENVIRONMENT.md, then
> docs/handoffs/HANDOFF-cloud-sql01-WS36-20260923.md, and do its "Do" section
> for both builds (ticketing in this folder, imaging in ..\dnd-poo-imaging).
> Preview everything first; change nothing without my go-ahead.

## Do

All read-only unless stated. Report each result with its evidence label.

1. **Prove the row.** `hostname` must print `DND-SQL01`. If it prints anything else, stop:
   you are not SQL01, say so, and do nothing further.
2. **Prove the route (read-only).**
   ```
   sqlcmd -S DND-SQL01\PMC_SS -E -Q "SELECT @@SERVERNAME, @@VERSION"
   ```
   Record the server name and version as MEASURED. Do not print or record connection
   strings, logins or addresses.
3. **Prove the ticketing branch runs here (no network, no install).**
   ```
   git checkout claude/psa-ticketing-build
   cd platform/psa-spine
   python -m unittest discover -s tests -p "test_*.py"    # or: python tests\test_spine.py
   ```
   If Python 3.11+ is not installed, report BLOCKED on that; **do not install anything**
   without the operator's say-so.
4. **Prove the imaging build runs here (no install without say-so).**
   ```
   cd ..\..\dnd-poo-imaging\apps\imaging-portal
   node --version        # needs >= 22 (package.json engines)
   npm ci
   npm test              # builds, then checks; the build refuses a hash off build/manifest.json
   ```
   If Node 22+ is absent, report BLOCKED; do not install it without the operator's say-so.
   `npm ci` fetches packages from the npm registry — ask before running it if the server
   has no approved internet egress. Never hand-edit `dist/`.
5. **Prove the Orthanc route, read-only.** From this host:
   ```
   .\scripts\Test-PmcPortalReadiness.ps1
   ```
   run in its preview form only, and record whether `PMC-ORTHANC01` answers (MEASURED) or
   not. Whether SQL01 has that route is NOT VERIFIED today; if it has none, report it and
   stop the imaging side there. **Do not run `Install-PmcImagingPortal.ps1`** — putting a
   build onto the live archive is the operator's decision, not this handoff's.
6. **Pick up the queued WS23 handoff** — `HANDOFF-cloud-sql01-WS23-20260922.md`, step 1
   only (the index backup). Preview run first (no `-Apply`), show the operator the plan,
   and apply only on their explicit go-ahead.
7. **Not in this sitting:** `sqlserver/PMC_PSA_Spine_SqlServer.sql` stays unrun until D7
   (where the spine lives) is decided. A `@Apply = 0` preview is allowed if the operator
   asks; `@Apply = 1` is not.

## Do NOT decide

- D7 — SQLite, SQL Server Express, or an existing instance for the PSA spine.
- Whether the imaging index backup target volume is acceptable long-term.
- Anything touching the live HIS databases on the same instance.
- Deploying the imaging portal onto `PMC-ORTHANC01`.

## Fence

Hostnames only. No patient identifier, credential, key, connection string or internal
address in any file, commit or reply. Label MEASURED / VERIFIED / INFERRED / NOT VERIFIED.

## Done means

- The master `ENVIRONMENT.md` (OneDrive `Documents/Claude`) SQL01 row carries a cell dated
  the day of the run: hostname, route to `PMC_SS` MEASURED, Python version MEASURED.
- The same row records the route to `PMC-ORTHANC01` (MEASURED yes / no) and the Node version.
- A Reply appended below: DONE or BLOCKED per step, with the psa-spine test count, the
  imaging `npm test` result and built `dist` sha256, and the index-backup manifest sha256
  if step 6 applied.

| Written | 2026-09-23, UTC |
|---|---|

## Reply

**SQL01: BLOCKED in part. 2026-09-23, 01:02 UTC.** A local Claude Code session on
`DND-SQL01`, Remote Control on. Ticketing at `D:\dnd-poo` (`claude/psa-ticketing-build`,
`a4b6c8e`), imaging at `D:\dnd-poo-imaging` (`claude/imaging-app-build-nqhh6f`, `fe4de35`).
Both equal origin (`git ls-remote`, MEASURED). Operator's rule for this sitting: preview
only; no install, no `-Apply`, no `@Apply = 1` without an explicit go-ahead.

| Step | State | Evidence |
|---|---|---|
| 1 Prove the row | **DONE** | `hostname` prints `DND-SQL01` (MEASURED) |
| 2 Route to `PMC_SS` | **BLOCKED** | `sqlcmd` refused twice by this repo's own deny rule, `.claude/settings.json` line 144: `Bash(sqlcmd *)` and `Bash(Invoke-Sqlcmd*)` (MEASURED). Not worked around. Server name and version: NOT VERIFIED |
| 3 Ticketing tests | **RAN, FAILING** | Python **3.12.10** at `C:\PMC\Python312\python.exe`, not on PATH (MEASURED). `C:\PMC\Python312\python.exe -m unittest discover -s tests -p "test_*.py"` in `platform/psa-spine`: **269 run, 8 failures, 1 error**, exit 1 (MEASURED, reproduced by an independent re-run). All nine are in `EmailIntakeTest`, and in every one intake records nothing: `new` = 0 in six (1 expected), `appended` = 0 in one, `duplicate` = 0 in one. The error is `TypeError: 'NoneType' object is not subscriptable` at `tests/test_spine.py:2570`, where no intake event row exists (MEASURED). Cause not diagnosed (NOT VERIFIED). No tracked file changed |
| 4 Imaging build | **HELD** | System Node **v20.20.0**; the record says production services run on it and it must not be upgraded in place (`pmc-estate` §12). Node **22.23.2** side by side at `C:\PMC\_tools\node22`, not on PATH (MEASURED). `apps/imaging-portal` has no `node_modules`, and Playwright is not installed globally for either Node either, which is the fallback `test/checks.mjs` tries, so Playwright is absent (MEASURED). `npm ci` needs registry egress and installs packages: held for the go-ahead. The operator stopped the build before it ran. No `npm test` result, no built `dist` sha256 |
| 5 Orthanc route | **BLOCKED** | `Test-PmcPortalReadiness.ps1` has no preview mode. It is read-only by design but calls `Get-Credential` for an Orthanc sign-in (MEASURED, source). This session enters no credentials, so the operator runs it. Route from `DND-SQL01` to `PMC-ORTHANC01`: NOT VERIFIED. `Install-PmcImagingPortal.ps1` not run |
| 6 Index backup (WS23 step 1) | **HELD** | Even the preview of `Backup-PmcImagingIndex.ps1` opens SQL connections through `System.Data.SqlClient`: it queries `sys.databases` and `sys.master_files` before the `-Apply` gate (MEASURED, source). The repo's deny rule does not literally match this, because it matches only the `sqlcmd` and `Invoke-Sqlcmd` command lines. It was held with step 2 by judgement, as the same kind of SQL contact that rule exists to fence (INFERRED). No run, no `-Apply`, no backup, no manifest. The script is identical on both branches (MEASURED) |
| 7 Spine on SQL Server | **NOT RUN** | Outside this sitting, as the handoff says |

**Against "Done means"**

- Master `ENVIRONMENT.md`, SQL01 row: **not updated**, because there is no row to update. No
  file of that name is in the local OneDrive `Documents` tree (`find`, MEASURED). Whether it
  exists online and is not synced here: NOT VERIFIED. The record's write lock is not missing:
  `pmc_lock.py`, named in record commit `19e5e80`, was superseded on 22 Sep by the user-level
  hook `~\.claude\hooks\pmc_session.py`, which takes the `docs/locks/` lock automatically on
  every Write or Edit into the record (MEASURED, source and user settings). No record write
  was made.
- psa-spine count: above. Imaging `npm test` and `dist` sha256: none, step 4 held. Index
  manifest: none, step 6 held.

**Found in passing** (not acted on)

- `gh` 2.101.0 is installed at `C:\Program Files\GitHub CLI` and was logged in this sitting
  as `DadaBanal`; `gh auth status` showed scopes `gist`, `read:org`, `repo` (MEASURED).
- **Nothing in settings fences `dist/` on this host.** The `claude` CLI warns that the deny
  rule `Write(//home/user/dnd-poo/apps/imaging-portal/dist/**)` is never matched by file
  permission checks, and that only `Edit(...)` rules are (MEASURED, CLI output). Both that rule
  and the `Edit(...)` rule beside it are also pinned to the cloud path `/home/user/dnd-poo`, so
  neither matches `D:\dnd-poo` or `D:\dnd-poo-imaging` (INFERRED from the path text). The
  build's own hash gate and CI still stand.
- A status message was sent one-way from this host on 23 Sep to the cloud sessions titled
  "WS23 Imaging app build" and "WS36 PSA ticketing build" (send accepted, MEASURED). The cloud
  row reports it did not arrive, so delivery is NOT VERIFIED. This Reply is the durable copy.

**What unblocks each, all the operator's call**

- Steps 2 and 6: allow `sqlcmd` for this repo on this host, or run them and paste the output.
- Step 4: a go-ahead for `npm ci` (registry egress, Playwright) and the build under Node 22.
- Step 5: the operator runs the readiness probe with the Orthanc sign-in.
- Step 3: a go-ahead to diagnose the nine failures.

**Follow-up, 2026-09-23 01:43 UTC:** step 3 is **DONE**. I pulled `claude/psa-ticketing-build`
at `bbb89ac` (a fast-forward from `ed2b7d4`) and ran
`C:\PMC\Python312\python.exe -m unittest discover -s tests -p "test_*.py"` in
`platform/psa-spine` on `DND-SQL01`. Result: **Ran 269 tests in 30.9 s, OK**, exit 0, with 0
FAIL or ERROR lines (MEASURED). The nine `EmailIntakeTest` failures recorded above are fixed
by `bbb89ac`.
