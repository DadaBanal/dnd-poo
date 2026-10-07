"""Attachments: files on a ticket, stored outside the database, compressed properly.

**Where.** Files live in a directory beside the database (`<database>.attachments/`,
or PSA_ATTACHMENT_DIR), named by the sha256 of what is stored: the same file
uploaded twice is kept once, and a file that no longer matches its name is
detectably corrupt. The database holds only the row that describes it.

**What is allowed** is decided by the file's first bytes, never by its name or
the type the browser claimed: images, PDF, plain text and logs, CSV, Office
documents, email. Programs and scripts are refused, and so is anything that
cannot be identified. A 10 MB limit per file.

**Compression, by kind, all lossless:**

  * PNG (most screenshots): the image data is re-deflated at the highest level
    and written back as one IDAT; every pixel is identical, checked by
    decompressing both. Text and time chunks are dropped (they carry paths,
    user names and software versions); colour chunks are kept.
  * JPEG (photos from phones): EXIF, XMP, IPTC and comment segments are removed (they
    carry GPS positions, device serials and dates). The compressed image data is
    not touched, so there is no quality loss.
  * Text, logs, CSV, email and uncompressed bitmaps: gzip at level 9, kept only
    when it saves at least a tenth.
  * Formats that are already compressed (PDF, GIF, WebP, Office documents):
    stored as they are, because compressing them again saves nothing.

**Patient data (§6.1).** Every file starts PENDING review. A board member
reviews it: CLEARED, or WITHHELD because it shows patient information. A
WITHHELD file is never served again except to the board's administrator, and
every read of a file on a restricted board is audited like any other read.

**Keeping the store whole, and not for ever (028).** `usage` says what is held,
as the database counts it and as the disk does. `verify` says whether every
live row has its file and every file has a row. `purge` removes files under a
retention rule -- a withheld file so many days after its review, any file so
many days after its ticket closed -- with the periods given by the operator,
never defaulted here (§6.1 point 3: retention is designed, not inherited). It
previews unless told to apply, refuses to run over a store that is not whole,
and leaves the row behind with `purged_at` set, so the ticket's history still
says what was sent and by whom.

Standard library only.
"""
from __future__ import annotations

import gzip
import hashlib
import os
import re
import sqlite3
import struct
import zlib
from datetime import datetime, timedelta
from pathlib import Path

from . import db

MAX_BYTES = 10 * 1024 * 1024
# A PNG whose image data inflates past this is left as sent rather than
# re-deflated: a small file can decompress to gigabytes.
PNG_INFLATE_LIMIT = 128 * 1024 * 1024
PNG_SIG = b"\x89PNG\r\n\x1a\n"
# Chunks kept when a PNG is rewritten: the image, its palette and transparency,
# and colour management. Everything else (tEXt, zTXt, iTXt, tIME, eXIf, ...) goes.
PNG_KEEP = {b"IHDR", b"PLTE", b"tRNS", b"gAMA", b"cHRM", b"sRGB", b"iCCP", b"sBIT",
            b"pHYs", b"IDAT", b"IEND"}
REVIEW = ("PENDING", "CLEARED", "WITHHELD")
# A file on disk with no row is an orphan only once it is older than this: the
# desk writes the file before it commits the row, and a purge that walked the
# disk in that gap would otherwise delete a file whose row is a moment away.
ORPHAN_GRACE_SECONDS = 3600


class Refused(ValueError):
    """The file is not one the desk keeps."""


class Removed(LookupError):
    """The file was removed under retention; its row remains."""


# ------------------------------------------------------------ what is it

def sniff(data: bytes, filename: str = "") -> str:
    """The media type from the file's own first bytes. Refuses what it cannot name."""
    head = data[:16]
    if head.startswith(PNG_SIG):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if head[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if head[:2] == b"BM":
        return "image/bmp"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head[:2] == b"MZ" or head[:4] == b"\x7fELF" or head[:4] in (b"\xca\xfe\xba\xbe",
                                                                     b"\xcf\xfa\xed\xfe"):
        raise Refused("programs are not kept on tickets")
    if head.startswith(b"PK\x03\x04"):
        ext = Path(filename).suffix.lower()
        office = {".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                  ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                  ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}
        if ext in office and b"[Content_Types].xml" in data[:4096]:
            return office[ext]
        raise Refused("zip archives are not kept on tickets: attach the files inside")
    unknown = Refused("the desk cannot tell what this file is, so it does not keep it")
    try:
        if head[:2] in (b"\xff\xfe", b"\xfe\xff"):   # UTF-16 only with its byte-order mark:
            text = data.decode("utf-16")           # without one, any even-length binary "decodes"
        else:
            text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise unknown
    if "\x00" in text[:4096]:
        raise unknown
    lowered = text[:2048].lower()
    if re.search(r"<\s*(script|html|svg|iframe)\b", lowered) or lowered.startswith("#!"):
        raise Refused("web pages and scripts are not kept on tickets")
    ext = Path(filename).suffix.lower()
    if ext in (".ps1", ".bat", ".cmd", ".vbs", ".js", ".sh", ".hta", ".reg", ".lnk"):
        raise Refused("scripts are not kept on tickets")
    if ext == ".eml" or re.match(r"(?s)^(received|from|return-path|message-id|mime-version):",
                                 lowered):
        return "message/rfc822"
    if ext == ".csv":
        return "text/csv"
    return "text/plain"


COMPRESSIBLE = {"text/plain", "text/csv", "message/rfc822", "image/bmp"}


# ------------------------------------------------------------ compression

def _png_chunks(data: bytes):
    pos = len(PNG_SIG)
    while pos + 8 <= len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if len(body) != length:
            raise ValueError("truncated PNG")
        yield kind, body
        pos += 12 + length
        if kind == b"IEND":
            return
    raise ValueError("PNG has no IEND")


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))


def optimise_png(data: bytes) -> bytes:
    """Re-deflate the image data at level 9 and drop metadata chunks. Lossless:
    the decompressed image data is compared byte for byte before anything is
    kept. Returns the input unchanged if it cannot improve on it."""
    try:
        chunks = list(_png_chunks(data))
    except (ValueError, struct.error):
        return data
    if any(kind == b"acTL" for kind, _ in chunks):
        return data                              # animated: frames live outside IDAT
    inflater = zlib.decompressobj()
    try:
        raw = inflater.decompress(b"".join(body for kind, body in chunks if kind == b"IDAT"),
                                  PNG_INFLATE_LIMIT)
    except zlib.error:
        return data
    if inflater.unconsumed_tail or not inflater.eof:
        return data
    packed = zlib.compress(raw, 9)
    if zlib.decompress(packed) != raw:          # never keep what cannot be proved identical
        return data
    out = [PNG_SIG]
    idat_written = False
    for kind, body in chunks:
        if kind == b"IDAT":
            if not idat_written:
                out.append(_chunk(b"IDAT", packed))
                idat_written = True
        elif kind in PNG_KEEP:
            out.append(_chunk(kind, body))
    new = b"".join(out)
    return new if len(new) < len(data) else data


def strip_jpeg(data: bytes) -> bytes:
    """Remove EXIF, XMP, IPTC and comment segments (APP1, APP13, COM). The scan data after
    SOS is copied untouched, so the picture is bit for bit the same."""
    if not data.startswith(b"\xff\xd8"):
        return data
    out = [b"\xff\xd8"]
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            return data                       # not a marker where one must be: leave it alone
        marker = data[pos + 1]
        if marker == 0xDA:                    # SOS: the image itself, to the end
            out.append(data[pos:])
            return b"".join(out)
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            out.append(data[pos:pos + 2])
            pos += 2
            continue
        (length,) = struct.unpack(">H", data[pos + 2:pos + 4])
        segment = data[pos:pos + 2 + length]
        if marker not in (0xE1, 0xED, 0xFE):  # APP1 EXIF/XMP, APP13 IPTC, COM comment
            out.append(segment)
        pos += 2 + length
    return data


def prepare(data: bytes, media_type: str) -> tuple[bytes, str, str]:
    """(bytes to store, encoding, what was done). Encoding is IDENTITY or GZIP:
    what the stored bytes need before they are the file served."""
    if media_type == "image/png":
        slim = optimise_png(data)
        return slim, "IDENTITY", "png re-deflated, metadata dropped" if slim != data else "png as sent"
    if media_type == "image/jpeg":
        slim = strip_jpeg(data)
        return slim, "IDENTITY", "jpeg metadata removed" if slim != data else "jpeg as sent"
    if media_type in COMPRESSIBLE:
        packed = gzip.compress(data, compresslevel=9, mtime=0)
        if len(packed) <= 0.9 * len(data):
            return packed, "GZIP", "gzip level 9"
    return data, "IDENTITY", "already compressed; stored as sent"


# ------------------------------------------------------------ storage

def store_dir(conn: sqlite3.Connection) -> Path:
    override = os.environ.get("PSA_ATTACHMENT_DIR")
    if override:
        return Path(override)
    if getattr(conn, "backend", "sqlite") != "sqlite":
        raise RuntimeError("a SQL Server desk keeps its files on a folder it is told about; "
                           "set PSA_ATTACHMENT_DIR")
    main = next((r[2] for r in conn.execute("PRAGMA database_list") if r[1] == "main"), "")
    if not main:
        raise RuntimeError("an in-memory database has nowhere to keep files; "
                           "set PSA_ATTACHMENT_DIR")
    return Path(main + ".attachments")


def _path(root: Path, sha: str) -> Path:
    return root / sha[:2] / sha[2:4] / sha


def safe_name(filename: str) -> str:
    name = Path((filename or "").replace("\\", "/")).name
    name = re.sub(r"[^\w.\- ()]+", "_", name).strip(" .") or "attachment"
    return name[:120]


def add(conn: sqlite3.Connection, work_item_id: str, data: bytes, filename: str, *,
        actor: str, at: datetime, source: str = "DESK", content_id: str | None = None) -> dict:
    """Keep a file on a ticket. Returns the row's fields. Raises Refused.

    `content_id` is the name an email's HTML calls this file by (066), so the
    note can show the picture where the sender put it."""
    from .board import _event, touch
    if not data:
        raise Refused("the file is empty")
    if len(data) > MAX_BYTES:
        raise Refused(f"files over {MAX_BYTES // (1024 * 1024)} MB are not kept")
    media_type = sniff(data, filename)
    stored, encoding, how = prepare(data, media_type)
    served = gzip.decompress(stored) if encoding == "GZIP" else stored
    sha = hashlib.sha256(served).hexdigest()
    root = store_dir(conn)
    path = _path(root, sha)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        tmp.write_bytes(stored)
        os.replace(tmp, path)
    stamp = at.isoformat(sep=" ", timespec="minutes")
    name = safe_name(filename)
    cid = (content_id or "").strip().strip("<>").strip()[:400] or None
    cur = conn.execute(
        "INSERT INTO attachment (work_item_id, filename, media_type, size_received, size_stored,"
        " sha256, encoding, treatment, source, uploaded_by, uploaded_at, review_status, content_id)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,'PENDING',?)",
        (work_item_id, name, media_type, len(data), len(stored), sha, encoding, how, source,
         actor, stamp, cid))
    _event(conn, work_item_id, stamp, "ATTACHMENT", actor,
           f"file attached: {name} ({_kb(len(data))} received, {_kb(len(stored))} stored); "
           "awaiting review for patient information")
    touch(conn, work_item_id, at)
    return {"attachment_id": cur.lastrowid, "media_type": media_type, "sha256": sha,
            "size_received": len(data), "size_stored": len(stored), "treatment": how}


def read(conn: sqlite3.Connection, attachment_id: int) -> tuple[sqlite3.Row, bytes]:
    """The row and the file's bytes as served, checked against their hash."""
    row = conn.execute("SELECT * FROM attachment WHERE attachment_id = ?",
                       (attachment_id,)).fetchone()
    if row is None:
        raise LookupError(f"no attachment {attachment_id}")
    if row["purged_at"]:
        raise Removed(f"attachment {attachment_id} was removed under retention on "
                      f"{row['purged_at']}")
    stored = _path(store_dir(conn), row["sha256"]).read_bytes()
    data = gzip.decompress(stored) if row["encoding"] == "GZIP" else stored
    if hashlib.sha256(data).hexdigest() != row["sha256"]:
        raise IOError(f"attachment {attachment_id} does not match its hash; not served")
    return row, data


def review(conn: sqlite3.Connection, attachment_id: int, decision: str, *, actor: str,
           at: datetime) -> str:
    """CLEARED or WITHHELD. Returns the ticket. A file withheld for patient
    information is flagged on the ticket as a PHI finding."""
    from .board import _event
    if decision not in ("CLEARED", "WITHHELD"):
        raise ValueError(f"a review is CLEARED or WITHHELD, not {decision!r}")
    row = conn.execute("SELECT * FROM attachment WHERE attachment_id = ?",
                       (attachment_id,)).fetchone()
    if row is None:
        raise LookupError(f"no attachment {attachment_id}")
    if row["purged_at"]:
        raise Removed(f"attachment {attachment_id} was removed under retention; "
                      "there is nothing left to review")
    stamp = at.isoformat(sep=" ", timespec="minutes")
    conn.execute("UPDATE attachment SET review_status = ?, reviewed_by = ?, reviewed_at = ?"
                 " WHERE attachment_id = ?", (decision, actor, stamp, attachment_id))
    _event(conn, row["work_item_id"], stamp, "ATTACHMENT", actor,
           f"file {row['filename']} {'cleared' if decision == 'CLEARED' else 'withheld: shows patient information'}")
    if decision == "WITHHELD":
        conn.execute("INSERT INTO data_quality (run_id, subject_kind, subject_id, code, detail,"
                     " severity) VALUES (?,?,?,?,?,?)",
                     ("review", "ticket", row["work_item_id"], "PHI_IN_ATTACHMENT",
                      f"attachment {attachment_id} withheld on review by {actor}", "WARN"))
        db.audit(conn, at=stamp, actor=actor, action="ATTACHMENT_WITHHELD",
                 subject_kind="attachment", subject_id=str(attachment_id))
    return row["work_item_id"]


def _kb(n: int) -> str:
    return f"{n / 1024:.0f} KB" if n >= 1024 else f"{n} B"


# ------------------------------------------------------------ keeping it whole

def _files_on_disk(root: Path) -> dict[str, Path]:
    """Every stored file by its name (the sha), .part leftovers excluded."""
    if not root.is_dir():
        return {}
    return {p.name: p for p in root.rglob("*") if p.is_file() and not p.name.endswith(".part")}


def usage(conn: sqlite3.Connection) -> dict:
    """What the store holds: by month and board as the database counts it, and
    on disk as the file system does. The two differ by design -- the same file
    on two tickets is one file on disk -- so both are reported."""
    rows = [dict(r) for r in conn.execute(
        "SELECT substr(a.uploaded_at, 1, 7) AS month, t.board_id, COUNT(*) AS files,"
        "       SUM(a.size_received) AS received,"
        "       SUM(CASE WHEN a.purged_at IS NULL THEN a.size_stored ELSE 0 END) AS stored,"
        "       SUM(a.review_status = 'PENDING' AND a.purged_at IS NULL) AS pending,"
        "       SUM(a.review_status = 'WITHHELD' AND a.purged_at IS NULL) AS withheld,"
        "       SUM(a.purged_at IS NOT NULL) AS purged"
        "  FROM attachment a JOIN ticket t ON t.work_item_id = a.work_item_id"
        " GROUP BY substr(a.uploaded_at, 1, 7), t.board_id ORDER BY substr(a.uploaded_at, 1, 7), t.board_id")]
    totals = {k: sum(r[k] for r in rows) for k in ("files", "received", "stored", "pending",
                                                    "withheld", "purged")}
    totals["live"] = totals["files"] - totals["purged"]
    totals["distinct_live"] = conn.execute(
        "SELECT COUNT(DISTINCT sha256) FROM attachment WHERE purged_at IS NULL").fetchone()[0]
    root = store_dir(conn)
    on_disk = _files_on_disk(root)
    return {"store": str(root), "rows": rows, "totals": totals,
            "disk": {"files": len(on_disk), "bytes": sum(p.stat().st_size for p in on_disk.values())}}


def verify(conn: sqlite3.Connection, *, check_hashes: bool = False,
           now: float | None = None) -> dict:
    """Is the store whole? `missing`: live rows whose file is not there.
    `orphans`: files no live row points at (a purge that stopped half way, or a
    row that was rolled back), once they are past the grace period.
    `mismatched`: with check_hashes, files that no longer hash to their name."""
    import time
    root = store_dir(conn)
    live = {r["sha256"]: r["encoding"] for r in conn.execute(
        "SELECT DISTINCT sha256, encoding FROM attachment WHERE purged_at IS NULL")}
    # 072: a picture sent in a chat is kept in the same store by its hash. It is
    # live too, so a purge never takes it as an orphan.
    from . import db as _db
    if _db.table_exists(conn, "chat_file"):
        for r in conn.execute("SELECT DISTINCT sha256, encoding FROM chat_file"):
            live.setdefault(r["sha256"], r["encoding"])
    present = _files_on_disk(root)
    now = time.time() if now is None else now
    orphans, recent = [], 0
    for sha, path in present.items():
        if sha in live:
            continue
        if now - path.stat().st_mtime < ORPHAN_GRACE_SECONDS:
            recent += 1
        else:
            orphans.append(sha)
    partial = sum(1 for p in root.rglob("*.part") if p.is_file()) if root.is_dir() else 0
    mismatched = []
    if check_hashes:
        for sha, encoding in live.items():
            if sha not in present:
                continue
            try:
                data = present[sha].read_bytes()
                if encoding == "GZIP":
                    data = gzip.decompress(data)
            except (OSError, gzip.BadGzipFile, EOFError, zlib.error):
                mismatched.append(sha)
                continue
            if hashlib.sha256(data).hexdigest() != sha:
                mismatched.append(sha)
    return {"store": str(root), "store_exists": root.is_dir(), "live": len(live),
            "present": len(present), "missing": sorted(set(live) - set(present)),
            "orphans": sorted(orphans), "recent_unindexed": recent, "partial": partial,
            "mismatched": sorted(mismatched), "checked_hashes": check_hashes}


def record_missing(conn: sqlite3.Connection, shas: list[str], *, actor: str,
                   at: datetime) -> int:
    """Settle rows whose file is gone: mark them purged with reason MISSING, so
    the ticket says the file is not there rather than serving an error, and so
    retention can run again. An operator's decision, audited; never automatic."""
    from .board import _event
    if not shas:
        return 0
    stamp = at.isoformat(sep=" ", timespec="minutes")
    rows = conn.execute(
        "SELECT attachment_id, work_item_id, filename FROM attachment WHERE purged_at IS NULL"
        " AND sha256 IN (%s)" % ",".join("?" * len(shas)), shas).fetchall()
    for r in rows:
        conn.execute("UPDATE attachment SET purged_at = ?, purge_reason = 'MISSING'"
                     " WHERE attachment_id = ?", (stamp, r["attachment_id"]))
        _event(conn, r["work_item_id"], stamp, "ATTACHMENT", actor,
               f"file {r['filename']} is missing from the store; recorded as gone")
    db.audit(conn, at=stamp, actor=actor, action="ATTACHMENT_MISSING",
             subject_kind="attachment_store", detail=f"{len(rows)} row(s) recorded as missing")
    return len(rows)


def purge(conn: sqlite3.Connection, *, at: datetime, withheld_days: int, closed_days: int,
          apply: bool = False, actor: str = "retention") -> dict:
    """Remove files under the retention rule. Previews unless `apply`.

    Due: a WITHHELD file `withheld_days` after its review; any file
    `closed_days` after its ticket closed (a reopened ticket has no closed_at,
    so its files stay). The row is kept with purged_at and the reason; the
    ticket gets an event. The bytes go only when no live row still points at
    them -- the same file on another open ticket keeps them.

    Refuses to run over a store that is not whole: a data drive that is not
    mounted looks like every file missing, and a purge that marked those rows
    would delete the files as orphans the day the drive came back.

    With `apply`, the rows are committed BEFORE any file is deleted, so a stop
    between the two leaves orphans (which the next run removes) and never a
    live row with no file.
    """
    if withheld_days < 1 or closed_days < 1:
        raise ValueError("retention periods are whole days, at least 1")
    root = store_dir(conn)
    check = verify(conn)
    if check["live"] and not check["store_exists"]:
        raise RuntimeError(f"the attachment store {root} is not there; nothing is purged "
                           "until it is back")
    if check["missing"]:
        raise RuntimeError(f"{len(check['missing'])} live file(s) are missing from the store;"
                           " run attachments-verify and settle that before purging")
    stamp = at.isoformat(sep=" ", timespec="minutes")
    withheld_before = (at - timedelta(days=withheld_days)).isoformat(sep=" ", timespec="minutes")
    closed_before = (at - timedelta(days=closed_days)).isoformat(sep=" ", timespec="minutes")
    due = conn.execute(
        "SELECT a.attachment_id, a.work_item_id, a.sha256, a.filename, a.size_stored, t.board_id,"
        "       CASE WHEN a.review_status = 'WITHHELD' AND a.reviewed_at <= ? THEN 'WITHHELD'"
        "            ELSE 'CLOSED' END AS reason"
        "  FROM attachment a JOIN ticket t ON t.work_item_id = a.work_item_id"
        " WHERE a.purged_at IS NULL"
        "   AND ((a.review_status = 'WITHHELD' AND a.reviewed_at <= ?)"
        "        OR (t.closed_at IS NOT NULL AND t.closed_at <= ?))"
        " ORDER BY a.attachment_id", (withheld_before, withheld_before, closed_before)).fetchall()

    by_reason: dict[str, int] = {"WITHHELD": 0, "CLOSED": 0}
    by_board: dict[str, int] = {}
    tickets: dict[str, int] = {}
    for r in due:
        by_reason[r["reason"]] += 1
        by_board[r["board_id"]] = by_board.get(r["board_id"], 0) + 1
        tickets[r["work_item_id"]] = tickets.get(r["work_item_id"], 0) + 1
    # Bytes that would go: files no live row would still point at afterwards.
    due_ids = {r["attachment_id"] for r in due}
    still_live = {r[0] for r in conn.execute(
        "SELECT sha256 FROM attachment WHERE purged_at IS NULL AND attachment_id NOT IN (%s)"
        % (",".join("?" * len(due_ids)) or "NULL"), list(due_ids))}
    from . import db as _db
    if _db.table_exists(conn, "chat_file"):          # 072: the same bytes kept for a chat stay
        still_live |= {r[0] for r in conn.execute("SELECT sha256 FROM chat_file")}
    freeable = {r["sha256"]: r["size_stored"] for r in due if r["sha256"] not in still_live}
    plan = {"applied": False, "due": len(due), "by_reason": by_reason, "by_board": by_board,
            "tickets": tickets, "files_to_free": len(freeable),
            "bytes_to_free": sum(freeable.values()), "orphans": len(check["orphans"]),
            "files_removed": 0, "orphans_removed": 0, "bytes_freed": 0,
            "withheld_before": withheld_before, "closed_before": closed_before}
    if not apply:
        return plan

    from .board import _event
    for r in due:
        conn.execute("UPDATE attachment SET purged_at = ?, purge_reason = ? WHERE attachment_id = ?",
                     (stamp, r["reason"], r["attachment_id"]))
        why = (f"{withheld_days} days after it was withheld" if r["reason"] == "WITHHELD"
               else f"{closed_days} days after the ticket closed")
        _event(conn, r["work_item_id"], stamp, "ATTACHMENT", actor,
               f"file {r['filename']} removed under retention: {why}")
    db.audit(conn, at=stamp, actor=actor, action="ATTACHMENT_PURGE", subject_kind="attachment_store",
             detail=f"{len(due)} row(s): {by_reason['WITHHELD']} withheld, {by_reason['CLOSED']} on "
                    f"closed tickets; periods {withheld_days}/{closed_days} days")
    conn.commit()                        # rows first: durable before any byte goes

    gone = [r[0] for r in conn.execute(
        "SELECT sha256 FROM attachment GROUP BY sha256 HAVING SUM(purged_at IS NULL) = 0")]
    for sha in gone + check["orphans"]:
        path = _path(root, sha)
        if not path.exists():
            continue
        size = path.stat().st_size
        path.unlink()
        plan["bytes_freed"] += size
        if sha in check["orphans"]:
            plan["orphans_removed"] += 1
        else:
            plan["files_removed"] += 1
        for parent in (path.parent, path.parent.parent):
            try:
                parent.rmdir()               # only when empty; otherwise it stays
            except OSError:
                break
    plan["applied"] = True
    return plan


def by_content_id(conn: sqlite3.Connection, work_item_id: str) -> dict:
    """The ticket's files an email's HTML can name, by Content-ID, lower case:
    each with its id, name, review state and whether it was purged. A picture
    the note names that is not here was a signature logo intake did not keep
    (INLINE_LOGO_BYTES), or came on a ticket stored before 066."""
    return {str(r["content_id"]).lower(): dict(r) for r in conn.execute(
        "SELECT attachment_id, filename, media_type, review_status, purged_at, content_id FROM attachment"
        " WHERE work_item_id = ? AND content_id IS NOT NULL", (work_item_id,))}
