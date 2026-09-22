# WS36 — D4 and D5 closed, and what is still open

**22 September 2026.** Supersedes nothing; this is the first dated record of
these two decisions. The open ones below are restated from
`WS36-psa-build-scope-20260909.md` §13 and are not re-argued here.

This file records decisions and what was built against them. The programme
record in OneDrive `Documents/Claude` remains the master; this is the repo side,
for the decisions whose evidence is code in this repository.

---

## D4 — ticket numbering. **CLOSED.**

**Decision: one `PMC-` sequence across every board, with the desk's own
reference kept beside it, not replaced.**

§13 rated this *"cheap now, very expensive after the first thousand tickets"*.
Phase C opens intake to roughly 400 staff and is precisely what produces the
first thousand, so it closes before intake rather than after.

**Why one sequence and not one per board.** A ticket moves board — that is what a
handover is (`005_ticket.sql`, and §5.3) — and a number that belongs to the board
it started on has only two futures: it follows the ticket and stops matching its
own board, or it is reissued and stops being a reference. A hospital-wide number
survives the handover, which is the one thing a ticket number has to do.

**Built** (MEASURED, this repository, 22 Sep 2026):

- `schema/014_numbering.sql` — `ticket_number`, append-only, and
  `ticket_numbering`, which holds the prefix and padding in **exactly one row**
  (a CHECK enforces it, so there is never a question of which prefix is in
  force).
- `psaspine/numbering.py` — `issue()`, `bind()`, `unbound()`.
- 8 tests in `tests/test_spine.py::TicketNumberingTest`.

**Three properties worth stating, because each is a decision somebody could take
differently:**

1. **A number is never reused.** `issue()` takes the next `INTEGER PRIMARY KEY`
   rather than computing `max+1`, because two callers computing `max+1` at once
   is how a sequence issues one number twice. Gaps are fine; a reused number is
   a reference pointing at two tickets, which is worse than a gap.
2. **Issue and bind are two steps.** A number spent and then abandoned stays
   visible as exactly that, rather than leaving an unexplained hole. `unbound()`
   reports them and nothing reclaims them.
3. **The prefix is configuration, not a constant** — §12 is explicit that
   anything PMC cannot change without a deployment is in the wrong place. The
   seed row lives in `db.seed()` because `schema/*.sql` is DDL only and the
   translator refuses a statement it does not recognise rather than guessing what
   a seed `INSERT` becomes on SQL Server.

**On `legacy_ref`.** §13 named a `legacy_ref` column. `ticket.external_ref`
already carries *"what the desk calls it, kept verbatim"* (`005_ticket.sql`), so
the requirement was already met and a second column meaning the same thing was
not added. Imported history keeps its own id: renumbering historical rows would
break every reference anybody has written down, and `numbering.bind()` no-ops on
an id that was never ours to issue.

---

## D5 — rule condition vocabulary. **CLOSED.**

**Decision: adopt ConnectWise's `WorkflowTrigger` shape — conditions are data —
rather than an expression language.**

§13 already called this *"largely answered"*. It is confirmed here because it was
**built that way in Phase A and never formally closed**, which is how a decision
quietly becomes an assumption.

**Already built** (MEASURED): `schema/008_workflow.sql` declares the field
vocabulary as rows (`workflow_trigger`), and `psaspine/rules.py` carries an
`OPERATORS` table of comparisons with no expression parser and no `eval`. An
unknown field raises `UnknownField` rather than silently evaluating False — a
rule that silently never fires is worse than one that refuses to load.

**Why it matters beyond tidiness:** security and testability, as §13 says. An
expression language in a rules engine is an execution surface, and this one runs
on a clinical desk.

---

## Still open, and what each blocks

| | Decision | What it blocks | Whose |
|---|---|---|---|
| **D6** | Is Phase A funded as a variation, and at what number? | §1.4 — the AUD 6,500 spine line does not cover it. Commercial, not code. | Dada |
| **D7** | SQLite, SQL Server Express, or an existing instance | Names the deployment target; the deploy script must refuse any other. Separation from the live HIS, which carries a 173-finding audit, `sa` enabled and the Domain firewall off. | Dada + PMC |

**D7 is not the same decision as ADR-001.** ADR-001 is the *imaging index*
(Orthanc, SQL Server/ODBC → PostgreSQL); D7 is the *PSA spine's* store. They are
two different questions that both contain the words "SQL Server", and conflating
them is how one of them gets decided by accident. ADR-001 remains **Proposed**
and nothing in this repository may depend on it.

---

## Not a decision, and still open: the PIA

**[NOT VERIFIED]** Whether a Privacy Impact Assessment is required before
hospital-wide rollout, and who signs it. §6.1 says to ask PMC's Data Protection
Officer **before** Phase C, not after. Two of §6.1's four requirements are now
code (see `013_intake.sql` and `psaspine/phi.py`); that does not answer this
question, and building the controls is not the same as being cleared to roll out.
