# WS36 — the PSA commercial spine, built

**Date:** 9 September 2026 · **Workstream:** WS36 · **Scope:** VARIATION
· **Machine:** claude.ai/code cloud (read-and-draft; no LAN, no local files)
· **Companion:** `WS36-psa-recommendation-20260909.md` (the decision paper)

Every claim below is **MEASURED** (from a run in this session), **INFERRED** or
**NOT VERIFIED**.

## 1. What was built

`platform/psa-spine/` — the contract half of a PSA. Python 3.11, standard library
only, SQLite. **21 tests, all passing** (MEASURED). CI added at
`.github/workflows/psa-spine.yml` — **NOT VERIFIED, never executed.**

It produces three artefacts from data: the Annex B variation register, one dated
client-dependency notice per blocked workstream, and the instrument exception
report. None needs a licence, a server or an approval.

The ticket desk is **not** built and **not** replaced — see the recommendation.

## 2. Three numbers, MEASURED against the real register

Run against the 35-row register (key columns; staged outside the repository):

| | Count |
|---|---|
| Rows in → work items out | **35 → 35** |
| `contract_basis` VARIATION | **17** |
| — of which the exact string `variation` | 16 |
| — qualified: **WS34** `variation (Amendment 1)` | 1 |
| BASELINE | 17 |
| UNKNOWN — **WS17**, `?` | 1 |
| BLOCKED | 11 |
| — client dependencies (notice issued) | **10** |
| — supplier's own action (**WS18**, no notice) | 1 |
| Compound scope links (`2->8`, `3+5`, `1/2`, `4/8`) | 4 |
| Data-quality findings | 6 |

**Two corrections to the recommendation paper.** It said 20 variations (it is 17)
and eleven notices (it is 10 — WS18's next action is *"Dada to execute Phase 1"*,
which is not a client dependency and must not receive a notice; issuing one would
be wrong and would cost credibility on the other ten).

## 3. The finding that shaped the design

**WS34's `contract_basis` is the literal string `variation (Amendment 1)`.** An
exact-match filter on `variation` drops it silently. That row is JRBY Cancer
Institute — an entire covered entity — and it is also the entity whose coverage
depends on the very amendment named in the string.

So the importer normalises rather than matches, keeps the raw value beside the
normalised one, and a test asserts both. The acceptance test in the paper was
written against the wrong number and would have passed on a lossy import.

This is the same class of defect as the record's own rule: *flags are counted,
never filtered out.* The importer refuses to exit zero if rows in ≠ rows out.

## 4. What is deliberately absent

Named so the omission is a decision, not a gap. None is started:

- CMDB / configurations (needed for a per-asset maintenance export at inspection)
- Service catalogue tables (the ConnectWise Type/Subtype/Item taxonomy)
- Contacts, companies, boards (the desk holds these)
- Invoicing (the spine produces an invoice's evidence, not the invoice)
- **The ticket ↔ variation adapter.** This is the completeness critic's blocking
  gap: effort can be banded against the 35 workstreams but not against tickets,
  so a hospital-wide uplift claim cannot yet be evidenced from ticket effort.
  It is the next build if the variation is approved.

## 5. The fence

The register is **not** committed — it carries internal network addresses and a
filename on the inventory denylist, and is read at runtime from a path argument.
`tests/fixtures/register-sample.csv` is **synthetic**: the same shape and the same
edge cases, invented content. Commercial amounts are not seeded; `seed/` carries
structure only. A CI step greps the tree for private network addresses and fails
the build if one appears.

## 6. What this does not touch

No PMC server. This container has no LAN route. Nothing here has been run against
SQL Server, Azure SQL, or the live register file.

## 7. Files

```
platform/psa-spine/
  README.md
  schema/001_core.sql · 002_commercial.sql · 003_delivery.sql
  seed/entities.csv · scope_items.csv · instruments.csv · annex_b_categories.csv
  psaspine/db.py · register.py · reports.py · __main__.py
  tests/test_spine.py · tests/fixtures/register-sample.csv
.github/workflows/psa-spine.yml
docs/WS36-psa-recommendation-20260909.md   (the decision paper + completeness critic)
docs/WS36-psa-spine-built-20260909.md      (this file)
```
