"""The running engine is the one the configuration describes, and it admits only known modalities."""

from __future__ import annotations

import requests
from pydicom.dataset import Dataset

import synth
from engine import REJECTED

# explorer.js is not a plugin: /plugins lists it as the scripts plugins add to
# the built-in explorer.
EXPECTED_PLUGINS = {
    "authorization": "0.12.0",
    "dicom-web": "1.24",
    "gdcm": "1.8",
    "housekeeper": "1.13.0",
    "orthanc-worklists": "0.9.2",
    "postgresql-index": "11.0",
    "postgresql-storage": "11.0",
}


def test_engine_version_and_index(engine):
    system = engine.get("/system")
    assert system["Version"] == "1.13.0"
    assert system["DatabaseBackendPlugin"].endswith("libOrthancPostgreSQLIndex.so")
    assert system["DatabaseServerIdentifier"] == "pmc-imaging-engine"
    assert system["DicomAet"] == engine.aet
    # Extended find is what makes server-side sorting work; key-value stores
    # are where the worklists live.
    assert system["Capabilities"]["HasExtendedFind"] is True
    assert system["Capabilities"]["HasKeyValueStores"] is True


def test_configuration_is_the_committed_one(engine):
    system = engine.get("/system")
    assert system["IngestTranscoding"] == "1.2.840.10008.1.2.4.80"
    assert system["OverwriteInstancesMode"] == "Never"
    assert system["MaximumStorageSize"] == 0
    assert system["MaximumPatientCount"] == 0
    assert system["StorageCompression"] is False
    assert system["StoreMD5ForAttachments"] is True
    instance_tags = system["MainDicomTags"]["Instance"].split(";")
    # Rows, Columns, SOPClassUID, PixelSpacing, BitsAllocated: the extra
    # main tags that must be in place before the first study arrives.
    for tag in ("0028,0010", "0028,0011", "0008,0016", "0028,0030", "0028,0100"):
        assert tag in instance_tags


def test_exactly_the_plugins_the_configuration_names(engine):
    loaded = set(engine.get("/plugins")) - {"explorer.js"}
    assert loaded == set(EXPECTED_PLUGINS)
    for plugin, version in EXPECTED_PLUGINS.items():
        assert engine.get(f"/plugins/{plugin}")["Version"] == version, plugin


def test_rest_refuses_a_caller_without_credentials(engine):
    # Orthanc's own password list is off; the authorization plugin decides,
    # and an anonymous caller may do nothing at all.
    assert requests.get(engine.url + "/system", timeout=30).status_code == 403
    assert requests.post(engine.url + "/tools/find", json={"Level": "Study", "Query": {}},
                         timeout=30).status_code == 403


def test_rest_refuses_a_wrong_api_key(engine):
    wrong = {"api-key": "not-" + engine.api_key}
    assert requests.get(engine.url + "/system", headers=wrong, timeout=30).status_code == 403
    assert requests.get(engine.url + "/system", headers={"api-key": engine.api_key},
                        timeout=30).status_code == 200


def test_a_route_the_permission_table_does_not_name_is_refused(engine):
    # Even the platform's own service account cannot reach what the table
    # leaves out, such as the engine's Lua endpoint.
    r = engine.request("POST", "/tools/execute-script", data="print(1)")
    assert r.status_code == 403


# ---- the DICOM network -------------------------------------------------------

def test_anyone_may_echo(engine):
    # A technologist can test a link without ICT; an echo reveals nothing.
    assert engine.echo("ANY_SCU") == 0x0000


def test_unknown_modality_cannot_store(engine, run_id):
    study = synth.Study("cr", run_id, "ROGUE_SCU", scale=0.1)
    result = engine.store("ROGUE_SCU", study.datasets)
    assert result == REJECTED or all(s != 0x0000 for s in result), result
    assert engine.instance_id(study.instance_uids[0]) is None


def test_a_modality_must_call_this_engine_by_its_ae_title(engine, modalities, run_id):
    study = synth.Study("cr", run_id, "NX_DEFAULT", scale=0.1)
    assert engine.store("NX_DEFAULT", study.datasets, called="ORTHANC") == REJECTED
    assert engine.instance_id(study.instance_uids[0]) is None


def test_a_known_ae_title_from_another_address_cannot_store(engine, run_id):
    # Registered, but at an RFC 5737 documentation address instead of ours:
    # an AE title alone is not an identity.
    engine.register("elsewhere", "SYN_ELSEWHERE", "192.0.2.10", store=True)
    try:
        study = synth.Study("cr", run_id, "SYN_ELSEWHERE", scale=0.1)
        result = engine.store("SYN_ELSEWHERE", study.datasets)
        assert result == REJECTED or all(s != 0x0000 for s in result), result
        assert engine.instance_id(study.instance_uids[0]) is None
    finally:
        engine.request("DELETE", "/modalities/elsewhere")


def test_a_store_only_modality_cannot_search_the_archive(engine, modalities):
    query = Dataset()
    query.QueryRetrieveLevel = "STUDY"
    query.PatientID = "*"
    query.StudyInstanceUID = ""
    statuses, matches = engine.find_studies("NX_DEFAULT", query)
    assert matches == []
    assert statuses and statuses[-1] != 0x0000, statuses
