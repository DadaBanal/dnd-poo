"""The three artefacts the spine exists to produce.

None of them needs a ticket desk, a licence or an approval. All three are
generated from data, so they stop being things somebody has to remember to
write.

  annex_b        the variation register, in the agreement's own Annex B shape
  dependency_notices  one dated written notice per workstream blocked on the client
  instrument_exceptions  everything resting on an instrument nobody has signed
"""
from __future__ import annotations

import sqlite3
from datetime import date

from . import db


def _d(value: str | None) -> date | None:
    """Parse the register's two date shapes: '20260904' and '2026-09-09'."""
    text = (value or "").strip()
    try:
        if len(text) == 8 and text.isdigit():
            return date(int(text[:4]), int(text[4:6]), int(text[6:]))
        if len(text) == 10 and text[4] == "-":
            return date.fromisoformat(text)
    except ValueError:
        pass
    return None


def days_outstanding(last_activity: str | None, as_of: date) -> int | None:
    started = _d(last_activity)
    return (as_of - started).days if started else None


# ------------------------------------------------------------------ Annex B

def annex_b(conn: sqlite3.Connection, *, as_of: date) -> str:
    rows = conn.execute(
        "SELECT w.work_item_id, w.name, w.entity_id, w.contract_basis_raw, w.status,"
        "       w.last_activity, w.risk"
        "  FROM work_item w WHERE w.contract_basis = 'VARIATION'"
        " ORDER BY w.work_item_id"
    ).fetchall()
    unknown = conn.execute(
        "SELECT work_item_id, name, contract_basis_raw FROM work_item"
        " WHERE contract_basis = 'UNKNOWN' ORDER BY work_item_id"
    ).fetchall()

    out = [
        "# Annex B — Variation Register",
        "",
        f"Generated {as_of.isoformat()} from the workstream register. "
        "Every row below is work already performed or in progress that the register itself "
        "classifies as outside the nine baseline scope items.",
        "",
        "Annex B categories available (assign each row before issue):",
        "",
    ]
    for cat in db.annex_b_categories():
        out.append(f"- **{cat['category']}** — {cat['description']}")
    out += [
        "",
        f"## Variations on the register — {len(rows)}",
        "",
        "| Ref | Workstream | Entity | Status | Risk | Days since activity | Basis as recorded |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        days = days_outstanding(r["last_activity"], as_of)
        out.append(
            f"| {r['work_item_id']} | {r['name']} | {r['entity_id']} | {r['status']} | "
            f"{r['risk'] or '—'} | {days if days is not None else '—'} | {r['contract_basis_raw']} |"
        )

    out += ["", "## Not yet classified", ""]
    if unknown:
        out.append("These carry no contract basis in the register and are counted, not dropped:")
        out.append("")
        for r in unknown:
            out.append(f"- **{r['work_item_id']}** {r['name']} — recorded basis `{r['contract_basis_raw']}`")
    else:
        out.append("None.")

    out += [
        "",
        "---",
        "",
        "**Note on completeness.** This register is generated from the workstream CSV and "
        "reflects what that file records. It is not evidence that any of these variations was "
        "notified, priced or approved — see the variation state machine in the spine, where "
        "every row starts at IDENTIFIED until a notice exists.",
    ]
    return "\n".join(out) + "\n"


# -------------------------------------------------------- dependency notices

def blocked_on_client(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Blocked workstreams whose next action sits with someone other than Dada."""
    return conn.execute(
        "SELECT work_item_id, name, entity_id, blocked_on, next_action, next_action_by,"
        "       risk, last_activity, contract_basis"
        "  FROM work_item"
        " WHERE status = 'BLOCKED'"
        "   AND LOWER(COALESCE(next_action_by,'')) <> 'dada'"
        " ORDER BY work_item_id"
    ).fetchall()


def dependency_notices(conn: sqlite3.Connection, *, as_of: date) -> dict[str, str]:
    """One notice per blocked workstream, keyed by a filename stem.

    The entitlement to relief is conditioned on written notice having been given.
    Today not one notice is recorded against any blocked workstream, so every
    day of client delay is currently absorbed rather than claimed.
    """
    notices: dict[str, str] = {}
    for r in blocked_on_client(conn):
        days = days_outstanding(r["last_activity"], as_of)
        wid = r["work_item_id"]
        body = [
            f"# Notice of Client Dependency — {wid}",
            "",
            f"**Date:** {as_of.isoformat()}  ",
            f"**Entity:** {r['entity_id']}  ",
            f"**Workstream:** {wid} — {r['name']}  ",
            f"**Addressed to:** {r['next_action_by'] or 'PMC'}  ",
            f"**Contract basis:** {r['contract_basis']}",
            "",
            "## What is outstanding",
            "",
            f"{r['blocked_on'] or 'A decision or input from the client.'}",
            "",
            "## Effect",
            "",
            "The next action on this workstream cannot be taken by the supplier:",
            "",
            f"> {r['next_action'] or 'Awaiting the client.'}",
            "",
            # State only what the register supports. last_activity is when the row
            # was last touched, not when the dependency was raised, so the letter
            # says exactly that rather than claiming a longer delay it cannot prove.
            (f"The register records no activity on this workstream for **{days} days** "
             f"(last activity {r['last_activity']})."
             if days is not None else
             "The register records no date of last activity for this workstream."),
            "",
            "## Purpose of this notice",
            "",
            "This notice is given so that the delay is recorded as a client dependency rather "
            "than a supplier delay. It is not an escalation and no action is required beyond "
            "the outstanding item above.",
            "",
            "Please confirm receipt.",
            "",
            "---",
            "",
            "_Generated from the workstream register. One notice per blocked workstream._",
        ]
        notices[f"Notice_{wid}_{as_of.strftime('%Y%m%d')}"] = "\n".join(body) + "\n"
    return notices


# ----------------------------------------------------- instrument exceptions

def instrument_exceptions(conn: sqlite3.Connection, *, as_of: date) -> str:
    """What is resting on an instrument that is not executed.

    The first output of this report is uncomfortable, and that is the point.
    """
    instruments = conn.execute(
        "SELECT * FROM instrument ORDER BY execution_status, instrument_id"
    ).fetchall()
    unexecuted = [i for i in instruments if i["execution_status"] != "EXECUTED"]
    fees = conn.execute(
        "SELECT f.*, i.execution_status FROM fee_line f"
        " JOIN instrument i ON i.instrument_id = f.instrument_id"
        " WHERE i.execution_status <> 'EXECUTED'"
    ).fetchall()
    uncovered = conn.execute(
        "SELECT entity_id, name, note FROM entity WHERE is_covered = 0 AND entity_id <> 'DADA-IT'"
    ).fetchall()

    out = [
        "# Instrument Exception Report",
        "",
        f"Generated {as_of.isoformat()}.",
        "",
        "## Instruments and their execution status",
        "",
        "| Instrument | Kind | Effective from | Execution status | Note |",
        "|---|---|---|---|---|",
    ]
    for i in instruments:
        out.append(
            f"| {i['instrument_id']} | {i['kind']} | {i['effective_from'] or '—'} | "
            f"**{i['execution_status']}** | {i['note'] or ''} |"
        )

    out += ["", f"## Not executed — {len(unexecuted)}", ""]
    if unexecuted:
        out.append(
            "Nothing below is a binding basis for invoicing or for treating an entity as covered:"
        )
        out.append("")
        for i in unexecuted:
            out.append(f"- **{i['instrument_id']}** — {i['title']} (`{i['execution_status']}`)")
    else:
        out.append("None.")

    out += ["", f"## Fee lines resting on an unexecuted instrument — {len(fees)}", ""]
    if fees:
        out.append("| Fee line | Entity | Description | Instrument | Status |")
        out.append("|---|---|---|---|---|")
        for f in fees:
            out.append(
                f"| {f['fee_line_id']} | {f['entity_id']} | {f['description']} | "
                f"{f['instrument_id']} | **{f['execution_status']}** |"
            )
    else:
        out.append(
            "No fee lines are loaded. Amounts are held outside this repository and load at "
            "runtime; run the loader before relying on this section."
        )

    out += ["", f"## Entities not covered by an executed instrument — {len(uncovered)}", ""]
    for e in uncovered:
        out.append(f"- **{e['entity_id']}** — {e['name']}. {e['note'] or ''}")

    out += [
        "",
        "---",
        "",
        "**Why this report exists.** The agreement requires amendments to be recorded in "
        "writing and signed by both parties to bind. Where an instrument is unexecuted, both "
        "the fee it sets and the entities it brings into scope rest on nothing enforceable. "
        "That is a paper problem with a paper fix, and it is cheaper to fix than anything "
        "else in the programme.",
    ]
    return "\n".join(out) + "\n"


# ------------------------------------------------------------ data quality

def data_quality_summary(conn: sqlite3.Connection, run_id: str) -> str:
    rows = conn.execute(
        "SELECT severity, code, COUNT(*) n FROM data_quality WHERE run_id = ?"
        " GROUP BY severity, code ORDER BY severity DESC, n DESC", (run_id,)
    ).fetchall()
    out = ["# Import data quality", "", "| Severity | Finding | Count |", "|---|---|---|"]
    for r in rows:
        out.append(f"| {r['severity']} | {r['code']} | {r['n']} |")
    if not rows:
        out.append("| — | nothing flagged | 0 |")
    out += ["", "Findings are counted, never filtered. Every input row was imported."]
    return "\n".join(out) + "\n"


# --------------------------------------------------------- the variation paper

def variation_paper(conn: sqlite3.Connection, *, as_of: date,
                    category: str = "OPERATIONAL_TICKETING",
                    eac_percent: float | None = None,
                    capacity_hours: float | None = None) -> str:
    """The paper that asks the client to fund the work, built from the register.

    Every number in it is counted from data rather than typed, because the one
    thing that reliably sinks an uplift claim is a figure the client's finance
    function can question and the supplier cannot source.
    """
    variations = conn.execute(
        "SELECT work_item_id, name, entity_id, status FROM work_item"
        " WHERE contract_basis = 'VARIATION' ORDER BY work_item_id").fetchall()
    deps = blocked_on_client(conn)
    unexecuted = conn.execute(
        "SELECT instrument_id, title, execution_status FROM instrument"
        " WHERE execution_status <> 'EXECUTED' ORDER BY instrument_id").fetchall()
    uncovered = conn.execute(
        "SELECT entity_id, name FROM entity"
        " WHERE is_covered = 0 AND entity_id <> 'DADA-IT'").fetchall()
    unknown = conn.execute(
        "SELECT COUNT(*) c FROM work_item WHERE contract_basis = 'UNKNOWN'").fetchone()["c"]
    cat = next((c for c in db.annex_b_categories() if c["category"] == category), None)

    out = [
        "# Variation Paper — service management platform",
        "",
        f"**Date:** {as_of.isoformat()}  ",
        f"**Annex B category:** {category}"
        + (f" — {cat['description']}" if cat else " — *(category not found in the seed list)*"),
        "",
        "## 1. What is being asked for",
        "",
        "Funding for the commercial half of a service-management platform: the register of "
        "agreements, scope items and variations, the notices that condition every commercial "
        "right under this agreement, and the evidence pack the periodic review requires.",
        "",
        "**No new ticketing licence is being requested.** The existing ticket desk is retained. "
        "That is a deliberate saving and it is the reason this paper is small.",
        "",
        "## 2. Why it is a variation and not baseline",
        "",
        f"Annex B already names *{cat['description'].lower()}* as a variation category"
        if cat else "This falls outside the numbered baseline scope items.",
        "",
        "The evidence is the register itself, counted at the date above:",
        "",
        f"- **{len(variations)} workstreams** are already recorded as variations.",
        f"- **{len(deps)} workstreams** are blocked on the client with no notice on file.",
        f"- **{unknown} workstream** carries no contract basis at all."
        if unknown == 1 else
        f"- **{unknown} workstreams** carry no contract basis at all.",
        "",
        "## 3. Work already performed and not billed as a variation",
        "",
        "| Ref | Workstream | Entity | Status |",
        "|---|---|---|---|",
    ]
    for v in variations:
        out.append(f"| {v['work_item_id']} | {v['name']} | {v['entity_id']} | {v['status']} |")

    out += [
        "",
        "Listing is not a claim. Each row above is offered as the basis for classification, "
        "not as an invoice; the ones already delivered are raised so the position is on the "
        "record rather than to be charged retrospectively.",
        "",
        "## 4. The commercial basis",
        "",
    ]
    if eac_percent is not None and capacity_hours is not None:
        out += [
            f"Capacity uplift of **{eac_percent:g}%**, computed against a declared capacity of "
            f"**{capacity_hours:g} hours per calendar month**.",
            "",
            "The denominator is stated here deliberately and is offered for initialling before "
            "the first uplift invoice. An uplift computed against an undisclosed capacity is an "
            "assertion, and it is rejected in one question.",
        ]
    else:
        out += [
            "**Not yet priced.** Two figures have to be set by the supplier and agreed by the "
            "client before this paper can be issued:",
            "",
            "1. the capacity uplift percentage claimed; and",
            "2. **the denominator it is computed against** — the declared available capacity in "
            "hours per calendar month.",
            "",
            "Neither is inferable from the agreement: no rate card exists in any instrument. "
            "Until the denominator is agreed, only a capacity uplift is expressible; a separate "
            "charge has no rate behind it.",
        ]

    out += [
        "",
        "## 5. Ownership, exit and data",
        "",
        "Because the client funds the platform, the following are conditions of this variation "
        "rather than matters to be settled later:",
        "",
        "- the tenancy and subscription are held **in the client's name**, with the client "
        "holding the break-glass credential and the supplier holding administrator access;",
        "- the ticket and register data is **the client's property**;",
        "- a scheduled export in a defined format to client-controlled storage is a contractual "
        "deliverable, not a courtesy;",
        "- return-and-delete applies on termination, and the platform term does not outlast the "
        "agreement.",
        "",
        "A platform the supplier owns and the client pays for is a concentration risk on the "
        "client's side. Naming it here is deliberate.",
        "",
        "## 6. Data protection",
        "",
        "A ticket raised by clinical staff will contain patient information regardless of policy. "
        "A processing schedule naming the client as controller and the supplier as processor is "
        "attached to this variation and is a condition of it, not a follow-up action.",
        "",
        "## 7. Instruments this paper depends on",
        "",
    ]
    if unexecuted:
        out.append("The following are **not executed**. Nothing below is a binding basis for "
                   "invoicing or for treating an entity as covered:")
        out.append("")
        for i in unexecuted:
            out.append(f"- **{i['instrument_id']}** — {i['title']} (`{i['execution_status']}`)")
        if uncovered:
            out.append("")
            out.append("Consequently these entities are not covered by an executed instrument: "
                       + ", ".join(f"**{e['entity_id']}**" for e in uncovered) + ".")
        out += [
            "",
            "**This should be resolved before the variation is issued, not alongside it.** "
            "A variation priced against an unexecuted instrument inherits its weakness.",
        ]
    else:
        out.append("All instruments are executed.")

    out += [
        "",
        "## 8. What the client is asked to do",
        "",
        "1. Confirm which instrument is operative, and execute the outstanding one.",
        "2. Agree the Annex B category and the classification of the rows in section 3.",
        "3. Initial the capacity denominator in section 4.",
        "4. Accept the ownership and exit conditions in section 5.",
        "5. Countersign the processing schedule in section 6.",
        "",
        "---",
        "",
        f"_Generated {as_of.isoformat()} from the workstream register. Counts are as at that "
        "date and change as the register changes._",
    ]
    return "\n".join(out) + "\n"
