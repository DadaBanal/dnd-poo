"""The feed watch and its alerts (M3.3), from the monitoring network.

The watch reads the engine, the stand-in AD, the images' filesystem and the
backups (watch/src/main.mjs); Prometheus turns what it reads into alerts
(monitor/rules.yml); Alertmanager emails ICT, here through a stand-in mail
relay (Mailpit) whose inbox the tests can read.
"""

from __future__ import annotations

import os
import re
import time

import pytest
import requests

import synth

WATCH = os.environ.get("WATCH_URL", "http://watch:9100")
MAIL = os.environ.get("MAILPIT_URL", "http://mailpit:8025")
DC = "ldaps://dc1.pmc.test:636"


def metrics() -> dict[str, list[tuple[dict[str, str], float]]]:
    found: dict[str, list[tuple[dict[str, str], float]]] = {}
    for line in requests.get(f"{WATCH}/metrics", timeout=10).text.splitlines():
        if not line or line.startswith("#"):
            continue
        name, labels, value = re.match(r"^([a-z_]+)(?:\{(.*)\})? (\S+)$", line).groups()
        found.setdefault(name, []).append((dict(re.findall(r'(\w+)="((?:[^"\\]|\\.)*)"', labels or "")), float(value)))
    return found


def value(found, name: str, **labels) -> float | None:
    for have, v in found.get(name, []):
        if all(have.get(k) == want for k, want in labels.items()):
            return v
    return None


def metrics_when(ready):
    """A check for wait_for: the watch's metrics, once ready(metrics) holds."""
    def check():
        found = metrics()
        return found if ready(found) else None
    return check


def wait_for(check, timeout: float, step: float = 2):
    deadline = time.monotonic() + timeout
    while not (result := check()):
        assert time.monotonic() < deadline, f"not within {timeout} s"
        time.sleep(step)
    return result


def test_the_watch_sees_the_engine_the_directory_the_storage_and_the_certificate():
    found = wait_for(metrics_when(lambda m: value(m, "pmc_engine_up") == 1), 60)
    assert value(found, "pmc_directory_up", server=DC) == 1
    assert value(found, "pmc_directory_certificate_expiry_timestamp_seconds", server=DC) > time.time()
    assert value(found, "pmc_site_certificate_expiry_timestamp_seconds") > time.time()
    assert value(found, "pmc_storage_free_bytes") > 0


def test_every_registered_modality_has_a_feed_and_a_limit(modalities):
    found = wait_for(metrics_when(lambda m: all(
        value(m, "pmc_feed_last_study_timestamp_seconds", modality=name) for name in modalities)), 60)
    for name, aet in modalities.items():
        # The site's limit: a day, unless ICT sets another for a modality.
        assert value(found, "pmc_feed_silence_threshold_seconds", modality=name, aet=aet) == 24 * 3600


def test_a_silent_modality_is_reported_to_ict_by_email(engine, run_id, measurements):
    # A modality ICT has just registered, allowed 20 s of silence here
    # (compose.test.yaml; a day or more on site).
    engine.register("watch-quiet", "SYN_QUIET", engine.my_address(), store=True)
    try:
        # It sends one study, and the watch sees it...
        study = synth.Study("cr", f"{run_id}Q", "SYN_QUIET", scale=0.25)
        assert all(s == 0x0000 for s in engine.store("SYN_QUIET", study.datasets))
        wait_for(lambda: (value(metrics(), "pmc_feed_studies_total", modality="watch-quiet") or 0) >= 1, 60)
        last = time.time()

        # ...then nothing more, and ICT gets an email naming it.
        def emailed():
            messages = requests.get(f"{MAIL}/api/v1/messages", timeout=10).json()["messages"]
            return next((m for m in messages
                         if "FeedSilent" in m["Subject"] and "watch-quiet" in m["Subject"]
                         and m["Subject"].startswith("[FIRING")), None)
        message = wait_for(emailed, 240, step=5)
        measurements["feed_silence_emailed_after_s"] = round(time.time() - last)
        body = requests.get(f"{MAIL}/api/v1/message/{message['ID']}", timeout=10).json()
        assert [to["Address"] for to in body["To"]] == ["ict@pmc.test"]
        assert "SYN_QUIET" in body["HTML"]
        # PMC's own email (monitor/templates/pmc.tmpl), with a plain-text part
        # for mail programs that show no HTML.
        assert "An alert for ICT" in body["HTML"] and "Better Care." in body["HTML"]
        assert body["Text"].startswith("PMC Imaging: an alert for ICT")
        assert "aet: SYN_QUIET" in body["Text"]
    finally:
        engine.request("DELETE", "/modalities/watch-quiet")


@pytest.mark.after_backup
def test_the_watch_sees_the_nightly_backup():
    def fresh():
        found = metrics()
        recent = time.time() - 900
        return all((value(found, "pmc_backup_last_success_timestamp_seconds", stanza=s, type="full") or 0) > recent
                   for s in ("index", "platform")) and \
            (value(found, "pmc_snapshot_last_success_timestamp_seconds") or 0) > recent
    wait_for(fresh, 60)
