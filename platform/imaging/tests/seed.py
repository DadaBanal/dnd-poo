"""Store synthetic studies for the browser tests and write their UIDs to /results/seed.json.

Run by ci/run.sh in the tests container:  python seed.py
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import synth
from conftest import MODALITIES, SENDER
from engine import REJECTED, Engine

# What the browser tests open: a cathlab run (cine), a CT series (a stack),
# a chest plate (shared with referrers), and an ultrasound run that arrived
# already JPEG-compressed.
KINDS = ["xa", "ct", "cr", "us-jpeg"]


def main() -> None:
    engine = Engine()
    here = engine.my_address()
    for name, aet in MODALITIES.items():
        engine.register(name, aet, here, store=True, worklist=True)
    run_id = "B" + uuid.uuid4().hex[:9].upper()
    seeded = {}
    for kind in KINDS:
        study = synth.Study(kind, run_id, SENDER[kind])
        statuses = engine.store(SENDER[kind], study.datasets)
        if statuses == REJECTED or any(s != 0x0000 for s in statuses):
            raise SystemExit(f"seeding {kind} failed: {statuses}")
        first = study.datasets[0]
        seeded[kind] = {
            "study": study.study_uid,
            "series": study.series_uid,
            "instances": len(study.datasets),
            "frames": int(getattr(first, "NumberOfFrames", 1)),
            "patient_id": study.patient_id,
        }
    # Share the chest plate with referrers (a label), so the browser tests can
    # show a referrer opening it and not the others.
    shared = engine.study_id(seeded["cr"]["study"])
    r = engine.request("PUT", f"/studies/{shared}/labels/referrer-shared")
    r.raise_for_status()
    seeded["cr"]["labels"] = ["referrer-shared"]
    seeded["cr"]["labelled_at_ms"] = int(time.time() * 1000)
    out = Path(os.environ.get("RESULTS_DIR", "/results")) / "seed.json"
    out.write_text(json.dumps(seeded, indent=2))
    print(f"seeded {', '.join(KINDS)} -> {out}")


if __name__ == "__main__":
    main()
