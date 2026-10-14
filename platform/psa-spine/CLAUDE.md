# Dada PSA desk — working rules for any session building it

Read this before touching `platform/psa-spine`. Under 200 lines on purpose (Anthropic's guidance); the detail lives
in the runbook and the handoffs — **grep them, never read them whole** (the runbook is 580 KB).

## 1. Load these skills — by condition, not by topic

Skill invocation is model judgment and a description alone does not fire it; an explicit instruction here does.
The `pmc-*` skills live in the record (`Documents/Claude/.claude/skills`) and are **junctioned into
`~/.claude/skills`** on DND-SQL01 (15 Oct), so every session here loads them with no copy to drift.
`permissions.additionalDirectories` would NOT do this — it grants file access only (Claude Code skills docs).
**If the condition is true, load the skill before the work, not after.**

| Condition | Load |
|---|---|
| Session start; before any recommendation, status summary, risk warning, or agreeing/disagreeing | `pmc-attitude` |
| Before the first write to any database or the live desk; before stating a limit, a price, or that something is absent; on any failed command or not-found | `dada-working-protocol` |
| Anything touching LiveDB_PMC, TrainingDB_HIS8, PMC_PSA, BizBox, SSRS, IIS, scheduled tasks, backups | `pmc-estate` |
| A decision Dada must make, or a recommendation with options | `dada-deciding` |
| Writing anything a person reads (a brief to Dada, a notice, a handoff summary) | `pmc-writing` |
| Any UI change, before it is deployed | `design:design-critique` and `design:accessibility-review` |
| Building UI to the house style | read PMC Vitals Console (`https://claude.ai/artifact/M6C4r6FT5B2CzzgWzdyNGB`, v7): `project/README.md` and `project/tokens.json`, never the page |
| A library, framework or API question | `find-docs` (ctx7) |
| Web search or fetch | `web-research-tools` (TinyFish first) |

## 2. One job, one session — the token rule

- **A session does one job and closes.** Start from a brief in `docs/jobs/` (one page). End with a commit and a
  runbook entry of **one paragraph**. The repo and the runbook are the memory, not the chat.
- **Never fork a long session** — a fork carries its whole context. Never keep one chat running all week: an idle
  gap past the cache TTL re-caches everything at once.
- **Subagents only to keep a big dump out of context** (a codebase sweep, a long SQL survey), and on a light model
  (`model: haiku`) for simple ones. They cost more tokens in total, not fewer (Anthropic: agents ~4×, multi-agent
  ~15× a chat).
- `/clear` between unrelated tasks. Lower `/effort` for routine measurement and record-keeping.
- Preprocess big outputs in the command (grep, `head`, a Python filter) — never pipe a whole file or table into the
  conversation.

## 3. Who holds what

| | |
|---|---|
| **This repo / desk code** | `platform/psa-spine` (Python, SQLite tests, T-SQL port in `sqlserver/`, schema steps `schema/NNN_*.sql`, now at 088) |
| **BizBox measurement** | the **Bizbox Chat** session — every question about what BizBox stores or how its client behaves goes there, never probed here. Findings and asks only; "nothing needed back" means no reply. |
| **Decisions** | Dada. He decides fast on one recommendation and badly on a menu. |

## 4. The host

- Live desk: `PSA-Desk` scheduled task, port 8085, `desk.pmcne.ph`. Restart = `Stop-ScheduledTask` / `Start-ScheduledTask`;
  **a restart is Dada's word, every time** (working hours, users on it).
- Hourly BizBox read: `PSA-BizBox` task; map `D:\psa\bizbox-map.json` (22 objects); mirrors `PMC_PSA.psa.ext_*`.
  Result `267009` = still running; wait for `0`.
- Throwaway desk for reviews: `.claude/launch.json` `psa-review`, port 8086, SQLite in the scratchpad, seeded by
  `seed_desk.py`. Build it with `psaspine init` on a fresh file; an old file does not migrate.
- BizBox side: schema `psa` on LiveDB_PMC **and** TrainingDB_HIS8 — 22 views, `fn_item_ledger`, `sp_apply_change`.
- Python: `C:/PMC/Python312/python.exe -I`. Push: `claude/psa-ticketing-build`; verify local == remote after every push.

## 5. The gate — every write to a database

Preview → control → apply in **one transaction** → checks inside → rollback on any FAIL → **verdict read on a fresh
connection after commit**. COPY_ONLY backup of PMC_PSA before a schema step. Schema blocks are extracted from the
port by their own guard text and run **unretyped**.

- A control is a **query that returns 0**, never a statement expected to raise (`XACT_ABORT` aborts the transaction
  and a later `commit()` is silently a no-op — a printed PASS over a rolled-back change, 14 Oct).
- **The verdict is what a fresh connection sees, never what the script prints** — a stale verdict line printed FAIL
  over a good commit (088).
- Every absence needs a control in the same call: "not found" and "cannot see" are different answers.

## 6. Fences — never cross

- **Patient fence:** no BizBox `remarks` or `description` rendered or mirrored; **`psDatacenter` is never read** (the
  stock card prints patient names from it). Seeded test data only; nothing read from a BizBox table is committed.
- No internal IPs, patient data, credentials in the repo. Hostnames only.
- `PSA_BIZBOX_WRITE_ODBC` stays **unset** until a kind is proven on Training; set only on the push task, never the desk.
- `bizboxsa` untouched. Writes reach BizBox only through `psa.sp_apply_change`, MMS kinds only.

## 7. Traps already paid for — do not re-learn them

- BizBox numbers requisitions, issuances and counts **per requesting department**: `DocNo` repeats; the identity is
  `TrxKey` (`PK_TRXNO`). Purchase orders and purchase requisitions number globally.
- Every MMS slip filters on the **key**, not the printed number; `TranNo` **is** `PK_TRXNO` despite its name.
- `PK_TRXNO` is allocated from `mscSeriesNo` `doccode = 'TRK'` — one `UPDATE … OUTPUT inserted.seriesno` in the
  insert's own transaction. `FK_ASUPost` on an unposted save is a literal `0`.
- Stock requisition: `FK_mscWarehouseSRC` = issuing, `DST` = requesting. Purchase requisition: **`FROM` = requesting,
  `TO` = issuing** — reversed. Same-department-both-sides is refused on stock requisitions, allowed on purchase.
- `smallconversion` is not a column; it is the line's `conversion`. Read stored `netcost`; compute only on create.
- **A constant is not an absence** (a one-value column still carries meaning). Find a counter by **what it holds**,
  not what it is called.
- Windows: Python `write_text` turns LF into CRLF — write bytes. Bash heredocs mangle quotes — write files with the
  Write tool. The 8.3 short path (`DADA~1.BAN`) is refused by the Artifact publish — use the long path.

## 8. Open with Dada (do not decide them)

The BizBox user `sp_apply_change` writes as (`FK_ASUReg`; no BizBox user exists for him and no service user);
department approvers (null on all 53); purging 2,396 dead mirror rows and ~1 GB of superseded backups; the 73
negative stock balances; showing deleted documents marked.

## Compact instructions

When compacting, keep: the job's brief, files changed, test and gate results, commits pushed, and any open decision
for Dada. Drop tool output and exploration.
