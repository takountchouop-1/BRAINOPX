import itertools
from datetime import datetime

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import safe_expr


def is_blank(value) -> bool:
    """
    True for None, blank/whitespace-only strings, and NaN.

    pandas.read_excel(..., dtype=str) still represents a genuinely
    empty cell as float('nan'), not None or "" — a plain `value is
    None` check misses it entirely, which is why a blank cell could
    slip past the "required" check undetected.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, float):
        return value != value  # the standard float NaN self-inequality test
    return False


def _matches_type(value, data_type: str) -> bool:
    """Loose type check against the SQL Server type string (e.g. 'INTEGER', 'VARCHAR(150)')."""
    dtype = data_type.upper()
    if is_blank(value):
        return True

    if "INT" in dtype or "DECIMAL" in dtype or "NUMERIC" in dtype or "FLOAT" in dtype:
        try:
            float(value)
            return True
        except (TypeError, ValueError):
            return False

    if "DATE" in dtype or "TIME" in dtype:
        import datetime
        if isinstance(value, (datetime.date, datetime.datetime)):
            return True
        # Uploaded rows are read with every cell forced to str (see
        # requests.py), so a real date arrives here as text (e.g.
        # "2025-01-15 00:00:00") rather than a datetime instance —
        # only garbage like "invalide date" should fail this.
        try:
            pd.to_datetime(str(value))
            return True
        except (ValueError, TypeError):
            return False

    return True


def _foreign_key_exists(db: Session, referred_table: str, referred_column: str, value) -> bool:
    if is_blank(value):
        return True

    query = text(f"SELECT TOP 1 1 FROM {referred_table} WHERE {referred_column} = :value")
    result = db.execute(query, {"value": value}).first()
    return result is not None


_DATE_HEADER_HINTS = ("date", "dob", "birthday")

_UNIQUE_HEADER_HINTS = (
    "id", "code", "number", "num", "ref", "sku", "key",
    "invoice", "order", "ticket", "transaction", "reference",
)


def _header_suggests_date(header: str) -> bool:
    h = str(header).strip().lower()
    return any(hint in h for hint in _DATE_HEADER_HINTS)


def _header_suggests_unique(header: str) -> bool:
    h = str(header).strip().lower()
    return any(hint in h for hint in _UNIQUE_HEADER_HINTS)


def _looks_datelike(value) -> bool:
    if isinstance(value, (datetime,)):
        return True
    text = str(value).strip()
    # A bare number ("10", "2024") parses as a date under pandas'
    # permissive rules but is almost always something else (an id, a
    # quantity, a year-as-count) — only text with actual date
    # separators should count.
    if not text or _looks_numeric(text):
        return False
    try:
        pd.to_datetime(text)
        return True
    except (ValueError, TypeError):
        return False


def infer_column_rules(headers: list[str], rows: list[dict]) -> list[dict]:
    """
    Builds a lightweight rule set straight from the uploaded file's own
    data, for a report_analyses task that has no target_table configured
    (so no DB-derived column_rules to validate against). Every expected
    column is treated as required, with extra checks added when the
    template's own data supports them:

      - numeric type, when every non-empty value parses as a number
      - non-negative, when every non-empty numeric value is >= 0 (the
        template never showed a negative, so one in an upload is
        treated as a mistake rather than a valid refund/adjustment)
      - date format, when the header name suggests a date (e.g.
        "date", "dob") or every non-empty value itself parses as one
      - unique, when the header name suggests an identifier (e.g.
        "id", "invoice", "order") or every non-empty value in the
        template is already distinct — without this, a repeated key
        value (a duplicated invoice/order/employee number with
        different other fields) is never flagged, since the only other
        duplicate check looks for a row that's a byte-for-byte clone
        across every column

    Without this, a task created without a target table gets no
    per-row validation at all — just the column-header match — which
    reads as "the file wasn't analysed".
    """
    rules = []
    for header in headers:
        if not header or str(header).startswith("Unnamed:"):
            continue

        non_empty = [
            row.get(header) for row in rows
            if not is_blank(row.get(header))
        ]

        data_type = "VARCHAR"
        non_negative = False

        if non_empty and all(_looks_numeric(v) for v in non_empty):
            data_type = "DECIMAL"
            non_negative = all(float(v) >= 0 for v in non_empty)
        elif non_empty and (
            _header_suggests_date(header) or all(_looks_datelike(v) for v in non_empty)
        ):
            data_type = "DATE"

        unique = _header_suggests_unique(header) or (
            len(non_empty) > 1 and len(non_empty) == len(set(non_empty))
        )

        rules.append({
            "name": header,
            "data_type": data_type,
            "required": True,
            "unique": unique,
            "foreign_key": None,
            "non_negative": non_negative,
        })

    return rules


def _looks_numeric(value) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


# ============================================================
# FORMULA INFERENCE FROM SAMPLE DATA
#
# excel_rule_parser.extract_formula_rules only finds a formula rule
# when the template's own cell is a live Excel formula. Many templates
# encode the same relationship as plain typed numbers instead (e.g. a
# "Total" column whose values happen to equal Quantity * Unit Price
# for every sample row, with no "=" formula behind it) — this is the
# data-driven counterpart: it looks for a small, curated set of common
# arithmetic shapes (sum, difference, product, percentage discount...)
# that hold EXACTLY across every one of the template's own sample
# rows, rather than fitting arbitrary coefficients to the data (which
# would risk "discovering" a wrong relationship that merely happens to
# pass through a handful of sample points). A shape with no free
# parameters that holds exactly for every sample row is a much safer
# signal than a best-fit line through the same points.
# ============================================================

_MIN_ROWS_FOR_FORMULA_INFERENCE = 3
_INFERRED_FORMULA_TOLERANCE = 0.01

# (expression, function) — expression must be valid for safe_expr and
# use exactly the variable names the function's positional args are
# bound to (v1, v2, ... in argument order).
_TWO_OPERAND_SHAPES = [
    ("v1 + v2", lambda a, b: a + b),
    ("v1 - v2", lambda a, b: a - b),
    ("v2 - v1", lambda a, b: b - a),
    ("v1 * v2", lambda a, b: a * b),
    ("v1 / v2", lambda a, b: (a / b) if b else None),
    ("v2 / v1", lambda a, b: (b / a) if a else None),
]

_THREE_OPERAND_SHAPES = [
    ("v1 + v2 - v3", lambda a, b, c: a + b - c),
    ("v1 + v2 + v3", lambda a, b, c: a + b + c),
    ("v1 * v2 - v3", lambda a, b, c: a * b - c),
    ("v1 * v2 + v3", lambda a, b, c: a * b + c),
    ("v1 * v2 * (1 - v3 / 100)", lambda a, b, c: a * b * (1 - c / 100)),
    ("v1 * v2 * (1 + v3 / 100)", lambda a, b, c: a * b * (1 + c / 100)),
    ("v1 * v2 * (1 - v3)", lambda a, b, c: a * b * (1 - c)),
    ("v1 * v2 * (1 + v3)", lambda a, b, c: a * b * (1 + c)),
]


def _numeric_columns(headers: list[str], rows: list[dict]) -> list[str]:
    """Headers whose sample values are all numeric, with enough
    non-blank values to test a formula against."""
    numeric = []
    for header in headers:
        if not header:
            continue
        values = [row.get(header) for row in rows if not is_blank(row.get(header))]
        if len(values) >= _MIN_ROWS_FOR_FORMULA_INFERENCE and all(_looks_numeric(v) for v in values):
            numeric.append(header)
    return numeric


def _complete_numeric_rows(rows: list[dict], columns: list[str]) -> list[dict]:
    """{column: float} for every row where all of `columns` are
    present and numeric — rows missing any of them are dropped rather
    than guessed at."""
    complete = []
    for row in rows:
        values = {}
        for column in columns:
            value = row.get(column)
            if is_blank(value) or not _looks_numeric(value):
                break
            values[column] = float(value)
        else:
            complete.append(values)
    return complete


def _shape_matches_every_row(rows_values: list[dict], columns: list[str], formula, target: str, tolerance: float) -> bool:
    for values in rows_values:
        try:
            expected = formula(*(values[c] for c in columns))
        except ZeroDivisionError:
            return False
        if expected is None or abs(expected - values[target]) > tolerance:
            return False
    return True


def _describe_inferred_formula(expression: str, operand_columns: dict) -> str:
    description = expression
    for var in sorted(operand_columns, key=len, reverse=True):
        description = description.replace(var, operand_columns[var])
    return description


def _find_formula_for_target(
    target: str, candidates: list[str], rows: list[dict], tolerance: float,
) -> dict | None:
    for a, b in itertools.combinations(candidates, 2):
        subset = _complete_numeric_rows(rows, [target, a, b])
        if len(subset) < _MIN_ROWS_FOR_FORMULA_INFERENCE:
            continue
        for expression, formula in _TWO_OPERAND_SHAPES:
            if _shape_matches_every_row(subset, [a, b], formula, target, tolerance):
                return _build_inferred_rule(target, {"v1": a, "v2": b}, expression, tolerance)

    if len(candidates) >= 3:
        for a, b, c in itertools.permutations(candidates, 3):
            subset = _complete_numeric_rows(rows, [target, a, b, c])
            if len(subset) < _MIN_ROWS_FOR_FORMULA_INFERENCE:
                continue
            for expression, formula in _THREE_OPERAND_SHAPES:
                if _shape_matches_every_row(subset, [a, b, c], formula, target, tolerance):
                    return _build_inferred_rule(
                        target, {"v1": a, "v2": b, "v3": c}, expression, tolerance
                    )

    return None


def _build_inferred_rule(target: str, operand_columns: dict, expression: str, tolerance: float) -> dict:
    return {
        "name": target,
        "rule_type": "formula",
        "expression": expression,
        "operand_columns": operand_columns,
        "raw_formula": _describe_inferred_formula(expression, operand_columns),
        "tolerance": tolerance,
        "source": "inferred_from_sample_data",
    }


def infer_formula_rules(
    headers: list[str],
    rows: list[dict],
    exclude_columns: set | None = None,
    tolerance: float = _INFERRED_FORMULA_TOLERANCE,
) -> list[dict]:
    """
    Looks for a cross-column arithmetic relationship that holds
    exactly across every sample row of a template — the data-driven
    counterpart to excel_rule_parser.extract_formula_rules for
    templates that encode a relationship as plain numbers rather than
    a live Excel formula.

    `exclude_columns` should name every column excel_rule_parser
    already produced a structural formula rule for, so a real formula
    found in the file itself always takes precedence over a guess from
    its sample data instead of the two being merged/conflicting.

    At most one rule per target column: the first matching shape,
    tried simplest-first (two operands before three), is returned —
    not the "best" fit, since these are zero-free-parameter hypothesis
    tests rather than a regression, so nothing here is being optimized
    for goodness of fit in the first place.

    A single linear identity among N columns (e.g. Closing = Opening +
    In - Out) holds just as exactly if rearranged to solve for any one
    of its columns, which would otherwise surface as N separate, purely
    algebraic restatements of the same one relationship — noisy, and
    liable to raise several redundant "formula_mismatch" errors from a
    single wrong cell. So once a relationship is found, its target AND
    the operand columns it used are treated as spoken for and are never
    tried as a target again (they remain eligible as operands elsewhere).
    Targets are tried rightmost-column-first, since the "computed"
    column (Total, Closing Stock, ...) is conventionally placed after
    the inputs it derives from — the same convention both real
    templates that motivated this were built with.
    """
    exclude_columns = exclude_columns or set()
    numeric_columns = _numeric_columns(headers, rows)

    claimed = set(exclude_columns)
    rules = []
    for target in reversed(numeric_columns):
        if target in claimed:
            continue

        candidates = [c for c in numeric_columns if c != target and c not in claimed]
        if len(candidates) < 2:
            continue

        rule = _find_formula_for_target(target, candidates, rows, tolerance)
        if rule:
            rules.append(rule)
            claimed.add(target)
            claimed.update(rule["operand_columns"].values())

    return rules


def check_single_value(
    db: Session,
    rule: dict,
    value,
    other_rows: list[dict],
    row_number: int,
) -> dict | None:
    """
    Runs one column rule against one value, the same checks
    validate_data_rows applies per-cell. Used there, and reused to
    re-validate a single corrected cell without re-scanning the whole
    file.

    other_rows must exclude the row being checked, so a corrected
    value isn't flagged as a duplicate of its own prior self.
    """
    col_name = rule["name"]
    is_empty = is_blank(value)

    # 1. Missing values
    if rule.get("required") and is_empty:
        return {
            "row": row_number,
            "column": col_name,
            "submitted_value": None,
            "rule_violated": "This field is required and cannot be empty.",
            "kind": "missing_value",
            "status": "open",
            "user_correction": None,
            "resolved_at": None,
        }

    if is_empty:
        return None

    # 2. Incorrect format / wrong data type
    if not _matches_type(value, rule.get("data_type", "")):
        return {
            "row": row_number,
            "column": col_name,
            "submitted_value": value,
            "rule_violated": f"Expected a value compatible with {rule.get('data_type')}.",
            "kind": "invalid_format",
            "status": "open",
            "user_correction": None,
            "resolved_at": None,
        }

    # 2b. Negative values in a column whose template data was never negative
    if rule.get("non_negative"):
        try:
            if float(value) < 0:
                return {
                    "row": row_number,
                    "column": col_name,
                    "submitted_value": value,
                    "rule_violated": "This field should not be negative.",
                    "kind": "negative_value",
                    "status": "open",
                    "user_correction": None,
                    "resolved_at": None,
                }
        except (TypeError, ValueError):
            pass  # non-numeric already caught by the format check above

    # 2c. Allowed values (template dropdown / list data validation)
    allowed_values = rule.get("allowed_values")
    if allowed_values and str(value) not in {str(v) for v in allowed_values}:
        return {
            "row": row_number,
            "column": col_name,
            "submitted_value": value,
            "rule_violated": f"Must be one of: {', '.join(str(v) for v in allowed_values)}.",
            "kind": "invalid_choice",
            "status": "open",
            "user_correction": None,
            "resolved_at": None,
        }

    # 2d. Numeric range (template min/max data validation)
    min_value, max_value = rule.get("min_value"), rule.get("max_value")
    if min_value is not None or max_value is not None:
        try:
            numeric_value = float(value)
            if (min_value is not None and numeric_value < min_value) or (
                max_value is not None and numeric_value > max_value
            ):
                if min_value is not None and max_value is not None:
                    bound_text = f"between {min_value} and {max_value}"
                elif min_value is not None:
                    bound_text = f"at least {min_value}"
                else:
                    bound_text = f"at most {max_value}"
                return {
                    "row": row_number,
                    "column": col_name,
                    "submitted_value": value,
                    "rule_violated": f"Must be {bound_text}.",
                    "kind": "out_of_range",
                    "status": "open",
                    "user_correction": None,
                    "resolved_at": None,
                }
        except (TypeError, ValueError):
            pass  # non-numeric already caught by the format check above

    # 2e. Text length (template length data validation)
    min_length, max_length = rule.get("min_length"), rule.get("max_length")
    if min_length is not None or max_length is not None:
        length = len(str(value))
        if (min_length is not None and length < min_length) or (
            max_length is not None and length > max_length
        ):
            if min_length is not None and max_length is not None:
                bound_text = f"between {min_length} and {max_length} characters"
            elif min_length is not None:
                bound_text = f"at least {min_length} characters"
            else:
                bound_text = f"at most {max_length} characters"
            return {
                "row": row_number,
                "column": col_name,
                "submitted_value": value,
                "rule_violated": f"Must be {bound_text}.",
                "kind": "invalid_length",
                "status": "open",
                "user_correction": None,
                "resolved_at": None,
            }

    # 3. Duplicated data
    if rule.get("unique"):
        prior_row = next(
            (r.get("_row_number") for r in other_rows if r.get(col_name) == value),
            None,
        )
        if prior_row is not None:
            return {
                "row": row_number,
                "column": col_name,
                "submitted_value": value,
                "rule_violated": f"Duplicate value — already used in row {prior_row}.",
                "kind": "duplicate",
                "status": "open",
                "user_correction": None,
                "resolved_at": None,
            }

    # 4. Foreign key references
    fk = rule.get("foreign_key")
    if fk:
        exists = _foreign_key_exists(db, fk["referred_table"], fk["referred_column"], value)
        if not exists:
            return {
                "row": row_number,
                "column": col_name,
                "submitted_value": value,
                "rule_violated": (
                    f"References '{fk['referred_table']}.{fk['referred_column']}', "
                    f"but no matching record was found."
                ),
                "kind": "unknown_code",
                "status": "open",
                "user_correction": None,
                "resolved_at": None,
            }

    return None


def check_formula_rule(rule: dict, row: dict) -> dict | None:
    """
    Checks one row against a template-derived cross-column formula rule
    (e.g. "Total = Quantity * Unit Price"), as extracted by
    excel_rule_parser.extract_formula_rules.

    Silently skips (returns None) when the target or any operand is
    blank or non-numeric — those are already reported by the ordinary
    missing-value / invalid-format checks, and a formula check on top
    would just be a confusing duplicate of the same underlying problem.
    """
    col_name = rule["name"]
    target_value = row.get(col_name)
    if is_blank(target_value):
        return None

    operand_columns = rule.get("operand_columns") or {}
    variables = {}
    for var_name, source_column in operand_columns.items():
        source_value = row.get(source_column)
        if is_blank(source_value):
            return None
        try:
            variables[var_name] = float(source_value)
        except (TypeError, ValueError):
            return None

    try:
        target_numeric = float(target_value)
        computed = safe_expr.evaluate(rule["expression"], variables)
    except (TypeError, ValueError, safe_expr.UnsafeExpressionError, ZeroDivisionError):
        return None

    tolerance = rule.get("tolerance", 0.01)
    if abs(computed - target_numeric) > tolerance:
        source_phrase = (
            "a pattern found in the template's own sample data"
            if rule.get("source") == "inferred_from_sample_data"
            else "the template's own formula"
        )
        return {
            "row": row.get("_row_number"),
            "column": col_name,
            "submitted_value": target_value,
            "rule_violated": (
                f"Expected {col_name} to equal {rule.get('raw_formula', rule['expression'])} "
                f"(computed {computed:g} from {source_phrase}), got {target_value}."
            ),
            "kind": "formula_mismatch",
            "status": "open",
            "user_correction": None,
            "resolved_at": None,
        }

    return None


def validate_data_rows(db: Session, rows: list[dict], column_rules: list[dict]) -> list[dict]:
    """
    Runs every row of uploaded data against the task's column rules.

    `column_rules` may mix ordinary per-cell rules (no "rule_type", or
    "rule_type": "cell") with cross-column formula rules
    ("rule_type": "formula", from excel_rule_parser) — the two are
    validated differently but share one list so every existing caller
    of this function keeps working unchanged.
    """
    cell_rules = [r for r in column_rules if r.get("rule_type", "cell") == "cell"]
    formula_rules = [r for r in column_rules if r.get("rule_type") == "formula"]

    errors = []
    seen_values = {rule["name"]: {} for rule in cell_rules if rule.get("unique")}

    for row in rows:
        row_number = row.get("_row_number")

        for rule in cell_rules:
            col_name = rule["name"]
            value = row.get(col_name)

            # check_single_value's duplicate check needs every other
            # row already seen so far, in the same shape as
            # `rows` (a "_row_number" + column dict) — seen_values
            # already tracks exactly that, one column at a time.
            other_rows = (
                [{"_row_number": r, col_name: v} for v, r in seen_values.get(col_name, {}).items()]
                if rule.get("unique")
                else []
            )

            error = check_single_value(db, rule, value, other_rows, row_number)
            if error:
                errors.append(error)
            elif rule.get("unique") and not is_blank(value):
                seen_values[col_name][value] = row_number

        for rule in formula_rules:
            error = check_formula_rule(rule, row)
            if error:
                errors.append(error)

    return errors


def mark_error_solved(
    validation_errors: list,
    user_message: str,
    anomaly_id: str | None = None,
    column: str | None = None,
    row: int | None = None,
) -> list:
    """
    Mark a specific validation error as solved, preferring an exact
    anomaly_id match (set once report_analysis_service seeds anomalies
    from these errors) and falling back to row+column.
    """
    for error in validation_errors:
        if error.get("status") == "solved":
            continue

        matched = (
            (anomaly_id is not None and error.get("anomaly_id") == anomaly_id)
            or (anomaly_id is None and error.get("column") == column and error.get("row") == row)
        )
        if matched:
            error["status"] = "solved"
            error["user_correction"] = user_message
            error["resolved_at"] = datetime.now().isoformat()
            break

    return validation_errors


#  New function: Get statistics
def get_validation_stats(validation_errors: list) -> dict:
    """
    Get statistics about validation errors.
    """
    total = len(validation_errors)
    solved = len([e for e in validation_errors if e.get("status") == "solved"])
    open_errors = total - solved
    
    return {
        "total": total,
        "solved": solved,
        "remaining": open_errors,
        "progress": round((solved / total) * 100) if total > 0 else 0
    }