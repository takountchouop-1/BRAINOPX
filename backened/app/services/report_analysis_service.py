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

from ..db.models import ReportReferenceFile, ReportScriptVersion
from .excel_service import read_data_rows

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
        }

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
    if value is None or (isinstance(value, str) and value.strip() == ""):
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
    True for every open unknown_code anomaly: by the time one exists,
    the DB check has already had its shot (run_db_anomaly_check only
    creates one when the live lookup failed).
    """

    return anomaly.get("kind") == "unknown_code" and anomaly.get("status") == "open"


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
# SQL SCRIPT GENERATION (deterministic — no AI)
# ============================================================

def _sql_literal(value) -> str:
    if value is None or (isinstance(value, str) and value.strip() == ""):
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

def build_anomaly_summary_message(state: dict) -> str:
    """A short chat-facing summary of where the analysis stands."""

    anomalies = state.get("anomalies") or []
    unresolved = state.get("unresolved_issues") or []

    if not anomalies:
        return "I checked every code against the database and didn't find any unknown values."

    open_unknown = [a for a in anomalies if a["status"] == "open" and a["kind"] == "unknown_code"]
    open_conflicts = [a for a in anomalies if a["status"] == "open" and a["kind"] == "conflict"]

    lines = [f"I found {len(anomalies)} code(s) that need attention."]

    if open_unknown:
        lines.append(
            f"**{len(open_unknown)} unknown code(s)** couldn't be matched in the database. "
            "Please upload a production extract so I can cross-check them."
        )
    if open_conflicts:
        lines.append(
            f"**{len(open_conflicts)} conflict(s)** were found between your file and the reference "
            "data — please confirm whether to update the existing record or ignore it, for each one."
        )
    if not unresolved:
        lines.append("Everything is resolved — ready to generate the script.")

    return "\n\n".join(lines)
