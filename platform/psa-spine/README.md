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
python3 tests/test_spine.py          # 266 tests
```

Python 3.11+, standard library only. No packages and no network; the Phase B
desk adds an optional server, and it too is standard library (`wsgiref`) — see
below.

`import-tickets` reads an **export file**. There is no API client in this
repository and nowhere to put a key: the TeamsWork keys were exposed in a
screenshot, neither is ever written down, and both should be rotated. A test
asserts the module contains no credential-shaped code.

## The fulfiller desk (Phase B)

The engine computes every SLA number but a person could only reach it from
Python. Phase B is the desk that puts it in front of Dada IT — the phasing gate
is that *Dada IT runs its own work on it before anyone at PMC is asked to*.

```bash
python3 -m psaspine serve spine.db --host 127.0.0.1 --port 8080
```

A standard-library WSGI app (`psaspine/web/`), run for the pilot by
`wsgiref.simple_server`. Zero packages, so the same WSGI callable drops behind a
production server in Phase C with no code change; a test wraps it in
`wsgiref.validate.validator()` to prove PEP 3333 conformance. It is **LAN only,
Dada IT only** and refuses to bind to a public interface. Seven surfaces: the
board, one ticket, dispatch/triage, the closed loop, the on-call rota, an admin
surface, and the uplift evidence screen (§7 — a first-class screen, not an
export).

**Two ways in.** Entra SSO is the normal path and the only one for everyone but
the on-call rota; its RS256 token check is written out in pure Python (no crypto
dependency) and is **NOT VERIFIED** against a real tenant — proven against a
synthetic key in the tests, run against Entra by somebody who has a route to it,
the way the SQL Server port is. Break-glass local accounts are the WAN-down
fallback (§11 test 10), sealed and scrypt-hashed:

```bash
python3 -m psaspine create-local-account spine.db --username oncall
```

The password is read from a no-echo prompt, never an argument or an environment
variable; the account is seeded into no repository; every login is audited. The
web offers no way to mint one — creation is CLI-only, and a test asserts there is
no route. The credential table lives in `schema/local/`, outside the `schema/*.sql`
glob, so it is applied to the local pilot database and **never** ported to the
commercial spine on `DND-SQL01`.

**The restricted-board guarantee.** A restricted board's tickets are filtered by
`board_member` at every query, for everyone — the sysadmin flag unlocks
cross-board configuration, never a restricted board's contents. This is §11 test
5, the acceptance test the record wrote and never ran: a non-member is *provably*
excluded, and a test asserts a non-member gets a 404, not a leak.

## Requester intake (Phase C)

Phase C opens the desk to the ~400 staff who raise work, which is what makes the
hospital-wide case evidenceable — and what scales the §6.1 PHI exposure unless
the controls land first. They did:

- **A ticket references a patient record and never carries one.**
  `013_intake.sql` adds `patient_reference`, held only on a restricted board by
  two triggers (insert and update). `psaspine/phi.py` detects identifiers at
  every intake path and flags them in `data_quality` — **naming the shape and
  the field, never the value**, because `detail` is read by reports. The ticket
  still imports: refusing it sends the identifier to the telephone, where
  nothing records it.
- **Every read of a restricted ticket is audited** — `RESTRICTED_READ`, with the
  ticket, the actor and which door they came through.
- **One ticket sequence (D4).** `PMC-000001`, hospital-wide, never reused; the
  prefix is a row, not a constant (§12). See
  [`docs/WS36-decisions-d4-d5-20260922.md`](../../docs/WS36-decisions-d4-d5-20260922.md).

Three ways in, each idempotent where it can be:

```bash
python3 -m psaspine import-mail spine.db ./drop --channel helpdesk   # RFC 822 files
python3 -m psaspine create-api-token spine.db --label "orthanc monitoring" --board IT_HELP
```

| Path | Who | The rule that matters |
|---|---|---|
| `/my` (portal) | a requester | Ownership, not board membership, is the filter. Reads `customer_description`, never the internal status name. |
| `import-mail` | the helpdesk mailboxes | Keyed by Message-ID, so a re-run makes no second ticket; replies thread by In-Reply-To. Kills the MEASURED double-creation at the intake end. |
| `/api/v1/tickets` | monitoring, the archive | A local token (§6.2 — the WAN-down alarm cannot fetch an Entra token), sha256 only, one board, tokens only. Priority computed from impact × urgency, never asserted. A `dedup_key` holds one open ticket per alert. |

API tokens live in `schema/local/` beside the break-glass accounts and are
never ported to SQL Server.

**NOT VERIFIED:** whether a Privacy Impact Assessment is required before
hospital-wide rollout. §6.1 says ask PMC's Data Protection Officer before Phase
C goes live. Building the controls is not the same as being cleared to use them.

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
