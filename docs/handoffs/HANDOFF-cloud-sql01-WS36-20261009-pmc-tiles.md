# HANDOFF — Cloud Build → SQL01, WS36, 9 Oct 2026 (the PMC tiles: 8 more, nothing else)

**No schema step and no restart. One preview, a gate on its exact contents, then one apply.**

This answers SQL01's Q1–Q4 (`…-20261009-premiere-one-question.md`) and follows Part 61. It supersedes nothing.

Branch: `claude/psa-ticketing-build`. Pull the head that carries this file.

## What Dada chose, 9 Oct 2026, from SQL01's answers

The answers that decided it:

- **Q3:** 15 of the 17 Premiere One tickets in 180 days were Payroll: *Cannot log in* 7, *Wrong data or report* 5.
- **Q4:** no tile reached *Payroll › Cannot log in*.
- **Q2:** PMC Portal has no Subtype; it is Payroll's second front door on the same process.

Dada chose **"New top tile + log-in"**:

- Under **Can't log in, or a password**, one smaller tile in Thobie's own words: *I cannot log in to PMC Portal or
  PMC Payroll*, landing on **Premiere One › Payroll › Cannot log in**.
- A new top tile, **PMC Portal, Payroll and PMC apps**, placed just before *Buy something* (`sort_order` 75). It
  goes to PMO Helpdesk and has six smaller tiles:

  | Smaller tile | Lands on |
  |---|---|
  | I cannot log in to PMC Portal or Payroll | Premiere One › Payroll › Cannot log in |
  | My payslip, attendance or leave looks wrong | Premiere One › Payroll › Wrong data or report |
  | PMC Portal or Payroll is not working | Premiere One › Payroll › Not working |
  | Queue (kiosk check-in, waiting-room screens) | Premiere One › Queue › Not working |
  | Imaging portal | Premiere One › Imaging › Not working |
  | My requests / PSA Desk | Premiere One › PSA Desk › Not working |

  Analytics and HomeBase are left out. In Q2 neither has a hostname (HomeBase is still in build), and in Q3 neither
  has a ticket.

Nothing already there changes, including the existing *Payroll* smaller tile under *BizBox or a hospital system*.
Whether to retire that one in Setup › Portal tiles is Dada's call, not this step's.

**Pinned by a test:** `PortalTilesTest.test_on_a_desk_with_the_first_46_a_run_adds_only_the_pmc_tiles`. It starts
from a desk carrying the first 46 tiles, with one of them edited by hand. It shows:

- the run adds exactly 8;
- it changes none of the 46, the edited one included;
- a third run adds nothing;
- the new top tile sits before *Buy something*.

`ticket-topics` also gets a matching word group for the new tile. Payroll, Queue and similar words move to it from
the BizBox group, so nothing is counted twice.

## The step

1. Pull.
2. **Preview** (writes nothing), under the desk account from `platform/psa-spine`, as Part 59:

   ```
   C:\PMC\Python312\python.exe -m psaspine portal-tiles "<the desk's connection>" --actor "sql01 for dada.banal"
   ```

3. **The gate.** The preview must show exactly this, and nothing more:
   - every one of the first nine top tiles reads `= tile … (already there, left as it is)`;
   - every one of their smaller tiles reads `= … (already there)`, **except one** new line under *Can't log in, or a
     password*:
     `+ I cannot log in to PMC Portal or PMC Payroll  -> PMO Helpdesk · Premiere One › Payroll › Cannot log in`;
   - one new block: `+ tile  PMC Portal, Payroll and PMC apps  -> PMO Helpdesk`, followed by its six `+` lines, each
     landing on **Premiere One** as in the table above;
   - the last line reads **`Would add 8 tile(s) and 0 question(s). Preview only`**.

   If the count is not 8, or any `+` line lands anywhere but Premiere One, or a `no catalogue match` appears:
   **stop and paste the preview back.** Nothing has been written.
4. **Apply**: the same command with `--apply`. It ends `Added 8 tile(s) and 0 question(s).` and then `applied`.
5. **Verify:**
   - `SELECT COUNT(*) FROM psa.portal_tile` goes from **46 to 54**;
   - top tiles (`parent_id IS NULL`) go from **9 to 10**;
   - `psa.ticket`'s count is unchanged;
   - running step 4 again prints `Added 0 tile(s)`.

## What to look for

- *My requests* shows **PMC Portal, Payroll and PMC apps** just before *Buy something*, and *Can't log in* now has
  four choices.
- Thobie's case: *Can't log in* → *I cannot log in to PMC Portal or PMC Payroll* → the ticket lands on PMO Helpdesk
  with *Premiere One › Payroll › Cannot log in* already set.

## Evidence

| | |
|---|---|
| Unit suite | See the commit message (SQLite). |
| SQL Server | CI `psa-spine` run 80, dispatched on `9c1977d`: green on all four jobs (Linux 3.11 and 3.14, sql-server, windows). MEASURED, 9 Oct 2026. |
| Not run here | The preview against the live catalogue: SQL01's Q1 makes the matches INFERRED, not measured. |
