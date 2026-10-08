"""The SQL Server backend (D7, 25 Sep 2026): the desk on the instance PMC has.

Everything in psaspine speaks one SQL, the SQLite dialect the schema is written
in, and one connection surface, sqlite3's. This module lets that same code run
on SQL Server without a second copy of any query: an ODBC connection string in
place of a file path opens a connection that translates each statement on the
way through and hands rows back in sqlite3's shape.

What it deliberately does NOT do is guess. A construct the translator has not
decided is refused with the statement in the message, not passed through to fail
somewhere less legible. The list of decisions is `translate()`; every one is
asserted by a test against a real SQL Server (tests/test_spine.py, run with
PSA_TEST_DB set), and the same tests run unchanged on SQLite.

The driver is pyodbc plus Microsoft's ODBC Driver for SQL Server. That is the
one dependency this package takes, and it is imported only here and only when a
connection string is used: a SQLite desk still needs nothing installed.

The error vocabulary stays sqlite3's. A unique key, a CHECK, a foreign key or a
gate trigger that refuses a write raises sqlite3.IntegrityError from this
backend too, so no caller has to know which store it is on.
"""
from __future__ import annotations

import decimal
import functools
import re
import sqlite3
import threading
import weakref
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = ROOT / "sqlserver" / "PMC_PSA_Spine_SqlServer.sql"
SCHEMA = "psa"

# An ODBC connection string names its server or driver somewhere among its
# ';'-separated keys, in any order; a file path names neither.
_CONNECTION_STRING = re.compile(
    r"(^|;)\s*(driver|server|dsn|data source|addr|address|network address)\s*=", re.I)


def is_connection_string(target) -> bool:
    return isinstance(target, str) and bool(_CONNECTION_STRING.search(target))


def describe(target: str) -> str:
    """A connection string for a console or a log: server, database and driver
    only. Never the rest, which is where a password would be."""
    keep = {"server", "database", "driver", "dsn", "data source"}
    parts = [p.strip() for p in target.split(";") if p.split("=", 1)[0].strip().lower() in keep]
    return "SQL Server, " + ";".join(parts)


class Refused(NotImplementedError):
    """A statement uses something this backend has no decision for."""


# ------------------------------------------------------------------ tokens

_TOKEN = re.compile(
    r"'(?:[^']|'')*'"            # string literal, '' escaped
    r"|\"[^\"]*\""               # quoted identifier
    r"|--[^\n]*"                 # line comment
    r"|\|\||<>|!=|<=|>="         # two-character operators
    r"|[A-Za-z_][A-Za-z_0-9]*"   # word
    r"|\d+(?:\.\d+)?"            # number
    r"|\s+"                      # whitespace
    r"|.",                       # anything else, one character
    re.S)


def _tokens(sql: str) -> list[str]:
    return _TOKEN.findall(sql)


def _is_word(tok: str) -> bool:
    return bool(tok) and (tok[0].isalpha() or tok[0] == "_")


def _is_space(tok: str) -> bool:
    return tok.isspace() or tok.startswith("--")


# Functions with a different name or shape. Anything SQLite-only that is not
# here is refused by name, below.
_FUNCTIONS = {"substr": "SUBSTRING", "length": "LEN", "ifnull": "ISNULL"}
_REFUSED_FUNCTIONS = {
    "instr", "strftime", "datetime", "date", "time", "julianday", "unixepoch",
    "random", "randomblob", "hex", "printf", "format", "iif", "typeof",
    "group_concat", "json", "json_extract", "glob", "changes", "total_changes",
    "last_insert_rowid", "quote", "zeroblob", "char", "unicode",
}
_PREDICATE = {"=", "<>", "!=", "<", ">", "<=", ">=", "IS", "LIKE", "IN", "AND", "OR", "NOT", "BETWEEN", "EXISTS"}
_CASTS = {"INTEGER": "INT", "INT": "INT", "REAL": "FLOAT", "TEXT": "NVARCHAR(MAX)", "NUMERIC": "DECIMAL(19,4)"}


class Plan:
    """One translated statement: the T-SQL, how to run it, and how the
    parameters move when the translation moved a placeholder."""
    __slots__ = ("sql", "verb", "conflict", "table", "columns", "values", "param_map", "n_params")

    def __init__(self, sql, verb, conflict, table, columns, values, param_map, n_params):
        self.sql, self.verb, self.conflict, self.table = sql, verb, conflict, table
        self.columns, self.values, self.param_map, self.n_params = columns, values, param_map, n_params


def _first_words(toks: list[str], n: int = 4) -> list[str]:
    return [t.upper() for t in toks if not _is_space(t)][:n]


def _balanced_end(toks: list[str], open_at: int) -> int:
    """Index of the ')' matching the '(' at open_at."""
    depth = 0
    for i in range(open_at, len(toks)):
        if toks[i] == "(":
            depth += 1
        elif toks[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    raise Refused("unbalanced parentheses")


def _split_args(toks: list[str]) -> list[list[str]]:
    """Split a token run on top-level commas."""
    out, cur, depth = [], [], 0
    for t in toks:
        if t == "(":
            depth += 1
        elif t == ")":
            depth -= 1
        if t == "," and depth == 0:
            out.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        out.append(cur)
    return out


def _strip(toks: list[str]) -> list[str]:
    while toks and _is_space(toks[0]):
        toks = toks[1:]
    while toks and _is_space(toks[-1]):
        toks = toks[:-1]
    return toks


def _rewrite_sum(toks: list[str]) -> list[str]:
    """SUM(<predicate>) counts true rows in SQLite; SQL Server has no boolean
    value to add, so it becomes SUM(CASE WHEN <predicate> THEN 1 ELSE 0 END)."""
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        if _is_word(t) and t.upper() in ("SUM", "AVG", "MAX", "MIN") and i + 1 < len(toks) and toks[i + 1] == "(":
            end = _balanced_end(toks, i + 1)
            inner = _rewrite_sum(toks[i + 2:end])
            depth, predicate = 0, False
            for u in inner:
                if u == "(":
                    depth += 1
                elif u == ")":
                    depth -= 1
                elif depth == 0 and _is_word(u) and u.upper() == "CASE":
                    predicate = False          # already a value; leave it
                    break
                elif depth == 0 and (u.upper() in _PREDICATE):
                    predicate = True
            if predicate:
                out.extend([t, "(", "CASE", " ", "WHEN", " ", *inner, " ", "THEN", " ", "1", " ", "ELSE", " ", "0", " ", "END", ")"])
            else:
                out.extend([t, "(", *inner, ")"])
            i = end + 1
            continue
        out.append(t)
        i += 1
    return out


def _rewrite_limit(toks: list[str]) -> list[str]:
    """LIMIT n [OFFSET m] -> OFFSET m ROWS FETCH NEXT n ROWS ONLY, which SQL
    Server accepts anywhere SQLite accepts LIMIT (a subquery included) as long
    as an ORDER BY precedes it; one is supplied when the query has none, and
    then the rows are whichever rows, as in SQLite."""
    out = list(toks)
    while True:
        pos = next((i for i, t in enumerate(out) if _is_word(t) and t.upper() == "LIMIT"), None)
        if pos is None:
            return out
        # the SELECT this LIMIT belongs to: the nearest one at the same depth
        depth, owner, ordered = 0, None, False
        for j in range(pos - 1, -1, -1):
            t = out[j]
            if t == ")":
                depth += 1
            elif t == "(":
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and _is_word(t):
                u = t.upper()
                if u == "SELECT":
                    owner = j
                    break
                if u == "BY" and j >= 2 and out[j - 2].upper() == "ORDER":
                    ordered = True
        if owner is None:
            raise Refused("LIMIT with no SELECT to belong to")
        # the clause: LIMIT <n> [OFFSET <m>] up to the end of this depth
        j, depth = pos + 1, 0
        end = len(out)
        while j < len(out):
            t = out[j]
            if t == "(":
                depth += 1
            elif t == ")":
                if depth == 0:
                    end = j
                    break
                depth -= 1
            elif t == ";" and depth == 0:
                end = j
                break
            j += 1
        clause = _strip(out[pos + 1:end])
        words = [t for t in clause if not _is_space(t)]
        n, m = None, ["0"]
        if "OFFSET" in [w.upper() for w in words]:
            k = [w.upper() for w in words].index("OFFSET")
            n, m = words[:k], words[k + 1:]
        else:
            n = words
        if not n or not m:
            raise Refused("LIMIT clause not understood: " + "".join(clause))
        fetch = ([] if ordered else [" ", "ORDER", " ", "BY", " ", "(", "SELECT", " ", "NULL", ")"]) + \
                [" ", "OFFSET", " ", *m, " ", "ROWS", " ", "FETCH", " ", "NEXT", " ", *n, " ", "ROWS", " ", "ONLY"]
        out = out[:pos] + fetch + out[end:]
        # trailing whitespace before LIMIT is harmless; the loop finds the next


def _param_order(before: list[str], after: list[str]) -> list[int] | None:
    """If the translation moved placeholders, which original parameter feeds
    each placeholder now. Placeholders are matched by the parameter-bearing
    token that follows or precedes them, which for the one moving construct
    (LIMIT ? OFFSET ?) is the keyword before each."""
    nb, na = before.count("?"), after.count("?")
    if nb != na:
        raise Refused("translation changed the number of parameters")
    if nb == 0:
        return None
    # Tag each ? in `before` by the keyword before it; the same tags in `after`.
    def tags(toks):
        res, last = [], ""
        for t in toks:
            if t == "?":
                res.append(last)
            elif _is_word(t):
                last = t.upper()
        return res
    tb, ta = tags(before), tags(after)
    if tb == ta:
        return None
    # Only LIMIT/OFFSET move. Everything else keeps its place in order.
    moved_b = [i for i, t in enumerate(tb) if t in ("LIMIT", "OFFSET")]
    moved_a = [i for i, t in enumerate(ta) if t in ("NEXT", "OFFSET")]
    if len(moved_b) != len(moved_a) or [t for t in tb if t not in ("LIMIT", "OFFSET")] != \
            [t for t in ta if t not in ("NEXT", "OFFSET")]:
        raise Refused("translation moved a parameter it cannot account for")
    by_tag = {"LIMIT": "NEXT", "OFFSET": "OFFSET"}
    order = list(range(nb))
    for ai in moved_a:
        want = [k for k, v in by_tag.items() if v == ta[ai]][0]
        bi = next(i for i in moved_b if tb[i] == want)
        order[ai] = bi
    return None if order == list(range(nb)) else order


@functools.lru_cache(maxsize=4096)
def translate(sql: str) -> Plan:
    """SQLite statement text -> Plan. Cached: the desk issues the same few
    hundred statements over and over."""
    toks = _tokens(sql)
    words = _first_words(toks)
    if not words:
        raise Refused("empty statement")
    if words[0] == "PRAGMA":
        raise Refused(f"PRAGMA has no meaning on SQL Server: {sql.strip()[:80]}")
    # Savepoints: SQL Server's are SAVE / ROLLBACK TRANSACTION <name>, and a
    # RELEASE has no counterpart (the savepoint simply stops mattering).
    if words[0] == "SAVEPOINT" and len(words) == 2:
        return Plan(f"IF @@TRANCOUNT = 0 BEGIN TRANSACTION; SAVE TRANSACTION {words[1]}",
                    "SAVEPOINT", None, None, None, None, None, 0)
    if words[0] == "RELEASE" and len(words) in (2, 3):
        return Plan("", "RELEASE", None, None, None, None, None, 0)
    if words[:2] == ["ROLLBACK", "TO"] and len(words) in (3, 4):
        return Plan(f"ROLLBACK TRANSACTION {words[-1]}", "ROLLBACK", None, None, None, None, None, 0)
    verb, conflict, table, columns, values = words[0], None, None, None, None

    if verb == "INSERT" and len(words) > 2 and words[1] == "OR":
        conflict = words[2]
        if conflict not in ("IGNORE", "REPLACE"):
            raise Refused(f"INSERT OR {conflict} has no port decided")
        # drop the "OR <conflict>" words; the INSERT itself is the same
        word_at = [k for k, t in enumerate(toks) if _is_word(t)]
        del toks[word_at[1]:word_at[3]]                # "OR", the conflict word, and the spaces after each
    if verb == "INSERT":
        nonspace = [(i, t) for i, t in enumerate(toks) if not _is_space(t)]
        try:
            into = next(k for k, (i, t) in enumerate(nonspace) if t.upper() == "INTO")
            table = nonspace[into + 1][1]
            open_i = nonspace[into + 2][0]
        except (StopIteration, IndexError):
            raise Refused("INSERT without INTO <table> (columns)")
        if toks[open_i] != "(":
            raise Refused("INSERT needs an explicit column list on this backend")
        close_i = _balanced_end(toks, open_i)
        columns = tuple(_strip(a)[0] for a in _split_args(toks[open_i + 1:close_i]))
        after = [t.upper() for t in toks[close_i + 1:] if not _is_space(t)]
        if after[:1] == ["VALUES"]:
            v_open = next(i for i in range(close_i + 1, len(toks)) if toks[i] == "(")
            v_close = _balanced_end(toks, v_open)
            values = tuple("".join(_strip(a)) for a in _split_args(toks[v_open + 1:v_close]))
            if len(values) != len(columns):
                raise Refused("INSERT column and value counts differ")
        elif conflict is not None:
            raise Refused(f"INSERT OR {conflict} ... SELECT: write it as INSERT ... SELECT ... "
                          "WHERE NOT EXISTS, which both dialects run")

    out = []
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.startswith("'") or t.startswith('"') or _is_space(t):
            out.append(t)
        elif t == "||":
            out.append("+")
        elif _is_word(t):
            u = t.upper()
            low = t.lower()
            nxt = next((toks[j] for j in range(i + 1, len(toks)) if not _is_space(toks[j])), "")
            prev = next((toks[j].upper() for j in range(i - 1, -1, -1) if not _is_space(toks[j])), "")
            if nxt == "(" and prev == "INTO":
                out.append(t)          # INSERT INTO quote (...): a table, whatever its name, never a function call
            elif nxt == "(" and low in _FUNCTIONS:
                out.append(_FUNCTIONS[low])
            elif nxt == "(" and low in _REFUSED_FUNCTIONS:
                raise Refused(f"{t}() has no port decided: {sql.strip()[:80]}")
            elif u == "COLLATE":
                # NOCASE -> a case-insensitive collation SQL Server always has
                j = i + 1
                while j < len(toks) and _is_space(toks[j]):
                    j += 1
                if j < len(toks) and toks[j].upper() == "NOCASE":
                    out.extend(["COLLATE", " ", "Latin1_General_CI_AS"])
                    i = j + 1
                    continue
                out.append(t)
            elif u == "CAST":
                out.append(t)
            elif u in _CASTS and i >= 2 and toks[i - 2].upper() == "AS" and _in_cast(toks, i):
                out.append(_CASTS[u])
            elif u == "SQLITE_MASTER":
                raise Refused("sqlite_master: use db.table_exists()")
            elif u in ("GLOB", "REGEXP", "MATCH") :
                raise Refused(f"{u} has no port decided")
            elif u == "IS" and (nxt == "?" or (nxt.upper() == "NOT" and _after(toks, i, 2) == "?")):
                raise Refused("IS ? / IS NOT ? (null-safe equality) has no port decided")
            elif u in ("TRUE", "FALSE"):
                out.append("1" if u == "TRUE" else "0")
            elif u == "AUTOINCREMENT":
                raise Refused("DDL is not translated at runtime; init applies the port")
            else:
                out.append(t)
        else:
            out.append(t)
        i += 1
    out = _rewrite_sum(out)
    out = _rewrite_limit(out)
    param_map = _param_order(toks, out)
    return Plan("".join(out), verb, conflict, table, columns, values, param_map, out.count("?"))


def _after(toks: list[str], i: int, n: int) -> str:
    """The n-th non-space token after toks[i], or ''."""
    for j in range(i + 1, len(toks)):
        if not _is_space(toks[j]):
            n -= 1
            if n == 0:
                return toks[j]
    return ""


def _in_cast(toks: list[str], i: int) -> bool:
    """Is the AS before toks[i] the AS of a CAST( ... AS type)?"""
    depth = 0
    for j in range(i - 1, -1, -1):
        t = toks[j]
        if t == ")":
            depth += 1
        elif t == "(":
            if depth == 0:
                k = j - 1
                while k >= 0 and _is_space(toks[k]):
                    k -= 1
                return k >= 0 and toks[k].upper() == "CAST"
            depth -= 1
    return False


# --------------------------------------------------------------- errors

# What SQLite's OR IGNORE swallows: a unique key (2627, 2601), a NOT NULL
# (515) and a CHECK (547, when it is the CHECK and not a FOREIGN KEY, which
# SQLite does not ignore and neither does this).
_DUPLICATE = re.compile(r"\((2627|2601|515)\) \(SQLExecDirectW\)|CHECK constraint .*\(547\) \(SQLExecDirectW\)")


def _sqlite_error(exc) -> Exception:
    """pyodbc's error -> the sqlite3 class the engine and its tests expect."""
    text = str(exc)
    state = exc.args[0] if exc.args else ""
    m = re.search(r"\((\d+)\) \(SQL\w+\)", text)
    number = int(m.group(1)) if m else 0
    if state == "23000" or number >= 50000 or number in (547, 2627, 2601, 515):
        err = sqlite3.IntegrityError(_message(text))
    else:
        err = sqlite3.OperationalError(_message(text))
    err.__cause__ = exc
    return err


def _message(text: str) -> str:
    # "[42000] [Microsoft][ODBC Driver 18 for SQL Server][SQL Server]Foo. (102) (SQLExecDirectW)"
    text = re.sub(r"^\('[^']*', [\"']?|[\"']?\)$", "", text)
    text = re.sub(r"^(\s*\[[^\]]*\])+", "", text)          # [42000] [Microsoft][ODBC ...][SQL Server]
    text = re.sub(r"\s*\(\d+\)\s*\(SQL\w+\)\s*$", "", text)
    return text.strip()


# ------------------------------------------------------------------ rows

class Row:
    """sqlite3.Row's surface: by index, by name (any case), keys(), len, iter,
    equality, and dict(row). Decimals arrive as floats, as SQLite's REAL
    would have given them; bits as ints."""
    __slots__ = ("_values", "_index")

    def __init__(self, values, index):
        self._values = values
        self._index = index

    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            return self._values[key]
        try:
            return self._values[self._index[key.lower()]]
        except KeyError:
            raise IndexError(f"No item with that key: {key!r}") from None

    def keys(self):
        return list(self._index)

    def __len__(self):
        return len(self._values)

    def __iter__(self):
        return iter(self._values)

    def __eq__(self, other):
        return tuple(self) == tuple(other) if isinstance(other, (Row, tuple, list, sqlite3.Row)) else NotImplemented

    def __hash__(self):
        return hash(tuple(self._values))

    def __repr__(self):
        return f"Row({dict(zip(self._index, self._values))!r})"


def _plain(v):
    if isinstance(v, decimal.Decimal):
        f = float(v)
        return int(f) if f.is_integer() and v == v.to_integral_value() and "." not in str(v) else f
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, bytearray):
        return bytes(v)
    return v


class Cursor:
    __slots__ = ("_index", "rowcount", "lastrowid", "description", "_rows", "_pos")

    def __init__(self, cur, rowcount, lastrowid, rows=None):
        self.rowcount = rowcount
        self.lastrowid = lastrowid
        self._rows = list(rows) if rows else []
        self._pos = 0
        desc = cur.description if cur is not None else None
        self.description = desc
        self._index = {}
        if desc:
            for k, d in enumerate(desc):
                self._index.setdefault((d[0] or "").lower(), k)

    def _wrap(self, raw):
        return None if raw is None else Row(tuple(_plain(v) for v in raw), self._index)

    def fetchone(self):
        if self._pos >= len(self._rows):
            return None
        row = self._rows[self._pos]
        self._pos += 1
        return self._wrap(row)

    def fetchall(self):
        rows, self._pos = self._rows[self._pos:], len(self._rows)
        return [self._wrap(r) for r in rows]

    def fetchmany(self, n=1):
        rows = self._rows[self._pos:self._pos + n]
        self._pos += len(rows)
        return [self._wrap(r) for r in rows]

    def __iter__(self):
        while True:
            r = self.fetchone()
            if r is None:
                return
            yield r

    def close(self):
        self._rows, self._pos = [], 0


# ------------------------------------------------------------ connection

_live: "weakref.WeakSet[Connection]" = weakref.WeakSet()
_schema_checked: set[str] = set()
_unique_keys: dict[str, list[tuple[str, ...]]] = {}
_columns: dict[str, tuple[list[str], list[str]]] = {}
_unique_lock = threading.Lock()


def _adapt(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, Path):
        return str(v)
    return v


class Connection:
    """sqlite3.Connection's surface over a pyodbc connection."""
    backend = "mssql"

    def __init__(self, raw, target: str):
        self._raw = raw
        self.target = target
        self.row_factory = None       # read by nobody; kept for shape
        _live.add(self)

    # -- statements
    def execute(self, sql: str, params=()) -> Cursor:
        plan = translate(sql)
        params = tuple(_adapt(p) for p in params)
        if len(params) != plan.n_params:
            raise sqlite3.ProgrammingError(
                f"Incorrect number of bindings supplied. The current statement uses "
                f"{plan.n_params}, and there are {len(params)} supplied.")
        if plan.param_map:
            params = tuple(params[i] for i in plan.param_map)
        if plan.verb == "RELEASE":
            return Cursor(None, -1, None)
        cur = self._raw.cursor()
        try:
            if plan.verb == "INSERT":
                if plan.conflict == "REPLACE" and self._replace_in_place(cur, plan, params):
                    cur.close()
                    return Cursor(None, 1, None)
                try:
                    cur.execute(plan.sql + "; SELECT @@ROWCOUNT, SCOPE_IDENTITY()", params)
                except Exception as exc:                       # pyodbc.Error
                    if plan.conflict == "IGNORE" and _DUPLICATE.search(str(exc)):
                        return Cursor(None, 0, None)
                    raise
                n, ident = cur.fetchone()
                cur.close()
                return Cursor(None, int(n), None if ident is None else int(ident))
            if plan.verb in ("UPDATE", "DELETE"):
                # NOCOUNT is on for the session (so an INSERT's batch yields its
                # SELECT first), which also blanks pyodbc's rowcount; ask for it.
                cur.execute(plan.sql + "; SELECT @@ROWCOUNT", params)
                n = int(cur.fetchone()[0])
                cur.close()
                return Cursor(None, n, None)
            cur.execute(plan.sql, params)
            if cur.description is None:
                n = cur.rowcount
                cur.close()
                return Cursor(None, n, None)
            # Read the whole result now. Without MARS the connection is busy
            # until a result set is drained, and the engine reads one query
            # while writing rows from it (SQLite allowed that; the pages the
            # desk reads are small by construction).
            result = Cursor(cur, -1, None, rows=cur.fetchall())
            cur.close()
            return result
        except sqlite3.Error:
            raise
        except Exception as exc:
            if exc.__class__.__module__ == "pyodbc":
                raise _sqlite_error(exc) from None
            raise

    def executemany(self, sql: str, seq) -> Cursor:
        n = 0
        for params in seq:
            n += max(self.execute(sql, params).rowcount, 0)
        return Cursor(None, n, None)

    def executescript(self, script: str) -> None:
        """Statements separated by ';', each translated and run in turn. For
        the rows a test seeds; the schema on SQL Server is the generated port,
        never a script through here."""
        for stmt in _statements(script):
            self.execute(stmt)

    def _replace_in_place(self, cur, plan: Plan, params: tuple) -> bool:
        """INSERT OR REPLACE. SQLite deletes the row the new one collides with
        and inserts, checking foreign keys only at the end of the statement,
        so a parent row other rows point at can be replaced. SQL Server checks
        the delete at once, so the same outcome is written as an UPDATE: every
        listed column set, every unlisted one back to its DEFAULT (which is
        what the delete-and-insert would have left). Returns True when a row
        with that key existed and was updated; False when the INSERT that
        follows is the right thing. A collision on some other unique key is
        rare here and is left to the INSERT to report."""
        keys = self._keys_of(plan.table)
        by_col, pi = {}, 0
        for col, val in zip(plan.columns, plan.values):
            if val == "?":
                by_col[col] = ("?", params[pi])
                pi += 1
            else:
                by_col[col] = ("literal", val)
        primary = next((k for k in keys if all(c in by_col for c in k)), None)
        if primary is None:
            return False
        where, args = [], []
        for c in primary:
            kind, v = by_col[c]
            if kind == "?":
                where.append(f"[{c}] = ?")
                args.append(v)
            else:
                where.append(f"[{c}] = {v}")
        cur.execute(f"SELECT 1 FROM [{plan.table}] WHERE " + " AND ".join(where), tuple(args))
        if cur.fetchone() is None:
            return False
        settable, generated = self._columns_of(plan.table)
        sets, set_args = [], []
        for c in settable:
            if c in primary:
                continue
            if c in by_col:
                kind, v = by_col[c]
                if kind == "?":
                    sets.append(f"[{c}] = ?")
                    set_args.append(v)
                else:
                    sets.append(f"[{c}] = {v}")
            else:
                sets.append(f"[{c}] = DEFAULT")
        if sets:
            cur.execute(f"UPDATE [{plan.table}] SET " + ", ".join(sets) + " WHERE " + " AND ".join(where),
                        tuple(set_args) + tuple(args))
        return True

    def _columns_of(self, table: str) -> tuple[list[str], list[str]]:
        """(columns an UPDATE may set, columns the server generates)."""
        with _unique_lock:
            if table in _columns:
                return _columns[table]
        cur = self._raw.cursor()
        cur.execute(
            "SELECT c.name, c.is_identity, c.is_computed FROM sys.columns c"
            " WHERE c.object_id = OBJECT_ID(?) ORDER BY c.column_id", (f"{SCHEMA}.{table}",))
        settable, generated = [], []
        for name, ident, computed in cur.fetchall():
            (generated if (ident or computed) else settable).append(name)
        cur.close()
        with _unique_lock:
            _columns[table] = (settable, generated)
        return settable, generated

    def _keys_of(self, table: str) -> list[tuple[str, ...]]:
        with _unique_lock:
            if table in _unique_keys:
                return _unique_keys[table]
        cur = self._raw.cursor()
        cur.execute(
            "SELECT i.index_id, c.name FROM sys.indexes i"
            " JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id"
            " JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id"
            " WHERE i.object_id = OBJECT_ID(?) AND i.is_unique = 1 AND i.has_filter = 0"
            " ORDER BY i.index_id, ic.key_ordinal", (f"{SCHEMA}.{table}",))
        keys: dict[int, list[str]] = {}
        for index_id, col in cur.fetchall():
            keys.setdefault(index_id, []).append(col)
        cur.close()
        result = [tuple(v) for v in keys.values()]
        with _unique_lock:
            _unique_keys[table] = result
        return result

    # -- transactions
    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        _live.discard(self)
        if self._raw is None:
            return
        try:
            self._raw.rollback()
        except Exception:
            pass
        try:
            self._raw.close()
        finally:
            self._raw = None

    # -- context manager, as sqlite3
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()


def _statements(script: str) -> list[str]:
    out, cur = [], []
    for t in _tokens(script):
        if t == ";":
            stmt = "".join(cur).strip()
            if stmt:
                out.append(stmt)
            cur = []
        else:
            cur.append(t)
    tail = "".join(cur).strip()
    if tail:
        out.append(tail)
    return out


def connect(target: str) -> Connection:
    try:
        import pyodbc
    except ImportError as exc:                                     # pragma: no cover
        raise RuntimeError("a SQL Server desk needs pyodbc and Microsoft's ODBC Driver for "
                           "SQL Server; see README, 'On SQL Server'") from exc
    raw = pyodbc.connect(target, autocommit=False)
    cur = raw.cursor()
    # One round trip: the session settings, and (the first time for this
    # target) the user's DEFAULT_SCHEMA. Not SCHEMA_NAME(): on a new database
    # the psa schema does not exist until init applies the port, and
    # SCHEMA_NAME() is NULL until it does.
    if target in _schema_checked:
        cur.execute("SET NOCOUNT ON; SET XACT_ABORT OFF")
        cur.close()
        return Connection(raw, target)
    row = cur.execute("SET NOCOUNT ON; SET XACT_ABORT OFF;"
                      " SELECT default_schema_name FROM sys.database_principals"
                      " WHERE principal_id = DATABASE_PRINCIPAL_ID()").fetchone()
    cur.close()
    schema = row[0] if row else None
    if schema != SCHEMA:
        raw.close()
        raise RuntimeError(
            f"the desk's login must have default schema [{SCHEMA}] on this database; it has "
            f"[{schema}]. ALTER USER <name> WITH DEFAULT_SCHEMA = {SCHEMA}.")
    _schema_checked.add(target)
    return Connection(raw, target)


# --------------------------------------------------------------- schema

def apply_port(conn: Connection, *, any_database: bool = False) -> None:
    """Create what is missing from the generated schema. The script previews
    by default and refuses a second run; init wants neither, so it is run
    with @Apply = 1 and @AllowExisting = 1: every object is guarded, so on a
    database that already has the schema this changes nothing.

    The script also refuses any database but D7's by name. `any_database`
    lets a TEST database of another name take the schema; the desk never
    passes it."""
    text = PORT.read_text(encoding="utf-8")
    text, n1 = re.subn(r"DECLARE @Apply\s+BIT = 0;", "DECLARE @Apply BIT = 1;", text, count=1)
    text, n2 = re.subn(r"DECLARE @AllowExisting\s+BIT = 0;", "DECLARE @AllowExisting BIT = 1;", text, count=1)
    n3 = 1
    if any_database:
        text, n3 = re.subn(r"DECLARE @Database\s+SYSNAME = N'[^']*';", "DECLARE @Database SYSNAME = DB_NAME();", text, count=1)
    if n1 != 1 or n2 != 1 or n3 != 1:
        raise RuntimeError(f"{PORT.name} does not carry the switches this expects")
    cur = conn._raw.cursor()
    try:
        cur.execute(text)
        while cur.nextset():
            pass
        # The script turns XACT_ABORT on for its own transaction and the
        # setting outlives it on this session. The desk needs it off: with it
        # on, a duplicate key that INSERT OR IGNORE means to swallow takes the
        # whole transaction down with it (found by the tests, 25 Sep 2026).
        cur.execute("SET XACT_ABORT OFF")
    except Exception as exc:
        if exc.__class__.__module__ == "pyodbc":
            raise RuntimeError(_message(str(exc))) from None
        raise
    finally:
        cur.close()
    conn._raw.commit()


def preview_port(conn: Connection) -> list[str]:
    """Run the generated script as it stands (@Apply = 0): the plan it prints,
    line by line, and nothing changed. What the handoff's step 4 reads before
    anyone applies, for an operator whose sitting has no sqlcmd."""
    text = PORT.read_text(encoding="utf-8")
    cur = conn._raw.cursor()
    try:
        cur.execute(text)
        lines = []
        while True:
            for _state, message in cur.messages:
                # "[01000] [Microsoft][ODBC Driver 18 for SQL Server][SQL Server]PREVIEW ONLY. ..."
                lines.append(re.sub(r"^(\s*\[[^\]]*\])+", "", str(message)).rstrip())
            if not cur.nextset():
                break
        return lines
    except Exception as exc:
        if exc.__class__.__module__ == "pyodbc":
            raise RuntimeError(_message(str(exc))) from None
        raise
    finally:
        cur.close()
        conn._raw.rollback()


def table_exists(conn: Connection, name: str) -> bool:
    cur = conn._raw.cursor()
    try:
        return cur.execute("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?",
                           (SCHEMA, name)).fetchone() is not None
    finally:
        cur.close()


def column_exists(conn: Connection, table: str, column: str) -> bool:
    cur = conn._raw.cursor()
    try:
        return cur.execute("SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?"
                           " AND COLUMN_NAME = ?", (SCHEMA, table, column)).fetchone() is not None
    finally:
        cur.close()


def wipe(conn: Connection) -> None:
    """Every row out of every table in the schema, identities reseeded. For a
    test to start from nothing; never called by the desk.

    Any other connection this process still holds is rolled back and closed
    first: a test that left one open with a write in it would otherwise hold
    the lock this waits on for ever (SQLite would have let both proceed)."""
    for other in list(_live):
        if other is not conn:
            try:
                other.close()
            except Exception:
                pass
    cur = conn._raw.cursor()
    tables = [r[0] for r in cur.execute(
        "SELECT t.name FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id"
        " WHERE s.name = ? ORDER BY t.name", (SCHEMA,)).fetchall()]
    # Only a table that has ever had a row is reseeded: DBCC CHECKIDENT's
    # RESEED 0 on one that never has makes its first id 0, not 1 (last_value
    # is NULL until the first insert; after a reseed it is 0, and the next is 1).
    ident = {r[0] for r in cur.execute(
        "SELECT OBJECT_NAME(object_id) FROM sys.identity_columns"
        " WHERE OBJECT_SCHEMA_NAME(object_id) = ? AND last_value IS NOT NULL",
        (SCHEMA,)).fetchall()}
    batch = [f"ALTER TABLE [{SCHEMA}].[{t}] NOCHECK CONSTRAINT ALL;" for t in tables]
    batch += [f"DELETE FROM [{SCHEMA}].[{t}];" for t in tables]
    batch += [f"DBCC CHECKIDENT ('{SCHEMA}.{t}', RESEED, 0) WITH NO_INFOMSGS;" for t in sorted(ident)]
    batch += [f"ALTER TABLE [{SCHEMA}].[{t}] WITH CHECK CHECK CONSTRAINT ALL;" for t in tables]
    cur.execute("\n".join(batch))
    while cur.nextset():
        pass
    cur.close()
    conn._raw.commit()
