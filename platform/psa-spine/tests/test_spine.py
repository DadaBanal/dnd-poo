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
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from psaspine import board, clocks, db, register, reports, rules, tickets  # noqa: E402
import sqlite_to_tsql  # noqa: E402
from sqlite_ddl import Unsupported  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "register-sample.csv"
DESK = Path(__file__).parent / "fixtures" / "desk-export-sample.csv"
AS_OF = date(2026, 9, 9)


class SpineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init(Path(self.tmp.name) / "spine.db")
        # The catalogue is no longer seeded by default — one board is. These
        # tests exercise the importer and the reports, so they load the sample.
        db.seed_sample(self.conn)
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
        # The catalogue is no longer seeded by default — one board is. These
        # tests exercise the importer and the reports, so they load the sample.
        db.seed_sample(self.conn)

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
        # The catalogue is no longer seeded by default — one board is. These
        # tests exercise the importer and the reports, so they load the sample.
        db.seed_sample(self.conn)
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
        # The catalogue is no longer seeded by default — one board is. These
        # tests exercise the importer and the reports, so they load the sample.
        db.seed_sample(self.conn)
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
        # The catalogue is no longer seeded by default — one board is. These
        # tests exercise the importer and the reports, so they load the sample.
        db.seed_sample(self.conn)
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
    """What a fresh database actually contains, and the rules it still enforces.

    Deliberately does NOT load seed/sample/. The whole point is that a new spine
    arrives nearly empty and PMC fills it, so these assert on the real default.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init(Path(self.tmp.name) / "spine.db")

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_a_new_spine_has_the_first_board_and_the_unrouted_queue(self):
        """A PSA does not arrive with boards in it. You create the one you run.

        Two seed, not one: the first real board, and the queue an unclassifiable
        row lands on. Without the second a lossless import is impossible -- the
        importer falls back to it by foreign key and fails outright when it is
        missing, which is how this was found.
        """
        boards = [(r["board_id"], r["is_live"], r["is_unrouted"])
                  for r in self.conn.execute(
                      "SELECT board_id, is_live, is_unrouted FROM board ORDER BY board_id")]
        self.assertEqual(boards, [("IT_HELP", 1, 0), ("UNROUTED", 1, 1)])
        unowned = self.conn.execute(
            "SELECT COUNT(*) c FROM board WHERE is_live=1"
            " AND (owner IS NULL OR deputy IS NULL)").fetchone()["c"]
        self.assertEqual(unowned, 0)

    def test_a_desk_import_survives_an_empty_catalogue(self):
        """The clean slate must not cost losslessness. Every row still lands."""
        summary = tickets.import_tickets(
            self.conn, DESK, run_id="clean", at=AS_OF.isoformat())
        self.assertEqual(summary["rows_in"], summary["rows_out"])
        placed = self.conn.execute(
            "SELECT COUNT(*) c FROM ticket WHERE board_id IS NOT NULL").fetchone()["c"]
        self.assertEqual(placed, summary["rows_out"])

    def test_the_catalogue_starts_empty_rather_than_guessed(self):
        """Sixteen boards and fifty-one items used to seed here, reverse-engineered
        from a workbook out of the desk in use today. That is a sample of how a
        different system was once configured, not PMC's decisions, and shipping it
        as the default made somebody else's guesses look authoritative."""
        for table in ("catalogue_item", "service_component", "service_family",
                      "service_action", "clinical_floor", "sla_target"):
            n = self.conn.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"]
            self.assertEqual(n, 0, f"{table} should start empty")

    def test_a_new_board_still_cannot_go_live_unowned(self):
        """The rule holds on boards PMC creates, which is where it now matters."""
        self.conn.execute(
            "INSERT INTO board (board_id, display_name, phase, fulfiller_group, is_live)"
            " VALUES ('NURSING', 'Nursing', '3b', 'Nursing supervisor', 0)")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE board SET is_live=1 WHERE board_id='NURSING'")

    def test_a_baseline_catalogue_item_must_name_its_baseline_heading(self):
        db.seed_sample(self.conn)         # needs items to test the rule against
        unknown = self.conn.execute(
            "SELECT COUNT(*) c FROM catalogue_item WHERE default_contract_basis='UNKNOWN'"
        ).fetchone()["c"]
        self.assertEqual(unknown, 21)     # PACS, imaging, medical gas, patching, hardware
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "UPDATE catalogue_item SET default_contract_basis='BASELINE',"
                " default_scope_item_id=NULL WHERE default_contract_basis='UNKNOWN'")

    def test_no_clinical_floor_is_signed_and_none_can_claim_to_be(self):
        db.seed_sample(self.conn)         # needs floors to test the rule against
        signed = self.conn.execute(
            "SELECT COUNT(*) c FROM clinical_floor WHERE status='SIGNED_OFF'").fetchone()["c"]
        self.assertEqual(signed, 0)
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE clinical_floor SET status='SIGNED_OFF'")

    def test_no_sla_target_is_enforced(self):
        db.seed_sample(self.conn)         # needs targets to test the rule against
        enforced = self.conn.execute(
            "SELECT COUNT(*) c FROM sla_target WHERE enforced=1").fetchone()["c"]
        self.assertEqual(enforced, 0)


class BoardConfigurationTest(unittest.TestCase):
    """006 — the board owns its statuses, its people and its working week.

    These are the rules a board engine rests on, so each one is walked into
    rather than described.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init(Path(self.tmp.name) / "spine.db")

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _status(self, sid: str, name: str, escalation: str, **flags) -> None:
        cols = "board_status_id, board_id, name, escalation_status"
        vals = [sid, "IT_HELP", name, escalation]
        for k, v in flags.items():
            cols += f", {k}"
            vals.append(v)
        self.conn.execute(
            f"INSERT INTO board_status ({cols}) VALUES ({','.join('?' * len(vals))})", vals)

    # ------------------------------------------------------------- statuses

    def test_a_status_declares_which_sla_milestone_it_represents(self):
        """One field, not three booleans. NO_ESCALATION is the pause."""
        self._status("IT_HELP.NEW", "New", "NOT_RESPONDED", is_default=1)
        self._status("IT_HELP.PARTS", "Waiting for parts", "NO_ESCALATION",
                     time_entry_allowed=0)
        self._status("IT_HELP.DONE", "Closed", "RESOLVED", is_closed=1)
        paused = self.conn.execute(
            "SELECT escalation_status, time_entry_allowed FROM board_status"
            " WHERE board_status_id='IT_HELP.PARTS'").fetchone()
        self.assertEqual(paused["escalation_status"], "NO_ESCALATION")
        self.assertEqual(paused["time_entry_allowed"], 0)

    def test_a_status_nobody_invented_is_refused(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._status("IT_HELP.X", "Probably fine", "SORT_OF_RESPONDED")

    def test_the_default_status_may_not_also_close_the_ticket(self):
        """A new ticket must not land already closed."""
        with self.assertRaises(sqlite3.IntegrityError):
            self._status("IT_HELP.ODD", "Done on arrival", "RESOLVED",
                         is_default=1, is_closed=1)

    def test_two_statuses_on_one_board_cannot_share_a_name(self):
        self._status("IT_HELP.A", "In progress", "RESPONDED")
        with self.assertRaises(sqlite3.IntegrityError):
            self._status("IT_HELP.B", "In progress", "RESPONDED")

    def test_a_status_belongs_to_a_board_that_exists(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO board_status (board_status_id, board_id, name,"
                " escalation_status) VALUES ('X.NEW','NO_SUCH_BOARD','New','NOT_RESPONDED')")

    def test_what_a_requester_reads_is_a_different_sentence(self):
        """Internal language must not be the only language a nurse gets."""
        self._status("IT_HELP.PARTS", "Awaiting vendor RMA, PO 4471", "NO_ESCALATION",
                     customer_description="We are waiting on a delivery.")
        row = self.conn.execute(
            "SELECT name, customer_description FROM board_status"
            " WHERE board_status_id='IT_HELP.PARTS'").fetchone()
        self.assertNotEqual(row["name"], row["customer_description"])
        self.assertNotIn("PO 4471", row["customer_description"])

    # ---------------------------------------------------------------- roles

    def test_a_board_carries_four_roles_not_an_owner_and_a_deputy(self):
        """Two names cannot say who answers at 02:00 and who answers when they do not."""
        for role, who in (("SERVICE_MANAGER", "Dada Banal"), ("DISPATCH", "Dela Cruz"),
                          ("ON_CALL", "Cadano"), ("DUTY_MANAGER", "Gabelo")):
            self.conn.execute(
                "INSERT INTO board_role (board_id, role, member) VALUES ('IT_HELP',?,?)",
                (role, who))
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM board_role WHERE board_id='IT_HELP'").fetchone()["c"], 4)

    def test_a_role_this_schema_does_not_know_is_refused(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO board_role (board_id, role, member)"
                " VALUES ('IT_HELP','WHOEVER_IS_FREE','Somebody')")

    def test_one_person_per_role_per_board(self):
        self.conn.execute(
            "INSERT INTO board_role (board_id, role, member)"
            " VALUES ('IT_HELP','ON_CALL','Cadano')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO board_role (board_id, role, member)"
                " VALUES ('IT_HELP','ON_CALL','Gabelo')")

    # --------------------------------------------------------- membership

    def test_membership_is_the_access_control_on_a_restricted_board(self):
        self.conn.execute(
            "INSERT INTO board_team (team_id, board_id, name, is_default)"
            " VALUES ('IT_HELP.T1','IT_HELP','Windows team',1)")
        self.conn.execute(
            "INSERT INTO board_member (board_id, member, team_id, access)"
            " VALUES ('IT_HELP','Cadano','IT_HELP.T1','WORK')")
        visible = self.conn.execute(
            "SELECT COUNT(*) c FROM board_member WHERE board_id='IT_HELP'"
            " AND member='Dietary supervisor'").fetchone()["c"]
        self.assertEqual(visible, 0)     # a non-member is provably excluded

    def test_a_person_holds_one_access_level_per_board(self):
        self.conn.execute(
            "INSERT INTO board_member (board_id, member, access)"
            " VALUES ('IT_HELP','Cadano','WORK')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO board_member (board_id, member, access)"
                " VALUES ('IT_HELP','Cadano','ADMIN')")

    # ------------------------------------------------------ the working week

    def test_a_calendar_is_a_table_so_a_ward_roster_is_a_row(self):
        self.conn.execute(
            "INSERT INTO holiday_list (holiday_list_id, name) VALUES ('PH','Philippines')")
        self.conn.execute(
            "INSERT INTO holiday (holiday_list_id, observed_on, name)"
            " VALUES ('PH','2026-11-30','Bonifacio Day')")
        self.conn.execute(
            "INSERT INTO calendar (calendar_id, name, monday_start, monday_end,"
            " holiday_list_id) VALUES ('MANILA','Manila business hours','08:00','17:00','PH')")
        row = self.conn.execute(
            "SELECT c.monday_start, c.sunday_start, h.name FROM calendar c"
            " JOIN holiday h ON h.holiday_list_id = c.holiday_list_id"
            " WHERE c.calendar_id='MANILA'").fetchone()
        self.assertEqual(row["monday_start"], "08:00")
        self.assertIsNone(row["sunday_start"])      # NULL means closed that day
        self.assertEqual(row["name"], "Bonifacio Day")

    def test_twenty_four_by_seven_is_a_row_not_a_special_case(self):
        self.conn.execute(
            "INSERT INTO calendar (calendar_id, name, monday_start, monday_end,"
            " tuesday_start, tuesday_end, wednesday_start, wednesday_end,"
            " thursday_start, thursday_end, friday_start, friday_end,"
            " saturday_start, saturday_end, sunday_start, sunday_end)"
            " VALUES ('CLINICAL','Clinical 24x7',"
            "'00:00','24:00','00:00','24:00','00:00','24:00','00:00','24:00',"
            "'00:00','24:00','00:00','24:00','00:00','24:00')")
        row = self.conn.execute(
            "SELECT * FROM calendar WHERE calendar_id='CLINICAL'").fetchone()
        for day in ("monday", "tuesday", "wednesday", "thursday", "friday",
                    "saturday", "sunday"):
            self.assertEqual(row[f"{day}_start"], "00:00", day)
            self.assertEqual(row[f"{day}_end"], "24:00", day)

    def test_a_holiday_cannot_be_listed_twice_on_one_calendar(self):
        self.conn.execute(
            "INSERT INTO holiday_list (holiday_list_id, name) VALUES ('PH','Philippines')")
        self.conn.execute(
            "INSERT INTO holiday (holiday_list_id, observed_on, name)"
            " VALUES ('PH','2026-12-25','Christmas Day')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO holiday (holiday_list_id, observed_on, name)"
                " VALUES ('PH','2026-12-25','Christmas')")


class ClockTest(unittest.TestCase):
    """007 — elapsed working time, and breach derived rather than stored.

    The arithmetic under every SLA number this spine will report, so it is
    asserted against dates somebody can check by hand rather than against
    whatever the code happened to return.
    """

    MANILA = {i: (480, 1020) for i in range(5)}      # Mon-Fri 08:00-17:00
    CLINICAL = {i: (0, 1440) for i in range(7)}      # every hour of every day

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init(Path(self.tmp.name) / "spine.db")
        self.conn.execute(
            "INSERT INTO holiday_list (holiday_list_id, name) VALUES ('PH','Philippines')")
        self.conn.execute(
            "INSERT INTO holiday (holiday_list_id, observed_on, name)"
            " VALUES ('PH','2026-11-30','Bonifacio Day')")
        self.conn.execute(
            "INSERT INTO calendar (calendar_id, name, monday_start, monday_end,"
            " tuesday_start, tuesday_end, wednesday_start, wednesday_end,"
            " thursday_start, thursday_end, friday_start, friday_end, holiday_list_id)"
            " VALUES ('MANILA','Manila business hours','08:00','17:00','08:00','17:00',"
            "'08:00','17:00','08:00','17:00','08:00','17:00','PH')")
        self.conn.execute(
            "INSERT INTO calendar (calendar_id, name, monday_start, monday_end,"
            " tuesday_start, tuesday_end, wednesday_start, wednesday_end,"
            " thursday_start, thursday_end, friday_start, friday_end,"
            " saturday_start, saturday_end, sunday_start, sunday_end)"
            " VALUES ('CLINICAL','Clinical 24x7','00:00','24:00','00:00','24:00',"
            "'00:00','24:00','00:00','24:00','00:00','24:00','00:00','24:00','00:00','24:00')")
        self.conn.execute(
            "INSERT INTO work_item (work_item_id, source, name, entity_id, contract_basis)"
            " VALUES ('ITO-2001','desk','Ward switch down','PMC','BASELINE')")
        self.conn.execute(
            "INSERT INTO ticket (work_item_id, board_id, path, impact, urgency, priority,"
            " priority_source, requested_at, opened_at, state)"
            " VALUES ('ITO-2001','IT_HELP','INCIDENT','I1','U1','P1','MATRIX',"
            "'2026-11-13','2026-11-13','IN_PROGRESS')")

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _clock(self, calendar: str = "MANILA", target: int = 240,
               started: str = "2026-11-13T16:00", stopped: str | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO ticket_clock (work_item_id, clock, calendar_id, target_minutes,"
            " started_at, stopped_at) VALUES ('ITO-2001','RESOLVE',?,?,?,?)",
            (calendar, target, started, stopped))
        return cur.lastrowid

    # ------------------------------------------------------- the arithmetic

    def test_a_weekend_does_not_count_on_a_business_calendar(self):
        """Friday 16:00 to Monday 09:00 is two working hours, not sixty-five."""
        cal = clocks.Calendar(self.MANILA, set())
        self.assertEqual(
            cal.working_minutes(datetime(2026, 11, 13, 16, 0),
                                datetime(2026, 11, 16, 9, 0)), 120)

    def test_a_philippine_holiday_does_not_count(self):
        """Bonifacio Day, 30 November 2026, is a Monday. It must not be counted."""
        cal = clocks.Calendar(self.MANILA, {date(2026, 11, 30)})
        self.assertEqual(
            cal.working_minutes(datetime(2026, 11, 27, 16, 0),
                                datetime(2026, 12, 1, 9, 0)), 120)
        without = clocks.Calendar(self.MANILA, set())
        self.assertEqual(
            without.working_minutes(datetime(2026, 11, 27, 16, 0),
                                    datetime(2026, 12, 1, 9, 0)), 660)

    def test_every_hour_counts_on_a_clinical_calendar(self):
        cal = clocks.Calendar(self.CLINICAL, set())
        self.assertEqual(
            cal.working_minutes(datetime(2026, 11, 13, 16, 0),
                                datetime(2026, 11, 16, 9, 0)), 65 * 60)

    def test_out_of_hours_time_counts_as_nothing(self):
        cal = clocks.Calendar(self.MANILA, set())
        self.assertEqual(
            cal.working_minutes(datetime(2026, 11, 13, 18, 0),
                                datetime(2026, 11, 13, 23, 0)), 0)

    def test_time_never_runs_backwards(self):
        cal = clocks.Calendar(self.MANILA, set())
        self.assertEqual(
            cal.working_minutes(datetime(2026, 11, 16, 9, 0),
                                datetime(2026, 11, 13, 16, 0)), 0)

    def test_a_closed_day_is_a_null_start_not_a_special_case(self):
        loaded = clocks.Calendar.load(self.conn, "MANILA")
        self.assertNotIn(5, loaded.windows)      # Saturday
        self.assertNotIn(6, loaded.windows)      # Sunday
        self.assertIn(date(2026, 11, 30), loaded.holidays)

    def test_twenty_four_by_seven_loads_as_seven_ordinary_rows(self):
        loaded = clocks.Calendar.load(self.conn, "CLINICAL")
        self.assertEqual(len(loaded.windows), 7)
        self.assertEqual(loaded.windows[6], (0, 1440))

    # ------------------------------------------------------------- pausing

    def test_a_pause_at_two_in_the_morning_costs_a_business_clock_nothing(self):
        """Nothing was running, so nothing is subtracted."""
        clock_id = self._clock(started="2026-11-16T08:00", stopped="2026-11-16T12:00")
        self.assertEqual(clocks.elapsed_minutes(self.conn, clock_id), 240)
        self.conn.execute(
            "INSERT INTO ticket_clock_pause (clock_id, paused_at, resumed_at, reason)"
            " VALUES (?,'2026-11-17T02:00','2026-11-17T04:00','vendor asleep')",
            (clock_id,))
        self.assertEqual(clocks.elapsed_minutes(self.conn, clock_id), 240)

    def test_a_pause_in_working_hours_is_subtracted(self):
        clock_id = self._clock(started="2026-11-16T08:00", stopped="2026-11-16T12:00")
        self.conn.execute(
            "INSERT INTO ticket_clock_pause (clock_id, paused_at, resumed_at, reason)"
            " VALUES (?,'2026-11-16T09:00','2026-11-16T10:30','waiting on the ward')",
            (clock_id,))
        self.assertEqual(clocks.elapsed_minutes(self.conn, clock_id), 150)

    def test_a_pause_that_never_ended_runs_to_the_moment_asked_about(self):
        clock_id = self._clock(started="2026-11-16T08:00")
        self.conn.execute(
            "INSERT INTO ticket_clock_pause (clock_id, paused_at, reason)"
            " VALUES (?,'2026-11-16T09:00','still waiting')", (clock_id,))
        used = clocks.elapsed_minutes(self.conn, clock_id,
                                      as_of=datetime(2026, 11, 16, 16, 0))
        self.assertEqual(used, 60)      # 08:00-09:00 only; the rest is paused

    def test_a_pause_must_say_why_or_name_the_status_that_caused_it(self):
        clock_id = self._clock()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO ticket_clock_pause (clock_id, paused_at) VALUES (?,'2026-11-16T09:00')",
                (clock_id,))

    def test_a_pause_cannot_end_before_it_began(self):
        clock_id = self._clock()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO ticket_clock_pause (clock_id, paused_at, resumed_at, reason)"
                " VALUES (?,'2026-11-16T10:00','2026-11-16T09:00','impossible')", (clock_id,))

    # -------------------------------------------------------------- breach

    def test_breach_is_derived_so_correcting_a_target_corrects_yesterday(self):
        """A stored flag would defend a number nobody can reproduce."""
        clock_id = self._clock(target=240, started="2026-11-16T08:00",
                               stopped="2026-11-16T14:00")     # 6 working hours
        self.assertTrue(clocks.breached(self.conn, clock_id))
        self.conn.execute(
            "UPDATE ticket_clock SET target_minutes = 480 WHERE clock_id = ?", (clock_id,))
        self.assertFalse(clocks.breached(self.conn, clock_id))

    def test_the_same_ticket_breaches_on_one_calendar_and_not_the_other(self):
        """Friday 16:00 to Monday 09:00, against a four-hour target."""
        biz = self._clock(calendar="MANILA", target=240,
                          started="2026-11-13T16:00", stopped="2026-11-16T09:00")
        self.assertFalse(clocks.breached(self.conn, biz))       # 120 working minutes
        self.conn.execute("UPDATE ticket_clock SET clock='RESPOND' WHERE clock_id=?", (biz,))
        clinical = self._clock(calendar="CLINICAL", target=240,
                               started="2026-11-13T16:00", stopped="2026-11-16T09:00")
        self.assertTrue(clocks.breached(self.conn, clinical))   # 3,900 minutes

    def test_a_running_clock_is_measured_to_the_moment_asked_about(self):
        clock_id = self._clock(target=240, started="2026-11-16T08:00")
        self.assertFalse(clocks.breached(self.conn, clock_id,
                                         as_of=datetime(2026, 11, 16, 11, 0)))
        self.assertTrue(clocks.breached(self.conn, clock_id,
                                        as_of=datetime(2026, 11, 16, 16, 0)))

    # ------------------------------------------- which status stops which clock

    def test_a_status_declares_the_milestone_and_the_clock_follows(self):
        self.assertTrue(clocks.stops_clock("RESPONDED", "RESPOND"))
        self.assertFalse(clocks.stops_clock("RESPONDED", "RESOLVE"))
        self.assertTrue(clocks.stops_clock("RESOLVED", "RESOLVE"))
        # Resolving without ever responding still satisfies the respond clock.
        self.assertTrue(clocks.stops_clock("RESOLVED", "RESPOND"))
        self.assertTrue(clocks.is_pause("NO_ESCALATION"))
        self.assertFalse(clocks.is_pause("RESPONDED"))

    def test_state_of_reports_everything_without_storing_any_of_it(self):
        clock_id = self._clock(target=240, started="2026-11-16T08:00")
        state = clocks.state_of(self.conn, clock_id, as_of=datetime(2026, 11, 16, 11, 0))
        self.assertEqual(state["elapsed_minutes"], 180)
        self.assertEqual(state["remaining_minutes"], 60)
        self.assertFalse(state["breached"])
        self.assertTrue(state["running"])
        self.assertFalse(state["paused"])

    def test_one_clock_of_each_kind_per_ticket(self):
        self._clock()
        with self.assertRaises(sqlite3.IntegrityError):
            self._clock()

    def test_a_target_of_zero_is_not_a_target(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO ticket_clock (work_item_id, clock, calendar_id,"
                " target_minutes, started_at) VALUES"
                " ('ITO-2001','ACKNOWLEDGE','MANILA',0,'2026-11-16T08:00')")


class RulesTest(unittest.TestCase):
    """008 — rules as rows, with no expression language anywhere near them.

    The headline case is the real one the record calls for: triage today is one
    person, and when she is unavailable the path is a personal chat to a CIO in
    another country. So an unowned ticket on the Unrouted queue must page IT
    every thirty minutes, four times, and then stop.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init(Path(self.tmp.name) / "spine.db")
        self.conn.execute(
            "INSERT INTO workflow (workflow_id, board_id, name, table_type, is_active)"
            " VALUES ('WF_UNROUTED','UNROUTED','Unrouted ages and pages IT','TICKET',1)")
        self.conn.execute(
            "INSERT INTO workflow_event (event_id, workflow_id, name, fires_on,"
            " execution_time, frequency, frequency_unit, max_executions)"
            " VALUES ('EV_AGE','WF_UNROUTED','Nobody has picked it up','ON_SCHEDULE',"
            "'MULTIPLE_TIMES',30,'MINUTES',4)")
        for tid, field, disp, vtype in (
                ("TICKET.OWNER", "owner", "Owner", "TEXT"),
                ("TICKET.PRIORITY", "priority", "Priority", "CODE"),
                ("TICKET.STATE", "state", "State", "CODE"),
                ("TICKET.AGE", "age_minutes", "Age in minutes", "NUMBER")):
            self.conn.execute(
                "INSERT INTO workflow_trigger (trigger_id, table_type, field,"
                " display_name, value_type) VALUES (?, 'TICKET', ?, ?, ?)",
                (tid, field, disp, vtype))
        self.conn.execute(
            "INSERT INTO workflow_condition (event_id, trigger_id, operator, sort_order)"
            " VALUES ('EV_AGE','TICKET.OWNER','IS_NULL',1)")
        self.conn.execute(
            "INSERT INTO workflow_condition (event_id, trigger_id, operator, value, sort_order)"
            " VALUES ('EV_AGE','TICKET.AGE','GTE','30',2)")
        self.conn.execute(
            "INSERT INTO workflow_action (event_id, action, notify_role, detail)"
            " VALUES ('EV_AGE','ESCALATE','ON_CALL','Unrouted and unowned')")
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    UNOWNED = {"work_item_id": "ITO-3001", "owner": None, "priority": "P2",
               "state": "NEW", "age_minutes": 45}

    # ------------------------------------------------------ the execution policy

    def test_the_unrouted_rule_pages_four_times_then_stops(self):
        """Every thirty minutes, capped. Not once into an empty room, not forever."""
        at = datetime(2026, 11, 16, 9, 0)
        fired = []
        for _ in range(8):
            result = rules.evaluate(self.conn, "EV_AGE", self.UNOWNED, as_of=at)
            if result["fired"]:
                fired.append(at)
            at += timedelta(minutes=30)
        self.assertEqual(len(fired), 4)
        self.assertEqual(fired[0], datetime(2026, 11, 16, 9, 0))
        self.assertEqual(fired[-1], datetime(2026, 11, 16, 10, 30))

    def test_it_does_not_fire_again_before_the_interval_is_up(self):
        at = datetime(2026, 11, 16, 9, 0)
        self.assertTrue(rules.evaluate(self.conn, "EV_AGE", self.UNOWNED, as_of=at)["fired"])
        soon = rules.evaluate(self.conn, "EV_AGE", self.UNOWNED,
                              as_of=at + timedelta(minutes=10))
        self.assertFalse(soon["fired"])
        self.assertIn("next firing is due", soon["reason"])

    def test_a_once_rule_fires_once(self):
        self.conn.execute(
            "INSERT INTO workflow_event (event_id, workflow_id, name, fires_on,"
            " execution_time) VALUES ('EV_ONE','WF_UNROUTED','Greet','ON_CREATE','ONCE')")
        at = datetime(2026, 11, 16, 9, 0)
        self.assertTrue(rules.evaluate(self.conn, "EV_ONE", self.UNOWNED, as_of=at)["fired"])
        again = rules.evaluate(self.conn, "EV_ONE", self.UNOWNED,
                               as_of=at + timedelta(days=1))
        self.assertFalse(again["fired"])
        self.assertIn("already acted once", again["reason"])

    def test_an_inactive_workflow_never_fires(self):
        """Off by default. A rule nobody has read should not be running."""
        self.conn.execute("UPDATE workflow SET is_active = 0 WHERE workflow_id='WF_UNROUTED'")
        result = rules.evaluate(self.conn, "EV_AGE", self.UNOWNED,
                                as_of=datetime(2026, 11, 16, 9, 0))
        self.assertFalse(result["fired"])
        self.assertIn("not active", result["reason"])

    def test_a_repeating_rule_must_carry_an_interval(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO workflow_event (event_id, workflow_id, fires_on,"
                " execution_time) VALUES ('EV_BAD','WF_UNROUTED','ON_SCHEDULE','CONTINUOUSLY')")

    def test_multiple_times_without_a_cap_is_refused(self):
        """If you mean forever, say CONTINUOUSLY and mean it."""
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO workflow_event (event_id, workflow_id, fires_on,"
                " execution_time, frequency, frequency_unit)"
                " VALUES ('EV_BAD','WF_UNROUTED','ON_SCHEDULE','MULTIPLE_TIMES',30,'MINUTES')")

    # --------------------------------------------------------- the conditions

    def test_an_owned_ticket_does_not_page_anybody(self):
        owned = dict(self.UNOWNED, owner="Dela Cruz")
        result = rules.evaluate(self.conn, "EV_AGE", owned,
                                as_of=datetime(2026, 11, 16, 9, 0))
        self.assertFalse(result["fired"])
        self.assertEqual(result["reason"], "conditions not met")

    def test_a_young_ticket_does_not_page_anybody(self):
        young = dict(self.UNOWNED, age_minutes=5)
        self.assertFalse(rules.evaluate(self.conn, "EV_AGE", young,
                                        as_of=datetime(2026, 11, 16, 9, 0))["fired"])

    def test_numbers_compare_as_numbers_not_as_text(self):
        """'100' < '30' as strings. That is how an ageing rule silently stops working."""
        self.assertTrue(rules.OPERATORS["GTE"](100, "30"))
        self.assertTrue(rules.OPERATORS["GT"](100, "30"))
        self.assertFalse(rules.OPERATORS["LT"](100, "30"))

    def test_every_operator_behaves(self):
        self.assertTrue(rules.OPERATORS["IN"]("P1", "P1,P2"))
        self.assertFalse(rules.OPERATORS["IN"]("P3", "P1,P2"))
        self.assertTrue(rules.OPERATORS["NOT_IN"]("P3", "P1,P2"))
        self.assertTrue(rules.OPERATORS["CONTAINS"]("Ward 3 switch stack", "switch"))
        self.assertTrue(rules.OPERATORS["IS_NULL"](None, None))
        self.assertFalse(rules.OPERATORS["IS_NOT_NULL"](None, None))
        self.assertTrue(rules.OPERATORS["NE"]("P1", "P2"))

    def test_a_condition_reading_a_field_nobody_supplied_raises(self):
        """A rule quietly evaluating False is a control that stopped working."""
        with self.assertRaises(rules.UnknownField):
            rules.matches(self.conn, "EV_AGE", {"priority": "P1"})   # no owner key

    def test_an_event_with_no_conditions_fires_on_its_trigger(self):
        self.conn.execute(
            "INSERT INTO workflow_event (event_id, workflow_id, fires_on, execution_time)"
            " VALUES ('EV_ANY','WF_UNROUTED','ON_CREATE','ONCE')")
        self.assertTrue(rules.matches(self.conn, "EV_ANY", {}))

    def test_conditions_combine_left_to_right_with_their_own_conjunction(self):
        self.conn.execute(
            "INSERT INTO workflow_event (event_id, workflow_id, fires_on, execution_time)"
            " VALUES ('EV_OR','WF_UNROUTED','ON_CREATE','ONCE')")
        self.conn.execute(
            "INSERT INTO workflow_condition (event_id, trigger_id, operator, value, sort_order)"
            " VALUES ('EV_OR','TICKET.PRIORITY','EQ','P1',1)")
        self.conn.execute(
            "INSERT INTO workflow_condition (event_id, trigger_id, operator, value,"
            " conjunction, sort_order) VALUES ('EV_OR','TICKET.STATE','EQ','NEW','OR',2)")
        self.assertTrue(rules.matches(self.conn, "EV_OR",
                                      {"priority": "P4", "state": "NEW"}))
        self.assertTrue(rules.matches(self.conn, "EV_OR",
                                      {"priority": "P1", "state": "CLOSED"}))
        self.assertFalse(rules.matches(self.conn, "EV_OR",
                                       {"priority": "P4", "state": "CLOSED"}))

    # --------------------------------------------------------- the audit trail

    def test_every_evaluation_is_recorded_whether_it_acted_or_not(self):
        """Why did nobody get paged, and why did this page four times."""
        at = datetime(2026, 11, 16, 9, 0)
        rules.evaluate(self.conn, "EV_AGE", self.UNOWNED, as_of=at)
        rules.evaluate(self.conn, "EV_AGE", self.UNOWNED, as_of=at + timedelta(minutes=5))
        rules.evaluate(self.conn, "EV_AGE", dict(self.UNOWNED, owner="Cadano"),
                       as_of=at + timedelta(minutes=40))
        outcomes = [r["outcome"] for r in self.conn.execute(
            "SELECT outcome FROM workflow_run WHERE event_id='EV_AGE' ORDER BY run_id")]
        self.assertEqual(outcomes, ["ACTED", "SUPPRESSED", "NOT_MATCHED"])

    def test_a_suppressed_firing_says_why(self):
        at = datetime(2026, 11, 16, 9, 0)
        rules.evaluate(self.conn, "EV_AGE", self.UNOWNED, as_of=at)
        rules.evaluate(self.conn, "EV_AGE", self.UNOWNED, as_of=at + timedelta(minutes=1))
        detail = self.conn.execute(
            "SELECT detail FROM workflow_run WHERE outcome='SUPPRESSED'").fetchone()["detail"]
        self.assertIn("30 minutes", detail)

    def test_the_action_names_a_role_rather_than_a_person(self):
        """So the rule survives somebody leaving."""
        result = rules.evaluate(self.conn, "EV_AGE", self.UNOWNED,
                                as_of=datetime(2026, 11, 16, 9, 0))
        self.assertEqual(result["actions"][0]["action"], "ESCALATE")
        self.assertEqual(result["actions"][0]["notify_role"], "ON_CALL")

    def test_a_notification_with_nobody_to_notify_is_refused(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO workflow_action (event_id, action) VALUES ('EV_AGE','NOTIFY')")

    def test_nothing_in_this_engine_reaches_eval(self):
        source = Path(rules.__file__).read_text(encoding="utf-8")
        for forbidden in ("eval(", "exec(", "compile(", "__import__"):
            self.assertNotIn(forbidden, source)


class BoardEngineTest(unittest.TestCase):
    """009 — one status change, and everything that follows from it.

    The seam where the board, the clocks and the rules stop being three
    libraries sharing a database.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init(Path(self.tmp.name) / "spine.db")
        self.conn.execute(
            "INSERT INTO calendar (calendar_id, name, monday_start, monday_end,"
            " tuesday_start, tuesday_end, wednesday_start, wednesday_end,"
            " thursday_start, thursday_end, friday_start, friday_end,"
            " saturday_start, saturday_end, sunday_start, sunday_end)"
            " VALUES ('CLINICAL','Clinical 24x7','00:00','24:00','00:00','24:00',"
            "'00:00','24:00','00:00','24:00','00:00','24:00','00:00','24:00','00:00','24:00')")
        for sid, name, esc, flags in (
                ("IT_HELP.NEW", "New", "NOT_RESPONDED", "is_default=1"),
                ("IT_HELP.WORKING", "In progress", "RESPONDED", ""),
                ("IT_HELP.PLAN", "Plan agreed", "RESOLUTION_PLAN", ""),
                ("IT_HELP.PARTS", "Waiting for parts", "NO_ESCALATION",
                 "time_entry_allowed=0"),
                ("IT_HELP.DONE", "Closed", "RESOLVED", "is_closed=1"),
                ("IT_HELP.OLD", "Retired status", "NO_ESCALATION", "inactive=1")):
            extra = f", {flags.split('=')[0]}" if flags else ""
            val = f", {flags.split('=')[1]}" if flags else ""
            self.conn.execute(
                f"INSERT INTO board_status (board_status_id, board_id, name,"
                f" escalation_status{extra}) VALUES (?,'IT_HELP',?,?{val})",
                (sid, name, esc))
        # Another board, to prove a status cannot be borrowed across one.
        self.conn.execute(
            "INSERT INTO board_status (board_status_id, board_id, name, escalation_status)"
            " VALUES ('UNROUTED.NEW','UNROUTED','New','NOT_RESPONDED')")
        for clock, minutes in (("RESPOND", 60), ("RESOLVE", 240)):
            self.conn.execute(
                "INSERT INTO sla_target (board_id, priority, clock, target_minutes,"
                " calendar, enforced) VALUES ('IT_HELP','P1',?,?, 'CLINICAL_24x7', 0)",
                (clock, minutes))
        self.conn.execute(
            "INSERT INTO work_item (work_item_id, source, name, entity_id, contract_basis)"
            " VALUES ('ITO-4001','desk','Ward switch stack down','PMC','BASELINE')")
        self.conn.execute(
            "INSERT INTO ticket (work_item_id, board_id, path, impact, urgency, priority,"
            " priority_source, requested_at, opened_at, state)"
            " VALUES ('ITO-4001','IT_HELP','INCIDENT','I1','U1','P1','MATRIX',"
            "'2026-11-16 08:00','2026-11-16 08:00','NEW')")
        board.open_clocks(self.conn, "ITO-4001",
                          at=datetime(2026, 11, 16, 8, 0), calendar_id="CLINICAL")
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _move(self, status_id: str, at: datetime) -> dict:
        return board.change_status(self.conn, "ITO-4001", status_id,
                                   at=at, actor="Cadano")

    def _clock(self, clock: str):
        return self.conn.execute(
            "SELECT * FROM ticket_clock WHERE work_item_id='ITO-4001' AND clock=?",
            (clock,)).fetchone()

    # ------------------------------------------------------------- the clocks

    def test_the_boards_sla_targets_start_the_clocks(self):
        self.assertEqual(
            {r["clock"] for r in self.conn.execute(
                "SELECT clock FROM ticket_clock WHERE work_item_id='ITO-4001'")},
            {"RESPOND", "RESOLVE"})

    def test_responding_stops_the_respond_clock_and_not_the_resolve_clock(self):
        result = self._move("IT_HELP.WORKING", datetime(2026, 11, 16, 8, 30))
        self.assertEqual(result["stopped"], ["RESPOND"])
        self.assertIsNotNone(self._clock("RESPOND")["stopped_at"])
        self.assertIsNone(self._clock("RESOLVE")["stopped_at"])

    def test_the_status_that_stopped_a_clock_is_on_the_record(self):
        self._move("IT_HELP.WORKING", datetime(2026, 11, 16, 8, 30))
        self.assertEqual(self._clock("RESPOND")["stopped_by_status"], "IT_HELP.WORKING")

    def test_resolving_stops_everything_still_running(self):
        result = self._move("IT_HELP.DONE", datetime(2026, 11, 16, 9, 0))
        self.assertEqual(sorted(result["stopped"]), ["RESOLVE", "RESPOND"])

    def test_a_pause_status_pauses_the_clocks_and_leaving_it_resumes_them(self):
        self._move("IT_HELP.WORKING", datetime(2026, 11, 16, 8, 30))
        paused = self._move("IT_HELP.PARTS", datetime(2026, 11, 16, 9, 0))
        self.assertEqual(paused["paused"], ["RESOLVE"])
        resumed = self._move("IT_HELP.WORKING", datetime(2026, 11, 16, 11, 0))
        self.assertEqual(resumed["resumed"], ["RESOLVE"])
        # Two hours parked, on a 24x7 calendar, must not count.
        used = clocks.elapsed_minutes(self.conn, self._clock("RESOLVE")["clock_id"],
                                      as_of=datetime(2026, 11, 16, 12, 0))
        self.assertEqual(used, 120)      # 08:00-09:00 and 11:00-12:00

    def test_pausing_twice_does_not_open_two_pauses(self):
        self._move("IT_HELP.PARTS", datetime(2026, 11, 16, 9, 0))
        again = self._move("IT_HELP.PARTS", datetime(2026, 11, 16, 10, 0))
        self.assertEqual(again["paused"], [])
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM ticket_clock_pause").fetchone()["c"], 2)  # one per clock

    def test_closing_from_a_pause_closes_the_pause_first(self):
        """Otherwise the paused interval runs on past the moment it stopped."""
        self._move("IT_HELP.PARTS", datetime(2026, 11, 16, 9, 0))
        self._move("IT_HELP.DONE", datetime(2026, 11, 16, 10, 0))
        open_pauses = self.conn.execute(
            "SELECT COUNT(*) c FROM ticket_clock_pause WHERE resumed_at IS NULL"
        ).fetchone()["c"]
        self.assertEqual(open_pauses, 0)

    # ---------------------------------------------------------- the lifecycle

    def test_the_universal_state_follows_the_boards_status(self):
        """`state` is what the variation gate tests, so it cannot drift."""
        self._move("IT_HELP.WORKING", datetime(2026, 11, 16, 8, 30))
        self.assertEqual(self.conn.execute(
            "SELECT state FROM ticket").fetchone()["state"], "IN_PROGRESS")
        self._move("IT_HELP.PARTS", datetime(2026, 11, 16, 9, 0))
        self.assertEqual(self.conn.execute(
            "SELECT state FROM ticket").fetchone()["state"], "WAITING_CLIENT")

    def test_a_closed_status_closes_the_ticket_and_stamps_the_date(self):
        self._move("IT_HELP.DONE", datetime(2026, 11, 16, 9, 0))
        row = self.conn.execute("SELECT state, closed_at FROM ticket").fetchone()
        self.assertEqual(row["state"], "CLOSED")
        self.assertEqual(row["closed_at"], "2026-11-16 09:00")

    def test_every_change_is_on_the_event_log(self):
        self._move("IT_HELP.WORKING", datetime(2026, 11, 16, 8, 30))
        detail = self.conn.execute(
            "SELECT detail FROM ticket_event WHERE kind='STATUS_CHANGE'").fetchone()["detail"]
        self.assertIn("IT_HELP.WORKING", detail)
        self.assertIn("RESPONDED", detail)

    # ------------------------------------------------------------- refusals

    def test_a_status_from_another_board_is_refused(self):
        with self.assertRaises(board.NotOnThisBoard):
            self._move("UNROUTED.NEW", datetime(2026, 11, 16, 9, 0))

    def test_a_retired_status_takes_no_new_tickets(self):
        with self.assertRaises(board.NotOnThisBoard):
            self._move("IT_HELP.OLD", datetime(2026, 11, 16, 9, 0))

    # ------------------------------------------------- effort, both gates

    def test_a_status_that_forbids_effort_says_so_before_the_attempt(self):
        self._move("IT_HELP.PARTS", datetime(2026, 11, 16, 9, 0))
        allowed, why = board.may_book_effort(self.conn, "ITO-4001")
        self.assertFalse(allowed)
        self.assertIn("Waiting for parts", why)

    def test_the_variation_gate_answers_before_the_database_refuses(self):
        """A nurse should read a sentence, not an IntegrityError."""
        self.conn.execute(
            "INSERT INTO work_item (work_item_id, source, name, entity_id, contract_basis)"
            " VALUES ('ITO-4002','desk','Raise a variation','PMC','VARIATION')")
        self.conn.execute(
            "INSERT INTO ticket (work_item_id, board_id, path, impact, urgency, priority,"
            " priority_source, requested_at, opened_at, state)"
            " VALUES ('ITO-4002','IT_HELP','VARIATION','I2','U2','P3','MATRIX',"
            "'2026-11-16 08:00','2026-11-16 08:00','NEW')")
        allowed, why = board.may_book_effort(self.conn, "ITO-4002")
        self.assertFalse(allowed)
        self.assertIn("must be attached to a variation", why)
        # And the trigger still refuses it regardless, which is the real gate.
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO time_entry (work_item_id, entity_id, worked_on, band_hours,"
                " performed_by, entered_by, charge_method) VALUES"
                " ('ITO-4002','PMC','2026-11-16',4,'Cadano','Cadano','CAPACITY_UPLIFT')")

    def test_effort_is_allowed_on_an_ordinary_working_ticket(self):
        self._move("IT_HELP.WORKING", datetime(2026, 11, 16, 8, 30))
        allowed, why = board.may_book_effort(self.conn, "ITO-4001")
        self.assertTrue(allowed, why)


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
