"""The engine as the tests see it: DICOM on 4242, REST and DICOMweb on 8042.

The tests reach it exactly as a modality or a viewer would, from their own
container on the engine network. Nothing is mocked.
"""

from __future__ import annotations

import json
import os
import re
import socket
import time
from io import BytesIO
from pathlib import Path
from typing import Callable, Iterable

import pydicom
import requests
from pydicom.dataset import Dataset
from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian
from pynetdicom import AE
from pynetdicom.sop_class import (
    ModalityWorklistInformationFind,
    StudyRootQueryRetrieveInformationModelFind,
    Verification,
)

REJECTED = "rejected"  # the association itself was refused


class Engine:
    def __init__(self) -> None:
        self.host = os.environ.get("ENGINE_HOST", "orthanc")
        self.aet = os.environ.get("ENGINE_AET", "PMC-IMAGING")
        self.dicom_port = int(os.environ.get("DICOM_PORT", "4242"))
        self.url = f"http://{self.host}:{os.environ.get('HTTP_PORT', '8042')}"
        secret = Path(os.environ.get("USERS_SECRET", "/run/secrets/orthanc-users.json"))
        users = json.loads(secret.read_text())["RegisteredUsers"]
        self.http = requests.Session()
        self.http.auth = next(iter(users.items()))

    # ---- REST ---------------------------------------------------------------
    def request(self, method: str, path: str, **kw) -> requests.Response:
        kw.setdefault("timeout", 120)
        return self.http.request(method, self.url + path, **kw)

    def get(self, path: str, **kw):
        r = self.request("GET", path, **kw)
        r.raise_for_status()
        return r.json()

    def text(self, path: str) -> str:
        r = self.request("GET", path)
        r.raise_for_status()
        return r.text

    def post(self, path: str, body=None, **kw):
        r = self.request("POST", path, json=body, **kw)
        r.raise_for_status()
        return r.json() if r.content else None

    def lookup(self, uid: str) -> list[dict]:
        r = self.request("POST", "/tools/lookup", data=uid)
        r.raise_for_status()
        return r.json()

    def instance_id(self, sop_uid: str) -> str | None:
        hits = [h for h in self.lookup(sop_uid) if h["Type"] == "Instance"]
        return hits[0]["ID"] if hits else None

    def study_id(self, study_uid: str) -> str | None:
        hits = [h for h in self.lookup(study_uid) if h["Type"] == "Study"]
        return hits[0]["ID"] if hits else None

    def stored_file(self, orthanc_id: str) -> Dataset:
        r = self.request("GET", f"/instances/{orthanc_id}/file")
        r.raise_for_status()
        return pydicom.dcmread(BytesIO(r.content))

    # ---- modalities, registered in the engine's database -------------------
    def my_address(self) -> str:
        """This container's address as the engine sees it (UDP connect sends nothing)."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect((self.host, self.dicom_port))
            return s.getsockname()[0]

    def register(self, name: str, aet: str, host: str, *, store: bool = False,
                 worklist: bool = False, find: bool = False) -> None:
        r = self.request("PUT", f"/modalities/{name}", json={
            "AET": aet, "Host": host, "Port": 104, "Manufacturer": "Generic",
            "AllowEcho": True, "AllowStore": store, "AllowFindWorklist": worklist,
            "AllowFind": find, "AllowGet": False, "AllowMove": False,
            "AllowStorageCommitment": False,
        })
        r.raise_for_status()

    # ---- DIMSE, as a modality ----------------------------------------------
    def _associate(self, calling: str, contexts: Iterable[tuple[str, list[str]]], called: str | None):
        ae = AE(ae_title=calling)
        ae.acse_timeout = ae.dimse_timeout = ae.network_timeout = 60
        for sop_class, syntaxes in contexts:
            ae.add_requested_context(sop_class, syntaxes)
        return ae.associate(self.host, self.dicom_port, ae_title=called or self.aet)

    def echo(self, calling: str, called: str | None = None):
        assoc = self._associate(calling, [(Verification, [ExplicitVRLittleEndian])], called)
        if not assoc.is_established:
            return REJECTED
        try:
            status = assoc.send_c_echo()
            return status.Status if "Status" in status else None
        finally:
            assoc.release()

    def store(self, calling: str, datasets: list[Dataset], called: str | None = None):
        """C-STORE every dataset in one association. Returns one status per dataset."""
        contexts = {}
        for ds in datasets:
            syntax = str(ds.file_meta.TransferSyntaxUID)
            wanted = [syntax] if ds.file_meta.TransferSyntaxUID.is_compressed else [
                ExplicitVRLittleEndian, ImplicitVRLittleEndian]
            contexts.setdefault(str(ds.SOPClassUID), wanted)
        assoc = self._associate(calling, contexts.items(), called)
        if not assoc.is_established:
            return REJECTED
        try:
            out = []
            for ds in datasets:
                status = assoc.send_c_store(ds)
                out.append(status.Status if "Status" in status else None)
            return out
        finally:
            if assoc.is_established:
                assoc.release()

    def find_worklist(self, calling: str, query: Dataset) -> tuple[list[int], list[Dataset]]:
        return self._find(calling, query, ModalityWorklistInformationFind)

    def find_studies(self, calling: str, query: Dataset) -> tuple[list[int], list[Dataset]]:
        return self._find(calling, query, StudyRootQueryRetrieveInformationModelFind)

    def _find(self, calling: str, query: Dataset, model) -> tuple[list[int], list[Dataset]]:
        assoc = self._associate(calling, [(model, [ExplicitVRLittleEndian])], None)
        if not assoc.is_established:
            return [REJECTED], []
        statuses, matches = [], []
        try:
            for status, identifier in assoc.send_c_find(query, model):
                statuses.append(status.Status if status and "Status" in status else None)
                if identifier is not None and status and status.Status in (0xFF00, 0xFF01):
                    matches.append(identifier)
        finally:
            if assoc.is_established:
                assoc.release()
        return statuses, matches


def wait_for(predicate: Callable[[], object], timeout: float, what: str, interval: float = 1.0):
    """Poll until predicate() is truthy; return its value or fail with what we waited for."""
    deadline = time.monotonic() + timeout
    while True:
        value = predicate()
        if value:
            return value
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out after {timeout:.0f}s waiting for {what}")
        time.sleep(interval)


def multipart(response: requests.Response) -> list[tuple[dict, bytes]]:
    """Split a multipart/related DICOMweb answer into (headers, body) parts."""
    match = re.search(r'boundary="?([^";]+)"?', response.headers["Content-Type"])
    assert match, f"no boundary in {response.headers['Content-Type']}"
    delimiter = b"--" + match.group(1).encode()
    parts = []
    for chunk in response.content.split(delimiter)[1:]:
        if chunk.startswith(b"--"):
            break
        head, _, body = chunk.lstrip(b"\r\n").partition(b"\r\n\r\n")
        headers = {}
        for line in head.decode("latin-1").split("\r\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        parts.append((headers, body[:-2] if body.endswith(b"\r\n") else body))
    return parts
