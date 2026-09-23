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
from datetime import datetime
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


class Refused(ValueError):
    """The file is not one the desk keeps."""


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
        actor: str, at: datetime, source: str = "DESK") -> dict:
    """Keep a file on a ticket. Returns the row's fields. Raises Refused."""
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
    cur = conn.execute(
        "INSERT INTO attachment (work_item_id, filename, media_type, size_received, size_stored,"
        " sha256, encoding, treatment, source, uploaded_by, uploaded_at, review_status)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,'PENDING')",
        (work_item_id, name, media_type, len(data), len(stored), sha, encoding, how, source,
         actor, stamp))
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
