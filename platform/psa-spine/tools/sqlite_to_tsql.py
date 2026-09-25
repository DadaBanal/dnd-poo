"""Generate the SQL Server schema from schema/*.sql. One source, two dialects.

    python3 tools/sqlite_to_tsql.py --write
    python3 tools/sqlite_to_tsql.py --check      # drift gate, exits 1 on a difference

There is no hand-maintained second schema, and there must never be one. Two
copies of a commercial rule drift, and the copy that drifts is the one nobody is
looking at — which here would be the one on the live server. So the SQLite files
under schema/ are the source, this translator is the only way the T-SQL is
written, and `--check` fails the build if the committed output is not what the
source produces today.

The translator refuses rather than guesses. Every construct is recognised by
name; every NVARCHAR width and every DECIMAL precision is read from
tools/tsql-decisions.json and a column missing from that file stops the build.
A rule that quietly stops being enforced on the port is the failure this whole
exercise exists to prevent, so nothing is allowed to be inferred.

VERIFIED against SQL Server 2022 Express (16.0, Linux container) on 25 Sep 2026:
the script applies, the verify gate passes and both triggers fire. It has still
not been run on DND-SQL01 itself -- no session here has a route to it -- so the
output stays written to be run by somebody who has one: preview by default, a
verify gate, and a rollback in the footer. The database name it expects is D7's:
PMC_PSA, a database of its own on the existing instance.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlite_ddl import (  # noqa: E402
    AlterAddColumn, Column, Index, Table, Trigger, Unsupported, _balanced,
    parse_schema,
)

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schema"
DECISIONS = Path(__file__).resolve().parent / "tsql-decisions.json"
OUTPUT = ROOT / "sqlserver" / "PMC_PSA_Spine_SqlServer.sql"

SCHEMA = "psa"
TARGET_SERVER = "DND-SQL01\\PMC_SS"
TARGET_DATABASE = "PMC_PSA"    # D7: its own database on the existing instance

# The only functions that may appear in a CHECK or a trigger condition. Anything
# else raises: a function silently dropped is a constraint silently weakened.
FUNCTIONS = {
    "length": lambda a: f"LEN({a})",
    # TRIM() is SQL Server 2017 and later. The version on DND-SQL01 is NOT
    # VERIFIED from here, so the port uses the form that works on every version.
    "trim": lambda a: f"LTRIM(RTRIM({a}))",
    "lower": lambda a: f"LOWER({a})",
    "upper": lambda a: f"UPPER({a})",
    "coalesce": lambda a: f"COALESCE({a})",
}

# Words that may be followed by "(" without being a function call.
KEYWORDS_BEFORE_PAREN = {
    "in", "exists", "not", "and", "or", "select", "values", "on", "where",
    "when", "then", "else", "by", "union", "case",
}

TRIGGER_ALIAS = "inserted_row"   # SQLite's NEW, as a row of the inserted table


# ------------------------------------------------------------- expressions

def _rewrite_calls(expr: str) -> str:
    """Translate function calls, refusing any function not in FUNCTIONS."""
    out: list[str] = []
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch == "'":
            j = i + 1
            while j < len(expr):
                if expr[j] == "'":
                    if expr[j + 1:j + 2] == "'":
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            out.append(expr[i:j])
            i = j
            continue
        m = re.compile(r"[A-Za-z_]\w*").match(expr, i)
        if not m:
            out.append(ch)
            i += 1
            continue
        word, j = m.group(0), m.end()
        k = j
        while k < len(expr) and expr[k] == " ":
            k += 1
        if k < len(expr) and expr[k] == "(":
            args, close = _balanced(expr, k)
            low = word.lower()
            if low in KEYWORDS_BEFORE_PAREN:
                out.append(word + expr[j:k] + "(" + _rewrite_calls(args) + ")")
            elif low in FUNCTIONS:
                out.append(FUNCTIONS[low](_rewrite_calls(args)))
            else:
                raise Unsupported(
                    f"function {word}() has no port decided; add it to FUNCTIONS "
                    f"deliberately rather than letting the constraint through unchecked")
            i = close + 1
        else:
            out.append(word)
            i = j
    return "".join(out)


def _qualify(expr: str, tables: set[str]) -> str:
    """Put the psa schema in front of every table this schema owns."""
    def sub(m: re.Match) -> str:
        return f"{m.group(1)} {SCHEMA}.{m.group(2)}" if m.group(2) in tables else m.group(0)
    return re.sub(r"\b(FROM|JOIN|UPDATE|INTO)\s+(\w+)\b", sub, expr, flags=re.I)


def _boolean_equality(expr: str) -> str:
    """SQLite lets two predicates be compared: (a IS NULL) = (b IS NULL) says
    "both or neither". T-SQL has no boolean value to compare, so the same rule
    is written out as (both) OR (neither). Only the whole-expression shape
    "(P) = (Q)" is recognised; a predicate compared anywhere else is refused by
    the parser on the server, which is the right place for a shape nobody
    decided here."""
    if not expr.startswith("("):
        return expr
    left, close = _balanced(expr, 0)
    rest = expr[close + 1:]
    m = re.match(r"\s*=\s*\(", rest)
    if not m:
        return expr
    right, close2 = _balanced(rest, m.end() - 1)
    if rest[close2 + 1:].strip():
        return expr
    return f"((({left}) AND ({right})) OR (NOT ({left}) AND NOT ({right})))"


def expression(expr: str, tables: set[str]) -> str:
    return _qualify(_rewrite_calls(_boolean_equality(" ".join(expr.split()))), tables)


def _literals(expr: str) -> list[str]:
    return [m.group(1).replace("''", "'") for m in re.finditer(r"'((?:[^']|'')*)'", expr)]


# ---------------------------------------------------------------- decisions

class Decisions:
    def __init__(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        self.classes = data["classes"]
        self.columns = data["columns"]
        self.decimals = data["decimals"]

    def text_type(self, table: str, column: str) -> tuple[str, str]:
        key = f"{table}.{column}"
        name = self.columns.get(key)
        if name is None:
            raise Unsupported(
                f"no width decided for TEXT column {key}. Add it to "
                f"{DECISIONS.name}; TEXT has one meaning in SQLite and many in "
                f"SQL Server, and a width nobody chose is a width nobody owns.")
        return name, self.classes[name]["sql"]

    def decimal_type(self, table: str, column: str) -> str:
        key = f"{table}.{column}"
        entry = self.decimals.get(key)
        if entry is None:
            raise Unsupported(
                f"no precision decided for REAL column {key}. Add it to "
                f"{DECISIONS.name} as a DECIMAL. FLOAT is refused here: these "
                f"numbers reach an invoice.")
        return entry["sql"]

    def unused(self, live: set[str]) -> list[str]:
        return sorted((set(self.columns) | set(self.decimals)) - live)


def _max_width(sql_type: str) -> int | None:
    m = re.match(r"NVARCHAR\((\d+)\)$", sql_type)
    return int(m.group(1)) if m else None


# ----------------------------------------------------------------- emitting

def column_type(table: Table, col: Column, dec: Decisions) -> tuple[str, str | None]:
    """Return (T-SQL type, decision class or None)."""
    if col.sqlite_type == "INTEGER":
        return "INT", None
    if col.sqlite_type == "REAL":
        return dec.decimal_type(table.name, col.name), None
    cls, sql_type = dec.text_type(table.name, col.name)
    width = _max_width(sql_type)
    if width is not None:
        for check in col.checks:
            for lit in _literals(check):
                if len(lit) > width:
                    raise Unsupported(
                        f"{table.name}.{col.name} is {sql_type} but its own CHECK "
                        f"admits {lit!r}, which is {len(lit)} characters. The width "
                        f"and the constraint disagree; decide, do not truncate.")
    return sql_type, cls


def _parsed_column(table: Table, col: Column, cls: str) -> str | None:
    """A computed column beside a date kept as text.

    Both '20260904' and '2026-09-09' are in circulation and the shape the source
    used is itself evidence, so the text column stays authoritative and this sits
    beside it. Not PERSISTED: the value is derived on read, so no deployment
    depends on the server agreeing that a styled CONVERT is deterministic.
    """
    name = f"{col.name}_parsed"
    if any(c.name == name for c in table.columns):
        raise Unsupported(f"{table.name}.{name} already exists; the parsed column would collide")
    c = col.name
    eight = "'[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'"
    dashed = "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"
    if cls == "DATE_TEXT":
        return (f"[{name}] AS (CASE WHEN [{c}] LIKE {eight} THEN TRY_CONVERT(DATE, [{c}], 112) "
                f"WHEN [{c}] LIKE {dashed} THEN TRY_CONVERT(DATE, [{c}], 23) END)")
    if cls == "TIMESTAMP_TEXT":
        return (f"[{name}] AS (COALESCE(TRY_CONVERT(DATETIME2(0), [{c}], 126), "
                f"CASE WHEN [{c}] LIKE {eight} THEN TRY_CONVERT(DATETIME2(0), [{c}], 112) END))")
    return None


def emit_table(table: Table, dec: Decisions, tables: set[str]) -> str:
    """One CREATE TABLE.

    Column notes go ABOVE the column, never after it. A trailing note in a
    generated file eventually swallows the comma that follows it, and the reason
    a column exists is worth carrying across the port.
    """
    pk_cols = [c.name for c in table.columns if c.primary_key]
    if len(pk_cols) > 1:
        raise Unsupported(f"{table.name}: more than one column carries an inline PRIMARY KEY")

    entries: list[tuple[list[str], str]] = []      # (comment lines, definition)
    parsed: list[tuple[list[str], str]] = []
    n_check = 0
    n_unique = 0

    for col in table.columns:
        sql_type, cls = column_type(table, col, dec)
        piece = [f"    [{col.name}]", sql_type]

        # INTEGER PRIMARY KEY is a rowid alias in SQLite: the value is generated
        # when it is not supplied. IDENTITY is the same bargain in SQL Server --
        # unless a CHECK pins the key (ticket_numbering's id = 1): a checked key
        # is a chosen value, and IDENTITY would refuse the one value allowed.
        if col.primary_key and col.sqlite_type == "INTEGER" and len(pk_cols) == 1 and not col.checks:
            piece.append("IDENTITY(1,1)")

        piece.append("NOT NULL" if (col.not_null or col.primary_key) else "NULL")

        if col.default is not None:
            piece.append(f"CONSTRAINT [DF_{table.name}_{col.name}] DEFAULT ({col.default})")
        if col.primary_key and len(pk_cols) == 1:
            piece.append(f"CONSTRAINT [PK_{table.name}] PRIMARY KEY")
        if col.references is not None:
            ref_table, ref_col = col.references
            piece.append(
                f"CONSTRAINT [FK_{table.name}_{col.name}] "
                f"REFERENCES {SCHEMA}.[{ref_table}]([{ref_col}])")
        for check in col.checks:
            n_check += 1
            piece.append(
                f"CONSTRAINT [CK_{table.name}_{n_check:02d}] "
                f"CHECK ({expression(check, tables)})")

        entries.append((col.comment or [], " ".join(piece)))

        if cls in ("DATE_TEXT", "TIMESTAMP_TEXT"):
            parsed.append(([], "    " + _parsed_column(table, col, cls)))

    if parsed:
        head, definition = parsed[0]
        parsed[0] = (["Dates are kept as the source wrote them. These read them,",
                      "without deciding for the reader which shape was meant."], definition)
        entries.extend(parsed)

    for constraint in table.constraints:
        head_word = constraint.split(" ", 1)[0].upper()
        body, _ = _balanced(constraint, constraint.index("("))
        if head_word in ("PRIMARY", "UNIQUE"):
            cols = ", ".join(f"[{c.strip()}]" for c in body.split(","))
            keyword = "PRIMARY KEY" if head_word == "PRIMARY" else "UNIQUE"
            if head_word == "PRIMARY":
                name = f"PK_{table.name}"
            else:
                # A second UNIQUE on one table must not reuse the first's name.
                n_unique += 1
                name = f"UQ_{table.name}" + (f"_{n_unique:02d}" if n_unique > 1 else "")
            entries.append(([], f"    CONSTRAINT [{name}] {keyword} ({cols})"))
        elif head_word == "CHECK":
            n_check += 1
            entries.append(([], f"    CONSTRAINT [CK_{table.name}_{n_check:02d}] "
                                f"CHECK ({expression(body, tables)})"))
        else:
            raise Unsupported(f"{table.name}: table constraint {constraint!r}")

    lines: list[str] = [f"CREATE TABLE {SCHEMA}.[{table.name}] ("]
    for n, (comment, definition) in enumerate(entries):
        if comment:
            if n:
                lines.append("")
            lines.extend(f"    -- {c}" for c in comment)
        lines.append(definition + ("," if n < len(entries) - 1 else ""))
    lines.append(");")
    return "\n".join(lines)


_NOT_NULL_TERM = re.compile(r"^(\w+)\s+IS\s+NOT\s+NULL$", re.I)


def emit_index(index: Index, nullable: set[str] | None = None) -> str:
    """A plain index, or a UNIQUE one with a WHERE that keeps NULLs out of it.

    The two engines disagree about NULL in a unique index: SQLite lets any number
    of rows hold NULL, SQL Server lets exactly one. Ported as written, the second
    contact with no AD GUID would be refused on the live server and nowhere else.
    So a UNIQUE index over a nullable column must say `WHERE col IS NOT NULL`,
    which is a no-op in SQLite and a filtered index in SQL Server; one that does
    not say it stops the build rather than changing meaning on the port.
    """
    cols = [c.strip() for c in index.columns.split(",")]
    guarded: list[str] = []
    if index.where is not None:
        for term in re.split(r"\s+AND\s+", index.where, flags=re.I):
            m = _NOT_NULL_TERM.match(term.strip())
            if not m or m.group(1) not in cols:
                raise Unsupported(
                    f"{index.name}: partial index condition {index.where!r} has no "
                    "port decided; only '<indexed column> IS NOT NULL' terms are recognised")
            guarded.append(m.group(1))
    if index.unique:
        if nullable is None:
            raise Unsupported(f"{index.name}: UNIQUE index on unknown table {index.table!r}")
        open_nulls = [c for c in cols if c in nullable and c not in guarded]
        if open_nulls:
            raise Unsupported(
                f"{index.name}: UNIQUE over nullable {', '.join(open_nulls)} means many "
                "NULLs in SQLite and one in SQL Server; add WHERE "
                + " AND ".join(f"{c} IS NOT NULL" for c in open_nulls))
    kind = "UNIQUE INDEX" if index.unique else "INDEX"
    where = (" WHERE " + " AND ".join(f"[{c}] IS NOT NULL" for c in guarded)) if guarded else ""
    col_sql = ", ".join(f"[{c}]" for c in cols)
    return f"CREATE {kind} [{index.name}] ON {SCHEMA}.[{index.table}] ({col_sql}){where};"


def emit_trigger(trigger: Trigger, number: int, tables: set[str]) -> str:
    if trigger.event not in ("INSERT", "UPDATE"):
        raise Unsupported(f"{trigger.name}: {trigger.event} triggers have no port decided")
    if trigger.raise_action not in ("ABORT", "ROLLBACK", "FAIL"):
        raise Unsupported(f"{trigger.name}: RAISE({trigger.raise_action}) has no port decided")
    if trigger.when is None:
        raise Unsupported(f"{trigger.name}: a trigger with no WHEN would fire on every row")

    when = expression(trigger.when, tables)
    if re.search(r"\bOLD\.", when, re.I):
        # SQL Server's OLD is the deleted table, which needs a join on the key
        # that nothing here decides. Refused rather than emitted unbound.
        raise Unsupported(f"{trigger.name}: OLD. in a trigger condition has no port decided")
    when = re.sub(r"\bNEW\.", f"{TRIGGER_ALIAS}.", when)

    guard = f"EXISTS (SELECT 1 FROM inserted AS {TRIGGER_ALIAS} WHERE {when})"
    if trigger.update_of:
        cols = " OR ".join(f"UPDATE({c})" for c in trigger.update_of)
        guard = f"({cols})\n       AND {guard}"

    message = trigger.message.replace("'", "''")
    return f"""CREATE TRIGGER {SCHEMA}.[{trigger.name}]
ON {SCHEMA}.[{trigger.table}]
AFTER {trigger.event}
AS
BEGIN
    SET NOCOUNT ON;
    IF {guard}
    BEGIN
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW {50000 + number}, N'{message}', 1;
    END
END"""


# ------------------------------------------------------------------ script

def _comment_block(text: str, indent: str = "") -> list[str]:
    return [indent + line for line in text.splitlines()] if text else []


def generate(schema_dir: Path = SCHEMA_DIR, decisions: Path = DECISIONS) -> str:
    # schema/local/ (the break-glass and API credential tables) was kept out of
    # the port while the spine on SQL Server was to be the commercial record
    # alone. D7 (25 Sep 2026) puts the whole desk there, and a desk signs people
    # in, so those tables go too: scrypt hashes and token hashes, never a secret.
    files = ([(p.name, p.read_text(encoding="utf-8")) for p in sorted(schema_dir.glob("*.sql"))]
             + [(f"local/{p.name}", p.read_text(encoding="utf-8"))
                for p in sorted((schema_dir / "local").glob("*.sql"))])
    tables, indexes, triggers, alters = parse_schema(files)
    dec = Decisions(decisions)
    names = {t.name for t in tables}

    live = {f"{t.name}.{c.name}" for t in tables for c in t.columns
            if c.sqlite_type in ("TEXT", "REAL")}
    live |= {f"{a.table}.{a.column.name}" for a in alters
             if a.column.sqlite_type in ("TEXT", "REAL")}
    stale = dec.unused(live)
    if stale:
        raise Unsupported(
            "tsql-decisions.json decides widths for columns that no longer exist: "
            + ", ".join(stale) + ". Remove them, so the decisions file cannot "
            "drift away from the schema either.")

    by_name = {t.name: t for t in tables}
    nullable = {t.name: {c.name for c in t.columns if not (c.not_null or c.primary_key)}
                for t in tables}
    for a in alters:
        if not a.column.not_null:
            nullable.setdefault(a.table, set()).add(a.column.name)
    objects = ([f"{SCHEMA}.{t.name}" for t in tables]
               + [f"{SCHEMA}.{i.name}" for i in indexes]
               + [f"{SCHEMA}.{t.name}" for t in triggers])

    out: list[str] = []
    w = out.append

    w(f"""/*==============================================================================
  PMC / Dada IT -- PSA spine, SQL Server schema
  Target: {TARGET_SERVER}, database {TARGET_DATABASE}, schema [{SCHEMA}]

  GENERATED FILE -- DO NOT EDIT.
      source:     platform/psa-spine/schema/  (the SQLite files, the one source)
      translator: platform/psa-spine/tools/sqlite_to_tsql.py
      decisions:  platform/psa-spine/tools/tsql-decisions.json
      regenerate: python3 tools/sqlite_to_tsql.py --write
      drift gate: python3 tools/sqlite_to_tsql.py --check   (CI runs this)

  An edit made here is lost on the next regeneration and, worse, is invisible in
  the SQLite copy that the importer and the reports actually run against. Change
  the files under schema/ and regenerate.

  ---------------------------------------------------------------------------
  HOW TO RUN IT

      sqlcmd -S "{TARGET_SERVER}" -d {TARGET_DATABASE} -i PMC_PSA_Spine_SqlServer.sql

  IT PREVIEWS BY DEFAULT. @Apply is 0 below and nothing is created until you set
  it to 1. That is the discipline this programme uses for anything that touches a
  live database.

      @Apply         0 = print the plan and change nothing. 1 = create.
      @AllowExisting 0 = refuse if anything already exists in [{SCHEMA}] (the default:
                     this script is not meant to run twice). 1 = create only what
                     is missing, which makes a re-run idempotent.

  The whole apply runs in one transaction with a verify gate at the end: if the
  object counts do not match what this script intended to create, it rolls the
  transaction back and throws. A partial schema is worse than none.

  ROLLBACK is at the foot of this file, commented out, in dependency order.

  ---------------------------------------------------------------------------
  WHAT THIS SCRIPT IS NOT

  It creates structure only. It seeds no data, no fee amount, no board owner and
  no signed clinical floor -- those are decisions with names attached and the
  schema refuses to hold them until somebody with the authority makes them.

  VERIFIED on SQL Server 2022 Express (16.0) in a container, 25 Sep 2026: applies,
  passes its own gate, both triggers fire. NOT VERIFIED on {TARGET_SERVER} itself,
  which no session here can reach. Run it with @Apply = 0 first and read the plan.

  Comments in this file never contain a slash-star pair: T-SQL nests block
  comments, and the first run found the header itself unterminated because of one.
==============================================================================*/

SET NOCOUNT ON;

-- XACT_ABORT means a failure anywhere in the apply below takes the whole
-- transaction with it rather than leaving half a schema behind.
SET XACT_ABORT ON;

DECLARE @Apply         BIT = 0;      -- <<<< set to 1 to make changes
DECLARE @AllowExisting BIT = 0;      -- <<<< set to 1 to fill in what is missing

DECLARE @Schema        SYSNAME = N'{SCHEMA}';
DECLARE @Database      SYSNAME = N'{TARGET_DATABASE}';  -- D7's name; the desk refuses any other
DECLARE @DbName        SYSNAME = DB_NAME();   -- RAISERROR takes variables, not calls
DECLARE @Existing      INT;
DECLARE @Tables        INT;
DECLARE @Triggers      INT;
DECLARE @Indexes       INT;

/*------------------------------------------------------------------ preflight */

IF @DbName <> @Database
BEGIN
    RAISERROR(N'Refusing: connected to database [%s], expected [%s] on {TARGET_SERVER}. Nothing was changed.',
              16, 1, @DbName, @Database);
    RETURN;
END;

SELECT @Existing = COUNT(*)
  FROM sys.objects o
  JOIN sys.schemas s ON s.schema_id = o.schema_id
 WHERE s.name = @Schema AND o.type IN ('U', 'TR');

IF @Existing > 0 AND @AllowExisting = 0
BEGIN
    RAISERROR(N'Refusing: schema [%s] already holds %d objects. This script is not meant to run twice. Set @AllowExisting = 1 to create only what is missing.',
              16, 1, @Schema, @Existing);
    RETURN;
END;

/*-------------------------------------------------------------------- preview */

IF @Apply = 0
BEGIN
    PRINT N'PREVIEW ONLY. Nothing has been changed.';
    PRINT N'';
    PRINT N'Would create schema [{SCHEMA}] and the following, in this order:';""")

    for name in objects:
        w(f"    PRINT N'    {name}';")

    w(f"""    PRINT N'';
    PRINT N'  {len(tables)} tables, {len(indexes)} indexes, {len(triggers)} triggers.';
    PRINT N'  Existing objects in [{SCHEMA}] right now: ' + CAST(@Existing AS NVARCHAR(10)) + N'.';
    PRINT N'';
    PRINT N'Re-run with @Apply = 1 to create them.';
    RETURN;
END;

/*---------------------------------------------------------------------- apply */
--
-- CREATE SCHEMA and CREATE TRIGGER must each be the first statement in their
-- batch, so those two go through sp_executesql. That keeps the whole file one
-- batch, which is what lets @Apply and the verify gate at the foot still be in
-- scope down there. Tables and indexes carry no such rule and are written plainly.

BEGIN TRANSACTION;

IF SCHEMA_ID(@Schema) IS NULL
    EXEC sp_executesql N'CREATE SCHEMA {SCHEMA}';
""")

    for table in tables:
        w("")
        w(f"-- {'-' * 74}")
        w(f"-- {table.name}   (from schema/{table.source_file})")
        if table.comment:
            out.extend(_comment_block(table.comment))
        w(f"IF OBJECT_ID(N'{SCHEMA}.[{table.name}]', N'U') IS NULL")
        w("BEGIN")
        w(emit_table(table, dec, names))
        w("END;")

    if alters:
        w("")
        w(f"-- {'=' * 74}")
        w("-- COLUMNS ADDED TO TABLES THAT ALREADY EXIST")
        w("--")
        w("-- Guarded by COL_LENGTH so a re-run adds nothing twice. A schema that can")
        w("-- only be created and never evolved is not a schema, but on a live clinical")
        w("-- database the only safe evolution is ADD: the translator refuses a rename")
        w("-- or a drop rather than losing a column quietly.")
    for alter in alters:
        table = by_name.get(alter.table)
        if table is None:
            raise Unsupported(
                f"ALTER TABLE {alter.table} adds a column to a table this schema "
                f"never creates")
        w("")
        if alter.comment:
            out.extend(_comment_block(alter.comment))
        sql_type, cls = column_type(table, alter.column, dec)
        piece = [f"ALTER TABLE {SCHEMA}.[{alter.table}] ADD [{alter.column.name}]", sql_type]
        # An added column is NULL by default and must be: the rows already there
        # have no value for it, and inventing one is how a migration lies.
        if alter.column.not_null:
            raise Unsupported(
                f"{alter.table}.{alter.column.name} is added NOT NULL. Existing rows "
                f"have no value for it, so either give it a DEFAULT or let it be NULL "
                f"rather than inventing data.")
        piece.append("NULL")
        if alter.column.default is not None:
            piece.append(f"CONSTRAINT [DF_{alter.table}_{alter.column.name}] "
                         f"DEFAULT ({alter.column.default})")
        if alter.column.references is not None:
            ref_table, ref_col = alter.column.references
            piece.append(f"CONSTRAINT [FK_{alter.table}_{alter.column.name}] "
                         f"REFERENCES {SCHEMA}.[{ref_table}]([{ref_col}])")
        for n, check in enumerate(alter.column.checks, start=1):
            piece.append(f"CONSTRAINT [CK_{alter.table}_{alter.column.name}_{n:02d}] "
                         f"CHECK ({expression(check, names)})")
        w(f"IF COL_LENGTH(N'{SCHEMA}.[{alter.table}]', N'{alter.column.name}') IS NULL")
        w(" ".join(piece) + ";")

    if indexes:
        w("")
        w(f"-- {'-' * 74}")
        w("-- indexes")
    for index in indexes:
        w("")
        if index.comment:
            out.extend(_comment_block(index.comment))
        w(f"IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'{index.name}'"
          f" AND object_id = OBJECT_ID(N'{SCHEMA}.[{index.table}]'))")
        w(emit_index(index, nullable.get(index.table)))

    w("")
    w(f"-- {'=' * 74}")
    w("-- THE GATE")
    w("--")
    w("-- These two triggers are the reason for the port. A variation-path ticket")
    w("-- must not be able to consume effort, or be closed, while no variation is")
    w("-- attached: the work then stays visible as work nobody has agreed to pay")
    w("-- for, instead of disappearing into a fixed monthly fee.")
    w("--")
    w("-- Two differences from the SQLite original, both deliberate:")
    w("--")
    w("--   * SQL Server has no BEFORE trigger. SQLite refuses the offending")
    w("--     statement and leaves the transaction alone; the nearest honest")
    w("--     equivalent here is an AFTER trigger that rolls the transaction back")
    w("--     and throws. The write is still refused. The blast radius is larger:")
    w("--     a caller batching this insert with other work loses that work too.")
    w("--     That is the correct trade -- a gate that yields under a batch is not")
    w("--     a gate -- but it has to be said out loud, so it is said here.")
    w("--")
    w("--   * RAISE(ABORT, ...) becomes THROW, whose message is the SQLite message")
    w("--     word for word. Anyone who hits it should be able to search for the")
    w("--     text and find this file and the schema it came from.")

    for number, trigger in enumerate(triggers, start=1):
        w("")
        if trigger.comment:
            out.extend(_comment_block(trigger.comment))
        of = f" OF {', '.join(trigger.update_of)}" if trigger.update_of else ""
        w(f"-- from schema/{trigger.source_file}, where it reads: "
          f"{trigger.timing} {trigger.event}{of} ON {trigger.table}")
        w(f"IF OBJECT_ID(N'{SCHEMA}.[{trigger.name}]', N'TR') IS NULL")
        w("EXEC sp_executesql N'")
        w(emit_trigger(trigger, number, names).replace("'", "''"))
        w("';")

    w(f"""
/*----------------------------------------------------------- the verify gate */
--
-- Count what is actually there before committing. If the schema is short an
-- object the transaction goes back: a half-created spine that looks installed is
-- worse than one that plainly is not.

SELECT @Tables = COUNT(*) FROM sys.tables t
  JOIN sys.schemas s ON s.schema_id = t.schema_id WHERE s.name = @Schema;
SELECT @Triggers = COUNT(*) FROM sys.triggers tr
  JOIN sys.tables t ON t.object_id = tr.parent_id
  JOIN sys.schemas s ON s.schema_id = t.schema_id WHERE s.name = @Schema;
SELECT @Indexes = COUNT(*) FROM sys.indexes i
  JOIN sys.tables t ON t.object_id = i.object_id
  JOIN sys.schemas s ON s.schema_id = t.schema_id
 WHERE s.name = @Schema AND i.type = 2 AND i.is_primary_key = 0 AND i.is_unique_constraint = 0;

IF @Tables <> {len(tables)} OR @Triggers <> {len(triggers)} OR @Indexes < {len(indexes)}
BEGIN
    ROLLBACK TRANSACTION;
    RAISERROR(N'VERIFY FAILED: found %d tables (expected {len(tables)}), %d triggers (expected {len(triggers)}), %d indexes (expected at least {len(indexes)}). Rolled back; nothing was created.',
              16, 1, @Tables, @Triggers, @Indexes);
    RETURN;
END;

COMMIT TRANSACTION;

PRINT N'Created: ' + CAST(@Tables AS NVARCHAR(10)) + N' tables, '
                   + CAST(@Triggers AS NVARCHAR(10)) + N' triggers, '
                   + CAST(@Indexes AS NVARCHAR(10)) + N' indexes in [{SCHEMA}].';
PRINT N'The gate is live: a variation-path ticket cannot consume effort or close';
PRINT N'with no variation attached.';
PRINT N'';
PRINT N'Seeded: nothing. No board is live, no clinical floor is signed and no SLA';
PRINT N'target is enforced until somebody with the authority says so.';
""")

    w("")
    w("/*=============================================================================")
    w("  ROLLBACK")
    w("")
    w("  In dependency order, children first. Uncomment and run against the same")
    w("  database. It drops the schema and everything this script created in it, so")
    w("  read it before you run it: anything imported since is dropped with it.")
    w("")
    for trigger in triggers:
        w(f"    DROP TRIGGER IF EXISTS {SCHEMA}.[{trigger.name}];")
    # A column added later can point at a table created after its own, so table
    # order alone is not dependency order: those keys go first.
    for alter in reversed(alters):
        if alter.column.references:
            w(f"    ALTER TABLE {SCHEMA}.[{alter.table}] DROP CONSTRAINT IF EXISTS "
              f"[FK_{alter.table}_{alter.column.name}];")
    for table in reversed(tables):
        w(f"    DROP TABLE IF EXISTS {SCHEMA}.[{table.name}];")
    w(f"    DROP SCHEMA IF EXISTS {SCHEMA};")
    w("=============================================================================*/")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--write", action="store_true", help="write the generated script")
    p.add_argument("--check", action="store_true",
                   help="fail if the committed script is not what the source produces")
    p.add_argument("--out", default=str(OUTPUT))
    a = p.parse_args(argv)

    try:
        text = generate()
    except Unsupported as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    out = Path(a.out)
    if a.check:
        if not out.exists():
            print(f"DRIFT: {out} does not exist. Run --write.", file=sys.stderr)
            return 1
        current = out.read_text(encoding="utf-8")
        if current != text:
            print(f"DRIFT: {out} is not what schema/*.sql produces today.", file=sys.stderr)
            print("Two copies of a commercial rule have diverged. Run --write and "
                  "commit the result with the change.", file=sys.stderr)
            return 1
        print(f"ok: {out.name} is in step with schema/*.sql")
        return 0

    if a.write:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}")
        return 0

    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
