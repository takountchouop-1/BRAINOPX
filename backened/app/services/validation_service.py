from sqlalchemy import text
from sqlalchemy.orm import Session


def _matches_type(value, data_type: str) -> bool:
    """Loose type check against the SQL Server type string (e.g. 'INTEGER', 'VARCHAR(150)')."""
    dtype = data_type.upper()
    if value is None:
        return True

    if "INT" in dtype or "DECIMAL" in dtype or "NUMERIC" in dtype or "FLOAT" in dtype:
        try:
            float(value)
            return True
        except (TypeError, ValueError):
            return False

    if "DATE" in dtype or "TIME" in dtype:
        import datetime
        return isinstance(value, (datetime.date, datetime.datetime))

    return True


def _foreign_key_exists(db: Session, referred_table: str, referred_column: str, value) -> bool:
    if value is None:
        return True

    query = text(f"SELECT TOP 1 1 FROM {referred_table} WHERE {referred_column} = :value")
    result = db.execute(query, {"value": value}).first()
    return result is not None


def validate_data_rows(db: Session, rows: list[dict], column_rules: list[dict]) -> list[dict]:
    """
    Runs every row of uploaded data against the task's column rules.
    """
    errors = []
    seen_values = {rule["name"]: {} for rule in column_rules if rule.get("unique")}

    for row in rows:
        row_number = row.get("_row_number")

        for rule in column_rules:
            col_name = rule["name"]
            value = row.get(col_name)
            is_empty = value is None or (isinstance(value, str) and value.strip() == "")

            # 1. Missing values
            if rule.get("required") and is_empty:
                errors.append({
                    "row": row_number,
                    "column": col_name,
                    "submitted_value": None,
                    "rule_violated": "This field is required and cannot be empty.",
                    "status": "open",                    #  Added
                    "user_correction": None,             #  Added
                    "resolved_at": None                  #  Added
                })
                continue

            if is_empty:
                continue

            # 2. Incorrect format / wrong data type
            if not _matches_type(value, rule.get("data_type", "")):
                errors.append({
                    "row": row_number,
                    "column": col_name,
                    "submitted_value": value,
                    "rule_violated": f"Expected a value compatible with {rule.get('data_type')}.",
                    "status": "open",                    #  Added
                    "user_correction": None,             #  Added
                    "resolved_at": None                  #  Added
                })
                continue

            # 3. Duplicated data
            if rule.get("unique"):
                prior_row = seen_values[col_name].get(value)
                if prior_row is not None:
                    errors.append({
                        "row": row_number,
                        "column": col_name,
                        "submitted_value": value,
                        "rule_violated": f"Duplicate value — already used in row {prior_row}.",
                        "status": "open",                #  Added
                        "user_correction": None,         #  Added
                        "resolved_at": None              #  Added
                    })
                else:
                    seen_values[col_name][value] = row_number

            # 4. Foreign key references
            fk = rule.get("foreign_key")
            if fk:
                exists = _foreign_key_exists(db, fk["referred_table"], fk["referred_column"], value)
                if not exists:
                    errors.append({
                        "row": row_number,
                        "column": col_name,
                        "submitted_value": value,
                        "rule_violated": (
                            f"References '{fk['referred_table']}.{fk['referred_column']}', "
                            f"but no matching record was found."
                        ),
                        "status": "open",                #  Added
                        "user_correction": None,         #  Added
                        "resolved_at": None              #  Added
                    })

    return errors


#  New function: Mark errors as solved
def mark_error_solved(validation_errors: list, column: str, row: int, user_message: str) -> list:
    """
    Mark a specific validation error as solved.
    """
    for error in validation_errors:
        if error.get("status") == "solved":
            continue
        
        if error.get("column") == column and error.get("row") == row:
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