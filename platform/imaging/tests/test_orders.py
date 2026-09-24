"""The BizBox connector (M3.2): orders placed in BizBox reach the consoles'
worklists, and leave them once the study has arrived.

BizBox here is a stand-in SQL Server 2022 with a synthetic schema
(orders/test/bizbox/): these tests write to it as BizBox's own staff would, and
ask the engine's worklist as each console does (C-FIND, from its own AE title).
The connector polls every 2 s here (30 s on site). Carried from the HIS-link
research proof, whose tests these are, made to run against the platform.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import time
from pathlib import Path

import mssql_python
import pytest
import requests

import synth
from engine import wait_for
from test_worklists import _query

SERVER = os.environ.get("BIZBOX_SERVER", "bizbox")
ORDERS = os.environ.get("ORDERS_URL", "http://orders:8080")
XRAY = ("NX_DEFAULT", "CONSOLE1")  # the X-ray section's two consoles (compose.test.yaml)
CT = "TM_CT_CMW_V3.00"


def connect(user: str, secret: str):
    conn = mssql_python.connect(
        f"SERVER={SERVER};DATABASE=BizBoxSim;UID={user};PWD={Path(os.environ[secret]).read_text().strip()};"
        "Encrypt=yes;TrustServerCertificate=yes")
    conn.autocommit = True
    return conn


@pytest.fixture(scope="module")
def bizbox():
    """BizBox's own side: its administrator, who can write orders."""
    return connect("sa", "BIZBOX_SA_PASSWORD_SECRET")


def place(conn, order_no: str, hospital_no: str, section: str, *, last="SYNTHETIC", first="PATIENT",
          birth=dt.date(1980, 1, 1), desc="SYNTHETIC ORDER", code="SYN01", commit: bool = True):
    cur = conn.cursor()
    cur.execute("IF NOT EXISTS (SELECT 1 FROM dbo.patient WHERE hospital_no = ?) "
                "INSERT INTO dbo.patient (hospital_no, last_name, first_name, birth_date, sex) "
                "VALUES (?, ?, ?, ?, 'O')", (hospital_no, hospital_no, last, first, birth))
    cur.execute("INSERT INTO dbo.imaging_order (order_no, hospital_no, section, procedure_code, "
                "procedure_desc, referring_doctor, scheduled_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (order_no, hospital_no, section, code, desc, "SYNTHETIC REFERRER",
                 synth._now().replace(hour=8, minute=0, second=0, microsecond=0, tzinfo=None)))
    if commit and not conn.autocommit:
        conn.commit()


def entry(engine, console: str, accession: str):
    """The console's worklist entry for this accession, as its C-FIND returns it.
    It asks for the birth date too, which a console shows the technologist."""
    query = _query(synth._now().strftime("%Y%m%d"))
    query.PatientBirthDate = ""
    statuses, matches = engine.find_worklist(console, query)
    assert statuses and statuses[-1] == 0x0000, statuses
    return next((m for m in matches if str(m.AccessionNumber) == accession), None)


def metric(name: str, **labels) -> float:
    text = requests.get(f"{ORDERS}/metrics", timeout=10).text
    want = ",".join(f'{k}="{v}"' for k, v in labels.items())
    pattern = re.escape(f"{name}{{{want}}}" if labels else name) + r" (\S+)$"
    m = re.search("^" + pattern, text, re.M)
    return float(m.group(1)) if m else 0.0


def test_the_connector_may_read_its_view_and_nothing_else():
    ro = connect("pmc_orders_ro", "BIZBOX_RO_PASSWORD_SECRET")
    ro.cursor().execute("SELECT TOP (1) order_no FROM dbo.v_pmc_imaging_orders").fetchall()
    for sql in ("SELECT TOP (1) * FROM dbo.imaging_order",
                "SELECT TOP (1) * FROM dbo.patient",
                "INSERT INTO dbo.patient (hospital_no, last_name, first_name) VALUES ('X', 'X', 'X')"):
        with pytest.raises(Exception, match="(?i)permission"):
            ro.cursor().execute(sql)


def test_an_order_reaches_every_console_of_its_section_and_no_other(bizbox, engine, modalities, run_id, measurements):
    order = f"B{run_id[:8]}01"
    started = time.monotonic()
    place(bizbox, order, f"H{run_id[:9]}", "XRAY", desc="SYNTHETIC CHEST PA")
    found = [wait_for(lambda c=c: entry(engine, c, order), 60, f"{order} on {c}") for c in XRAY]
    measurements["order_reached_worklist_s"] = round(time.monotonic() - started, 1)
    # Both consoles hold the order's own StudyInstanceUID, fixed by the order.
    assert found[0].StudyInstanceUID == found[1].StudyInstanceUID
    assert str(found[0].StudyInstanceUID).startswith("2.25.")
    assert str(found[0].RequestedProcedureDescription) == "SYNTHETIC CHEST PA"
    assert entry(engine, CT, order) is None


def test_a_filipino_name_reaches_the_console_intact(bizbox, engine, modalities, run_id):
    order = f"B{run_id[:8]}02"
    place(bizbox, order, f"N{run_id[:9]}", "CT", last="SYNTHETIC PEÑA", first="NIÑO")
    found = wait_for(lambda: entry(engine, CT, order), 60, f"{order} on the CT console")
    assert str(found.PatientName) == "SYNTHETIC PEÑA^NIÑO"


def test_a_change_in_bizbox_updates_the_waiting_entry(bizbox, engine, modalities, run_id):
    order = f"B{run_id[:8]}03"
    hospital = f"C{run_id[:9]}"
    place(bizbox, order, hospital, "CT", desc="SYNTHETIC CT HEAD", birth=dt.date(1970, 5, 5))
    wait_for(lambda: entry(engine, CT, order), 60, f"{order} on the CT console")
    cur = bizbox.cursor()
    cur.execute("UPDATE dbo.imaging_order SET procedure_desc = ? WHERE order_no = ?", ("SYNTHETIC CT CHEST", order))
    cur.execute("UPDATE dbo.patient SET birth_date = ? WHERE hospital_no = ?", (dt.date(1971, 6, 6), hospital))
    found = wait_for(lambda: (e := entry(engine, CT, order)) is not None and
                     str(e.RequestedProcedureDescription) == "SYNTHETIC CT CHEST" and
                     str(e.PatientBirthDate) == "19710606" and e, 60, "the change on the CT console")
    assert found


def test_a_cancelled_order_leaves_every_console(bizbox, engine, modalities, run_id):
    order = f"B{run_id[:8]}04"
    place(bizbox, order, f"X{run_id[:9]}", "XRAY")
    for c in XRAY:
        wait_for(lambda c=c: entry(engine, c, order), 60, f"{order} on {c}")
    bizbox.cursor().execute("UPDATE dbo.imaging_order SET status = 'CANCELLED' WHERE order_no = ?", (order,))
    for c in XRAY:
        wait_for(lambda c=c: entry(engine, c, order) is None, 60, f"{order} gone from {c}")


def test_the_exam_takes_the_order_off_the_worklist_and_marks_it_performed(bizbox, engine, modalities, run_id):
    order = f"B{run_id[:8]}05"
    hospital = f"P{run_id[:9]}"
    place(bizbox, order, hospital, "CT")
    found = wait_for(lambda: entry(engine, CT, order), 60, f"{order} on the CT console")
    performed = metric("pmc_orders_synced_total", outcome="performed")
    # The CT console does the exam under the order's identifiers.
    study = synth.Study("ct", run_id, CT, accession=order, study_uid=str(found.StudyInstanceUID),
                        patient_id=hospital, scale=0.25)
    assert all(s == 0x0000 for s in engine.store(CT, study.datasets))
    wait_for(lambda: entry(engine, CT, order) is None, 90, f"{order} gone once its study is stable")
    wait_for(lambda: metric("pmc_orders_synced_total", outcome="performed") > performed, 60,
             "the connector marking the order performed")


def test_an_order_that_commits_late_is_neither_lost_nor_blocking(bizbox, engine, modalities, run_id):
    early, late = f"B{run_id[:8]}06", f"B{run_id[:8]}07"
    # A BizBox transaction writes the early order and stays open...
    held = connect("sa", "BIZBOX_SA_PASSWORD_SECRET")
    held.autocommit = False
    try:
        place(held, early, f"E{run_id[:9]}", "CT", commit=False)
        # ...while another writes, and commits, the late one.
        place(bizbox, late, f"L{run_id[:9]}", "CT")
        synced = metric("pmc_orders_last_sync_timestamp_seconds")
        # The connector keeps polling, not waiting behind the open transaction,
        # and holds the late order back rather than move past the early one.
        wait_for(lambda: metric("pmc_orders_last_sync_timestamp_seconds") > synced + 4, 30,
                 "the connector to keep polling")
        assert entry(engine, CT, late) is None
        held.commit()
    finally:
        held.close()
    for order in (early, late):
        wait_for(lambda o=order: entry(engine, CT, o), 60, f"{order} on the CT console")


def test_a_hundred_orders_at_once_all_reach_their_consoles(bizbox, engine, modalities, run_id, measurements):
    prefix = f"M{run_id[:8]}"
    started = time.monotonic()
    cur = bizbox.cursor()
    for n in range(100):
        place(bizbox, f"{prefix}{n:03d}", f"{prefix[:9]}{n:03d}", "XRAY")
    cur.execute("SELECT COUNT(*) FROM dbo.imaging_order WHERE order_no LIKE ?", (prefix + "%",))
    assert cur.fetchone()[0] == 100

    def on(console):
        statuses, matches = engine.find_worklist(console, _query(synth._now().strftime("%Y%m%d")))
        return sum(str(m.AccessionNumber).startswith(prefix) for m in matches)
    for c in XRAY:
        wait_for(lambda c=c: on(c) == 100, 120, f"100 orders on {c}")
    measurements["hundred_orders_on_both_consoles_s"] = round(time.monotonic() - started, 1)
