"""Run the connector: poll BizBox and the engine, and serve /health and
/metrics on :8080 for compose and Prometheus. It never crashes on BizBox or
the engine being down: it says so in its metrics and tries again."""
from __future__ import annotations

import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config, his, sync
from .engine import Engine
from .state import State

log = logging.getLogger("orders")
OUTCOMES = ("created", "updated", "withdrawn", "review", "refused", "performed")


class Health:
    def __init__(self, configured: bool):
        self.configured = configured
        self.last_success = 0.0
        self.totals = dict.fromkeys(OUTCOMES, 0)
        self.needs_review = 0

    def metrics(self) -> str:
        lines = [
            "# HELP pmc_orders_configured Whether the connector has a BizBox server to read.",
            "# TYPE pmc_orders_configured gauge",
            f"pmc_orders_configured {int(self.configured)}",
            "# HELP pmc_orders_last_sync_timestamp_seconds When BizBox and the engine were last both read.",
            "# TYPE pmc_orders_last_sync_timestamp_seconds gauge",
        ]
        if self.last_success:
            lines.append(f"pmc_orders_last_sync_timestamp_seconds {self.last_success}")
        lines += ["# HELP pmc_orders_synced_total What the connector did, since it started.",
                  "# TYPE pmc_orders_synced_total counter"]
        lines += [f'pmc_orders_synced_total{{outcome="{k}"}} {v}' for k, v in self.totals.items()]
        lines += ["# HELP pmc_orders_needs_review Orders changed in BizBox after their exam, waiting for a person.",
                  "# TYPE pmc_orders_needs_review gauge", f"pmc_orders_needs_review {self.needs_review}"]
        return "\n".join(lines) + "\n"


def serve(health: Health) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = health.metrics() if self.path == "/metrics" else "ok\n" if self.path == "/health" else None
            self.send_response(200 if body else 404)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            self.wfile.write((body or "").encode())

        def log_message(self, *args):
            pass

    threading.Thread(target=ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever, daemon=True).start()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    cfg = config.load()
    health = Health(cfg.configured)
    serve(health)
    if not cfg.configured:
        log.info("no BizBox server set (PMC_BIZBOX_SERVER): idle")
        threading.Event().wait()
    state = State(cfg.platform_db)
    engine = Engine(cfg.engine_url, cfg.engine_api_key)
    conn = None
    while True:
        try:
            if conn is None:
                conn = his.connect(cfg)
            counts = sync.sync_orders(cfg, conn, state, engine)
            counts["performed"] = sync.follow_engine(state, engine)
            for k in OUTCOMES:
                health.totals[k] += counts.get(k, 0)
            health.needs_review = state.one(
                "SELECT count(*) AS n FROM ris.order_map WHERE state = 'NEEDS_REVIEW'")["n"]
            health.last_success = time.time()
            if any(counts.get(k) for k in OUTCOMES):
                log.info("sync %s", {k: v for k, v in counts.items() if v})
        except Exception as exc:  # BizBox or the engine is down: say so, and try again
            log.warning("sync failed: %s", exc)
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass
            conn = None
        time.sleep(cfg.poll_seconds)


main()
