"""
sql_constraint_parser.py

A deterministic reader for business rules that are written as SQL
DDL / constraints rather than prose — `CREATE TABLE` column
definitions, `CHECK (...)` expressions, `ALTER TABLE ... ADD
CONSTRAINT`, `NOT NULL`, `UNIQUE`, `VARCHAR(n)` lengths, and so on.

This exists alongside the Groq-based RULES_PARSER_PROMPT rather than
instead of it. The LLM is taught to read SQL too (see
groq_service.RULES_PARSER_PROMPT), but a model can misread a CHECK
expression or skip a column silently, and there was previously no
safety net for that the way there already is for natural-language
rules (`_infer_text_constraints`). This module is that safety net:
it parses the raw document text directly, with no model involved, so
a document written entirely as SQL constraints still produces working
rules even if the LLM extraction misses them.

Deliberately conservative: a clause this parser doesn't recognise is
left alone rather than guessed at, the same "do not invent
constraints" rule the rest of the rules pipeline follows.
"""
import re

_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"

_LENGTH_TYPE_RE = re.compile(
    r"^(N?VARCHAR|N?CHAR|CHARACTER\s+VARYING|CHARACTER)\s*\(\s*(\d+)\s*\)",
    re.IGNORECASE,
)

_INTEGER_TYPES = ("INT", "INTEGER", "SMALLINT", "BIGINT", "TINYINT")
_NUMBER_TYPES = ("DECIMAL", "NUMERIC", "FLOAT", "REAL", "DOUBLE", "MONEY")
_DATE_TYPES = ("DATE", "DATETIME", "DATETIME2", "TIMESTAMP", "SMALLDATETIME")


def _find_matching_paren(text: str, open_idx: int) -> int:
    """
    Index of the ')' matching the '(' at `open_idx`, skipping over
    nested parens and single-quoted string literals (where SQL
    escapes a literal quote as two: '' ). Returns -1 if unbalanced.
    """
    depth = 0
    in_string = False
    i = open_idx
    length = len(text)

    while i < length:
        ch = text[i]

        if in_string:
            if ch == "'":
                if i + 1 < length and text[i + 1] == "'":
                    i += 2
                    continue
                in_string = False
        elif ch == "'":
            in_string = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i

        i += 1

    return -1


def _split_top_level(text: str, pattern: str) -> list:
    """
    Split `text` on `pattern` (a regex, matched case-insensitively)
    but only where paren depth is 0 and not inside a quoted string —
    so a comma inside CHECK(col IN ('A, B')) never splits the list.
    """
    parts = []
    depth = 0
    in_string = False
    start = 0
    i = 0
    length = len(text)
    sep_re = re.compile(pattern, re.IGNORECASE)

    while i < length:
        ch = text[i]

        if in_string:
            if ch == "'":
                if i + 1 < length and text[i + 1] == "'":
                    i += 2
                    continue
                in_string = False
            i += 1
            continue

        if ch == "'":
            in_string = True
            i += 1
            continue

        if ch == "(":
            depth += 1
            i += 1
            continue

        if ch == ")":
            depth -= 1
            i += 1
            continue

        if depth == 0:
            match = sep_re.match(text, i)
            if match:
                parts.append(text[start:i])
                i = match.end()
                start = i
                continue

        i += 1

    parts.append(text[start:])
    return [p for p in (p.strip() for p in parts) if p]


def _split_and_clauses(expression: str) -> list:
    """
    Split a CHECK expression on top-level AND, the same way
    _split_top_level does — except the AND inside "col BETWEEN a AND
    b" is part of that syntax, not a clause separator, so it must
    never split there.
    """
    parts = []
    depth = 0
    in_string = False
    start = 0
    i = 0
    length = len(expression)
    pending_between = False
    between_re = re.compile(r"\bBETWEEN\b", re.IGNORECASE)
    and_re = re.compile(r"\bAND\b", re.IGNORECASE)

    while i < length:
        ch = expression[i]

        if in_string:
            if ch == "'":
                if i + 1 < length and expression[i + 1] == "'":
                    i += 2
                    continue
                in_string = False
            i += 1
            continue

        if ch == "'":
            in_string = True
            i += 1
            continue

        if ch == "(":
            depth += 1
            i += 1
            continue

        if ch == ")":
            depth -= 1
            i += 1
            continue

        if depth == 0:
            between_match = between_re.match(expression, i)
            if between_match:
                pending_between = True
                i = between_match.end()
                continue

            and_match = and_re.match(expression, i)
            if and_match:
                if pending_between:
                    pending_between = False
                    i = and_match.end()
                    continue
                parts.append(expression[start:i])
                i = and_match.end()
                start = i
                continue

        i += 1

    parts.append(expression[start:])
    return [p.strip() for p in parts if p.strip()]


def _unwrap_parens(clause: str) -> str:
    """Strip one layer of wrapping parens — "(col > 1)" -> "col > 1"
    — but only when the first '(' actually matches the last ')', so
    "col IN ('A', 'B')" is left alone rather than losing its close
    paren to a blind character-class strip."""
    clause = clause.strip()
    while clause.startswith("(") and clause.endswith(")"):
        close_idx = _find_matching_paren(clause, 0)
        if close_idx != len(clause) - 1:
            break
        clause = clause[1:-1].strip()
    return clause


def _humanize(identifier: str) -> str:
    words = re.split(r"[_\-]+", identifier.strip())
    return " ".join(w.capitalize() for w in words if w)


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def _parse_value_list(inner: str) -> list:
    values = []
    for item in _split_top_level(inner, r","):
        values.append(_strip_quotes(item))
    return values


def _apply_type_constraints(data_type: str, constraints: dict) -> None:
    data_type = data_type.strip()

    length_match = _LENGTH_TYPE_RE.match(data_type)
    if length_match:
        size = int(length_match.group(2))
        base = length_match.group(1).upper()
        if base.endswith("CHAR") and "VARYING" not in base and "VARCHAR" not in base:
            constraints.setdefault("exact_length", size)
        else:
            constraints.setdefault("max_length", size)
        return

    upper = data_type.upper()
    first_word = re.split(r"[\s(]", upper, 1)[0]

    if first_word in _INTEGER_TYPES:
        constraints.setdefault("format", "integer")
    elif first_word in _NUMBER_TYPES:
        constraints.setdefault("format", "number")
    elif first_word in _DATE_TYPES:
        constraints.setdefault("format", "date")


def _parse_check_expression(expression: str) -> dict:
    """
    Parse the inside of a CHECK(...) expression (already stripped of
    the outer parens) into {column_name_lower: constraints}.

    A single CHECK can name more than one column once its clauses are
    ANDed together — "length > 0 AND width > 0 AND height > 0"
    constrains three separate columns in one constraint — so each
    clause is attributed to its own column rather than everything
    being folded into one flat dict under a single guessed column
    (which would let same-named keys like "min_value" from different
    columns silently overwrite one another).
    """
    by_column = {}

    def _set(column, key, value):
        if not column:
            return
        by_column.setdefault(column.lower(), {})[key] = value

    for clause in _split_and_clauses(expression):
        clause = _unwrap_parens(clause)

        # LEN(col) / LENGTH(col) — length checks, not value checks.
        len_match = re.match(
            r"(?:LEN|LENGTH|CHAR_LENGTH)\s*\(\s*(" + _IDENTIFIER + r")\s*\)\s*"
            r"(=|>=|<=|>|<)\s*(\d+)",
            clause,
            re.IGNORECASE,
        )
        if len_match:
            column, op, num = len_match.group(1), len_match.group(2), int(len_match.group(3))
            if op == "=":
                _set(column, "exact_length", num)
            elif op in (">=", ">"):
                # Loose on strict-vs-inclusive here, same as the
                # natural-language "at least N characters" reading
                # elsewhere in this file — treated as the boundary
                # itself, not boundary+1.
                _set(column, "min_length", num)
            elif op in ("<=", "<"):
                _set(column, "max_length", num)
            continue

        len_between = re.match(
            r"(?:LEN|LENGTH|CHAR_LENGTH)\s*\(\s*(" + _IDENTIFIER + r")\s*\)\s*"
            r"BETWEEN\s+(\d+)\s+AND\s+(\d+)",
            clause,
            re.IGNORECASE,
        )
        if len_between:
            column = len_between.group(1)
            _set(column, "min_length", int(len_between.group(2)))
            _set(column, "max_length", int(len_between.group(3)))
            continue

        # col IN ('A', 'B', 'C')  /  col NOT IN (...)
        in_match = re.match(
            r"(" + _IDENTIFIER + r")\s*(NOT\s+)?IN\s*\(", clause, re.IGNORECASE
        )
        if in_match:
            column = in_match.group(1)
            open_idx = clause.index("(", in_match.end() - 1)
            close_idx = _find_matching_paren(clause, open_idx)
            if close_idx != -1:
                values = _parse_value_list(clause[open_idx + 1:close_idx])
                _set(column, "forbidden_values" if in_match.group(2) else "allowed_values", values)
            continue

        # col BETWEEN a AND b
        between_match = re.match(
            r"(" + _IDENTIFIER + r")\s+BETWEEN\s+([\d.]+)\s+AND\s+([\d.]+)",
            clause,
            re.IGNORECASE,
        )
        if between_match:
            column = between_match.group(1)
            _set(column, "min_value", float(between_match.group(2)))
            _set(column, "max_value", float(between_match.group(3)))
            continue

        # col LIKE 'PREFIX%'  /  col LIKE '%SUFFIX'
        like_match = re.match(
            r"(" + _IDENTIFIER + r")\s+(NOT\s+)?LIKE\s+'([^']*)'",
            clause,
            re.IGNORECASE,
        )
        if like_match and not like_match.group(2):
            column = like_match.group(1)
            pattern = like_match.group(3)
            starts_wild = pattern.startswith("%")
            ends_wild = pattern.endswith("%")
            core = pattern.strip("%")
            if ends_wild and not starts_wild and core:
                _set(column, "prefix", core)
            elif starts_wild and not ends_wild and core:
                _set(column, "suffix", core)
            elif not starts_wild and not ends_wild and core:
                _set(column, "exact_length", len(core))
            continue

        # col ~ 'regex'  (Postgres)   /   col REGEXP 'regex'  (MySQL)
        regex_match = re.match(
            r"(" + _IDENTIFIER + r")\s*(?:~|REGEXP)\s*'([^']*)'",
            clause,
            re.IGNORECASE,
        )
        if regex_match:
            _set(regex_match.group(1), "regex", regex_match.group(2))
            continue

        # col >= n / col > n / col <= n / col < n / col = n
        cmp_match = re.match(
            r"(" + _IDENTIFIER + r")\s*(>=|<=|>|<|=)\s*(-?[\d.]+)",
            clause,
        )
        if cmp_match:
            column, op, num = cmp_match.group(1), cmp_match.group(2), float(cmp_match.group(3))
            # Loose on strict-vs-inclusive, matching this codebase's
            # existing "greater than N" / "less than N" natural-
            # language handling — a boundary count could otherwise
            # come out wrong for decimal columns (a hard-coded +1 is
            # meaningless for "unit_rate > 0" on a DECIMAL column).
            if op in (">=", ">"):
                _set(column, "min_value", num)
            elif op in ("<=", "<"):
                _set(column, "max_value", num)
            elif op == "=":
                _set(column, "min_value", num)
                _set(column, "max_value", num)
            continue

    return by_column


def _parse_column_definition(segment: str) -> dict:
    """
    Parse one column definition from inside a CREATE TABLE's
    parentheses, e.g.:

        tariff_code VARCHAR(10) NOT NULL CHECK (tariff_code LIKE 'TRF%')

    Returns {} if this segment is a table-level clause (PRIMARY KEY
    (...), FOREIGN KEY (...), a standalone CONSTRAINT / UNIQUE list)
    rather than an actual column.
    """
    segment = segment.strip()
    if not segment:
        return {}

    first_word_match = re.match(r"^(" + _IDENTIFIER + r")", segment)
    if not first_word_match:
        return {}

    # Table-level clauses ("PRIMARY KEY (...)", "FOREIGN KEY (...)
    # REFERENCES ...", a named "CONSTRAINT ... CHECK (...)", a
    # bare "UNIQUE (...)" list) are not a single column's own
    # definition — skip them here; a named CHECK constraint is still
    # picked up separately by _find_standalone_checks.
    upper_segment = segment.upper()
    if re.match(r"^(PRIMARY\s+KEY|FOREIGN\s+KEY|CONSTRAINT|UNIQUE|INDEX|KEY|CHECK)\b", upper_segment):
        return {}

    first_word = first_word_match.group(1).upper()

    column_name = first_word_match.group(1)
    rest = segment[first_word_match.end():].strip()

    constraints = {}

    # Data type is whatever comes next, up to NOT/NULL/UNIQUE/DEFAULT/
    # CHECK/PRIMARY/REFERENCES or the end of the segment.
    type_match = re.match(
        r"([A-Za-z][A-Za-z0-9_ ]*?(?:\(\s*\d+(?:\s*,\s*\d+)?\s*\))?)"
        r"(?=\s+(?:NOT\s+NULL|NULL|UNIQUE|DEFAULT|CHECK|PRIMARY|REFERENCES)\b|\s*$)",
        rest,
        re.IGNORECASE,
    )
    if type_match:
        _apply_type_constraints(type_match.group(1), constraints)

    if re.search(r"\bNOT\s+NULL\b", rest, re.IGNORECASE):
        constraints["required"] = True

    if re.search(r"\bPRIMARY\s+KEY\b", rest, re.IGNORECASE):
        constraints["required"] = True
        constraints["unique"] = True

    if re.search(r"\bUNIQUE\b", rest, re.IGNORECASE):
        constraints["unique"] = True

    # CHECK(...) is deliberately not read here even when it sits
    # inside this column's own definition — extract_rules_from_sql
    # scans every CHECK(...) in the whole document in one pass
    # instead, since a single CHECK can name more than one column
    # (see _parse_check_expression) and this function only has one
    # column's constraints dict to return.

    return {"column": column_name, "constraints": constraints}


def _parse_table_level_clause(segment: str) -> dict:
    """
    A table-level "PRIMARY KEY (col1, col2)" or "UNIQUE (col1, col2)"
    names columns rather than defining one — _parse_column_definition
    deliberately skips these, so the columns they name would
    otherwise lose that constraint entirely. Returns {} for anything
    else (FOREIGN KEY, a named CONSTRAINT, ...).
    """
    segment = segment.strip()
    upper_segment = segment.upper()

    for keyword, constraints in (
        ("PRIMARY KEY", {"required": True, "unique": True}),
        ("UNIQUE", {"unique": True}),
    ):
        match = re.match(r"^" + keyword.replace(" ", r"\s+") + r"\s*\(", upper_segment)
        if not match:
            continue

        open_idx = match.end() - 1
        close_idx = _find_matching_paren(segment, open_idx)
        if close_idx == -1:
            return {}

        columns = [
            col.strip().strip("\"[]`")
            for col in segment[open_idx + 1:close_idx].split(",")
        ]

        return {
            "columns": [c for c in columns if c],
            "constraints": constraints,
        }

    return {}


def _find_create_table_blocks(text: str) -> list:
    """List of (table_name, body_between_the_outer_parens) tuples."""
    blocks = []
    for match in re.finditer(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
        r"[\[\"`]?(" + _IDENTIFIER + r")[\]\"`]?\s*\(",
        text,
        re.IGNORECASE,
    ):
        open_idx = match.end() - 1
        close_idx = _find_matching_paren(text, open_idx)
        if close_idx == -1:
            continue
        blocks.append((match.group(1), text[open_idx + 1:close_idx]))
    return blocks


def _find_all_checks(text: str) -> dict:
    """
    Every CHECK(...) in the document, wherever it sits — inline in a
    CREATE TABLE column, a named table-level CONSTRAINT, an ALTER
    TABLE ... ADD CONSTRAINT, or a bare constraint line on its own —
    parsed in one pass and merged into {column_name_lower:
    constraints}. One CHECK naming several columns (an ANDed
    multi-column clause) contributes to each of them.
    """
    by_column = {}

    for match in re.finditer(r"\bCHECK\s*\(", text, re.IGNORECASE):
        open_idx = match.end() - 1
        close_idx = _find_matching_paren(text, open_idx)
        if close_idx == -1:
            continue
        inner = text[open_idx + 1:close_idx]

        for column_key, constraints in _parse_check_expression(inner).items():
            by_column.setdefault(column_key, {}).update(constraints)

    return by_column


def extract_rules_from_sql(text: str) -> list:
    """
    Read `text` for SQL constraint syntax and return a list of rule
    dicts shaped like {"name", "description", "task", "data_type",
    "keywords", "expected_outcome", "constraints"} — the same shape
    `parse_rules_to_json` normalizes LLM output into, so both sources
    can be merged on equal footing.

    Returns [] when the text has no recognisable SQL in it at all,
    so callers can skip the merge step cheaply.
    """
    if not text or "(" not in text:
        return []

    has_sql_markers = bool(
        re.search(r"\bCREATE\s+TABLE\b|\bCHECK\s*\(|\bNOT\s+NULL\b", text, re.IGNORECASE)
    )
    if not has_sql_markers:
        return []

    by_column = {}

    for _table_name, body in _find_create_table_blocks(text):
        for segment in _split_top_level(body, r","):
            parsed = _parse_column_definition(segment)
            if parsed and parsed["constraints"]:
                key = parsed["column"].lower()
                existing = by_column.setdefault(key, {"column": parsed["column"], "constraints": {}})
                existing["constraints"].update(parsed["constraints"])
                continue

            table_level = _parse_table_level_clause(segment)
            for column_name in table_level.get("columns", []):
                key = column_name.lower()
                existing = by_column.setdefault(key, {"column": column_name, "constraints": {}})
                existing["constraints"].update(table_level["constraints"])

    # Every CHECK(...) in the document, read in one pass — inline
    # column CHECKs, named table-level CONSTRAINTs, ALTER TABLE ADD
    # CONSTRAINT, and bare CHECK lines alike — merged on top of
    # whatever CREATE TABLE parsing already found for the same
    # column, and added fresh for columns mentioned only in a CHECK.
    for column_key, constraints in _find_all_checks(text).items():
        existing = by_column.setdefault(column_key, {"column": column_key, "constraints": {}})
        existing["constraints"].update(constraints)

    rules = []
    for entry in by_column.values():
        constraints = entry["constraints"]
        if not constraints:
            continue

        column_name = entry["column"]
        pretty_name = _humanize(column_name)

        if constraints.get("allowed_values"):
            data_type = "allowed_choice"
        elif constraints.get("format"):
            data_type = constraints["format"]
        elif constraints.get("prefix") or constraints.get("suffix"):
            data_type = "identifier"
        else:
            data_type = "text"

        rules.append(
            {
                "name": pretty_name,
                "description": (
                    f"SQL constraint for `{column_name}` extracted from the "
                    f"uploaded document."
                ),
                "task": f"Please provide your value for {pretty_name}.",
                "data_type": data_type,
                "keywords": [column_name, pretty_name.lower()],
                "expected_outcome": "A value satisfying the column's SQL constraints is provided.",
                "constraints": constraints,
            }
        )

    return rules
