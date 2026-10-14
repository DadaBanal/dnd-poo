# Jobs — one page each, one session each

## How this runs

- **Home:** one session named **PSA desk — control**, pinned at the top of the *PMC — PSA Ticketing* group. It never
  builds. It starts jobs, says what is running and done (from this board), and carries Dada's decisions. When it grows
  long, archive it and open a new one with the same name: this board and the runbook are its memory.
- **A job:** Dada tells control *"start job NN"*; control puts up a card (spawn task) titled
  **"Job NN · <short name>"** — e.g. *Job 02 · Design review fixes* — whose prompt is *do docs/jobs/NN-<name>.md* plus
  the worktree push rule in `platform/psa-spine/CLAUDE.md` §4. One click starts it; it reads `platform/psa-spine/CLAUDE.md`
  and the brief, builds, tests, reviews, pushes, adds one runbook paragraph, marks its brief done, and closes.
- **Going live** is Dada's word (*"restart"*), said in the job's session.
- **One job builds at a time**, so two sessions never push to the branch at once.

## The board

| Job | Card name | Status |
|---|---|---|
| `01-login-screen.md` + `02-design-review-fixes.md` | Job 01 · Login screen (Vitals v7) | **live** 15 Oct 2026 on Dada's "restart" — `D:\dnd-poo` at `765351c`, code `336a4f1` (runbook Parts 121–122). Dada's word, same day: `Bash(sqlcmd *)` deny removed; the 15 test-run files moved (not deleted) to `D:\psa\files-testrun-20261015`. Open finding: `psa.attachment` 400 hashed rows, `psa.chat_file` 22, but `D:\psa\files` held no files before the run |
| `03-waiting-rule.md` | Job 03 · Waiting rule | **running** — started 15 Oct 2026 on Dada's "start job 03", from `352fd76` |

A new job: add a one-page brief here as `NN-<name>.md` (Status line first, then *First: read platform/psa-spine/CLAUDE.md*),
and a row above.
