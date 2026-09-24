"""The engine's worklists (the Worklists plugin 0.9.2, database mode), kept
with the platform's service key."""
from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class Engine:
    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip("/")
        s = requests.Session()
        s.headers["api-key"] = api_key
        s.trust_env = False  # never through a proxy: the engine is on the engine network
        # Keep-alive, with the idempotent calls retried on a dropped connection
        # (the proof MEASURED an occasional drop). A create is made safe by the
        # caller instead: adopt what exists before creating.
        retry = Retry(total=3, connect=3, read=2, backoff_factor=0.3,
                      allowed_methods={"GET", "PUT", "DELETE"}, status_forcelist=())
        s.mount("http://", HTTPAdapter(max_retries=retry))
        self.http = s

    def get(self, path: str, **kw):
        r = self.http.get(self.url + path, timeout=60, **kw)
        r.raise_for_status()
        return r.json()

    def create_worklist(self, tags: dict) -> str:
        r = self.http.post(self.url + "/worklists/create", json={"Tags": tags}, timeout=60)
        r.raise_for_status()
        return r.json()["ID"]

    def update_worklist(self, wl_id: str, tags: dict) -> int:
        return self.http.put(f"{self.url}/worklists/{wl_id}", json={"Tags": tags}, timeout=60).status_code

    def delete_worklist(self, wl_id: str) -> int:
        return self.http.delete(f"{self.url}/worklists/{wl_id}", timeout=60).status_code

    def worklists_by_accession(self) -> dict[str, list[tuple[str, str]]]:
        """{accession: [(worklist id, console AE title)]} for every entry held."""
        held: dict[str, list[tuple[str, str]]] = {}
        for w in self.get("/worklists", params={"format": "Simplify"}):
            tags = w.get("Tags", w)
            step = (tags.get("ScheduledProcedureStepSequence") or [{}])[0]
            held.setdefault(tags.get("AccessionNumber", ""), []).append(
                (w["ID"], step.get("ScheduledStationAETitle", "")))
        return held
