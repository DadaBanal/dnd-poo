# HANDOFF-‹from›-‹to›-‹WSnn›-YYYYMMDD

One file, one shape, placed where the **receiver** can read it without asking:
the record's `docs/handoffs/` for anything to or from SQL01 or MEL; this folder
for Cloud Build; Main files every finished cloud handoff into the record.
Rows, never people. Never edited after its reply; a follow-up is a new dated file.

| Field | |
|---|---|
| To | ‹row› |
| From | ‹row› |
| Workstream | WSnn |
| Bucket | One sentence. Sized to one sitting for SQL01: nothing on the host survives an RDP logoff. |
| Read first | Ordered files. |
| Do | Exact commands. Every T-SQL with `@Apply = 0` preview, verify gate, `PMC_Backup_*` table, exact keys, rollback in this file. PowerShell `$Apply=$false` first, pure ASCII, tested under Windows PowerShell 5.1. |
| Do NOT decide | The list that goes to Dada. |
| Fence | Hostnames only; no patient identifier, credential, key or internal address; label MEASURED / VERIFIED / INFERRED / NOT VERIFIED. |
| Done means | Which file appears where, with what evidence label. |
| Written | date, time, timezone |
| Reply | Appended once by the receiver: DONE, BLOCKED or WITHDRAWN, plus an evidence pointer. |

Two handoffs written before this template existed, kept where they are because
other documents cite their paths: `../WS36-ticketing-handover-20260909.md` and
`../WS23-imaging-parked-20260909.md`.

Retiring a session is this protocol addressed to itself
(`HANDOFF-main-main-YYYYMMDD.md`): what is in flight, what is undecided, where
every file went.
