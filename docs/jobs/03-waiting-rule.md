Status: done 15 Oct 2026, built, not live — the pull and restart are Dada's word (runbook Part 124)

# Job 03 — Dada's rule for tickets waiting on someone outside the desk

**First:** read `platform/psa-spine/CLAUDE.md` — it says which skills to load and the rules every job follows.

**Source, with his words verbatim:** `docs/handoffs/HANDOFF-sql01-cloud-WS36-20261015-waiting-rule.md`.

**The rule:** in *Awaiting approval* or *Waiting on Requester* both clocks stop; respond is met by the status move
(ConnectWise's rule — the desk already carries the escalation statuses); at 3 days a reminder goes out (to the
requester; on *Awaiting approval* to both approver and requester); at 3 more the ticket closes with the reopen
sentence; a reply by email or portal reopens it (exists).

**Do:**
1. Stop **both** clocks on `NO_ESCALATION` statuses (today only resolve pauses — the "Breached by 28h" defect).
2. Respond met by the move from a *not responded* status to any other.
3. A time-in-status trigger (the rules engine only has age-since-opened), and two outbox kinds:
   `WAITING_REMINDER` and `CLOSED_NO_RESPONSE`, each with an approval and a response wording.
4. The no-response close goes to `>Closed` with the reason, never *Resolved*.

**Not this job:** department approvers (Dada's to set). **Done when:** tests for each step, suite green, committed,
one runbook paragraph; the restart is Dada's word.
