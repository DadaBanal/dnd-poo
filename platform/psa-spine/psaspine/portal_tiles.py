"""Tiles on the requester portal (078), in the reference PSA's help-portal shape.

Dada, 9 Oct 2026: "on the my requests portal we should add in there an option
like the help portal for connectwise like choosing tiles what are your issues so
that we can route to the procurement board the pmo helpdesk board so it helps
the ticketer". Confirmed before building:

  * Setup › Portal tiles holds them: add, rename, reorder, retire.
  * A tile may open a row of smaller tiles, one level deep. The tile a request
    is raised from sends it to its board with its Type, Subtype and Item
    already chosen (one catalogue pair), so the ticketer opens a ticket that is
    already classified. A sub-tile with no board or no pair takes its parent's.
  * A tile asks a few questions. A parent's questions are asked for each of its
    sub-tiles too. The answers are kept per question (`portal_answer`) and put
    in the ticket's description, so the desk reads them where it reads the rest.
  * Every department sees every tile ("every department has procurement
    inventory mms issues"): a tile's board needs no department tick.
  * A request whose Item needs approval (049) asks for it, as the desk does.

The PMC starter set (`seed_pmc`, `psaspine portal-tiles`) is matched against the
live catalogue by name, because the live tree was restructured on 2 Oct and no
longer has the pack's names everywhere. It previews first and writes only with
--apply, and never changes a tile that is already there.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime

from . import db

FIELD_TYPES = {"TEXT": "A line of text", "PARAGRAPH": "A few lines", "NUMBER": "A number",
               "DATE": "A date", "CHECKBOX": "A tick box"}
ICONS = ("monitor", "note", "lock", "mail", "layers", "link", "plus", "briefcase", "inbox", "users",
         "building", "tag", "ticket", "info", "alert", "shield", "calendar", "clock", "image", "star")
LABEL_MAX, HINT_MAX = 80, 160


def available(conn) -> bool:
    """Whether 078 is in. Without it the portal shows the plain form, as before."""
    return db.table_exists(conn, "portal_tile")


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


# ------------------------------------------------------------------ reading

def tiles(conn, *, all_rows: bool = False) -> list[dict]:
    """Every tile, parents before their sub-tiles, each in its order."""
    rows = [dict(r) for r in conn.execute(
        "SELECT p.*, b.display_name AS board_name FROM portal_tile p"
        " LEFT JOIN board b ON b.board_id = p.board_id"
        + ("" if all_rows else " WHERE p.inactive = 0")
        + " ORDER BY p.sort_order, p.label").fetchall()]
    top = [r for r in rows if r["parent_id"] is None]
    out = []
    for r in top:
        out.append(r)
        out.extend(x for x in rows if x["parent_id"] == r["tile_id"])
    return out


def top(conn) -> list[dict]:
    return [r for r in tiles(conn) if r["parent_id"] is None]


def children(conn, tile_id: int) -> list[dict]:
    return [r for r in tiles(conn) if r["parent_id"] == tile_id]


def get(conn, tile_id) -> dict | None:
    try:
        tid = int(tile_id)
    except (TypeError, ValueError):
        return None
    r = conn.execute("SELECT * FROM portal_tile WHERE tile_id = ?", (tid,)).fetchone()
    return dict(r) if r else None


def _board_ok(conn, board_id: str | None) -> bool:
    if not board_id:
        return False
    r = conn.execute("SELECT is_live, is_unrouted, COALESCE(inactive, 0) AS inactive FROM board WHERE board_id = ?",
                     (board_id,)).fetchone()
    return bool(r) and r["is_live"] == 1 and r["is_unrouted"] == 0 and r["inactive"] == 0


def _pair(conn, catalogue_item_id: str | None):
    """A live catalogue pair, or None."""
    if not catalogue_item_id:
        return None
    return conn.execute(
        "SELECT i.*, f.display_name AS type, c.display_name AS subtype, a.display_name AS item"
        "  FROM catalogue_item i JOIN service_component c ON c.component_id = i.component_id"
        "  JOIN service_family f ON f.family_id = c.family_id JOIN service_action a ON a.action_id = i.action_id"
        " WHERE i.catalogue_item_id = ? AND i.is_draft = 0 AND c.is_draft = 0"
        "   AND COALESCE(f.inactive, 0) = 0 AND COALESCE(a.inactive, 0) = 0", (catalogue_item_id,)).fetchone()


def pair_label(conn, catalogue_item_id: str | None) -> str:
    p = _pair(conn, catalogue_item_id)
    return f"{p['type']} › {p['subtype']} › {p['item']}" if p else ""


def questions(conn, tile_id: int, *, all_rows: bool = False) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM portal_tile_question WHERE tile_id = ?" + ("" if all_rows else " AND inactive = 0")
        + " ORDER BY sort_order, question_id", (tile_id,)).fetchall()]


def route(conn, tile_id) -> dict:
    """Where a request raised from this tile goes, and what it asks. Raises
    LookupError for a tile that cannot take a request: retired, one that opens
    sub-tiles, or one whose board is not live."""
    tile = get(conn, tile_id)
    if tile is None or tile["inactive"]:
        raise LookupError("That choice is not available any more.")
    parent = get(conn, tile["parent_id"]) if tile["parent_id"] else None
    if parent is not None and parent["inactive"]:
        raise LookupError("That choice is not available any more.")
    if children(conn, tile["tile_id"]):
        raise LookupError("Choose one of the smaller tiles first.")
    board_id = tile["board_id"] or (parent or {}).get("board_id")
    if not _board_ok(conn, board_id):
        raise LookupError("That choice is not taking requests right now. Use Something else.")
    item = tile["catalogue_item_id"] or (parent or {}).get("catalogue_item_id")
    if item and _pair(conn, item) is None:
        item = None                                  # retired in the catalogue since: the ticketer classifies it
    qs = (questions(conn, parent["tile_id"]) if parent else []) + questions(conn, tile["tile_id"])
    return {"tile": tile, "parent": parent, "board_id": board_id, "catalogue_item_id": item, "questions": qs}


# ------------------------------------------------------------------ answers

def clean(q: dict, raw) -> str | None:
    """One answer, as the configuration questions (056) clean theirs; a
    paragraph keeps its lines."""
    if q["field_type"] == "PARAGRAPH":
        text = "\n".join(" ".join(line.split()) for line in str(raw or "").splitlines()).strip()
        return text[:2000] or None
    v = " ".join(str(raw if raw is not None else "").split())
    if q["field_type"] == "CHECKBOX":
        return "Yes" if v.lower() in ("1", "on", "yes", "true") else None
    if not v:
        return None
    if q["field_type"] == "NUMBER":
        try:
            return f"{float(v.replace(',', '')):g}"
        except ValueError:
            raise ValueError(f"{q['label']}: a number, please.") from None
    if q["field_type"] == "DATE":
        try:
            return date.fromisoformat(v).isoformat()
        except ValueError:
            raise ValueError(f"{q['label']}: a date, please, e.g. 2026-12-31.") from None
    return v[:400]


def read_answers(qs: list[dict], form) -> list[tuple[dict, str | None]]:
    """Every answer checked before any is kept. Form fields are `q<id>`."""
    out = []
    for q in qs:
        v = clean(q, form.get(f"q{q['question_id']}"))
        if q["required"] and v is None:
            raise ValueError(f"Please answer: {q['label']}")
        out.append((q, v))
    return out


def answers_text(answers) -> str:
    lines = [f"{q['label']}: {v}" for q, v in answers if v is not None]
    return ("Answers from the portal:\n" + "\n".join(lines)) if lines else ""


def keep_answers(conn, work_item_id: str, answers) -> None:
    for q, v in answers:
        if v is not None:
            conn.execute("INSERT INTO portal_answer (work_item_id, question_id, label, value) VALUES (?,?,?,?)",
                         (work_item_id, q["question_id"], q["label"], v))


def answers_of(conn, work_item_id: str) -> list[dict]:
    if not available(conn):
        return []
    return [dict(r) for r in conn.execute(
        "SELECT a.label, a.value FROM portal_answer a JOIN portal_tile_question q ON q.question_id = a.question_id"
        " WHERE a.work_item_id = ? ORDER BY q.tile_id, q.sort_order, q.question_id", (work_item_id,)).fetchall()]


# ------------------------------------------------------------------ setup

def _check(conn, *, tile_id: int | None, label: str, hint: str | None, icon: str | None, parent_id,
           board_id: str | None, catalogue_item_id: str | None) -> tuple:
    label = " ".join((label or "").split())
    if not label:
        raise ValueError("A tile needs a name.")
    if len(label) > LABEL_MAX:
        raise ValueError(f"A tile's name is at most {LABEL_MAX} characters.")
    hint = " ".join((hint or "").split())[:HINT_MAX] or None
    icon = icon if icon in ICONS else None
    parent = None
    if parent_id not in (None, "", 0, "0"):
        parent = get(conn, parent_id)
        if parent is None:
            raise ValueError("No such parent tile.")
        if parent["parent_id"] is not None:
            raise ValueError("A tile goes one level deep: its parent must be a top tile.")
        if tile_id is not None and parent["tile_id"] == tile_id:
            raise ValueError("A tile cannot be its own parent.")
        if tile_id is not None and conn.execute("SELECT 1 FROM portal_tile WHERE parent_id = ?", (tile_id,)).fetchone():
            raise ValueError("This tile has smaller tiles of its own, so it stays a top tile.")
    board_id = board_id or None
    if board_id and conn.execute("SELECT 1 FROM board WHERE board_id = ?", (board_id,)).fetchone() is None:
        raise ValueError("No such board.")
    catalogue_item_id = catalogue_item_id or None
    if catalogue_item_id and _pair(conn, catalogue_item_id) is None:
        raise ValueError("That Type › Subtype › Item is not in the live catalogue.")
    eff_board = board_id or (parent or {}).get("board_id")
    eff_item = catalogue_item_id or (parent or {}).get("catalogue_item_id")
    if eff_board and eff_item:
        from . import itil
        try:
            itil.resolve(conn, eff_board, item=_pair(conn, eff_item))
        except itil.NotAccepted as exc:
            raise ValueError(f"That Item cannot go to that board: {exc}.") from None
    return label, hint, icon, (parent["tile_id"] if parent else None), board_id, catalogue_item_id


def add_tile(conn, *, label: str, at: datetime, actor: str, hint: str | None = None, icon: str | None = None,
             parent_id=None, board_id: str | None = None, catalogue_item_id: str | None = None,
             sort_order: int = 0) -> int:
    label, hint, icon, parent_id, board_id, catalogue_item_id = _check(
        conn, tile_id=None, label=label, hint=hint, icon=icon, parent_id=parent_id, board_id=board_id,
        catalogue_item_id=catalogue_item_id)
    conn.execute("INSERT INTO portal_tile (parent_id, label, hint, icon, board_id, catalogue_item_id, sort_order)"
                 " VALUES (?,?,?,?,?,?,?)", (parent_id, label, hint, icon, board_id, catalogue_item_id, int(sort_order)))
    tid = conn.execute("SELECT MAX(tile_id) FROM portal_tile WHERE label = ?", (label,)).fetchone()[0]
    db.audit(conn, at=_stamp(at), actor=actor, action="PORTAL_TILE", subject_kind="portal_tile", subject_id=str(tid),
             detail=f"added {label!r} -> {board_id or 'its parent board'}"
                    + (f", {pair_label(conn, catalogue_item_id)}" if catalogue_item_id else ""))
    return tid


def save_tile(conn, tile_id: int, *, at: datetime, actor: str, label: str, hint: str | None, icon: str | None,
              parent_id, board_id: str | None, catalogue_item_id: str | None, sort_order: int,
              inactive: bool | None = None) -> str:
    old = get(conn, tile_id)
    if old is None:
        raise ValueError("No such tile.")
    label, hint, icon, parent_id, board_id, catalogue_item_id = _check(
        conn, tile_id=old["tile_id"], label=label, hint=hint, icon=icon, parent_id=parent_id, board_id=board_id,
        catalogue_item_id=catalogue_item_id)
    new = {"label": label, "hint": hint, "icon": icon, "parent_id": parent_id, "board_id": board_id,
           "catalogue_item_id": catalogue_item_id, "sort_order": int(sort_order),
           "inactive": old["inactive"] if inactive is None else int(bool(inactive))}
    changed = [f"{k}: {old[k]!r} -> {v!r}" for k, v in new.items() if old[k] != v]
    if not changed:
        return "nothing changed"
    conn.execute("UPDATE portal_tile SET label = ?, hint = ?, icon = ?, parent_id = ?, board_id = ?,"
                 " catalogue_item_id = ?, sort_order = ?, inactive = ? WHERE tile_id = ?",
                 (*new.values(), old["tile_id"]))
    db.audit(conn, at=_stamp(at), actor=actor, action="PORTAL_TILE", subject_kind="portal_tile",
             subject_id=str(old["tile_id"]), detail="; ".join(changed)[:900])
    return "; ".join(changed)


def add_question(conn, tile_id: int, *, label: str, field_type: str, required: bool, at: datetime, actor: str,
                 sort_order: int | None = None) -> int:
    tile = get(conn, tile_id)
    if tile is None:
        raise ValueError("No such tile.")
    label = " ".join((label or "").split())[:120]
    if not label:
        raise ValueError("A question needs words.")
    if field_type not in FIELD_TYPES:
        raise ValueError("Choose what kind of answer it takes.")
    if sort_order is None:
        sort_order = (conn.execute("SELECT COALESCE(MAX(sort_order), 0) FROM portal_tile_question WHERE tile_id = ?",
                                   (tile["tile_id"],)).fetchone()[0] or 0) + 10
    conn.execute("INSERT INTO portal_tile_question (tile_id, label, field_type, required, sort_order) VALUES (?,?,?,?,?)",
                 (tile["tile_id"], label, field_type, int(bool(required)), int(sort_order)))
    qid = conn.execute("SELECT MAX(question_id) FROM portal_tile_question WHERE tile_id = ?",
                       (tile["tile_id"],)).fetchone()[0]
    db.audit(conn, at=_stamp(at), actor=actor, action="PORTAL_TILE", subject_kind="portal_tile",
             subject_id=str(tile["tile_id"]), detail=f"asks {label!r} ({field_type}{', needed' if required else ''})")
    return qid


def save_question(conn, question_id: int, *, at: datetime, actor: str, label: str | None = None,
                  required: bool | None = None, inactive: bool | None = None) -> str:
    r = conn.execute("SELECT * FROM portal_tile_question WHERE question_id = ?", (question_id,)).fetchone()
    if r is None:
        raise ValueError("No such question.")
    new_label = " ".join((label if label is not None else r["label"]).split())[:120] or r["label"]
    new_req = r["required"] if required is None else int(bool(required))
    new_off = r["inactive"] if inactive is None else int(bool(inactive))
    changed = [w for w, a, b in (("words", r["label"], new_label), ("needed", r["required"], new_req),
                                 ("retired", r["inactive"], new_off)) if a != b]
    if not changed:
        return "nothing changed"
    conn.execute("UPDATE portal_tile_question SET label = ?, required = ?, inactive = ? WHERE question_id = ?",
                 (new_label, new_req, new_off, question_id))
    db.audit(conn, at=_stamp(at), actor=actor, action="PORTAL_TILE", subject_kind="portal_tile",
             subject_id=str(r["tile_id"]), detail=f"question {r['label']!r}: " + ", ".join(changed))
    return ", ".join(changed)


# ------------------------------------------------------------------ the PMC starter set
#
# Ten tiles in plain words (Dada chose these, 9 Oct 2026): seven for PMO
# Helpdesk, two for Procurement, and Something else, which is the plain form
# and needs no row. Each sub-tile names the catalogue pair it should land on as
# (Type, Subtype, Item) patterns, tried in order against the live catalogue; the
# first live pair that matches all three wins. No match: the tile still routes
# to its board and the ticketer classifies, and the preview says so.

H, P = "HELPDESK", "PROCUREMENT"
NOT_WORKING = r"^not working$"
PAYROLL_LOGIN = [(r"premiere", r"^payroll", r"cannot log in"), (None, r"^payroll", r"cannot log in")]
BUY_QUESTIONS = [("What do you need?", "TEXT", True), ("How many?", "NUMBER", True),
                 ("Needed by", "DATE", False), ("What is it for, and for which area?", "TEXT", True),
                 ("Estimated cost, if you know it", "NUMBER", False)]
STARTER = [
    {"label": "Computer or laptop", "hint": "Not working, slow, or showing an error", "icon": "monitor", "board": H,
     "questions": [("The computer's name, or the sticker on it", "TEXT", False)],
     "subs": [("Desktop computer", [(None, r"desktop|\bnuc\b", NOT_WORKING)]),
              ("Laptop", [(None, r"^laptop", NOT_WORKING)]),
              ("Monitor or screen", [(None, r"^monitor", NOT_WORKING)]),
              ("Keyboard, mouse or cable", [(None, r"keyboard|mouse", NOT_WORKING)])]},
    {"label": "Printer or scanner", "hint": "Not printing, jammed, or not scanning", "icon": "note", "board": H,
     "questions": [("The printer's name, or where it is", "TEXT", False)],
     "subs": [("Printer", [(None, r"^printers?$", NOT_WORKING)]),
              ("Scanner", [(None, r"^scanner", NOT_WORKING)]),
              ("Label or barcode printer", [(None, r"label|barcode", NOT_WORKING)])]},
    {"label": "Can't log in, or a password", "hint": "Locked out, or a password to reset", "icon": "lock", "board": H,
     "questions": [],
     "subs": [("Reset my password or unlock me", [(None, r"windows account|^windows", r"password")]),
              ("I cannot log in to Windows", [(None, r"windows account|^windows", r"cannot log in")]),
              ("I cannot log in to BizBox", [(None, r"\bHIS\b", r"cannot log in"), (r"^HIS\b", None, r"cannot log in")]),
              # 9 Oct 2026, Thobie Dela Cruz on the portal; Dada chose it. PMC Portal has no
              # Subtype: it is Payroll's second front door, one process (SQL01, Q2)
              ("I cannot log in to PMC Portal or PMC Payroll", PAYROLL_LOGIN)]},
    {"label": "Email and Teams", "hint": "Outlook, Teams, a shared mailbox", "icon": "mail", "board": H,
     "questions": [],
     "subs": [("Not working", [(None, r"email and teams|^e-?mail", NOT_WORKING)]),
              ("I cannot sign in", [(None, r"email and teams|^e-?mail", r"cannot log in")]),
              ("A shared mailbox or folder", [(None, r"shared mailbox", r"access")]),
              ("How do I ...?", [(None, r"email and teams|^e-?mail", r"how do i")])]},
    {"label": "BizBox or a hospital system", "hint": "HIS, Pharmacy, PhilHealth, MMS, FMS, payroll", "icon": "layers",
     "board": H, "questions": [("Which screen, and what you were doing", "TEXT", False)],
     "subs": [("BizBox HIS", [(None, r"\bHIS\b", NOT_WORKING), (r"^HIS\b", None, NOT_WORKING)]),
              ("Pharmacy", [(None, r"pharmacy", NOT_WORKING), (r"pharmacy", None, NOT_WORKING)]),   # not PIS: that is PhilHealth
              ("PhilHealth or eClaims", [(None, r"philhealth|eclaims", NOT_WORKING), (r"philhealth", None, NOT_WORKING)]),
              ("BizBox MMS (the inventory system)", [(None, r"\bMMS\b", NOT_WORKING), (r"\bMMS\b", None, NOT_WORKING)]),
              ("BizBox FMS (finance)", [(None, r"\bFMS\b", NOT_WORKING), (r"\bFMS\b", None, NOT_WORKING)]),
              ("Payroll", [(None, r"payroll", NOT_WORKING)])]},
    {"label": "Network, Wi-Fi or internet", "hint": "No connection, slow, or a point not working", "icon": "link",
     "board": H, "questions": [],
     "subs": [("Wi-Fi", [(None, r"wi-?fi", NOT_WORKING)]),
              ("Internet", [(None, r"^internet", NOT_WORKING)]),
              ("A network point or cable", [(None, r"network point", NOT_WORKING)])]},
    {"label": "Set up something new, or get access", "hint": "A new account, a computer set up or moved, access",
     "icon": "plus", "board": H, "questions": [],
     "subs": [("A new Windows account", [(None, r"windows account|^windows", r"new or install")]),
              ("Set up a computer or device", [(None, r"desktop|\bnuc\b", r"new or install")]),
              ("Move a computer or printer", [(None, r"desktop|\bnuc\b", r"move or change")]),
              ("Access to a folder, mailbox or system", [(None, r"shared mailbox|folder", r"access")])]},
    # 9 Oct 2026 (Dada: "also include the other pmc one things"), from SQL01's Q1-Q3:
    # Premiere One is six Subtypes on IT_HELP; 15 of its 17 tickets in 180 days were
    # Payroll (7 cannot log in, 5 wrong data). Placed before Buy something.
    {"label": "PMC Portal, Payroll and PMC apps", "hint": "Payslip, attendance, leave, Queue, Imaging, My requests",
     "icon": "users", "board": H, "sort": 75, "questions": [],
     "subs": [("I cannot log in to PMC Portal or Payroll", PAYROLL_LOGIN),
              ("My payslip, attendance or leave looks wrong", [(r"premiere", r"^payroll", r"wrong data"),
                                                               (None, r"^payroll", r"wrong data")]),
              ("PMC Portal or Payroll is not working", [(r"premiere", r"^payroll", NOT_WORKING),
                                                        (None, r"^payroll", NOT_WORKING)]),
              ("Queue (kiosk check-in, waiting-room screens)", [(r"premiere", r"^queue", NOT_WORKING)]),
              ("Imaging portal", [(r"premiere", r"^imaging", NOT_WORKING), (None, r"imaging", NOT_WORKING)]),
              ("My requests / PSA Desk", [(r"premiere", r"psa desk", NOT_WORKING)])]},
    {"label": "Buy something", "hint": "A purchase request for Procurement", "icon": "briefcase", "board": P,
     "questions": BUY_QUESTIONS,
     "subs": [("IT equipment", [(None, r"^it equipment", r"^purchase$")]),
              ("Software or a licence", [(None, r"software", r"^purchase$")]),
              ("Consumables (toner, ink, cables)", [(None, r"consumables", r"^purchase$")]),
              ("Medical supplies", [(None, r"medical supplies", r"^purchase$")]),
              ("Furniture and fixtures", [(None, r"furniture", r"^purchase$")]),
              ("Services and repairs", [(None, r"services and repairs|^services", r"repair by supplier")])]},
    {"label": "Stock, a delivery or a PO", "hint": "BizBox MMS: deliveries, purchase orders, invoices, items",
     "icon": "inbox", "board": P,
     "questions": [("PO or item number, if you have it", "TEXT", False), ("What happened?", "PARAGRAPH", True)],
     "subs": [("A delivery is short, wrong or damaged", [(None, r"receiving|delivery", r"short or wrong")]),
              ("Follow up a purchase order", [(None, r"purchase order", r"follow up")]),
              ("A supplier invoice", [(None, r"invoice", r"query")]),
              ("An item or product in BizBox MMS", [(None, r"^product", r"query")])]},
]


def _find_pair(conn, patterns) -> sqlite3.Row | None:
    rows = conn.execute(
        "SELECT i.catalogue_item_id, i.default_board_id, f.display_name AS type, c.display_name AS subtype,"
        "       a.display_name AS item"
        "  FROM catalogue_item i JOIN service_component c ON c.component_id = i.component_id"
        "  JOIN service_family f ON f.family_id = c.family_id JOIN service_action a ON a.action_id = i.action_id"
        " WHERE i.is_draft = 0 AND c.is_draft = 0 AND COALESCE(f.inactive, 0) = 0 AND COALESCE(a.inactive, 0) = 0"
        " ORDER BY f.display_name, c.display_name, a.display_name").fetchall()
    for ty, sub, it in patterns:
        for r in rows:
            if all(p is None or re.search(p, v or "", re.I) for p, v in ((ty, r["type"]), (sub, r["subtype"]), (it, r["item"]))):
                return r
    return None


def seed_pmc(conn, *, helpdesk: str, procurement: str, apply: bool, at: datetime, actor: str) -> list[str]:
    """The PMC starter set. Returns what it did (or would do), line by line.
    Never changes a tile or a question that is already there (by name)."""
    if not available(conn):
        raise ValueError("Step 078 is not applied to this store: there is no portal_tile table.")
    boards = {H: helpdesk, P: procurement}
    names = {}
    for k, b in boards.items():
        r = conn.execute("SELECT display_name FROM board WHERE board_id = ?", (b,)).fetchone()
        if r is None:
            raise ValueError(f"No board {b!r}.")
        names[b] = r["display_name"]
        if not _board_ok(conn, b):
            raise ValueError(f"{b} is not a live board that takes requests.")
    out, added_t, added_q = [], 0, 0

    def existing(label, parent):
        return conn.execute("SELECT tile_id FROM portal_tile WHERE LOWER(label) = LOWER(?) AND "
                            + ("parent_id IS NULL" if parent is None else "parent_id = ?"),
                            (label,) if parent is None else (label, parent)).fetchone()

    def ask(tid, qs, indent):
        nonlocal added_q
        for label, kind, req in qs:
            if tid is not None and conn.execute("SELECT 1 FROM portal_tile_question WHERE tile_id = ? AND LOWER(label) = LOWER(?)",
                                                (tid, label)).fetchone():
                continue
            out.append(f"{indent}+ asks  {label}  ({FIELD_TYPES[kind].lower()}{', needed' if req else ''})")
            added_q += 1
            if apply and tid is not None:
                add_question(conn, tid, label=label, field_type=kind, required=req, at=at, actor=actor)

    for n, spec in enumerate(STARTER, 1):
        board = boards[spec["board"]]
        row = existing(spec["label"], None)
        if row:
            out.append(f"= tile  {spec['label']}  (already there, left as it is)")
            tid = row["tile_id"]
        else:
            out.append(f"+ tile  {spec['label']}  -> {names[board]}")
            added_t += 1
            tid = add_tile(conn, label=spec["label"], hint=spec["hint"], icon=spec["icon"], board_id=board,
                           sort_order=spec.get("sort", n * 10), at=at, actor=actor) if apply else None
        ask(tid, spec["questions"], "    ")
        for m, (label, patterns) in enumerate(spec["subs"], 1):
            if tid is not None and existing(label, tid):
                out.append(f"    = {label}  (already there)")
                continue
            pair = _find_pair(conn, patterns)
            sub_board = board
            if pair is not None and pair["default_board_id"] in boards.values():
                sub_board = pair["default_board_id"]           # the live catalogue's own routing wins
            if pair is not None:
                from . import itil
                try:
                    itil.resolve(conn, sub_board, item=conn.execute(
                        "SELECT * FROM catalogue_item WHERE catalogue_item_id = ?", (pair["catalogue_item_id"],)).fetchone())
                except itil.NotAccepted:
                    pair = None
            where = names[sub_board] + (f" · {pair['type']} › {pair['subtype']} › {pair['item']}" if pair else
                                        " · no catalogue match: the ticketer classifies it (set one in Setup › Portal tiles)")
            out.append(f"    + {label}  -> {where}")
            added_t += 1
            if apply and tid is not None:
                add_tile(conn, label=label, parent_id=tid, board_id=sub_board if sub_board != board else None,
                         catalogue_item_id=pair["catalogue_item_id"] if pair else None, sort_order=m * 10,
                         at=at, actor=actor)
    out.append("+ Something else, or not sure  (always there: the plain form, as today; no row)")
    out.append(f"{'Added' if apply else 'Would add'} {added_t} tile(s) and {added_q} question(s)."
               + ("" if apply else " Preview only: nothing was written. Run again with --apply."))
    return out


# ------------------------------------------------------------------ what is usually ticketed
#
# Dada, 9 Oct 2026: "check the ticketing for previous errors so u can have a
# read to what is usually ticketed". The live tickets are on SQL01 and their
# summaries can carry a patient's or a person's name, so this reads them where
# they are and prints counts only: never a summary, a name or a reference. It
# writes nothing. The keyword families are the starter tiles', so the output
# says how many past tickets each tile would have caught, and how many none.

FAMILIES = [
    ("Computer or laptop", r"\b(pc|computer|desktop|laptop|monitor|screen|mouse|keyboard|cpu|nuc|ups|avr)\b"),
    ("Printer or scanner", r"\b(print\w*|toner|ink|scan\w*|label|barcode)\b"),
    ("Can't log in, or a password", r"\b(password|log ?in|login|log-in|sign ?in|locked|unlock|account|access)\b"),
    ("Email and Teams", r"\b(e-?mail|outlook|teams|mailbox|o365|office ?365)\b"),
    # not "his" alone (the everyday word) and not "system" (too wide): BizBox's own words
    ("BizBox or a hospital system", r"\b(bizbox|his module|pis|pharmacy|philhealth|eclaims?|mms|fms|lis|ris|pacs)\b"),
    ("PMC Portal, Payroll and PMC apps", r"\b(pmc portal|employee portal|payroll|payslip|pay ?slip|attendance|biometric|"
                                        r"leave|premiere|homebase|queu\w*|kiosk|power ?bi|analytics|imaging)\b"),
    ("Network, Wi-Fi or internet", r"\b(wi-?fi|wifi|internet|network|lan|cable|connection|offline|no connection|"
                                   r"router|switch|ethernet)\b"),
    ("Set up something new, or get access", r"\b(new user|new account|install\w*|set ?up|transfer|move|relocat\w*|"
                                            r"deploy\w*|create)\b"),
    ("Buy something", r"\b(purchase|request for|property request|procure\w*|quotation|canvass|buy|order|requisition|"
                      r"pr\b|supplies)\b"),
    ("Stock, a delivery or a PO", r"\b(po|purchase order|deliver\w*|invoice|supplier|vendor|stock|inventory|receiv\w*|"
                                  r"item code|product)\b"),
    ("(no starter tile) Phone or extension", r"\b(phone|telephone|extension|ip ?phone|landline|trunk)\b"),
    ("(no starter tile) CCTV", r"\b(cctv|camera|nvr|dvr)\b"),
]


def topics(conn, *, since: str, top: int = 25) -> list[str]:
    """Counts of what was ticketed since `since` ('YYYY-MM-DD'): per board,
    classified or not; the most used Type › Subtype › Item; and how many
    summaries each tile's words would catch. Never prints a summary."""
    out = [f"Tickets opened since {since} (counts only; no summary, name or reference is printed)"]
    rows = conn.execute(
        "SELECT t.board_id, b.display_name, COUNT(*) AS n,"
        "       SUM(CASE WHEN t.catalogue_item_id IS NULL THEN 0 ELSE 1 END) AS classified"
        "  FROM ticket t JOIN board b ON b.board_id = t.board_id WHERE t.opened_at >= ?"
        " GROUP BY t.board_id, b.display_name ORDER BY COUNT(*) DESC", (since,)).fetchall()
    total = sum(r["n"] for r in rows)
    out.append(f"  all boards: {total}")
    for r in rows:
        out.append(f"  {r['display_name']} ({r['board_id']}): {r['n']}, of which {r['classified'] or 0} have a"
                   f" Type › Subtype › Item")
    out.append(f"Most used Type › Subtype › Item (top {top}):")
    pairs = conn.execute(
        "SELECT f.display_name AS type, c.display_name AS subtype, a.display_name AS item, t.board_id, COUNT(*) AS n"
        "  FROM ticket t JOIN catalogue_item i ON i.catalogue_item_id = t.catalogue_item_id"
        "  JOIN service_component c ON c.component_id = i.component_id"
        "  JOIN service_family f ON f.family_id = c.family_id JOIN service_action a ON a.action_id = i.action_id"
        " WHERE t.opened_at >= ? GROUP BY f.display_name, c.display_name, a.display_name, t.board_id"
        " ORDER BY COUNT(*) DESC", (since,)).fetchall()
    for r in pairs[:top]:
        out.append(f"  {r['n']:>5}  {r['type']} › {r['subtype']} › {r['item']}  [{r['board_id']}]")
    if not pairs:
        out.append("  (none classified)")
    out.append("What each tile's words would have caught in the summaries (a rough net: a ticket can count under"
               " more than one, and a word can miss):")
    compiled = [(label, re.compile(rx, re.I)) for label, rx in FAMILIES]
    hits = {label: {} for label, _ in compiled}
    none, missed = {}, {}
    for r in conn.execute(
            "SELECT t.board_id, w.name, f.display_name AS type, c.display_name AS subtype"
            "  FROM ticket t JOIN work_item w ON w.work_item_id = t.work_item_id"
            "  LEFT JOIN catalogue_item i ON i.catalogue_item_id = t.catalogue_item_id"
            "  LEFT JOIN service_component c ON c.component_id = i.component_id"
            "  LEFT JOIN service_family f ON f.family_id = c.family_id"
            " WHERE t.opened_at >= ?", (since,)):
        caught = False
        for label, rx in compiled:
            if rx.search(r["name"] or ""):
                hits[label][r["board_id"]] = hits[label].get(r["board_id"], 0) + 1
                caught = True
        if not caught:
            none[r["board_id"]] = none.get(r["board_id"], 0) + 1
            # 9 Oct 2026 (Dada: "yes build it"): what the desk itself called the
            # ones no tile's words caught, so a missing tile shows by name
            key = (f"{r['type']} › {r['subtype']}" if r["type"] else "(no Type › Subtype › Item yet)", r["board_id"])
            missed[key] = missed.get(key, 0) + 1
    for label, _ in compiled:
        by = hits[label]
        out.append(f"  {sum(by.values()):>5}  {label}" + (
            "  (" + ", ".join(f"{b} {n}" for b, n in sorted(by.items(), key=lambda x: -x[1])) + ")" if by else ""))
    out.append(f"  {sum(none.values()):>5}  caught by no tile's words  ("
               + ", ".join(f"{b} {n}" for b, n in sorted(none.items(), key=lambda x: -x[1])) + ")")
    if missed:
        out.append(f"Of the {sum(none.values())} no tile's words caught, how the desk classified them"
                   f" (Type › Subtype, top {top}):")
        for (name, board_id), n in sorted(missed.items(), key=lambda x: (-x[1], x[0]))[:top]:
            out.append(f"  {n:>5}  {name}  [{board_id}]")
        if len(missed) > top:
            out.append(f"  {sum(n for _, n in sorted(missed.items(), key=lambda x: (-x[1], x[0]))[top:]):>5}"
                       f"  in {len(missed) - top} more Type › Subtype")
    return out


def without_item(conn) -> list[str]:
    """12 Oct 2026 (Dada: "when they pick ... type subtype and item can be
    auto picked"): the tiles a request is raised from that carry no Type ›
    Subtype › Item of their own or from their parent, so the ticketer still
    classifies those by hand. Labels only. Set them in Setup › Portal tiles."""
    if not available(conn):
        return []
    out = []
    for tile in conn.execute("SELECT * FROM portal_tile WHERE inactive = 0 ORDER BY sort_order, label").fetchall():
        if children(conn, tile["tile_id"]):
            continue
        try:
            r = route(conn, tile["tile_id"])
        except LookupError:
            continue
        if not r["catalogue_item_id"]:
            out.append((f"{r['parent']['label']} › " if r["parent"] else "") + tile["label"])
    return out
