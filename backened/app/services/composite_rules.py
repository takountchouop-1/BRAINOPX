"""
composite_rules.py

Steps whose answer is more than one value.

Three input shapes exist beyond a single value:

    list        several values of the same kind, one per line
    table       rows of named columns, one row per line
    narrative   prose (handled by the narrative constraints)

The user types these into the ordinary chat box. This module turns
what they typed into rows or items, and validates every cell against
its own column rule.

Nothing here re-implements validation. A table is validated as N x M
ordinary scalar validations, so a column behaves exactly like a
one-value step: the same constraint inference, the same example
builder, the same error wording. That reuse is what keeps a composite
step from becoming a second rules engine.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


SHAPE_SCALAR = "scalar"
SHAPE_LIST = "list"
SHAPE_TABLE = "table"
SHAPE_NARRATIVE = "narrative"

COMPOSITE_SHAPES = (SHAPE_LIST, SHAPE_TABLE)

# How many cell errors to report at once. Enough to fix a row in one
# go, few enough that the reply stays readable.
MAX_REPORTED_PROBLEMS = 6

_CELL_SEPARATORS = ("|", ",", ";", "\t")


# ============================================================
# SHAPE
# ============================================================

def input_shape(rule: dict) -> str:
    """
    The shape of answer a rule expects.

    Prefers what the parser declared. Falls back to reading the rule
    text, so a document that describes a table still works when the
    parser did not label it.
    """

    if not isinstance(rule, dict):
        return SHAPE_SCALAR

    declared = str(
        rule.get("input_shape")
        or ""
    ).strip().lower()

    if declared in (SHAPE_LIST, SHAPE_TABLE, SHAPE_NARRATIVE, SHAPE_SCALAR):
        return declared

    if columns_of(rule):
        return SHAPE_TABLE

    text = " ".join(
        str(rule.get(key) or "")
        for key in ("name", "description", "task", "expected_outcome")
    ).lower()

    if re.search(
        r"\bone\s+(?:row|line|record|entry)\s+per\b"
        r"|\bfor\s+each\s+\w+\s+provide\b"
        r"|\btable\s+of\b|\brows?\s+of\b|\bcolumns\b",
        text,
    ):
        return SHAPE_TABLE

    if re.search(
        r"\blist\s+(?:of|all|the|each)\b"
        r"|\bone\s+per\s+line\b"
        r"|\bmultiple\s+(?:values|entries|items)\b"
        r"|\benter\s+all\b",
        text,
    ):
        return SHAPE_LIST

    return SHAPE_SCALAR


def is_composite(rule: dict) -> bool:
    """True when a rule expects rows or a list rather than one value."""

    return input_shape(rule) in COMPOSITE_SHAPES


def columns_of(rule: dict) -> list[dict]:
    """
    The column rules of a table step.

    Each column is itself a rule, so it can be passed straight to the
    example builder and the validator.
    """

    if not isinstance(rule, dict):
        return []

    raw = rule.get("columns")

    if not isinstance(raw, list):
        return []

    columns = []

    for index, column in enumerate(raw, start=1):

        if isinstance(column, str):
            column = {"name": column}

        if not isinstance(column, dict):
            continue

        name = str(
            column.get("name")
            or column.get("column")
            or f"Column {index}"
        ).strip()

        if not name:
            continue

        columns.append({
            "name": name,
            "description": str(
                column.get("description")
                or column.get("rule")
                or ""
            ).strip(),
            "constraints": (
                column.get("constraints")
                if isinstance(column.get("constraints"), dict)
                else {}
            ),
        })

    return columns


def item_rule_of(rule: dict) -> dict:
    """
    The rule every item of a list must satisfy.

    Defaults to the list rule itself minus its shape, so "list of
    tariff codes, each TRF + 3 digits" validates each entry.
    """

    if not isinstance(rule, dict):
        return {}

    declared = rule.get("item_rule")

    if isinstance(declared, dict) and declared:
        return declared

    item = {
        key: value
        for key, value in rule.items()
        if key not in ("input_shape", "columns", "min_rows", "min_items")
    }

    item["input_shape"] = SHAPE_SCALAR

    return item


def _minimum(rule: dict, key: str) -> int:
    try:
        return max(0, int(rule.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def minimum_rows(rule: dict) -> int:
    """The fewest rows a table step will accept."""

    return _minimum(rule, "min_rows") or 1


def minimum_items(rule: dict) -> int:
    """The fewest items a list step will accept."""

    return _minimum(rule, "min_items") or 1


# ============================================================
# PARSING WHAT THE USER TYPED
# ============================================================

def _split_lines(value: str) -> list[str]:
    return [
        line.strip()
        for line in str(value or "").splitlines()
        if line.strip()
    ]


def _pick_separator(line: str) -> str:
    for separator in _CELL_SEPARATORS:
        if separator in line:
            return separator
    return ","


def _split_cells(line: str, separator: str) -> list[str]:
    return [
        cell.strip().strip("\"'")
        for cell in line.split(separator)
    ]


def parse_items(value: str) -> list[str]:
    """
    Read a list the user typed.

    Accepts one item per line, or several separated by commas on a
    single line.
    """

    lines = _split_lines(value)

    if len(lines) > 1:
        return [line.strip().strip("\"'") for line in lines]

    if not lines:
        return []

    separator = _pick_separator(lines[0])

    items = [
        item
        for item in _split_cells(lines[0], separator)
        if item
    ]

    return items


def parse_rows(
    value: str,
    columns: list[dict],
) -> list[list[str]]:
    """
    Read a table the user typed, one row per line.

    A leading header line naming the columns is recognised and
    dropped, so pasting a block copied from a spreadsheet works.
    """

    lines = _split_lines(value)

    if not lines:
        return []

    separator = _pick_separator(lines[0])

    rows = [
        _split_cells(line, separator)
        for line in lines
    ]

    if columns and rows:

        expected = [
            column["name"].strip().lower()
            for column in columns
        ]

        first = [cell.strip().lower() for cell in rows[0]]

        if first == expected:
            rows = rows[1:]

    return [row for row in rows if any(cell for cell in row)]


# ============================================================
# VALIDATION
# ============================================================

def _validate_cell(value: str, column: dict) -> list[str]:
    """Validate one cell using the ordinary scalar validator."""

    from app.services.groq_service import deterministic_validate_example

    try:
        verdict = deterministic_validate_example(
            example=value,
            rule=column,
        )
    except Exception:
        logger.exception(
            "Cell validation failed for column '%s'",
            column.get("name", "unknown"),
        )
        return []

    if verdict.get("valid"):
        return []

    errors = verdict.get("errors")

    if isinstance(errors, list) and errors:
        return [str(error) for error in errors]

    reason = str(verdict.get("reason") or "").strip()

    return [reason] if reason else ["Value is not valid."]


def validate_list(value: str, rule: dict) -> dict:
    """Validate every entry of a list against the item rule."""

    items = parse_items(value)

    minimum = minimum_items(rule)

    if len(items) < minimum:
        return {
            "valid": False,
            "reason": "Not enough entries.",
            "errors": [
                f"Enter at least {minimum} "
                f"{'entry' if minimum == 1 else 'entries'}, "
                f"one per line. You entered {len(items)}."
            ],
            "problem_limit": MAX_REPORTED_PROBLEMS,
        }

    item_rule = item_rule_of(rule)

    errors = []

    for index, item in enumerate(items, start=1):

        for message in _validate_cell(item, item_rule):

            errors.append(f"Item {index}: {message}")

            if len(errors) >= MAX_REPORTED_PROBLEMS:
                break

        if len(errors) >= MAX_REPORTED_PROBLEMS:
            break

    if errors:
        return {
            "valid": False,
            "reason": "Some entries are not valid.",
            "errors": errors,
            "problem_limit": MAX_REPORTED_PROBLEMS,
        }

    return {
        "valid": True,
        "reason": "All entries are valid.",
        "errors": [],
    }


def validate_table(value: str, rule: dict) -> dict:
    """Validate every cell of a table against its own column rule."""

    columns = columns_of(rule)

    if not columns:
        # Nothing to check the cells against; fall back to treating
        # the answer as a list so the step is still usable.
        return validate_list(value, rule)

    rows = parse_rows(value, columns)

    minimum = minimum_rows(rule)

    if len(rows) < minimum:
        return {
            "valid": False,
            "reason": "Not enough rows.",
            "errors": [
                f"Enter at least {minimum} "
                f"{'row' if minimum == 1 else 'rows'}, one per line, "
                f"with {len(columns)} values separated by commas. "
                f"You entered {len(rows)}."
            ],
            "problem_limit": MAX_REPORTED_PROBLEMS,
        }

    errors = []

    # Which cells failed, so the table can be shown back with the
    # offending ones marked rather than described in prose.
    cell_errors = []

    for row_number, row in enumerate(rows, start=1):

        if len(row) != len(columns):

            errors.append(
                f"Row {row_number}: expected {len(columns)} values "
                f"({', '.join(c['name'] for c in columns)}), "
                f"found {len(row)}."
            )

            cell_errors.append({
                "row": row_number,
                "column": None,
                "message": "wrong number of values",
            })

            if len(errors) >= MAX_REPORTED_PROBLEMS:
                break

            continue

        for position, (cell, column) in enumerate(zip(row, columns)):

            for message in _validate_cell(cell, column):

                errors.append(
                    f"Row {row_number}, {column['name']}: {message}"
                )

                cell_errors.append({
                    "row": row_number,
                    "column": position,
                    "column_name": column["name"],
                    "message": message,
                })

                if len(errors) >= MAX_REPORTED_PROBLEMS:
                    break

            if len(errors) >= MAX_REPORTED_PROBLEMS:
                break

        if len(errors) >= MAX_REPORTED_PROBLEMS:
            break

    if errors:
        return {
            "valid": False,
            "reason": "Some values are not valid.",
            "errors": errors,
            "problem_limit": MAX_REPORTED_PROBLEMS,
            "rows": rows,
            "cell_errors": cell_errors,
        }

    return {
        "valid": True,
        "reason": "All rows are valid.",
        "errors": [],
        "rows": rows,
    }


def validate_composite(value: str, rule: dict) -> dict:
    """Validate a list or table answer."""

    shape = input_shape(rule)

    if shape == SHAPE_TABLE:
        return validate_table(value, rule)

    return validate_list(value, rule)


# ============================================================
# EXAMPLES
# ============================================================

def build_table_example(rule: dict) -> str:
    """
    A sample table: the column names, then two rows of valid cells.

    Each cell comes from the ordinary example builder for that
    column, so the sample demonstrates the real per-column format.
    """

    from app.services.example_utils import build_example_value

    columns = columns_of(rule)

    if not columns:
        return ""

    header = ", ".join(column["name"] for column in columns)

    rows = []

    for _ in range(2):
        cells = []
        for column in columns:
            try:
                cells.append(str(build_example_value(column)).strip())
            except Exception:
                cells.append("")
        rows.append(", ".join(cells))

    # Vary the second row so it reads as a table, not a repeat.
    if len(rows) == 2 and rows[0] == rows[1]:
        rows[1] = _vary(rows[1])

    return "\n".join([header] + rows)


def build_list_example(rule: dict) -> str:
    """A sample list: three valid entries, one per line."""

    from app.services.example_utils import build_example_value

    item_rule = item_rule_of(rule)

    try:
        base = str(build_example_value(item_rule)).strip()
    except Exception:
        base = ""

    if not base:
        return ""

    entries = [base, _vary(base), _vary(_vary(base))]

    seen = []

    for entry in entries:
        if entry not in seen:
            seen.append(entry)

    return "\n".join(seen)


def _vary(value: str) -> str:
    """
    Nudge a sample value so repeated rows are not identical.

    Increments the trailing number where there is one; otherwise
    leaves the value alone, since changing it might break its format.
    """

    match = re.search(r"(\d+)(\D*)$", value)

    if not match:
        return value

    digits = match.group(1)
    tail = match.group(2)

    incremented = str(int(digits) + 1).zfill(len(digits))

    return value[: match.start(1)] + incremented + tail


def build_composite_example(rule: dict) -> str:
    """A sample answer for a list or table step."""

    shape = input_shape(rule)

    if shape == SHAPE_TABLE:
        return build_table_example(rule)

    return build_list_example(rule)


# ============================================================
# RENDERING A TABLE
# ============================================================

def render_table_html(
    columns: list[dict],
    rows: list[list[str]],
    cell_errors: list[dict] | None = None,
    caption: str = "",
) -> str:
    """
    Render rows as an HTML table.

    Every cell is escaped as it is placed, so the markup this returns
    is safe to insert without further escaping — which matters,
    because the values in it were typed by a user.

    Cells that failed validation are marked, so the user can see
    which value to fix instead of matching prose against their input.
    """

    import html as _html

    if not columns:
        return ""

    bad = {
        (item.get("row"), item.get("column"))
        for item in (cell_errors or [])
        if item.get("column") is not None
    }

    bad_rows = {
        item.get("row")
        for item in (cell_errors or [])
        if item.get("column") is None
    }

    parts = ['<table class="data-table">']

    if caption:
        parts.append(
            f'<caption>{_html.escape(str(caption))}</caption>'
        )

    parts.append("<thead><tr>")
    parts.append('<th class="row-number">#</th>')

    for column in columns:
        parts.append(
            f'<th>{_html.escape(str(column.get("name", "")))}</th>'
        )

    parts.append("</tr></thead><tbody>")

    for row_number, row in enumerate(rows or [], start=1):

        row_class = ' class="bad-row"' if row_number in bad_rows else ""

        parts.append(f"<tr{row_class}>")
        parts.append(
            f'<td class="row-number">{row_number}</td>'
        )

        for position in range(len(columns)):

            value = row[position] if position < len(row) else ""

            css = ' class="bad-cell"' if (row_number, position) in bad else ""

            parts.append(
                f"<td{css}>{_html.escape(str(value))}</td>"
            )

        parts.append("</tr>")

    parts.append("</tbody></table>")

    return "".join(parts)


def render_example_table(rule: dict) -> str:
    """The example for a table step, laid out as a table."""

    columns = columns_of(rule)

    if not columns:
        return ""

    sample = build_table_example(rule)

    if not sample:
        return ""

    lines = [line for line in sample.splitlines() if line.strip()]

    # build_table_example puts the column names on the first line;
    # the header is drawn from the columns themselves.
    rows = [
        _split_cells(line, _pick_separator(line))
        for line in lines[1:]
    ]

    return render_table_html(columns, rows)


def render_submitted_table(rule: dict, value: str, verdict: dict) -> str:
    """
    The rows the user just sent, laid out as a table with any
    failing cells marked.
    """

    columns = columns_of(rule)

    if not columns:
        return ""

    # run_rule_workflow nests the validator's result under
    # "validation", so look in both places.
    sources = []

    if isinstance(verdict, dict):
        sources.append(verdict)

        nested = verdict.get("validation")

        if isinstance(nested, dict):
            sources.append(nested)

    rows = None
    cell_errors = None

    for source in sources:
        if rows is None and isinstance(source.get("rows"), list):
            rows = source["rows"]
        if cell_errors is None and isinstance(source.get("cell_errors"), list):
            cell_errors = source["cell_errors"]

    if not rows:
        rows = parse_rows(value, columns)

    if not rows:
        return ""

    return render_table_html(
        columns,
        rows,
        cell_errors=cell_errors,
        caption="What you entered",
    )


def render_list_html(items: list[str], caption: str = "") -> str:
    """
    Render a list of items as a table with a single column.

    Reuses render_table_html rather than a second markup builder, so a
    list's "what you entered" preview escapes and lays out exactly
    like a table's does.
    """

    if not items:
        return ""

    return render_table_html(
        [{"name": "Value"}],
        [[item] for item in items],
        caption=caption,
    )


# ============================================================
# WHAT TO PROVIDE
# ============================================================

def describe_expected_input(rule: dict) -> str:
    """
    One line telling the user how to enter this step.

    Names the columns, because a user cannot supply a table without
    knowing its columns — but says nothing about what makes a cell
    valid, which stays hidden like every other rule.
    """

    shape = input_shape(rule)

    if shape == SHAPE_TABLE:

        columns = columns_of(rule)

        if columns:
            names = ", ".join(column["name"] for column in columns)
            return (
                f"Enter one row per line, with these values "
                f"separated by commas: {names}."
            )

        return "Enter one row per line, with values separated by commas."

    if shape == SHAPE_LIST:
        return "Enter one entry per line."

    return ""


# ============================================================
# COMPLETED-STEP PREVIEW
# ============================================================

def completed_step_preview(step: dict) -> dict:
    """
    A completed step, reduced to what an "edit this answer" view needs:
    identity, the value the user submitted, and — for a composite step
    — that value laid out as a table so it reads the way it did when
    it was collected, rather than as a raw separated blob.

    Shared by step_by_step_service and rule_router_service so the two
    guided-walkthrough consumers don't each grow their own copy of
    this table/list branching.
    """

    user_value = str(step.get("user_value") or "")

    preview_html = None

    shape = input_shape(step)

    if shape == SHAPE_TABLE:
        columns = columns_of(step)
        if columns:
            rows = parse_rows(user_value, columns)
            preview_html = render_table_html(columns, rows) or None

    elif shape == SHAPE_LIST:
        items = parse_items(user_value)
        preview_html = render_list_html(items) or None

    return {
        "step_index": step.get("step_index"),
        "rule_id": step.get("rule_id"),
        "rule_name": step.get("rule_name"),
        "status": step.get("status"),
        "user_value": user_value,
        "preview_html": preview_html,
    }
