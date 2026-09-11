# State as of 11 Sep 2026 — cloud session (machine: cloud)

Per-machine state file. Counterparts for the same day: `docs/state-20260911-sql01.md` (DND-SQL01,
has `sqlcmd -E` and the app folder) and `docs/state-20260911-mel.md` (Melbourne PC).
Previous file from this machine: `docs/state-20260910-cloud.md`.

This session is the PMC 365 Desk running as Claude Code in a cloud container. It holds the
Microsoft 365 connector for the OneDrive folder **and, new today, a git clone of
`DadaBanal/dnd-poo`**. It has **no route to DND-SQL01, `LIVEDB_PMC`, PMC-ORTHANC01 or any hospital
host**, and no `sqlcmd` or SQL Server of any kind.

`PMC_START_HERE.md` and `docs/_INDEX.md` were **not** edited, per the working rules.

Files written this session:
- `sql/Create-WS38-ClaimsSchema-HMO-20260911-v2.sql`
- `docs/ws38-schema-v2-and-repo-findings-20260911.md`
- `docs/bus/to-sql01-002.md`
- `docs/bus/to-mel-002.md`
- `docs/state-20260911-cloud.md` (this file)

Renamed, bytes untouched: `sql/Create-WS38-ClaimsSchema-HMO-20260911.sql` →
`sql/SUPERSEDED-DO-NOT-RUN-Create-WS38-ClaimsSchema-HMO-20260911.sql`.

**No existing file was overwritten.** Every file above is new. Each was written locally and uploaded
as a single atomic create through the Graph API — there is no partial-write window for OneDrive to
turn into a conflict, which is the same outcome the write-to-temp-then-move rule exists to get.

---

## 1. What this session did

Picked up **WS38** from `docs/continuation-prompt-ws38-hmo-20260911-v2.md` and executed **§J steps 1
and 2**: file the corrected schema script with the §A fixes, and fold in both §B defects.

Read first, in order: the continuation prompt v2, `CLAUDE.md`, `docs/state-20260911-sql01.md` (all
17 sections), `docs/state-20260911-mel.md`, `docs/ws38-schema-parse-and-corrections-20260911.md`,
`docs/bus/README-session-bus.md`, and both existing bus messages. Then the superseded schema file
itself, in full, before changing anything.

**Nothing was applied. No database was touched — none is reachable from here.**

## 2. The bus

Checked at session start, per the standing habit. `docs/bus/` held three files:
`README-session-bus.md`, `to-sql01-001.md` (mel → sql01) and `to-mel-001.md` (sql01 → mel). **Neither
message is addressed to `cloud`, so neither was answered as if it were, and neither was edited.**

Written this session: `to-sql01-002.md` and `to-mel-002.md`, both **from `cloud`**.

**Sequence decision, recorded because it departs from the README table.** That table assigns
`to-sql01-NNN.md` to `mel` and `to-mel-NNN.md` to `sql01`, and says `NNN` is a sequence *per
direction*. `cloud → sql01` is a third direction that would restart at 001 — and collide with mel's
existing `to-sql01-001.md`, which is the precise failure the bus exists to prevent. I took **002** in
each recipient's shared sequence instead, and the `From:` header line identifies the writer. If
either machine prefers a different convention, say so and I will follow it; the one rule I will not
break is two writers on one filename.

Last sequence handled by this machine: **none addressed to cloud**. Last sent: `to-sql01-002`,
`to-mel-002`.

## 3. The corrected schema script — FILED, NOT COMPILED

`sql/Create-WS38-ClaimsSchema-HMO-20260911-v2.sql`
SHA256 `84c49a9b4c6e774bf6a5521d1b6da3330593eeff5339e53b95f6470802594b79`, 35,448 bytes, 586 lines.
Supersedes SHA256 `5C940EA2…`, 25,165 bytes, 432 lines.

Nine corrections, tagged `[F1]`–`[F9]` in the file at the line each sits on, every one traced to a
measurement made on DND-SQL01. Full table in
`docs/ws38-schema-v2-and-repo-findings-20260911.md` §2. In short: both `RAISERROR` guards take a
variable; the proof harness is split so catalogue rows always run and content rows bind at execution
time behind `sp_executesql`; `SET QUOTED_IDENTIFIER ON` in all four batches; `DENY UPDATE, DELETE` in
front of the append-only trigger; MAXICARE carries no presentable name and harness row 12 loses its
exclusion; the database guard is repeated in batches 3 and 4; the stale HMO-only prose is corrected;
the preview stops promising two triggers the file does not create; and the trigger comment no longer
states a disproven belief.

**This file has not been compiled.** There is no T-SQL parser on this machine — the same position
Melbourne was in when it wrote the file that failed. What *was* done here is structural proof only,
and it is worth naming for what it is not:

| Check | Result |
|---|---|
| `BEGIN`/`END` block balance, comments and string literals excluded | balanced, depth 0 |
| `CASE`/`END` balance, outer batches and each dynamic string scanned separately | balanced |
| Single-quote parity, per batch, comments stripped | even in all four batches |
| Every `RAISERROR` call takes `@db`, never `DB_NAME()` | 0 violations |
| `SET QUOTED_IDENTIFIER ON` present in every batch | 4 of 4 |
| `claims.*` read statically in batch 4 outside a dynamic string | none |
| Passwords, patient identifiers, name columns | none |

**This is regex and bracket-counting. It is exactly the kind of verification that passed the first
file and then failed to compile.** It is not a parse. The gate on DND-SQL01 is the gate.

## 4. Deliberately left undone in that file, rather than guessed

1. **`@AppPrincipal` is NULL**, so the `DENY` is skipped and new harness row 17 reports FAIL. The
   FAIL is the honest state: until the account the bridge connects as is established, the
   append-only control is trigger-only, and MEASURED on sql01 a trigger cannot give the caller one
   clean error. The elevated diagnostic already on Dada's list returns that account.
2. **`trgCaseAudit` / `trgApprovalAudit` are not written.** Brief §6 requires field-level audit. The
   pattern is `payroll.AuditLog` plus three existing `trg*Audit` triggers in `PMC_Apps`, none
   readable from here. Writing them blind is what produced the first file.
3. **INFERRED, NOT VERIFIED:** whether an `INSERT` into a table with a persisted computed column also
   needs `QUOTED_IDENTIFIER ON` on the connection. If it does, it is the bridge's problem too, not
   only the deploy script's. One statement on DND-SQL01 settles it.

## 5. NEW MEASURED FINDING — `DadaBanal/dnd-poo` is empty

| Measure | Value |
|---|---|
| Commits on the default branch | **1** (`fc16991`, "Initial commit") |
| Files tracked, entire history | **2** — `LICENSE`, `README.md` |
| `README.md` | the single line `# dnd-poo` |
| `platform/psa-spine/`, `build/manifest.json`, imaging portal, ticketing spine | **absent from every commit** |

This disproves two things being carried as fact:

- **`docs/continuation-prompt-ws38-hmo-20260911-v2.md` §I.6** — "`platform/psa-spine/` in the repo
  consumes this file, so fix it there rather than hand-editing the CSV", labelled INFERRED. There is
  no such path. Logging WS36/37/38 means a **new dated register file in `deliverables/`**.
- **`docs/state-20260910-cloud.md` §4 item 3** — "the repository holds the imaging portal and the
  ticketing spine", used there as the reason the 9 Sep GitHub OAuth authorisation is urgent. It holds
  neither. **The OAuth item still stands on its own merits** — an unrecognised authorisation on
  Dada's account is a problem regardless — but it should be ranked on the account, not on code value,
  because there is no code.

Caveat stated plainly: this is measured against the repository §H names by URL, the one this session
can reach. If the imaging portal lives in a different repository then §H names the wrong one, and
that is the correction instead. Either way, the sentence as written is not true.

**Unchanged by this:** §H's instruction to install `gh`, authenticate and clone on DND-SQL01 stands,
and so does the ruling **not** to `git init` inside the OneDrive folder. An empty repository argues
for putting work into it, not against.

## 6. Third correction to the continuation prompt, and it is from its own source

§D of the prompt lists two disproven beliefs. Here is a third, and it did not come from this session:
**§E and §I.2 still quote 347 claims / PHP 3,143,601.50** due within 30 days, and
`docs/state-20260911-sql01.md` §9 withdrew that number the same day. `dischdate` carries a time
component on 2,595 of 2,600 rows; comparing against a midnight date dropped the boundary day.

**The measured figure is 423 claims, PHP 3,904,722.20** — 22% larger. The prompt is what people are
reading, so the withdrawn number is the one in circulation. Both bus messages carry the correction.
The prompt itself was not edited.

## 7. Git — the repo now has WS38 in it

Unlike DND-SQL01 (`docs/state-20260911-sql01.md` §15, where no clone, remote, credential helper or
`gh` exists), this session has a working authenticated clone. The five files above were committed to
branch `dada/vigilant-darwin-t4abgp` and pushed, and a **draft** pull request was opened. The
OneDrive folder remains the record; the repo now carries the same bytes under version control, which
is what §H asks for and what R14 is about.

`git init` was **not** run inside the OneDrive folder. The clone is a separate checkout in the
container.

## 8. Still open, and none of it settled here

- **The gate.** v2 has never been compiled. sql01 to run it at `@Apply = 0`, twice, with and without
  `sqlcmd -I`, and report. A clean parse is a finding, not permission to set `@Apply = 1`.
- **PhilHealth filing owner.** 423 claims, PHP 3,904,722.20 inside 30 days; 2,434 unfiled in total,
  PHP 28.9M at risk, everything due between 4 Oct and 10 Nov. No software fixes this and it is worth
  more this week than the form is.
- **Bridge supervision.** Unresolved at sql01's privilege level; ten seconds of elevation settles it.
- **The watchdog glob repair.** Printed, not applied. Payroll app, mid parallel run.
- **WS38 not logged as a VARIATION.** Register CSV still ends at WS35.
- **HTTPS redirect** on `payroll.pmcne.ph` and `queue.pmcne.ph`.
- The four rulings remain Dada's. Nothing in this session settles one.

---

# Round 2 — after context compaction, 11 Sep 2026 ~13:00–13:45 PHT

## 9. A failure worth recording, because it cost Dada time

This session's context was compacted mid-run. Everything in §1–§8 had already been done, filed and
pushed. **The session then lost that fact and began re-deriving it from scratch** — re-reading the
superseded script, re-verifying the corrected one, and attempting to upload a file that was already
sitting in `sql/`. The upload failed on a name collision with its own earlier work, which is how the
duplication was caught.

Worse, and separately: it twice told Dada it **"had no route to DND-SQL01"** and declined work on
that basis. That was wrong. It had already delivered a file to DND-SQL01 that morning, through this
folder. Dada's correction was blunt and correct.

**The rule that came out of it, now in `CLAUDE.md` on both the OneDrive root and the repo root:**
the OneDrive folder is the **transport** as well as the record. A cloud session holding the
Microsoft 365 connector writes a file here and it is on DND-SQL01 within a sync cycle. No VPN, no
resolving hostname, no SQL access required. What a cloud session cannot do is *execute*.

## 10. Capability, measured in the container rather than assumed

| Probe | Result |
|---|---|
| `sqlcmd`, `bcp`, `mssql-cli`, `isql`, `tsql`, `osql`, `sqlpackage` | all absent |
| DNS for `DND-SQL01`, `dnd-sql01.pmcne.ph` | no resolution |
| Computer use / screen control / screenshot tool | none; tool surface searched twice |
| Read and write this OneDrive folder over Graph | **yes, and used all session** |

An RDP window open on Dada's desktop is not a route into this container, and this session cannot
drive it. Session records also show the four `bridge`-environment sessions — the ones that do run on
Dada's own machines — were **all disconnected**, three logging `computer_unreachable`, the most
recent at 01:20 UTC today. So there was no local session to hand the work to either.

## 11. Two corrections to my own earlier statements

- **The 17-byte discrepancy is explained.** `sql/Create-WS38-ClaimsSchema-HMO-20260911-v2.sql` was
  35,431 bytes when first written and 35,448 when hashed, committed and filed. The difference is
  `AND minor_id = 0` added to harness row 17's permission check, which correctly restricts it to a
  table-level `DENY` rather than a column-level one. The filed file — SHA256 `84c49a9b…`, 35,448
  bytes — is the corrected one and is what §3 and both bus messages describe.
- **`docs/bus/to-sql01-002.md` is stamped `14:20 PHT` and was actually written about `12:32 PHT`.**
  The file is not edited; the correction is here. Nothing else in it is affected.

## 12. Files written this round

- `CLAUDE.md` (OneDrive root) — **appended**, not restructured: new section "How a cloud session gets
  work onto DND-SQL01 — stop re-deriving this", plus a `cloud` row under Machines and a note that a
  Graph upload satisfies the write-to-temp-then-move rule by construction.
- `CLAUDE.md` (repo root, new) — the same operating facts, for sessions working the git clone.
- `docs/continuation-prompt-ws38-hmo-20260911-v3.md` — **supersedes v2**. Written for a session that
  *can* run SQL. Its §B is the gate command with a hash check that refuses to run the wrong file;
  §D now carries the withdrawn PhilHealth figure as a third disproven belief; §H is the capability
  table from §10 above.
- `docs/state-20260911-cloud.md` (this file, appended).

`PMC_START_HERE.md` and `docs/_INDEX.md` still not edited. Nothing overwritten. The two `CLAUDE.md`
writes are appends to a rules file, which is what that file is for; the state-file denylist is
unaffected.

## 13. Where WS38 actually stands

**Unchanged since §8: the gate has still not been run.** The corrected script is filed, verified
structurally, hash-pinned and sitting on DND-SQL01. It has never been compiled. Everything else in
this workstream is behind that one command.

Handoff is prepared: a local session started on the v3 prompt runs §B, pastes the output, and this
picks up from there.
