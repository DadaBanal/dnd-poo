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

from psaspine import db, register, reports  # noqa: E402
import sqlite_to_tsql  # noqa: E402
from sqlite_ddl import Unsupported  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "register-sample.csv"
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

    def test_no_board_is_live_and_none_can_go_live_without_a_named_owner(self):
        live = self.conn.execute("SELECT COUNT(*) c FROM board WHERE is_live=1").fetchone()["c"]
        self.assertEqual(live, 0)
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE board SET is_live=1 WHERE board_id='IT_HELP'")

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
