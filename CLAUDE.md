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

## What a cloud session cannot do DIRECTLY — and the one route that gets round it

Measured in this container, 11 Sep 2026, and still true:

| Capability | State |
|---|---|
| `sqlcmd`, `bcp`, `mssql-cli`, `isql`, `tsql`, `osql`, `sqlpackage` | all absent |
| DNS for `DND-SQL01` / `dnd-sql01.pmcne.ph` | no resolution |
| Direct network path to the hospital LAN | none, by design |

So no cloud session executes SQL over the network. **But it may still be able to reach
the server by driving Dada's desktop.**

**MEASURED 11 Sep 2026:** a cloud session drove `mstsc.exe` on `desktop-ranfmve` into
his already-open RDP session on the SQL server and ran the schema gate there in elevated
PowerShell. Computer use had been failing — the approval dialog rendered with only a
*Deny* control — and started working when the Claude desktop build moved from 1.49585.0
to 1.52386.0.

**Therefore: check your own tool surface before claiming you cannot reach that machine.**
Computer use is not present in every session; search for it rather than assuming either
way. A session that has it can drive the RDP window. A session that does not still has
the OneDrive route above, and still cannot press F5 itself.

Getting this wrong in both directions has cost Dada time: once by refusing OneDrive
delivery that worked, once by stating flatly that no session could drive his screen.

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

## Working cheaply — this account has run into its seven-day limit

MEASURED 17 Sep 2026 across ten sessions: $570.92, 549.8M tokens. **95.1% of those tokens were
cache reads** — re-reading conversation history. Output was 0.5%. One session accounted for 70%
of the spend.

Cost is driven by session length, not by how much is asked for. A one-line question in a 500K
session costs about the same as a fifty-line one.

- **Keep sessions short.** Findings go to a dated file in the record, then start a new session that
  reads it. Do not carry a conversation for days.
- **Never set a recurring check-in on something that cannot change on its own.** A pull request in a
  repository with no CI and no reviewers will not move; each wake re-reads the whole context to
  report nothing.
- **Read narrowly.** Fetch the lines needed, not whole files, and never re-read a file already in
  context.
- **Do not re-derive.** Check the state file and the bus before re-measuring something.
- Connectors flapping in and out invalidate the prompt prefix and force the whole context to be
  re-cached, which is the expensive kind of token. Fewer connectors, cheaper turns.

## Scope a claim to what was actually checked

A fresh clone has `main` and one branch. **"Absent from every commit" requires `git fetch --all`
and `git branch -r` first.** On 11 Sep a claim that this repository held two files and no PSA
spine went into the record as MEASURED; 40 spine files, a CI workflow and 25,097 lines were sitting
on an unfetched branch the whole time. Say which ref you measured.

## WS38 specifics

- Never write to `LIVEDB_PMC`, `PMC` or `PHILHEALTH`. WS38 lives only in `PMC_Apps`,
  schema `claims`.
- No patient identifiers anywhere. Employee guarantors are captured by employee number.
- Production T-SQL runs at `@Apply = 0` first. A clean parse is a finding, never
  permission to apply.
- New dated file, `Supersedes:` header, do-not-run banner on the old one. Never
  overwrite, never duplicate.
