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
            f"| {r['work_item_id']} | {r['name']} | {r['entity_id'] or '—'} | {r['status']} | "
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
        out.append(f"| {v['work_item_id']} | {v['name']} | {v['entity_id'] or '—'} | {v['status']} |")

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


# ---------------------------------------------------------- uplift evidence

def _month(value: str | None) -> str:
    """'20260904' and '2026-09-09' both become '2026-09'. Anything else is
    'unknown' — a bucket, never a discard."""
    parsed = _d(value)
    return parsed.strftime("%Y-%m") if parsed else "unknown"


def round_down_to_5(percent: float) -> int:
    """Round to the nearest 5, downward.

    Not free precision: 5 points is a material monthly sum, so the arithmetic is
    made conservative against Dada IT and unarguable against PMC. A number
    rounded up in the supplier's favour is the first thing a finance function
    strikes out.
    """
    return int(percent // 5) * 5


def effort_by_basis(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Banded effort, grouped the three ways an uplift claim has to be defended.

    contract_basis is inherited from the work item and never set per entry, so
    this reads the commercial classification of the work rather than an opinion
    typed by whoever logged the time.
    """
    return conn.execute(
        "SELECT w.entity_id,"
        "       w.contract_basis,"
        "       COALESCE(t.path, 'WORKSTREAM') AS path,"
        "       te.worked_on,"
        "       te.band_hours,"
        "       te.counts_to_capacity"
        "  FROM time_entry te"
        "  JOIN work_item w ON w.work_item_id = te.work_item_id"
        "  LEFT JOIN ticket t ON t.work_item_id = te.work_item_id"
    ).fetchall()


def decisions_owed(conn: sqlite3.Connection) -> dict[str, list[sqlite3.Row]]:
    """Everything on the ticket estate that nobody has ruled on.

    Three separate questions, kept separate because they have three different
    answers and three different people who can give them.
    """
    unknown_basis = conn.execute(
        "SELECT t.work_item_id, t.external_ref, t.board_id, t.priority, t.state,"
        "       t.catalogue_item_id, w.name, w.entity_id"
        "  FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
        " WHERE w.contract_basis = 'UNKNOWN' ORDER BY t.work_item_id"
    ).fetchall()
    closed_unattached = conn.execute(
        "SELECT t.work_item_id, t.external_ref, t.board_id, t.state, w.name, w.entity_id"
        "  FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
        " WHERE t.path = 'VARIATION' AND t.state IN ('RESOLVED','CLOSED')"
        "   AND w.variation_id IS NULL ORDER BY t.work_item_id"
    ).fetchall()
    open_unattached = conn.execute(
        "SELECT t.work_item_id, t.external_ref, t.board_id, t.state, w.name, w.entity_id"
        "  FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
        " WHERE t.path = 'VARIATION' AND t.state NOT IN ('RESOLVED','CLOSED','CANCELLED')"
        "   AND w.variation_id IS NULL ORDER BY t.work_item_id"
    ).fetchall()
    return {"unknown_basis": unknown_basis,
            "closed_unattached": closed_unattached,
            "open_unattached": open_unattached}


def uplift_evidence(conn: sqlite3.Connection, *, as_of: date,
                    capacity_hours: float | None = None) -> str:
    """The report the whole spine exists to produce.

    Effort by contract basis, per entity, per month, with variation-path effort
    kept separate and every UNKNOWN-basis ticket named as a decision somebody
    owes. It is deliberately unflattering in three places:

      * It prints no uplift percentage until a capacity denominator is supplied.
        An undisclosed denominator is the single easiest way for a finance
        function to reject an uplift invoice, and inventing one here would put
        the supplier's own software in charge of both halves of the fraction.

      * It prints the baseline hours next to the variation hours. Those are the
        denominator of any capacity argument and cannot be left out of the
        evidence — but see the note at the foot about publishing them.

      * It counts what is not classified rather than reporting around it. A
        report that quietly drops the UNKNOWN rows shows a cleaner picture of a
        smaller claim.
    """
    rows = effort_by_basis(conn)
    owed = decisions_owed(conn)

    totals: dict[tuple[str, str, str], float] = {}
    variation_path: dict[tuple[str, str], float] = {}
    excluded = 0.0
    for r in rows:
        month = _month(r["worked_on"])
        hours = float(r["band_hours"] or 0)
        if not r["counts_to_capacity"]:
            excluded += hours
            continue
        totals[(r["entity_id"] or "UNCLASSIFIED", month, r["contract_basis"])] = (
            totals.get((r["entity_id"] or "UNCLASSIFIED", month, r["contract_basis"]), 0) + hours)
        if r["path"] == "VARIATION":
            key = (r["entity_id"] or "UNCLASSIFIED", month)
            variation_path[key] = variation_path.get(key, 0) + hours

    declared = conn.execute(
        "SELECT hours_per_month, basis, agreed_by, agreed_on FROM capacity_declaration"
        " ORDER BY effective_from DESC").fetchone()
    denominator = capacity_hours if capacity_hours is not None else (
        declared["hours_per_month"] if declared else None)

    out = [
        "# Uplift Evidence — effort by contract basis",
        "",
        f"Generated {as_of.isoformat()} from banded effort in the spine.",
        "",
        "This is the evidence behind a capacity uplift claim, and it is the reason the "
        "spine exists. Nothing here is an invoice. It is the arithmetic and the narrative "
        "that have to survive a finance function reading them side by side.",
        "",
    ]

    # ------------------------------------------------------------ the numerator
    if not rows:
        out += [
            "## No effort is banded",
            "",
            "**There is no banded effort in this database, so there is no claim to make "
            "from it yet.** That is a finding, not an error. Effort is banded by a person — "
            "`time_entry` requires a performer, an enterer, a charge method and an authority "
            "source, and a desk export carries none of them reliably — and it is banded "
            "**monthly, including for open items**. Banding only at close means the blocked "
            "and the long-running contribute zero, which structurally under-counts exactly "
            "the work that best evidences a capacity claim.",
            "",
            "The decisions owed below stand regardless: they are about classification, not "
            "about hours.",
            "",
        ]
    else:
        out += [
            "## Effort by entity, month and contract basis",
            "",
            "| Entity | Month | Basis | Hours |",
            "|---|---|---|---|",
        ]
        for (entity, month, basis) in sorted(totals):
            out.append(f"| {entity} | {month} | {basis} | {totals[(entity, month, basis)]:.1f} |")
        if excluded:
            out += [
                "",
                f"**{excluded:.1f} hours are recorded and excluded** from every figure above. "
                "Only hours performed by Dada IT personnel count toward capacity; "
                "client-employed fulfiller effort is recorded so it is visible, and excluded "
                "so it is never claimed.",
            ]

        out += ["", "## Variation-path effort, separated", ""]
        if variation_path:
            out += ["| Entity | Month | Variation-path hours | All hours | Share |",
                    "|---|---|---|---|---|"]
            for (entity, month) in sorted(variation_path):
                var = variation_path[(entity, month)]
                allh = sum(v for (e, m, _b), v in totals.items() if e == entity and m == month)
                share = f"{(var / allh * 100):.0f}%" if allh else "—"
                out.append(f"| {entity} | {month} | {var:.1f} | {allh:.1f} | {share} |")
        else:
            out.append(
                "No effort is banded against a variation-path ticket. Either none has been "
                "done, or it has been done and banded against something else — and the "
                "second is what this report exists to make visible."
            )

        # ---------------------------------------------------------- denominator
        out += ["", "## The denominator", ""]
        if denominator is None:
            out += [
                "**Not stated, so no uplift percentage is printed.**",
                "",
                "EAC% is variation hours divided by available capacity, and no instrument "
                "defines available capacity. Without a declared and dated denominator, an "
                "uplift percentage is a self-reported numerator over a self-declared "
                "denominator computed by software written by the party being paid. It gets "
                "rejected in one question, and it deserves to be.",
                "",
                "Declare one with `--capacity-hours`, or record it in `capacity_declaration` "
                "and offer it to the client for initialling. It is a decision, not a "
                "measurement, and it should be signed as one.",
            ]
        else:
            source = (f"declared in the spine as {declared['basis']}"
                      if capacity_hours is None and declared else "supplied for this run")
            agreed = (f"agreed by {declared['agreed_by']} on {declared['agreed_on']}"
                      if declared and declared["agreed_by"] else
                      "**not yet agreed by the client**")
            out += [
                f"Available capacity is taken as **{denominator:g} hours per calendar "
                f"month** ({source}), {agreed}.",
                "",
                "| Entity | Month | Variation hours | EAC% (rounded down to 5) |",
                "|---|---|---|---|",
            ]
            for (entity, month) in sorted(variation_path):
                raw = variation_path[(entity, month)] / denominator * 100
                out.append(f"| {entity} | {month} | {variation_path[(entity, month)]:.1f} | "
                           f"{round_down_to_5(raw)}% |")
            out += [
                "",
                "Rounded to the nearest 5 **downward**, so the arithmetic is conservative "
                "against Dada IT. No monetary amount is printed here: the base monthly fee "
                "is a commercial figure held outside this repository, and the execution gate "
                "has to pass before any fee line is invoiceable at all.",
            ]

    # ------------------------------------------------------- decisions owed
    unknown = owed["unknown_basis"]
    out += ["", f"## Decisions somebody owes — {len(unknown)} tickets with no contract basis", ""]
    if unknown:
        out += [
            "Each of these is work that has been done or is being done, which is neither "
            "claimable as a variation nor absorbed as baseline, because nobody has ruled "
            "which it is. Twenty-one catalogue items seed UNKNOWN for the same reason: none "
            "of the nine baseline headings covers PACS, imaging, medical gas, patching or "
            "end-user hardware. Forcing them into the nearest heading is the quiet "
            "reclassification this spine exists to prevent, so they are listed instead.",
            "",
            "| Ticket | Desk ref | Entity | Board | Priority | State | Summary |",
            "|---|---|---|---|---|---|---|",
        ]
        for t in unknown:
            out.append(
                f"| {t['work_item_id']} | {t['external_ref'] or '—'} | {t['entity_id'] or '—'} | "
                f"{t['board_id']} | {t['priority']} | {t['state']} | {t['name']} |")
        out += ["", "**Who owes it:** whether PACS, imaging and medical gas sit inside any "
                "baseline heading is a ruling for the parties to the agreement, not for "
                "Dada IT and not for this software."]
    else:
        out.append("None. Every ticket carries a contract basis.")

    closed = owed["closed_unattached"]
    out += ["", f"## Closed on the variation path with no variation — {len(closed)}", ""]
    if closed:
        out += [
            "These arrived from the desk already closed. The close gate guards an update, "
            "not an insert, so history imports as it was rather than being refused at the "
            "door — but the effort on them cannot reach an uplift claim until a variation "
            "exists to carry it. That is work already given away unless somebody raises one.",
            "",
            "| Ticket | Desk ref | Entity | Board | State | Summary |",
            "|---|---|---|---|---|---|",
        ]
        for t in closed:
            out.append(f"| {t['work_item_id']} | {t['external_ref'] or '—'} | {t['entity_id'] or '—'} | "
                       f"{t['board_id']} | {t['state']} | {t['name']} |")
    else:
        out.append("None.")

    open_ = owed["open_unattached"]
    out += ["", f"## Open on the variation path with no variation — {len(open_)}", ""]
    if open_:
        out += [
            "These cannot consume effort at all: the database refuses a time entry against "
            "them until a variation is attached. That is the gate working. Each one is a "
            "variation waiting to be raised, and every day it is not raised is effort that "
            "either goes unrecorded or goes somewhere it does not belong.",
            "",
            "| Ticket | Desk ref | Entity | Board | State | Summary |",
            "|---|---|---|---|---|---|",
        ]
        for t in open_:
            out.append(f"| {t['work_item_id']} | {t['external_ref'] or '—'} | {t['entity_id'] or '—'} | "
                       f"{t['board_id']} | {t['state']} | {t['name']} |")
    else:
        out.append("None.")

    out += [
        "",
        "---",
        "",
        "**On publishing the baseline hours.** They are in the table above because they are "
        "the denominator of any capacity argument and the evidence is incomplete without "
        "them. They are not for the client's copy until the available-capacity constant is "
        "initialled: an hours record against a fixed fee with no hours cap invites the "
        "question *what does the monthly fee actually buy*, and that question is much easier "
        "to answer once both parties have signed what a month of capacity is.",
        "",
        "**The narrative is the defence; the band is only the arithmetic.** A percentage "
        "should be corroborated by things PMC can check without trusting Dada's bands: "
        "ticket counts on the variation's boards, dated notices, days a client dependency "
        "stood outstanding, and delivered items with dates.",
        "",
        "_Generated from the spine. Every figure is banded effort against work items whose "
        "contract basis is inherited, never typed per entry._",
    ]
    return "\n".join(out) + "\n"
