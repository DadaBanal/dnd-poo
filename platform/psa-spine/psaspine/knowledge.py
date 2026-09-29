"""The knowledge base (039): articles the desk writes once and uses again.

An article is a title and a Markdown body, for the desk (INTERNAL) or for
requesters too (REQUESTER, shown on the portal's Help page once PUBLISHED). It
may belong to a board and to a Subtype › Item pair; a ticket on that pair is
offered it first. Every save keeps the words it replaced, as a revision, and
the version counts up. A ticket an article helped with is linked, and the
article's use count is how the desk learns which articles earn their keep.

Patient details are not refused; they are flagged on save for the author to
tidy, like every other free text (Dada, 28 Sep 2026). Nothing is deleted: an
article is retired.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from . import db, phi

AUDIENCES = {"INTERNAL": "The desk only", "REQUESTER": "The desk and requesters"}
STATUSES = ("DRAFT", "PUBLISHED", "RETIRED")
MAX_TITLE = 200
MAX_BODY = 100_000


class Refused(ValueError):
    """A sentence for the person; nothing was written."""


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def _next_id(conn) -> str:
    n = 0
    for (aid,) in conn.execute("SELECT article_id FROM kb_article"):
        try:
            n = max(n, int(aid.split("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"KB-{n + 1:04d}"


def _clean(title, body, audience, board_id, catalogue_item_id, conn):
    title = " ".join((title or "").split())
    body = (body or "").replace("\r\n", "\n").strip()
    if not title:
        raise Refused("An article needs a title.")
    if len(title) > MAX_TITLE:
        raise Refused(f"A title is at most {MAX_TITLE} characters.")
    if not body:
        raise Refused("An article needs some words.")
    if len(body) > MAX_BODY:
        raise Refused("An article is at most 100,000 characters; split it.")
    if audience not in AUDIENCES:
        raise Refused("Say who the article is for.")
    if board_id and not conn.execute("SELECT 1 FROM board WHERE board_id = ?", (board_id,)).fetchone():
        raise Refused("No such board.")
    if catalogue_item_id and not conn.execute("SELECT 1 FROM catalogue_item WHERE catalogue_item_id = ?",
                                              (catalogue_item_id,)).fetchone():
        raise Refused("No such Subtype › Item pair.")
    return title, body


def _flag(conn, article_id: str, title: str, body: str) -> int:
    findings = phi.scan_fields({"title": title, "body": body})
    conn.execute("DELETE FROM data_quality WHERE run_id = 'kb' AND subject_kind = 'kb_article' AND subject_id = ?",
                 (article_id,))
    for code, severity, detail in findings:
        conn.execute("INSERT INTO data_quality (run_id, subject_kind, subject_id, code, detail, severity)"
                     " VALUES ('kb', 'kb_article', ?, ?, ?, ?)", (article_id, code, detail, severity))
    return len(findings)


def flags(conn, article_id: str) -> list[str]:
    return [r[0] for r in conn.execute("SELECT detail FROM data_quality WHERE run_id = 'kb'"
                                       " AND subject_kind = 'kb_article' AND subject_id = ?", (article_id,))]


def create(conn, *, title: str, body: str, audience: str = "INTERNAL", board_id: str | None = None,
           catalogue_item_id: str | None = None, at: datetime, actor: str) -> str:
    title, body = _clean(title, body, audience, board_id, catalogue_item_id, conn)
    aid = _next_id(conn)
    stamp = _stamp(at)
    conn.execute(
        "INSERT INTO kb_article (article_id, title, body, audience, status, board_id, catalogue_item_id, version,"
        " uses, created_at, created_by, updated_at, updated_by) VALUES (?,?,?,?, 'DRAFT', ?,?,1,0,?,?,?,?)",
        (aid, title, body, audience, board_id or None, catalogue_item_id or None, stamp, actor, stamp, actor))
    conn.execute("INSERT INTO kb_revision (article_id, version, title, body, saved_at, saved_by) VALUES (?,1,?,?,?,?)",
                 (aid, title, body, stamp, actor))
    _flag(conn, aid, title, body)
    db.audit(conn, at=stamp, actor=actor, action="KB_ARTICLE", subject_kind="kb_article", subject_id=aid,
             detail=f"written: {title}")
    return aid


def get(conn, article_id: str):
    return conn.execute(
        "SELECT a.*, b.display_name AS board_name FROM kb_article a LEFT JOIN board b ON b.board_id = a.board_id"
        " WHERE a.article_id = ?", (article_id,)).fetchone()


def save(conn, article_id: str, *, title: str, body: str, audience: str, board_id: str | None,
         catalogue_item_id: str | None, at: datetime, actor: str) -> str:
    row = get(conn, article_id)
    if row is None:
        raise Refused("No such article.")
    title, body = _clean(title, body, audience, board_id, catalogue_item_id, conn)
    same = (title == row["title"] and body == row["body"] and audience == row["audience"]
            and (board_id or None) == row["board_id"] and (catalogue_item_id or None) == row["catalogue_item_id"])
    if same:
        return "nothing changed"
    version = row["version"] + 1
    stamp = _stamp(at)
    conn.execute("UPDATE kb_article SET title = ?, body = ?, audience = ?, board_id = ?, catalogue_item_id = ?,"
                 " version = ?, updated_at = ?, updated_by = ? WHERE article_id = ?",
                 (title, body, audience, board_id or None, catalogue_item_id or None, version, stamp, actor, article_id))
    conn.execute("INSERT INTO kb_revision (article_id, version, title, body, saved_at, saved_by) VALUES (?,?,?,?,?,?)",
                 (article_id, version, title, body, stamp, actor))
    _flag(conn, article_id, title, body)
    db.audit(conn, at=stamp, actor=actor, action="KB_ARTICLE", subject_kind="kb_article", subject_id=article_id,
             detail=f"saved as version {version}")
    return f"saved as version {version}"


def set_status(conn, article_id: str, status: str, *, at: datetime, actor: str) -> str:
    row = get(conn, article_id)
    if row is None:
        raise Refused("No such article.")
    if status not in STATUSES:
        raise Refused("No such status.")
    if status == row["status"]:
        return "nothing changed"
    conn.execute("UPDATE kb_article SET status = ?, updated_at = ?, updated_by = ? WHERE article_id = ?",
                 (status, _stamp(at), actor, article_id))
    db.audit(conn, at=_stamp(at), actor=actor, action="KB_ARTICLE", subject_kind="kb_article", subject_id=article_id,
             detail=f"{row['status'].lower()} -> {status.lower()}")
    return f"{row['status'].lower()} -> {status.lower()}"


def revisions(conn, article_id: str):
    return conn.execute("SELECT * FROM kb_revision WHERE article_id = ? ORDER BY version DESC", (article_id,)).fetchall()


def _like(needle: str) -> str:
    """A contains-match with every wildcard escaped: SQLite's two, and '[',
    which SQL Server's LIKE reads as a character class (part 12's rule)."""
    return "%" + (needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                  .replace("[", "\\[")) + "%"


def search(conn, *, q: str = "", status: str | None = None, audience: str | None = None,
           board_ids=None, limit: int = 200):
    """Articles matching every word of q in the title or body. `board_ids`
    limits a board's own articles to the boards the reader sees; an article on
    no board is everyone's."""
    sql = ["SELECT a.*, b.display_name AS board_name FROM kb_article a LEFT JOIN board b ON b.board_id = a.board_id"
           " WHERE 1 = 1"]
    args: list = []
    for word in [w for w in (q or "").split() if w][:6]:
        like = _like(word.lower())
        sql.append(" AND (LOWER(a.title) LIKE ? ESCAPE '\\' OR LOWER(a.body) LIKE ? ESCAPE '\\')")
        args += [like, like]
    if status:
        sql.append(" AND a.status = ?")
        args.append(status)
    if audience:
        sql.append(" AND a.audience = ?")
        args.append(audience)
    if board_ids is not None:
        boards = sorted(board_ids)
        sql.append(" AND (a.board_id IS NULL" + (f" OR a.board_id IN ({','.join('?' * len(boards))})" if boards else "") + ")")
        args += boards
    sql.append(" ORDER BY a.uses DESC, a.updated_at DESC")
    return conn.execute("".join(sql), args).fetchall()[:limit]


def suggest(conn, work_item_id: str, *, board_ids, limit: int = 5):
    """Published articles for a ticket: its own pair first, then its board's,
    then any whose title shares a word of four letters or more with the summary."""
    tk = conn.execute("SELECT t.board_id, t.catalogue_item_id, w.name FROM ticket t JOIN work_item w"
                      " ON w.work_item_id = t.work_item_id WHERE t.work_item_id = ?", (work_item_id,)).fetchone()
    if tk is None:
        return []
    words = {w.lower().strip(".,:;!?()") for w in (tk["name"] or "").split() if len(w) >= 4}
    # only the columns the ranking reads, and only articles that can score:
    # the ticket's pair, its board, or a title word in common. Never the bodies.
    boards = sorted(board_ids) if board_ids is not None else None
    sql = ["SELECT a.article_id, a.title, a.board_id, a.catalogue_item_id, a.uses FROM kb_article a"
           " WHERE a.status = 'PUBLISHED'"]
    args: list = []
    if boards is not None:
        sql.append(" AND (a.board_id IS NULL" + (f" OR a.board_id IN ({','.join('?' * len(boards))})" if boards else "") + ")")
        args += boards
    hit = ["a.board_id = ?"]
    args.append(tk["board_id"])
    if tk["catalogue_item_id"]:
        hit.append("a.catalogue_item_id = ?")
        args.append(tk["catalogue_item_id"])
    for w in sorted(words)[:12]:
        hit.append("LOWER(a.title) LIKE ? ESCAPE '\\'")
        args.append(_like(w))
    sql.append(" AND (" + " OR ".join(hit) + ")")
    live = conn.execute("".join(sql), args).fetchall()

    def score(a):
        s = 0
        if tk["catalogue_item_id"] and a["catalogue_item_id"] == tk["catalogue_item_id"]:
            s += 100
        if a["board_id"] == tk["board_id"]:
            s += 10
        s += sum(1 for w in words if w in a["title"].lower())
        return s
    ranked = sorted((a for a in live if score(a) > 0), key=lambda a: (-score(a), -a["uses"]))
    return ranked[:limit]


def link(conn, article_id: str, work_item_id: str, *, at: datetime, actor: str) -> bool:
    from .board import _event
    if get(conn, article_id) is None:
        raise Refused("No such article.")
    if conn.execute("SELECT 1 FROM kb_ticket WHERE article_id = ? AND work_item_id = ?",
                    (article_id, work_item_id)).fetchone():
        return False
    conn.execute("INSERT INTO kb_ticket (article_id, work_item_id, linked_at, linked_by) VALUES (?,?,?,?)",
                 (article_id, work_item_id, _stamp(at), actor))
    conn.execute("UPDATE kb_article SET uses = uses + 1 WHERE article_id = ?", (article_id,))
    _event(conn, work_item_id, _stamp(at), "KNOWLEDGE", actor, f"article used: {article_id}")
    return True


def linked(conn, work_item_id: str):
    return conn.execute("SELECT a.article_id, a.title, a.status FROM kb_ticket k JOIN kb_article a"
                        " ON a.article_id = k.article_id WHERE k.work_item_id = ? ORDER BY k.linked_at",
                        (work_item_id,)).fetchall()
