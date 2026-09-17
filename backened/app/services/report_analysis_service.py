"""
Report Analysis conversation state machine.

Handles the multi-turn "report_analyses" flow that sits on top of the
plain column-rule validation in validation_service.py:

    upload -> DB-first unknown-code check -> (maybe) ask for a
    production reference file -> compare files -> surface conflicts ->
    ask the user to decide update/ignore -> generate a SQL script.

All state lives inside ConfigurationRequest.eval_profile, under the
top-level key "analysis_state" — sibling to the "rule_results" and
"step_workflow" keys already written by requests.py / step_by_step_service.py.
Reads/writes here always merge-preserve those other keys, the same way
step_by_step_service._save_workflow_data does.

Kept separate from step_by_step_service.py on purpose: that machine
assumes one rules document and exactly one string per turn. This flow
has heterogeneous turns (a file, or a discrete update/ignore decision)
keyed off validation results, not a rules list.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db.database import engine
from ..db.models import ReportReferenceFile, ReportScriptVersion
from .excel_service import read_data_rows
from . import validation_service
from . import schema_introspection

logger = logging.getLogger(__name__)

REFERENCE_UPLOAD_DIR = os.path.join("uploads", "reference_files")
os.makedirs(REFERENCE_UPLOAD_DIR, exist_ok=True)

Decision = Literal["update", "ignore"]


# ============================================================
# STATE STORAGE
# ============================================================

def _safe_json_loads(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError, ValueError):
        return default


def get_analysis_state(request) -> dict:
    """analysis_state lives inside request.eval_profile, preserving sibling keys."""

    profile = _safe_json_loads(getattr(request, "eval_profile", None), {})
    if not isinstance(profile, dict):
        profile = {}

    state = profile.get("analysis_state")
    if not isinstance(state, dict):
        state = {
            "task_type": None,
            "raw_rows": [],
            "anomalies": [],
            "questions_asked": [],
            "answers_received": [],
            "unresolved_issues": [],
            "validated_rows": [],
            "correction_mode": None,
        }

    # Back-fills requests whose analysis_state was written before
    # correction_mode existed, so callers can rely on the key always
    # being present.
    state.setdefault("correction_mode", None)

    return state


def _save_analysis_state(request, state: dict) -> None:
    profile = _safe_json_loads(getattr(request, "eval_profile", None), {})
    if not isinstance(profile, dict):
        profile = {}

    profile["analysis_state"] = state
    request.eval_profile = json.dumps(profile, ensure_ascii=False)


# Maps a stage to the closest existing `status` value, so the frontend's
# already-built Stepper/STATUS_CONFIG (keyed off `status`) reflects
# progress without needing a second, parallel stepper UI.
_STAGE_TO_STATUS = {
    "draft": "draft",
    "file_submitted": "file_submitted",
    "analysis": "analysis_in_progress",
    "awaiting_reference_file": "additional_information_required",
    "awaiting_decision": "additional_information_required",
    "validated": "data_validated",
    "script_generated": "script_generated",
    "completed": "processing_completed",
}


def advance_stage(db: Session, request, new_stage: str) -> None:
    request.current_stage = new_stage
    if new_stage in _STAGE_TO_STATUS:
        request.status = _STAGE_TO_STATUS[new_stage]
    db.add(request)
    db.commit()
    db.refresh(request)


def sync_stage_from_state(db: Session, request, state: dict) -> None:
    """
    Recomputes and persists current_stage from the anomaly list: no
    open issues -> validated; open conflicts -> awaiting a decision;
    open unknown codes -> still awaiting a reference file.
    """

    open_anomalies = [a for a in state["anomalies"] if a.get("status") == "open"]

    if not open_anomalies:
        advance_stage(db, request, "validated")
    elif any(a["kind"] == "conflict" for a in open_anomalies):
        advance_stage(db, request, "awaiting_decision")
    else:
        advance_stage(db, request, "awaiting_reference_file")


# ============================================================
# DB-FIRST ANOMALY DETECTION
# ============================================================

def _value_exists_in_table(db: Session, table: str, column: str, value) -> bool:
    if validation_service.is_blank(value):
        return True
    result = db.execute(
        text(f"SELECT TOP 1 1 FROM {table} WHERE {column} = :value"),
        {"value": value},
    ).first()
    return result is not None


def run_db_anomaly_check(
    db: Session,
    request,
    rows: list[dict],
    column_rules: list[dict],
    task_type: str | None = None,
) -> dict:
    """
    Runs the existing live foreign-key/lookup check (the same one
    validation_service.py uses) and records every failure as an
    "unknown_code" anomaly. Anomalies already resolved in a previous
    round are kept as-is.
    """

    state = get_analysis_state(request)
    state["task_type"] = task_type or state.get("task_type")
    state["raw_rows"] = rows

    existing_open_keys = {
        (a["row"], a["column"]) for a in state["anomalies"] if a.get("status") == "open"
    }

    for row in rows:
        row_number = row.get("_row_number")

        for rule in column_rules:
            fk = rule.get("foreign_key")
            if not fk:
                continue

            col_name = rule["name"]
            value = row.get(col_name)

            if (row_number, col_name) in existing_open_keys:
                continue  # already tracked from a prior round

            if _value_exists_in_table(db, fk["referred_table"], fk["referred_column"], value):
                continue  # DB check resolves it — no anomaly

            anomaly = {
                "id": uuid.uuid4().hex[:12],
                "row": row_number,
                "column": col_name,
                "code": value,
                "kind": "unknown_code",
                "status": "open",
                "decision": None,
                "reference_file_id": None,
                "conflict_detail": None,
                "detected_at": datetime.now().isoformat(),
            }
            state["anomalies"].append(anomaly)
            state["unresolved_issues"].append(anomaly["id"])

    _save_analysis_state(request, state)
    db.add(request)
    db.commit()
    db.refresh(request)

    return state


def needs_reference_file(anomaly: dict) -> bool:
    """
    True for any open anomaly: a production extract can help resolve
    any issue kind (missing value, bad format, duplicate, unknown
    code, inconsistency, incomplete relationship), not just unknown
    codes.
    """

    return anomaly.get("status") == "open"


# ============================================================
# GENERALIZED DETECTION: every validate_data_rows() kind, plus
# inconsistent values and incomplete relationships
# ============================================================

def seed_anomalies_from_errors(state: dict, validation_errors: list[dict]) -> None:
    """
    Turns the flat validate_data_rows() errors (missing_value,
    invalid_format, duplicate, unknown_code — see validation_service's
    "kind" tag) into anomalies, so they can be resolved through the
    same conversational actions (correction / reference-file /
    decision) as the existing unknown-code flow. Mutates both `state`
    and `validation_errors` in place: each error dict gets an
    "anomaly_id" stamped onto it so resolving the anomaly can flip its
    status back on the flat list the Validation Report table reads.
    """

    existing_open_keys = {
        (a["row"], a["column"]) for a in state["anomalies"] if a.get("status") == "open"
    }

    for error in validation_errors:
        if error.get("anomaly_id"):
            continue  # already seeded in a prior round

        row_number = error.get("row")
        column = error.get("column")

        if (row_number, column) in existing_open_keys:
            continue

        anomaly = {
            "id": uuid.uuid4().hex[:12],
            "row": row_number,
            "column": column,
            "code": error.get("submitted_value"),
            "kind": error.get("kind", "unknown_code"),
            "status": "open",
            "decision": None,
            "reference_file_id": None,
            "conflict_detail": None,
            "detected_at": datetime.now().isoformat(),
        }
        state["anomalies"].append(anomaly)
        state["unresolved_issues"].append(anomaly["id"])
        error["anomaly_id"] = anomaly["id"]


def detect_inconsistent_values(rows: list[dict], column_rules: list[dict]) -> list[dict]:
    """
    For every foreign-key column (a natural entity key), groups rows
    by that column's value. If two rows share the same key but
    disagree on another column's value, the file is describing the
    same referenced entity two different ways — flagged so the user
    can say which value is correct.
    """

    anomalies = []
    key_columns = [r["name"] for r in column_rules if r.get("foreign_key")]
    other_columns = [r["name"] for r in column_rules]

    for key_col in key_columns:
        groups: dict[str, list[dict]] = {}
        for row in rows:
            key_value = row.get(key_col)
            if validation_service.is_blank(key_value):
                continue
            groups.setdefault(str(key_value).strip(), []).append(row)

        for key_value, group_rows in groups.items():
            if len(group_rows) < 2:
                continue

            for other_col in other_columns:
                if other_col == key_col:
                    continue

                # More than one distinct non-empty value across the
                # group means an inconsistency.
                distinct_values = {
                    str(row.get(other_col)).strip(): row.get("_row_number")
                    for row in group_rows
                    if not validation_service.is_blank(row.get(other_col))
                }
                if len(distinct_values) < 2:
                    continue

                (value_a, row_a), (value_b, row_b) = list(distinct_values.items())[:2]
                anomalies.append({
                    "id": uuid.uuid4().hex[:12],
                    "row": row_b,
                    "column": other_col,
                    "code": value_b,
                    "kind": "inconsistent_value",
                    "status": "open",
                    "decision": None,
                    "reference_file_id": None,
                    "conflict_detail": {
                        "key_column": key_col,
                        "key_value": key_value,
                        other_col: {f"row {row_a}": value_a, f"row {row_b}": value_b},
                    },
                    "detected_at": datetime.now().isoformat(),
                })

    return anomalies


def detect_incomplete_relationships(db: Session, rows: list[dict], column_rules: list[dict]) -> list[dict]:
    """
    One hop further than plain FK-exists: the referenced value is
    found in the DB, but the referenced row itself is missing data
    its own table requires (a NOT NULL column left NULL) — a sign the
    production record this file depends on is itself incomplete.
    """

    anomalies = []
    referred_table_rules_cache: dict[str, list[dict]] = {}

    for rule in column_rules:
        fk = rule.get("foreign_key")
        if not fk:
            continue

        referred_table = fk["referred_table"]
        referred_column = fk["referred_column"]

        if referred_table not in referred_table_rules_cache:
            try:
                referred_table_rules_cache[referred_table] = schema_introspection.get_table_column_rules(
                    engine, referred_table,
                )
            except Exception:
                referred_table_rules_cache[referred_table] = []

        required_columns = [
            r["name"] for r in referred_table_rules_cache[referred_table]
            if r.get("required") and r["name"] != referred_column
        ]
        if not required_columns:
            continue

        col_name = rule["name"]

        for row in rows:
            value = row.get(col_name)
            if validation_service.is_blank(value):
                continue

            select_cols = ", ".join(required_columns)
            record = db.execute(
                text(f"SELECT TOP 1 {select_cols} FROM {referred_table} WHERE {referred_column} = :value"),
                {"value": value},
            ).mappings().first()

            if not record:
                continue  # plain FK-exists already flags this as unknown_code

            missing = [c for c in required_columns if record.get(c) is None]
            if not missing:
                continue

            anomalies.append({
                "id": uuid.uuid4().hex[:12],
                "row": row.get("_row_number"),
                "column": col_name,
                "code": value,
                "kind": "incomplete_relationship",
                "status": "open",
                "decision": None,
                "reference_file_id": None,
                "conflict_detail": {
                    "referred_table": referred_table,
                    "referred_column": referred_column,
                    "missing_columns": missing,
                },
                "detected_at": datetime.now().isoformat(),
            })

    return anomalies


def detect_duplicate_rows(rows: list[dict], column_rules: list[dict]) -> list[dict]:
    """
    Flags a row whose value is identical to an earlier row across every
    rule column — a likely copy-paste duplicate. Distinct from the
    "duplicate" kind (validate_data_rows' per-column `unique` check,
    which only catches one column repeating a value): this looks at
    the whole row at once, so it also catches a row that was cloned
    wholesale even though none of its individual columns are marked
    unique.
    """

    anomalies = []
    columns = [r["name"] for r in column_rules]
    seen: dict[tuple, int] = {}

    for row in rows:
        key = tuple(
            "" if validation_service.is_blank(row.get(col)) else str(row.get(col)).strip()
            for col in columns
        )
        if all(v == "" for v in key):
            continue  # a fully blank row isn't a meaningful duplicate

        if key in seen:
            anomalies.append({
                "id": uuid.uuid4().hex[:12],
                "row": row.get("_row_number"),
                "column": None,
                "code": None,
                "kind": "duplicate_row",
                "status": "open",
                "decision": None,
                "reference_file_id": None,
                "conflict_detail": {"duplicate_of_row": seen[key]},
                "detected_at": datetime.now().isoformat(),
            })
        else:
            seen[key] = row.get("_row_number")

    return anomalies


_STRUCTURAL_ANOMALY_KINDS = {
    "missing_value", "invalid_format", "duplicate", "negative_value",
    "unknown_code", "inconsistent_value", "incomplete_relationship",
    "duplicate_row", "invalid_choice", "out_of_range", "invalid_length",
    "formula_mismatch",
}


def _reset_open_structural_anomalies(state: dict) -> None:
    """
    Drops every open anomaly of a "structural" kind (everything this
    scan itself detects, as opposed to a "conflict" raised by a
    reference-file comparison) before re-scanning.

    Needed for resubmit-file: without this, an anomaly that the
    corrected file already fixes stays "open" forever, because the
    detectors below only ever add anomalies for issues they find —
    they never notice one has disappeared. Dropping the stale ones
    first means the fresh scan is the only source of truth for what's
    still open; anything already resolved, or a reference-file
    conflict, is untouched.
    """
    kept = []
    for anomaly in state["anomalies"]:
        if anomaly.get("status") == "open" and anomaly.get("kind") in _STRUCTURAL_ANOMALY_KINDS:
            if anomaly["id"] in state["unresolved_issues"]:
                state["unresolved_issues"].remove(anomaly["id"])
            continue
        kept.append(anomaly)
    state["anomalies"] = kept


def run_full_anomaly_scan(
    db: Session,
    request,
    rows: list[dict],
    column_rules: list[dict],
    validation_errors: list[dict],
    task_type: str | None = None,
) -> dict:
    """
    Single entry point that seeds every kind of issue into
    analysis_state.anomalies, so all of them can go through the same
    correction / reference-file / decision resolution flow:

      - unknown_code       (live FK re-check, existing behavior)
      - missing_value / invalid_format / duplicate / negative_value
                           (mirrored from validation_errors)
      - inconsistent_value (new)
      - incomplete_relationship (new)
      - duplicate_row (new — whole-row duplicate, not just one column)

    Safe to call more than once on the same request (e.g. resubmit-file
    swapping in a corrected version of the upload): stale open
    anomalies from a prior scan are cleared first, so the fresh scan
    is what decides what's still open.

    Mutates validation_errors in place (stamping anomaly_id onto each
    entry) — callers must re-persist it after this call.
    """

    state = get_analysis_state(request)
    _reset_open_structural_anomalies(state)
    _save_analysis_state(request, state)
    db.add(request)
    db.commit()
    db.refresh(request)

    state = run_db_anomaly_check(db, request, rows, column_rules, task_type=task_type)

    seed_anomalies_from_errors(state, validation_errors)

    for anomaly in detect_inconsistent_values(rows, column_rules):
        state["anomalies"].append(anomaly)
        state["unresolved_issues"].append(anomaly["id"])
        validation_errors.append({
            "row": anomaly["row"],
            "column": anomaly["column"],
            "submitted_value": anomaly["code"],
            "rule_violated": (
                f"Inconsistent with another row sharing the same "
                f"{anomaly['conflict_detail']['key_column']} = "
                f"'{anomaly['conflict_detail']['key_value']}'."
            ),
            "kind": "inconsistent_value",
            "status": "open",
            "user_correction": None,
            "resolved_at": None,
            "anomaly_id": anomaly["id"],
        })

    for anomaly in detect_incomplete_relationships(db, rows, column_rules):
        state["anomalies"].append(anomaly)
        state["unresolved_issues"].append(anomaly["id"])
        missing = ", ".join(anomaly["conflict_detail"]["missing_columns"])
        validation_errors.append({
            "row": anomaly["row"],
            "column": anomaly["column"],
            "submitted_value": anomaly["code"],
            "rule_violated": (
                f"References '{anomaly['conflict_detail']['referred_table']}."
                f"{anomaly['conflict_detail']['referred_column']}', which exists but is "
                f"itself missing required data ({missing})."
            ),
            "kind": "incomplete_relationship",
            "status": "open",
            "user_correction": None,
            "resolved_at": None,
            "anomaly_id": anomaly["id"],
        })

    for anomaly in detect_duplicate_rows(rows, column_rules):
        state["anomalies"].append(anomaly)
        state["unresolved_issues"].append(anomaly["id"])
        validation_errors.append({
            "row": anomaly["row"],
            "column": anomaly["column"],
            "submitted_value": anomaly["code"],
            "rule_violated": (
                f"This row duplicates row {anomaly['conflict_detail']['duplicate_of_row']} "
                "(same values across every column)."
            ),
            "kind": "duplicate_row",
            "status": "open",
            "user_correction": None,
            "resolved_at": None,
            "anomaly_id": anomaly["id"],
        })

    _save_analysis_state(request, state)
    db.add(request)
    db.commit()
    db.refresh(request)

    return state


def pending_reference_requests(request) -> list[dict]:
    """Open unknown_code anomalies that still need a reference file."""

    state = get_analysis_state(request)
    return [a for a in state["anomalies"] if needs_reference_file(a)]


def record_question_asked(db: Session, request, anomaly_id: str, question_text: str) -> None:
    state = get_analysis_state(request)
    state["questions_asked"].append({
        "id": uuid.uuid4().hex[:12],
        "anomaly_id": anomaly_id,
        "text": question_text,
        "asked_at": datetime.now().isoformat(),
    })
    _save_analysis_state(request, state)
    db.add(request)
    db.commit()


# ============================================================
# REFERENCE FILE / CONFLICT DETECTION
# ============================================================

def compare_files(primary_rows: list[dict], reference_rows: list[dict], key_column: str) -> list[dict]:
    """
    Row-level diff between the primary upload and a reference file,
    matched on key_column. Assumes both files use the same column name
    for the key under dispute (v1 simplification — no column mapping).
    """

    ref_index: dict[str, dict] = {}
    for ref_row in reference_rows:
        key = ref_row.get(key_column)
        if key is not None and str(key).strip() != "":
            ref_index[str(key).strip()] = ref_row

    results = []
    for row in primary_rows:
        key = row.get(key_column)
        if key is None or str(key).strip() == "":
            continue

        ref_row = ref_index.get(str(key).strip())
        if ref_row is None:
            results.append({
                "row": row.get("_row_number"),
                "key_column": key_column,
                "key_value": key,
                "found_in_reference": False,
                "diffs": {},
            })
            continue

        diffs = {}
        for col, val in row.items():
            if col in ("_row_number", key_column):
                continue
            if col in ref_row and str(ref_row.get(col)) != str(val):
                diffs[col] = {"primary": val, "reference": ref_row.get(col)}

        results.append({
            "row": row.get("_row_number"),
            "key_column": key_column,
            "key_value": key,
            "found_in_reference": True,
            "diffs": diffs,
        })

    return results


def record_reference_file(
    db: Session,
    request,
    uploaded_by_user_id: int,
    original_filename: str,
    file_bytes: bytes,
    linked_anomaly_id: str,
) -> dict:
    """
    Saves an uploaded reference file, compares it against the primary
    upload for the anomaly it was requested for, and updates that
    anomaly:
      - found in reference with no diff  -> resolved automatically
        (the reference file confirms the code, ready to be inserted).
      - found in reference with a diff   -> becomes a "conflict",
        stays open, needs an update/ignore decision.
      - not found in reference either    -> stays open, unresolved.
    """

    ext = os.path.splitext(original_filename)[1].lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = os.path.join(REFERENCE_UPLOAD_DIR, unique_name)
    with open(stored_path, "wb") as buffer:
        buffer.write(file_bytes)

    state = get_analysis_state(request)
    anomaly = next((a for a in state["anomalies"] if a["id"] == linked_anomaly_id), None)
    if anomaly is None:
        raise ValueError(f"No anomaly found with id '{linked_anomaly_id}'.")

    reference_rows = read_data_rows(stored_path)
    primary_rows = [r for r in state["raw_rows"] if r.get("_row_number") == anomaly["row"]]
    comparison = compare_files(primary_rows, reference_rows, anomaly["column"])
    match = next((c for c in comparison if c["row"] == anomaly["row"]), None)

    ref_file = ReportReferenceFile(
        request_id=request.id,
        uploaded_by=uploaded_by_user_id,
        original_filename=original_filename,
        stored_path=stored_path,
        size_bytes=len(file_bytes),
        linked_anomaly_id=linked_anomaly_id,
        comparison_result=json.dumps(comparison, ensure_ascii=False),
    )
    db.add(ref_file)
    db.commit()
    db.refresh(ref_file)

    anomaly["reference_file_id"] = ref_file.id

    if match and match["found_in_reference"] and not match["diffs"]:
        anomaly["status"] = "resolved"
        anomaly["decision"] = "update"
        if anomaly["id"] in state["unresolved_issues"]:
            state["unresolved_issues"].remove(anomaly["id"])
    elif match and match["found_in_reference"] and match["diffs"]:
        anomaly["kind"] = "conflict"
        anomaly["conflict_detail"] = match["diffs"]
        # stays open — needs an explicit update/ignore decision
    # else: still not found anywhere — left open as an unresolved unknown code

    _save_analysis_state(request, state)
    db.add(request)
    db.commit()
    db.refresh(request)

    sync_stage_from_state(db, request, state)

    return {"anomaly": anomaly, "comparison": comparison, "reference_file_id": ref_file.id}


# ============================================================
# UPDATE / IGNORE DECISIONS
# ============================================================

def record_decision(db: Session, request, anomaly_id: str, decision: Decision) -> dict:
    if decision not in ("update", "ignore"):
        raise ValueError("decision must be 'update' or 'ignore'.")

    state = get_analysis_state(request)
    anomaly = next((a for a in state["anomalies"] if a["id"] == anomaly_id), None)
    if anomaly is None:
        raise ValueError(f"No anomaly found with id '{anomaly_id}'.")

    anomaly["status"] = "resolved"
    anomaly["decision"] = decision

    if anomaly_id in state["unresolved_issues"]:
        state["unresolved_issues"].remove(anomaly_id)

    matching_question = next(
        (q for q in state["questions_asked"] if q["anomaly_id"] == anomaly_id),
        None,
    )
    state["answers_received"].append({
        "question_id": matching_question["id"] if matching_question else None,
        "anomaly_id": anomaly_id,
        "decision": decision,
        "answered_at": datetime.now().isoformat(),
    })

    _save_analysis_state(request, state)
    db.add(request)
    db.commit()
    db.refresh(request)

    sync_stage_from_state(db, request, state)

    return {"anomaly": anomaly, "all_resolved": all_resolved(request)}


def all_resolved(request) -> bool:
    state = get_analysis_state(request)
    return len(state.get("unresolved_issues") or []) == 0


# ============================================================
# CORRECTION MODE: chat vs. reopen-Excel-and-resubmit
# ============================================================
#
# Asked once per request, the first time there's an open anomaly the
# user could act on, so the chat doesn't silently assume they want to
# retype every fix by hand. The choice sticks for the rest of the
# request — it is not re-asked after a later resubmit or new anomaly
# batch, though the user can call set_correction_mode again to switch.

#  Kinds resolved only through an update/ignore decision or a reference
#  file — never by typing a corrected value — so asking chat-vs-Excel
#  is meaningless when these are the only open anomalies left.
_KINDS_WITHOUT_DIRECT_CORRECTION = frozenset({
    "conflict", "incomplete_relationship", "duplicate_row",
})


def needs_correction_mode_choice(state: dict) -> bool:
    """
    True when there's at least one open anomaly the user could fix by
    typing a corrected value, and they haven't yet said whether they'd
    rather do that here in chat or in Excel instead.
    """

    if state.get("correction_mode"):
        return False

    return any(
        a.get("status") == "open"
        and a.get("kind") not in _KINDS_WITHOUT_DIRECT_CORRECTION
        for a in (state.get("anomalies") or [])
    )


def set_correction_mode(db: Session, request, mode: str) -> dict:
    if mode not in ("chat", "excel"):
        raise ValueError("mode must be 'chat' or 'excel'.")

    state = get_analysis_state(request)
    state["correction_mode"] = mode

    _save_analysis_state(request, state)
    db.add(request)
    db.commit()
    db.refresh(request)

    return state


def resolve_with_correction(
    db: Session,
    request,
    anomaly_id: str,
    corrected_value: str,
    column_rules: list[dict],
) -> dict:
    """
    Re-validates a user-supplied corrected value against the rule for
    the anomaly's column, and on success applies it: updates the row
    in analysis_state.raw_rows (so script generation and any later
    consistency check see the fix), resolves the anomaly, and flips
    the matching validation_errors entry to solved.
    """

    state = get_analysis_state(request)
    anomaly = next((a for a in state["anomalies"] if a["id"] == anomaly_id), None)
    if anomaly is None:
        raise ValueError(f"No anomaly found with id '{anomaly_id}'.")

    rule = next((r for r in column_rules if r["name"] == anomaly["column"]), None)
    if rule is None:
        raise ValueError(f"No column rule found for '{anomaly['column']}'.")

    other_rows = [r for r in state["raw_rows"] if r.get("_row_number") != anomaly["row"]]
    check_error = validation_service.check_single_value(
        db, rule, corrected_value, other_rows, anomaly["row"],
    )

    if check_error:
        return {"accepted": False, "anomaly": anomaly, "reason": check_error["rule_violated"]}

    for row in state["raw_rows"]:
        if row.get("_row_number") == anomaly["row"]:
            row[anomaly["column"]] = corrected_value
            break

    anomaly["status"] = "resolved"
    anomaly["decision"] = "corrected"
    anomaly["code"] = corrected_value

    if anomaly_id in state["unresolved_issues"]:
        state["unresolved_issues"].remove(anomaly_id)

    _save_analysis_state(request, state)
    db.add(request)
    db.commit()
    db.refresh(request)

    sync_stage_from_state(db, request, state)

    return {"accepted": True, "anomaly": anomaly, "all_resolved": all_resolved(request)}


# ============================================================
# SQL SCRIPT GENERATION (deterministic — no AI)
# ============================================================

def _sql_literal(value) -> str:
    if validation_service.is_blank(value):
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def generate_sql_script(db: Session, request, task) -> tuple[str, int]:
    """
    Builds INSERT/UPDATE statements for every validated row, skipping
    rows tied to an "ignore" decision. INSERT vs UPDATE is decided by
    checking whether the row already exists in target_table on its
    unique/key columns (from column_rules).
    """

    if not task.target_table:
        raise ValueError("This task has no target_table configured; cannot generate a script.")

    column_rules = _safe_json_loads(task.column_rules, [])
    key_columns = [r["name"] for r in column_rules if r.get("unique")]
    known_columns = [r["name"] for r in column_rules]

    state = get_analysis_state(request)
    ignored_rows = {
        a["row"] for a in state["anomalies"]
        if a.get("decision") == "ignore"
    }

    statements = []
    row_count = 0

    for row in state.get("raw_rows", []):
        row_number = row.get("_row_number")
        if row_number in ignored_rows:
            continue

        values = {col: row.get(col) for col in known_columns if col in row}
        if not values:
            continue

        exists = False
        if key_columns:
            exists = all(
                _value_exists_in_table(db, task.target_table, k, values.get(k))
                and values.get(k) not in (None, "")
                for k in key_columns
            )

        if exists:
            set_clause = ", ".join(f"{col} = {_sql_literal(val)}" for col, val in values.items())
            where_clause = " AND ".join(f"{k} = {_sql_literal(values.get(k))}" for k in key_columns)
            statements.append(f"UPDATE {task.target_table} SET {set_clause} WHERE {where_clause};")
        else:
            cols = ", ".join(values.keys())
            vals = ", ".join(_sql_literal(v) for v in values.values())
            statements.append(f"INSERT INTO {task.target_table} ({cols}) VALUES ({vals});")

        row_count += 1

    script_text = "\n".join(statements) if statements else "-- No rows to apply."
    return script_text, row_count


def save_script_version(db: Session, request, script_text: str, row_count: int, generated_by_user_id: int) -> ReportScriptVersion:
    last_version = (
        db.query(ReportScriptVersion)
        .filter(ReportScriptVersion.request_id == request.id)
        .order_by(ReportScriptVersion.version_number.desc())
        .first()
    )
    next_version = (last_version.version_number + 1) if last_version else 1

    version = ReportScriptVersion(
        request_id=request.id,
        version_number=next_version,
        script_text=script_text,
        row_count=row_count,
        generated_by=generated_by_user_id,
    )
    db.add(version)

    request.generated_script = script_text
    db.add(request)
    db.commit()
    db.refresh(version)

    return version


# ============================================================
# CONVERSATIONAL SUMMARY
# ============================================================

_KIND_DESCRIPTIONS = {
    "missing_value": "missing required value(s)",
    "invalid_format": "value(s) in the wrong format",
    "duplicate": "duplicate value(s)",
    "negative_value": "negative value(s) where none were expected",
    "unknown_code": "unknown reference(s) — couldn't be matched in the database",
    "inconsistent_value": "inconsistent value(s) across rows describing the same record",
    "incomplete_relationship": "reference(s) pointing to a record that is itself missing required data",
    "duplicate_row": "row(s) that duplicate another row entirely",
    "invalid_choice": "value(s) outside the template's allowed choices",
    "out_of_range": "value(s) outside the template's allowed numeric range",
    "invalid_length": "value(s) with the wrong length for the template's rule",
    "formula_mismatch": "value(s) that don't match the template's own formula",
    "conflict": "conflict(s) between your file and a reference file",
}


def build_anomaly_summary_message(state: dict) -> str:
    """A short, friendly chat-facing summary of every open issue, grouped by kind."""

    anomalies = state.get("anomalies") or []
    unresolved = state.get("unresolved_issues") or []

    if not anomalies:
        return "Good news — I went through your file and didn't find any issues."

    open_by_kind: dict[str, int] = {}
    for a in anomalies:
        if a.get("status") != "open":
            continue
        open_by_kind[a["kind"]] = open_by_kind.get(a["kind"], 0) + 1

    if not open_by_kind:
        return "Everything's sorted now — you're all set to generate your script whenever you're ready."

    total_open = sum(open_by_kind.values())
    plural = "s" if total_open != 1 else ""

    lines = [
        f"## Open Issues ({total_open})",
        f"I went through your file and found {total_open} thing{plural} worth fixing before we finish up:",
        "",
    ]

    for kind, count in open_by_kind.items():
        description = _KIND_DESCRIPTIONS.get(kind, kind)
        lines.append(f"- **{count}** {description}")

    lines.append("")
    lines.append("## Next Steps")

    mode = state.get("correction_mode")

    if mode == "excel":
        lines.append(
            "You said you'd rather fix these in Excel — open the file, correct the "
            "flagged rows, and resubmit it here whenever you're ready and I'll check "
            "everything again. (Reference files and update/ignore decisions for "
            "unknown codes and conflicts still work the same either way.)"
        )
    elif mode == "chat":
        lines.append(
            "For each one you can send me the corrected value, attach a production extract, "
            "or (where it applies) tell me to update or ignore the record. You'll find the "
            "full list in the Validation Report, and I'm right here if you get stuck."
        )
    elif needs_correction_mode_choice(state):
        lines.append(
            "Would you rather fix these directly here in the chat, or reopen the Excel "
            "file, correct them there, and resubmit it for another check? Pick whichever's "
            "easier below."
        )
    else:
        # None of the open issues take a typed correction (only
        # conflicts / incomplete relationships / duplicate rows remain)
        # — nothing to ask chat-vs-Excel about.
        lines.append(
            "For each one you can attach a production extract, or tell me to update or "
            "ignore the record. You'll find the full list in the Validation Report, and "
            "I'm right here if you get stuck."
        )

    if not unresolved:
        lines.append("")
        lines.append("Everything's sorted now — you're all set to generate your script whenever you're ready.")

    return "\n".join(lines)
