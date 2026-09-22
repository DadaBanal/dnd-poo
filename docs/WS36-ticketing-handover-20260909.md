# WS36 — ticketing handover, 9 September 2026

For the session that takes this on. Written so it can be picked up cold.

## The one thing to know before planning anything

**A Claude Code cloud session cannot reach `DND-SQL01`.** The only environment on
this account is `anthropic_cloud`, which has no route to PMC's network — the same
limitation this session has had throughout. So "post directly to the SQL Server"
splits in two:

| Part | Where it can run |
|---|---|
| Write the T-SQL, the importer, the reports, the tests | A cloud session. Anywhere. |
| **Execute** anything against `DND-SQL01\PMC_SS` | A machine with a route. Dada's, or a PMC box. |

Build everything so it can be handed over as a script and run by someone with a
route. Do not design anything that assumes a live connection from the agent.

## What exists now

`platform/psa-spine/`, SQLite, Python 3.11 standard library only, 23 tests
passing.

| | |
|---|---|
| `schema/001_core.sql` | entities, sites, instruments, the nine scope items, fee lines |
| `schema/002_commercial.sql` | variations as a nine-state machine, notices, client dependencies, reclassification, decision notes |
| `schema/003_delivery.sql` | work items, banded time entry, capacity, documents, data quality, audit |
| `schema/004_catalogue.sql` | **new** — boards, families, components, a shared verb set, curated triples, clinical floors, SLA targets |
| `schema/005_ticket.sql` | **new** — the ticket, handovers, priority overrides, and the two triggers that are the gate |
| `psaspine/register.py` | imports the workstream register losslessly |
| `psaspine/reports.py` | Annex B register, dependency notices, instrument exceptions, the variation paper |

Seeded: 15 boards, 20 families, 56 components, 7 verbs, 51 catalogue items,
4 clinical floors, 21 SLA targets. **None of it is live, signed, or enforced** —
see the rules below, which are the reason.

## The gate, which was the blocking gap

A ticket is a `work_item` with `source = 'desk'`; `003` already documented the id
as *"'WS23', later 'ITO-1723'"*. So `time_entry` hangs off a ticket unchanged and
ticket effort reaches a variation the same way a workstream's does.

Two triggers enforce the commercial rule:

- `time_entry_requires_a_variation` — a variation-path ticket cannot consume
  effort while no variation is attached.
- `ticket_close_requires_a_variation` — nor can it be closed.

In the schema, not the importer, because an importer can be bypassed and a
trigger cannot. **Both must survive the SQL Server port.** `RAISE(ABORT, …)`
becomes `THROW` inside a trigger that rolls back.

## What to build next, in order

**1. The SQL Server port.** Target `DND-SQL01\PMC_SS`, a `psa` schema. Generate
it from `schema/*.sql` with a translator under `tools/`, and add a drift check,
so the two can never disagree. Do not hand-maintain a second copy.

Constructs that need real decisions, not defaults:
- `INTEGER PRIMARY KEY` is a rowid alias. `INT IDENTITY(1,1) PRIMARY KEY`.
- `TEXT` everywhere. Pick `NVARCHAR` widths deliberately; `MAX` only for note and
  detail columns. The register's free-text cells run to thousands of characters.
- Dates are stored as the source wrote them, `'20260904'` **and** `'2026-09-09'`
  both appear. Keep them as text on the port and add parsed columns separately;
  converting on the way in loses which shape the source used.
- `REAL` for `band_hours` and `eac_percent`. `DECIMAL`, not `FLOAT` — these reach
  an invoice.
- The two triggers, and the `CHECK (length(trim(reason)) >= 15)` on
  `priority_override`.
- Make it idempotent and refuse to run twice over existing objects.

**2. The desk-export importer.** `psaspine/tickets.py`, modelled on
`register.py`. Read an **export file**, never the API — see the fence. Every row
becomes exactly one work item plus one ticket; anything unclassifiable is
imported *and* flagged, never dropped. Default the scope item and the contract
basis from `catalogue_item`; compute the priority, never read it.

```
priority = LEAST( matrix(impact, urgency),
                  catalogue_item.min_priority,
                  P2 when catalogue_item.clinical_impact = 1 )
```

**3. The uplift evidence.** The report the whole spine exists to produce: effort
by contract basis, per entity, per month, with the variation-path effort
separated and every UNKNOWN-basis ticket listed as a decision somebody owes.

## Rules that are not negotiable

These are enforced in the schema. Do not relax one to make a port easier.

- **No named owner, no live board.** Fifteen boards seed, none live.
- **A BASELINE catalogue item must name its baseline heading.** Twenty-one items
  seed as UNKNOWN — PACS, imaging, medical gas, patching, end-user hardware —
  because none of the nine headings covers them. Forcing them into the nearest
  heading is the quiet reclassification the spine exists to prevent.
- **A clinical floor is signed by the Chief of Hospital, the Chief Nurse and the
  Quality officer.** All four seed PROPOSED. None is Dada IT's to sign.
- **Every SLA target ships `enforced = 0`.** The agreement contains no response
  or resolution commitment and three clauses disclaim creating one. Enforcement
  would create an obligation Dada IT is not paid for.
- **Flags are counted, never filtered out.** The importer exits non-zero if rows
  in ≠ rows out.

## The fence

- **Never** commit patient identifiers or patient names, passwords, hashes,
  tokens, API keys or SMTP secrets, `.env`, or anything on the record's
  inventory denylist.
- **Never use or record the TeamsWork API keys.** They were exposed in a
  screenshot; the standing instruction is that only the read-only key is ever
  used and neither is written down. Both should be rotated. Read an **export**.
- **No internal IP addresses or network topology.** Hostnames and service names
  are fine: `DND-SQL01\PMC_SS`, `PMC-ORTHANC01`, `imaging.pmcne.ph`.
- Label every claim **MEASURED**, **VERIFIED** (with the URL, read today),
  **INFERRED** or **NOT VERIFIED**. Never present an inference as a measurement.

## Production T-SQL discipline

Anything that will run against a live database: `@Apply = 0` preview by default,
a verify gate, a backup table, exact keys in the WHERE, and the rollback in the
comments. The same shape as the imaging installer in this repo, which previews
by default and reverses itself if the service does not come back.

## Still undecided, and not for the agent to decide

- Whether the variation is approved. Everything downstream of the uplift claim
  waits on that.
- Who owns each board, and who deputises.
- Whether the clinical floor list is signed, and by whom.
- Whether PACS, imaging and medical gas are inside any baseline heading. Twenty-one
  catalogue items are UNKNOWN pending that ruling.
