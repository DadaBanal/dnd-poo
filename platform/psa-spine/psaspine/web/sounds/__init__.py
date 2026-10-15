"""The sounds a new chat or a new ticket can make (Dada, 15 Oct 2026: "add the oh my god and all the other
notification bells on to choose from for the new chat notification", "also add fwahhh", "all the other catchy
ones", "dont repeat just do it once", and "for new tickets and newchats add a picker beside the theme picker").

Each person picks one for each, from the bell beside the theme button; the choice lives in their browser. The
desk phone ring is made by the page itself (Web Audio, no file); the rest are MP3s kept here and served by the
desk, so ringing never reaches outside. Where each file came from: SOURCES.md beside them.
"""
from __future__ import annotations

from pathlib import Path

DIR = Path(__file__).resolve().parent

# (key, what the picker says, file). The phone ring needs no file.
SOUNDS = (
    ("phone", "Desk phone ring", None),
    ("oh-my-god", "Oh my god", "oh-my-god.mp3"),
    ("oh-my-god-loud", "OH MY GOD (loud)", "oh-my-god-loud.mp3"),
    ("fah", "Fahhh", "fah.mp3"),
    ("vine-boom", "Vine boom", "vine-boom.mp3"),
    ("bruh", "Bruh", "bruh.mp3"),
    ("anime-wow", "Anime wow", "anime-wow.mp3"),
    ("metal-pipe", "Metal pipe", "metal-pipe.mp3"),
    ("ka-ching", "Ka-ching", "ka-ching.mp3"),
    ("ding-dong", "Ding dong", "ding-dong.mp3"),
    ("bell-notification", "Bell", "bell-notification.mp3"),
    ("notification-bell", "Notification bell", "notification-bell.mp3"),
    ("bell-ring", "Bell ring", "bell-ring.mp3"),
    ("soft-bell", "Soft bell", "soft-bell.mp3"),
    ("off", "No sound", None),
)
FILES = {k: f for k, _, f in SOUNDS if f}
KINDS = (("chat", "New chat"), ("ticket", "New ticket"))


def picker(kind: str) -> str:
    """One labelled picker. The page's script selects the person's choice and
    plays each one as it is picked, so choosing is also hearing it."""
    from ..templates import esc
    word = dict(KINDS)[kind]
    opts = "".join(f"<option value='{esc(k)}'>{esc(w)}</option>" for k, w, _ in SOUNDS)
    return (f"<label for=snd-{kind}>{esc(word)}</label>"
            f"<select id=snd-{kind} class=tpick data-for={kind}>{opts}</select>")


def header_button() -> str:
    """The bell beside the theme button, and what it opens."""
    from ..templates import icon
    return ("<button class=iconbtn type=button popovertarget=soundpick title='Sounds for a new chat and a new ticket'"
            f" aria-label='Sounds for a new chat and a new ticket'>{icon('bell')}</button>"
            "<div id=soundpick popover class=soundpop><h4>Sounds</h4>"
            + "".join(picker(k) for k, _ in KINDS) +
            "<p class=why>Kept in this browser. Choosing one plays it; each new chat or ticket plays it once.</p></div>")


def serve(ctx, name):
    """One of the files above, and nothing else: the name is looked up, never
    joined onto a path."""
    from .. import HttpError, Response
    f = FILES.get(str(name))
    if f is None:
        raise HttpError("404 Not Found", "No such sound.")
    return Response(body=(DIR / f).read_bytes(), content_type="audio/mpeg",
                    headers=[("Cache-Control", "private, max-age=604800")])
