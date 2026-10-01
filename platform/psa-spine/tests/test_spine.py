"""Tests for the PSA spine.

The acceptance tests that matter are the ones about not losing anything: the
register is the commercial record, and a transform that quietly drops a row
loses a covered entity or a billable variation.

Run: python3 tests/test_spine.py
"""
from __future__ import annotations

import os
import sqlite3
import sys
import html
import re
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from psaspine import (board, clocks, db, intake, numbering, phi,  # noqa: E402
                      register, reports, rules, setup, tickets, walkthrough)
import sqlite_to_tsql  # noqa: E402
from sqlite_ddl import Unsupported  # noqa: E402

# The same tests on SQL Server: PSA_TEST_DB is an ODBC connection string to a
# database that carries (or may receive) the generated port; each test empties
# it and reseeds. Unset, every test gets a fresh SQLite file, as before.
TEST_DB = os.environ.get("PSA_TEST_DB")
ON_SQLITE = not TEST_DB


def _target(tmp):
    """What a test hands to db.connect / make_app / the CLI."""
    return TEST_DB if TEST_DB else Path(tmp.name) / "spine.db"


def _fresh(tmp):
    """A database with the schema and the seed rows and nothing else."""
    if TEST_DB:
        os.environ["PSA_ATTACHMENT_DIR"] = str(Path(tmp.name) / "files")
        return db.init(TEST_DB, reset=True)
    return db.init(Path(tmp.name) / "spine.db")


FIXTURE = Path(__file__).parent / "fixtures" / "register-sample.csv"
DESK = Path(__file__).parent / "fixtures" / "desk-export-sample.csv"
AS_OF = date(2026, 9, 9)


class SpineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
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
        self.conn = _fresh(self.tmp)
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
        self.conn = _fresh(self.tmp)
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
            " JOIN work_item w ON w.work_item_id = t.work_item_id WHERE t.work_item_id='ITO-1806'"
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
        self.conn = _fresh(self.tmp)
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
        self.conn = _fresh(self.tmp)
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
        # Committed, as a real ticket is by the time anyone tries to close it:
        # on SQL Server a gate trigger's refusal rolls the transaction back
        # (the port says so), and an uncommitted fixture would go with it.
        self.conn.commit()

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
        self.conn = _fresh(self.tmp)

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
        self.conn = _fresh(self.tmp)

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
        self.conn = _fresh(self.tmp)
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
        self.conn = _fresh(self.tmp)
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
        self.conn = _fresh(self.tmp)
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
        # One: the RESOLVE clock. RESPOND never pauses (see the next test).
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM ticket_clock_pause").fetchone()["c"], 1)

    def test_a_waiting_status_never_pauses_the_respond_clock(self):
        """Parking a ticket before anyone answered is not a response.

        Otherwise a New ticket moved straight to 'waiting for parts' would stop
        accruing response time and a missed response would never show. The
        record's §5.5 pauses the RESOLVE clock in a waiting status, not RESPOND.
        """
        result = self._move("IT_HELP.PARTS", datetime(2026, 11, 16, 9, 0))
        self.assertEqual(result["paused"], ["RESOLVE"])
        respond = self.conn.execute(
            "SELECT clock_id FROM ticket_clock WHERE clock = 'RESPOND'").fetchone()
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM ticket_clock_pause WHERE clock_id = ?",
            (respond["clock_id"],)).fetchone()["c"], 0)

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


class WalkthroughTest(unittest.TestCase):
    """The engine runs, not merely passes.

    The record's base rate is designs that were never run, so this asserts the
    narrative itself: if the arithmetic changes, the sentence a person reads
    changes, and the test fails.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.text = "\n".join(walkthrough.run(self.conn))

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_the_pause_is_what_keeps_the_ticket_inside_its_target(self):
        """Eleven hours of wall clock, two and three quarter hours of ours."""
        self.assertIn("RESOLVE  used   2h 45m  of   4h 00m   within target", self.text)
        self.assertIn("Wall clock from raise to close is 11h 10m", self.text)

    def test_the_respond_clock_stopped_when_somebody_actually_responded(self):
        self.assertIn("RESPOND  used   0h 25m  of   1h 00m   within target", self.text)

    def test_a_parked_ticket_refuses_effort_in_words(self):
        self.assertIn("effort: refused", self.text)
        self.assertIn("'Waiting for parts' does not allow effort", self.text)

    def test_the_unrouted_rule_pages_four_times_then_stops(self):
        self.assertEqual(self.text.count("PAGE ON-CALL"), 4)
        self.assertIn("firing 4 of 4", self.text)
        self.assertIn("reached its cap of 4 firings", self.text)

    def test_it_never_claims_a_target_is_enforced(self):
        self.assertIn("These measure. They do not promise.", self.text)
        enforced = self.conn.execute(
            "SELECT COUNT(*) c FROM sla_target WHERE enforced = 1").fetchone()["c"]
        self.assertEqual(enforced, 0)

    def test_the_ticket_ends_closed_with_every_clock_stopped(self):
        row = self.conn.execute(
            "SELECT state, board_status_id, closed_at FROM ticket"
            " WHERE work_item_id='ITO-9001'").fetchone()
        self.assertEqual(row["state"], "CLOSED")
        self.assertEqual(row["board_status_id"], "IT_HELP.DONE")
        self.assertEqual(row["closed_at"], "2026-11-17 09:20")
        still_running = self.conn.execute(
            "SELECT COUNT(*) c FROM ticket_clock WHERE work_item_id='ITO-9001'"
            " AND stopped_at IS NULL").fetchone()["c"]
        self.assertEqual(still_running, 0)


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

    def test_a_unique_index_over_a_nullable_column_must_keep_nulls_out(self):
        """SQLite lets many rows be NULL under UNIQUE; SQL Server lets one."""
        with self.assertRaises(Unsupported) as caught:
            self._translate("CREATE TABLE t (a TEXT);\nCREATE UNIQUE INDEX u ON t (a);",
                            {"t.a": "ID"})
        self.assertIn("WHERE a IS NOT NULL", str(caught.exception))

    def test_a_filtered_unique_index_ports_as_one(self):
        tsql = self._translate(
            "CREATE TABLE t (a TEXT);\n"
            "CREATE UNIQUE INDEX u ON t (a) WHERE a IS NOT NULL;", {"t.a": "ID"})
        self.assertIn("CREATE UNIQUE INDEX [u] ON psa.[t] ([a]) WHERE [a] IS NOT NULL;", tsql)

    def test_a_unique_index_over_not_null_columns_needs_no_filter(self):
        tsql = self._translate("CREATE TABLE t (a TEXT NOT NULL);\n"
                               "CREATE UNIQUE INDEX u ON t (a);", {"t.a": "ID"})
        self.assertIn("CREATE UNIQUE INDEX [u] ON psa.[t] ([a]);", tsql)

    def test_any_other_partial_index_condition_stops_the_build(self):
        with self.assertRaises(Unsupported) as caught:
            self._translate("CREATE TABLE t (a TEXT);\n"
                            "CREATE INDEX i ON t (a) WHERE a = 'x';", {"t.a": "ID"})
        self.assertIn("no port decided", str(caught.exception))

    def test_rollback_drops_an_added_foreign_key_before_its_target(self):
        """A column added later may point at a table created after its own."""
        tsql = self._translate(
            "CREATE TABLE p (id TEXT PRIMARY KEY);\n"
            "CREATE TABLE q (id TEXT PRIMARY KEY);\n"
            "ALTER TABLE p ADD COLUMN q_id TEXT REFERENCES q(id);",
            {"p.id": "ID", "q.id": "ID", "p.q_id": "ID"})
        rollback = tsql[tsql.index("  ROLLBACK"):]
        self.assertLess(rollback.index("DROP CONSTRAINT IF EXISTS [FK_p_q_id]"),
                        rollback.index("DROP TABLE IF EXISTS psa.[q]"))

    def test_a_one_line_table_keeps_every_column(self):
        """zip() over two splits once dropped every column after the first."""
        tsql = self._translate(
            "CREATE TABLE t (id TEXT PRIMARY KEY, k TEXT NOT NULL CHECK (k IN ('A','B')), n INTEGER);",
            {"t.id": "ID", "t.k": "CODE"})
        self.assertIn("[k] NVARCHAR(32) NOT NULL CONSTRAINT [CK_t_01] CHECK (k IN ('A','B'))", tsql)
        self.assertIn("[n] INT NULL", tsql)

    def test_old_in_a_trigger_condition_stops_the_build(self):
        with self.assertRaises(Unsupported) as caught:
            self._translate(
                "CREATE TABLE t (a TEXT);\n"
                "CREATE TRIGGER g BEFORE UPDATE ON t FOR EACH ROW WHEN OLD.a <> NEW.a"
                " BEGIN SELECT RAISE(ABORT, 'no'); END;", {"t.a": "NAME"})
        self.assertIn("OLD.", str(caught.exception))

    def test_two_unique_constraints_get_two_names(self):
        tsql = self._translate("CREATE TABLE t (a TEXT NOT NULL, b TEXT NOT NULL,\n"
                               "  UNIQUE (a),\n  UNIQUE (b));", {"t.a": "ID", "t.b": "ID"})
        self.assertIn("CONSTRAINT [UQ_t] UNIQUE ([a])", tsql)
        self.assertIn("CONSTRAINT [UQ_t_02] UNIQUE ([b])", tsql)

    def test_the_verify_gate_counts_unique_indexes_it_expects(self):
        """A filtered unique index is declared, so the gate must count it, or a
        correct install on SQL Server rolls itself back."""
        tsql = self._translate(
            "CREATE TABLE t (a TEXT);\nCREATE INDEX i ON t (a);\n"
            "CREATE UNIQUE INDEX u ON t (a) WHERE a IS NOT NULL;", {"t.a": "ID"})
        self.assertIn("@Indexes < 2", tsql)
        gate = tsql[tsql.index("SELECT @Indexes"):tsql.index("@Indexes < 2")]
        self.assertNotIn("is_unique = 0", gate)
        self.assertIn("is_unique_constraint = 0", gate)

    def test_a_trigger_body_that_is_not_a_raise_stops_the_build(self):
        with self.assertRaises(Unsupported) as caught:
            self._translate(
                "CREATE TABLE t (a TEXT);\n"
                "CREATE TRIGGER g AFTER INSERT ON t FOR EACH ROW WHEN NEW.a = 'x'"
                " BEGIN UPDATE t SET a = 'y'; END;",
                {"t.a": "NAME"})
        self.assertIn("SELECT RAISE", str(caught.exception))


# ============================================================ Phase B additions
#
# The fulfiller surfaces: the on-call rota, the closed loop, the auth that lets
# the desk answer when the WAN is down, and the WSGI app that carries all three.

import base64 as _b64        # noqa: E402
import hashlib as _hashlib   # noqa: E402
import io as _io             # noqa: E402
import json as _json         # noqa: E402
import secrets as _secrets   # noqa: E402
import time as _time         # noqa: E402
import urllib.error            # noqa: E402
import urllib.parse as _urlparse   # noqa: E402
from wsgiref.validate import validator as _validator   # noqa: E402

from psaspine.web import Config, make_app, auth as webauth  # noqa: E402
from psaspine.web import api as webapi  # noqa: E402


def _b64u(raw: bytes) -> str:
    return _b64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _miller_rabin(n: int, rounds: int = 12) -> bool:
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(rounds):
        a = 2 + _secrets.randbelow(n - 3)
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _prime(bits: int) -> int:
    while True:
        cand = _secrets.randbits(bits) | (1 << (bits - 1)) | 1
        if _miller_rabin(cand):
            return cand


def _rsa_keypair(bits: int = 512):
    """A throwaway RSA keypair in pure Python, so the RS256 verifier is proven
    end to end without a crypto dependency and without a network. Small primes:
    this is a signature-shape test, not a strength claim."""
    p = _prime(bits)
    q = _prime(bits)
    while q == p:
        q = _prime(bits)
    n = p * q
    e = 65537
    d = pow(e, -1, (p - 1) * (q - 1))
    return n, e, d


def _sign_rs256(claims: dict, n: int, d: int, *, kid: str = "k1") -> str:
    header = _b64u(_json.dumps({"alg": "RS256", "kid": kid}).encode())
    body = _b64u(_json.dumps(claims).encode())
    signing_input = f"{header}.{body}".encode("ascii")
    k = (n.bit_length() + 7) // 8
    der = bytes.fromhex("3031300d060960864801650304020105000420")
    tail = der + _hashlib.sha256(signing_input).digest()
    em = b"\x00\x01" + b"\xff" * (k - len(tail) - 3) + b"\x00" + tail
    sig = pow(int.from_bytes(em, "big"), d, n).to_bytes(k, "big")
    return f"{header}.{body}." + _b64u(sig)


class OnCallTest(unittest.TestCase):
    """011 — the rota answers 'who is on shift now', over the org chart."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.conn.execute(
            "INSERT OR REPLACE INTO board (board_id, display_name, phase, fulfiller_group,"
            " owner, deputy, is_live) VALUES ('IT_HELP','IT Help','2','Dada','a','b',1)")
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _slot(self, member, role, start, end):
        self.conn.execute(
            "INSERT INTO oncall_slot (slot_id, board_id, member, role, starts_at, ends_at)"
            " VALUES (?,?,?,?,?,?)",
            (f"OC-{member}-{start}", "IT_HELP", member, role, start, end))
        self.conn.commit()

    def test_the_member_on_shift_now_is_returned(self):
        self._slot("nightnurse", "ON_CALL", "2026-09-17 18:00", "2026-09-18 06:00")
        who = board.current_oncall(self.conn, "IT_HELP", "ON_CALL",
                                   at=datetime(2026, 9, 17, 23, 0))
        self.assertEqual(who, "nightnurse")

    def test_nobody_on_shift_is_none(self):
        self._slot("nightnurse", "ON_CALL", "2026-09-17 18:00", "2026-09-18 06:00")
        who = board.current_oncall(self.conn, "IT_HELP", "ON_CALL",
                                   at=datetime(2026, 9, 17, 12, 0))
        self.assertIsNone(who)

    def test_end_is_exclusive(self):
        self._slot("nightnurse", "ON_CALL", "2026-09-17 18:00", "2026-09-18 06:00")
        self.assertIsNone(board.current_oncall(
            self.conn, "IT_HELP", "ON_CALL", at=datetime(2026, 9, 18, 6, 0)))

    def test_overlap_resolves_to_the_later_start(self):
        """A hand-off writes a new slot; the new slot wins."""
        self._slot("early", "ON_CALL", "2026-09-17 18:00", "2026-09-18 08:00")
        self._slot("relief", "ON_CALL", "2026-09-17 23:00", "2026-09-18 08:00")
        self.assertEqual(board.current_oncall(
            self.conn, "IT_HELP", "ON_CALL", at=datetime(2026, 9, 18, 1, 0)), "relief")

    def test_role_is_not_crossed(self):
        self._slot("oncall1", "ON_CALL", "2026-09-17 18:00", "2026-09-18 06:00")
        self.assertIsNone(board.current_oncall(
            self.conn, "IT_HELP", "DUTY_MANAGER", at=datetime(2026, 9, 17, 23, 0)))


class ClosedLoopTest(unittest.TestCase):
    """012 — answering the requester and banding the effort as one action."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.conn.executescript(
            "INSERT OR REPLACE INTO board (board_id, display_name, phase, fulfiller_group, owner,"
            " deputy, is_live, closed_loop_required) VALUES"
            " ('IT_HELP','IT Help','2','Dada','a','b',1,1);"
            "INSERT OR REPLACE INTO board_status (board_status_id, board_id, name, escalation_status,"
            " is_default) VALUES ('IT_HELP.NEW','IT_HELP','New','NOT_RESPONDED',1);"
            "INSERT OR REPLACE INTO board_status (board_status_id, board_id, name, escalation_status,"
            " is_closed) VALUES ('IT_HELP.DONE','IT_HELP','Resolved','RESOLVED',1);")
        self._ticket("ITO-1", "BASELINE", "INCIDENT")
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _ticket(self, wid, basis, path, variation_id=None):
        self.conn.execute(
            "INSERT INTO work_item (work_item_id, source, name, entity_id, contract_basis,"
            " variation_id) VALUES (?,?,?,?,?,?)",
            (wid, "desk", "A thing", "PMC", basis, variation_id))
        self.conn.execute(
            "INSERT INTO ticket (work_item_id, board_id, path, impact, urgency, priority,"
            " priority_source, requested_at, opened_at, state, board_status_id)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (wid, "IT_HELP", path, "I3", "U3", "P3", "MATRIX",
             "2026-09-17 08:00", "2026-09-17 08:00", "NEW", "IT_HELP.NEW"))

    def test_the_loop_writes_a_reply_and_bands_the_effort_in_one_go(self):
        result = board.close_loop(
            self.conn, "ITO-1", "IT_HELP.DONE", body="Fixed, back online.",
            sent_by="cadano", at=datetime(2026, 9, 17, 9, 0), band_hours=0.5)
        self.conn.commit()
        reply = self.conn.execute("SELECT * FROM loop_reply").fetchone()
        entry = self.conn.execute("SELECT * FROM time_entry").fetchone()
        self.assertEqual(reply["body"], "Fixed, back online.")
        self.assertEqual(reply["effort_minutes"], 30)
        self.assertEqual(entry["band_hours"], 0.5)
        self.assertEqual(entry["loop_reply_id"], reply["loop_reply_id"])
        self.assertEqual(result["status"]["state"], "CLOSED")

    def test_a_holding_reply_bands_nothing(self):
        board.close_loop(self.conn, "ITO-1", "IT_HELP.DONE", body="Chasing the vendor.",
                         sent_by="cadano", at=datetime(2026, 9, 17, 9, 0))
        self.conn.commit()
        self.assertEqual(self.conn.execute("SELECT COUNT(*) c FROM time_entry").fetchone()["c"], 0)
        self.assertIsNone(self.conn.execute("SELECT effort_minutes FROM loop_reply").fetchone()["effort_minutes"])

    def test_a_variation_ticket_with_no_variation_is_refused_before_any_write(self):
        self._ticket("ITO-2", "VARIATION", "VARIATION")
        self.conn.commit()
        with self.assertRaises(board.EffortRefused):
            board.close_loop(self.conn, "ITO-2", "IT_HELP.DONE", body="Done.",
                             sent_by="cadano", at=datetime(2026, 9, 17, 9, 0), band_hours=2)
        # Nothing partial left behind.
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM loop_reply WHERE work_item_id='ITO-2'").fetchone()["c"], 0)


class TimeEntryTest(unittest.TestCase):
    """033 and board.add_time: time as Dada PSA records it (start and end or
    actual hours, a deduction, a work role and type, a bill option), with the
    spine's band derived from it so §5.2's arithmetic stands."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 28, 9, 0)
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)
        self.wid = tickets.open_ticket(self.conn, board_id="IT_HELP", summary="PC slow", impact="I3",
                                       urgency="U3", requested_by=None, at=self.at, entity_id="PMC")

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _entry(self):
        return self.conn.execute("SELECT * FROM time_entry ORDER BY time_entry_id DESC").fetchone()

    def test_start_and_end_give_the_hours_less_the_deduction_and_the_band(self):
        board.add_time(self.conn, self.wid, at=self.at, actor="alice", charge_method="INCLUDED_IN_MONTHLY_FEE",
                       time_start="2026-09-28 09:00", time_end="2026-09-28 12:10", hours_deduct=0.5,
                       work_role_id="TECHNICIAN", work_type_id="ON_SITE", billable_option="BILLABLE")
        e = self._entry()
        self.assertEqual((e["actual_hours"], e["hours_deduct"], e["band_hours"]), (2.75, 0.5, 4))
        self.assertEqual((e["time_start"], e["time_end"], e["worked_on"]),
                         ("2026-09-28 09:00", "2026-09-28 12:10", "2026-09-28"))
        self.assertEqual((e["work_role_id"], e["work_type_id"], e["billable_option"], e["entry_status"]),
                         ("TECHNICIAN", "ON_SITE", "BILLABLE", "OPEN"))
        self.assertEqual(e["performed_by"], "alice")
        line = self.conn.execute("SELECT detail FROM ticket_event WHERE kind = 'TIME'").fetchone()[0]
        self.assertIn("2.75 h (09:00–12:10, less 0.5 h)", line)
        self.assertIn("band 4 h", line)

    def test_actual_hours_are_kept_to_the_quarter_hour_and_banded_up(self):
        for given, hours, band in (("1", 1, 2), ("0.13", 0.25, 0.5), ("1.6", 1.5, 2), ("8", 8, 8),
                                   ("8.01", 8, 8), ("8.2", 8.25, 20)):
            board.add_time(self.conn, self.wid, at=self.at, actor="alice",
                           charge_method="INCLUDED_IN_MONTHLY_FEE", actual_hours=given)
            e = self._entry()
            self.assertEqual((e["actual_hours"], e["band_hours"]), (hours, band), given)
            self.assertIsNone(e["time_start"])
        # the defaults the reference PSA takes from the member: the first role and type in Setup
        self.assertEqual((e["work_role_id"], e["work_type_id"], e["billable_option"]),
                         ("TECHNICIAN", "REGULAR", "NO_DEFAULT"))

    def test_connectwises_rules_are_refused_in_a_sentence(self):
        cases = [
            (dict(actual_hours="2", time_start="2026-09-28 09:00", time_end="2026-09-28 10:00"), "not both"),
            (dict(time_start="2026-09-28 09:00"), "needs an end time"),
            (dict(time_start="2026-09-28 10:00", time_end="2026-09-28 09:00"), "not after the start"),
            (dict(time_start="2026-09-28 09:00", time_end="2026-09-28 09:30", hours_deduct=0.5), "comes to nothing"),
            (dict(actual_hours="abc"), "is a number"),
            (dict(), "or the actual hours"),
            (dict(actual_hours="21"), "more than one entry holds"),
            (dict(actual_hours="1", hours_deduct=-1), "cannot be negative"),
            (dict(actual_hours="1", work_role_id="NOPE"), "work role that is in use"),
            (dict(actual_hours="1", work_type_id="NOPE"), "work type that is in use"),
            (dict(actual_hours="1", billable_option="MAYBE"), "bill option"),
        ]
        for kw, words in cases:
            with self.assertRaises(board.EffortRefused, msg=words) as c:
                board.add_time(self.conn, self.wid, at=self.at, actor="alice",
                               charge_method="INCLUDED_IN_MONTHLY_FEE", **kw)
            self.assertIn(words, str(c.exception), kw)
        with self.assertRaises(board.EffortRefused) as c:
            board.add_time(self.conn, self.wid, at=self.at, actor="alice", charge_method=None, actual_hours="1")
        self.assertIn("never assumed", str(c.exception))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM time_entry").fetchone()[0], 0)

    def test_a_retired_role_stays_on_old_entries_and_is_refused_on_new_ones(self):
        board.add_time(self.conn, self.wid, at=self.at, actor="alice", charge_method="INCLUDED_IN_MONTHLY_FEE",
                       actual_hours="1", work_role_id="ENGINEER")
        self.conn.execute("UPDATE work_role SET inactive = 1 WHERE work_role_id = 'ENGINEER'")
        with self.assertRaises(board.EffortRefused):
            board.add_time(self.conn, self.wid, at=self.at, actor="alice",
                           charge_method="INCLUDED_IN_MONTHLY_FEE", actual_hours="1", work_role_id="ENGINEER")
        self.assertEqual(self._entry()["work_role_id"], "ENGINEER")

    def test_a_note_carries_its_time_entry_and_both_are_refused_together(self):
        r = board.add_note(self.conn, self.wid, body="Swapped the toner.", flag="DISCUSSION", actor="alice",
                           at=self.at, charge_method="INCLUDED_IN_MONTHLY_FEE",
                           time={"time_start": "2026-09-28 14:00", "time_end": "2026-09-28 14:20",
                                 "work_type_id": "REMOTE", "performed_by": "bob"})
        self.assertEqual((r["actual_hours"], r["band_hours"]), (0.25, 0.5))
        e = self._entry()
        note = self.conn.execute("SELECT ticket_event_id FROM ticket_event WHERE detail = 'Swapped the toner.'").fetchone()
        self.assertEqual(e["ticket_event_id"], note[0])
        self.assertEqual((e["performed_by"], e["entered_by"], e["work_type_id"]), ("bob", "alice", "REMOTE"))
        # refused whole: no note is written when the time is wrong
        with self.assertRaises(board.EffortRefused):
            board.add_note(self.conn, self.wid, body="Nope.", flag="DISCUSSION", actor="alice", at=self.at,
                           charge_method="INCLUDED_IN_MONTHLY_FEE", time={"actual_hours": "x"})
        self.assertIsNone(self.conn.execute("SELECT 1 FROM ticket_event WHERE detail = 'Nope.'").fetchone())
        # the old spelling still works: band_hours means actual hours
        board.add_note(self.conn, self.wid, body="Old call.", flag="INTERNAL", actor="alice", at=self.at,
                       band_hours=2, charge_method="CAPACITY_UPLIFT")
        self.assertEqual((self._entry()["actual_hours"], self._entry()["band_hours"]), (2, 2))

    def test_the_uplift_evidence_still_reads_the_band(self):
        from psaspine import reports
        board.add_time(self.conn, self.wid, at=self.at, actor="alice", charge_method="CAPACITY_UPLIFT",
                       actual_hours="2.5")
        rows = reports.effort_by_basis(self.conn)
        self.assertEqual([r["band_hours"] for r in rows], [4])


class DeskParityTest(unittest.TestCase):
    """Three board behaviours the reference PSA has that a technician expects (the
    parity pass of 28 Sep 2026): the owner is emailed on assignment when the
    board says so; a note's "Contact" tick decides the requester's email; and
    a board's own default work role and type start a time entry."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 28, 9, 0)
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)
        self.conn.execute(
            "INSERT INTO contact (contact_id, entity_id, display_name, email, sam_account, source, inactive,"
            " created_at) VALUES ('C_BOB', 'PMC', 'Bob', 'bob@pmcne.ph', 'bob', 'AD', 0, '2026')")
        self.wid = tickets.open_ticket(self.conn, board_id="IT_HELP", summary="Printer down", impact="I3",
                                       urgency="U3", requested_by="ward@pmcne.ph", at=self.at, entity_id="PMC")
        # switched on after the open, so the "we have it" email is not in the way
        self.conn.execute("UPDATE board SET notify_owner = 1, notify_requester = 1 WHERE board_id = 'IT_HELP'")

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _mails(self, role):
        return self.conn.execute("SELECT recipient, subject, body FROM notification WHERE recipient_role = ?"
                                 " ORDER BY notification_id", (role,)).fetchall()

    def test_the_owner_is_emailed_on_assignment_once_and_never_by_themselves(self):
        board.update_fields(self.conn, self.wid, at=self.at, actor="alice", owner="bob")
        mails = self._mails("OWNER")
        self.assertEqual([(m["recipient"], m["subject"]) for m in mails],
                         [("bob", f"[{self.wid}] Assigned to you on PMO Helpdesk")])
        self.assertNotIn("Printer", mails[0]["subject"])                 # no summary leaves the desk
        self.assertIn("assigned to you by alice", mails[0]["body"])
        # a second assignment while the first is unsent adds nothing
        board.update_fields(self.conn, self.wid, at=self.at, actor="alice", owner="carol")
        board.update_fields(self.conn, self.wid, at=self.at, actor="alice", owner="bob")
        self.assertEqual(len(self._mails("OWNER")), 1)
        # taking a ticket yourself is not news; an owner with no address gets nothing
        self.conn.execute("DELETE FROM notification")
        board.update_fields(self.conn, self.wid, at=self.at, actor="bob", owner="carol")
        board.update_fields(self.conn, self.wid, at=self.at, actor="Bob", owner="bob")
        self.assertEqual(self._mails("OWNER"), [])
        # off by default: a board that has not said so sends none
        self.conn.execute("UPDATE board SET notify_owner = NULL WHERE board_id = 'IT_HELP'")
        board.update_fields(self.conn, self.wid, at=self.at, actor="alice", owner="carol")
        board.update_fields(self.conn, self.wid, at=self.at, actor="alice", owner="bob")
        self.assertEqual(self._mails("OWNER"), [])
        # a move that names an owner emails them too
        self.conn.execute("UPDATE board SET notify_owner = 1 WHERE board_id = 'IT_HELP'")
        setup.apply_starter(self.conn, "UNROUTED", actor="t", at=self.at)
        other = tickets.open_ticket(self.conn, board_id="UNROUTED", summary="Route me", impact="I3",
                                    urgency="U3", requested_by=None, at=self.at, entity_id="PMC")
        board.move(self.conn, other, "IT_HELP", at=self.at, actor="alice", owner="bob", reason="routed")
        self.assertEqual([m["recipient"] for m in self._mails("OWNER")], ["bob"])

    def test_a_notes_contact_tick_decides_the_requesters_email(self):
        board.add_note(self.conn, self.wid, body="Quiet note.", flag="DISCUSSION", actor="alice", at=self.at,
                       notify_requester=False)
        self.assertEqual(self._mails("REQUESTER"), [])
        board.add_note(self.conn, self.wid, body="Loud note.", flag="DISCUSSION", actor="alice", at=self.at)
        self.assertEqual(len(self._mails("REQUESTER")), 1)

    def test_a_boards_own_work_role_and_type_start_its_time_entries(self):
        self.conn.execute("UPDATE board SET default_work_role_id = 'ENGINEER', default_work_type_id = 'ON_SITE'"
                          " WHERE board_id = 'IT_HELP'")
        self.assertEqual(board.time_defaults(self.conn, board_id="IT_HELP"),
                         {"work_role_id": "ENGINEER", "work_type_id": "ON_SITE"})
        board.add_time(self.conn, self.wid, at=self.at, actor="alice", charge_method="INCLUDED_IN_MONTHLY_FEE",
                       actual_hours="1")
        e = self.conn.execute("SELECT work_role_id, work_type_id FROM time_entry").fetchone()
        self.assertEqual(tuple(e), ("ENGINEER", "ON_SITE"))
        # a retired default falls back to the first in use
        self.conn.execute("UPDATE work_role SET inactive = 1 WHERE work_role_id = 'ENGINEER'")
        self.assertEqual(board.time_defaults(self.conn, board_id="IT_HELP")["work_role_id"], "TECHNICIAN")
        self.assertEqual(board.time_defaults(self.conn, board_id="NOPE")["work_type_id"], "REGULAR")


class AuthTest(unittest.TestCase):
    """The two ways in: sealed break-glass, and a hand-verified Entra token."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.secret = _secrets.token_bytes(32)

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_scrypt_round_trips_and_rejects_the_wrong_password(self):
        h = webauth.hash_password("correct horse battery staple")
        self.assertTrue(webauth.verify_password("correct horse battery staple", h))
        self.assertFalse(webauth.verify_password("Tr0ub4dor&3", h))

    def test_a_local_account_is_created_and_authenticates(self):
        webauth.create_local_account(self.conn, "oncall", "shift-secret",
                                     at=datetime(2026, 9, 17))
        self.conn.commit()
        user = webauth.authenticate_local(self.conn, "oncall", "shift-secret",
                                          at=datetime(2026, 9, 17, 23, 0))
        self.assertEqual(user.id, "oncall")
        self.assertEqual(user.via, "local")

    def test_the_stored_hash_is_never_the_password(self):
        webauth.create_local_account(self.conn, "oncall", "shift-secret",
                                     at=datetime(2026, 9, 17))
        stored = self.conn.execute(
            "SELECT scrypt_hash FROM local_account WHERE username='oncall'").fetchone()["scrypt_hash"]
        self.assertTrue(stored.startswith("scrypt$"))
        self.assertNotIn("shift-secret", stored)

    def test_a_creation_and_every_login_is_audited(self):
        webauth.create_local_account(self.conn, "oncall", "shift-secret",
                                     at=datetime(2026, 9, 17))
        webauth.authenticate_local(self.conn, "oncall", "shift-secret",
                                   at=datetime(2026, 9, 17, 23, 0))
        actions = [r["action"] for r in self.conn.execute(
            "SELECT action FROM audit_event WHERE subject_id='oncall' ORDER BY audit_id")]
        self.assertEqual(actions, ["LOCAL_ACCOUNT_CREATE", "LOCAL_LOGIN"])

    def test_a_refused_login_is_audited_too(self):
        webauth.create_local_account(self.conn, "oncall", "shift-secret",
                                     at=datetime(2026, 9, 17))
        with self.assertRaises(webauth.Unauthenticated):
            webauth.authenticate_local(self.conn, "oncall", "wrong",
                                       at=datetime(2026, 9, 17, 23, 0))
        self.assertTrue(self.conn.execute(
            "SELECT 1 FROM audit_event WHERE action='LOCAL_LOGIN_REFUSED'").fetchone())

    def test_a_disabled_account_cannot_log_in(self):
        webauth.create_local_account(self.conn, "oncall", "shift-secret",
                                     at=datetime(2026, 9, 17))
        self.conn.execute("UPDATE local_account SET disabled=1 WHERE username='oncall'")
        self.conn.commit()
        with self.assertRaises(webauth.Unauthenticated):
            webauth.authenticate_local(self.conn, "oncall", "shift-secret",
                                       at=datetime(2026, 9, 17, 23, 0))

    def test_a_duplicate_account_is_refused_not_overwritten(self):
        webauth.create_local_account(self.conn, "oncall", "one", at=datetime(2026, 9, 17))
        with self.assertRaises(ValueError):
            webauth.create_local_account(self.conn, "oncall", "two", at=datetime(2026, 9, 17))

    def test_a_session_cookie_round_trips_and_is_tamper_evident(self):
        user = webauth.User(id="oncall", name="On Call", via="local")
        token = webauth.open_session(user, self.secret)
        self.assertEqual(webauth.read_session(token, self.secret)["sub"], "oncall")
        self.assertIsNone(webauth.read_session(token + "x", self.secret))
        self.assertIsNone(webauth.read_session(token, _secrets.token_bytes(32)))

    def test_an_expired_session_is_rejected(self):
        user = webauth.User(id="oncall", name="On Call")
        old = webauth.open_session(user, self.secret, now=1.0)
        self.assertIsNone(webauth.read_session(old, self.secret))

    def test_a_correctly_signed_entra_token_verifies(self):
        n, e, d = _rsa_keypair()
        now = int(_time.time())
        token = _sign_rs256({"oid": "u-1", "name": "Alice",
                             "preferred_username": "alice@pmcne.ph", "aud": "client-x",
                             "iss": "https://login.microsoftonline.com/tenant-y/v2.0",
                             "nbf": now - 10, "exp": now + 3600}, n, d)
        user = webauth.verify_entra_token(token, {"k1": {"n": n, "e": e}},
                                          tenant="tenant-y", client_id="client-x", now=now)
        self.assertEqual(user.id, "u-1")
        self.assertEqual(user.email, "alice@pmcne.ph")

    def test_a_tampered_or_wrong_token_is_refused(self):
        n, e, d = _rsa_keypair()
        n2, e2, d2 = _rsa_keypair()
        now = int(_time.time())
        jwks = {"k1": {"n": n, "e": e}}
        good = {"oid": "u", "aud": "client-x",
                "iss": "https://login.microsoftonline.com/tenant-y/v2.0",
                "nbf": now - 10, "exp": now + 3600}
        # signed by a different key
        forged = _sign_rs256(good, n2, d2)
        with self.assertRaises(webauth.Unauthenticated):
            webauth.verify_entra_token(forged, jwks, tenant="tenant-y",
                                       client_id="client-x", now=now)
        # expired well past the 60s leeway
        expired = _sign_rs256({**good, "nbf": now - 7200, "exp": now - 3600}, n, d)
        with self.assertRaises(webauth.Unauthenticated):
            webauth.verify_entra_token(expired, jwks, tenant="tenant-y",
                                       client_id="client-x", now=now)
        # wrong audience
        wrong_aud = _sign_rs256({**good, "aud": "someone-else"}, n, d)
        with self.assertRaises(webauth.Unauthenticated):
            webauth.verify_entra_token(wrong_aud, jwks, tenant="tenant-y",
                                       client_id="client-x", now=now)
        # wrong tenant
        wrong_iss = _sign_rs256(
            {**good, "iss": "https://login.microsoftonline.com/evil/v2.0"}, n, d)
        with self.assertRaises(webauth.Unauthenticated):
            webauth.verify_entra_token(wrong_iss, jwks, tenant="tenant-y",
                                       client_id="client-x", now=now)


def t_esc(text: str) -> str:
    return html.escape(text, quote=True).replace("'", "&#x27;")


class WebWSGITest(unittest.TestCase):
    """The WSGI app: PEP 3333 conformance, the seven surfaces, and the one
    guarantee the record wrote and never ran — a non-member is provably excluded
    from a restricted board (§11 test 5)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(_target(self.tmp))
        conn = _fresh(self.tmp)
        conn.executescript(
            "INSERT OR IGNORE INTO entity (entity_id,name,is_covered,note) VALUES ('PMC','PMC',1,'');"
            "INSERT OR REPLACE INTO board (board_id,display_name,phase,fulfiller_group,owner,deputy,"
            " is_live,is_unrouted,closed_loop_required) VALUES"
            " ('IT_HELP','IT Help','2','Dada','a','b',1,0,1);"
            "INSERT OR REPLACE INTO board (board_id,display_name,phase,fulfiller_group,owner,deputy,"
            " is_live,restricted) VALUES ('PHI','PHI Board','2','Clin','a','b',1,1);"
            "INSERT OR REPLACE INTO board_status (board_status_id,board_id,name,escalation_status,"
            " is_default) VALUES ('IT_HELP.NEW','IT_HELP','New','NOT_RESPONDED',1);"
            "INSERT OR REPLACE INTO board_status (board_status_id,board_id,name,escalation_status,"
            " is_closed) VALUES ('IT_HELP.DONE','IT_HELP','Resolved','RESOLVED',1);"
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','alice','ADMIN');"
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('PHI','alice','WORK');"
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','carol','READ');"
            "INSERT INTO work_item (work_item_id,source,name,entity_id,contract_basis)"
            " VALUES ('ITO-1','desk','Printer down','PMC','BASELINE');"
            "INSERT INTO ticket (work_item_id,board_id,path,impact,urgency,priority,"
            " priority_source,requested_at,opened_at,state,board_status_id) VALUES"
            " ('ITO-1','IT_HELP','INCIDENT','I1','U1','P1','MATRIX','2026-09-17 08:00',"
            "'2026-09-17 08:00','NEW','IT_HELP.NEW');"
            "INSERT INTO work_item (work_item_id,source,name,entity_id,contract_basis)"
            " VALUES ('ITO-9','desk','Sensitive','PMC','BASELINE');"
            "INSERT INTO ticket (work_item_id,board_id,path,impact,urgency,priority,"
            " priority_source,requested_at,opened_at,state) VALUES"
            " ('ITO-9','PHI','INCIDENT','I1','U1','P1','MATRIX','2026-09-17 08:00',"
            "'2026-09-17 08:00','NEW');")
        conn.commit()
        conn.close()
        self.config = Config(session_secret=_secrets.token_bytes(32))
        self.raw = make_app(self.db_path, config=self.config,
                            clock=lambda: datetime(2026, 9, 17, 10, 0))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _environ(self, method, path, *, cookie=None, body=b"", query="", headers=None,
                 remote_addr=None):
        env = {
            "REQUEST_METHOD": method, "PATH_INFO": path, "SCRIPT_NAME": "",
            "QUERY_STRING": query, "SERVER_NAME": "t", "SERVER_PORT": "80",
            "SERVER_PROTOCOL": "HTTP/1.1", "wsgi.version": (1, 0),
            "wsgi.url_scheme": "http", "wsgi.input": _io.BytesIO(body),
            "wsgi.errors": _io.StringIO(), "wsgi.multithread": False,
            "wsgi.multiprocess": False, "wsgi.run_once": False}
        if body:
            env["CONTENT_LENGTH"] = str(len(body))
            env["CONTENT_TYPE"] = "application/x-www-form-urlencoded"
        if cookie:
            env["HTTP_COOKIE"] = cookie
        for k, v in (headers or {}).items():
            env["HTTP_" + k.upper().replace("-", "_")] = v
        if remote_addr:
            env["REMOTE_ADDR"] = remote_addr
        return env

    def _call(self, method, path, *, cookie=None, form=None, query="", validate=True,
              headers=None, remote_addr=None):
        body = _urlparse.urlencode(form).encode() if form else b""
        app = _validator(self.raw) if validate else self.raw
        captured = {}

        def start_response(status, headers, exc_info=None):
            captured["status"] = status
            captured["headers"] = headers
        it = app(self._environ(method, path, cookie=cookie, body=body, query=query,
                               headers=headers, remote_addr=remote_addr), start_response)
        try:
            payload = b"".join(it).decode()
        finally:
            if hasattr(it, "close"):
                it.close()
        return captured["status"], captured.get("headers", []), payload

    def _cookie_for(self, member, **kw):
        user = webauth.User(id=member, name=member, **kw)
        return "psa_session=" + webauth.open_session(user, self.config.session_secret)

    # ------------------------------------------------------- conformance & auth

    def test_a_sysadmin_names_a_memberless_boards_first_administrator_once(self):
        conn = db.connect(self.db_path)
        conn.execute("INSERT OR REPLACE INTO board (board_id,display_name,phase,fulfiller_group,is_live,is_unrouted)"
                     " VALUES ('SEEDED','Seeded board','2','Dada',0,0)")
        conn.commit()
        conn.close()
        root = self._cookie_for("root", is_sysadmin=True)
        status, _, body = self._call("GET", "/admin", cookie=root)
        self.assertIn("Boards with no administrator", body)
        self.assertIn("/admin/board/SEEDED/claim", body)
        self.assertNotIn("/admin/board/IT_HELP/claim", body)          # IT_HELP has members here
        status, headers, _ = self._call("POST", "/admin/board/SEEDED/claim", cookie=root,
                                        form={"member": "dana"})
        self.assertTrue(status.startswith("303"))
        conn = db.connect(self.db_path)
        self.assertEqual(tuple(conn.execute("SELECT member, access FROM board_member WHERE board_id = 'SEEDED'").fetchone()),
                         ("dana", "ADMIN"))
        self.assertEqual(conn.execute("SELECT detail FROM audit_event WHERE action = 'BOARD_MEMBER'").fetchone()[0],
                         "first administrator dana (the board had no members)")
        conn.close()
        # once: the second claim is refused, and a non-sysadmin never gets there
        status, headers, _ = self._call("POST", "/admin/board/SEEDED/claim", cookie=root, form={"member": "eve"})
        self.assertIn("already has members", _urlparse.unquote(dict(headers)["Location"]))
        status, _, _ = self._call("POST", "/admin/board/SEEDED/claim", cookie=self._cookie_for("alice"),
                                  form={"member": "alice"})
        self.assertTrue(status.startswith("403"), status)
        _, _, body = self._call("GET", "/admin", cookie=root)
        self.assertNotIn("/admin/board/SEEDED/claim", body)       # UNROUTED, from the seed, may still be listed

    def test_the_app_is_pep3333_conformant_when_unauthenticated(self):
        status, _, body = self._call("GET", "/")
        self.assertTrue(status.startswith("401"))
        self.assertIn("Break-glass", body)

    def test_a_break_glass_login_opens_a_session(self):
        conn = db.connect(self.db_path)
        webauth.create_local_account(conn, "oncall", "shift-secret",
                                     at=datetime(2026, 9, 17), is_sysadmin=True)
        conn.execute("INSERT OR REPLACE INTO board_member (board_id,member,access)"
                     " VALUES ('IT_HELP','oncall','WORK')")
        conn.commit()
        conn.close()
        status, headers, _ = self._call(
            "POST", "/login", form={"username": "oncall", "password": "shift-secret", "next": "/"})
        self.assertTrue(status.startswith("303"))
        self.assertTrue(any(k == "Set-Cookie" and "psa_session=" in v for k, v in headers))

    # -------------------------------------------------------------- the surfaces

    def test_each_surface_renders_for_a_member(self):
        cookie = self._cookie_for("alice")
        for path, needle in (("/", "ITO-1"), ("/ticket/ITO-1", "Printer down"),
                             ("/dispatch", "Dispatch"), ("/oncall", "On-call"),
                             ("/uplift", "Uplift"), ("/admin", "Setup"),
                             ("/ticket/new", "New ticket"),
                             ("/admin/board/IT_HELP", "Statuses")):
            status, _, body = self._call("GET", path, cookie=cookie)
            self.assertTrue(status.startswith("200"), f"{path} -> {status}")
            self.assertIn(needle, body)

    # ------------------------------------------------ the Dada PSA-style desk

    def _db(self):
        return db.connect(self.db_path)

    def test_a_note_is_flagged_and_can_carry_banded_time(self):
        cookie = self._cookie_for("alice")
        status, headers, _ = self._call("POST", "/ticket/ITO-1/note", cookie=cookie, form={
            "body": "Checked the switch.", "flag": "INTERNAL", "hours": "2",
            "charge": "INCLUDED_IN_MONTHLY_FEE"})
        self.assertTrue(status.startswith("303"))
        conn = self._db()
        self.assertEqual(conn.execute(
            "SELECT note_flag FROM ticket_event WHERE detail = 'Checked the switch.'"
        ).fetchone()[0], "INTERNAL")
        self.assertEqual(conn.execute(
            "SELECT band_hours, charge_method FROM time_entry WHERE work_item_id='ITO-1'"
        ).fetchone()[:], (2.0, "INCLUDED_IN_MONTHLY_FEE"))
        conn.close()

    def test_the_time_pod_takes_a_connectwise_time_entry_and_lists_it_like_the_time_tab(self):
        alice = self._cookie_for("alice")
        _, _, page = self._call("GET", "/ticket/ITO-1", cookie=alice)
        for field in ("name=worked_on", "name=start", "name=end", "name=hours", "name=deduct",
                      "name=work_role", "name=work_type", "name=bill", "name=charge"):
            self.assertIn(field, page, field)
        self.assertIn("Add time", page)
        self.assertNotIn("No time</option>", page)                # the band picker is gone
        status, headers, _ = self._call("POST", "/ticket/ITO-1/time", cookie=alice, form={
            "worked_on": "2026-09-17", "start": "09:00", "end": "11:40", "deduct": "0.25",
            "work_role": "ENGINEER", "work_type": "ON_SITE", "bill": "BILLABLE",
            "charge": "INCLUDED_IN_MONTHLY_FEE", "body": "Replaced the switch.", "flag": "INTERNAL"})
        self.assertTrue(status.startswith("303"), status)
        self.assertIn("Time+saved%3A+2.5+h", dict(headers)["Location"])
        conn = self._db()
        e = conn.execute("SELECT * FROM time_entry").fetchone()
        note = conn.execute("SELECT ticket_event_id, note_flag FROM ticket_event WHERE detail = 'Replaced the switch.'").fetchone()
        conn.close()
        self.assertEqual((e["actual_hours"], e["hours_deduct"], e["band_hours"], e["work_role_id"],
                          e["work_type_id"], e["billable_option"], e["time_start"], e["time_end"]),
                         (2.5, 0.25, 4, "ENGINEER", "ON_SITE", "BILLABLE", "2026-09-17 09:00", "2026-09-17 11:40"))
        self.assertEqual((e["ticket_event_id"], note["note_flag"]), (note["ticket_event_id"], "INTERNAL"))
        _, _, page = self._call("GET", "/ticket/ITO-1", cookie=alice)
        self.assertIn("Time · 2.5 h (band 4 h)", page)
        for cell in ("<td>2026-09-17</td>", "<td>alice</td>", "<td>09:00–11:40</td>", "<td class=num>2.5</td>",
                     "<td class=num>0.25</td>", "<td>Engineer</td>", "<td>On-site</td>", "<td>Billable</td>",
                     "<td>Included in monthly fee</td>", "<td class=num>4</td>"):
            self.assertIn(cell, page, cell)
        # both ways at once is Dada PSA's refusal, in a sentence, and nothing is written
        status, headers, _ = self._call("POST", "/ticket/ITO-1/time", cookie=alice, form={
            "worked_on": "2026-09-17", "start": "09:00", "end": "10:00", "hours": "1",
            "charge": "INCLUDED_IN_MONTHLY_FEE"})
        self.assertIn("not+both", dict(headers)["Location"])
        conn = self._db()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM time_entry").fetchone()[0], 1)
        conn.close()
        # a reader cannot
        status, _, _ = self._call("POST", "/ticket/ITO-1/time", cookie=self._cookie_for("carol"),
                                  form={"hours": "1", "charge": "INCLUDED_IN_MONTHLY_FEE"})
        self.assertTrue(status.startswith("404"))

    def test_the_note_composer_carries_the_same_time_fields(self):
        alice = self._cookie_for("alice")
        status, headers, _ = self._call("POST", "/ticket/ITO-1/note", cookie=alice, form={
            "body": "Looked at it.", "flag": "DISCUSSION", "worked_on": "2026-09-17", "hours": "0.4",
            "work_role": "TECHNICIAN", "work_type": "REMOTE", "charge": "CAPACITY_UPLIFT"})
        self.assertIn("Note+saved", dict(headers)["Location"])
        conn = self._db()
        e = conn.execute("SELECT actual_hours, band_hours, work_type_id, worked_on FROM time_entry").fetchone()
        conn.close()
        self.assertEqual(tuple(e), (0.5, 0.5, "REMOTE", "2026-09-17"))

    def test_setup_time_adds_and_retires_work_roles_and_types(self):
        root = self._cookie_for("root", is_sysadmin=True)
        status, _, page = self._call("GET", "/admin/time", cookie=root)
        self.assertTrue(status.startswith("200"))
        for name in ("Technician", "Engineer", "Service manager", "On-call", "Regular", "Remote",
                     "On-site", "After hours", "Internal"):
            self.assertIn(name, page, name)
        _, headers, _ = self._call("POST", "/admin/time/role", cookie=root, form={"name": "Biomedical engineer"})
        self.assertIn("Added+work+role", dict(headers)["Location"])
        _, headers, _ = self._call("POST", "/admin/time/type", cookie=root,
                                   form={"name": "Project", "bill_time": "NO_CHARGE"})
        self.assertIn("Added+work+type", dict(headers)["Location"])
        _, headers, _ = self._call("POST", "/admin/time/role", cookie=root, form={"name": "biomedical engineer"})
        self.assertIn("already", dict(headers)["Location"])
        _, headers, _ = self._call("POST", "/admin/time/toggle", cookie=root, form={"kind": "role", "id": "ENGINEER"})
        self.assertIn("Retired", dict(headers)["Location"])
        conn = self._db()
        self.assertEqual(conn.execute("SELECT inactive FROM work_role WHERE work_role_id = 'ENGINEER'").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT bill_time FROM work_type WHERE work_type_id = 'PROJECT'").fetchone()[0],
                         "NO_CHARGE")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit_event WHERE action LIKE 'WORK_%'").fetchone()[0], 3)
        conn.close()
        # a retired role is no longer offered on the ticket, and a board admin is not a sysadmin
        _, _, page = self._call("GET", "/ticket/ITO-1", cookie=self._cookie_for("alice"))
        self.assertNotIn(">Engineer<", page)
        self.assertIn(">Biomedical engineer<", page)
        status, _, _ = self._call("GET", "/admin/time", cookie=self._cookie_for("alice"))
        self.assertTrue(status.startswith("403"))
        _, _, setup_page = self._call("GET", "/admin", cookie=root)
        self.assertIn("/admin/time", setup_page)

    def test_time_with_no_charge_method_is_refused_and_nothing_is_written(self):
        """The charge method is never assumed (the numerator of an uplift claim)."""
        status, headers, _ = self._call("POST", "/ticket/ITO-1/note",
                                        cookie=self._cookie_for("alice"),
                                        form={"body": "x", "flag": "DISCUSSION", "hours": "2"})
        self.assertIn("err=", dict(headers)["Location"])
        conn = self._db()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM time_entry").fetchone()[0], 0)
        self.assertIsNone(conn.execute(
            "SELECT 1 FROM ticket_event WHERE detail = 'x'").fetchone())
        conn.close()

    def test_a_read_only_member_cannot_add_a_note(self):
        status, _, _ = self._call("POST", "/ticket/ITO-1/note", cookie=self._cookie_for("carol"),
                                  form={"body": "nope", "flag": "DISCUSSION"})
        self.assertTrue(status.startswith("404"))

    def test_the_requester_sees_discussion_and_resolution_never_internal(self):
        conn = self._db()
        conn.execute("UPDATE ticket SET requested_by = 'nurse@pmcne.ph' WHERE work_item_id='ITO-1'")
        board.add_note(conn, "ITO-1", body="We are on it.", flag="DISCUSSION",
                       actor="alice", at=datetime(2026, 9, 17, 9, 0))
        board.add_note(conn, "ITO-1", body="Vendor contract lapsed, do not say.",
                       flag="INTERNAL", actor="alice", at=datetime(2026, 9, 17, 9, 5))
        board.add_note(conn, "ITO-1", body="Replaced the cable.", flag="RESOLUTION",
                       actor="alice", at=datetime(2026, 9, 17, 9, 10))
        conn.commit()
        conn.close()
        status, _, body = self._call("GET", "/my/ITO-1", cookie=self._cookie_for(
            "nurse", email="nurse@pmcne.ph"))
        self.assertTrue(status.startswith("200"), status)
        self.assertIn("We are on it.", body)
        self.assertIn("Replaced the cable.", body)
        self.assertNotIn("Vendor contract lapsed", body)

    def test_a_note_can_also_be_the_resolution_and_internal_stays_internal(self):
        """Dada PSA lets one note carry more than one flag (025)."""
        conn = self._db()
        conn.execute("UPDATE ticket SET requested_by = 'nurse@pmcne.ph' WHERE work_item_id='ITO-1'")
        board.add_note(conn, "ITO-1", body="Swapped the toner; printing again.",
                       flag="DISCUSSION", resolution=True, actor="alice",
                       at=datetime(2026, 9, 17, 9, 0))
        board.add_note(conn, "ITO-1", body="Root cause: counterfeit toner batch.",
                       flag="INTERNAL", resolution=True, actor="alice",
                       at=datetime(2026, 9, 17, 9, 5))
        conn.commit()
        conn.close()
        _, _, mine = self._call("GET", "/my/ITO-1", cookie=self._cookie_for(
            "nurse", email="nurse@pmcne.ph"))
        self.assertIn("Swapped the toner", mine)
        self.assertIn("IT Help — resolution", mine)          # signed with the board, never "IT"
        self.assertNotIn("counterfeit", mine)             # an internal resolution stays internal
        _, _, desk = self._call("GET", "/ticket/ITO-1", cookie=self._cookie_for("alice"),
                                query="tab=RESOLUTION")
        self.assertIn("Swapped the toner", desk)
        self.assertIn("counterfeit", desk)
        self.assertIn("Resolution 2", desk)

    def test_changing_the_two_answers_recomputes_priority_never_typed(self):
        status, _, _ = self._call("POST", "/ticket/ITO-1/update", cookie=self._cookie_for("alice"),
                                  form={"board_id": "IT_HELP", "impact": "I3", "urgency": "U3",
                                        "owner": "bob", "to_status": "IT_HELP.NEW",
                                        "entity_id": "PMC", "requested_by": ""})
        self.assertTrue(status.startswith("303"))
        conn = self._db()
        row = conn.execute("SELECT priority, priority_source, owner FROM ticket"
                           " WHERE work_item_id='ITO-1'").fetchone()
        self.assertEqual(tuple(row), ("P4", "MATRIX", "bob"))
        self.assertIsNotNone(conn.execute(
            "SELECT 1 FROM ticket_event WHERE work_item_id='ITO-1' AND kind='UPDATED'").fetchone())
        conn.close()

    def test_new_ticket_from_the_desk_records_its_source_and_priority(self):
        status, headers, _ = self._call("POST", "/ticket/new", cookie=self._cookie_for("alice"),
                                        form={"board_id": "IT_HELP", "source": "PHONE",
                                              "entity_id": "PMC", "summary": "Ward 5 phone dead",
                                              "impact": "I2", "urgency": "U2"})
        self.assertTrue(status.startswith("303"), status)
        wid = dict(headers)["Location"].split("/ticket/")[1].split("?")[0]
        conn = self._db()
        row = conn.execute("SELECT intake_source, priority, board_status_id FROM ticket"
                           " WHERE work_item_id = ?", (wid,)).fetchone()
        self.assertEqual(tuple(row), ("PHONE", "P3", "IT_HELP.NEW"))
        conn.close()

    def test_new_ticket_refuses_a_board_the_user_cannot_work(self):
        status, _, body = self._call("POST", "/ticket/new", cookie=self._cookie_for("carol"),
                                     form={"board_id": "IT_HELP", "summary": "x",
                                           "impact": "I3", "urgency": "U3"})
        self.assertIn("not a working", body)

    def test_bulk_assign_goes_through_the_engine_and_respects_access(self):
        status, headers, _ = self._call("POST", "/bulk", cookie=self._cookie_for("alice"),
                                        form=[("ids", "ITO-1"), ("ids", "ITO-9"),
                                              ("owner", "bob"), ("back", "/")])
        self.assertIn("Updated+2", dict(headers)["Location"])
        status, headers, _ = self._call("POST", "/bulk", cookie=self._cookie_for("carol"),
                                        form=[("ids", "ITO-1"), ("owner", "mallory")])
        self.assertIn("1+could+not", dict(headers)["Location"])
        conn = self._db()
        self.assertEqual(conn.execute("SELECT owner FROM ticket WHERE work_item_id='ITO-1'"
                                      ).fetchone()[0], "bob")
        conn.close()

    def test_board_setup_takes_board_admin(self):
        status, _, _ = self._call("GET", "/admin/board/IT_HELP", cookie=self._cookie_for("carol"))
        self.assertTrue(status.startswith("404"))
        status, _, _ = self._call("POST", "/admin/board/IT_HELP/starter",
                                  cookie=self._cookie_for("carol"))
        self.assertTrue(status.startswith("404"))

    def test_setup_applies_the_starter_and_edits_targets_with_an_audit(self):
        cookie = self._cookie_for("alice")
        self._call("POST", "/admin/board/IT_HELP/starter", cookie=cookie)
        self._call("POST", "/admin/board/IT_HELP/sla", cookie=cookie,
                   form={"t_P1_RESPOND": "7", "t_P1_RESOLUTION_PLAN": "60",
                         "t_P1_RESOLVE": ""})
        conn = self._db()
        targets = {r[0]: r[1] for r in conn.execute(
            "SELECT clock, target_minutes FROM sla_target WHERE board_id='IT_HELP' AND priority='P1'")}
        self.assertEqual(targets, {"RESPOND": 7, "RESOLUTION_PLAN": 60})
        self.assertEqual(conn.execute("SELECT calendar_id FROM board WHERE board_id='IT_HELP'"
                                      ).fetchone()[0], "ALL_HOURS")
        self.assertGreaterEqual(conn.execute(
            "SELECT COUNT(*) FROM audit_event WHERE action IN ('BOARD_SETUP','BOARD_CONFIG')"
        ).fetchone()[0], 2)
        conn.close()

    def test_a_status_edit_keeps_exactly_one_default(self):
        cookie = self._cookie_for("alice")
        self._call("POST", "/admin/board/IT_HELP/starter", cookie=cookie)
        self._call("POST", "/admin/board/IT_HELP/status/save", cookie=cookie,
                   form={"board_status_id": "IT_HELP.ASSIGNED", "name": "Assigned",
                         "escalation_status": "NOT_RESPONDED", "is_default": "1",
                         "time_entry_allowed": "1", "display_on_board": "1", "sort_order": "20"})
        conn = self._db()
        defaults = [r[0] for r in conn.execute(
            "SELECT board_status_id FROM board_status WHERE board_id='IT_HELP' AND is_default=1")]
        self.assertEqual(defaults, ["IT_HELP.ASSIGNED"])
        conn.close()

    def test_a_technicians_note_is_scanned_for_patient_details_like_every_other_intake(self):
        """Pilot script H3 (SQL01 part 9, defect 6): the note is saved and a
        data-quality finding names the shape, never the number."""
        status, headers, _ = self._call("POST", "/ticket/ITO-1/note", cookie=self._cookie_for("alice"),
                                        form={"body": "Patient PhilHealth 12-345678901-2 says the printer is out",
                                              "flag": "DISCUSSION"})
        self.assertTrue(status.startswith("303"), status)
        self.assertIn("Note+saved", dict(headers)["Location"])
        conn = db.connect(self.db_path)
        rows = conn.execute("SELECT code, detail FROM data_quality WHERE subject_id = 'ITO-1'").fetchall()
        note = conn.execute("SELECT detail FROM ticket_event WHERE work_item_id = 'ITO-1' AND kind = 'NOTE'").fetchone()
        conn.close()
        self.assertIn("PHI_PHILHEALTH_NUMBER", [r["code"] for r in rows])
        for r in rows:
            self.assertNotIn("345678901", r["detail"])
            self.assertIn("in the note", r["detail"])
        self.assertIn("345678901", note["detail"])           # kept, flagged, never dropped

    def test_a_settings_save_audits_each_change_as_old_to_new(self):
        """SQL01, part 15: Dada's rename read only "settings saved: live=1 inactive=0"."""
        alice = self._cookie_for("alice")
        base = {"display_name": "IT Help", "fulfiller_group": "Dada", "owner": "a", "deputy": "b", "is_live": "1"}
        self._call("POST", "/admin/board/IT_HELP/settings", cookie=alice, form=base)
        self._call("POST", "/admin/board/IT_HELP/settings", cookie=alice, form=base)               # the same again
        self._call("POST", "/admin/board/IT_HELP/settings", cookie=alice,
                   form=base | {"display_name": "PMO Helpdesk", "notify_owner": "1"})
        conn = self._db()
        rows = [r[0] for r in conn.execute("SELECT detail FROM audit_event WHERE action = 'BOARD_CONFIG'"
                                           " AND subject_id = 'IT_HELP' ORDER BY audit_id")]
        conn.close()
        self.assertEqual(rows[-2], "settings saved: nothing changed")
        self.assertEqual(rows[-1], "settings saved: name 'IT Help' -> 'PMO Helpdesk'; email the owner 0 -> 1")
        conn = self._db()
        conn.execute("UPDATE board SET notify_requester = NULL, inactive = NULL WHERE board_id = 'IT_HELP'")
        conn.commit()
        conn.close()
        self._call("POST", "/admin/board/IT_HELP/settings", cookie=alice,
                   form=base | {"display_name": "PMO Helpdesk", "notify_owner": "1"})
        conn = self._db()
        last = conn.execute("SELECT detail FROM audit_event WHERE action = 'BOARD_CONFIG' AND subject_id = 'IT_HELP'"
                            " ORDER BY audit_id DESC").fetchone()[0]
        conn.close()
        self.assertEqual(last, "settings saved: nothing changed")                    # NULL -> 0 is no change

    def test_the_board_tab_saves_the_owner_mail_and_the_time_defaults_and_the_composer_shows_them(self):
        alice = self._cookie_for("alice")
        _, headers, _ = self._call("POST", "/admin/board/IT_HELP/settings", cookie=alice, form={
            "display_name": "IT Help", "fulfiller_group": "Dada", "owner": "a", "deputy": "b", "is_live": "1",
            "notify_owner": "1", "notify_requester": "1", "default_work_role_id": "ENGINEER",
            "default_work_type_id": "REMOTE"})
        self.assertIn("Board+saved", dict(headers)["Location"])
        conn = self._db()
        row = conn.execute("SELECT notify_owner, default_work_role_id, default_work_type_id FROM board"
                           " WHERE board_id = 'IT_HELP'").fetchone()
        conn.close()
        self.assertEqual(tuple(row), (1, "ENGINEER", "REMOTE"))
        _, _, page = self._call("GET", "/ticket/ITO-1", cookie=alice)
        self.assertIn("<option value='ENGINEER' selected>", page)
        self.assertIn("<option value='REMOTE' selected>", page)
        self.assertIn("name=notify value=1 checked", page)              # the requester tick, on
        _, headers, _ = self._call("POST", "/admin/board/IT_HELP/settings", cookie=alice, form={
            "display_name": "IT Help", "fulfiller_group": "Dada", "owner": "a", "deputy": "b", "is_live": "1",
            "default_work_role_id": "NOPE"})
        self.assertIn("no+such+work+role", dict(headers)["Location"])
        # unticked: the Discussion note is written and no requester email is queued
        _, headers, _ = self._call("POST", "/ticket/ITO-1/note", cookie=alice, form={
            "body": "Quietly.", "flag": "DISCUSSION"})
        self.assertIn("Note+saved", dict(headers)["Location"])
        conn = self._db()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM notification WHERE recipient_role = 'REQUESTER'").fetchone()[0], 0)
        conn.close()

    def test_a_form_posted_from_another_site_is_refused(self):
        status, _, _ = self._call("POST", "/ticket/ITO-1/note", cookie=self._cookie_for("alice"),
                                  form={"body": "csrf", "flag": "DISCUSSION"},
                                  headers={"Origin": "http://evil.example", "Host": "t"})
        self.assertTrue(status.startswith("403"))
        status, _, _ = self._call("POST", "/ticket/ITO-1/note", cookie=self._cookie_for("alice"),
                                  form={"body": "same site", "flag": "DISCUSSION"},
                                  headers={"Origin": "http://t", "Host": "t"})
        self.assertTrue(status.startswith("303"))

    def test_the_board_tiles_filter_and_every_column_sorts(self):
        cookie = self._cookie_for("alice")
        _, _, body = self._call("GET", "/", cookie=cookie, query="tile=unassigned")
        self.assertIn("ITO-1", body)
        for key in ("id", "summary", "company", "contact", "board", "status", "pri",
                    "owner", "age", "updated", "sla"):
            status, _, _ = self._call("GET", "/", cookie=cookie, query=f"sort={key}&dir=asc")
            self.assertTrue(status.startswith("200"), key)

    def test_a_sysadmin_creates_a_board_and_a_member_works_many_boards(self):
        admin = self._cookie_for("root", is_sysadmin=True)
        status, headers, _ = self._call("POST", "/admin/board/new", cookie=admin, form={
            "display_name": "Biomedical", "fulfiller_group": "Biomed", "copy_from": "starter"})
        self.assertTrue(status.startswith("303"), status)
        self._call("POST", "/admin/board/BIOMEDICAL/team", cookie=admin,
                   form={"name": "Ward rounds", "team_leader": "reyes", "is_default": "1"})
        self._call("POST", "/admin/member/add", cookie=admin, form={
            "board_id": "BIOMEDICAL", "member": "alice", "access": "WORK",
            "team_id": "BIOMEDICAL.WARD_ROUNDS", "back": "members"})
        conn = self._db()
        self.assertEqual(sorted(r[0] for r in conn.execute(
            "SELECT board_id FROM board_member WHERE member = 'alice'")),
            ["BIOMEDICAL", "IT_HELP", "PHI"])
        self.assertEqual(conn.execute("SELECT team_id FROM board_member WHERE member='alice'"
                                      " AND board_id='BIOMEDICAL'").fetchone()[0],
                         "BIOMEDICAL.WARD_ROUNDS")
        conn.close()
        _, _, body = self._call("GET", "/ticket/new", cookie=self._cookie_for("alice"))
        self.assertIn("Biomedical", body)

    def test_only_a_sysadmin_creates_boards(self):
        status, _, _ = self._call("POST", "/admin/board/new", cookie=self._cookie_for("alice"),
                                  form={"display_name": "Rogue", "fulfiller_group": "x"})
        self.assertTrue(status.startswith("403"))

    def test_a_live_board_needs_an_owner_and_deputy_and_a_retired_one_takes_no_tickets(self):
        cookie = self._cookie_for("alice")
        _, headers, _ = self._call("POST", "/admin/board/IT_HELP/settings", cookie=cookie,
                                   form={"display_name": "IT Help", "is_live": "1",
                                         "owner": "", "deputy": ""})
        self.assertIn("owner+and+a+deputy", dict(headers)["Location"])
        self._call("POST", "/admin/board/IT_HELP/settings", cookie=cookie,
                   form={"display_name": "IT Help", "inactive": "1"})
        _, _, body = self._call("GET", "/ticket/new", cookie=cookie)
        self.assertNotIn("<option value='IT_HELP'", body)   # retired: not offered
        self.assertIn("<option value='PHI'", body)          # her other board still is

    def test_the_catalogue_page_loads_the_template(self):
        admin = self._cookie_for("root", is_sysadmin=True)
        _, headers, _ = self._call("POST", "/admin/catalogue/template", cookie=admin)
        self.assertIn("Template+applied", dict(headers)["Location"])
        _, _, body = self._call("GET", "/admin/catalogue", cookie=admin)
        self.assertIn("Request", body)

    # ------------------------------------------------ companies and contacts

    def _add_contact(self, contact_id="CT-1", email="ward3@pmcne.ph"):
        conn = db.connect(self.db_path)
        conn.execute(
            "INSERT INTO contact (contact_id, entity_id, display_name, email, department,"
            " source, inactive, created_at) VALUES (?, 'PMC', 'Ward Three Station', ?,"
            " 'Ward 3', 'AD', 0, '2026-09-17 08:00')", (contact_id, email))
        conn.execute("UPDATE ticket SET contact_id = ? WHERE work_item_id IN ('ITO-1','ITO-9')",
                     (contact_id,))
        conn.commit()
        conn.close()

    def test_companies_and_contacts_are_for_fulfillers_only(self):
        """Contacts are staff details; a requester with no board gets a 404."""
        for path in ("/companies", "/company/PMC", "/contacts"):
            status, _, _ = self._call("GET", path, cookie=self._cookie_for("dave"))
            self.assertTrue(status.startswith("404"), path)
            status, _, _ = self._call("GET", path, cookie=self._cookie_for("carol"))
            self.assertTrue(status.startswith("200"), path)

    def test_a_company_page_never_lists_a_restricted_ticket(self):
        """Restricted tickets are read on their own board, where the read is
        audited; a company page is not a side door round that."""
        self._add_contact()
        _, _, body = self._call("GET", "/company/PMC", cookie=self._cookie_for("alice"))
        self.assertIn("ITO-1", body)
        self.assertNotIn("ITO-9", body)
        self.assertNotIn("Sensitive", body)
        self.assertIn("1 more on restricted boards", body)
        _, _, body = self._call("GET", "/contact/CT-1", cookie=self._cookie_for("alice"))
        self.assertIn("Ward Three Station", body)
        self.assertIn("ITO-1", body)
        self.assertNotIn("ITO-9", body)
        conn = db.connect(self.db_path)
        self.assertIsNone(conn.execute(
            "SELECT 1 FROM audit_event WHERE action = 'RESTRICTED_READ'").fetchone())
        conn.close()

    def test_the_ticket_shows_its_contact_and_offers_the_list(self):
        self._add_contact()
        _, _, body = self._call("GET", "/ticket/ITO-1", cookie=self._cookie_for("alice"))
        self.assertIn("href='/contact/CT-1'", body)
        self.assertIn("<datalist id=contacts-ticket>", body)
        self.assertIn("Ward Three Station &lt;ward3@pmcne.ph&gt;", body)

    def test_new_ticket_from_a_contact_is_prefilled(self):
        _, _, body = self._call("GET", "/ticket/new", cookie=self._cookie_for("alice"),
                                query="entity_id=PMC&requested_by=ward3%40pmcne.ph")
        self.assertIn("value='ward3@pmcne.ph'", body)

    def test_editing_the_contact_re_resolves_the_person(self):
        self._add_contact()
        conn = db.connect(self.db_path)
        conn.execute("UPDATE work_item SET entity_id = 'UNCLASSIFIED' WHERE work_item_id = 'ITO-1'")
        conn.execute("UPDATE ticket SET contact_id = NULL WHERE work_item_id = 'ITO-1'")
        conn.commit()
        board.update_fields(conn, "ITO-1", at=datetime(2026, 9, 17, 10, 0), actor="alice",
                            requested_by="Ward 3 <ward3@pmcne.ph>", entity_id="UNCLASSIFIED")
        row = conn.execute("SELECT t.contact_id, w.entity_id FROM ticket t JOIN work_item w"
                           " ON w.work_item_id = t.work_item_id WHERE t.work_item_id = 'ITO-1'").fetchone()
        self.assertEqual((row["contact_id"], row["entity_id"]), ("CT-1", "PMC"))
        board.update_fields(conn, "ITO-1", at=datetime(2026, 9, 17, 10, 5), actor="alice",
                            requested_by="someone at the front desk")
        self.assertIsNone(conn.execute(
            "SELECT contact_id FROM ticket WHERE work_item_id = 'ITO-1'").fetchone()["contact_id"])
        conn.close()

    # ------------------------------------------ board kinds, Types, changes, links

    def test_the_types_tab_sets_what_a_board_takes(self):
        alice = self._cookie_for("alice")
        _, _, body = self._call("GET", "/admin/board/IT_HELP", cookie=alice, query="tab=types")
        self.assertIn("Incident", body)
        self.assertIn("service</b> board", body)
        body_form = "types=INCIDENT&types=SERVICE_REQUEST&default=SERVICE_REQUEST".encode()
        env = self._environ("POST", "/admin/board/IT_HELP/types", cookie=alice, body=body_form)
        captured = {}
        b"".join(self.raw(env, lambda st, h, e=None: captured.update(status=st)))
        self.assertTrue(captured["status"].startswith("303"))
        conn = db.connect(self.db_path)
        from psaspine import itil
        self.assertEqual(itil.board_default(conn, "IT_HELP"), "SERVICE_REQUEST")
        self.assertFalse(itil.accepts(conn, "IT_HELP", "PROBLEM"))
        conn.close()
        status, _, _ = self._call("POST", "/admin/board/IT_HELP/types",
                                  cookie=self._cookie_for("carol"), form={"types": "EVENT"})
        self.assertFalse(status.startswith("303"))          # READ only: refused

    def test_a_change_is_approved_on_the_ticket_by_an_admin_not_its_owner(self):
        conn = db.connect(self.db_path)
        conn.execute("UPDATE ticket SET record_type = 'CHANGE', change_type = 'NORMAL',"
                     " owner = 'alice' WHERE work_item_id = 'ITO-1'")
        conn.execute("INSERT INTO board_member (board_id, member, access) VALUES"
                     " ('IT_HELP', 'lead', 'ADMIN')")
        conn.commit()
        conn.close()
        _, _, body = self._call("GET", "/ticket/ITO-1", cookie=self._cookie_for("alice"))
        self.assertIn("never by its owner", body)          # alice owns it: no form
        _, _, body = self._call("GET", "/ticket/ITO-1", cookie=self._cookie_for("lead"))
        self.assertIn("/ticket/ITO-1/change/decide", body)
        _, headers, _ = self._call("POST", "/ticket/ITO-1/change/decide",
                                   cookie=self._cookie_for("alice"),
                                   form={"decision": "APPROVED", "authority": "CAB"})
        self.assertIn("err=", dict(headers)["Location"])
        _, headers, _ = self._call("POST", "/ticket/ITO-1/change/decide",
                                   cookie=self._cookie_for("lead"),
                                   form={"decision": "APPROVED", "authority": "CAB"})
        self.assertIn("msg=", dict(headers)["Location"])

    def test_linking_never_reaches_a_ticket_on_a_board_you_cannot_see(self):
        conn = db.connect(self.db_path)
        conn.execute("UPDATE ticket SET record_type = 'PROBLEM' WHERE work_item_id = 'ITO-9'")
        conn.commit()
        conn.close()
        _, headers, _ = self._call("POST", "/ticket/ITO-1/link", cookie=self._cookie_for("carol"),
                                   form={"linked_id": "ITO-9", "relation": "CAUSED_BY"})
        self.assertNotIn("Linked", dict(headers).get("Location", ""))

    def test_the_portal_asks_broken_or_need_and_files_the_type(self):
        _, _, body = self._call("GET", "/my", cookie=self._cookie_for("dave"))
        self.assertIn("Is something broken, or do you need something?", body)

    def test_a_board_admin_builds_tests_and_switches_on_a_rule(self):
        alice = self._cookie_for("alice")                 # ADMIN on IT_HELP
        _, headers, _ = self._call("POST", "/admin/rules/new", cookie=alice,
                                   form={"name": "Unowned P1", "board_id": "IT_HELP"})
        loc = dict(headers)["Location"]
        wid = loc.rsplit("/", 1)[1]
        self._call("POST", f"/admin/rules/{wid}/event", cookie=alice, form={
            "event_name": "P1 created", "fires_on": "ON_CREATE", "mode": "ONCE",
            "field0": "TICKET.PRIORITY", "op0": "EQ", "value0": "P1",
            "act0": "ADD_NOTE", "detail0": "P1: page the on-call"})
        _, headers, _ = self._call("POST", f"/admin/rules/{wid}/activate", cookie=alice)
        self.assertIn("err=", dict(headers)["Location"])          # untested: refused
        _, headers, _ = self._call("POST", f"/admin/rules/{wid}/test", cookie=alice,
                                   form={"event_id": f"{wid}_E1"})
        self.assertIn("1+open+ticket", dict(headers)["Location"])  # ITO-1 is a P1
        _, headers, _ = self._call("POST", f"/admin/rules/{wid}/activate", cookie=alice)
        self.assertIn("Switched+on", dict(headers)["Location"])
        _, _, body = self._call("GET", f"/admin/rules/{wid}", cookie=alice)
        self.assertIn("P1 created", body)
        # carol only reads the board: no rules for her
        status, _, _ = self._call("GET", f"/admin/rules/{wid}", cookie=self._cookie_for("carol"))
        self.assertTrue(status.startswith("403"))

    def test_tasks_and_templates_on_the_desk(self):
        alice = self._cookie_for("alice")
        self._call("POST", "/admin/board/IT_HELP/template", cookie=alice, form={
            "name": "Printer swap", "summary": "Swap a ward printer",
            "tasks": "Unplug the old one\nFit the new one\nTest a wristband"})
        _, _, body = self._call("GET", "/ticket/new", cookie=alice, query="template=TPL_PRINTER_SWAP")
        self.assertIn("value='Swap a ward printer'", body)
        self.assertIn("name=template_id value='TPL_PRINTER_SWAP'", body)
        self._call("POST", "/ticket/ITO-1/template", cookie=alice,
                   form={"template_id": "TPL_PRINTER_SWAP"})
        self._call("POST", "/ticket/ITO-1/task/add", cookie=alice, form={"text": "Tell the ward"})
        _, _, body = self._call("GET", "/ticket/ITO-1", cookie=alice)
        self.assertIn("Tasks · 0 of 4", body)
        conn = db.connect(self.db_path)
        first = conn.execute("SELECT task_id FROM ticket_task WHERE work_item_id = 'ITO-1'"
                             " ORDER BY sort_order").fetchone()[0]
        conn.close()
        self._call("POST", "/ticket/ITO-1/task/toggle", cookie=alice,
                   form={"task_id": str(first), "done": "1"})
        _, _, body = self._call("GET", "/ticket/ITO-1", cookie=alice)
        self.assertIn("Tasks · 1 of 4", body)
        status, _, _ = self._call("POST", "/ticket/ITO-1/task/add", cookie=self._cookie_for("carol"),
                                  form={"text": "x"})
        self.assertFalse(status.startswith("303"))         # READ only

    def _add_configuration(self):
        conn = db.connect(self.db_path)
        conn.execute(
            "INSERT INTO configuration (configuration_id, entity_id, name, config_type, status,"
            " remote_session_id, source, created_at) VALUES ('CF-1', 'PMC', 'WARD3-PC01',"
            " 'WORKSTATION', 'ACTIVE', '0f9c3a0e-aaaa-4c2a-9a55-2b8f3c1d00ff', 'AD',"
            " '2026-09-17 08:00')")
        conn.commit()
        conn.close()

    def test_only_a_sysadmin_writes_where_every_click_goes(self):
        form = {"label": "ScreenConnect", "applies_to": "CONFIGURATION",
                "url_template": "https://x.screenconnect.com/Host#Access/All%20Machines//"
                                "{remote_session_id}/Join"}
        status, _, _ = self._call("POST", "/admin/integrations/add",
                                  cookie=self._cookie_for("alice"), form=form)
        self.assertTrue(status.startswith("403"))
        root = self._cookie_for("root", is_sysadmin=True)
        _, headers, _ = self._call("POST", "/admin/integrations/add", cookie=root, form=form)
        self.assertIn("Link+added", dict(headers)["Location"])
        _, headers, _ = self._call("POST", "/admin/integrations/add", cookie=root,
                                   form=dict(form, url_template="http://evil.example/{name}"))
        self.assertIn("err=", dict(headers)["Location"])

    def test_a_ticket_attaches_a_configuration_and_launches_it(self):
        self._add_configuration()
        conn = db.connect(self.db_path)
        from psaspine import configurations as cmdb
        cmdb.add_link(conn, label="ScreenConnect", applies_to="CONFIGURATION",
                      url_template="https://x.screenconnect.com/Host#Access/All%20Machines//"
                                   "{remote_session_id}/Join",
                      at=datetime(2026, 9, 17), actor="root")
        conn.commit()
        conn.close()
        alice = self._cookie_for("alice")
        status, _, _ = self._call("POST", "/ticket/ITO-1/config/add", cookie=alice,
                                  form={"configuration_id": "CF-1"})
        self.assertTrue(status.startswith("303"))
        _, _, body = self._call("GET", "/ticket/ITO-1", cookie=alice)
        self.assertIn("href='/configuration/CF-1'", body)
        self.assertIn("https://x.screenconnect.com/Host#Access/All%20Machines//"
                      "0f9c3a0e-aaaa-4c2a-9a55-2b8f3c1d00ff/Join", body)
        self.assertIn("rel='noopener noreferrer'", body)
        # by name, as the card's search box posts it; an unknown name says so
        self._call("POST", "/ticket/ITO-1/config/remove", cookie=alice, form={"configuration_id": "CF-1"})
        status, headers, _ = self._call("POST", "/ticket/ITO-1/config/add", cookie=alice,
                                        form={"name": "ward3-pc01"})
        self.assertIn("msg=", dict(headers).get("Location", ""))
        status, headers, _ = self._call("POST", "/ticket/ITO-1/config/add", cookie=alice,
                                        form={"name": "no-such-machine"})
        self.assertIn("err=", dict(headers).get("Location", ""))
        # carol only reads IT_HELP, so she cannot attach
        status, _, _ = self._call("POST", "/ticket/ITO-1/config/remove",
                                  cookie=self._cookie_for("carol"),
                                  form={"configuration_id": "CF-1"})
        self.assertFalse(status.startswith("303"))

    def test_the_configurations_page_counts_filters_sorts_and_adds_by_hand(self):
        self._add_configuration()
        alice = self._cookie_for("alice")
        status, headers, _ = self._call("POST", "/configurations/new", cookie=alice, form={
            "name": "PRN-WARD3-01", "entity_id": "PMC", "config_type": "PRINTER", "serial_number": "SN123",
            "manufacturer": "HP", "model": "M479", "description": "Nurses' station, ward 3"})
        self.assertTrue(status.startswith("303"), status)
        cid = dict(headers)["Location"].split("/configuration/")[1].split("?")[0]
        _, headers, _ = self._call("POST", "/configurations/new", cookie=alice, form={
            "name": "prn-ward3-01", "entity_id": "PMC", "config_type": "PRINTER"})
        self.assertIn("already", dict(headers)["Location"])
        status, _, _ = self._call("POST", "/configurations/new", cookie=self._cookie_for("carol"),
                                  form={"name": "X", "entity_id": "PMC", "config_type": "PRINTER"})
        self.assertTrue(status.startswith("403"))
        # the index: counts by type that filter, a status filter, a search, sorting
        _, _, page = self._call("GET", "/configurations", cookie=alice)
        self.assertIn("<div class=n>2</div><div class=l>Active, all types</div>", page)
        self.assertIn("<div class=n>1</div><div class=l>Printers</div>", page)
        self.assertIn("PRN-WARD3-01", page)
        self.assertIn("WARD3-PC01", page)
        self.assertIn("by hand", page)
        _, _, page = self._call("GET", "/configurations", cookie=alice, query="type=PRINTER")
        self.assertIn("PRN-WARD3-01", page)
        self.assertNotIn("WARD3-PC01", page)
        _, _, page = self._call("GET", "/configurations", cookie=alice, query="q=SN123")
        self.assertIn("PRN-WARD3-01", page)
        self.assertNotIn("WARD3-PC01", page)
        _, _, page = self._call("GET", "/configurations", cookie=alice, query="sort=type")
        self.assertLess(page.index("PRN-WARD3-01"), page.index("WARD3-PC01"))       # printer before workstation
        conn = db.connect(self.db_path)
        conn.execute("UPDATE configuration SET status = 'RETIRED' WHERE configuration_id = 'CF-1'")
        conn.commit()
        conn.close()
        _, _, page = self._call("GET", "/configurations", cookie=alice)
        self.assertNotIn("WARD3-PC01", page)
        _, _, page = self._call("GET", "/configurations", cookie=alice, query="status=ALL")
        self.assertIn("WARD3-PC01", page)
        # the detail: every field, the edit that the desk owns, and the history
        _, _, page = self._call("GET", f"/configuration/{cid}", cookie=alice)
        for needle in ("<dt>Manufacturer</dt><dd>HP</dd>", "<dt>Model</dt><dd>M479</dd>", "typed in by hand",
                       "Raise a ticket for this machine", "name=name", "name=description", "History",
                       "create: PRN-WARD3-01 (printer) at PMC, by hand"):
            self.assertIn(needle, page, needle)
        _, headers, _ = self._call("POST", f"/configuration/{cid}/update", cookie=alice, form={
            "config_type": "PRINTER", "status": "ACTIVE", "contact_id": "", "manufacturer": "HP",
            "model": "M479dw", "serial_number": "SN123", "name": "PRN-WARD3-01", "description": "Ward 3, by the lift",
            "remote_session_id": ""})
        self.assertIn("Saved%3A+model%2C+description", dict(headers)["Location"])
        # an imported machine's name is AD's
        _, _, page = self._call("GET", "/configuration/CF-1", cookie=alice)
        self.assertNotIn("name=name", page.split("<form")[1] if "<form" in page else "")
        self.assertIn("Active Directory's", page)
        _, headers, _ = self._call("POST", "/configuration/CF-1/update", cookie=alice, form={
            "config_type": "WORKSTATION", "status": "RETIRED", "contact_id": "", "name": "RENAMED",
            "manufacturer": "", "model": "", "serial_number": "", "remote_session_id": ""})
        self.assertIn("err=", dict(headers)["Location"])

    def test_a_ticket_raised_for_a_machine_is_attached_on_creation(self):
        self._add_configuration()
        alice = self._cookie_for("alice")
        _, _, page = self._call("GET", "/ticket/new", cookie=alice, query="configuration_id=CF-1&entity_id=PMC")
        self.assertIn("For the machine <b>WARD3-PC01</b>", page)
        self.assertIn("name=configuration_id value='CF-1'", page)
        status, headers, _ = self._call("POST", "/ticket/new", cookie=alice, form={
            "board_id": "IT_HELP", "summary": "PC slow", "impact": "I3", "urgency": "U3", "source": "PHONE",
            "entity_id": "PMC", "configuration_id": "CF-1"})
        self.assertTrue(status.startswith("303"), status)
        wid = dict(headers)["Location"].split("/ticket/")[1].split("?")[0]
        conn = db.connect(self.db_path)
        self.assertEqual(conn.execute("SELECT configuration_id FROM ticket_configuration WHERE work_item_id = ?",
                                      (wid,)).fetchone()[0], "CF-1")
        conn.close()
        _, _, page = self._call("GET", "/configuration/CF-1", cookie=alice)
        self.assertIn(wid, page)                     # under Open tickets and in the history
        self.assertIn("attached", page)

    def test_a_configuration_page_never_lists_a_restricted_ticket(self):
        self._add_configuration()
        conn = db.connect(self.db_path)
        for wid in ("ITO-1", "ITO-9"):
            conn.execute("INSERT INTO ticket_configuration (work_item_id, configuration_id, linked_at,"
                         " linked_by) VALUES (?, 'CF-1', '2026-09-17', 'a')",
                         (wid,))
        conn.commit()
        conn.close()
        _, _, body = self._call("GET", "/configuration/CF-1", cookie=self._cookie_for("alice"))
        self.assertIn("ITO-1", body)
        self.assertNotIn("ITO-9", body)
        self.assertIn("1 more on restricted boards", body)
        status, _, _ = self._call("GET", "/configuration/CF-1", cookie=self._cookie_for("dave"))
        self.assertTrue(status.startswith("404"))

    def test_the_board_says_why_a_ticket_has_no_clock(self):
        _, _, body = self._call("GET", "/", cookie=self._cookie_for("alice"))
        self.assertIn("board not set up", body)

    def test_the_board_shows_only_the_members_boards(self):
        status, _, body = self._call("GET", "/", cookie=self._cookie_for("carol"))
        self.assertIn("ITO-1", body)       # carol reads IT_HELP
        self.assertNotIn("ITO-9", body)    # carol is not on PHI

    # -------- §11 test 5: a non-member is PROVABLY excluded from a restricted board

    def test_a_non_member_cannot_reach_a_restricted_boards_ticket(self):
        status, _, _ = self._call("GET", "/ticket/ITO-9", cookie=self._cookie_for("carol"))
        self.assertTrue(status.startswith("404"),
                        "restricted-board ticket leaked to a non-member")

    def test_even_a_break_glass_sysadmin_does_not_bypass_board_membership(self):
        """The sysadmin flag unlocks cross-board config, never a restricted
        board's contents. Otherwise the exclusion is 'absolute unless admin'."""
        cookie = self._cookie_for("nobody", via="local", is_sysadmin=True)
        status, _, _ = self._call("GET", "/ticket/ITO-9", cookie=cookie)
        self.assertTrue(status.startswith("404"))

    # ---------------------------------------------------------- admin & the loop

    # ------- §6.1 requirement 4: every read of a restricted ticket is audited

    def _audit_rows(self, action="RESTRICTED_READ"):
        conn = db.connect(self.db_path)
        rows = conn.execute(
            "SELECT actor, subject_kind, subject_id, detail FROM audit_event"
            " WHERE action = ? ORDER BY audit_id", (action,)).fetchall()
        conn.close()
        return rows

    def test_reading_a_restricted_ticket_is_audited(self):
        status, _, _ = self._call("GET", "/ticket/ITO-9", cookie=self._cookie_for("alice"))
        self.assertTrue(status.startswith("200"))
        rows = self._audit_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["actor"], "alice")
        self.assertEqual(rows[0]["subject_kind"], "ticket")
        self.assertEqual(rows[0]["subject_id"], "ITO-9")

    def test_reading_an_unrestricted_ticket_is_not_audited(self):
        """An audit log that records every printer fault is one nobody reads."""
        self._call("GET", "/ticket/ITO-1", cookie=self._cookie_for("alice"))
        self.assertEqual(self._audit_rows(), [])

    def test_a_refused_read_writes_no_read_audit(self):
        """A 404 is not a read — the board never appeared."""
        status, _, _ = self._call("GET", "/ticket/ITO-9", cookie=self._cookie_for("carol"))
        self.assertTrue(status.startswith("404"))
        self.assertEqual(self._audit_rows(), [])

    def test_listing_a_restricted_board_is_audited_once_with_a_count(self):
        status, _, _ = self._call("GET", "/", cookie=self._cookie_for("alice"))
        self.assertTrue(status.startswith("200"))
        rows = self._audit_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["subject_kind"], "board")
        self.assertEqual(rows[0]["subject_id"], "PHI")
        self.assertIn("listed 1 ticket(s)", rows[0]["detail"])

    def test_the_audit_records_which_door_the_reader_came_through(self):
        """A break-glass read and an Entra read are not the same risk."""
        cookie = self._cookie_for("alice", via="local")
        self._call("GET", "/ticket/ITO-9", cookie=cookie)
        self.assertIn("via local", self._audit_rows()[0]["detail"])

    # ---- SQL01 sitting 2, part 9: the pages that named tickets without the rule

    def test_uplift_names_only_my_boards_tickets_and_audits_a_restricted_listing(self):
        conn = db.connect(self.db_path)
        conn.execute("UPDATE work_item SET contract_basis = 'UNKNOWN' WHERE work_item_id IN ('ITO-1','ITO-9')")
        conn.commit()
        conn.close()
        # carol is on IT_HELP only: the restricted ticket is not on her page
        status, _, body = self._call("GET", "/uplift", cookie=self._cookie_for("carol"))
        self.assertTrue(status.startswith("200"))
        self.assertIn("ITO-1", body)
        self.assertNotIn("ITO-9", body)
        self.assertNotIn("Sensitive", body)
        self.assertIn("boards you are a member of", body)
        self.assertEqual(self._audit_rows(), [])
        # nobody on no board reads it at all
        status, _, body = self._call("GET", "/uplift", cookie=self._cookie_for("dave"))
        self.assertTrue(status.startswith("200"))
        self.assertIn("for board members", body)
        self.assertNotIn("ITO-1", body)
        # alice is on PHI: she sees it, and the read is on the record
        _, _, body = self._call("GET", "/uplift", cookie=self._cookie_for("alice"))
        self.assertIn("ITO-9", body)
        rows = self._audit_rows()
        self.assertEqual([(r["subject_kind"], r["subject_id"]) for r in rows], [("board", "PHI")])
        self.assertIn("uplift evidence listed 1 ticket(s)", rows[0]["detail"])

    def test_the_dispatch_day_audits_a_restricted_boards_visit(self):
        from psaspine import schedule
        conn = db.connect(self.db_path)
        schedule.add(conn, "ITO-9", member="alice", starts_at=datetime(2026, 9, 17, 14),
                     ends_at=datetime(2026, 9, 17, 15), note=None, actor="t", at=datetime(2026, 9, 17, 9))
        conn.commit()
        conn.close()
        _, _, body = self._call("GET", "/dispatch", cookie=self._cookie_for("carol"))
        self.assertNotIn("ITO-9", body)
        self.assertEqual(self._audit_rows(), [])
        _, _, body = self._call("GET", "/dispatch", cookie=self._cookie_for("alice"))
        self.assertIn("ITO-9", body)
        rows = self._audit_rows()
        self.assertEqual([(r["subject_kind"], r["subject_id"]) for r in rows], [("board", "PHI")])
        self.assertIn("dispatch listed 1 ticket(s)", rows[0]["detail"])

    def test_a_sysadmins_every_board_rule_is_tested_on_their_own_boards_only(self):
        root = self._cookie_for("root", is_sysadmin=True)          # on no board at all
        _, headers, _ = self._call("POST", "/admin/rules/new", cookie=root,
                                   form={"name": "Any P1", "board_id": ""})
        wid = dict(headers)["Location"].rsplit("/", 1)[1]
        self._call("POST", f"/admin/rules/{wid}/event", cookie=root, form={
            "event_name": "P1 anywhere", "fires_on": "ON_CREATE", "mode": "ONCE",
            "field0": "TICKET.PRIORITY", "op0": "EQ", "value0": "P1",
            "act0": "ADD_NOTE", "detail0": "noted"})
        _, headers, _ = self._call("POST", f"/admin/rules/{wid}/test", cookie=root,
                                   form={"event_id": f"{wid}_E1"})
        loc = _urlparse.unquote_plus(dict(headers)["Location"])
        # both P1s exist (ITO-1, ITO-9); root is on neither board, so neither is named
        self.assertIn("0 open ticket(s) match now on the boards you are a member of", loc)
        self.assertNotIn("ITO-9", loc)
        self.assertEqual(self._audit_rows(), [])
        # alice, a sysadmin on both boards, sees both and the restricted one is audited
        alice = self._cookie_for("alice", is_sysadmin=True)
        _, headers, _ = self._call("POST", f"/admin/rules/{wid}/test", cookie=alice,
                                   form={"event_id": f"{wid}_E1"})
        loc = _urlparse.unquote_plus(dict(headers)["Location"])
        self.assertIn("2 open ticket(s) match now on the boards you are a member of", loc)
        rows = self._audit_rows()
        self.assertEqual([(r["subject_kind"], r["subject_id"]) for r in rows], [("board", "PHI")])
        self.assertIn("rule test listed 1 ticket(s)", rows[0]["detail"])

    def test_the_admin_surface_adds_a_board_status(self):
        cookie = self._cookie_for("alice")
        status, _, _ = self._call("POST", "/admin/status/add", cookie=cookie,
                                  form={"board_id": "IT_HELP", "name": "Waiting client",
                                        "escalation": "NO_ESCALATION", "is_closed": "0"})
        self.assertTrue(status.startswith("303"))
        conn = db.connect(self.db_path)
        row = conn.execute("SELECT escalation_status FROM board_status"
                           " WHERE board_id='IT_HELP' AND name='Waiting client'").fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["escalation_status"], "NO_ESCALATION")

    def test_the_web_offers_no_way_to_create_a_break_glass_account(self):
        """Creation is CLI-only by design; there must be no route that mints one."""
        for path in ("/admin/local/create", "/local/create", "/admin/create-local"):
            status, _, _ = self._call("GET", path, cookie=self._cookie_for(
                "root", is_sysadmin=True))
            self.assertTrue(status.startswith(("404", "405")), f"{path} -> {status}")

    def test_closing_the_loop_over_http_bands_effort_and_closes(self):
        cookie = self._cookie_for("alice")
        status, _, _ = self._call(
            "POST", "/ticket/ITO-1/loop", cookie=cookie,
            form={"body": "Reseated the cable.", "hours": "0.5", "to_status": "IT_HELP.DONE"})
        self.assertTrue(status.startswith("303"))
        conn = db.connect(self.db_path)
        entry = conn.execute("SELECT band_hours, loop_reply_id FROM time_entry"
                             " WHERE work_item_id='ITO-1'").fetchone()
        state = conn.execute("SELECT state FROM ticket WHERE work_item_id='ITO-1'").fetchone()
        conn.close()
        self.assertEqual(entry["band_hours"], 0.5)
        self.assertIsNotNone(entry["loop_reply_id"])
        self.assertEqual(state["state"], "CLOSED")


class TicketNumberingTest(unittest.TestCase):
    """D4 — one sequence across every board, and a number never reused."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 22, 10, 0)

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_numbers_are_issued_in_order_and_formatted(self):
        issued = [numbering.issue(self.conn, at=self.at) for _ in range(3)]
        self.assertEqual(issued, ["PMC-000001", "PMC-000002", "PMC-000003"])

    def test_the_sequence_is_hospital_wide_not_per_board(self):
        """A ticket moves board — that is what a handover is — so a number that
        belongs to a board stops being a reference the moment it is used."""
        self.conn.executescript(
            "INSERT OR REPLACE INTO board (board_id,display_name,phase,"
            " fulfiller_group,owner,deputy,is_live) VALUES"
            " ('A','Board A','2','Dada','x','y',1);"
            "INSERT OR REPLACE INTO board (board_id,display_name,phase,"
            " fulfiller_group,owner,deputy,is_live) VALUES"
            " ('B','Board B','2','Dada','x','y',1);")
        # Issuing while working two boards draws from the same sequence.
        first = numbering.issue(self.conn, at=self.at)
        second = numbering.issue(self.conn, at=self.at)
        self.assertNotEqual(first, second)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) c FROM ticket_number").fetchone()["c"], 2)

    def test_the_prefix_is_configuration_not_a_constant(self):
        """§12: if PMC cannot change it without a deployment, it is in the wrong
        place."""
        self.conn.execute("UPDATE ticket_numbering SET prefix='PMCNE', padding=4")
        self.assertEqual(numbering.issue(self.conn, at=self.at), "PMCNE-0001")

    def test_there_can_only_ever_be_one_numbering_row(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO ticket_numbering (id, prefix, padding) VALUES (2,'X',6)")

    def test_a_number_is_not_reused_after_the_last_one_is_abandoned(self):
        """A reused ticket number points at two tickets. Worse than a gap."""
        numbering.issue(self.conn, at=self.at)
        numbering.issue(self.conn, at=self.at)
        third = numbering.issue(self.conn, at=self.at)
        self.assertEqual(third, "PMC-000003")
        # Nothing reclaims 1 and 2 just because they never became tickets.
        self.assertEqual(numbering.unbound(self.conn), [1, 2, 3])
        self.assertEqual(numbering.issue(self.conn, at=self.at), "PMC-000004")

    def test_binding_records_what_the_number_became(self):
        self.conn.executescript(
            "INSERT OR REPLACE INTO board (board_id,display_name,phase,"
            " fulfiller_group,owner,deputy,is_live) VALUES"
            " ('A','Board A','2','Dada','x','y',1);")
        ticket_id = numbering.issue(self.conn, at=self.at)
        self.conn.execute(
            "INSERT INTO work_item (work_item_id, source, name, entity_id,"
            " contract_basis) VALUES (?,'desk','A thing','PMC','BASELINE')",
            (ticket_id,))
        self.conn.execute(
            "INSERT INTO ticket (work_item_id, board_id, path, impact, urgency,"
            " priority, priority_source, requested_at, opened_at, state)"
            " VALUES (?,'A','INCIDENT','I3','U3','P3','MATRIX',"
            "'2026-09-22 10:00','2026-09-22 10:00','NEW')", (ticket_id,))
        numbering.bind(self.conn, ticket_id)
        self.assertEqual(numbering.unbound(self.conn), [])
        self.assertEqual(self.conn.execute(
            "SELECT issued_to FROM ticket_number WHERE number=1").fetchone()["issued_to"],
            ticket_id)

    def test_binding_an_imported_id_is_a_no_op(self):
        """An imported desk id was never ours to issue; external_ref keeps it."""
        numbering.issue(self.conn, at=self.at)
        numbering.bind(self.conn, "ITO-1723")
        self.assertEqual(numbering.unbound(self.conn), [1])

    def test_the_desk_reference_is_not_replaced_by_renumbering(self):
        """Imported history keeps its own id — renumbering breaks every
        reference anybody wrote down. external_ref already carries the source."""
        cols = [d[0] for d in self.conn.execute("SELECT * FROM ticket WHERE 1 = 0").description]
        self.assertIn("external_ref", cols)


class PhiDetectionTest(unittest.TestCase):
    """§6.1 — a ticket references a patient record and never carries one.

    The load-bearing property is not just that identifiers are found: it is that
    finding one never repeats it. A detector that copies the PhilHealth number
    into data_quality.detail has moved the identifier into a column that reports
    read, and called it compliance.
    """

    def test_a_philhealth_shaped_number_is_an_error(self):
        found = phi.scan("PhilHealth 12-345678901-2 for the charge date",
                         field="summary")
        codes = {c for c, _, _ in found}
        self.assertIn("PHI_PHILHEALTH_NUMBER", codes)
        self.assertEqual(
            [s for c, s, _ in found if c == "PHI_PHILHEALTH_NUMBER"], ["ERROR"])

    def test_a_case_number_and_a_record_number_are_errors(self):
        self.assertIn("PHI_CASE_NUMBER",
                      {c for c, _, _ in phi.scan("Case No: 44812", field="summary")})
        self.assertIn("PHI_RECORD_NUMBER",
                      {c for c, _, _ in phi.scan("MRN 99812 needs editing",
                                                 field="description")})

    def test_the_finding_never_repeats_the_identifier(self):
        """The whole point. detail is read by reports, and reports are shared."""
        secret = "12-345678901-2"
        for _, _, detail in phi.scan(f"PhilHealth {secret}", field="summary"):
            self.assertNotIn(secret, detail)
            self.assertNotIn("345678901", detail)

    def test_the_finding_names_the_field_it_was_found_in(self):
        found = phi.scan("Case No: 44812", field="description")
        self.assertTrue(all("description" in d for _, _, d in found))

    def test_ordinary_ticket_text_is_not_flagged(self):
        """A detector that flags every printer fault is one nobody acts on."""
        self.assertEqual(phi.scan("Printer in ward 3 is offline", field="summary"), [])
        self.assertEqual(phi.scan("Ticket 4821 needs reassigning", field="summary"), [])
        self.assertTrue(phi.looks_clean({"summary": "Switch stack down",
                                         "description": "Reseated the uplink."}))

    def test_one_rule_fires_once_per_field(self):
        """Three case numbers in one summary is one problem, not three."""
        found = phi.scan("Case No: 1 and Case No: 2 and Case No: 3", field="summary")
        self.assertEqual(len([c for c, _, _ in found if c == "PHI_CASE_NUMBER"]), 1)

    def test_scan_fields_covers_every_field_given(self):
        found = phi.scan_fields({"summary": "Case No: 1", "description": "MRN 2"})
        self.assertEqual({c for c, _, _ in found},
                         {"PHI_CASE_NUMBER", "PHI_RECORD_NUMBER"})


class PhiAtIntakeTest(unittest.TestCase):
    """The detector wired to the importer: flagged, counted, never dropped.

    Modelled on the message that prompted §6.1 — a charge-date request carrying a
    named patient and a PhilHealth case number, on the same queue as printer
    faults (MEASURED, 9 Sep 2026).
    """

    EXPORT = ("id,summary,description,status,requested_by,opened_at\n"
              "T-1,REQUEST TO EDIT CHARGE DATE,"
              "PhilHealth 12-345678901-2 Case No: 44812 for the charge date,"
              "New,ward3@pmcne.ph,2026-09-09\n"
              "T-2,Printer in ward 3 offline,Reseated the cable,"
              "New,ward3@pmcne.ph,2026-09-09\n")

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        export = Path(self.tmp.name) / "desk.csv"
        export.write_text(self.EXPORT, encoding="utf-8")
        self.summary = tickets.import_tickets(
            self.conn, export, run_id="phi1", at="2026-09-09")

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _phi_findings(self):
        return self.conn.execute(
            "SELECT subject_id, code, severity, detail FROM data_quality"
            " WHERE code LIKE 'PHI_%' ORDER BY finding_id").fetchall()

    def test_the_phi_bearing_row_is_flagged(self):
        codes = {r["code"] for r in self._phi_findings()}
        self.assertIn("PHI_PHILHEALTH_NUMBER", codes)
        self.assertIn("PHI_CASE_NUMBER", codes)

    def test_the_clean_row_is_not_flagged(self):
        self.assertEqual({r["subject_id"] for r in self._phi_findings()}, {"T-1"})

    def test_the_row_still_imports_rather_than_being_dropped(self):
        """Losslessness outranks tidiness: a refused import hides the exposure."""
        self.assertEqual(self.summary["rows_in"], self.summary["rows_out"])
        self.assertEqual(self.summary["rows_in"], 2)
        self.assertTrue(self.conn.execute(
            "SELECT 1 FROM ticket WHERE work_item_id='T-1'").fetchone())

    def test_no_finding_anywhere_repeats_the_identifier(self):
        for row in self.conn.execute("SELECT detail FROM data_quality"):
            self.assertNotIn("345678901", row["detail"] or "")
            self.assertNotIn("44812", row["detail"] or "")


class PatientReferenceTest(unittest.TestCase):
    """013 — the reference may only live where reads are filtered and audited."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.conn.executescript(
            "INSERT OR REPLACE INTO board (board_id,display_name,phase,fulfiller_group,"
            " owner,deputy,is_live,restricted) VALUES"
            " ('OPEN','Open board','2','Dada','a','b',1,0);"
            "INSERT OR REPLACE INTO board (board_id,display_name,phase,fulfiller_group,"
            " owner,deputy,is_live,restricted) VALUES"
            " ('PHI','PHI board','2','Clin','a','b',1,1);")
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _ticket(self, wid, board_id, patient_reference=None):
        self.conn.execute(
            "INSERT INTO work_item (work_item_id, source, name, entity_id,"
            " contract_basis) VALUES (?,'desk','A thing','PMC','BASELINE')", (wid,))
        self.conn.execute(
            "INSERT INTO ticket (work_item_id, board_id, path, impact, urgency,"
            " priority, priority_source, requested_at, opened_at, state,"
            " patient_reference) VALUES (?,?,'INCIDENT','I3','U3','P3','MATRIX',"
            "'2026-09-17 08:00','2026-09-17 08:00','NEW',?)",
            (wid, board_id, patient_reference))

    def test_a_restricted_board_may_hold_a_patient_reference(self):
        self._ticket("ITO-1", "PHI", patient_reference="MRN-0042")
        self.conn.commit()
        self.assertEqual(self.conn.execute(
            "SELECT patient_reference FROM ticket WHERE work_item_id='ITO-1'"
        ).fetchone()["patient_reference"], "MRN-0042")

    def test_an_open_board_may_not(self):
        with self.assertRaises(sqlite3.IntegrityError) as caught:
            self._ticket("ITO-2", "OPEN", patient_reference="MRN-0042")
        self.assertIn("restricted board", str(caught.exception))

    def test_a_ticket_cannot_be_moved_onto_an_open_board_carrying_one(self):
        """Otherwise the rule is only true at insert, which is not a rule."""
        self._ticket("ITO-3", "PHI", patient_reference="MRN-0042")
        self.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "UPDATE ticket SET board_id='OPEN' WHERE work_item_id='ITO-3'")

    def test_an_open_board_ticket_with_no_reference_is_unaffected(self):
        self._ticket("ITO-4", "OPEN")
        self.conn.commit()
        self.assertIsNone(self.conn.execute(
            "SELECT patient_reference FROM ticket WHERE work_item_id='ITO-4'"
        ).fetchone()["patient_reference"])


class EmailIntakeTest(unittest.TestCase):
    """015 — what arrived, what it became, and never the same ticket twice.

    The double-creation is MEASURED (§13 prescribes aliasing support@ onto
    helpdesk@ to stop one cause of it). Aliasing fixes a cause; it does not make
    intake idempotent, which is what these assert.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.drop = Path(self.tmp.name) / "drop"
        self.drop.mkdir()
        self.at = datetime(2026, 9, 22, 9, 0)
        self.n = 0

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _msg(self, *, subject, body="Please help.", sender="ward3@pmcne.ph",
             message_id=None, in_reply_to=None, date="Tue, 22 Sep 2026 09:00:00 +0800",
             name=None):
        self.n += 1
        mid = message_id or f"<m{self.n}@pmcne.ph>"
        headers = [f"From: {sender}", f"Subject: {subject}",
                   f"Date: {date}", f"Message-ID: {mid}"]
        if in_reply_to:
            headers.append(f"In-Reply-To: {in_reply_to}")
        raw = "\r\n".join(headers) + "\r\n\r\n" + body + "\r\n"
        # Bytes, not write_text: on Windows write_text turns each "\n" into
        # "\r\n", so "\r\n" lands on disk as "\r\r\n" and the parser ends the
        # headers after the first line. An .eml is bytes; write it as bytes.
        (self.drop / (name or f"{self.n:03d}.eml")).write_bytes(raw.encode("utf-8"))
        return mid

    def _run(self, run_id="i1"):
        return intake.import_drop(self.conn, self.drop, run_id=run_id, at=self.at)

    def _rows(self):
        return self.conn.execute(
            "SELECT * FROM intake_message ORDER BY received_at, message_id").fetchall()

    # ------------------------------------------------------------ opening one

    def test_a_message_opens_one_numbered_ticket(self):
        self._msg(subject="Printer in ward 3 offline")
        counts = self._run()
        self.assertEqual(counts["new"], 1)
        row = self._rows()[0]
        self.assertEqual(row["disposition"], "NEW_TICKET")
        self.assertTrue(row["work_item_id"].startswith("PMC-"))
        self.assertEqual(self.conn.execute(
            "SELECT name FROM work_item WHERE work_item_id=?",
            (row["work_item_id"],)).fetchone()["name"], "Printer in ward 3 offline")

    def test_the_body_becomes_the_first_event(self):
        self._msg(subject="Printer offline", body="It flashes a red light.")
        self._run()
        detail = self.conn.execute(
            "SELECT detail FROM ticket_event WHERE kind='INTAKE'").fetchone()["detail"]
        self.assertEqual(detail, "It flashes a red light.")

    # -------------------------------------------------------------- idempotent

    def test_running_the_same_drop_twice_makes_no_second_ticket(self):
        """The guard that actually stops double-creation on a re-run."""
        self._msg(subject="Printer offline")
        first = self._run()
        second = self._run(run_id="i2")
        self.assertEqual(first["new"], 1)
        self.assertEqual(second["new"], 0)
        self.assertEqual(second["already_seen"], 1)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM ticket").fetchone()["c"], 1)

    # ------------------------------------------------------------- threading

    def test_a_reply_appends_to_the_ticket_rather_than_opening_one(self):
        parent = self._msg(subject="Printer offline")
        self._run()
        self._msg(subject="RE: Printer offline", body="Still down.",
                  in_reply_to=parent)
        counts = self._run(run_id="i2")
        self.assertEqual(counts["appended"], 1)
        self.assertEqual(counts["new"], 0)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM ticket").fetchone()["c"], 1)
        self.assertTrue(self.conn.execute(
            "SELECT 1 FROM ticket_event WHERE kind='INTAKE_REPLY'").fetchone())

    def test_reply_and_forward_prefixes_do_not_change_the_subject(self):
        self.assertEqual(intake.normalise_subject("RE: FW: Re:  printer"), "printer")
        self.assertEqual(intake.normalise_subject("Printer   offline"), "Printer offline")

    # ------------------------------------------------- the weaker duplicate guard

    def test_a_resend_with_no_thread_header_inside_the_window_is_a_duplicate(self):
        self._msg(subject="Printer offline")
        self._run()
        self._msg(subject="Printer offline")          # no In-Reply-To
        counts = self._run(run_id="i2")
        self.assertEqual(counts["duplicate"], 1)
        self.assertEqual(counts["new"], 0)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM ticket").fetchone()["c"], 1)

    def test_the_same_subject_long_afterwards_is_a_new_request(self):
        """A printer that breaks twice in a month is two tickets, not one."""
        self._msg(subject="Printer offline")
        self._run()
        self.at = datetime(2026, 10, 22, 9, 0)
        self._msg(subject="Printer offline",
                  date="Thu, 22 Oct 2026 09:00:00 +0800")
        counts = self._run(run_id="i2")
        self.assertEqual(counts["new"], 1)

    def test_a_different_requester_with_the_same_subject_is_not_a_duplicate(self):
        self._msg(subject="Printer offline", sender="ward3@pmcne.ph")
        self._run()
        self._msg(subject="Printer offline", sender="ward7@pmcne.ph")
        self.assertEqual(self._run(run_id="i2")["new"], 1)

    # ------------------------------------------------------------ losslessness

    def test_a_message_that_cannot_be_placed_is_imported_and_flagged(self):
        self._msg(subject="", sender="", body="who knows")
        counts = self._run()
        self.assertEqual(counts["unclassified"], 1)
        self.assertEqual(self._rows()[0]["disposition"], "UNCLASSIFIED")
        self.assertTrue(self.conn.execute(
            "SELECT 1 FROM data_quality WHERE code='INTAKE_UNCLASSIFIED'").fetchone())

    def test_every_file_produces_exactly_one_row(self):
        self._msg(subject="One")
        self._msg(subject="Two")
        self._msg(subject="", sender="")
        counts = self._run()
        self.assertEqual(counts["files"], 3)
        self.assertEqual(len(self._rows()), 3)

    def test_a_message_with_no_message_id_is_still_identified_once(self):
        raw = ("From: ward3@pmcne.ph\r\nSubject: No id\r\n"
               "Date: Tue, 22 Sep 2026 09:00:00 +0800\r\n\r\nbody\r\n")
        (self.drop / "noid.eml").write_bytes(raw.encode("utf-8"))
        self.assertEqual(self._run()["new"], 1)
        self.assertEqual(self._run(run_id="i2")["already_seen"], 1)
        self.assertTrue(self._rows()[0]["message_id"].startswith("sha256:"))

    # -------------------------------------------------------------------- PHI

    def test_phi_in_a_message_is_flagged_and_the_message_still_imports(self):
        self._msg(subject="REQUEST TO EDIT CHARGE DATE",
                  body="PhilHealth 12-345678901-2 Case No: 44812")
        counts = self._run()
        self.assertGreater(counts["phi_flagged"], 0)
        self.assertEqual(counts["new"], 1)
        for row in self.conn.execute("SELECT detail FROM data_quality"):
            self.assertNotIn("345678901", row["detail"] or "")


class PortalTest(unittest.TestCase):
    """The requester portal: ownership, not board membership, is the filter.

    Every fulfiller view answers "which boards may you see". This one answers
    "which tickets did you raise", and nothing else — never a board, never a
    queue, never somebody else's request.
    """

    # Reuse the WSGI harness without inheriting WebWSGITest's tests.
    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(_target(self.tmp))
        conn = _fresh(self.tmp)
        conn.executescript(
            "INSERT OR REPLACE INTO board_status (board_status_id, board_id, name,"
            " escalation_status, customer_description) VALUES"
            " ('UNROUTED.PARTS','UNROUTED','Awaiting parts from vendor, PO raised',"
            "  'NO_ESCALATION','We are waiting on a delivery');"
            "INSERT INTO work_item (work_item_id,source,name,contract_basis)"
            " VALUES ('PMC-000901','desk','Printer in ward 3','UNKNOWN');"
            "INSERT INTO ticket (work_item_id,board_id,path,impact,urgency,priority,"
            " priority_source,requested_by,requested_at,opened_at,state,board_status_id,"
            " owner) VALUES ('PMC-000901','UNROUTED','INCIDENT','I3','U3','P4','MATRIX',"
            " 'nurse.a@pmcne.ph','2026-09-22 08:00','2026-09-22 08:00','WAITING_CLIENT',"
            " 'UNROUTED.PARTS','Cadano');"
            "INSERT INTO work_item (work_item_id,source,name,contract_basis)"
            " VALUES ('PMC-000902','desk','Somebody else entirely','UNKNOWN');"
            "INSERT INTO ticket (work_item_id,board_id,path,impact,urgency,priority,"
            " priority_source,requested_by,requested_at,opened_at,state) VALUES"
            " ('PMC-000902','UNROUTED','INCIDENT','I3','U3','P4','MATRIX',"
            " 'nurse.b@pmcne.ph','2026-09-22 08:00','2026-09-22 08:00','NEW');")
        conn.commit()
        conn.close()
        self.config = Config(session_secret=_secrets.token_bytes(32))
        self.raw = make_app(self.db_path, config=self.config,
                            clock=lambda: datetime(2026, 9, 22, 10, 0))
        # A requester: no board membership at all, which is the normal case.
        self.nurse_a = self._cookie_for("nurse.a", email="nurse.a@pmcne.ph")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _conn(self):
        return db.connect(self.db_path)

    # --------------------------------------------------------------- the filter

    def test_requester_wording_never_says_it_and_names_the_owning_board(self):
        """A request may be for any department: the desk's notes are signed with
        the board's name, the emails name the board, and no requester page says IT."""
        conn = self._conn()
        conn.execute("INSERT INTO ticket_event (work_item_id, occurred_at, kind, actor, detail, note_flag)"
                     " VALUES ('PMC-000901', '2026-09-22 09:00', 'NOTE', 'cadano', 'Parts ordered.', 'DISCUSSION')")
        conn.execute("INSERT INTO ticket_event (work_item_id, occurred_at, kind, actor, detail, note_flag)"
                     " VALUES ('PMC-000901', '2026-09-22 09:30', 'NOTE', 'cadano', 'Fitted.', 'RESOLUTION')")
        conn.execute("UPDATE board SET notify_requester = 1 WHERE board_id = 'UNROUTED'")
        conn.commit()
        from psaspine import outbox
        outbox.queue_requester(conn, "PMC-000901", "UPDATED", at=datetime(2026, 9, 22, 10))
        conn.commit()
        body = conn.execute("SELECT body FROM notification WHERE recipient_role = 'REQUESTER'").fetchone()[0]
        board_name = conn.execute("SELECT display_name FROM board WHERE board_id = 'UNROUTED'").fetchone()[0]
        conn.close()
        self.assertIn(f"{board_name} has added an update", body)
        for path in ("/my", "/my/PMC-000901"):
            _, _, page = self._call("GET", path, cookie=self.nurse_a)
            main = page.split("<main>")[1].split("</main>")[0]
            self.assertNotRegex(main, r"\bIT\b", path)
        _, _, page = self._call("GET", "/my/PMC-000901", cookie=self.nurse_a)
        self.assertIn(f"{board_name} &middot;", page)
        self.assertIn(f"{board_name} — resolution", page)

    def test_a_requester_sees_their_own_tickets(self):
        status, _, body = self._call("GET", "/my", cookie=self.nurse_a)
        self.assertTrue(status.startswith("200"))
        self.assertIn("PMC-000901", body)

    def test_a_requester_never_sees_somebody_elses(self):
        _, _, body = self._call("GET", "/my", cookie=self.nurse_a)
        self.assertNotIn("PMC-000902", body)
        self.assertNotIn("Somebody else entirely", body)

    def test_opening_somebody_elses_ticket_is_a_404_not_a_403(self):
        """Absence is the honest answer; a 403 confirms the ticket exists."""
        status, _, _ = self._call("GET", "/my/PMC-000902", cookie=self.nurse_a)
        self.assertTrue(status.startswith("404"))

    def test_the_portal_needs_no_board_membership(self):
        """Four hundred requesters are not board members, and must not need to be."""
        status, _, _ = self._call("GET", "/my/PMC-000901", cookie=self.nurse_a)
        self.assertTrue(status.startswith("200"))

    # -------------------------------------------------- what a requester reads

    def test_the_requester_reads_the_customer_description(self):
        _, _, body = self._call("GET", "/my/PMC-000901", cookie=self.nurse_a)
        self.assertIn("We are waiting on a delivery", body)

    def test_internal_language_and_fields_do_not_leak(self):
        _, _, body = self._call("GET", "/my/PMC-000901", cookie=self.nurse_a)
        self.assertNotIn("Awaiting parts from vendor, PO raised", body)
        self.assertNotIn("Cadano", body)           # the owner
        self.assertNotIn("UNKNOWN", body)          # the contract basis

    def test_with_no_customer_description_the_state_is_said_plainly(self):
        nurse_b = self._cookie_for("nurse.b", email="nurse.b@pmcne.ph")
        _, _, body = self._call("GET", "/my/PMC-000902", cookie=nurse_b)
        self.assertIn("Received, not yet picked up", body)

    # --------------------------------------------------------------- raising one

    def test_raising_a_request_opens_a_numbered_ticket_owned_by_the_requester(self):
        status, headers, _ = self._call(
            "POST", "/my/new", cookie=self.nurse_a,
            form={"summary": "Monitor flickers", "description": "Bed 4.",
                  "impact": "I3", "urgency": "U3"})
        self.assertTrue(status.startswith("303"))
        conn = self._conn()
        row = conn.execute(
            "SELECT work_item_id, requested_by, board_id FROM ticket"
            " WHERE work_item_id LIKE 'PMC-0000%'").fetchone()
        conn.close()
        self.assertEqual(row["requested_by"], "nurse.a@pmcne.ph")
        self.assertEqual(row["board_id"], "UNROUTED")

    # ------------------------------------- the two questions, never a dropdown

    def test_the_form_asks_both_questions_and_offers_no_priority(self):
        _, _, body = self._call("GET", "/my", cookie=self.nurse_a)
        self.assertIn("Who is affected?", body)
        self.assertIn("Is a patient waiting?", body)
        self.assertNotIn("name='priority'", body)
        self.assertNotIn('name="priority"', body)

    def test_the_answers_decide_the_priority(self):
        """One user, patient waiting with care stopped: I3/U1, which the matrix
        puts at P3. Hospital-wide with care stopped: I1/U1, P1."""
        for impact, urgency, expected in (("I3", "U1", "P3"), ("I1", "U1", "P1"),
                                          ("I2", "U2", "P3"), ("I3", "U3", "P4")):
            self._call("POST", "/my/new", cookie=self.nurse_a,
                       form={"summary": f"{impact}{urgency}", "impact": impact,
                             "urgency": urgency})
            conn = self._conn()
            row = conn.execute(
                "SELECT t.priority, t.priority_source FROM ticket t"
                " JOIN work_item w ON w.work_item_id = t.work_item_id WHERE w.name = ?",
                (f"{impact}{urgency}",)).fetchone()
            conn.close()
            self.assertEqual(row["priority"], expected, (impact, urgency))
            self.assertEqual(row["priority_source"], "MATRIX")

    def test_a_priority_smuggled_into_the_form_is_ignored(self):
        """There is no priority field; a crafted one changes nothing."""
        self._call("POST", "/my/new", cookie=self.nurse_a,
                   form={"summary": "smuggle", "impact": "I3", "urgency": "U3",
                         "priority": "P1"})
        conn = self._conn()
        row = conn.execute("SELECT t.priority FROM ticket t JOIN work_item w"
                           " ON w.work_item_id = t.work_item_id WHERE w.name='smuggle'").fetchone()
        conn.close()
        self.assertEqual(row["priority"], "P4")

    def test_an_unanswered_question_is_refused_in_words(self):
        for form in ({"summary": "x", "urgency": "U3"},
                     {"summary": "x", "impact": "I3"},
                     {"summary": "x", "impact": "I9", "urgency": "U3"}):
            status, _, body = self._call("POST", "/my/new", cookie=self.nurse_a,
                                         form=form)
            self.assertTrue(status.startswith("400"), form)
            self.assertIn("answer both questions", body)

    def test_a_request_with_no_summary_is_refused_in_words(self):
        status, _, body = self._call("POST", "/my/new", cookie=self.nurse_a,
                                     form={"summary": "", "description": "x"})
        self.assertTrue(status.startswith("400"))
        self.assertIn("Tell us what you need", body)

    def test_every_requester_box_has_a_help_pop_out_with_a_sample_and_no_rule(self):
        """Dada, 28 Sep 2026: help them nicely, a "?" pop-out or a sample, never a rule."""
        _, _, body = self._call("GET", "/my", cookie=self.nurse_a)
        self.assertGreaterEqual(body.count("<details class=tip>"), 2)     # the text box and the file box
        self.assertIn("What helps us most", body)
        self.assertIn("Ward 3, room 302", body)                             # a worked sample
        self.assertIn("since when", body)
        self.assertIn("crop them out if you can", body)
        for words in ("Please do not", "not allowed", "must not", "prohibited"):
            self.assertNotIn(words, body)
        self.assertNotIn("<script", body.split("<main", 1)[-1].split("</main>", 1)[0])   # plain <details>, no script
        _, _, page = self._call("GET", "/my/PMC-000901", cookie=self.nurse_a)
        self.assertIn("<details class=tip>", page)
        self.assertIn("printed once after a restart", page)
        self.assertNotIn("Please do not", page)

    def test_phi_is_flagged_the_ticket_is_still_created_and_the_requester_told(self):
        """Refusing sends the identifier to the telephone, where nothing records it."""
        status, _, body = self._call(
            "POST", "/my/new", cookie=self.nurse_a,
            form={"summary": "Edit charge date",
                  "description": "PhilHealth 12-345678901-2 Case No: 44812",
                  "impact": "I3", "urgency": "U3"})
        self.assertTrue(status.startswith("200"))
        self.assertIn("One tip for next time", body)                  # a tip, never a telling-off
        self.assertNotIn("Please do not", body)
        self.assertNotIn("flagged", body)
        conn = self._conn()
        created = conn.execute(
            "SELECT COUNT(*) c FROM ticket WHERE requested_by='nurse.a@pmcne.ph'"
        ).fetchone()["c"]
        flags = conn.execute(
            "SELECT detail FROM data_quality WHERE code LIKE 'PHI_%'").fetchall()
        conn.close()
        self.assertEqual(created, 2)
        self.assertTrue(flags)
        for f in flags:
            self.assertNotIn("345678901", f["detail"])

    # ---------------------------------------------------------------- replying

    def test_a_requester_can_reply_on_their_own_ticket(self):
        status, _, _ = self._call("POST", "/my/PMC-000901/reply", cookie=self.nurse_a,
                                  form={"body": "Still flickering."})
        self.assertTrue(status.startswith("303"))
        conn = self._conn()
        ok = conn.execute("SELECT 1 FROM ticket_event WHERE work_item_id='PMC-000901'"
                          " AND kind='PORTAL_REPLY'").fetchone()
        conn.close()
        self.assertTrue(ok)

    def test_a_requester_cannot_reply_on_somebody_elses(self):
        status, _, _ = self._call("POST", "/my/PMC-000902/reply", cookie=self.nurse_a,
                                  form={"body": "hello"})
        self.assertTrue(status.startswith("404"))
        conn = self._conn()
        leaked = conn.execute("SELECT 1 FROM ticket_event WHERE work_item_id='PMC-000902'"
                              " AND kind='PORTAL_REPLY'").fetchone()
        conn.close()
        self.assertIsNone(leaked)


class ProxyAndPortalTest(unittest.TestCase):
    """The desk behind IIS/ARR on DND-SQL01 (SQL01 sitting 2, parts 8 to 10):
    the proxy sends `Host: 127.0.0.1:8085`, the browser's Origin is the public
    one, TLS ends at the proxy, and the requester portal has an address of its
    own. Everything the desk decides about that comes from PSA_PUBLIC_URL and
    PSA_PORTAL_URL, never from a header a LAN client could write."""

    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for
    tearDown = WebWSGITest.tearDown

    def setUp(self) -> None:
        WebWSGITest.setUp(self)
        self.config.public_url = "https://desk.pmcne.ph"
        self.config.portal_url = "https://help.pmcne.ph"
        self.alice = self._cookie_for("alice")
        self.nurse = self._cookie_for("nurse.a", email="nurse.a@pmcne.ph")
        self.proxy = {"Host": "127.0.0.1:8085"}

    # ------------------------------------------------------------ part 8

    def test_a_form_posted_from_a_public_address_is_accepted_and_any_other_refused(self):
        for origin, ok in (("https://desk.pmcne.ph", True), ("https://help.pmcne.ph", True),
                           ("https://DESK.pmcne.ph:443", True), ("https://evil.example", False),
                           ("http://desk.pmcne.ph", False)):
            status, _, _ = self._call("POST", "/ticket/ITO-1/note", cookie=self.alice,
                                      form={"body": "via the proxy", "flag": "DISCUSSION"},
                                      headers={**self.proxy, "Origin": origin})
            self.assertEqual(status.startswith("303"), ok, origin)

    def test_with_a_public_https_url_every_cookie_is_secure_and_hsts_is_sent_over_plain_http(self):
        conn = db.connect(self.db_path)
        webauth.create_local_account(conn, "glass", "correct horse battery staple", created_by="t",
                                     at=datetime(2026, 9, 17, 9))
        conn.commit()
        conn.close()
        status, headers, _ = self._call("POST", "/login", headers=self.proxy, form={
            "username": "glass", "password": "correct horse battery staple", "next": "/"})
        self.assertTrue(status.startswith("303"), status)
        cookie = next(v for k, v in headers if k == "Set-Cookie")
        self.assertIn("psa_session=", cookie)
        self.assertIn("Secure", cookie)
        self.assertIn(("Strict-Transport-Security", "max-age=31536000"), headers)
        # and the same page with no public URL at all: neither
        self.config.public_url = self.config.portal_url = None
        _, headers, _ = self._call("POST", "/login", headers=self.proxy, form={
            "username": "glass", "password": "correct horse battery staple", "next": "/"})
        cookie = next(v for k, v in headers if k == "Set-Cookie")
        self.assertNotIn("Secure", cookie)
        self.assertFalse(any(k == "Strict-Transport-Security" for k, _ in headers))

    def test_secure_comes_from_config_never_from_a_forwarded_proto_header(self):
        self.config.public_url = self.config.portal_url = None
        conn = db.connect(self.db_path)
        webauth.create_local_account(conn, "glass", "pw pw pw pw", created_by="t", at=datetime(2026, 9, 17, 9))
        conn.commit()
        conn.close()
        _, headers, _ = self._call("POST", "/login", form={"username": "glass", "password": "pw pw pw pw"},
                                   headers={**self.proxy, "X-Forwarded-Proto": "https"}, remote_addr="127.0.0.1")
        self.assertNotIn("Secure", next(v for k, v in headers if k == "Set-Cookie"))

    # ------------------------------------------------------------ part 10

    def _portal(self, method, path, **kw):
        """A request that came through the portal's IIS site: the proxy is on the
        loopback and says which host it was asked for."""
        headers = {**self.proxy, "X-Forwarded-Host": "help.pmcne.ph", **kw.pop("headers", {})}
        return self._call(method, path, headers=headers, remote_addr="127.0.0.1", **kw)

    def test_the_portal_host_serves_the_requesters_pages_and_nothing_else(self):
        status, headers, _ = self._portal("GET", "/")
        self.assertTrue(status.startswith("303"))
        self.assertEqual(dict(headers)["Location"], "/my")
        # technician paths are not there, signed in or not, and say nothing more
        for path in ("/dispatch", "/uplift", "/admin", "/ticket/new", "/ticket/ITO-1",
                     "/api/v1/tickets", "/search.json", "/reports", "/companies", "/bulk"):
            status, _, body = self._portal("GET", path, cookie=self.alice)
            self.assertTrue(status.startswith("404"), f"{path} -> {status}")
            self.assertNotIn("Printer down", body)
            status, _, _ = self._portal("GET", path)
            self.assertTrue(status.startswith("404"), f"{path} unauthenticated -> {status}")
        # the requester's own pages answer
        status, _, body = self._portal("GET", "/my", cookie=self.nurse)
        self.assertTrue(status.startswith("200"))
        self.assertIn("Your requests", body)
        status, _, _ = self._portal("GET", "/logout", cookie=self.nurse)
        self.assertTrue(status.startswith("303"))

    def test_on_the_portal_host_sign_in_returns_to_my_requests(self):
        status, _, body = self._portal("GET", "/dispatch")
        self.assertTrue(status.startswith("404"))
        status, _, body = self._portal("GET", "/login", query="next=/admin")
        self.assertTrue(status.startswith("200"))
        self.assertIn('name="next" value="/my"', body)
        status, _, body = self._portal("GET", "/my/ITO-1")            # not signed in
        self.assertTrue(status.startswith("401"))
        self.assertIn('name="next" value="/my/ITO-1"', body)
        conn = db.connect(self.db_path)
        webauth.create_local_account(conn, "glass", "correct horse battery staple", created_by="t",
                                     at=datetime(2026, 9, 17, 9))
        conn.commit()
        conn.close()
        status, headers, _ = self._portal("POST", "/login", form={
            "username": "glass", "password": "correct horse battery staple", "next": "/admin"})
        self.assertTrue(status.startswith("303"), status)
        self.assertEqual(dict(headers)["Location"], "/my")

    def test_the_portal_hosts_sign_in_page_wears_the_requesters_brand(self):
        """SQL01, part 14: a ward's first sight of help.pmcne.ph was "Sign in · Dada PSA"."""
        status, _, body = self._portal("GET", "/my")
        self.assertTrue(status.startswith("401"), status)
        self.assertIn("<title>Sign in · PMC Requests</title>", body)
        self.assertNotIn("Dada PSA", body)
        _, _, body = self._portal("GET", "/login")
        self.assertIn("<title>Sign in · PMC Requests</title>", body)
        status, _, body = self._portal("POST", "/login", form={"username": "x", "password": "y"})
        self.assertTrue(status.startswith("401"), status)
        self.assertIn("<title>Sign in · PMC Requests</title>", body)      # a refused try, the same brand
        _, _, body = self._call("GET", "/login")
        self.assertIn("<title>Sign in · Dada PSA</title>", body)          # the desk keeps its own

    def test_on_a_phone_the_nav_keeps_its_icons_and_loses_its_words(self):
        """SQL01, part 15: at 390 px "My requests" sat under the user block."""
        _, _, body = self._portal("GET", "/my", cookie=self.alice)
        self.assertIn("<span class=lbl>My requests</span>", body)
        self.assertIn("@media (max-width:480px)", body)
        self.assertIn("header.top nav a .lbl{display:none}", body)

    def test_answer_choices_are_laid_out_one_per_item(self):
        """Dada, part 14: the raise form read "not working○ I need something"."""
        _, _, body = self._portal("GET", "/my", cookie=self.alice)
        self.assertGreaterEqual(body.count("<div class=choices>"), 3)
        self.assertNotIn("</label><label style=", body)
        self.assertNotIn("style='width:auto'", body)

    def test_on_the_portal_host_even_a_technician_gets_the_requesters_shell(self):
        _, _, body = self._portal("GET", "/my", cookie=self.alice)
        self.assertIn("<body data-requester>", body)
        self.assertIn("PMC Requests", body)
        for gone in (">Dispatch<", ">Service Board<", ">Setup<", 'id="pal"', "⌘K", 'class="newbtn"',
                     'popovertarget="keys"'):
            self.assertNotIn(gone, body, gone)
        self.assertIn('id="theme"', body)                         # light/dark stays
        self.assertIn("sign out", body)
        # the same person on the desk's address has the whole desk
        _, _, body = self._call("GET", "/my", cookie=self.alice, headers={"Host": "desk.pmcne.ph"})
        self.assertNotIn("<body data-requester>", body)
        for there in (">Dispatch<", ">Service Board<", 'id="pal"', 'class="newbtn"'):
            self.assertIn(there, body, there)

    def test_a_forwarded_host_is_believed_from_the_loopback_only(self):
        # a LAN client naming the portal host in a header is not on the portal
        status, _, body = self._call("GET", "/dispatch", cookie=self.alice,
                                     headers={"Host": "desk.pmcne.ph", "X-Forwarded-Host": "help.pmcne.ph"},
                                     remote_addr="192.0.2.10")
        self.assertTrue(status.startswith("200"), status)
        # the same header from the loopback is the proxy speaking
        status, _, _ = self._call("GET", "/dispatch", cookie=self.alice,
                                  headers={"Host": "127.0.0.1:8085", "X-Forwarded-Host": "help.pmcne.ph"},
                                  remote_addr="127.0.0.1")
        self.assertTrue(status.startswith("404"), status)
        # and the Host header alone names the portal when nothing is in front
        status, _, _ = self._call("GET", "/dispatch", cookie=self.alice,
                                  headers={"Host": "help.pmcne.ph"})
        self.assertTrue(status.startswith("404"), status)
        # with no portal URL configured nothing is a portal host
        self.config.portal_url = None
        status, _, _ = self._call("GET", "/dispatch", cookie=self.alice, headers={"Host": "help.pmcne.ph"})
        self.assertTrue(status.startswith("200"), status)

    def test_a_person_on_no_board_lands_on_their_requests_with_the_requesters_shell(self):
        status, headers, _ = self._call("GET", "/", cookie=self.nurse, headers={"Host": "desk.pmcne.ph"})
        self.assertTrue(status.startswith("303"))
        self.assertEqual(dict(headers)["Location"], "/my")
        _, _, body = self._call("GET", "/my", cookie=self.nurse, headers={"Host": "desk.pmcne.ph"})
        self.assertIn("<body data-requester>", body)
        self.assertNotIn(">Dispatch<", body)
        self.assertNotIn('id="pal"', body)
        # a member keeps the desk's shell on the same page
        _, _, body = self._call("GET", "/my", cookie=self.alice, headers={"Host": "desk.pmcne.ph"})
        self.assertNotIn("<body data-requester>", body)
        self.assertIn(">Dispatch<", body)


class EmployeePortalDoorTest(unittest.TestCase):
    """POST /sso/portal (SQL01's handoff of 28 Sep 2026, hardened per its review
    the same day): an employee the payroll portal has signed in opens My
    requests with no second sign-in. The bridge is a fake on the Config here
    (the real one is tried below against a loopback server); every refusal is
    audited and then a redirect to a fixed page, and the token appears nowhere."""

    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for
    tearDown = WebWSGITest.tearDown
    TOKEN = "0123456789abcdef0123456789abcdef0123456789abcdef"

    def setUp(self) -> None:
        WebWSGITest.setUp(self)
        conn = db.connect(self.db_path)
        conn.execute(
            "INSERT INTO contact (contact_id, entity_id, display_name, email, sam_account, department, source,"
            " inactive, created_at) VALUES ('C_NURSE', 'PMC', 'Nurse A. Santos', 'nurse.a@pmcne.ph',"
            " 'nurse.a', 'Nursing', 'AD', 0, '2026-09-17 08:00')")
        conn.execute("UPDATE ticket SET requested_by = 'nurse.a@pmcne.ph' WHERE work_item_id = 'ITO-1'")
        conn.commit()
        conn.close()
        self.calls = []
        self.answer = (200, {"employee": {"ADLogin": "Nurse.A", "FullName": "Nurse A. Santos",
                                          "Department": "Nursing", "EmpKey": 4471}, "impersonated": False})
        self.raises = None

        def bridge_get(url, headers, timeout):
            self.calls.append((url, dict(headers), timeout))
            if self.raises:
                raise self.raises
            return self.answer

        self.config.public_url = "https://desk.pmcne.ph"
        self.config.portal_url = "https://help.pmcne.ph"
        self.config.employee_portal_origins = "https://portal.pmcne.ph, https://payroll.pmcne.ph"
        self.config.employee_portal_departments = "Nursing, Pharmacy"
        self.config.bridge_get = bridge_get

    def _door(self, *, origin="https://portal.pmcne.ph", token=None, host="help.pmcne.ph", method="POST",
              extra=None):
        form = {"token": self.TOKEN if token is None else token, **(extra or {})}
        headers = {"Host": "127.0.0.1:8085", "X-Forwarded-Host": host}
        if origin:
            headers["Origin"] = origin
        return self._call(method, "/sso/portal", form=form if method == "POST" else None,
                          headers=headers, remote_addr="127.0.0.1")

    def _refusal(self, headers):
        """Follow the post-redirect-get to the refusal page: (code, status, body)."""
        loc = dict(headers)["Location"]
        self.assertTrue(loc.startswith("/sso/portal?refused="), loc)
        code = loc.split("=", 1)[1]
        status, _, body = self._call("GET", "/sso/portal", query="refused=" + code,
                                     headers={"Host": "127.0.0.1:8085", "X-Forwarded-Host": "help.pmcne.ph"},
                                     remote_addr="127.0.0.1")
        return code, status, body

    def _audit(self, action):
        conn = db.connect(self.db_path)
        rows = conn.execute("SELECT actor, subject_id, detail FROM audit_event WHERE action = ?"
                            " ORDER BY audit_id", (action,)).fetchall()
        conn.close()
        return [tuple(r) for r in rows]

    def test_an_employee_the_portal_vouches_for_lands_on_their_requests(self):
        status, headers, _ = self._door()
        self.assertTrue(status.startswith("303"), status)
        self.assertEqual(dict(headers)["Location"], "/my")
        url, hdrs, timeout = self.calls[0]
        self.assertEqual(url, "http://127.0.0.1:4100/api/portal/me")
        self.assertEqual(hdrs, {"x-pmc-portal-token": self.TOKEN})
        self.assertLessEqual(timeout, 5)
        cookie = next(v for k, v in headers if k == "Set-Cookie")
        self.assertTrue(cookie.startswith("psa_session="))
        self.assertNotIn("Max-Age", cookie)
        for attr in ("Secure", "HttpOnly", "SameSite=Lax", "Path=/"):
            self.assertIn(attr, cookie)
        # two hours, not the desk's twelve; and the department rides on the session
        payload = webauth.read_session(cookie.split(";", 1)[0].split("=", 1)[1], self.config.session_secret)
        self.assertEqual(payload["exp"] - payload["iat"], 2 * 3600)
        self.assertEqual((payload["via"], payload["dept"]), ("portal", "Nursing"))
        self.assertEqual(self._audit("PORTAL_SSO"),
                         [("nurse.a", "nurse.a", "employee portal, contact C_NURSE, department Nursing")])
        self.assertEqual(self._audit("PORTAL_SSO_REFUSED"), [])
        session = cookie.split(";", 1)[0]
        status, _, body = self._call("GET", "/my", cookie=session, headers={"Host": "help.pmcne.ph"})
        self.assertTrue(status.startswith("200"), status)
        self.assertIn("Printer down", body)
        self.assertIn("Nurse A. Santos", body)
        self.assertIn("<body data-requester>", body)
        self.assertIn("PMC Requests", body)
        self.assertNotIn("IT help", body)
        self.assertNotIn("Dada IT only", body)
        # the same person through the Windows door sees the same tickets
        self.config.windows_domain = "PMCNE"
        self.config.windows_logon = lambda domain, user, pw: (user == "nurse.a" and pw == "pw", 0)
        _, headers, _ = self._call("POST", "/login", form={"door": "windows", "username": "PMCNE\\Nurse.A",
                                                            "password": "pw", "next": "/my"})
        win = next(v for k, v in headers if k == "Set-Cookie").split(";", 1)[0]
        _, _, windows = self._call("GET", "/my", cookie=win)
        self.assertIn("Printer down", windows)

    def test_next_is_ignored_and_the_landing_is_always_my_requests(self):
        _, headers, _ = self._door(extra={"next": "/admin"})
        self.assertEqual(dict(headers)["Location"], "/my")
        _, headers, _ = self._door(extra={"next": "/my/ITO-1%0D%0AX-Injected: 1"})
        self.assertEqual(dict(headers)["Location"], "/my")

    def test_the_origin_must_be_a_listed_https_origin(self):
        for origin, ok in (("https://portal.pmcne.ph", True), ("https://PAYROLL.pmcne.ph:443", True),
                           ("http://portal.pmcne.ph", False), ("https://evil.example", False),
                           ("https://help.pmcne.ph", False), ("", False)):
            self.calls.clear()
            status, headers, _ = self._door(origin=origin)
            self.assertEqual(status.startswith("303"), True, origin)
            if ok:
                self.assertEqual(dict(headers)["Location"], "/my", origin)
            else:
                code, status, body = self._refusal(headers)
                self.assertEqual(code, "origin")
                self.assertTrue(status.startswith("403"), (origin, status))
                self.assertEqual(self.calls, [], origin)           # the token never left for the bridge
                self.assertIn("not the Employee Portal", body)
        refused = self._audit("PORTAL_SSO_REFUSED")
        self.assertEqual(len(refused), 4)
        self.assertTrue(any("not https" in r[2] for r in refused))
        self.assertFalse(any(self.TOKEN in (r[2] or "") for r in refused))

    def test_the_door_is_off_until_origins_are_named_and_only_on_the_portal_host(self):
        status, _, _ = self._door(host="desk.pmcne.ph")
        self.assertTrue(status.startswith("404"), status)
        self.config.employee_portal_origins = None
        status, _, _ = self._door()
        self.assertTrue(status.startswith("404"), status)
        self.config.employee_portal_origins = "http://portal.pmcne.ph"          # not https: not a list
        status, _, _ = self._door()
        self.assertTrue(status.startswith("404"), status)
        self.assertEqual(self.calls, [])
        self.config.employee_portal_origins = "https://portal.pmcne.ph"
        status, _, _ = self._door(method="PUT")
        self.assertTrue(status.startswith("405"), status)
        # the refusal page itself is a GET on the portal host, with fixed words
        status, _, body = self._call("GET", "/sso/portal", query="refused=closed",
                                     headers={"Host": "127.0.0.1:8085", "X-Forwarded-Host": "help.pmcne.ph"},
                                     remote_addr="127.0.0.1")
        self.assertTrue(status.startswith("403"))
        self.assertIn("not open for your department", body)
        status, _, body = self._call("GET", "/sso/portal", query="refused=<script>",
                                     headers={"Host": "127.0.0.1:8085", "X-Forwarded-Host": "help.pmcne.ph"},
                                     remote_addr="127.0.0.1")
        self.assertTrue(status.startswith("503"))
        self.assertNotIn("<script>", body.split("<main>")[1].split("</main>")[0])    # never reflected

    def test_each_refusal_is_a_redirect_to_a_page_in_words_and_an_audit_row_without_the_token(self):
        cases = [
            ("no token", dict(token=""), None, None, "ended", "401", "session has ended", "no token"),
            ("bad shape", dict(token="abc\r\nX: 1"), None, None, "ended", "401", "session has ended", "not shaped"),
            ("dead token", {}, (401, None), None, "ended", "401", "session has ended", "bridge answered 401"),
            ("forbidden", {}, (403, None), None, "ended", "401", "session has ended", "bridge answered 403"),
            ("bridge fault", {}, (500, None), None, "unchecked", "503", "could not be checked", "bridge answered 500"),
            ("redirect", {}, (302, None), None, "unchecked", "503", "could not be checked", "bridge answered 302"),
            ("not json", {}, (200, None), None, "unchecked", "503", "could not be checked", "bridge answered 200"),
            ("preview", {}, (200, {"employee": {"ADLogin": "pmo.admin", "Department": "Nursing"},
                                   "impersonated": True}), None, "preview", "403", "admin preview", "admin preview"),
            ("no flag", {}, (200, {"employee": {"ADLogin": "nurse.a", "Department": "Nursing"}}), None,
             "preview", "403", "admin preview", "no impersonated flag"),
            ("no ADLogin", {}, (200, {"employee": {"ADLogin": "", "Department": "Nursing", "EmpKey": 9},
                                      "impersonated": False}), None, "not_linked", "403", "not linked", "no ADLogin"),
            ("ADLogin true", {}, (200, {"employee": {"ADLogin": True, "Department": "Nursing"},
                                        "impersonated": False}), None, "not_linked", "403", "not linked", "no ADLogin"),
            ("bad shape login", {}, (200, {"employee": {"ADLogin": "Bad Login!", "Department": "Nursing"},
                                           "impersonated": False}), None, "not_linked", "403", "not linked", "not shaped"),
            ("closed", {}, (200, {"employee": {"ADLogin": "nurse.a", "Department": "Radiology"},
                                  "impersonated": False}), None, "closed", "403", "not open for your department",
             "department not open (Radiology)"),
            ("timeout", {}, None, TimeoutError("timed out"), "unchecked", "503", "could not be checked", "not answering"),
        ]
        for label, kw, answer, raises, code, status_prefix, words, audit_words in cases:
            if answer is not None:
                self.answer = answer
            self.raises = raises
            status, headers, body = self._door(**kw)
            self.assertTrue(status.startswith("303"), (label, status))            # never the page itself
            self.assertFalse(any(k == "Set-Cookie" for k, _ in headers), label)
            got, status, body = self._refusal(headers)
            self.assertEqual(got, code, label)
            self.assertTrue(status.startswith(status_prefix), (label, status))
            self.assertIn(words, body, label)
            self.assertIn("/login?next=/my", body, label)
            self.assertIn("<body data-requester>", body, label)
            self.assertNotIn(self.TOKEN, body, label)
        refused = self._audit("PORTAL_SSO_REFUSED")
        self.assertEqual(len(refused), len(cases))
        for (label, *_, audit_words), row in zip(cases, refused):
            self.assertIn(audit_words, row[2], label)
            self.assertNotIn(self.TOKEN, row[2] or "", label)
        self.assertEqual([r[1] for r in refused if "EmpKey" in str(r) or r[2].startswith("no ADLogin")][:1], ["9"])
        self.assertEqual(self._audit("PORTAL_SSO"), [])

    def test_a_disabled_windows_account_is_refused_and_a_department_with_no_list_is_closed(self):
        conn = db.connect(self.db_path)
        conn.execute("UPDATE contact SET inactive = 1 WHERE contact_id = 'C_NURSE'")
        conn.commit()
        conn.close()
        _, headers, _ = self._door()
        code, status, body = self._refusal(headers)
        self.assertEqual((code, status[:3]), ("disabled", "403"))
        self.assertIn("disabled", body)
        self.assertEqual(self._audit("PORTAL_SSO_REFUSED")[-1], ("nurse.a", "nurse.a", "AD account disabled"))
        conn = db.connect(self.db_path)
        conn.execute("UPDATE contact SET inactive = 0 WHERE contact_id = 'C_NURSE'")
        conn.commit()
        conn.close()
        self.config.employee_portal_departments = None
        _, headers, _ = self._door()
        self.assertEqual(self._refusal(headers)[0], "closed")

    def test_the_checklist_decides_once_a_box_is_ticked(self):
        from psaspine import departments
        conn = db.connect(self.db_path)
        departments.add(conn, "Nursing", at=datetime(2026, 9, 28), actor="root")
        departments.add(conn, "Radiology", at=datetime(2026, 9, 28), actor="root")
        departments.save_grid(conn, {"Radiology": {"IT_HELP"}}, at=datetime(2026, 9, 28), actor="root")
        conn.commit()
        conn.close()
        # the env var names Nursing, but the grid is in charge now and Nursing has no tick
        _, headers, _ = self._door()
        self.assertEqual(self._refusal(headers)[0], "closed")
        self.answer = (200, {"employee": {"ADLogin": "rad.b", "Department": "Radiology"}, "impersonated": False})
        _, headers, _ = self._door()
        self.assertEqual(dict(headers)["Location"], "/my")

    def test_a_username_with_an_underscore_never_binds_to_another_persons_email(self):
        conn = db.connect(self.db_path)
        conn.execute("INSERT INTO contact (contact_id, entity_id, display_name, email, upn, source, inactive,"
                     " created_at) VALUES ('C_JA', 'PMC', 'Ja Cruz', 'jacruz@pmcne.ph', 'jacruz@pmcne.ph',"
                     " 'AD', 0, '2026-09-17 08:00')")
        conn.commit()
        conn.close()
        self.answer = (200, {"employee": {"ADLogin": "j_cruz", "Department": "Nursing"}, "impersonated": False})
        _, headers, _ = self._door()
        cookie = next(v for k, v in headers if k == "Set-Cookie").split(";", 1)[0]
        payload = webauth.read_session(cookie.split("=", 1)[1], self.config.session_secret)
        self.assertIsNone(payload["email"])                     # not jacruz's
        self.assertEqual(self._audit("PORTAL_SSO")[-1][2], "employee portal, no contact row, department Nursing")

    def test_sign_out_on_the_portal_host_clears_a_secure_cookie(self):
        status, headers, _ = self._call("GET", "/logout", cookie=self._cookie_for("nurse.a"),
                                        headers={"Host": "127.0.0.1:8085", "X-Forwarded-Host": "help.pmcne.ph"},
                                        remote_addr="127.0.0.1")
        self.assertTrue(status.startswith("303"))
        cookie = next(v for k, v in headers if k == "Set-Cookie")
        self.assertTrue(cookie.startswith("psa_session=;") or cookie.startswith('psa_session="";'), cookie)
        self.assertIn("Max-Age=0", cookie)
        self.assertIn("Secure", cookie)
        self.config.public_url = self.config.portal_url = None
        _, headers, _ = self._call("GET", "/logout", cookie=self._cookie_for("nurse.a"))
        self.assertNotIn("Secure", next(v for k, v in headers if k == "Set-Cookie"))


class RealBridgeTest(unittest.TestCase):
    """sso.bridge_get against a loopback http.server: what the bridge answers is
    a status, a redirect is refused before the token goes anywhere, a slow
    bridge is an exception, and nothing is read past 64 KB."""

    def setUp(self) -> None:
        import http.server
        import threading
        seen = self.seen = []

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                seen.append((self.path, self.headers.get("x-pmc-portal-token")))
                if self.path == "/slow/api/portal/me":
                    import time as _t
                    _t.sleep(1.2)
                    self.send_response(200)
                    self.end_headers()
                    return
                if self.path == "/redirect/api/portal/me":
                    self.send_response(302)
                    self.send_header("Location", "http://127.0.0.1:1/elsewhere")
                    self.end_headers()
                    return
                if self.path == "/html/api/portal/me":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"<html>not json</html>")
                    return
                if self.path == "/big/api/portal/me":
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"pad":"' + b"x" * (70 * 1024) + b'"}')
                    return
                code = {"/ok/api/portal/me": 200, "/dead/api/portal/me": 401, "/fault/api/portal/me": 500}[self.path]
                body = b'{"employee": {"ADLogin": "nurse.a"}, "impersonated": false}' if code == 200 else b'{"error":"x"}'
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

        self.httpd = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def test_statuses_come_back_as_statuses_and_the_rest_as_the_door_expects(self):
        from psaspine.web import sso
        h = {"x-pmc-portal-token": "ab" * 24}
        self.assertEqual(sso.bridge_get(self.base + "/ok/api/portal/me", h, 2),
                         (200, {"employee": {"ADLogin": "nurse.a"}, "impersonated": False}))
        self.assertEqual(sso.bridge_get(self.base + "/dead/api/portal/me", h, 2), (401, None))
        self.assertEqual(sso.bridge_get(self.base + "/fault/api/portal/me", h, 2), (500, None))
        self.assertEqual(sso.bridge_get(self.base + "/html/api/portal/me", h, 2), (200, None))
        self.assertEqual(sso.bridge_get(self.base + "/big/api/portal/me", h, 2), (200, None))
        # a redirect is a status of its own and the token was sent once, to the bridge only
        self.assertEqual(sso.bridge_get(self.base + "/redirect/api/portal/me", h, 2), (302, None))
        self.assertTrue(all(tok == "ab" * 24 for _, tok in self.seen))
        self.assertFalse(any("elsewhere" in path for path, _ in self.seen))
        with self.assertRaises(Exception):
            sso.bridge_get(self.base + "/slow/api/portal/me", h, 0.3)

    def test_the_environments_proxy_is_never_used(self):
        import os
        from psaspine.web import sso
        old = {k: os.environ.get(k) for k in ("HTTP_PROXY", "http_proxy")}
        os.environ["HTTP_PROXY"] = os.environ["http_proxy"] = "http://127.0.0.1:1"
        try:
            self.assertEqual(sso.bridge_get(self.base + "/dead/api/portal/me", {"x-pmc-portal-token": "a" * 48}, 2),
                             (401, None))
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class DepartmentsTest(unittest.TestCase):
    """034 and psaspine.departments: the list from payroll, the grid, and what
    obeys it (the portal's raise form; the door is tried above)."""

    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for
    tearDown = WebWSGITest.tearDown

    def setUp(self) -> None:
        WebWSGITest.setUp(self)
        conn = db.connect(self.db_path)
        conn.executescript(
            "INSERT OR REPLACE INTO board (board_id,display_name,phase,fulfiller_group,owner,deputy,is_live,is_unrouted)"
            " VALUES ('MAINT','Maintenance','2','Facilities','m','n',1,0);"
            "INSERT OR REPLACE INTO board_status (board_status_id,board_id,name,escalation_status,is_default)"
            " VALUES ('MAINT.NEW','MAINT','New','NOT_RESPONDED',1);"
            "INSERT INTO contact (contact_id, entity_id, display_name, email, sam_account, department, source,"
            " inactive, created_at) VALUES ('C_WARD', 'PMC', 'Ward B', 'ward.b@pmcne.ph', 'ward.b', 'Ward B',"
            " 'AD', 0, '2026-09-17 08:00');")
        conn.commit()
        conn.close()
        self.root = self._cookie_for("root", is_sysadmin=True)
        self.at = datetime(2026, 9, 28, 9)

    def _csv(self, *names):
        path = Path(self.tmp.name) / "departments.csv"
        path.write_text("\ufeffDepartment\r\n" + "".join(n + "\r\n" for n in names), encoding="utf-8")
        return path

    def test_the_list_imports_retires_and_never_deletes(self):
        from psaspine import departments
        conn = db.connect(self.db_path)
        r = departments.import_csv(conn, self._csv("Ward A", "Ward B", "Ward A", "Pharmacy"), at=self.at)
        self.assertEqual((r["rows"], r["new"]), (3, 3))
        departments.add(conn, "Biomedical", at=self.at, actor="root")
        departments.save_grid(conn, {"Ward A": {"IT_HELP"}, "Pharmacy": {"IT_HELP", "MAINT"}}, at=self.at, actor="root")
        r = departments.import_csv(conn, self._csv("Ward A", "Ward B"), at=self.at)
        self.assertEqual((r["new"], r["seen"], r["retired"]), (0, 2, 1))
        rows = {d["name"]: (d["retired"], d["source"]) for d in departments.all_departments(conn)}
        self.assertEqual(rows["Pharmacy"], (1, "PAYROLL"))          # retired, not deleted
        self.assertEqual(rows["Biomedical"], (0, "MANUAL"))         # a manual one is left alone
        self.assertEqual([b["board_id"] for b in departments.boards_for(conn, "Pharmacy")], ["IT_HELP", "MAINT"])
        r = departments.import_csv(conn, self._csv("Ward A", "Ward B", "Pharmacy"), at=self.at)
        self.assertEqual(r["restored"], 1)
        with self.assertRaises(ValueError):
            departments.import_csv(conn, Path(self.tmp.name) / "nope.csv" if False else self._nocol(), at=self.at)
        conn.close()

    def _nocol(self):
        path = Path(self.tmp.name) / "wrong.csv"
        path.write_text("Name\r\nWard A\r\n")
        return path

    def test_the_grid_saves_once_and_audits_what_changed(self):
        from psaspine import departments
        conn = db.connect(self.db_path)
        departments.import_csv(conn, self._csv("Ward A", "Ward B"), at=self.at)
        conn.commit()
        conn.close()
        status, _, page = self._call("GET", "/admin/departments", cookie=self.root)
        self.assertTrue(status.startswith("200"))
        self.assertIn("Ward A", page)
        self.assertIn("Maintenance", page)
        self.assertNotIn("Unrouted", page.split("<thead>")[1].split("</thead>")[0])
        _, headers, _ = self._call("POST", "/admin/departments/save", cookie=self.root,
                                   form=None, query="")
        self.assertIn("Nothing+changed", dict(headers)["Location"])
        body = _urlparse.urlencode([("tick", "Ward A|IT_HELP"), ("tick", "Ward A|MAINT"), ("tick", "Ward B|MAINT"),
                                    ("tick", "Ward B|UNROUTED"), ("tick", "Nobody|IT_HELP")]).encode()
        status, headers, _ = self._call_raw("POST", "/admin/departments/save", body)
        loc = _urlparse.unquote_plus(dict(headers)["Location"])
        self.assertIn("Ward A: + IT Help, + Maintenance; Ward B: + Maintenance", loc)
        conn = db.connect(self.db_path)
        self.assertEqual(sorted((r[0], r[1]) for r in conn.execute("SELECT department, board_id FROM department_board")),
                         [("Ward A", "IT_HELP"), ("Ward A", "MAINT"), ("Ward B", "MAINT")])
        audit = conn.execute("SELECT detail FROM audit_event WHERE action = 'DEPARTMENT_BOARDS'").fetchall()
        self.assertEqual(len(audit), 1)
        conn.close()
        body = _urlparse.urlencode([("tick", "Ward A|MAINT")]).encode()
        _, headers, _ = self._call_raw("POST", "/admin/departments/save", body)
        loc = _urlparse.unquote_plus(dict(headers)["Location"])
        self.assertIn("Ward A: − IT Help; Ward B: − Maintenance", loc)
        _, _, page = self._call("GET", "/admin/departments", cookie=self.root)
        self.assertIn(">open<", page)
        self.assertIn(">closed<", page)
        _, headers, _ = self._call("POST", "/admin/departments/add", cookie=self.root, form={"name": "Ward B"})
        self.assertIn("already", dict(headers)["Location"])
        status, _, _ = self._call("GET", "/admin/departments", cookie=self._cookie_for("alice"))
        self.assertTrue(status.startswith("403"))

    def _call_raw(self, method, path, body):
        import io as _io
        env = self._environ(method, path, cookie=self.root, body=body)
        app = _validator(self.raw)
        captured = {}

        def start_response(status, headers, exc_info=None):
            captured["status"], captured["headers"] = status, headers
        it = app(env, start_response)
        try:
            payload = b"".join(it).decode()
        finally:
            it.close()
        return captured["status"], captured["headers"], payload

    def test_the_raise_form_offers_the_ticked_boards_and_the_ticket_lands_there(self):
        from psaspine import departments
        conn = db.connect(self.db_path)
        departments.import_csv(conn, self._csv("Ward B"), at=self.at)
        conn.commit()
        conn.close()
        ward = self._cookie_for("ward.b", email="ward.b@pmcne.ph", department="Ward B")
        # nothing ticked: no choice, Unrouted as today
        _, _, page = self._call("GET", "/my", cookie=ward)
        self.assertNotIn("Who is this for?", page)
        _, headers, _ = self._call("POST", "/my/new", cookie=ward, form={
            "summary": "Bed 3 monitor", "impact": "I3", "urgency": "U3"})
        wid = dict(headers)["Location"].rsplit("/", 1)[1]
        conn = db.connect(self.db_path)
        self.assertEqual(conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?", (wid,)).fetchone()[0], "UNROUTED")
        departments.save_grid(conn, {"Ward B": {"MAINT"}}, at=self.at, actor="root")
        conn.commit()
        conn.close()
        # one tick: it goes there, said on the form
        _, _, page = self._call("GET", "/my", cookie=ward)
        self.assertIn("This goes to <b>Maintenance</b>", page)
        _, headers, _ = self._call("POST", "/my/new", cookie=ward, form={
            "summary": "Leaking tap", "impact": "I3", "urgency": "U3"})
        wid = dict(headers)["Location"].rsplit("/", 1)[1]
        conn = db.connect(self.db_path)
        self.assertEqual(conn.execute("SELECT board_id, intake_source FROM ticket WHERE work_item_id = ?",
                                      (wid,)).fetchone()[:], ("MAINT", "PORTAL"))
        departments.save_grid(conn, {"Ward B": {"MAINT", "IT_HELP"}}, at=self.at, actor="root")
        conn.commit()
        conn.close()
        # two ticks: a choice, checked on the server
        _, _, page = self._call("GET", "/my", cookie=ward)
        self.assertIn("Who is this for?", page)
        self.assertIn("IT Help", page)
        status, _, page = self._call("POST", "/my/new", cookie=ward, form={
            "summary": "Which one", "impact": "I3", "urgency": "U3"})
        self.assertTrue(status.startswith("400"))
        self.assertIn("who this is for", page)
        status, _, page = self._call("POST", "/my/new", cookie=ward, form={
            "summary": "Sneaky", "impact": "I3", "urgency": "U3", "board_id": "PHI"})
        self.assertTrue(status.startswith("400"))
        self.assertIn("not one of the places", page)
        _, headers, _ = self._call("POST", "/my/new", cookie=ward, form={
            "summary": "Printer", "impact": "I3", "urgency": "U3", "board_id": "IT_HELP"})
        wid = dict(headers)["Location"].rsplit("/", 1)[1]
        conn = db.connect(self.db_path)
        self.assertEqual(conn.execute("SELECT board_id FROM ticket WHERE work_item_id = ?", (wid,)).fetchone()[0], "IT_HELP")
        conn.close()
        # the Windows door learns the department from the AD contact
        self.config.windows_domain = "PMCNE"
        self.config.windows_logon = lambda d, u, p: (True, 0)
        _, headers, _ = self._call("POST", "/login", form={"door": "windows", "username": "ward.b", "password": "x"})
        cookie = next(v for k, v in headers if k == "Set-Cookie").split(";", 1)[0]
        payload = webauth.read_session(cookie.split("=", 1)[1], self.config.session_secret)
        self.assertEqual(payload["dept"], "Ward B")
        _, _, page = self._call("GET", "/my", cookie=cookie)
        self.assertIn("Who is this for?", page)


class CatalogueSetupTest(unittest.TestCase):
    """036 and psaspine.catalogue: the setup tables for Areas, Subtypes and
    Items, and the Subtype › Item pairs a ticket offers (Setup › Catalogue)."""

    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for

    def setUp(self) -> None:
        WebWSGITest.setUp(self)
        # Cleanups run last-in first-out, after tearDown: registering the folder's
        # removal first means each test's conn.close runs before it (SQL01, part 15:
        # Windows will not remove a folder with an open file).
        self.addCleanup(self.tmp.cleanup)
        self.root = self._cookie_for("root", is_sysadmin=True)
        self.at = datetime(2026, 9, 28, 10)

    def _audits(self, conn):
        return [r["detail"] for r in conn.execute(
            "SELECT detail FROM audit_event WHERE action = 'CATALOGUE_CONFIG' ORDER BY audit_id")]

    def test_add_rename_retire_never_delete_and_every_change_is_audited(self):
        from psaspine import catalogue as cat, setup
        conn = db.connect(self.db_path)
        self.addCleanup(conn.close)                    # Windows will not remove a folder with an open file
        fid = cat.add_area(conn, "  Clinical   apps ", at=self.at, actor="root")
        self.assertEqual(fid, "CLINICAL_APPS")
        with self.assertRaises(cat.Refused):
            cat.add_area(conn, "clinical APPS", at=self.at, actor="root")      # names are unique, any case
        with self.assertRaises(cat.Refused):
            cat.add_area(conn, "   ", at=self.at, actor="root")
        cid = cat.add_subtype(conn, fid, "Label printer", at=self.at, actor="root")
        with self.assertRaises(cat.Refused):
            cat.add_subtype(conn, fid, "label printer", at=self.at, actor="root")
        with self.assertRaises(cat.Refused):
            cat.add_subtype(conn, "NOPE", "x", at=self.at, actor="root")
        aid = cat.add_item(conn, "Relocate", kind="REQUEST", at=self.at, actor="root")
        aid2 = cat.add_item(conn, "Relocate!", kind="FAULT", implies_impact="I3", at=self.at, actor="root")
        self.assertEqual(aid2, "RELOCATE_2")                                   # a fresh id, never a clash
        with self.assertRaises(cat.Refused):
            cat.add_item(conn, "Break", kind="MAYBE", at=self.at, actor="root")
        with self.assertRaises(cat.Refused):
            cat.add_item(conn, "Break", kind="FAULT", implies_impact="I9", at=self.at, actor="root")
        with self.assertRaises(cat.Refused):                                    # baseline needs its scope item
            cat.associate(conn, cid, aid, "IT_HELP", basis="BASELINE", at=self.at, actor="root")
        pair = cat.associate(conn, cid, aid, "IT_HELP", basis="VARIATION", min_priority="P3", at=self.at, actor="root")
        with self.assertRaises(cat.Refused):
            cat.associate(conn, cid, aid, "IT_HELP", at=self.at, actor="root")  # one pair once
        with self.assertRaises(cat.Refused):
            cat.associate(conn, cid, aid2, "NO_BOARD", at=self.at, actor="root")
        labels = [c["label"] for c in setup.catalogue_choices(conn)]
        self.assertIn("Clinical apps › Label printer › Relocate", labels)

        self.assertIn("renamed Label printer -> Labels printer",
                      cat.save_subtype(conn, cid, name="Labels printer", at=self.at, actor="root"))
        self.assertEqual(cat.save_item(conn, aid, kind="FAULT", implies_impact="I1", at=self.at, actor="root"),
                         "kind REQUEST -> FAULT; impact - -> I1")
        self.assertEqual(cat.save_area(conn, fid, name="Clinical apps", at=self.at, actor="root"), "nothing changed")
        cat.save_area(conn, fid, inactive=True, at=self.at, actor="root")
        self.assertEqual(setup.catalogue_choices(conn), [])                   # a retired area leaves the picker
        cat.save_area(conn, fid, inactive=False, at=self.at, actor="root")
        cat.save_item(conn, aid, inactive=True, at=self.at, actor="root")
        self.assertEqual(setup.catalogue_choices(conn), [])                   # so does a retired item
        cat.save_item(conn, aid, inactive=False, at=self.at, actor="root")
        cat.save_subtype(conn, cid, inactive=True, at=self.at, actor="root")
        self.assertEqual(setup.catalogue_choices(conn), [])                   # and a retired subtype
        cat.save_subtype(conn, cid, inactive=False, at=self.at, actor="root")
        self.assertEqual(len(setup.catalogue_choices(conn)), 1)
        # nothing was deleted
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM service_family").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM service_action").fetchone()[0], 2)
        self.assertEqual(conn.execute("SELECT catalogue_item_id FROM catalogue_item").fetchone()[0], pair)
        details = self._audits(conn)
        self.assertEqual(details[:4], ["area added: Clinical apps", "subtype added: Clinical apps › Label printer",
                                       "item added: Relocate (REQUEST)", "item added: Relocate! (FAULT, I3)"])
        self.assertIn("pair added: Clinical apps › Label printer › Relocate -> IT Help, VARIATION", details)
        self.assertEqual(details.count("retired"), 3)
        self.assertEqual(details.count("restored"), 3)
        self.assertNotIn("nothing changed", details)                           # a no-op writes no row

    def test_the_setup_pages_build_a_pair_the_ticket_offers_and_a_retired_pair_stays_on_its_ticket(self):
        from psaspine import tickets
        for tab in ("pairs", "types", "areas", "subtypes", "items"):
            status, _, body = self._call("GET", "/admin/catalogue", cookie=self.root, query=f"tab={tab}")
            self.assertEqual(status, "200 OK", tab)
            self.assertNotIn("ConnectWise", body)
        _, _, body = self._call("GET", "/admin/catalogue", cookie=self.root, query="tab=types")
        self.assertIn("Incident", body)
        self.assertIn("/admin/board/IT_HELP?tab=types", body)                 # the board's own Types tab
        _, h, _ = self._call("POST", "/admin/catalogue/area", cookie=self.root, form={"name": "Clinical apps"})
        self.assertIn("msg=Added+Clinical+apps&tab=areas", dict(h)["Location"])
        _, h, _ = self._call("POST", "/admin/catalogue/area", cookie=self.root, form={"name": "clinical apps"})
        self.assertIn("err=There+is+already+an+area", dict(h)["Location"])
        _, h, _ = self._call("POST", "/admin/catalogue/subtype", cookie=self.root,
                             form={"family_id": "CLINICAL_APPS", "name": "Label printer"})
        self.assertIn("tab=subtypes", dict(h)["Location"])
        _, h, _ = self._call("POST", "/admin/catalogue/item", cookie=self.root,
                             form={"name": "Relocate", "kind": "REQUEST", "implies_impact": ""})
        self.assertIn("tab=items", dict(h)["Location"])
        _, h, _ = self._call("POST", "/admin/catalogue/associate", cookie=self.root,
                             form={"component_id": "LABEL_PRINTER", "action_id": "RELOCATE",
                                   "default_board_id": "IT_HELP", "basis": "BASELINE", "scope_item_id": ""})
        self.assertIn("err=A+baseline+pair+must+name", dict(h)["Location"])
        _, h, _ = self._call("POST", "/admin/catalogue/associate", cookie=self.root,
                             form={"component_id": "LABEL_PRINTER", "action_id": "RELOCATE",
                                   "default_board_id": "IT_HELP", "basis": "UNKNOWN", "min_priority": "P4"})
        self.assertIn("msg=Pair+added", dict(h)["Location"])
        _, _, body = self._call("GET", "/admin/catalogue", cookie=self.root)
        self.assertIn("Label printer</td><td>Relocate</td>", body)
        alice = self._cookie_for("alice")                                      # IT Help's administrator
        _, _, body = self._call("GET", "/ticket/new", cookie=alice)
        self.assertIn("Label printer › Relocate", body)

        conn = db.connect(self.db_path)
        self.addCleanup(conn.close)
        pair = conn.execute("SELECT catalogue_item_id FROM catalogue_item").fetchone()[0]
        wid = tickets.open_ticket(conn, board_id="IT_HELP", summary="move the label printer", impact="I3",
                                  urgency="U3", requested_by=None, at=self.at, catalogue_item_id=pair)
        conn.commit()
        _, h, _ = self._call("POST", "/admin/catalogue/item/save", cookie=self.root,
                             form={"action_id": "RELOCATE", "act": "retire"})
        self.assertIn("msg=Item%3A+retired", dict(h)["Location"])
        _, _, body = self._call("GET", "/ticket/new", cookie=alice)
        self.assertNotIn("Label printer › Relocate", body)                    # not offered to a new ticket
        _, _, body = self._call("GET", f"/ticket/{wid}", cookie=alice)
        self.assertIn(f"<option value='{pair}' selected>Label printer › Relocate (retired)</option>", body)
        _, h, _ = self._call("POST", "/admin/catalogue/subtype/save", cookie=self.root,
                             form={"component_id": "LABEL_PRINTER", "name": "Label printers",
                                   "family_id": "CLINICAL_APPS", "act": "rename"})
        self.assertIn("renamed+Label+printer+-%3E+Label+printers", dict(h)["Location"])
        # a technician cannot reach the setup tables
        tech = self._cookie_for("tech1")
        status, _, _ = self._call("GET", "/admin/catalogue", cookie=tech)
        self.assertNotEqual(status, "200 OK")
        status, _, _ = self._call("POST", "/admin/catalogue/area", cookie=tech, form={"name": "x"})
        self.assertNotEqual(status, "200 OK")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM service_family").fetchone()[0], 1)


class MachineApiTest(unittest.TestCase):
    """The machine API: a local token, JSON, priority computed, repeats collapsed.

    §6.2 is why the credential is local: the monitor that raises "the WAN is
    down" cannot fetch an Entra token while the WAN is down.
    """

    _cookie_for = WebWSGITest._cookie_for

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(_target(self.tmp))
        conn = _fresh(self.tmp)
        conn.execute(
            "INSERT OR REPLACE INTO board_status (board_status_id, board_id, name,"
            " escalation_status, is_closed) VALUES"
            " ('IT_HELP.DONE','IT_HELP','Resolved','RESOLVED',1)")
        self.token_id, self.token = webapi.create_token(
            conn, label="orthanc monitoring", board_id="IT_HELP",
            at=datetime(2026, 9, 22))
        self.other_id, self.other = webapi.create_token(
            conn, label="ups alerts", board_id="IT_HELP", at=datetime(2026, 9, 22))
        conn.commit()
        conn.close()
        self.config = Config(session_secret=_secrets.token_bytes(32))
        self.raw = make_app(self.db_path, config=self.config,
                            clock=lambda: datetime(2026, 9, 22, 10, 0))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _api(self, method, path, *, token=None, payload=None, raw=None,
             ctype="application/json", cookie=None, validate=True):
        body = raw if raw is not None else (
            _json.dumps(payload).encode() if payload is not None else b"")
        path, _, query = path.partition("?")                    # a query on the path, as a client sends it
        env = {
            "REQUEST_METHOD": method, "PATH_INFO": path, "SCRIPT_NAME": "",
            "QUERY_STRING": query, "SERVER_NAME": "t", "SERVER_PORT": "80",
            "SERVER_PROTOCOL": "HTTP/1.1", "wsgi.version": (1, 0),
            "wsgi.url_scheme": "http", "wsgi.input": _io.BytesIO(body),
            "wsgi.errors": _io.StringIO(), "wsgi.multithread": False,
            "wsgi.multiprocess": False, "wsgi.run_once": False}
        if body:
            env["CONTENT_LENGTH"] = str(len(body))
            env["CONTENT_TYPE"] = ctype
        if token:
            env["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        if cookie:
            env["HTTP_COOKIE"] = cookie
        app = _validator(self.raw) if validate else self.raw
        got = {}

        def start_response(status, headers, exc_info=None):
            got["status"], got["headers"] = status, headers
        it = app(env, start_response)
        try:
            text = b"".join(it).decode()
        finally:
            if hasattr(it, "close"):
                it.close()
        try:
            data = _json.loads(text)
        except ValueError:
            data = text
        return got["status"], dict(got["headers"]), data

    def _conn(self):
        return db.connect(self.db_path)

    def test_a_dedup_key_longer_than_its_column_is_refused(self):
        # api_alert's clustered key on SQL Server is capped at 900 bytes; the
        # column is 200 characters and the API says so instead of failing later.
        status, _, data = self._api("POST", "/api/v1/tickets", token=self.token,
                                    payload={"summary": "x", "impact": "I3", "urgency": "U3",
                                             "dedup_key": "k" * 201})
        self.assertTrue(status.startswith("400"), status)
        self.assertIn("200 characters", str(data))

    # ------------------------------------------------------------- the credential

    def test_no_token_is_401_with_a_bearer_challenge(self):
        status, headers, data = self._api("POST", "/api/v1/tickets",
                                          payload={"summary": "x"})
        self.assertTrue(status.startswith("401"))
        self.assertIn("Bearer", headers.get("WWW-Authenticate", ""))

    def test_an_unknown_and_a_disabled_token_are_refused_identically(self):
        """A caller probing for which tokens exist learns nothing from the answer."""
        conn = self._conn()
        conn.execute("UPDATE api_token SET disabled=1 WHERE token_id=?", (self.other_id,))
        conn.commit()
        conn.close()
        s1, _, d1 = self._api("POST", "/api/v1/tickets", token="psa_nope",
                              payload={"summary": "x"})
        s2, _, d2 = self._api("POST", "/api/v1/tickets", token=self.other,
                              payload={"summary": "x"})
        self.assertEqual((s1, d1), (s2, d2))
        self.assertTrue(s1.startswith("401"))

    def test_the_token_is_stored_only_as_a_hash(self):
        conn = self._conn()
        # every value the token table holds, on either store
        dump = "\n".join(str(v) for r in conn.execute("SELECT * FROM api_token").fetchall() for v in r)
        conn.close()
        self.assertNotIn(self.token, dump)
        self.assertIn(_hashlib.sha256(self.token.encode()).hexdigest(), dump)

    def test_every_refusal_is_audited(self):
        self._api("POST", "/api/v1/tickets", token="psa_nope", payload={"summary": "x"})
        conn = self._conn()
        n = conn.execute("SELECT COUNT(*) c FROM audit_event"
                         " WHERE action='API_AUTH_REFUSED'").fetchone()["c"]
        conn.close()
        self.assertEqual(n, 1)

    # -------------------------------------------------------- tokens and cookies

    def test_a_session_cookie_cannot_authorise_an_api_call(self):
        """A cookie on an API is how another site makes a browser raise tickets."""
        cookie = self._cookie_for("alice", is_sysadmin=True)
        status, _, _ = self._api("POST", "/api/v1/tickets", cookie=cookie,
                                 payload={"summary": "x"})
        self.assertTrue(status.startswith("401"))

    def test_a_machine_token_is_not_a_person_on_the_desk(self):
        """One leaked machine credential must not become a user of the UI."""
        status, _, body = self._api("GET", "/", token=self.token)
        self.assertTrue(status.startswith("401"))
        self.assertIn("Break-glass", body)

    # ---------------------------------------------------------------- creating

    def test_a_valid_call_opens_a_numbered_ticket_on_the_tokens_board(self):
        status, _, data = self._api("POST", "/api/v1/tickets", token=self.token,
                                    payload={"summary": "Orthanc not answering",
                                             "impact": "I1", "urgency": "U1"})
        self.assertTrue(status.startswith("201"))
        self.assertTrue(data["id"].startswith("PMC-"))
        conn = self._conn()
        row = conn.execute("SELECT board_id, requested_by FROM ticket WHERE work_item_id=?",
                           (data["id"],)).fetchone()
        conn.close()
        self.assertEqual(row["board_id"], "IT_HELP")
        self.assertEqual(row["requested_by"], f"api:{self.token_id}")

    def test_priority_is_computed_from_impact_and_urgency(self):
        _, _, data = self._api("POST", "/api/v1/tickets", token=self.token,
                               payload={"summary": "x", "impact": "I1", "urgency": "U1"})
        self.assertEqual(data["priority"], "P1")
        self.assertEqual(data["priority_source"], "MATRIX")

    def test_a_caller_cannot_assert_a_priority(self):
        status, _, data = self._api("POST", "/api/v1/tickets", token=self.token,
                                    payload={"summary": "x", "priority": "P1"})
        self.assertTrue(status.startswith("422"))
        self.assertEqual(data["field"], "priority")
        self.assertIn("computed", data["error"])

    def test_bad_input_is_refused_with_the_field_named(self):
        for payload, field in (({"summary": ""}, "summary"),
                               ({"summary": "x", "impact": "I9"}, "impact"),
                               ({"summary": "x", "urgency": "U0"}, "urgency"),
                               ({"summary": "y" * 201}, "summary")):
            status, _, data = self._api("POST", "/api/v1/tickets", token=self.token,
                                        payload=payload)
            self.assertTrue(status.startswith("422"), payload)
            self.assertEqual(data["field"], field)

    def test_not_json_is_refused(self):
        s1, _, _ = self._api("POST", "/api/v1/tickets", token=self.token,
                             raw=b"summary=x", ctype="application/x-www-form-urlencoded")
        s2, _, _ = self._api("POST", "/api/v1/tickets", token=self.token, raw=b"{not json")
        self.assertTrue(s1.startswith("415"))
        self.assertTrue(s2.startswith("400"))

    # --------------------------------------------------------- repeats collapse

    def test_a_repeat_firing_while_open_is_a_count_not_a_ticket(self):
        first = self._api("POST", "/api/v1/tickets", token=self.token,
                          payload={"summary": "Orthanc down", "dedup_key": "orthanc-down"})
        again = self._api("POST", "/api/v1/tickets", token=self.token,
                          payload={"summary": "Orthanc down", "dedup_key": "orthanc-down"})
        self.assertTrue(first[0].startswith("201"))
        self.assertTrue(again[0].startswith("200"))
        self.assertEqual(again[2]["id"], first[2]["id"])
        self.assertTrue(again[2]["duplicate"])
        self.assertEqual(again[2]["times"], 2)
        conn = self._conn()
        n = conn.execute("SELECT COUNT(*) c FROM ticket").fetchone()["c"]
        conn.close()
        self.assertEqual(n, 1)

    def test_a_fault_that_returns_after_being_fixed_is_a_new_ticket(self):
        """Folding it into the closed ticket hides the recurrence."""
        _, _, first = self._api("POST", "/api/v1/tickets", token=self.token,
                                payload={"summary": "UPS on battery",
                                         "dedup_key": "ups"})
        conn = self._conn()
        board.change_status(conn, first["id"], "IT_HELP.DONE",
                            at=datetime(2026, 9, 22, 10, 30), actor="Cadano")
        conn.commit()
        conn.close()
        status, _, second = self._api("POST", "/api/v1/tickets", token=self.token,
                                      payload={"summary": "UPS on battery",
                                               "dedup_key": "ups"})
        self.assertTrue(status.startswith("201"))
        self.assertNotEqual(second["id"], first["id"])

    # ----------------------------------------------------------------- reading

    def test_a_token_reads_the_tickets_it_raised(self):
        _, _, made = self._api("POST", "/api/v1/tickets", token=self.token,
                               payload={"summary": "x"})
        status, _, data = self._api("GET", f"/api/v1/tickets/{made['id']}",
                                    token=self.token)
        self.assertTrue(status.startswith("200"))
        self.assertTrue(data["open"])

    def test_a_token_cannot_read_a_ticket_another_token_raised(self):
        _, _, made = self._api("POST", "/api/v1/tickets", token=self.token,
                               payload={"summary": "x"})
        status, _, _ = self._api("GET", f"/api/v1/tickets/{made['id']}",
                                 token=self.other)
        self.assertTrue(status.startswith("404"))

    # --------------------------------------------------------------------- PHI

    def test_phi_is_flagged_and_the_value_never_repeated(self):
        status, _, _ = self._api(
            "POST", "/api/v1/tickets", token=self.token,
            payload={"summary": "Charge date", "description": "PhilHealth 12-345678901-2"})
        self.assertTrue(status.startswith("201"))
        conn = self._conn()
        rows = conn.execute("SELECT detail FROM data_quality WHERE code LIKE 'PHI_%'").fetchall()
        conn.close()
        self.assertTrue(rows)
        for r in rows:
            self.assertNotIn("345678901", r["detail"])


@unittest.skipUnless(ON_SQLITE, "SQLite's file settings; SQL Server has its own")
class SeedIdempotenceTest(unittest.TestCase):
    """SQL01, part 14: `init` after a Setup change leaves the seeded boards as
    Setup left them. On SQL Server a replace-seed was an UPDATE that put every
    unlisted column back to its DEFAULT, so Unrouted lost its calendar."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 28, 10, 40)

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_init_never_overwrites_a_seeded_board(self):
        from psaspine import setup
        setup.apply_starter(self.conn, "UNROUTED", actor="root", at=self.at)
        self.conn.execute("UPDATE board SET display_name = 'Help Desk (renamed)', kind = 'SERVICE',"
                          " notify_owner = 1 WHERE board_id = 'IT_HELP'")
        self.conn.commit()
        before = {r["board_id"]: tuple(r) for r in self.conn.execute(
            "SELECT board_id, display_name, calendar_id, kind, notify_owner, owner, deputy, is_live"
            " FROM board ORDER BY board_id")}
        self.assertEqual(before["UNROUTED"][2], "ALL_HOURS")
        self.conn.close()
        if TEST_DB:
            self.conn = db.init(TEST_DB)                    # the host's `init`, on a database that exists
        else:
            # SQLite's create() is not re-runnable (plain scripts), so a second
            # `init` there is the seed alone, which is all the host's run adds.
            self.conn = db.connect(Path(self.tmp.name) / "spine.db")
            db.seed(self.conn)
        after = {r["board_id"]: tuple(r) for r in self.conn.execute(
            "SELECT board_id, display_name, calendar_id, kind, notify_owner, owner, deputy, is_live"
            " FROM board ORDER BY board_id")}
        self.assertEqual(after, before)
        self.assertEqual(after["IT_HELP"][1], "Help Desk (renamed)")

    def test_a_fresh_install_names_the_first_board_as_pmc_runs_it(self):
        name = self.conn.execute("SELECT display_name FROM board WHERE board_id = 'IT_HELP'").fetchone()[0]
        self.assertEqual(name, "PMO Helpdesk")                             # Dada's own name (part 15); the id stays IT_HELP


class CalendarSetupTest(unittest.TestCase):
    """037 and psaspine.calendars: the Calendar and Holiday List setup tables in
    the reference PSA's shape, and the clocks honouring what they say."""

    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for

    def setUp(self) -> None:
        WebWSGITest.setUp(self)
        self.addCleanup(self.tmp.cleanup)
        self.root = self._cookie_for("root", is_sysadmin=True)
        self.at = datetime(2026, 9, 28, 14)

    def _conn(self):
        conn = db.connect(self.db_path)
        self.addCleanup(conn.close)
        return conn

    def test_a_part_day_holiday_closes_only_its_hours(self):
        from psaspine import clocks
        mon_fri = {i: (480, 1020) for i in range(5)}                      # 08:00-17:00
        eve = date(2026, 12, 24)                                           # a Thursday
        cal = clocks.Calendar(mon_fri, set(), closures={eve: [(720, 1440)]})   # closed from noon
        self.assertEqual(cal.working_minutes(datetime(2026, 12, 24, 8), datetime(2026, 12, 24, 17)), 240)
        self.assertEqual(cal.working_minutes(datetime(2026, 12, 24, 13), datetime(2026, 12, 24, 16)), 0)
        # a span crossing it whole: Wed 08:00 to Fri 17:00 is 9 + 4 + 9 hours
        self.assertEqual(cal.working_minutes(datetime(2026, 12, 23, 8), datetime(2026, 12, 25, 17)), 22 * 60)
        # whole days still win: the same date as an all-day holiday is 18 hours
        full = clocks.Calendar(mon_fri, {eve})
        self.assertEqual(full.working_minutes(datetime(2026, 12, 23, 8), datetime(2026, 12, 25, 17)), 18 * 60)

    def test_add_edit_retire_and_every_change_is_audited(self):
        from psaspine import calendars as cal, clocks
        conn = self._conn()
        lid = cal.add_holiday_list(conn, "Philippine public holidays", at=self.at, actor="root")
        cal.add_holiday(conn, lid, "2026-11-30", "Bonifacio Day", at=self.at, actor="root")
        cal.add_holiday(conn, lid, "2026-12-24", "Christmas Eve", all_day=False, time_start="12:00",
                        time_end="24:00", at=self.at, actor="root")
        with self.assertRaises(cal.Refused):
            cal.add_holiday(conn, lid, "2026-11-30", "Again", at=self.at, actor="root")      # one date once
        with self.assertRaises(cal.Refused):
            cal.add_holiday(conn, lid, "30/11/2026", "Bad", at=self.at, actor="root")
        with self.assertRaises(cal.Refused):
            cal.add_holiday(conn, lid, "2026-12-31", "Eve", all_day=False, time_start="17:00",
                            time_end="12:00", at=self.at, actor="root")
        week = cal.clean_week({"monday_start": "8:00", "monday_end": "17:00", "tuesday_start": "08:00",
                               "tuesday_end": "17:00"})
        self.assertEqual(week["monday"], ("08:00", "17:00"))
        self.assertEqual(week["sunday"], (None, None))
        for bad in ({"monday_start": "08:00"}, {"monday_start": "17:00", "monday_end": "08:00"},
                    {"monday_start": "25:00", "monday_end": "26:00"}):
            with self.assertRaises(cal.Refused):
                cal.clean_week(bad)
        cid = cal.add_calendar(conn, "Pharmacy counter", week, holiday_list_id=lid, at=self.at, actor="root")
        with self.assertRaises(cal.Refused):
            cal.add_calendar(conn, "pharmacy COUNTER", week, at=self.at, actor="root")
        with self.assertRaises(cal.Refused):
            cal.add_calendar(conn, "Never open", cal.clean_week({}), at=self.at, actor="root")
        loaded = clocks.Calendar.load(conn, cid)
        self.assertIn(date(2026, 11, 30), loaded.holidays)
        self.assertEqual(loaded.closures[date(2026, 12, 24)], [(720, 1440)])
        what = cal.save_calendar(conn, cid, week=cal.clean_week(
            {"monday_start": "07:00", "monday_end": "17:00", "tuesday_start": "08:00", "tuesday_end": "17:00"}),
            at=self.at, actor="root")
        self.assertEqual(what, "hours: Mon 08:00-17:00 -> 07:00-17:00")
        self.assertEqual(cal.save_calendar(conn, cid, name="Pharmacy counter", at=self.at, actor="root"),
                         "nothing changed")
        cal.save_calendar(conn, cid, inactive=True, at=self.at, actor="root")
        self.assertNotIn(cid, [c["calendar_id"] for c in cal.live_calendars(conn)])
        self.assertIn(cid, [c["calendar_id"] for c in cal.live_calendars(conn, keep=cid)])   # kept where chosen
        cal.remove_holiday(conn, lid, "2026-11-30", at=self.at, actor="root")
        self.assertNotIn(date(2026, 11, 30), clocks.Calendar.load(conn, cid).holidays)
        details = [r[0] for r in conn.execute("SELECT detail FROM audit_event WHERE action = 'CALENDAR_CONFIG'"
                                              " ORDER BY audit_id")]
        self.assertEqual(details[0], "holiday list added: Philippine public holidays")
        self.assertIn("holiday added: 2026-12-24 Christmas Eve (closed 12:00-24:00)", details)
        self.assertIn("retired", details)
        self.assertIn("holiday removed: 2026-11-30 Bonifacio Day; the clocks on this list recompute", details)
        self.assertNotIn("nothing changed", details)

    def test_the_holiday_csv_loads_a_year_and_a_rerun_adds_nothing(self):
        from psaspine import calendars as cal
        conn = self._conn()
        lid = cal.add_holiday_list(conn, "PH 2026", at=self.at, actor="root")
        path = Path(self.tmp.name) / "holidays.csv"
        path.write_text("\ufeffDate,Name,AllDay,Start,End\r\n2026-12-25,Christmas Day,,,\r\n"
                        "2026-12-31,New Year's Eve,no,12:00,24:00\r\n", encoding="utf-8")
        self.assertEqual(cal.import_csv(conn, lid, path, at=self.at), {"rows": 2, "new": 2, "seen": 0})
        self.assertEqual(cal.import_csv(conn, lid, path, at=self.at), {"rows": 2, "new": 0, "seen": 2})
        eve = [h for h in cal.holidays(conn, lid) if h["observed_on"] == "2026-12-31"][0]
        self.assertEqual((eve["all_day"], eve["time_start"], eve["time_end"]), (0, "12:00", "24:00"))

    def test_the_setup_page_adds_a_calendar_a_list_and_a_date_and_the_board_tab_offers_it(self):
        for tab in ("calendars", "holidays"):
            status, _, body = self._call("GET", "/admin/calendars", cookie=self.root, query=f"tab={tab}")
            self.assertEqual(status, "200 OK", tab)
        _, h, _ = self._call("POST", "/admin/calendars/holiday-list", cookie=self.root,
                             form={"name": "Philippine public holidays"})
        self.assertIn("tab=holidays", dict(h)["Location"])
        _, h, _ = self._call("POST", "/admin/calendars/holiday", cookie=self.root, form={
            "holiday_list_id": "PHILIPPINE_PUBLIC_HOLIDAYS", "observed_on": "2026-11-30", "name": "Bonifacio Day",
            "all_day": "1"})
        self.assertIn("msg=Added+2026-11-30", dict(h)["Location"])
        form = {"name": "Ward 3 roster", "holiday_list_id": "PHILIPPINE_PUBLIC_HOLIDAYS"}
        form.update({f"{d}_start": "06:00" for d in ("monday", "tuesday", "wednesday", "thursday", "friday",
                                                     "saturday", "sunday")})
        form.update({f"{d}_end": "22:00" for d in ("monday", "tuesday", "wednesday", "thursday", "friday",
                                                   "saturday", "sunday")})
        _, h, _ = self._call("POST", "/admin/calendars", cookie=self.root, form=form)
        self.assertIn("msg=Added+Ward+3+roster", dict(h)["Location"])
        _, h, _ = self._call("POST", "/admin/calendars", cookie=self.root, form=form | {"monday_end": ""})
        self.assertIn("err=Monday", dict(h)["Location"])
        _, _, body = self._call("GET", "/admin/calendars", cookie=self.root)
        self.assertIn("value='Ward 3 roster'", body)
        _, _, body = self._call("GET", "/admin/calendars", cookie=self.root, query="tab=holidays")
        self.assertIn("Bonifacio Day", body)
        alice = self._cookie_for("alice")                                    # the board's administrator
        _, _, page = self._call("GET", "/admin/board/IT_HELP", cookie=alice, query="tab=board")
        self.assertIn(">Ward 3 roster</option>", page)
        self._call("POST", "/admin/calendars/save", cookie=self.root, form={"calendar_id": "WARD_3_ROSTER",
                                                                             "act": "retire"})
        _, _, page = self._call("GET", "/admin/board/IT_HELP", cookie=alice, query="tab=board")
        self.assertNotIn(">Ward 3 roster</option>", page)                   # retired: not offered
        tech = self._cookie_for("tech1")
        status, _, _ = self._call("GET", "/admin/calendars", cookie=tech)
        self.assertNotEqual(status, "200 OK")


class SchedulingTest(unittest.TestCase):
    """038 and psaspine.schedule: visits with a status, a where, a lead, done
    and acknowledged; conflicts refused unless allowed; time off never
    double-booked; the week Schedule and Setup › Schedule."""

    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for

    def setUp(self) -> None:
        WebWSGITest.setUp(self)
        self.addCleanup(self.tmp.cleanup)
        conn = db.connect(self.db_path)
        conn.executescript(
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','bob','WORK');"
            "INSERT INTO work_item (work_item_id,source,name,entity_id,contract_basis)"
            " VALUES ('ITO-2','desk','Label printer','PMC','BASELINE');"
            "INSERT INTO ticket (work_item_id,board_id,path,impact,urgency,priority,priority_source,"
            " requested_at,opened_at,state,board_status_id) VALUES ('ITO-2','IT_HELP','INCIDENT','I3',"
            "'U3','P4','MATRIX','2026-09-17 08:00','2026-09-17 08:00','NEW','IT_HELP.NEW');")
        conn.commit()
        conn.close()
        self.at = datetime(2026, 9, 28, 9)

    def _conn(self):
        conn = db.connect(self.db_path)
        self.addCleanup(conn.close)
        return conn

    def test_visits_statuses_lead_done_ack_and_conflicts(self):
        from psaspine import schedule
        conn = self._conn()
        d = lambda h, m=0: datetime(2026, 9, 29, h, m)
        v1 = schedule.add(conn, "ITO-1", member="bob", starts_at=d(10), ends_at=d(11), note="Ward 3",
                          actor="alice", at=self.at, location_id="ON_SITE")
        row = conn.execute("SELECT * FROM ticket_schedule WHERE schedule_id = ?", (v1,)).fetchone()
        self.assertEqual((row["status_id"], row["location_id"], row["is_lead"]), ("FIRM", "ON_SITE", 1))  # first is lead
        with self.assertRaises(schedule.Refused) as refused:                                 # bob is busy
            schedule.add(conn, "ITO-2", member="Bob", starts_at=d(10, 30), ends_at=d(11, 30), note=None,
                         actor="alice", at=self.at)
        self.assertIn("allow a double booking", str(refused.exception))
        v2 = schedule.add(conn, "ITO-2", member="bob", starts_at=d(10, 30), ends_at=d(11, 30), note=None,
                          actor="alice", at=self.at, status_id="TENTATIVE", allow_conflict=True)
        self.assertEqual(conn.execute("SELECT conflict_allowed FROM ticket_schedule WHERE schedule_id = ?",
                                      (v2,)).fetchone()[0], 1)
        v3 = schedule.add(conn, "ITO-1", member="alice", starts_at=d(10), ends_at=d(11), note=None,
                          actor="alice", at=self.at, is_lead=True)
        leads = [r["member"] for r in schedule.entries_for(conn, "ITO-1") if r["is_lead"]]
        self.assertEqual(leads, ["alice"])                                                   # one lead a ticket
        schedule.make_lead(conn, v1, actor="alice", at=self.at)
        self.assertEqual([r["member"] for r in schedule.entries_for(conn, "ITO-1") if r["is_lead"]], ["bob"])
        with self.assertRaises(schedule.Refused):
            schedule.acknowledge(conn, v1, member="alice", at=self.at)                     # only bob can
        schedule.acknowledge(conn, v1, member="BOB", at=self.at)
        what = schedule.update(conn, v1, actor="alice", at=self.at, starts_at=d(14), ends_at=d(15))
        self.assertIn("moved bob, 2026-09-29 10:00 to 11:00 -> bob, 2026-09-29 14:00 to 15:00", what)
        self.assertIsNone(conn.execute("SELECT acknowledged_at FROM ticket_schedule WHERE schedule_id = ?",
                                       (v1,)).fetchone()[0])                              # a move asks again
        self.assertEqual(schedule.update(conn, v1, actor="alice", at=self.at), "nothing changed")
        schedule.set_done(conn, v1, True, actor="bob", at=self.at)
        with self.assertRaises(schedule.Refused):
            schedule.update(conn, v1, actor="alice", at=self.at, starts_at=d(16), ends_at=d(17))
        schedule.set_done(conn, v1, False, actor="bob", at=self.at)
        events = [r[0] for r in conn.execute("SELECT detail FROM ticket_event WHERE work_item_id = 'ITO-1'"
                                             " AND kind = 'SCHEDULE' ORDER BY ticket_event_id")]
        self.assertTrue(events[0].startswith("visit scheduled: bob, 2026-09-29 10:00 to 11:00 (firm), lead"))
        self.assertIn("visit acknowledged: bob, 2026-09-29 10:00 to 11:00", events)
        self.assertIn("visit done: bob, 2026-09-29 14:00 to 15:00", events)
        self.assertIn("visit reopened: bob, 2026-09-29 14:00 to 15:00", events)
        del v3

    def test_time_off_is_never_double_booked_and_a_meeting_can_be(self):
        from psaspine import schedule
        conn = self._conn()
        schedule.add_block(conn, member="bob", kind="TIME_OFF", name="Annual leave",
                           starts_at=datetime(2026, 9, 30, 0), ends_at=datetime(2026, 10, 2, 0), actor="bob", at=self.at)
        for allow in (False, True):
            with self.assertRaises(schedule.Refused) as refused:
                schedule.add(conn, "ITO-1", member="bob", starts_at=datetime(2026, 10, 1, 9),
                             ends_at=datetime(2026, 10, 1, 10), note=None, actor="alice", at=self.at,
                             allow_conflict=allow)
            self.assertIn("time off is never double-booked", str(refused.exception))
        schedule.add_block(conn, member="alice", kind="MEETING", name="Vendor meeting",
                           starts_at=datetime(2026, 10, 1, 9), ends_at=datetime(2026, 10, 1, 10), actor="alice", at=self.at)
        with self.assertRaises(schedule.Refused):
            schedule.add(conn, "ITO-1", member="alice", starts_at=datetime(2026, 10, 1, 9, 30),
                         ends_at=datetime(2026, 10, 1, 10, 30), note=None, actor="alice", at=self.at)
        schedule.add(conn, "ITO-1", member="alice", starts_at=datetime(2026, 10, 1, 9, 30),
                     ends_at=datetime(2026, 10, 1, 10, 30), note=None, actor="alice", at=self.at, allow_conflict=True)
        with self.assertRaises(schedule.Refused):                  # time off over a booked visit needs the tick
            schedule.add_block(conn, member="alice", kind="TIME_OFF", name="Sick",
                               starts_at=datetime(2026, 10, 1, 0), ends_at=datetime(2026, 10, 2, 0), actor="alice", at=self.at)
        wk = schedule.week(conn, ["IT_HELP"], date(2026, 9, 28))
        self.assertEqual(len(wk["blocks"]), 2)
        self.assertIn("bob", wk["members"])
        audits = [r[0] for r in conn.execute("SELECT detail FROM audit_event WHERE action = 'SCHEDULE_BLOCK'")]
        self.assertEqual(audits[0], "time off added: bob, 2026-09-30 00:00 to 2026-10-02 00:00, Annual leave")

    def test_the_booked_member_is_emailed_when_the_board_says_so(self):
        from psaspine import schedule
        conn = self._conn()
        conn.execute("UPDATE board SET notify_owner = 1 WHERE board_id = 'IT_HELP'")
        for who in ("bob", "alice"):
            conn.execute("INSERT INTO contact (contact_id, entity_id, display_name, email, sam_account, source,"
                         " inactive, created_at) VALUES (?, 'PMC', ?, ?, ?, 'AD', 0, '2026-09-17 08:00')",
                         (f"C_{who}", who, f"{who}@pmcne.ph", who))
        schedule.add(conn, "ITO-1", member="bob", starts_at=datetime(2026, 9, 29, 10), ends_at=datetime(2026, 9, 29, 11),
                     note=None, actor="alice", at=self.at)
        schedule.add(conn, "ITO-2", member="alice", starts_at=datetime(2026, 9, 29, 12), ends_at=datetime(2026, 9, 29, 13),
                     note=None, actor="alice", at=self.at)                                   # booked herself: none
        mails = [(r["recipient"], r["subject"]) for r in conn.execute(
            "SELECT recipient, subject FROM notification WHERE recipient_role = 'SCHEDULED'")]
        self.assertEqual(mails, [("bob", "[ITO-1] Scheduled for you on IT Help")])     # none to alice; no summary
        conn.execute("UPDATE board SET notify_owner = 0 WHERE board_id = 'IT_HELP'")
        schedule.add(conn, "ITO-2", member="bob", starts_at=datetime(2026, 9, 29, 14), ends_at=datetime(2026, 9, 29, 15),
                     note=None, actor="alice", at=self.at)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM notification WHERE recipient_role = 'SCHEDULED'").fetchone()[0], 1)

    def test_the_week_page_books_blocks_and_setup_edits_the_vocabulary(self):
        alice, root = self._cookie_for("alice"), self._cookie_for("root", is_sysadmin=True)
        _, h, _ = self._call("POST", "/schedule/book", cookie=alice, form={
            "work_item_id": "ito-2", "member": "bob", "starts_at": "2026-09-29T10:00", "ends_at": "2026-09-29T11:00",
            "status_id": "TENTATIVE", "location_id": "REMOTE", "week": "2026-09-28"})
        self.assertIn("msg=Booked+ITO-2+for+bob", dict(h)["Location"])
        _, h, _ = self._call("POST", "/schedule/block", cookie=alice, form={
            "member": "bob", "kind": "TIME_OFF", "name": "Annual leave", "starts_at": "2026-09-30T00:00",
            "ends_at": "2026-10-01T00:00", "week": "2026-09-28"})
        self.assertIn("msg=Added", dict(h)["Location"])
        _, h, _ = self._call("POST", "/schedule/book", cookie=alice, form={
            "work_item_id": "ITO-1", "member": "bob", "starts_at": "2026-09-30T10:00", "ends_at": "2026-09-30T11:00"})
        self.assertIn("never+double-booked", dict(h)["Location"])
        carol = self._cookie_for("carol")                                                # reads IT Help, works nothing
        _, h, _ = self._call("POST", "/schedule/book", cookie=carol, form={
            "work_item_id": "ITO-2", "member": "bob", "starts_at": "2026-09-29T12:00", "ends_at": "2026-09-29T13:00"})
        self.assertIn("err=You+do+not+work", dict(h)["Location"])
        status, _, _ = self._call("POST", "/schedule/block", cookie=carol, form={
            "member": "carol", "kind": "MEETING", "name": "x", "starts_at": "2026-09-29T12:00", "ends_at": "2026-09-29T13:00"})
        self.assertTrue(status.startswith("403"), status)
        _, _, page = self._call("GET", "/schedule", cookie=carol, query="week=2026-09-28")
        self.assertNotIn("Book a visit", page)                                            # a reader sees, cannot book
        status, _, page = self._call("GET", "/schedule", cookie=alice, query="week=2026-09-28")
        self.assertEqual(status, "200 OK")
        self.assertIn("class='sch visit tentative'", page)
        self.assertIn("10:00–11:00</b> ITO-2", page)
        self.assertIn("Remote", page)
        self.assertIn("<b>Time off</b> all day<br>Annual leave", page)
        self.assertIn("Mon 28 Sep", page)
        _, _, page = self._call("GET", "/dispatch", cookie=alice, query="day=2026-09-30")
        self.assertIn("Time off: Annual leave", page)
        _, _, ticket = self._call("GET", "/ticket/ITO-2", cookie=alice)
        self.assertIn("Tentative", ticket)
        self.assertIn("Move or change", ticket)
        # Setup › Schedule: a sysadmin only
        status, _, _ = self._call("GET", "/admin/schedule", cookie=alice)
        self.assertNotEqual(status, "200 OK")
        _, h, _ = self._call("POST", "/admin/schedule/add", cookie=root, form={"kind": "status", "name": "Waiting on parts"})
        self.assertIn("msg=Added+Waiting+on+parts", dict(h)["Location"])
        _, h, _ = self._call("POST", "/admin/schedule/save", cookie=root, form={"kind": "status", "key": "FIRM", "act": "retire"})
        self.assertIn("err=Not+saved%3A+the+default+status", dict(h)["Location"])
        _, h, _ = self._call("POST", "/admin/schedule/save", cookie=root, form={"kind": "status", "key": "WAITING_ON_PARTS", "act": "default"})
        self.assertIn("made+the+default", dict(h)["Location"])
        _, h, _ = self._call("POST", "/admin/schedule/save", cookie=root, form={"kind": "location", "key": "IN_HOUSE", "name": "Brought to IT", "act": "rename"})
        self.assertIn("renamed", dict(h)["Location"])
        _, _, page = self._call("GET", "/admin/schedule", cookie=root)
        self.assertIn("value='Brought to IT'", page)
        conn = self._conn()
        self.assertEqual(conn.execute("SELECT status_id FROM schedule_status WHERE is_default = 1").fetchone()[0],
                         "WAITING_ON_PARTS")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'SCHEDULE_CONFIG'").fetchone()[0], 3)


class ModulesTest(unittest.TestCase):
    """039-043: the knowledge base, security roles, projects, the report writer
    and the read-only BizBox mirror with its change log."""

    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for

    def setUp(self) -> None:
        WebWSGITest.setUp(self)
        self.addCleanup(self.tmp.cleanup)
        self.at = datetime(2026, 9, 29, 10)
        self.alice = self._cookie_for("alice")
        self.root = self._cookie_for("root", is_sysadmin=True)

    def _conn(self):
        conn = db.connect(self.db_path)
        self.addCleanup(conn.close)
        return conn

    # ------------------------------------------------------------ roles

    def test_roles_gate_the_modules_and_never_open_a_board(self):
        from psaspine import security
        from psaspine.web import auth as webauth
        conn = self._conn()
        alice = webauth.User(id="alice", name="alice")
        self.assertEqual(security.level(conn, alice, "KNOWLEDGE"), "WRITE")        # the default role, Technician
        self.assertEqual(security.level(conn, webauth.User(id="root", name="root", is_sysadmin=True), "FINANCE"), "ADMIN")
        req = webauth.User(id="nurse", name="nurse")
        req.requester = True
        self.assertEqual(security.level(conn, req, "KNOWLEDGE"), "NONE")
        security.assign(conn, "alice", "READ_ONLY", at=self.at, actor="root")
        self.assertEqual(security.level(conn, alice, "FINANCE"), "NONE")
        with self.assertRaises(security.Refused):
            security.set_inactive(conn, "TECHNICIAN", True, at=self.at, actor="root")   # the default stays
        self.assertEqual(security.save_grants(conn, "READ_ONLY", {"FINANCE": "READ"}, at=self.at, actor="root"),
                         "Finance (BizBox) NONE -> READ")
        conn.commit()
        status, _, _ = self._call("GET", "/kb/new", cookie=self.alice)                   # READ only: no writing
        self.assertTrue(status.startswith("403"), status)
        _, _, page = self._call("GET", "/finance", cookie=self.alice)
        self.assertIn("<h1>Finance</h1>", page)
        _, h, _ = self._call("POST", "/admin/roles/assign", cookie=self.root, form={"member": "alice", "role_id": ""})
        self.assertIn("alice%3A+READ_ONLY+-%3E+default", dict(h)["Location"])
        status, _, _ = self._call("GET", "/admin/roles", cookie=self.root)
        self.assertEqual(status, "200 OK")
        status, _, _ = self._call("GET", "/admin/roles", cookie=self.alice)
        self.assertTrue(status.startswith("403"))
        self.assertEqual(self._conn().execute("SELECT COUNT(*) FROM audit_event WHERE action = 'SECURITY_ROLE'").fetchone()[0], 3)
        conn = self._conn()
        self.assertEqual(security.levels(conn, alice), {m: security.level(conn, alice, m) for m in security.MODULES})
        security.assign(conn, "alice", "READ_ONLY", at=self.at, actor="root")                 # SCHEDULE READ: may look, not book
        conn.commit()
        status, _, _ = self._call("GET", "/schedule", cookie=self.alice)
        self.assertEqual(status, "200 OK")
        status, _, _ = self._call("POST", "/schedule/block", cookie=self.alice, form={"week": "2026-09-14"})
        self.assertTrue(status.startswith("403"), status)
        rid = security.add_role(conn, "No calendar", at=self.at, actor="root")
        security.save_grants(conn, rid, {"SCHEDULE": "NONE"}, at=self.at, actor="root")
        security.assign(conn, "alice", rid, at=self.at, actor="root")
        conn.commit()
        status, _, _ = self._call("GET", "/schedule", cookie=self.alice)                      # SCHEDULE NONE: the page is gone too
        self.assertTrue(status.startswith("403"), status)

    # --------------------------------------------------------- knowledge

    def test_knowledge_writes_publishes_suggests_links_and_reaches_the_portal(self):
        from psaspine import knowledge
        conn = self._conn()
        conn.execute("UPDATE work_item SET name = 'Label printer prints blank labels' WHERE work_item_id = 'ITO-1'")
        aid = knowledge.create(conn, title="Label printer prints blank labels", body="1. Check the ribbon.\n2. Recalibrate.",
                               audience="REQUESTER", at=self.at, actor="alice")
        self.assertEqual(aid, "KB-0001")
        with self.assertRaises(knowledge.Refused):
            knowledge.create(conn, title="", body="x", at=self.at, actor="alice")
        self.assertEqual(knowledge.save(conn, aid, title="Label printer prints blank labels", body="1. Check the ribbon.\n2. Recalibrate.",
                                        audience="REQUESTER", board_id=None, catalogue_item_id=None, at=self.at, actor="alice"),
                         "nothing changed")
        knowledge.save(conn, aid, title="Label printer prints blank labels", body="1. Check the ribbon.\n2. Recalibrate.\n3. Test print.",
                       audience="REQUESTER", board_id=None, catalogue_item_id=None, at=self.at, actor="alice")
        self.assertEqual([r["version"] for r in knowledge.revisions(conn, aid)], [2, 1])
        self.assertEqual(knowledge.suggest(conn, "ITO-1", board_ids={"IT_HELP"}), [])     # drafts are not suggested
        knowledge.set_status(conn, aid, "PUBLISHED", at=self.at, actor="alice")
        self.assertEqual([a["article_id"] for a in knowledge.suggest(conn, "ITO-1", board_ids={"IT_HELP"})], [aid])
        secret = knowledge.create(conn, title="PHI board runbook", body="steps", board_id="PHI", at=self.at, actor="alice")
        knowledge.create(conn, title="Flagged", body="Patient: Juan, PhilHealth 12-345678901-2", at=self.at, actor="alice")
        self.assertTrue(knowledge.flags(conn, "KB-0003"))                                  # flagged, not refused
        conn.commit()
        _, h, _ = self._call("POST", "/ticket/ITO-1/kb", cookie=self.alice, form={"article_id": aid.lower()})
        self.assertIn("linked", dict(h)["Location"])
        self.assertEqual(self._conn().execute("SELECT uses FROM kb_article WHERE article_id = ?", (aid,)).fetchone()[0], 1)
        _, _, ticket = self._call("GET", "/ticket/ITO-1", cookie=self.alice)
        self.assertIn("data-pod=knowledge", ticket)
        self.assertIn(f"✓ <a href='/kb/{aid}'>", ticket)
        carol = self._cookie_for("carol")                                                  # not on the PHI board
        status, _, _ = self._call("GET", f"/kb/{secret}", cookie=carol)
        self.assertTrue(status.startswith("404"))
        _, _, page = self._call("GET", "/kb", cookie=carol)
        self.assertNotIn("PHI board runbook", page)
        nurse = self._cookie_for("nurse")                                                   # a requester
        _, _, help_page = self._call("GET", "/my/help", cookie=nurse)
        self.assertIn("Label printer prints blank labels", help_page)
        self.assertNotIn("PHI board runbook", help_page)
        status, _, _ = self._call("GET", "/my/help/KB-0003", cookie=nurse)                  # a draft, internal
        self.assertTrue(status.startswith("404"))
        status, _, _ = self._call("GET", "/kb", cookie=nurse)
        self.assertTrue(status.startswith("403"))
        self.assertIn("href=\"/my/help\"", help_page)                                          # the portal's own nav reaches it
        conn = self._conn()
        ward = knowledge.create(conn, title="Ward 5 label printer", body="steps", board_id="PHI", audience="REQUESTER",
                                at=self.at, actor="alice")
        knowledge.set_status(conn, ward, "PUBLISHED", at=self.at, actor="alice")
        conn.commit()
        for who in (nurse, carol, self.root):                                                # a board's article is its members' only
            status, _, _ = self._call("GET", f"/my/help/{ward}", cookie=who)
            self.assertTrue(status.startswith("404"), status)
        _, _, help_page = self._call("GET", "/my/help", cookie=nurse)
        self.assertNotIn("Ward 5 label printer", help_page)

    # ---------------------------------------------------------- projects

    def test_projects_phases_predecessors_tickets_and_actual_hours(self):
        from psaspine import projects
        conn = self._conn()
        pid = projects.create(conn, name="Replace ward 3 switches", manager="alice", budget_hours=40, starts_on="2026-10-01",
                              ends_on="2026-10-31", at=self.at, actor="alice")
        with self.assertRaises(projects.Refused):
            projects.create(conn, name="Backwards", starts_on="2026-10-31", ends_on="2026-10-01", at=self.at, actor="alice")
        a = projects.add_phase(conn, pid, name="Survey", budget_hours=8, at=self.at, actor="alice")
        b = projects.add_phase(conn, pid, name="Install", budget_hours=24, at=self.at, actor="alice")
        c = projects.add_phase(conn, pid, name="Cut over ward 3", parent_id=b, at=self.at, actor="alice")
        projects.add_dependency(conn, b, a, at=self.at, actor="alice")
        with self.assertRaises(projects.Refused):
            projects.add_dependency(conn, a, b, at=self.at, actor="alice")                 # a loop
        with self.assertRaises(projects.Refused):
            projects.set_phase_status(conn, b, True, at=self.at, actor="alice")            # waits on Survey
        projects.set_phase_status(conn, a, True, at=self.at, actor="alice")
        projects.set_phase_status(conn, b, True, at=self.at, actor="alice")
        self.assertEqual([(p["name"], p["depth"]) for p in projects.phases(conn, pid)],
                         [("Survey", 0), ("Install", 0), ("Cut over ward 3", 1)])
        projects.link_ticket(conn, "ITO-1", pid, a, at=self.at, actor="alice")
        conn.execute("INSERT INTO time_entry (work_item_id, entity_id, worked_on, band_hours, performed_by, entered_by,"
                     " charge_method, actual_hours) VALUES ('ITO-1','PMC','2026-10-02',2,'alice','alice','INCLUDED_IN_MONTHLY_FEE',1.5)")
        self.assertEqual(projects.actual_hours(conn, pid), 1.5)
        self.assertEqual(projects.phases(conn, pid)[0]["actual_hours"], 1.5)
        conn.commit()
        del c
        _, _, page = self._call("GET", f"/project/{pid}", cookie=self.alice)
        self.assertIn("1.50 of 40.00 h", page)
        self.assertIn("waits on Survey", page)
        _, _, ticket = self._call("GET", "/ticket/ITO-1", cookie=self.alice)
        self.assertIn(f"<a href='/project/{pid}'>{pid}</a> Replace ward 3 switches · Survey", ticket)
        _, h, _ = self._call("POST", "/projects/new", cookie=self.alice, form={"name": "Second", "board_id": "NOPE"})
        self.assertIn("err=", dict(h)["Location"])
        _, h, _ = self._call("POST", f"/project/{pid}/ticket", cookie=self._cookie_for("carol"), form={"work_item_id": "ITO-1"})
        self.assertIn("err=No+ticket+ITO-1+that+you+work", dict(h)["Location"])
        conn = self._conn()
        projects.link_ticket(conn, "ITO-9", pid, a, at=self.at, actor="alice")                # a PHI ticket joins the project
        conn.execute("INSERT INTO time_entry (work_item_id, entity_id, worked_on, band_hours, performed_by, entered_by,"
                     " charge_method, actual_hours) VALUES ('ITO-9','PMC','2026-10-03',8,'alice','alice','INCLUDED_IN_MONTHLY_FEE',7.75)")
        conn.commit()
        _, _, page = self._call("GET", f"/project/{pid}", cookie=self.alice)                  # on PHI: sees 1.5 + 7.75
        self.assertIn("9.25 of 40.00 h", page)
        self.assertIn("ITO-9", page)
        _, _, page = self._call("GET", f"/project/{pid}", cookie=self._cookie_for("carol"))   # not on PHI: neither the ticket nor its hours
        self.assertIn("1.50 of 40.00 h", page)
        self.assertNotIn("ITO-9", page)
        _, _, page = self._call("GET", "/projects", cookie=self._cookie_for("carol"))
        self.assertIn("1.50 of 40.00 h", page)
        self.assertIn("<td class=center>1</td>", page)                                         # one ticket she may see, not two
        self.assertEqual(self._conn().execute("SELECT COUNT(*) FROM audit_event WHERE action = 'RESTRICTED_READ'"
                                              " AND detail LIKE 'project %'").fetchone()[0], 1)  # alice's read of the PHI ticket

    # ---------------------------------------------------- report writer

    def test_the_report_writer_groups_filters_and_never_crosses_a_board(self):
        from psaspine import reportwriter as rw
        conn = self._conn()
        grouped = rw.run(conn, "TICKETS", [], "board", {}, boards={"IT_HELP", "PHI"})
        self.assertEqual(grouped["headers"], ["Board", "Count"])
        self.assertEqual(sorted(r[0] for r in grouped["rows"]), ["IT Help", "PHI Board"])
        mine = rw.run(conn, "TICKETS", ["id", "summary"], None, {}, boards={"IT_HELP"})
        self.assertEqual([r[0] for r in mine["rows"]], ["ITO-1"])                          # PHI's ticket never appears
        with self.assertRaises(rw.Refused):
            rw.run(conn, "TICKETS", ["id; DROP TABLE ticket"], "nope", {}, boards={"IT_HELP"})
        self.assertIn("'=cmd", rw.as_csv({"headers": ["x"], "rows": [["=cmd"]]}))        # no formula in a spreadsheet
        rid = rw.save(conn, name="By board", dataset="TICKETS", columns=[], group_by="board", filters={"evil": "1"},
                      owner="alice", shared=True, at=self.at)
        conn.commit()
        _, _, page = self._call("GET", f"/reports/custom/{rid}", cookie=self._cookie_for("carol"))
        self.assertIn("IT Help", page)
        self.assertNotIn("PHI Board", page)                                                 # carol is not on PHI
        _, _, adhoc = self._call("GET", "/reports/custom/run", cookie=self.alice,
                                 query="dataset=TICKETS&col=id&col=state&board=IT_HELP")
        self.assertIn("<th>Ticket</th><th>State</th>", adhoc)
        status, headers, body = self._call("GET", f"/reports/custom/{rid}/csv", cookie=self.alice)
        self.assertIn("text/csv", dict(headers)["Content-Type"])
        self.assertTrue(body.startswith("Board,Count"))
        _, h, _ = self._call("POST", f"/reports/custom/{rid}/pin", cookie=self.root)
        self.assertIn("Pinned", dict(h)["Location"])
        _, _, reports = self._call("GET", "/reports", cookie=self.alice)
        self.assertIn(f"/reports/custom/{rid}'>By board</a>", reports)
        conn = self._conn()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'REPORT_DEF'").fetchone()[0], 1)
        before = conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'RESTRICTED_READ' AND subject_id = 'PHI'"
                              " AND detail LIKE 'report %'").fetchone()[0]
        _, _, body = self._call("GET", "/reports/custom/run", cookie=self.alice, query="dataset=TICKETS&col=id&format=csv")
        self.assertIn("ITO-9", body)                                                            # alice works PHI, so she may
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'RESTRICTED_READ' AND subject_id = 'PHI'"
                                      " AND detail LIKE 'report %'").fetchone()[0], before + 1)  # and the read is on the record
        _, _, body = self._call("GET", "/reports/custom/run", cookie=self._cookie_for("carol"), query="dataset=TICKETS&col=id&format=csv")
        self.assertNotIn("ITO-9", body)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'RESTRICTED_READ' AND subject_id = 'PHI'"
                                      " AND detail LIKE 'report %'").fetchone()[0], before + 1)  # nothing to audit: she saw nothing

    # ------------------------------------------------------------ BizBox

    def _csvs(self, rows_po="PONo,VendorName,PODate,Status,TotalAmount,Currency\r\nPO-1,Vendor A,2026-09-02,Approved,1000,PHP\r\n"):
        folder = Path(self.tmp.name) / "bizbox"
        folder.mkdir(exist_ok=True)
        (folder / "agreement.csv").write_text("AgreementNo,AgreementName,VendorName,Status,ContractAmount,Currency,StartDate,EndDate\r\n"
                                              "AGR-1,Printer care,Vendor A,Active,1200.50,PHP,2026-01-01,20261231\r\n", encoding="utf-8")
        (folder / "product.csv").write_text("ItemCode,ItemName,Category,Unit,UnitCost\r\nIT-1,Toner,Consumables,pc,\"4,250.00\"\r\n",
                                            encoding="utf-8")
        (folder / "purchase_order.csv").write_text(rows_po, encoding="utf-8")
        (folder / "invoice.csv").write_text("ReceivingNo,SupplierInvoiceNo,VendorName,InvoiceDate,DueDate,Status,TotalAmount,Currency,AgreementNo\r\n"
                                            "INV-1,SI-778,Vendor A,2026-09-05,2026-10-05,Posted,100,PHP,AGR-1\r\n", encoding="utf-8")
        (folder / "po_line.csv").write_text("LineID,PONo,LineNo,ItemCode,Description,QtyOrdered,QtyReceived,UnitCost\r\n"
                                            "L-1,PO-1,1,IT-1,Toner black,2,2,500\r\n", encoding="utf-8")
        return folder

    def _full_map(self):
        """The sample map plus an agreement source and the invoice's agreement_ref,
        for the tests of what the desk shows when a source has agreements.
        BizBox has none (SQL01, 29 Sep 2026), so the sample map carries neither."""
        from psaspine import bizbox
        m = bizbox.load_map(Path(__file__).parent.parent / "bizbox" / "bizbox-map.sample.json")
        m["objects"]["agreement"] = {"view": "psa.vw_agreement", "columns": {
            "ext_ref": "AgreementNo", "name": "AgreementName", "party": "VendorName", "starts_on": "StartDate",
            "ends_on": "EndDate", "status": "Status", "amount": "ContractAmount", "currency": "Currency"}}
        m["objects"]["invoice"]["columns"]["agreement_ref"] = "AgreementNo"
        return bizbox.check_map(m)

    def test_the_bizbox_map_refuses_patient_names_sql_and_the_sa_login(self):
        from psaspine import bizbox
        good = bizbox.load_map(Path(__file__).parent.parent / "bizbox" / "bizbox-map.sample.json")
        self.assertIn("po_line", good["objects"])
        self.assertNotIn("agreement", good["objects"])                                          # BizBox holds none
        self.assertEqual(good["objects"]["invoice"]["columns"]["ext_ref"], "ReceivingNo")      # as SQL01 built the view
        for view, col in (("dbo.Patients", "AgreementNo"), ("psa.vw_agreement", "PatientName"),
                          ("psa.vw_agreement; DROP TABLE x", "AgreementNo"), ("psa.vw_agreement", "Name]--"),
                          ("hr.vw_admission", "AgreementNo"), ("psa.vw_agreement", "PhilHealthNo"),
                          ("psa.vw_agreement", "CaseNumber"), ("psa.vw_agreement", "Surname"), ("psa.vw_agreement", "GivenName"),
                          ("psa.vw_agreement", "PtName"), ("psa.vw_agreement", "HospitalNo"), ("psa.vw_agreement", "AgreementNo\n"),
                          ("psa.vw_agreement\n", "AgreementNo")):
            with self.assertRaises(bizbox.Refused, msg=(view, col)):
                bizbox.check_map({"objects": {"agreement": {"view": view, "columns": {"ext_ref": col, "name": "X"}}}})
        for cs in ("DRIVER={x};SERVER=a;UID=sa;PWD=b", "Driver={x};Server=a;User ID = SA ;Pwd=b", "DRIVER={x};UID={sa};PWD=b",
                   "DRIVER={x};User=sa"):
            with self.assertRaises(bizbox.Refused, msg=cs):
                bizbox.odbc_string(cs)
        self.assertTrue(bizbox.odbc_string("DRIVER={x};SERVER=a;UID=psa_bizbox_reader;PWD=b;ApplicationIntent=ReadWrite")
                        .endswith(";ApplicationIntent=ReadOnly"))                                # never a read-write intent
        self.assertNotIn("ReadWrite", bizbox.odbc_string("DRIVER={x};UID=r;PWD=b;ApplicationIntent=ReadWrite;Encrypt=yes"))
        with self.assertRaises(bizbox.Refused):
            bizbox.check_map({"objects": {"payroll": {"view": "a.b", "columns": {"ext_ref": "X"}}}})
        for cs in ("Driver=x;Server=h;UID=sa;PWD=p", "Server=h;User ID = SA ;Pwd=p"):
            with self.assertRaises(bizbox.Refused):
                bizbox.odbc_string(cs)
        self.assertIn("ApplicationIntent=ReadOnly", bizbox.odbc_string("Driver=x;Server=h;UID=psa_reader;PWD=p"))
        with self.assertRaises(bizbox.Refused):
            bizbox.odbc_string("")

    def test_sync_previews_then_mirrors_marks_absent_and_never_deletes(self):
        from psaspine import bizbox
        conn = self._conn()
        mapping = self._full_map()
        rows = bizbox.read_csv_dir(self._csvs(), mapping)
        preview = bizbox.sync(conn, rows, at=self.at, actor="t")
        self.assertEqual(preview["agreement"]["new"], 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ext_agreement").fetchone()[0], 0)   # preview wrote nothing
        bizbox.sync(conn, rows, at=self.at, actor="t", apply=True)
        agr = bizbox.get(conn, "agreement", "AGR-1")
        self.assertEqual((agr["ends_on"], agr["amount"]), ("2026-12-31", 1200.5))
        self.assertEqual(bizbox.get(conn, "product", "IT-1")["unit_cost"], 4250.0)
        self.assertEqual(len(bizbox.po_lines(conn, "PO-1")), 1)
        inv = bizbox.get(conn, "invoice", "INV-1")
        self.assertEqual((inv["supplier_ref"], inv["agreement_ref"], inv["status"]), ("SI-778", "AGR-1", "Posted"))
        wide = bizbox._value("Partially Received - Awaiting Invoice", "text", "purchase_order.status", bizbox.WIDTH["status"])
        self.assertEqual(len(wide), 32)                                                          # the port's NVARCHAR(32), not a failed insert
        with self.assertRaises(bizbox.Refused) as cm:
            bizbox._value("ten pesos", "money", "purchase_order.total")
        self.assertNotIn("pesos", str(cm.exception))                                             # the refusal names the field, not the cell
        long_key = {"ext_ref": "K" * (bizbox.MAX_KEY + 1), "name": "too long a key", "unit_cost": "1"}
        c = bizbox.sync(conn, {"product": [long_key, {"ext_ref": "IT-1", "name": "Toner", "unit_cost": "1"}]}, at=self.at, actor="t")
        self.assertEqual((c["product"]["skipped"], c["product"]["unchanged"]), (1, 0))          # 900-byte key guard: skipped, counted
        self.assertEqual(c["product"]["changed"], 1)
        bizbox.link(conn, "TICKET", "ITO-1", "purchase_order", "PO-1", at=self.at, actor="alice")
        conn.commit()
        rows = bizbox.read_csv_dir(self._csvs("PONo,VendorName,PODate,Status,TotalAmount,Currency\r\n"
                                              "PO-2,Vendor B,2026-09-10,Draft,50,PHP\r\n"), mapping)
        c = bizbox.sync(conn, rows, at=self.at, actor="t", apply=True)["purchase_order"]
        self.assertEqual((c["new"], c["absent"]), (1, 1))
        gone = bizbox.get(conn, "purchase_order", "PO-1")
        self.assertEqual(gone["present"], 0)                                                   # kept, marked absent
        self.assertEqual(len(bizbox.links(conn, "TICKET", "ITO-1")), 1)                         # the link survives
        with self.assertRaises(bizbox.Refused):
            bizbox.link(conn, "TICKET", "ITO-1", "invoice", "INV-404", at=self.at, actor="alice")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'BIZBOX_SYNC'").fetchone()[0], 2)

    def test_finance_pages_links_and_changes_waiting_for_bizbox(self):
        from psaspine import bizbox
        conn = self._conn()
        _, _, page = self._call("GET", "/finance", cookie=self.alice)
        self.assertIn("href='/finance?tab=agreement'", page)                                    # an empty mirror shows every kind
        mapping = bizbox.load_map(Path(__file__).parent.parent / "bizbox" / "bizbox-map.sample.json")
        bizbox.sync(conn, bizbox.read_csv_dir(self._csvs(), mapping), at=self.at, actor="t", apply=True)
        for tab in ("agreement", "purchase_order", "product", "invoice", "changes"):
            status, _, page = self._call("GET", "/finance", cookie=self.alice, query=f"tab={tab}")
            self.assertEqual(status, "200 OK", tab)
        _, _, page = self._call("GET", "/finance", cookie=self.alice, query="tab=agreement")
        self.assertIn("<a class='on' href='/finance?tab=agreement'>Agreements · 0</a>", page)   # the desk's own tab (045), empty
        self.assertIn("No agreement yet.", page)
        self.assertNotIn("<h3><svg class=ic aria-hidden=true><use href=#i-plus></use></svg>New agreement", page)  # READ: no form
        _, _, page = self._call("GET", "/finance", cookie=self.alice)
        self.assertIn("<a class='on' href='/finance?tab=agreement'>", page)                     # and Finance opens on it
        _, _, page = self._call("GET", "/finance", cookie=self.alice, query="tab=purchase_order")
        self.assertIn("<div class=l>Approved</div><div class=n>1</div>", page)                # the procurement summary
        _, _, page = self._call("GET", "/finance", cookie=self.alice, query="tab=invoice")
        self.assertIn("<div class=l>Posted</div><div class=n>1</div>", page)                  # invoices summarised in BizBox's own words
        self.assertIn("<th>Supplier&#x27;s invoice no.</th>", page)
        self.assertIn("<td>SI-778</td>", page)
        self.assertNotIn("<th>Agreement</th>", page)                                            # no invoice has one, so no column
        _, _, page = self._call("GET", "/finance/invoice", cookie=self.alice, query="ref=INV-1")
        self.assertIn("<dd>SI-778</dd>", page)
        self.assertNotIn("<dt>Agreement</dt>", page)
        _, _, page = self._call("GET", "/ticket/ITO-1", cookie=self.alice)
        self.assertNotIn("<option value=agreement>", page)                                      # nor does the Finance pod offer one
        self.assertIn("<option value=purchase_order>", page)
        bizbox.sync(conn, bizbox.read_csv_dir(self._csvs(), self._full_map()), at=self.at, actor="t", apply=True)
        _, _, page = self._call("GET", "/finance", cookie=self.alice, query="tab=invoice")
        self.assertIn("href='/finance?tab=agreement'", page)                                    # a source with agreements shows them
        self.assertIn("<th>Agreement</th>", page)
        _, _, page = self._call("GET", "/finance/invoice", cookie=self.alice, query="ref=INV-1")
        self.assertIn("<a href='/finance/agreement?ref=AGR-1'>AGR-1</a>", page)               # an invoice's agreement is a link
        _, _, page = self._call("GET", "/finance/purchase_order", cookie=self.alice, query="ref=PO-1")
        self.assertIn("Toner black", page)
        self.assertIn("PHP 1,000.00", page)
        status, _, _ = self._call("GET", "/finance/po_line", cookie=self.alice, query="ref=L-1")
        self.assertTrue(status.startswith("404"), status)                                      # a line is not a record of its own
        _, h, _ = self._call("POST", "/ticket/ITO-1/finance/link", cookie=self.alice, form={"kind": "purchase_order", "ext_ref": "PO-1"})
        self.assertIn("Linked", dict(h)["Location"])                                            # a Finance reader links
        _, h, _ = self._call("POST", "/ticket/ITO-1/finance/link", cookie=self.alice, form={"kind": "po_line", "ext_ref": "L-1"})
        self.assertIn("err=", dict(h)["Location"])
        _, _, page = self._call("GET", "/finance", cookie=self.alice, query="tab=purchase_order")
        self.assertIn("<a href='/ticket/ITO-1'>ITO-1</a>", page)                               # the Linked column, one query for the page
        status, _, _ = self._call("POST", "/finance/purchase_order/propose", cookie=self.alice,
                                  form={"ref": "PO-1", "field": "status", "new_value": "Received", "reason": "x"})
        self.assertTrue(status.startswith("403"), status)                                      # but may not propose
        from psaspine import security
        security.assign(conn, "alice", "SERVICE_MANAGER", at=self.at, actor="root")
        conn.commit()
        _, h, _ = self._call("POST", "/finance/purchase_order/propose", cookie=self.alice,
                             form={"ref": "PO-1", "field": "status", "new_value": "Received", "reason": "Delivered to ward 3 today"})
        self.assertIn("BizBox+has+not+changed", dict(h)["Location"])
        self.assertTrue(dict(h)["Location"].startswith("/finance/purchase_order?ref=PO-1&"), dict(h)["Location"])
        _, h, _ = self._call("POST", "/finance/purchase_order/propose", cookie=self.alice,
                             form={"ref": "PO-1", "field": "status", "new_value": "Closed", "reason": "again"})
        self.assertIn("already+pending", dict(h)["Location"])
        _, h, _ = self._call("POST", "/finance/purchase_order/propose", cookie=self.alice,
                             form={"ref": "PO-1", "field": "vendor", "new_value": "x", "reason": "y"})
        self.assertIn("err=", dict(h)["Location"])                                              # not an editable field
        conn = self._conn()
        self.assertEqual(bizbox.get(conn, "purchase_order", "PO-1")["status"], "Approved")    # BizBox's value stands
        self.assertEqual(bizbox.push(conn, at=self.at), {"applied": 0, "rejected": 0, "pending": 1})

        class Fake(bizbox.Writer):
            def apply(self, change):
                return "applied by the test writer"
        self.assertEqual(bizbox.push(conn, Fake(), at=self.at), {"applied": 1, "rejected": 0, "pending": 0})
        conn.commit()
        _, _, page = self._call("GET", "/finance", cookie=self.alice, query="tab=changes&status=APPLIED")
        self.assertIn("Delivered to ward 3 today", page)
        self.assertIn("Applied in BizBox", page)
        security_ro = self._conn()
        from psaspine import security
        security.assign(security_ro, "alice", "READ_ONLY", at=self.at, actor="root")
        security_ro.commit()
        status, _, _ = self._call("GET", "/finance", cookie=self.alice)
        self.assertTrue(status.startswith("403"))                                               # READ_ONLY has no finance
        _, _, board = self._call("GET", "/", cookie=self.alice)
        self.assertNotIn('href="/finance"', board)                                              # and the nav hides it

    def test_agreements_are_the_desks_own_and_cover_what_bizbox_holds(self):
        from psaspine import agreements, bizbox, security
        conn = self._conn()
        mapping = bizbox.load_map(Path(__file__).parent.parent / "bizbox" / "bizbox-map.sample.json")
        bizbox.sync(conn, bizbox.read_csv_dir(self._csvs(), mapping), at=self.at, actor="t", apply=True)
        with self.assertRaises(agreements.Refused):
            agreements.create(conn, name="", at=self.at, actor="alice")
        with self.assertRaises(agreements.Refused):
            agreements.create(conn, name="Backwards", starts_on="2026-12-31", ends_on="2026-01-01", at=self.at, actor="alice")
        with self.assertRaises(agreements.Refused):
            agreements.create(conn, name="Words", amount="ten", at=self.at, actor="alice")
        aid = agreements.create(conn, name="Printer care 2026", party="Vendor A", starts_on="2026-01-01", ends_on="2026-12-31",
                                amount="120,000", currency="php", at=self.at, actor="alice")
        self.assertEqual(aid, "AGR-0001")
        a = agreements.get(conn, aid)
        self.assertEqual((a["status"], a["amount"], a["currency"]), ("DRAFT", 120000.0, "PHP"))
        self.assertEqual(agreements.update(conn, aid, at=self.at, actor="alice", name="Printer care 2026"), "nothing changed")
        self.assertEqual(agreements.update(conn, aid, at=self.at, actor="alice", status="ACTIVE", party="Vendor A Inc"),
                         "Party Vendor A -> Vendor A Inc; Status DRAFT -> ACTIVE")
        self.assertTrue(agreements.add_item(conn, aid, "invoice", "INV-1", at=self.at, actor="alice"))
        self.assertFalse(agreements.add_item(conn, aid, "invoice", "INV-1", at=self.at, actor="alice"))   # once
        self.assertTrue(agreements.add_item(conn, aid, "purchase_order", "PO-1", note="the toner order", at=self.at, actor="alice"))
        self.assertTrue(agreements.add_item(conn, aid, "product", "IT-1", at=self.at, actor="alice"))
        with self.assertRaises(agreements.Refused):
            agreements.add_item(conn, aid, "invoice", "INV-404", at=self.at, actor="alice")             # not in the mirror
        with self.assertRaises(agreements.Refused):
            agreements.add_item(conn, aid, "po_line", "L-1", at=self.at, actor="alice")                  # a line is not covered on its own
        items = agreements.items(conn, aid)
        self.assertEqual([(i["kind"], i["ext_ref"], i["present"]) for i in items],
                         [("INVOICE", "INV-1", True), ("PRODUCT", "IT-1", True), ("PURCHASE_ORDER", "PO-1", True)])
        self.assertEqual(items[2]["record"]["vendor"], "Vendor A")
        tot = agreements.totals(conn, aid)
        self.assertEqual((tot["INVOICE"], tot["PURCHASE_ORDER"], tot["PRODUCT"]),
                         ({"n": 1, "total": 100.0}, {"n": 1, "total": 1000.0}, {"n": 1, "total": None}))
        self.assertEqual([r["agreement_id"] for r in agreements.covering(conn, "invoice", "INV-1")], [aid])
        self.assertEqual(agreements.covering_for(conn, "purchase_order", ["PO-1", "PO-9"])["PO-9"], [])
        # the hourly sync marks PO-1 absent; the agreement and its covering survive, and the page says so
        bizbox.sync(conn, bizbox.read_csv_dir(self._csvs("PONo,VendorName,PODate,Status,TotalAmount,Currency\r\n"
                                                         "PO-2,Vendor B,2026-09-10,Draft,50,PHP\r\n"), mapping),
                    at=self.at, actor="t", apply=True)
        self.assertEqual([(i["ext_ref"], i["present"]) for i in agreements.items(conn, aid) if i["kind"] == "PURCHASE_ORDER"],
                         [("PO-1", False)])
        self.assertEqual(agreements.totals(conn, aid)["PURCHASE_ORDER"], {"n": 1, "total": 1000.0})     # covered is covered
        self.assertTrue(agreements.remove_item(conn, aid, "product", "IT-1", at=self.at, actor="alice"))
        self.assertFalse(agreements.remove_item(conn, aid, "product", "IT-1", at=self.at, actor="alice"))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'AGREEMENT'").fetchone()[0], 6)
        conn.commit()
        # the pages: Finance READ sees, WRITE changes; who has WRITE is set in Setup › Security roles
        _, _, page = self._call("GET", "/finance", cookie=self.alice, query="tab=agreement")
        self.assertIn("Agreements · 1</a>", page)
        self.assertIn(f"<a href='/agreement/{aid}'>{aid}</a></td><td><b>Printer care 2026</b></td><td>Vendor A Inc</td>", page)
        self.assertIn("<td class=center>2</td>", page)                                                 # covers two records
        status, _, _ = self._call("POST", "/agreements/new", cookie=self.alice, form={"name": "Nope"})
        self.assertTrue(status.startswith("403"), status)                                              # Technician: READ only
        _, _, page = self._call("GET", f"/agreement/{aid}", cookie=self.alice)
        self.assertIn("<a href='/finance/invoice?ref=INV-1'>INV-1</a>", page)
        self.assertIn("<span class=pill>gone from BizBox</span>", page)                                # PO-1, kept and marked
        self.assertIn("<div class=l>Invoices</div><div class=n>1</div><div class=muted>PHP 100.00</div>", page)
        self.assertNotIn("/agreement/AGR-0001/item/remove", page)                                      # READ: no remove buttons
        status, _, _ = self._call("GET", f"/agreement/{aid}", cookie=self._cookie_for("nurse"))
        self.assertTrue(status.startswith("403"), status)                                              # a requester has no Finance
        security.assign(conn, "alice", "SERVICE_MANAGER", at=self.at, actor="root")
        conn.commit()
        _, h, _ = self._call("POST", "/agreements/new", cookie=self.alice,
                             form={"name": "Network switches, ward 3", "party": "Vendor B", "amount": "50000", "currency": "PHP"})
        self.assertIn("/agreement/AGR-0002?msg=", dict(h)["Location"])
        _, h, _ = self._call("POST", "/agreement/AGR-0002/item", cookie=self.alice, form={"kind": "invoice", "ext_ref": "INV-1"})
        self.assertIn("INV-1+is+now+covered", dict(h)["Location"])
        _, h, _ = self._call("POST", "/agreement/AGR-0002/item", cookie=self.alice, form={"kind": "invoice", "ext_ref": "INV-9"})
        self.assertIn("err=No+invoice", dict(h)["Location"])
        _, _, page = self._call("GET", "/agreement/AGR-0002", cookie=self.alice, query="find=product&fq=toner")
        self.assertIn("<a href='/finance/product?ref=IT-1'>IT-1</a>", page)                            # found in the mirror
        self.assertIn("<button class='ghost small' type=submit>Add</button>", page)
        _, _, page = self._call("GET", "/finance/invoice", cookie=self.alice, query="ref=INV-1")
        self.assertIn(f"<a href='/agreement/{aid}'>{aid}</a> Printer care 2026", page)                # covered by both, on the record's page
        self.assertIn("<a href='/agreement/AGR-0002'>AGR-0002</a> Network switches, ward 3", page)
        _, _, page = self._call("GET", "/finance", cookie=self.alice, query="tab=invoice")
        self.assertIn(f"<a href='/agreement/{aid}' title='Printer care 2026'>{aid}</a>", page)      # and in the list's Linked column
        _, h, _ = self._call("POST", "/agreement/AGR-0002/status", cookie=self.alice, form={"status": "CANCELLED"})
        self.assertIn("Now+cancelled", dict(h)["Location"])
        _, h, _ = self._call("POST", "/agreement/AGR-0002/item", cookie=self.alice, form={"kind": "product", "ext_ref": "IT-1"})
        self.assertIn("cancelled+agreement", dict(h)["Location"])                                      # covers nothing new
        _, _, page = self._call("GET", "/finance", cookie=self.alice, query="tab=agreement")
        self.assertIn("Agreements · 1</a>", page)                                                      # a cancelled one is not counted
        _, h, _ = self._call("POST", f"/agreement/{aid}/update", cookie=self.alice,
                             form={"name": "Printer care 2026", "party": "Vendor A Inc", "starts_on": "2026-01-01", "ends_on": "2025-01-01",
                                   "amount": "120000", "currency": "PHP", "notes": ""})
        self.assertIn("err=An+agreement+ends+after+it+starts", dict(h)["Location"])
        status, _, _ = self._call("GET", "/agreement/AGR-0404", cookie=self.alice)
        self.assertTrue(status.startswith("404"))

    def test_finance_pages_count_the_whole_mirror_and_open_every_key(self):
        import threading
        import urllib.request
        from wsgiref.simple_server import WSGIRequestHandler, make_server
        from psaspine import bizbox

        class Quiet(WSGIRequestHandler):
            def log_message(self, *a):                      # the request log is noise in a test run
                pass
        conn = self._conn()
        rows = [{"ext_ref": f"IT-{i:04d}", "name": f"Item {i}", "unit_cost": "1"} for i in range(1, 251)]
        rows += [{"ext_ref": "A/B-1", "name": "Slash", "unit_cost": "1"}, {"ext_ref": "P%25", "name": "Percent", "unit_cost": "1"},
                 {"ext_ref": "ünïcødé-1", "name": "Accents", "unit_cost": "1"}]
        pos = [{"ext_ref": f"PO-{i:04d}", "status": ("Approved", "Draft", "Received")[i % 3], "total": "10"} for i in range(1, 301)]
        bizbox.sync(conn, {"product": rows, "purchase_order": pos}, at=self.at, actor="t", apply=True)
        _, _, page = self._call("GET", "/finance", cookie=self.alice, query="tab=product")
        self.assertIn("Products · 253", page)                                                   # the tab counts the table, not the page
        self.assertIn("Showing 1–100 of 253", page)
        self.assertEqual(page.count("<tr><td><a href='/finance/product?ref="), 100)
        _, _, page = self._call("GET", "/finance", cookie=self.alice, query="tab=product&page=3")
        self.assertIn("Showing 201–253 of 253", page)
        self.assertIn("‹ Previous", page)
        self.assertNotIn("Next ›", page)
        _, _, page = self._call("GET", "/finance", cookie=self.alice, query="tab=purchase_order")
        self.assertIn("<div class=l>Approved</div><div class=n>100</div>", page)               # tiles over all 300, not the 100 shown
        self.assertIn("PHP 1,000.00", page)
        _, _, page = self._call("GET", "/finance", cookie=self.alice, query="tab=product&q=slash")
        self.assertEqual(page.count("<tr><td><a href='/finance/product?ref="), 1)
        # the links the list emits open through a real WSGI server, which percent-decodes the path once
        srv = make_server("127.0.0.1", 0, self.raw, handler_class=Quiet)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        base = f"http://127.0.0.1:{srv.server_port}"

        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))       # never through a proxy

        def get(path):
            req = urllib.request.Request(base + path, headers={"Cookie": self.alice})
            with opener.open(req, timeout=10) as r:
                return r.status, r.read().decode("utf-8")
        _, listing = get("/finance?tab=product&q=" + urllib.parse.quote("Slash Percent Accents"))
        hrefs = re.findall(r"<a href='(/finance/product\?ref=[^']*)'", listing)
        self.assertEqual(len(hrefs), 0)                                                         # three words AND together: none has all
        for ref in ("A/B-1", "P%25", "ünïcødé-1"):
            _, listing = get("/finance?tab=product&q=" + urllib.parse.quote(ref[:3]))
            hrefs = re.findall(r"<a href='(/finance/product\?ref=[^']*)'", listing)
            self.assertTrue(hrefs, ref)
            for href in hrefs:
                status, body = get(html.unescape(href))
                self.assertEqual(status, 200, href)
                self.assertIn("<h1>Product", body)
            self.assertIn(t_esc(ref), listing)


class DatabaseSettingsTest(unittest.TestCase):
    """How the store behaves with more than one person on the desk."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "spine.db"
        db.init(self.path).close()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_the_database_runs_in_wal_mode(self):
        """Readers carry on while one writer commits."""
        conn = db.connect(self.path)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        self.assertEqual(mode.lower(), "wal")

    def test_every_connection_enforces_foreign_keys(self):
        conn = db.connect(self.path)
        self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        conn.close()

    def test_a_reader_is_not_blocked_by_an_open_write(self):
        writer = db.connect(self.path)
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("INSERT INTO entity (entity_id, name) VALUES ('X-WAL','x')")
        reader = db.connect(self.path)
        # Under the old rollback journal this read would wait or fail; under
        # WAL it sees the last committed state at once.
        n = reader.execute("SELECT COUNT(*) FROM entity WHERE entity_id='X-WAL'").fetchone()[0]
        self.assertEqual(n, 0)
        writer.commit()
        writer.close()
        reader.close()

    def test_synchronous_is_left_at_full(self):
        """NORMAL can lose the last commit on a power cut; not a quiet change."""
        conn = db.connect(self.path)
        self.assertEqual(conn.execute("PRAGMA synchronous").fetchone()[0], 2)  # FULL
        conn.close()

    def test_backup_copies_a_consistent_single_file_and_proves_it(self):
        conn = db.connect(self.path)
        conn.execute("INSERT INTO entity (entity_id, name) VALUES ('X-B','x')")
        conn.commit()          # left open: the commit may still be in the WAL
        dest = Path(self.tmp.name) / "escrow" / "spine-escrow.db"
        dest.parent.mkdir()
        r = db.backup(self.path, dest)
        conn.close()
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["integrity"], "ok")
        self.assertEqual(len(r["sha256"]), 64)
        check = sqlite3.connect(str(dest))
        self.assertEqual(check.execute(
            "SELECT COUNT(*) FROM entity WHERE entity_id='X-B'").fetchone()[0], 1)
        self.assertEqual(check.execute("PRAGMA journal_mode").fetchone()[0].lower(),
                         "delete")
        check.close()
        # One file: no -wal or -shm beside the escrow copy.
        self.assertEqual(sorted(p.name for p in dest.parent.iterdir()),
                         ["spine-escrow.db"])

    def test_backup_refuses_to_overwrite_an_existing_backup(self):
        dest = Path(self.tmp.name) / "escrow.db"
        db.backup(self.path, dest)
        with self.assertRaises(FileExistsError):
            db.backup(self.path, dest)

    def test_backup_refuses_itself_and_a_missing_source(self):
        with self.assertRaises((ValueError, FileExistsError)):
            db.backup(self.path, self.path)
        with self.assertRaises(FileNotFoundError):
            db.backup(Path(self.tmp.name) / "nope.db", Path(self.tmp.name) / "x.db")
        self.assertFalse((Path(self.tmp.name) / "nope.db").exists())

    def test_the_backup_api_captures_a_commit_still_in_the_wal(self):
        """Why escrow must use Connection.backup and not a copy of the .db file."""
        conn = db.connect(self.path)
        conn.execute("INSERT INTO entity (entity_id, name) VALUES ('X-ESCROW','x')")
        conn.commit()
        target = sqlite3.connect(str(Path(self.tmp.name) / "escrow.db"))
        conn.backup(target)
        got = target.execute(
            "SELECT COUNT(*) FROM entity WHERE entity_id='X-ESCROW'").fetchone()[0]
        target.close()
        db.close(conn)
        self.assertEqual(got, 1)


class BoardSetupTest(unittest.TestCase):
    """017 and psaspine.setup — a board runs the way a Dada PSA board does.

    The gap these close is the one the first preview showed: every ticket read
    "no clock" because nothing that opened a ticket ever started one, and a fresh
    board had no statuses to move a ticket into.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 23, 9, 0)

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _open(self, board_id="IT_HELP", impact="I1", urgency="U1", **kw):
        return tickets.open_ticket(self.conn, board_id=board_id, summary="Printer down",
                                   impact=impact, urgency=urgency,
                                   requested_by="ward3@pmcne.ph", at=self.at, **kw)

    def test_init_seeds_no_statuses_or_targets(self):
        """Dada's direction (9 Sep): a PSA does not arrive configured."""
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM board_status").fetchone()["c"], 0)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM sla_target").fetchone()["c"], 0)
        self.assertIn("a default status for new tickets", setup.readiness(self.conn, "IT_HELP"))

    def test_the_starter_makes_a_board_ready(self):
        r = setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)
        self.assertEqual((r["statuses"], r["targets"]), (9, 12))                                  # 049 added Awaiting approval
        self.assertEqual(setup.readiness(self.conn, "IT_HELP"), [])
        # Every starter target is measured, never promised.
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM sla_target WHERE enforced <> 0").fetchone()["c"], 0)
        self.assertIsNotNone(self.conn.execute(
            "SELECT 1 FROM audit_event WHERE action = 'BOARD_SETUP'").fetchone())

    def test_reapplying_never_overwrites_an_administrators_change(self):
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)
        self.conn.execute("UPDATE sla_target SET target_minutes = 7"
                          " WHERE board_id='IT_HELP' AND priority='P1' AND clock='RESPOND'")
        self.conn.execute("UPDATE board SET calendar_id = 'BUSINESS' WHERE board_id='IT_HELP'")
        again = setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)
        self.assertEqual((again["statuses"], again["targets"]), (0, 0))
        self.assertEqual(self.conn.execute(
            "SELECT target_minutes FROM sla_target WHERE board_id='IT_HELP'"
            " AND priority='P1' AND clock='RESPOND'").fetchone()[0], 7)
        self.assertEqual(self.conn.execute(
            "SELECT calendar_id FROM board WHERE board_id='IT_HELP'").fetchone()[0], "BUSINESS")

    def test_a_new_ticket_lands_in_the_default_status_with_its_clocks_running(self):
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)
        tid = self._open()
        row = self.conn.execute(
            "SELECT t.board_status_id, t.priority, w.entity_id FROM ticket t"
            " JOIN work_item w ON w.work_item_id = t.work_item_id WHERE t.work_item_id = ?", (tid,)).fetchone()
        self.assertEqual(row["board_status_id"], "IT_HELP.NEW")
        self.assertEqual(row["priority"], "P1")
        clocks_ = {r["clock"]: r["target_minutes"] for r in self.conn.execute(
            "SELECT clock, target_minutes FROM ticket_clock WHERE work_item_id = ?", (tid,))}
        self.assertEqual(clocks_, {"RESPOND": 15, "RESOLUTION_PLAN": 60, "RESOLVE": 240})

    def test_a_ticket_with_no_known_company_goes_to_the_catch_all_not_to_pmc(self):
        """Guessing PMC would put effort against the wrong entity."""
        tid = self._open()
        self.assertEqual(self.conn.execute(
            "SELECT entity_id FROM work_item WHERE work_item_id = ?", (tid,)).fetchone()[0],
            "UNCLASSIFIED")
        named = self._open(entity_id="PMC")
        self.assertEqual(self.conn.execute(
            "SELECT entity_id FROM work_item WHERE work_item_id = ?", (named,)).fetchone()[0],
            "PMC")

    def test_a_board_that_is_not_set_up_starts_no_clock_and_says_why(self):
        tid = self._open()
        self.assertIsNone(self.conn.execute(
            "SELECT board_status_id FROM ticket WHERE work_item_id = ?", (tid,)).fetchone()[0])
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM ticket_clock WHERE work_item_id = ?", (tid,)).fetchone()[0], 0)

    def test_the_requesters_words_are_a_discussion_note(self):
        tid = tickets.open_ticket(self.conn, board_id="IT_HELP", summary="x", impact="I3",
                                  urgency="U3", requested_by="a@pmcne.ph", at=self.at,
                                  description="It flashes red.")
        self.assertEqual(self.conn.execute(
            "SELECT note_flag FROM ticket_event WHERE work_item_id = ?", (tid,)).fetchone()[0],
            "DISCUSSION")

    def test_moving_boards_keeps_the_id_the_clocks_and_the_milestone(self):
        """The reference PSA's Auto Assign does not follow a moved ticket; ours keeps
        everything, because one id across a handover is the point."""
        for bid in ("IT_HELP", "UNROUTED"):
            setup.apply_starter(self.conn, bid, actor="t", at=self.at)
        tid = self._open(board_id="UNROUTED")
        board.change_status(self.conn, tid, "UNROUTED.IN_PROGRESS",
                            at=self.at + timedelta(minutes=5), actor="t")
        before = self.conn.execute("SELECT clock_id, stopped_at FROM ticket_clock"
                                   " WHERE work_item_id = ? ORDER BY clock", (tid,)).fetchall()
        board.move(self.conn, tid, "IT_HELP", at=self.at + timedelta(minutes=9),
                   actor="t", owner="cadano")
        row = self.conn.execute("SELECT board_id, board_status_id, owner FROM ticket"
                                " WHERE work_item_id = ?", (tid,)).fetchone()
        self.assertEqual(tuple(row), ("IT_HELP", "IT_HELP.IN_PROGRESS", "cadano"))
        after = self.conn.execute("SELECT clock_id, stopped_at FROM ticket_clock"
                                  " WHERE work_item_id = ? ORDER BY clock", (tid,)).fetchall()
        self.assertEqual([tuple(r) for r in before], [tuple(r) for r in after])
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM ticket_handover WHERE work_item_id = ?", (tid,)).fetchone()[0], 1)

    def test_every_door_records_where_the_ticket_came_from(self):
        """018: Dada PSA's Source, and the build scope's intake_source."""
        tid = self._open(source="PHONE")
        self.assertEqual(self.conn.execute(
            "SELECT intake_source FROM ticket WHERE work_item_id = ?", (tid,)).fetchone()[0],
            "PHONE")
        drop = Path(self.tmp.name) / "drop"
        drop.mkdir()
        (drop / "a.eml").write_bytes(
            b"From: ward3@pmcne.ph\r\nSubject: Printer\r\nMessage-ID: <s1@pmcne.ph>\r\n"
            b"Date: Tue, 22 Sep 2026 09:00:00 +0800\r\n\r\nbody\r\n")
        intake.import_drop(self.conn, drop, run_id="s", at=self.at)
        self.assertEqual(self.conn.execute(
            "SELECT t.intake_source FROM intake_message m JOIN ticket t"
            " ON t.work_item_id = m.work_item_id").fetchone()[0], "EMAIL")
        with self.assertRaises(sqlite3.IntegrityError):
            self._open(source="CARRIER_PIGEON")

    def test_setup_board_cli(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr
        from psaspine.__main__ import main
        path = str(Path(self.tmp.name) / "cli.db")
        db.init(path).close()
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            self.assertEqual(main(["setup-board", path, "--board", "IT_HELP"]), 0)
            self.assertEqual(main(["setup-board", path, "--board", "NOPE"]), 1)
        self.assertIn("ready", out.getvalue())

    def test_a_seeded_board_gets_its_first_administrator_from_the_cli_once(self):
        # IT_HELP and UNROUTED come from the seed with no members, and board
        # access is membership only (SQL01 found the desk locked out, 26 Sep).
        import io
        from contextlib import redirect_stdout, redirect_stderr
        from psaspine.__main__ import main
        path = str(Path(self.tmp.name) / "cli2.db")
        db.init(path).close()
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(main(["board-admin", path, "--board", "IT_HELP", "--member", "alice"]), 0)
            self.assertEqual(main(["board-admin", path, "--board", "IT_HELP", "--member", "bob"]), 1)
            self.assertEqual(main(["board-admin", path, "--board", "NOPE", "--member", "bob"]), 1)
            self.assertEqual(main(["setup-board", path, "--board", "UNROUTED", "--admin", "carol"]), 0)
        self.assertIn("alice is its first administrator", out.getvalue())
        self.assertIn("already has members", err.getvalue())
        conn = db.connect(path)
        self.assertEqual([tuple(r) for r in conn.execute(
            "SELECT board_id, member, access FROM board_member ORDER BY board_id")],
            [("IT_HELP", "alice", "ADMIN"), ("UNROUTED", "carol", "ADMIN")])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'BOARD_MEMBER'").fetchone()[0], 2)
        conn.close()


class ManyBoardsTest(unittest.TestCase):
    """019 and setup.create_board / apply_template — many boards, the way an
    MSP runs the reference PSA: a service board, a change board and a project board to
    start, then one per group that runs its own queue, each with its own
    statuses, SLA and people."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 23, 9, 0)

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_a_new_board_gets_the_starter_and_its_creator_as_admin(self):
        bid = setup.create_board(self.conn, display_name="Facilities & Engineering",
                                 fulfiller_group="Engineering", creator="dada", at=self.at)
        self.assertEqual(bid, "FACILITIES_ENGINEERING")
        self.assertEqual(setup.readiness(self.conn, bid), [])
        self.assertEqual(self.conn.execute(
            "SELECT access FROM board_member WHERE board_id = ? AND member = 'dada'",
            (bid,)).fetchone()[0], "ADMIN")
        # Not live until someone owns it (the CHECK in 004).
        self.assertEqual(self.conn.execute("SELECT is_live FROM board WHERE board_id = ?",
                                           (bid,)).fetchone()[0], 0)

    def test_a_board_can_copy_another_boards_setup(self):
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)
        self.conn.execute("UPDATE sla_target SET target_minutes = 5 WHERE board_id='IT_HELP'"
                          " AND priority='P1' AND clock='RESPOND'")
        bid = setup.create_board(self.conn, display_name="Biomedical", fulfiller_group="Biomed",
                                 creator="dada", at=self.at, copy_from="IT_HELP")
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM board_status WHERE board_id = ?", (bid,)).fetchone()[0], 9)      # 049 added Awaiting approval
        self.assertEqual(self.conn.execute(
            "SELECT target_minutes FROM sla_target WHERE board_id = ? AND priority='P1'"
            " AND clock='RESPOND'", (bid,)).fetchone()[0], 5)

    def test_a_duplicate_board_is_refused(self):
        with self.assertRaises(ValueError):
            setup.create_board(self.conn, display_name="IT Help", fulfiller_group="x",
                               creator="dada", at=self.at, board_id="IT_HELP")

    def test_the_connectwise_template_is_board_kinds_not_help_and_request(self):
        """23 Sep direction: no Help/Request split. One service board takes the
        four ITIL service-desk types; changes and projects get their own boards."""
        from psaspine import itil
        r = setup.apply_template(self.conn, actor="dada", at=self.at)
        self.assertEqual(r["created"], ["IT_CHANGE", "IT_PROJECTS"])
        self.assertEqual(r["items"], 31)                 # all of Dada's items, on IT Help
        self.assertIn("BIOMEDICAL", r["waiting"])        # waits for its board
        self.assertIsNone(self.conn.execute(
            "SELECT 1 FROM board WHERE board_id = 'IT_REQUEST'").fetchone())
        self.assertEqual(itil.profile_of(self.conn, "IT_HELP"), "SERVICE")
        self.assertEqual(itil.profile_of(self.conn, "IT_CHANGE"), "CHANGE")
        self.assertEqual(itil.profile_of(self.conn, "IT_PROJECTS"), "PROJECT")
        # projects run no SLA clocks; the request board's numbers survive as typed targets
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM sla_target WHERE board_id"
                                           " IN ('IT_CHANGE','IT_PROJECTS')").fetchone()[0], 0)
        self.assertEqual(self.conn.execute(
            "SELECT target_minutes FROM sla_target_type WHERE board_id='IT_HELP' AND"
            " record_type='SERVICE_REQUEST' AND priority='P4' AND clock='RESPOND'").fetchone()[0], 960)
        again = setup.apply_template(self.conn, actor="dada", at=self.at)
        self.assertEqual((again["created"], again["items"]), ([], 0))
        setup.create_board(self.conn, display_name="Biomedical", board_id="BIOMEDICAL",
                           fulfiller_group="Biomed", creator="dada", at=self.at)
        self.assertEqual(setup.apply_template(self.conn, actor="dada", at=self.at)["items"], 4)

    def test_the_template_replaces_placeholders_but_never_a_saved_target(self):
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)
        self.conn.execute("UPDATE sla_target SET target_minutes = 7, note = 'set on the Setup page'"
                          " WHERE board_id='IT_HELP' AND priority='P1' AND clock='RESPOND'")
        setup.apply_template(self.conn, actor="dada", at=self.at)
        t = {(r[0], r[1]): r[2] for r in self.conn.execute(
            "SELECT priority, clock, target_minutes FROM sla_target WHERE board_id='IT_HELP'")}
        self.assertEqual(t[("P1", "RESPOND")], 7)        # kept
        self.assertEqual(t[("P3", "RESOLVE")], 1920)     # from the workbook
        self.assertNotIn(("P3", "RESOLUTION_PLAN"), t)   # placeholder gone

    def test_an_items_floor_takes_part_in_priority(self):
        setup.apply_template(self.conn, actor="dada", at=self.at)
        self.conn.execute("UPDATE catalogue_item SET min_priority = 'P2' WHERE catalogue_item_id ="
                          " (SELECT catalogue_item_id FROM catalogue_item WHERE default_board_id="
                          "'IT_HELP' LIMIT 1)")
        item = self.conn.execute("SELECT catalogue_item_id FROM catalogue_item WHERE min_priority"
                                 " = 'P2'").fetchone()[0]
        tid = tickets.open_ticket(self.conn, board_id="IT_HELP", summary="x", impact="I3",
                                  urgency="U3", requested_by="a", at=self.at,
                                  catalogue_item_id=item)
        row = self.conn.execute("SELECT priority, priority_source, catalogue_item_id FROM ticket"
                                " WHERE work_item_id = ?", (tid,)).fetchone()
        self.assertEqual(tuple(row), ("P2", "CATALOGUE_FLOOR", item))


class MailPickupScriptTest(unittest.TestCase):
    """scripts/Invoke-PmcMailPickup.ps1 runs on the live server, where nothing
    here can execute it. So its fences are asserted as text: pure ASCII for
    Windows PowerShell 5.1, preview unless -Apply, a certificate and never a
    secret, and no inbound listener."""

    SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "Invoke-PmcMailPickup.ps1"

    def setUp(self) -> None:
        self.raw = self.SCRIPT.read_bytes()
        self.text = self.raw.decode("ascii")          # raises if not pure ASCII

    def test_it_holds_no_secret_and_takes_none(self):
        lowered = self.text.lower()
        for shape in ("client_secret", "password", "convertto-securestring", "apikey"):
            self.assertNotIn(shape, lowered, shape)
        self.assertIn("client-assertion-type:jwt-bearer", self.text)

    def test_nothing_is_written_without_apply(self):
        self.assertIn("[switch] $Apply", self.text)
        preview = self.text.index("if (-not $Apply) {")
        first_write = self.text.index("Invoke-Graph \"$Graph/users/$mbx/messages/")
        self.assertLess(preview, first_write)

    def test_it_polls_and_never_listens(self):
        for shape in ("HttpListener", "notificationUrl", "subscriptions"):
            self.assertNotIn(shape, self.text)

    def test_the_delta_link_only_moves_after_a_good_import(self):
        failed = self.text.index("if ($code -ne 0) {")
        saved = self.text.index("Set-Content -Path $DeltaFile")
        self.assertLess(failed, saved)

    def test_two_pickups_keep_apart_and_one_can_name_its_board(self):
        # 058, the cut-over: helpdesk@ and support@ each get a pickup. Each
        # mailbox has its own delta link, log and drop subfolder, so a shared
        # -StateDir never mixes them; -BoardId reaches import-mail.
        self.assertIn('"inbox-deltalink-$Slug.txt"', self.text)
        self.assertIn("$DropDir = Join-Path $DropDir $Slug", self.text)
        self.assertNotIn("'inbox-deltalink.txt'", self.text)
        self.assertIn("[string] $BoardId", self.text)
        self.assertIn("if ($BoardId) { $importArgs += @('--board-id', $BoardId) }", self.text)


class BoardKindAndTypeTest(unittest.TestCase):
    """022 and psaspine.itil: board kinds (Service, Change, Project), the board's
    Types (Incident, Request, Problem, Event), change enablement, and incident ->
    problem -> change links."""

    def setUp(self) -> None:
        from psaspine import itil
        self.itil = itil
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 23, 9, 0)
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)
        setup.create_board(self.conn, display_name="IT Change", board_id="IT_CHANGE",
                           fulfiller_group="Dada", creator="lead", at=self.at, profile="CHANGE")

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _open(self, board="IT_HELP", **kw):
        return tickets.open_ticket(self.conn, board_id=board, summary="x", impact="I3",
                                   urgency="U3", requested_by=None, at=self.at, **kw)

    def _row(self, wid):
        return self.conn.execute("SELECT * FROM ticket WHERE work_item_id = ?", (wid,)).fetchone()

    def _status(self, board, name):
        return setup.status_id(board, name)

    def test_a_service_board_takes_the_four_service_desk_types(self):
        self.assertEqual(self._row(self._open())["record_type"], "INCIDENT")   # board default
        self.assertEqual(self._row(self._open(record_type="SERVICE_REQUEST"))["record_type"],
                         "SERVICE_REQUEST")
        with self.assertRaises(self.itil.NotAccepted):
            self._open(record_type="CHANGE")          # changes run on the change board
        wid = self._open(board="IT_CHANGE")
        self.assertEqual((self._row(wid)["record_type"], self._row(wid)["change_type"]),
                         ("CHANGE", "NORMAL"))          # the safe default needs approval

    def test_a_board_has_a_kind_and_a_change_board_runs_no_sla(self):
        kinds = dict(self.conn.execute("SELECT board_id, kind FROM board WHERE board_id IN"
                                       " ('IT_HELP','IT_CHANGE')").fetchall())
        self.assertEqual(kinds, {"IT_HELP": "SERVICE", "IT_CHANGE": "CHANGE"})
        names = [r[0] for r in self.conn.execute(
            "SELECT name FROM board_status WHERE board_id = 'IT_CHANGE' ORDER BY sort_order")]
        self.assertIn("Awaiting Approval", names)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM sla_target WHERE board_id = 'IT_CHANGE'").fetchone()[0], 0)

    def test_either_of_dadas_phrasings_is_configuration(self):
        self.itil.set_board_types(self.conn, "IT_HELP", list(self.itil.PROFILES["SERVICE"])
                                  + ["CHANGE"])
        self.assertEqual(self._row(self._open(record_type="CHANGE"))["record_type"], "CHANGE")

    def test_the_path_is_derived_so_a_variation_item_cannot_slip_the_gate(self):
        """The bypass: open_ticket wrote INCIDENT for a VARIATION item, and effort
        was booked against it unrefused."""
        db.seed_sample(self.conn)
        var = self.conn.execute("SELECT catalogue_item_id, default_board_id FROM catalogue_item"
                                " WHERE default_contract_basis = 'VARIATION' LIMIT 1").fetchone()
        wid = tickets.open_ticket(self.conn, board_id=var["default_board_id"], summary="x",
                                  impact="I3", urgency="U3", requested_by=None, at=self.at,
                                  catalogue_item_id=var["catalogue_item_id"])
        self.assertEqual(self._row(wid)["path"], "VARIATION")
        ok, _ = board.may_book_effort(self.conn, wid)
        self.assertFalse(ok)
        self.assertEqual(tickets_path := self._row(self._open(record_type="SERVICE_REQUEST"))["path"],
                         "SERVICE_REQUEST")
        self.assertEqual(self._row(self._open())["path"], "INCIDENT")

    def test_a_move_to_a_board_that_does_not_take_the_type_is_refused(self):
        wid = self._open()
        with self.assertRaises(board.NotOnThisBoard):
            board.move(self.conn, wid, "IT_CHANGE", at=self.at, actor="t")

    def test_a_normal_change_is_built_only_once_approved(self):
        wid = self._open(board="IT_CHANGE", owner="alice")
        approved = self._status("IT_CHANGE", "Approved")
        with self.assertRaises(self.itil.ChangeNotAuthorised):
            board.change_status(self.conn, wid, approved, at=self.at, actor="alice")
        with self.assertRaises(PermissionError):         # the owner never authorises it
            self.itil.decide(self.conn, wid, decision="APPROVED", authority="CAB",
                             actor="alice", at=self.at)
        with self.assertRaises(PermissionError):         # nor does anyone without authority
            self.itil.decide(self.conn, wid, decision="APPROVED", authority="CAB",
                             actor="bob", at=self.at)
        self.itil.decide(self.conn, wid, decision="DECLINED", authority="CAB", actor="lead",
                         at=self.at, comment="no backout plan")
        with self.assertRaises(self.itil.ChangeNotAuthorised):
            board.change_status(self.conn, wid, approved, at=self.at, actor="alice")
        self.itil.decide(self.conn, wid, decision="APPROVED", authority="CAB", actor="lead",
                         at=self.at)
        board.change_status(self.conn, wid, approved, at=self.at, actor="alice")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM change_approval").fetchone()[0], 2)

    def test_a_standard_change_needs_no_approval(self):
        wid = self._open(board="IT_CHANGE", change_type="STANDARD")
        board.change_status(self.conn, wid, self._status("IT_CHANGE", "Implementing"),
                            at=self.at, actor="t")

    def test_an_emergency_change_goes_ahead_but_closes_only_once_authorised(self):
        wid = self._open(board="IT_CHANGE", change_type="EMERGENCY")
        board.change_status(self.conn, wid, self._status("IT_CHANGE", "Implementing"),
                            at=self.at, actor="t")
        with self.assertRaises(self.itil.ChangeNotAuthorised):
            board.change_status(self.conn, wid, self._status("IT_CHANGE", ">Closed"),
                                at=self.at, actor="t")
        self.itil.decide(self.conn, wid, decision="APPROVED", authority="ECAB", actor="lead",
                         at=self.at)
        board.change_status(self.conn, wid, self._status("IT_CHANGE", ">Closed"),
                            at=self.at, actor="t")

    def test_change_fields_are_validated_and_belong_to_changes(self):
        wid = self._open(board="IT_CHANGE")
        board.update_fields(self.conn, wid, at=self.at, actor="t", change_risk="HIGH",
                            planned_start="2026-09-26 22:00", planned_end="2026-09-26 23:30",
                            backout_plan="restore the VM snapshot")
        self.assertEqual(self._row(wid)["change_risk"], "HIGH")
        with self.assertRaises(ValueError):
            board.update_fields(self.conn, wid, at=self.at, actor="t",
                                planned_end="2026-09-26 21:00")
        with self.assertRaises(ValueError):
            board.update_fields(self.conn, self._open(), at=self.at, actor="t", change_risk="LOW")

    def test_incidents_link_to_a_problem_and_a_problem_to_its_fix(self):
        inc1, inc2 = self._open(), self._open()
        prob = self._open(record_type="PROBLEM")
        fix = self._open(board="IT_CHANGE")
        self.itil.link(self.conn, inc1, prob, "CAUSED_BY", actor="t", at=self.at)
        self.itil.link(self.conn, inc2, prob, "CAUSED_BY", actor="t", at=self.at)
        self.itil.link(self.conn, prob, fix, "FIXED_BY", actor="t", at=self.at)
        with self.assertRaises(ValueError):              # an incident is not a problem
            self.itil.link(self.conn, inc1, inc2, "CAUSED_BY", actor="t", at=self.at)
        reads = sorted(x["reads"] for x in self.itil.links_of(self.conn, prob))
        self.assertEqual(reads, ["causes", "causes", "fixed by change"])
        # a link changes neither ticket's status or clocks
        self.assertIsNone(self._row(inc1)["closed_at"])

    def test_a_request_runs_on_its_own_targets_where_they_exist(self):
        self.conn.execute("INSERT INTO sla_target_type (board_id, record_type, priority, clock,"
                          " target_minutes, calendar) VALUES ('IT_HELP','SERVICE_REQUEST','P4',"
                          "'RESPOND',960,'MANILA_BUSINESS')")
        req = self._open(record_type="SERVICE_REQUEST")
        inc = self._open()
        clocks_of = lambda w: {r["clock"]: r["target_minutes"] for r in self.conn.execute(  # noqa: E731
            "SELECT clock, target_minutes FROM ticket_clock WHERE work_item_id = ?", (w,))}
        self.assertEqual(clocks_of(req), {"RESPOND": 960})
        self.assertEqual(clocks_of(inc)["RESPOND"], setup.STARTER_TARGETS["P4"][0])
        board.update_fields(self.conn, inc, at=self.at, actor="t", record_type="SERVICE_REQUEST")
        self.assertEqual(clocks_of(inc)["RESPOND"], 960)     # the running clock retargets

    def test_the_item_sets_the_type_unless_the_same_save_says_otherwise(self):
        db.seed_sample(self.conn)
        req_item = self.conn.execute(
            "SELECT i.catalogue_item_id FROM catalogue_item i JOIN service_action a"
            " ON a.action_id = i.action_id WHERE a.kind = 'REQUEST' AND i.default_board_id ="
            " 'IT_HELP' AND i.default_contract_basis = 'BASELINE' LIMIT 1").fetchone()[0]
        wid = self._open()
        board.update_fields(self.conn, wid, at=self.at, actor="t", catalogue_item_id=req_item,
                            record_type="INCIDENT")
        self.assertEqual(self._row(wid)["record_type"], "SERVICE_REQUEST")


class MailPolicyTest(unittest.TestCase):
    """023 and intake: loop guards, a ticket number in the subject, and each
    board's answer to a reply on a closed ticket (Dada PSA's email connector)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 23, 9, 0)
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)
        self.drop = Path(self.tmp.name) / "drop"
        self.drop.mkdir()
        self.n = 0

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _mail(self, subject, sender="ward3@pmcne.ph", headers="", body="Hello"):
        self.n += 1
        raw = (f"From: {sender}\r\nTo: helpdesk@pmcne.ph\r\nSubject: {subject}\r\n"
               f"Message-ID: <m{self.n}@pmcne.ph>\r\nDate: Wed, 23 Sep 2026 09:0{self.n % 10}:00 +0800\r\n"
               f"{headers}\r\n{body}\r\n")
        (self.drop / f"{self.n:03d}.eml").write_bytes(raw.encode())

    def _run(self, **kw):
        c = intake.import_drop(self.conn, self.drop, run_id=f"r{self.n}", board_id="IT_HELP",
                               at=self.at, **kw)
        for f in self.drop.iterdir():
            f.unlink()
        return c

    def _open(self, summary="Printer down", days_ago=0):
        return tickets.open_ticket(self.conn, board_id="IT_HELP", summary=summary, impact="I3",
                                   urgency="U3", requested_by="ward3@pmcne.ph",
                                   at=self.at - timedelta(days=days_ago))

    def _close(self, wid, days_ago=0):
        board.change_status(self.conn, wid, setup.status_id("IT_HELP", ">Closed"),
                            at=self.at - timedelta(days=days_ago), actor="t")

    def test_bounces_out_of_office_and_our_own_mail_open_nothing_but_are_counted(self):
        self._mail("Undeliverable: Printer", sender="MAILER-DAEMON@pmcne.ph")
        self._mail("Out of office", headers="Auto-Submitted: auto-replied\r\n")
        self._mail("Re: your ticket", sender="helpdesk@pmcne.ph")
        self._mail("Backup job failed", sender="veeam@pmcne.ph",
                   headers="Auto-Submitted: auto-generated\r\n")   # an alert is work
        c = self._run(own_addresses=["helpdesk@pmcne.ph"])
        self.assertEqual((c["loop_guarded"], c["new"]), (3, 1))
        self.assertEqual(c["new"] + c["unclassified"], c["files"])       # nothing lost

    def test_a_ticket_number_in_the_subject_finds_the_ticket(self):
        wid = self._open()
        self._mail(f"Still broken {intake.subject_token(wid)}")
        c = self._run()
        self.assertEqual(c["appended"], 1)
        self.assertEqual(self.conn.execute("SELECT customer_updated FROM ticket WHERE"
                                           " work_item_id = ?", (wid,)).fetchone()[0], 1)

    def test_a_reply_to_a_closed_ticket_reopens_it_by_default(self):
        wid = self._open()
        self._close(wid)
        self._mail(f"Re: [{wid}] printer")
        c = self._run()
        self.assertEqual(c["reopened"], 1)
        row = self.conn.execute("SELECT closed_at, board_status_id FROM ticket WHERE"
                                " work_item_id = ?", (wid,)).fetchone()
        self.assertIsNone(row["closed_at"])
        self.assertEqual(row["board_status_id"], setup.status_id("IT_HELP", "New"))

    def test_a_late_reply_opens_a_new_ticket_linked_to_the_old(self):
        from psaspine import itil
        self.conn.execute("UPDATE board SET reopen_within_days = 7 WHERE board_id = 'IT_HELP'")
        wid = self._open(days_ago=40)
        self._close(wid, days_ago=30)
        self._mail(f"Re: [{wid}] printer")
        c = self._run()
        self.assertEqual((c["reply_to_closed"], c["reopened"]), (1, 0))
        links = itil.links_of(self.conn, wid)
        self.assertEqual(len(links), 1)
        self.assertNotEqual(links[0]["other"], wid)

    def test_a_fulfillers_note_clears_customer_updated(self):
        wid = self._open()
        self._mail(f"More detail [{wid}]")
        self._run()
        board.add_note(self.conn, wid, body="On my way", actor="t", at=self.at,
                       flag="DISCUSSION")
        self.assertEqual(self.conn.execute("SELECT customer_updated FROM ticket WHERE"
                                           " work_item_id = ?", (wid,)).fetchone()[0], 0)


class WorkflowRunnerTest(unittest.TestCase):
    """024 and psaspine.workflow: rules run at the moment, age in SLA time,
    escalation as successive events, test before activate, all-or-nothing."""

    def setUp(self) -> None:
        from psaspine import workflow
        self.wf = workflow
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 23, 9, 0)
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)
        workflow.ensure_vocabulary(self.conn)
        self.conn.execute("INSERT INTO board_role (board_id, role, member) VALUES"
                          " ('IT_HELP', 'DISPATCH', 'disp'), ('IT_HELP', 'SERVICE_MANAGER', 'mgr')")

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _rule(self, wid, events):
        self.conn.execute("INSERT INTO workflow (workflow_id, board_id, name, table_type)"
                          " VALUES (?, 'IT_HELP', ?, 'TICKET')", (wid, wid))
        for ev, fires_on, conds, acts, extra in events:
            self.conn.execute(
                "INSERT INTO workflow_event (event_id, workflow_id, fires_on, execution_time,"
                " frequency, frequency_unit, max_executions) VALUES (?,?,?,?,?,?,?)",
                (ev, wid, fires_on, *extra))
            for n, (trig, op, val) in enumerate(conds):
                self.conn.execute("INSERT INTO workflow_condition (event_id, trigger_id, operator,"
                                  " value, sort_order) VALUES (?,?,?,?,?)", (ev, trig, op, val, n))
            for n, (act, role, status, detail) in enumerate(acts):
                self.conn.execute("INSERT INTO workflow_action (event_id, action, notify_role,"
                                  " target_status_id, detail, sort_order) VALUES (?,?,?,?,?,?)",
                                  (ev, act, role, status, detail, n))
            self.wf.test_event(self.conn, ev, at=self.at)
        self.wf.activate(self.conn, wid, actor="t", at=self.at)

    def _open(self, **kw):
        return tickets.open_ticket(self.conn, board_id="IT_HELP", summary="Printer down",
                                   impact="I3", urgency="U3", requested_by=None, at=self.at, **kw)

    def test_a_rule_that_was_never_tested_cannot_be_switched_on(self):
        self.conn.execute("INSERT INTO workflow (workflow_id, name, table_type) VALUES"
                          " ('W', 'W', 'TICKET')")
        self.conn.execute("INSERT INTO workflow_event (event_id, workflow_id, fires_on)"
                          " VALUES ('E', 'W', 'ON_CREATE')")
        with self.assertRaises(ValueError):
            self.wf.activate(self.conn, "W", actor="t", at=self.at)
        self.assertEqual(self.wf.test_event(self.conn, "E", at=self.at)["matches"], 0)
        self.wf.activate(self.conn, "W", actor="t", at=self.at)
        self.wf.edited(self.conn, "W")                      # an edit switches it off again
        self.assertEqual(self.conn.execute("SELECT is_active FROM workflow").fetchone()[0], 0)

    def test_an_every_board_rule_never_touches_a_restricted_board(self):
        """SQL01 part 9, defect 3: a system administrator's Every-board rule ran on
        restricted boards, so "Move to board" could carry a patient's ticket onto an
        open one. A restricted board is never "every board": its own administrators
        write its rules, on the board."""
        setup.create_board(self.conn, display_name="Ward systems", fulfiller_group="Clin",
                           creator="t", at=self.at, board_id="WARD", restricted=True)
        self.conn.execute("INSERT INTO workflow (workflow_id, board_id, name, table_type)"
                          " VALUES ('W_ALL', NULL, 'Any P1', 'TICKET')")
        self.conn.execute("INSERT INTO workflow_event (event_id, workflow_id, fires_on, execution_time)"
                          " VALUES ('E_ALL', 'W_ALL', 'ON_CREATE', 'ONCE')")
        self.conn.execute("INSERT INTO workflow_condition (event_id, trigger_id, operator, value,"
                          " sort_order) VALUES ('E_ALL', 'TICKET.PRIORITY', 'EQ', 'P1', 0)")
        self.conn.execute("INSERT INTO workflow_action (event_id, action, detail, sort_order)"
                          " VALUES ('E_ALL', 'ADD_NOTE', 'seen by the every-board rule', 0)")
        # the unscoped test (the CLI's) counts open boards only, and says which
        r = self.wf.test_event(self.conn, "E_ALL", at=self.at)
        self.assertEqual(r["matches"], 0)
        self.wf.activate(self.conn, "W_ALL", actor="t", at=self.at)
        open_p1 = self._open(min_priority="P1")
        ward_p1 = tickets.open_ticket(self.conn, board_id="WARD", summary="Monitor in bay 2",
                                      impact="I3", urgency="U3", requested_by=None, at=self.at,
                                      min_priority="P1")
        noted = {r[0] for r in self.conn.execute(
            "SELECT work_item_id FROM ticket_event WHERE kind = 'NOTE' AND actor = 'workflow:W_ALL/E_ALL'")}
        self.assertEqual(noted, {open_p1})
        self.assertNotIn(ward_p1, noted)
        # a rule written on the restricted board itself still runs there
        self.conn.execute("INSERT INTO workflow (workflow_id, board_id, name, table_type, is_active)"
                          " VALUES ('W_WARD', 'WARD', 'Ward P1', 'TICKET', 1)")
        self.conn.execute("INSERT INTO workflow_event (event_id, workflow_id, fires_on, execution_time,"
                          " tested_at) VALUES ('E_WARD', 'W_WARD', 'ON_CREATE', 'ONCE', '2026-09-23 09:00')")
        self.conn.execute("INSERT INTO workflow_action (event_id, action, detail, sort_order)"
                          " VALUES ('E_WARD', 'ADD_NOTE', 'seen by the ward rule', 0)")
        ward_2 = tickets.open_ticket(self.conn, board_id="WARD", summary="Monitor in bay 3",
                                     impact="I3", urgency="U3", requested_by=None, at=self.at)
        self.assertIsNotNone(self.conn.execute(
            "SELECT 1 FROM ticket_event WHERE work_item_id = ? AND actor = 'workflow:W_WARD/E_WARD'",
            (ward_2,)).fetchone())

    def test_a_p1_fires_at_the_moment_it_is_created(self):
        self._rule("W_P1", [("E_P1", "ON_CREATE", [("TICKET.PRIORITY", "EQ", "P1")],
                             [("NOTIFY", "SERVICE_MANAGER", None, "P1 raised")],
                             ("ONCE", None, None, None))])
        p1 = self._open(min_priority="P1")
        self._open()                                      # a P4: no page
        rows = self.conn.execute("SELECT work_item_id, recipient, subject FROM notification").fetchall()
        self.assertEqual([(r[0], r[1]) for r in rows], [(p1, "mgr")])
        self.assertIn(f"[{p1}]", rows[0][2])              # the token a reply threads on
        self.assertIsNotNone(self.conn.execute(
            "SELECT 1 FROM ticket_event WHERE work_item_id = ? AND kind = 'NOTIFY'"
            " AND actor = 'workflow:W_P1/E_P1'", (p1,)).fetchone())

    def test_escalation_is_successive_events_on_sla_time(self):
        """The reference PSA's own pattern: New too long tells dispatch; later still,
        the service manager."""
        self._rule("W_ESC", [
            ("E_50", "ON_SLA_THRESHOLD", [("TICKET.ESCALATION", "EQ", "NOT_RESPONDED"),
                                          ("TICKET.SLA_PERCENT", "GTE", "50")],
             [("NOTIFY", "DISPATCH", None, "half the respond time gone")], ("ONCE", None, None, None)),
            ("E_100", "ON_SLA_THRESHOLD", [("TICKET.ESCALATION", "EQ", "NOT_RESPONDED"),
                                           ("TICKET.SLA_PERCENT", "GTE", "100")],
             [("ESCALATE", "SERVICE_MANAGER", None, "respond target missed")],
             ("ONCE", None, None, None))])
        wid = self._open()                                # P4: respond target 480 min
        target = setup.STARTER_TARGETS["P4"][0]
        self.wf.sweep(self.conn, at=self.at + timedelta(minutes=target * 0.3))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM notification").fetchone()[0], 0)
        self.wf.sweep(self.conn, at=self.at + timedelta(minutes=target * 0.6))
        self.wf.sweep(self.conn, at=self.at + timedelta(minutes=target * 0.7))   # once only
        self.assertEqual([r[0] for r in self.conn.execute("SELECT recipient FROM notification")],
                         ["disp"])
        self.wf.sweep(self.conn, at=self.at + timedelta(minutes=target + 5))
        self.assertEqual([r[0] for r in self.conn.execute(
            "SELECT recipient FROM notification ORDER BY notification_id")], ["disp", "mgr"])
        self.assertTrue(wid)

    def test_a_rules_own_status_change_fires_no_further_rules(self):
        progress = setup.status_id("IT_HELP", "In Progress")
        self._rule("W_LOOP", [("E_A", "ON_CREATE", [], [("SET_STATUS", None, progress, "start")],
                               ("ONCE", None, None, None)),
                              ("E_B", "ON_STATUS_CHANGE", [], [("ADD_NOTE", None, None, "loop?")],
                               ("CONTINUOUSLY", 1, "MINUTES", None))])
        wid = self._open()
        self.assertEqual(self.conn.execute("SELECT board_status_id FROM ticket WHERE"
                                           " work_item_id = ?", (wid,)).fetchone()[0], progress)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM workflow_run WHERE"
                                           " event_id = 'E_B'").fetchone()[0], 0)

    def test_a_failing_action_leaves_nothing_half_done(self):
        self._rule("W_BAD", [("E_BAD", "ON_CREATE", [],
                              [("ADD_NOTE", None, None, "first"),
                               ("NOTIFY", "ON_CALL", None, "nobody is on call")],
                              ("ONCE", None, None, None))])
        wid = self._open()                                # the ticket itself stands
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM ticket_event WHERE"
                                           " work_item_id = ? AND detail = 'first'",
                                           (wid,)).fetchone()[0], 0)
        run = self.conn.execute("SELECT outcome, detail FROM workflow_run WHERE"
                                " event_id = 'E_BAD'").fetchall()
        self.assertEqual([r[0] for r in run], ["ERROR"])
        self.assertIn("no one holds that role", run[0][1])


class OutboxTest(unittest.TestCase):
    """024 notification outbox and psaspine.outbox: only resolvable, in-domain
    addresses are released; nothing sits PENDING for ever; a preview changes nothing."""

    def setUp(self) -> None:
        from psaspine import outbox
        self.outbox = outbox
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.conn.execute(
            "INSERT INTO contact (contact_id, entity_id, display_name, email, sam_account, source,"
            " inactive, created_at) VALUES ('CT-1','PMC','Dada','dada@pmcne.ph','dada','MANUAL',0,'2026')")
        for who in ("dada", "mgr@pmcne.ph", "someone@gmail.com", "ghost"):
            self.conn.execute("INSERT INTO notification (recipient, subject, body, created_at)"
                              " VALUES (?, '[PMC-000001] Escalate: P1 on IT_HELP', 'x', '2026')", (who,))
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_only_resolvable_in_domain_addresses_are_released(self):
        preview = self.outbox.pending(self.conn, allowed_domains=("pmcne.ph",), dry_run=True)
        self.assertEqual(sorted(i["to"] for i in preview), ["dada@pmcne.ph", "mgr@pmcne.ph"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM notification WHERE status ="
                                           " 'PENDING'").fetchone()[0], 4)   # preview: untouched
        due = self.outbox.pending(self.conn, allowed_domains=("pmcne.ph",))
        self.assertEqual(len(due), 2)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM notification WHERE status ="
                                           " 'NO_SENDER'").fetchone()[0], 2)  # gmail and ghost
        self.assertTrue(self.outbox.mark(self.conn, due[0]["id"], "SENT", at=datetime(2026, 9, 23)))
        self.assertFalse(self.outbox.mark(self.conn, due[0]["id"], "SENT", at=datetime(2026, 9, 23)))


class NotificationSenderScriptTest(unittest.TestCase):
    """scripts/Send-PmcNotifications.ps1: ASCII, certificate not secret, preview
    unless -Apply, domain checked again before sending, counts-only logs."""

    SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "Send-PmcNotifications.ps1"

    def setUp(self) -> None:
        self.text = self.SCRIPT.read_bytes().decode("ascii")

    def test_it_holds_no_secret(self):
        lowered = self.text.lower()
        for shape in ("client_secret", "password", "convertto-securestring", "apikey"):
            self.assertNotIn(shape, lowered, shape)
        self.assertIn("client-assertion-type:jwt-bearer", self.text)

    def test_nothing_is_sent_without_apply(self):
        self.assertLess(self.text.index("if (-not $Apply) {"), self.text.index("Send-One $item"))
        self.assertIn("'--dry-run'", self.text)

    def test_the_domain_is_checked_again_before_sending(self):
        self.assertLess(self.text.index("EndsWith('@' + $AllowedDomain"),
                        self.text.index("Send-One $item"))

    def test_logs_carry_no_address_or_subject(self):
        for line in self.text.splitlines():
            if "Write-Log" in line and "function" not in line:
                self.assertNotIn("$item.to", line)
                self.assertNotIn("$item.subject", line)

    def test_it_sends_only_as_mailbox_or_send_as(self):
        # 058: the desk names the address a requester wrote to; the script sends
        # as it only when it is -Mailbox or in -SendAs, else as -Mailbox.
        self.assertIn("[string[]] $SendAs = @()", self.text)
        self.assertIn("if ($from -and ($script:Senders -contains $from)) { return $from }", self.text)
        self.assertIn("$mbx = [Uri]::EscapeDataString((Get-SenderFor $Item))", self.text)
        self.assertEqual(self.text.count("/sendMail"), 1)


class TeamsSenderScriptTest(unittest.TestCase):
    """scripts/Send-PsaTeamsNotifications.ps1 and its siblings, after SQL01's
    part 21 measured three defects under Windows PowerShell 5.1 on the host."""

    SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

    def _text(self, name):
        return (self.SCRIPTS / name).read_bytes().decode("ascii")

    def test_a_teams_workflows_webhook_is_allowed_and_nothing_else_is(self):
        text = self._text("Send-PsaTeamsNotifications.ps1")
        self.assertIn("EndsWith('.api.powerplatform.com')", text)               # (a) the shape made today
        self.assertIn("$u.Scheme -ne 'https'", text)
        self.assertLess(text.index("function Test-WebhookUrl"), text.index("Send-Card $item $url"))

    def test_no_script_reads_psscriptroot_in_a_param_default(self):
        for name in ("Send-PsaTeamsNotifications.ps1", "Send-PmcNotifications.ps1", "Invoke-PmcMailPickup.ps1"):
            text = self._text(name)
            head = text[:text.index("Set-StrictMode")]                          # the param() block and the help
            self.assertNotIn("$PSScriptRoot", head, name)                        # (b) empty under 5.1 -File
            self.assertIn("$MyInvocation.MyCommand.Path", text, name)

    def test_no_format_string_carries_a_variable_and_no_local_shadows_a_parameter(self):
        # SQL01, part 27: the pickup put $Database into a -f format string, so an
        # ODBC connection string's {ODBC Driver 17 for SQL Server} was read as a
        # placeholder and threw before sign-in; and a local $since overwrote the
        # [datetime] $Since parameter (PowerShell names ignore case). Every script.
        import re
        for path in sorted(self.SCRIPTS.glob("*.ps1")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'\("((?:[^"`]|`.)*)"\s*-f\b', text, re.S):
                self.assertNotIn("$", m.group(1), f"{path.name}: a variable inside a -f format string")
            block = re.search(r"param\s*\((.*?)\n\)", text, re.S)
            params = set(re.findall(r"\$(\w+)", block.group(1))) if block else set()
            for m in re.finditer(r"^\s*\$(\w+)\s*=", text, re.M):
                for p in params:
                    self.assertFalse(m.group(1).lower() == p.lower() and m.group(1) != p,
                                     f"{path.name}: ${m.group(1)} overwrites the parameter ${p}")

    def test_the_mail_tasks_hold_support_back_and_preview_first(self):
        # 058's cut-over: Register-PsaMail.ps1 registers helpdesk@ and the sender;
        # support@ only with -IncludeSupport (after PCSD stops reading it).
        text = self._text("Register-PsaMail.ps1")
        self.assertIn("if (-not $Apply) { Write-Step 'RESULT: preflight PASS. Nothing was changed", text)
        self.assertLess(text.index("if (-not $Apply)"), text.index("Register-ScheduledTask @reg"))
        self.assertIn("$(if ($IncludeSupport) { @('PSA-Mail-Support') } else { @() })", text)
        self.assertIn("-SendAs 'support@pmcne.ph'", text)
        for shape in ("client_secret", "convertto-securestring", "Write-Host $thumb", "Write-Step ($thumb"):
            self.assertNotIn(shape, text.lower() if shape.islower() else text)

    def test_an_idle_pass_counts_zero_on_windows_powershell(self):
        for name in ("Send-PsaTeamsNotifications.ps1", "Send-PmcNotifications.ps1"):
            text = self._text(name)
            self.assertNotIn("@($r.Out | ConvertFrom-Json)", text, name)       # (c) one element on 5.1
            self.assertIn("foreach ($x in ($r.Out | ConvertFrom-Json))", text, name)


class TasksTemplatesTest(unittest.TestCase):
    """026 and psaspine.tasks: a ticket's checklist, and board templates."""

    def setUp(self) -> None:
        from psaspine import tasks
        self.tasks = tasks
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 23, 9, 0)
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)
        self.tpl = tasks.save_template(
            self.conn, board_id="IT_HELP", name="New starter", actor="lead", at=self.at,
            summary="New starter: account and badge", record_type="SERVICE_REQUEST",
            task_lines=["Create the AD account", "", "Add to HIS roles", "Issue the badge"])

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_a_ticket_from_a_template_has_its_type_summary_and_checklist(self):
        wid = self.tasks.open_from_template(self.conn, self.tpl, impact="I3", urgency="U3",
                                            requested_by=None, at=self.at, actor="t")
        row = self.conn.execute("SELECT t.record_type, w.name FROM ticket t JOIN work_item w"
                                " ON w.work_item_id = t.work_item_id WHERE t.work_item_id = ?", (wid,)).fetchone()
        self.assertEqual(tuple(row), ("SERVICE_REQUEST", "New starter: account and badge"))
        self.assertEqual([r["text"] for r in self.tasks.tasks_of(self.conn, wid)],
                         ["Create the AD account", "Add to HIS roles", "Issue the badge"])
        self.assertEqual(self.tasks.apply_template(self.conn, wid, self.tpl, actor="t", at=self.at), 0)

    def test_ticking_a_task_records_who_and_unticking_says_so(self):
        wid = self.tasks.open_from_template(self.conn, self.tpl, impact="I3", urgency="U3",
                                            requested_by=None, at=self.at, actor="t")
        first = self.tasks.tasks_of(self.conn, wid)[0]["task_id"]
        self.tasks.set_done(self.conn, first, True, actor="alice", at=self.at)
        self.assertEqual(self.tasks.progress(self.conn, wid), (1, 3))
        self.tasks.set_done(self.conn, first, False, actor="alice", at=self.at)
        details = [r[0] for r in self.conn.execute(
            "SELECT detail FROM ticket_event WHERE work_item_id = ? AND kind = 'TASK'", (wid,))]
        self.assertEqual(details, ["task done: Create the AD account",
                                   "task reopened: Create the AD account"])

    def test_a_template_type_must_be_one_the_board_takes(self):
        from psaspine import itil
        with self.assertRaises(itil.NotAccepted):
            self.tasks.save_template(self.conn, board_id="IT_HELP", name="Change", actor="t",
                                     at=self.at, record_type="CHANGE")

    def test_a_workflow_rule_can_apply_a_template(self):
        from psaspine import workflow
        workflow.ensure_vocabulary(self.conn)
        self.conn.execute("INSERT INTO workflow (workflow_id, board_id, name, table_type) VALUES"
                          " ('W', 'IT_HELP', 'Starter checklist', 'TICKET')")
        self.conn.execute("INSERT INTO workflow_event (event_id, workflow_id, fires_on) VALUES"
                          " ('E', 'W', 'ON_CREATE')")
        self.conn.execute("INSERT INTO workflow_condition (event_id, trigger_id, operator, value)"
                          " VALUES ('E', 'TICKET.RECORD_TYPE', 'EQ', 'SERVICE_REQUEST')")
        self.conn.execute("INSERT INTO workflow_action (event_id, action, target_template_id)"
                          " VALUES ('E', 'APPLY_TEMPLATE', ?)", (self.tpl,))
        workflow.test_event(self.conn, "E", at=self.at)
        workflow.activate(self.conn, "W", actor="t", at=self.at)
        wid = tickets.open_ticket(self.conn, board_id="IT_HELP", summary="New nurse starts Monday",
                                  impact="I3", urgency="U3", requested_by=None, at=self.at,
                                  record_type="SERVICE_REQUEST")
        self.assertEqual(self.tasks.progress(self.conn, wid), (0, 3))


def _png(width=64, height=64, *, text=b"Author\x00C:\\Users\\alice"):
    """A real PNG, deliberately badly packed (deflate level 0) and carrying a
    tEXt chunk, which is what an unoptimised screenshot tool writes."""
    import struct as _struct
    import zlib as _zlib
    raw = b"".join(b"\x00" + bytes((x * 4) % 256 for x in range(width)) * 3
                   for _ in range(height))

    def chunk(kind, body):
        return (_struct.pack(">I", len(body)) + kind + body
                + _struct.pack(">I", _zlib.crc32(kind + body)))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", _struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"tEXt", text)
            + chunk(b"IDAT", _zlib.compress(raw, 0)) + chunk(b"IEND", b""))


def _jpeg():
    """The marker structure of a phone photo: JFIF, then EXIF with a GPS block,
    a comment, a quantisation table and the scan."""
    import struct as _struct

    def seg(marker, body):
        return b"\xff" + bytes([marker]) + _struct.pack(">H", len(body) + 2) + body
    return (b"\xff\xd8" + seg(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
            + seg(0xE1, b"Exif\x00\x00GPS 14.5995N 120.9842E serial X123")
            + seg(0xFE, b"taken by alice") + seg(0xDB, b"\x00" + bytes(range(64)))
            + seg(0xDA, b"\x01\x01\x00\x00\x3f\x00") + b"\x12\x34\x56\xff\x00\x78"
            + b"\xff\xd9")


class AttachmentsTest(unittest.TestCase):
    """027 and psaspine.attachments: kept outside the database, compressed by
    kind and losslessly, and every file waits for a patient-information review."""

    def setUp(self) -> None:
        from psaspine import attachments
        self.att = attachments
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = _target(self.tmp)
        self.conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 23, 9, 0)
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)
        self.wid = tickets.open_ticket(self.conn, board_id="IT_HELP", summary="Printer",
                                       impact="I3", urgency="U3", requested_by=None, at=self.at)

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_a_png_is_repacked_losslessly_and_loses_its_text_chunks(self):
        import zlib as _zlib
        original = _png()
        slim = self.att.optimise_png(original)
        self.assertLess(len(slim), len(original) // 4)
        self.assertNotIn(b"tEXt", slim)
        self.assertNotIn(b"alice", slim)

        def pixels(data):
            return _zlib.decompress(b"".join(b for k, b in self.att._png_chunks(data) if k == b"IDAT"))
        self.assertEqual(pixels(slim), pixels(original))
        self.assertEqual(self.att.sniff(slim), "image/png")

    def test_an_animated_or_damaged_png_is_kept_as_sent(self):
        import struct as _struct
        import zlib as _zlib
        png = _png()
        actl = b"acTL" + b"\x00" * 8
        animated = png[:33] + _struct.pack(">I", 8) + actl + _struct.pack(">I", _zlib.crc32(actl)) + png[33:]
        self.assertEqual(self.att.optimise_png(animated), animated)
        self.assertEqual(self.att.optimise_png(png[:60]), png[:60])

    def test_a_jpeg_loses_exif_and_comments_and_keeps_its_scan_bit_for_bit(self):
        photo = _jpeg()
        slim = self.att.strip_jpeg(photo)
        self.assertNotIn(b"GPS", slim)
        self.assertNotIn(b"alice", slim)
        self.assertIn(b"JFIF", slim)
        scan = photo[photo.index(b"\xff\xda"):]
        self.assertTrue(slim.endswith(scan))

    def test_text_is_gzipped_and_served_back_identical(self):
        log = ("2026-09-23 09:00 spooler restarted on PRN-WARD3\n" * 400).encode()
        info = self.att.add(self.conn, self.wid, log, "spooler.log", actor="alice", at=self.at)
        self.assertEqual(info["media_type"], "text/plain")
        self.assertLess(info["size_stored"], len(log) // 10)
        row, data = self.att.read(self.conn, info["attachment_id"])
        self.assertEqual(data, log)
        self.assertEqual((row["encoding"], row["review_status"]), ("GZIP", "PENDING"))

    def test_what_the_desk_will_not_keep_is_refused_by_content_not_name(self):
        for data, name in ((b"MZ\x90\x00" + b"\x00" * 60, "invoice.pdf"),
                           (b"PK\x03\x04" + b"\x00" * 60, "logs.zip"),
                           (b"<html><script>x()</script></html>", "note.txt"),
                           (b"#!/bin/sh\nrm -rf /\n", "readme.txt"),
                           (b"Write-Host hi", "fix.ps1"),
                           (bytes(range(256)) * 4, "blob.dat"),
                           (b"\x00\x01" * 50, "utf16-without-bom.txt"),
                           (b"", "empty.txt")):
            with self.subTest(name=name), self.assertRaises(self.att.Refused):
                self.att.add(self.conn, self.wid, data, name, actor="a", at=self.at)
        with self.assertRaises(self.att.Refused):
            self.att.add(self.conn, self.wid, b"a" * (self.att.MAX_BYTES + 1), "big.txt",
                         actor="a", at=self.at)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM attachment").fetchone()[0], 0)

    def test_the_same_file_twice_is_stored_once_and_tampering_is_caught(self):
        a = self.att.add(self.conn, self.wid, _png(), "shot.png", actor="a", at=self.at)
        b = self.att.add(self.conn, self.wid, _png(), "shot again.png", actor="b", at=self.at)
        self.assertEqual(a["sha256"], b["sha256"])
        stored = [p for p in self.att.store_dir(self.conn).rglob("*") if p.is_file()]
        self.assertEqual(len(stored), 1)
        stored[0].write_bytes(b"not the file")
        with self.assertRaises(IOError):
            self.att.read(self.conn, a["attachment_id"])

    def test_withholding_a_file_flags_the_ticket_for_patient_information(self):
        info = self.att.add(self.conn, self.wid, _png(), "his-screen.png", actor="a", at=self.at)
        self.att.review(self.conn, info["attachment_id"], "WITHHELD", actor="lead", at=self.at)
        dq = self.conn.execute("SELECT code, subject_id FROM data_quality"
                               " WHERE code = 'PHI_IN_ATTACHMENT'").fetchone()
        self.assertEqual(tuple(dq), ("PHI_IN_ATTACHMENT", self.wid))
        self.assertTrue(self.conn.execute("SELECT 1 FROM audit_event WHERE action ="
                                          " 'ATTACHMENT_WITHHELD'").fetchone())
        with self.assertRaises(ValueError):
            self.att.review(self.conn, info["attachment_id"], "MAYBE", actor="lead", at=self.at)

    def test_email_attachments_land_on_the_ticket_and_refusals_are_recorded(self):
        from email.message import EmailMessage
        drop = Path(self.tmp.name) / "drop"
        drop.mkdir()
        m = EmailMessage()
        m["From"] = "nurse@pmcne.ph"
        m["Subject"] = "Scanner error"
        m["Message-ID"] = "<att1@pmcne.ph>"
        m["Date"] = "Wed, 23 Sep 2026 08:00:00 +0800"
        m.set_content("See the screenshot.")
        m.add_attachment(_png(), maintype="image", subtype="png", filename="error.png")
        m.add_attachment(b"MZ" + b"\x00" * 100, maintype="application", subtype="octet-stream",
                         filename="fix.exe")
        m.add_attachment(("x" * 3000).encode(), maintype="text", subtype="plain",
                         filename="trace.txt")
        (drop / "001.eml").write_bytes(bytes(m))
        c = intake.import_drop(self.conn, drop, run_id="m1", board_id="IT_HELP", at=self.at)
        self.assertEqual((c["new"], c["files_kept"], c["files_refused"]), (1, 2, 1))
        wid = self.conn.execute("SELECT work_item_id FROM intake_message").fetchone()[0]
        rows = self.conn.execute("SELECT filename, source FROM attachment WHERE work_item_id = ?"
                                 " ORDER BY attachment_id", (wid,)).fetchall()
        self.assertEqual([tuple(r) for r in rows], [("error.png", "EMAIL"), ("trace.txt", "EMAIL")])
        self.assertTrue(self.conn.execute("SELECT 1 FROM data_quality WHERE code ="
                                          " 'ATTACHMENT_REFUSED' AND detail LIKE 'fix.exe%'").fetchone())
        # The text/plain attachment is a file, not the ticket's description.
        texts = [r[0] or "" for r in self.conn.execute(
            "SELECT detail FROM ticket_event WHERE work_item_id = ?", (wid,))]
        self.assertIn("See the screenshot.", texts)
        self.assertFalse(any("xxxx" in x for x in texts))


class AttachmentRetentionTest(unittest.TestCase):
    """028: what the store holds, whether it is whole, and removing files under
    a retention rule that previews first and refuses over a broken store."""

    def setUp(self) -> None:
        from psaspine import attachments
        self.att = attachments
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = _target(self.tmp)
        self.conn = _fresh(self.tmp)
        self.store = (Path(os.environ["PSA_ATTACHMENT_DIR"]) if TEST_DB
                      else Path(str(self.db_path) + ".attachments"))
        self.at = datetime(2026, 9, 23, 9, 0)
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _ticket(self, *, at=None):
        return tickets.open_ticket(self.conn, board_id="IT_HELP", summary="Printer", impact="I3",
                                   urgency="U3", requested_by=None, at=at or self.at)

    def _close(self, wid, at):
        board.change_status(self.conn, wid, "IT_HELP.CLOSED", at=at, actor="alice")

    def _add(self, wid, data, name, at=None):
        return self.att.add(self.conn, wid, data, name, actor="alice", at=at or self.at)

    def _purge(self, at, **kw):
        kw.setdefault("withheld_days", 30)
        kw.setdefault("closed_days", 730)
        return self.att.purge(self.conn, at=at, **kw)

    def _files(self):
        return sorted(p.name for p in self.store.rglob("*") if p.is_file())

    def test_usage_counts_rows_by_month_and_board_and_files_once_on_disk(self):
        a, b = self._ticket(), self._ticket(at=datetime(2026, 10, 2, 9, 0))
        self._add(a, _png(), "one.png")
        self._add(b, _png(), "same.png", at=datetime(2026, 10, 2, 9, 0))
        self._add(b, b"log line\n" * 100, "b.log", at=datetime(2026, 10, 2, 9, 0))
        u = self.att.usage(self.conn)
        self.assertEqual([(r["month"], r["board_id"], r["files"]) for r in u["rows"]],
                         [("2026-09", "IT_HELP", 1), ("2026-10", "IT_HELP", 2)])
        self.assertEqual((u["totals"]["live"], u["totals"]["distinct_live"], u["disk"]["files"]),
                         (3, 2, 2))
        self.assertLess(u["disk"]["bytes"], u["totals"]["received"])

    def test_verify_sees_a_missing_file_an_orphan_and_a_corrupt_one(self):
        wid = self._ticket()
        info = self._add(wid, b"trace\n" * 200, "t.log")
        self.assertEqual(self.att.verify(self.conn)["missing"], [])
        stored = self.store / info["sha256"][:2] / info["sha256"][2:4] / info["sha256"]
        stored.write_bytes(b"garbage")
        self.assertEqual(self.att.verify(self.conn, check_hashes=True)["mismatched"], [info["sha256"]])
        stored.unlink()
        self.assertEqual(self.att.verify(self.conn)["missing"], [info["sha256"]])
        orphan = self.store / "ab" / "cd" / ("ab" + "c" * 62)
        orphan.parent.mkdir(parents=True)
        orphan.write_bytes(b"nobody points here")
        v = self.att.verify(self.conn)
        self.assertEqual((v["orphans"], v["recent_unindexed"]), ([], 1))   # just written: grace
        later = _time.time() + self.att.ORPHAN_GRACE_SECONDS + 1
        self.assertEqual(self.att.verify(self.conn, now=later)["orphans"], [orphan.name])

    def test_a_missing_file_is_recorded_as_gone_by_a_person_not_by_the_purge(self):
        wid = self._ticket()
        info = self._add(wid, b"trace\n" * 200, "t.log")
        (self.store / info["sha256"][:2] / info["sha256"][2:4] / info["sha256"]).unlink()
        with self.assertRaises(RuntimeError):
            self._purge(datetime(2030, 1, 1))
        n = self.att.record_missing(self.conn, self.att.verify(self.conn)["missing"],
                                    actor="ops", at=self.at)
        self.assertEqual(n, 1)
        row = self.conn.execute("SELECT purge_reason FROM attachment").fetchone()
        self.assertEqual(row[0], "MISSING")
        with self.assertRaises(self.att.Removed):
            self.att.read(self.conn, info["attachment_id"])
        self.assertEqual(self._purge(datetime(2030, 1, 1))["due"], 0)

    def test_purge_previews_then_removes_withheld_and_closed_files_keeping_the_rows(self):
        old, live = self._ticket(), self._ticket()
        w = self._add(old, _png(), "his.png")
        self.att.review(self.conn, w["attachment_id"], "WITHHELD", actor="lead",
                        at=datetime(2026, 9, 24, 9, 0))
        c = self._add(old, b"closed ticket log\n" * 50, "closed.log")
        shared = self._add(old, b"same bytes on two tickets\n" * 50, "shared-a.txt")
        self._add(live, b"same bytes on two tickets\n" * 50, "shared-b.txt")
        self._close(old, datetime(2026, 10, 1, 9, 0))

        soon = datetime(2026, 10, 30, 9, 0)                   # 36 days after the review
        plan = self._purge(soon)
        self.assertFalse(plan["applied"])
        self.assertEqual((plan["due"], plan["by_reason"]), (1, {"WITHHELD": 1, "CLOSED": 0}))
        self.assertEqual(len(self._files()), 3)                # preview changed nothing
        self.assertIsNone(self.conn.execute("SELECT purged_at FROM attachment WHERE"
                                            " attachment_id = ?", (w["attachment_id"],)).fetchone()[0])

        done = self._purge(soon, apply=True)
        self.assertEqual((done["files_removed"], done["bytes_freed"] > 0), (1, True))
        self.assertNotIn(w["sha256"], self._files())
        with self.assertRaises(self.att.Removed):
            self.att.read(self.conn, w["attachment_id"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM attachment").fetchone()[0], 4)

        later = datetime(2028, 10, 2, 9, 0)                   # 731 days after closing
        plan = self._purge(later)
        self.assertEqual((plan["due"], plan["by_reason"]["CLOSED"], plan["files_to_free"]),
                         (2, 2, 1))                            # the shared file stays: live points at it
        done = self._purge(later, apply=True)
        self.assertEqual(done["files_removed"], 1)
        self.assertNotIn(c["sha256"], self._files())
        self.assertIn(shared["sha256"], self._files())
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM attachment WHERE purged_at IS NULL"
                                           " AND work_item_id = ?", (live,)).fetchone()[0], 1)
        self.assertEqual(self._purge(later, apply=True)["due"], 0)
        events = [r[0] for r in self.conn.execute("SELECT detail FROM ticket_event WHERE"
                                                  " work_item_id = ? AND detail LIKE '%retention%'", (old,))]
        self.assertEqual(len(events), 3)
        self.assertTrue(self.conn.execute("SELECT 1 FROM audit_event WHERE action ="
                                          " 'ATTACHMENT_PURGE'").fetchone())

    def test_a_reopened_ticket_keeps_its_files(self):
        wid = self._ticket()
        self._add(wid, b"keep me\n" * 50, "k.log")
        self._close(wid, datetime(2026, 10, 1, 9, 0))
        board.change_status(self.conn, wid, "IT_HELP.IN_PROGRESS", at=datetime(2026, 10, 5), actor="a")
        self.conn.execute("UPDATE ticket SET closed_at = NULL WHERE work_item_id = ?", (wid,))
        self.assertEqual(self._purge(datetime(2030, 1, 1))["due"], 0)

    def test_purge_refuses_an_unmounted_store_and_bad_periods(self):
        wid = self._ticket()
        self._add(wid, b"x\n" * 50, "x.log")
        import shutil
        shutil.move(str(self.store), str(self.store) + ".away")   # the drive is not there
        with self.assertRaises(RuntimeError):
            self._purge(datetime(2030, 1, 1))
        shutil.move(str(self.store) + ".away", str(self.store))
        with self.assertRaises(ValueError):
            self._purge(datetime(2030, 1, 1), closed_days=0)
        self.assertEqual(self._purge(datetime(2030, 1, 1))["due"], 0)  # nothing closed: nothing due

    def test_the_cli_previews_with_counts_only_and_verify_exits_nonzero_on_a_gap(self):
        import contextlib
        from psaspine.__main__ import main as cli_main
        wid = self._ticket()
        info = self._add(wid, b"CANARY-NAME\n" * 50, "patient-list-CANARY.txt")
        self.att.review(self.conn, info["attachment_id"], "WITHHELD", actor="lead", at=self.at)
        self.conn.commit()
        self.conn.close()
        out = _io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli_main(["attachments-purge", str(self.db_path), "--withheld-days", "30",
                             "--closed-days", "730", "--as-of", "2026-12-01"])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("PREVIEW: 1 file(s) due", text)
        self.assertNotIn("CANARY", text)
        self.assertEqual(len(self._files()), 1)
        out = _io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(cli_main(["attachments-verify", str(self.db_path)]), 0)
            self.assertEqual(cli_main(["attachments-usage", str(self.db_path)]), 0)
        self.assertIn("OK: the store is whole", out.getvalue())
        self.assertIn("1 files (1 live, 1 distinct)", out.getvalue())
        (self.store / info["sha256"][:2] / info["sha256"][2:4] / info["sha256"]).unlink()
        with contextlib.redirect_stdout(_io.StringIO()):
            self.assertEqual(cli_main(["attachments-verify", str(self.db_path)]), 1)
        self.conn = db.connect(self.db_path)


class AttachmentRetentionScriptTest(unittest.TestCase):
    """scripts/Invoke-PmcAttachmentRetention.ps1: ASCII, verify before purge,
    --apply only under -Apply, no default period, counts-only logs."""

    SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "Invoke-PmcAttachmentRetention.ps1"

    def setUp(self) -> None:
        self.text = self.SCRIPT.read_bytes().decode("ascii")

    def test_periods_are_mandatory_and_nothing_is_purged_without_apply(self):
        for name in ("WithheldDays", "ClosedDays"):
            self.assertIn(f"[Parameter(Mandatory = $true)] [int] ${name}", self.text)
        self.assertIn("if ($Apply) { $purgeArgs += '--apply' }", self.text)
        self.assertLess(self.text.index("'attachments-verify'"), self.text.index("'attachments-purge'"))

    def test_it_holds_no_secret_and_logs_no_names(self):
        lowered = self.text.lower()
        for shape in ("client_secret", "password", "convertto-securestring", "apikey"):
            self.assertNotIn(shape, lowered, shape)
        self.assertNotIn("filename", lowered)


class DeskSpeedTest(unittest.TestCase):
    """The board over thousands of tickets: the batched clock path gives the
    same answer as the one-clock path, the calendar's arithmetic gives the same
    answer as walking every day, the table pages, and the server threads."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = _target(self.tmp)
        self.conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 23, 9, 0)
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)
        self.conn.execute("INSERT OR REPLACE INTO board_member (board_id, member, access)"
                          " VALUES ('IT_HELP', 'alice', 'ADMIN')")

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_calendar_arithmetic_matches_walking_every_day(self):
        import random
        rnd = random.Random(7)
        cal = clocks.Calendar({0: (480, 1020), 1: (480, 1020), 2: (480, 1020), 3: (480, 1020),
                               4: (480, 720), 5: (540, 780)},
                              {date(2026, 9, 28), date(2026, 10, 3), date(2026, 12, 25)}, "biz")

        def walked(start, end):
            total, day = 0, start.date()
            while day <= end.date():
                total += cal._day_overlap(day, start, end)
                day += timedelta(days=1)
            return total
        for _ in range(300):
            start = datetime(2026, 9, 1) + timedelta(minutes=rnd.randint(0, 60 * 24 * 60))
            end = start + timedelta(minutes=rnd.randint(-100, 60 * 24 * 200))
            self.assertEqual(cal.working_minutes(start, end), max(walked(start, end), 0)
                             if end > start else 0, (start, end))
        always = clocks.Calendar({d: (0, 1440) for d in range(7)}, set(), "all")
        self.assertTrue(always.round_the_clock)
        self.assertEqual(always.working_minutes(datetime(2026, 1, 1), datetime(2026, 1, 3, 0, 30)),
                         48 * 60 + 30)

    def test_states_many_says_what_state_of_says(self):
        from psaspine.web.views import common
        wids = []
        for i in range(12):
            wid = tickets.open_ticket(self.conn, board_id="IT_HELP", summary=f"t{i}", impact="I2",
                                      urgency="U2", requested_by=None,
                                      at=self.at - timedelta(hours=i * 7))
            if i % 3 == 0:
                board.change_status(self.conn, wid, "IT_HELP.WAITING_ON_REQUESTER",
                                    at=self.at - timedelta(hours=i * 7, minutes=-30), actor="a")
            if i % 4 == 0:
                board.change_status(self.conn, wid, "IT_HELP.CLOSED",
                                    at=self.at + timedelta(hours=3), actor="a")
            wids.append(wid)
        now = datetime(2026, 9, 24, 15, 0)
        many = clocks.states_many(self.conn, wids, as_of=now)
        for wid in wids:
            singles = [clocks.state_of(self.conn, r["clock_id"], as_of=now) for r in
                       self.conn.execute("SELECT clock_id FROM ticket_clock WHERE work_item_id = ?"
                                         " ORDER BY clock_id", (wid,))]
            self.assertEqual(many[wid], singles, wid)
        self.assertEqual(common.clock_states_many(self.conn, wids, now=now)[wids[1]],
                         common.clock_states(self.conn, wids[1], now=now))
        self.assertEqual(clocks.states_many(self.conn, [], as_of=now), {})

    def test_the_board_pages_at_a_hundred_and_filters_in_sql(self):
        from psaspine.web import Config, make_app, auth as webauth
        from psaspine.web.views.board import PAGE
        for i in range(PAGE + 30):
            tickets.open_ticket(self.conn, board_id="IT_HELP", summary=f"Load {i} widget",
                                impact="I3", urgency="U3", requested_by=f"u{i}@pmcne.ph",
                                owner="alice" if i % 2 else None,
                                at=self.at - timedelta(minutes=i))
        self.conn.commit()
        self.conn.close()
        cfg = Config(session_secret=_secrets.token_bytes(32))
        app = make_app(str(self.db_path), config=cfg, clock=lambda: datetime(2026, 9, 24, 9))
        cookie = "psa_session=" + webauth.open_session(webauth.User(id="alice", name="alice"),
                                                       cfg.session_secret)

        def get(query):
            env = {"REQUEST_METHOD": "GET", "PATH_INFO": "/", "SCRIPT_NAME": "", "QUERY_STRING": query,
                   "SERVER_NAME": "t", "SERVER_PORT": "80", "SERVER_PROTOCOL": "HTTP/1.1",
                   "wsgi.version": (1, 0), "wsgi.url_scheme": "http", "wsgi.input": _io.BytesIO(b""),
                   "wsgi.errors": _io.StringIO(), "wsgi.multithread": False,
                   "wsgi.multiprocess": False, "wsgi.run_once": False, "HTTP_COOKIE": cookie}
            return b"".join(app(env, lambda s, h, e=None: None)).decode()
        first = get("")
        self.assertIn(f"Showing 1–{PAGE} of {PAGE + 30}", first)
        self.assertEqual(first.count("<tr class="), PAGE)
        second = get("page=2")
        self.assertIn(f"Showing {PAGE + 1}–{PAGE + 30} of {PAGE + 30}", second)
        self.assertIn("Previous", second)
        self.assertNotIn("Next ›", second)
        mine = get("owner=me&sort=id&dir=asc")
        self.assertIn("65 ticket(s).", mine)                    # one page: no pager
        self.assertEqual(get("q=Load 7 w").count("<tr class="), 1)
        self.assertIn("No tickets match", get("q=100%"))          # a LIKE wildcard is a character
        self.conn = db.connect(self.db_path)

    def test_the_server_threads_and_the_rule_guard_is_per_thread(self):
        import threading
        from socketserver import ThreadingMixIn
        from psaspine import workflow
        from psaspine.web import server
        self.assertTrue(issubclass(server.ThreadedServer, ThreadingMixIn))
        self.assertTrue(server.ThreadedServer.daemon_threads)
        seen = {}
        workflow._guard.running = True

        def other():
            seen["other"] = workflow._is_running()
        th = threading.Thread(target=other)
        th.start()
        th.join()
        workflow._guard.running = False
        self.assertFalse(seen["other"])


class DeskLookTest(unittest.TestCase):
    """The desk's shell: self-contained by fence (no CDN, no font, no external
    request), one script that only adds, a palette only for the signed-in, and
    the board's select-all without an inline handler."""

    setUp = WebWSGITest.setUp
    tearDown = WebWSGITest.tearDown
    _call = WebWSGITest._call
    _environ = WebWSGITest._environ
    _cookie_for = WebWSGITest._cookie_for

    def test_every_page_is_self_contained(self):
        cookie = self._cookie_for("alice")
        for path in ("/", "/ticket/ITO-1", "/ticket/new", "/admin", "/my", "/login"):
            _, _, body = self._call("GET", path, cookie=None if path == "/login" else cookie)
            for shape in ("<link rel=\"stylesheet\"", "<link rel=stylesheet", "<script src",
                          "@import", "url(http", "fonts.googleapis", "cdn."):
                self.assertNotIn(shape, body, f"{path}: {shape}")
            self.assertNotRegex(body, r"(src|href)=['\"]https?://", path)

    def test_the_shell_carries_the_design_system_and_the_palette_only_when_signed_in(self):
        _, _, signed = self._call("GET", "/", cookie=self._cookie_for("alice"))
        for needle in ("@view-transition", "prefers-reduced-motion", "prefers-color-scheme:dark",
                       "id=\"pal\"", "id=\"theme\"", "data-all", "data-count", "psa-theme",
                       "aria-current=page"):
            self.assertIn(needle, signed, needle)
        self.assertNotIn("onclick", signed)
        _, _, login = self._call("GET", "/login")
        self.assertNotIn("id=\"pal\"", login)
        self.assertIn("@view-transition", login)

    def test_icons_favicon_dialog_and_popover_are_on_the_page(self):
        from psaspine.web import templates
        _, _, board = self._call("GET", "/", cookie=self._cookie_for("alice"))
        _, _, ticket = self._call("GET", "/ticket/ITO-1", cookie=self._cookie_for("alice"))
        self.assertEqual(board.count("<symbol id=\"i-"), len(templates.ICONS))
        self.assertIn('<link rel=icon href="data:image/svg+xml,', board)
        self.assertIn('<dialog id="pal"', board)
        self.assertIn('id="keys" popover', board)
        self.assertGreaterEqual(ticket.count("<use href=#i-"), 12)        # headings and buttons
        self.assertGreaterEqual(board.count("class='tile"), 5)
        self.assertIn("data-density=compact", board)
        for name in set(__import__("re").findall(r'#i-([a-z]+)', board + ticket)):
            self.assertIn(name, templates.ICONS, name)

    def test_the_ticket_side_cards_are_pods_with_a_shipped_order(self):
        import re as _re
        from psaspine.web import templates
        _, _, ticket = self._call("GET", "/ticket/ITO-1", cookie=self._cookie_for("alice"))
        pods = _re.findall(r"data-pod=([a-z]+)", ticket)
        # two columns, each with its shipped order; every card is in one of them
        cols = _re.findall(r"<div class=pods data-col=([a-z]+) data-order='([a-z,]+)'>", ticket)
        self.assertEqual([c for c, _ in cols], ["left", "right"])
        order = [k for _, o in cols for k in o.split(",")]
        self.assertTrue(set(pods) <= set(order), set(pods) - set(order))
        self.assertIn("ticket", pods)
        self.assertIn("stream", pods)                       # the activity stream is a pod too
        self.assertIn("composer", pods)
        self.assertIn("psa-pods", templates.SCRIPT)
        self.assertIn("Reset layout", templates.SCRIPT)
        self.assertIn("Move to the other column", templates.SCRIPT)

    def test_on_a_technicians_phone_the_board_is_a_list_of_cards_and_the_ticket_has_a_quick_bar(self):
        """Gap 5 (29 Sep): the same pages read their width. Under 640 px the
        board row keeps the summary, the priority and the clocks and folds the
        rest into a line; a fixed bar at the foot of the ticket reaches the
        board, the note, the ticket card and a call to the contact; a coarse
        pointer gets 40 px controls. None of it exists on a desk."""
        from psaspine.web import templates
        css = templates.STYLE
        self.assertIn("@media (pointer:coarse){button,.btn,.iconbtn,select,input:not([type=checkbox]):not([type=radio]){min-height:40px}", css)
        self.assertIn("@media (max-width:640px){", css)
        for rule in (".sm-hide{display:none!important}.sm-only{display:block}", "input,select,textarea{font-size:16px}",
                     ".quick{display:flex;position:fixed;left:0;right:0;bottom:0;", "main{padding:12px 10px 84px}",
                     "form.toolbar{display:grid;grid-template-columns:1fr 1fr;", ".tablewrap>table:not(.cards){min-width:720px}"):
            self.assertIn(rule, css, rule)
        self.assertIn(".sm-only{display:none} .quick{display:none}", css)     # off until the width says so
        alice = self._cookie_for("alice")
        _, _, board_page = self._call("GET", "/", cookie=alice)
        self.assertIn("<th class='sort sm-hide'><a", board_page)                 # the id column folds
        self.assertIn("<td class=sm-hide><a href='/ticket/ITO-1'>ITO-1</a></td>", board_page)
        self.assertRegex(board_page, r"<div class='sm-only meta'>ITO-1 · [^<]+ · [^<]+ · [^<]+</div>")
        self.assertNotIn("<th class='sort sm-hide'><a href='[^']*sort=summary", board_page)
        self.assertIn("<div class=wide style='flex:1'><label>Search</label>", board_page)
        self.assertIn("<table class='grid cards'><thead>", board_page)
        sections = re.search(r"<nav class=quick aria-label='Sections'>(.*?)</nav>", board_page).group(1)
        self.assertEqual(re.findall(r"href='([^']+)'", sections), ["/", "/dispatch", "/schedule", "/time", "/ticket/new"])
        self.assertIn("<span class=sep> · </span><a href=\"/logout\">sign out</a>", board_page)
        self.assertIn("header.top nav a .lbl,header.top nav a.on .lbl{display:none}", css)   # the active label too
        self.assertIn("table.grid.cards tr{display:grid;", css)
        conn = db.connect(self.db_path)
        conn.execute("INSERT INTO contact (contact_id, entity_id, display_name, email, phone, source, inactive, created_at)"
                     " VALUES ('C_PH', 'PMC', 'Ward Clerk', 'clerk@pmcne.ph', '(02) 8123 4567 loc. 301', 'AD', 0, '2026-09-17 08:00')")
        conn.execute("UPDATE ticket SET contact_id = 'C_PH' WHERE work_item_id = 'ITO-1'")
        conn.commit()
        conn.close()
        _, _, ticket = self._call("GET", "/ticket/ITO-1", cookie=alice)
        self.assertIn("<div class=card data-pod=composer id=composer>", ticket)
        self.assertIn("<div class='card fields' data-pod=ticket id=ticketcard>", ticket)
        quick = re.search(r"<nav class=quick aria-label='Quick actions'>(.*?)</nav>", ticket).group(1)
        self.assertEqual(re.findall(r"href='([^']+)'", quick), ["/", "/ticket/ITO-1#composer", "/ticket/ITO-1#ticketcard", "tel:+0281234567301".replace("+", "")])
        self.assertEqual(ticket.count("<nav class=quick"), 1)
        _, _, read_only = self._call("GET", "/ticket/ITO-1", cookie=self._cookie_for("carol"))   # READ: no note, no card
        self.assertEqual(re.findall(r"href='([^']+)'", re.search(r"<nav class=quick[^>]*>(.*?)</nav>", read_only).group(1)),
                         ["/", "tel:0281234567301"])
        _, _, portal = self._call("GET", "/my", cookie=self._cookie_for("nurse", email="nurse@pmcne.ph"))
        self.assertNotIn("class=quick", portal)                                 # the requester's shell has none

    def test_the_script_is_plain_and_escapes_what_it_shows(self):
        from psaspine.web import templates
        # innerHTML only ever takes a string literal; anything from a ticket goes through textContent.
        import re as _re
        self.assertEqual(_re.findall(r"innerHTML=(?![\"'])\S{0,20}", templates.SCRIPT), [])
        self.assertIn("textContent", templates.SCRIPT)
        self.assertIn("prefetch", templates.SCRIPT)
        self.assertIn("aria-busy", templates.SCRIPT)


class ChildTicketsTest(unittest.TestCase):
    """030 and psaspine.family: one parent, many children, one level, and the
    children close with the parent, each on its own board."""

    def setUp(self) -> None:
        from psaspine import family
        self.family = family
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = _target(self.tmp)
        self.conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 25, 9, 0)
        for b in ("IT_HELP", "UNROUTED"):
            setup.apply_starter(self.conn, b, actor="t", at=self.at)

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _open(self, board="IT_HELP", who="a@pmcne.ph", **kw):
        return tickets.open_ticket(self.conn, board_id=board, summary="Printer", impact="I3",
                                   urgency="U3", requested_by=who, at=self.at, **kw)

    def test_the_rules_each_refuse_with_a_sentence(self):
        p, c, g = self._open(), self._open(), self._open()
        with self.assertRaises(self.family.Refused):
            self.family.attach(self.conn, p, p, actor="a", at=self.at)
        self.assertTrue(self.family.attach(self.conn, p, c, actor="a", at=self.at))
        self.assertFalse(self.family.attach(self.conn, p, c, actor="a", at=self.at))   # already
        with self.assertRaises(self.family.Refused):                                  # one level
            self.family.attach(self.conn, c, g, actor="a", at=self.at)
        with self.assertRaises(self.family.Refused):                                  # a parent as a child
            self.family.attach(self.conn, g, p, actor="a", at=self.at)
        with self.assertRaises(self.family.Refused):                                  # a loop, the long way
            self.family.attach(self.conn, c, p, actor="a", at=self.at)
        board.change_status(self.conn, g, "IT_HELP.CLOSED", at=self.at, actor="a")
        with self.assertRaises(self.family.Refused):                                  # closed
            self.family.attach(self.conn, p, g, actor="a", at=self.at)
        self.assertEqual([k["work_item_id"] for k in self.family.children_of(self.conn, p)], [c])
        self.assertEqual(self.family.parent_of(self.conn, c)["work_item_id"], p)
        self.assertTrue(self.family.detach(self.conn, c, actor="a", at=self.at))
        self.assertFalse(self.family.detach(self.conn, c, actor="a", at=self.at))
        kinds = [r[0] for r in self.conn.execute("SELECT detail FROM ticket_event WHERE kind = 'CHILD'"
                                                 " AND work_item_id = ? ORDER BY ticket_event_id", (c,))]
        self.assertEqual(kinds, [f"made a child of {p}: closes when it closes", f"detached from parent {p}"])

    def test_closing_the_parent_closes_the_children_each_on_its_own_board(self):
        p = self._open()
        c1, c2 = self._open(who="b@pmcne.ph"), self._open(board="UNROUTED", who="c@pmcne.ph")
        for c in (c1, c2):
            self.family.attach(self.conn, p, c, actor="a", at=self.at)
        # a child that needs approval to close is left open, and says why
        ch = self._open(record_type=None)
        self.family.attach(self.conn, p, ch, actor="a", at=self.at)
        board.change_status(self.conn, ch, "IT_HELP.RESOLVED", at=self.at, actor="a")   # already resolved: skipped
        later = datetime(2026, 9, 25, 12, 0)
        board.change_status(self.conn, p, "IT_HELP.CLOSED", at=later, actor="alice")
        rows = {r[0]: (r[1], r[2]) for r in self.conn.execute(
            "SELECT work_item_id, state, closed_at FROM ticket WHERE work_item_id IN (?,?,?)", (c1, c2, ch))}
        self.assertEqual(rows[c1][0], "CLOSED")
        self.assertEqual(rows[c2][0], "CLOSED")
        self.assertEqual(rows[c1][1], "2026-09-25 12:00")
        self.assertEqual(self.conn.execute("SELECT board_status_id FROM ticket WHERE work_item_id = ?",
                                           (c2,)).fetchone()[0], "UNROUTED.CLOSED")
        self.assertIn(f"closed with parent {p}", [r[0] for r in self.conn.execute(
            "SELECT detail FROM ticket_event WHERE work_item_id = ? AND kind = 'CHILD'", (c1,))])
        summary = self.conn.execute("SELECT detail FROM ticket_event WHERE work_item_id = ? AND kind = 'CHILD'"
                                    " ORDER BY ticket_event_id DESC LIMIT 1", (p,)).fetchone()[0]
        self.assertTrue(summary.startswith("closed with 2 child(ren)"), summary)

    def test_a_child_that_cannot_close_is_left_open_and_the_parent_still_closes(self):
        self.conn.execute("UPDATE board_status SET inactive = 1 WHERE board_status_id = 'UNROUTED.CLOSED'")
        p, c = self._open(), self._open(board="UNROUTED")
        self.family.attach(self.conn, p, c, actor="a", at=self.at)
        board.change_status(self.conn, p, "IT_HELP.CLOSED", at=self.at, actor="a")
        self.assertEqual(self.conn.execute("SELECT state FROM ticket WHERE work_item_id = ?", (p,)).fetchone()[0], "CLOSED")
        self.assertNotEqual(self.conn.execute("SELECT state FROM ticket WHERE work_item_id = ?", (c,)).fetchone()[0], "CLOSED")
        self.assertIn("no closed status; left open", self.conn.execute(
            "SELECT detail FROM ticket_event WHERE work_item_id = ? ORDER BY ticket_event_id DESC LIMIT 1",
            (c,)).fetchone()[0])


class ChildTicketsWebTest(unittest.TestCase):
    """The Children pod, the routes, the board's chips and bulk attach."""

    setUp = WebWSGITest.setUp
    tearDown = WebWSGITest.tearDown
    _call = WebWSGITest._call
    _environ = WebWSGITest._environ
    _cookie_for = WebWSGITest._cookie_for

    def _second(self):
        conn = db.connect(self.db_path)
        conn.executescript(
            "INSERT INTO work_item (work_item_id,source,name,entity_id,contract_basis)"
            " VALUES ('ITO-2','desk','Printer down too','PMC','BASELINE');"
            "INSERT INTO ticket (work_item_id,board_id,path,impact,urgency,priority,priority_source,"
            " requested_at,opened_at,state,board_status_id) VALUES ('ITO-2','IT_HELP','INCIDENT','I3',"
            "'U3','P4','MATRIX','2026-09-17 08:00','2026-09-17 08:00','NEW','IT_HELP.NEW');")
        conn.commit()
        conn.close()

    def test_attach_detach_and_the_board_says_so(self):
        self._second()
        alice = self._cookie_for("alice")
        status, headers, _ = self._call("POST", "/ticket/ITO-1/child/add", cookie=alice,
                                        form={"child_id": "ito-2"})
        self.assertIn("msg=", dict(headers)["Location"])
        _, _, parent = self._call("GET", "/ticket/ITO-1", cookie=alice)
        self.assertIn("Children · 1", parent)
        self.assertIn("href='/ticket/ITO-2'", parent)
        _, _, child = self._call("GET", "/ticket/ITO-2", cookie=alice)
        self.assertIn("Child of", child)
        self.assertIn("Detach from parent", child)
        _, _, boardpage = self._call("GET", "/", cookie=alice)
        self.assertIn("child of ITO-1", boardpage)
        self.assertIn("1 child<", boardpage)
        status, headers, _ = self._call("POST", "/ticket/ITO-1/child/add", cookie=alice,
                                        form={"child_id": "ITO-1"})
        self.assertIn("err=", dict(headers)["Location"])
        status, headers, _ = self._call("POST", "/ticket/ITO-2/parent/remove", cookie=alice, form={"x": "1"})
        self.assertIn("msg=", dict(headers)["Location"])
        # a reader cannot attach; a stranger's ticket cannot be reached
        status, _, _ = self._call("POST", "/ticket/ITO-1/child/add", cookie=self._cookie_for("carol"),
                                  form={"child_id": "ITO-2"})
        self.assertFalse(status.startswith("303"))
        status, headers, _ = self._call("POST", "/ticket/ITO-1/child/add", cookie=alice,
                                        form={"child_id": "ITO-9"})           # PHI board: alice works it, so allowed
        self.assertIn("msg=", dict(headers)["Location"])
        status, headers, _ = self._call("POST", "/ticket/ITO-1/child/add",
                                        cookie=self._cookie_for("bob"), form={"child_id": "ITO-2"})
        self.assertFalse(status.startswith("303"))

    def test_bulk_attach_to_parent_from_the_board(self):
        self._second()
        alice = self._cookie_for("alice")
        status, headers, _ = self._call("POST", "/bulk", cookie=alice,
                                        form=[("ids", "ITO-2"), ("parent", "ito-1"), ("back", "/")])
        self.assertIn("Updated+1", dict(headers)["Location"])
        conn = db.connect(self.db_path)
        self.assertEqual(conn.execute("SELECT parent_id FROM ticket WHERE work_item_id = 'ITO-2'").fetchone()[0], "ITO-1")
        conn.close()


class SearchViewsNotesTest(unittest.TestCase):
    """031: the palette's server search, a person's saved views, a board's
    standard notes."""

    setUp = WebWSGITest.setUp
    tearDown = WebWSGITest.tearDown
    _call = WebWSGITest._call
    _environ = WebWSGITest._environ
    _cookie_for = WebWSGITest._cookie_for

    def test_search_answers_only_from_my_boards_and_audits_a_restricted_hit(self):
        alice, carol = self._cookie_for("alice"), self._cookie_for("carol")
        status, headers, body = self._call("GET", "/search.json", cookie=alice, query="q=sensitive")
        self.assertTrue(status.startswith("200"))
        self.assertEqual(dict(headers)["Content-Type"], "application/json; charset=utf-8")
        j = _json.loads(body)
        self.assertEqual([x["id"] for x in j["tickets"]], ["ITO-9"])
        conn = db.connect(self.db_path)
        self.assertTrue(conn.execute("SELECT 1 FROM audit_event WHERE action = 'RESTRICTED_READ' AND"
                                     " detail LIKE 'search listed 1%'").fetchone())
        conn.close()
        j = _json.loads(self._call("GET", "/search.json", cookie=carol, query="q=sensitive")[2])
        self.assertEqual(j["tickets"], [])                      # carol is not on the PHI board
        j = _json.loads(self._call("GET", "/search.json", cookie=carol, query="q=printer")[2])
        self.assertEqual([x["id"] for x in j["tickets"]], ["ITO-1"])
        j = _json.loads(self._call("GET", "/search.json", cookie=carol, query="q=p")[2])
        self.assertEqual(j["tickets"], [])                      # one letter asks nothing
        status, _, _ = self._call("GET", "/search.json", query="q=printer")
        self.assertTrue(status.startswith("401"))

    def test_a_saved_view_is_mine_named_and_cleaned(self):
        alice = self._cookie_for("alice")
        status, headers, _ = self._call("POST", "/views/save", cookie=alice,
                                        form={"name": "P1 on IT Help", "query": "board=IT_HELP&pri=P1&evil=1&msg=x"})
        self.assertIn("View+saved", dict(headers)["Location"])
        _, _, page = self._call("GET", "/", cookie=alice, query="board=IT_HELP&pri=P1")
        self.assertIn("P1 on IT Help", page)
        self.assertIn("class='stab on'", page)
        self.assertNotIn("evil", page)
        _, _, other = self._call("GET", "/", cookie=self._cookie_for("carol"))
        self.assertNotIn("P1 on IT Help", other)
        conn = db.connect(self.db_path)
        vid, q = conn.execute("SELECT view_id, query FROM user_view").fetchone()
        conn.close()
        self.assertEqual(q, "board=IT_HELP&pri=P1")
        self._call("POST", "/views/delete", cookie=self._cookie_for("carol"), form={"view_id": str(vid)})
        conn = db.connect(self.db_path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM user_view").fetchone()[0], 1)   # not hers to forget
        conn.close()
        self._call("POST", "/views/delete", cookie=alice, form={"view_id": str(vid)})
        conn = db.connect(self.db_path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM user_view").fetchone()[0], 0)
        conn.close()

    def test_a_standard_note_is_set_up_by_an_admin_and_offered_in_the_composer(self):
        alice = self._cookie_for("alice")
        status, headers, _ = self._call("POST", "/admin/board/IT_HELP/standard-note", cookie=alice,
                                        form={"name": "Received", "flag": "DISCUSSION",
                                              "body": "Thank you, we have your request."})
        self.assertIn("saved", dict(headers)["Location"])
        _, _, setup_page = self._call("GET", "/admin/board/IT_HELP", cookie=alice, query="tab=notes")
        self.assertIn("Received", setup_page)
        _, _, ticket_page = self._call("GET", "/ticket/ITO-1", cookie=alice)
        self.assertIn("id=stdnote", ticket_page)
        self.assertIn("data-body='Thank you, we have your request.'", ticket_page)
        status, headers, _ = self._call("POST", "/admin/board/IT_HELP/standard-note", cookie=alice,
                                        form={"name": "", "flag": "DISCUSSION", "body": "x"})
        self.assertIn("Not+saved", dict(headers)["Location"])
        conn = db.connect(self.db_path)
        nid = conn.execute("SELECT note_id FROM standard_note").fetchone()[0]
        conn.close()
        self._call("POST", "/admin/board/IT_HELP/standard-note/toggle", cookie=alice, form={"note_id": str(nid)})
        _, _, ticket_page = self._call("GET", "/ticket/ITO-1", cookie=alice)
        self.assertNotIn("id=stdnote", ticket_page)               # retired: not offered
        status, _, _ = self._call("POST", "/admin/board/IT_HELP/standard-note", cookie=self._cookie_for("carol"),
                                  form={"name": "x", "flag": "INTERNAL", "body": "y"})
        self.assertFalse(status.startswith("303"))


class ReportsTest(unittest.TestCase):
    """metrics.desk and the Reports screen: counts by month, SLA met, medians,
    and a page of charts that is still self-contained."""

    def setUp(self) -> None:
        from psaspine import metrics
        self.metrics = metrics
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = _target(self.tmp)
        self.conn = _fresh(self.tmp)
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=datetime(2026, 7, 1))
        self.conn.execute("INSERT OR REPLACE INTO board_member (board_id, member, access)"
                          " VALUES ('IT_HELP', 'alice', 'ADMIN')")
        # July: two tickets, one closed fast (met) and one closed late (missed);
        # August: one opened, still open. All hours calendar: minutes are minutes.
        a = tickets.open_ticket(self.conn, board_id="IT_HELP", summary="fast", impact="I3", urgency="U3",
                                requested_by=None, at=datetime(2026, 7, 3, 9, 0), source="PHONE")
        board.change_status(self.conn, a, "IT_HELP.CLOSED", at=datetime(2026, 7, 3, 9, 30), actor="x")
        b = tickets.open_ticket(self.conn, board_id="IT_HELP", summary="slow", impact="I3", urgency="U3",
                                requested_by=None, at=datetime(2026, 7, 10, 9, 0), source="EMAIL")
        board.change_status(self.conn, b, "IT_HELP.CLOSED", at=datetime(2026, 7, 30, 9, 0), actor="x")
        tickets.open_ticket(self.conn, board_id="IT_HELP", summary="open", impact="I3", urgency="U3",
                            requested_by=None, at=datetime(2026, 8, 2, 9, 0), source="PORTAL")
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_counts_met_share_and_medians(self):
        m = self.metrics.desk(self.conn, {"IT_HELP"}, now=datetime(2026, 8, 20), months=3)
        self.assertEqual(m["months"], ["2026-06", "2026-07", "2026-08"])
        self.assertEqual((m["opened"]["2026-07"], m["opened"]["2026-08"], m["closed"]["2026-07"]), (2, 1, 2))
        self.assertEqual((m["opened_total"], m["closed_total"], m["backlog"]), (3, 2, 1))
        self.assertEqual(m["resolve_met"]["2026-07"], 50)
        self.assertIsNone(m["resolve_met"]["2026-06"])
        self.assertEqual(m["resolve_met_total"], 50)
        self.assertEqual(m["median_resolve"], (30 + 20 * 24 * 60) // 2)
        self.assertEqual(dict(m["by_source"]), {"PHONE": 1, "EMAIL": 1, "PORTAL": 1})
        self.assertEqual(m["by_board"], [("PMO Helpdesk", 3)])
        self.assertEqual(self.metrics.desk(self.conn, set(), now=datetime(2026, 8, 20))["opened_total"], 0)
        rows = self.metrics.csv_rows(m)
        self.assertEqual(rows[0][0], "month")
        self.assertEqual(rows[2][:3], ["2026-07", 2, 2])

    def test_the_page_draws_charts_and_the_csv_downloads(self):
        from psaspine.web import Config, make_app, auth as webauth
        self.conn.close()
        cfg = Config(session_secret=_secrets.token_bytes(32))
        app = make_app(str(self.db_path), config=cfg, clock=lambda: datetime(2026, 8, 20, 9))
        cookie = "psa_session=" + webauth.open_session(webauth.User(id="alice", name="alice"), cfg.session_secret)

        def get(path, query=""):
            env = {"REQUEST_METHOD": "GET", "PATH_INFO": path, "SCRIPT_NAME": "", "QUERY_STRING": query,
                   "SERVER_NAME": "t", "SERVER_PORT": "80", "SERVER_PROTOCOL": "HTTP/1.1",
                   "wsgi.version": (1, 0), "wsgi.url_scheme": "http", "wsgi.input": _io.BytesIO(b""),
                   "wsgi.errors": _io.StringIO(), "wsgi.multithread": False,
                   "wsgi.multiprocess": False, "wsgi.run_once": False, "HTTP_COOKIE": cookie}
            st = {}
            body = b"".join(app(env, lambda s, h, e=None: st.update(status=s, headers=dict(h)))).decode()
            return st, body
        st, page = get("/reports", "months=3")
        self.assertTrue(st["status"].startswith("200"))
        self.assertGreaterEqual(page.count('<svg class="viz"'), 5)
        self.assertIn("Opened and closed, by month", page)
        self.assertIn("<title>Jul 2026: 2 opened</title>", page)
        self.assertIn("50%", page)
        self.assertNotRegex(page, r"(src|href)=['\"]https?://")
        # Every chart is well-formed XML on its own: an unquoted attribute that
        # ate a "/" once swallowed a whole chart into its first <line>.
        import re as _re
        import xml.etree.ElementTree as _ET
        for frag in _re.findall(r'<svg class="viz".*?</svg>', page, _re.S):
            root = _ET.fromstring(frag)
            self.assertGreaterEqual(len(list(root)), 2)
        st, body = get("/reports.csv", "months=3")
        self.assertEqual(st["headers"]["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("2026-07,2,2,", body)
        self.conn = db.connect(self.db_path)


class MergeScheduleSurveyTest(unittest.TestCase):
    """032: merge a duplicate, book a visit, answer the survey."""

    def setUp(self) -> None:
        from psaspine import family, schedule, survey
        self.family, self.schedule, self.survey = family, schedule, survey
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = _target(self.tmp)
        self.conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 25, 9, 0)
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)
        self.conn.execute("UPDATE board SET notify_requester = 1 WHERE board_id = 'IT_HELP'")

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _open(self, who="a@pmcne.ph", **kw):
        return tickets.open_ticket(self.conn, board_id="IT_HELP", summary="Printer", impact="I3",
                                   urgency="U3", requested_by=who, at=self.at, description="mine", **kw)

    def test_merge_copies_notes_moves_files_and_closes_the_duplicate_quietly(self):
        from psaspine import attachments
        keep, dup = self._open(), self._open(who="b@pmcne.ph")
        board.add_note(self.conn, dup, body="the dup's words", flag="DISCUSSION", actor="alice", at=self.at)
        attachments.add(self.conn, dup, b"log\n" * 50, "d.log", actor="alice", at=self.at)
        kid = self._open(who="c@pmcne.ph")
        self.family.attach(self.conn, dup, kid, actor="alice", at=self.at)
        self.conn.execute("DELETE FROM notification")
        r = self.family.merge(self.conn, dup, keep, actor="alice", at=self.at)
        self.assertEqual((r["notes"], r["files"], r["children"], r["same_requester"]), (2, 1, 1, False))
        row = self.conn.execute("SELECT state, merged_into FROM ticket WHERE work_item_id = ?", (dup,)).fetchone()
        self.assertEqual(tuple(row), ("CLOSED", keep))
        self.assertEqual(self.conn.execute("SELECT parent_id FROM ticket WHERE work_item_id = ?", (kid,)).fetchone()[0], keep)
        self.assertEqual(self.conn.execute("SELECT work_item_id FROM attachment").fetchone()[0], keep)
        copied = self.conn.execute("SELECT detail, note_flag FROM ticket_event WHERE work_item_id = ?"
                                   " AND kind = 'MERGED_NOTE' ORDER BY ticket_event_id", (keep,)).fetchall()
        self.assertEqual([tuple(c) for c in copied], [(f"(from {dup}) mine", "INTERNAL"),
                                                      (f"(from {dup}) the dup's words", "INTERNAL")])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM notification WHERE work_item_id = ?"
                                           " AND recipient_role = 'REQUESTER'", (dup,)).fetchone()[0], 0)
        with self.assertRaises(self.family.Refused):
            self.family.merge(self.conn, keep, dup, actor="alice", at=self.at)        # dup is closed
        with self.assertRaises(self.family.Refused):
            self.family.merge(self.conn, keep, keep, actor="alice", at=self.at)
        same_a, same_b = self._open(), self._open()
        board.add_note(self.conn, same_b, body="same person", flag="DISCUSSION", actor="alice", at=self.at)
        r = self.family.merge(self.conn, same_b, same_a, actor="alice", at=self.at)
        self.assertTrue(r["same_requester"])
        self.assertEqual(self.conn.execute("SELECT note_flag FROM ticket_event WHERE work_item_id = ? AND"
                                           " kind = 'MERGED_NOTE' AND detail LIKE '%same person'",
                                           (same_a,)).fetchone()[0], "DISCUSSION")

    def test_a_visit_is_booked_once_per_person_per_hour_and_shows_on_the_day(self):
        wid, other = self._open(), self._open()
        s = self.schedule
        s.add(self.conn, wid, member="Bob", starts_at=datetime(2026, 9, 26, 10), ends_at=datetime(2026, 9, 26, 11),
              note="Ward 3", actor="alice", at=self.at)
        with self.assertRaises(s.Refused):                                             # Bob is busy
            s.add(self.conn, other, member="bob", starts_at=datetime(2026, 9, 26, 10, 30),
                  ends_at=datetime(2026, 9, 26, 12), note=None, actor="alice", at=self.at)
        with self.assertRaises(s.Refused):
            s.add(self.conn, other, member="Bob", starts_at=datetime(2026, 9, 26, 12), ends_at=datetime(2026, 9, 26, 12),
                  note=None, actor="alice", at=self.at)
        s.add(self.conn, other, member="Bob", starts_at=datetime(2026, 9, 26, 11), ends_at=datetime(2026, 9, 26, 12),
              note=None, actor="alice", at=self.at)
        day = s.day(self.conn, {"IT_HELP"}, "2026-09-26")
        self.assertEqual([(e["work_item_id"], e["starts_at"][11:]) for e in day], [(wid, "10:00"), (other, "11:00")])
        self.assertEqual(s.day(self.conn, {"IT_HELP"}, "2026-09-27"), [])
        self.assertEqual(s.parse_local("2026-09-26T10:30"), datetime(2026, 9, 26, 10, 30))
        with self.assertRaises(s.Refused):
            s.parse_local("tomorrow")
        self.assertEqual(s.remove(self.conn, day[0]["schedule_id"], actor="alice", at=self.at), wid)
        self.assertIn("visit cancelled", self.conn.execute(
            "SELECT detail FROM ticket_event WHERE work_item_id = ? ORDER BY ticket_event_id DESC LIMIT 1",
            (wid,)).fetchone()[0])

    def test_closing_asks_the_requester_and_the_answer_is_one_per_ticket(self):
        wid = self._open()
        self.assertFalse(self.survey.pending(self.conn, wid))
        board.change_status(self.conn, wid, "IT_HELP.CLOSED", at=self.at, actor="alice")
        mail = self.conn.execute("SELECT subject FROM notification WHERE work_item_id = ? ORDER BY notification_id DESC"
                                 " LIMIT 1", (wid,)).fetchone()[0]
        self.assertIn("Your request is closed", mail)
        self.assertTrue(self.survey.pending(self.conn, wid))
        findings = self.survey.answer(self.conn, wid, score=4, comment="Quick, thanks", by="a@pmcne.ph", at=self.at)
        self.assertEqual(findings, [])
        self.assertFalse(self.survey.pending(self.conn, wid))
        with self.assertRaises(ValueError):
            self.survey.answer(self.conn, wid, score=5, comment=None, by="a@pmcne.ph", at=self.at)
        with self.assertRaises(ValueError):
            self.survey.answer(self.conn, self._open(), score=9, comment=None, by="a", at=self.at)
        from psaspine import metrics
        m = metrics.desk(self.conn, {"IT_HELP"}, now=self.at, months=1)
        self.assertEqual((m["satisfaction"], m["satisfaction_n"]), (4.0, 1))
        # a second answer: the average is a fraction on both stores (SQL
        # Server's AVG of an integer column would have said 4)
        other = self._open(who="b@pmcne.ph")
        board.change_status(self.conn, other, "IT_HELP.CLOSED", at=self.at, actor="alice")
        self.survey.answer(self.conn, other, score=5, comment=None, by="b@pmcne.ph", at=self.at)
        m = metrics.desk(self.conn, {"IT_HELP"}, now=self.at, months=1)
        self.assertEqual((m["satisfaction"], m["satisfaction_n"]), (4.5, 2))


class MergeScheduleSurveyWebTest(unittest.TestCase):
    setUp = WebWSGITest.setUp
    tearDown = WebWSGITest.tearDown
    _call = WebWSGITest._call
    _environ = WebWSGITest._environ
    _cookie_for = WebWSGITest._cookie_for

    def test_the_ticket_books_a_visit_dispatch_shows_the_day_and_a_merge_closes(self):
        alice = self._cookie_for("alice")
        status, headers, _ = self._call("POST", "/ticket/ITO-1/schedule/add", cookie=alice, form={
            "member": "bob", "starts_at": "2026-09-18T10:00", "ends_at": "2026-09-18T11:00", "note": "Ward 3"})
        self.assertIn("scheduled", dict(headers)["Location"])
        _, _, page = self._call("GET", "/dispatch", cookie=alice, query="day=2026-09-18")
        self.assertIn("10:00–11:00 · ITO-1", page)
        _, _, ticket = self._call("GET", "/ticket/ITO-1", cookie=alice)
        self.assertIn("Schedule · 1", ticket)
        conn = db.connect(self.db_path)
        conn.executescript(
            "INSERT INTO work_item (work_item_id,source,name,entity_id,contract_basis)"
            " VALUES ('ITO-2','desk','Printer down too','PMC','BASELINE');"
            "INSERT INTO ticket (work_item_id,board_id,path,impact,urgency,priority,priority_source,"
            " requested_at,opened_at,state,board_status_id) VALUES ('ITO-2','IT_HELP','INCIDENT','I3',"
            "'U3','P4','MATRIX','2026-09-17 08:00','2026-09-17 08:00','NEW','IT_HELP.NEW');")
        conn.commit()
        conn.close()
        status, headers, _ = self._call("POST", "/ticket/ITO-2/merge", cookie=alice, form={"into": "ito-1"})
        self.assertIn("Merged+into+ITO-1", dict(headers)["Location"])
        _, _, page = self._call("GET", "/ticket/ITO-2", cookie=alice)
        self.assertIn("Merged into <a href='/ticket/ITO-1'>", page)
        self.assertNotIn("Duplicate? Merge into", page)

    def test_the_portal_asks_once_after_close_and_flags_patient_details(self):
        conn = db.connect(self.db_path)
        conn.execute("UPDATE ticket SET requested_by = 'bob@pmcne.ph', state = 'CLOSED',"
                     " closed_at = '2026-09-17 09:00' WHERE work_item_id = 'ITO-1'")
        conn.commit()
        conn.close()
        bob = self._cookie_for("bob", email="bob@pmcne.ph")
        _, _, page = self._call("GET", "/my/ITO-1", cookie=bob)
        self.assertIn("How did we do?", page)
        status, _, page = self._call("POST", "/my/ITO-1/survey", cookie=bob,
                                     form={"score": "5", "comment": "Sorted, case no. 4471 done quickly"})
        self.assertTrue(status.startswith("200"))
        self.assertIn("we will tidy this one", page)            # a friendly tip, the flag is written
        _, _, page = self._call("GET", "/my/ITO-1", cookie=bob)
        self.assertNotIn("How did we do?", page)
        self.assertIn("5 out of 5", page)
        status, _, _ = self._call("POST", "/my/ITO-1/survey", cookie=self._cookie_for("eve", email="eve@x"),
                                  form={"score": "1"})
        self.assertTrue(status.startswith("404"))


class AttachmentsWebTest(unittest.TestCase):
    """The desk and the portal: upload, download, review, and who may see what."""

    setUp = WebWSGITest.setUp
    tearDown = WebWSGITest.tearDown
    _cookie_for = WebWSGITest._cookie_for

    def _send(self, method, path, *, cookie, fields=None, files=()):
        import io as _io_
        import wsgiref.validate as _v
        body, ctype = b"", None
        if fields is not None or files:
            boundary = "----psa-test-boundary"
            parts = []
            for k, v in (fields or {}).items():
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"'
                             f"\r\n\r\n{v}\r\n".encode())
            for fname, data in files:
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file";'
                             f' filename="{fname}"\r\nContent-Type: application/octet-stream'
                             "\r\n\r\n".encode() + data + b"\r\n")
            body = b"".join(parts) + f"--{boundary}--\r\n".encode()
            ctype = f"multipart/form-data; boundary={boundary}"
        env = {"REQUEST_METHOD": method, "PATH_INFO": path, "SCRIPT_NAME": "",
               "QUERY_STRING": "", "SERVER_NAME": "t", "SERVER_PORT": "80",
               "SERVER_PROTOCOL": "HTTP/1.1", "wsgi.version": (1, 0),
               "wsgi.url_scheme": "http", "wsgi.input": _io_.BytesIO(body),
               "wsgi.errors": _io_.StringIO(), "wsgi.multithread": False,
               "wsgi.multiprocess": False, "wsgi.run_once": False, "HTTP_COOKIE": cookie}
        if body:
            env["CONTENT_LENGTH"] = str(len(body))
            env["CONTENT_TYPE"] = ctype
        captured = {}

        def start_response(status, headers, exc_info=None):
            captured.update(status=status, headers=dict(headers))
        it = _v.validator(self.raw)(env, start_response)
        try:
            payload = b"".join(it)
        finally:
            it.close()
        return captured["status"], captured["headers"], payload

    def _conn(self):
        return db.connect(self.db_path)

    def test_a_file_uploaded_at_the_desk_downloads_as_an_attachment(self):
        cookie = self._cookie_for("alice")
        status, headers, _ = self._send("POST", "/ticket/ITO-1/attach", cookie=cookie,
                                        files=[("error screen.png", _png())])
        self.assertTrue(status.startswith("303"), status)
        self.assertIn("Attached", headers["Location"])
        conn = self._conn()
        aid, stored = conn.execute("SELECT attachment_id, size_stored FROM attachment").fetchone()
        conn.close()
        self.assertLess(stored, len(_png()))
        status, headers, data = self._send("GET", f"/ticket/ITO-1/file/{aid}", cookie=cookie)
        self.assertTrue(status.startswith("200"))
        self.assertTrue(headers["Content-Disposition"].startswith("attachment;"))
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Content-Security-Policy"], "sandbox")
        self.assertTrue(data.startswith(b"\x89PNG"))
        _, _, page = self._send("GET", "/ticket/ITO-1", cookie=cookie)
        self.assertIn(b"Awaiting review", page)

    def test_a_refused_upload_says_why_and_keeps_nothing(self):
        status, headers, _ = self._send("POST", "/ticket/ITO-1/attach",
                                        cookie=self._cookie_for("alice"),
                                        files=[("tool.exe", b"MZ" + b"\x00" * 64)])
        self.assertIn("err=", headers["Location"])
        conn = self._conn()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM attachment").fetchone()[0], 0)
        conn.close()

    def test_a_reader_cannot_upload_or_review(self):
        status, _, _ = self._send("POST", "/ticket/ITO-1/attach", cookie=self._cookie_for("carol"),
                                  files=[("a.txt", b"hello there")])
        self.assertFalse(status.startswith("303"))

    def test_a_withheld_file_is_served_only_to_the_board_admin(self):
        from psaspine import attachments
        conn = self._conn()
        aid = attachments.add(conn, "ITO-1", _png(), "his.png", actor="alice",
                              at=datetime(2026, 9, 17, 9))["attachment_id"]
        conn.commit()
        conn.close()
        status, headers, _ = self._send("POST", f"/ticket/ITO-1/file/{aid}/review",
                                        cookie=self._cookie_for("alice"),
                                        fields={"decision": "WITHHELD"})
        self.assertIn("withheld", headers["Location"])
        status, _, _ = self._send("GET", f"/ticket/ITO-1/file/{aid}", cookie=self._cookie_for("carol"))
        self.assertTrue(status.startswith("404"))
        status, _, _ = self._send("GET", f"/ticket/ITO-1/file/{aid}", cookie=self._cookie_for("alice"))
        self.assertTrue(status.startswith("200"))

    def test_a_download_on_a_restricted_board_is_audited_with_the_file(self):
        from psaspine import attachments
        conn = self._conn()
        aid = attachments.add(conn, "ITO-9", b"trace line\n" * 50, "trace.txt", actor="alice",
                              at=datetime(2026, 9, 17, 9))["attachment_id"]
        conn.commit()
        conn.close()
        status, _, data = self._send("GET", f"/ticket/ITO-9/file/{aid}", cookie=self._cookie_for("alice"))
        self.assertEqual(data, b"trace line\n" * 50)
        conn = self._conn()
        details = [r[0] for r in conn.execute("SELECT detail FROM audit_event WHERE action ="
                                              " 'RESTRICTED_READ' AND subject_id = 'ITO-9'")]
        conn.close()
        self.assertTrue(any(f"attachment {aid}" in d for d in details), details)

    def test_the_requester_sees_cleared_files_and_their_own_never_withheld(self):
        from psaspine import attachments
        conn = self._conn()
        conn.execute("UPDATE ticket SET requested_by = 'bob@pmcne.ph' WHERE work_item_id = 'ITO-1'")
        at = datetime(2026, 9, 17, 9)
        pending = attachments.add(conn, "ITO-1", b"desk note\n" * 20, "desk.txt", actor="alice",
                                  at=at)["attachment_id"]
        cleared = attachments.add(conn, "ITO-1", b"how to fix\n" * 20, "howto.txt", actor="alice",
                                  at=at)["attachment_id"]
        attachments.review(conn, cleared, "CLEARED", actor="alice", at=at)
        conn.commit()
        conn.close()
        bob = self._cookie_for("bob", email="bob@pmcne.ph")
        status, headers, _ = self._send("POST", "/my/ITO-1/reply", cookie=bob,
                                        fields={"body": ""}, files=[("mine.png", _png())])
        self.assertTrue(status.startswith("303"), status)
        _, _, page = self._send("GET", "/my/ITO-1", cookie=bob)
        self.assertIn(b"howto.txt", page)
        self.assertIn(b"mine.png", page)
        self.assertNotIn(b"desk.txt", page)
        status, _, _ = self._send("GET", f"/my/ITO-1/file/{pending}", cookie=bob)
        self.assertTrue(status.startswith("404"))
        status, _, data = self._send("GET", f"/my/ITO-1/file/{cleared}", cookie=bob)
        self.assertEqual(data, b"how to fix\n" * 20)
        conn = self._conn()
        self.assertEqual(conn.execute("SELECT customer_updated FROM ticket WHERE work_item_id"
                                      " = 'ITO-1'").fetchone()[0], 1)
        conn.close()

    def test_a_file_removed_under_retention_is_shown_as_gone_and_never_served(self):
        from psaspine import attachments
        conn = self._conn()
        conn.execute("UPDATE ticket SET requested_by = 'bob@pmcne.ph' WHERE work_item_id = 'ITO-1'")
        at = datetime(2026, 9, 17, 9)
        aid = attachments.add(conn, "ITO-1", b"old trace\n" * 30, "old.log", actor="bob@pmcne.ph",
                              at=at)["attachment_id"]
        attachments.review(conn, aid, "WITHHELD", actor="alice", at=at)
        conn.commit()
        done = attachments.purge(conn, at=datetime(2026, 12, 1), withheld_days=30,
                                 closed_days=730, apply=True)
        conn.close()
        self.assertEqual(done["files_removed"], 1)
        status, _, _ = self._send("GET", f"/ticket/ITO-1/file/{aid}", cookie=self._cookie_for("alice"))
        self.assertTrue(status.startswith("410"), status)
        _, _, page = self._send("GET", "/ticket/ITO-1", cookie=self._cookie_for("alice"))
        self.assertIn(b"removed 2026-12-01", page)
        self.assertNotIn(b"Withhold", page)
        bob = self._cookie_for("bob", email="bob@pmcne.ph")
        _, _, page = self._send("GET", "/my/ITO-1", cookie=bob)
        self.assertNotIn(b"old.log", page)
        status, _, _ = self._send("GET", f"/my/ITO-1/file/{aid}", cookie=bob)
        self.assertTrue(status.startswith("404"))

    def test_a_body_over_the_limit_is_refused_unread(self):
        import io as _io_
        from psaspine.web import MAX_BODY

        class Exploding(_io_.BytesIO):
            def read(self, *a):
                raise AssertionError("the body was read")
        env = {"REQUEST_METHOD": "POST", "PATH_INFO": "/ticket/ITO-1/attach", "SCRIPT_NAME": "",
               "QUERY_STRING": "", "SERVER_NAME": "t", "SERVER_PORT": "80",
               "SERVER_PROTOCOL": "HTTP/1.1", "wsgi.version": (1, 0), "wsgi.url_scheme": "http",
               "wsgi.input": Exploding(), "wsgi.errors": _io_.StringIO(),
               "wsgi.multithread": False, "wsgi.multiprocess": False, "wsgi.run_once": False,
               "CONTENT_LENGTH": str(MAX_BODY + 1), "HTTP_COOKIE": self._cookie_for("alice")}
        captured = {}
        b"".join(self.raw(env, lambda s, h, e=None: captured.update(status=s)))
        self.assertTrue(captured["status"].startswith("413"))


class RequesterMailTest(unittest.TestCase):
    """The requester's email: opened or updated, a link, and never the words."""

    def setUp(self) -> None:
        from psaspine import outbox
        self.outbox = outbox
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 23, 9, 0)
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)
        self.conn.execute("UPDATE board SET notify_requester = 1 WHERE board_id = 'IT_HELP'")

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _open(self, requester="Nurse.Ward3@pmcne.ph", source="PORTAL"):
        return tickets.open_ticket(self.conn, board_id="IT_HELP", impact="I3", urgency="U3",
                                   summary="SUMMARY-CANARY cannot open HIS", requested_by=requester,
                                   at=self.at, source=source)

    def _mail(self, wid):
        return self.conn.execute("SELECT * FROM notification WHERE work_item_id = ? AND"
                                 " recipient_role = 'REQUESTER' ORDER BY notification_id",
                                 (wid,)).fetchall()

    def _note(self, wid, flag, body="NOTE-CANARY reset the HIS role."):
        board.add_note(self.conn, wid, body=body, flag=flag, actor="alice", at=self.at)

    def test_opening_a_ticket_tells_the_requester_without_the_summary(self):
        wid = self._open()
        [n] = self._mail(wid)
        self.assertEqual(n["subject"], f"[{wid}] We have your request")
        self.assertNotIn("CANARY", n["subject"] + n["body"])
        [item] = self.outbox.pending(self.conn, allowed_domains=("pmcne.ph",),
                                     portal_url="https://imaging.pmcne.ph/")
        self.assertEqual(item["to"], "nurse.ward3@pmcne.ph")
        self.assertIn(f"https://imaging.pmcne.ph/my/{wid}", item["body"])
        self.assertNotIn("CANARY", item["body"])
        self.assertNotIn("on the desk", item["body"])

    def test_a_readable_note_sends_one_update_and_an_internal_note_sends_none(self):
        wid = self._open()
        self.outbox.mark(self.conn, self._mail(wid)[0]["notification_id"], "SENT", at=self.at)
        self._note(wid, "INTERNAL")
        self.assertEqual(len(self._mail(wid)), 1)
        self._note(wid, "DISCUSSION")
        self._note(wid, "DISCUSSION", body="And again.")
        mails = self._mail(wid)
        self.assertEqual(len(mails), 2)                 # the second update waits on the first
        self.assertEqual(mails[1]["subject"], f"[{wid}] Your request has been updated")
        self.assertNotIn("CANARY", mails[1]["body"])
        self.outbox.mark(self.conn, mails[1]["notification_id"], "SENT", at=self.at)
        self._note(wid, "RESOLUTION", body="Fixed.")
        self.assertEqual(len(self._mail(wid)), 3)

    def test_nothing_is_sent_where_it_should_not_be(self):
        self.assertEqual(self._mail(self._open(source="API")), [])
        self.assertEqual(self._mail(self._open(requester="nobody-we-know")), [])
        self.assertEqual(self._mail(self._open(requester=None)), [])
        for off in (0, None):                      # switched off, and never switched on
            self.conn.execute("UPDATE board SET notify_requester = ? WHERE board_id = 'IT_HELP'",
                              (off,))
            wid = self._open()
            self._note(wid, "DISCUSSION")
            self.assertEqual(self._mail(wid), [])

    def test_the_portal_link_must_be_https_and_is_optional(self):
        self._open()
        with self.assertRaises(ValueError):
            self.outbox.pending(self.conn, allowed_domains=("pmcne.ph",), dry_run=True,
                                portal_url="http://imaging.pmcne.ph")
        [item] = self.outbox.pending(self.conn, allowed_domains=("pmcne.ph",), dry_run=True)
        self.assertIn("the PMC Requests portal, under Your requests", item["body"])


class ContactsTest(unittest.TestCase):
    """020 and psaspine.contacts: the people who ask, from what AD already holds."""

    HEADER = ("ObjectGUID,DisplayName,Mail,UserPrincipalName,SamAccountName,"
              "Department,Title,Office,TelephoneNumber,Enabled\r\n")
    G1 = "0f9c3a0e-1111-4c2a-9a55-2b8f3c1d0001"
    G2 = "0f9c3a0e-2222-4c2a-9a55-2b8f3c1d0002"

    def setUp(self) -> None:
        from psaspine import contacts
        self.contacts = contacts
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 23, 9, 0)
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _export(self, *rows: str, bom: bool = True) -> Path:
        path = Path(self.tmp.name) / "ad.csv"
        body = self.HEADER + "".join(r + "\r\n" for r in rows)
        path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + body.encode("utf-8"))
        return path

    def _row(self, guid, name="Ward Three Nurse Station", mail="ward3@pmcne.ph",
             dept="Ward 3", enabled="True"):
        return f"{guid},{name},{mail},{mail},ward3,{dept},Charge Nurse,Main,100,{enabled}"

    def test_an_export_imports_and_a_rerun_changes_nothing(self):
        path = self._export(self._row(self.G1), self._row(self.G2, name="IT Office",
                                                          mail="it@pmcne.ph", dept="IT"))
        first = self.contacts.import_csv(self.conn, path, entity_id="PMC", at=self.at)
        self.assertEqual((first["rows"], first["new"], first["skipped"]), (2, 2, 0))
        again = self.contacts.import_csv(self.conn, path, entity_id="PMC", at=self.at)
        self.assertEqual((again["new"], again["updated"], again["unchanged"]), (0, 0, 2))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) c FROM contact").fetchone()["c"], 2)
        self.assertIsNotNone(self.conn.execute(
            "SELECT 1 FROM audit_event WHERE action = 'CONTACT_IMPORT'").fetchone())

    def test_a_renamed_person_is_the_same_contact(self):
        """The objectGUID is the identity; a new name or mailbox is an update."""
        self.contacts.import_csv(self.conn, self._export(self._row(self.G1)),
                                 entity_id="PMC", at=self.at)
        r = self.contacts.import_csv(
            self.conn, self._export(self._row(self.G1.upper(), name="Ward 3 Station",
                                              mail="Ward3.Station@pmcne.ph")),
            entity_id="PMC", at=self.at)
        self.assertEqual((r["new"], r["updated"]), (0, 1))
        row = self.conn.execute("SELECT display_name, email FROM contact").fetchone()
        self.assertEqual((row["display_name"], row["email"]),
                         ("Ward 3 Station", "ward3.station@pmcne.ph"))

    def test_disabled_in_ad_is_inactive_never_deleted(self):
        self.contacts.import_csv(self.conn, self._export(self._row(self.G1)),
                                 entity_id="PMC", at=self.at)
        r = self.contacts.import_csv(self.conn, self._export(self._row(self.G1, enabled="False")),
                                     entity_id="PMC", at=self.at)
        self.assertEqual(r["deactivated"], 1)
        self.assertEqual(self.conn.execute("SELECT inactive FROM contact").fetchone()["inactive"], 1)

    def test_absence_from_an_export_is_not_a_departure(self):
        """An export scoped to one OU says nothing about anybody else."""
        self.contacts.import_csv(self.conn, self._export(self._row(self.G1), self._row(
            self.G2, mail="it@pmcne.ph")), entity_id="PMC", at=self.at)
        self.contacts.import_csv(self.conn, self._export(self._row(self.G1)),
                                 entity_id="PMC", at=self.at)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) c FROM contact WHERE inactive = 0").fetchone()["c"], 2)

    def test_every_row_is_accounted_for_and_a_skip_says_why(self):
        r = self.contacts.import_csv(self.conn, self._export(
            self._row(self.G1), self._row("not-a-guid"), self._row(self.G2, enabled="maybe")),
            entity_id="PMC", at=self.at)
        self.assertEqual(r["new"] + r["updated"] + r["unchanged"] + r["skipped"], r["rows"])
        self.assertEqual(r["skipped"], 2)
        self.assertEqual(len(r["reasons"]), 2)
        self.assertTrue(all(reason.startswith("line ") for reason in r["reasons"]))

    def test_a_file_that_is_not_an_export_is_refused(self):
        path = Path(self.tmp.name) / "other.csv"
        path.write_bytes(b"Name,Email\r\nA,a@b.c\r\n")
        with self.assertRaises(ValueError):
            self.contacts.import_csv(self.conn, path, entity_id="PMC", at=self.at)
        with self.assertRaises(LookupError):
            self.contacts.import_csv(self.conn, self._export(), entity_id="NOPE", at=self.at)

    def test_a_new_ticket_finds_its_contact_and_company(self):
        self.contacts.import_csv(self.conn, self._export(self._row(self.G1)),
                                 entity_id="PMC", at=self.at)
        wid = tickets.open_ticket(self.conn, board_id="IT_HELP", summary="Printer down",
                                  impact="I2", urgency="U2", at=self.at,
                                  requested_by="Ward 3 <WARD3@pmcne.ph>")
        row = self.conn.execute(
            "SELECT t.contact_id, w.entity_id FROM ticket t JOIN work_item w"
            " ON w.work_item_id = t.work_item_id WHERE t.work_item_id = ?", (wid,)).fetchone()
        self.assertIsNotNone(row["contact_id"])
        self.assertEqual(row["entity_id"], "PMC")

    def test_an_ambiguous_or_unknown_requester_resolves_to_nobody(self):
        """A ticket under the wrong person is worse than one under nobody."""
        self.contacts.import_csv(self.conn, self._export(
            self._row(self.G1), self._row(self.G2, name="Other")), entity_id="PMC", at=self.at)
        self.assertIsNone(self.contacts.resolve(self.conn, "ward3@pmcne.ph"))
        self.assertIsNone(self.contacts.resolve(self.conn, "stranger@example.org"))
        self.assertIsNone(self.contacts.resolve(self.conn, "Ward Three Nurse Station"))
        wid = tickets.open_ticket(self.conn, board_id="IT_HELP", summary="x", impact="I2",
                                  urgency="U2", at=self.at, requested_by="ward3@pmcne.ph")
        row = self.conn.execute(
            "SELECT t.contact_id, w.entity_id FROM ticket t JOIN work_item w"
            " ON w.work_item_id = t.work_item_id WHERE t.work_item_id = ?", (wid,)).fetchone()
        self.assertIsNone(row["contact_id"])
        # No one person, but the domain belongs to one company: filed under it.
        self.assertEqual(row["entity_id"], "PMC")

    def test_a_domain_names_a_company_only_when_it_is_one_companys(self):
        """The reference PSA's third match: exact address, unique name, then a domain
        owned by exactly one company. Public mail domains never match."""
        self.contacts.import_csv(self.conn, self._export(self._row(self.G1)),
                                 entity_id="PMC", at=self.at)
        self.assertEqual(self.contacts.company_for_domain(self.conn, "new.nurse@pmcne.ph"), "PMC")
        self.assertIsNone(self.contacts.company_for_domain(self.conn, "someone@gmail.com"))
        self.assertIsNone(self.contacts.company_for_domain(self.conn, "x@example.org"))
        self.conn.execute(
            "INSERT INTO contact (contact_id, entity_id, display_name, email, source, inactive,"
            " created_at) VALUES ('CT-J', 'JRBY-CI', 'Other', 'o@pmcne.ph', 'MANUAL', 0, '2026')")
        self.assertIsNone(self.contacts.company_for_domain(self.conn, "new.nurse@pmcne.ph"))

    def test_an_inactive_contact_is_never_resolved(self):
        self.contacts.import_csv(self.conn, self._export(self._row(self.G1, enabled="False")),
                                 entity_id="PMC", at=self.at)
        self.assertIsNone(self.contacts.resolve(self.conn, "ward3@pmcne.ph"))

    def test_the_cli_imports_and_counts(self):
        dbp = Path(self.tmp.name) / "cli.db"
        db.init(dbp).close()
        path = self._export(self._row(self.G1))
        import contextlib
        from psaspine.__main__ import main as cli_main
        out = _io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli_main(["import-contacts", str(dbp), str(path), "--company", "PMC"])
        self.assertEqual(code, 0)
        self.assertIn("1 rows: 1 new", out.getvalue())


class ConfigurationsTest(unittest.TestCase):
    """021 and psaspine.configurations: machines from AD, links out, ticket links."""

    HEADER = ("ObjectGUID,Name,DNSHostName,OperatingSystem,OperatingSystemVersion,"
              "Description,Enabled,LastLogonDate\r\n")
    G1 = "7a1c3a0e-1111-4c2a-9a55-2b8f3c1d0001"
    G2 = "7a1c3a0e-2222-4c2a-9a55-2b8f3c1d0002"
    SESSION = "0f9c3a0e-aaaa-4c2a-9a55-2b8f3c1d00ff"

    def setUp(self) -> None:
        from psaspine import configurations
        self.cmdb = configurations
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 23, 9, 0)
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _export(self, *rows: str) -> Path:
        path = Path(self.tmp.name) / "computers.csv"
        path.write_bytes(b"\xef\xbb\xbf" + (self.HEADER + "".join(r + "\r\n" for r in rows))
                         .encode("utf-8"))
        return path

    def _row(self, guid, name="WARD3-PC01", os_name="Windows 11 Pro", enabled="True"):
        return (f"{guid},{name},{name.lower()}.pmcne.ph,{os_name},10.0 (22631),"
                f"Nurse station,{enabled},2026-09-22 07:10")

    def _one(self):
        return self.conn.execute("SELECT * FROM configuration").fetchone()

    def test_computers_import_and_a_rerun_changes_nothing(self):
        path = self._export(self._row(self.G1),
                            self._row(self.G2, name="PMC-ORTHANC01",
                                      os_name="Windows Server 2022 Standard"))
        r = self.cmdb.import_ad_computers(self.conn, path, entity_id="PMC", at=self.at)
        self.assertEqual((r["rows"], r["new"], r["skipped"]), (2, 2, 0))
        kinds = dict(self.conn.execute("SELECT name, config_type FROM configuration").fetchall())
        self.assertEqual(kinds, {"WARD3-PC01": "WORKSTATION", "PMC-ORTHANC01": "SERVER"})
        again = self.cmdb.import_ad_computers(self.conn, path, entity_id="PMC", at=self.at)
        self.assertEqual((again["new"], again["updated"], again["unchanged"]), (0, 0, 2))

    def test_the_desk_owns_type_contact_and_retirement(self):
        """A re-import refreshes what AD knows and nothing the desk decided."""
        self.cmdb.import_ad_computers(self.conn, self._export(self._row(self.G1)),
                                      entity_id="PMC", at=self.at)
        cid = self._one()["configuration_id"]
        self.cmdb.update(self.conn, cid, at=self.at, actor="t", config_type="LAPTOP",
                         status="RETIRED")
        self.cmdb.import_ad_computers(self.conn, self._export(self._row(self.G1, name="WARD3-LT01")),
                                      entity_id="PMC", at=self.at)
        row = self._one()
        self.assertEqual((row["name"], row["config_type"], row["status"]),
                         ("WARD3-LT01", "LAPTOP", "RETIRED"))

    def test_disabled_in_ad_is_inactive(self):
        self.cmdb.import_ad_computers(self.conn, self._export(self._row(self.G1)),
                                      entity_id="PMC", at=self.at)
        r = self.cmdb.import_ad_computers(
            self.conn, self._export(self._row(self.G1, enabled="False")), entity_id="PMC", at=self.at)
        self.assertEqual(r["deactivated"], 1)
        self.assertEqual(self._one()["status"], "INACTIVE")

    def test_every_row_is_accounted_for(self):
        r = self.cmdb.import_ad_computers(
            self.conn, self._export(self._row(self.G1), self._row("nope")),
            entity_id="PMC", at=self.at)
        self.assertEqual(r["new"] + r["updated"] + r["unchanged"] + r["skipped"], r["rows"])
        self.assertEqual(r["reasons"], ["line 3: no usable ObjectGUID"])

    def test_a_session_id_must_be_a_guid(self):
        """So a pasted URL or note can never become part of a launch link."""
        self.cmdb.import_ad_computers(self.conn, self._export(self._row(self.G1)),
                                      entity_id="PMC", at=self.at)
        cid = self._one()["configuration_id"]
        with self.assertRaises(ValueError):
            self.cmdb.update(self.conn, cid, at=self.at, actor="t",
                             remote_session_id="https://evil.example/")
        self.cmdb.update(self.conn, cid, at=self.at, actor="t",
                         remote_session_id="{" + self.SESSION.upper() + "}")
        self.assertEqual(self._one()["remote_session_id"], self.SESSION)
        self.assertIsNotNone(self.conn.execute(
            "SELECT 1 FROM audit_event WHERE action = 'CONFIGURATION_UPDATE'").fetchone())

    def test_a_link_template_is_https_to_a_fixed_host_with_known_fields(self):
        for bad in ("http://x.screenconnect.com/{remote_session_id}",
                    "https://{name}.example/", "javascript:alert(1)//{name}",
                    "https://x.screenconnect.com/{password}",
                    "https://x.screenconnect.com/Host"):
            with self.assertRaises(ValueError, msg=bad):
                self.cmdb.check_template("CONFIGURATION", bad)
        self.cmdb.check_template(
            "CONFIGURATION",
            "https://x.screenconnect.com/Host#Access/All%20Machines//{remote_session_id}/Join")

    def test_a_link_is_filled_encoded_or_drawn_disabled_with_the_reason(self):
        self.cmdb.import_ad_computers(self.conn, self._export(self._row(self.G1)),
                                      entity_id="PMC", at=self.at)
        self.cmdb.add_link(
            self.conn, label="ScreenConnect", applies_to="CONFIGURATION", at=self.at, actor="t",
            url_template="https://x.screenconnect.com/Host#Access/All%20Machines//"
                         "{remote_session_id}/Join")
        self.cmdb.add_link(self.conn, label="Search", applies_to="CONFIGURATION", at=self.at,
                           actor="t", url_template="https://kb.example/q/{name}")
        links = {x["label"]: x for x in self.cmdb.links_for(self.conn, "CONFIGURATION", self._one())}
        self.assertIsNone(links["ScreenConnect"]["url"])
        self.assertIn("remote session id", links["ScreenConnect"]["why"])
        self.assertEqual(links["Search"]["url"], "https://kb.example/q/WARD3-PC01")
        cid = self._one()["configuration_id"]
        self.conn.execute("UPDATE configuration SET name = 'a b/c?d' WHERE configuration_id = ?",
                          (cid,))
        self.cmdb.update(self.conn, cid, at=self.at, actor="t", remote_session_id=self.SESSION)
        links = {x["label"]: x for x in self.cmdb.links_for(self.conn, "CONFIGURATION", self._one())}
        self.assertEqual(links["ScreenConnect"]["url"],
                         "https://x.screenconnect.com/Host#Access/All%20Machines//"
                         + self.SESSION + "/Join")
        self.assertEqual(links["Search"]["url"], "https://kb.example/q/a%20b%2Fc%3Fd")

    def test_a_machine_typed_in_by_hand_is_the_desks_and_an_imported_ones_name_is_ads(self):
        cid = self.cmdb.create(self.conn, name="PRN-01", entity_id="PMC", config_type="PRINTER", at=self.at,
                               actor="t", manufacturer="HP", description="Ward 3")
        row = self.conn.execute("SELECT * FROM configuration WHERE configuration_id = ?", (cid,)).fetchone()
        self.assertEqual((row["source"], row["status"], row["manufacturer"], row["description"]),
                         ("MANUAL", "ACTIVE", "HP", "Ward 3"))
        self.assertEqual(self.cmdb.update(self.conn, cid, at=self.at, actor="t", name="PRN-02", model="M479"),
                         ["model", "name"])
        with self.assertRaises(ValueError):
            self.cmdb.create(self.conn, name="prn-02", entity_id="PMC", config_type="PRINTER", at=self.at, actor="t")
        with self.assertRaises(ValueError):
            self.cmdb.create(self.conn, name="X", entity_id="PMC", config_type="TOASTER", at=self.at, actor="t")
        self.cmdb.import_ad_computers(self.conn, self._export(self._row(self.G1)), entity_id="PMC", at=self.at)
        ad = self.conn.execute("SELECT configuration_id FROM configuration WHERE source = 'AD'").fetchone()[0]
        with self.assertRaises(ValueError):
            self.cmdb.update(self.conn, ad, at=self.at, actor="t", name="RENAMED")
        self.assertEqual(self.cmdb.update(self.conn, ad, at=self.at, actor="t", name="WARD3-PC01",
                                          manufacturer="Dell"), ["manufacturer"])

    def test_attach_and_detach_are_recorded_on_the_ticket(self):
        self.cmdb.import_ad_computers(self.conn, self._export(self._row(self.G1)),
                                      entity_id="PMC", at=self.at)
        cid = self._one()["configuration_id"]
        wid = tickets.open_ticket(self.conn, board_id="IT_HELP", summary="PC slow", impact="I3",
                                  urgency="U3", requested_by=None, at=self.at)
        self.assertTrue(self.cmdb.attach(self.conn, wid, cid, at=self.at, actor="t"))
        self.assertFalse(self.cmdb.attach(self.conn, wid, cid, at=self.at, actor="t"))
        self.assertTrue(self.cmdb.detach(self.conn, wid, cid, at=self.at, actor="t"))
        details = [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM ticket_event WHERE work_item_id = ? AND kind = 'UPDATED'", (wid,))]
        self.assertEqual(details, [f"configuration WARD3-PC01 ({cid}) attached",
                                   f"configuration WARD3-PC01 ({cid}) removed"])


class AdComputersScriptTest(unittest.TestCase):
    """scripts/Export-PmcAdComputers.ps1: read-only, no address, no secret."""

    SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "Export-PmcAdComputers.ps1"

    def setUp(self) -> None:
        self.text = self.SCRIPT.read_bytes().decode("ascii")

    def test_it_never_writes_to_ad_and_reads_no_address_or_secret(self):
        for shape in ("Set-AD", "New-AD", "Remove-AD", "Move-AD", "Disable-AD",
                      "IPv4Address", "IPv6Address", "ms-Mcs-AdmPwd", "msLAPS",
                      "msFVE-RecoveryInformation", "Get-Credential"):
            self.assertNotIn(shape, self.text, shape)
        self.assertIn("Get-ADComputer", self.text)

    def test_nothing_is_written_without_apply(self):
        self.assertLess(self.text.index("if (-not $Apply) {"), self.text.index("Export-Csv"))

    def test_the_columns_are_the_ones_the_importer_reads(self):
        from psaspine import configurations
        for column in configurations.COLUMNS:
            self.assertIn(f"        {column}", self.text, column)


class AdContactsScriptTest(unittest.TestCase):
    """scripts/Export-PmcAdContacts.ps1 runs against AD, which nothing here can
    reach. Its fences are asserted as text: pure ASCII for PowerShell 5.1,
    read-only against AD, preview unless -Apply, and the header the importer reads."""

    SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "Export-PmcAdContacts.ps1"

    def setUp(self) -> None:
        self.text = self.SCRIPT.read_bytes().decode("ascii")   # raises if not ASCII

    def test_it_never_writes_to_ad(self):
        for verb in ("Set-AD", "New-AD", "Remove-AD", "Move-AD", "Enable-AD",
                     "Disable-AD", "Add-AD", "Rename-AD"):
            self.assertNotIn(verb, self.text)
        self.assertIn("Get-ADUser", self.text)

    def test_it_asks_for_no_credential_and_exports_no_secret(self):
        lowered = self.text.lower()
        for shape in ("get-credential", "-credential", "convertto-securestring",
                      "memberof", "pwdlastset", "unicodepwd"):
            self.assertNotIn(shape, lowered, shape)

    def test_nothing_is_written_without_apply(self):
        self.assertIn("[switch] $Apply", self.text)
        self.assertLess(self.text.index("if (-not $Apply) {"), self.text.index("Export-Csv"))

    def test_the_columns_are_the_ones_the_importer_reads(self):
        from psaspine import contacts
        for column in list(contacts.COLUMNS) + ["Enabled"]:
            self.assertIn(f"        {column}", self.text, column)


class MarkdownRenderTest(unittest.TestCase):
    """The uplift screen renders the report's own markdown; the renderer must
    handle exactly the shapes the reports emit, and escape everything else."""

    def _render(self, md):
        from psaspine.web import templates
        return templates.md_to_html(md)

    def test_headings_bold_and_code(self):
        html = self._render("# Title\n\nText with **bold** and `code`.")
        self.assertIn("<h1>Title</h1>", html)
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("<code>code</code>", html)

    def test_a_pipe_table_becomes_a_table(self):
        html = self._render("| A | B |\n|---|---|\n| 1 | 2 |")
        self.assertIn("<table>", html)
        self.assertIn("<th>A</th>", html)
        self.assertIn("<td>1</td>", html)

    def test_content_is_escaped(self):
        html = self._render("A paragraph with <script> in it.")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


class EntraSignInTest(unittest.TestCase):
    """The browser's way in: authorization code with PKCE against a tenant that
    never leaves the process. The token endpoint and the keys are fakes on the
    Config; the ID token is signed with the suite's synthetic RSA key."""
    _call = WebWSGITest._call
    _environ = WebWSGITest._environ

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = _target(self.tmp)
        _fresh(self.tmp).close()
        self.n, self.e, self.d = _rsa_keypair()
        self.gets, self.posts = [], []
        self.nonce_to_sign = None            # None: the one the flight carries
        self.post_raises = None

        def http_get(url):
            self.gets.append(url)
            nb = self.n.to_bytes((self.n.bit_length() + 7) // 8, "big")
            eb = self.e.to_bytes((self.e.bit_length() + 7) // 8, "big")
            return {"keys": [{"kty": "RSA", "kid": "k1", "n": _b64u(nb), "e": _b64u(eb)}]}

        def http_post(url, data):
            self.posts.append((url, data))
            if self.post_raises:
                raise self.post_raises
            now = _time.time()
            claims = {"aud": "client-z", "iss": "https://login.microsoftonline.com/tenant-y/v2.0",
                      "exp": now + 600, "nbf": now - 10, "oid": "oid-alice", "name": "Alice Cruz",
                      "preferred_username": "alice@pmcne.ph",
                      "nonce": self.nonce_to_sign if self.nonce_to_sign is not None else self.flight["nonce"]}
            return {"id_token": _sign_rs256(claims, self.n, self.d)}

        self.config = Config(session_secret=_secrets.token_bytes(32), entra_tenant="tenant-y",
                             entra_client="client-z", http_get=http_get, http_post=http_post)
        self.raw = make_app(self.db_path, config=self.config, clock=lambda: datetime(2026, 9, 26, 9, 0))
        self.flight = {}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _start(self, next_url="/my"):
        status, headers, _ = self._call("GET", "/entra/start", query=f"next={next_url}",
                                        headers={"host": "desk.test:8443"})
        self.assertTrue(status.startswith("303"), status)
        location = dict(headers)["Location"]
        cookie = next(v for k, v in headers if k == "Set-Cookie")
        self.flight_cookie_header = cookie
        value = cookie.split(";", 1)[0].split("=", 1)[1]
        self.flight = _json.loads(_b64.urlsafe_b64decode(value.split(".")[0] + "=="))
        return location, "psa_entra=" + value

    def test_the_login_page_offers_entra_when_a_tenant_is_configured(self):
        status, _, body = self._call("GET", "/login")
        self.assertIn("/entra/start", body)
        self.assertIn("Break-glass", body)

    def test_start_sends_the_browser_to_the_tenant_with_pkce_and_a_signed_flight(self):
        location, cookie = self._start()
        self.assertTrue(location.startswith("https://login.microsoftonline.com/tenant-y/oauth2/v2.0/authorize?"))
        q = dict(_urlparse.parse_qsl(_urlparse.urlsplit(location).query))
        self.assertEqual((q["client_id"], q["response_type"], q["code_challenge_method"]),
                         ("client-z", "code", "S256"))
        self.assertEqual(q["redirect_uri"], "http://desk.test:8443/entra/callback")
        self.assertEqual(q["state"], self.flight["state"])
        self.assertEqual(q["nonce"], self.flight["nonce"])
        expected = _b64u(_hashlib.sha256(self.flight["verifier"].encode()).digest())
        self.assertEqual(q["code_challenge"], expected)
        for attr in ("HttpOnly", "SameSite=Lax", "Path=/entra", "Max-Age=600"):
            self.assertIn(attr, self.flight_cookie_header)
        self.assertNotIn("Secure", self.flight_cookie_header)          # plain http in this test

    def test_the_callback_exchanges_the_code_verifies_the_token_and_opens_a_session(self):
        location, cookie = self._start("/my")
        state = self.flight["state"]
        status, headers, _ = self._call("GET", "/entra/callback", query=f"code=abc&state={state}",
                                        cookie=cookie, headers={"host": "desk.test:8443"})
        self.assertTrue(status.startswith("303"), status)
        self.assertEqual(dict(headers)["Location"], "/my")
        cookies = [v for k, v in headers if k == "Set-Cookie"]
        self.assertTrue(any(c.startswith("psa_session=") for c in cookies))
        self.assertTrue(any(c.startswith("psa_entra=;") for c in cookies))
        url, data = self.posts[0]
        self.assertEqual(url, "https://login.microsoftonline.com/tenant-y/oauth2/v2.0/token")
        self.assertEqual((data["code"], data["code_verifier"], data["redirect_uri"], data["client_id"]),
                         ("abc", self.flight["verifier"], "http://desk.test:8443/entra/callback", "client-z"))
        self.assertNotIn("client_secret", data)
        self.assertEqual(self.gets, ["https://login.microsoftonline.com/tenant-y/discovery/v2.0/keys"])
        conn = db.connect(self.db_path)
        row = conn.execute("SELECT actor, subject_id, detail FROM audit_event WHERE action = 'ENTRA_LOGIN'").fetchone()
        conn.close()
        self.assertEqual(tuple(row), ("oid-alice", "alice@pmcne.ph", "Alice Cruz"))
        # the session works: the portal answers for this person
        session = next(c for c in cookies if c.startswith("psa_session=")).split(";", 1)[0]
        status, _, body = self._call("GET", "/my", cookie=session)
        self.assertTrue(status.startswith("200"), status)

    def test_a_wrong_state_a_stale_flight_and_a_foreign_nonce_are_each_refused(self):
        _, cookie = self._start()
        status, _, body = self._call("GET", "/entra/callback", query="code=abc&state=not-it", cookie=cookie)
        self.assertTrue(status.startswith("401"))
        self.assertIn("did not match", body)
        self.assertEqual(self.posts, [])
        status, _, body = self._call("GET", "/entra/callback", query=f"code=abc&state={self.flight['state']}",
                                     cookie="psa_entra=" + cookie.split("=", 1)[1][:-3] + "xyz")
        self.assertTrue(status.startswith("401"))
        self.assertIn("did not start here", body)
        self.nonce_to_sign = "someone-elses"
        status, _, body = self._call("GET", "/entra/callback", query=f"code=abc&state={self.flight['state']}",
                                     cookie=cookie)
        self.assertTrue(status.startswith("401"))
        self.assertIn("not issued for this sign-in", body)
        conn = db.connect(self.db_path)
        try:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM audit_event WHERE action = 'ENTRA_LOGIN'").fetchone()[0], 0)
        finally:
            db.close(conn)             # left open, Windows refuses to delete the file (WinError 32)

    def test_when_the_tenant_is_unreachable_the_break_glass_door_is_offered(self):
        _, cookie = self._start()
        self.post_raises = OSError("no route")
        status, _, body = self._call("GET", "/entra/callback", query=f"code=abc&state={self.flight['state']}",
                                     cookie=cookie)
        self.assertTrue(status.startswith("401"))
        self.assertIn("could not be reached", body)
        self.assertIn("Break-glass", body)

    def test_behind_a_tls_proxy_the_flight_cookie_is_secure_and_the_redirect_uri_is_the_public_one(self):
        """SQL01 part 8: IIS terminates TLS and speaks plain http to the desk, so
        `request.secure` is False; the public URL is what says the world is https."""
        self.config.public_url = "https://desk.pmcne.ph"
        status, headers, _ = self._call("GET", "/entra/start", query="next=/my",
                                        headers={"host": "127.0.0.1:8085"})
        self.assertTrue(status.startswith("303"), status)
        cookie = next(v for k, v in headers if k == "Set-Cookie")
        self.assertIn("Secure", cookie)
        q = dict(_urlparse.parse_qsl(_urlparse.urlsplit(dict(headers)["Location"]).query))
        self.assertEqual(q["redirect_uri"], "https://desk.pmcne.ph/entra/callback")
        self.assertIn(("Strict-Transport-Security", "max-age=31536000"), headers)

    def test_a_bearer_token_on_the_api_side_fetches_the_keys_it_needs(self):
        from psaspine.web import entra
        cfg = Config(session_secret=b"x" * 32, entra_tenant="tenant-y", entra_client="client-z",
                     http_get=lambda url: {"keys": [{"kty": "RSA", "kid": "k9", "n": "AQAB", "e": "AQAB"}]})
        self.assertEqual(cfg.jwks, {})
        keys = entra.ensure_key(cfg, "k9")
        self.assertEqual(keys["k9"], {"n": 65537, "e": 65537})
        self.assertIs(entra.ensure_key(cfg, "k9"), cfg.jwks)      # held, not fetched twice


class WindowsSignInTest(unittest.TestCase):
    """The staff's own Windows account at the login page. Windows itself is a
    fake on the Config here; on the host it is LogonUser. No licence, no tenant."""
    _call = WebWSGITest._call
    _environ = WebWSGITest._environ

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = _target(self.tmp)
        conn = _fresh(self.tmp)
        conn.execute("INSERT OR IGNORE INTO entity (entity_id, name, is_covered, note) VALUES ('PMC','PMC',1,NULL)")
        conn.execute("INSERT INTO contact (contact_id, entity_id, display_name, email, upn, sam_account, source,"
                     " created_at) VALUES ('CT-1','PMC','Alice Cruz','Alice.Cruz@pmcne.ph','alice@pmcne.ph','alice',"
                     "'AD','2026-09-26 09:00')")
        conn.execute("INSERT OR REPLACE INTO board (board_id,display_name,phase,fulfiller_group,owner,deputy,"
                     " is_live,is_unrouted) VALUES ('IT_HELP','IT Help','2','Dada','a','b',1,0)")
        conn.execute("INSERT INTO board_member (board_id, member, access) VALUES ('IT_HELP','bob','WORK')")
        conn.commit()
        conn.close()
        self.asked = []

        def logon(domain, username, password):
            self.asked.append((domain, username))
            if (username, password) == ("alice", "correct horse"):
                return True, 0
            if username == "locked":
                return False, 1909
            if username == "stale":
                return False, 1330
            return False, 1326

        self.config = Config(session_secret=_secrets.token_bytes(32), windows_domain="PMCNE",
                             windows_logon=logon)
        self.raw = make_app(self.db_path, config=self.config, clock=lambda: datetime(2026, 9, 26, 9, 0))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _login(self, username, password):
        return self._call("POST", "/login", form={"door": "windows", "username": username,
                                                  "password": password, "next": "/my"})

    def test_the_page_offers_the_windows_account_first_and_break_glass_last(self):
        status, _, body = self._call("GET", "/login")
        self.assertLess(body.index("Your Windows account"), body.index("Break-glass"))
        self.assertIn("PMCNE", body)
        self.assertNotIn("/entra/start", body)          # no tenant configured

    def test_a_good_password_opens_a_session_as_the_ad_contact(self):
        status, headers, _ = self._login("alice", "correct horse")
        self.assertTrue(status.startswith("303"), status)
        self.assertEqual(dict(headers)["Location"], "/my")
        cookie = next(v for k, v in headers if k == "Set-Cookie").split(";", 1)[0]
        self.assertEqual(self.asked, [("PMCNE", "alice")])
        status, _, body = self._call("GET", "/my", cookie=cookie)
        self.assertTrue(status.startswith("200"))
        conn = db.connect(self.db_path)
        row = conn.execute("SELECT actor, detail FROM audit_event WHERE action = 'WINDOWS_LOGIN'").fetchone()
        conn.close()
        self.assertEqual(tuple(row), ("alice", "contact CT-1"))

    def test_domain_and_upn_spellings_of_the_name_are_the_same_person(self):
        for spelling in ("PMCNE\\alice", "alice@pmcne.ph", "  Alice "):
            self.asked.clear()
            status, _, _ = self._login(spelling, "correct horse")
            self.assertTrue(status.startswith("303"), spelling)
            self.assertEqual(self.asked, [("PMCNE", "alice")], spelling)

    def test_the_session_carries_the_contacts_email_so_the_portal_finds_their_tickets(self):
        from psaspine import tickets
        conn = db.connect(self.db_path)
        setup.apply_starter(conn, "IT_HELP", actor="t", at=datetime(2026, 9, 26, 8))
        wid = tickets.open_ticket(conn, board_id="IT_HELP", summary="Printer in ward 3", impact="I3",
                                  urgency="U3", requested_by="alice.cruz@pmcne.ph",
                                  at=datetime(2026, 9, 26, 8), actor="t")
        conn.commit()
        conn.close()
        _, headers, _ = self._login("alice", "correct horse")
        cookie = next(v for k, v in headers if k == "Set-Cookie").split(";", 1)[0]
        _, _, body = self._call("GET", "/my", cookie=cookie)
        self.assertIn("Printer in ward 3", body)
        # and no board: a requester is not a fulfiller, so '/' is their requests
        status, headers, _ = self._call("GET", "/", cookie=cookie)
        self.assertTrue(status.startswith("303"), status)
        self.assertEqual(dict(headers)["Location"], "/my")

    def test_a_refusal_says_what_windows_said_and_is_audited_without_the_password(self):
        for user, words in (("alice", "wrong"), ("locked", "locked out"), ("stale", "expired")):
            status, _, body = self._login(user, "nope")
            self.assertTrue(status.startswith("401"), user)
            self.assertIn(words, body)
            self.assertNotIn("nope", body)
        conn = db.connect(self.db_path)
        rows = conn.execute("SELECT actor, detail FROM audit_event WHERE action = 'WINDOWS_LOGIN_REFUSED'"
                            " ORDER BY audit_id").fetchall()
        conn.close()
        self.assertEqual([tuple(r) for r in rows], [
            ("alice", "the username or password is wrong"), ("locked", "the account is locked out"),
            ("stale", "the password has expired; change it on your PC first")])
        self.assertNotIn("nope", str([tuple(r) for r in rows]))

    def test_without_a_domain_the_door_is_neither_shown_nor_open(self):
        cfg = Config(session_secret=_secrets.token_bytes(32))
        app = make_app(self.db_path, config=cfg, clock=lambda: datetime(2026, 9, 26, 9, 0))
        self.raw = app
        _, _, body = self._call("GET", "/login")
        self.assertNotIn("Your Windows account", body)
        status, _, body = self._login("alice", "correct horse")
        self.assertTrue(status.startswith("401"))
        self.assertIn("not configured", body)

    def test_on_a_host_that_is_not_windows_the_real_logon_says_so(self):
        import sys as _sys
        if _sys.platform.startswith("win"):
            self.skipTest("this asserts the refusal on a non-Windows host")
        with self.assertRaises(webauth.AuthConfigError):
            webauth.windows_logon("PMCNE", "alice", "x")


class HttpsServerTest(unittest.TestCase):
    """The desk speaking TLS itself, with a certificate made for the test."""

    @classmethod
    def setUpClass(cls):
        import shutil
        cls.openssl = shutil.which("openssl")
        if not cls.openssl:
            # Git for Windows ships one; on DND-SQL01 it is not on the task account's PATH
            for candidate in (r"C:\Program Files\Git\usr\bin\openssl.exe",
                              r"C:\Program Files (x86)\Git\usr\bin\openssl.exe"):
                if Path(candidate).is_file():
                    cls.openssl = candidate
                    break

    def setUp(self) -> None:
        if not self.openssl:
            self.skipTest("openssl is not on this machine to make a test certificate")
        import subprocess
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = _target(self.tmp)
        conn = _fresh(self.tmp)
        webauth.create_local_account(conn, "glass", "correct horse battery staple", created_by="t",
                                     at=datetime(2026, 9, 26, 9))
        conn.commit()
        conn.close()
        self.cert = str(Path(self.tmp.name) / "desk.pem")
        self.key = str(Path(self.tmp.name) / "desk-key.pem")
        subprocess.run([self.openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", self.key,
                        "-out", self.cert, "-days", "2", "-subj", "/CN=localhost",
                        "-addext", "subjectAltName=IP:127.0.0.1,DNS:localhost"],
                       check=True, capture_output=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_https_answers_and_the_session_cookie_is_secure(self):
        import ssl
        import threading
        import urllib.request
        from psaspine.web import server
        cfg = Config(session_secret=_secrets.token_bytes(32))
        httpd = server.build(str(self.db_path), host="127.0.0.1", port=0, config=cfg,
                             cert=self.cert, key=self.key)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            ctx = ssl.create_default_context(cafile=self.cert)
            with urllib.request.urlopen(f"https://127.0.0.1:{port}/login", context=ctx, timeout=10) as r:
                self.assertEqual(r.status, 200)
                self.assertIn("Break-glass", r.read().decode())
            body = _urlparse.urlencode({"username": "glass", "password": "correct horse battery staple",
                                        "next": "/"}).encode()
            req = urllib.request.Request(f"https://127.0.0.1:{port}/login", data=body, method="POST")

            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *a, **k):
                    return None
            opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPSHandler(context=ctx))
            try:
                r = opener.open(req, timeout=10)
                status, headers = r.status, r.headers
            except urllib.error.HTTPError as e:
                status, headers = e.code, e.headers
            self.assertEqual(status, 303)
            cookie = headers.get("Set-Cookie", "")
            self.assertIn("psa_session=", cookie)
            self.assertIn("Secure", cookie)
            self.assertIn("HttpOnly", cookie)
            # plain http to the TLS port is refused by the handshake, not served
            with self.assertRaises(Exception):
                urllib.request.urlopen(f"http://127.0.0.1:{port}/login", timeout=5)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_a_certificate_without_its_key_or_a_missing_file_is_refused_in_a_sentence(self):
        from psaspine.web import server
        with self.assertRaises(SystemExit) as c1:
            server.build(str(self.db_path), host="127.0.0.1", port=0, cert=self.cert)
        self.assertIn("go together", str(c1.exception))
        with self.assertRaises(SystemExit) as c2:
            server.build(str(self.db_path), host="127.0.0.1", port=0, cert=self.cert,
                         key=str(Path(self.tmp.name) / "nope.pem"))
        self.assertIn("does not exist", str(c2.exception))


class SqlServerDialectTest(unittest.TestCase):
    """The translator in psaspine/mssql.py, on both stores: it needs no server
    to be asserted, and every decision it makes is one the SQL Server run of
    this suite then proves against a real one."""

    def setUp(self) -> None:
        from psaspine import mssql
        self.m = mssql

    def t(self, sql):
        return self.m.translate(sql).sql

    def test_a_path_is_sqlite_and_a_connection_string_is_sql_server(self):
        self.assertEqual(db.backend_of("spine.db"), "sqlite")
        self.assertEqual(db.backend_of(Path("/tmp/x/spine.db")), "sqlite")
        self.assertEqual(db.backend_of("Driver={ODBC Driver 18 for SQL Server};Server=h;Database=PMC_PSA"), "mssql")
        self.assertEqual(db.backend_of("DSN=psa"), "mssql")
        # the keys come in any order; a string that starts with Database= is no file
        self.assertEqual(db.backend_of("Database=PMC_PSA;Trusted_Connection=yes;Server=h;Driver={x}"), "mssql")
        self.assertEqual(db.backend_of("D:\\psa\\spine.db"), "sqlite")

    def test_a_connection_string_is_described_never_printed(self):
        cs = "Driver={ODBC Driver 18 for SQL Server};Server=h;Database=PMC_PSA;UID=u;PWD=hunter2;Encrypt=yes"
        shown = db.describe(cs)
        self.assertNotIn("hunter2", shown)
        self.assertNotIn("UID", shown)
        self.assertIn("Server=h", shown)
        self.assertIn("Database=PMC_PSA", shown)
        self.assertEqual(db.describe("spine.db"), "spine.db")

    def test_a_table_named_like_a_function_is_still_a_table_after_into(self):
        # 052's quote table: INSERT INTO quote (...) is a table with a column list,
        # not SQLite's quote() function; quote(x) anywhere else stays refused.
        self.assertEqual(self.t("INSERT INTO quote (quote_id, name) VALUES (?, ?)"),
                         "INSERT INTO quote (quote_id, name) VALUES (?, ?)")
        with self.assertRaises(self.m.Refused):
            self.t("SELECT quote(name) FROM quote")

    def test_limit_becomes_offset_fetch_and_needs_an_order_by(self):
        self.assertEqual(self.t("SELECT 1 FROM ticket WHERE parent_id = ? LIMIT 1"),
                         "SELECT 1 FROM ticket WHERE parent_id = ?  ORDER BY (SELECT NULL) OFFSET 0 ROWS FETCH NEXT 1 ROWS ONLY")
        self.assertEqual(self.t("SELECT a FROM t ORDER BY a LIMIT 5"),
                         "SELECT a FROM t ORDER BY a  OFFSET 0 ROWS FETCH NEXT 5 ROWS ONLY")
        inner = self.t("SELECT * FROM t WHERE EXISTS (SELECT 1 FROM u WHERE u.x = t.x LIMIT 1) AND y = ?")
        self.assertIn("(SELECT 1 FROM u WHERE u.x = t.x  ORDER BY (SELECT NULL) OFFSET 0 ROWS FETCH NEXT 1 ROWS ONLY) AND y = ?", inner)

    def test_a_moved_placeholder_moves_its_parameter(self):
        plan = self.m.translate("SELECT a FROM t WHERE x = ? ORDER BY a LIMIT ? OFFSET ?")
        self.assertEqual(plan.sql, "SELECT a FROM t WHERE x = ? ORDER BY a  OFFSET ? ROWS FETCH NEXT ? ROWS ONLY")
        self.assertEqual(plan.param_map, [0, 2, 1])
        self.assertIsNone(self.m.translate("SELECT a FROM t WHERE x = ? LIMIT ?").param_map)

    def test_conflict_clauses_are_read_and_removed(self):
        plan = self.m.translate("INSERT OR IGNORE INTO ticket_link (work_item_id, linked_id) VALUES (?,?)")
        self.assertEqual((plan.verb, plan.conflict, plan.table), ("INSERT", "IGNORE", "ticket_link"))
        self.assertEqual(plan.columns, ("work_item_id", "linked_id"))
        self.assertNotIn("OR", plan.sql.split("INTO")[0])
        plan = self.m.translate("INSERT OR REPLACE INTO entity (entity_id, name, is_covered, note) VALUES (?,?,1,?)")
        self.assertEqual((plan.conflict, plan.values), ("REPLACE", ("?", "?", "1", "?")))
        with self.assertRaises(self.m.Refused):
            self.m.translate("INSERT OR IGNORE INTO t (a) SELECT a FROM u")

    def test_functions_operators_and_predicates_in_aggregates(self):
        self.assertEqual(self.t("SELECT substr(opened_at, 1, 7), length(x), ifnull(a, b) FROM t"),
                         "SELECT SUBSTRING(opened_at, 1, 7), LEN(x), ISNULL(a, b) FROM t")
        self.assertEqual(self.t("SELECT 'copied from ' || board_id FROM t"), "SELECT 'copied from ' + board_id FROM t")
        self.assertEqual(self.t("SELECT SUM(a.purged_at IS NOT NULL) AS purged, SUM(a.size) FROM a"),
                         "SELECT SUM(CASE WHEN a.purged_at IS NOT NULL THEN 1 ELSE 0 END) AS purged, SUM(a.size) FROM a")
        self.assertEqual(self.t("SELECT w.name COLLATE NOCASE FROM w"), "SELECT w.name COLLATE Latin1_General_CI_AS FROM w")
        self.assertEqual(self.t("SELECT CAST(x AS INTEGER), CAST(y AS REAL) FROM t"), "SELECT CAST(x AS INT), CAST(y AS FLOAT) FROM t")
        # a string literal is never touched
        self.assertEqual(self.t("SELECT 'substr(a || b) LIMIT 1' FROM t"), "SELECT 'substr(a || b) LIMIT 1' FROM t")

    def test_what_has_no_decision_is_refused_by_name(self):
        for sql in ("PRAGMA foreign_keys", "SELECT strftime('%Y', x) FROM t", "SELECT 1 FROM sqlite_master",
                    "SELECT random()", "SELECT * FROM t WHERE a IS ?", "SELECT * FROM t WHERE a IS NOT ?"):
            with self.assertRaises(self.m.Refused, msg=sql):
                self.m.translate(sql)

    def test_the_first_history_row_after_a_fresh_start_is_number_one(self):
        # On SQL Server the test reset reseeds identities; a reseed to 0 on a
        # table that never had a row would make the first id 0, so only tables
        # that have had rows are reseeded. Either way the answer is 1.
        tmp = tempfile.TemporaryDirectory()
        try:
            conn = _fresh(tmp)
            first = conn.execute(
                "INSERT INTO audit_event (occurred_at, actor, action, subject_kind, subject_id, detail,"
                " override_reason) VALUES ('2026-09-26 09:00','t','TEST','x',NULL,NULL,NULL)").lastrowid
            self.assertEqual(first, 1)
            conn.close()
        finally:
            tmp.cleanup()

    def test_ignore_swallows_what_sqlite_ignores_and_no_more(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            conn = _fresh(tmp)
            conn.execute("INSERT OR IGNORE INTO entity (entity_id, name, is_covered, note) VALUES ('E1','one',1,NULL)")
            # a unique key: skipped
            self.assertEqual(conn.execute("INSERT OR IGNORE INTO entity (entity_id, name, is_covered, note)"
                                          " VALUES ('E1','again',1,NULL)").rowcount, 0)
            # a CHECK (is_covered IN (0,1)): skipped
            self.assertEqual(conn.execute("INSERT OR IGNORE INTO entity (entity_id, name, is_covered, note)"
                                          " VALUES ('E2','two',7,NULL)").rowcount, 0)
            # a foreign key: refused, on both stores
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT OR IGNORE INTO board_member (board_id, member, access)"
                             " VALUES ('NO_SUCH_BOARD','x','READ')")
            conn.rollback()
            self.assertEqual(conn.execute("SELECT name FROM entity WHERE entity_id = 'E1'").fetchone(), None)
            conn.close()
        finally:
            tmp.cleanup()

    def test_a_row_answers_like_sqlite_row(self):
        import decimal
        cur = type("C", (), {"description": (("Name", str), ("n", int), ("hours", decimal.Decimal)), "fetchone": lambda s: None})()
        c = self.m.Cursor(cur, -1, None)
        row = c._wrap(("x", 3, decimal.Decimal("0.25")))
        self.assertEqual((row["name"], row["NAME"], row[0], row["n"], row["hours"]), ("x", "x", "x", 3, 0.25))
        self.assertIsInstance(row["hours"], float)
        self.assertEqual(dict(row), {"name": "x", "n": 3, "hours": 0.25})
        self.assertEqual(tuple(row), ("x", 3, 0.25))
        with self.assertRaises(IndexError):
            row["missing"]

    def test_like_patterns_escape_the_bracket_sql_server_reads_as_a_class(self):
        from psaspine.web.views import board as board_view, search as search_view
        for like in (board_view._like, search_view._like):
            self.assertEqual(like("a[b]%_\\"), "%a\\[b]\\%\\_\\\\%")

    @unittest.skipUnless(TEST_DB, "needs the SQL Server the suite is pointed at")
    def test_the_schema_preview_runs_the_script_unapplied_and_refuses_a_second_run(self):
        # The test database already carries the schema (and may not be named
        # PMC_PSA), so one of the script's own guards answers: the refusal is
        # read over pyodbc, word for word, and nothing is changed.
        conn = db.connect(TEST_DB)
        try:
            with self.assertRaises(RuntimeError) as caught:
                self.m.preview_port(conn)
            self.assertIn("Refusing:", str(caught.exception))
            self.assertIn("Nothing was changed", str(caught.exception))
        finally:
            conn.close()

    def test_serve_refuses_a_port_another_service_holds(self):
        import socket
        from psaspine.web import server
        holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        holder.bind(("127.0.0.1", 0))
        holder.listen(1)
        taken = holder.getsockname()[1]
        try:
            with self.assertRaises(SystemExit) as caught:
                server.serve("spine.db", host="127.0.0.1", port=taken)
            self.assertIn(f"port {taken}", str(caught.exception))
            self.assertIn("already in use", str(caught.exception))
        finally:
            holder.close()

    def test_the_cli_closes_its_connection_on_every_road_out(self):
        # Windows cannot delete a file a process still holds; two CLI tests
        # found that on DND-SQL01 (26 Sep). Every command closes what it opened.
        from unittest import mock
        from psaspine.__main__ import main as cli_main
        tmp = tempfile.TemporaryDirectory()
        try:
            target = _fresh(tmp)
            target.close()
            with mock.patch.object(db, "close", wraps=db.close) as closed:
                self.assertEqual(cli_main(["setup-board", str(_target(tmp)), "--board", "IT_HELP"]), 0)
                self.assertEqual(cli_main(["setup-board", str(_target(tmp)), "--board", "NOPE"]), 1)
            self.assertEqual(closed.call_count, 2)
        finally:
            tmp.cleanup()

    def test_backup_refuses_a_sql_server_target(self):
        with self.assertRaises(ValueError):
            db.backup("Driver={x};Server=h;Database=PMC_PSA", "/tmp/nowhere.bak")


class TimesheetsTest(unittest.TestCase):
    """046: a week of one person's time, submitted by them and decided by
    somebody else; a submitted week takes no more time; utilisation against
    hours a week; the uplift evidence says how much an approver signed."""
    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for

    def setUp(self) -> None:
        from psaspine import security
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(_target(self.tmp))
        conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 30, 9, 0)                     # a Wednesday
        setup.apply_starter(conn, "IT_HELP", actor="t", at=self.at)
        conn.executescript(
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','alice','ADMIN');"
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','bob','WORK');"
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','dave','WORK');")
        security.ensure_roles(conn)
        security.assign(conn, "alice", "SERVICE_MANAGER", at=self.at, actor="root")    # TIME ADMIN
        security.assign(conn, "dave", "SERVICE_MANAGER", at=self.at, actor="root")
        self.wid = tickets.open_ticket(conn, board_id="IT_HELP", summary="PC slow", impact="I3", urgency="U3",
                                       requested_by=None, at=self.at, entity_id="PMC")
        conn.commit()
        conn.close()
        self.config = Config(session_secret=_secrets.token_bytes(32))
        self.raw = make_app(self.db_path, config=self.config, clock=lambda: self.at)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _book(self, who, day, hours):
        conn = db.connect(self.db_path)
        try:
            board.add_time(conn, self.wid, at=self.at, actor=who, charge_method="INCLUDED_IN_MONTHLY_FEE",
                           actual_hours=hours, worked_on=day)
            conn.commit()
        finally:
            conn.close()

    def _sheet(self, conn, member):
        from psaspine import timesheets
        return timesheets.get(conn, member, date(2026, 9, 28))

    def test_grants_written_before_046_are_read_across_once_and_the_new_module_lands(self):
        # A desk that ran 040-045 holds its roles in role_permission, whose CHECK
        # lists five modules. The first look-up after 046 copies them into
        # role_grant, where Timesheets can be written too, and nothing is lost.
        from psaspine import security
        conn = db.connect(self.db_path)
        try:
            conn.execute("DELETE FROM role_grant")
            conn.execute("DELETE FROM member_role")
            conn.execute("DELETE FROM security_role")
            conn.execute("INSERT INTO security_role (role_id, name, is_default, inactive) VALUES ('OLD', 'Old role', 1, 0)")
            conn.execute("INSERT INTO role_permission (role_id, module, level) VALUES ('OLD', 'FINANCE', 'WRITE')")
            conn.execute("INSERT INTO role_permission (role_id, module, level) VALUES ('OLD', 'REPORTS', 'READ')")
            conn.commit()
            user = webauth.User(id="zed", name="zed")
            self.assertEqual(security.levels(conn, user)["FINANCE"], "WRITE")     # carried across
            self.assertEqual(security.levels(conn, user)["TIME"], "WRITE")        # the default for a role that predates it
            security.save_grants(conn, "OLD", {"FINANCE": "WRITE", "REPORTS": "READ", "TIME": "ADMIN"}, at=self.at, actor="root")
            conn.commit()
            self.assertEqual(security.level(conn, user, "TIME"), "ADMIN")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM role_permission").fetchone()[0], 2)   # untouched
            self.assertEqual(conn.execute("SELECT level FROM role_grant WHERE role_id = 'OLD' AND module = 'TIME'").fetchone()[0], "ADMIN")
        finally:
            conn.close()

    def test_a_week_starts_on_monday_and_an_entry_joins_its_open_sheet(self):
        from psaspine import timesheets
        self.assertEqual(timesheets.week_of("2026-09-30"), date(2026, 9, 28))
        self.assertEqual(timesheets.week_of(date(2026, 10, 4)), date(2026, 9, 28))     # a Sunday
        self.assertEqual(timesheets.week_of(datetime(2026, 9, 28, 0, 1)), date(2026, 9, 28))
        with self.assertRaises(timesheets.Refused):
            timesheets.week_of("next tuesday")
        self._book("bob", "2026-09-29", 2)
        conn = db.connect(self.db_path)
        try:
            sheet = self._sheet(conn, "bob")
            self.assertEqual((sheet["status"], sheet["week_start"]), ("OPEN", "2026-09-28"))
            entry = conn.execute("SELECT timesheet_id FROM time_entry").fetchone()
            self.assertEqual(entry["timesheet_id"], sheet["timesheet_id"])
            rows = timesheets.entries(conn, "bob", date(2026, 9, 28))
            self.assertEqual([float(r["hours"]) for r in rows], [2.0])
            self.assertEqual(timesheets.totals(rows), {"days": {"2026-09-29": 2.0},
                                                       "by_charge": {"INCLUDED_IN_MONTHLY_FEE": 2.0}, "total": 2.0})
        finally:
            conn.close()

    def test_a_submitted_week_takes_no_more_time_until_someone_reopens_it_with_a_reason(self):
        from psaspine import timesheets
        self._book("bob", "2026-09-29", 2)
        conn = db.connect(self.db_path)
        try:
            with self.assertRaises(timesheets.Refused):
                timesheets.submit(conn, "bob", date(2026, 10, 5), at=self.at, actor="bob")    # not yet begun
            sheet = timesheets.submit(conn, "bob", date(2026, 9, 28), at=self.at, actor="bob")
            self.assertEqual((sheet["status"], sheet["submitted_by"]), ("SUBMITTED", "bob"))
            conn.commit()
            with self.assertRaises(board.EffortRefused) as caught:
                board.add_time(conn, self.wid, at=self.at, actor="bob", charge_method="INCLUDED_IN_MONTHLY_FEE",
                               actual_hours=1, worked_on="2026-09-30")
            self.assertIn("submitted", str(caught.exception))
            conn.rollback()
            with self.assertRaises(timesheets.Refused):
                timesheets.reopen(conn, sheet["timesheet_id"], at=self.at, actor="alice", note="")
            sheet = timesheets.reopen(conn, sheet["timesheet_id"], at=self.at, actor="alice", note="Missed Wednesday")
            self.assertEqual(sheet["status"], "OPEN")
            board.add_time(conn, self.wid, at=self.at, actor="bob", charge_method="INCLUDED_IN_MONTHLY_FEE",
                           actual_hours=1, worked_on="2026-09-30")
            conn.commit()
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM time_entry WHERE timesheet_id = ?",
                                          (sheet["timesheet_id"],)).fetchone()[0], 2)
            actions = [e["action"] for e in timesheets.history(conn, sheet["timesheet_id"])]
            self.assertEqual(actions, ["SUBMIT", "REOPEN"])
        finally:
            conn.close()

    def test_nobody_decides_their_own_sheet_and_a_rejection_says_why(self):
        from psaspine import timesheets
        self._book("alice", "2026-09-28", 8)
        conn = db.connect(self.db_path)
        try:
            sheet = timesheets.submit(conn, "alice", date(2026, 9, 28), at=self.at, actor="alice")
            sid = sheet["timesheet_id"]
            with self.assertRaises(timesheets.Refused) as own:
                timesheets.decide(conn, sid, "APPROVE", at=self.at, actor="alice")
            self.assertIn("own timesheet", str(own.exception))
            with self.assertRaises(timesheets.Refused):
                timesheets.decide(conn, sid, "REJECT", at=self.at, actor="dave")               # no reason
            with self.assertRaises(timesheets.Refused):
                timesheets.decide(conn, sid, "MAYBE", at=self.at, actor="dave")
            sheet = timesheets.decide(conn, sid, "REJECT", at=self.at, actor="dave", note="Monday is 8 h on one ticket?")
            self.assertEqual((sheet["status"], sheet["decided_by"], sheet["note"]),
                             ("REJECTED", "dave", "Monday is 8 h on one ticket?"))
            conn.commit()
            # a rejected week is open for corrections, then goes round again
            board.add_time(conn, self.wid, at=self.at, actor="alice", charge_method="INCLUDED_IN_MONTHLY_FEE",
                           actual_hours=1, worked_on="2026-09-29")
            sheet = timesheets.submit(conn, "alice", date(2026, 9, 28), at=self.at, actor="alice")
            self.assertEqual(sheet["status"], "SUBMITTED")
            with self.assertRaises(timesheets.Refused):
                timesheets.decide(conn, sid, "APPROVE", at=self.at, actor="dave", note="x") if False else \
                    timesheets.reopen(conn, 999999, at=self.at, actor="dave", note="no such")
            sheet = timesheets.decide(conn, sid, "APPROVE", at=self.at, actor="dave")
            self.assertEqual(sheet["status"], "APPROVED")
            with self.assertRaises(timesheets.Refused):
                timesheets.decide(conn, sid, "APPROVE", at=self.at, actor="dave")              # decided already
            conn.commit()
            self.assertEqual([e["action"] for e in timesheets.history(conn, sid)],
                             ["SUBMIT", "REJECT", "SUBMIT", "APPROVE"])
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'TIMESHEET'").fetchone()[0], 4)
            self.assertEqual(len(timesheets.waiting(conn)), 0)
        finally:
            conn.close()

    def test_submitting_stamps_the_entries_written_before_this_step(self):
        from psaspine import timesheets
        conn = db.connect(self.db_path)
        try:
            conn.execute("INSERT INTO time_entry (work_item_id, entity_id, worked_on, band_hours, performed_by,"
                         " entered_by, charge_method) VALUES (?,?,?,?,?,?,?)",
                         (self.wid, "PMC", "2026-09-29", 2, "bob", "bob", "INCLUDED_IN_MONTHLY_FEE"))
            conn.commit()
            self.assertIsNone(conn.execute("SELECT timesheet_id FROM time_entry").fetchone()[0])
            sheet = timesheets.submit(conn, "bob", date(2026, 9, 28), at=self.at, actor="bob")
            conn.commit()
            self.assertEqual(conn.execute("SELECT timesheet_id FROM time_entry").fetchone()[0], sheet["timesheet_id"])
            waiting = timesheets.waiting(conn)
            self.assertEqual([(w["member"], float(w["hours"])) for w in waiting], [("bob", 2.0)])
        finally:
            conn.close()

    def test_utilisation_is_hours_against_hours_a_week_and_says_what_is_approved(self):
        from psaspine import timesheets
        self._book("bob", "2026-09-28", 8)
        self._book("bob", "2026-09-29", 4)
        conn = db.connect(self.db_path)
        try:
            week = (date(2026, 9, 28), date(2026, 10, 4))
            self.assertEqual(timesheets.capacity(conn, "bob"), 40.0)
            u = timesheets.utilisation(conn, since=week[0], until=week[1])
            self.assertEqual(u, [{"member": "bob", "hours": 12.0, "approved": 0.0, "capacity": 40.0, "percent": 30}])
            sheet = timesheets.submit(conn, "bob", week[0], at=self.at, actor="bob")
            timesheets.decide(conn, sheet["timesheet_id"], "APPROVE", at=self.at, actor="alice")
            timesheets.set_capacity(conn, "bob", "20", at=self.at, actor="alice")
            conn.commit()
            u = timesheets.utilisation(conn, since=week[0], until=week[1])
            self.assertEqual(u, [{"member": "bob", "hours": 12.0, "approved": 12.0, "capacity": 20.0, "percent": 60}])
            for bad in ("abc", "0", "200"):
                with self.assertRaises(timesheets.Refused):
                    timesheets.set_capacity(conn, "bob", bad, at=self.at, actor="alice")
            self.assertIn("bob", timesheets.members(conn))
            text = reports.uplift_evidence(conn, as_of=date(2026, 10, 5))
            self.assertIn("Time approval: 12 h of 12 h that count to capacity sit on an approved timesheet (100%)", text)
        finally:
            conn.close()

    def test_the_page_is_your_own_week_and_an_administrators_view_of_everyone(self):
        from psaspine import security
        self._book("bob", "2026-09-29", 2)
        bob, alice = self._cookie_for("bob"), self._cookie_for("alice")
        status, _, body = self._call("GET", "/time", cookie=bob)
        self.assertEqual(status, "200 OK")
        self.assertIn("Week of 2026-09-28 to 2026-10-04 · bob", body)
        self.assertIn("Submit for approval", body)
        self.assertNotIn("Waiting for a decision", body)
        self.assertIn('href="/time"', body)                                   # in the nav
        status, _, _ = self._call("GET", "/time", cookie=bob, query="member=alice")
        self.assertEqual(status, "403 Forbidden")
        status, _, body = self._call("GET", "/time", cookie=alice, query="member=bob&week=2026-10-01")
        self.assertEqual(status, "200 OK")
        self.assertIn("Waiting for a decision", body)
        self.assertIn("Hours a week", body)
        self.assertIn(f"/ticket/{self.wid}", body)
        # a role with no Timesheets level sees no Time in the nav and no page
        conn = db.connect(self.db_path)
        rid = security.add_role(conn, "Auditor", at=self.at, actor="root")
        security.save_grants(conn, rid, {m: "NONE" for m in security.MODULES}, at=self.at, actor="root")
        security.assign(conn, "eve", rid, at=self.at, actor="root")
        conn.execute("INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','eve','READ')")
        conn.commit()
        conn.close()
        eve = self._cookie_for("eve")
        status, _, body = self._call("GET", "/", cookie=eve)
        self.assertNotIn('href="/time"', body)
        status, _, _ = self._call("GET", "/time", cookie=eve)
        self.assertEqual(status, "403 Forbidden")

    def test_submit_and_decide_from_the_page_and_never_your_own(self):
        import urllib.parse as up
        self._book("bob", "2026-09-29", 2)
        bob, alice = self._cookie_for("bob"), self._cookie_for("alice")
        status, headers, _ = self._call("POST", "/time/submit", cookie=bob, form={"member": "bob", "week": "2026-09-30"})
        self.assertEqual(status, "303 See Other")
        self.assertIn("msg=Submitted+for+approval", dict(headers)["Location"])
        conn = db.connect(self.db_path)
        sid = conn.execute("SELECT timesheet_id FROM timesheet WHERE member = 'bob'").fetchone()[0]
        conn.close()
        # bob cannot decide (WRITE, not ADMIN); alice can, and the page then says so
        status, _, _ = self._call("POST", "/time/decide", cookie=bob,
                                  form={"member": "bob", "week": "2026-09-30", "timesheet_id": sid, "decision": "APPROVE"})
        self.assertEqual(status, "403 Forbidden")
        status, headers, _ = self._call("POST", "/time/decide", cookie=alice,
                                        form={"member": "bob", "week": "2026-09-30", "timesheet_id": sid, "decision": "APPROVE"})
        self.assertEqual(status, "303 See Other")
        self.assertIn("msg=Approved", dict(headers)["Location"])
        status, _, body = self._call("GET", "/time", cookie=alice, query="member=bob&week=2026-09-30")
        self.assertIn("Approved", body)
        self.assertIn("Reopen", body)
        # alice's own week: submitted by her, refused to her
        self._book("alice", "2026-09-28", 3)
        self._call("POST", "/time/submit", cookie=alice, form={"member": "alice", "week": "2026-09-28"})
        conn = db.connect(self.db_path)
        own = conn.execute("SELECT timesheet_id FROM timesheet WHERE member = 'alice'").fetchone()[0]
        conn.close()
        status, headers, _ = self._call("POST", "/time/decide", cookie=alice,
                                        form={"member": "alice", "week": "2026-09-28", "timesheet_id": own, "decision": "APPROVE"})
        self.assertEqual(status, "303 See Other")
        self.assertIn("own timesheet", up.unquote_plus(dict(headers)["Location"]))
        status, _, body = self._call("GET", "/reports", cookie=alice)
        self.assertEqual(status, "200 OK")
        self.assertIn("Utilisation, by member", body)
        self.assertIn("<td>bob</td>", body)



class RecurringTest(unittest.TestCase):
    """047: a board template raised on a cadence by the minute runner, once
    per due day however long the runner was down, with the template's tasks,
    an owner, the machine, and a line on the ticket saying so."""
    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for

    def setUp(self) -> None:
        from psaspine import configurations
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(_target(self.tmp))
        conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 30, 9, 0)
        setup.apply_starter(conn, "IT_HELP", actor="t", at=self.at)
        conn.executescript(
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','alice','ADMIN');"
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','bob','WORK');"
            "INSERT INTO ticket_template (template_id,board_id,name,summary,record_type,description,inactive,created_at,created_by)"
            " VALUES ('TPL1','IT_HELP','Monthly analyser check','Analyser monthly check','SERVICE_REQUEST','Run the checklist.',0,'2026-09-01 09:00','alice');"
            "INSERT INTO ticket_template_task (template_id,sort_order,text) VALUES ('TPL1',1,'Clean the sample probe');"
            "INSERT INTO ticket_template_task (template_id,sort_order,text) VALUES ('TPL1',2,'Run the calibration');")
        self.cid = configurations.create(conn, name="LAB-ANALYSER-01", entity_id="PMC", config_type="OTHER",
                                         at=self.at, actor="alice")
        conn.commit()
        conn.close()
        self.config = Config(session_secret=_secrets.token_bytes(32))
        self.raw = make_app(self.db_path, config=self.config, clock=lambda: self.at)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_the_next_due_day_keeps_the_day_the_series_was_set_on(self):
        from psaspine import recurring
        a = recurring.advance
        self.assertEqual(a(date(2026, 1, 31), "MONTHLY", anchor_day=31), date(2026, 2, 28))
        self.assertEqual(a(date(2026, 2, 28), "MONTHLY", anchor_day=31), date(2026, 3, 31))
        self.assertEqual(a(date(2026, 11, 30), "QUARTERLY", anchor_day=30), date(2027, 2, 28))
        self.assertEqual(a(date(2028, 2, 29), "YEARLY", anchor_day=29), date(2029, 2, 28))
        self.assertEqual(a(date(2026, 9, 30), "WEEKLY", 2), date(2026, 10, 14))
        self.assertEqual(a(date(2026, 9, 30), "DAILY", 3), date(2026, 10, 3))
        self.assertEqual(a(date(2026, 12, 15), "MONTHLY", 2, anchor_day=15), date(2027, 2, 15))
        self.assertEqual(recurring.cadence_words("QUARTERLY", 1), "Every quarter")
        self.assertEqual(recurring.cadence_words("WEEKLY", 2), "Every 2 weeks")

    def test_a_recurrence_is_refused_in_a_sentence_when_it_cannot_raise_a_ticket(self):
        from psaspine import recurring
        conn = db.connect(self.db_path)
        try:
            good = dict(name="Monthly analyser check", template_id="TPL1", cadence="MONTHLY", first_due_on="2026-10-01",
                        entity_id="PMC", at=self.at, actor="alice")
            for bad in ({"template_id": "NOPE"}, {"cadence": "FORTNIGHTLY"}, {"every_n": "0"}, {"every_n": "x"},
                        {"first_due_on": "soon"}, {"owner": "carol"}, {"entity_id": ""}, {"impact": "I9"},
                        {"name": "  "}, {"configuration_id": "CFG-none"}, {"contact_id": "who"}):
                with self.assertRaises(recurring.Refused, msg=str(bad)):
                    recurring.create(conn, **{**good, **bad})
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM recurrence").fetchone()[0], 0)
        finally:
            conn.close()

    def test_the_runner_raises_once_with_the_tasks_and_moves_the_due_day_past_today(self):
        from psaspine import recurring
        conn = db.connect(self.db_path)
        try:
            rid = recurring.create(conn, name="Monthly analyser check", template_id="TPL1", cadence="MONTHLY",
                                   first_due_on="2026-07-01", owner="bob", entity_id="PMC", configuration_id=self.cid,
                                   at=self.at, actor="alice")
            conn.commit()
            raised = recurring.raise_due(conn, at=self.at)                       # three months overdue
            self.assertEqual(len(raised), 1)
            wid = raised[0]["work_item_id"]
            self.assertEqual(raised[0]["next_due_on"], "2026-10-01")               # once, and past today
            tk = conn.execute("SELECT owner, recurrence_id, board_id FROM ticket WHERE work_item_id = ?", (wid,)).fetchone()
            self.assertEqual((tk["owner"], tk["recurrence_id"], tk["board_id"]), ("bob", rid, "IT_HELP"))
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ticket_task WHERE work_item_id = ?", (wid,)).fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ticket_configuration WHERE work_item_id = ? AND configuration_id = ?",
                                          (wid, self.cid)).fetchone()[0], 1)
            lines = [r[0] for r in conn.execute("SELECT detail FROM ticket_event WHERE work_item_id = ? ORDER BY ticket_event_id", (wid,))]
            self.assertTrue(any("raised by the recurrence Monthly analyser check (#" in ln for ln in lines), lines)
            rec = recurring.get(conn, rid)
            self.assertEqual((rec["last_work_item_id"], rec["next_due_on"]), (wid, "2026-10-01"))
            self.assertEqual(recurring.raise_due(conn, at=self.at), [])          # nothing due now
            self.assertEqual(recurring.raise_due(conn, at=datetime(2026, 10, 1, 0, 5))[0]["next_due_on"], "2026-11-01")
            recurring.set_active(conn, rid, False, at=self.at, actor="alice")
            conn.commit()
            self.assertEqual(recurring.raise_due(conn, at=datetime(2026, 12, 1, 9)), [])   # paused
            extra = recurring.run_now(conn, rid, at=datetime(2026, 12, 2, 9), actor="alice")
            conn.commit()
            self.assertEqual(recurring.get(conn, rid)["next_due_on"], "2026-11-01")         # run now moves nothing
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ticket WHERE recurrence_id = ?", (rid,)).fetchone()[0], 3)
            self.assertNotEqual(extra, wid)
        finally:
            conn.close()

    def test_a_failure_on_one_recurrence_is_audited_and_the_others_still_run(self):
        from psaspine import recurring
        conn = db.connect(self.db_path)
        try:
            ok = recurring.create(conn, name="Fine", template_id="TPL1", cadence="WEEKLY", first_due_on="2026-09-29",
                                  entity_id="PMC", at=self.at, actor="alice")
            broken = recurring.create(conn, name="Broken", template_id="TPL1", cadence="WEEKLY", first_due_on="2026-09-29",
                                      entity_id="PMC", at=self.at, actor="alice")
            conn.execute("UPDATE ticket_template SET inactive = 1 WHERE template_id = 'TPL1'")
            conn.execute("INSERT INTO ticket_template (template_id,board_id,name,inactive,created_at,created_by)"
                         " VALUES ('TPL2','IT_HELP','Other',0,'2026-09-01 09:00','alice')")
            conn.execute("UPDATE recurrence SET template_id = 'TPL2' WHERE recurrence_id = ?", (ok,))
            conn.commit()
            out = recurring.raise_due(conn, at=self.at)
            by = {r["recurrence_id"]: r for r in out}
            self.assertIn("work_item_id", by[ok])
            self.assertIn("error", by[broken])                                    # a retired template raises nothing
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'RECURRENCE' AND detail LIKE 'failed:%'").fetchone()[0], 1)
            self.assertEqual(recurring.get(conn, broken)["next_due_on"], "2026-09-29")       # still due; nothing half-written
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ticket WHERE recurrence_id = ?", (broken,)).fetchone()[0], 0)
        finally:
            conn.close()

    def test_the_setup_page_lists_adds_runs_and_pauses_and_the_ticket_says_who_raised_it(self):
        alice, bob = self._cookie_for("alice"), self._cookie_for("bob")
        status, _, body = self._call("GET", "/admin", cookie=alice)
        self.assertIn("Recurring tickets (0 active)", body)
        status, _, _ = self._call("GET", "/admin/recurring", cookie=bob)
        self.assertEqual(status, "403 Forbidden")
        status, _, body = self._call("GET", "/admin/recurring", cookie=alice)
        self.assertEqual(status, "200 OK")
        self.assertIn("No recurring ticket yet", body)
        self.assertIn("IT Help · Monthly analyser check", body) if "IT Help" in body else self.assertIn("Monthly analyser check", body)
        status, headers, _ = self._call("POST", "/admin/recurring/add", cookie=alice, form={
            "name": "Monthly analyser check", "template_id": "TPL1", "cadence": "MONTHLY", "every_n": "1",
            "first_due_on": "2026-10-01", "owner": "bob", "entity_id": "PMC", "configuration": "lab-analyser-01",
            "impact": "I3", "urgency": "U3"})
        self.assertEqual(status, "303 See Other")
        self.assertIn("msg=Recurrence", dict(headers)["Location"])
        status, headers, _ = self._call("POST", "/admin/recurring/add", cookie=alice, form={
            "name": "Bad", "template_id": "TPL1", "cadence": "MONTHLY", "first_due_on": "2026-10-01",
            "entity_id": "PMC", "configuration": "no-such-machine"})
        self.assertIn("err=", dict(headers)["Location"])
        status, _, body = self._call("GET", "/admin/recurring", cookie=alice)
        self.assertIn("<b>Monthly analyser check</b>", body)
        self.assertIn("Every month", body)
        self.assertIn("2026-10-01", body)
        status, headers, _ = self._call("POST", "/admin/recurring/run", cookie=alice, form={"id": "1"})
        self.assertEqual(status, "303 See Other")
        where = dict(headers)["Location"]
        self.assertTrue(where.startswith("/ticket/PMC-"), where)
        status, _, body = self._call("GET", where.split("?")[0], cookie=alice)
        self.assertIn("Raised by", body)
        self.assertIn("the recurrence Monthly analyser check", body)
        self.assertIn("Clean the sample probe", body)
        status, headers, _ = self._call("POST", "/admin/recurring/toggle", cookie=alice, form={"id": "1", "active": "0"})
        self.assertIn("paused", dict(headers)["Location"])
        status, _, body = self._call("GET", "/admin", cookie=alice)
        self.assertIn("Recurring tickets (0 active)", body)
        status, _, _ = self._call("POST", "/admin/recurring/run", cookie=bob, form={"id": "1"})
        self.assertEqual(status, "403 Forbidden")

    def test_the_minute_runner_raises_what_is_due(self):
        from psaspine import recurring
        from psaspine.__main__ import main as cli_main
        conn = db.connect(self.db_path)
        recurring.create(conn, name="Yearly UPS test", template_id="TPL1", cadence="YEARLY", first_due_on="2000-01-01",
                         entity_id="PMC", at=self.at, actor="alice")
        conn.commit()
        conn.close()
        self.assertEqual(cli_main(["run-rules", self.db_path]), 0)
        conn = db.connect(self.db_path)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ticket WHERE recurrence_id IS NOT NULL").fetchone()[0], 1)
            self.assertGreater(recurring.get(conn, 1)["next_due_on"], "2026-09-29")
        finally:
            conn.close()



class AssetLifecycleTest(unittest.TestCase):
    """048: what only the desk can know about a machine (bought, warranty,
    installed, vendor, agreement, where), the warranty tiles, the maintenance
    record per asset, and the two report-writer datasets."""
    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for

    def setUp(self) -> None:
        from psaspine import agreements, configurations, schedule
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(_target(self.tmp))
        conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 30, 9, 0)
        setup.apply_starter(conn, "IT_HELP", actor="t", at=self.at)
        conn.executescript(
            "INSERT OR REPLACE INTO board (board_id,display_name,phase,fulfiller_group,owner,deputy,is_live,restricted)"
            " VALUES ('PHI','PHI Board','2','Clin','a','b',1,1);"
            "INSERT OR REPLACE INTO board_status (board_status_id,board_id,name,escalation_status,is_default)"
            " VALUES ('PHI.NEW','PHI','New','NOT_RESPONDED',1);"
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','alice','ADMIN');"
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','bob','WORK');"
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('PHI','alice','WORK');")
        self.cid = configurations.create(conn, name="WARD3-LBL01", entity_id="PMC", config_type="PRINTER",
                                         serial_number="ZX-1001", at=self.at, actor="alice")
        self.old = configurations.create(conn, name="OLD-PC-01", entity_id="PMC", config_type="WORKSTATION",
                                         at=self.at, actor="alice")
        self.agr = agreements.create(conn, name="Printer care 2026", party="PrintCare", at=self.at, actor="alice")
        self.wid = tickets.open_ticket(conn, board_id="IT_HELP", summary="Label printer prints blank", impact="I3",
                                       urgency="U3", requested_by=None, at=self.at, entity_id="PMC")
        configurations.attach(conn, self.wid, self.cid, at=self.at, actor="alice")
        board.add_time(conn, self.wid, at=self.at, actor="bob", charge_method="INCLUDED_IN_MONTHLY_FEE", actual_hours=2)
        schedule.add(conn, self.wid, member="bob", starts_at=datetime(2026, 9, 30, 10), ends_at=datetime(2026, 9, 30, 11),
                     note=None, actor="alice", at=self.at)
        self.phi = tickets.open_ticket(conn, board_id="PHI", summary="Printer by the bed", impact="I3", urgency="U3",
                                       requested_by=None, at=self.at, entity_id="PMC")
        configurations.attach(conn, self.phi, self.cid, at=self.at, actor="alice")
        conn.commit()
        conn.close()
        self.config = Config(session_secret=_secrets.token_bytes(32))
        self.raw = make_app(self.db_path, config=self.config, clock=lambda: self.at)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_the_life_of_a_machine_is_written_checked_and_audited(self):
        from psaspine import configurations
        conn = db.connect(self.db_path)
        try:
            with self.assertRaises(ValueError) as bad:
                configurations.update(conn, self.cid, at=self.at, actor="alice", warranty_ends_on="March")
            self.assertIn("warranty ends on is a date", str(bad.exception))
            with self.assertRaises(LookupError):
                configurations.update(conn, self.cid, at=self.at, actor="alice", agreement_id="AGR-9999")
            changed = configurations.update(conn, self.cid, at=self.at, actor="alice", purchased_on="2025-03-31",
                                            warranty_ends_on="2027-03-31", installed_on="2025-04-02", vendor="PrintCare Services",
                                            purchase_ref="PO-25-0102", location="Ward 3, nurses' station", agreement_id=self.agr)
            conn.commit()
            self.assertEqual(sorted(changed), ["agreement_id", "installed_on", "location", "purchase_ref", "purchased_on",
                                               "vendor", "warranty_ends_on"])
            row = conn.execute("SELECT * FROM configuration WHERE configuration_id = ?", (self.cid,)).fetchone()
            self.assertEqual((row["vendor"], row["warranty_ends_on"], row["agreement_id"]), ("PrintCare Services", "2027-03-31", self.agr))
            detail = conn.execute("SELECT detail FROM audit_event WHERE action = 'CONFIGURATION_UPDATE' ORDER BY audit_id DESC").fetchone()[0]
            self.assertIn("warranty_ends_on - -> 2027-03-31", detail)
            self.assertEqual(configurations.update(conn, self.cid, at=self.at, actor="alice", warranty_ends_on="2027-03-31"), [])
            self.assertEqual(configurations.warranty_state("2027-03-31", date(2026, 9, 30)), ("COVERED", 182))
            self.assertEqual(configurations.warranty_state("2026-11-30", date(2026, 9, 30)), ("EXPIRING", 61))
            self.assertEqual(configurations.warranty_state("2026-09-01", date(2026, 9, 30)), ("EXPIRED", -29))
            self.assertEqual(configurations.warranty_state(None, date(2026, 9, 30)), (None, None))
            configurations.update(conn, self.old, at=self.at, actor="alice", warranty_ends_on="2026-01-15")
            conn.commit()
            self.assertEqual(configurations.warranty_counts(conn, date(2026, 9, 30)), {"expired": 1, "expiring": 0})
        finally:
            conn.close()

    def test_the_list_counts_and_filters_warranties_and_the_page_shows_and_edits_the_life(self):
        from psaspine import configurations
        conn = db.connect(self.db_path)
        configurations.update(conn, self.old, at=self.at, actor="alice", warranty_ends_on="2026-01-15")
        configurations.update(conn, self.cid, at=self.at, actor="alice", warranty_ends_on="2026-10-20", vendor="PrintCare Services",
                              agreement_id=self.agr)
        conn.commit()
        conn.close()
        alice = self._cookie_for("alice")
        status, _, body = self._call("GET", "/configurations", cookie=alice)
        self.assertEqual(status, "200 OK")
        self.assertIn("<div class=n>1</div><div class=l>Warranty ends in 90 days</div>", body)
        self.assertIn("<div class=n>1</div><div class=l>Out of warranty</div>", body)
        self.assertIn("ended 2026-01-15", body)
        self.assertIn("20 d left · 2026-10-20", body)
        self.assertIn("/configurations/maintenance.csv?", body)
        status, _, body = self._call("GET", "/configurations", cookie=alice, query="warranty=expired")
        self.assertIn("OLD-PC-01", body)
        self.assertNotIn(">WARD3-LBL01<", body)
        status, _, body = self._call("GET", f"/configuration/{self.cid}", cookie=alice)
        self.assertIn("PrintCare Services", body)
        self.assertIn(f"/agreement/{self.agr}", body)
        self.assertIn("Printer care 2026", body)
        self.assertIn(f"/configuration/{self.cid}/maintenance.csv", body)
        self.assertIn("name=warranty_ends_on", body)
        status, headers, _ = self._call("POST", f"/configuration/{self.cid}/update", cookie=alice, form={
            "config_type": "PRINTER", "status": "ACTIVE", "contact_id": "", "remote_session_id": "", "serial_number": "ZX-1001",
            "manufacturer": "", "model": "", "purchased_on": "2025-03-31", "warranty_ends_on": "2026-10-20", "installed_on": "",
            "vendor": "PrintCare Services", "purchase_ref": "PO-25-0102", "location": "Ward 3", "agreement_id": self.agr})
        self.assertEqual(status, "303 See Other")
        loc = dict(headers)["Location"]
        self.assertIn("purchased+on", loc)
        self.assertIn("location", loc)
        status, headers, _ = self._call("POST", f"/configuration/{self.cid}/update", cookie=alice, form={
            "config_type": "PRINTER", "status": "ACTIVE", "warranty_ends_on": "next year"})
        self.assertIn("warranty+ends+on+is+a+date", dict(headers)["Location"])

    def test_the_maintenance_record_lists_the_tickets_the_reader_may_see(self):
        bob, alice = self._cookie_for("bob"), self._cookie_for("alice")
        status, headers, body = self._call("GET", f"/configuration/{self.cid}/maintenance.csv", cookie=bob)
        self.assertEqual(status, "200 OK")
        self.assertIn("text/csv", dict(headers)["Content-Type"])
        lines = body.strip().split("\r\n")
        self.assertEqual(lines[0], "Configuration,Type,Serial,Ticket,Summary,Board,Ticket type,State,Opened,Closed,Owner,Hours,Visits")
        self.assertEqual(len(lines), 2)                                     # the PHI ticket is not bob's to see
        self.assertIn(f"WARD3-LBL01,PRINTER,ZX-1001,{self.wid},Label printer prints blank,", lines[1])
        self.assertTrue(lines[1].endswith(",2.0,1"), lines[1])                # 2 h booked, 1 visit
        status, _, body = self._call("GET", f"/configuration/{self.cid}/maintenance.csv", cookie=alice)
        self.assertEqual(len(body.strip().split("\r\n")), 3)
        self.assertIn("Printer by the bed", body)
        conn = db.connect(self.db_path)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'RESTRICTED_READ'"
                                          " AND detail LIKE 'maintenance export%'").fetchone()[0], 1)
        finally:
            conn.close()
        status, _, body = self._call("GET", "/configurations/maintenance.csv", cookie=bob, query="type=PRINTER")
        self.assertEqual(len(body.strip().split("\r\n")), 2)
        status, _, body = self._call("GET", "/configurations/maintenance.csv", cookie=bob, query="type=WORKSTATION")
        self.assertEqual(len(body.strip().split("\r\n")), 1)               # header only: nothing on that machine
        status, _, _ = self._call("GET", "/configuration/CFG-none/maintenance.csv", cookie=bob)
        self.assertEqual(status, "404 Not Found")

    def test_the_report_writer_knows_configurations_and_maintenance(self):
        from psaspine import reportwriter
        conn = db.connect(self.db_path)
        try:
            r = reportwriter.run(conn, "CONFIGURATIONS", ["name", "type", "warranty"], None, {}, boards=set())
            self.assertEqual(r["headers"], ["Name", "Type", "Warranty ends"])
            self.assertEqual(sorted(row[0] for row in r["rows"]), ["OLD-PC-01", "WARD3-LBL01"])
            r = reportwriter.run(conn, "MAINTENANCE", ["configuration", "ticket", "hours"], None, {}, boards={"IT_HELP"})
            self.assertEqual(r["rows"], [["WARD3-LBL01", self.wid, 2.0]])
            self.assertEqual(r["boards"], {"IT_HELP": 1})
            r = reportwriter.run(conn, "MAINTENANCE", [], "configuration", {}, boards={"IT_HELP", "PHI"})
            self.assertEqual(r["headers"], ["Configuration", "Count", "Hours"])
            self.assertEqual(r["rows"], [["WARD3-LBL01", 2, 2.0]])
        finally:
            conn.close()
        status, _, body = self._call("GET", "/reports/custom", cookie=self._cookie_for("alice"))
        self.assertIn("Maintenance: tickets by configuration", body)
        self.assertIn(">Configurations<", body)


class ApprovalsTest(unittest.TestCase):
    """049: a request parks the ticket in Awaiting approval, emails the
    approver, and shows on their portal page; only they decide it, a decline
    says why, the decision goes on the ticket as a note the requester reads,
    and the ticket returns to where it was. The catalogue asks by itself when
    the pair needs approval and the requester's department names someone."""
    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for
    APPROVER = "head.nursing@pmcne.ph"

    def setUp(self) -> None:
        from psaspine import catalogue as cat
        from psaspine import departments
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(_target(self.tmp))
        conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 30, 9, 0)
        setup.apply_starter(conn, "IT_HELP", actor="t", at=self.at)
        conn.executescript(
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','alice','ADMIN');"
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','bob','WORK');"
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','carol','READ');"
            "UPDATE board SET notify_requester = 1 WHERE board_id = 'IT_HELP';"
            "INSERT INTO contact (contact_id, entity_id, display_name, email, sam_account, department, source,"
            " inactive, created_at) VALUES ('C_MS', 'PMC', 'Maria Santos', 'msantos@pmcne.ph', 'msantos',"
            " 'Nursing - Ward 3', 'AD', 0, '2026-09-17 08:00');")
        departments.add(conn, "Nursing - Ward 3", at=self.at, actor="root")
        departments.add(conn, "Pharmacy", at=self.at, actor="root")
        self.assertTrue(departments.set_approver(conn, "Nursing - Ward 3", "Head.Nursing@pmcne.ph", at=self.at, actor="root"))
        fid = cat.add_area(conn, "Accounts", at=self.at, actor="root")
        sub = cat.add_subtype(conn, fid, "User account", at=self.at, actor="root")
        item = cat.add_item(conn, "New", kind="REQUEST", at=self.at, actor="root")
        self.pair = cat.associate(conn, sub, item, "IT_HELP", needs_approval=True, at=self.at, actor="root")
        plain = cat.add_item(conn, "Reset", kind="REQUEST", at=self.at, actor="root")
        self.plain_pair = cat.associate(conn, sub, plain, "IT_HELP", at=self.at, actor="root")
        self.wid = tickets.open_ticket(conn, board_id="IT_HELP", summary="New user account for a nurse", impact="I3",
                                       urgency="U3", requested_by="msantos@pmcne.ph", at=self.at, entity_id="PMC")
        board.change_status(conn, self.wid, "IT_HELP.IN_PROGRESS", at=self.at, actor="bob")
        conn.commit()
        conn.close()
        self.config = Config(session_secret=_secrets.token_bytes(32))
        self.raw = make_app(self.db_path, config=self.config, clock=lambda: self.at)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _status(self, conn, wid=None):
        return conn.execute("SELECT board_status_id FROM ticket WHERE work_item_id = ?", (wid or self.wid,)).fetchone()[0]

    def test_a_request_parks_the_ticket_emails_the_approver_and_a_decision_returns_it(self):
        from psaspine import approvals, outbox
        conn = db.connect(self.db_path)
        try:
            self.assertEqual(approvals.approver_for(conn, self.wid), self.APPROVER)
            with self.assertRaises(approvals.Refused):
                approvals.request(conn, self.wid, approver="the head nurse", at=self.at, actor="bob")
            aid = approvals.request(conn, self.wid, approver="Head.Nursing@pmcne.ph", reason="  a new  account ",
                                    at=self.at, actor="bob")
            conn.commit()
            row = approvals.get(conn, aid)
            self.assertEqual((row["status"], row["approver"], row["reason"], row["return_status_id"]),
                             ("PENDING", self.APPROVER, "a new account", "IT_HELP.IN_PROGRESS"))
            self.assertEqual(self._status(conn), "IT_HELP.AWAITING_APPROVAL")
            with self.assertRaises(approvals.Refused) as twice:
                approvals.request(conn, self.wid, approver=self.APPROVER, at=self.at, actor="bob")
            self.assertIn("already waiting", str(twice.exception))
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ticket_event WHERE work_item_id = ? AND detail = ?",
                                          (self.wid, f"approval requested from {self.APPROVER}: a new account")).fetchone()[0], 1)
            n = conn.execute("SELECT * FROM notification WHERE recipient_role = 'APPROVER'").fetchall()
            self.assertEqual([(x["recipient"], x["status"]) for x in n], [(self.APPROVER, "PENDING")])
            self.assertIn("needs your approval", n[0]["subject"])
            due = [m for m in outbox.pending(conn, allowed_domains=("pmcne.ph",), dry_run=True,
                                             portal_url="https://requests.pmcne.ph") if m["to"] == self.APPROVER]
            self.assertEqual(len(due), 1)
            self.assertIn("Decide it here: https://requests.pmcne.ph/my/approvals", due[0]["body"])
            self.assertNotIn("New user account", due[0]["body"])            # the words stay behind the sign-in
            # only the approver decides, and a decline says why
            with self.assertRaises(approvals.Refused) as other:
                approvals.decide(conn, aid, "APPROVE", identities=["bob@pmcne.ph", "bob"], at=self.at)
            self.assertIn("someone else", str(other.exception))
            with self.assertRaises(approvals.Refused) as why:
                approvals.decide(conn, aid, "DECLINE", identities=[self.APPROVER], at=self.at)
            self.assertIn("says why", str(why.exception))
            with self.assertRaises(approvals.Refused):
                approvals.decide(conn, aid, "MAYBE", identities=[self.APPROVER], at=self.at)
            self.assertEqual(self._status(conn), "IT_HELP.AWAITING_APPROVAL")    # nothing above was written
            conn.execute("UPDATE notification SET status = 'SENT' WHERE recipient_role = 'REQUESTER'")   # the "we have it" went
            before = conn.execute("SELECT COUNT(*) FROM notification WHERE recipient_role = 'REQUESTER'").fetchone()[0]
            row = approvals.decide(conn, aid, "APPROVE", identities=["Head.Nursing@pmcne.ph"], at=self.at, note="Fine for a ward account")
            conn.commit()
            self.assertEqual((row["status"], row["decided_by"], row["note"]), ("APPROVED", self.APPROVER, "Fine for a ward account"))
            self.assertEqual(self._status(conn), "IT_HELP.IN_PROGRESS")           # back where it was
            note = conn.execute("SELECT detail, note_flag, actor FROM ticket_event WHERE work_item_id = ? AND kind = 'NOTE'"
                                " ORDER BY ticket_event_id DESC", (self.wid,)).fetchone()
            self.assertEqual(tuple(note), (f"Approved by {self.APPROVER}: Fine for a ward account", "DISCUSSION", self.APPROVER))
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM notification WHERE recipient_role = 'REQUESTER'").fetchone()[0],
                             before + 1)                                          # the requester is told
            with self.assertRaises(approvals.Refused) as done:
                approvals.decide(conn, aid, "DECLINE", identities=[self.APPROVER], at=self.at, note="no")
            self.assertIn("already approved", str(done.exception))
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'APPROVAL'").fetchone()[0], 2)
        finally:
            conn.close()

    def test_a_decline_and_a_withdrawal_return_the_ticket_and_a_closed_ticket_needs_none(self):
        from psaspine import approvals
        conn = db.connect(self.db_path)
        try:
            aid = approvals.request(conn, self.wid, approver=self.APPROVER, at=self.at, actor="bob")
            row = approvals.decide(conn, aid, "DECLINE", identities=[self.APPROVER], at=self.at, note="Not this quarter")
            self.assertEqual(row["status"], "DECLINED")
            self.assertEqual(self._status(conn), "IT_HELP.IN_PROGRESS")
            self.assertEqual(conn.execute("SELECT detail FROM ticket_event WHERE work_item_id = ? AND kind = 'NOTE'"
                                          " ORDER BY ticket_event_id DESC", (self.wid,)).fetchone()[0],
                             f"Declined by {self.APPROVER}: Not this quarter")
            aid2 = approvals.request(conn, self.wid, approver=self.APPROVER, at=self.at, actor="alice")
            self.assertEqual(self._status(conn), "IT_HELP.AWAITING_APPROVAL")
            row = approvals.withdraw(conn, aid2, at=self.at, actor="alice")
            self.assertEqual((row["status"], row["decided_by"]), ("WITHDRAWN", "alice"))
            self.assertEqual(self._status(conn), "IT_HELP.IN_PROGRESS")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ticket_event WHERE work_item_id = ? AND detail = ?",
                                          (self.wid, f"approval request to {self.APPROVER} withdrawn")).fetchone()[0], 1)
            with self.assertRaises(approvals.Refused):
                approvals.withdraw(conn, aid2, at=self.at, actor="alice")
            self.assertEqual([r["status"] for r in approvals.for_ticket(conn, self.wid)], ["DECLINED", "WITHDRAWN"])
            # parked in a status somebody has since moved it out of: the decision leaves the ticket alone
            aid3 = approvals.request(conn, self.wid, approver=self.APPROVER, at=self.at, actor="bob")
            board.change_status(conn, self.wid, "IT_HELP.SCHEDULED", at=self.at, actor="bob")
            approvals.decide(conn, aid3, "APPROVE", identities=[self.APPROVER], at=self.at)
            self.assertEqual(self._status(conn), "IT_HELP.SCHEDULED")
            board.change_status(conn, self.wid, "IT_HELP.RESOLVED", at=self.at, actor="bob")
            with self.assertRaises(approvals.Refused) as closed:
                approvals.request(conn, self.wid, approver=self.APPROVER, at=self.at, actor="bob")
            self.assertIn("closed ticket", str(closed.exception))
            with self.assertRaises(approvals.Refused):
                approvals.request(conn, "PMC-999999", approver=self.APPROVER, at=self.at, actor="bob")
            # a board without the status: the request is recorded and nothing is parked
            conn.execute("UPDATE board_status SET inactive = 1 WHERE board_status_id = 'IT_HELP.AWAITING_APPROVAL'")
            other = tickets.open_ticket(conn, board_id="IT_HELP", summary="Licence for the lab", impact="I3", urgency="U3",
                                        requested_by="msantos@pmcne.ph", at=self.at, entity_id="PMC")
            aid4 = approvals.request(conn, other, approver=self.APPROVER, at=self.at, actor="bob")
            self.assertEqual(self._status(conn, other), "IT_HELP.NEW")
            self.assertIsNone(approvals.get(conn, aid4)["return_status_id"])
            approvals.decide(conn, aid4, "APPROVE", identities=[self.APPROVER], at=self.at)
            self.assertEqual(self._status(conn, other), "IT_HELP.NEW")
        finally:
            conn.close()

    def test_the_catalogue_asks_by_itself_when_the_pair_needs_approval(self):
        from psaspine import approvals
        conn = db.connect(self.db_path)
        try:
            self.assertEqual(approvals.maybe_request(conn, self.wid, at=self.at, actor="bob"), "NOT_NEEDED")
            board.update_fields(conn, self.wid, at=self.at, actor="bob", catalogue_item_id=self.plain_pair)
            self.assertEqual(approvals.maybe_request(conn, self.wid, at=self.at, actor="bob"), "NOT_NEEDED")
            board.update_fields(conn, self.wid, at=self.at, actor="bob", catalogue_item_id=self.pair)
            self.assertEqual(approvals.maybe_request(conn, self.wid, at=self.at, actor="bob"), "REQUESTED")
            p = approvals.pending(conn, self.wid)
            self.assertEqual((p["approver"], p["reason"], p["requested_by"]), (self.APPROVER, "the request's item needs approval", "bob"))
            self.assertEqual(self._status(conn), "IT_HELP.AWAITING_APPROVAL")
            self.assertEqual(approvals.maybe_request(conn, self.wid, at=self.at, actor="bob"), "ALREADY")
            approvals.decide(conn, p["approval_id"], "APPROVE", identities=[self.APPROVER], at=self.at)
            self.assertEqual(approvals.maybe_request(conn, self.wid, at=self.at, actor="bob"), "ALREADY")   # approved once is enough
            # a requester the desk does not know, or whose department names nobody: the ticket says so
            stranger = tickets.open_ticket(conn, board_id="IT_HELP", summary="Account for a locum", impact="I3", urgency="U3",
                                           requested_by="locum@example.org", at=self.at, entity_id="PMC", catalogue_item_id=self.pair)
            self.assertEqual(approvals.maybe_request(conn, stranger, at=self.at, actor="bob"), "NO_APPROVER")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ticket_event WHERE work_item_id = ? AND detail LIKE"
                                          " 'this item needs an approval, but the requester''s department names no approver%'",
                                          (stranger,)).fetchone()[0], 1)
            self.assertIsNone(approvals.pending(conn, stranger))
            conn.execute("UPDATE contact SET department = 'Pharmacy' WHERE contact_id = 'C_MS'")
            pharm = tickets.open_ticket(conn, board_id="IT_HELP", summary="Account for pharmacy", impact="I3", urgency="U3",
                                        requested_by="MSantos@pmcne.ph", at=self.at, entity_id="PMC", catalogue_item_id=self.pair)
            self.assertEqual(approvals.maybe_request(conn, pharm, at=self.at, actor="bob"), "NO_APPROVER")
            self.assertEqual(approvals.waiting_for(conn, [self.APPROVER]), [])
            self.assertEqual([r["work_item_id"] for r in approvals.decided_by(conn, ["HEAD.NURSING@pmcne.ph"])], [self.wid])
        finally:
            conn.close()

    def test_the_ticket_card_asks_and_withdraws_and_the_portal_lists_and_decides(self):
        bob, carol, nurse = self._cookie_for("bob"), self._cookie_for("carol"), self._cookie_for("msantos", email="msantos@pmcne.ph")
        head = self._cookie_for("head.nursing", email="Head.Nursing@pmcne.ph")
        someone = self._cookie_for("someone", email="someone@pmcne.ph")
        status, _, body = self._call("GET", f"/ticket/{self.wid}", cookie=bob)
        self.assertIn("data-pod=approval", body)
        self.assertIn(f"name=approver value='{self.APPROVER}'", body)             # suggested from the department
        self.assertIn("No approval asked for.", body)
        status, _, _ = self._call("POST", f"/ticket/{self.wid}/approval/request", cookie=carol,
                                  form={"approver": self.APPROVER, "reason": "x"})
        self.assertEqual(status, "404 Not Found")                             # READ may not ask; absence is the answer
        status, headers, _ = self._call("POST", f"/ticket/{self.wid}/approval/request", cookie=bob,
                                        form={"approver": "nobody", "reason": "x"})
        self.assertIn("err=An+approver+is+an+email", dict(headers)["Location"])
        status, headers, _ = self._call("POST", f"/ticket/{self.wid}/approval/request", cookie=bob,
                                        form={"approver": self.APPROVER, "reason": "A new account for the ward"})
        self.assertEqual(status, "303 See Other")
        self.assertIn("msg=Approval+asked+for", dict(headers)["Location"])
        status, _, body = self._call("GET", f"/ticket/{self.wid}", cookie=bob)
        self.assertIn("Withdraw the request", body)
        self.assertIn("A new account for the ward", body)
        self.assertIn("Awaiting approval", body)
        status, _, body = self._call("GET", f"/my/{self.wid}", cookie=nurse)
        self.assertEqual(status, "200 OK")
        self.assertIn(f"Waiting for approval from {self.APPROVER} since 2026-09-30 09:00", body)
        status, _, body = self._call("GET", "/my", cookie=nurse)
        self.assertIn('href="/my/approvals"', body)
        # the approver's page: theirs to see and decide, nobody else's
        status, _, body = self._call("GET", "/my/approvals", cookie=someone)
        self.assertEqual(status, "200 OK")
        self.assertIn("Nothing waits for you.", body)
        status, _, body = self._call("GET", "/my/approvals", cookie=head)
        self.assertIn(f"{self.wid} · New user account for a nurse", body)
        self.assertIn("Raised by msantos@pmcne.ph", body)
        self.assertIn("A new account for the ward", body)
        aid = int(re.search(r"/my/approvals/(\d+)/decide", body).group(1))
        status, headers, _ = self._call("POST", f"/my/approvals/{aid}/decide", cookie=someone, form={"decision": "APPROVE"})
        self.assertIn("err=This+approval+is+for+someone+else", dict(headers)["Location"])
        status, headers, _ = self._call("POST", f"/my/approvals/{aid}/decide", cookie=head, form={"decision": "DECLINE", "note": ""})
        self.assertIn("A+decline+says+why", dict(headers)["Location"])
        status, headers, _ = self._call("POST", f"/my/approvals/999/decide", cookie=head, form={"decision": "APPROVE"})
        self.assertIn("err=No+such+approval", dict(headers)["Location"])
        status, headers, _ = self._call("POST", f"/my/approvals/{aid}/decide", cookie=head,
                                        form={"decision": "APPROVE", "note": "Fine, standard ward access"})
        self.assertEqual(status, "303 See Other")
        self.assertIn("msg=Approved.", dict(headers)["Location"])
        status, _, body = self._call("GET", "/my/approvals", cookie=head)
        self.assertIn("Nothing waits for you.", body)
        self.assertIn("Decided", body)
        self.assertIn("Fine, standard ward access", body)
        status, _, body = self._call("GET", f"/my/{self.wid}", cookie=nurse)
        self.assertNotIn("Waiting for approval", body)
        self.assertIn(f"Approved by {self.APPROVER}: Fine, standard ward access", body)   # the note is theirs to read
        status, _, body = self._call("GET", f"/ticket/{self.wid}", cookie=bob)
        self.assertIn("Approved</span>", body)
        self.assertIn("Ask for approval from", body)                            # can ask again
        conn = db.connect(self.db_path)
        try:
            self.assertEqual(self._status(conn), "IT_HELP.IN_PROGRESS")
        finally:
            conn.close()
        # withdraw from the card
        self._call("POST", f"/ticket/{self.wid}/approval/request", cookie=bob, form={"approver": self.APPROVER})
        status, _, body = self._call("GET", f"/ticket/{self.wid}", cookie=bob)
        aid2 = int(re.search(r"name=approval_id value=(\d+)", body).group(1))
        status, headers, _ = self._call("POST", f"/ticket/{self.wid}/approval/withdraw", cookie=bob, form={"approval_id": aid})
        self.assertIn("err=This+approval+was+already+approved", dict(headers)["Location"])   # the decided one stays decided
        status, headers, _ = self._call("POST", f"/ticket/{self.wid}/approval/withdraw", cookie=bob, form={"approval_id": "999"})
        self.assertIn("err=No+such+approval+on+this+ticket", dict(headers)["Location"])
        status, headers, _ = self._call("POST", f"/ticket/{self.wid}/approval/withdraw", cookie=bob, form={"approval_id": aid2})
        self.assertIn("msg=Approval+request+withdrawn", dict(headers)["Location"])
        conn = db.connect(self.db_path)
        try:
            self.assertEqual(self._status(conn), "IT_HELP.IN_PROGRESS")
            self.assertEqual(conn.execute("SELECT status FROM approval WHERE approval_id = ?", (aid2,)).fetchone()[0], "WITHDRAWN")
        finally:
            conn.close()

    def test_a_new_ticket_with_the_pair_asks_and_setup_names_the_approver_and_the_pair(self):
        root = self._cookie_for("alice", is_sysadmin=True)
        status, headers, _ = self._call("POST", "/ticket/new", cookie=root, form={
            "board_id": "IT_HELP", "summary": "Account for the new ward clerk", "impact": "I3", "urgency": "U3",
            "requested_by": "msantos@pmcne.ph", "catalogue_item_id": self.pair, "entity_id": "PMC"})
        self.assertEqual(status, "303 See Other")
        wid = dict(headers)["Location"].split("/ticket/")[1].split("?")[0]
        conn = db.connect(self.db_path)
        try:
            self.assertEqual(self._status(conn, wid), "IT_HELP.AWAITING_APPROVAL")
            self.assertEqual(conn.execute("SELECT approver FROM approval WHERE work_item_id = ?", (wid,)).fetchone()[0], self.APPROVER)
        finally:
            conn.close()
        # Setup › Departments names the approver
        status, _, body = self._call("GET", "/admin/departments", cookie=root)
        self.assertIn(f"name='approver|Nursing - Ward 3' value='{self.APPROVER}'", body)
        self.assertIn("name='approver|Pharmacy' value=''", body)
        status, headers, _ = self._call("POST", "/admin/departments/save", cookie=root,
                                        form={"approver|Pharmacy": "chief pharmacist"})
        self.assertIn("is+an+email+address", dict(headers)["Location"])
        status, headers, _ = self._call("POST", "/admin/departments/save", cookie=root,
                                        form={"approver|Pharmacy": " Chief.Pharmacist@pmcne.ph ", "approver|Nursing - Ward 3": self.APPROVER})
        self.assertIn("Pharmacy%3A+approver+chief.pharmacist%40pmcne.ph", dict(headers)["Location"])
        conn = db.connect(self.db_path)
        try:
            self.assertEqual(conn.execute("SELECT approver FROM department WHERE name = 'Pharmacy'").fetchone()[0], "chief.pharmacist@pmcne.ph")
            self.assertEqual(conn.execute("SELECT detail FROM audit_event WHERE action = 'DEPARTMENT_APPROVER' ORDER BY audit_id DESC")
                             .fetchone()[0], "- -> chief.pharmacist@pmcne.ph")
        finally:
            conn.close()
        status, _, _ = self._call("POST", "/admin/departments/save", cookie=self._cookie_for("bob"), form={"approver|Pharmacy": ""})
        self.assertEqual(status, "403 Forbidden")
        # Setup › Boards and the service catalogue: the pair's Approval toggle
        status, _, body = self._call("GET", "/admin/catalogue", cookie=root, query="tab=pairs")
        self.assertIn("Approval: yes", body)
        self.assertIn("Approval: no", body)
        status, headers, _ = self._call("POST", "/admin/catalogue/approval", cookie=root,
                                        form={"catalogue_item_id": self.pair, "needs_approval": "0"})
        self.assertIn("no+longer+asks", dict(headers)["Location"])
        status, headers, _ = self._call("POST", "/admin/catalogue/approval", cookie=root,
                                        form={"catalogue_item_id": self.pair, "needs_approval": "0"})
        self.assertIn("Nothing+changed", dict(headers)["Location"])
        conn = db.connect(self.db_path)
        try:
            self.assertEqual(conn.execute("SELECT needs_approval FROM catalogue_item WHERE catalogue_item_id = ?",
                                          (self.pair,)).fetchone()[0], 0)
            from psaspine import approvals
            self.assertEqual(approvals.maybe_request(conn, self.wid, at=self.at, actor="bob"), "NOT_NEEDED")
        finally:
            conn.close()

class ChannelsAndPagingTest(unittest.TestCase):
    """050: a card in a Teams channel named on the desk (the address lives on
    the host), a rule that notifies a channel or pages the on-call, and a page
    that repeats until answered and hands to the duty manager when it is not."""
    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for

    def setUp(self) -> None:
        from psaspine import channels, workflow
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(_target(self.tmp))
        conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 30, 9, 0)
        setup.apply_starter(conn, "IT_HELP", actor="t", at=self.at)
        workflow.ensure_vocabulary(conn)
        conn.executescript(
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','alice','ADMIN');"
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','bob','WORK');"
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','carol','READ');"
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','oncall1','WORK');"
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','dm1','WORK');"
            "INSERT INTO oncall_slot (slot_id, board_id, member, role, starts_at, ends_at) VALUES"
            " ('OC-1', 'IT_HELP', 'oncall1', 'ON_CALL', '2026-09-30 00:00', '2026-10-01 00:00'),"
            " ('OC-2', 'IT_HELP', 'dm1', 'DUTY_MANAGER', '2026-09-30 00:00', '2026-10-01 00:00');"
            "INSERT INTO contact (contact_id, entity_id, display_name, email, sam_account, source, inactive, created_at)"
            " VALUES ('C_OC', 'PMC', 'On Call One', 'oncall1@pmcne.ph', 'oncall1', 'AD', 0, '2026-09-17 08:00');")
        channels.add_target(conn, "helpdesk-alerts", label="IT Helpdesk › Alerts", pages=True, at=self.at, actor="root")
        channels.add_target(conn, "quiet", label="Quiet channel", pages=False, at=self.at, actor="root")
        self.wid = tickets.open_ticket(conn, board_id="IT_HELP", summary="Printer down in Ward 3", impact="I2",
                                       urgency="U2", requested_by=None, at=self.at, entity_id="PMC")
        conn.commit()
        conn.close()
        self.config = Config(session_secret=_secrets.token_bytes(32))
        self.raw = make_app(self.db_path, config=self.config, clock=lambda: self.at)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _rule(self, conn, wf, fires_on, acts):
        from psaspine import workflow
        conn.execute("INSERT INTO workflow (workflow_id, board_id, name, table_type) VALUES (?, 'IT_HELP', ?, 'TICKET')", (wf, wf))
        ev = f"{wf}_E1"
        conn.execute("INSERT INTO workflow_event (event_id, workflow_id, fires_on, execution_time) VALUES (?,?,?,'ONCE')",
                     (ev, wf, fires_on))
        for n, (act, role, channel, target, detail) in enumerate(acts):
            conn.execute("INSERT INTO workflow_action (event_id, action, notify_role, detail, sort_order, channel, target_id,"
                         " target_member) VALUES (?,?,?,?,?,?,?,?)",
                         (ev, act, role, detail, n, channel, target, target if channel == "TEAMS" else None))
        workflow.test_event(conn, ev, at=self.at)
        workflow.activate(conn, wf, actor="t", at=self.at)
        return ev

    def test_a_channel_is_named_on_the_desk_and_a_card_carries_no_summary(self):
        from psaspine import channels, outbox
        conn = db.connect(self.db_path)
        try:
            for bad in ("Helpdesk Alerts", "x", "-lead", "a" * 41):
                with self.assertRaises(channels.Refused):
                    channels.add_target(conn, bad, label="x", at=self.at, actor="root")
            with self.assertRaises(channels.Refused):
                channels.add_target(conn, "ward-3", label="  ", at=self.at, actor="root")
            with self.assertRaises(channels.Refused):
                channels.add_target(conn, "helpdesk-alerts", label="again", at=self.at, actor="root")
            with self.assertRaises(LookupError):
                channels.queue_teams(conn, self.wid, "nope", subject="s", body="b", at=self.at)
            nid = channels.queue_teams(conn, self.wid, "helpdesk-alerts", subject="[X] Notify: P2 on IT_HELP",
                                       body="New P2 for the ward", at=self.at)
            conn.commit()
            n = conn.execute("SELECT * FROM notification WHERE notification_id = ?", (nid,)).fetchone()
            self.assertEqual((n["channel"], n["recipient"], n["recipient_role"], n["target_id"]),
                             ("TEAMS", "helpdesk-alerts", "CHANNEL", "helpdesk-alerts"))
            # the email sender never sees it; the Teams sender gets a card with no summary
            self.assertEqual(outbox.pending(conn, allowed_domains=("pmcne.ph",), dry_run=True), [])
            with self.assertRaises(ValueError):
                channels.pending_teams(conn, dry_run=True, desk_url="http://desk.pmcne.ph")
            items = channels.pending_teams(conn, dry_run=True, desk_url="https://desk.pmcne.ph/")
            self.assertEqual([(i["id"], i["target"], i["ticket"]) for i in items], [(nid, "helpdesk-alerts", self.wid)])
            card = items[0]["card"]
            text = _json.dumps(card)
            self.assertNotIn("Printer down", text)
            self.assertEqual(card["type"], "message")
            content = card["attachments"][0]["content"]
            facts = {f["title"]: f["value"] for f in content["body"][1]["facts"]}
            pri = conn.execute("SELECT priority FROM ticket WHERE work_item_id = ?", (self.wid,)).fetchone()[0]
            self.assertEqual(facts, {"Ticket": self.wid, "Board": "PMO Helpdesk", "Priority": pri, "Status": "New", "Owner": "unassigned"})
            self.assertEqual(content["actions"][0]["url"], f"https://desk.pmcne.ph/ticket/{self.wid}")
            self.assertEqual(content["body"][2]["text"], "New P2 for the ward")
            self.assertTrue(outbox.mark(conn, nid, "SENT", at=self.at))
            # a channel turned off: its cards are marked NO_SENDER, never posted
            nid2 = channels.queue_teams(conn, self.wid, "quiet", subject="s", body=None, at=self.at)
            self.assertTrue(channels.set_active(conn, "quiet", False, at=self.at, actor="root"))
            self.assertFalse(channels.set_active(conn, "quiet", False, at=self.at, actor="root"))
            self.assertEqual(channels.pending_teams(conn), [])
            self.assertEqual(conn.execute("SELECT status FROM notification WHERE notification_id = ?", (nid2,)).fetchone()[0], "NO_SENDER")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'CHANNEL'").fetchone()[0], 3)
        finally:
            conn.close()

    def test_a_rule_notifies_a_teams_channel_or_pages_the_on_call(self):
        from psaspine import channels
        conn = db.connect(self.db_path)
        try:
            self._rule(conn, "W_TEAMS", "ON_CREATE", [("NOTIFY", None, "TEAMS", "helpdesk-alerts", "a new ticket")])
            self._rule(conn, "W_PAGE", "ON_CREATE", [("ESCALATE", "ON_CALL", "PAGE", None, "page the on-call")])
            self._rule(conn, "W_BAD", "ON_CREATE", [("NOTIFY", None, "TEAMS", "quiet", "to a channel since turned off")])
            channels.set_active(conn, "quiet", False, at=self.at, actor="root")
            conn.commit()
            wid = tickets.open_ticket(conn, board_id="IT_HELP", summary="Lab analyser offline", impact="I1", urgency="U1",
                                      requested_by=None, at=self.at, entity_id="PMC")
            conn.commit()
            cards = conn.execute("SELECT * FROM notification WHERE work_item_id = ? AND channel = 'TEAMS' ORDER BY notification_id",
                                 (wid,)).fetchall()
            self.assertEqual(sorted((c["target_id"], c["event_id"] or "", c["page_id"] or 0) for c in cards),
                             [("helpdesk-alerts", "", 1), ("helpdesk-alerts", "W_TEAMS_E1", 0)])   # the page's card and the rule's
            self.assertEqual([c["body"] for c in cards if c["event_id"]], ["W_TEAMS: a new ticket"])
            page = conn.execute("SELECT * FROM page WHERE work_item_id = ?", (wid,)).fetchone()
            self.assertEqual((page["member"], page["role"], page["attempts"], page["status"], page["every_minutes"], page["max_attempts"]),
                             ("oncall1", "ON_CALL", 1, "OPEN", 5, 3))
            mail = conn.execute("SELECT * FROM notification WHERE work_item_id = ? AND COALESCE(channel, 'EMAIL') = 'EMAIL'"
                                " AND recipient_role = 'PAGE'", (wid,)).fetchall()
            self.assertEqual([(m["recipient"], m["page_id"]) for m in mail], [("oncall1", 1)])
            self.assertEqual(mail[0]["subject"], f"[{wid}] Page 1 of 3: P1 on PMO Helpdesk")
            self.assertNotIn("analyser", mail[0]["body"])
            run = conn.execute("SELECT outcome, detail FROM workflow_run WHERE event_id = 'W_BAD_E1'").fetchone()
            self.assertEqual(run["outcome"], "ERROR")
            self.assertIn("quiet is not set up or is off", run["detail"])
            # the page's card went to the channel that carries pages, not to the quiet one
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM notification WHERE target_id = 'quiet'").fetchone()[0], 0)
            # the page's email says how to answer
            from psaspine import outbox
            due = outbox.pending(conn, allowed_domains=("pmcne.ph",), dry_run=True)
            mine = [d for d in due if d["to"] == "oncall1@pmcne.ph"]
            self.assertEqual(len(mine), 1)
            self.assertIn("press Acknowledge", mine[0]["body"])
        finally:
            conn.close()

    def test_a_page_repeats_until_answered_and_hands_to_the_duty_manager(self):
        from psaspine import paging
        conn = db.connect(self.db_path)
        try:
            with self.assertRaises(LookupError):
                paging.page_oncall(conn, self.wid, at=datetime(2026, 10, 2, 9, 0), actor="bob")
            pid = paging.page_oncall(conn, self.wid, at=self.at, actor="bob", note="Ward 3 printer, nurses waiting")
            self.assertEqual(paging.page_oncall(conn, self.wid, at=self.at, actor="bob"), pid)      # not doubled
            conn.commit()

            def sent(page_id):
                return conn.execute("SELECT COUNT(*) FROM notification WHERE page_id = ? AND channel = 'EMAIL'", (page_id,)).fetchone()[0]
            self.assertEqual(sent(pid), 1)
            self.assertEqual(paging.tick(conn, at=self.at + timedelta(minutes=3)), {"open": 1, "sent": 0, "ended": 0, "escalated": 0})
            self.assertEqual(paging.tick(conn, at=self.at + timedelta(minutes=5))["sent"], 1)
            self.assertEqual(paging.tick(conn, at=self.at + timedelta(minutes=10))["sent"], 1)
            self.assertEqual((sent(pid), paging.get(conn, pid)["attempts"]), (3, 3))
            c = paging.tick(conn, at=self.at + timedelta(minutes=15))
            self.assertEqual((c["ended"], c["escalated"]), (1, 1))
            self.assertEqual(paging.get(conn, pid)["status"], "EXHAUSTED")
            dm = [p for p in paging.open_for(conn, self.wid)]
            self.assertEqual([(p["member"], p["role"], p["attempts"]) for p in dm], [("dm1", "DUTY_MANAGER", 1)])
            self.assertIn("did not answer 3 pages", dm[0]["note"])
            self.assertEqual(paging.tick(conn, at=self.at + timedelta(minutes=16))["sent"], 0)
            row = paging.acknowledge(conn, dm[0]["page_id"], at=self.at + timedelta(minutes=17), actor="dm1")
            self.assertEqual((row["status"], row["ended_by"]), ("ACKNOWLEDGED", "dm1"))
            with self.assertRaises(paging.Refused):
                paging.acknowledge(conn, dm[0]["page_id"], at=self.at, actor="dm1")
            self.assertEqual(paging.tick(conn, at=self.at + timedelta(minutes=30)), {"open": 0, "sent": 0, "ended": 0, "escalated": 0})
            events = [r[0] for r in conn.execute("SELECT detail FROM ticket_event WHERE work_item_id = ? ORDER BY ticket_event_id", (self.wid,))]
            for want in ("page 1 of 3 to oncall1 (on call)", "page 3 of 3 to oncall1 (on call)",
                         "page to oncall1 unanswered after 3 attempts", "page 1 of 3 to dm1 (duty manager)",
                         "page to dm1 acknowledged by dm1"):
                self.assertTrue(any(want in e for e in events), want)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'PAGE'").fetchone()[0], 4)
            # a note by the person paged answers the page; a closed ticket ends it; stop says why
            other = tickets.open_ticket(conn, board_id="IT_HELP", summary="Second", impact="I3", urgency="U3",
                                        requested_by=None, at=self.at, entity_id="PMC")
            p2 = paging.page_oncall(conn, other, at=self.at, actor="bob")
            board.add_note(conn, other, body="On my way", flag="INTERNAL", actor="OnCall1", at=self.at)
            self.assertEqual(paging.get(conn, p2)["status"], "ACKNOWLEDGED")
            p3 = paging.start(conn, other, member="bob", at=self.at, actor="alice")
            self.assertEqual(paging.get(conn, p3)["role"], "NAMED")
            board.change_status(conn, other, "IT_HELP.RESOLVED", at=self.at, actor="bob")
            self.assertEqual(paging.tick(conn, at=self.at + timedelta(minutes=1))["ended"], 1)
            self.assertEqual(paging.get(conn, p3)["status"], "STOPPED")
            with self.assertRaises(paging.Refused):
                paging.start(conn, other, member="bob", at=self.at, actor="alice")
            p4 = paging.page_oncall(conn, self.wid, at=self.at + timedelta(hours=1), actor="bob")
            row = paging.stop(conn, p4, at=self.at + timedelta(hours=1), actor="alice", reason="handled by phone")
            self.assertEqual(row["status"], "STOPPED")
            self.assertIn("stopped by alice: handled by phone",
                          conn.execute("SELECT detail FROM ticket_event WHERE work_item_id = ? ORDER BY ticket_event_id DESC", (self.wid,)).fetchone()[0])
            with self.assertRaises(paging.Refused):
                paging.start(conn, self.wid, member="bob", every_minutes=0, at=self.at, actor="alice")
        finally:
            conn.close()

    def test_the_ticket_pages_and_acknowledges_and_setup_names_the_channels(self):
        bob, carol, oncall = self._cookie_for("bob"), self._cookie_for("carol"), self._cookie_for("oncall1")
        root = self._cookie_for("alice", is_sysadmin=True)
        status, _, body = self._call("GET", f"/ticket/{self.wid}", cookie=bob)
        self.assertIn("Page the on-call", body)
        status, _, _ = self._call("POST", f"/ticket/{self.wid}/page", cookie=carol, form={"note": "x"})
        self.assertEqual(status, "404 Not Found")
        status, headers, _ = self._call("POST", f"/ticket/{self.wid}/page", cookie=bob, form={"note": "nurses waiting"})
        self.assertEqual(status, "303 See Other")
        self.assertIn("msg=Paging+oncall1", dict(headers)["Location"])
        status, _, body = self._call("GET", f"/ticket/{self.wid}", cookie=bob)
        self.assertIn("Paging <b>oncall1</b> (on call): attempt 1 of 3, every 5 min", body)
        self.assertIn("nurses waiting", body)
        self.assertIn("/page/1/ack", body)
        self.assertIn("Stop paging", body)
        self.assertNotIn("Page the on-call", body)
        status, _, body = self._call("GET", f"/ticket/{self.wid}", cookie=carol)     # may look, not answer
        self.assertIn("Paging <b>oncall1</b>", body)
        self.assertNotIn("/page/1/ack", body)
        status, _, _ = self._call("POST", f"/ticket/{self.wid}/page/1/ack", cookie=self._cookie_for("stranger"))
        self.assertEqual(status, "404 Not Found")
        status, _, _ = self._call("POST", f"/ticket/{self.wid}/page/9/ack", cookie=oncall)
        self.assertEqual(status, "404 Not Found")
        status, headers, _ = self._call("POST", f"/ticket/{self.wid}/page/1/ack", cookie=oncall)
        self.assertIn("msg=Page+acknowledged", dict(headers)["Location"])
        status, headers, _ = self._call("POST", f"/ticket/{self.wid}/page/1/ack", cookie=oncall)
        self.assertIn("already+ended", dict(headers)["Location"])
        self._call("POST", f"/ticket/{self.wid}/page", cookie=bob, form={})
        status, headers, _ = self._call("POST", f"/ticket/{self.wid}/page/2/stop", cookie=bob, form={"reason": "by phone"})
        self.assertIn("msg=Paging+stopped", dict(headers)["Location"])
        conn = db.connect(self.db_path)
        try:
            self.assertEqual([r[0] for r in conn.execute("SELECT status FROM page ORDER BY page_id")], ["ACKNOWLEDGED", "STOPPED"])
        finally:
            conn.close()
        # Setup › Integrations › Teams channels
        status, _, body = self._call("GET", "/admin/integrations", cookie=root)
        self.assertIn("Teams channels", body)
        self.assertIn("<code>helpdesk-alerts</code>", body)
        self.assertIn("Pages: yes", body)
        self.assertIn("Pages: no", body)
        status, headers, _ = self._call("POST", "/admin/integrations/teams/add", cookie=root, form={"target_id": "Ward 3", "label": "x"})
        self.assertIn("err=A+channel+name+is", dict(headers)["Location"])
        status, headers, _ = self._call("POST", "/admin/integrations/teams/add", cookie=root,
                                        form={"target_id": "ward-3", "label": "Ward 3 nurses", "pages": "1"})
        self.assertIn("msg=Teams+channel+ward-3+added", dict(headers)["Location"])
        status, headers, _ = self._call("POST", "/admin/integrations/teams/toggle", cookie=root, form={"target_id": "quiet"})
        self.assertIn("msg=Teams+channel+updated", dict(headers)["Location"])
        status, headers, _ = self._call("POST", "/admin/integrations/teams/pages", cookie=root, form={"target_id": "quiet", "pages": "1"})
        self.assertIn("msg=Teams+channel+updated", dict(headers)["Location"])
        status, _, _ = self._call("POST", "/admin/integrations/teams/add", cookie=bob, form={"target_id": "x-y", "label": "x"})
        self.assertEqual(status, "403 Forbidden")
        conn = db.connect(self.db_path)
        try:
            rows = {r["target_id"]: (r["inactive"], r["pages"]) for r in conn.execute("SELECT * FROM channel_target")}
            self.assertEqual(rows, {"helpdesk-alerts": (0, 1), "quiet": (1, 1), "ward-3": (0, 1)})
            conn.execute("INSERT INTO workflow (workflow_id, board_id, name, table_type) VALUES ('W1', 'IT_HELP', 'W1', 'TICKET')")
            conn.commit()
        finally:
            conn.close()
        # the rules editor: a notify as a Teams card needs a channel; a page needs none
        status, _, body = self._call("GET", "/admin/rules/W1", cookie=root)
        self.assertIn("name=channel0", body)
        self.assertIn("<option value='helpdesk-alerts'>IT Helpdesk › Alerts (helpdesk-alerts)</option>", body)
        self.assertNotIn("value='quiet'", body)                                    # off: not offered
        status, headers, _ = self._call("POST", "/admin/rules/W1/event", cookie=root, form={
            "event_name": "New P1 to Teams", "fires_on": "ON_CREATE", "mode": "ONCE", "act0": "NOTIFY", "channel0": "TEAMS", "detail0": "new"})
        self.assertIn("needs+a+channel", dict(headers)["Location"])
        status, headers, _ = self._call("POST", "/admin/rules/W1/event", cookie=root, form={
            "event_name": "New P1 to Teams", "fires_on": "ON_CREATE", "mode": "ONCE", "act0": "NOTIFY", "channel0": "TEAMS",
            "target0": "helpdesk-alerts", "detail0": "new", "act1": "ESCALATE", "role1": "ON_CALL", "channel1": "PAGE", "target1": "helpdesk-alerts"})
        self.assertEqual(status, "303 See Other")
        conn = db.connect(self.db_path)
        try:
            acts = conn.execute("SELECT action, channel, target_id, notify_role FROM workflow_action WHERE event_id = 'W1_E1' ORDER BY sort_order").fetchall()
            self.assertEqual([tuple(a) for a in acts], [("NOTIFY", "TEAMS", "helpdesk-alerts", None), ("ESCALATE", "PAGE", None, "ON_CALL")])
        finally:
            conn.close()
        status, _, body = self._call("GET", "/admin/rules/W1", cookie=root)
        self.assertIn("<span class=chip>Teams helpdesk-alerts</span>", body)
        self.assertIn("<span class=chip>page</span>", body)

    def test_the_cli_serves_the_teams_sender_and_runs_the_paging_clock(self):
        import subprocess
        from psaspine import channels, paging
        conn = db.connect(self.db_path)
        channels.queue_teams(conn, self.wid, "helpdesk-alerts", subject="[x] Notify: P2 on IT_HELP", body="hello", at=self.at)
        paging.start(conn, self.wid, member="oncall1", role="ON_CALL", at=datetime.now() - timedelta(minutes=30), actor="bob")
        conn.commit()
        conn.close()
        root = Path(__file__).resolve().parent.parent
        r = subprocess.run([sys.executable, "-m", "psaspine", "outbox-pending", self.db_path, "--channel", "TEAMS",
                            "--allowed-domain", "pmcne.ph", "--dry-run", "--desk-url", "https://desk.pmcne.ph"],
                           cwd=root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        items = _json.loads(r.stdout)
        self.assertEqual([i["target"] for i in items], ["helpdesk-alerts", "helpdesk-alerts"])   # the rule's card and the page's
        self.assertIn("Open on the desk", r.stdout)
        r = subprocess.run([sys.executable, "-m", "psaspine", "outbox-pending", self.db_path, "--channel", "TEAMS",
                            "--allowed-domain", "pmcne.ph", "--desk-url", "http://desk"], cwd=root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("https://", r.stderr)
        r = subprocess.run([sys.executable, "-m", "psaspine", "run-rules", self.db_path], cwd=root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pages: 1 open, 1 repeated, 0 ended, 0 escalated", r.stdout)
        conn = db.connect(self.db_path)
        try:
            self.assertEqual(conn.execute("SELECT attempts FROM page").fetchone()[0], 2)
        finally:
            conn.close()

class KnowledgeFilesTest(unittest.TestCase):
    """051: a picture on an article, kept the way a ticket's files are, reviewed
    before a requester sees it, shown in the text as ![caption](file:N)."""
    tearDown = WebWSGITest.tearDown

    def setUp(self) -> None:
        WebWSGITest.setUp(self)
        self.at = datetime(2026, 9, 29, 10)

    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for
    _send = AttachmentsWebTest._send

    def _article(self, body="Step 1: find the switch.\n\n![Where the switch is](file:1)\n\nThen read [the manual](file:2)."):
        from psaspine import knowledge, security
        conn = db.connect(self.db_path)
        try:
            security.ensure_roles(conn)
            conn.execute("INSERT OR REPLACE INTO board_member (board_id, member, access) VALUES ('IT_HELP', 'reader', 'READ')")
            security.assign(conn, "reader", "READ_ONLY", at=self.at, actor="root")             # knowledge READ, no writing
            aid = knowledge.create(conn, title="Label printer prints blank", body=body, audience="REQUESTER",
                                   at=self.at, actor="alice")
            conn.commit()
        finally:
            conn.close()
        return aid

    def test_a_file_is_kept_reviewed_shown_and_removed(self):
        import hashlib
        from psaspine import kbfiles
        aid = self._article()
        conn = db.connect(self.db_path)
        try:
            with self.assertRaises(LookupError):
                kbfiles.add(conn, "KB-9999", _png(), "x.png", actor="alice", at=self.at)
            with self.assertRaises(kbfiles.Refused):
                kbfiles.add(conn, aid, b"MZ\x90\x00 program", "setup.exe", actor="alice", at=self.at)
            with self.assertRaises(kbfiles.Refused):
                kbfiles.add(conn, aid, b"", "empty.png", actor="alice", at=self.at)
            r = kbfiles.add(conn, aid, _png(), "switch.png", caption="  Where the  switch is ", actor="alice", at=self.at)
            conn.commit()
            self.assertEqual((r["file_id"], r["media_type"]), (1, "image/png"))
            row, data = kbfiles.read(conn, 1)
            self.assertTrue(data.startswith(b"\x89PNG"))
            self.assertEqual(hashlib.sha256(data).hexdigest(), row["sha256"])
            self.assertEqual((row["review_status"], row["caption"], row["filename"]), ("PENDING", "Where the switch is", "switch.png"))
            self.assertTrue(kbfiles.kb_dir(conn).name.endswith("-kb"))
            self.assertTrue(kbfiles._path(kbfiles.kb_dir(conn), row["sha256"]).exists())
            self.assertTrue(kbfiles.visible(row, portal=False))
            self.assertFalse(kbfiles.visible(row, portal=True))
            url = kbfiles.resolver(conn, aid, portal=False, base="/x/")
            self.assertEqual((url(1), url(2)), ("/x/1", None))
            self.assertIsNone(kbfiles.resolver(conn, aid, portal=True, base="/x/")(1))
            with self.assertRaises(ValueError):
                kbfiles.review(conn, 1, "MAYBE", actor="alice", at=self.at)
            row = kbfiles.review(conn, 1, "CLEAR", actor="alice", at=self.at)
            self.assertEqual((row["review_status"], row["reviewed_by"]), ("CLEARED", "alice"))
            self.assertTrue(kbfiles.visible(row, portal=True))
            row = kbfiles.review(conn, 1, "WITHHOLD", actor="alice", at=self.at)
            self.assertFalse(kbfiles.visible(row, portal=False))
            self.assertTrue(kbfiles.remove(conn, 1, actor="root", at=self.at))
            self.assertFalse(kbfiles.remove(conn, 1, actor="root", at=self.at))
            self.assertFalse(kbfiles._path(kbfiles.kb_dir(conn), row["sha256"]).exists())
            with self.assertRaises(kbfiles.Removed):
                kbfiles.read(conn, 1)
            self.assertEqual(kbfiles.of_article(conn, aid), [])
            self.assertEqual([r[0] for r in conn.execute("SELECT detail FROM audit_event WHERE action = 'KB_FILE' ORDER BY audit_id")][::3],
                             [f"added to {aid}: switch.png (image/png, {len(_png())} B received, {r['size_stored']} B stored); awaiting review",
                              f"removed from {aid}: switch.png"])
        finally:
            conn.close()

    def test_the_article_shows_its_pictures_to_the_desk_at_once_and_to_requesters_once_cleared(self):
        from psaspine import knowledge
        aid = self._article()
        alice, reader, root = self._cookie_for("alice"), self._cookie_for("reader"), self._cookie_for("root", is_sysadmin=True)
        nurse = self._cookie_for("nurse", email="nurse@pmcne.ph")
        status, headers, _ = self._send("POST", f"/kb/{aid}/file", cookie=alice, fields={"caption": "Where the switch is"},
                                        files=[("switch.png", _png())])
        self.assertEqual(status, "303 See Other")
        self.assertIn("File+1+added", headers["Location"])
        status, headers, _ = self._send("POST", f"/kb/{aid}/file", cookie=alice, fields={"caption": "The manual"},
                                        files=[("manual.pdf", b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\n")])
        self.assertIn("File+2+added", headers["Location"])
        status, headers, _ = self._send("POST", f"/kb/{aid}/file", cookie=alice, fields={}, files=[("run.exe", b"MZ\x90\x00")])
        self.assertIn("Not+kept%3A+programs", headers["Location"])
        status, _, _ = self._send("POST", f"/kb/{aid}/file", cookie=reader, fields={}, files=[("x.png", _png())])
        self.assertEqual(status, "403 Forbidden")
        # the desk sees a pending file at once, as a picture in the text and in the Files card
        status, _, body = self._call("GET", f"/kb/{aid}", cookie=alice)
        self.assertIn(f'<img src="/kb/{aid}/file/1" alt="Where the switch is" class=kbimg loading=lazy>', body)
        self.assertIn(f'<a href="/kb/{aid}/file/2">the manual</a>', body)
        self.assertIn("awaiting review", body)
        self.assertIn(f"<code>![Where the switch is](file:1)</code>", body)
        self.assertIn(f"<code>[The manual](file:2)</code>", body)
        self.assertIn("name=decision value=CLEAR", body)
        self.assertNotIn(">Remove<", body)                                        # not an administrator
        status, headers, payload = self._send("GET", f"/kb/{aid}/file/1", cookie=reader)
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "image/png")
        self.assertTrue(headers["Content-Disposition"].startswith('inline; filename="switch.png"'))
        self.assertEqual(headers["Content-Security-Policy"], "sandbox")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertTrue(payload.startswith(b"\x89PNG"))
        status, headers, _ = self._send("GET", f"/kb/{aid}/file/2", cookie=reader)
        self.assertTrue(headers["Content-Disposition"].startswith('attachment; filename="manual.pdf"'))
        status, _, _ = self._send("GET", f"/kb/{aid}/file/1", cookie=nurse)
        self.assertEqual(status, "403 Forbidden")
        # the requester's help page: nothing until a person clears the file
        conn = db.connect(self.db_path)
        knowledge.set_status(conn, aid, "PUBLISHED", at=self.at, actor="alice")
        conn.commit()
        conn.close()
        status, _, body = self._call("GET", f"/my/help/{aid}", cookie=nurse)
        self.assertEqual(status, "200 OK")
        self.assertIn("[image not shown: Where the switch is]", body)
        self.assertIn("[the manual: file not shown]", body)
        self.assertNotIn("<img", body)
        status, _, _ = self._send("GET", f"/my/help/{aid}/file/1", cookie=nurse)
        self.assertEqual(status, "404 Not Found")
        for n in (1, 2):
            status, headers, _ = self._call("POST", f"/kb/{aid}/file/{n}/review", cookie=alice, form={"decision": "CLEAR"})
            self.assertIn("cleared", dict(headers)["Location"])
        status, _, body = self._call("GET", f"/my/help/{aid}", cookie=nurse)
        self.assertIn(f'<img src="/my/help/{aid}/file/1" alt="Where the switch is" class=kbimg loading=lazy>', body)
        self.assertIn(f"<a href='/my/help/{aid}/file/2'>The manual</a>", body)
        status, headers, payload = self._send("GET", f"/my/help/{aid}/file/1", cookie=nurse)
        self.assertEqual((status, headers["Content-Type"]), ("200 OK", "image/png"))
        # withheld: nobody is served it, and the text says so; a reader may not review; an administrator removes
        status, _, _ = self._call("POST", f"/kb/{aid}/file/1/review", cookie=reader, form={"decision": "WITHHOLD"})
        self.assertEqual(status, "403 Forbidden")
        self._call("POST", f"/kb/{aid}/file/1/review", cookie=alice, form={"decision": "WITHHOLD"})
        status, _, _ = self._send("GET", f"/kb/{aid}/file/1", cookie=alice)
        self.assertEqual(status, "404 Not Found")
        status, _, body = self._call("GET", f"/kb/{aid}", cookie=alice)
        self.assertIn("[image not shown: Where the switch is]", body)
        self.assertIn("withheld", body)
        status, _, _ = self._call("POST", f"/kb/{aid}/file/2/remove", cookie=alice)
        self.assertEqual(status, "403 Forbidden")
        status, headers, _ = self._call("POST", f"/kb/{aid}/file/2/remove", cookie=root)
        self.assertIn("manual.pdf+removed", dict(headers)["Location"])
        status, _, _ = self._send("GET", f"/kb/{aid}/file/2", cookie=alice)
        self.assertEqual(status, "404 Not Found")
        status, _, _ = self._send("GET", f"/kb/{aid}/file/9", cookie=alice)
        self.assertEqual(status, "404 Not Found")
        status, _, body = self._call("GET", f"/kb/{aid}/edit", cookie=alice)
        self.assertIn("![caption](file:3)", body)

class ApiScopesTest(unittest.TestCase):
    """Gap 8: a token's scope. RAISE raises and reads its own (as before); READ
    lists and reads every ticket on its board and the configurations; WRITE
    adds a note, sets a status or an owner, applied the way the desk applies
    them. One board still; a restricted board's reads audited like a person's."""
    _api = MachineApiTest._api
    _conn = MachineApiTest._conn

    def setUp(self) -> None:
        from psaspine import configurations
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(_target(self.tmp))
        conn = _fresh(self.tmp)
        self.at = datetime(2026, 9, 30, 9, 0)
        setup.apply_starter(conn, "IT_HELP", actor="t", at=self.at)
        conn.executescript(
            "INSERT OR REPLACE INTO board (board_id,display_name,phase,fulfiller_group,owner,deputy,is_live,restricted)"
            " VALUES ('PHI','PHI Board','2','Clin','a','b',1,1);"
            "INSERT OR REPLACE INTO board_status (board_status_id,board_id,name,escalation_status,is_default)"
            " VALUES ('PHI.NEW','PHI','New','NOT_RESPONDED',1);"
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','bob','WORK');")
        with self.assertRaises(ValueError):
            webapi.create_token(conn, label="x", board_id="IT_HELP", at=self.at, scope="ROOT")
        _, self.raise_tok = webapi.create_token(conn, label="monitor", board_id="IT_HELP", at=self.at)
        self.read_id, self.read_tok = webapi.create_token(conn, label="dashboard", board_id="IT_HELP", at=self.at, scope="READ")
        self.write_id, self.write_tok = webapi.create_token(conn, label="runbook tool", board_id="IT_HELP", at=self.at, scope="WRITE")
        self.phi_id, self.phi_tok = webapi.create_token(conn, label="ward board", board_id="PHI", at=self.at, scope="READ")
        self.mine = tickets.open_ticket(conn, board_id="IT_HELP", summary="Printer down in Ward 3", impact="I3", urgency="U3",
                                        requested_by="nurse@pmcne.ph", description="Zebra at the station", at=self.at, entity_id="PMC")
        self.old = tickets.open_ticket(conn, board_id="IT_HELP", summary="Old one", impact="I3", urgency="U3",
                                       requested_by=None, at=datetime(2026, 9, 1, 9), entity_id="PMC")
        board.change_status(conn, self.old, "IT_HELP.RESOLVED", at=datetime(2026, 9, 2, 9), actor="bob")
        self.other = tickets.open_ticket(conn, board_id="PHI", summary="Bedside monitor", impact="I3", urgency="U3",
                                         requested_by=None, at=self.at, entity_id="PMC")
        self.cfg = configurations.create(conn, name="WARD3-LBL01", entity_id="PMC", config_type="PRINTER",
                                         serial_number="ZX-1001", at=self.at, actor="alice")
        conn.commit()
        conn.close()
        self.config = Config(session_secret=_secrets.token_bytes(32))
        self.raw = make_app(self.db_path, config=self.config, clock=lambda: self.at)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_a_scope_says_what_a_token_may_read(self):
        status, _, data = self._api("GET", "/api/v1/tickets", token=self.raise_tok)
        self.assertEqual((status, data["error"]), ("403 Forbidden", "this token's scope is RAISE; READ is needed"))
        status, _, data = self._api("GET", f"/api/v1/tickets/{self.mine}", token=self.raise_tok)
        self.assertEqual(status, "404 Not Found")                                 # not its own
        status, _, data = self._api("POST", "/api/v1/tickets", token=self.raise_tok, payload={"summary": "Link down"})
        raised = data["id"]
        status, _, data = self._api("GET", f"/api/v1/tickets/{raised}", token=self.raise_tok)
        self.assertEqual(status, "200 OK")
        self.assertNotIn("status", data)                                           # the short shape, as before
        status, _, data = self._api("GET", "/api/v1/tickets", token=self.read_tok)
        self.assertEqual(status, "200 OK")
        self.assertEqual(([t["id"] for t in data["tickets"]], data["count"], data["total"]), ([raised, self.mine], 2, 2))
        self.assertEqual(data["tickets"][1]["status"], "New")
        self.assertEqual(data["tickets"][1]["description"], "Zebra at the station")
        status, _, data = self._api("GET", "/api/v1/tickets?state=closed", token=self.read_tok)
        self.assertEqual([t["id"] for t in data["tickets"]], [self.old])
        status, _, data = self._api("GET", "/api/v1/tickets?state=all&since=2026-09-15&limit=1", token=self.read_tok)
        self.assertEqual((data["count"], data["total"]), (1, 2))
        for bad in ("state=bogus", "since=2026-13-01", "limit=0", "limit=201", "offset=x"):
            status, _, _ = self._api("GET", "/api/v1/tickets?" + bad, token=self.read_tok)
            self.assertEqual(status, "400 Bad Request", bad)
        status, _, data = self._api("GET", f"/api/v1/tickets/{self.mine}", token=self.read_tok)
        self.assertEqual((status, data["board"], data["owner"], data["open"]), ("200 OK", "IT_HELP", None, True))
        status, _, _ = self._api("GET", f"/api/v1/tickets/{self.other}", token=self.read_tok)   # another board
        self.assertEqual(status, "404 Not Found")
        status, _, data = self._api("PATCH", f"/api/v1/tickets/{self.mine}", token=self.read_tok, payload={"note": "x"})
        self.assertEqual(status, "403 Forbidden")
        status, _, _ = self._api("GET", "/api/v1/configurations", token=self.raise_tok)
        self.assertEqual(status, "403 Forbidden")
        status, _, data = self._api("GET", "/api/v1/configurations?type=printer", token=self.read_tok)
        self.assertEqual((status, data["count"], data["configurations"][0]["name"], data["configurations"][0]["type"]),
                         ("200 OK", 1, "WARD3-LBL01", "PRINTER"))
        self.assertNotIn("contact_id", data["configurations"][0])                 # the person never comes with the machine
        status, _, data = self._api("GET", "/api/v1/configurations?q=ZX-10", token=self.read_tok)
        self.assertEqual(data["total"], 1)
        status, _, data = self._api("GET", f"/api/v1/configurations/{self.cfg}", token=self.read_tok)
        self.assertEqual((status, data["id"], data["serial_number"]), ("200 OK", self.cfg, "ZX-1001"))
        status, _, _ = self._api("GET", "/api/v1/configurations/CFG-none", token=self.read_tok)
        self.assertEqual(status, "404 Not Found")
        status, _, _ = self._api("POST", "/api/v1/configurations", token=self.read_tok, payload={})
        self.assertEqual(status, "405 Method Not Allowed")
        status, _, _ = self._api("GET", "/api/v1/people", token=self.read_tok)
        self.assertEqual(status, "404 Not Found")
        # a row from before the scope column reads as RAISE
        conn = self._conn()
        conn.execute("UPDATE api_token SET scope = NULL WHERE token_id = ?", (self.read_id,))
        conn.commit()
        conn.close()
        status, _, data = self._api("GET", "/api/v1/tickets", token=self.read_tok)
        self.assertEqual(status, "403 Forbidden")

    def test_a_write_token_notes_moves_and_assigns_the_way_the_desk_does(self):
        status, _, data = self._api("PATCH", f"/api/v1/tickets/{self.mine}", token=self.write_tok, payload={})
        self.assertEqual(status, "400 Bad Request")
        for payload, field in (({"note": ""}, "note"), ({"note": "x", "flag": "SECRET"}, "flag"), ({"status": "Nope"}, "status"),
                               ({"owner": "zed"}, "owner"), ({"priority": "P1"}, "priority")):
            status, _, data = self._api("PATCH", f"/api/v1/tickets/{self.mine}", token=self.write_tok, payload=payload)
            self.assertEqual((status, data["field"]), ("422 Unprocessable Entity", field), payload)
        status, _, _ = self._api("PATCH", f"/api/v1/tickets/{self.other}", token=self.write_tok, payload={"note": "x"})
        self.assertEqual(status, "404 Not Found")
        status, _, data = self._api("PATCH", f"/api/v1/tickets/{self.mine}", token=self.write_tok,
                                    payload={"note": "Restarted the print spooler; PhilHealth 12-345678901-2 was on the label",
                                             "owner": "bob", "status": "In Progress"})
        self.assertEqual(status, "200 OK", data)
        self.assertEqual((data["owner"], data["status"], data["open"]), ("bob", "In Progress", True))
        self.assertEqual(data["applied"], ["owner - -> bob", "internal note", "status In Progress"])
        conn = self._conn()
        try:
            actor = f"api:{self.write_id}"
            events = conn.execute("SELECT kind, actor, note_flag FROM ticket_event WHERE work_item_id = ? AND actor = ?"
                                  " ORDER BY ticket_event_id", (self.mine, actor)).fetchall()
            self.assertIn(("NOTE", actor, "INTERNAL"), [tuple(e) for e in events])
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM data_quality WHERE subject_id = ? AND code = 'PHI_PHILHEALTH_NUMBER'",
                                          (self.mine,)).fetchone()[0], 1)                  # flagged, never dropped
            audit = conn.execute("SELECT detail FROM audit_event WHERE action = 'API_UPDATE'").fetchone()[0]
            self.assertEqual(audit, "owner - -> bob; internal note; status In Progress")
        finally:
            conn.close()
        status, _, data = self._api("PATCH", f"/api/v1/tickets/{self.mine}", token=self.write_tok,
                                    payload={"status": "resolved", "note": "Fixed", "flag": "DISCUSSION"})
        self.assertEqual((status, data["status"], data["open"]), ("200 OK", "Resolved", False))
        status, _, data = self._api("PATCH", f"/api/v1/tickets/{self.mine}", token=self.write_tok, payload={"owner": ""})
        self.assertEqual((status, data["owner"]), ("200 OK", None))

    def test_a_token_on_a_restricted_board_is_audited_on_every_read(self):
        status, _, data = self._api("GET", "/api/v1/tickets", token=self.phi_tok)
        self.assertEqual((status, [t["id"] for t in data["tickets"]]), ("200 OK", [self.other]))
        status, _, _ = self._api("GET", f"/api/v1/tickets/{self.other}", token=self.phi_tok)
        self.assertEqual(status, "200 OK")
        self._api("GET", "/api/v1/tickets", token=self.read_tok)                   # an open board: no audit row
        conn = self._conn()
        try:
            rows = conn.execute("SELECT actor, subject_id, detail FROM audit_event WHERE action = 'RESTRICTED_READ' ORDER BY audit_id").fetchall()
            self.assertEqual([tuple(r) for r in rows], [(f"api:{self.phi_id}", "PHI", "api list open 1 ticket(s)"),
                                                        (f"api:{self.phi_id}", "PHI", f"api read {self.other}")])
        finally:
            conn.close()


class SalesTest(unittest.TestCase):
    """052: opportunities and quotes. The pipeline, quote totals, the stage
    moves and the agreement a win drafts; the FINANCE gate on the pages."""

    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for

    def setUp(self) -> None:
        WebWSGITest.setUp(self)
        self.addCleanup(self.tmp.cleanup)
        self.at = datetime(2026, 9, 29, 10)
        self.alice = self._cookie_for("alice")
        self.root = self._cookie_for("root", is_sysadmin=True)

    def _conn(self):
        conn = db.connect(self.db_path)
        self.addCleanup(conn.close)
        return conn

    # ------------------------------------------------------------ engine

    def test_an_opportunity_is_created_edited_and_moved_and_a_loss_says_why(self):
        from psaspine import sales
        conn = self._conn()
        with self.assertRaises(sales.Refused):
            sales.create(conn, name="", at=self.at, actor="alice")
        with self.assertRaises(sales.Refused):
            sales.create(conn, name="Won already", stage="WON", at=self.at, actor="alice")
        with self.assertRaises(sales.Refused):
            sales.create(conn, name="Bad company", entity_id="NOPE", at=self.at, actor="alice")
        with self.assertRaises(sales.Refused):
            sales.create(conn, name="Bad date", expected_on="soon", at=self.at, actor="alice")
        with self.assertRaises(sales.Refused):
            sales.create(conn, name="Bad odds", probability="140", at=self.at, actor="alice")
        oid = sales.create(conn, name="Ward 3 endpoint refresh", entity_id="PMC", amount="250,000", currency="php",
                           expected_on="2026-12-15", owner="alice", at=self.at, actor="alice")
        self.assertEqual(oid, "OPP-0001")
        o = sales.get(conn, oid)
        self.assertEqual((o["stage"], o["probability"], o["amount"], o["currency"], o["entity_name"]),
                         ("LEAD", 10, 250000.0, "PHP", "Premiere Medical Center Nueva Ecija"))
        self.assertEqual(sales.update(conn, oid, at=self.at, actor="alice", name="Ward 3 endpoint refresh"), [])
        self.assertEqual(sales.update(conn, oid, at=self.at, actor="alice", probability="25", owner="bob"),
                         ["probability 10 -> 25", "owner alice -> bob"])
        self.assertIsNone(sales.move(conn, oid, "QUALIFIED", at=self.at, actor="alice"))
        self.assertEqual(sales.get(conn, oid)["probability"], 40)                     # the stage's default odds
        with self.assertRaises(sales.Refused):
            sales.move(conn, oid, "LOST", at=self.at, actor="alice")                  # a loss says why
        with self.assertRaises(sales.Refused):
            sales.move(conn, oid, "SIDEWAYS", at=self.at, actor="alice")
        self.assertIsNone(sales.move(conn, oid, "LOST", at=self.at, actor="alice", reason="Budget deferred to 2027"))
        o = sales.get(conn, oid)
        self.assertEqual((o["stage"], o["probability"], o["lost_reason"]), ("LOST", 0, "Budget deferred to 2027"))
        self.assertIsNotNone(o["closed_at"])
        with self.assertRaises(sales.Refused):
            sales.update(conn, oid, at=self.at, actor="alice", name="Reopened")        # closed stays closed
        with self.assertRaises(sales.Refused):
            sales.move(conn, oid, "LEAD", at=self.at, actor="alice")
        with self.assertRaises(sales.Refused):
            sales.create_quote(conn, oid, name="Too late", at=self.at, actor="alice")
        trail = [r["detail"] for r in conn.execute(
            "SELECT detail FROM audit_event WHERE action = 'SALES' AND subject_id = ? ORDER BY audit_id", (oid,))]
        self.assertEqual(trail[0], "created (Lead): Ward 3 endpoint refresh")
        self.assertIn("lost: Budget deferred to 2027", trail)

    def test_a_quote_totals_its_lines_with_tax_and_moves_the_opportunity_as_it_goes(self):
        from psaspine import agreements, sales
        conn = self._conn()
        oid = sales.create(conn, name="Radiology workstation", entity_id="PMC", amount="100000", at=self.at, actor="alice")
        with self.assertRaises(sales.Refused):
            sales.create_quote(conn, oid, name="", at=self.at, actor="alice")
        with self.assertRaises(sales.Refused):
            sales.create_quote(conn, oid, name="Over", tax_percent="120", at=self.at, actor="alice")
        qid = sales.create_quote(conn, oid, name="Option A", valid_until="2026-10-31", tax_percent="12", at=self.at, actor="alice")
        self.assertEqual(qid, "Q-0001")
        with self.assertRaises(sales.Refused):
            sales.set_quote_status(conn, qid, "SENT", at=self.at, actor="alice")           # no lines, not sent
        with self.assertRaises(sales.Refused):
            sales.add_line(conn, qid, description="", quantity="1", unit_price="10", at=self.at, actor="alice")
        with self.assertRaises(sales.Refused):
            sales.add_line(conn, qid, description="Zero", quantity="0", unit_price="10", at=self.at, actor="alice")
        with self.assertRaises(sales.Refused):
            sales.add_line(conn, qid, description="Negative", quantity="1", unit_price="-5", at=self.at, actor="alice")
        with self.assertRaises(sales.Refused):
            sales.add_line(conn, qid, description="Words", quantity="two", unit_price="5", at=self.at, actor="alice")
        l1 = sales.add_line(conn, qid, description="Workstation, 32 GB", quantity="2", unit_price="60,000", at=self.at, actor="alice")
        sales.add_line(conn, qid, description="Monitor, 27in medical", quantity="2", unit_price="25000", at=self.at, actor="alice")
        l3 = sales.add_line(conn, qid, description="Install and migrate", quantity="1.5", unit_price="4000", at=self.at, actor="alice")
        q = sales.quote(conn, qid)
        self.assertEqual((q["subtotal"], q["total"]), (176000.0, 197120.0))                # 176,000 × 1.12
        self.assertTrue(sales.remove_line(conn, qid, l3, at=self.at, actor="alice"))
        self.assertFalse(sales.remove_line(conn, qid, 9999, at=self.at, actor="alice"))
        q = sales.quote(conn, qid)
        self.assertEqual((q["subtotal"], q["total"]), (170000.0, 190400.0))
        self.assertEqual([r["line_id"] for r in sales.lines(conn, qid)][0], l1)
        with self.assertRaises(sales.Refused):
            sales.set_quote_status(conn, qid, "ACCEPTED", at=self.at, actor="alice")       # a draft is sent first
        self.assertEqual(sales.set_quote_status(conn, qid, "SENT", at=self.at, actor="alice"), "SENT")
        self.assertEqual(sales.get(conn, oid)["stage"], "PROPOSAL")                        # sending moves a lead on
        with self.assertRaises(sales.Refused):
            sales.add_line(conn, qid, description="Late", quantity="1", unit_price="1", at=self.at, actor="alice")   # sent: frozen
        self.assertEqual(sales.set_quote_status(conn, qid, "DRAFT", at=self.at, actor="alice"), "DRAFT")           # unless withdrawn
        self.assertEqual(sales.set_quote_status(conn, qid, "SENT", at=self.at, actor="alice"), "SENT")
        self.assertEqual(sales.set_quote_status(conn, qid, "ACCEPTED", at=self.at, actor="alice"), "ACCEPTED")
        self.assertEqual(sales.get(conn, oid)["amount"], 190400.0)                          # the opportunity is worth the quote
        with self.assertRaises(sales.Refused):
            sales.set_quote_status(conn, qid, "DECLINED", at=self.at, actor="alice")       # decided is decided
        aid = sales.move(conn, oid, "WON", at=self.at, actor="alice")
        self.assertEqual(aid, "AGR-0001")
        a = agreements.get(conn, aid)
        self.assertEqual((a["name"], a["party"], a["amount"], a["currency"], a["status"]),
                         ("Radiology workstation", "Premiere Medical Center Nueva Ecija", 190400.0, "PHP", "DRAFT"))
        self.assertIn("quote Q-0001", a["notes"])
        o = sales.get(conn, oid)
        self.assertEqual((o["stage"], o["probability"], o["agreement_id"], o["agreement_name"]),
                         ("WON", 100, aid, "Radiology workstation"))
        # a win with no accepted quote takes the amount
        oid2 = sales.create(conn, name="Spare parts retainer", amount="36000", currency="PHP", at=self.at, actor="alice")
        aid2 = sales.move(conn, oid2, "WON", at=self.at, actor="alice")
        self.assertEqual(agreements.get(conn, aid2)["amount"], 36000.0)

    def test_the_pipeline_counts_and_weights_by_stage_and_the_list_filters(self):
        from psaspine import sales
        conn = self._conn()
        a = sales.create(conn, name="Alpha", amount="1000", at=self.at, actor="alice")
        b = sales.create(conn, name="Beta", amount="2000", stage="QUALIFIED", owner="bob", at=self.at, actor="alice")
        c = sales.create(conn, name="Gamma", amount="3000", stage="PROPOSAL", at=self.at, actor="alice")
        sales.move(conn, c, "LOST", reason="Went elsewhere", at=self.at, actor="alice")
        by = {p["stage"]: p for p in sales.pipeline(conn)}
        self.assertEqual([p["stage"] for p in sales.pipeline(conn)], ["LEAD", "QUALIFIED", "PROPOSAL", "WON", "LOST"])
        self.assertEqual((by["LEAD"]["count"], by["LEAD"]["amount"], by["LEAD"]["weighted"]), (1, 1000.0, 100.0))
        self.assertEqual((by["QUALIFIED"]["count"], by["QUALIFIED"]["weighted"]), (1, 800.0))
        self.assertEqual((by["PROPOSAL"]["count"], by["WON"]["count"], by["LOST"]["count"]), (0, 0, 1))
        self.assertEqual([r["opportunity_id"] for r in sales.all_(conn, stage="OPEN")], [a, b])
        self.assertEqual([r["opportunity_id"] for r in sales.all_(conn)], [a, b, c])       # lost sorts last
        self.assertEqual([r["opportunity_id"] for r in sales.all_(conn, stage="LOST")], [c])
        self.assertEqual([r["opportunity_id"] for r in sales.all_(conn, q="bet")], [b])
        self.assertEqual([r["opportunity_id"] for r in sales.all_(conn, owner="BOB")], [b])

    # ------------------------------------------------------------ web

    def test_sales_pages_are_gated_by_finance_and_write_is_needed_to_change(self):
        from psaspine import sales, security
        conn = self._conn()
        oid = sales.create(conn, name="Ward 3 endpoint refresh", entity_id="PMC", amount="250000", at=self.at, actor="alice")
        conn.commit()
        # Technician: FINANCE READ. Sees, cannot change.
        status, _, page = self._call("GET", "/sales", cookie=self.alice)
        self.assertTrue(status.startswith("200"), status)
        self.assertIn("<h1>Sales</h1>", page)
        self.assertIn("Ward 3 endpoint refresh", page)
        self.assertNotIn("New opportunity", page)
        self.assertIn('href="/sales"', page)                                                  # the nav shows it
        status, _, page = self._call("GET", f"/sales/{oid}", cookie=self.alice)
        self.assertTrue(status.startswith("200"), status)
        self.assertNotIn("/stage", page)
        status, _, _ = self._call("POST", "/sales/new", cookie=self.alice, form={"name": "Nope"})
        self.assertTrue(status.startswith("403"), status)
        status, _, _ = self._call("POST", f"/sales/{oid}/stage", cookie=self.alice, form={"stage": "WON"})
        self.assertTrue(status.startswith("403"), status)
        # A requester has no finance at all; a stranger to the record gets 404.
        status, _, _ = self._call("GET", "/sales", cookie=self._cookie_for("nurse"))
        self.assertTrue(status.startswith("403"), status)
        status, _, _ = self._call("GET", "/sales/OPP-9999", cookie=self.alice)
        self.assertTrue(status.startswith("404"), status)
        status, _, _ = self._call("GET", "/quote/Q-9999", cookie=self.alice)
        self.assertTrue(status.startswith("404"), status)
        security.assign(conn, "alice", "READ_ONLY", at=self.at, actor="root")
        conn.commit()
        status, _, _ = self._call("GET", "/sales", cookie=self.alice)
        self.assertTrue(status.startswith("403"), status)
        _, _, board = self._call("GET", "/", cookie=self.alice)
        self.assertNotIn('href="/sales"', board)

    def test_a_service_manager_runs_an_opportunity_to_a_won_agreement_from_the_desk(self):
        from psaspine import security
        conn = self._conn()
        security.ensure_roles(conn)
        security.assign(conn, "alice", "SERVICE_MANAGER", at=self.at, actor="root")
        conn.commit()
        _, h, _ = self._call("POST", "/sales/new", cookie=self.alice, form={"name": "", "amount": "1"})
        self.assertIn("err=An+opportunity+needs+a+name", dict(h)["Location"])
        _, h, _ = self._call("POST", "/sales/new", cookie=self.alice,
                             form={"name": "Ward 3 endpoint refresh", "entity_id": "PMC", "amount": "250000",
                                   "currency": "PHP", "expected_on": "2026-12-15", "owner": "alice", "notes": "24 endpoints"})
        self.assertEqual(dict(h)["Location"], "/sales/OPP-0001?msg=OPP-0001+created.")
        _, _, page = self._call("GET", "/sales/OPP-0001", cookie=self.alice, query="msg=OPP-0001+created.")
        self.assertIn("OPP-0001 created.", page)
        self.assertIn("Premiere Medical Center Nueva Ecija", page)
        self.assertIn("action='/sales/OPP-0001/update'", page)
        self.assertIn("<input name=amount inputmode=decimal value='250000'>", page)              # never 2.5e+05
        self.assertIn("value=WON", page)
        _, h, _ = self._call("POST", "/sales/OPP-0001/update", cookie=self.alice,
                             form={"name": "Ward 3 endpoint refresh", "entity_id": "PMC", "probability": "30", "amount": "250000",
                                   "currency": "PHP", "expected_on": "2026-12-15", "owner": "alice", "notes": "24 endpoints"})
        self.assertIn("msg=Saved.", dict(h)["Location"])
        _, h, _ = self._call("POST", "/sales/OPP-0001/stage", cookie=self.alice, form={"stage": "LOST", "reason": ""})
        self.assertIn("err=A+lost+opportunity+says+why", dict(h)["Location"])
        # a quote, its lines, sent and accepted
        _, h, _ = self._call("POST", "/sales/OPP-0001/quote", cookie=self.alice,
                             form={"name": "Option A", "valid_until": "2026-10-31", "tax_percent": "12"})
        self.assertTrue(dict(h)["Location"].startswith("/quote/Q-0001?msg="), dict(h)["Location"])
        _, h, _ = self._call("POST", "/quote/Q-0001/status", cookie=self.alice, form={"status": "SENT"})
        self.assertIn("err=A+quote+with+no+lines+is+not+sent", dict(h)["Location"])
        self._call("POST", "/quote/Q-0001/line", cookie=self.alice,
                   form={"description": "Endpoint, 14in, 16 GB", "quantity": "24", "unit_price": "45000"})
        _, h, _ = self._call("POST", "/quote/Q-0001/line", cookie=self.alice,
                             form={"description": "Deploy", "quantity": "x", "unit_price": "1"})
        self.assertIn("err=Quantity+is+a+number", dict(h)["Location"])
        _, _, page = self._call("GET", "/quote/Q-0001", cookie=self.alice)
        self.assertIn("Endpoint, 14in, 16 GB", page)
        self.assertIn("PHP 1,080,000.00", page)                                                 # subtotal
        self.assertIn("PHP 1,209,600.00", page)                                                 # total with 12% tax
        self.assertIn("action='/quote/Q-0001/line/remove'", page)
        _, h, _ = self._call("POST", "/quote/Q-0001/status", cookie=self.alice, form={"status": "SENT"})
        self.assertIn("msg=Q-0001+is+sent.", dict(h)["Location"])
        _, _, page = self._call("GET", "/quote/Q-0001", cookie=self.alice)
        self.assertNotIn("action='/quote/Q-0001/line/remove'", page)                           # sent: frozen
        self.assertIn("value=ACCEPTED", page)
        self._call("POST", "/quote/Q-0001/status", cookie=self.alice, form={"status": "ACCEPTED"})
        _, _, page = self._call("GET", "/sales", cookie=self.alice)
        self.assertIn("Proposal sent", page)
        self.assertIn("PHP 1,209,600.00", page)                                                 # the pipeline is worth the quote
        _, h, _ = self._call("POST", "/sales/OPP-0001/stage", cookie=self.alice, form={"stage": "WON"})
        loc = dict(h)["Location"]
        self.assertTrue(loc.startswith("/agreement/AGR-0001?msg=OPP-0001+won."), loc)
        _, _, page = self._call("GET", "/agreement/AGR-0001", cookie=self.alice)
        self.assertIn("Ward 3 endpoint refresh", page)
        self.assertIn("PHP 1,209,600.00", page)
        _, _, page = self._call("GET", "/sales/OPP-0001", cookie=self.alice)
        self.assertIn("href='/agreement/AGR-0001'", page)
        self.assertNotIn("action='/sales/OPP-0001/update'", page)                             # won: read-only
        _, _, page = self._call("GET", "/sales", cookie=self.alice, query="stage=WON")
        self.assertIn("OPP-0001", page)
        _, _, page = self._call("GET", "/sales", cookie=self.alice, query="stage=OPEN")
        self.assertIn("No opportunity here.", page)




class MembersTest(unittest.TestCase):
    """053: a member is a record. The list, the page, the memberships and the
    role in one place; leaving ends what points at the person and says so."""

    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for

    def setUp(self) -> None:
        WebWSGITest.setUp(self)
        self.addCleanup(self.tmp.cleanup)
        self.at = datetime(2026, 9, 29, 10)
        self.alice = self._cookie_for("alice")
        self.root = self._cookie_for("root", is_sysadmin=True)
        conn = self._conn()
        conn.executescript(
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','bob','WORK');"
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','alice','ADMIN');")
        conn.commit()

    def _conn(self):
        conn = db.connect(self.db_path)
        self.addCleanup(conn.close)
        return conn

    def test_everyone_the_desk_knows_is_a_member_and_a_record_names_them(self):
        from psaspine import members, security
        conn = self._conn()
        self.assertEqual(members.identifiers(conn), ["alice", "bob", "carol"])
        self.assertEqual(members.name_of(conn, "bob"), "bob")                          # no record, no contact: the identifier
        with self.assertRaises(members.Refused):
            members.add(conn, "bob", at=self.at, actor="root")                          # already known
        with self.assertRaises(members.Refused):
            members.add(conn, "j/cruz", at=self.at, actor="root")
        with self.assertRaises(members.Refused):
            members.add(conn, "jcruz", email="not an address", at=self.at, actor="root")
        self.assertEqual(members.add(conn, "jcruz", display_name="Juan Cruz", title="Technician", email="jcruz@pmcne.ph",
                                     at=self.at, actor="root"), "jcruz")
        self.assertEqual(members.name_of(conn, "jcruz"), "Juan Cruz")
        self.assertEqual(members.save(conn, "bob", at=self.at, actor="root", display_name="Bob Santos", mobile="0917 000 0000"),
                         ["display_name - -> Bob Santos", "mobile - -> 0917 000 0000"])
        self.assertEqual(members.save(conn, "bob", at=self.at, actor="root", display_name="Bob Santos"), [])
        with self.assertRaises(members.Refused):
            members.save(conn, "bob", at=self.at, actor="root", reports_to="bob")          # not to himself
        with self.assertRaises(members.Refused):
            members.save(conn, "bob", at=self.at, actor="root", reports_to="nobody")
        with self.assertRaises(members.Refused):
            members.save(conn, "bob", at=self.at, actor="root", default_board_id="NOPE")
        members.save(conn, "bob", at=self.at, actor="root", reports_to="alice", time_approver="alice", default_board_id="IT_HELP")
        m = members.get(conn, "bob")
        self.assertEqual((m["display_name"], m["reports_to"], m["time_approver"], m["default_board_name"], m["active"]),
                         ("Bob Santos", "alice", "alice", "IT Help", True))
        self.assertEqual([b["board_id"] for b in m["boards"]], ["IT_HELP"])
        self.assertEqual(members.set_membership(conn, "bob", "IT_HELP", "ADMIN", at=self.at, actor="root"), "bob is ADMIN on IT Help")
        self.assertEqual(members.set_membership(conn, "bob", "IT_HELP", None, at=self.at, actor="root"), "bob is off IT Help")
        self.assertEqual(members.get(conn, "bob")["boards"], [])
        rows = {r["member"]: r for r in members.all_(conn)}
        self.assertEqual(sorted(rows), ["alice", "bob", "carol", "jcruz"])
        self.assertEqual(rows["jcruz"]["title"], "Technician")
        self.assertEqual([r["member"] for r in members.all_(conn, q="santos")], ["bob"])
        self.assertIsNone(members.get(conn, "nobody"))

    def test_leaving_ends_what_points_at_the_person_and_keeps_the_history(self):
        from psaspine import members
        conn = self._conn()
        members.save(conn, "bob", at=self.at, actor="root", email="bob@pmcne.ph")
        members.save(conn, "alice", at=self.at, actor="root", reports_to="bob", time_approver="bob")
        conn.execute("INSERT INTO oncall_slot (slot_id, board_id, member, role, starts_at, ends_at) VALUES"
                     " ('s-past','IT_HELP','bob','ON_CALL','2026-09-01 00:00','2026-09-02 00:00'),"
                     " ('s-next','IT_HELP','bob','ON_CALL','2026-10-01 00:00','2026-10-02 00:00')")
        conn.execute("INSERT INTO department (name, source, created_at, approver) VALUES ('Ward 3', 'MANUAL', '2026-09-29 10:00', 'bob@pmcne.ph')")
        from psaspine.web import auth as webauth
        conn.execute("INSERT INTO local_account (username, scrypt_hash, is_sysadmin, disabled, created_at, created_by)"
                     " VALUES (?,?,0,0,?,'root')", ("bob", webauth.hash_password("x" * 12), "2026-09-29 10:00"))
        with self.assertRaises(members.Refused):
            members.deactivate(conn, "bob", at=self.at, actor="bob")                     # not your own
        done = members.deactivate(conn, "bob", at=self.at, actor="root")
        self.assertEqual(done, ["taken off 1 board(s): IT Help",
                                "1 future on-call slot(s) removed; the rota needs someone else there",
                                "no longer the approver for: Ward 3",
                                "no longer reported to by: alice",
                                "no longer the time approver for: alice",
                                "break-glass account disabled"])
        m = members.get(conn, "bob")
        self.assertEqual((m["active"], m["inactive_from"], m["boards"]), (False, "2026-09-29", []))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM oncall_slot WHERE member = 'bob'").fetchone()[0], 1)   # the past stays
        self.assertIsNone(conn.execute("SELECT approver FROM department WHERE name = 'Ward 3'").fetchone()[0])
        self.assertIsNone(members.get(conn, "alice")["reports_to"])
        self.assertEqual(conn.execute("SELECT disabled FROM local_account WHERE username = 'bob'").fetchone()[0], 1)
        with self.assertRaises(members.Refused):
            members.deactivate(conn, "bob", at=self.at, actor="root")                    # once
        self.assertEqual([r["member"] for r in members.all_(conn)], ["alice", "carol"])  # gone from the list
        self.assertIn("bob", [r["member"] for r in members.all_(conn, include_inactive=True)])
        members.reactivate(conn, "bob", at=self.at, actor="root")
        self.assertTrue(members.get(conn, "bob")["active"])
        self.assertEqual(members.get(conn, "bob")["boards"], [])                        # memberships are given again on purpose

    def test_setup_members_pages_are_a_system_administrators_and_hold_it_all(self):
        conn = self._conn()
        status, _, _ = self._call("GET", "/admin/members", cookie=self.alice)
        self.assertTrue(status.startswith("403"), status)
        _, _, page = self._call("GET", "/admin/members", cookie=self.root)
        self.assertIn("<h1>Members</h1>", page)
        self.assertIn("href='/admin/member/bob'", page)
        _, _, setup_page = self._call("GET", "/admin", cookie=self.root)
        self.assertIn("href='/admin/members'", setup_page)
        _, h, _ = self._call("POST", "/admin/members/add", cookie=self.root,
                             form={"member": "jcruz", "display_name": "Juan Cruz", "email": "jcruz@pmcne.ph", "default_board_id": "IT_HELP"})
        self.assertEqual(dict(h)["Location"], "/admin/member/jcruz?msg=jcruz+added.+Now+put+them+on+their+boards.")
        _, h, _ = self._call("POST", "/admin/member/jcruz/board", cookie=self.root, form={"board_id": "IT_HELP", "access": "WORK"})
        self.assertIn("msg=jcruz+is+WORK+on+IT+Help", dict(h)["Location"])
        _, h, _ = self._call("POST", "/admin/member/jcruz/role", cookie=self.root, form={"role_id": "SERVICE_MANAGER"})
        self.assertIn("msg=", dict(h)["Location"])
        _, h, _ = self._call("POST", "/admin/member/jcruz/capacity", cookie=self.root, form={"hours": "36"})
        self.assertIn("msg=36+hours+a+week.", dict(h)["Location"])
        _, h, _ = self._call("POST", "/admin/member/jcruz/save", cookie=self.root,
                             form={"display_name": "Juan Cruz", "title": "Biomedical engineer", "email": "jcruz@pmcne.ph",
                                   "reports_to": "alice", "time_approver": "alice", "default_board_id": "IT_HELP"})
        self.assertIn("msg=Saved.", dict(h)["Location"])
        _, _, page = self._call("GET", "/admin/member/jcruz", cookie=self.root)
        self.assertIn("<h1>Juan Cruz", page)
        self.assertIn("Biomedical engineer", page)
        self.assertIn("value='36'", page)
        self.assertIn("Service manager", page)
        self.assertIn("This person has left", page)
        status, _, _ = self._call("GET", "/admin/member/nobody", cookie=self.root)
        self.assertTrue(status.startswith("404"), status)
        _, h, _ = self._call("POST", "/admin/member/jcruz/deactivate", cookie=self.root)
        self.assertIn("msg=Juan+Cruz+has+left.+taken+off+1+board", dict(h)["Location"])
        _, _, page = self._call("GET", "/admin/member/jcruz", cookie=self.root)
        self.assertIn("Back on the desk", page)
        self.assertNotIn("action='/admin/member/jcruz/board'", page.split("Boards")[1].split("</table>")[1] if "Boards" in page else "")
        # the member's name reaches the shell: bob signs in and is Bob Santos in the header
        from psaspine import members
        members.save(conn, "bob", at=self.at, actor="root", display_name="Bob Santos")
        conn.commit()
        _, _, board = self._call("GET", "/", cookie=self._cookie_for("bob"))
        self.assertIn('<a href="/my/profile" title="My profile">Bob Santos</a>', board)

    def test_my_profile_is_the_persons_own_and_mints_a_calendar_feed(self):
        from psaspine import members
        conn = self._conn()
        members.save(conn, "alice", at=self.at, actor="root", display_name="Alice Reyes", title="Service manager")
        conn.commit()
        _, _, page = self._call("GET", "/my/profile", cookie=self.alice)
        self.assertIn("<h1>Alice Reyes</h1>", page)
        self.assertIn("Service manager", page)
        self.assertIn("IT Help", page)
        self.assertIn("Make a feed address", page)
        _, h, _ = self._call("POST", "/my/profile/save", cookie=self.alice, form={"phone": "5501", "mobile": "0917 111 2222"})
        self.assertIn("msg=Saved.", dict(h)["Location"])
        self.assertEqual(members.get(conn, "alice")["mobile"], "0917 111 2222")
        _, h, _ = self._call("POST", "/my/profile/feed", cookie=self.alice)
        token = dict(h)["Location"].split("token=")[1]
        self.assertTrue(token.startswith("cal_"))
        _, _, page = self._call("GET", "/my/profile", cookie=self.alice, query=f"token={token}")
        self.assertIn(f"/calendar/feed/{token}.ics", page)
        self.assertIn("New feed address", page)
        self.assertEqual(members.member_for_feed(conn, token), "alice")
        self.assertIsNone(members.member_for_feed(conn, "cal_wrong"))
        _, h, _ = self._call("POST", "/my/profile/feed", cookie=self.alice)                 # rotating ends the old one
        self.assertIsNone(members.member_for_feed(conn, token))
        status, _, _ = self._call("GET", "/my/profile", cookie=self._cookie_for("nurse"))   # a requester has no profile
        self.assertTrue(status.startswith("404"), status)


class CalendarTest(unittest.TestCase):
    """053: a person's calendar, three views, and the .ics feed for a phone."""

    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for

    def setUp(self) -> None:
        WebWSGITest.setUp(self)
        self.addCleanup(self.tmp.cleanup)
        self.at = datetime(2026, 9, 29, 10)
        self.alice = self._cookie_for("alice")
        self.bob = self._cookie_for("bob")
        conn = db.connect(self.db_path)
        self.addCleanup(conn.close)
        self.conn = conn
        conn.executescript(
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','alice','ADMIN');"
            "INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','bob','WORK');")
        from psaspine import schedule, tickets
        schedule.ensure_vocabulary(conn)
        self.wid = tickets.open_ticket(conn, board_id="IT_HELP", summary="Printer jams on ward 3", impact="I3", urgency="U3",
                                       requested_by="ward3@pmcne.ph", at=self.at)
        schedule.add(conn, self.wid, member="bob", starts_at=datetime(2026, 9, 30, 10), ends_at=datetime(2026, 9, 30, 11),
                     note="Ward 3", actor="alice", at=self.at)
        schedule.add_block(conn, member="bob", kind="TIME_OFF", name="Dentist", starts_at=datetime(2026, 10, 2, 13),
                           ends_at=datetime(2026, 10, 2, 15), actor="bob", at=self.at)
        conn.execute("INSERT INTO oncall_slot (slot_id, board_id, member, role, starts_at, ends_at) VALUES"
                     " ('s1','IT_HELP','bob','ON_CALL','2026-10-03 18:00','2026-10-04 08:00')")
        conn.commit()

    def test_the_three_views_show_visits_blocks_and_on_call_for_one_person(self):
        _, _, page = self._call("GET", "/calendar", cookie=self.bob, query="date=2026-09-29")
        self.assertIn("My calendar", page)
        self.assertIn("Week of 28 Sep 2026", page)
        self.assertIn(self.wid, page)
        self.assertIn("Dentist", page)
        self.assertIn("On call", page)
        self.assertNotIn("Printer jams on ward 3 x", page)
        _, _, page = self._call("GET", "/calendar", cookie=self.bob, query="view=day&date=2026-09-30")
        self.assertIn("Wednesday 30 September 2026", page)
        self.assertIn(self.wid, page)
        self.assertNotIn("Dentist", page)
        _, _, page = self._call("GET", "/calendar", cookie=self.bob, query="view=month&date=2026-10-15")
        self.assertIn("October 2026", page)
        self.assertIn("Dentist", page)
        self.assertIn("On call", page)
        _, _, page = self._call("GET", "/calendar", cookie=self.bob, query="view=day&date=2026-11-01")
        self.assertIn("Nothing on this day.", page)
        _, _, page = self._call("GET", "/", cookie=self.bob)
        self.assertIn('href="/calendar"', page)

    def test_a_dispatcher_opens_a_colleagues_calendar_and_a_stranger_cannot(self):
        _, _, page = self._call("GET", "/calendar", cookie=self.alice, query="member=bob&date=2026-09-29")
        self.assertIn(self.wid, page)
        self.assertIn("<h1>bob", page)
        status, _, _ = self._call("GET", "/calendar", cookie=self.alice, query="member=nobody")
        self.assertTrue(status.startswith("404"), status)
        status, _, _ = self._call("GET", "/calendar", cookie=self._cookie_for("nurse"))
        self.assertTrue(status.startswith("403"), status)                              # no Schedule module for a requester

    def test_the_feed_needs_only_its_token_and_never_says_what_a_ticket_says(self):
        from psaspine import members
        token = members.new_feed_token(self.conn, "bob", at=self.at)
        self.conn.commit()
        status, h, body = self._call("GET", f"/calendar/feed/{token}.ics")
        self.assertTrue(status.startswith("200"), status)
        self.assertEqual(dict(h)["Content-Type"], "text/calendar; charset=utf-8")
        self.assertIn("BEGIN:VCALENDAR", body)
        self.assertIn(f"SUMMARY:{self.wid} · IT_HELP", body)
        self.assertIn("DTSTART:20260930T100000", body)
        self.assertIn("SUMMARY:Time off: Dentist", body)
        self.assertIn("SUMMARY:On call · IT Help", body)
        self.assertNotIn("Printer jams", body)                                          # §6.1: the summary stays behind the sign-in
        self.assertEqual(body.count("BEGIN:VEVENT"), 3)
        status, _, _ = self._call("GET", "/calendar/feed/cal_nope.ics")
        self.assertTrue(status.startswith("404"), status)
        status, _, _ = self._call("GET", f"/calendar/feed/{token}")                       # with or without the suffix
        self.assertTrue(status.startswith("200"), status)
        members.deactivate(self.conn, "bob", at=self.at, actor="root")
        self.conn.commit()
        status, _, _ = self._call("GET", f"/calendar/feed/{token}.ics")                  # leaving ends the feed
        self.assertTrue(status.startswith("404"), status)


class IntakeRoutingTest(unittest.TestCase):
    """053: a board claims an address; mail to it lands there, whichever
    mailbox delivered it. Better than a connector per board: one mailbox
    with aliases, or one per board, both work."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = _fresh(self.tmp)
        self.drop = Path(self.tmp.name) / "drop"
        self.drop.mkdir()
        self.at = datetime(2026, 9, 29, 9, 0)
        self.n = 0
        from psaspine import setup
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)
        self.conn.execute("INSERT INTO board (board_id, display_name, phase, fulfiller_group, is_live, is_unrouted, intake_address)"
                          " VALUES ('BIOMED', 'Biomedical', '2', 'Dada', 0, 0, 'Biomed@pmcne.ph')")
        self.conn.execute("UPDATE board SET intake_address = 'helpdesk@pmcne.ph' WHERE board_id = 'IT_HELP'")
        self.assertEqual(db.move_intake_addresses(self.conn), 2)   # 058: the 053 column's values move, once
        self.assertEqual(db.move_intake_addresses(self.conn), 0)
        setup.apply_starter(self.conn, "BIOMED", actor="t", at=self.at)
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _msg(self, *, subject, to="helpdesk@pmcne.ph", cc=None, delivered_to=None, sender="ward3@pmcne.ph"):
        self.n += 1
        headers = [f"From: {sender}", f"To: {to}", f"Subject: {subject}", "Date: Tue, 29 Sep 2026 09:00:00 +0800",
                   f"Message-ID: <r{self.n}@pmcne.ph>"]
        if cc:
            headers.append(f"Cc: {cc}")
        if delivered_to:
            headers.append(f"Delivered-To: {delivered_to}")
        (self.drop / f"{self.n:03d}.eml").write_bytes(("\r\n".join(headers) + "\r\n\r\nPlease help.\r\n").encode())

    def _board_of(self, n):
        return self.conn.execute("SELECT t.board_id, i.to_address FROM intake_message i JOIN ticket t ON t.work_item_id = i.work_item_id"
                                 " WHERE i.message_id = ?", (f"<r{n}@pmcne.ph>",)).fetchone()

    def test_mail_lands_on_the_board_that_claims_the_address(self):
        from psaspine import intake
        self._msg(subject="Infusion pump alarm", to="Nurse Station <ward3@pmcne.ph>, biomed@pmcne.ph")          # To, mixed case claimed
        self._msg(subject="Printer jams", to="helpdesk@pmcne.ph")
        self._msg(subject="Aliased on the way in", to="BIOMED@PMCNE.PH", delivered_to="helpdesk@pmcne.ph")      # Exchange alias
        self._msg(subject="Nobody's address", to="someone@pmcne.ph")
        self._msg(subject="Copied to biomed", to="someone@pmcne.ph", cc="biomed@pmcne.ph")
        self._msg(subject="The desk talking", sender="biomed@pmcne.ph", to="ward3@pmcne.ph")                      # a board's own address
        counts = intake.import_drop(self.conn, self.drop, run_id="r1", at=self.at, board_id="IT_HELP")
        self.assertEqual((counts["new"], counts["routed_by_address"], counts["loop_guarded"]), (5, 4, 1))
        self.assertEqual(tuple(self._board_of(1)), ("BIOMED", "biomed@pmcne.ph"))
        self.assertEqual(tuple(self._board_of(2)), ("IT_HELP", "helpdesk@pmcne.ph"))
        self.assertEqual(tuple(self._board_of(3)), ("BIOMED", "biomed@pmcne.ph"))
        self.assertEqual(tuple(self._board_of(4)), ("IT_HELP", None))                    # the run's board, no address decided it
        self.assertEqual(tuple(self._board_of(5)), ("BIOMED", "biomed@pmcne.ph"))
        self.assertEqual(self.conn.execute("SELECT disposition FROM intake_message WHERE message_id = '<r6@pmcne.ph>'").fetchone()[0],
                         "UNCLASSIFIED")
        # with no run board, an unclaimed address goes to the unrouted queue as before
        self._msg(subject="Unrouted", to="someone@pmcne.ph")
        intake.import_drop(self.conn, self.drop, run_id="r2", at=self.at)
        self.assertEqual(self._board_of(7)["board_id"], self.conn.execute("SELECT board_id FROM board WHERE is_unrouted = 1").fetchone()[0])
        # a re-run makes no second ticket
        self.assertEqual(intake.import_drop(self.conn, self.drop, run_id="r3", at=self.at)["new"], 0)




class AuditPageTest(unittest.TestCase):
    """054: Setup > Audit reads the trail, with the source of each change,
    filters, a CSV, and a mask on restricted boards; API tokens on a page."""

    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for

    def setUp(self) -> None:
        WebWSGITest.setUp(self)
        self.addCleanup(self.tmp.cleanup)
        self.at = datetime(2026, 9, 30, 9)
        self.alice = self._cookie_for("alice")
        self.root = self._cookie_for("root", is_sysadmin=True)

    def _conn(self):
        conn = db.connect(self.db_path)
        self.addCleanup(conn.close)
        return conn

    def test_every_change_says_where_it_came_from(self):
        conn = self._conn()
        db.set_source(None)
        db.audit(conn, at="2026-09-30 08:00", actor="t", action="TEST", subject_kind="x", detail="from nowhere")
        db.set_source("CLI")
        db.audit(conn, at="2026-09-30 08:01", actor="t", action="TEST", subject_kind="x", detail="from a command")
        with self.assertRaises(ValueError):
            db.set_source("ELSEWHERE")
        db.set_source(None)
        conn.commit()
        rows = {r["detail"]: r["source"] for r in conn.execute("SELECT detail, source FROM audit_event WHERE action = 'TEST'")}
        self.assertEqual(rows, {"from nowhere": None, "from a command": "CLI"})
        # a desk request stamps DESK; a portal request stamps PORTAL; the API stamps API
        self._call("POST", "/admin/members/add", cookie=self.root, form={"member": "jcruz", "display_name": "Juan Cruz"})
        self.assertEqual(conn.execute("SELECT source FROM audit_event WHERE action = 'MEMBER' AND subject_id = 'jcruz'").fetchone()[0], "DESK")
        self.assertIsNone(db.current_source())                                            # nothing leaks into the test thread

    def test_the_audit_page_filters_exports_and_masks_a_restricted_board(self):
        from psaspine import tickets
        conn = self._conn()
        conn.execute("INSERT OR REPLACE INTO board_member (board_id,member,access) VALUES ('IT_HELP','root','ADMIN')")
        wid = tickets.open_ticket(conn, board_id="PHI", summary="A patient's chart will not open", impact="I3", urgency="U3",
                                  requested_by="ward3@pmcne.ph", at=self.at)
        db.audit(conn, at="2026-09-30 08:02", actor="alice", action="STATUS", subject_kind="ticket", subject_id=wid,
                 detail="the chart words")
        db.audit(conn, at="2026-09-30 08:03", actor="bob", action="STATUS", subject_kind="ticket", subject_id="PMC-999999",
                 detail="an ordinary line")
        conn.commit()
        status, _, _ = self._call("GET", "/admin/audit", cookie=self.alice)
        self.assertTrue(status.startswith("403"), status)
        _, _, page = self._call("GET", "/admin/audit", cookie=self.root)
        self.assertIn("<h1>Audit</h1>", page)
        self.assertIn("an ordinary line", page)
        self.assertNotIn("the chart words", page)                                           # root is not on PHI
        self.assertIn("(a restricted board you are not on)", page)
        _, _, page = self._call("GET", "/admin/audit", cookie=self.root, query="actor=bob")
        self.assertIn("an ordinary line", page)
        self.assertNotIn("restricted board you are not on", page)
        _, _, page = self._call("GET", "/admin/audit", cookie=self.root, query="action=STATUS&since=2026-10-01")
        self.assertIn("Nothing matches.", page)
        _, h, body = self._call("GET", "/admin/audit.csv", cookie=self.root, query="action=STATUS")
        self.assertEqual(dict(h)["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("occurred_at,actor,action", body)
        self.assertIn("an ordinary line", body)
        self.assertNotIn("the chart words", body)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'AUDIT_EXPORT'").fetchone()[0], 1)
        _, _, setup_page = self._call("GET", "/admin", cookie=self.root)
        self.assertIn("href='/admin/audit'", setup_page)

    def test_api_tokens_are_minted_shown_once_and_disabled_on_a_page(self):
        conn = self._conn()
        status, _, _ = self._call("GET", "/admin/api-tokens", cookie=self.alice)
        self.assertTrue(status.startswith("403"), status)
        _, _, page = self._call("GET", "/admin/api-tokens", cookie=self.root)
        self.assertIn("No token yet.", page)
        _, h, _ = self._call("POST", "/admin/api-tokens/new", cookie=self.root, form={"label": "", "board_id": "IT_HELP", "scope": "READ"})
        self.assertIn("err=", dict(h)["Location"])
        _, h, _ = self._call("POST", "/admin/api-tokens/new", cookie=self.root,
                             form={"label": "Orthanc monitoring", "board_id": "IT_HELP", "scope": "READ"})
        loc = dict(h)["Location"]
        token = _urlparse.parse_qs(loc.split("?", 1)[1])["token"][0]
        self.assertTrue(token.startswith("psa_"))
        _, _, page = self._call("GET", "/admin/api-tokens", cookie=self.root, query=loc.split("?", 1)[1])
        self.assertIn(token, page)
        self.assertIn("Orthanc monitoring", page)
        self.assertIn("<span class=pill>READ</span>", page)
        row = conn.execute("SELECT token_id, token_sha256 FROM api_token").fetchone()
        self.assertNotIn(token, row["token_sha256"])                                       # only the hash is kept
        _, _, page = self._call("GET", "/admin/api-tokens", cookie=self.root)
        self.assertNotIn(token, page)                                                      # shown once
        _, h, _ = self._call("POST", f"/admin/api-tokens/{row['token_id']}/toggle", cookie=self.root)
        self.assertIn("disabled", dict(h)["Location"])
        self.assertEqual(conn.execute("SELECT disabled FROM api_token").fetchone()[0], 1)
        status, _, _ = self._call("GET", "/api/v1/tickets", cookie=None, headers={"Authorization": f"Bearer {token}"})
        self.assertTrue(status.startswith("401"), status)                                  # a disabled token is refused
        status, _, _ = self._call("POST", "/admin/api-tokens/tok_nope/toggle", cookie=self.root)
        self.assertTrue(status.startswith("404"), status)




class MailSetupTest(unittest.TestCase):
    """055: Setup > Email connector. Exclusions made once on the desk; mail
    from them is recorded and opens nothing; the page shows addresses,
    exclusions and the week's dispositions without subjects."""

    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for

    def setUp(self) -> None:
        WebWSGITest.setUp(self)
        self.addCleanup(self.tmp.cleanup)
        self.at = datetime(2026, 9, 30, 9)
        self.root = self._cookie_for("root", is_sysadmin=True)
        self.alice = self._cookie_for("alice")
        self.drop = Path(self.tmp.name) / "drop"
        self.drop.mkdir()
        self.n = 0

    def _conn(self):
        conn = db.connect(self.db_path)
        self.addCleanup(conn.close)
        return conn

    def _msg(self, *, subject, sender):
        self.n += 1
        raw = f"From: {sender}\r\nTo: helpdesk@pmcne.ph\r\nSubject: {subject}\r\nDate: Wed, 30 Sep 2026 09:00:00 +0800\r\nMessage-ID: <x{self.n}@pmcne.ph>\r\n\r\nHello.\r\n"
        (self.drop / f"{self.n:03d}.eml").write_bytes(raw.encode())

    def test_excluded_mail_is_recorded_and_opens_nothing(self):
        from psaspine import intake
        conn = self._conn()
        with self.assertRaises(ValueError):
            intake.add_exclusion(conn, "ADDRESS", "not-an-address", at=self.at, actor="root")
        with self.assertRaises(ValueError):
            intake.add_exclusion(conn, "DOMAIN", "someone@vendor.com", at=self.at, actor="root")
        with self.assertRaises(ValueError):
            intake.add_exclusion(conn, "ELSE", "x", at=self.at, actor="root")
        intake.add_exclusion(conn, "ADDRESS", "Newsletter@Vendor.com", note="monthly", at=self.at, actor="root")
        intake.add_exclusion(conn, "DOMAIN", "spam.example", at=self.at, actor="root")
        intake.add_exclusion(conn, "SUBJECT", "Out of Office", at=self.at, actor="root")
        with self.assertRaises(ValueError):
            intake.add_exclusion(conn, "DOMAIN", "spam.example", at=self.at, actor="root")             # once
        self.assertEqual([(r["kind"], r["pattern"]) for r in intake.exclusions(conn)],
                         [("ADDRESS", "newsletter@vendor.com"), ("DOMAIN", "spam.example"), ("SUBJECT", "out of office")])
        self._msg(subject="September offers", sender="newsletter@vendor.com")
        self._msg(subject="Buy now", sender="bot@mail.spam.example")
        self._msg(subject="Automatic reply: Out of office until Monday", sender="ward3@pmcne.ph")
        self._msg(subject="Printer jams", sender="ward3@pmcne.ph")
        counts = intake.import_drop(conn, self.drop, run_id="e1", at=self.at, board_id="IT_HELP")
        self.assertEqual((counts["new"], counts["unclassified"], counts["excluded"], counts["loop_guarded"]), (1, 3, 3, 0))
        why = [r[0] for r in conn.execute("SELECT detail FROM data_quality WHERE code = 'MAIL_EXCLUDED' ORDER BY finding_id")]
        self.assertEqual(why, ["not turned into a ticket: excluded address newsletter@vendor.com",
                               "not turned into a ticket: excluded domain spam.example",
                               "not turned into a ticket: excluded subject phrase 'out of office'"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM intake_message").fetchone()[0], 4)   # nothing dropped
        eid = intake.exclusions(conn)[0]["exclusion_id"]
        self.assertTrue(intake.remove_exclusion(conn, eid, at=self.at, actor="root"))
        self.assertFalse(intake.remove_exclusion(conn, eid, at=self.at, actor="root"))

    def test_the_email_connector_page_is_a_system_administrators(self):
        from psaspine import intake
        conn = self._conn()
        conn.execute("INSERT INTO board_intake_address (address, board_id) VALUES ('helpdesk@pmcne.ph', 'IT_HELP')")
        conn.commit()
        self._msg(subject="A patient's chart will not open", sender="nurse@pmcne.ph")
        intake.import_drop(conn, self.drop, run_id="e2", at=self.at, board_id="IT_HELP")
        conn.commit()
        status, _, _ = self._call("GET", "/admin/mail", cookie=self.alice)
        self.assertTrue(status.startswith("403"), status)
        _, _, page = self._call("GET", "/admin/mail", cookie=self.root)
        self.assertIn("<h1>Email connector</h1>", page)
        self.assertIn("helpdesk@pmcne.ph", page)
        self.assertIn("unrouted queue", page)
        self.assertIn("…@pmcne.ph", page)                                                   # the domain, not the person
        self.assertNotIn("nurse@pmcne.ph", page)
        self.assertNotIn("patient's chart", page)                                           # never the subject
        self.assertIn("opened a ticket", page)
        _, h, _ = self._call("POST", "/admin/mail/exclude", cookie=self.root, form={"kind": "DOMAIN", "pattern": "vendor.com", "note": "newsletters"})
        self.assertIn("msg=Excluded", dict(h)["Location"])
        _, h, _ = self._call("POST", "/admin/mail/exclude", cookie=self.root, form={"kind": "ADDRESS", "pattern": "nope"})
        self.assertIn("err=An+address+looks+like", dict(h)["Location"])
        _, _, page = self._call("GET", "/admin/mail", cookie=self.root)
        self.assertIn("<code>vendor.com</code>", page)
        eid = intake.exclusions(conn)[0]["exclusion_id"]
        _, h, _ = self._call("POST", "/admin/mail/exclude/remove", cookie=self.root, form={"exclusion_id": str(eid)})
        self.assertIn("msg=Removed.", dict(h)["Location"])
        self.assertEqual(intake.exclusions(conn), [])
        _, _, setup_page = self._call("GET", "/admin", cookie=self.root)
        self.assertIn("href='/admin/mail'", setup_page)




class ConfigurationTypesTest(unittest.TestCase):
    """056: configuration types and statuses as setup tables, each counting
    as one of 021's codes, with the questions a type asks."""

    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for

    def setUp(self) -> None:
        WebWSGITest.setUp(self)
        self.addCleanup(self.tmp.cleanup)
        self.at = datetime(2026, 9, 30, 10)
        self.alice = self._cookie_for("alice")
        self.root = self._cookie_for("root", is_sysadmin=True)

    def _conn(self):
        conn = db.connect(self.db_path)
        self.addCleanup(conn.close)
        return conn

    def test_a_new_type_counts_as_one_of_the_seven_and_asks_its_own_questions(self):
        from psaspine import configurations as cmdb
        conn = self._conn()
        self.assertEqual([x["type_id"] for x in cmdb.types(conn)], list(cmdb.TYPE_WORDS))          # the seven, on first use
        self.assertEqual([x["status_id"] for x in cmdb.statuses(conn)], ["ACTIVE", "INACTIVE", "RETIRED"])
        with self.assertRaises(ValueError):
            cmdb.add_type(conn, "Infusion pump", "DEVICE", at=self.at, actor="root")
        tid = cmdb.add_type(conn, "Infusion pump", "OTHER", at=self.at, actor="root")
        self.assertEqual(tid, "CT_INFUSION_PUMP")
        with self.assertRaises(ValueError):
            cmdb.add_type(conn, "infusion pump", "OTHER", at=self.at, actor="root")             # once
        with self.assertRaises(ValueError):
            cmdb.save_type(conn, "PRINTER", at=self.at, actor="root", inactive=True)          # the seven stay
        sid = cmdb.add_status(conn, "In repair", "INACTIVE", at=self.at, actor="root")
        q1 = cmdb.add_question(conn, tid, label="Asset tag", field_type="TEXT", required=True, at=self.at, actor="root")
        q2 = cmdb.add_question(conn, tid, label="Last calibration", field_type="DATE", at=self.at, actor="root")
        q3 = cmdb.add_question(conn, tid, label="Under contract", field_type="CHECKBOX", at=self.at, actor="root")
        q4 = cmdb.add_question(conn, tid, label="Flow rate ceiling", field_type="NUMBER", at=self.at, actor="root")
        with self.assertRaises(ValueError):
            cmdb.add_question(conn, tid, label="asset tag", field_type="TEXT", at=self.at, actor="root")
        cid = cmdb.create(conn, name="PUMP-W3-01", entity_id="PMC", config_type=tid, at=self.at, actor="alice")
        row = conn.execute("SELECT config_type, type_id, status, status_id FROM configuration WHERE configuration_id = ?", (cid,)).fetchone()
        self.assertEqual(tuple(row), ("OTHER", tid, "ACTIVE", "ACTIVE"))                          # both columns, so 021 readers keep working
        self.assertEqual(cmdb.type_word(conn, conn.execute("SELECT * FROM configuration WHERE configuration_id = ?", (cid,)).fetchone()), "Infusion pump")
        with self.assertRaises(ValueError):
            cmdb.save_answers(conn, cid, {str(q2): "2026-09-01"}, at=self.at, actor="alice")      # the asset tag is needed
        with self.assertRaises(ValueError):
            cmdb.save_answers(conn, cid, {str(q1): "BM-0042", str(q4): "ten"}, at=self.at, actor="alice")
        with self.assertRaises(ValueError):
            cmdb.save_answers(conn, cid, {str(q1): "BM-0042", str(q2): "soon"}, at=self.at, actor="alice")
        changed = cmdb.save_answers(conn, cid, {str(q1): "BM-0042", str(q2): "2026-09-01", str(q3): "1", str(q4): "1,200"},
                                    at=self.at, actor="alice")
        self.assertEqual(changed, ["Asset tag: - -> BM-0042", "Last calibration: - -> 2026-09-01", "Under contract: - -> 1",
                                   "Flow rate ceiling: - -> 1200"])
        self.assertEqual(cmdb.save_answers(conn, cid, {str(q1): "BM-0042", str(q2): "2026-09-01", str(q3): "1", str(q4): "1200"},
                                           at=self.at, actor="alice"), [])
        self.assertEqual({a["label"]: a["value"] for a in cmdb.answers(conn, cid)},
                         {"Asset tag": "BM-0042", "Last calibration": "2026-09-01", "Under contract": "1", "Flow rate ceiling": "1200"})
        cmdb.update(conn, cid, at=self.at, actor="alice", status=sid)
        row = conn.execute("SELECT status, status_id FROM configuration WHERE configuration_id = ?", (cid,)).fetchone()
        self.assertEqual(tuple(row), ("INACTIVE", sid))
        # a type that changes what it counts as carries its configurations with it
        cmdb.save_type(conn, tid, at=self.at, actor="root", maps_to="NETWORK")
        self.assertEqual(conn.execute("SELECT config_type FROM configuration WHERE configuration_id = ?", (cid,)).fetchone()[0], "NETWORK")
        cmdb.save_question(conn, q4, at=self.at, actor="root", inactive=True)
        self.assertEqual([a["label"] for a in cmdb.answers(conn, cid)], ["Asset tag", "Last calibration", "Under contract"])

    def test_the_setup_page_and_the_configuration_page_ask_the_questions(self):
        from psaspine import configurations as cmdb
        conn = self._conn()
        status, _, _ = self._call("GET", "/admin/configuration-types", cookie=self.alice)
        self.assertTrue(status.startswith("403"), status)
        _, _, page = self._call("GET", "/admin/configuration-types", cookie=self.root)
        self.assertIn("<h1>Configuration types</h1>", page)
        self.assertIn("counts as itself", page)
        _, h, _ = self._call("POST", "/admin/configuration-types/type", cookie=self.root, form={"name": "Infusion pump", "maps_to": "OTHER"})
        self.assertIn("msg=Type+added", dict(h)["Location"])
        _, h, _ = self._call("POST", "/admin/configuration-types/type/CT_INFUSION_PUMP/question", cookie=self.root,
                             form={"label": "Asset tag", "field_type": "TEXT", "required": "1"})
        self.assertIn("msg=Question+added", dict(h)["Location"])
        _, h, _ = self._call("POST", "/admin/configuration-types/status", cookie=self.root, form={"name": "In repair", "maps_to": "INACTIVE"})
        self.assertIn("msg=Status+added", dict(h)["Location"])
        _, _, page = self._call("GET", "/admin/configuration-types", cookie=self.root)
        self.assertIn("Infusion pump", page)
        self.assertIn("value='Asset tag'", page)
        self.assertIn("value='In repair'", page)
        # a technician adds a pump by hand, and its page asks the question
        _, h, _ = self._call("POST", "/configurations/new", cookie=self.alice,
                             form={"name": "PUMP-W3-01", "entity_id": "PMC", "config_type": "CT_INFUSION_PUMP"})
        cid = dict(h)["Location"].split("/configuration/")[1].split("?")[0]
        _, _, page = self._call("GET", f"/configuration/{cid}", cookie=self.alice)
        self.assertIn("<span class=chip>Infusion pump</span>", page)
        self.assertIn("Infusion pump details", page)
        self.assertIn("Asset tag <span class=muted>(needed)</span>", page)
        qid = cmdb.questions(conn, "CT_INFUSION_PUMP")[0]["question_id"]
        _, h, _ = self._call("POST", f"/configuration/{cid}/answers", cookie=self.alice, form={f"q{qid}": ""})
        self.assertIn("err=Asset+tag+is+needed", dict(h)["Location"])
        _, h, _ = self._call("POST", f"/configuration/{cid}/answers", cookie=self.alice, form={f"q{qid}": "BM-0042"})
        self.assertIn("msg=Saved.", dict(h)["Location"])
        _, _, page = self._call("GET", f"/configuration/{cid}", cookie=self.alice)
        self.assertIn("value='BM-0042'", page)
        _, h, _ = self._call("POST", f"/configuration/{cid}/update", cookie=self.alice, form={"config_type": "CT_INFUSION_PUMP", "status": "CS_IN_REPAIR"})
        _, _, page = self._call("GET", f"/configuration/{cid}", cookie=self.alice)
        self.assertIn("<span class=chip>in repair</span>", page)
        _, _, page = self._call("GET", "/configurations", cookie=self.alice, query="type=CT_INFUSION_PUMP&status=ALL")
        self.assertIn("PUMP-W3-01", page)
        self.assertIn("<td>Infusion pump</td>", page)
        _, _, page = self._call("GET", "/configurations", cookie=self.alice, query="type=PRINTER&status=ALL")
        self.assertNotIn("PUMP-W3-01", page)


class SmallSetupTest(unittest.TestCase):
    """057: the six small setup items the parity check left: emails per board,
    the survey per board, knowledge categories, company status and type,
    auto-assign on a board, and the in/out board. A board that has said nothing
    behaves as it did yesterday."""

    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for

    def setUp(self) -> None:
        WebWSGITest.setUp(self)
        self.addCleanup(self.tmp.cleanup)
        self.at = datetime(2026, 9, 30, 9)
        self.root = self._cookie_for("root", is_sysadmin=True)
        self.alice = self._cookie_for("alice")
        self.conn = db.connect(self.db_path)
        self.addCleanup(self.conn.close)
        self.conn.execute(
            "INSERT INTO contact (contact_id, entity_id, display_name, email, sam_account, source, inactive,"
            " created_at) VALUES ('C_BOB', 'PMC', 'Bob', 'bob@pmcne.ph', 'bob', 'AD', 0, '2026')")
        self.conn.execute("INSERT OR REPLACE INTO board_member (board_id, member, access) VALUES ('IT_HELP', 'bob', 'WORK')")
        self.conn.commit()

    def _open(self, **kw):
        args = dict(board_id="IT_HELP", summary="Printer down", impact="I3", urgency="U3",
                    requested_by="ward@pmcne.ph", at=self.at, entity_id="PMC")
        args.update(kw)
        return tickets.open_ticket(self.conn, **args)

    def _mails(self, role):
        return self.conn.execute("SELECT recipient, subject, body FROM notification WHERE recipient_role = ?"
                                 " ORDER BY notification_id", (role,)).fetchall()

    # ------------------------------------------------------------ emails per board

    def test_a_board_writes_its_own_email_words_and_only_four_placeholders(self):
        from psaspine import outbox
        self.conn.execute("UPDATE board SET notify_requester = 1, notify_owner = 1 WHERE board_id = 'IT_HELP'")
        with self.assertRaises(ValueError):
            outbox.set_template(self.conn, "IT_HELP", "OPENED", subject="Got it", body="{summary} is in the queue",
                                at=self.at, actor="alice")                                  # no summary leaves the desk
        with self.assertRaises(ValueError):
            outbox.set_template(self.conn, "IT_HELP", "NEWSLETTER", subject="x", body="y", at=self.at, actor="alice")
        with self.assertRaises(ValueError):
            outbox.set_template(self.conn, "IT_HELP", "OPENED", subject="", body="y", at=self.at, actor="alice")
        self.assertFalse(outbox.template(self.conn, "IT_HELP", "OPENED")["custom"])
        outbox.set_template(self.conn, "IT_HELP", "OPENED", subject="{board} has {ticket}",
                            body="Thanks. {board} has your request {ticket} and will be in touch.", at=self.at, actor="alice")
        outbox.set_template(self.conn, "IT_HELP", "ASSIGNED", subject="Yours: {ticket}",
                            body="{actor} gave you {ticket} on {board}.", at=self.at, actor="alice")
        wid = self._open()
        mails = self._mails("REQUESTER")
        self.assertEqual(mails[0]["subject"], f"[{wid}] IT Help has {wid}")
        self.assertEqual(mails[0]["body"], f"Thanks. IT Help has your request {wid} and will be in touch.")
        board.update_fields(self.conn, wid, at=self.at, actor="alice", owner="bob")
        owner = self._mails("OWNER")
        self.assertEqual((owner[0]["subject"], owner[0]["body"]), (f"[{wid}] Yours: {wid}", f"alice gave you {wid} on IT Help."))
        # the PHI board said nothing: the desk's words, as before
        self.assertEqual(outbox.words(self.conn, "PHI", "ASSIGNED", ticket="X", board="PHI Board", actor="a", when="")[0],
                         "Assigned to you on PHI Board")
        # back to the desk's words
        self.assertTrue(outbox.reset_template(self.conn, "IT_HELP", "OPENED", at=self.at, actor="alice"))
        self.assertFalse(outbox.reset_template(self.conn, "IT_HELP", "OPENED", at=self.at, actor="alice"))
        self.assertEqual(outbox.template(self.conn, "IT_HELP", "OPENED")["subject"], "We have your request")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'MAIL_TEMPLATE'").fetchone()[0], 3)
        self.conn.commit()
        # the tab: a board administrator's; saves and resets through the form
        _, _, page = self._call("GET", "/admin/board/IT_HELP", cookie=self.alice, query="tab=emails")
        self.assertIn("What this board's emails say", page)
        self.assertIn("Yours: {ticket}", page)
        self.assertIn("the desk's words", page)
        _, h, _ = self._call("POST", "/admin/board/IT_HELP/emails", cookie=self.alice,
                             form={"kind": "CLOSED", "subject": "Closed: {ticket}", "body": "{board} closed it. {note}"})
        self.assertIn("Not+saved", dict(h)["Location"])
        _, h, _ = self._call("POST", "/admin/board/IT_HELP/emails", cookie=self.alice,
                             form={"kind": "CLOSED", "subject": "Closed: {ticket}", "body": "{board} closed it."})
        self.assertIn("own+words", dict(h)["Location"])
        conn = db.connect(self.db_path)
        self.addCleanup(conn.close)
        self.assertTrue(outbox.template(conn, "IT_HELP", "CLOSED")["custom"])
        _, h, _ = self._call("POST", "/admin/board/IT_HELP/emails", cookie=self.alice,
                             form={"kind": "CLOSED", "subject": "x", "body": "y", "reset": "1"})
        self.assertFalse(outbox.template(conn, "IT_HELP", "CLOSED")["custom"])
        status, _, _ = self._call("GET", "/admin/board/IT_HELP", cookie=self._cookie_for("carol"), query="tab=emails")
        self.assertTrue(status.startswith("404"), status)                                    # a reader: not a board admin

    # ------------------------------------------------------------ the survey per board

    def test_a_board_switches_the_survey_off_or_asks_its_own_question(self):
        from psaspine import survey
        self.conn.execute("UPDATE ticket SET requested_by = 'bob@pmcne.ph', state = 'CLOSED', closed_at = '2026-09-17 09:00'"
                          " WHERE work_item_id = 'ITO-1'")
        self.conn.commit()
        self.assertTrue(survey.pending(self.conn, "ITO-1"))                                 # unset is on, as it always was
        self.assertEqual(survey.question(self.conn, "ITO-1"), "How did we do?")
        bob = self._cookie_for("bob", email="bob@pmcne.ph")
        base = {"display_name": "IT Help", "fulfiller_group": "Dada", "owner": "a", "deputy": "b", "is_live": "1",
                "closed_loop_required": "1"}
        self._call("POST", "/admin/board/IT_HELP/settings", cookie=self.alice,
                   form=base | {"survey_enabled": "1", "survey_question": "Was the printer fixed to your liking?"})
        _, _, page = self._call("GET", "/my/ITO-1", cookie=bob)
        self.assertIn("Was the printer fixed to your liking?", page)
        self.assertNotIn("How did we do?", page)
        self._call("POST", "/admin/board/IT_HELP/settings", cookie=self.alice, form=base)         # the box unticked: off
        conn = db.connect(self.db_path)
        self.addCleanup(conn.close)
        self.assertEqual(conn.execute("SELECT survey_enabled, survey_question FROM board WHERE board_id = 'IT_HELP'").fetchone()[:],
                         (0, None))
        self.assertFalse(survey.pending(conn, "ITO-1"))
        _, _, page = self._call("GET", "/my/ITO-1", cookie=bob)
        self.assertNotIn("How did we do?", page)
        self.assertNotIn("/my/ITO-1/survey", page)
        status, _, _ = self._call("POST", "/my/ITO-1/survey", cookie=bob, form={"score": "5"})
        self.assertFalse(conn.execute("SELECT 1 FROM survey_response").fetchone())
        detail = conn.execute("SELECT detail FROM audit_event WHERE action = 'BOARD_CONFIG' ORDER BY audit_id DESC LIMIT 1").fetchone()[0]
        self.assertIn("survey", detail)

    # ------------------------------------------------------------ knowledge categories

    def test_knowledge_categories_are_kept_in_setup_and_filter_the_list(self):
        from psaspine import knowledge
        with self.assertRaises(ValueError):
            knowledge.add_category(self.conn, "  ", at=self.at, actor="root")
        printers = knowledge.add_category(self.conn, "Printers", at=self.at, actor="root")
        accounts = knowledge.add_category(self.conn, "Accounts", at=self.at, actor="root")
        with self.assertRaises(ValueError):
            knowledge.add_category(self.conn, "printers", at=self.at, actor="root")
        self.assertEqual((printers, accounts), ("KC_PRINTERS", "KC_ACCOUNTS"))
        a1 = knowledge.create(self.conn, title="Blank labels", body="Restart it.", category_id=printers, at=self.at, actor="alice")
        a2 = knowledge.create(self.conn, title="Locked out", body="Unlock in AD.", category_id=accounts, at=self.at, actor="alice")
        with self.assertRaises(ValueError):
            knowledge.create(self.conn, title="x", body="y", category_id="KC_NOPE", at=self.at, actor="alice")
        self.assertEqual([r["article_id"] for r in knowledge.search(self.conn, category_id=printers)], [a1])
        self.assertEqual(knowledge.get(self.conn, a2)["category_name"], "Accounts")
        self.assertEqual(knowledge.save_category(self.conn, accounts, at=self.at, actor="root", inactive=True), "saved")
        self.assertEqual([c["category_id"] for c in knowledge.categories(self.conn)], [printers])       # retired: not offered
        with self.assertRaises(ValueError):
            knowledge.save(self.conn, a1, title="Blank labels", body="Restart it.", audience="INTERNAL", board_id=None,
                           catalogue_item_id=None, category_id=accounts, at=self.at, actor="alice")
        self.assertEqual(knowledge.get(self.conn, a2)["category_name"], "Accounts")                 # kept where it was
        self.assertEqual(knowledge.categories(self.conn, all_rows=True)[0]["used"], 1)
        self.conn.commit()
        status, _, _ = self._call("GET", "/admin/kb-categories", cookie=self.alice)
        self.assertTrue(status.startswith("403"), status)
        _, _, page = self._call("GET", "/admin/kb-categories", cookie=self.root)
        self.assertIn("<h1>Knowledge categories</h1>", page)
        self.assertIn("value='Printers'", page)
        self.assertIn("Restore", page)                                                        # the retired one
        self._call("POST", "/admin/kb-categories", cookie=self.root, form={"name": "Clinical systems"})
        self._call("POST", "/admin/kb-categories/KC_PRINTERS", cookie=self.root, form={"name": "Printing"})
        conn = db.connect(self.db_path)
        self.addCleanup(conn.close)
        self.assertEqual([c["name"] for c in knowledge.categories(conn)], ["Printing", "Clinical systems"])
        _, _, page = self._call("GET", "/kb", cookie=self.alice, query="category=KC_PRINTERS")
        self.assertIn("Blank labels", page)
        self.assertNotIn("Locked out", page)
        self.assertIn("<td>Printing</td>", page)
        _, _, page = self._call("GET", "/kb/new", cookie=self.alice)
        self.assertIn("<select name=category_id>", page)

    # ------------------------------------------------------------ company status and type

    def test_company_status_and_type_are_words_a_system_administrator_keeps(self):
        from psaspine import companies
        cust = companies.add(self.conn, "status", "Customer", at=self.at, actor="root")
        dept = companies.add(self.conn, "type", "Hospital department", at=self.at, actor="root")
        supplier = companies.add(self.conn, "type", "Supplier", at=self.at, actor="root")
        self.assertEqual((cust, dept, supplier), ("CS_CUSTOMER", "CT_HOSPITAL_DEPARTMENT", "CT_SUPPLIER"))
        with self.assertRaises(ValueError):
            companies.add(self.conn, "status", "customer", at=self.at, actor="root")
        with self.assertRaises(ValueError):
            companies.set_company(self.conn, "PMC", at=self.at, actor="root", status_id="CS_NOPE")
        with self.assertRaises(ValueError):
            companies.set_company(self.conn, "NOBODY", at=self.at, actor="root", status_id=cust)
        self.assertEqual(companies.set_company(self.conn, "PMC", at=self.at, actor="root", status_id=cust, type_id=dept),
                         ["status - -> CS_CUSTOMER", "type - -> CT_HOSPITAL_DEPARTMENT"])
        self.assertEqual(companies.set_company(self.conn, "PMC", at=self.at, actor="root", status_id=cust, type_id=dept), [])
        row = self.conn.execute("SELECT * FROM entity WHERE entity_id = 'PMC'").fetchone()
        self.assertEqual(companies.words(self.conn, row), ("Customer", "Hospital department"))
        self.assertEqual(companies.save(self.conn, "type", supplier, at=self.at, actor="root", inactive=True), "saved")
        with self.assertRaises(ValueError):
            companies.set_company(self.conn, "PMC", at=self.at, actor="root", type_id=supplier)   # retired: not offered
        self.assertEqual(companies.rows(self.conn, "type")[0]["used"], 1)
        self.conn.commit()
        _, _, page = self._call("GET", "/company/PMC", cookie=self.alice)
        self.assertIn('<span class="chip">Customer</span>', page)
        self.assertIn('<span class="chip">Hospital department</span>', page)
        _, _, page = self._call("GET", "/companies", cookie=self.alice)
        self.assertIn('<span class="chip">Customer</span>', page)
        status, _, _ = self._call("GET", "/admin/companies", cookie=self.alice)
        self.assertTrue(status.startswith("403"), status)
        _, _, page = self._call("GET", "/admin/companies", cookie=self.root)
        self.assertIn("<h1>Companies</h1>", page)
        self.assertIn("value='CS_CUSTOMER' selected", page)
        self._call("POST", "/admin/companies/status", cookie=self.root, form={"name": "Prospect"})
        self._call("POST", "/admin/companies/PMC", cookie=self.root, form={"status_id": "CS_PROSPECT", "type_id": ""})
        conn = db.connect(self.db_path)
        self.addCleanup(conn.close)
        self.assertEqual(conn.execute("SELECT status_id, type_id FROM entity WHERE entity_id = 'PMC'").fetchone()[:], ("CS_PROSPECT", None))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'COMPANY_SETUP'").fetchone()[0], 7)

    # ------------------------------------------------------------ auto-assign

    def test_auto_assign_gives_an_unowned_ticket_an_owner_by_rule_or_mode(self):
        from psaspine import members
        setup.apply_template(self.conn, actor="t", at=self.at)
        pairs = setup.catalogue_choices(self.conn, "IT_HELP")
        self.assertTrue(pairs)
        item = pairs[0]["catalogue_item_id"]
        # nothing said: nobody, as it always was
        self.assertIsNone(board.auto_assignee(self.conn, "IT_HELP", item))
        w0 = self._open(catalogue_item_id=item)
        self.assertIsNone(self.conn.execute("SELECT owner FROM ticket WHERE work_item_id = ?", (w0,)).fetchone()[0])
        # least loaded among WORK/ADMIN members: alice (ADMIN), bob (WORK); carol reads only
        board.set_auto_assign(self.conn, "IT_HELP", "LEAST_LOADED", at=self.at, actor="alice")
        with self.assertRaises(ValueError):
            board.set_auto_assign(self.conn, "IT_HELP", "RANDOM", at=self.at, actor="alice")
        board.update_fields(self.conn, w0, at=self.at, actor="alice", owner="alice")
        w1 = self._open()
        self.assertEqual(self.conn.execute("SELECT owner FROM ticket WHERE work_item_id = ?", (w1,)).fetchone()[0], "bob")
        w2 = self._open()                                                                    # 1 each: alphabetical
        self.assertEqual(self.conn.execute("SELECT owner FROM ticket WHERE work_item_id = ?", (w2,)).fetchone()[0], "alice")
        kinds = [r[0] for r in self.conn.execute("SELECT kind FROM ticket_event WHERE work_item_id = ? AND kind = 'ASSIGN'", (w2,))]
        self.assertEqual(kinds, ["ASSIGN"])
        # a ticket that arrives with an owner keeps it
        w3 = self._open(owner="carol")
        self.assertEqual(self.conn.execute("SELECT owner FROM ticket WHERE work_item_id = ?", (w3,)).fetchone()[0], "carol")
        # a rule for the pair outranks the mode, and names only someone who works the board
        with self.assertRaises(ValueError):
            board.set_auto_assign_rule(self.conn, "IT_HELP", item, "carol", at=self.at, actor="alice")
        with self.assertRaises(ValueError):
            board.set_auto_assign_rule(self.conn, "IT_HELP", "NO_SUCH_PAIR", "bob", at=self.at, actor="alice")
        board.set_auto_assign_rule(self.conn, "IT_HELP", item, "BOB", at=self.at, actor="alice")
        self.assertEqual(board.auto_assign_rules(self.conn, "IT_HELP")[0]["member"], "bob")
        w4 = self._open(catalogue_item_id=item)
        self.assertEqual(self.conn.execute("SELECT owner FROM ticket WHERE work_item_id = ?", (w4,)).fetchone()[0], "bob")
        # the owner is emailed when the board emails owners (bob has an address)
        self.conn.execute("UPDATE board SET notify_owner = 1 WHERE board_id = 'IT_HELP'")
        w5 = self._open(catalogue_item_id=item)
        self.assertEqual([m["recipient"] for m in self._mails("OWNER")], ["bob"])
        self.assertIn("auto-assign", self._mails("OWNER")[0]["body"])
        # a member who left the board is never assigned: the rule falls through to the mode
        members.deactivate(self.conn, "bob", at=self.at, actor="root")
        self.assertEqual(board.auto_assignee(self.conn, "IT_HELP", item), "alice")
        # the default team's leader
        self.conn.execute("INSERT INTO board_team (team_id, board_id, name, team_leader, is_default) VALUES ('T1','IT_HELP','Desk','alice',1)")
        board.set_auto_assign(self.conn, "IT_HELP", "TEAM_LEADER", at=self.at, actor="alice")
        self.assertEqual(board.auto_assignee(self.conn, "IT_HELP", None), "alice")
        self.conn.execute("UPDATE board_team SET team_leader = 'carol' WHERE team_id = 'T1'")   # reads only: nobody
        self.assertIsNone(board.auto_assignee(self.conn, "IT_HELP", None))
        board.set_auto_assign_rule(self.conn, "IT_HELP", item, None, at=self.at, actor="alice")
        self.assertEqual(board.auto_assign_rules(self.conn, "IT_HELP"), [])
        self.conn.commit()
        # the tab
        _, _, page = self._call("GET", "/admin/board/IT_HELP", cookie=self.alice, query="tab=assign")
        self.assertIn("Who a new ticket goes to", page)
        self.assertIn("value=TEAM_LEADER style='width:auto' checked", page)
        _, h, _ = self._call("POST", "/admin/board/IT_HELP/assign", cookie=self.alice, form={"mode": "LEAST_LOADED"})
        self.assertIn("msg=Saved", dict(h)["Location"])
        _, h, _ = self._call("POST", "/admin/board/IT_HELP/assign/rule", cookie=self.alice,
                             form={"catalogue_item_id": item, "member": "alice"})
        self.assertIn("Rule+added", dict(h)["Location"])
        _, _, page = self._call("GET", "/admin/board/IT_HELP", cookie=self.alice, query="tab=assign")
        self.assertIn(f"value='{item}'", page)
        _, h, _ = self._call("POST", "/admin/board/IT_HELP/assign/rule/remove", cookie=self.alice, form={"catalogue_item_id": item})
        self.assertIn("Rule+removed", dict(h)["Location"])

    # ------------------------------------------------------------ the in/out board

    def test_the_in_out_board_is_said_by_each_person_for_themselves(self):
        from psaspine import presence
        with self.assertRaises(ValueError):
            presence.set_state(self.conn, "alice", "GONE", at=self.at)
        with self.assertRaises(ValueError):
            presence.set_state(self.conn, "alice", "OUT", at=self.at, back_at="soon")
        presence.set_state(self.conn, "alice", "OUT", at=self.at, note="ward 3", back_at="2026-09-30T14:00")
        presence.set_state(self.conn, "Alice", "ON_SITE", at=self.at, note="ward 3")           # the same person, once
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM member_presence").fetchone()[0], 1)
        self.assertEqual(presence.word(presence.current(self.conn, "alice")), "On site: ward 3")
        presence.set_state(self.conn, "bob", "OUT", at=self.at, back_at="2026-09-30 14:00")
        self.assertEqual(presence.word(presence.current(self.conn, "bob")), "Out until 14:00")
        presence.set_state(self.conn, "bob", "LEAVE", at=self.at, back_at="2026-10-05 08:00")
        self.assertEqual(presence.word(presence.current(self.conn, "bob")), "On leave until 2026-10-05 08:00")
        self.assertEqual(presence.all_(self.conn, ["carol"]), {"carol": None})
        self.conn.commit()
        _, _, page = self._call("GET", "/inout", cookie=self.alice)
        self.assertIn("<h1>In / out</h1>", page)
        self.assertIn("On leave", page)
        self.assertIn("ward 3", page)
        self.assertIn("not said", page)                                                       # carol
        _, h, _ = self._call("POST", "/inout/me", cookie=self.alice, form={"state": "IN", "note": "", "back_at": ""})
        self.assertIn("msg=Said", dict(h)["Location"])
        conn = db.connect(self.db_path)
        self.addCleanup(conn.close)
        self.assertEqual(conn.execute("SELECT state, note, set_by FROM member_presence WHERE member = 'alice'").fetchone()[:],
                         ("IN", None, "alice"))
        _, _, page = self._call("GET", "/schedule", cookie=self.alice, query="week=2026-09-28")
        self.assertIn("On leave until 2026-10-05 08:00", page)
        self.assertIn("href='/inout'", page)
        _, _, page = self._call("GET", "/my/profile", cookie=self.alice)
        self.assertIn("Say where I am", page)
        status, _, _ = self._call("GET", "/inout", cookie=self._cookie_for("nobody"))
        self.assertTrue(status.startswith("403") or status.startswith("404"), status)


class MailCutoverTest(unittest.TestCase):
    """058, SQL01's mail cut-over (1 Oct 2026): helpdesk@, its help@ alias and
    support@ all land on PMO Helpdesk; the requester hears at each status
    change in that status's own words, with more placeholders and none that
    carries a summary, a note or a subject; a reply goes out from the address
    the requester wrote to."""

    _environ = WebWSGITest._environ
    _call = WebWSGITest._call
    _cookie_for = WebWSGITest._cookie_for

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.conn = _fresh(self.tmp)
        self.addCleanup(self.conn.close)
        self.drop = Path(self.tmp.name) / "drop"
        self.drop.mkdir()
        self.at = datetime(2026, 10, 1, 9, 0)
        self.n = 0
        from psaspine import setup
        setup.apply_starter(self.conn, "IT_HELP", actor="t", at=self.at)
        self.conn.execute("INSERT INTO board (board_id, display_name, phase, fulfiller_group, is_live, is_unrouted)"
                          " VALUES ('BIOMED', 'Biomedical', '2', 'Dada', 0, 0)")
        self.conn.execute(
            "INSERT INTO contact (contact_id, entity_id, display_name, email, sam_account, source, inactive, created_at)"
            " VALUES ('C_W3', 'PMC', 'Ward 3 Station', 'ward3@pmcne.ph', 'ward3', 'AD', 0, '2026')")
        self.conn.execute(
            "INSERT INTO contact (contact_id, entity_id, display_name, email, sam_account, source, inactive, created_at)"
            " VALUES ('C_BOB', 'PMC', 'Bob Reyes', 'bob@pmcne.ph', 'bob', 'AD', 0, '2026')")
        self.conn.commit()

    def _msg(self, *, subject, to, sender="ward3@pmcne.ph", delivered_to=None):
        self.n += 1
        headers = [f"From: {sender}", f"To: {to}", f"Subject: {subject}", "Date: Thu, 01 Oct 2026 09:00:00 +0800",
                   f"Message-ID: <c{self.n}@pmcne.ph>"]
        if delivered_to:
            headers.append(f"Delivered-To: {delivered_to}")
        (self.drop / f"{self.n:03d}.eml").write_bytes(("\r\n".join(headers) + "\r\n\r\nPlease help.\r\n").encode())

    def _ticket(self, n):
        return self.conn.execute("SELECT t.work_item_id, t.board_id, i.to_address FROM intake_message i"
                                 " JOIN ticket t ON t.work_item_id = i.work_item_id WHERE i.message_id = ?",
                                 (f"<c{n}@pmcne.ph>",)).fetchone()

    def _status_mails(self, wid):
        return self.conn.execute("SELECT notification_id, subject, body, status, from_address FROM notification"
                                 " WHERE work_item_id = ? AND recipient_role = 'REQUESTER_STATUS' ORDER BY notification_id",
                                 (wid,)).fetchall()

    # ------------------------------------------------------------ item 1: several addresses, one board

    def test_one_board_claims_three_addresses_and_each_lands_there(self):
        from psaspine import intake
        got = intake.set_addresses(self.conn, "IT_HELP", "Helpdesk@pmcne.ph, help@pmcne.ph;\nsupport@pmcne.ph help@pmcne.ph",
                                   at=self.at, actor="dada")
        self.assertEqual(got, ["help@pmcne.ph", "helpdesk@pmcne.ph", "support@pmcne.ph"])
        # an address is one board's, and nothing is written when any one is refused
        with self.assertRaises(ValueError):
            intake.set_addresses(self.conn, "BIOMED", "biomed@pmcne.ph, support@pmcne.ph", at=self.at, actor="dada")
        with self.assertRaises(ValueError):
            intake.set_addresses(self.conn, "BIOMED", "biomed@pmcne.ph, not an address", at=self.at, actor="dada")
        self.assertEqual(intake.addresses_of(self.conn, "BIOMED"), [])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM audit_event WHERE action = 'BOARD_INTAKE_ADDRESS'").fetchone()[0], 1)
        self._msg(subject="Printer jams", to="help@pmcne.ph")                                              # the alias, as To keeps it
        self._msg(subject="Scanner offline", to="PMC Service Board <support@pmcne.ph>")
        self._msg(subject="Keyboard", to="someone@pmcne.ph", delivered_to="helpdesk@pmcne.ph")
        self._msg(subject="The desk talking", to="ward3@pmcne.ph", sender="support@pmcne.ph")              # never a ticket
        (self.drop / "half.eml.part").write_bytes(b"From: x\r\n")                                         # a pickup mid-write
        counts = intake.import_drop(self.conn, self.drop, run_id="c1", at=self.at)                         # no run board
        self.assertEqual((counts["files"], counts["new"], counts["routed_by_address"], counts["loop_guarded"]), (4, 3, 3, 1))
        self.assertEqual([tuple(self._ticket(i))[1:] for i in (1, 2, 3)],
                         [("IT_HELP", "help@pmcne.ph"), ("IT_HELP", "support@pmcne.ph"), ("IT_HELP", "helpdesk@pmcne.ph")])
        # the pickup's -BoardId: mail nobody claims lands on the board it names
        self._msg(subject="Mouse", to="someone@pmcne.ph")
        intake.import_drop(self.conn, self.drop, run_id="c2", at=self.at, board_id="BIOMED")
        self.assertEqual(self._ticket(5)["board_id"], "BIOMED")
        # a board that is cleared claims nothing
        intake.set_addresses(self.conn, "IT_HELP", "", at=self.at, actor="dada")
        self.assertEqual(intake.board_addresses(self.conn), {})

    # ------------------------------------------------------------ items 2 and 3: an email for each status

    def test_each_status_sends_its_own_email_with_the_new_placeholders(self):
        from psaspine import board, intake, outbox
        self.conn.execute("UPDATE board SET notify_requester = 1 WHERE board_id = 'IT_HELP'")
        intake.set_addresses(self.conn, "IT_HELP", "helpdesk@pmcne.ph, support@pmcne.ph", at=self.at, actor="dada")
        self._msg(subject="A patient's chart will not print", to="support@pmcne.ph")
        intake.import_drop(self.conn, self.drop, run_id="c1", at=self.at)
        wid = self._ticket(1)["work_item_id"]
        # off until the board turns a status on: as before 058
        board.change_status(self.conn, wid, "IT_HELP.IN_PROGRESS", at=self.at, actor="bob")
        self.assertEqual(self._status_mails(wid), [])
        self.assertEqual(outbox.set_all_status_mails(self.conn, "IT_HELP", enabled=True, at=self.at, actor="dada"),
                         len(outbox.status_mails(self.conn, "IT_HELP")) + 1)          # and picked up
        board.update_fields(self.conn, wid, at=self.at, actor="bob", owner="bob")
        board.change_status(self.conn, wid, "IT_HELP.ASSIGNED", at=self.at, actor="bob")
        [m] = self._status_mails(wid)
        self.assertEqual(m["subject"], f"[{wid}] Your request: Assigned")
        self.assertIn("Hello Ward 3 Station,", m["body"])
        self.assertIn("Assigned to a technician", m["body"])                      # {status_text}: the portal's words
        self.assertIn("It is with Bob Reyes.", m["body"])                          # {owner}
        self.assertTrue(m["body"].endswith("PMO Helpdesk\nPremiere Medical Center - Nueva Ecija"))   # {board}, {hospital}
        self.assertIn("1 October 2026", m["body"])                                 # {date}
        self.assertNotIn("chart", m["subject"] + m["body"])                        # the requester's subject never comes back
        self.assertEqual(m["from_address"], "support@pmcne.ph")                    # where they wrote
        # a second change before the sender runs: one email, the newer
        board.change_status(self.conn, wid, "IT_HELP.WAITING_ON_REQUESTER", at=self.at, actor="bob")
        [m] = self._status_mails(wid)
        self.assertEqual(m["subject"], f"[{wid}] We need something from you")
        self.assertIn("Reply to this email", m["body"])
        due = {d["id"]: d for d in outbox.pending(self.conn, allowed_domains=("pmcne.ph",), portal_url="https://help.pmcne.ph")}
        item = due[m["notification_id"]]
        self.assertEqual((item["to"], item["from"]), ("ward3@pmcne.ph", "support@pmcne.ph"))
        self.assertIn("https://help.pmcne.ph/my/" + wid, item["body"])
        outbox.mark(self.conn, m["notification_id"], "SENT", at=self.at)
        # the status the ticket is already in is no change
        board.change_status(self.conn, wid, "IT_HELP.WAITING_ON_REQUESTER", at=self.at, actor="bob")
        self.assertEqual(len(self._status_mails(wid)), 1)
        # a closing status with its email on sends that, not the closed email as well
        board.change_status(self.conn, wid, "IT_HELP.CLOSED", at=self.at, actor="bob")
        last = self._status_mails(wid)[-1]
        self.assertEqual(last["subject"], f"[{wid}] Your request is closed")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM notification WHERE work_item_id = ? AND recipient_role = 'REQUESTER'"
                                           " AND subject LIKE '%closed%'", (wid,)).fetchone()[0], 0)
        # the board's requester switch still governs every requester email
        self._msg(subject="Mouse", to="helpdesk@pmcne.ph")
        intake.import_drop(self.conn, self.drop, run_id="c2", at=self.at)
        w2 = self._ticket(2)["work_item_id"]
        self.conn.execute("UPDATE board SET notify_requester = 0 WHERE board_id = 'IT_HELP'")
        board.change_status(self.conn, w2, "IT_HELP.IN_PROGRESS", at=self.at, actor="bob")
        self.assertEqual(self._status_mails(w2), [])
        # a status turned off sends nothing; the closed email is back for a closing status that is off
        self.conn.execute("UPDATE board SET notify_requester = 1 WHERE board_id = 'IT_HELP'")
        outbox.set_status_mail(self.conn, "IT_HELP.CLOSED", enabled=False, at=self.at, actor="dada")
        board.change_status(self.conn, w2, "IT_HELP.CLOSED", at=self.at, actor="bob")
        self.assertEqual(self._status_mails(w2), [])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM notification WHERE work_item_id = ? AND recipient_role = 'REQUESTER'"
                                           " AND status = 'PENDING'", (w2,)).fetchone()[0], 1)

    def test_a_board_words_each_status_and_only_safe_placeholders(self):
        from psaspine import board, outbox, tickets
        self.conn.execute("UPDATE board SET notify_requester = 1 WHERE board_id = 'IT_HELP'")
        shapes = {m["name"]: m["shape"] for m in outbox.status_mails(self.conn, "IT_HELP")}
        self.assertEqual((shapes["Waiting on Requester"], shapes["Waiting on Vendor"], shapes["Resolved"], shapes["Closed"]),
                         ("WAITING", "OTHER", "RESOLVED", "CLOSED"))
        for bad in ("{summary}", "{note}", "{subject}", "{requester.__class__}", "{0}", "{", "{owner!r}",
                    "{requester:>99999999}"):
            with self.assertRaises(ValueError, msg=bad):
                outbox.set_status_mail(self.conn, "IT_HELP.IN_PROGRESS", enabled=True, subject="x",
                                       body=f"About {bad}", at=self.at, actor="dada")
        m = outbox.set_status_mail(self.conn, "IT_HELP.IN_PROGRESS", enabled=True, at=self.at, actor="dada",
                                   subject="{ticket} is {status}",
                                   body="Hi {requester}. {owner} took it on {date}: {status_text}. Track it at {link}.")
        self.assertTrue(m["custom"] and m["enabled"])
        wid = tickets.open_ticket(self.conn, board_id="IT_HELP", summary="Printer", impact="I3", urgency="U3",
                                  requested_by="bob@pmcne.ph", at=self.at, source="PORTAL")
        board.change_status(self.conn, wid, "IT_HELP.IN_PROGRESS", at=self.at, actor="alice")
        [n] = self._status_mails(wid)
        self.assertEqual(n["subject"], f"[{wid}] {wid} is In Progress")
        self.assertEqual(n["body"], "Hi Bob Reyes. the PMO Helpdesk team took it on 1 October 2026: Someone is working on it."
                                    " Track it at {link}.")
        self.assertIsNone(n["from_address"])                                       # a portal ticket: the sender's mailbox
        [item] = [d for d in outbox.pending(self.conn, allowed_domains=("pmcne.ph",)) if d["id"] == n["notification_id"]]
        self.assertIn("Track it at the PMC Requests portal, under Your requests.", item["body"])
        self.assertIsNone(item["from"])
        # back to the desk's words keeps the switch
        m = outbox.set_status_mail(self.conn, "IT_HELP.IN_PROGRESS", enabled=True, desk_words=True, at=self.at, actor="dada")
        self.assertEqual((m["custom"], m["subject"]), (False, "Your request: {status}"))
        # the event templates take the new placeholders too
        outbox.set_template(self.conn, "IT_HELP", "OPENED", subject="Thanks {requester}", body="{board} has it. {link}",
                            at=self.at, actor="dada")

    def test_the_requester_hears_when_someone_picks_the_ticket_up(self):
        from psaspine import board, outbox, tickets
        self.conn.execute("UPDATE board SET notify_requester = 1 WHERE board_id = 'IT_HELP'")
        outbox.set_pickup_mail(self.conn, "IT_HELP", enabled=True, at=self.at, actor="dada")
        wid = tickets.open_ticket(self.conn, board_id="IT_HELP", summary="Monitor flickers", impact="I3", urgency="U3",
                                  requested_by="ward3@pmcne.ph", at=self.at, source="PORTAL")
        opened = self.conn.execute("SELECT body FROM notification WHERE work_item_id = ? AND recipient_role = 'REQUESTER'",
                                   (wid,)).fetchone()["body"]
        self.assertIn("Hello Ward 3 Station,", opened)                              # the desk's words, for the hospital
        self.assertIn("it is with the PMO Helpdesk team", opened)
        self.assertIn("stopping care on the ward", opened)
        self.assertTrue(opened.endswith("Premiere Medical Center - Nueva Ecija"))
        self.assertEqual(self._status_mails(wid), [])                               # nobody has it yet
        board.update_fields(self.conn, wid, at=self.at, actor="bob", owner="bob")
        [m] = self._status_mails(wid)
        self.assertEqual(m["subject"], f"[{wid}] Bob Reyes has picked up your request")
        self.assertIn("Bob Reyes from PMO Helpdesk has picked up your request, as of 1 October 2026", m["body"])
        # handed to someone else before the first has gone: one email, the newer
        board.update_fields(self.conn, wid, at=self.at, actor="bob", owner="ward3")
        [m] = self._status_mails(wid)
        self.assertIn("Ward 3 Station has picked up", m["subject"])
        # cleared: nobody picked it up, nothing new is said
        board.update_fields(self.conn, wid, at=self.at, actor="bob", owner="")
        self.assertIn("Ward 3 Station has picked up", self._status_mails(wid)[0]["subject"])
        # the hospital's name is deployment config
        os.environ["PSA_HOSPITAL_NAME"] = "PMC Annex"
        self.addCleanup(os.environ.pop, "PSA_HOSPITAL_NAME", None)
        self.assertEqual(outbox._values(self.conn, wid, at=self.at)["hospital"], "PMC Annex")

    def test_mail_setup_turns_a_board_on_in_one_step_and_previews_first(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr
        from psaspine.__main__ import main
        path = str(Path(self.tmp.name) / "cli-mail.db")
        db.init(path).close()
        args = ["mail-setup", path, "--board", "IT_HELP", "--addresses", "helpdesk@pmcne.ph, help@pmcne.ph, support@pmcne.ph",
                "--email-requester", "on", "--moving-emails", "on", "--actor", "sql01 for dada.banal"]
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            from psaspine import setup
            c = db.connect(path)
            setup.apply_starter(c, "IT_HELP", actor="t", at=self.at)
            c.commit()
            c.close()
            self.assertEqual(main(args), 0)                                         # preview
            c = db.connect(path)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM board_intake_address").fetchone()[0], 0)
            c.close()
            self.assertEqual(main(args + ["--apply", "--show"]), 0)
            self.assertEqual(main(["mail-setup", path, "--board", "NOPE", "--actor", "x"]), 1)
        self.assertIn("PREVIEW", out.getvalue())
        shown = out.getvalue()
        self.assertIn("email the requester: ON", shown)
        self.assertIn("[on] Status: Waiting on Requester", shown)
        self.assertIn("[on] Picked up", shown)
        self.assertIn("signed off as: Premiere Medical Center - Nueva Ecija", shown)
        c = db.connect(path)
        self.addCleanup(c.close)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM board_intake_address WHERE board_id = 'IT_HELP'").fetchone()[0], 3)
        self.assertEqual(c.execute("SELECT notify_requester FROM board WHERE board_id = 'IT_HELP'").fetchone()[0], 1)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM status_mail WHERE board_id = 'IT_HELP' AND enabled = 1").fetchone()[0],
                         c.execute("SELECT COUNT(*) FROM board_status WHERE board_id = 'IT_HELP' AND inactive = 0").fetchone()[0] + 1)

    def test_the_emails_tab_turns_statuses_on_and_saves_their_words(self):
        WebWSGITest.setUp(self)
        self.addCleanup(self.tmp.cleanup)
        from psaspine import setup
        conn = db.connect(self.db_path)
        self.addCleanup(conn.close)
        setup.apply_starter(conn, "IT_HELP", actor="t", at=self.at)
        conn.commit()
        root = self._cookie_for("alice")             # ADMIN on IT_HELP
        status, _, body = self._call("GET", "/admin/board/IT_HELP", cookie=root, query="tab=emails")
        self.assertTrue(status.startswith("200"), status)
        self.assertIn("An email at each status", body)
        self.assertIn("Waiting on Requester", body)
        self.assertIn("<b>0</b> of", body)
        status, headers, _ = self._call("POST", "/admin/board/IT_HELP/emails/status-all", cookie=root, form={"enabled": "1"})
        self.assertTrue(status.startswith("303"), status)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM status_mail WHERE board_id = 'IT_HELP' AND enabled = 1").fetchone()[0],
                         conn.execute("SELECT COUNT(*) FROM board_status WHERE board_id = 'IT_HELP' AND inactive = 0").fetchone()[0] + 1)
        status, headers, _ = self._call("POST", "/admin/board/IT_HELP/emails/status", cookie=root,
                                        form={"board_status_id": "IT_HELP.IN_PROGRESS", "enabled": "1",
                                              "subject": "Fixed?", "body": "{summary} is fixed"})
        self.assertIn("Not+saved", dict(headers)["Location"])
        self._call("POST", "/admin/board/IT_HELP/emails/status", cookie=root,
                   form={"board_status_id": "IT_HELP.IN_PROGRESS", "subject": "Fixed?", "body": "Is it fixed, {requester}?"})
        row = conn.execute("SELECT enabled, subject FROM status_mail WHERE board_id = 'IT_HELP' AND mail_key = 'IT_HELP.IN_PROGRESS'").fetchone()
        self.assertEqual(tuple(row), (0, "Fixed?"))                               # unticked: off, words kept
        # another board's status cannot be set from this board's page
        status, headers, _ = self._call("POST", "/admin/board/IT_HELP/emails/status", cookie=root,
                                        form={"board_status_id": "PHI.NEW", "enabled": "1", "subject": "x", "body": "y"})
        self.assertIn("not+on+this+board", dict(headers)["Location"])
        # the board page takes several intake addresses
        self._call("POST", "/admin/board/IT_HELP/reply-policy", cookie=root,
                   form={"policy": "REOPEN", "intake_address": "helpdesk@pmcne.ph, help@pmcne.ph, support@pmcne.ph"})
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM board_intake_address WHERE board_id = 'IT_HELP'").fetchone()[0], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
