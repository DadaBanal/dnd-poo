"""Files on a ticket: the card, the upload, the download and the review.

Who sees what (§6.1). Every file starts PENDING review for patient information.

  * Board members read PENDING and CLEARED files; a WITHHELD file is served only
    to the board's administrators, who decide whether it is deleted at source.
  * The requester, on the portal, sees CLEARED files and the ones they sent
    themselves, never a WITHHELD one.
  * Any member who can work the board can review a file.
  * Every download on a restricted board is audited with the file it was, on top
    of the audit of the ticket read.

A download is always served as an attachment, never displayed in the page, with
nosniff and a sandbox policy: a file on a ticket is something someone sent, and
the browser is not asked to trust it.
"""
from __future__ import annotations

import urllib.parse

from ... import attachments
from .. import templates as t
from . import common

REVIEW_LABEL = {"PENDING": "Awaiting review", "CLEARED": "Cleared",
                "WITHHELD": "Withheld: patient information"}


def of_ticket(conn, work_item_id: str):
    return conn.execute("SELECT * FROM attachment WHERE work_item_id = ?"
                        " ORDER BY attachment_id", (work_item_id,)).fetchall()


def _size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / 1024:.0f} KB" if n >= 1024 else f"{n} B"


def ticket_card(ctx, tk, *, can_work: bool) -> str:
    wid = t.esc(tk["work_item_id"])
    is_admin = common.may_access_board(ctx, tk["board_id"], need="ADMIN")
    rows = of_ticket(ctx.conn, tk["work_item_id"])
    items = []
    for r in rows:
        name = t.esc(r["filename"])
        if r["purged_at"]:
            items.append(f"<li><s>{name}</s> <span class=muted>{_size(r['size_received'])} · "
                         f"{t.esc(r['uploaded_by'])} · removed {t.esc(r['purged_at'][:10])}"
                         f" ({'missing' if r['purge_reason'] == 'MISSING' else 'retention'})"
                         "</span></li>")
            continue
        served = r["review_status"] != "WITHHELD" or is_admin
        link = file_link(f"/ticket/{wid}/file/{r['attachment_id']}", r) if served else f"<s>{name}</s>"
        saved = ""
        if r["size_stored"] < r["size_received"]:
            saved = f", stored {_size(r['size_stored'])}"
        line = (f"<li>{link} <span class=muted>{_size(r['size_received'])}{saved} · "
                f"{t.esc(r['uploaded_by'])}</span> {t.chip(REVIEW_LABEL[r['review_status']])}")
        if can_work and r["review_status"] == "PENDING":
            line += (f"<form method=post action='/ticket/{wid}/file/{r['attachment_id']}/review'"
                     " style='display:inline'>"
                     "<button class='ghost small' name=decision value=CLEARED type=submit>"
                     f"Clear</button> <button class='ghost small' name=decision value=WITHHELD"
                     f" type=submit aria-label='Withhold {name}: shows patient information'>"
                     "Withhold</button></form>")
        items.append(line + "</li>")
    upload = ""
    if can_work:
        upload = (f"<form method=post action='/ticket/{wid}/attach' enctype='multipart/form-data'"
                  " class=row style='margin-top:8px'>"
                  "<div><input type=file name=file required></div>"
                  "<div style='flex:0 0 auto'><button class=ghost type=submit><svg class=ic aria-hidden=true><use href=#i-paperclip></use></svg> Attach</button></div>"
                  "</form><p class=why style='margin:6px 0 0'>Up to 10 MB. Screenshots, photos, "
                  "PDFs, logs and Office documents. Every file waits for a patient-information "
                  "review.</p>")
    pending = sum(1 for r in rows if r["review_status"] == "PENDING" and not r["purged_at"])
    head = f"Files · {len(rows)}" + (f" · {pending} to review" if pending else "")
    viewable = any(view_kind(r["media_type"]) and not r["purged_at"] for r in rows)
    return (f"<div class=card data-pod=files><h3><svg class=ic aria-hidden=true><use href=#i-paperclip></use></svg>{head if rows else 'Files'}</h3>"
            + (f"<ul class=plain>{''.join(items)}</ul>" if items
               else "<div class=muted>No files.</div>")
            + upload + (viewer_dialog() if viewable else "") + "</div>")


def file_link(href: str, r) -> str:
    """The file's name as a link: viewable kinds open in the viewer (and the
    plain link still works without script), with a download beside; the rest
    download."""
    name = t.esc(r["filename"])
    kind = view_kind(r["media_type"])
    if not kind:
        return f"<a href='{href}'>{name}</a>"
    return (f"<a href='{href}' data-view='{kind}' data-name='{name}'>{name}</a> "
            f"<a href='{href}?dl=1' class=muted title='Download {name}' aria-label='Download {name}'>" + t.icon("down") + "</a>")


def _attachment_on(ctx, work_item_id: str, attachment_id: str):
    from .. import HttpError
    if not attachment_id.isdigit():
        raise HttpError("404 Not Found", "No such file.")
    row = ctx.conn.execute("SELECT * FROM attachment WHERE attachment_id = ? AND work_item_id = ?",
                           (int(attachment_id), work_item_id)).fetchone()
    if row is None:
        raise HttpError("404 Not Found", "No such file on this ticket.")
    return row


# What the browser shows in place rather than saves (Dada, 1 Oct 2026: "autoviewer
# on attachments rather than being downloaded"). Pictures, PDFs and plain text:
# the kinds a browser renders itself. Office documents and mail files have no
# viewer in a browser and stay downloads. ?dl=1 downloads any of them.
VIEWABLE = ("image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp", "application/pdf",
            "text/plain", "text/csv")


def view_kind(media_type: str) -> str:
    """'image', 'pdf', 'text' or '' (download only)."""
    if media_type.startswith("image/") and media_type in VIEWABLE:
        return "image"
    if media_type == "application/pdf":
        return "pdf"
    if media_type in ("text/plain", "text/csv"):
        return "text"
    return ""


def viewer_dialog() -> str:
    """The one dialog a page with viewable files carries: the picture or frame
    goes in when a file is clicked (templates JS, [data-view])."""
    return ("<dialog id=viewer class=viewer aria-label='File'><div class=vbar><b class=vname></b>"
            "<span class=grow></span><a class='btn ghost small' data-vdl href='#'>Download</a> "
            "<a class='btn ghost small' data-vopen href='#' target=_blank rel=noopener>Open in a tab</a> "
            "<button type=button class='iconbtn' data-close title='Close'>" + t.icon("x") + "</button></div>"
            "<div class=vbody></div></dialog>")


def serve(ctx, row, *, board_id: str):
    """The file, shown in place when the browser can show it (a picture, a PDF,
    plain text) and as a download otherwise or on ?dl=1. Audited on a
    restricted board."""
    from .. import HttpError, Response
    kind = view_kind(row["media_type"])
    inline = bool(kind) and ctx.request.query.get("dl") != "1"
    common.audit_restricted_read(
        ctx, board_id, subject_id=row["work_item_id"],
        detail=f"{'viewed' if inline else 'downloaded'} attachment {row['attachment_id']} ({row['filename']})"
               f" via {ctx.user.via}")
    try:
        _, data = attachments.read(ctx.conn, row["attachment_id"])
    except attachments.Removed:
        raise HttpError("410 Gone", "That file was removed under the retention rule.")
    except (OSError, LookupError):
        raise HttpError("404 Not Found", "That file is missing or damaged; it was not served.")
    ascii_name = row["filename"].encode("ascii", "replace").decode().replace("?", "_") \
        .replace('"', "_")
    disposition = (f'{"inline" if inline else "attachment"}; filename="{ascii_name}"; '
                   f"filename*=UTF-8''{urllib.parse.quote(row['filename'])}")
    # A picture or text shown inline is sandboxed as before: no script, no
    # origin. A PDF is drawn by the browser's own viewer, which Chromium does not
    # run inside a sandboxed document (INFERRED from its plugin rules: a
    # sandboxed PDF comes up blank or downloads), so a PDF shown inline gets a
    # policy that lets nothing load instead of the sandbox flag.
    csp = "default-src 'none'; frame-ancestors 'self'" if inline and kind == "pdf" else "sandbox"
    return Response(body=data, content_type=row["media_type"], headers=[
        ("Content-Disposition", disposition),
        ("Content-Security-Policy", csp),
        ("Cache-Control", "private, no-store")])


# ------------------------------------------------------------------ desk routes

def upload(ctx, work_item_id):
    from .ticket import _back, _load
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    files = ctx.request.files("file")
    if not files:
        return _back(work_item_id, err="Not attached: choose a file first")
    kept, refused = [], []
    for filename, data in files:
        try:
            attachments.add(ctx.conn, work_item_id, data, filename, actor=ctx.user.id,
                            at=ctx.now, source="DESK")
            kept.append(attachments.safe_name(filename))
        except attachments.Refused as exc:
            refused.append(f"{attachments.safe_name(filename)}: {exc}")
    ctx.conn.commit()
    if refused:
        return _back(work_item_id, msg=("Attached " + ", ".join(kept)) if kept else "",
                     err="Not attached: " + "; ".join(refused))
    return _back(work_item_id, msg="Attached " + ", ".join(kept))


def download(ctx, work_item_id, attachment_id):
    from .. import HttpError
    from .ticket import _load
    tk = _load(ctx, work_item_id)
    row = _attachment_on(ctx, work_item_id, attachment_id)
    if row["purged_at"]:
        raise HttpError("410 Gone", "That file was removed under the retention rule.")
    if row["review_status"] == "WITHHELD" and \
            not common.may_access_board(ctx, tk["board_id"], need="ADMIN"):
        raise HttpError("404 Not Found", "That file was withheld for patient information.")
    return serve(ctx, row, board_id=tk["board_id"])


def review(ctx, work_item_id, attachment_id):
    from .ticket import _back, _load
    tk = _load(ctx, work_item_id)
    common.require_board(ctx, tk["board_id"], need="WORK")
    row = _attachment_on(ctx, work_item_id, attachment_id)
    decision = ctx.request.form().get("decision", "")
    if decision not in ("CLEARED", "WITHHELD"):
        return _back(work_item_id, err="Not reviewed: choose Clear or Withhold")
    if row["purged_at"]:
        return _back(work_item_id, err="That file was removed under retention; nothing to review")
    if row["review_status"] != "PENDING":
        return _back(work_item_id, err="That file has already been reviewed")
    attachments.review(ctx.conn, row["attachment_id"], decision, actor=ctx.user.id, at=ctx.now)
    ctx.conn.commit()
    return _back(work_item_id, msg=f"{row['filename']}: "
                 + ("cleared" if decision == "CLEARED" else "withheld"))
