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
# Reading a stored note back: an email is stored as its reply plus a fold of
# the messages it quoted, each cleaned up to EMAIL_MAX, so the read-back bound
# is twice that. It bounds parse cost; nothing that was stored is cut.
READ_MAX = 2 * EMAIL_MAX
# Which `ticket_event.body_format` values are markup. 'HTML' is a note written
# in the desk's editor (064); 'EMAIL' is an email's own HTML (6 Oct 2026), kept
# under the email profile and only ever drawn inside its sandbox. NULL or
# 'TEXT' is plain text, as every note was before 064.
RICH = ("HTML", "EMAIL")


def is_rich(body_format) -> bool:
    return (body_format or "").upper() in RICH


# ------------------------------------------------------- the email profile
#
# Dada, 6 Oct 2026, with two screenshots: an email on a ticket whose signature
# ran a blank line between every line of it, and *"can we search on github
# whats the best renderer for html so we can beautify the pages more"*.
#
# What the research says (VERIFIED 6 Oct 2026: making.close.com/posts/
# rendering-untrusted-html-email-safely, engineering.agentmail.to/blog/
# rendering-email-safely-preventing-phishing-attacks, github.com/cure53/
# DOMPurify) is three layers, not a library: an allow-list sanitizer, then a
# sandboxed `srcdoc` iframe so the email's layout and the page's stylesheet
# cannot touch each other, then a Content-Security-Policy that stops it
# fetching anything. This module was already the first layer -- a real
# tokenizer rebuilding a new document out of its own lists, which is how
# DOMPurify and Rust's ammonia (`nh3` in Python) work too, and not the regex
# stripping the Close write-up warns against. What was missing were the other
# two, and so the desk's own `p{margin}` was spacing out every line of an
# Outlook signature that is laid out one paragraph per line.
#
# An email is drawn inside its own frame now (`mail_document`), so it may keep
# more of itself than a note typed at the desk: its tables, so a signature lays
# out side by side; a filtered handful of inline CSS (weight, size, alignment,
# spacing, borders -- never a colour, so it stays readable in the dark theme,
# and nothing with a bracket, a quote or a slash, so never a url()); its inline
# pictures, by Content-ID only; and a fold for the earlier messages it quotes.
EMAIL_KEEP = {"table", "thead", "tbody", "tfoot", "tr", "td", "th", "span", "img", "hr",
              "sup", "sub", "details", "summary", "div"}
EMAIL_VOID = {"br", "img", "hr"}
CSS_PROPS = {
    "font-weight", "font-style", "font-size", "line-height", "text-decoration", "text-align",
    "text-indent", "vertical-align", "white-space", "list-style-type", "display", "float",
    "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
    "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
    "width", "min-width", "max-width", "height",
    "border", "border-top", "border-right", "border-bottom", "border-left",
    "border-width", "border-style", "border-collapse", "border-spacing"}
# Letters, digits, '#', '%', '.', ',', '-' and spaces: enough for "bold",
# "11.0pt", "solid #E1E1E1 1.0pt" and "0in 5.4pt"; never a bracket, a quote, a
# slash, a colon or a backslash, so never url(), expression(), var() or an
# escape that spells one.
CSS_VALUE = re.compile(r"^[a-z0-9#%., -]{1,80}$")
CSS_DISPLAY = {"none", "block", "inline", "inline-block", "table", "table-row", "table-cell"}
_INT = re.compile(r"^\d{1,4}%?$")
_CID = re.compile(r"^cid:[^\s\"'<>\\]{1,400}$", re.I)


def css(style: str) -> str:
    """Keep only the declarations on the lists, rebuilt, lower case."""
    keep = []
    for decl in str(style or "").split(";"):
        if ":" not in decl:
            continue
        prop, val = decl.split(":", 1)
        prop = prop.strip().lower()
        val = val.strip().lower().replace("!important", "").strip()
        if prop not in CSS_PROPS or not CSS_VALUE.match(val):
            continue
        if prop == "display" and val not in CSS_DISPLAY:
            continue
        keep.append(f"{prop}:{val}")
    return ";".join(keep)


class _Clean(HTMLParser):
    """Reads the input and writes a new document out of the lists above.

    `profile` is "note" for anything a person typed at the desk, and "email"
    for an email's own HTML, which is only ever drawn inside its sandbox."""

    def __init__(self, profile: str = "note") -> None:
        super().__init__(convert_charrefs=True)
        self.email = profile == "email"
        self.out: list[str] = []
        self.open: list[str] = []
        self.skip = 0              # inside a tag whose words go too (script, style)
        self.spans: list[bool] = []    # was each open <span> written, or unwrapped?

    def _attrs(self, tag, attrs) -> str:
        """The attributes a kept tag may carry, rebuilt. Email only."""
        got = {k.lower(): (v or "").strip() for k, v in attrs}
        out = []
        if tag in ("td", "th"):
            for k in ("colspan", "rowspan", "width"):
                if _INT.match(got.get(k, "")):
                    out.append(f'{k}="{got[k]}"')
            if got.get("align", "").lower() in ("left", "center", "right", "justify"):
                out.append(f'align="{got["align"].lower()}"')
            if got.get("valign", "").lower() in ("top", "middle", "bottom", "baseline"):
                out.append(f'valign="{got["valign"].lower()}"')
        elif tag == "table":
            for k in ("width", "cellpadding", "cellspacing", "border"):
                if _INT.match(got.get(k, "")):
                    out.append(f'{k}="{got[k]}"')
            if got.get("align", "").lower() in ("left", "center", "right"):
                out.append(f'align="{got["align"].lower()}"')
        style = css(got.get("style", ""))
        if style:
            out.append(f'style="{escape(style, quote=True)}"')
        return (" " + " ".join(out)) if out else ""

    # -------------------------------------------------------------- tags
    def _name(self, tag: str) -> str:
        # A note maps <div> to <p>: the desk's editor writes one per line and
        # the page spaces paragraphs. An email keeps its <div>s, because the
        # frame it is drawn in spaces neither.
        tag = tag.lower()
        return tag if (self.email and tag == "div") else SAME.get(tag, tag)

    def handle_starttag(self, tag, attrs):
        tag = self._name(tag)
        if tag in ("script", "style", "title"):
            self.skip += 1
            return
        if self.skip:
            return
        if self.email and tag == "span":
            extra = self._attrs(tag, attrs)
            self.spans.append(bool(extra))
            if extra:                  # a span that carries something we keep
                self.out.append(f"<span{extra}>")
                self.open.append("span")
            return
        kept = tag in ALLOWED or (self.email and tag in EMAIL_KEEP)
        if not kept or (tag in UNWRAP and not (self.email and tag in EMAIL_KEEP)):
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
        if tag == "img":
            # Only a picture the message itself carries, named by Content-ID.
            # A remote address is never written: fetching it would tell the
            # sender that a clinician opened the ticket, and when.
            src = next((v.strip() for k, v in attrs if k.lower() == "src" and v), "")
            if not _CID.match(src):
                return
            got = {k.lower(): (v or "").strip() for k, v in attrs}
            size = "".join(f' {k}="{got[k]}"' for k in ("width", "height")
                           if _INT.match(got.get(k, "")) and not got[k].endswith("%"))
            alt = escape(got.get("alt", "")[:200], quote=True)
            self.out.append(f'<img src="{escape(src, quote=True)}" alt="{alt}"{size}>')
            return
        if tag in VOID or (self.email and tag in EMAIL_VOID):
            self.out.append("<br>" if tag == "br" else f"<{tag}{self._attrs(tag, attrs) if self.email else ''}>")
            return
        self.out.append(f"<{tag}{self._attrs(tag, attrs) if self.email else ''}>")
        self.open.append(tag)

    def handle_startendtag(self, tag, attrs):
        if self.skip:
            return
        name = self._name(tag)
        if name in VOID or (self.email and name in EMAIL_VOID):
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = self._name(tag)
        if tag in ("script", "style", "title"):
            self.skip = max(0, self.skip - 1)
            return
        if self.skip or tag in VOID or (self.email and tag in EMAIL_VOID):
            return
        if self.email and tag == "span":
            # An unwrapped span's end must not close a kept one around it.
            if not (self.spans and self.spans.pop()):
                return
        elif not self.email:
            if tag in GAP:
                self.out.append(GAP[tag])
                return
            if tag in NEWLINE:
                # A row's end is a line only when its cells left no block to
                # end it: a signature written one paragraph per line already
                # breaks there, and a second break was a blank line too many.
                if not re.search(r"</(p|ul|ol|li|blockquote|pre|h3|h4)>\s*$|<br>\s*$", "".join(self.out[-3:])):
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


def clean(value, *, limit: int = MAX, profile: str = "note") -> str:
    """The one gate. Returns a document made only of what the lists allow,
    emptied of anything that could act, and tidied of the empty wrappers a
    paste out of Word leaves behind.

    `limit` is how much input is read: MAX for a note somebody typed,
    EMAIL_MAX for an email, READ_MAX for reading a stored note back.
    `profile` is "note" or "email" (see the email profile above)."""
    p = _Clean(profile)
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
_BREAKS = re.compile(r"</(p|blockquote|pre|h3|h4|ul|ol|tr|table|div|details|summary)>|<br\s*/?>|<hr\b[^>]*>", re.I)
_CELL = re.compile(r"</t[dh]>", re.I)
_LI = re.compile(r"<li\b[^>]*>", re.I)


def text(value) -> str:
    """The words without the markup: what the PHI scan reads, what the plain
    part of an email carries, and what a search matches. A list keeps its
    dashes, because a list read aloud still has them."""
    from html import unescape
    s = str(value or "")
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", s)
    s = _LI.sub("\n- ", s)
    s = _CELL.sub(" ", s)
    s = _BREAKS.sub("\n", s)
    s = _TAGS.sub("", s)
    s = unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
    return "\n".join(line.rstrip() for line in s.split("\n")).strip()


# ------------------------------------------------- the messages an email quotes
#
# A reply carries everything before it: in the screenshot of 6 Oct 2026 a
# requester's two-line answer arrived with the desk's own previous email, its
# headers and its signature under it, and so does every reply after. Mail
# clients fold that away ("show trimmed content"); so does the desk now. The
# reply is the note; what it quotes goes inside a <details> fold, which needs
# no script, so it works inside the sandbox.
#
# The markers are the ones the common clients write (MEASURED on Outlook
# desktop, Outlook on the web, Gmail, Apple Mail, Thunderbird and Yahoo HTML).
# The earliest one wins. A message with nothing above its quote -- a bare
# forward -- is left whole, because folding everything would hide the message.
_QUOTE_MARKS = (
    re.compile(r"<div\b[^>]*\bid=[\"']?(?:appendonsend|divRplyFwdMsg)\b", re.I),        # Outlook on the web, new Outlook
    re.compile(r"<div\b[^>]*\bclass=[\"']?[^\"'>]*\b(?:gmail_quote|yahoo_quoted|moz-cite-prefix)\b", re.I),
    re.compile(r"<blockquote\b[^>]*\btype=[\"']?cite\b", re.I),                          # Apple Mail
    re.compile(r"-{3,}\s*Original Message\s*-{3,}", re.I),
)
# Outlook desktop: no id, only a bold "From:" header followed by "Sent:" or
# "Date:". Also how a fold is found again in a note stored before today, whose
# ids and classes the gate had already dropped.
_FROM = re.compile(r"<b\b[^>]*>(?:\s*<span\b[^>]*>)?\s*From:\s*(?:</span>\s*)?</b>", re.I)
_SENT = re.compile(r"<b\b[^>]*>(?:\s*<span\b[^>]*>)?\s*(?:Sent|Date):\s*(?:</span>\s*)?</b>", re.I)
FOLD_TITLE = "Earlier messages in this email"


def split_quote(html: str) -> tuple[str, str]:
    """(the reply, what it quotes); the second is "" when nothing is quoted."""
    html = str(html or "")
    at = [m.start() for rx in _QUOTE_MARKS for m in [rx.search(html)] if m]
    m = _FROM.search(html)
    if m and _SENT.search(html, m.end(), m.end() + 1500):
        # Back up to the element that holds the header block: the bordered div
        # Outlook draws the rule with, else the paragraph the label is in.
        div = html.rfind("<div", max(0, m.start() - 600), m.start())
        par = html.rfind("<p", max(0, m.start() - 300), m.start())
        hr = html.rfind("<hr", max(0, m.start() - 600), m.start())
        at.append(max(div, hr) if max(div, hr) >= 0 else (par if par >= 0 else m.start()))
    if not at:
        return html, ""
    cut = min(at)
    return html[:cut], html[cut:]


def fold(html: str, *, profile: str = "email", limit: int = EMAIL_MAX) -> str:
    """Clean an email's HTML and fold away what it quotes. Returns "" when it
    cleans to no words at all."""
    head, quoted = split_quote(str(html or "")[:limit])
    head_c = clean(head, limit=limit, profile=profile)
    # The blank lines and rule a client leaves above the quote belong to the
    # quote: without this the fold sits under an empty gap. Closing tags after
    # them are kept, so the document stays well formed.
    head_c = re.sub(r"(?:\s*<hr\b[^>]*>|\s*<br>|\s*<p>(?:\s|<br>)*</p>)+((?:\s*</\w+>)*)\s*$", r"\1", head_c)
    if quoted and text(head_c).strip():
        quoted_c = clean(quoted, limit=limit, profile=profile)
        if text(quoted_c).strip():
            return f"{head_c}<details><summary>{FOLD_TITLE}</summary>{quoted_c}</details>"
        return head_c
    whole = clean(html, limit=limit, profile=profile)
    return whole if text(whole).strip() else ""


def unfolded(html: str) -> str:
    """The reply alone: what an outgoing email quotes back, since the thread
    under it already lists the earlier messages one by one."""
    return re.sub(r"<details>.*?</details>", "", str(html or ""), flags=re.S).strip()


# ----------------------------------------------- an email's pictures, by name

def resolve_images(html: str, resolve) -> str:
    """Point each `cid:` picture at a URL the person looking may open, or put
    a short line where it was. `resolve(cid)` returns (url or None, why or
    None). Run at drawing time, never stored: what may be shown depends on who
    is looking and on the file's review, and both change."""
    from html import unescape

    def one(m):
        cid = unescape(m.group(1))[4:]                  # the pattern only matches "cid:..."
        url, why = resolve(cid) if resolve else (None, None)
        if url:
            return f'<img src="{escape(url, quote=True)}"{m.group(2)} loading="lazy">'
        return f'<span class="imgph">{escape(why)}</span>' if why else ""
    return re.sub(r'<img src="(cid:[^"]+)"([^>]*)>', one, str(html or ""))


# ------------------------------------------------ an email on an email client
#
# An email client has no stylesheet of ours, and Outlook gives a bare <p> the
# better part of a line of margin -- which, on a note written one paragraph per
# line, is the double spacing in the screenshot. Each element is given the
# spacing the desk's own frame gives it, as an inline style, unless the sender
# already set one.
_EMAIL_INLINE = {"p": "margin:0", "ul": "margin:0 0 0 0;padding-left:22px", "ol": "margin:0;padding-left:22px",
                 "li": "margin:0 0 2px", "blockquote": "margin:0 0 8px;padding:2px 0 2px 10px;border-left:3px solid #d5dae6;color:#3b4454",
                 "h3": "margin:10px 0 4px;font-size:16px", "h4": "margin:8px 0 4px;font-size:15px",
                 "table": "border-collapse:collapse", "td": "vertical-align:top", "pre": "margin:0;white-space:pre-wrap"}


def email_inline(html: str) -> str:
    """A rich note as it should go out in an email: the reply without its
    fold, no pictures (their Content-IDs mean nothing in someone else's
    mailbox), and the frame's spacing written inline."""
    out = unfolded(html)
    out = re.sub(r"<img\b[^>]*>", "", out)
    out = re.sub(r'<span class="imgph">.*?</span>', "", out)

    def style(m):
        tag, rest = m.group(1).lower(), m.group(2) or ""
        if "style=" in rest or tag not in _EMAIL_INLINE:
            return m.group(0)
        return f'<{m.group(1)} style="{_EMAIL_INLINE[tag]}"{rest}>'
    return re.sub(r"<(p|ul|ol|li|blockquote|h3|h4|table|td|pre)\b([^>]*)>", style, out, flags=re.I)


# --------------------------------------------------- the sandbox it is drawn in
#
# The email's own document: our stylesheet, its HTML, and a policy that lets it
# load nothing but pictures from this desk. Put in an iframe's `srcdoc` with
# `sandbox="allow-popups allow-popups-to-escape-sandbox allow-same-origin"` --
# never `allow-scripts`, which together with same-origin would be the one
# combination that undoes the sandbox. Same-origin is there only so the page
# can measure the email's height; `<base target=_blank>` sends every link to a
# new tab rather than navigating the frame.
MAIL_CSP = ("default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; font-src 'none'; "
            "base-uri 'none'; form-action 'none'")
MAIL_STYLE = (
    ":root{color-scheme:light dark;--ink:#1f2430;--ink2:#5b6574;--line:#d5dae6;--link:#3d63dd}"
    ":root[data-theme=dark]{--ink:#e4e7ee;--ink2:#a3acba;--line:#3b4352;--link:#93b2ff}"
    "@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--ink:#e4e7ee;--ink2:#a3acba;"
    "--line:#3b4352;--link:#93b2ff}}"
    # A border keeps the sender's colour in light, where it was chosen; in dark
    # Outlook's pale-grey rule over a quoted header reads as a white bar, so
    # every border takes the theme's own line colour instead.
    ":root[data-theme=dark] [style*=border]{border-color:var(--line)!important}"
    "@media (prefers-color-scheme:dark){:root:not([data-theme=light]) [style*=border]"
    "{border-color:var(--line)!important}}"
    "html,body{margin:0;padding:0;background:transparent}"
    "body{font:var(--size,14.5px)/1.5 Aptos,'Segoe UI',system-ui,-apple-system,sans-serif;color:var(--ink);"
    "overflow-wrap:anywhere;padding:1px 0}"
    "p,div{margin:0}ul,ol{margin:0;padding-left:22px}li{margin:0 0 2px}"
    "h3{font-size:1.08em;margin:10px 0 4px}h4{font-size:1em;margin:8px 0 4px}"
    "blockquote{margin:4px 0;padding:0 0 0 10px;border-left:3px solid var(--line);color:var(--ink2)}"
    "a{color:var(--link)}table{border-collapse:collapse;max-width:100%}td,th{vertical-align:top}"
    "img{max-width:100%;height:auto;border-radius:4px}"
    "hr{border:0;border-top:1px solid var(--line);margin:10px 0}"
    "details{margin-top:10px}summary{cursor:pointer;color:var(--ink2);font-size:.9em;list-style:none;"
    "display:inline-block;padding:2px 10px;border:1px solid var(--line);border-radius:999px}"
    "summary::-webkit-details-marker{display:none}details[open]>summary{margin-bottom:10px}"
    "details>:not(summary){color:var(--ink2)}"
    ".imgph{display:inline-block;margin:2px 0;padding:2px 8px;border:1px dashed var(--line);"
    "border-radius:6px;color:var(--ink2);font-size:.88em}")


def mail_document(html: str) -> str:
    """The whole document an email is drawn in, ready for `srcdoc`."""
    return ("<!doctype html><html><head><meta charset=utf-8>"
            f'<meta http-equiv="Content-Security-Policy" content="{MAIL_CSP}">'
            '<meta name=color-scheme content="light dark"><meta name=referrer content=no-referrer>'
            f"<base target=_blank><style>{MAIL_STYLE}</style></head><body>{html}</body></html>")
