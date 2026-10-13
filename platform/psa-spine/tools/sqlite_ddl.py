"""A small, strict reader for the SQLite DDL in schema/*.sql.

Strict is the point. This is not a general SQL parser and must never behave like
one: the schema it reads is the commercial record, and a parser that shrugs at a
construct it does not understand will silently emit a SQL Server schema that
enforces less than the SQLite one does. A rule that quietly stops being enforced
on the port is exactly the failure the spine exists to prevent.

So every construct is either recognised by name or raises `Unsupported`. There
is no default branch anywhere in this file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


class Unsupported(Exception):
    """A construct this translator does not recognise. Never a warning."""


# ------------------------------------------------------------------ scanning

def split_statements(sql: str) -> list[tuple[str, str]]:
    """Split into (raw, code) pairs, one per statement.

    `raw` keeps the comments — they are carried into the generated script,
    because the reasons in this schema are as load-bearing as the constraints.
    `code` has only the comments blanked, so a semicolon or a parenthesis inside
    a comment cannot end a statement early. String literals are left intact —
    the values in a CHECK list and the text of a RAISE are the content being
    ported, not noise — and the scanners below track quoting themselves.
    """
    out: list[tuple[str, str]] = []
    raw: list[str] = []
    code: list[str] = []
    i, n = 0, len(sql)
    depth = 0

    def flush() -> None:
        # raw and code are the same length by construction — every branch above
        # writes equal numbers of characters to each — so an index found in code
        # slices raw at the same place. Nothing here may strip one and not the
        # other, or that alignment is lost.
        text, blanked = "".join(raw), "".join(code)
        if blanked.strip():
            out.append((text, blanked))
        raw.clear()
        code.clear()

    while i < n:
        ch = sql[i]
        two = sql[i:i + 2]
        if two == "--":
            j = sql.find("\n", i)
            j = n if j < 0 else j
            raw.append(sql[i:j])
            code.append(" " * (j - i))
            i = j
            continue
        if two == "/*":
            j = sql.find("*/", i + 2)
            if j < 0:
                raise Unsupported("unterminated block comment")
            j += 2
            raw.append(sql[i:j])
            code.append(" " * (j - i))
            i = j
            continue
        if ch == "'":
            j = i + 1
            while j < n:
                if sql[j] == "'":
                    if sql[j + 1:j + 2] == "'":
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            else:
                raise Unsupported("unterminated string literal")
            raw.append(sql[i:j])
            code.append(sql[i:j])       # literals are kept: a CHECK's value
            i = j                        # list and a RAISE message are content
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        raw.append(ch)
        code.append(ch)
        i += 1
        if ch == ";" and depth == 0:
            body = "".join(code)
            # A trigger body carries its own semicolons between BEGIN and END.
            if _is_trigger(body) and _word_count(body, "BEGIN") > _word_count(body, "END"):
                continue
            flush()
    flush()
    return out


def _is_trigger(code: str) -> bool:
    return re.match(r"\s*CREATE\s+TRIGGER\b", code, re.I) is not None


def _word_count(text: str, word: str) -> int:
    return len(re.findall(rf"\b{word}\b", text, re.I))


def split_top_level(text: str) -> list[str]:
    """Split on commas at paren depth zero."""
    parts, buf, depth = [], [], 0
    in_str = False
    for ch in text:
        if in_str:
            buf.append(ch)
            if ch == "'":
                in_str = False
            continue
        if ch == "'":
            in_str = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def strip_comments(text: str) -> str:
    """Remove -- comments from a fragment, keeping the code."""
    return "\n".join(re.sub(r"--.*$", "", line) for line in text.splitlines())


def leading_comment(raw: str) -> str:
    """The comment block that sits above a statement, if any."""
    lines, keep = raw.splitlines(), []
    for line in lines:
        if line.strip().startswith("--") or not line.strip():
            keep.append(line)
        else:
            break
    return "\n".join(keep).strip()


# ------------------------------------------------------------------- model

@dataclass
class Column:
    name: str
    sqlite_type: str
    not_null: bool = False
    primary_key: bool = False
    default: str | None = None
    references: tuple[str, str] | None = None
    checks: list[str] = field(default_factory=list)
    comment: list[str] | None = None


@dataclass
class Table:
    name: str
    columns: list[Column]
    constraints: list[str]          # table-level, already in source text
    comment: str
    source_file: str


@dataclass
class AlterAddColumn:
    """A column added to a table that already exists.

    A schema that can only ever be created and never evolved is not a schema, so
    this is recognised deliberately rather than refused. Only ADD COLUMN: a
    rename or a drop loses data, and neither should happen silently on a live
    clinical database.
    """
    table: str
    column: "Column"
    comment: str
    source_file: str


@dataclass
class Rebuild:
    """A table rebuilt to widen a CHECK (SQLite cannot alter one): in one file,

        CREATE TABLE <name>_new ( ...the whole definition, changed... );
        INSERT INTO <name>_new (...) SELECT ... FROM <name>;
        DROP TABLE <name>;
        ALTER TABLE <name>_new RENAME TO <name>;

    then its indexes created again by their old names. Recognised as one
    construct, deliberately: on a live database the port never drops a table,
    so SQL Server gets a constraint swap (DROP CONSTRAINT, ADD CONSTRAINT) and
    an ADD for each new column, both guarded, and the rebuilt definition is
    what a fresh install creates. Anything a rebuild changes beyond a CHECK's
    text and new columns at the end is refused, not ported silently.
    """
    table: "Table"                  # the new definition, under the final name
    original: "Table"               # as it stood before
    comment: str
    source_file: str


@dataclass
class Index:
    name: str
    table: str
    columns: str
    comment: str
    unique: bool = False
    where: str | None = None        # a partial index's condition, verbatim


@dataclass
class Trigger:
    name: str
    timing: str                     # BEFORE | AFTER | INSTEAD OF
    event: str                      # INSERT | UPDATE | DELETE
    update_of: list[str]
    table: str
    when: str | None
    raise_action: str               # ABORT | FAIL | ROLLBACK
    message: str
    comment: str
    source_file: str


# ------------------------------------------------------------------ parsing

TYPES = {"TEXT", "INTEGER", "REAL"}
TABLE_CONSTRAINT_HEADS = {"PRIMARY", "UNIQUE", "CHECK", "FOREIGN", "CONSTRAINT"}

_CREATE_TABLE = re.compile(r"^\s*CREATE\s+TABLE\s+(\w+)\s*\(", re.I)
_CREATE_INDEX = re.compile(
    r"^\s*CREATE\s+(UNIQUE\s+)?INDEX\s+(\w+)\s+ON\s+(\w+)\s*\(([^()]*)\)"
    r"\s*(?:WHERE\s+(.*?))?\s*;?\s*$", re.I | re.S)
_PRAGMA = re.compile(r"^\s*PRAGMA\s+\w+\s*=\s*\w+\s*;?\s*$", re.I)
_ALTER = re.compile(r"^\s*ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+(.*?);?\s*$", re.I | re.S)
_REBUILD_INSERT = re.compile(r"^\s*INSERT\s+INTO\s+(\w+)\s*(?:\([^)]*\))?\s*SELECT\b.*?\bFROM\s+(\w+)\s*;?\s*$", re.I | re.S)
_DROP_TABLE = re.compile(r"^\s*DROP\s+TABLE\s+(\w+)\s*;?\s*$", re.I)
_RENAME = re.compile(r"^\s*ALTER\s+TABLE\s+(\w+)\s+RENAME\s+TO\s+(\w+)\s*;?\s*$", re.I)
_TRIGGER_HEAD = re.compile(
    r"^\s*CREATE\s+TRIGGER\s+(\w+)\s+(BEFORE|AFTER|INSTEAD\s+OF)\s+"
    r"(INSERT|DELETE|UPDATE)(?:\s+OF\s+([\w\s,]+?))?\s+ON\s+(\w+)\s+",
    re.I,
)
_RAISE = re.compile(r"SELECT\s+RAISE\s*\(\s*(ABORT|FAIL|ROLLBACK)\s*,\s*'(.*?)'\s*\)\s*;", re.I | re.S)


def _balanced(text: str, start: int) -> tuple[str, int]:
    """Return the contents of the parenthesised group opening at `start`."""
    depth, i, in_str = 0, start, False
    while i < len(text):
        ch = text[i]
        if in_str:
            if ch == "'":
                in_str = False
        elif ch == "'":
            in_str = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i
        i += 1
    raise Unsupported("unbalanced parentheses")


def parse_column(code: str, raw: str) -> Column:
    """Parse one column definition. Anything unrecognised raises.

    `code` has comments blanked; `raw` is the same text with them intact, so the
    trailing note on a column travels to the generated script.
    """
    notes = [line.split("--", 1)[1].strip() for line in raw.splitlines() if "--" in line]
    comment = [n for n in notes if n] or None

    tokens = " ".join(code.split()).split(" ", 2)
    name = tokens[0]
    if not re.fullmatch(r"\w+", name):
        raise Unsupported(f"column name {name!r}")
    if len(tokens) < 2:
        raise Unsupported(f"column {name!r} has no type; this schema never omits one")
    ctype = tokens[1].upper()
    if ctype not in TYPES:
        raise Unsupported(f"column {name!r} has type {ctype!r}; only {sorted(TYPES)} are ported")

    col = Column(name=name, sqlite_type=ctype, comment=comment)
    rest = tokens[2] if len(tokens) > 2 else ""
    i = 0
    while i < len(rest):
        if rest[i] == " ":
            i += 1
            continue
        upper = rest[i:].upper()
        if upper.startswith("PRIMARY KEY"):
            col.primary_key = True
            i += len("PRIMARY KEY")
        elif upper.startswith("NOT NULL"):
            col.not_null = True
            i += len("NOT NULL")
        elif upper.startswith("DEFAULT "):
            i += len("DEFAULT ")
            m = re.match(r"('(?:[^']|'')*'|-?\d+(?:\.\d+)?|NULL)", rest[i:], re.I)
            if not m:
                raise Unsupported(f"{name}: DEFAULT expression {rest[i:]!r} is not a literal")
            col.default = m.group(1)
            i += m.end()
        elif upper.startswith("CHECK"):
            i = rest.index("(", i)
            body, end = _balanced(rest, i)
            col.checks.append(body.strip())
            i = end + 1
        elif upper.startswith("REFERENCES "):
            m = re.match(r"REFERENCES\s+(\w+)\s*\(\s*(\w+)\s*\)", rest[i:], re.I)
            if not m:
                raise Unsupported(f"{name}: REFERENCES clause {rest[i:]!r} names no column")
            col.references = (m.group(1), m.group(2))
            i += m.end()
        else:
            raise Unsupported(f"{name}: unrecognised column constraint at {rest[i:]!r}")
    return col


def parse_table(raw: str, code: str, source_file: str) -> Table:
    m = _CREATE_TABLE.search(code)
    if not m:
        raise Unsupported("CREATE TABLE header not recognised")
    open_paren = code.index("(", m.start(1))
    body_code, close = _balanced(code, open_paren)
    trailing = code[close + 1:].strip().rstrip(";").strip()
    if trailing:
        raise Unsupported(f"table options after the column list: {trailing!r}")

    # code and raw are position-aligned, so the same slice carries the comments.
    body_raw = raw[open_paren + 1:close]

    columns, constraints = [], []
    code_parts = split_top_level(body_code)
    raw_parts = split_top_level_raw(body_code, body_raw)
    if len(code_parts) != len(raw_parts):
        # zip() would silently drop columns. Refuse instead.
        raise Unsupported(f"{m.group(1)}: column list could not be split consistently")
    for part_code, part_raw in zip(code_parts, raw_parts):
        head = part_code.strip().split(" ", 1)[0].upper()
        if head in TABLE_CONSTRAINT_HEADS:
            constraints.append(" ".join(part_code.split()))
        else:
            columns.append(parse_column(part_code, part_raw))
    return Table(name=m.group(1), columns=columns, constraints=constraints,
                 comment=leading_comment(raw), source_file=source_file)


def split_top_level_raw(body_code: str, body_raw: str) -> list[str]:
    """The same split as split_top_level, but cut from the aligned raw text.

    A comma is not the end of the line. `external_ref TEXT,  -- kept verbatim`
    puts the note AFTER the separator, and cutting at the comma would file that
    note against the next column. So each cut runs on to the end of its line and
    the note stays with the column it describes.
    """
    cuts, depth, in_str = [], 0, False
    for i, ch in enumerate(body_code):
        if in_str:
            if ch == "'":
                in_str = False
            continue
        if ch == "'":
            in_str = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            # Run on to the end of the line only when nothing but a note follows
            # the comma there; a second column on the same line starts here.
            end_of_line = body_code.find("\n", i)
            end_of_line = len(body_code) if end_of_line < 0 else end_of_line
            rest = body_code[i + 1:end_of_line]
            cuts.append((i, end_of_line if not rest.strip() else i + 1))
    parts, start = [], 0
    for cut, resume in cuts + [(len(body_code), len(body_code))]:
        if body_code[start:cut].strip():
            parts.append(body_raw[start:resume])
        start = resume
    return parts


def parse_index(raw: str, code: str) -> Index:
    m = _CREATE_INDEX.match(strip_comments(code).strip())
    if not m:
        raise Unsupported("CREATE INDEX form not recognised")
    where = " ".join(m.group(5).split()) if m.group(5) else None
    return Index(name=m.group(2), table=m.group(3),
                 columns=" ".join(m.group(4).split()), comment=leading_comment(raw),
                 unique=bool(m.group(1)), where=where)


def parse_trigger(raw: str, code: str, source_file: str) -> Trigger:
    clean = strip_comments(code)
    m = _TRIGGER_HEAD.match(clean)
    if not m:
        raise Unsupported("CREATE TRIGGER header not recognised")
    name, timing, event, update_of, table = m.groups()

    tail = clean[m.end():]
    when = None
    if re.match(r"\s*WHEN\b", tail, re.I):
        start = re.match(r"\s*WHEN\b", tail, re.I).end()
        begin = re.search(r"\bBEGIN\b", tail[start:], re.I)
        if not begin:
            raise Unsupported(f"{name}: WHEN clause with no BEGIN")
        when = " ".join(tail[start:start + begin.start()].split())
        tail = tail[start + begin.start():]
    elif re.match(r"\s*FOR\s+EACH\s+ROW\b", tail, re.I):
        raise Unsupported(f"{name}: FOR EACH ROW should already be consumed")

    body_match = re.search(r"\bBEGIN\b(.*)\bEND\b", tail, re.I | re.S)
    if not body_match:
        raise Unsupported(f"{name}: trigger body is not BEGIN ... END")
    body = body_match.group(1).strip()

    r = _RAISE.search(body)
    if not r:
        raise Unsupported(
            f"{name}: the only trigger body this translator ports is a single "
            f"SELECT RAISE(...); got {body[:80]!r}")
    if _RAISE.sub("", body).strip():
        raise Unsupported(f"{name}: trigger body has statements beyond the RAISE")

    return Trigger(
        name=name,
        timing=" ".join(timing.upper().split()),
        event=event.upper(),
        update_of=[c.strip() for c in (update_of or "").split(",") if c.strip()],
        table=table,
        when=when,
        raise_action=r.group(1).upper(),
        message=" ".join(r.group(2).split()),
        comment=leading_comment(raw),
        source_file=source_file,
    )


def parse_alter(raw: str, code: str, source_file: str) -> AlterAddColumn:
    m = _ALTER.match(strip_comments(code))
    if not m:
        raise Unsupported(
            "only ALTER TABLE ... ADD COLUMN is ported. A rename or a drop loses "
            "data and must not happen silently on a live clinical database.")
    open_paren = code.index("(", code.upper().index("ADD COLUMN")) if False else None
    body_code = m.group(2)
    start = code.upper().index("ADD COLUMN") + len("ADD COLUMN")
    return AlterAddColumn(table=m.group(1),
                          column=parse_column(body_code, raw[start:].rstrip().rstrip(";")),
                          comment=leading_comment(raw), source_file=source_file)


def _rebuild_diff(old: Table, new: Table) -> list[Column]:
    """What a rebuild may change: a CHECK's text, and columns added at the
    end. Everything else is refused by name. Returns the new columns."""
    name = new.name
    old_cols = {c.name: c for c in old.columns}
    for i, c in enumerate(new.columns):
        if i < len(old.columns):
            o = old.columns[i]
            if o.name != c.name:
                raise Unsupported(f"rebuild of {name}: column {i + 1} is {c.name!r}, was {o.name!r}; a rebuild keeps the columns in order")
            same = (o.sqlite_type, o.not_null, o.primary_key, o.default, o.references, len(o.checks))
            if same != (c.sqlite_type, c.not_null, c.primary_key, c.default, c.references, len(c.checks)):
                raise Unsupported(f"rebuild of {name}: column {c.name!r} changes more than a CHECK's text; only that is ported")
        elif c.name in old_cols:
            raise Unsupported(f"rebuild of {name}: column {c.name!r} moved; a rebuild keeps the columns in order")
        elif c.not_null and c.default is None and not c.primary_key:
            raise Unsupported(f"rebuild of {name}: new column {c.name!r} is NOT NULL with no DEFAULT; existing rows have no value for it")
    if len(new.columns) < len(old.columns):
        raise Unsupported(f"rebuild of {name}: drops column(s); the port never drops a column")
    others = lambda t: [c for c in t.constraints if c.split(" ", 1)[0].upper() != "CHECK"]
    checks = lambda t: [c for c in t.constraints if c.split(" ", 1)[0].upper() == "CHECK"]
    if len(checks(old)) != len(checks(new)) or others(old) != others(new):
        raise Unsupported(f"rebuild of {name}: table constraints added, removed or reordered; a rebuild changes a CHECK's text only")
    return new.columns[len(old.columns):]


def parse_schema(files: list[tuple[str, str]]) -> tuple[list[Table], list[Index], list[Trigger], list[AlterAddColumn], list[Rebuild]]:
    """Parse (filename, sql) pairs in the order given. A rebuilt table (see
    Rebuild) replaces its original in `tables` at the point of the rebuild,
    its new columns join `alters`, and its re-created indexes are matched
    to the ones already parsed rather than counted twice."""
    tables: list[Table] = []
    indexes: list[Index] = []
    triggers: list[Trigger] = []
    alters: list[AlterAddColumn] = []
    rebuilds: list[Rebuild] = []
    for filename, sql in files:
        statements = [(raw, code, strip_comments(code).strip()) for raw, code in split_statements(sql)]
        statements = [s for s in statements if s[2]]
        i = 0
        while i < len(statements):
            raw, code, clean = statements[i]
            if _PRAGMA.match(clean):
                i += 1
                continue                               # recognised; see the emitter
            if _ALTER.match(clean):
                alters.append(parse_alter(raw, code, filename))
            elif re.match(r"\s*CREATE\s+TABLE\s+\w+_new\s*\(", clean, re.I):
                # the rebuild idiom: four statements, read as one
                if i + 3 >= len(statements):
                    raise Unsupported(f"{filename}: CREATE TABLE ..._new is a rebuild and needs INSERT, DROP TABLE and RENAME after it")
                new = parse_table(raw, code, filename)
                m_ins = _REBUILD_INSERT.match(statements[i + 1][2])
                m_drop = _DROP_TABLE.match(statements[i + 2][2])
                m_ren = _RENAME.match(statements[i + 3][2])
                final = new.name[:-len("_new")]
                if not (m_ins and m_drop and m_ren and m_ins.group(1) == new.name and m_ins.group(2) == final
                        and m_drop.group(1) == final and m_ren.group(1) == new.name and m_ren.group(2) == final):
                    raise Unsupported(f"{filename}: the rebuild of {final} must be INSERT INTO {new.name} ... SELECT ... FROM {final};"
                                      f" DROP TABLE {final}; ALTER TABLE {new.name} RENAME TO {final}; in that order")
                originals = [t for t in tables if t.name == final]
                if not originals:
                    raise Unsupported(f"{filename}: rebuild of {final}, which this schema never created")
                old = originals[-1]
                new.name = final
                # as the table stands: its CREATE plus every column added since
                stands = Table(name=old.name, columns=old.columns + [a.column for a in alters if a.table == final],
                               constraints=old.constraints, comment=old.comment, source_file=old.source_file)
                for col in _rebuild_diff(stands, new):
                    alters.append(AlterAddColumn(table=final, column=col, comment="", source_file=filename))
                tables[:] = [t for t in tables if t.name != final] + [new]
                rebuilds.append(Rebuild(table=new, original=old, comment=leading_comment(raw), source_file=filename))
                i += 4
                continue
            elif re.match(r"\s*CREATE\s+TABLE\b", clean, re.I):
                # FOR EACH ROW never appears in a table; guard the order below.
                tables.append(parse_table(raw, code, filename))
            elif re.match(r"\s*CREATE\s+(UNIQUE\s+)?INDEX\b", clean, re.I):
                index = parse_index(raw, code)
                before = [x for x in indexes if x.name == index.name]
                if before:
                    # an index created again after a rebuild: the same one, or refused
                    b = before[-1]
                    if (b.table, " ".join(b.columns.split()), b.unique, b.where) != (index.table, " ".join(index.columns.split()), index.unique, index.where):
                        raise Unsupported(f"{filename}: index {index.name} already exists with another definition")
                else:
                    indexes.append(index)
            elif re.match(r"\s*CREATE\s+TRIGGER\b", clean, re.I):
                triggers.append(parse_trigger(raw, _consume_for_each_row(code), filename))
            elif _REBUILD_INSERT.match(clean) or _DROP_TABLE.match(clean) or _RENAME.match(clean):
                raise Unsupported(f"{filename}: {clean.split()[0].upper()} is ported only inside a rebuild (CREATE TABLE <name>_new ...)")
            else:
                raise Unsupported(f"{filename}: statement not recognised: {clean[:100]!r}")
            i += 1
    return tables, indexes, triggers, alters, rebuilds


def _consume_for_each_row(code: str) -> str:
    """SQLite's FOR EACH ROW is the only granularity it supports, and SQL Server
    has no per-row triggers at all — see the emitter, which is why this is
    dropped here rather than translated."""
    return re.sub(r"\bFOR\s+EACH\s+ROW\b", " ", code, flags=re.I)
