# WS38 — corrected claims schema filed, and two carried beliefs disproven, 11 September 2026

**Machine:** cloud (PMC 365 Desk — Microsoft 365 connector + a `dnd-poo` git clone; **no route to
DND-SQL01, `LIVEDB_PMC` or PMC-ORTHANC01**)
**Answers:** `docs/continuation-prompt-ws38-hmo-20260911-v2.md` §J steps 1 and 2
**Corrects:** `docs/continuation-prompt-ws38-hmo-20260911-v2.md` §E, §I.2 and §I.6, and
`docs/state-20260910-cloud.md` §4 item 3. Neither of those files is edited; this is the correction,
the same convention they use.

**Nothing was run against any database.** No `sqlcmd` and no SQL Server exist on this machine. The
corrected script is **filed, not compiled**. The parse gate still has to be run on DND-SQL01.

---

## 1. What was filed

`sql/Create-WS38-ClaimsSchema-HMO-20260911-v2.sql`

| | |
|---|---|
| SHA256 | `84c49a9b4c6e774bf6a5521d1b6da3330593eeff5339e53b95f6470802594b79` |
| Bytes | 35,448 |
| Lines | 586 |
| Supersedes | `sql/Create-WS38-ClaimsSchema-HMO-20260911.sql` (SHA256 `5C940EA2…`, 25,165 bytes, 432 lines) |

The superseded file was **renamed in place** to
`sql/SUPERSEDED-DO-NOT-RUN-Create-WS38-ClaimsSchema-HMO-20260911.sql`. Its bytes are untouched — a
rename is not an in-place edit, and it matches the convention already used by
`SUPERSEDED-DO-NOT-RUN-Fix-BioRollup-ParityCarry-20260909.sql`. Anything that referenced the old
path by name now needs the new one.

**The v2 file has NOT been compiled.** It was written on a machine with no T-SQL parser, which is
exactly how the first one was written and exactly why it failed. Treat §3 below as the gate.

## 2. The nine corrections, and what each is evidenced by

Each is tagged `[Fn]` in the file at the line it sits on.

| Tag | Correction | Evidence |
|---|---|---|
| F1 | `DB_NAME()` hoisted into `@db`; both `RAISERROR` guards take the variable | MEASURED, sql01 — Msg 102 at old lines 45 and 52 |
| F2 | Harness split: catalogue rows run always, content rows run inside `sp_executesql` behind an `OBJECT_ID` test | MEASURED, sql01 — Msg 208 at old line 343; `SELECT` does not defer, `INSERT`/`UPDATE` do |
| F3 | `SET QUOTED_IDENTIFIER ON` in all four batches | MEASURED, sql01 — `SESSIONPROPERTY` returns 0 under sqlcmd, `CREATE` fails Msg 1934 |
| F4 | `DENY UPDATE, DELETE ON claims.CaseEvent` in front of the trigger | MEASURED, sql01 — trigger errors doom the caller (`XACT_STATE() = -1`, 3930 then 3998); DENY gives 229 with `XACT_STATE() = 1` |
| F5 | MAXICARE row now carries no name at all; harness row 12 loses its exclusion | MEASURED, sql01 — the excluded key was the only row that would display as confirmed |
| F6 | Database guard repeated in batches 3 and 4 | MEASURED, sql01 — `RETURN` leaves only its own batch |
| F7 | Header prose corrected to HMO **and** EMPLOYEE active | Dada's ruling, 11 Sep. The seed and harness row 9 were already right |
| F8 | Preview no longer promises audit triggers the file does not create | MEASURED, sql01 — old line 92 named two objects that appear nowhere else |
| F9 | Trigger comment rewritten; it stated a disproven belief about `THROW` | MEASURED, sql01 |

Two harness rows are new: **17** proves the DENY is actually in place, and **18** proves `CaseRef`
persisted. Row 17 reports **FAIL** until `@AppPrincipal` is set — see §4.

## 3. The gate — run this on DND-SQL01 before anything else

Same gate as last time, same rule: **a clean parse is a finding, not permission to set `@Apply = 1`.**

```
sqlcmd -S DND-SQL01\PMC_SS -d PMC_Apps -E -I ^
  -i "C:\Users\dada.banal\OneDrive - Premiere Medical Center Nueva Ecija\Documents\Claude\sql\Create-WS38-ClaimsSchema-HMO-20260911-v2.sql"
```

`-I` sets `QUOTED_IDENTIFIER ON` at the client as well. The file sets it per batch anyway; running
with and without `-I` is the cheapest way to prove F3 actually holds from an automated path.

Expected at `@Apply = 0` on a clean database: no `Msg`, the BEFORE block reports
`schema claims = absent`, the preview list prints, harness part 1 prints rows 1-8 and 16-18 as FAIL
or n/a, and part 2 prints `SKIPPED: claims tables absent`. **Anything else is a defect — report it,
do not patch it silently.**

## 4. What is still missing from the file, deliberately

1. **`@AppPrincipal` is NULL**, so the DENY is skipped and harness row 17 reports FAIL. That FAIL is
   the truth: until the account the bridge connects as is established, the append-only control is
   trigger-only, and a trigger cannot give the bridge one clean error. Settling it needs the owner of
   the `node.exe` on port 4100 — the same elevated look that
   `scripts/ps/Diagnose-PMCBridgeSupervision-20260911.ps1` already does.
2. **`trgCaseAudit` / `trgApprovalAudit` are not written.** Brief §6 requires field-level audit. The
   pattern is `payroll.AuditLog` plus three existing `trg*Audit` triggers in `PMC_Apps`, none of
   which is readable from this machine. Writing them blind is what produced the first file.
3. **INFERRED, NOT VERIFIED:** an `INSERT` into a table carrying a persisted computed column may also
   need `QUOTED_IDENTIFIER ON` on the *connection*, which would make this the bridge's problem and
   not just the deploy script's. One `SET QUOTED_IDENTIFIER OFF; INSERT …` on DND-SQL01 settles it.

## 5. NEW MEASURED FINDING — the `dnd-poo` repository is empty, and two carried beliefs rest on it

A clone of `https://github.com/DadaBanal/dnd-poo` was read from this session. **MEASURED:**

| Measure | Value |
|---|---|
| Commits on the default branch | **1** (`fc16991`, "Initial commit") |
| Files tracked, entire history | **2** — `LICENSE` and `README.md` |
| `README.md` contents | the single line `# dnd-poo` |
| `platform/psa-spine/` | **does not exist**, in any commit |
| `build/manifest.json`, any imaging-portal source, any ticketing spine | **do not exist**, in any commit |

Two things that have been carried as fact are therefore wrong:

**a) "`platform/psa-spine/` in the repo consumes the register CSV, so fix it there rather than
hand-editing the CSV"** — `docs/continuation-prompt-ws38-hmo-20260911-v2.md` §I.6, labelled INFERRED.
There is no `platform/psa-spine/`. The advice cannot be followed as written. Logging WS36, WS37 and
WS38 means a new dated register file in `deliverables/`, because there is no code path to fix.

**b) "the repository holds the imaging portal and the ticketing spine"** —
`docs/state-20260910-cloud.md` §4 item 3, which is the stated reason the GitHub OAuth authorisation
of 9 Sep is urgent. It holds neither. **The OAuth item is still worth acting on** — an unrecognised
authorisation on Dada's account is a problem whatever the repo contains — but it should be ranked on
the account, not on the value of the code, because there is no code.

**Scope of this finding:** it is measured against the repository §H names by URL, which is the one
this session can reach. If the imaging portal lives in a *different* repository, then §H names the
wrong one and that is the correction instead. Either way the sentence as written is not true.

**What this does NOT change:** §H's instruction to install `gh`, authenticate and clone on DND-SQL01
stands, and so does the ruling not to `git init` inside the OneDrive folder. An empty repository is
an argument for putting work in it, not against.

## 5b. The continuation prompt carries a PhilHealth figure its own machine already withdrew

`docs/continuation-prompt-ws38-hmo-20260911-v2.md` §E and §I.2 both say **347 claims, PHP
3,143,601.50** due within 30 days. `docs/state-20260911-sql01.md` §9 — written on the machine that
measured it, the same day — **withdraws that number**: `dischdate` carries a time component on 2,595
of 2,600 rows, and comparing against a midnight date dropped the boundary day.

**The measured figure is 423 claims, PHP 3,904,722.20.** It is 22% larger, and it is the number that
should be quoted to whoever is given the filing backlog. The continuation prompt is not edited; this
is the correction. §D of that prompt lists two disproven beliefs — this is a third, and it comes from
the prompt's own source document rather than from anything found here.

## 6. Files written this session

- `sql/Create-WS38-ClaimsSchema-HMO-20260911-v2.sql`
- `docs/ws38-schema-v2-and-repo-findings-20260911.md` (this file)
- `docs/bus/to-sql01-002.md`
- `docs/bus/to-mel-002.md`
- `docs/state-20260911-cloud.md`

Renamed, bytes untouched: `sql/Create-WS38-ClaimsSchema-HMO-20260911.sql` →
`sql/SUPERSEDED-DO-NOT-RUN-Create-WS38-ClaimsSchema-HMO-20260911.sql`.

Nothing was overwritten. Every file above is new. `PMC_START_HERE.md` and `docs/_INDEX.md` were not
edited.

## 7. Not done, and not this session's to do

- Nothing was applied. `@Apply` is 0 in both batches. The `claims` schema does not exist.
- No database was read. No `LIVEDB_PMC` access exists from here.
- The register CSV was not edited; it still ends at WS35. WS38 is still not logged as a VARIATION.
- No PhilHealth work. The filing backlog still has no named owner, and that is worth more this week
  than this file is: **423 claims, PHP 3,904,722.20, due inside 30 days** (corrected figure, per
  `docs/state-20260911-sql01.md` §9 — the 347 in the continuation prompt §E is the withdrawn one).
- The bridge supervision question, the watchdog glob repair and the four rulings remain Dada's.
