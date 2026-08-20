"""
BRAINOPX - Groq AI Service
===========================

Architecture:

    TASK
      |
      v
    LOAD ALL RULES
      |
      v
    CURRENT RULE
      |
      +-----------------------------+
      |                             |
      v                             v
  Generate Example             User Input
      |                             |
      v                             v
  Deterministic                  Deterministic
  Validation                     Validation
      |                             |
      v                             v
   VALID?                        VALID?
   /    \                        /    \
 YES    NO                      YES    NO
  |      |                       |      |
  |    Retry                     |    Stay on
  |    Groq                      |    same step
  |      |                       |
  |      v                       |
  |  Deterministic               |
  |  Validation                  |
  |      |                       |
  |      v                       |
  |  Fallback                    |
  |      |                       |
  +------+-----------------------+
         |
         v
   COMPLETE CURRENT RULE
         |
         v
   MOVE TO NEXT RULE

IMPORTANT:

- Groq generates examples/explanations only.
- Python deterministic validation is authoritative.
- AI cannot decide whether user input is valid.
- AI cannot modify rule constraints.
- A failed input never advances the task.
- The same validation engine is used for:
    * AI examples
    * user input
    * deterministic fallback
- Rules are normalized so future tasks use the same logic.
"""

import copy
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Optional

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

from .sql_constraint_parser import extract_rules_from_sql


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b",
)

MAX_RETRIES = int(
    os.getenv(
        "GROQ_EXAMPLE_MAX_RETRIES",
        "3",
    )
)


# ============================================================
# GROQ CLIENT
# ============================================================

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)


# ============================================================
# CONSTANTS
# ============================================================

GENERIC_PLACEHOLDERS = {
    "example",
    "sample",
    "test",
    "value",
    "valid",
    "valid001",
    "example001",
    "test001",
    "sample001",
    "user001",
    "abc",
    "xyz",
    "hello",
    "hi",
    "j",
    "e",
    "df",
    "t",
    "y",
    "i",
    "a",
    "b",
    "c",
    "d",
    "f",
    "g",
    "h",
    "k",
    "l",
    "m",
    "n",
    "o",
    "p",
    "q",
    "r",
    "s",
    "u",
    "v",
    "w",
    "x",
    "z",
}

EMAIL_PATTERN = (
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@"
    r"[A-Za-z0-9-]+"
    r"(?:\.[A-Za-z0-9-]+)+$"
)

NAME_PATTERN = (
    r"[A-Za-zÀ-ÖØ-öø-ÿ'’-]+"
    r"(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ'’-]+)+"
)

SINGLE_NAME_PATTERN = (
    r"[A-Za-zÀ-ÖØ-öø-ÿ'’-]+"
    r"(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ'’-]+)*"
)


# ============================================================
# GROQ SYSTEM PROMPT
# ============================================================

RULE_EXAMPLE_SYSTEM_PROMPT = """
You are the BRAINOPX Rule Example Generator.

Your job is to generate ONE concrete example value
for ONE business rule.

The supplied rule is authoritative.

You MUST:

1. Read the complete rule.
2. Read the rule name.
3. Read the description.
4. Read the task.
5. Read the expected outcome.
6. Read every structured constraint.
7. Respect exact prefixes.
8. Respect exact suffixes.
9. Respect exact lengths.
10. Respect minimum and maximum lengths.
11. Respect uppercase requirements.
12. Respect lowercase requirements.
13. Respect numeric requirements.
14. Respect special-character requirements.
15. Respect allowed values.
16. Respect forbidden values.
17. Respect number ranges.
18. Respect date formats.
19. Respect email formats.
20. Respect phone formats.
21. Respect regex/pattern requirements.
22. Respect semantic requirements.
23. Do not invent constraints.
24. Do not change constraints.
25. Generate exactly ONE concrete value.

VERY IMPORTANT:

If the rule is:

"Notification type must be one of EMAIL, SMS, PUSH, SLACK, TEAMS"

then:

EMAIL

is valid.

Do NOT generate:

user@example.com

because that is an email address, not a notification type.

If the rule is:

"Email must be a valid email address"

then:

john.smith@example.com

is valid.

If the rule is:

"Unique Tariff Code must start with TRF and contain 3 digits"

then:

TRF123

is valid.

If the rule is:

"Unique Business Rule ID must start with BR and contain 4 digits"

then:

BR1234

is valid.

Return ONLY JSON:

{
  "rule_understood": true,
  "example": "ONE_CONCRETE_VALUE",
  "explanation": "Short explanation.",
  "constraints": [
    "constraint 1",
    "constraint 2"
  ]
}

Never return a generic placeholder.
Never return multiple examples.
"""


# ============================================================
# GROQ REQUEST
# ============================================================

# How many extra times _call_groq will wait out a 429 and retry
# before giving up and letting the caller's own retry loop
# (generate_rule_example_with_retry) take over. Kept small — this is
# a synchronous request, not a background job.
_RATE_LIMIT_RETRIES = 2

_RATE_LIMIT_WAIT_RE = re.compile(
    r"try again in\s*(?:([\d.]+)\s*m)?\s*([\d.]+)\s*s",
    re.IGNORECASE,
)

_DAILY_RATE_LIMIT_RE = re.compile(
    r"tokens per day|\bTPD\b",
    re.IGNORECASE,
)


def _is_daily_rate_limit(exc: Exception) -> bool:
    """
    Whether a RateLimitError is Groq's daily token cap (TPD) rather
    than the per-minute burst limit.

    A TPD block reports waits of several minutes — far past what the
    local retry loop's 20s cap can bridge, and it will not clear
    until Groq's day rolls over. Retrying it locally, or spending all
    of generate_rule_example_with_retry's attempts on it, only burns
    time for a result that was already decided by the first 429.
    """

    return bool(_DAILY_RATE_LIMIT_RE.search(str(exc)))


def _rate_limit_wait_seconds(
    exc: Exception,
    default: float = 5.0,
    cap: float = 20.0,
) -> float:
    """
    How long Groq itself says to wait before the next attempt.

    Prefers the Retry-After response header; falls back to the
    "Please try again in Xs" text Groq puts in the error message, and
    finally to `default` if neither is present.
    """

    response = getattr(exc, "response", None)

    if response is not None:
        header_value = (
            response.headers.get("retry-after")
            or response.headers.get("Retry-After")
        )

        if header_value:
            try:
                return min(cap, max(0.5, float(header_value)))
            except (TypeError, ValueError):
                pass

    match = _RATE_LIMIT_WAIT_RE.search(str(exc))

    if match:
        try:
            minutes = float(match.group(1)) if match.group(1) else 0.0
            seconds = float(match.group(2)) + minutes * 60
            return min(cap, max(0.5, seconds))
        except ValueError:
            pass

    return default


def _call_groq(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.0,
    max_tokens: int = 700,
    reasoning_effort: Optional[str] = "low",
) -> str:
    """
    Send a request to Groq.

    reasoning_effort defaults to "low": every prompt in this module
    asks for one short, concrete value or a small JSON object, not
    open-ended reasoning. At the "medium" server-side default,
    openai/gpt-oss-120b can spend the whole max_tokens budget on its
    hidden reasoning and return no visible content at all — the
    "Groq returned an empty response" failures this guards against.
    """

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]

    response = None

    # Groq's per-minute token budget is easy to exceed once a task has
    # more than a handful of rules, since each rule's example used to
    # be requested back-to-back with no pause. Rather than let a 429
    # fail the call immediately, wait the time Groq itself reports and
    # try again a couple of times before handing the error up to the
    # caller's own retry loop.
    for attempt in range(_RATE_LIMIT_RETRIES + 1):

        try:
            create_kwargs = {
                "model": GROQ_MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            # reasoning_effort is only supported by gpt-oss models on Groq;
            # other models (e.g. llama-3.1-8b-instant) reject the param.
            if "gpt-oss" in GROQ_MODEL:
                create_kwargs["reasoning_effort"] = reasoning_effort

            response = client.chat.completions.create(**create_kwargs)
            break

        except RateLimitError as exc:

            if attempt >= _RATE_LIMIT_RETRIES or _is_daily_rate_limit(exc):
                raise

            wait_seconds = _rate_limit_wait_seconds(exc)

            logger.warning(
                "Groq rate limit hit, waiting %.1fs before retry (%d/%d)",
                wait_seconds,
                attempt + 1,
                _RATE_LIMIT_RETRIES,
            )

            time.sleep(wait_seconds)

    if not response.choices:
        raise RuntimeError(
            "Groq returned no response choices."
        )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "Groq returned an empty response."
        )

    return content.strip()


# ============================================================
# JSON EXTRACTION
# ============================================================

def _extract_json(text: str) -> Optional[Any]:
    """
    Safely extract JSON from Groq output.
    """

    if not text:
        return None

    text = text.strip()

    # Direct JSON
    try:
        return json.loads(text)
    except Exception:
        pass

    # Remove markdown fences
    cleaned = re.sub(
        r"```(?:json)?",
        "",
        text,
        flags=re.IGNORECASE,
    )

    cleaned = cleaned.replace(
        "```",
        "",
    ).strip()

    # Clean JSON
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # JSON object
    object_start = cleaned.find("{")
    object_end = cleaned.rfind("}")

    if (
        object_start >= 0
        and object_end > object_start
    ):
        try:
            return json.loads(
                cleaned[
                    object_start : object_end + 1
                ]
            )
        except Exception:
            pass

    # JSON array
    array_start = cleaned.find("[")
    array_end = cleaned.rfind("]")

    if (
        array_start >= 0
        and array_end > array_start
    ):
        try:
            return json.loads(
                cleaned[
                    array_start : array_end + 1
                ]
            )
        except Exception:
            pass

    return None


# ============================================================
# NORMALIZATION
# ============================================================

def _normalize_example(value: Any) -> str:
    """
    Convert any AI output into a string.
    """

    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(
        value,
        (int, float, bool),
    ):
        return str(value)

    if isinstance(value, list):
        return ", ".join(
            str(item).strip()
            for item in value
            if item is not None
        )

    if isinstance(value, dict):

        for key in (
            "value",
            "example",
            "sample",
            "valid_value",
        ):
            if key in value:
                return _normalize_example(
                    value[key]
                )

        return json.dumps(
            value,
            ensure_ascii=False,
        )

    return str(value).strip()


def _normalize_constraints(
    constraints: Any,
) -> list[str]:
    """
    Normalize AI explanation constraints.
    """

    if constraints is None:
        return []

    if isinstance(
        constraints,
        str,
    ):
        value = constraints.strip()
        return [value] if value else []

    if isinstance(
        constraints,
        list,
    ):
        return [
            str(item).strip()
            for item in constraints
            if item is not None
            and str(item).strip()
        ]

    return [
        str(constraints).strip()
    ]


# ============================================================
# IMMUTABLE CONSTRAINTS
# ============================================================

def _get_immutable_constraints(
    rule: dict,
) -> dict:
    """
    Return a deep copy of database constraints.

    AI can never modify these.
    """

    if not isinstance(rule, dict):
        return {}

    constraints = rule.get(
        "constraints"
    )

    if isinstance(
        constraints,
        dict,
    ):
        return copy.deepcopy(
            constraints
        )

    return {}


# ============================================================
# BUILD COMPLETE RULE
# ============================================================

def _build_complete_rule_text(
    rule: dict,
) -> str:
    """
    Build the complete authoritative rule
    sent to Groq.
    """

    constraints = _get_immutable_constraints(
        rule
    )

    constraint_lines = []

    if constraints.get("required") is True:
        constraint_lines.append(
            "- A value is REQUIRED."
        )

    if constraints.get("prefix"):
        prefix = constraints["prefix"]
        digit_count = constraints.get(
            "prefix_digit_count"
        )
        if digit_count is not None:
            constraint_lines.append(
                f"- Value must start with '{prefix}' "
                f"followed by exactly {digit_count} digits."
            )
        else:
            constraint_lines.append(
                f"- Value must start with '{prefix}'."
            )

    if constraints.get("suffix"):
        constraint_lines.append(
            f"- Value must end with '{constraints['suffix']}'."
        )

    if constraints.get("exact_length") is not None:
        constraint_lines.append(
            f"- Value must contain EXACTLY "
            f"{constraints['exact_length']} characters."
        )

    if constraints.get("min_length") is not None:
        constraint_lines.append(
            f"- Value must contain AT LEAST "
            f"{constraints['min_length']} characters."
        )

    if constraints.get("max_length") is not None:
        constraint_lines.append(
            f"- Value must contain NO MORE THAN "
            f"{constraints['max_length']} characters."
        )

    if constraints.get("allowed_values"):
        values = constraints["allowed_values"]
        constraint_lines.append(
            "- Value must be ONE of: "
            + ", ".join(
                str(v) for v in values
            )
            + "."
        )

    if constraints.get("forbidden_values"):
        values = constraints["forbidden_values"]
        constraint_lines.append(
            "- Value must NOT be: "
            + ", ".join(
                str(v) for v in values
            )
            + "."
        )

    if constraints.get("format"):
        fmt = constraints["format"]
        constraint_lines.append(
            f"- Format must be: {fmt}"
        )

    if constraints.get("uppercase") is True:
        constraint_lines.append(
            "- Value must contain AT LEAST ONE uppercase letter."
        )

    if constraints.get("lowercase") is True:
        constraint_lines.append(
            "- Value must contain AT LEAST ONE lowercase letter."
        )

    if constraints.get("special_character") is True:
        constraint_lines.append(
            "- Value must contain AT LEAST ONE special character."
        )

    if constraints.get("number") is True:
        constraint_lines.append(
            "- Value must contain AT LEAST ONE number."
        )

    if constraints.get("no_number") is True:
        constraint_lines.append(
            "- Value must NOT contain numbers."
        )

    if constraints.get("min_value") is not None:
        constraint_lines.append(
            f"- Value must be AT LEAST {constraints['min_value']}."
        )

    if constraints.get("max_value") is not None:
        constraint_lines.append(
            f"- Value must be NO MORE THAN {constraints['max_value']}."
        )

    if constraints.get("domain"):
        constraint_lines.append(
            f"- Email domain must be: {constraints['domain']}"
        )

    if constraints.get("pattern") or constraints.get("regex"):
        pattern = constraints.get(
            "pattern"
        ) or constraints.get(
            "regex"
        )
        constraint_lines.append(
            f"- Value must match this pattern: {pattern}"
        )

    if constraint_lines:
        constraints_text = "\n".join(
            constraint_lines
        )
    else:
        constraints_text = (
            "- No explicit structured constraints found. "
            "Use the semantic meaning of the rule."
        )

    return f"""
OFFICIAL BRAINOPX RULE

RULE ID:
{rule.get("id", "")}

RULE NAME:
{rule.get("name", "")}

DESCRIPTION:
{rule.get("description", "")}

TASK:
{rule.get("task", "")}

EXPECTED OUTCOME:
{rule.get("expected_outcome", "")}

DATA TYPE:
{rule.get("data_type", "")}

KEYWORDS:
{json.dumps(
    rule.get("keywords", []),
    ensure_ascii=False,
)}

STRUCTURED CONSTRAINTS:
{json.dumps(
    constraints,
    ensure_ascii=False,
    indent=2,
)}

CRITICAL CONSTRAINTS (follow ALL of these):
{constraints_text}

IMPORTANT:

The structured constraints are authoritative.

The semantic meaning of the rule name,
description, task, and expected outcome must
also be respected.

Generate exactly ONE concrete value.
"""


# ============================================================
# SEMANTIC INFERENCE
# ============================================================

# Field names that state their own format. Keyed on the head noun —
# the trailing word or words of the field's name — so "Customer
# Email" and "Email" both resolve, while "Email Template" does not.
_NAME_SEMANTICS = {
    "email": "email",
    "e-mail": "email",
    "email address": "email",
    "mail address": "email",

    "phone": "phone",
    "telephone": "phone",
    "mobile": "phone",
    "phone number": "phone",
    "mobile number": "phone",
    "telephone number": "phone",
    "contact number": "phone",

    "time": "time",
    "start time": "time",
    "end time": "time",
    "run time": "time",
}


def _semantic_from_field_name(name: str) -> str:
    """
    Resolve a semantic type from what the field is called.

    Only the end of the name is considered: the head noun carries the
    field's meaning ("Customer Email" is an email), while a leading
    word does not ("Email Template" is not).
    """

    words = re.findall(
        r"[a-z0-9\-]+",
        str(name or "").lower(),
    )

    if not words:
        return ""

    # Longest trailing phrase first: "phone number" beats "number".
    for size in (3, 2, 1):

        if len(words) < size:
            continue

        phrase = " ".join(words[-size:])

        if phrase in _NAME_SEMANTICS:
            return _NAME_SEMANTICS[phrase]

    return ""


# The semantic types deterministic_validate_example actually checks.
# Anything else carries no validation meaning.
_KNOWN_SEMANTIC_TYPES = {
    "allowed_choice",
    "currency",
    "date", "datetime",
    "department",
    "email",
    "full_name", "fullname",
    "identifier",
    "integer", "int", "whole_number",
    "number", "numeric", "decimal", "float",
    "password",
    "phone",
    "role", "user_role", "job_role",
    "status",
    "time",
    "username",
}


def _infer_semantic_type(
    rule: dict,
    constraints: dict,
) -> str:
    """
    Determine the semantic type of a rule.

    This protects validation when the AI parser
    fails to populate data_type correctly.

    A declared type is honoured only when the validator has a check
    for it. The parser is told every rule must carry a data_type, so
    it routinely writes vague ones — "text", "string", "varchar". Those
    used to be returned as-is and matched no branch, which silently
    disabled EVERY check on the field: an Email step named Email,
    described as an email, accepted "leo". A label the validator does
    not understand is now treated as no information, and inference
    continues.
    """

    explicit_type = str(
        constraints.get(
            "data_type",
            rule.get(
                "data_type",
                "",
            ),
        )
        or ""
    ).strip().lower()

    if explicit_type in _KNOWN_SEMANTIC_TYPES:
        return explicit_type

    explicit_format = str(
        constraints.get(
            "format",
            rule.get(
                "format",
                "",
            ),
        )
        or ""
    ).strip().lower()

    if explicit_format in _KNOWN_SEMANTIC_TYPES:
        return explicit_format

    name = str(
        rule.get("name", "")
    ).lower()

    description = str(
        rule.get("description", "")
    ).lower()

    task = str(
        rule.get("task", "")
    ).lower()

    combined = " ".join(
        [
            name,
            description,
            task,
        ]
    )

    # --------------------------------------------------------
    # What the field is called
    #
    # A field named "Email" wants an email even when nothing says
    # "valid email address". Without this the example builder read
    # the name and offered user@example.com while validation, which
    # reads only constraints, accepted anything.
    #
    # Matched on the name alone, and only on its head noun, so a
    # description that happens to mention email elsewhere cannot
    # retype an unrelated field.
    # --------------------------------------------------------

    from_name = _semantic_from_field_name(name)

    if from_name:
        return from_name

    # --------------------------------------------------------
    # Username / alphanumeric code
    # --------------------------------------------------------

    if (
        "username" in combined
        or "user name" in combined
        or "login" in combined
        or "user id" in combined
    ):
        return "username"

    # --------------------------------------------------------
    # Notification type
    # --------------------------------------------------------

    if (
        "notification type" in combined
        or "type of notification" in combined
    ):
        return "allowed_choice"

    # --------------------------------------------------------
    # Currency
    # --------------------------------------------------------

    if (
        "currency" in combined
        and "rate" not in combined
    ):
        return "currency"

    # --------------------------------------------------------
    # Email
    # --------------------------------------------------------

    if (
        "email address" in combined
        or "valid email" in combined
        or "email format" in combined
    ):
        return "email"

    # --------------------------------------------------------
    # Phone
    # --------------------------------------------------------

    if (
        "phone number" in combined
        or "telephone number" in combined
        or "mobile number" in combined
    ):
        return "phone"

    # --------------------------------------------------------
    # Full name
    # --------------------------------------------------------

    if (
        "full name" in combined
        or "fullname" in combined
    ):
        return "full_name"

    # --------------------------------------------------------
    # Password
    # --------------------------------------------------------

    if (
        "password" in combined
        or "passcode" in combined
    ):
        return "password"

    # --------------------------------------------------------
    # Date
    # --------------------------------------------------------

    if (
        "date" in combined
        and "update" not in combined
    ):
        return "date"

    # --------------------------------------------------------
    # Integer / number
    # --------------------------------------------------------

    if (
        "integer" in combined
        or "whole number" in combined
    ):
        return "integer"

    if (
        "unit rate" in combined
        or "tax rate" in combined
        or "percentage" in combined
        or "numeric value" in combined
    ):
        return "number"

    # --------------------------------------------------------
    # Role
    # --------------------------------------------------------

    if (
        "valid role" in combined
        or "user role" in combined
        or name.strip() == "role"
    ):
        return "role"

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    if (
        "valid status" in combined
        or name.strip() == "status"
    ):
        return "status"

    # --------------------------------------------------------
    # Department
    # --------------------------------------------------------

    if (
        "department" in combined
    ):
        return "department"

    # --------------------------------------------------------
    # Generic ID / code
    # --------------------------------------------------------

    if (
        "unique" in combined
        and (
            "id" in combined
            or "code" in combined
        )
    ):
        return "identifier"

    # Nothing inferred. Hand back whatever the parser declared, even
    # though the validator has no check for it, so downstream callers
    # that only report the type still see it.
    return explicit_type or explicit_format or ""


# ============================================================
# INFER CONSTRAINTS FROM RULE TEXT
# ============================================================

def _infer_text_constraints(
    rule: dict,
) -> dict:
    """
    Extract obvious constraints from natural-language
    rule text.

    This is a safety layer.

    It does NOT replace structured constraints.
    It supplements them when the parser missed something.
    """

    constraints = {}

    name = str(
        rule.get("name", "")
    )

    description = str(
        rule.get("description", "")
    )

    task = str(
        rule.get("task", "")
    )

    expected = str(
        rule.get("expected_outcome", "")
    )

    text = " ".join(
        [
            name,
            description,
            task,
            expected,
        ]
    )

    lower = text.lower()

    # ========================================================
    # REQUIRED
    # ========================================================

    constraints["required"] = True

    # ========================================================
    # PREFIX
    # ========================================================

    prefix_patterns = [
        r"format\s+([A-Za-z]+)\s*\+\s*(\d+)\s*digits",
        r"start(?:s)?\s+with\s+([A-Za-z]+).*?(\d+)\s*digits",
        r"prefix\s*(?:is|:)?\s*([A-Za-z]+).*?(\d+)\s*digits",
        r"format\s+([A-Za-z]+)\s*(\d+)\s*digits",
        r"must\s+start\s+with\s+([A-Za-z]+)",
        r"begins?\s+with\s+([A-Za-z]+)",
    ]

    for pattern in prefix_patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:

            constraints["prefix"] = (
                match.group(1)
            )

            if len(match.groups()) > 1:

                try:

                    constraints[
                        "prefix_digit_count"
                    ] = int(
                        match.group(2)
                    )

                except ValueError:
                    pass

            break

    # ========================================================
    # SUFFIX
    # ========================================================

    suffix_match = re.search(
        r"(?:end(?:s)?\s+with|suffix\s*(?:is|:)?)\s*([A-Za-z]+)",
        text,
        flags=re.IGNORECASE,
    )

    if suffix_match:
        constraints["suffix"] = suffix_match.group(1)

    # ========================================================
    # MIN LENGTH
    # ========================================================

    match = re.search(
        r"(?:at least|min(?:imum)?|minimum of)[^\d]{0,20}"
        r"(\d+)\s*(?:characters|chars|letters|digits)",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        constraints["min_length"] = int(
            match.group(1)
        )

    # ========================================================
    # MAX LENGTH
    # ========================================================

    match = re.search(
        r"(?:at most|max(?:imum)?|no more than|maximum of"
        r"|(?:must |should |can )?(?:not|cannot|never) exceed"
        r"|up to)"
        r"[^\d]{0,20}"
        r"(\d+)\s*(?:characters|chars|letters|digits)",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        constraints["max_length"] = int(
            match.group(1)
        )

    # ========================================================
    # EXACT LENGTH
    # ========================================================

    match = re.search(
        r"(?:exactly|exact length|must be)\s+"
        r"(\d+)\s*(?:characters|chars|digits)",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        constraints["exact_length"] = int(
            match.group(1)
        )

    # ========================================================
    # RANGE LENGTH
    #
    #   "3-30 characters"
    #   "between 3 and 50 characters"
    # ========================================================

    range_match = re.search(
        r"(\d+)\s*-\s*(\d+)\s*(?:characters|chars|letters|digits)",
        text,
        flags=re.IGNORECASE,
    )

    if not range_match:
        range_match = re.search(
            r"between\s+(\d+)\s+and\s+(\d+)\s*"
            r"(?:characters|chars|letters|digits)",
            text,
            flags=re.IGNORECASE,
        )

    if range_match and "min_length" not in constraints and "max_length" not in constraints:

        try:

            constraints["min_length"] = int(
                range_match.group(1)
            )

            constraints["max_length"] = int(
                range_match.group(2)
            )

        except (
            TypeError,
            ValueError,
        ):
            pass

    # ========================================================
    # ALLOWED VALUES
    # ========================================================

    allowed_match = re.search(
        r"(?:one of|allowed values?|allowed types?|valid types?|"
        r"must be one of|valid values?|acceptable)"
        r"\s*:?\s*"
        r"(.+?)(?:\.|\n|$)",
        text,
        flags=re.IGNORECASE,
    )

    if allowed_match:

        raw_values = allowed_match.group(
            1
        )

        raw_values = re.sub(
            r"\band\b",
            ",",
            raw_values,
            flags=re.IGNORECASE,
        )

        if ":" in raw_values:
            raw_values = raw_values.split(":", 1)[1]

        values = [
            value.strip(
                " `\"'"
            )
            for value in raw_values.split(",")
        ]

        values = [
            value
            for value in values
            if value
            and len(value.split()) <= 4
            and not re.search(
                r"\b(the|a|an|of|for|in|on|with|and|or|to|from|by|is|are)\b",
                value,
                flags=re.IGNORECASE,
            )
        ]

        if values:
            constraints[
                "allowed_values"
            ] = values

    # ========================================================
    # EMAIL
    # ========================================================

    if (
        "valid email" in lower
        or "email address" in lower
        or "e-mail" in lower
    ):
        constraints["format"] = "email"

    # ========================================================
    # PHONE
    # ========================================================

    if (
        "phone number" in lower
        or "telephone number" in lower
        or "mobile number" in lower
    ):
        constraints["format"] = "phone"

    # ========================================================
    # FULL NAME
    # ========================================================

    if (
        "full name" in lower
        or "first name and a last name" in lower
        or "first and last name" in lower
    ):
        constraints["format"] = "full_name"

    # ========================================================
    # UPPERCASE
    # ========================================================

    if (
        "uppercase" in lower
        or "upper case" in lower
        or "all caps" in lower
    ):
        constraints["uppercase"] = True

    # ========================================================
    # LOWERCASE
    # ========================================================

    if (
        "lowercase" in lower
        or "lower case" in lower
    ):
        constraints["lowercase"] = True

    # ========================================================
    # SPECIAL CHARACTER
    # ========================================================

    if (
        "special character" in lower
        or "special characters" in lower
    ) and (
        "no special characters" not in lower
        and "not contain special characters" not in lower
        and "without special characters" not in lower
    ):
        constraints["special_character"] = True

    # ========================================================
    # NUMBER REQUIREMENT
    # ========================================================

    if (
        "must contain at least one number" in lower
        or "contain at least one digit" in lower
        or (
            "contain number" in lower
            and "no number" not in lower
            and "not contain number" not in lower
            and "without number" not in lower
        )
        or (
            "contain numbers" in lower
            and "no numbers" not in lower
            and "not contain numbers" not in lower
            and "without numbers" not in lower
        )
    ):
        constraints["number"] = True

    # ========================================================
    # POSITIVE / NON-NEGATIVE
    # ========================================================

    if (
        "positive" in lower
        or "greater than zero" in lower
    ):
        constraints["min_value"] = 0.000001

    if (
        "non-negative" in lower
        or "greater than or equal to zero" in lower
    ):
        constraints["min_value"] = 0

    # ========================================================
    # EMAIL DOMAIN
    # ========================================================

    domain_match = re.search(
        r"(?:domain|email domain)"
        r"\s*(?:is|:)?\s*"
        r"@?([A-Za-z0-9.-]+\.[A-Za-z]{2,})",
        text,
        flags=re.IGNORECASE,
    )

    if domain_match:
        constraints["domain"] = (
            domain_match.group(1)
        )

    # ========================================================
    # NAME-LIKE FIELDS SHOULD NOT CONTAIN NUMBERS
    # ========================================================

    name_like = (
        "step name" in lower
        or "operation name" in lower
        or "rule name" in lower
        or "task name" in lower
        or "business name" in lower
        or "valid step name" in lower
        or "valid operation name" in lower
        or "valid rule name" in lower
        or "workflow name" in lower
    ) and (
        "no special characters" in lower
        or "not contain special characters" in lower
        or "without special characters" in lower
        or "letters and spaces" in lower
        or "letters only" in lower
        or "alphabetic" in lower
    )

    if name_like:
        constraints["no_number"] = True

    # ========================================================
    # USERNAME / ALPHANUMERIC FIELDS
    # ========================================================

    alphanumeric = (
        "username" in lower
        or "user name" in lower
        or "login" in lower
        or "user id" in lower
    ) and (
        "only letters and numbers" in lower
        or "letters and numbers only" in lower
        or "alphanumeric" in lower
        or "only letters and digits" in lower
    )

    if alphanumeric:
        constraints["no_special_characters"] = True
        constraints["no_spaces"] = True

    # ========================================================
    # ORDER / NUMERIC FIELDS
    # ========================================================

    if (
        "step order" in lower
        or "operation order" in lower
        or "rule order" in lower
        or "task order" in lower
        or "sequence number" in lower
    ):
        constraints["format"] = "integer"
        constraints["min_value"] = 1

    # ========================================================
    # STATUS FIELDS
    # ========================================================

    if (
        "step status" in lower
        or "operation status" in lower
        or "rule status" in lower
        or "task status" in lower
        or "valid step status" in lower
    ):
        constraints["min_length"] = 2

    # ========================================================
    # DESCRIPTION FIELDS
    # ========================================================

    if (
        "step description" in lower
        or "operation description" in lower
        or "rule description" in lower
        or "task description" in lower
        or "optional step description" in lower
    ):
        constraints["min_length"] = 5

    # ========================================================
    # DATE REQUIREMENTS
    # ========================================================

    if (
        "date" in lower
        and (
            "valid date" in lower
            or "date format" in lower
            or "yyyy-mm-dd" in lower
            or "dd/mm/yyyy" in lower
            or "mm/dd/yyyy" in lower
        )
    ):
        constraints["format"] = "date"

    # ========================================================
    # URL / LINK
    # ========================================================

    if (
        "url" in lower
        or "website" in lower
        or "link" in lower
    ) and (
        "valid" in lower
        or "must be" in lower
    ):
        constraints["format"] = "url"

    # ========================================================
    # IP ADDRESS
    # ========================================================

    if "ip address" in lower or "ipv4" in lower:
        constraints["format"] = "ipv4"

    # ========================================================
    # PASSWORD REQUIREMENTS
    # ========================================================

    if "password" in lower:
        constraints["format"] = "password"

    # ========================================================
    # USERNAME
    # ========================================================

    if "username" in lower or "user name" in lower:
        constraints["format"] = "username"

    # ========================================================
    # CODE / SHORT TEXT
    # ========================================================

    if (
        "code" in lower
        and "postal" not in lower
        and "zip" not in lower
    ) or "short text" in lower:
        constraints["format"] = "code"

    # ========================================================
    # POSTAL / ZIP CODE
    # ========================================================

    if (
        "postal code" in lower
        or "zip code" in lower
    ):
        constraints["format"] = "postal_code"

    # ========================================================
    # MIN VALUE (numeric)
    # ========================================================

    min_value_match = re.search(
        r"(?:at least|min(?:imum)?|minimum of|greater than)\s+"
        r"(\d+(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )

    if min_value_match and "min_value" not in constraints:
        try:
            constraints["min_value"] = float(
                min_value_match.group(1)
            )
        except ValueError:
            pass

    # ========================================================
    # MAX VALUE (numeric)
    # ========================================================

    max_value_match = re.search(
        r"(?:at most|max(?:imum)?|no more than|maximum of|less than)\s+"
        r"(\d+(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )

    if max_value_match and "max_value" not in constraints:
        try:
            constraints["max_value"] = float(
                max_value_match.group(1)
            )
        except ValueError:
            pass

    # ========================================================
    # NUMERIC RANGE  "between 0 and 100"
    #
    # Only when no unit follows, so "between 3 and 50 characters"
    # stays a length rule.
    # ========================================================

    # The \b after each number stops the match backtracking to a
    # shorter number so the guard below no longer sees the unit:
    # without it "between 3 and 50 characters" matched "3" and "5",
    # leaving "0 characters" ahead, and a length rule became a
    # numeric range.
    numeric_range = re.search(
        r"between\s+(\d+(?:\.\d+)?)\b\s+and\s+(\d+(?:\.\d+)?)\b"
        r"(?!\s*(?:characters|chars|letters|digits))",
        text,
        flags=re.IGNORECASE,
    )

    if numeric_range:
        try:
            low = float(numeric_range.group(1))
            high = float(numeric_range.group(2))

            if low > high:
                low, high = high, low

            constraints.setdefault("min_value", low)
            constraints.setdefault("max_value", high)

        except ValueError:
            pass

    # A percentage is bounded even when the bounds are not spelled out.
    if re.search(r"\bpercentage\b|\bpercent\b|\bper\s?cent\b", text, re.I):
        constraints.setdefault("min_value", 0)
        constraints.setdefault("max_value", 100)

    # ========================================================
    # DECIMAL PLACES  "with 2 decimal places"
    # ========================================================

    decimals = re.search(
        r"(\d+)\s*decimal\s*(?:places?|digits?|points?)?",
        text,
        flags=re.IGNORECASE,
    )

    if decimals:
        try:
            constraints.setdefault(
                "decimal_places",
                max(0, int(decimals.group(1))),
            )
        except ValueError:
            pass

    # ========================================================
    # DATE FORMAT
    #
    # A rule that names a layout means it. Previously any parseable
    # date passed, so "15/01/2026" and "17-3-3432" both satisfied a
    # rule that asked for YYYY-MM-DD.
    # ========================================================

    date_format = re.search(
        r"\b(yyyy[/-]mm[/-]dd|dd[/-]mm[/-]yyyy|mm[/-]dd[/-]yyyy)\b",
        text,
        flags=re.IGNORECASE,
    )

    if date_format:
        constraints.setdefault(
            "date_format",
            date_format.group(1).upper(),
        )

    # ========================================================
    # DATE MUST BE FUTURE / PAST
    # ========================================================

    if re.search(
        r"\bin\s+the\s+future\b|\bfuture\s+date\b|\bafter\s+today\b"
        r"|\blater\s+than\s+today\b|\bnot\s+in\s+the\s+past\b",
        text,
        flags=re.IGNORECASE,
    ):
        constraints.setdefault("date_must_be", "future")

    elif re.search(
        r"\bin\s+the\s+past\b|\bpast\s+date\b|\bbefore\s+today\b"
        r"|\bnot\s+in\s+the\s+future\b",
        text,
        flags=re.IGNORECASE,
    ):
        constraints.setdefault("date_must_be", "past")

    # ========================================================
    # FORBIDDEN VALUES
    # ========================================================

    forbidden_match = re.search(
        r"(?:not allowed|forbidden|cannot be|must not be)\s*:?\s*"
        r"(.+?)(?:\.|\n|$)",
        text,
        flags=re.IGNORECASE,
    )

    if forbidden_match:

        raw_values = forbidden_match.group(1)

        raw_values = re.sub(
            r"\band\b",
            ",",
            raw_values,
            flags=re.IGNORECASE,
        )

        values = [
            value.strip(" `\"'")
            for value in raw_values.split(",")
        ]

        values = [
            value
            for value in values
            if value
            and len(value.split()) <= 4
        ]

        if values:
            constraints["forbidden_values"] = values

    # ========================================================
    # NARRATIVE CONTENT
    #
    # Some rules describe a section of a document — "Problem
    # Statement", "Scope of Work", "Terms and Conditions" — rather
    # than a formatted field. They yield no prefix, length or type
    # constraint, which previously left them with nothing to check
    # and nothing to build an example from.
    #
    # Marked here so the validator can require real content and the
    # example builder can offer a sentence instead of a code.
    # ========================================================

    if _looks_like_narrative(rule, constraints):
        constraints["content_type"] = "narrative"
        constraints.setdefault("min_words", 3)

    return constraints


# ============================================================
# NARRATIVE SECTION DETECTION
# ============================================================

# Words that name a section of prose rather than a value.
_NARRATIVE_WORDS = {
    "statement", "description", "summary", "overview", "scope",
    "terms", "conditions", "background", "objective", "objectives",
    "deliverable", "deliverables", "breakdown", "information",
    "details", "detail", "notes", "comments", "justification",
    "rationale", "benefits", "approach", "methodology", "introduction",
    "conclusion", "recommendation", "recommendations", "assumptions",
    "risks", "proposal", "solution", "requirements", "responsibilities",
    "narrative", "explanation", "purpose", "goals", "outcome",
    "outcomes", "steps", "timeline", "schedule", "milestones",
    "plan", "agreement", "warranty", "support",
}

# Constraints that mean the rule describes a formatted value, so it
# is not narrative however it is worded.
_FORMAT_KEYS = (
    "prefix", "suffix", "exact_length", "min_length", "max_length",
    "pattern", "regex", "allowed_values", "min_value", "max_value",
    "format", "domain", "prefix_digit_count",
)


def _looks_like_narrative(
    rule: dict,
    constraints: dict,
) -> bool:
    """
    Decide whether a rule asks for prose rather than a formatted value.

    Deliberately conservative: any format constraint, or any inferred
    semantic type, disqualifies the rule. Only rules that would
    otherwise have nothing to validate are treated as narrative.
    """

    if not isinstance(constraints, dict):
        return False

    for key in _FORMAT_KEYS:
        if constraints.get(key) not in (None, "", [], {}):
            return False

    try:
        if _infer_semantic_type(rule, constraints):
            return False
    except Exception:
        return False

    # Rules carry `name`; guided steps carry `rule_name`. Accept both,
    # so passing a step here cannot silently look like an unnamed rule.
    name = str(
        (rule or {}).get("name")
        or (rule or {}).get("rule_name")
        or ""
    ).lower()

    description = str(
        (rule or {}).get("description", "")
        or (rule or {}).get("rule_description", "")
        or (rule or {}).get("task", "")
        or ""
    ).lower()

    # A field the user picks a value for is not a section of prose,
    # however the rest of the rule is worded. "Select Operation Type"
    # was being asked for "a short paragraph".
    if re.match(
        r"\s*(select|choose|pick|set|enter|specify)\b",
        name,
    ):
        return False

    words = set(
        re.findall(r"[a-z]+", f"{name} {description}")
    )

    if words & _NARRATIVE_WORDS:
        return True

    # A rule that says to describe/explain/list something wants prose.
    return bool(
        re.search(
            r"\b(describe|explain|outline|summaris|summariz|list|"
            r"detail|provide an? (?:overview|account))",
            description,
        )
    )


# ============================================================
# MERGE RULE CONSTRAINTS
# ============================================================

def _get_effective_constraints(
    rule: dict,
) -> dict:
    """
    Merge:

        1. Explicit structured constraints
        2. Text-derived safety constraints

    Explicit structured constraints always win.
    """

    explicit = _get_immutable_constraints(
        rule
    )

    inferred = _infer_text_constraints(
        rule
    )

    effective = copy.deepcopy(
        inferred
    )

    effective.update(
        explicit
    )

    return effective


# ============================================================
# GENERATE ONE RULE EXAMPLE
# ============================================================

def generate_rule_example(
    rule: dict,
    previous_example: Optional[str] = None,
    validation_feedback: Optional[str] = None,
) -> dict:
    """
    Ask Groq for one concrete example.

    Groq does not validate the example.
    Python validates it afterwards.
    """

    effective_constraints = (
        _get_effective_constraints(
            rule
        )
    )

    complete_rule = (
        _build_complete_rule_text(
            {
                **rule,
                "constraints": effective_constraints,
            }
        )
    )

    retry_context = ""

    if previous_example:

        retry_context += f"""

PREVIOUS INVALID EXAMPLE:

{previous_example}

Do NOT reuse this value.
"""

    if validation_feedback:

        retry_context += f"""

DETERMINISTIC VALIDATION FEEDBACK:

{validation_feedback}

Generate a NEW value that fixes all
reported validation errors.
"""

    user_prompt = f"""
Generate ONE concrete example for the rule below.

{complete_rule}

{retry_context}

CRITICAL INSTRUCTIONS:

1. The example must match the SEMANTIC MEANING of the rule.
   - If the rule is about "Notification Type", do NOT return an email address.
   - If the rule is about "Tariff Code", do NOT return a tariff name.

2. The example must satisfy EVERY constraint listed below.
   Do NOT skip any constraint.

3. Return ONLY a single concrete value in the "example" field.
   Do NOT return descriptions, explanations as the example value.

4. Do NOT invent new constraints.
   Do NOT change existing constraints.

Return ONLY JSON:

{{
  "rule_understood": true,
  "example": "one concrete value",
  "explanation": "short explanation of why this value satisfies the rule",
  "constraints": [
    "constraint 1",
    "constraint 2"
  ]
}}
"""

    raw_response = _call_groq(
        system_prompt=RULE_EXAMPLE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.0,
        # Groq's own docs note 1024 (its server-side default) "may be
        # too low" once reasoning tokens are counted against the
        # budget — 500 was well under that and starved the model of
        # room to reach a final answer.
        max_tokens=1000,
    )

    parsed = _extract_json(
        raw_response
    )

    if not isinstance(
        parsed,
        dict,
    ):
        return {
            "success": False,
            "example": "",
            "explanation": "",
            "constraints": [],
            "raw_response": raw_response,
            "error": "invalid_json",
        }

    example = _normalize_example(
        parsed.get("example")
    )

    explanation = str(
        parsed.get("explanation")
        or ""
    ).strip()

    ai_constraints = (
        _normalize_constraints(
            parsed.get("constraints")
        )
    )

    if not example:
        return {
            "success": False,
            "example": "",
            "explanation": explanation,
            "constraints": effective_constraints,
            "raw_response": raw_response,
            "error": "empty_example",
        }

    return {
        "success": bool(
            parsed.get(
                "rule_understood",
                True,
            )
        ),
        "example": example,
        "explanation": explanation,
        "constraints": effective_constraints,
        "ai_constraints": ai_constraints,
        "raw_response": raw_response,
        "error": None,
    }


# ============================================================
# DETERMINISTIC VALIDATION
# ============================================================

def deterministic_validate_example(
    example: str,
    rule: dict,
) -> dict:
    """
    FINAL AUTHORITY.

    Validate the value without asking Groq.

    This function validates both:
        - generated examples
        - user input
    """

    if not isinstance(
        rule,
        dict,
    ):
        return {
            "valid": False,
            "reason": "Invalid rule definition.",
            "errors": [
                "Invalid rule definition."
            ],
        }

    # ========================================================
    # COMPOSITE ANSWERS
    #
    # A list or table step is validated cell by cell, each cell
    # coming back through this same function. Dispatching here keeps
    # this the single validation authority for every shape.
    # ========================================================

    from app.services import composite_rules

    if composite_rules.is_composite(rule):
        return composite_rules.validate_composite(
            str(example or ""),
            rule,
        )

    value = str(
        example or ""
    ).strip()

    errors = []

    rule_name = str(
        rule.get(
            "name",
            "Current rule",
        )
        or ""
    ).strip()

    rule_description = str(
        rule.get(
            "description",
            "",
        )
        or ""
    ).strip()

    rule_task = str(
        rule.get(
            "task",
            "",
        )
        or ""
    ).strip()

    rule_text = " ".join(
        [
            rule_name,
            rule_description,
            rule_task,
            str(
                rule.get(
                    "expected_outcome",
                    "",
                )
                or ""
            ),
        ]
    )

    lower_text = rule_text.lower()

    constraints = _get_effective_constraints(
        rule
    )

    # ========================================================
    # REQUIRED
    # ========================================================

    required = constraints.get(
        "required",
        True,
    )

    if required and not value:

        return {
            "valid": False,
            "reason": "A value is required.",
            "errors": [
                "A value is required."
            ],
        }

    if not value:

        return {
            "valid": True,
            "reason": "No value is required.",
            "errors": [],
        }

    # ========================================================
    # SEMANTIC TYPE
    # ========================================================

    semantic_type = _infer_semantic_type(
        rule,
        constraints,
    )

    # ========================================================
    # GENERIC PLACEHOLDERS
    # ========================================================

    if (
        value.lower()
        in GENERIC_PLACEHOLDERS
    ):
        errors.append(
            "Value cannot be a generic placeholder."
        )

    # ========================================================
    # GIBBERISH CHECK
    # ========================================================

    allowed_values = constraints.get(
        "allowed_values",
        [],
    )

    if isinstance(allowed_values, list):
        allowed_normalized = [
            str(v).strip().lower()
            for v in allowed_values
            if v is not None
            and str(v).strip()
        ]
    else:
        allowed_normalized = []

    # A value with stray punctuation mixed into its letters ("M,./MN")
    # can't be a plausible abbreviation — isalpha() is False for it —
    # so it's checked at any length. Clean alphanumeric codes with no
    # punctuation ("TRK4589") are still only checked when short, since
    # those are frequently legitimate longer identifiers.
    has_punctuation = bool(
        re.search(r"[^A-Za-z0-9\s]", value)
    )

    if (
        (len(value) <= 3 or has_punctuation)
        and value.upper() not in allowed_normalized
        and value.lower() not in allowed_normalized
    ):
        vowels = set("aeiou")
        consonants = set("bcdfghjklmnpqrstvwxyz")
        chars = set(value.lower())

        # A short run of consonants is usually an abbreviation the
        # user meant — SMS, CRM, VAT, SLA. Rejecting those as
        # gibberish is wrong; only flag values that are also not
        # plausible abbreviations.

        looks_like_abbreviation = (
            value.isalpha()
            and (
                value.isupper()
                or len(value) >= 2
            )
        )

        if (
            not chars & vowels
            and chars & consonants
            and not looks_like_abbreviation
        ):
            errors.append(
                "Value appears to be invalid. "
                "Please provide a meaningful value."
            )

    # ========================================================
    # FREE-TEXT CONTENT QUALITY
    #
    # A field with no recognised semantic type and no explicit
    # pattern/allowed_values relies entirely on the checks in this
    # function to catch nonsense — and none of the typed branches
    # below apply to it. Two cheap, safe checks close that gap:
    # a value must contain at least one letter or digit (not be
    # pure punctuation, like "/"), and if the document's own worked
    # example for this field contains letters, the submitted value
    # must contain letters too (an address whose example is "12 Rue
    # Bastos, Yaounde" cannot be validly answered with "09").
    # ========================================================

    has_structured_type = semantic_type in _KNOWN_SEMANTIC_TYPES
    has_pattern = bool(
        constraints.get("pattern")
    ) or bool(allowed_normalized)

    if not has_structured_type and not has_pattern:

        if not re.search(r"[0-9A-Za-z]", value):
            errors.append(
                "Value must contain actual content, "
                "not just punctuation."
            )
        else:
            reference_example = str(
                rule.get("example_input")
                or rule.get("example")
                or rule.get("suggested_fix")
                or ""
            ).strip()

            if (
                reference_example
                and re.search(r"[A-Za-z]", reference_example)
                and not re.search(r"[A-Za-z]", value)
            ):
                errors.append(
                    "Value must contain letters, "
                    "matching the expected format."
                )

    # ========================================================
    # NARRATIVE CONTENT
    #
    # A section of a document needs actual content. Without this a
    # one-word answer satisfied a rule asking for a full section.
    # ========================================================

    min_words = constraints.get("min_words")

    if min_words and value:

        try:
            required_words = int(min_words)
        except (TypeError, ValueError):
            required_words = 0

        word_count = len(
            [
                word
                for word in re.split(r"\s+", value.strip())
                if word
            ]
        )

        if word_count < required_words:
            errors.append(
                f"This needs to be written out in full — "
                f"at least {required_words} words. "
                f"You entered {word_count}."
            )

    # ========================================================
    # EXACT LENGTH
    # ========================================================

    exact_length = constraints.get(
        "exact_length"
    )

    if exact_length is not None:

        try:

            expected_length = int(
                exact_length
            )

            if len(value) != expected_length:
                errors.append(
                    f"Value must contain exactly "
                    f"{expected_length} characters."
                )

        except (
            TypeError,
            ValueError,
        ):
            errors.append(
                "Invalid exact_length rule."
            )

    # ========================================================
    # MIN LENGTH
    # ========================================================

    min_length = constraints.get(
        "min_length"
    )

    if min_length is not None:

        try:

            minimum = int(
                min_length
            )

            if len(value) < minimum:
                errors.append(
                    f"Value must contain at least "
                    f"{minimum} characters."
                )

        except (
            TypeError,
            ValueError,
        ):
            errors.append(
                "Invalid min_length rule."
            )

    # ========================================================
    # RANGE LENGTH  e.g. "3-30 characters"
    # ========================================================

    range_match = re.search(
        r"(\d+)\s*-\s*(\d+)\s*(?:characters|chars|letters)",
        rule_text,
        flags=re.IGNORECASE,
    )

    if range_match and min_length is None:

        try:

            minimum = int(
                range_match.group(1)
            )

            maximum = int(
                range_match.group(2)
            )

            if len(value) < minimum:
                errors.append(
                    f"Value must contain at least "
                    f"{minimum} characters."
                )

            if len(value) > maximum:
                errors.append(
                    f"Value must contain no more than "
                    f"{maximum} characters."
                )

        except (
            TypeError,
            ValueError,
        ):
            pass

    # ========================================================
    # MAX LENGTH
    # ========================================================

    max_length = constraints.get(
        "max_length"
    )

    if max_length is not None:

        try:

            maximum = int(
                max_length
            )

            if len(value) > maximum:
                errors.append(
                    f"Value must contain no more than "
                    f"{maximum} characters."
                )

        except (
            TypeError,
            ValueError,
        ):
            errors.append(
                "Invalid max_length rule."
            )

    # ========================================================
    # PREFIX
    # ========================================================

    prefix = constraints.get(
        "prefix"
    )

    if prefix:

        prefix = str(prefix)

        if not value.startswith(
            prefix
        ):
            errors.append(
                f"Value must start with '{prefix}'."
            )

    # ========================================================
    # PREFIX + DIGIT COUNT
    # ========================================================

    prefix_digit_count = constraints.get(
        "prefix_digit_count"
    )

    if (
        prefix
        and prefix_digit_count is not None
    ):

        try:

            count = int(
                prefix_digit_count
            )

            remainder = value[
                len(prefix):
            ]

            if not re.fullmatch(
                rf"\d{{{count}}}",
                remainder,
            ):
                errors.append(
                    f"Value must be '{prefix}' "
                    f"followed by exactly {count} digits."
                )

        except (
            TypeError,
            ValueError,
        ):
            errors.append(
                "Invalid prefix digit-count rule."
            )

    # ========================================================
    # SUFFIX
    # ========================================================

    suffix = constraints.get(
        "suffix"
    )

    if suffix:

        suffix = str(suffix)

        if not value.endswith(
            suffix
        ):
            errors.append(
                f"Value must end with '{suffix}'."
            )

    # ========================================================
    # UPPERCASE
    # ========================================================

    if constraints.get(
        "uppercase",
        False,
    ):

        if not re.search(
            r"[A-Z]",
            value,
        ):
            errors.append(
                "Value must contain at least one uppercase letter."
            )

    # ========================================================
    # LOWERCASE
    # ========================================================

    if constraints.get(
        "lowercase",
        False,
    ):

        if not re.search(
            r"[a-z]",
            value,
        ):
            errors.append(
                "Value must contain at least one lowercase letter."
            )

    # ========================================================
    # NUMBER
    # ========================================================

    requires_number = (
        constraints.get(
            "number",
            False,
        )
        or constraints.get(
            "numbers",
            False,
        )
    )

    if requires_number:

        if not re.search(
            r"\d",
            value,
        ):
            errors.append(
                "Value must contain at least one number."
            )

    # ========================================================
    # NO NUMBER
    # ========================================================

    if constraints.get(
        "no_number",
        False,
    ):

        if re.search(
            r"\d",
            value,
        ):
            errors.append(
                "Value must not contain numbers."
            )

    # ========================================================
    # SPECIAL CHARACTER
    # ========================================================

    requires_special = (
        constraints.get(
            "special_character",
            False,
        )
        or constraints.get(
            "special_characters",
            False,
        )
    )

    if requires_special:

        if not re.search(
            r"[^A-Za-z0-9\s]",
            value,
        ):
            errors.append(
                "Value must contain at least one special character."
            )

    # ========================================================
    # FULL NAME
    # ========================================================

    if semantic_type in (
        "full_name",
        "fullname",
    ) or "full name" in lower_text:

        if len(
            value.split()
        ) < 2:

            errors.append(
                "Full name must contain at least "
                "a first name and a last name."
            )

        if not re.fullmatch(
            NAME_PATTERN,
            value,
        ):

            errors.append(
                "Full name may contain letters, spaces, "
                "apostrophes, and hyphens only."
            )

    # ========================================================
    # USERNAME / ALPHANUMERIC
    # ========================================================

    if semantic_type == "username" or (
        "username" in lower_text
        or "user name" in lower_text
        or "login" in lower_text
    ):

        if re.search(
            r"\s",
            value,
        ):
            errors.append(
                "Username must not contain spaces."
            )

        if re.search(
            r"[^A-Za-z0-9]",
            value,
        ):
            errors.append(
                "Username must contain only "
                "letters and numbers."
            )

    # ========================================================
    # EMAIL
    # ========================================================

    if semantic_type == "email":

        if not re.fullmatch(
            EMAIL_PATTERN,
            value,
        ):
            errors.append(
                "Value must be a valid email address."
            )

    # ========================================================
    # PHONE
    # ========================================================

    if semantic_type == "phone":

        # Accept:
        # 690000001
        # +237690000001
        # +237-690-000-001

        digits = re.sub(
            r"[\s().-]",
            "",
            value,
        )

        if not re.fullmatch(
            r"\+?\d{9,15}",
            digits,
        ):

            errors.append(
                "Value must be a valid phone number."
            )

    # ========================================================
    # NEGATIVE CONSTRAINTS
    # ========================================================

    if (
        "no special characters" in lower_text
        or "not contain special characters" in lower_text
        or "without special characters" in lower_text
    ):
        if re.search(
            r"[^A-Za-z0-9\s]",
            value,
        ):
            errors.append(
                "Value must contain letters, spaces, "
                "apostrophes, and hyphens only."
            )

    if (
        "no numbers" in lower_text
        or "not contain numbers" in lower_text
        or "without numbers" in lower_text
    ):
        if re.search(
            r"\d",
            value,
        ):
            errors.append(
                "Value must not contain numbers."
            )

    # ========================================================
    # NO SPACES
    # ========================================================

    if (
        constraints.get("no_spaces")
        or "no spaces" in lower_text
        or "not contain spaces" in lower_text
        or "without spaces" in lower_text
    ):
        if re.search(
            r"\s",
            value,
        ):
            errors.append(
                "Value must not contain spaces."
            )

    # ========================================================
    # CURRENCY
    # ========================================================

    if semantic_type == "currency":

        common_currencies = {
            "USD",
            "EUR",
            "GBP",
            "XAF",
            "XOF",
            "NGN",
            "GHS",
            "CAD",
            "AUD",
            "JPY",
            "CNY",
            "CHF",
            "ZAR",
            "KES",
            "INR",
        }

        if value.upper() not in common_currencies:

            errors.append(
                "Value must be a valid currency code."
            )

    # ========================================================
    # ROLE
    # ========================================================

    if semantic_type in (
        "role",
        "user_role",
        "job_role",
    ):

        allowed = constraints.get(
            "allowed_values"
        )

        if allowed:

            allowed_normalized = [
                str(item).strip().lower()
                for item in allowed
            ]

            if (
                value.lower()
                not in allowed_normalized
            ):
                errors.append(
                    "Value must be one of: "
                    + ", ".join(
                        str(item)
                        for item in allowed
                    )
                    + "."
                )

        else:

            if not re.fullmatch(
                r"[A-Za-zÀ-ÖØ-öø-ÿ'’ -]+",
                value,
            ):
                errors.append(
                    "Role must contain letters and spaces only."
                )

            if len(value) < 2:
                errors.append(
                    "Role must contain at least 2 characters."
                )

    # ========================================================
    # STATUS
    # ========================================================

    if semantic_type == "status":

        allowed = constraints.get(
            "allowed_values"
        )

        if allowed:

            allowed_normalized = [
                str(item).strip().lower()
                for item in allowed
            ]

            if (
                value.lower()
                not in allowed_normalized
            ):
                errors.append(
                    "Value must be one of: "
                    + ", ".join(
                        str(item)
                        for item in allowed
                    )
                    + "."
                )

        else:

            if len(value) < 2:
                errors.append(
                    "Status must contain at least 2 characters."
                )

    # ========================================================
    # DEPARTMENT
    # ========================================================

    if semantic_type == "department":

        allowed = constraints.get(
            "allowed_values"
        )

        if allowed:

            allowed_normalized = [
                str(item).strip().lower()
                for item in allowed
            ]

            if (
                value.lower()
                not in allowed_normalized
            ):
                errors.append(
                    "Value must be one of: "
                    + ", ".join(
                        str(item)
                        for item in allowed
                    )
                    + "."
                )

        else:

            if not re.fullmatch(
                r"[A-Za-zÀ-ÖØ-öø-ÿ'’ -]+",
                value,
            ):
                errors.append(
                    "Department must contain letters and spaces only."
                )

            if len(value) < 2:
                errors.append(
                    "Department must contain at least 2 characters."
                )

    # ========================================================
    # PASSWORD
    # ========================================================

    if semantic_type == "password":

        if len(value) < 8:
            errors.append(
                "Password must contain at least 8 characters."
            )

        if not re.search(
            r"[A-Z]",
            value,
        ):
            errors.append(
                "Password must contain an uppercase letter."
            )

        if not re.search(
            r"[a-z]",
            value,
        ):
            errors.append(
                "Password must contain a lowercase letter."
            )

        if not re.search(
            r"\d",
            value,
        ):
            errors.append(
                "Password must contain a number."
            )

        if not re.search(
            r"[^A-Za-z0-9]",
            value,
        ):
            errors.append(
                "Password must contain a special character."
            )

    # ========================================================
    # INTEGER
    # ========================================================

    if semantic_type in (
        "integer",
        "int",
        "whole_number",
    ):

        if not re.fullmatch(
            r"-?\d+",
            value,
        ):
            errors.append(
                "Value must be a whole number."
            )

    # ========================================================
    # NUMBER
    # ========================================================

    if semantic_type in (
        "number",
        "numeric",
        "decimal",
        "float",
    ):

        try:
            float(value)

        except ValueError:
            errors.append(
                "Value must be a valid number."
            )

    # ========================================================
    # DECIMAL PLACES
    #
    # A rule asking for 2 decimal places was demonstrating "120.00"
    # while accepting "12".
    # ========================================================

    required_decimals = constraints.get("decimal_places")

    if required_decimals is not None and value:

        try:
            places = int(required_decimals)
        except (TypeError, ValueError):
            places = None

        if places is not None:

            match = re.fullmatch(
                r"[+-]?\d+(?:\.(\d*))?",
                value.strip(),
            )

            if match:

                actual = len(match.group(1) or "")

                if actual != places:
                    errors.append(
                        f"Value must have exactly {places} "
                        f"decimal place{'' if places == 1 else 's'} "
                        f"(you entered {actual})."
                    )

    # ========================================================
    # TIME OF DAY
    #
    # A step named "Start Time" demonstrated 09:30 while accepting
    # "21", because the field name reached the example builder but
    # never the validator.
    # ========================================================

    if semantic_type == "time":

        if not re.fullmatch(
            r"([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?",
            value,
        ):
            errors.append(
                "Value must be a time in HH:MM format, "
                "such as 09:30."
            )

    # ========================================================
    # DATE
    # ========================================================

    if semantic_type in (
        "date",
        "datetime",
    ):

        # A rule that names a layout means it. Accepting any parseable
        # date let "15/01/2026" and "17-3-3432" satisfy a rule that
        # asked for YYYY-MM-DD.

        _DATE_LAYOUTS = {
            "YYYY-MM-DD": "%Y-%m-%d",
            "YYYY/MM/DD": "%Y/%m/%d",
            "DD-MM-YYYY": "%d-%m-%Y",
            "DD/MM/YYYY": "%d/%m/%Y",
            "MM-DD-YYYY": "%m-%d-%Y",
            "MM/DD/YYYY": "%m/%d/%Y",
        }

        required_layout = str(
            constraints.get("date_format") or ""
        ).strip().upper()

        if required_layout in _DATE_LAYOUTS:
            formats = (_DATE_LAYOUTS[required_layout],)
        else:
            formats = tuple(_DATE_LAYOUTS.values())

        parsed_date = None

        for date_format in formats:

            try:

                parsed_date = datetime.strptime(
                    value,
                    date_format,
                )

                break

            except ValueError:
                continue

        if parsed_date is None:

            if required_layout in _DATE_LAYOUTS:
                errors.append(
                    f"Value must be a date in {required_layout} format."
                )
            else:
                errors.append(
                    "Value must be a valid date."
                )

        else:

            must_be = str(
                constraints.get("date_must_be") or ""
            ).strip().lower()

            today = datetime.now().date()

            if must_be == "future" and parsed_date.date() <= today:
                errors.append(
                    "Value must be a date in the future."
                )

            elif must_be == "past" and parsed_date.date() >= today:
                errors.append(
                    "Value must be a date in the past."
                )

    # ========================================================
    # ALLOWED VALUES
    # ========================================================

    allowed_values = constraints.get(
        "allowed_values"
    )

    if allowed_values is not None:

        if not isinstance(
            allowed_values,
            list,
        ):
            allowed_values = [
                allowed_values
            ]

        normalized_allowed = [
            str(item).strip().lower()
            for item in allowed_values
        ]

        if (
            value.lower()
            not in normalized_allowed
        ):

            errors.append(
                "Value must be one of: "
                + ", ".join(
                    str(item)
                    for item in allowed_values
                )
                + "."
            )

    # ========================================================
    # FORBIDDEN VALUES
    # ========================================================

    forbidden_values = constraints.get(
        "forbidden_values"
    )

    if forbidden_values:

        if not isinstance(
            forbidden_values,
            list,
        ):
            forbidden_values = [
                forbidden_values
            ]

        normalized_forbidden = [
            str(item).strip().lower()
            for item in forbidden_values
        ]

        if (
            value.lower()
            in normalized_forbidden
        ):
            errors.append(
                "This value is not allowed."
            )

    # ========================================================
    # DOMAIN
    # ========================================================

    domain = constraints.get(
        "domain"
    )

    if domain:

        if "@" not in value:

            errors.append(
                "Value must contain an email address."
            )

        else:

            actual_domain = (
                value
                .split("@", 1)[1]
                .lower()
            )

            expected_domain = (
                str(domain)
                .strip()
                .lower()
                .lstrip("@")
            )

            if actual_domain != expected_domain:

                errors.append(
                    f"Email must use the '{expected_domain}' domain."
                )

    # ========================================================
    # NUMBER RANGE
    # ========================================================

    min_value = constraints.get(
        "min_value"
    )

    max_value = constraints.get(
        "max_value"
    )

    if (
        min_value is not None
        or max_value is not None
    ):

        try:

            numeric_value = float(
                value
            )

            if (
                min_value is not None
                and numeric_value
                < float(min_value)
            ):

                errors.append(
                    f"Value must be at least {min_value}."
                )

            if (
                max_value is not None
                and numeric_value
                > float(max_value)
            ):

                errors.append(
                    f"Value must be no more than {max_value}."
                )

        except ValueError:

            errors.append(
                "Value must be a valid number."
            )

    # ========================================================
    # REGEX / PATTERN
    # ========================================================

    pattern = (
        constraints.get(
            "regex"
        )
        or constraints.get(
            "pattern"
        )
    )

    if pattern:

        try:

            if not re.fullmatch(
                str(pattern),
                value,
            ):
                errors.append(
                    "Value does not match the required format."
                )

        except re.error as exc:

            logger.warning(
                "Invalid regex in rule '%s': %s",
                rule_name,
                exc,
            )

            errors.append(
                "The rule contains an invalid regular expression."
            )

    # ========================================================
    # GENERIC IDENTIFIER
    # ========================================================

    if semantic_type == "identifier":

        if (
            "prefix" not in constraints
            and "prefix_digit_count"
            not in constraints
            and "regex" not in constraints
            and "pattern" not in constraints
        ):

            if len(value) < 2:

                errors.append(
                    "Identifier must contain at least 2 characters."
                )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    if errors:

        # Remove duplicates while preserving order
        unique_errors = list(
            dict.fromkeys(errors)
        )

        return {
            "valid": False,
            "reason": " ".join(
                unique_errors
            ),
            "errors": unique_errors,
        }

    return {
        "valid": True,
        "reason": (
            "Value satisfies all rule constraints."
        ),
        "errors": [],
    }


# ============================================================
# DETERMINISTIC FALLBACK
# ============================================================

def deterministic_fallback(
    rule: dict,
) -> str:
    """
    Generate a local example when Groq fails.
    """

    constraints = _get_effective_constraints(
        rule
    )

    semantic_type = _infer_semantic_type(
        rule,
        constraints,
    )

    # ========================================================
    # ALLOWED VALUES
    # ========================================================

    allowed = constraints.get(
        "allowed_values"
    )

    if allowed:

        for item in allowed:

            candidate = str(
                item
            ).strip()

            if deterministic_validate_example(
                candidate,
                rule,
            )["valid"]:

                return candidate

    # ========================================================
    # PREFIX + DIGITS
    # ========================================================

    prefix = constraints.get(
        "prefix"
    )

    digit_count = constraints.get(
        "prefix_digit_count"
    )

    if (
        prefix
        and digit_count
    ):

        candidate = (
            str(prefix)
            + (
                "0"
                * max(
                    int(digit_count) - 1,
                    0,
                )
            )
            + "1"
        )

        if deterministic_validate_example(
            candidate,
            rule,
        )["valid"]:

            return candidate

    # ========================================================
    # EMAIL
    # ========================================================

    if semantic_type == "email":

        candidate = "john.smith@example.com"

        if deterministic_validate_example(
            candidate,
            rule,
        )["valid"]:

            return candidate

    # ========================================================
    # PHONE
    # ========================================================

    if semantic_type == "phone":

        candidate = "+237690000001"

        if deterministic_validate_example(
            candidate,
            rule,
        )["valid"]:

            return candidate

    # ========================================================
    # FULL NAME
    # ========================================================

    if semantic_type == "full_name":

        candidate = "Leonel Christ"

        if deterministic_validate_example(
            candidate,
            rule,
        )["valid"]:

            return candidate

    # ========================================================
    # USERNAME
    # ========================================================

    if semantic_type == "username":

        candidate = "User01"

        if deterministic_validate_example(
            candidate,
            rule,
        )["valid"]:

            return candidate

    # ========================================================
    # PASSWORD
    # ========================================================

    if semantic_type == "password":

        candidate = "BrainOPX@2026"

        if deterministic_validate_example(
            candidate,
            rule,
        )["valid"]:

            return candidate

    # ========================================================
    # NUMBER
    # ========================================================

    if semantic_type in (
        "number",
        "numeric",
        "decimal",
        "float",
    ):

        candidate = "100"

        if deterministic_validate_example(
            candidate,
            rule,
        )["valid"]:

            return candidate

    # ========================================================
    # INTEGER
    # ========================================================

    if semantic_type in (
        "integer",
        "int",
        "whole_number",
    ):

        candidate = "100"

        if deterministic_validate_example(
            candidate,
            rule,
        )["valid"]:

            return candidate

    # ========================================================
    # DATE
    # ========================================================

    if semantic_type in (
        "date",
        "datetime",
    ):

        candidate = "2026-01-15"

        if deterministic_validate_example(
            candidate,
            rule,
        )["valid"]:

            return candidate

    # ========================================================
    # GENERIC TEXT
    # ========================================================

    candidates = [
        "Finance",
        "Active",
        "Administrator",
        "Leonel Christ",
        "Standard",
    ]

    for candidate in candidates:

        if deterministic_validate_example(
            candidate,
            rule,
        )["valid"]:

            return candidate

    return ""


# ============================================================
# GENERATE VALID EXAMPLE WITH RETRY
# ============================================================

def generate_rule_example_with_retry(
    rule: dict,
    max_retries: Optional[int] = None,
) -> dict:
    """
    Generate an example and validate it.

    Groq:
        generate

    Python:
        validate

    If invalid:
        ask Groq again.

    If all attempts fail:
        deterministic fallback.
    """

    retries = (
        max_retries
        if max_retries is not None
        else MAX_RETRIES
    )

    retries = max(
        1,
        int(retries),
    )

    previous_example = None
    validation_feedback = None

    attempts = []
    daily_quota_exceeded = False

    for attempt in range(
        1,
        retries + 1,
    ):

        try:

            generated = generate_rule_example(
                rule=rule,
                previous_example=previous_example,
                validation_feedback=validation_feedback,
            )

        except Exception as exc:

            logger.exception(
                "Groq generation failed for rule '%s'",
                rule.get(
                    "name",
                    "",
                ),
            )

            attempts.append({
                "attempt": attempt,
                "source": "groq",
                "valid": False,
                "example": "",
                "reason": str(exc),
            })

            # A daily quota block will still be in effect on the next
            # attempt too — spending the rest of `retries` on it just
            # repeats the same failure and logs the same traceback
            # again for every remaining rule in the caller's batch.
            if isinstance(exc, RateLimitError) and _is_daily_rate_limit(exc):
                daily_quota_exceeded = True
                break

            validation_feedback = str(
                exc
            )

            continue

        example = _normalize_example(
            generated.get(
                "example"
            )
        )

        if not example:

            reason = (
                generated.get(
                    "error"
                )
                or "Groq returned no example."
            )

            attempts.append({
                "attempt": attempt,
                "source": "groq",
                "valid": False,
                "example": "",
                "reason": reason,
            })

            validation_feedback = reason

            continue

        validation = (
            deterministic_validate_example(
                example=example,
                rule=rule,
            )
        )

        attempts.append({
            "attempt": attempt,
            "source": "groq",
            "valid": validation[
                "valid"
            ],
            "example": example,
            "reason": validation[
                "reason"
            ],
        })

        if validation["valid"]:

            return {
                "success": True,
                "valid": True,
                "source": "groq",
                "example": example,
                "explanation": generated.get(
                    "explanation",
                    "",
                ),
                "constraints": generated.get(
                    "constraints",
                    {},
                ),
                "validation": validation,
                "validation_reason": validation[
                    "reason"
                ],
                "attempt": attempt,
                "attempts": attempts,
                "fallback_used": False,
            }

        previous_example = example

        validation_feedback = (
            "The generated example failed "
            "deterministic validation.\n"
            "Validation errors:\n"
            + "\n".join(
                f"- {error}"
                for error in validation.get(
                    "errors",
                    [],
                )
            )
        )

    # ========================================================
    # ALL ATTEMPTS FAILED
    #
    # No silent local substitute. A caller that asked for an AI
    # example is told plainly that Groq could not produce a validated
    # one after `retries` attempts, rather than silently receiving a
    # locally pattern-matched value with no way to tell the two apart.
    # deterministic_fallback() still exists for callers that
    # explicitly want a non-AI value, but it is no longer invoked
    # automatically here.
    # ========================================================

    return {
        "success": False,
        "valid": False,
        "source": "ai_unavailable",
        "example": "",
        "explanation": (
            f"Groq's daily token quota is exhausted; giving up after "
            f"{len(attempts)} attempt(s)."
            if daily_quota_exceeded
            else (
                f"Groq could not generate a value satisfying this rule "
                f"after {len(attempts)} attempt(s)."
            )
        ),
        "constraints": _get_effective_constraints(
            rule
        ),
        "validation": None,
        "validation_reason": (
            "Groq's daily token quota is exhausted."
            if daily_quota_exceeded
            else (
                "The AI service is currently unavailable, or could not "
                "produce a value satisfying this rule."
            )
        ),
        "attempt": len(attempts),
        "attempts": attempts,
        "daily_quota_exceeded": daily_quota_exceeded,
        "fallback_used": False,
    }


# ============================================================
# RUN ONE RULE WORKFLOW
# ============================================================

def run_rule_workflow(
    rule: dict,
    user_input: str,
    conversation_history: Optional[
        list[dict]
    ] = None,
    known_example: Optional[str] = None,
) -> dict:
    """
    Process one rule.

    CRITICAL:

    A failed user input remains on the SAME rule.

    The caller/router must only advance when:

        result["passed"] is True

    known_example:

        An example already generated and persisted for this rule.

        When supplied, it is validated deterministically and reused
        instead of asking Groq for a new one. Callers that already
        hold a step's example should always pass it — otherwise every
        submitted value costs up to MAX_RETRIES Groq round-trips to
        rebuild an example the caller already has.
    """

    conversation_history = (
        conversation_history or []
    )

    if not isinstance(
        rule,
        dict,
    ):

        return {
            "status": "failed",
            "passed": False,
            "validated": False,
            "example": "",
            "user_input": str(
                user_input or ""
            ).strip(),
            "validation": {
                "valid": False,
                "reason": "Invalid rule definition.",
                "errors": [
                    "Invalid rule definition."
                ],
            },
        }

    # ========================================================
    # IMMUTABLE RULE
    # ========================================================

    effective_rule = copy.deepcopy(
        rule
    )

    effective_rule[
        "constraints"
    ] = _get_effective_constraints(
        rule
    )

    # ========================================================
    # REUSE OR GENERATE A VALID EXAMPLE
    # ========================================================

    reused_example = _normalize_example(
        known_example
    )

    if reused_example:

        # No Groq call: the caller already holds an example for
        # this rule. It is still validated below.

        example_result = {
            "example": reused_example,
            "attempt": 0,
            "attempts": [],
            "fallback_used": False,
            "source": "caller",
        }

        example = reused_example

    else:

        example_result = (
            generate_rule_example_with_retry(
                rule=effective_rule,
                max_retries=MAX_RETRIES,
            )
        )

        example = _normalize_example(
            example_result.get(
                "example"
            )
        )

    # ========================================================
    # VALIDATE GENERATED EXAMPLE
    # ========================================================

    if example:

        example_validation = (
            deterministic_validate_example(
                example=example,
                rule=effective_rule,
            )
        )

    else:

        example_validation = {
            "valid": False,
            "reason": (
                "No valid example could be generated."
            ),
            "errors": [
                "No valid example could be generated."
            ],
        }

    example_valid = bool(
        example_validation.get(
            "valid",
            False,
        )
    )

    # ========================================================
    # USER INPUT
    # ========================================================

    clean_input = str(
        user_input or ""
    ).strip()

    if not clean_input:

        user_validation = {
            "valid": False,
            "reason": "Please provide a value.",
            "errors": [
                "Please provide a value."
            ],
        }

        passed = False

    else:

        user_validation = (
            deterministic_validate_example(
                example=clean_input,
                rule=effective_rule,
            )
        )

        passed = bool(
            user_validation.get(
                "valid",
                False,
            )
        )

    # ========================================================
    # RESPONSE
    # ========================================================

    rule_name = str(
        rule.get(
            "name",
            "Current rule",
        )
    ).strip()

    if passed:

        guidance = (
            "Rule completed successfully."
        )

        next_action = (
            "Proceed to the next rule."
        )

    else:

        errors = user_validation.get(
            "errors",
            [],
        )

        # The rule's description is NOT restated here. Callers render
        # this text to the user, and the rule behind a step stays
        # hidden — only what is wrong with the value is reported.

        if errors:

            guidance = (
                "The value was not accepted for "
                + rule_name
                + ".\n"
                + "What is missing: "
                + " ".join(errors)
            )

        else:

            guidance = (
                "The value was not accepted for "
                + rule_name
                + "."
            )

        if example_valid:

            guidance += (
                "\nExample of a valid value: `"
                + example
                + "`"
            )

        next_action = (
            "Please provide another value for "
            + rule_name
            + "."
        )

    return {
        "rule_id": rule.get(
            "id"
        ),

        "rule_name": rule_name,

        "status": (
            "passed"
            if passed
            else "failed"
        ),

        "passed": passed,

        "validated": passed,

        "user_input": clean_input,

        "validation": user_validation,

        "validation_reason": (
            user_validation.get(
                "reason",
                "",
            )
        ),

        "validation_errors": (
            user_validation.get(
                "errors",
                [],
            )
        ),

        # AI-generated example,
        # but ONLY if deterministic validation passed.
        "example": (
            example
            if example_valid
            else ""
        ),

        "suggested_fix": (
            example
            if example_valid
            else ""
        ),

        "example_valid": example_valid,

        "example_validation": (
            example_validation
        ),

        "guidance": guidance,

        "constraints": (
            _get_effective_constraints(
                rule
            )
        ),

        "summary": (
            f"'{rule_name}' passed."
            if passed
            else f"'{rule_name}' requires correction."
        ),

        "questions": [
            f"Please provide your value for {rule_name}."
        ],

        "next_action": next_action,

        "attempt": example_result.get(
            "attempt",
            1,
        ),

        "attempts": example_result.get(
            "attempts",
            [],
        ),

        "fallback_used": example_result.get(
            "fallback_used",
            False,
        ),
    }


# ============================================================
# RULE FOLLOW-UP
# ============================================================

def run_rule_followup(
    rule: dict,
    user_message: str,
    conversation_history: Optional[
        list[dict]
    ] = None,
    previous_verdict: Optional[
        dict
    ] = None,
) -> str:
    """
    Rule-aware conversational explanation.

    This does NOT decide validation.
    """

    conversation_history = (
        conversation_history or []
    )

    complete_rule = (
        _build_complete_rule_text(
            {
                **rule,
                "constraints": (
                    _get_effective_constraints(
                        rule
                    )
                ),
            }
        )
    )

    previous_context = ""

    if previous_verdict:

        previous_context = f"""

PREVIOUS VALIDATION RESULT:

Status:
{previous_verdict.get("status", "")}

Validation:
{json.dumps(
    previous_verdict.get(
        "validation",
        {},
    ),
    ensure_ascii=False,
)}

Example:
{previous_verdict.get(
    "example",
    "",
)}
"""

    system_prompt = f"""
You are the BRAINOPX Rule Assistant.

The user is completing ONE business rule.

COMPLETE RULE:

{complete_rule}

{previous_context}

IMPORTANT:

1. Discuss ONLY this rule.
2. Do not invent requirements.
3. Do not modify requirements.
4. Do not change allowed values.
5. Do not confuse the semantic meaning of the rule.
6. Ask one question at a time.
7. If giving an example, use one concrete example.
8. Never decide validation yourself.
9. Python deterministic validation is authoritative.
"""

    conversation_parts = []

    for msg in conversation_history[-10:]:

        role = (
            "ASSISTANT"
            if msg.get(
                "sender"
            ) == "ai"
            else "USER"
        )

        content = str(
            msg.get(
                "text",
                "",
            )
        ).strip()

        if content:

            conversation_parts.append(
                f"{role}: {content}"
            )

    conversation_parts.append(
        "USER: "
        + str(
            user_message
        )
    )

    return _call_groq(
        system_prompt=system_prompt,
        user_prompt="\n\n".join(
            conversation_parts
        ),
        temperature=0.2,
        max_tokens=700,
    )


# ============================================================
# RULE-AWARE RESPONSE
# ============================================================

def get_rule_aware_response(
    task_name: str,
    user_message: str,
    conversation_history: Optional[
        list[dict]
    ] = None,
    rules_content: str = "",
    parsed_rules: Optional[
        list[dict]
    ] = None,
    validation_errors: Optional[
        list[dict]
    ] = None,
    current_rule: Optional[
        dict
    ] = None,
    previous_verdict: Optional[
        dict
    ] = None,
) -> str:

    conversation_history = (
        conversation_history or []
    )

    parsed_rules = (
        parsed_rules or []
    )

    validation_errors = (
        validation_errors or []
    )

    if current_rule:

        try:

            return run_rule_followup(
                rule=current_rule,
                user_message=user_message,
                conversation_history=(
                    conversation_history
                ),
                previous_verdict=(
                    previous_verdict
                ),
            )

        except Exception:

            logger.exception(
                "Rule-aware response failed."
            )

    return get_ai_response(
        task_name=task_name,
        validation_errors=validation_errors,
        conversation_history=(
            conversation_history
        ),
        user_message=user_message,
        rules_content=rules_content,
        parsed_rules=parsed_rules,
        mode="validation",
    )


# ============================================================
# RULE PARSER
# ============================================================

RULES_PARSER_PROMPT = """
You are the BRAINOPX Business Rules Parser.

Convert business rules into structured JSON.

Return ONLY a JSON array.

Each rule MUST have:

{
  "id": 1,
  "name": "Unique Rule ID",
  "description": "Each business rule must have a unique ID in the format BR + 4 digits.",
  "task": "Please provide your value for Unique Rule ID.",
  "data_type": "identifier",
  "keywords": [
    "rule",
    "id",
    "business rule"
  ],
  "expected_outcome": "A valid unique rule ID is entered.",
  "constraints": {
    "required": true,
    "prefix": "BR",
    "prefix_digit_count": 4
  }
}

CRITICAL:

Extract EVERY constraint from the actual source text.

Do NOT invent constraints.

Do NOT use "email" as a format merely because
the word "valid" appears.

Do NOT convert semantic choices into unrelated formats.

For example:

"Notification type must be one of:
EMAIL, SMS, PUSH, SLACK, TEAMS"

MUST become:

"data_type": "allowed_choice"

and:

"allowed_values": [
  "EMAIL",
  "SMS",
  "PUSH",
  "SLACK",
  "TEAMS"
]

It must NOT become:

"data_type": "email"

Extract ALL of the following constraint types
when they appear in the source text:

- required / optional
- prefixes (e.g. "must start with EMP")
- suffixes (e.g. "must end with .pdf")
- exact lengths (e.g. "exactly 10 characters")
- minimum lengths (e.g. "at least 5 characters")
- maximum lengths (e.g. "no more than 50 characters")
- length ranges (e.g. "3-30 characters")
- allowed values (e.g. "must be one of A, B, C")
- forbidden values (e.g. "must not be X or Y")
- numeric ranges (e.g. "between 1 and 100")
- minimum values (e.g. "greater than 0")
- maximum values (e.g. "no more than 500")
- date formats (e.g. "YYYY-MM-DD")
- email requirements (e.g. "valid email address")
- phone requirements (e.g. "valid phone number")
- regex / pattern requirements (e.g. "must match ^[A-Z]{3}\\d{3}$")
- uppercase requirements (e.g. "must be uppercase")
- lowercase requirements (e.g. "must be lowercase")
- special character requirements
- number requirements (e.g. "must contain at least one number")
- no-number requirements (e.g. "letters and spaces only")
- domain requirements (e.g. "must use @company.com")
- format requirements (e.g. "must be a valid date", "must be an integer")

Preserve exact values, exact counts, and exact formats.

If a constraint is ambiguous, include it in the constraints
object with the most specific representation possible.

SQL CONSTRAINTS

Some documents state rules as SQL — a CREATE TABLE with typed
columns, CHECK(...) expressions, ALTER TABLE ... ADD CONSTRAINT,
or a bare CHECK(...) line. Read these exactly like prose rules:
one rule per column, using the same constraints object.

Map SQL onto the constraint types above like this:

- NOT NULL                          -> "required": true
- PRIMARY KEY                       -> "required": true
- VARCHAR(n) / CHAR(n) / NVARCHAR(n) -> "max_length": n
  (CHAR/NCHAR with no variable length -> "exact_length": n)
- INT / INTEGER / SMALLINT / BIGINT -> "format": "integer"
- DECIMAL / NUMERIC / FLOAT / REAL  -> "format": "number"
- DATE / DATETIME / TIMESTAMP       -> "format": "date"
- CHECK (col IN ('A','B','C'))      -> "data_type": "allowed_choice",
                                        "allowed_values": ["A","B","C"]
- CHECK (col NOT IN (...))          -> "forbidden_values": [...]
- CHECK (col LIKE 'ABC%')           -> "prefix": "ABC"
- CHECK (col LIKE '%XYZ')           -> "suffix": "XYZ"
- CHECK (col BETWEEN a AND b)       -> "min_value": a, "max_value": b
- CHECK (col >= n) / (col > n)      -> "min_value"
- CHECK (col <= n) / (col < n)      -> "max_value"
- CHECK (LEN(col) BETWEEN a AND b)  -> "min_length": a, "max_length": b

A column's rule "name" is the column name in human words (e.g.
tariff_code -> "Tariff Code"), and its description states the
constraint in plain language, e.g. "Must start with TRF and be at
most 10 characters." Extract every column of a CREATE TABLE as its
own rule, not just the ones that look unusual.

INPUT SHAPE

Most rules ask for ONE value. Some ask for more.

Add "input_shape" to every rule, using exactly one of:

  "scalar"     one value                      (the default)
  "list"       several values of the same kind
  "table"      rows made of named columns
  "narrative"  a paragraph of prose

Use "table" when the rule describes rows, columns, or says
something like "one row per item" or "for each X provide
A, B and C".

A table rule MUST also have "columns" and "min_rows":

{
  "id": 5,
  "name": "Tariff Lines",
  "description": "Provide one row per tariff with the tariff
                  code, unit rate and currency.",
  "input_shape": "table",
  "min_rows": 1,
  "columns": [
    {
      "name": "Tariff Code",
      "description": "Must start with TRF followed by 3 digits.",
      "constraints": {
        "required": true,
        "prefix": "TRF",
        "prefix_digit_count": 3
      }
    },
    {
      "name": "Unit Rate",
      "description": "A positive number with 2 decimal places.",
      "constraints": {
        "required": true,
        "format": "number",
        "min_value": 0
      }
    },
    {
      "name": "Currency",
      "description": "Must be USD or XAF.",
      "constraints": {
        "required": true,
        "allowed_values": ["USD", "XAF"]
      }
    }
  ]
}

Every column is itself a rule: give each one its own
description and its own constraints, extracted from the source
text using all the constraint types listed above.

Use "list" when the rule asks for several values of the SAME
kind. A list rule MUST also have "min_items" and "item_rule",
where "item_rule" holds the constraints one entry must meet:

{
  "id": 6,
  "name": "Authorised Approvers",
  "description": "List the employee ID of every approver.",
  "input_shape": "list",
  "min_items": 1,
  "item_rule": {
    "name": "Employee ID",
    "constraints": {
      "required": true,
      "prefix": "EMP",
      "prefix_digit_count": 4
    }
  }
}

Use "narrative" for sections of a document that call for
prose — a problem statement, scope of work, terms and
conditions. Do NOT invent format constraints for these.

Use "scalar" for everything else.

Return ONLY JSON.
"""


def _normalize_parsed_rule(rule: dict, index: int) -> dict:
    """
    Shared normalization for one rule dict, whichever source produced
    it — the LLM's JSON array, or the deterministic SQL constraint
    parser. Both must end up in exactly the same shape so they can be
    matched and merged on equal footing.
    """

    constraints = rule.get(
        "constraints",
        {},
    )

    if not isinstance(
        constraints,
        dict,
    ):
        constraints = {}

    keywords = rule.get(
        "keywords",
        [],
    )

    if not isinstance(
        keywords,
        list,
    ):
        keywords = [
            keywords
        ]

    normalized_rule = {
        "id": rule.get(
            "id",
            index,
        ),

        "name": str(
            rule.get(
                "name",
                f"Rule {index}",
            )
        ).strip(),

        "description": str(
            rule.get(
                "description",
                "",
            )
        ).strip(),

        "task": str(
            rule.get(
                "task",
                rule.get(
                    "description",
                    "",
                ),
            )
        ).strip(),

        "data_type": str(
            rule.get(
                "data_type",
                "",
            )
        ).strip(),

        "keywords": [
            str(k).strip()
            for k in keywords
            if str(k).strip()
        ][:20],

        "expected_outcome": str(
            rule.get(
                "expected_outcome",
                "",
            )
        ).strip(),

        "constraints": copy.deepcopy(
            constraints
        ),
    }

    # ----------------------------------------------------
    # Input shape.
    #
    # A step can ask for one value, a list, a table of named
    # columns, or a paragraph. Carried through here so the
    # example builder and the validator both see it — dropping
    # it would flatten a table into a single field.
    # ----------------------------------------------------

    shape = str(
        rule.get("input_shape", "")
    ).strip().lower()

    if shape in ("scalar", "list", "table", "narrative"):
        normalized_rule["input_shape"] = shape

    columns = rule.get("columns")

    if isinstance(columns, list) and columns:
        normalized_rule["columns"] = copy.deepcopy(columns)
        normalized_rule.setdefault("input_shape", "table")

    item_rule = rule.get("item_rule")

    if isinstance(item_rule, dict) and item_rule:
        normalized_rule["item_rule"] = copy.deepcopy(item_rule)
        normalized_rule.setdefault("input_shape", "list")

    for count_key in ("min_rows", "min_items"):

        if rule.get(count_key) is not None:

            try:
                normalized_rule[count_key] = max(
                    0,
                    int(rule[count_key]),
                )
            except (TypeError, ValueError):
                pass

    # ----------------------------------------------------
    # Add inferred constraints as safety metadata.
    # Explicit parser constraints remain authoritative.
    # ----------------------------------------------------

    inferred = _infer_text_constraints(
        normalized_rule
    )

    merged = copy.deepcopy(
        inferred
    )

    merged.update(
        normalized_rule[
            "constraints"
        ]
    )

    # ----------------------------------------------------
    # allowed_values is a special case: an LLM-parsed enum list
    # can silently drop an item (a known LLM failure mode on long
    # lists). The regex-derived list only ever adds values that
    # literally appear in the source text, so union it in here,
    # once, before the constraints are frozen as immutable -
    # instead of letting the parser's list clobber it outright.
    # ----------------------------------------------------

    explicit_allowed = normalized_rule["constraints"].get(
        "allowed_values"
    )
    inferred_allowed = inferred.get("allowed_values")

    if isinstance(explicit_allowed, list) and isinstance(inferred_allowed, list):

        seen = {
            str(item).strip().lower()
            for item in explicit_allowed
        }

        combined = list(explicit_allowed)

        for item in inferred_allowed:
            key = str(item).strip().lower()
            if key and key not in seen:
                seen.add(key)
                combined.append(item)

        merged["allowed_values"] = combined

    normalized_rule[
        "constraints"
    ] = merged

    return normalized_rule


def _rule_merge_key(name: str) -> str:
    """A rule name collapsed to bare letters/digits, so "Tariff Code"
    and a SQL column "tariff_code" are recognised as the same rule."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _merge_keys(rule: dict) -> list[str]:
    """
    Every key a rule or column can be matched under.

    Matching on the display name alone misses a composite table whose
    column is named differently from the SQL parser's humanized
    column name (e.g. a column the model calls "Item Ref" for a SQL
    `order_item_id`). The SQL parser always lists the raw column
    identifier as a keyword, so matching on keywords too closes that
    gap without needing semantic understanding of the rename.
    """
    keys = [_rule_merge_key(rule.get("name", ""))]

    for keyword in rule.get("keywords") or []:
        key = _rule_merge_key(keyword)
        if key and key not in keys:
            keys.append(key)

    return [key for key in keys if key]


def _merge_sql_rules(
    normalized: list[dict],
    sql_rules: list[dict],
) -> list[dict]:
    """
    Fold the deterministic SQL parser's rules into the model's rules.

    A SQL-derived rule can already be covered two ways:
      - the same rule under another name/spelling ("Tariff Code" vs
        SQL column "tariff_code") — its constraints merge onto the
        existing rule;
      - already one column of a composite table rule the model
        produced (e.g. "Order Item Id" inside "Order Items".columns)
        — its constraints merge onto that column instead of creating
        a duplicate top-level step asking for the same value twice.

    Anything left over genuinely is a new rule and is appended.
    """

    if not sql_rules:
        return normalized

    by_key = {}

    for existing in normalized:
        for key in _merge_keys(existing):
            by_key.setdefault(key, existing)

    covered_columns = {}

    for existing in normalized:

        for column in existing.get("columns") or []:

            if not isinstance(column, dict):
                continue

            for key in _merge_keys(column):
                covered_columns.setdefault(key, column)

    next_id = 1 + max(
        [r["id"] for r in normalized if isinstance(r["id"], int)] or [0]
    )

    for offset, sql_rule in enumerate(sql_rules):

        normalized_sql_rule = _normalize_parsed_rule(
            sql_rule, len(normalized) + offset + 1
        )

        keys = _merge_keys(normalized_sql_rule)

        existing = next(
            (by_key[key] for key in keys if key in by_key),
            None,
        )

        if existing:
            existing["constraints"] = {
                **existing["constraints"],
                **normalized_sql_rule["constraints"],
            }
            continue

        covered_column = next(
            (covered_columns[key] for key in keys if key in covered_columns),
            None,
        )

        if covered_column is not None:
            if not isinstance(covered_column.get("constraints"), dict):
                covered_column["constraints"] = {}

            covered_column["constraints"] = {
                **covered_column["constraints"],
                **normalized_sql_rule["constraints"],
            }
            continue

        normalized_sql_rule["id"] = next_id
        next_id += 1
        normalized.append(normalized_sql_rule)

        for key in keys:
            by_key.setdefault(key, normalized_sql_rule)

    return normalized


# ============================================================
# FREE-TEXT FIELD CLASSIFICATION
#
# A field carrying a generic SQL/text type (an ordinary VARCHAR with
# no CHECK, or an LLM-guessed "text"/"string") resolves to no semantic
# type at all, so deterministic_validate_example has nothing but its
# baseline punctuation/example-derived check to validate it with. That
# baseline is enough to catch obvious garbage but nothing document-
# specific. Rather than hardcode field names ("address", "state", ...)
# — which only ever covers fields already seen — one batched call per
# document asks the model to read each unresolved field's own wording
# and, only where it is confident, emit constraints from the same
# vocabulary deterministic_validate_example already knows how to check
# (min_length, max_length, pattern). No new validation branch is ever
# needed for a field type this has not seen before.
# ============================================================

_FREE_TEXT_CLASSIFIER_PROMPT = """
You classify fields from a business rules document that carry no
usable validation constraint today, so an assistant collecting values
for them currently accepts almost anything typed into them.

For each field given (its name, its description/task, and a worked
example if one exists), decide whether the field's OWN wording implies
a minimum length or a strict format. Do not invent a constraint the
text does not support — a missing constraint is safe, a wrong one
rejects a legitimate answer.

Return a JSON array, one object per field, in the SAME ORDER as given:

    {
        "name": "<field name, unchanged>",
        "min_length": <integer, or null>,
        "max_length": <integer, or null>,
        "pattern": <a regex the value must fully match, or null>
    }

Rules:
- Leave every key null unless the field's own text clearly supports it.
- "pattern" is only for a genuinely fixed structure the text states
  (a stated ID prefix, a stated code format) — never for ordinary free
  text like an address, a name, a city, or a comment field.
- Output the JSON array only. No prose, no markdown fences.
"""


def _unresolved_free_text_targets(
    normalized: list[dict],
) -> list[tuple[dict, str]]:
    """
    Fields with no recognised semantic type and no constraint that
    already limits content. Both a standalone rule and each column of
    a composite table rule are considered — a table column earns no
    less scrutiny than a standalone field asking for the same thing.
    """

    targets: list[tuple[dict, str]] = []

    def _consider(field, example_hint):

        if not isinstance(field, dict):
            return

        constraints = _get_effective_constraints(field)
        semantic_type = _infer_semantic_type(field, constraints)

        if semantic_type in _KNOWN_SEMANTIC_TYPES:
            return

        already_constrained = any(
            constraints.get(key)
            for key in (
                "min_length", "max_length", "exact_length",
                "pattern", "regex", "allowed_values",
                "prefix", "suffix", "min_words",
            )
        )

        if already_constrained:
            return

        targets.append((field, example_hint))

    for rule in normalized:

        columns = rule.get("columns")

        if isinstance(columns, list) and columns:
            for column in columns:
                _consider(column, "")
            continue

        item_rule = rule.get("item_rule")

        if isinstance(item_rule, dict) and item_rule:
            _consider(item_rule, "")
            continue

        _consider(
            rule,
            str(
                rule.get("example_input")
                or rule.get("example")
                or ""
            ),
        )

    return targets


def _classify_unresolved_free_text_fields(
    normalized: list[dict],
) -> list[dict]:
    """
    Ask the model, once per document, for constraints on every field
    left with no semantic type and no explicit constraint. Never
    overrides a constraint the document already gave; skips entirely,
    with the rules unchanged, on any parsing or model failure.
    """

    targets = _unresolved_free_text_targets(normalized)

    if not targets:
        return normalized

    # Bounded so one document with hundreds of loose text columns
    # cannot blow up the prompt or the bill. The unclassified rest
    # still get the baseline check in deterministic_validate_example.
    targets = targets[:30]

    fields_payload = [
        {
            "name": field.get("name", ""),
            "description": (
                field.get("description")
                or field.get("task")
                or ""
            ),
            "example": example_hint,
        }
        for field, example_hint in targets
    ]

    try:
        raw = _call_groq(
            system_prompt=_FREE_TEXT_CLASSIFIER_PROMPT,
            user_prompt=json.dumps(fields_payload, ensure_ascii=False),
            temperature=0.0,
            max_tokens=2000,
        )

        classified = _extract_json(raw)

    except Exception:
        logger.exception("Free-text field classification failed.")
        return normalized

    if not isinstance(classified, list):
        return normalized

    by_name = {
        _rule_merge_key(item.get("name", "")): item
        for item in classified
        if isinstance(item, dict)
    }

    for field, _hint in targets:

        result = by_name.get(
            _rule_merge_key(field.get("name", ""))
        )

        if not isinstance(result, dict):
            continue

        addition = {}

        min_length = result.get("min_length")

        if isinstance(min_length, int) and 0 < min_length <= 500:
            addition["min_length"] = min_length

        max_length = result.get("max_length")

        if isinstance(max_length, int) and 0 < max_length <= 2000:
            addition["max_length"] = max_length

        pattern = result.get("pattern")

        if isinstance(pattern, str) and pattern.strip():

            try:
                re.compile(pattern)
                addition["pattern"] = pattern.strip()
            except re.error:
                pass

        if not addition:
            continue

        if not isinstance(field.get("constraints"), dict):
            field["constraints"] = {}

        # Explicit, document-derived constraints always win over a
        # classified guess — same precedence SQL constraints already
        # have over everything else in this file.
        field["constraints"] = {
            **addition,
            **field["constraints"],
        }

    return normalized


# ============================================================
# RAW-TEXT ALLOWED-VALUES SAFETY NET
#
# The LLM parser can paraphrase a rule's own description and, in
# doing so, silently drop the literal enum it was given ("Allowed
# types: RUN, SCHEDULE, BACKUP, CLEANUP, SYNC" becomes "must be a
# valid operation type"). The field then carries no allowed_values
# constraint, and deterministic_validate_example has nothing to
# reject an out-of-list value with — any short string passes.
#
# This reads the enum straight off the raw "RULE N: <name>" block it
# came from, which can't lose text the model chose not to keep. Only
# documents using that heading convention are covered; anything else
# yields no matches and changes nothing.
# ============================================================

_RULE_HEADING = re.compile(
    r"(?im)^[ \t]*RULE\s+\d+\s*:\s*(.+?)\s*$"
)

_ALLOWED_VALUES_LINE = re.compile(
    r"(?im)^[ \t]*[-*]?\s*(?:"
    r"(?:allowed|valid)\s+(?:values?|types?)\s*:?\s*|"
    r"must\s+be\s+one\s+of\s*:?\s*|"
    r"must\s+be\s*:\s*"
    r")(.+?)\s*$"
)


def _raw_rule_blocks(rules_text: str) -> list[tuple[str, str]]:
    """Split a "RULE N: <name>" document into (name, block_text) pairs."""

    headings = list(_RULE_HEADING.finditer(rules_text or ""))

    blocks = []

    for index, heading in enumerate(headings):

        name = heading.group(1).strip()

        start = heading.end()

        end = (
            headings[index + 1].start()
            if index + 1 < len(headings)
            else len(rules_text)
        )

        blocks.append((name, rules_text[start:end]))

    return blocks


def _extract_raw_allowed_values(
    rules_text: str,
) -> dict[str, list[str]]:
    """Enum lists read directly off each raw rule block, keyed by
    the rule's merge key (see _rule_merge_key)."""

    result: dict[str, list[str]] = {}

    for name, block in _raw_rule_blocks(rules_text):

        match = _ALLOWED_VALUES_LINE.search(block)

        if not match:
            continue

        raw_values = re.sub(
            r"\band\b", ",", match.group(1), flags=re.IGNORECASE
        )

        values = [
            value.strip(" `\"'.")
            for value in raw_values.split(",")
        ]

        values = [
            value
            for value in values
            if value
            and len(value.split()) <= 4
            and not re.search(
                r"\b(the|a|an|of|for|in|on|with|and|or|to|from|by|"
                r"is|are|only|empty)\b",
                value,
                flags=re.IGNORECASE,
            )
        ]

        # A real enum lists at least two options — one bare value is
        # far more likely a stray "must be: <something else>" match
        # than a genuine allowed-values list.
        if len(values) < 2:
            continue

        key = _rule_merge_key(name)

        if key:
            result[key] = values

    return result


def _merge_raw_allowed_values(
    normalized: list[dict],
    raw_allowed_values: dict[str, list[str]],
) -> None:
    """
    Fold enum lists read straight off the raw document onto the rules
    (and table columns/list items) they belong to, by name. Mutates
    `normalized` in place.

    Same union behaviour as the LLM-vs-regex merge in
    _normalize_parsed_rule: never replaces values the parser already
    kept, only adds ones the raw text has that it doesn't.
    """

    def _apply(field: dict) -> None:

        for key in _merge_keys(field):

            values = raw_allowed_values.get(key)

            if not values:
                continue

            constraints = field.get("constraints")

            if not isinstance(constraints, dict):
                constraints = {}
                field["constraints"] = constraints

            existing = constraints.get("allowed_values")

            if isinstance(existing, list) and existing:

                seen = {
                    str(item).strip().lower()
                    for item in existing
                }

                combined = list(existing)

                for item in values:
                    normalized_item = str(item).strip().lower()
                    if normalized_item and normalized_item not in seen:
                        seen.add(normalized_item)
                        combined.append(item)

                constraints["allowed_values"] = combined

            else:
                constraints["allowed_values"] = list(values)

            return

    for rule in normalized:

        columns = rule.get("columns")

        if isinstance(columns, list) and columns:
            for column in columns:
                if isinstance(column, dict):
                    _apply(column)
            continue

        item_rule = rule.get("item_rule")

        if isinstance(item_rule, dict) and item_rule:
            _apply(item_rule)
            continue

        _apply(rule)


def parse_rules_to_json(
    rules_text: str,
) -> list[dict]:
    """
    Parse business rules into normalized rules.

    Two sources feed this, on equal footing: the Groq model (handles
    prose, and — per RULES_PARSER_PROMPT — SQL too), and a
    deterministic SQL constraint parser that reads the same raw text
    directly. The model can misread a CHECK expression or drop a
    column silently; the deterministic pass is the safety net for
    that, the same role _infer_text_constraints already plays for
    natural-language rules. Where both name the same column, the SQL
    parser's constraints win, since they were read off the actual
    constraint rather than guessed at.
    """

    if not rules_text or not rules_text.strip():
        return []

    parsed = []

    try:

        raw = _call_groq(
            system_prompt=RULES_PARSER_PROMPT,
            user_prompt=(
                "BUSINESS RULES DOCUMENT:\n\n"
                + rules_text[:45000]
            ),
            temperature=0.0,
            max_tokens=5000,
        )

        parsed = _extract_json(
            raw
        )

        if not isinstance(
            parsed,
            list,
        ):
            raise ValueError(
                "Expected a JSON array."
            )

    except Exception as exc:

        logger.exception(
            "Rule parsing failed: %s",
            exc,
        )

        parsed = []

    normalized = [
        _normalize_parsed_rule(rule, index)
        for index, rule in enumerate(parsed, start=1)
        if isinstance(rule, dict)
    ]

    try:
        sql_rules = extract_rules_from_sql(rules_text)
    except Exception:
        logger.exception("SQL constraint parsing failed.")
        sql_rules = []

    normalized = _merge_sql_rules(normalized, sql_rules)

    try:
        raw_allowed_values = _extract_raw_allowed_values(rules_text)
    except Exception:
        logger.exception("Raw allowed-values extraction failed.")
        raw_allowed_values = {}

    if raw_allowed_values:
        _merge_raw_allowed_values(normalized, raw_allowed_values)

    normalized = _classify_unresolved_free_text_fields(normalized)

    return normalized


# ============================================================
# GENERAL AI RESPONSE
# ============================================================

def get_ai_response(
    task_name: str,
    validation_errors: list[dict],
    conversation_history: list[dict],
    user_message: str,
    rules_content: str = "",
    parsed_rules: Optional[
        list[dict]
    ] = None,
    mode: str = "validation",
) -> str:
    """
    General BRAINOPX assistant.
    """

    context = f"""
TASK:
{task_name}

MODE:
{mode}

USER MESSAGE:
{user_message}
"""

    if rules_content:

        context += f"""

OFFICIAL RULES:
{rules_content[:12000]}
"""

    if parsed_rules:

        context += """

STRUCTURED RULES:
"""

        for rule in parsed_rules[:30]:

            context += f"""

Rule {rule.get("id")}:
Name: {rule.get("name")}
Description: {rule.get("description")}
Task: {rule.get("task")}
Data Type: {rule.get("data_type")}
Constraints:
{json.dumps(
    rule.get("constraints", {}),
    ensure_ascii=False,
    indent=2,
)}
"""

    if validation_errors:

        context += """

VALIDATION ERRORS:
"""

        for error in validation_errors[:20]:

            context += (
                "- "
                + str(
                    error.get(
                        "rule_violated",
                        error,
                    )
                )
                + "\n"
            )

    conversation_parts = []

    for msg in conversation_history[-10:]:

        role = (
            "ASSISTANT"
            if msg.get(
                "sender"
            ) == "ai"
            else "USER"
        )

        content = str(
            msg.get(
                "text",
                "",
            )
        ).strip()

        if content:

            conversation_parts.append(
                f"{role}: {content}"
            )

    if conversation_parts:

        context += (
            "\n\nRECENT CONVERSATION:\n"
            + "\n".join(
                conversation_parts
            )
        )

    system_prompt = """
You are the BRAINOPX Configuration Assistant.

Help the user understand and resolve business
configuration requirements.

Use ONLY supplied rules.

Do not invent requirements.

Do not generate SQL.

Do not decide validation.

Python deterministic validation is authoritative.

Be concise and actionable.

Ask one question at a time.
"""

    return _call_groq(
        system_prompt=system_prompt,
        user_prompt=context,
        temperature=0.2,
        max_tokens=700,
    )


# ============================================================
# SIDEBAR AI ASSISTANT (general chatbot)
# ============================================================

ASSISTANT_SYSTEM_PROMPT = """
You are the BRAINOPX Assistant, a chatbot embedded in the BRAINOPX
business-configuration platform.

What BRAINOPX is:
- Admins define "tasks": an Excel/CSV template, expected columns, and a set
  of column rules extracted from an uploaded rules document, mapped to a
  target SQL table.
- Users submit "configuration requests" against a task, uploading data and
  being guided step by step through validating it against that task's rules
  before a script is generated to load it into the target table.
- Requests move through statuses such as draft, in-progress, script
  generated and processing completed.

What you can do:
- Hold a normal conversation and answer questions about how BRAINOPX works.
- When information about a specific task is supplied below (its rules,
  description, target table, and its requests' status counts), you may
  analyze, summarize, review, extract details from, or produce a report
  on that task.
- When one or more documents are attached below (under ATTACHED DOCUMENTS),
  you may read, summarize, analyze, compare, or answer questions about
  their content. Only use what the document text actually says.

Formatting:
- When producing a structured summary or report, organize it with
  '#'/'##' markdown-style headings and bulleted ('- ') or numbered
  ('1. ') lists rather than one long paragraph, so it renders clearly
  and can be exported to PDF/Word cleanly.

Rules:
- Use ONLY the information supplied to you in this conversation. Never
  invent task names, rules, numbers, or system behavior that were not
  given to you.
- If asked about a task and no task context was supplied, say so and ask
  the user to select a task, rather than guessing.
- Do not generate SQL and do not decide whether a user's data is valid —
  deterministic validation elsewhere in BRAINOPX is authoritative for that.
- Be concise, clear, and helpful.

Staying on topic:
- Greetings, small talk, and pleasantries (hello, hi, good morning/
  afternoon/evening, how are you, thanks, thank you, you're welcome, bye)
  are always in scope. Reply to them briefly and naturally like a normal
  conversation, and you may invite the user to ask about BRAINOPX, but do
  not use the redirect message below for these.
- If the user's message is NOT a greeting/small talk and is unrelated to
  BRAINOPX, its tasks, requests, rules, or the task/document context
  supplied above (e.g. general knowledge questions, unrelated topics,
  requests to do something outside this platform), do not attempt to
  answer it. Reply with exactly this and nothing else:
  "I'm sorry, I don't have an answer for that. Would you like to talk
  about something else related to BRAINOPX?"
- Always steer the conversation back toward BRAINOPX: tasks, configuration
  requests, rules, or the supplied task/document context.
"""


def get_assistant_chat_response(
    user_message: str,
    conversation_history: list[dict],
    task_context: Optional[str] = None,
    extra_context: Optional[str] = None,
) -> str:
    """
    General-purpose conversational reply for the sidebar AI assistant.

    Unlike get_ai_response (the task-creation/validation guide),
    conversation_history here is [{"role": "user"|"assistant", "content": str}]
    and there is no notion of validation errors or a wizard mode.

    extra_context carries text extracted from files the user attached to
    this message (see assistant_attachments) — kept as its own labeled
    section rather than folded into task_context, so document content
    isn't mislabeled as task metadata.
    """

    context = ""

    if task_context:
        context += f"TASK CONTEXT:\n{task_context}\n\n"

    if extra_context:
        context += f"{extra_context}\n\n"

    conversation_parts = []

    for msg in conversation_history[-10:]:
        role = msg.get("role")
        content = str(msg.get("content", "")).strip()
        if content and role in ("user", "assistant"):
            conversation_parts.append(f"{role.upper()}: {content}")

    if conversation_parts:
        context += "RECENT CONVERSATION:\n" + "\n".join(conversation_parts) + "\n\n"

    context += f"USER MESSAGE:\n{user_message}"

    return _call_groq(
        system_prompt=ASSISTANT_SYSTEM_PROMPT,
        user_prompt=context,
        temperature=0.4,
        max_tokens=1400,
        reasoning_effort="medium",
    )


# ============================================================
# RULE ROUTER
# ============================================================

def route_message_to_rule(
    user_message: str,
    rules: list[dict],
    conversation_history: Optional[
        list[dict]
    ] = None,
) -> dict:
    """
    Determine which rule a message relates to.
    """

    conversation_history = (
        conversation_history or []
    )

    if not user_message.strip():

        return {
            "success": False,
            "rule_id": None,
            "rule_index": None,
            "rule_name": "",
            "confidence": 0.0,
            "reason": "Empty message.",
        }

    if not rules:

        return {
            "success": False,
            "rule_id": None,
            "rule_index": None,
            "rule_name": "",
            "confidence": 0.0,
            "reason": "No rules available.",
        }

    message = (
        user_message
        .strip()
        .lower()
    )

    best_rule = None
    best_index = None
    best_score = 0

    for index, rule in enumerate(
        rules
    ):

        if not isinstance(
            rule,
            dict,
        ):
            continue

        score = 0

        name = str(
            rule.get(
                "name",
                "",
            )
        ).lower()

        description = str(
            rule.get(
                "description",
                "",
            )
        ).lower()

        keywords = rule.get(
            "keywords",
            [],
        ) or []

        # Exact name
        if name and name in message:
            score += 20

        # Name words
        for word in re.findall(
            r"[a-zA-Z0-9]+",
            name,
        ):

            if (
                len(word) > 2
                and word in message
            ):
                score += 4

        # Keywords
        for keyword in keywords:

            keyword = str(
                keyword
            ).strip().lower()

            if (
                keyword
                and keyword in message
            ):
                score += 6

        # Description words
        for word in set(
            re.findall(
                r"[a-zA-Z0-9]+",
                description,
            )
        ):

            if (
                len(word) > 4
                and word in message
            ):
                score += 1

        if score > best_score:

            best_score = score
            best_rule = rule
            best_index = index

    if (
        best_rule is not None
        and best_score >= 5
    ):

        return {
            "success": True,
            "rule_id": best_rule.get(
                "id",
                best_index + 1,
            ),
            "rule_index": best_index,
            "rule_name": str(
                best_rule.get(
                    "name",
                    f"Rule {best_index + 1}",
                )
            ),
            "confidence": min(
                1.0,
                best_score / 20.0,
            ),
            "reason": (
                "Rule selected using "
                "deterministic matching."
            ),
        }

    # ========================================================
    # GROQ FALLBACK
    # ========================================================

    rules_for_ai = []

    for index, rule in enumerate(
        rules
    ):

        rules_for_ai.append({
            "index": index,
            "id": rule.get(
                "id",
                index + 1,
            ),
            "name": rule.get(
                "name",
                "",
            ),
            "description": rule.get(
                "description",
                "",
            ),
            "task": rule.get(
                "task",
                "",
            ),
            "keywords": rule.get(
                "keywords",
                [],
            ),
        })

    routing_prompt = f"""
OFFICIAL RULES:

{json.dumps(
    rules_for_ai,
    ensure_ascii=False,
    indent=2,
)}

USER MESSAGE:

{user_message}

Select the ONE rule that this message refers to.

Return ONLY:

{{
  "rule_index": 0,
  "confidence": 0.95,
  "reason": "short reason"
}}

If there is no clear match:

{{
  "rule_index": null,
  "confidence": 0,
  "reason": "No clear rule."
}}
"""

    routing_system_prompt = """
You are the BRAINOPX Rule Router.

Select only from supplied rules.

Never invent a rule.

Return ONLY valid JSON.
"""

    try:

        raw = _call_groq(
            system_prompt=(
                routing_system_prompt
            ),
            user_prompt=routing_prompt,
            temperature=0.0,
            max_tokens=300,
        )

        parsed = _extract_json(
            raw
        )

        if not isinstance(
            parsed,
            dict,
        ):
            raise ValueError(
                "Invalid router JSON."
            )

        selected_index = parsed.get(
            "rule_index"
        )

        if selected_index is None:

            return {
                "success": False,
                "rule_id": None,
                "rule_index": None,
                "rule_name": "",
                "confidence": 0.0,
                "reason": str(
                    parsed.get(
                        "reason",
                        "No matching rule.",
                    )
                ),
            }

        selected_index = int(
            selected_index
        )

        if not (
            0
            <= selected_index
            < len(rules)
        ):
            raise ValueError(
                "Invalid rule index."
            )

        selected_rule = rules[
            selected_index
        ]

        return {
            "success": True,
            "rule_id": selected_rule.get(
                "id",
                selected_index + 1,
            ),
            "rule_index": selected_index,
            "rule_name": str(
                selected_rule.get(
                    "name",
                    f"Rule {selected_index + 1}",
                )
            ),
            "confidence": float(
                parsed.get(
                    "confidence",
                    0.0,
                )
            ),
            "reason": str(
                parsed.get(
                    "reason",
                    "Rule selected by Groq.",
                )
            ),
        }

    except Exception as exc:

        logger.exception(
            "Rule routing failed."
        )

        if best_rule is not None:

            return {
                "success": True,
                "rule_id": best_rule.get(
                    "id",
                    best_index + 1,
                ),
                "rule_index": best_index,
                "rule_name": str(
                    best_rule.get(
                        "name",
                        f"Rule {best_index + 1}",
                    )
                ),
                "confidence": 0.2,
                "reason": (
                    "Fallback deterministic routing."
                ),
            }

        return {
            "success": False,
            "rule_id": None,
            "rule_index": None,
            "rule_name": "",
            "confidence": 0.0,
            "reason": str(exc),
        }


# ============================================================
# SIMPLE BOOLEAN HELPER
# ============================================================

def check_rule_example(
    example: str,
    rule: dict,
) -> bool:
    """
    Return True only if Python validation passes.
    """

    result = deterministic_validate_example(
        example=example,
        rule=rule,
    )

    return bool(
        result.get(
            "valid",
            False,
        )
    )


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    "generate_rule_example",
    "generate_rule_example_with_retry",
    "deterministic_validate_example",
    "deterministic_fallback",
    "run_rule_workflow",
    "run_rule_followup",
    "parse_rules_to_json",
    "get_rule_aware_response",
    "get_ai_response",
    "route_message_to_rule",
    "check_rule_example",
]