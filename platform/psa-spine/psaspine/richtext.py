"""A note written as rich text, and the one gate every word of it passes.

Dada, 2 Oct 2026: *"also copy pasting and a proper text editor via html or
like html or teams text editor"*. A technician writes a note the way they
write a Teams message: bold, a list, a link, and whatever they paste out of
Outlook or Word. So a note may now be HTML.

That is only safe because of one rule, and this module is the only place it is
written: **nothing reaches the database until `clean` has rebuilt it**. The
parser here does not strip what it dislikes from a string; it reads the input
and emits a new document made only of the tags and attributes on these lists.
Anything else - a script, an event handler, a style, an iframe, a `javascript:`
address, Word's thousand lines of mso markup - is not removed, it is simply
never written. A note that arrives as plain text is left as plain text, and
`templates.rich` reads it as it always did.

`text` goes the other way: the words without the markup, for the things that
want words. The PHI scan reads that, never the markup, so a patient's name
cannot hide inside an attribute.
"""

from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser

# What a note may contain. A technician's formatting, and nothing that can act.
BLOCK = ("p", "div", "ul", "ol", "li", "blockquote", "pre", "h3", "h4")
INLINE = ("b", "strong", "i", "em", "u", "s", "strike", "del", "code", "br", "a")
ALLOWED = set(BLOCK) | set(INLINE)
# Word and Outlook write <b> as <span style=font-weight:bold>; a span carries
# nothing we keep, so it is dropped and its words are kept.
UNWRAP = ("span", "font", "o:p", "body", "html", "head", "section", "article",
          "table", "tbody", "thead", "tr", "td", "th", "center", "small", "big")
# A table is unwrapped, not kept -- but a table laid out words in a grid, and
# dropping the grid without a trace runs "Ward 3" into "Sister Reyes" into the
# phone number. Email is written in tables (Outlook signatures, every layout a
# mail client has), so the end of a cell is worth a space and the end of a row
# a line. Nothing is kept that could act; only the spacing survives.
GAP = {"td": " ", "th": " "}
NEWLINE = ("tr",)
SAME = {"strong": "b", "em": "i", "strike": "s", "del": "s", "div": "p", "h1": "h3",
        "h2": "h3", "h5": "h4", "h6": "h4"}
VOID = {"br"}
# Only an address a browser may follow to somewhere a person can read.
LINK = re.compile(r"^(https?://|mailto:)", re.I)
MAX = 60_000                     # a note, not a document
# An email is a document. A ward's reply carries the whole quoted thread, a
# signature and Outlook's own markup, and 60 KB cuts it mid-sentence; what the
# gate caps is parse cost, not editorial length, so the door that takes email
# says so. Render-time re-cleaning uses this bound too, because by then the
# stored note may have come in by either door (064, both of them).
EMAIL_MAX = 400_000


class _Clean(HTMLParser):
    """Reads the input and writes a new document out of the lists above."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.open: list[str] = []
        self.skip = 0              # inside a tag whose words go too (script, style)

    # -------------------------------------------------------------- tags
    def handle_starttag(self, tag, attrs):
        tag = SAME.get(tag.lower(), tag.lower())
        if tag in ("script", "style", "title"):
            self.skip += 1
            return
        if self.skip:
            return
        if tag in UNWRAP or tag not in ALLOWED:
            return                 # its words are kept; the tag is not
        if tag == "a":
            href = ""
            for k, v in attrs:
                if k.lower() == "href" and v and LINK.match(v.strip()):
                    href = v.strip()
            if not href:
                return             # a link to nowhere a person can read is not a link
            self.out.append('<a href="%s" target="_blank" rel="noopener noreferrer">' % escape(href, quote=True))
            self.open.append("a")
            return
        if tag in VOID:
            self.out.append("<br>")
            return
        self.out.append("<%s>" % tag)
        self.open.append(tag)

    def handle_startendtag(self, tag, attrs):
        if not self.skip and SAME.get(tag.lower(), tag.lower()) in VOID:
            self.out.append("<br>")

    def handle_endtag(self, tag):
        tag = SAME.get(tag.lower(), tag.lower())
        if tag in ("script", "style", "title"):
            self.skip = max(0, self.skip - 1)
            return
        if self.skip or tag in VOID:
            return
        if tag in GAP:
            self.out.append(GAP[tag])
            return
        if tag in NEWLINE:
            self.out.append("<br>")
            return
        if tag not in self.open:
            return
        # Close back to it, so the document this writes is always well formed
        # however badly nested the one it read was.
        while self.open:
            last = self.open.pop()
            self.out.append("</%s>" % last)
            if last == tag:
                break

    def handle_data(self, data):
        if not self.skip and data:
            self.out.append(escape(data, quote=False))

    def result(self) -> str:
        while self.open:
            self.out.append("</%s>" % self.open.pop())
        return "".join(self.out)


def looks_rich(value) -> bool:
    """Whether this is meant as rich text at all: a tag we would keep."""
    return bool(re.search(r"<(%s)\b" % "|".join(ALLOWED | set(UNWRAP)), str(value or ""), re.I))


def clean(value, *, limit: int = MAX) -> str:
    """The one gate. Returns a document made only of what the lists allow,
    emptied of anything that could act, and tidied of the empty wrappers a
    paste out of Word leaves behind.

    `limit` is how much input is read: MAX for a note somebody typed,
    EMAIL_MAX for an email and for reading a stored note back."""
    p = _Clean()
    p.feed(str(value or "")[:limit])
    p.close()
    out = p.result()
    # A paste leaves runs of empty paragraphs; one is a blank line, five are a
    # mistake. And a note that says nothing says nothing.
    out = re.sub(r"(?:<p>(?:\s|<br>|&nbsp;)*</p>\s*){2,}", "<p><br></p>", out)
    out = re.sub(r"^(?:<p>(?:\s|<br>|&nbsp;)*</p>\s*)+", "", out)
    out = re.sub(r"(?:<p>(?:\s|<br>|&nbsp;)*</p>\s*)+$", "", out)
    # Three blank lines in a row is a mail client's layout showing through.
    out = re.sub(r"(?:<br>\s*){3,}", "<br><br>", out)
    out = re.sub(r"^(?:<br>\s*)+", "", out)
    out = re.sub(r"(?:<br>\s*)+$", "", out)
    return out.strip()


_TAGS = re.compile(r"<[^>]*>")
_BREAKS = re.compile(r"</(p|blockquote|pre|h3|h4|ul|ol)>|<br\s*/?>", re.I)
_LI = re.compile(r"<li\b[^>]*>", re.I)


def text(value) -> str:
    """The words without the markup: what the PHI scan reads, what the plain
    part of an email carries, and what a search matches. A list keeps its
    dashes, because a list read aloud still has them."""
    from html import unescape
    s = str(value or "")
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", s)
    s = _LI.sub("\n- ", s)
    s = _BREAKS.sub("\n", s)
    s = _TAGS.sub("", s)
    s = unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
    return "\n".join(line.rstrip() for line in s.split("\n")).strip()
