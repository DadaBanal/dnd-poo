# psa-spine — the commercial half of a PSA

The half no PSA on the market ships: a fixed monthly fee against nine numbered
baseline scope items, with everything else a named variation under Annex B,
notices that condition every commercial right, and client dependencies that are
only claimable once written notice exists.

**The ticket desk is not here and is not being replaced.** That was the
conclusion of WS36 — see [`docs/WS36-psa-recommendation-20260909.md`](../../docs/WS36-psa-recommendation-20260909.md).
The incumbent is USD 88.50 per organisation per month with unlimited users, so
replacing it saves nothing and costs 9×–58× at the seat counts intended. What is
expensive is that nothing records which work is baseline, which is a variation,
and which client delay was ever put in writing. That is what this builds.

## What it produces

Three artefacts, from data, needing no licence and no approval:

| Artefact | What it is |
|---|---|
| **Annex B variation register** | Every workstream the register itself classifies as outside the nine baseline items, in the agreement's own Annex B shape. Discharges an action open since the register was written. |
| **Client dependency notices** | One dated written notice per workstream blocked on the client. The entitlement to relief is conditioned on notice, and today not one is recorded. |
| **Instrument exception report** | Every fee line and covered entity resting on an instrument nobody has signed. |

Plus a data-quality summary, because the standing rule here is that flags are
**counted, never filtered out**.

## Run it

```bash
cd platform/psa-spine
python3 -m psaspine init spine.db
python3 -m psaspine import spine.db /path/to/PMC_Workstream_Register_YYYYMMDD.csv --run-id r1
python3 -m psaspine import-tickets spine.db /path/to/desk-export.csv --run-id desk-1
python3 -m psaspine report spine.db --out ./out --run-id desk-1 --capacity-hours 160
python3 tests/test_spine.py          # 83 tests
```

Python 3.11+, standard library only. No packages, no server, no network.

`import-tickets` reads an **export file**. There is no API client in this
repository and nowhere to put a key: the TeamsWork keys were exposed in a
screenshot, neither is ever written down, and both should be rotated. A test
asserts the module contains no credential-shaped code.

## Measured against the real register

35 rows in, 35 work items out. **17 variation · 17 baseline · 1 unknown (WS17).**
11 rows BLOCKED, of which **10 are client dependencies** — WS18 is blocked on the
supplier's own action and correctly gets no notice. 4 compound scope links, 6
data-quality findings.

Two of those numbers contradict the WS36 paper, which said 20 variations and 11
notices. The code is right and the paper carries a correction block.

### The row that gets lost

`WS34.contract_basis` is the literal string **`variation (Amendment 1)`**. An
exact-match filter on `variation` drops it, and that row is an entire covered
entity. `normalise_basis()` exists to make that mistake impossible rather than
something to be remembered, and a test asserts it.

## The SQL Server port

`schema/*.sql` is the one schema. The copy that runs on `DND-SQL01\PMC_SS` is
**generated** from it:

```bash
python3 tools/sqlite_to_tsql.py --write     # regenerate sqlserver/
python3 tools/sqlite_to_tsql.py --check     # drift gate; CI runs this
```

Two copies of a commercial rule drift, and the copy that drifts is the one nobody
reads — which here would be the one on the live server. So there is no
hand-maintained second schema and the build fails if the committed T-SQL is not
what the source produces today.

The translator **refuses rather than guesses**. Every NVARCHAR width and every
DECIMAL precision is a named decision in `tools/tsql-decisions.json`; a column
missing from that file stops the build, as does an unrecognised statement, an
unknown function inside a CHECK, or a width narrower than the CHECK beside it.

| Construct | Port | Why |
|---|---|---|
| `INTEGER PRIMARY KEY` | `INT IDENTITY(1,1)` | It is a rowid alias, not an integer column |
| `TEXT` | `NVARCHAR(n)`, `MAX` only for notes and details | The register's free-text cells run to thousands of characters; a name is not a note |
| `REAL` | `DECIMAL` | These numbers reach an invoice |
| dates | `NVARCHAR` **plus** a parsed computed column | `'20260904'` and `'2026-09-09'` both appear, and which shape the source used is itself evidence |
| `RAISE(ABORT, …)` | `THROW` in an AFTER trigger that rolls back | SQL Server has no BEFORE trigger. The write is still refused; the blast radius is larger, and the generated file says so |

`sqlserver/PMC_PSA_Spine_SqlServer.sql` previews by default (`@Apply = 0`),
refuses to run twice over existing objects, verifies its own object counts inside
the transaction before committing, and carries its rollback in the footer.

**NOT VERIFIED.** It has never been executed. No environment on this account has
a network route to `DND-SQL01`, so it is written to be handed to somebody who
has one. Run it with `@Apply = 0` first and read the plan.

## Design notes

**Losslessness is the headline invariant.** Every input row produces exactly one
work item. Anything unclassifiable is imported *and* flagged. The CLI exits
non-zero if rows in ≠ rows out.

**Compound scope values become two links each.** The register carries `2->8`,
`3+5`, `1/2`, `4/8`; the separator carries meaning, so it survives as the link
relation rather than being discarded.

**A variation is a state machine, not a flag.** Nine states, including
`PERFORMED_WITHOUT_APPROVAL` — work done on best efforts without waiving the
right to fees. No off-the-shelf PSA can express it, which is why that work
currently disappears.

**A decision note cannot be back-dated.** `CHECK (advisory_at <= decision_at)`.
Advice written after the decision is worth nothing, so the schema refuses it.

**SQLite, deliberately.** No server, no provisioning, no procurement, and one
file that can be escrowed nightly to client-controlled storage. It is also still
the source of the SQL Server schema rather than a thing that was replaced by it —
see the port above. Nothing here has been run against SQL Server, and that
remains **NOT VERIFIED**; what changed is that the T-SQL is now generated and
drift-checked instead of being a claim about portability.

## What is deliberately not here

Named so the omissions are a decision rather than a gap. Each is Phase 4+ and
none is started:

- **CMDB / configurations** — needed for the per-asset maintenance export a DOH
  inspection would ask for, and for medical devices as configuration items.
- **Service catalogue tables** — the ConnectWise Type/Subtype/Item taxonomy.
- **Contacts, companies, boards** — the desk holds these today.
- **Invoicing** — the spine produces the evidence for an invoice, not the invoice.
- **Effort capture from the desk.** `import-tickets` writes work items and
  tickets, never `time_entry`. Effort is banded by a person — the schema requires
  a performer, an enterer, a charge method and an authority source, and a desk
  export carries none of them reliably. An importer that invented those four
  would be inventing the numerator of an uplift claim.
- **Seeding the SQL Server copy.** The generated script creates structure only.
  No fee amount, no board owner and no signed clinical floor: each is a decision
  with a name attached that nobody has made yet.

The ticket ↔ variation adapter is no longer on this list. `psaspine/tickets.py`
puts tickets in `work_item`, `time_entry` already hangs off a work item, and
`reports.uplift_evidence` produces the claim — see the two triggers in `005`,
which are why a variation-path ticket cannot consume effort or close without a
variation attached.

## The repository fence

The register itself is **not** in this repository. It carries internal network
addresses and at least one filename on the record's inventory denylist, so it is
read at runtime from a path given on the command line. `tests/fixtures/` holds a
**synthetic** register of the same shape — same edge cases, invented content.

Commercial amounts are likewise not seeded. `seed/` carries structure only: the
nine scope-item headings, the entities, the instruments and their execution
status. The fee schedule loads at runtime from a file held outside git.
