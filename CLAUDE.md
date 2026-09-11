# Operating facts for Claude sessions in this repository

Read this before saying anything about what you can and cannot reach.

## The OneDrive folder is both the record and the transport

The user's folder `…/OneDrive - Premiere Medical Center Nueva Ecija/Documents/Claude`
is opened by three sessions: the Melbourne PC (`mel`), the hospital SQL server
(`sql01`) and a cloud session (`cloud`). OneDrive keeps all three byte-identical —
verified 8 Sep 2026 and recorded in that folder's own `CLAUDE.md`.

**A cloud session holding the Microsoft 365 connector can read AND write that folder
over Graph.** Writing a file there puts it on DND-SQL01 within a sync cycle.

So: **to get a file onto the hospital SQL server, write it into the OneDrive folder.**
Do not tell the user there is no route to that machine. File delivery works. It has
been used in this very session to read the schema scripts, the state files and the
session bus, and to rename a superseded script.

## What a cloud session genuinely cannot do

Measured in this container, 11 Sep 2026:

| Capability | State |
|---|---|
| `sqlcmd`, `bcp`, `mssql-cli`, `isql`, `tsql`, `osql`, `sqlpackage` | all absent |
| DNS for `DND-SQL01` / `dnd-sql01.pmcne.ph` | no resolution |
| Network path to the hospital LAN | none, by design |

It cannot execute SQL, run PowerShell on a hospital host, or press F5. It also cannot
see an RDP window the user has open — that is a window on their desktop, not a route
into this container.

## The division of labour that follows

1. The cloud session **writes and verifies** the script, and files it into OneDrive.
2. The user, or the Claude session running on DND-SQL01, **executes** it and pastes
   the output back.
3. The cloud session reads that output and carries on.

Anything the user must run goes **in the reply**, not only in tool output.

## Verification honesty

A cloud session can only check a `.sql` file structurally: bracket and quote parity,
guard shape, write targets. **That is not a parse.** The superseded WS38 schema script
passed exactly that class of check on the Melbourne PC and then failed to compile three
ways on first contact with the server. Always say which of the two was done, and never
present the first as the second.

## WS38 specifics

- Never write to `LIVEDB_PMC`, `PMC` or `PHILHEALTH`. WS38 lives only in `PMC_Apps`,
  schema `claims`.
- No patient identifiers anywhere. Employee guarantors are captured by employee number.
- Production T-SQL runs at `@Apply = 0` first. A clean parse is a finding, never
  permission to apply.
- New dated file, `Supersedes:` header, do-not-run banner on the old one. Never
  overwrite, never duplicate.
