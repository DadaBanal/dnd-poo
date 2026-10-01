# HANDOFF-sql01-cloud-WS36-20261001: three mail defects hot-fixed live, a schema step to carry one, the left menu, and the Procurement pack extras

| Field | |
|---|---|
| To | Cloud (WS36) |
| From | SQL01 |
| Workstream | WS36 |
| Head seen | `a9520bc` (059–061 live, applied by SQL01; mail cut-over run) |
| Fence | Hostnames, mailbox names, column names only. No tenant/client id, thumbprint or password. |

## 1. Three defects that blocked all support@ ingestion (each MEASURED on DND-SQL01, 1 Oct 2026)

The cut-over tasks ran, but **no support@ mail became tickets** until these were hot-fixed. Clean mail (no attachment, short Message-ID) worked; real PCSD mail did not — the end-to-end test with synthetic mail would not have caught them.

- **(a) The pickup task sets no `PSA_ATTACHMENT_DIR`.** A mail with an attachment hits `attachments.store_dir`, which raises *"a SQL Server desk … set PSA_ATTACHMENT_DIR"*, failing the pass. PSA-Desk and PSA-Rules set `D:\psa\files`; the pickup (and sender) do not.
  - **SQL01's host fix:** `PSA_ATTACHMENT_DIR=D:\psa\files` set machine-wide; the per-minute task inherits it.
  - **WS36:** `Invoke-PmcMailPickup.ps1` (and `Send-PmcNotifications.ps1`) should set `$env:PSA_ATTACHMENT_DIR` themselves, as the other task scripts do, so it does not depend on a machine variable.
- **(b) `__main__.py:363` had an unescaped `\p`** in `"...D:\psa\logs\PSA-Mail-<mailbox>.log"` — a `SyntaxWarning` to stderr on every psaspine start. The pickup runs python `2>&1` under `$ErrorActionPreference='Stop'`, so native stderr became a terminating error (pmc-estate §6) → every pass "failed".
  - **SQL01's fix, committed in the live tree** (`b5c1135`): made that string a raw string (`r"..."`).
  - **WS36:** take that change; and consider the pickup wrapper should not treat a mere stderr write as a fatal pass failure (capture, inspect `$LASTEXITCODE`).
- **(c) `data_quality.subject_id` was nvarchar(64)** (TEXT → 64 in the port), but `_record_failure` writes the full **Message-ID** there, and a real Exchange Message-ID is longer → *"String or binary data would be truncated"*. So the per-message **failure recorder itself raised**, killing the whole pass — one unplaceable message blocked every later one, defeating "one message at a time, never a lost pass".
  - **SQL01's host fix:** `ALTER TABLE psa.data_quality ALTER COLUMN subject_id nvarchar(800)` (to match `intake_message.message_id(800)`).
  - **WS36, REQUIRED — this diverges from the port and a rebuild would revert it:** carry it in a **schema step** (widen `data_quality.subject_id` to match `message_id`). Also `_record_failure` should bound what it writes so a long id can never truncate.

After all three: support@ drop cleared, delta saved, the yahoo and "Property Request" mails ingested; `mail-why` shows yahoo/gmail/"Property Request" as `NEW_TICKET`.

## 2. Left-hand menu (Dada, 1 Oct: "this doesnt fit make sure to place the menu on the left like connectwise if possible")

The top nav overflows: **14 top-level items** (Service Board, Dispatch, Schedule, Calendar, Time, Projects, Knowledge, Companies, On-call, Reports, Finance, Sales, Uplift, Setup) plus the brand and the user block do not fit the bar at normal widths. Dada wants a **left sidebar** nav in the reference PSA's shape. This is a desk UI change (web views/CSS), WS36's. SQL01 changes nothing on the host for it.

## 3. Procurement pack extras (Dada, 1 Oct: "add additional statuses subtype item to the bizbox one" / "add what u think is missing")

SQL01 applied `pmc_pack.apply` to Procurement (it had never been run there) **and** added BizBox-procurement content, via the desk's own functions, audited `PMC_PACK`; Procurement stays **not live** (owner/deputy is Dada's gate). The extras exist only in SQL01's run, not in `pmc_pack.py` — **WS36 should fold them into the pack** so a rebuild recreates them:

- **Extra statuses on Procurement:** `Waiting on BizBox`, `For Receiving`, `For Payment`, `On Hold` (NO_ESCALATION / RESOLUTION_PLAN as fits).
- **Extra item verbs (`ITEMS`):** `Amend`, `Cancel`, `Query`, `Follow up`, `Dispute`, `Receive` (REQUEST), `Short or wrong delivery` (FAULT).
- **New area `BizBox procurement`** with subtypes and items:
  - Purchase order: New or install, Amend, Cancel, Query, Follow up
  - Supplier invoice: New or install, Dispute, Query, Follow up
  - Receiving / delivery: Receive, Short or wrong delivery, Damaged, Query
  - Supplier / vendor: New or install, Amend, Query
  - Product / item: New or install, Amend, Query
  - Agreement / contract: New or install, Amend, Query

PMO Helpdesk also received the pack's helpdesk catalogue (it was empty) and the three helpdesk-extra statuses.

## Not SQL01's to decide

- The menu design and the per-defect code fixes above.
- Whether Procurement's generic statuses (Assigned, In Progress, Scheduled, Waiting on Requester/Vendor, Resolved) are retired now that the procurement flow is in — Dada, on Setup.

## Added 1 Oct evening: members cannot be removed from a Windows sign-in

Dada: "also the users or members cannot be removed". **Root cause (MEASURED on DND-SQL01):** every member-mutating handler in `web/views/members.py` (`board_remove`, `deactivate`, `role`, `capacity`, and add) calls `common.require_sysadmin`, which checks `ctx.user.is_sysadmin`. `auth.authenticate_windows` returns a `User` with `is_sysadmin` left at its default `False` - it is set only for a break-glass local account or an Entra/JWT `sysadmin` claim. So a **Windows (AD) sign-in is never a sysadmin**, and every member change answers 403 "a system administrator changes it". The backend `members.deactivate` works (SQL01 reproduced it as the task account).

**Please let a Windows admin be a sysadmin on the desk** - a `member.is_sysadmin` flag, a `PSA_SYSADMINS` account list, or membership of an AD group checked in `authenticate_windows`. Until then member management only works through the break-glass door.

## Added 1 Oct evening: Grant-PsaCalendars fails for a SQL sysadmin caller

`Grant-PsaCalendars.ps1` is run by Dada (Exchange admin), who is a **SQL sysadmin** → his PMC_PSA connection resolves to schema **[dbo]**, and the desk's `db.connect` refuses it ("default schema must be [psa]"). So its step 1, `psaspine calendar-members`, throws and the grant never runs. `calsync.members` itself works (SQL01 ran it as the task account: 8 members).

**SQL01's stopgap (committed):** added `-MembersFile` to the script — a JSON array of `{"mailbox": ...}` the desk produced (`D:\psa\calendar-members.json`, written as the task account), used instead of the live python call. Dada runs `Grant-PsaCalendars.ps1 -MembersFile D:\psa\calendar-members.json` (preview, then `-Apply`). **WS36:** the real fix is to run the `calendar-members` step as the task account (or let a read-only desk command accept a dbo/sysadmin connection); then `-MembersFile` is unnecessary.
