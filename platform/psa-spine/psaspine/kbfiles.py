"""Files on a knowledge article (051): the picture of the fix.

Kept the way a ticket's files are (027): the media type from the file's own
bytes, compressed where that helps, named by its hash, and every file
reviewed for patient information. The desk shows a file to anyone who may
read the knowledge base while it is PENDING or CLEARED; a requester on the
portal sees CLEARED only; a WITHHELD file is served to nobody. The store is
a folder of its own beside the attachment store (`PSA_KB_DIR`, else
`<attachments>-kb`), so the attachment store's verifier and purge, which
know only tickets, never take an article's file for an orphan.
"""
from __future__ import annotations

import gzip
import hashlib
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from . import attachments, db
from .attachments import MAX_BYTES, Refused, Removed, prepare, safe_name, sniff

DECISIONS = {"CLEAR": "CLEARED", "WITHHOLD": "WITHHELD"}


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def kb_dir(conn: sqlite3.Connection) -> Path:
    override = os.environ.get("PSA_KB_DIR")
    if override:
        return Path(override)
    root = attachments.store_dir(conn)
    return root.with_name(root.name + "-kb")


def _path(root: Path, sha: str) -> Path:
    return root / sha[:2] / sha[2:4] / sha


def get(conn: sqlite3.Connection, file_id: int):
    return conn.execute("SELECT * FROM kb_file WHERE file_id = ?", (file_id,)).fetchone()


def of_article(conn: sqlite3.Connection, article_id: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM kb_file WHERE article_id = ? AND removed_at IS NULL ORDER BY file_id",
                        (article_id,)).fetchall()


def visible(row, *, portal: bool) -> bool:
    """Who may be served the file: the desk anything not withheld, a
    requester only what a person cleared."""
    if row is None or row["removed_at"]:
        return False
    return row["review_status"] == "CLEARED" if portal else row["review_status"] != "WITHHELD"


def add(conn: sqlite3.Connection, article_id: str, data: bytes, filename: str, *, caption: str | None = None,
        actor: str, at: datetime) -> dict:
    """Keep a file on an article. Raises Refused for what the desk does not keep."""
    if conn.execute("SELECT 1 FROM kb_article WHERE article_id = ?", (article_id,)).fetchone() is None:
        raise LookupError(f"no article {article_id}")
    if not data:
        raise Refused("the file is empty")
    if len(data) > MAX_BYTES:
        raise Refused(f"files over {MAX_BYTES // (1024 * 1024)} MB are not kept")
    media_type = sniff(data, filename)
    stored, encoding, how = prepare(data, media_type)
    served = gzip.decompress(stored) if encoding == "GZIP" else stored
    sha = hashlib.sha256(served).hexdigest()
    path = _path(kb_dir(conn), sha)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        tmp.write_bytes(stored)
        os.replace(tmp, path)
        attachments.seal(path)
    stamp = _stamp(at)
    name = safe_name(filename)
    caption = " ".join((caption or "").split())[:200] or None
    cur = conn.execute(
        "INSERT INTO kb_file (article_id, filename, caption, media_type, size_received, size_stored, sha256, encoding,"
        " treatment, uploaded_by, uploaded_at, review_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,'PENDING')",
        (article_id, name, caption, media_type, len(data), len(stored), sha, encoding, how, actor, stamp))
    db.audit(conn, at=stamp, actor=actor, action="KB_FILE", subject_kind="kb_file", subject_id=str(cur.lastrowid),
             detail=f"added to {article_id}: {name} ({media_type}, {len(data)} B received, {len(stored)} B stored); awaiting review")
    return {"file_id": cur.lastrowid, "media_type": media_type, "sha256": sha, "size_received": len(data),
            "size_stored": len(stored), "treatment": how}


def read(conn: sqlite3.Connection, file_id: int) -> tuple[sqlite3.Row, bytes]:
    row = get(conn, file_id)
    if row is None:
        raise LookupError(f"no article file {file_id}")
    if row["removed_at"]:
        raise Removed(f"article file {file_id} was removed on {row['removed_at']}")
    stored = _path(kb_dir(conn), row["sha256"]).read_bytes()
    data = gzip.decompress(stored) if row["encoding"] == "GZIP" else stored
    if hashlib.sha256(data).hexdigest() != row["sha256"]:
        raise IOError(f"article file {file_id} does not match its hash; not served")
    return row, data


def review(conn: sqlite3.Connection, file_id: int, decision: str, *, actor: str, at: datetime):
    """CLEAR or WITHHOLD, by a person, once; a withheld file may be cleared
    again after a second look, and a cleared one withheld."""
    if decision not in DECISIONS:
        raise ValueError("a review is CLEAR or WITHHOLD")
    row = get(conn, file_id)
    if row is None or row["removed_at"]:
        raise LookupError(f"no article file {file_id}")
    stamp = _stamp(at)
    conn.execute("UPDATE kb_file SET review_status = ?, reviewed_by = ?, reviewed_at = ? WHERE file_id = ?",
                 (DECISIONS[decision], actor, stamp, file_id))
    db.audit(conn, at=stamp, actor=actor, action="KB_FILE", subject_kind="kb_file", subject_id=str(file_id),
             detail=f"{DECISIONS[decision].lower()} on {row['article_id']}: {row['filename']}")
    return get(conn, file_id)


def remove(conn: sqlite3.Connection, file_id: int, *, actor: str, at: datetime) -> bool:
    """Take a file off an article. The row stays with who and when; the bytes
    go only when no other live file on any article shares them."""
    row = get(conn, file_id)
    if row is None or row["removed_at"]:
        return False
    stamp = _stamp(at)
    conn.execute("UPDATE kb_file SET removed_at = ?, removed_by = ? WHERE file_id = ?", (stamp, actor, file_id))
    db.audit(conn, at=stamp, actor=actor, action="KB_FILE", subject_kind="kb_file", subject_id=str(file_id),
             detail=f"removed from {row['article_id']}: {row['filename']}")
    still = conn.execute("SELECT 1 FROM kb_file WHERE sha256 = ? AND removed_at IS NULL", (row["sha256"],)).fetchone()
    if still is None:
        path = _path(kb_dir(conn), row["sha256"])
        if path.exists():
            attachments.remove_sealed(path)
    return True


_PLACED = re.compile(r"\]\(file:(\d+)\)")


def unplaced(conn: sqlite3.Connection, article_id: str, body: str, *, portal: bool) -> list[sqlite3.Row]:
    """The article's pictures this reader may see that the text never places
    (Dada, 16 Oct 2026: images added to an article were on it but shown to
    nobody, because only a ![caption](file:N) in the text drew them). They
    are shown after the text, so a picture added is a picture seen."""
    placed = {int(n) for n in _PLACED.findall(body or "")}
    return [r for r in of_article(conn, article_id)
            if str(r["media_type"] or "").startswith("image/") and r["file_id"] not in placed
            and visible(r, portal=portal)]


def resolver(conn: sqlite3.Connection, article_id: str, *, portal: bool, base: str):
    """What ![caption](file:N) in the article's text turns into for this
    reader: the file's address, or nothing when it is not theirs to see."""
    rows = {r["file_id"]: r for r in of_article(conn, article_id)}

    def url(n: int):
        r = rows.get(n)
        return f"{base}{n}" if r is not None and visible(r, portal=portal) else None
    return url
