"""Tests for the PSA spine.

The acceptance tests that matter are the ones about not losing anything: the
register is the commercial record, and a transform that quietly drops a row
loses a covered entity or a billable variation.

Run: python3 tests/test_spine.py
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from psaspine import db, register, reports, tickets  # noqa: E402
import sqlite_to_tsql  # noqa: E402
from sqlite_ddl import Unsupported  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "register-sample.csv"
DESK = Path(__file__).parent / "fixtures" / "desk-export-sample.csv"
AS_OF = date(2026, 9, 9)


class SpineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init(Path(self.tmp.name) / "spine.db")
        self.summary = register.import_register(
            self.conn, FIXTURE, run_id="t1", at=AS_OF.isoformat())

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    # ------------------------------------------------------------ losslessness

    def test_every_row_becomes_a_work_item(self):
        """The headline invariant: nothing is dropped, for any reason."""
        self.assertEqual(self.summary["rows_in"], self.summary["rows_out"])
        self.assertEqual(self.summary["rows_in"], 15)

    def test_unclassifiable_rows_are_imported_and_counted(self):
        """WS17 has contract_basis '?' — it must import, be flagged, and be visible."""
        row = self.conn.execute(
            "SELECT contract_basis, contract_basis_raw FROM work_item WHERE work_item_id='WS17'"
        ).fetchone()
        self.assertEqual(row["contract_basis"], "UNKNOWN")
        self.assertEqual(row["contract_basis_raw"], "?")
        flagged = self.conn.execute(
            "SELECT COUNT(*) c FROM data_quality WHERE code='UNKNOWN_BASIS' AND subject_id='WS17'"
        ).fetchone()["c"]
        self.assertEqual(flagged, 1)

    # -------------------------------------------------- the row that gets lost

    def test_qualified_variation_is_still_a_variation(self):
        """WS34's basis is the literal 'variation (Amendment 1)'.

        An exact-match filter on 'variation' drops it. That row is an entire
        covered entity, so this is the single most important assertion here.
        """
        row = self.conn.execute(
            "SELECT contract_basis, contract_basis_raw FROM work_item WHERE work_item_id='WS34'"
        ).fetchone()
        self.assertEqual(row["contract_basis"], "VARIATION")
        self.assertEqual(row["contract_basis_raw"], "variation (Amendment 1)")

    def test_variation_count_includes_the_qualified_row(self):
        n = self.conn.execute(
            "SELECT COUNT(*) c FROM work_item WHERE contract_basis='VARIATION'").fetchone()["c"]
        exact = self.conn.execute(
            "SELECT COUNT(*) c FROM work_item WHERE contract_basis_raw='variation'").fetchone()["c"]
        self.assertEqual(n, 5)       # WS02, WS05, WS07, WS34, WS35
        self.assertEqual(exact, 4)   # the naive filter, one short
        self.assertGreater(n, exact)

    # ---------------------------------------------------------- compound scope

    def test_compound_scope_becomes_two_links_each(self):
        cases = {
            "WS14": ("2->8", {("2", "PRIMARY"), ("8", "SUCCEEDS")}),
            "WS15": ("3+5", {("3", "PRIMARY"), ("5", "SECONDARY")}),
            "WS19": ("1/2", {("1", "PRIMARY"), ("2", "ALTERNATIVE")}),
            "WS26": ("4/8", {("4", "PRIMARY"), ("8", "ALTERNATIVE")}),
        }
        for wid, (raw, expected) in cases.items():
            got = {
                (r["scope_item_id"], r["relation"])
                for r in self.conn.execute(
                    "SELECT scope_item_id, relation FROM work_item_scope_item WHERE work_item_id=?",
                    (wid,))
            }
            self.assertEqual(got, expected, f"{wid} ({raw})")

    def test_scope_value_that_is_not_a_scope_item_is_flagged_not_silently_kept(self):
        """WS34's scope cell is 'JRBY', which is not one of the nine or VAR."""
        links = self.conn.execute(
            "SELECT COUNT(*) c FROM work_item_scope_item WHERE work_item_id='WS34'").fetchone()["c"]
        self.assertEqual(links, 0)
        flagged = self.conn.execute(
            "SELECT detail FROM data_quality WHERE code='UNKNOWN_SCOPE_ITEM' AND subject_id='WS34'"
        ).fetchone()
        self.assertIsNotNone(flagged)
        self.assertIn("JRBY", flagged["detail"])

    def test_scope_not_stated_is_flagged(self):
        flagged = self.conn.execute(
            "SELECT COUNT(*) c FROM data_quality WHERE code='SCOPE_NOT_STATED' AND subject_id='WS17'"
        ).fetchone()["c"]
        self.assertEqual(flagged, 1)

    # ------------------------------------------------------------- normalising

    def test_status_qualifiers_are_normalised_but_kept(self):
        row = self.conn.execute(
            "SELECT status, status_raw FROM work_item WHERE work_item_id='WS28'").fetchone()
        self.assertEqual(row["status"], "DONE")
        self.assertEqual(row["status_raw"], "DONE (filed; execution unverified)")

    def test_multi_entity_is_attributed_and_flagged(self):
        row = self.conn.execute(
            "SELECT entity_id, entity_raw FROM work_item WHERE work_item_id='WS07'").fetchone()
        self.assertEqual(row["entity_id"], "PMC")
        self.assertEqual(row["entity_raw"], "PMC+JRBY")
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM data_quality WHERE code='MULTI_ENTITY'").fetchone()["c"], 1)

    def test_embedded_commas_and_quotes_survive(self):
        note = self.conn.execute(
            "SELECT body FROM work_item_note WHERE work_item_id='WS07'").fetchone()["body"]
        self.assertIn("Contains, commas, and semicolons;", note)
        self.assertIn('quoted "text"', note)

    def test_evidence_is_split_and_classified(self):
        rows = self.conn.execute(
            "SELECT raw, kind FROM work_item_evidence WHERE work_item_id='WS07' ORDER BY ordinal"
        ).fetchall()
        self.assertEqual([r["kind"] for r in rows], ["DOC", "PATH", "DELIVERABLE"])

    def test_lane_is_derived(self):
        lanes = dict(self.conn.execute("SELECT work_item_id, lane FROM work_item").fetchall())
        self.assertEqual(lanes["WS20"], "C-chase")                 # blocked on the client
        self.assertEqual(lanes["WS26"], "B-finish-what-is-built")  # built, not run
        self.assertEqual(lanes["WS12"], "A-stop-the-bleeding")     # high risk, Dada acts

    # ---------------------------------------------------------------- reports

    def test_annex_b_lists_the_qualified_variation(self):
        text = reports.annex_b(self.conn, as_of=AS_OF)
        self.assertIn("WS34", text)
        self.assertIn("variation (Amendment 1)", text)
        self.assertIn("Variations on the register — 5", text)
        self.assertIn("WS17", text)      # the unclassified row is shown, not hidden

    def test_a_notice_is_generated_for_every_client_blocked_row(self):
        blocked = reports.blocked_on_client(self.conn)
        notices = reports.dependency_notices(self.conn, as_of=AS_OF)
        self.assertEqual(len(notices), len(blocked))
        self.assertEqual(len(blocked), 5)   # WS01, WS02, WS05, WS14, WS20
        one = notices["Notice_WS20_20260909"]
        self.assertIn("Client procurement", one)
        self.assertIn("days", one)

    def test_notices_exclude_rows_the_supplier_owns(self):
        """WS26 is BUILT-NOT-RUN with Dada to act — not a client dependency."""
        self.assertNotIn("WS26", " ".join(reports.dependency_notices(self.conn, as_of=AS_OF)))

    def test_exception_report_names_the_unexecuted_instruments(self):
        text = reports.instrument_exceptions(self.conn, as_of=AS_OF)
        self.assertIn("AMEND-1", text)
        self.assertIn("Not executed — 5", text)
        self.assertIn("JRBY-CI", text)

    def test_import_run_is_recorded_with_a_source_hash(self):
        run = self.conn.execute("SELECT * FROM import_run WHERE run_id='t1'").fetchone()
        self.assertEqual(run["rows_in"], 15)
        self.assertEqual(len(run["source_sha256"]), 64)

    def test_variation_paper_counts_from_data_not_prose(self):
        text = reports.variation_paper(self.conn, as_of=AS_OF)
        self.assertIn("**5 workstreams** are already recorded as variations", text)
        self.assertIn("**5 workstreams** are blocked on the client with no notice", text)
        self.assertIn("WS34", text)                      # the qualified variation is listed
        self.assertIn("AMEND-1", text)                   # unexecuted instruments named
        self.assertIn("JRBY-CI", text)                   # the uncovered entity named

    def test_variation_paper_refuses_to_invent_a_price(self):
        """Unpriced by default: no rate card exists, so a number would be fiction."""
        unpriced = reports.variation_paper(self.conn, as_of=AS_OF)
        self.assertIn("**Not yet priced.**", unpriced)
        self.assertIn("no rate card exists", unpriced)
        priced = reports.variation_paper(self.conn, as_of=AS_OF, eac_percent=20, capacity_hours=160)
        self.assertIn("Capacity uplift of **20%**", priced)
        self.assertIn("**160 hours per calendar month**", priced)
        self.assertIn("offered for initialling", priced)
        self.assertNotIn("**Not yet priced.**", priced)

    def test_days_outstanding_handles_both_date_shapes_and_unknown(self):
        self.assertEqual(reports.days_outstanding("20260902", AS_OF), 7)
        self.assertEqual(reports.days_outstanding("2026-09-09", AS_OF), 0)
        self.assertIsNone(reports.days_outstanding("unknown", AS_OF))
        self.assertIsNone(reports.days_outstanding(None, AS_OF))


class GateTest(unittest.TestCase):
    """The execution gate: nothing invoiceable rests on an unsigned instrument."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init(Path(self.tmp.name) / "spine.db")

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_decision_note_cannot_be_backdated_after_the_decision(self):
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO decision_note (entity_id, subject, advisory_at, decision_at, advised_by)"
                " VALUES ('PMC','advice after the fact','2026-09-09','2026-09-01','Dada')")

    def test_variation_state_must_be_one_of_the_nine(self):
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO variation (variation_id, title, entity_id, category, state)"
                " VALUES ('VAR-1','x','PMC','OPERATIONAL_TICKETING','PROBABLY_FINE')")

    def test_performed_without_approval_is_expressible(self):
        """The state that makes unbilled variation work visible instead of lost."""
        self.conn.execute(
            "INSERT INTO variation (variation_id, title, entity_id, category, state)"
            " VALUES ('VAR-1','Hospital-wide ticketing','PMC','OPERATIONAL_TICKETING',"
            "'PERFORMED_WITHOUT_APPROVAL')")
        self.assertEqual(self.conn.execute(
            "SELECT state FROM variation WHERE variation_id='VAR-1'").fetchone()["state"],
            "PERFORMED_WITHOUT_APPROVAL")


class DeskImportTest(unittest.TestCase):
    """The desk export, imported losslessly.

    The synthetic export carries the shapes a real one carries: a row with no
    reference, the same reference twice, a company that is not a covered entity,
    a status nobody has heard of, a component spelt the way the workbook misspells
    it, a desk priority that disagrees with the matrix, and a variation-path
    ticket that arrived already closed.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init(Path(self.tmp.name) / "spine.db")
        self.summary = tickets.import_tickets(
            self.conn, DESK, run_id="d1", at=AS_OF.isoformat())

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _flags(self, code: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM data_quality WHERE code = ? ORDER BY finding_id", (code,)).fetchall()

    # ------------------------------------------------------------ losslessness

    def test_every_row_becomes_one_work_item_and_one_ticket(self):
        self.assertEqual(self.summary["rows_in"], self.summary["rows_out"])
        self.assertEqual(self.summary["rows_in"], 13)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM work_item WHERE source='desk'").fetchone()["c"], 13)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM ticket").fetchone()["c"], 13)

    def test_a_row_with_no_reference_is_still_a_row(self):
        row = self.conn.execute(
            "SELECT * FROM ticket WHERE work_item_id LIKE 'DESK-d1-%'").fetchone()
        self.assertIsNotNone(row)
        self.assertIsNone(row["external_ref"])
        self.assertEqual(len(self._flags("NO_TICKET_REFERENCE")), 1)

    def test_the_same_reference_twice_does_not_overwrite_the_first(self):
        """INSERT OR REPLACE on a repeated key is how a row disappears silently."""
        both = self.conn.execute(
            "SELECT work_item_id, external_ref FROM ticket WHERE external_ref='ITO-1802'"
            " ORDER BY work_item_id").fetchall()
        self.assertEqual([r["work_item_id"] for r in both], ["ITO-1802", "ITO-1802#2"])
        self.assertEqual(len(self._flags("DUPLICATE_REFERENCE")), 1)

    def test_an_unclassifiable_row_is_imported_and_flagged_not_dropped(self):
        """Medical gas matches no curated triple. It must not be forced into one.

        The board the export named is still honoured — a board is a queue, not a
        commercial classification — but nothing is defaulted from a catalogue
        item that does not exist.
        """
        row = self.conn.execute(
            "SELECT t.board_id, t.catalogue_item_id, w.contract_basis FROM ticket t"
            " JOIN work_item w USING(work_item_id) WHERE t.work_item_id='ITO-1806'"
        ).fetchone()
        self.assertEqual(row["board_id"], "FACILITIES")
        self.assertIsNone(row["catalogue_item_id"])
        self.assertEqual(row["contract_basis"], "UNKNOWN")
        self.assertEqual(len(self._flags("UNKNOWN_CATALOGUE_ITEM")), 2)

    def test_a_row_with_no_board_at_all_lands_on_the_unrouted_queue(self):
        row = self.conn.execute(
            "SELECT board_id, catalogue_item_id FROM ticket WHERE work_item_id='ITO-1812'"
        ).fetchone()
        self.assertEqual(row["board_id"], "UNROUTED")
        self.assertIsNone(row["catalogue_item_id"])

    def test_a_status_nobody_knows_is_kept_verbatim_on_the_event_log(self):
        self.assertEqual(self.conn.execute(
            "SELECT state FROM ticket WHERE work_item_id='ITO-1809'").fetchone()["state"], "NEW")
        self.assertEqual(self.conn.execute(
            "SELECT status_raw FROM work_item WHERE work_item_id='ITO-1809'"
        ).fetchone()["status_raw"], "Parked pending parts")
        detail = self.conn.execute(
            "SELECT detail FROM ticket_event WHERE work_item_id='ITO-1809'").fetchone()["detail"]
        self.assertIn("Parked pending parts", detail)
        self.assertEqual(len(self._flags("UNKNOWN_STATUS")), 1)

    def test_embedded_commas_and_quotes_survive(self):
        note = self.conn.execute(
            "SELECT body FROM work_item_note WHERE work_item_id='ITO-1801'").fetchone()["body"]
        self.assertIn("Escalated by phone, then by ticket.", note)

    # ----------------------------------------------- defaults from the catalogue

    def test_the_scope_item_and_basis_come_from_the_catalogue(self):
        """A nurse files a ticket without ever seeing a commercial field."""
        row = self.conn.execute(
            "SELECT contract_basis, contract_basis_raw FROM work_item"
            " WHERE work_item_id='ITO-1802'").fetchone()
        self.assertEqual(row["contract_basis"], "BASELINE")
        self.assertIn("CI_USER_NEW", row["contract_basis_raw"])
        scope = self.conn.execute(
            "SELECT scope_item_id FROM work_item_scope_item WHERE work_item_id='ITO-1802'"
        ).fetchone()
        self.assertEqual(scope["scope_item_id"], "2")     # Active Directory

    def test_a_component_spelt_the_way_the_workbook_misspells_it_still_lands(self):
        """'Distrubution List'. Ten misspellings shipped; the raw name is indexed."""
        self.assertEqual(self.conn.execute(
            "SELECT catalogue_item_id FROM ticket WHERE work_item_id='ITO-1804'"
        ).fetchone()["catalogue_item_id"], "CI_MAIL_DL")

    def test_pacs_stays_unknown_rather_than_being_filed_under_the_nearest_heading(self):
        """The quiet reclassification the spine exists to prevent."""
        row = self.conn.execute(
            "SELECT contract_basis FROM work_item WHERE work_item_id='ITO-1803'").fetchone()
        self.assertEqual(row["contract_basis"], "UNKNOWN")
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM work_item_scope_item WHERE work_item_id='ITO-1803'"
        ).fetchone()["c"], 0)
        self.assertIn("ITO-1803", [f["subject_id"] for f in self._flags("UNKNOWN_BASIS")])

    def test_a_variation_catalogue_item_puts_the_ticket_on_the_variation_path(self):
        self.assertEqual(self.conn.execute(
            "SELECT path FROM ticket WHERE work_item_id='ITO-1811'").fetchone()["path"],
            "VARIATION")
        self.assertEqual(self.conn.execute(
            "SELECT path FROM ticket WHERE work_item_id='ITO-1801'").fetchone()["path"],
            "INCIDENT")
        self.assertEqual(self.conn.execute(
            "SELECT path FROM ticket WHERE work_item_id='ITO-1802'").fetchone()["path"],
            "SERVICE_REQUEST")

    # -------------------------------------------------- priority is computed

    def test_the_matrix(self):
        self.assertEqual(tickets.compute_priority("I1", "U1"), ("P1", "MATRIX"))
        self.assertEqual(tickets.compute_priority("I2", "U2"), ("P3", "MATRIX"))
        self.assertEqual(tickets.compute_priority("I3", "U3"), ("P4", "MATRIX"))

    def test_a_catalogue_floor_and_a_clinical_item_can_only_raise_a_priority(self):
        self.assertEqual(tickets.compute_priority("I3", "U3", min_priority="P2"),
                         ("P2", "CATALOGUE_FLOOR"))
        self.assertEqual(tickets.compute_priority("I3", "U3", clinical_impact=1),
                         ("P2", "CLINICAL_IMPACT"))
        # A floor below the matrix result never lowers it, and never takes credit.
        self.assertEqual(tickets.compute_priority("I1", "U1", min_priority="P4"),
                         ("P1", "MATRIX"))
        self.assertEqual(tickets.compute_priority("I1", "U1", clinical_impact=1),
                         ("P1", "MATRIX"))

    def test_the_desk_priority_is_evidence_not_input(self):
        """ITO-1808 is filed P4 at the desk and is a switch outage in the catalogue."""
        row = self.conn.execute(
            "SELECT priority, priority_source FROM ticket WHERE work_item_id='ITO-1808'"
        ).fetchone()
        self.assertEqual(row["priority"], "P2")
        self.assertEqual(row["priority_source"], "CATALOGUE_FLOOR")
        disagreements = [f["subject_id"] for f in self._flags("PRIORITY_DISAGREES")]
        self.assertIn("ITO-1808", disagreements)

    def test_no_unsigned_clinical_floor_was_applied(self):
        """All four floors seed PROPOSED. An unsigned floor does not bind."""
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM ticket WHERE priority_source='CLINICAL_FLOOR'"
        ).fetchone()["c"], 0)
        self.assertEqual(len(self._flags("FLOOR_NOT_SIGNED")), 1)

    def test_a_missing_urgency_is_taken_low_and_said_out_loud(self):
        """Nobody asked the requester whether a patient was waiting."""
        self.assertEqual(self.conn.execute(
            "SELECT urgency FROM ticket WHERE work_item_id='ITO-1804'").fetchone()["urgency"],
            "U3")
        self.assertEqual(len(self._flags("URGENCY_NOT_STATED")), 1)

    # -------------------------------------------------------------- the gate

    def test_a_ticket_closed_on_the_variation_path_is_imported_and_owed_a_decision(self):
        """The close trigger guards an UPDATE, so history imports as it was.

        That is deliberate — a desk export is full of already-closed work — and
        the gap is carried as an ERROR finding rather than left silent.
        """
        self.assertEqual(self.conn.execute(
            "SELECT state FROM ticket WHERE work_item_id='ITO-1805'").fetchone()["state"],
            "CLOSED")
        flagged = [f["subject_id"] for f in self._flags("CLOSED_WITH_NO_VARIATION")]
        self.assertEqual(flagged, ["ITO-1805"])

    def test_an_imported_ticket_still_cannot_be_closed_without_a_variation(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE ticket SET state='CLOSED' WHERE work_item_id='ITO-1811'")

    # ------------------------------------------------------------- the record

    def test_the_run_is_recorded_with_a_source_hash(self):
        run = self.conn.execute("SELECT * FROM import_run WHERE run_id='d1'").fetchone()
        self.assertEqual(run["rows_in"], 13)
        self.assertEqual(run["rows_out"], 13)
        self.assertEqual(len(run["source_sha256"]), 64)

    def test_no_api_key_is_read_or_recorded(self):
        """The keys were exposed in a screenshot. This path reads a file."""
        source = Path(tickets.__file__).read_text(encoding="utf-8")
        for word in ("api_key", "apikey", "public_key", "private_key", "Authorization",
                     "bearer", "requests.get", "urlopen"):
            self.assertNotIn(word.lower(), source.lower(), f"{word} appears in tickets.py")


class UpliftEvidenceTest(unittest.TestCase):
    """The report the whole spine exists to produce.

    Its job is to be defensible, which mostly means being unflattering: it prints
    no percentage without a declared denominator, it counts what nobody has
    classified rather than reporting around it, and it rounds against the party
    being paid.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init(Path(self.tmp.name) / "spine.db")
        tickets.import_tickets(self.conn, DESK, run_id="d1", at=AS_OF.isoformat())

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _band(self, work_item_id: str, worked_on: str, hours: float,
              counts: int = 1) -> None:
        self.conn.execute(
            "INSERT INTO time_entry (work_item_id, entity_id, worked_on, band_hours,"
            " performed_by, entered_by, charge_method, counts_to_capacity)"
            " VALUES (?, (SELECT entity_id FROM work_item WHERE work_item_id = ?),"
            " ?,?,'K. Simon','T. Dela Cruz','CAPACITY_UPLIFT',?)",
            (work_item_id, work_item_id, worked_on, hours, counts))

    def _attach_a_variation(self, work_item_id: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO variation (variation_id, title, entity_id, category, state)"
            " VALUES ('VAR-1','Hospital-wide ticketing','JRBY-CI','OPERATIONAL_TICKETING',"
            "'PRICED')")
        self.conn.execute("UPDATE work_item SET variation_id='VAR-1' WHERE work_item_id=?",
                          (work_item_id,))

    def _with_effort(self) -> None:
        self._attach_a_variation("ITO-1811")
        self._band("ITO-1811", "2026-09-02", 8)
        self._band("ITO-1811", "20260903", 4)      # the other date shape, same month
        self._band("ITO-1801", "2026-09-02", 4)    # baseline
        self._band("ITO-1803", "2026-08-30", 8)    # UNKNOWN basis, an earlier month
        self._band("ITO-1801", "2026-09-04", 2, counts=0)   # excluded from capacity
        self.conn.commit()

    # ------------------------------------------------------- refusing to guess

    def test_it_prints_no_percentage_without_a_declared_denominator(self):
        """An undisclosed denominator is how an uplift invoice gets rejected."""
        self._with_effort()
        text = reports.uplift_evidence(self.conn, as_of=AS_OF)
        self.assertIn("**Not stated, so no uplift percentage is printed.**", text)
        self.assertNotIn("EAC% (rounded down to 5)", text)     # no column, no number
        self.assertNotIn("%) |", text)

    def test_it_says_so_plainly_when_no_effort_is_banded(self):
        text = reports.uplift_evidence(self.conn, as_of=AS_OF, capacity_hours=160)
        self.assertIn("There is no banded effort in this database", text)

    def test_the_rounding_runs_against_the_party_being_paid(self):
        self.assertEqual(reports.round_down_to_5(7.5), 5)
        self.assertEqual(reports.round_down_to_5(24.9), 20)
        self.assertEqual(reports.round_down_to_5(25.0), 25)
        self.assertEqual(reports.round_down_to_5(4.9), 0)

    # ---------------------------------------------------------- the arithmetic

    def test_effort_is_grouped_by_entity_month_and_basis(self):
        self._with_effort()
        text = reports.uplift_evidence(self.conn, as_of=AS_OF)
        self.assertIn("| JRBY-CI | 2026-09 | VARIATION | 12.0 |", text)
        self.assertIn("| PMC | 2026-09 | BASELINE | 4.0 |", text)
        self.assertIn("| PMC | 2026-08 | UNKNOWN | 8.0 |", text)

    def test_both_date_shapes_fall_in_the_same_month(self):
        """'20260903' and '2026-09-02' are both September, and both are kept."""
        self._with_effort()
        self.assertEqual(reports._month("20260903"), "2026-09")
        self.assertEqual(reports._month("2026-09-02"), "2026-09")
        self.assertEqual(reports._month("some time in August"), "unknown")

    def test_effort_that_does_not_count_to_capacity_is_shown_and_excluded(self):
        self._with_effort()
        text = reports.uplift_evidence(self.conn, as_of=AS_OF)
        self.assertIn("**2.0 hours are recorded and excluded**", text)
        self.assertIn("| PMC | 2026-09 | BASELINE | 4.0 |", text)   # not 6.0

    def test_variation_path_effort_is_separated(self):
        self._with_effort()
        text = reports.uplift_evidence(self.conn, as_of=AS_OF)
        section = text[text.index("## Variation-path effort"):text.index("## The denominator")]
        self.assertIn("| JRBY-CI | 2026-09 | 12.0 |", section)
        self.assertNotIn("PMC", section)

    def test_the_percentage_when_a_denominator_is_supplied(self):
        self._with_effort()
        text = reports.uplift_evidence(self.conn, as_of=AS_OF, capacity_hours=160)
        self.assertIn("**160 hours per calendar month**", text)
        self.assertIn("**not yet agreed by the client**", text)
        self.assertIn("| JRBY-CI | 2026-09 | 12.0 | 5% |", text)    # 7.5% rounded down

    def test_a_declared_capacity_is_used_and_its_agreement_reported(self):
        self._with_effort()
        self.conn.execute(
            "INSERT INTO capacity_declaration (effective_from, hours_per_month, basis,"
            " agreed_by, agreed_on) VALUES ('2026-07-01', 160, 'one CIO-equivalent',"
            " 'PMC Finance', '2026-08-01')")
        self.conn.commit()
        text = reports.uplift_evidence(self.conn, as_of=AS_OF)
        self.assertIn("declared in the spine as one CIO-equivalent", text)
        self.assertIn("agreed by PMC Finance on 2026-08-01", text)

    # --------------------------------------------------------- decisions owed

    def test_every_unknown_basis_ticket_is_listed_as_a_decision_somebody_owes(self):
        text = reports.uplift_evidence(self.conn, as_of=AS_OF)
        self.assertIn("Decisions somebody owes — 3 tickets with no contract basis", text)
        for ticket in ("ITO-1803", "ITO-1806", "ITO-1812"):     # PACS, medical gas, lift
            self.assertIn(ticket, text)
        self.assertIn("not for Dada IT and not for this software", text)

    def test_variation_tickets_with_no_variation_are_split_open_from_closed(self):
        text = reports.uplift_evidence(self.conn, as_of=AS_OF)
        closed = text[text.index("## Closed on the variation path"):
                      text.index("## Open on the variation path")]
        open_ = text[text.index("## Open on the variation path"):]
        self.assertIn("ITO-1805", closed)      # arrived closed; effort can never reach a claim
        self.assertNotIn("ITO-1811", closed)
        self.assertIn("ITO-1811", open_)       # cannot consume effort until one is raised
        self.assertNotIn("ITO-1805", open_)

    def test_attaching_a_variation_clears_the_decision(self):
        self._attach_a_variation("ITO-1811")
        self.conn.commit()
        text = reports.uplift_evidence(self.conn, as_of=AS_OF)
        self.assertIn("## Open on the variation path with no variation — 0", text)


class TheGateTest(unittest.TestCase):
    """The two triggers, exercised rather than admired.

    They were added with the ticket schema and never actually fired at. A gate
    nobody has walked into is a comment, so these walk into it: a variation-path
    ticket must not be able to consume effort, or be closed, while no variation
    is attached.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init(Path(self.tmp.name) / "spine.db")
        self.conn.execute(
            "INSERT INTO work_item (work_item_id, source, name, entity_id, contract_basis)"
            " VALUES ('ITO-1723','desk','MRI feed dead','PMC','VARIATION')")
        self.conn.execute(
            "INSERT INTO ticket (work_item_id, board_id, path, impact, urgency, priority,"
            " priority_source, requested_at, opened_at, state)"
            " VALUES ('ITO-1723','IT_HELP','VARIATION','I1','U1','P1','MATRIX',"
            "'2026-09-09','2026-09-09','IN_PROGRESS')")

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _log_time(self):
        return self.conn.execute(
            "INSERT INTO time_entry (work_item_id, entity_id, worked_on, band_hours,"
            " performed_by, entered_by, charge_method)"
            " VALUES ('ITO-1723','PMC','2026-09-09',4,'K. Simon','T. Dela Cruz',"
            "'CAPACITY_UPLIFT')")

    def _attach_a_variation(self) -> None:
        self.conn.execute(
            "INSERT INTO variation (variation_id, title, entity_id, category, state)"
            " VALUES ('VAR-1','Hospital-wide ticketing','PMC','OPERATIONAL_TICKETING','PRICED')")
        self.conn.execute(
            "UPDATE work_item SET variation_id='VAR-1' WHERE work_item_id='ITO-1723'")

    def test_effort_is_refused_while_no_variation_is_attached(self):
        with self.assertRaises(sqlite3.IntegrityError) as caught:
            self._log_time()
        self.assertIn("must be attached to a variation", str(caught.exception))
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM time_entry").fetchone()["c"], 0)

    def test_close_is_refused_while_no_variation_is_attached(self):
        for state in ("RESOLVED", "CLOSED"):
            with self.assertRaises(sqlite3.IntegrityError) as caught:
                self.conn.execute("UPDATE ticket SET state=? WHERE work_item_id='ITO-1723'",
                                  (state,))
            self.assertIn("cannot be closed with no variation", str(caught.exception))
        self.assertEqual(self.conn.execute(
            "SELECT state FROM ticket").fetchone()["state"], "IN_PROGRESS")

    def test_both_are_allowed_once_a_variation_exists(self):
        self._attach_a_variation()
        self._log_time()
        self.conn.execute("UPDATE ticket SET state='CLOSED' WHERE work_item_id='ITO-1723'")
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM time_entry").fetchone()["c"], 1)
        self.assertEqual(self.conn.execute(
            "SELECT state FROM ticket").fetchone()["state"], "CLOSED")

    def test_the_gate_is_only_on_the_variation_path(self):
        """An incident consumes the fee. It has no commercial event to wait for."""
        self.conn.execute(
            "INSERT INTO work_item (work_item_id, source, name, entity_id, contract_basis)"
            " VALUES ('ITO-1724','desk','Printer re-cabled','PMC','BASELINE')")
        self.conn.execute(
            "INSERT INTO ticket (work_item_id, board_id, path, impact, urgency, priority,"
            " priority_source, requested_at, opened_at, state)"
            " VALUES ('ITO-1724','IT_HELP','INCIDENT','I3','U3','P4','MATRIX',"
            "'2026-09-09','2026-09-09','IN_PROGRESS')")
        self.conn.execute(
            "INSERT INTO time_entry (work_item_id, entity_id, worked_on, band_hours,"
            " performed_by, entered_by, charge_method)"
            " VALUES ('ITO-1724','PMC','2026-09-09',0.5,'K. Simon','T. Dela Cruz',"
            "'INCLUDED_IN_MONTHLY_FEE')")
        self.conn.execute("UPDATE ticket SET state='CLOSED' WHERE work_item_id='ITO-1724'")
        self.assertEqual(self.conn.execute(
            "SELECT state FROM ticket WHERE work_item_id='ITO-1724'").fetchone()["state"],
            "CLOSED")

    def test_a_typed_reason_is_required_to_lower_a_priority(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO priority_override (work_item_id, overridden_at, was_priority,"
                " now_priority, escalation_role, reason)"
                " VALUES ('ITO-1723','2026-09-09','P1','P3','DUTY_MANAGER','ok')")


class SchemaRulesTest(unittest.TestCase):
    """The four rules that are decisions somebody with authority has not made.

    Each is enforced in the schema precisely so a port, an importer or a hurry
    cannot relax it. These assert the seed does not quietly claim otherwise.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init(Path(self.tmp.name) / "spine.db")

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_the_phase_2_boards_are_live_and_every_live_board_is_owned(self):
        # A desk nobody can file on is not a foot in the door. The five phase 2
        # boards are Dada IT's and the PMO's own work, so they seed live.
        live = [r["board_id"] for r in self.conn.execute(
            "SELECT board_id FROM board WHERE is_live=1 ORDER BY board_id")]
        self.assertEqual(live, ["AGREEMENT", "IT_HELP", "IT_REQUEST", "SECURITY", "UNROUTED"])
        unowned = self.conn.execute(
            "SELECT COUNT(*) c FROM board WHERE is_live=1"
            " AND (owner IS NULL OR deputy IS NULL)").fetchone()["c"]
        self.assertEqual(unowned, 0)

    def test_a_departmental_board_still_cannot_go_live_unowned(self):
        # Not a signature: phase 3a has not opened, so there is nobody to name.
        # The rule still bites the moment somebody tries to skip that.
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE board SET is_live=1 WHERE board_id='NURSING'")

    def test_a_baseline_catalogue_item_must_name_its_baseline_heading(self):
        unknown = self.conn.execute(
            "SELECT COUNT(*) c FROM catalogue_item WHERE default_contract_basis='UNKNOWN'"
        ).fetchone()["c"]
        self.assertEqual(unknown, 21)     # PACS, imaging, medical gas, patching, hardware
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "UPDATE catalogue_item SET default_contract_basis='BASELINE',"
                " default_scope_item_id=NULL WHERE default_contract_basis='UNKNOWN'")

    def test_no_clinical_floor_is_signed_and_none_can_claim_to_be(self):
        signed = self.conn.execute(
            "SELECT COUNT(*) c FROM clinical_floor WHERE status='SIGNED_OFF'").fetchone()["c"]
        self.assertEqual(signed, 0)
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE clinical_floor SET status='SIGNED_OFF'")

    def test_no_sla_target_is_enforced(self):
        enforced = self.conn.execute(
            "SELECT COUNT(*) c FROM sla_target WHERE enforced=1").fetchone()["c"]
        self.assertEqual(enforced, 0)


class PortTest(unittest.TestCase):
    """The SQL Server port, and the drift gate that keeps the two in step.

    NOT VERIFIED against DND-SQL01\\PMC_SS: no environment on this account has a
    route to it, so nothing here has been executed by a server. These assert what
    the translator emits, which is the part that can be checked from here.
    """

    def setUp(self) -> None:
        self.tsql = sqlite_to_tsql.generate()

    # ------------------------------------------------------------------- drift

    def test_the_committed_script_is_what_the_schema_produces_today(self):
        """The whole point of generating it: two copies cannot disagree."""
        committed = sqlite_to_tsql.OUTPUT.read_text(encoding="utf-8")
        self.assertEqual(committed, self.tsql,
                         "sqlserver/ has drifted from schema/. Run "
                         "python3 tools/sqlite_to_tsql.py --write and commit both.")

    def test_every_table_and_both_triggers_are_ported(self):
        for table in ("entity", "variation", "work_item", "time_entry", "ticket",
                      "catalogue_item", "board", "priority_override"):
            self.assertIn(f"CREATE TABLE psa.[{table}] (", self.tsql)
        self.assertIn("CREATE TRIGGER psa.[time_entry_requires_a_variation]", self.tsql)
        self.assertIn("CREATE TRIGGER psa.[ticket_close_requires_a_variation]", self.tsql)

    # ------------------------------------------------------------ the decisions

    def test_integer_primary_key_becomes_identity_and_a_text_key_does_not(self):
        self.assertIn("[time_entry_id] INT IDENTITY(1,1) NOT NULL", self.tsql)
        self.assertIn("[work_item_id] NVARCHAR(64) NOT NULL", self.tsql)
        self.assertNotIn("NVARCHAR(64) IDENTITY", self.tsql)

    def test_nothing_that_reaches_an_invoice_is_a_float(self):
        self.assertNotIn("FLOAT", self.tsql.upper())
        self.assertNotIn("] REAL", self.tsql)
        self.assertIn("[band_hours] DECIMAL(9,2)", self.tsql)
        self.assertIn("[amount] DECIMAL(19,4)", self.tsql)
        self.assertIn("[eac_percent] DECIMAL(9,4)", self.tsql)

    def test_max_is_only_where_a_note_or_a_detail_lives(self):
        self.assertIn("[next_action] NVARCHAR(MAX)", self.tsql)   # thousands of characters
        self.assertIn("[detail] NVARCHAR(MAX)", self.tsql)
        self.assertIn("[name] NVARCHAR(400)", self.tsql)          # a name is not a note
        self.assertIn("[work_item_id] NVARCHAR(64)", self.tsql)

    def test_dates_stay_as_the_source_wrote_them(self):
        """Converting on the way in loses which shape the source used."""
        self.assertIn("[worked_on] NVARCHAR(32) NOT NULL", self.tsql)
        self.assertIn("[worked_on_parsed] AS (CASE WHEN [worked_on] LIKE", self.tsql)
        self.assertIn("TRY_CONVERT(DATE, [worked_on], 112)", self.tsql)   # '20260904'
        self.assertIn("TRY_CONVERT(DATE, [worked_on], 23)", self.tsql)    # '2026-09-09'

    def test_the_typed_reason_survives_the_port(self):
        self.assertIn("CHECK (LEN(LTRIM(RTRIM(reason))) >= 15)", self.tsql)

    def test_the_decision_note_ordering_check_survives_the_port(self):
        self.assertIn("CHECK (decision_at IS NULL OR advisory_at <= decision_at)", self.tsql)

    def test_a_board_still_cannot_go_live_without_an_owner(self):
        self.assertIn("CHECK (is_live = 0 OR (owner IS NOT NULL AND deputy IS NOT NULL))",
                      self.tsql)

    # -------------------------------------------------------------- the gate

    def test_the_gate_rolls_back_and_throws_with_the_same_words(self):
        self.assertIn("IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;", self.tsql)
        self.assertIn(
            "THROW 50001, N''a variation-path ticket must be attached to a variation "
            "before it can consume effort'', 1;", self.tsql)
        self.assertIn(
            "THROW 50002, N''a variation-path ticket cannot be closed with no variation "
            "attached'', 1;", self.tsql)

    def test_before_becomes_after_over_the_inserted_rows(self):
        """SQL Server has no BEFORE trigger; NEW becomes a row of `inserted`."""
        self.assertIn("AFTER INSERT", self.tsql)
        self.assertNotIn("BEFORE INSERT\nAS", self.tsql)
        self.assertIn("FROM inserted AS inserted_row", self.tsql)
        self.assertNotIn("NEW.", self.tsql)

    def test_the_close_gate_only_fires_when_the_state_column_moves(self):
        self.assertIn("IF (UPDATE(state))", self.tsql)

    # ---------------------------------------------------- refusing to guess

    def _translate(self, schema_sql: str, decisions: dict | None = None) -> str:
        import json
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "001.sql").write_text(schema_sql, encoding="utf-8")
        dec_path = root / "decisions.json"
        base = json.loads(sqlite_to_tsql.DECISIONS.read_text(encoding="utf-8"))
        base["columns"] = (decisions or {})
        base["decimals"] = {}
        dec_path.write_text(json.dumps(base), encoding="utf-8")
        return sqlite_to_tsql.generate(root, dec_path)

    def test_a_column_with_no_decided_width_stops_the_build(self):
        with self.assertRaises(Unsupported) as caught:
            self._translate("CREATE TABLE t (a TEXT);")
        self.assertIn("no width decided", str(caught.exception))

    def test_a_float_with_no_decided_precision_stops_the_build(self):
        with self.assertRaises(Unsupported) as caught:
            self._translate("CREATE TABLE t (a REAL);")
        self.assertIn("no precision decided", str(caught.exception))

    def test_an_unknown_function_in_a_check_stops_the_build(self):
        """A function quietly dropped is a constraint quietly weakened."""
        with self.assertRaises(Unsupported) as caught:
            self._translate("CREATE TABLE t (a TEXT CHECK (substr(a,1,2) = 'ab'));",
                            {"t.a": "NAME"})
        self.assertIn("substr", str(caught.exception))

    def test_an_unknown_statement_stops_the_build(self):
        with self.assertRaises(Unsupported) as caught:
            self._translate("CREATE VIEW v AS SELECT 1;")
        self.assertIn("not recognised", str(caught.exception))

    def test_a_width_narrower_than_its_own_check_stops_the_build(self):
        with self.assertRaises(Unsupported) as caught:
            self._translate(
                "CREATE TABLE t (a TEXT CHECK (a IN ('PAUSED_PENDING_AUTHORISATION_AND_THEN_SOME')));",
                {"t.a": "CODE"})
        self.assertIn("disagree", str(caught.exception))

    def test_the_decisions_file_cannot_drift_either(self):
        with self.assertRaises(Unsupported) as caught:
            self._translate("CREATE TABLE t (a TEXT);", {"t.a": "NAME", "t.gone": "NAME"})
        self.assertIn("t.gone", str(caught.exception))

    def test_a_trigger_body_that_is_not_a_raise_stops_the_build(self):
        with self.assertRaises(Unsupported) as caught:
            self._translate(
                "CREATE TABLE t (a TEXT);\n"
                "CREATE TRIGGER g AFTER INSERT ON t FOR EACH ROW WHEN NEW.a = 'x'"
                " BEGIN UPDATE t SET a = 'y'; END;",
                {"t.a": "NAME"})
        self.assertIn("SELECT RAISE", str(caught.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
