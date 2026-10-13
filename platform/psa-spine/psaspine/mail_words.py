"""Each board's own words for its requester emails (Dada, 12 Oct 2026).

"the messages or replies are very robotic can we please do specific replies for
procurement board and the pmo helpdesk board and make it more human and fit for
the hospital". Confirmed before building: warm and plain, first names, what
happens next; the help desk talks about checking it on the ward, Procurement
about quotes, approval and delivery.

Nothing new is stored: these are the same per-board words a person can write on
Setup > board > Emails (057 `mail_template` for opened, replied and closed; 058
`status_mail` for each status and for picked up). `apply_words` writes them, in
a preview first, and never overwrites words someone on the desk already wrote
for a board unless asked to (`replace`). Whether a status emails at all is not
touched: that stays the board's own switch.

Every sentence avoids starting with {owner}, which reads "the PMO Helpdesk
team" while nobody owns the ticket. Only the placeholders the desk allows are
used; there is no {summary}, so nothing a requester typed leaves in a subject.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from . import outbox

_SIGN = "\n\nThanks,\n{board}\n{hospital}"
_HI = "Hi {requester},\n\n"
_REPLY = "just reply to this email"


def _w(subject: str, body: str, *, sign: bool = True) -> tuple[str, str]:
    return subject, _HI + body + (_SIGN if sign else "")


# ------------------------------------------------------------ PMO Helpdesk
_HD_WARD = ("\n\nIf this is stopping patient care right now, please call the PMO Helpdesk and quote {ticket} "
            "so we can help straight away.")
HELPDESK = {
    "kinds": {
        "OPENED": _w("We've got your request",
                     "Thanks for letting us know. We've got your request, and {owner} will take care of it.\n\n"
                     "There's nothing else you need to do for now. We'll email you as soon as there's news." + _HD_WARD),
        "UPDATED": _w("New reply on your request",
                      "Here's the latest from {owner}:\n\n{note}\n\nIf you'd like to answer, " + _REPLY + "."),
        "CLOSED": _w("Your request is closed",
                     "We've closed your request. Thank you for your patience while we sorted it out.\n\n"
                     "If it's still giving you trouble, " + _REPLY + " and we'll reopen it. And if you have a minute, "
                     "you can rate how we did on the PMC Requests portal."),
    },
    "pickup": _w("{owner} has picked up your request",
                 "Your request is with {owner}, who has started on it now.\n\n"
                 "If anything else is needed, we'll be in touch. You can add details any time by replying to this "
                 "email." + _HD_WARD),
    "statuses": {
        "new": _w("We've got your request",
                  "We've got your request and it's in our queue. Someone from the PMO Helpdesk will pick it up "
                  "shortly.\n\nThere's nothing else you need to do for now." + _HD_WARD),
        "assigned": _w("Your request has been assigned",
                       "Your request is now with {owner}, who will take it from here.\n\n"
                       "Nothing you need to do for now. We'll keep you posted."),
        "in progress": _w("We're working on your request",
                          "Your request is with {owner}, who is working on it now.\n\n"
                          "We'll let you know as soon as it's done."),
        "scheduled": _w("A visit is planned for your request",
                        "We've planned a time to come and sort out your request, and {owner} will be in touch "
                        "about when.\n\nIf the time doesn't suit the ward, " + _REPLY + " and we'll find another."),
        "waiting on requester": _w("We need a little more from you",
                                   "To keep going on your request, we need a bit more information from you.\n\n"
                                   "Could you reply to this email with the details? The ward, the room, the machine "
                                   "or a photo of the error all help. Please don't include patient names or numbers."),
        "waiting on vendor": _w("We're waiting on the supplier",
                                "We've raised your request with the supplier and we're waiting to hear back from "
                                "them.\n\nWe haven't forgotten about it. We'll update you as soon as they respond."),
        "waiting on parts": _w("We're waiting for a part",
                               "We need a replacement part to fix this, and we're waiting for it to arrive.\n\n"
                               "We'll be in touch as soon as it's here and we can finish the job."),
        "waiting on bizbox": _w("We've asked the BizBox team",
                                "This one needs the BizBox support team, so we've raised it with them and we're "
                                "waiting for their answer.\n\nWe'll update you as soon as we hear back."),
        "awaiting approval": _w("Your request is waiting for approval",
                                "Your request needs an approval before we can go ahead. We've asked for it, and "
                                "we'll carry on as soon as it's approved."),
        "on hold": _w("Your request is on hold",
                      "We've put your request on hold for now. It's still with {owner}, and we'll let you know "
                      "as soon as it moves again."),
        "resolved": _w("Good news: your request is fixed",
                       "Good news: {owner} has fixed your request.\n\nCould you check it on the ward when you get a "
                       "moment? If it's still not right, " + _REPLY + " and it comes straight back to us."),
        "cancelled": _w("Your request has been cancelled",
                        "We've cancelled this request, so we won't be doing any more work on it.\n\n"
                        "If that's a mistake, or you still need help, " + _REPLY + " and we'll pick it up again."),
        "closed": _w("Your request is closed",
                     "We've closed your request. Thank you for your patience while we sorted it out.\n\n"
                     "If it's still giving you trouble, " + _REPLY + " and we'll reopen it."),
    },
}

# ------------------------------------------------------------ Procurement
_PR_URGENT = "\n\nIf this is urgent for patient care, please call Procurement and quote {ticket}."
PROCUREMENT = {
    "kinds": {
        "OPENED": _w("We've got your request",
                     "Thanks for your request. Procurement has it, and {owner} will look after it.\n\n"
                     "We'll email you at each step, from quotations and approval through to delivery." + _PR_URGENT),
        "UPDATED": _w("New reply on your request",
                      "Here's the latest from {owner} in Procurement:\n\n{note}\n\nIf you'd like to answer, "
                      + _REPLY + "."),
        "CLOSED": _w("Your request is closed",
                     "We've closed your request. Thank you for your patience.\n\nIf anything is still missing or "
                     "not right, " + _REPLY + " and we'll reopen it."),
    },
    "pickup": _w("{owner} has picked up your request",
                 "Your request is with {owner} in Procurement, who has started on it now.\n\n"
                 "We'll email you at each step. You can add details any time by replying to this email."),
    "statuses": {
        "new": _w("We've got your request",
                  "We've got your request and it's in Procurement's queue. Someone will pick it up shortly.\n\n"
                  "There's nothing else you need to do for now." + _PR_URGENT),
        "for quotation": _w("We're getting quotations",
                            "We're now asking suppliers for quotations for your request. Once we have them, it "
                            "goes for approval.\n\nThere's nothing you need to do for now."),
        "for approval": _w("Your request is waiting for approval",
                           "We have the quotations, and the purchase is now waiting for approval. We'll let you "
                           "know as soon as it's approved."),
        "approved": _w("Your purchase is approved",
                       "Good news: the purchase for your request has been approved. Next, we'll raise the purchase "
                       "order with the supplier."),
        "po raised": _w("Purchase order raised",
                        "We've raised the purchase order for your request and it's going to the supplier.\n\n"
                        "We'll let you know once it's ordered."),
        "ordered": _w("Your item has been ordered",
                      "Your request has been ordered from the supplier. We'll let you know as soon as it arrives "
                      "at the hospital.\n\nThere's nothing you need to do for now."),
        "delivered": _w("Your item has arrived",
                        "Your item has been delivered to the hospital. We're checking it and receiving it in, and "
                        "we'll let you know when it's ready for you."),
        "for receiving": _w("Your item is being received",
                            "Your item has arrived and is being received into stock. We'll let you know as soon as "
                            "it's ready to be issued to you."),
        "for payment": _w("Your item has been received",
                          "Your item has been received, and the supplier's invoice is now with Finance.\n\n"
                          "There's nothing you need to do."),
        "issued": _w("Your item has been issued",
                     "Good news: your item has been issued to you.\n\nPlease check that everything is right. If "
                     "anything is missing or wrong, " + _REPLY + " and we'll sort it out."),
        "waiting on bizbox": _w("We've asked the BizBox team",
                                "Your request needs the BizBox support team, so we've raised it with them and we're "
                                "waiting for their answer.\n\nWe'll update you as soon as we hear back."),
        "on hold": _w("Your request is on hold",
                      "We've put your request on hold for now. It's still with {owner}, and we'll let you know "
                      "as soon as it moves again."),
        "cancelled": _w("Your request has been cancelled",
                        "We've cancelled this request, so we won't be buying anything for it.\n\n"
                        "If that's a mistake, or you still need it, " + _REPLY + " and we'll pick it up again."),
        "closed": _w("Your request is closed",
                     "We've closed your request. Thank you for your patience.\n\nIf anything is still missing or "
                     "not right, " + _REPLY + " and we'll reopen it."),
    },
}

SETS = {"HELPDESK": HELPDESK, "PROCUREMENT": PROCUREMENT}


def _key(status_name: str) -> str:
    return " ".join(str(status_name or "").lstrip(">").split()).casefold()


def apply_words(conn: sqlite3.Connection, board_id: str, which: str, *, apply: bool, replace: bool,
                at: datetime, actor: str) -> list[str]:
    """Write one board's words. Returns the preview lines: one per email,
    `+` written, `=` already these words, `~` the board's own words kept
    (`replace` to overwrite), `?` a status with no words here (the desk's
    defaults stay)."""
    words = SETS[which]
    if conn.execute("SELECT 1 FROM board WHERE board_id = ?", (board_id,)).fetchone() is None:
        raise ValueError(f"no board {board_id!r}")
    lines: list[str] = []
    counts = {"+": 0, "=": 0, "~": 0, "?": 0}

    def note(mark: str, what: str, subject: str = "") -> None:
        counts[mark] += 1
        lines.append(f"{mark} {what}" + (f"  \"{subject}\"" if subject else ""))

    for kind, (subject, body) in words["kinds"].items():
        cur = outbox.template(conn, board_id, kind)
        label = outbox.TEMPLATE_KINDS[kind]
        if (cur["subject"], cur["body"]) == (subject, body):
            note("=", label)
        elif cur["custom"] and not replace:
            note("~", label + " (the board's own words kept)")
        else:
            note("+", label, subject)
            if apply:
                outbox.set_template(conn, board_id, kind, subject=subject, body=body, at=at, actor=actor)

    def one(cur: dict, wanted: tuple[str, str] | None, label: str, setter) -> None:
        if wanted is None:
            note("?", label + " (no words here: the desk's own stay)")
            return
        subject, body = wanted
        # Words equal to the desk's own are stored as NULL (outbox._set_mail), so
        # such a row never reads custom: compare the words themselves (Part 77).
        if (cur["subject"], cur["body"]) == (subject, body):
            note("=", label)
        elif cur["custom"] and not replace:
            note("~", label + " (the board's own words kept)")
        else:
            note("+", label, subject)
            if apply:
                setter(enabled=cur["enabled"], at=at, actor=actor, subject=subject, body=body)

    cur = outbox.pickup_mail(conn, board_id)
    one(cur, words["pickup"], "Picked up",
        lambda **kw: outbox.set_pickup_mail(conn, board_id, **kw))
    for m in outbox.status_mails(conn, board_id):
        one(m, words["statuses"].get(_key(m["name"])), f"Status {m['name']}" + ("" if m["enabled"] else " (email off)"),
            lambda _id=m["board_status_id"], **kw: outbox.set_status_mail(conn, _id, **kw))
    lines.append(f"{'Wrote' if apply else 'Would write'} {counts['+']} email(s); {counts['=']} already so; "
                 f"{counts['~']} kept as the board wrote them; {counts['?']} left on the desk's words."
                 + ("" if apply else " Preview only"))
    return lines
