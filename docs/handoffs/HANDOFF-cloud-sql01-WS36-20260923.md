# HANDOFF-cloud-sql01-WS36-20260923

| Field | |
|---|---|
| **To** | SQL01 — a Claude Code session running **on** `DND-SQL01`, not a cloud session viewed from it. |
| **From** | Cloud Build. MEASURED 23 Sep 2026: this session executes on a cloud VM (hostname `vm`, Ubuntu 24.04); the Claude app on `DND-SQL01` only displays it. No route to `PMC_SS` or `PMC-ORTHANC01`. |
| **Workstream** | WS36 (PSA ticketing), plus the waiting WS23 handoff |
| **Bucket** | Stand up the SQL01 row as a real local session, prove its route, and pick up the handoff already queued for it. One sitting. |
| **Read first** | 1. `CLAUDE.md` 2. `ENVIRONMENT.md` 3. this file 4. `docs/handoffs/HANDOFF-cloud-sql01-WS23-20260922.md` |

## Step 0 — for the person at the keyboard (not for Claude)

1. On `DND-SQL01`, in the Claude app, start a **new Claude Code session that runs on this
   computer** (a local folder), not in the cloud environment `dnd`. Exact menu wording is
   NOT VERIFIED.
2. If there is no clone yet, in PowerShell:
   ```
   git clone https://github.com/dadabanal/dnd-poo.git
   cd dnd-poo
   git fetch origin claude/psa-ticketing-build
   ```
   Clone onto a volume that is **not** the SQL Server data volume.
3. Open that folder as the session's working directory and paste the message below.

## The opening message to paste

> You are the SQL01 row. Read CLAUDE.md, then ENVIRONMENT.md, then
> docs/handoffs/HANDOFF-cloud-sql01-WS36-20260923.md, and do its "Do" section.
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
4. **Pick up the queued WS23 handoff** — `HANDOFF-cloud-sql01-WS23-20260922.md`, step 1
   only (the index backup). Preview run first (no `-Apply`), show the operator the plan,
   and apply only on their explicit go-ahead.
5. **Not in this sitting:** `sqlserver/PMC_PSA_Spine_SqlServer.sql` stays unrun until D7
   (where the spine lives) is decided. A `@Apply = 0` preview is allowed if the operator
   asks; `@Apply = 1` is not.

## Do NOT decide

- D7 — SQLite, SQL Server Express, or an existing instance for the PSA spine.
- Whether the imaging index backup target volume is acceptable long-term.
- Anything touching the live HIS databases on the same instance.

## Fence

Hostnames only. No patient identifier, credential, key, connection string or internal
address in any file, commit or reply. Label MEASURED / VERIFIED / INFERRED / NOT VERIFIED.

## Done means

- The master `ENVIRONMENT.md` (OneDrive `Documents/Claude`) SQL01 row carries a cell dated
  the day of the run: hostname, route to `PMC_SS` MEASURED, Python version MEASURED.
- A Reply appended below: DONE or BLOCKED, with the test count and the index-backup
  manifest sha256 if step 4 applied.

| Written | 2026-09-23, UTC |
|---|---|

## Reply

*(appended once by SQL01)*
