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
| `01-login-screen.md` | Job 01 · Login screen (Vitals v7) | running (started 15 Oct) — **continues WS36's unverified WIP `84bcb47`**, do not start over |
| `02-design-review-fixes.md` | Job 02 · Design review fixes | open — part done in WS36's WIP `84bcb47`; check what is left first |
| `03-waiting-rule.md` | Job 03 · Waiting rule | open |

A new job: add a one-page brief here as `NN-<name>.md` (Status line first, then *First: read platform/psa-spine/CLAUDE.md*),
and a row above.
