# Jobs — the work list for the main SQL01 chat

## How this runs

- **The main SQL01 chat builds** (Dada, 15 Oct 2026). Per-job sessions and the control chat were tried on 15 Oct and
  dropped: each new session re-learned the codebase (one reached 587K tokens in two hours) and carried ~95K of fixed
  overhead. Job 03 was already running when this changed and finishes in its own session; no new job sessions after it.
- Each file here is still the brief for one piece of work: the main chat works it, commits, adds one runbook
  paragraph, and marks the brief `Status: done <date> <commit>`.
- **Going live** is Dada's word (*"restart"*).
- Before running the test suite or anything that writes files: the attachment-store rule in
  `platform/psa-spine/CLAUDE.md` §2.

## The board

| Job | Card name | Status |
|---|---|---|
| `01-login-screen.md` + `02-design-review-fixes.md` | Job 01 · Login screen (Vitals v7) | **live** 15 Oct 2026 on Dada's "restart" — `D:\dnd-poo` at `765351c`, code `336a4f1` (runbook Parts 121–122). Dada's word, same day: `Bash(sqlcmd *)` deny removed; the 15 test-run files moved (not deleted) to `D:\psa\files-testrun-20261015`. Open finding: `psa.attachment` 400 hashed rows, `psa.chat_file` 22, but `D:\psa\files` held no files before the run |
| `03-waiting-rule.md` | Job 03 · Waiting rule | **running** — started 15 Oct 2026 on Dada's "start job 03", from `352fd76` |

A new job: add a one-page brief here as `NN-<name>.md` (Status line first, then *First: read platform/psa-spine/CLAUDE.md*),
and a row above.
