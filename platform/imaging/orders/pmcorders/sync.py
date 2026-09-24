"""Keep the engine's worklists in step with BizBox: create, change, withdraw;
and mark an order performed once its study has arrived. Carried from the
research proof's poller."""
from __future__ import annotations

import json

from . import his, mapping


def sync_orders(cfg, conn, state, engine) -> dict:
    counts = {"created": 0, "updated": 0, "withdrawn": 0, "review": 0, "refused": 0, "unchanged": 0}
    since = state.cursor("orders")
    rows = his.fetch_changes(conn, cfg.bizbox_view, since)
    held = None  # the engine's entries, listed once a cycle, and only when a new order needs it
    for row in rows:
        order_no = row["order_no"]
        known = state.one("SELECT * FROM ris.order_map WHERE order_no = %s", (order_no,))
        if row["status"] == "CANCELLED":
            if known and known["worklist_ids"] and known["state"] == "SCHEDULED":
                codes = [engine.delete_worklist(w) for w in known["worklist_ids"]]
                state.q("UPDATE ris.order_map SET state = 'CANCELLED', worklist_ids = '[]', change_seq = %s, "
                        "updated_at = now() WHERE order_no = %s", (row["change_seq"], order_no))
                state.event("worklist-withdrawn", order_no, {"http": codes})
                counts["withdrawn"] += 1
            continue
        why = mapping.problem(row, cfg.stations)
        if why:
            state.event("order-refused", order_no, {"reason": why})
            counts["refused"] += 1
            continue
        entries = mapping.worklist_entries(row, cfg.stations, cfg.issuer_of_patient_id)
        digest = mapping.tags_hash(entries)
        first = entries[0]
        if not known:
            # A create whose answer was lost may still have happened (MEASURED
            # once in the proof). So adopt what the engine already holds for
            # this accession, remove any duplicate, and create only the rest.
            if held is None:
                held = engine.worklists_by_accession()
            have: dict[str, list[str]] = {}
            for wl_id, aet in held.get(first["AccessionNumber"], []):
                have.setdefault(aet, []).append(wl_id)
            ids, adopted = [], 0
            for tags in entries:
                found = have.get(tags["ScheduledProcedureStepSequence"][0]["ScheduledStationAETitle"], [])
                if found:
                    for extra in found[1:]:
                        engine.delete_worklist(extra)
                    engine.update_worklist(found[0], tags)
                    ids.append(found[0])
                    adopted += 1
                else:
                    ids.append(engine.create_worklist(tags))
            state.q("INSERT INTO ris.order_map (order_no, accession, patient_id, study_uid, worklist_ids, "
                    "tags_hash, change_seq, state) VALUES (%s, %s, %s, %s, %s, %s, %s, 'SCHEDULED')",
                    (order_no, first["AccessionNumber"], first["PatientID"], first["StudyInstanceUID"],
                     json.dumps(ids), digest, row["change_seq"]))
            state.event("worklist-created", order_no, {
                "worklists": ids, "adopted": adopted,
                "consoles": [t["ScheduledProcedureStepSequence"][0]["ScheduledStationAETitle"] for t in entries]})
            counts["created"] += 1
        elif known["tags_hash"] == digest:
            counts["unchanged"] += 1
        elif known["state"] == "SCHEDULED" and len(known["worklist_ids"]) == len(entries):
            codes = [engine.update_worklist(w, t) for w, t in zip(known["worklist_ids"], entries)]
            if all(c == 200 for c in codes):
                state.q("UPDATE ris.order_map SET tags_hash = %s, patient_id = %s, change_seq = %s, "
                        "updated_at = now() WHERE order_no = %s",
                        (digest, first["PatientID"], row["change_seq"], order_no))
                state.event("worklist-updated", order_no, {"worklists": known["worklist_ids"]})
                counts["updated"] += 1
            else:
                _needs_review(state, row, {"http": codes})
                counts["review"] += 1
        else:
            # The exam has happened (or the entry is gone): the change has to
            # reach the images, and that is a person's decision, never an
            # automatic rewrite.
            _needs_review(state, row, {"state": known["state"]})
            counts["review"] += 1
    if rows:
        state.set_cursor("orders", max(int(r["change_seq"]) for r in rows))
    return counts


def _needs_review(state, row, detail) -> None:
    state.q("UPDATE ris.order_map SET state = 'NEEDS_REVIEW', change_seq = %s, updated_at = now() "
            "WHERE order_no = %s", (row["change_seq"], row["order_no"]))
    state.event("order-changed-after-performed", row["order_no"], detail)


def follow_engine(state, engine) -> int:
    """A StableStudy whose StudyInstanceUID belongs to a scheduled order marks
    that order performed. (The engine itself removes its worklist entries.)"""
    since = state.cursor("engine_changes")
    if since == 0:
        # First start: begin at the end of the engine's feed.
        since = int(engine.get("/changes", params={"last": ""}).get("Last", 0))
    feed = engine.get("/changes", params={"since": since, "limit": 200})
    done = 0
    for change in feed.get("Changes", []):
        if change.get("ChangeType") != "StableStudy":
            continue
        uid = engine.get(f"/studies/{change['ID']}")["MainDicomTags"].get("StudyInstanceUID")
        for r in state.q("UPDATE ris.order_map SET state = 'PERFORMED', updated_at = now() "
                         "WHERE study_uid = %s AND state = 'SCHEDULED' RETURNING order_no", (uid,)):
            state.event("order-performed", r["order_no"], {"study": change["ID"]})
            done += 1
    state.set_cursor("engine_changes", int(feed.get("Last", since)))
    return done
