"""Who is typing in a chat, and which chat operators are on (chat round six).

Dada, 8 Oct 2026: "add a ... is typing for presence and also add to the requests
portal and the desk portal presence for the operators". Confirmed before
building: both sides of a chat see "... is typing"; an operator is online while
a desk page is open, away after about five minutes without one, and can set
Busy or Away by hand; the In/Out board's Out or On leave wins over all of it;
the portal shows how many are online and their first names; the desk shows
them in the Live chats quick view.

Kept in this process's memory, not in the database. It changes every few
seconds and means nothing after a restart, and a table would put a write on
every poll of every open page. INFERRED from the code: PSA-Desk is one process
(`psaspine serve`, threaded), so every page reads the same state. A restart
clears it: typing stops showing, operators read offline until their next page
loads, and a hand-set Busy or Away goes back to automatic.
"""
from __future__ import annotations

import threading
import time

TYPING_SECONDS = 6            # "... is typing" lasts this long after the last key
ONLINE_SECONDS = 5 * 60       # online while a desk page checks in (a hidden tab does about once a minute)
AWAY_SECONDS = 30 * 60        # then away; after this, offline
LIST_SECONDS = 30             # who the operators are (names, In/Out) is read again after this

MANUAL = {"BUSY": "Busy", "AWAY": "Away"}
WORDS = {"ONLINE": "Online", "BUSY": "Busy", "AWAY": "Away", "OFFLINE": "Offline", "OUT": "Out", "LEAVE": "On leave"}

_lock = threading.Lock()
_typing: dict[tuple[int, str], tuple[str, float]] = {}
_seen: dict[str, float] = {}
_manual: dict[str, str] = {}
_lists: dict[str | None, tuple[float, list]] = {}
clock = time.monotonic        # a test may swap it


def reset() -> None:
    """Forget everything, as a restart does. For tests."""
    with _lock:
        _typing.clear()
        _seen.clear()
        _manual.clear()
        _lists.clear()


def typing(chat_id: int, side: str, name: str) -> None:
    with _lock:
        _typing[(int(chat_id), side)] = (name, clock())


def stop_typing(chat_id: int, side: str) -> None:
    with _lock:
        _typing.pop((int(chat_id), side), None)


def who_is_typing(chat_id: int, side: str) -> str | None:
    """The name typing on that side of the chat, if a key went down lately."""
    with _lock:
        got = _typing.get((int(chat_id), side))
        if got and clock() - got[1] <= TYPING_SECONDS:
            return got[0]
        _typing.pop((int(chat_id), side), None)
        return None


def seen(member: str) -> None:
    """A desk page of theirs just asked for something."""
    if member:
        with _lock:
            _seen[member.lower()] = clock()


def set_manual(member: str, state: str | None) -> None:
    """BUSY or AWAY by hand; None (or anything else) is automatic again."""
    with _lock:
        if state in MANUAL:
            _manual[member.lower()] = state
        else:
            _manual.pop(member.lower(), None)


def manual_of(member: str) -> str | None:
    with _lock:
        return _manual.get((member or "").lower())


def state_of(member: str) -> str:
    """ONLINE, BUSY, AWAY or OFFLINE, from the desk alone (no In/Out board)."""
    key = (member or "").lower()
    with _lock:
        at, hand = _seen.get(key), _manual.get(key)
    if at is None:
        return "OFFLINE"
    ago = clock() - at
    if ago > AWAY_SECONDS:
        return "OFFLINE"
    if hand:
        return hand
    return "ONLINE" if ago <= ONLINE_SECONDS else "AWAY"


def _roster(conn, board_id: str | None) -> list[tuple[str, str, str | None]]:
    """(member, name, In/Out state) for the operators, read from the database
    at most every LIST_SECONDS: the ward's page asks every few seconds, and who
    the operators are changes far less often than that."""
    with _lock:
        got = _lists.get(board_id)
        if got and clock() - got[0] <= LIST_SECONDS:
            return got[1]
    from . import chat
    rows = []
    for member in chat.operators(conn, board_id):
        try:
            row = conn.execute("SELECT state FROM member_presence WHERE LOWER(member) = LOWER(?)", (member,)).fetchone()
        except Exception:                              # noqa: BLE001 - a store without the In/Out board
            row = None
        rows.append((member, chat._name(conn, member), row["state"] if row else None))
    with _lock:
        _lists[board_id] = (clock(), rows)
    return rows


def operators(conn, board_id: str | None = None) -> list[dict]:
    """The chat operators (of one board, or of every board that takes chats),
    each with their state: the In/Out board's Out or On leave first, then the
    desk's. Online first, then busy, away, and the rest; then by name. The
    states are always current; names and the In/Out board can be 30 s old."""
    out = []
    for member, name, inout in _roster(conn, board_id):
        state = inout if inout in ("OUT", "LEAVE") else state_of(member)
        out.append({"member": member, "name": name, "first": (name.split() or [member])[0], "state": state,
                    "word": WORDS[state], "on": state in ("ONLINE", "BUSY")})
    rank = {"ONLINE": 0, "BUSY": 1, "AWAY": 2}
    return sorted(out, key=lambda o: (rank.get(o["state"], 3), o["name"].lower()))
