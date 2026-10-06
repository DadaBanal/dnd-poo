"""Members: the people who work the desk, as records (053).

The identifier every table already carries (board_member.member,
member_role.member, member_capacity.member, oncall_slot.member,
time_entry, local_account.username) is the key. This module puts a record
beside it: a name, how to reach them, where they sit, who they report to,
who approves their week, the day they left. A member with no row is what
they were before 053: an identifier with a name from the AD contact import
when it has one.

Deactivation is the reference PSA's MemberDeactivation family in one
function: it ends the memberships, the future on-call slots, the approver
and reports-to duties and the local account, and says what it did.
Nothing is deleted from the history: time booked, notes written and tickets
owned keep the identifier. Every change is audited (MEMBER).
"""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import date, datetime

from . import db

FIELDS = ("display_name", "title", "email", "phone", "mobile", "department", "location", "reports_to",
          "default_board_id", "work_role_id", "time_approver", "notes")
WIDTH = {"display_name": 200, "title": 200, "email": 200, "phone": 32, "mobile": 32, "department": 200,
         "location": 200, "notes": 4000}


class Refused(ValueError):
    """A sentence for the person; nothing was written."""


def _stamp(at: datetime) -> str:
    return at.isoformat(sep=" ", timespec="minutes")


def _text(value, width: int) -> str | None:
    return " ".join(str(value or "").split())[:width] or None


def _audit(conn, at: datetime, actor: str, member: str, detail: str) -> None:
    db.audit(conn, at=_stamp(at), actor=actor, action="MEMBER", subject_kind="member", subject_id=member,
             detail=detail)


# ------------------------------------------------------------ who exists

def identifiers(conn: sqlite3.Connection) -> list[str]:
    """Every identifier the desk knows, however it came to know it: a record,
    a board membership, a role, a capacity, a break-glass account. One entry
    per identifier, the first spelling seen kept."""
    seen: dict[str, str] = {}
    for sql in ("SELECT member FROM member", "SELECT member FROM board_member", "SELECT member FROM member_role",
                "SELECT member FROM member_capacity", "SELECT username FROM local_account"):
        for (m,) in conn.execute(sql):
            if m and m.lower() not in seen:
                seen[m.lower()] = m
    return sorted(seen.values(), key=str.lower)


def exists(conn: sqlite3.Connection, member: str) -> bool:
    m = (member or "").strip().lower()
    return bool(m) and m in {x.lower() for x in identifiers(conn)}


def for_sign_in(conn: sqlite3.Connection, address: str | None) -> str | None:
    """The desk identifier for a person who signed in with an address -- a
    Microsoft (Entra) account's UPN or email -- or None when there is no address.

    Dada, 6 Oct 2026: Ethel, on the Procurement board, saw *"the old menu"* and
    a board that *"does not look like the PMO helpdesk board"*. The Windows
    door has always turned `PMCNE\\ethel.luciano` or `ethel.luciano@pmcne.ph`
    into `ethel.luciano`, the identifier her board membership, her owner
    column and her sysadmin flag are kept under. The Microsoft door did not: it
    used the account's object GUID, which matches no row anywhere, so a member
    signing in that way was on no board -- and a person on no board is drawn
    the three-link requester shell, whose `/` is My requests. One person, two
    identities, depending on the button they pressed.

    So both doors now arrive at the same name, in this order:

    1. a member record whose email is this address -- exact, and the only way a
       mailbox on a second domain finds its member;
    2. an identifier the desk already knows (a member, a board membership, a
       role, a break-glass account) equal to the address's local part, which is
       exactly the rule the Windows door applies;
    3. otherwise the local part itself, lower case, so a requester who signs in
       either way is still one person.
    """
    addr = (address or "").strip().lower()
    if not addr:
        return None
    row = conn.execute("SELECT member FROM member WHERE LOWER(email) = ?", (addr,)).fetchone()
    if row:
        return row["member"]
    local = addr.split("@", 1)[0]
    if "\\" in local:
        local = local.split("\\", 1)[1]
    for known in identifiers(conn):
        if known.lower() == local:
            return known
    return local or None


def _contact(conn, member: str):
    from .web import auth
    return auth.contact_for_account(conn, (member or "").lower())


def name_of(conn: sqlite3.Connection, member: str) -> str:
    """The name to show for an identifier: the record's, else the AD
    contact's, else the identifier."""
    row = conn.execute("SELECT display_name FROM member WHERE LOWER(member) = LOWER(?)", (member,)).fetchone()
    if row and row["display_name"]:
        return row["display_name"]
    c = _contact(conn, member)
    return c["display_name"] if c else member


def get(conn: sqlite3.Connection, member: str) -> dict | None:
    """One person: the record (or its AD fallback), role, boards, capacity,
    the local account, whether they are active."""
    if not exists(conn, member):
        return None
    from . import security, timesheets
    row = conn.execute("SELECT m.*, b.display_name AS default_board_name, w.name AS work_role_name FROM member m"
                       " LEFT JOIN board b ON b.board_id = m.default_board_id"
                       " LEFT JOIN work_role w ON w.work_role_id = m.work_role_id"
                       " WHERE LOWER(m.member) = LOWER(?)", (member,)).fetchone()
    out = {k: None for k in FIELDS}
    out.update({"member": member, "inactive_from": None, "is_sysadmin": 0, "default_board_name": None, "work_role_name": None,
                "created_at": None, "created_by": None, "updated_at": None, "updated_by": None, "has_record": False})
    if row:
        out.update(dict(row))
        out["has_record"] = True
    contact = _contact(conn, member)
    if contact:
        out["display_name"] = out["display_name"] or contact["display_name"]
        out["email"] = out["email"] or contact["email"]
        out["department"] = out["department"] or contact["department"]
    out["display_name"] = out["display_name"] or out["member"]
    out["role_id"] = security.role_of(conn, out["member"])
    out["role_name"] = next((r["name"] for r in security.roles(conn) if r["role_id"] == out["role_id"]), None) \
        if out["role_id"] else None
    out["boards"] = boards_of(conn, out["member"])
    out["hours_per_week"] = timesheets.capacity(conn, out["member"])
    la = conn.execute("SELECT is_sysadmin, disabled, last_login_at FROM local_account WHERE LOWER(username) = LOWER(?)",
                      (out["member"],)).fetchone()
    out["local_account"] = dict(la) if la else None
    out["active"] = out["inactive_from"] is None
    return out


def boards_of(conn: sqlite3.Connection, member: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT bm.board_id, b.display_name, bm.access, bm.team_id, t.name AS team_name"
        "  FROM board_member bm JOIN board b ON b.board_id = bm.board_id"
        "  LEFT JOIN board_team t ON t.team_id = bm.team_id"
        " WHERE LOWER(bm.member) = LOWER(?) ORDER BY b.display_name", (member,))]


def all_(conn: sqlite3.Connection, *, q: str = "", include_inactive: bool = False) -> list[dict]:
    """Everyone, one row each: name, role, boards, capacity, local account,
    active. The list is the union of every identifier the desk knows."""
    from . import security
    security.ensure_roles(conn)
    records = {r["member"].lower(): dict(r) for r in conn.execute("SELECT * FROM member")}
    roles = {r["member"].lower(): r["name"] for r in conn.execute(
        "SELECT m.member, r.name FROM member_role m JOIN security_role r ON r.role_id = m.role_id WHERE r.inactive = 0")}
    boards: dict[str, list[str]] = {}
    for r in conn.execute("SELECT bm.member, b.display_name FROM board_member bm JOIN board b ON b.board_id = bm.board_id"
                          " ORDER BY b.display_name"):
        boards.setdefault(r["member"].lower(), []).append(r["display_name"])
    caps = {r["member"].lower(): r["hours_per_week"] for r in conn.execute("SELECT member, hours_per_week FROM member_capacity")}
    locals_ = {r["username"].lower(): dict(r) for r in conn.execute(
        "SELECT username, is_sysadmin, disabled, last_login_at FROM local_account")}
    out = []
    needle = (q or "").strip().lower()
    for ident in identifiers(conn):
        key = ident.lower()
        rec = records.get(key, {})
        name = rec.get("display_name")
        email = rec.get("email")
        if not name or not email:
            c = _contact(conn, ident)
            if c:
                name = name or c["display_name"]
                email = email or c["email"]
        row = {"member": ident, "display_name": name or ident, "title": rec.get("title"), "email": email,
               "department": rec.get("department"), "role_name": roles.get(key), "boards": boards.get(key, []),
               "hours_per_week": caps.get(key), "local_account": locals_.get(key),
               "inactive_from": rec.get("inactive_from"), "has_record": key in records}
        if row["inactive_from"] and not include_inactive:
            continue
        if needle and needle not in " ".join(filter(None, (ident, row["display_name"], email or "", row["title"] or "",
                                                            row["department"] or ""))).lower():
            continue
        out.append(row)
    return out


# ------------------------------------------------------------ the record

def _clean(conn, fields: dict) -> dict:
    out = {}
    for k, v in fields.items():
        if k not in FIELDS:
            raise Refused(f"No such field: {k}.")
        if k in WIDTH:
            out[k] = _text(v, WIDTH[k])
        elif k in ("reports_to", "time_approver"):
            who = (v or "").strip()
            if who and not exists(conn, who):
                raise Refused(f"{who} is not a member the desk knows.")
            out[k] = who or None
        elif k == "default_board_id":
            bid = (v or "").strip() or None
            if bid and conn.execute("SELECT 1 FROM board WHERE board_id = ?", (bid,)).fetchone() is None:
                raise Refused("No such board.")
            out[k] = bid
        elif k == "work_role_id":
            wid = (v or "").strip() or None
            if wid and conn.execute("SELECT 1 FROM work_role WHERE work_role_id = ?", (wid,)).fetchone() is None:
                raise Refused("No such work role.")
            out[k] = wid
    if "email" in out and out["email"] and ("@" not in out["email"] or " " in out["email"]):
        raise Refused("The email address does not look like one.")
    return out


def add(conn: sqlite3.Connection, member: str, *, at: datetime, actor: str, **fields) -> str:
    """A new identifier with a record. The identifier is what the person
    signs in as: the AD account name, or an Entra object id."""
    ident = " ".join(str(member or "").split())
    if not ident or len(ident) > 200 or any(ch in ident for ch in "/?#%"):
        raise Refused("An identifier is the sign-in name: letters, digits, dots, no slashes.")
    if exists(conn, ident):
        raise Refused(f"{ident} is already a member; open their page.")
    f = _clean(conn, fields)
    stamp = _stamp(at)
    conn.execute("INSERT INTO member (member, display_name, title, email, phone, mobile, department, location, reports_to,"
                 " default_board_id, work_role_id, time_approver, notes, created_at, created_by, updated_at, updated_by)"
                 " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (ident, f.get("display_name"), f.get("title"), f.get("email"), f.get("phone"), f.get("mobile"),
                  f.get("department"), f.get("location"), f.get("reports_to"), f.get("default_board_id"),
                  f.get("work_role_id"), f.get("time_approver"), f.get("notes"), stamp, actor, stamp, actor))
    _audit(conn, at, actor, ident, f"added: {f.get('display_name') or ident}")
    return ident


def save(conn: sqlite3.Connection, member: str, *, at: datetime, actor: str, **fields) -> list[str]:
    """Write fields on a person's record, making the record if the identifier
    is known only from a membership or a role. Returns what changed."""
    if not exists(conn, member):
        raise Refused("No such member.")
    if (m := fields.get("reports_to")) and m.strip().lower() == member.lower():
        raise Refused("Nobody reports to themselves.")
    if (m := fields.get("time_approver")) and m.strip().lower() == member.lower():
        raise Refused("Nobody approves their own week.")
    f = _clean(conn, fields)
    stamp = _stamp(at)
    row = conn.execute("SELECT * FROM member WHERE LOWER(member) = LOWER(?)", (member,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO member (member, created_at, created_by, updated_at, updated_by) VALUES (?,?,?,?,?)",
                     (member, stamp, actor, stamp, actor))
        row = conn.execute("SELECT * FROM member WHERE LOWER(member) = LOWER(?)", (member,)).fetchone()
    changed = []
    for k, v in f.items():
        if v != row[k]:
            conn.execute(f"UPDATE member SET {k} = ? WHERE member = ?", (v, row["member"]))
            changed.append(f"{k} {row[k] if row[k] is not None else '-'} -> {v if v is not None else '-'}")
    if changed:
        conn.execute("UPDATE member SET updated_at = ?, updated_by = ? WHERE member = ?", (stamp, actor, row["member"]))
        _audit(conn, at, actor, row["member"], "; ".join(changed)[:900])
    return changed


# ------------------------------------------------------------ desk sysadmin

def is_sysadmin(conn: sqlite3.Connection, member: str) -> bool:
    """Whether the member record carries the desk's cross-board flag (062)."""
    row = conn.execute("SELECT is_sysadmin FROM member WHERE LOWER(member) = LOWER(?)", (member or "",)).fetchone()
    return bool(row and row["is_sysadmin"])


def sysadmins(conn: sqlite3.Connection) -> list[str]:
    """Every active member with the flag, by identifier."""
    return [r["member"] for r in conn.execute(
        "SELECT member FROM member WHERE is_sysadmin = 1 AND inactive_from IS NULL ORDER BY member")]


def set_sysadmin(conn: sqlite3.Connection, member: str, on: bool, *, at: datetime, actor: str) -> str:
    """Grant or take back the desk's sysadmin on a member record (062). Makes
    the record if the identifier is known only from a membership. Nobody
    changes their own, and the last one cannot be taken off, so the desk
    always has somebody who can run Setup > Members. Audited."""
    if member.strip().lower() == actor.strip().lower():
        raise Refused("Somebody else changes your own sysadmin flag.")
    if exists(conn, member):
        ident = next(x for x in identifiers(conn) if x.lower() == member.lower())
    elif on and _contact(conn, member.strip()):
        ident = member.strip().lower()            # an AD account the desk has not met yet: a record is made for it
    else:
        raise Refused("No such member.")
    stamp = _stamp(at)
    row = conn.execute("SELECT member, is_sysadmin, inactive_from FROM member WHERE LOWER(member) = LOWER(?)", (ident,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO member (member, created_at, created_by, updated_at, updated_by) VALUES (?,?,?,?,?)",
                     (ident, stamp, actor, stamp, actor))
        row = conn.execute("SELECT member, is_sysadmin, inactive_from FROM member WHERE member = ?", (ident,)).fetchone()
    if on and row["inactive_from"]:
        raise Refused("They have left; bring them back on the desk first.")
    if bool(row["is_sysadmin"]) == bool(on):
        return f"{ident} is already " + ("a sysadmin." if on else "not a sysadmin.")
    if not on and len(sysadmins(conn)) <= 1:
        raise Refused("The last sysadmin cannot be taken off; make somebody else one first.")
    conn.execute("UPDATE member SET is_sysadmin = ?, updated_at = ?, updated_by = ? WHERE member = ?",
                 (1 if on else 0, stamp, actor, row["member"]))
    _audit(conn, at, actor, row["member"], "desk sysadmin " + ("granted" if on else "taken off"))
    return f"{ident} is " + ("now a sysadmin." if on else "no longer a sysadmin.")


# ------------------------------------------------------------ memberships

def set_membership(conn: sqlite3.Connection, member: str, board_id: str, access: str | None, *,
                   at: datetime, actor: str, team_id: str | None = None) -> str:
    """Put a person on a board at an access level, or (access None) take them
    off it. The same rows the board's own tab writes."""
    if not exists(conn, member):
        raise Refused("No such member.")
    b = conn.execute("SELECT board_id, display_name FROM board WHERE board_id = ?", (board_id,)).fetchone()
    if b is None:
        raise Refused("No such board.")
    ident = next(x for x in identifiers(conn) if x.lower() == member.lower())
    if access is None:
        n = conn.execute("DELETE FROM board_member WHERE LOWER(member) = LOWER(?) AND board_id = ?", (ident, board_id)).rowcount
        if n:
            _audit(conn, at, actor, ident, f"off {b['display_name']}")
        return f"{ident} is off {b['display_name']}" if n else f"{ident} was not on {b['display_name']}"
    if access not in ("READ", "WORK", "ADMIN"):
        raise Refused("Access is READ, WORK or ADMIN.")
    if team_id and conn.execute("SELECT 1 FROM board_team WHERE team_id = ? AND board_id = ?", (team_id, board_id)).fetchone() is None:
        team_id = None
    conn.execute("DELETE FROM board_member WHERE LOWER(member) = LOWER(?) AND board_id = ?", (ident, board_id))
    conn.execute("INSERT INTO board_member (board_id, member, team_id, access) VALUES (?,?,?,?)", (board_id, ident, team_id, access))
    _audit(conn, at, actor, ident, f"{b['display_name']}: {access}")
    return f"{ident} is {access} on {b['display_name']}"


# ------------------------------------------------------------ leaving

def deactivate(conn: sqlite3.Connection, member: str, *, at: datetime, actor: str) -> list[str]:
    """The person has left. Ends what points at them and says what it did:
    board memberships, future on-call slots, the departments they approve
    for, the members who report to them or are approved by them, the
    break-glass account. History keeps the identifier."""
    if not exists(conn, member):
        raise Refused("No such member.")
    if member.lower() == actor.lower():
        raise Refused("Somebody else ends your membership; you cannot end your own.")
    row = conn.execute("SELECT inactive_from FROM member WHERE LOWER(member) = LOWER(?)", (member,)).fetchone()
    if row and row["inactive_from"]:
        raise Refused("Already inactive.")
    ident = next(x for x in identifiers(conn) if x.lower() == member.lower())
    stamp = _stamp(at)
    done: list[str] = []
    boards = [r["display_name"] for r in boards_of(conn, ident)]
    if boards:
        conn.execute("DELETE FROM board_member WHERE LOWER(member) = LOWER(?)", (ident,))
        done.append(f"taken off {len(boards)} board(s): " + ", ".join(boards))
    n = conn.execute("DELETE FROM oncall_slot WHERE LOWER(member) = LOWER(?) AND ends_at > ?", (ident, stamp)).rowcount
    if n:
        done.append(f"{n} future on-call slot(s) removed; the rota needs someone else there")
    email = (get(conn, ident) or {}).get("email")          # a department's approver is an email (049)
    deps = [r[0] for r in conn.execute("SELECT name FROM department WHERE LOWER(approver) = LOWER(?)", (email or "",))] if email else []
    if deps:
        conn.execute("UPDATE department SET approver = NULL WHERE LOWER(approver) = LOWER(?)", (email,))
        done.append("no longer the approver for: " + ", ".join(deps))
    reports = [r[0] for r in conn.execute("SELECT member FROM member WHERE LOWER(reports_to) = LOWER(?)", (ident,))]
    if reports:
        conn.execute("UPDATE member SET reports_to = NULL WHERE LOWER(reports_to) = LOWER(?)", (ident,))
        done.append("no longer reported to by: " + ", ".join(reports))
    approves = [r[0] for r in conn.execute("SELECT member FROM member WHERE LOWER(time_approver) = LOWER(?)", (ident,))]
    if approves:
        conn.execute("UPDATE member SET time_approver = NULL WHERE LOWER(time_approver) = LOWER(?)", (ident,))
        done.append("no longer the time approver for: " + ", ".join(approves))
    n = conn.execute("UPDATE local_account SET disabled = 1 WHERE LOWER(username) = LOWER(?) AND disabled = 0", (ident,)).rowcount
    if n:
        done.append("break-glass account disabled")
    conn.execute("DELETE FROM calendar_feed WHERE LOWER(member) = LOWER(?)", (ident,))
    if row is None:
        conn.execute("INSERT INTO member (member, created_at, created_by, updated_at, updated_by) VALUES (?,?,?,?,?)",
                     (ident, stamp, actor, stamp, actor))
    conn.execute("UPDATE member SET inactive_from = ?, updated_at = ?, updated_by = ? WHERE LOWER(member) = LOWER(?)",
                 (at.date().isoformat(), stamp, actor, ident))
    _audit(conn, at, actor, ident, "deactivated: " + ("; ".join(done) if done else "nothing pointed at them"))
    return done


def reactivate(conn: sqlite3.Connection, member: str, *, at: datetime, actor: str) -> None:
    """Back on the desk, with no memberships: those are given again on purpose."""
    row = conn.execute("SELECT inactive_from FROM member WHERE LOWER(member) = LOWER(?)", (member,)).fetchone()
    if row is None or not row["inactive_from"]:
        raise Refused("Not inactive.")
    conn.execute("UPDATE member SET inactive_from = NULL, updated_at = ?, updated_by = ? WHERE LOWER(member) = LOWER(?)",
                 (_stamp(at), actor, member))
    _audit(conn, at, actor, member, "reactivated; memberships are given again in Setup")


def is_inactive(conn: sqlite3.Connection, member: str) -> bool:
    row = conn.execute("SELECT inactive_from FROM member WHERE LOWER(member) = LOWER(?)", (member,)).fetchone()
    return bool(row and row["inactive_from"])


# ------------------------------------------------------------ the calendar feed

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def new_feed_token(conn: sqlite3.Connection, member: str, *, at: datetime) -> str:
    """Mint (or rotate) the person's feed token. Returned once; only its hash
    is kept, so a copy of the database is not a copy of anyone's calendar."""
    if not exists(conn, member):
        raise Refused("No such member.")
    token = "cal_" + secrets.token_urlsafe(24)
    conn.execute("DELETE FROM calendar_feed WHERE LOWER(member) = LOWER(?)", (member,))
    conn.execute("INSERT INTO calendar_feed (member, token_hash, created_at) VALUES (?,?,?)", (member, _hash(token), _stamp(at)))
    return token


def member_for_feed(conn: sqlite3.Connection, token: str) -> str | None:
    if not token or not token.startswith("cal_") or len(token) > 80:
        return None
    row = conn.execute("SELECT member FROM calendar_feed WHERE token_hash = ?", (_hash(token),)).fetchone()
    if row is None or is_inactive(conn, row["member"]):
        return None
    return row["member"]


def has_feed(conn: sqlite3.Connection, member: str) -> bool:
    return conn.execute("SELECT 1 FROM calendar_feed WHERE LOWER(member) = LOWER(?)", (member,)).fetchone() is not None


def today(at: datetime) -> date:
    return at.date()
