"""The connector's settings: site values from the environment, passwords from
Docker secrets. With no BizBox server set it idles, so the platform can run
before the view exists on DND-SQL01."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass


def secret(name: str) -> str:
    with open(os.path.join("/run/secrets", name), encoding="utf-8") as f:
        return f.read().strip()


@dataclass(frozen=True)
class Config:
    configured: bool
    bizbox_server: str
    bizbox_database: str
    bizbox_user: str
    bizbox_password: str
    bizbox_view: str
    bizbox_trust_server_cert: bool
    engine_url: str
    engine_api_key: str
    platform_db: str
    poll_seconds: float
    issuer_of_patient_id: str
    # BizBox section -> {"modality": "CT", "aets": ["console AE title", ...]}
    stations: dict


def load() -> Config:
    server = os.environ.get("PMC_BIZBOX_SERVER", "").strip()
    configured = bool(server)
    stations = json.loads(os.environ.get("PMC_ORDERS_STATIONS") or "{}")
    if configured and not stations:
        raise SystemExit("orders: PMC_ORDERS_STATIONS is not set (which console takes which section)")
    for section, station in stations.items():
        if not station.get("modality") or not station.get("aets"):
            raise SystemExit(f"orders: PMC_ORDERS_STATIONS[{section}] needs a modality and its consoles' AE titles")
    return Config(
        configured=configured,
        bizbox_server=server,
        bizbox_database=os.environ.get("PMC_BIZBOX_DATABASE", ""),
        bizbox_user=os.environ.get("PMC_BIZBOX_USER", ""),
        bizbox_password=secret("bizbox-password") if configured else "",
        bizbox_view=os.environ.get("PMC_BIZBOX_VIEW") or "dbo.v_pmc_imaging_orders",
        # On site the connector checks SQL Server's certificate; only a stand-in
        # with a self-signed one may skip that (the tests).
        bizbox_trust_server_cert=os.environ.get("PMC_BIZBOX_TRUST_SERVER_CERT", "no") == "yes",
        engine_url=os.environ.get("ENGINE_URL", "http://orthanc:8042"),
        engine_api_key=secret("svc-platform-api-key"),
        platform_db=(f"host={os.environ.get('PLATFORM_DB_HOST', 'pg-platform')} dbname=platform "
                     f"user=platform_orders password={secret('platform-orders-password')}"),
        poll_seconds=float(os.environ.get("POLL_SECONDS", "30")),
        issuer_of_patient_id=os.environ.get("PMC_ISSUER_OF_PATIENT_ID", "PMC"),
        stations=stations,
    )
