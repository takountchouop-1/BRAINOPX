from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import ConfigurationRequest, ConfigurationTask
from app.services.groq_service import (
    parse_rules_to_json,
    generate_rule_example_with_retry,
)
from app.services.validation_service import get_validation_stats

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


router = APIRouter()


# ============================================================================
# REQUEST MODEL
# ============================================================================

class ChatRequest(BaseModel):
    request_id: int
    user_message: str


# ============================================================================
# BASIC HELPERS
# ============================================================================

def _now() -> str:
    return datetime.now().isoformat()


def _load_json(value: Any, default: Any) -> Any:
    """
    Safely decode JSON database fields.
    """

    if value is None:
        return default

    if isinstance(value, (dict, list)):
        return value

    if isinstance(value, str):

        value = value.strip()

        if not value:
            return default

        try:
            result = json.loads(value)

            if result is None:
                return default

            return result

        except Exception:
            return default

    return default


def _text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _case(value: Any) -> str:
    return _text(value).casefold()


# ============================================================================
# RULE LOADING
# ============================================================================

def _load_task_rules(
    task: ConfigurationTask,
    db: Session,
) -> Tuple[str, List[Dict[str, Any]]]:

    rules_content = ""
    parsed_rules: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------------
    # Load rules_content
    # ------------------------------------------------------------------------

    if task.rules_content:

        data = _load_json(
            task.rules_content,
            {},
        )

        if isinstance(data, dict):

            rules_content = (
                data.get("full_text")
                or data.get("text")
                or data.get("content")
                or ""
            )

        elif isinstance(data, str):

            rules_content = data

    # ------------------------------------------------------------------------
    # Load cached parsed rules
    # ------------------------------------------------------------------------

    if task.category_metadata:

        metadata = _load_json(
            task.category_metadata,
            {},
        )

        if isinstance(metadata, dict):

            cached = metadata.get(
                "parsed_rules"
            )

            if isinstance(cached, list):

                parsed_rules = cached

    # ------------------------------------------------------------------------
    # Parse rules if necessary
    # ------------------------------------------------------------------------

    if not parsed_rules and rules_content:

        try:

            parsed = parse_rules_to_json(
                rules_content
            )

            if isinstance(parsed, list):

                parsed_rules = parsed

                metadata = _load_json(
                    task.category_metadata,
                    {},
                )

                if not isinstance(
                    metadata,
                    dict,
                ):
                    metadata = {}

                metadata[
                    "parsed_rules"
                ] = parsed_rules

                task.category_metadata = json.dumps(
                    metadata,
                    ensure_ascii=False,
                )

                db.commit()

        except Exception as exc:

            print(
                "[RULE PARSER ERROR]",
                exc,
            )

    # ------------------------------------------------------------------------
    # Fallback: column_rules
    # ------------------------------------------------------------------------

    if not parsed_rules and task.column_rules:

        column_rules = _load_json(
            task.column_rules,
            [],
        )

        if isinstance(
            column_rules,
            list,
        ):

            for index, raw_rule in enumerate(
                column_rules,
                start=1,
            ):

                if not isinstance(
                    raw_rule,
                    dict,
                ):
                    continue

                rule = dict(raw_rule)

                rule.setdefault(
                    "id",
                    index,
                )

                rule.setdefault(
                    "name",
                    f"Rule {index}",
                )

                description = []

                if rule.get("required"):
                    description.append(
                        "This field is required."
                    )

                if rule.get("unique"):
                    description.append(
                        "This field must be unique."
                    )

                if rule.get("pattern"):
                    description.append(
                        "Value must match the required pattern."
                    )

                if rule.get("data_type"):
                    description.append(
                        f"Data type must be "
                        f"{rule['data_type']}."
                    )

                if rule.get("allowed_values"):
                    description.append(
                        "Allowed values: "
                        + ", ".join(
                            map(
                                str,
                                rule[
                                    "allowed_values"
                                ],
                            )
                        )
                    )

                rule.setdefault(
                    "description",
                    " ".join(description),
                )

                rule.setdefault(
                    "task",
                    f"Provide a valid value for "
                    f"{rule['name']}.",
                )

                parsed_rules.append(
                    rule
                )

    # ------------------------------------------------------------------------
    # Normalize rules
    # ------------------------------------------------------------------------

    cleaned = []

    for index, rule in enumerate(
        parsed_rules,
        start=1,
    ):

        if not isinstance(
            rule,
            dict,
        ):
            continue

        normalized = dict(rule)

        normalized.setdefault(
            "id",
            index,
        )

        normalized.setdefault(
            "name",
            f"Rule {index}",
        )

        normalized.setdefault(
            "description",
            "",
        )

        normalized.setdefault(
            "task",
            "",
        )

        normalized.setdefault(
            "expected_outcome",
            "",
        )

        cleaned.append(
            normalized
        )

    return (
        rules_content,
        cleaned,
    )


# ============================================================================
# COMPLETE RULE TEXT
# ============================================================================

def _rule_text(
    rule: Dict[str, Any],
) -> str:

    return "\n".join(
        [
            _text(
                rule.get("name")
                or rule.get("rule_name")
            ),
            _text(
                rule.get("description")
            ),
            _text(
                rule.get("task")
            ),
            _text(
                rule.get("expected_outcome")
            ),
            _text(
                rule.get("requirement")
            ),
        ]
    )


# ============================================================================
# EXPLICIT REGEX
# ============================================================================

def _get_pattern(
    rule: Dict[str, Any],
) -> str:

    value = (
        rule.get("pattern")
        or rule.get("regex")
        or rule.get("regular_expression")
    )

    if value is None:
        return ""

    return _text(value)


# ============================================================================
# PREFIX + DIGITS
# ============================================================================

def _extract_prefix_digit_pattern(
    rule: Dict[str, Any],
) -> Optional[str]:

    text = _rule_text(
        rule
    )

    if not text:
        return None

    patterns = [

        # SCH + 3 digits
        r"\b([A-Za-z]{1,15})\s*\+\s*(\d+)\s*(?:digits?|numbers?)\b",

        # SCH followed by 3 digits
        r"\b([A-Za-z]{1,15})\s+(?:followed\s+by|with)\s+(\d+)\s*(?:digits?|numbers?)\b",

        # format SCH123
        r"\bformat\s*:?\s*([A-Za-z]{1,15})(\d{1,10})\b",

        # value must be SCH followed by exactly 3 digits
        r"\b([A-Za-z]{1,15})\s+followed\s+by\s+exactly\s+(\d+)\s+digits?\b",
    ]

    for expression in patterns:

        match = re.search(
            expression,
            text,
            flags=re.IGNORECASE,
        )

        if match:

            prefix = match.group(1).upper()
            count = int(
                match.group(2)
            )

            return (
                rf"^{re.escape(prefix)}\d{{{count}}}$"
            )

    return None


# ============================================================================
# HUMAN DESCRIPTION OF PREFIX RULE
# ============================================================================

def _prefix_description(
    pattern: str,
) -> str:

    match = re.fullmatch(
        r"\^([A-Z]+)\\d\{(\d+)\}\$",
        pattern,
    )

    if match:

        return (
            f"{match.group(1)} followed by "
            f"exactly {match.group(2)} digits"
        )

    return pattern


# ============================================================================
# ALLOWED VALUES
# ============================================================================

def _get_allowed_values(
    rule: Dict[str, Any],
) -> List[str]:

    structured = rule.get(
        "allowed_values"
    )

    if isinstance(
        structured,
        (list, tuple, set),
    ):

        return [
            _text(x)
            for x in structured
            if _text(x)
        ]

    text = _rule_text(
        rule
    )

    expressions = [

        r"(?:allowed\s+(?:values?|types?|options?))\s*[:\-]\s*([A-Za-z0-9_\- ,/]+)",

        r"one\s+of\s+(?:the\s+)?(?:allowed\s+)?(?:values?|types?|options?)\s*[:\-]\s*([A-Za-z0-9_\- ,/]+)",

        r"must\s+be\s+one\s+of\s*[:\-]?\s*([A-Za-z0-9_\- ,/]+)",
    ]

    for expression in expressions:

        match = re.search(
            expression,
            text,
            flags=re.IGNORECASE,
        )

        if match:

            raw = match.group(1)

            values = re.split(
                r"\s*,\s*|\s*/\s*|\s+or\s+",
                raw,
                flags=re.IGNORECASE,
            )

            values = [
                _text(x)
                for x in values
                if _text(x)
            ]

            if len(values) >= 2:
                return values

    return []


# ============================================================================
# REQUIRED
# ============================================================================

def _is_required(
    rule: Dict[str, Any],
) -> bool:

    if rule.get(
        "required"
    ) is True:

        return True

    text = _rule_text(
        rule
    )

    return bool(
        re.search(
            r"\brequired\b"
            r"|\bmandatory\b"
            r"|\bmust\s+be\s+provided\b"
            r"|\bcannot\s+be\s+empty\b"
            r"|\bmust\s+not\s+be\s+empty\b"
            r"|\bnot\s+empty\b",
            text,
            flags=re.IGNORECASE,
        )
    )


# ============================================================================
# LENGTH
# ============================================================================

def _get_min_length(
    rule: Dict[str, Any],
) -> Optional[int]:

    value = rule.get(
        "min_length"
    )

    if value is not None:

        try:
            return int(value)
        except Exception:
            pass

    text = _rule_text(
        rule
    )

    expressions = [

        r"(?:at\s+least|minimum\s+of|min(?:imum)?\s+length\s*(?:is|of)?)\s*(\d+)\s*characters?",

        r"(\d+)\s*(?:to|-)\s*\d+\s*characters?",
    ]

    for expression in expressions:

        match = re.search(
            expression,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            return int(
                match.group(1)
            )

    return None


def _get_max_length(
    rule: Dict[str, Any],
) -> Optional[int]:

    value = rule.get(
        "max_length"
    )

    if value is not None:

        try:
            return int(value)
        except Exception:
            pass

    text = _rule_text(
        rule
    )

    expressions = [

        r"(?:at\s+most|maximum\s+of|max(?:imum)?\s+length\s*(?:is|of)?)\s*(\d+)\s*characters?",

        r"\d+\s*(?:to|-)\s*(\d+)\s*characters?",
    ]

    for expression in expressions:

        match = re.search(
            expression,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            return int(
                match.group(1)
            )

    return None


# ============================================================================
# DATA TYPE
# ============================================================================

def _get_data_type(
    rule: Dict[str, Any],
) -> str:

    value = rule.get(
        "data_type"
    )

    if value:
        return _case(value)

    text = _rule_text(
        rule
    )

    if re.search(
        r"\binteger\b|\bwhole\s+number\b",
        text,
        flags=re.IGNORECASE,
    ):
        return "integer"

    if re.search(
        r"\bdecimal\b|\bfloat\b|\bdouble\b|\bnumeric\b|\bnumber\b",
        text,
        flags=re.IGNORECASE,
    ):
        return "number"

    if re.search(
        r"\bboolean\b|\btrue\s+or\s+false\b",
        text,
        flags=re.IGNORECASE,
    ):
        return "boolean"

    return ""


# ============================================================================
# EMAIL
# ============================================================================

def _requires_email(
    rule: Dict[str, Any],
) -> bool:

    text = _rule_text(
        rule
    )

    return bool(
        re.search(
            r"\bemail\s+address\b"
            r"|\bvalid\s+email\b"
            r"|\bemail\s+format\b"
            r"|\bmust\s+be\s+an?\s+email\b"
            r"|\bmust\s+be\s+a\s+valid\s+email\b",
            text,
            flags=re.IGNORECASE,
        )
    )


# ============================================================================
# PHONE
# ============================================================================

def _requires_phone(
    rule: Dict[str, Any],
) -> bool:

    text = _rule_text(
        rule
    )

    return bool(
        re.search(
            r"\bphone\s+number\b"
            r"|\btelephone\s+number\b"
            r"|\bmobile\s+number\b"
            r"|\bphone\s+format\b",
            text,
            flags=re.IGNORECASE,
        )
    )


# ============================================================================
# FULL NAME
# ============================================================================

def _requires_full_name(
    rule: Dict[str, Any],
) -> bool:

    text = _rule_text(
        rule
    )

    return bool(
        re.search(
            r"\bfull\s+name\b"
            r"|\bfirst\s+name\s+and\s+last\s+name\b"
            r"|\bfirst\s+and\s+last\s+name\b",
            text,
            flags=re.IGNORECASE,
        )
    )


# ============================================================================
# DIGITS ONLY
# ============================================================================

def _digits_only(
    rule: Dict[str, Any],
) -> bool:

    text = _rule_text(
        rule
    )

    return bool(
        re.search(
            r"\bdigits\s+only\b"
            r"|\bnumbers\s+only\b"
            r"|\bonly\s+digits\b"
            r"|\bonly\s+numbers\b",
            text,
            flags=re.IGNORECASE,
        )
    )


# ============================================================================
# LETTERS ONLY
# ============================================================================

def _letters_only(
    rule: Dict[str, Any],
) -> bool:

    text = _rule_text(
        rule
    )

    return bool(
        re.search(
            r"\bletters\s+only\b"
            r"|\bonly\s+letters\b",
            text,
            flags=re.IGNORECASE,
        )
    )


# ============================================================================
# NUMERIC RANGE
# ============================================================================

def _get_range(
    rule: Dict[str, Any],
) -> Tuple[Optional[float], Optional[float]]:

    minimum = rule.get(
        "min_value"
    )

    maximum = rule.get(
        "max_value"
    )

    if (
        minimum is not None
        or maximum is not None
    ):

        try:

            return (
                float(minimum)
                if minimum is not None
                else None,

                float(maximum)
                if maximum is not None
                else None,
            )

        except Exception:
            pass

    text = _rule_text(
        rule
    )

    match = re.search(
        r"(?:between|from)\s+"
        r"(-?\d+(?:\.\d+)?)"
        r"\s+(?:and|to)\s+"
        r"(-?\d+(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )

    if match:

        return (
            float(match.group(1)),
            float(match.group(2)),
        )

    return (
        None,
        None,
    )


# ============================================================================
# DETERMINISTIC VALIDATOR
# ============================================================================

def validate_user_input(
    value: Any,
    rule: Dict[str, Any],
    previous_values: Optional[List[str]] = None,
) -> Dict[str, Any]:

    previous_values = (
        previous_values
        if isinstance(
            previous_values,
            list,
        )
        else []
    )

    value = _text(
        value
    )

    rule_name = _text(
        rule.get("name")
        or rule.get("rule_name")
        or "Rule"
    )

    # ------------------------------------------------------------------------
    # REQUIRED
    # ------------------------------------------------------------------------

    if not value:

        if _is_required(rule):

            return {
                "valid": False,
                "reason": (
                    f"{rule_name} is required."
                ),
            }

        return {
            "valid": True,
            "reason": (
                "Optional field."
            ),
        }

    # ------------------------------------------------------------------------
    # EXPLICIT REGEX
    # ------------------------------------------------------------------------

    explicit_pattern = _get_pattern(
        rule
    )

    if explicit_pattern:

        try:

            if not re.fullmatch(
                explicit_pattern,
                value,
                flags=re.IGNORECASE,
            ):

                return {
                    "valid": False,
                    "reason": (
                        "Value does not match "
                        "the required pattern."
                    ),
                }

        except re.error as exc:

            print(
                "[INVALID RULE REGEX]",
                explicit_pattern,
                exc,
            )

    # ------------------------------------------------------------------------
    # PREFIX + DIGITS
    # ------------------------------------------------------------------------

    prefix_pattern = (
        _extract_prefix_digit_pattern(
            rule
        )
    )

    if prefix_pattern:

        try:

            matched = re.fullmatch(
                prefix_pattern,
                value,
                flags=re.IGNORECASE,
            )

        except re.error as exc:

            print(
                "[PREFIX REGEX ERROR]",
                prefix_pattern,
                exc,
            )

            matched = False

        if not matched:

            return {
                "valid": False,
                "reason": (
                    "Value must be "
                    + _prefix_description(
                        prefix_pattern
                    )
                    + "."
                ),
            }

    # ------------------------------------------------------------------------
    # ALLOWED VALUES
    # ------------------------------------------------------------------------

    allowed = _get_allowed_values(
        rule
    )

    if allowed:

        lookup = {
            _case(item)
            for item in allowed
        }

        if _case(value) not in lookup:

            return {
                "valid": False,
                "reason": (
                    "Value must be one of: "
                    + ", ".join(allowed)
                    + "."
                ),
            }

    # ------------------------------------------------------------------------
    # MIN LENGTH
    # ------------------------------------------------------------------------

    minimum_length = _get_min_length(
        rule
    )

    if (
        minimum_length is not None
        and len(value) < minimum_length
    ):

        return {
            "valid": False,
            "reason": (
                f"Value must contain at least "
                f"{minimum_length} characters."
            ),
        }

    # ------------------------------------------------------------------------
    # MAX LENGTH
    # ------------------------------------------------------------------------

    maximum_length = _get_max_length(
        rule
    )

    if (
        maximum_length is not None
        and len(value) > maximum_length
    ):

        return {
            "valid": False,
            "reason": (
                f"Value must contain at most "
                f"{maximum_length} characters."
            ),
        }

    # ------------------------------------------------------------------------
    # EMAIL
    # ------------------------------------------------------------------------

    if _requires_email(rule):

        if not re.fullmatch(
            r"[A-Za-z0-9._%+-]+@"
            r"[A-Za-z0-9.-]+\."
            r"[A-Za-z]{2,}",
            value,
        ):

            return {
                "valid": False,
                "reason": (
                    "Value must be a valid "
                    "email address."
                ),
            }

    # ------------------------------------------------------------------------
    # PHONE
    # ------------------------------------------------------------------------

    if _requires_phone(rule):

        phone = re.sub(
            r"[\s\-\(\)]",
            "",
            value,
        )

        if not re.fullmatch(
            r"\+?\d{7,15}",
            phone,
        ):

            return {
                "valid": False,
                "reason": (
                    "Value must be a valid "
                    "phone number."
                ),
            }

    # ------------------------------------------------------------------------
    # FULL NAME
    # ------------------------------------------------------------------------

    if _requires_full_name(rule):

        if not re.fullmatch(
            r"[A-Za-zÀ-ÖØ-öø-ÿ' -]+",
            value,
        ):

            return {
                "valid": False,
                "reason": (
                    "Full name may contain "
                    "letters, spaces, apostrophes "
                    "and hyphens only."
                ),
            }

        if len(
            value.split()
        ) < 2:

            return {
                "valid": False,
                "reason": (
                    "Please provide at least "
                    "a first name and a last name."
                ),
            }

    # ------------------------------------------------------------------------
    # DIGITS ONLY
    # ------------------------------------------------------------------------

    if _digits_only(rule):

        if not re.fullmatch(
            r"\d+",
            value,
        ):

            return {
                "valid": False,
                "reason": (
                    "Value must contain digits only."
                ),
            }

    # ------------------------------------------------------------------------
    # LETTERS ONLY
    # ------------------------------------------------------------------------

    if _letters_only(rule):

        if not re.fullmatch(
            r"[A-Za-zÀ-ÖØ-öø-ÿ]+",
            value,
        ):

            return {
                "valid": False,
                "reason": (
                    "Value must contain letters only."
                ),
            }

    # ------------------------------------------------------------------------
    # DATA TYPE
    # ------------------------------------------------------------------------

    data_type = _get_data_type(
        rule
    )

    if data_type in {
        "integer",
        "int",
    }:

        if not re.fullmatch(
            r"-?\d+",
            value,
        ):

            return {
                "valid": False,
                "reason": (
                    "Value must be an integer."
                ),
            }

    elif data_type in {
        "number",
        "numeric",
        "float",
        "double",
        "decimal",
    }:

        if not re.fullmatch(
            r"-?(?:\d+(?:\.\d+)?|\.\d+)",
            value,
        ):

            return {
                "valid": False,
                "reason": (
                    "Value must be a valid number."
                ),
            }

    elif data_type in {
        "boolean",
        "bool",
    }:

        if _case(value) not in {
            "true",
            "false",
            "yes",
            "no",
        }:

            return {
                "valid": False,
                "reason": (
                    "Value must be true, false, "
                    "yes, or no."
                ),
            }

    # ------------------------------------------------------------------------
    # NUMERIC RANGE
    # ------------------------------------------------------------------------

    minimum, maximum = _get_range(
        rule
    )

    if (
        minimum is not None
        or maximum is not None
    ):

        try:

            numeric_value = float(
                value
            )

        except ValueError:

            return {
                "valid": False,
                "reason": (
                    "Value must be numeric."
                ),
            }

        if (
            minimum is not None
            and numeric_value < minimum
        ):

            return {
                "valid": False,
                "reason": (
                    f"Value must be at least "
                    f"{minimum:g}."
                ),
            }

        if (
            maximum is not None
            and numeric_value > maximum
        ):

            return {
                "valid": False,
                "reason": (
                    f"Value must be at most "
                    f"{maximum:g}."
                ),
            }

    # ------------------------------------------------------------------------
    # UNIQUE
    # ------------------------------------------------------------------------

    is_unique = bool(
        rule.get("unique")
    )

    if not is_unique:

        is_unique = bool(
            re.search(
                r"\bunique\b",
                _rule_text(rule),
                flags=re.IGNORECASE,
            )
        )

    if is_unique:

        current = _case(
            value
        )

        for previous in previous_values:

            if _case(
                previous
            ) == current:

                return {
                    "valid": False,
                    "reason": (
                        "This value must be unique. "
                        "The value has already been used."
                    ),
                }

    # ------------------------------------------------------------------------
    # SUCCESS
    # ------------------------------------------------------------------------

    return {
        "valid": True,
        "reason": (
            "The value satisfies the rule."
        ),
    }


# ============================================================================
# EXAMPLE GENERATION
# ============================================================================

def _fallback_example(
    rule: Dict[str, Any],
) -> str:

    # ------------------------------------------------------------------------
    # Explicit example
    # ------------------------------------------------------------------------

    candidates = [
        rule.get("example"),
        rule.get("example_input"),
        rule.get("suggested_fix"),
    ]

    for candidate in candidates:

        candidate = _text(
            candidate
        )

        if candidate:

            result = validate_user_input(
                candidate,
                rule,
                [],
            )

            if result["valid"]:
                return candidate

    # ------------------------------------------------------------------------
    # Allowed values
    # ------------------------------------------------------------------------

    allowed = _get_allowed_values(
        rule
    )

    for candidate in allowed:

        result = validate_user_input(
            candidate,
            rule,
            [],
        )

        if result["valid"]:
            return candidate

    # ------------------------------------------------------------------------
    # Prefix + digits
    # ------------------------------------------------------------------------

    pattern = (
        _extract_prefix_digit_pattern(
            rule
        )
    )

    if pattern:

        match = re.fullmatch(
            r"\^([A-Z]+)\\d\{(\d+)\}\$",
            pattern,
        )

        if match:

            prefix = match.group(1)
            count = int(
                match.group(2)
            )

            candidate = (
                prefix
                + ("0" * count)
            )

            result = validate_user_input(
                candidate,
                rule,
                [],
            )

            if result["valid"]:
                return candidate

    # ------------------------------------------------------------------------
    # Email
    # ------------------------------------------------------------------------

    if _requires_email(rule):

        candidate = (
            "example@example.com"
        )

        if validate_user_input(
            candidate,
            rule,
            [],
        )["valid"]:

            return candidate

    # ------------------------------------------------------------------------
    # Phone
    # ------------------------------------------------------------------------

    if _requires_phone(rule):

        candidate = (
            "+237690000000"
        )

        if validate_user_input(
            candidate,
            rule,
            [],
        )["valid"]:

            return candidate

    # ------------------------------------------------------------------------
    # Boolean
    # ------------------------------------------------------------------------

    if _get_data_type(rule) in {
        "boolean",
        "bool",
    }:

        return "true"

    # ------------------------------------------------------------------------
    # Integer
    # ------------------------------------------------------------------------

    if _get_data_type(rule) in {
        "integer",
        "int",
    }:

        return "1"

    # ------------------------------------------------------------------------
    # Number
    # ------------------------------------------------------------------------

    if _get_data_type(rule) in {
        "number",
        "numeric",
        "float",
        "decimal",
        "double",
    }:

        return "1.0"

    return ""


def _generate_example(
    rule: Dict[str, Any],
    task_name: str,
) -> Dict[str, Any]:

    # ------------------------------------------------------------------------
    # A VALUE ALREADY ON THE RULE
    #
    # Usually a real Groq example generated once at task-creation time
    # by example_utils.build_rules_with_examples() (source "ai"), or,
    # more rarely, a literal example lifted straight from the document
    # text (source "rule"). Reusing it here avoids a second Groq call
    # for something already answered. _fallback_example() also tries
    # unambiguous local guesses (allowed values, prefix+digits, email,
    # phone...) when nothing is stored — those are genuinely "builder",
    # not the AI's answer, and are labelled as such below.
    # ------------------------------------------------------------------------

    fallback = _fallback_example(
        rule
    )

    if fallback:

        validation = validate_user_input(
            fallback,
            rule,
            [],
        )

        if validation["valid"]:

            stored = _text(
                rule.get("example")
                or rule.get("example_input")
                or rule.get("suggested_fix")
            )

            source = (
                (rule.get("example_source") or "rule")
                if stored and fallback == stored
                else "builder"
            )

            return {
                "example": fallback,
                "validated": True,
                "reason": validation["reason"],
                "source": source,
            }

    # ------------------------------------------------------------------------
    # Ask Groq only if nothing usable was already stored or guessed.
    #
    # generate_rule_example_with_retry(rule=..., max_retries=...) is the
    # only signature the function has (see groq_service.py). This used
    # to be called with rule_name=/rule_text=/task_name=/validator=
    # keywords it does not accept, which raised a TypeError on every
    # call — silently swallowed by the except below — so Groq was never
    # actually reached from this endpoint; every example fell straight
    # through to "No valid example could be generated."
    #
    # On failure this returns example="" (see groq_service.py) rather
    # than a silently substituted local value — that empty string must
    # not be treated as a validated example just because an optional
    # field accepts blank input.
    # ------------------------------------------------------------------------

    try:

        result = generate_rule_example_with_retry(
            rule=rule,
        )

        if isinstance(
            result,
            dict,
        ):

            example = _text(
                result.get("example")
            )

            if example:

                validation = validate_user_input(
                    example,
                    rule,
                    [],
                )

                if validation["valid"]:

                    return {
                        "example": example,
                        "validated": True,
                        "reason": validation["reason"],
                        "source": "ai",
                    }

    except Exception as exc:

        print(
            "[EXAMPLE GENERATION ERROR]",
            exc,
        )

    return {
        "example": "",
        "validated": False,
        "reason": (
            "The AI service could not generate an example for this "
            "rule right now."
        ),
        "source": "ai_unavailable",
    }


# ============================================================================
# WORKFLOW STATE
# ============================================================================

def _get_workflow(
    history: List[Any],
) -> Dict[str, Any]:

    for item in reversed(history):

        if (
            isinstance(item, dict)
            and "_workflow" in item
        ):

            state = item[
                "_workflow"
            ]

            if isinstance(
                state,
                dict,
            ):

                return state

    return {
        "current_rule_index": 0,
        "completed_rules": [],
        "rule_results": [],
        "started": False,
        "completed": False,
    }


def _save_workflow(
    history: List[Any],
    workflow: Dict[str, Any],
) -> None:

    history[:] = [
        item
        for item in history
        if not (
            isinstance(item, dict)
            and "_workflow" in item
        )
    ]

    history.append(
        {
            "_workflow": workflow,
            "timestamp": _now(),
        }
    )


# ============================================================================
# USER VALUES
# ============================================================================

def _previous_user_values(
    history: List[Any],
) -> List[str]:

    result = []

    for item in history:

        if not isinstance(
            item,
            dict,
        ):
            continue

        if item.get(
            "sender"
        ) != "user":
            continue

        value = _text(
            item.get("text")
        )

        if value:
            result.append(
                value
            )

    return result


# ============================================================================
# RESPONSE HELPERS
# ============================================================================

def _rule_payload(
    rule: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:

    if not rule:
        return None

    return {
        "id": rule.get("id"),
        "name": rule.get("name"),
        "description": rule.get(
            "description"
        ),
        "task": rule.get(
            "task"
        ),
        "expected_outcome": rule.get(
            "expected_outcome"
        ),
    }


def _initial_message(
    rule: Dict[str, Any],
    step: int,
    total: int,
    example: str,
) -> str:

    name = _text(
        rule.get("name")
    )

    description = _text(
        rule.get("description")
    )

    task = _text(
        rule.get("task")
    )

    response = (
        f"Welcome to the task creation\n\n"
        f"**Step {step}/{total}: {name}**\n\n"
    )

    if description:

        response += (
            f"{description}\n\n"
        )

    if task:

        response += (
            f"{task}\n\n"
        )

    if example:

        response += (
            f"**Example:** `{example}`\n\n"
        )

    response += (
        f"Please provide your value for "
        f"**{name}**."
    )

    return response


# ============================================================================
# MAIN CHAT ENDPOINT
# ============================================================================

@router.post("/chat")
async def chat_with_assistant(
    chat_request: ChatRequest,
    db: Session = Depends(get_db),
):

    # ========================================================================
    # LOAD REQUEST
    # ========================================================================

    request = (
        db.query(
            ConfigurationRequest
        )
        .filter(
            ConfigurationRequest.id
            == chat_request.request_id
        )
        .first()
    )

    if not request:

        raise HTTPException(
            status_code=404,
            detail="Request not found",
        )

    # ========================================================================
    # LOAD TASK
    # ========================================================================

    task = (
        db.query(
            ConfigurationTask
        )
        .filter(
            ConfigurationTask.id
            == request.task_id
        )
        .first()
    )

    if not task:

        raise HTTPException(
            status_code=404,
            detail="Configuration task not found",
        )

    task_name = (
        _text(task.name)
        or "Configuration"
    )

    # ========================================================================
    # LOAD RULES
    # ========================================================================

    _, rules = _load_task_rules(
        task,
        db,
    )

    if not rules:

        raise HTTPException(
            status_code=400,
            detail=(
                "No validation rules were found "
                "for this task."
            ),
        )

    total = len(
        rules
    )

    # ========================================================================
    # LOAD HISTORY
    # ========================================================================

    history = _load_json(
        request.conversation,
        [],
    )

    if not isinstance(
        history,
        list,
    ):
        history = []

    # ========================================================================
    # LOAD ERRORS
    # ========================================================================

    validation_errors = _load_json(
        request.validation_errors,
        [],
    )

    if not isinstance(
        validation_errors,
        list,
    ):
        validation_errors = []

    # ========================================================================
    # LOAD WORKFLOW
    # ========================================================================

    workflow = _get_workflow(
        history
    )

    # ========================================================================
    # COMPLETED
    # ========================================================================

    if workflow.get(
        "completed"
    ):

        response = (
            "✅ **Task completed successfully.**\n\n"
            "All configuration rules have been "
            "validated successfully.\n\n"
            "The task is ready for final "
            "configuration script generation."
        )

        return {
            "request_id": chat_request.request_id,
            "user_message": chat_request.user_message,
            "ai_response": response,
            "user_input_valid": True,
            "completed": True,
            "ready_for_script": True,
            "workflow": workflow,
            "validation_errors": validation_errors,
            "stats": get_validation_stats(
                validation_errors
            ),
        }

    # ========================================================================
    # CURRENT INDEX
    # ========================================================================

    try:

        current_index = int(
            workflow.get(
                "current_rule_index",
                0,
            )
        )

    except Exception:

        current_index = 0

    if current_index < 0:
        current_index = 0

    if current_index >= total:

        workflow[
            "completed"
        ] = True

        _save_workflow(
            history,
            workflow,
        )

        request.conversation = json.dumps(
            history,
            ensure_ascii=False,
        )

        db.commit()

        response = (
            "✅ All configuration rules "
            "have been completed successfully."
        )

        return {
            "request_id": chat_request.request_id,
            "user_message": chat_request.user_message,
            "ai_response": response,
            "user_input_valid": True,
            "completed": True,
            "ready_for_script": True,
            "workflow": workflow,
            "validation_errors": validation_errors,
            "stats": get_validation_stats(
                validation_errors
            ),
        }

    # ========================================================================
    # CURRENT RULE
    # ========================================================================

    current_rule = rules[
        current_index
    ]

    step = (
        current_index + 1
    )

    # ========================================================================
    # HAS USER ALREADY ANSWERED THIS RULE?
    # ========================================================================

    rule_results = workflow.get(
        "rule_results",
        [],
    )

    if not isinstance(
        rule_results,
        list,
    ):

        rule_results = []

    current_rule_answered = any(
        isinstance(item, dict)
        and item.get(
            "step_index"
        ) == current_index
        for item in rule_results
    )

    # ========================================================================
    # FIRST DISPLAY OF RULE
    # ========================================================================

    if not current_rule_answered:

        generated = _generate_example(
            current_rule,
            task_name,
        )

        example = generated[
            "example"
        ]

        response = _initial_message(
            current_rule,
            step,
            total,
            example,
        )

        history.append(
            {
                "sender": "ai",
                "text": response,
                "timestamp": _now(),
            }
        )

        workflow[
            "started"
        ] = True

        _save_workflow(
            history,
            workflow,
        )

        request.conversation = json.dumps(
            history,
            ensure_ascii=False,
        )

        db.commit()

        return {
            "request_id": chat_request.request_id,
            "user_message": chat_request.user_message,
            "ai_response": response,
            "user_input_valid": None,
            "completed": False,
            "ready_for_script": False,
            "workflow": workflow,
            "current_rule": _rule_payload(
                current_rule
            ),
            "generated_example": example,
            "example_validated": generated[
                "validated"
            ],
            "example_source": generated.get(
                "source", "none"
            ),
            "validation_reason": generated[
                "reason"
            ],
            "validation_errors": validation_errors,
            "stats": get_validation_stats(
                validation_errors
            ),
        }

    # ========================================================================
    # USER INPUT
    # ========================================================================

    user_value = _text(
        chat_request.user_message
    )

    previous_values = (
        _previous_user_values(
            history
        )
    )

    # ========================================================================
    # IMPORTANT:
    #
    # THE ONLY AUTHORITY FOR USER VALIDATION
    # IS validate_user_input().
    #
    # GROQ IS NOT USED HERE.
    # ========================================================================

    validation = validate_user_input(
        value=user_value,
        rule=current_rule,
        previous_values=previous_values,
    )

    valid = bool(
        validation.get(
            "valid"
        )
    )

    reason = _text(
        validation.get(
            "reason"
        )
    )

    # ========================================================================
    # INVALID
    # ========================================================================

    if not valid:

        validation_error = {
            "step_index": current_index,
            "step_number": step,
            "rule_id": current_rule.get(
                "id"
            ),
            "rule_name": current_rule.get(
                "name"
            ),
            "value": user_value,
            "reason": reason,
            "timestamp": _now(),
        }

        validation_errors.append(
            validation_error
        )

        generated = _generate_example(
            current_rule,
            task_name,
        )

        example = generated[
            "example"
        ]

        response = (
            f"❌ **The value does not satisfy "
            f"this rule.**\n\n"
            f"**Rule:** "
            f"{current_rule.get('name', 'Rule')}\n\n"
            f"**Requirement:** "
            f"{current_rule.get('description', '')}\n\n"
            f"**Problem:** "
            f"{reason}\n\n"
        )

        if example:

            response += (
                f"**Example of a valid value:** "
                f"`{example}`\n\n"
            )

        response += (
            f"Please provide another value for "
            f"**{current_rule.get('name', 'Rule')}**."
        )

        # --------------------------------------------------------------------
        # SAVE USER
        # --------------------------------------------------------------------

        history.append(
            {
                "sender": "user",
                "text": user_value,
                "timestamp": _now(),
            }
        )

        # --------------------------------------------------------------------
        # SAVE AI
        # --------------------------------------------------------------------

        history.append(
            {
                "sender": "ai",
                "text": response,
                "timestamp": _now(),
            }
        )

        # --------------------------------------------------------------------
        # VERY IMPORTANT:
        #
        # DO NOT CHANGE current_rule_index.
        # --------------------------------------------------------------------

        workflow[
            "current_rule_index"
        ] = current_index

        _save_workflow(
            history,
            workflow,
        )

        request.validation_errors = json.dumps(
            validation_errors,
            ensure_ascii=False,
        )

        request.conversation = json.dumps(
            history,
            ensure_ascii=False,
        )

        db.commit()

        return {
            "request_id": chat_request.request_id,
            "user_message": user_value,
            "ai_response": response,
            "user_input_valid": False,
            "completed": False,
            "ready_for_script": False,
            "workflow": workflow,
            "current_rule": _rule_payload(
                current_rule
            ),
            "generated_example": example,
            "example_validated": generated[
                "validated"
            ],
            "example_source": generated.get(
                "source", "none"
            ),
            "validation_reason": reason,
            "validation_errors": validation_errors,
            "stats": get_validation_stats(
                validation_errors
            ),
        }

    # ========================================================================
    # VALID
    # ========================================================================

    rule_result = {
        "step_index": current_index,
        "step_number": step,
        "rule_id": current_rule.get(
            "id"
        ),
        "rule_name": current_rule.get(
            "name"
        ),
        "user_value": user_value,
        "validated": True,
        "validation_reason": reason,
        "timestamp": _now(),
    }

    workflow.setdefault(
        "rule_results",
        [],
    )

    workflow[
        "rule_results"
    ].append(
        rule_result
    )

    workflow.setdefault(
        "completed_rules",
        [],
    )

    workflow[
        "completed_rules"
    ].append(
        current_rule.get(
            "id"
        )
    )

    workflow[
        "started"
    ] = True

    # ========================================================================
    # MOVE TO NEXT RULE
    # ========================================================================

    next_index = (
        current_index + 1
    )

    workflow[
        "current_rule_index"
    ] = next_index

    # ========================================================================
    # ALL COMPLETED
    # ========================================================================

    if next_index >= total:

        workflow[
            "completed"
        ] = True

        response = (
            "✅ **Rule completed successfully.**\n\n"
            "🎉 All configuration rules have "
            "now been completed successfully.\n\n"
            "The task is ready for final "
            "configuration script generation."
        )

        next_rule = None
        next_example = ""
        next_example_source = "none"

    # ========================================================================
    # NEXT RULE
    # ========================================================================

    else:

        workflow[
            "completed"
        ] = False

        next_rule = rules[
            next_index
        ]

        next_step = (
            next_index + 1
        )

        generated = _generate_example(
            next_rule,
            task_name,
        )

        next_example = generated[
            "example"
        ]

        next_example_source = generated.get(
            "source", "none"
        )

        response = (
            "✅ **Rule completed successfully.**\n\n"
            f"Now proceed to: "
            f"**{next_rule.get('name', 'Rule')}**\n\n"
            f"### Step {next_step}/{total}: "
            f"{next_rule.get('name', 'Rule')}\n\n"
            f"**Rule:** "
            f"{next_rule.get('description', '')}\n\n"
        )

        if next_rule.get(
            "task"
        ):

            response += (
                f"**What to do:** "
                f"{next_rule.get('task')}\n\n"
            )

        if next_example:

            response += (
                f"**Example:** "
                f"`{next_example}`\n\n"
            )

        response += (
            f"Please provide your value for "
            f"**{next_rule.get('name', 'Rule')}**."
        )

    # ========================================================================
    # SAVE USER
    # ========================================================================

    history.append(
        {
            "sender": "user",
            "text": user_value,
            "timestamp": _now(),
        }
    )

    # ========================================================================
    # SAVE AI
    # ========================================================================

    history.append(
        {
            "sender": "ai",
            "text": response,
            "timestamp": _now(),
        }
    )

    # ========================================================================
    # SAVE
    # ========================================================================

    _save_workflow(
        history,
        workflow,
    )

    request.validation_errors = json.dumps(
        validation_errors,
        ensure_ascii=False,
    )

    request.conversation = json.dumps(
        history,
        ensure_ascii=False,
    )

    db.commit()

    # ========================================================================
    # RETURN
    # ========================================================================

    return {
        "request_id": chat_request.request_id,
        "user_message": user_value,
        "ai_response": response,
        "user_input_valid": True,
        "completed": workflow[
            "completed"
        ],
        "ready_for_script": workflow[
            "completed"
        ],
        "workflow": workflow,
        "current_rule": (
            _rule_payload(
                next_rule
            )
            if next_rule
            else _rule_payload(
                current_rule
            )
        ),
        "generated_example": next_example,
        "example_validated": bool(
            next_example
        ),
        "example_source": next_example_source,
        "validation_reason": reason,
        "validation_errors": validation_errors,
        "stats": get_validation_stats(
            validation_errors
        ),
    }