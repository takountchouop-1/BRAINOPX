
"""
BRAINOPX Example Utilities

Deterministic, text-pattern example generation for configuration
rules — every builder in this module (build_example_value() and the
functions it tries in turn) reads only rule text/constraints and
calls no AI service.

build_rules_with_examples(), the one exception, is the task-creation
entry point: it asks Groq for each rule's stored example (composite
list/table rules aside, which are still built column by column here)
so the value shown throughout a walkthrough is one the model actually
produced from the rule, not a local guess. It leaves a rule with no
example, rather than substituting one from this module, when Groq
cannot produce a validated value for it — see its own docstring.

Callers elsewhere (guided_engine, chat.py) still reach into this
module's builders directly for the narrower case of a step that has
no backing rule to send to the model at all.
"""

import re
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def _rule_text(rule: dict) -> str:
    """
    Combine all important rule fields into one searchable text.
    """

    if not isinstance(rule, dict):
        return str(rule or "")

    parts = [
        rule.get("name", ""),
        rule.get("description", ""),
        rule.get("task", ""),
        rule.get("expected_outcome", ""),
    ]

    keywords = rule.get("keywords", [])

    if isinstance(keywords, list):
        parts.extend(str(k) for k in keywords)
    elif keywords:
        parts.append(str(keywords))

    return " ".join(
        str(part)
        for part in parts
        if part is not None
    ).strip()


def _clean_value(value: Any) -> str:
    """
    Convert a generated value into a clean string.
    """

    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, (int, float, bool)):
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
                return _clean_value(value[key])

        return json.dumps(
            value,
            ensure_ascii=False,
        )

    return str(value).strip()


# ============================================================
# EXPLICIT EXAMPLE EXTRACTION
# ============================================================

def extract_explicit_example(rule: dict) -> Optional[str]:
    """
    Look for an example explicitly provided in the rule.

    Examples detected:

        Example: ACT001
        e.g. ACT001
        For example: ACT001
        Sample: ACT001
    """

    text = _rule_text(rule)

    patterns = [
        r"(?:example|sample)\s*[:=]\s*[\"']?([A-Za-z0-9@._+\-/]+)",
        r"e\.g\.\s*[:=]?\s*[\"']?([A-Za-z0-9@._+\-/]+)",
        r"for\s+example\s*[:=]?\s*[\"']?([A-Za-z0-9@._+\-/]+)",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            value = match.group(1).strip(
                "\"' .,;"
            )

            if value:
                return value

    return None


# ============================================================
# ALLOWED VALUES
# ============================================================

def extract_allowed_values(rule: dict) -> list[str]:
    """
    Extract allowed values from rules such as:

        Allowed values: ACTIVE, INACTIVE
        Valid values: YES, NO
        Must be one of: A, B, C
    """

    text = _rule_text(rule)

    patterns = [
        r"(?:allowed|valid|accepted|permitted)\s+values?\s*[:=]\s*(.+)",
        r"must\s+be\s+one\s+of\s*[:=]?\s*(.+)",
        r"choose\s+from\s*[:=]?\s*(.+)",

        # "must be either PRODUCTION or STAGING"
        r"\beither\s+(.+)",

        # "must be ACTIVE or INACTIVE"
        r"must\s+be\s+((?:[A-Z][A-Z0-9_-]{1,}\s*(?:,|\s+or\s+)\s*)+"
        r"[A-Z][A-Z0-9_-]{1,})",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        values_text = match.group(1)

        # If the captured text has a colon, take only the part after it.
        if ":" in values_text:
            values_text = values_text.split(":", 1)[1]

        # Stop at a sentence boundary when possible.
        values_text = re.split(
            r"\.\s+|\n",
            values_text,
            maxsplit=1,
        )[0]

        values = [
            item.strip().strip("\"'")
            for item in re.split(
                r",|\s+or\s+|\s+and\s+",
                values_text,
                flags=re.IGNORECASE,
            )
        ]

        values = [
            value
            for value in values
            if value
        ]

        if values:
            return values

    return []


# ============================================================
# PREFIX + DIGITS
# ============================================================

def build_prefix_digits_example(rule: dict) -> Optional[str]:
    """
    Generate examples for rules such as:

        Must start with ACT followed by 3 digits
        Prefix: EMP + 4 digits
        Format: INV + 5 digits
    """

    text = _rule_text(rule)

    patterns = [

        # "in the format WFS + 3 digits"
        r"in\s+the\s+format\s+"
        r"[\"']?([A-Za-z][A-Za-z0-9_-]*)"
        r"[\"']?\s*\+\s*"
        r"(\d+)\s*digits",

        # "format: ACT + 3 digits"
        r"format\s*[:=]\s*"
        r"[\"']?([A-Za-z][A-Za-z0-9_-]*)"
        r"[\"']?\s*\+\s*"
        r"(\d+)\s*digits",

        # "start with ACT followed by 3 digits"
        r"(?:start|begin)\s+with\s+[\"']?"
        r"([A-Za-z][A-Za-z0-9_-]*)"
        r"[\"']?"
        r".{0,40}?"
        r"(?:followed\s+by|with)\s+"
        r"(\d+)"
        r"\s+digits",

        # "prefix ACT followed by 3 digits"
        r"prefix\s*[:=]?\s*[\"']?"
        r"([A-Za-z][A-Za-z0-9_-]*)"
        r"[\"']?"
        r".{0,40}?"
        r"(?:followed\s+by|with)\s+"
        r"(\d+)"
        r"\s+digits",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        prefix = match.group(1)
        digit_count = int(match.group(2))

        if digit_count <= 0:
            digit_count = 1

        return (
            prefix
            + "0" * (digit_count - 1)
            + "1"
        )

    return None


# ============================================================
# EXACT LENGTH
# ============================================================

_READABLE_SAMPLE = "Standard Value"


def build_length_example(rule: dict) -> Optional[str]:
    """
    Generate examples for length rules.

    Examples:

        Must be exactly 6 characters
        Exactly 8 digits
        Must contain 5 letters
        Must be between 3 and 50 characters
        Must not exceed 200 characters
        At least 4 characters
    """

    text = _rule_text(rule)

    def _sample(
        length: int,
        unit: str,
        readable: bool = False,
    ) -> Optional[str]:
        """
        A value of the requested length.

        `readable` is used where only a bound is given, so the example
        looks like a real value instead of a run of letters. Exact
        lengths still use a run, since real words rarely land on one.
        """
        if length <= 0:
            return None
        if "digit" in unit:
            return "1" * length
        if "letter" in unit:
            return "A" * length
        if readable:
            base = _READABLE_SAMPLE
            if len(base) >= length:
                return base[:length].strip() or "A" * length
            return base + "X" * (length - len(base))
        return "A" * length

    # "between 3 and 50 characters" — sit inside the range, not on an
    # edge, so a boundary read as exclusive still accepts the example.

    match = re.search(
        r"between\s+(\d+)\s+and\s+(\d+)\s*"
        r"(characters?|chars?|digits?|letters?)",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        low = int(match.group(1))
        high = int(match.group(2))

        if low > high:
            low, high = high, low

        unit = match.group(3).lower()

        if "digit" in unit or "letter" in unit:
            return _sample(
                min(low + 2, high) if high > low else low,
                unit,
            )

        # Free text: aim for a natural-looking length inside the
        # range rather than hugging the minimum.
        return _sample(
            min(max(low, len(_READABLE_SAMPLE)), high),
            unit,
            readable=True,
        )

    # "exactly 6 characters"

    match = re.search(
        r"(?:exactly|must\s+be)\s+"
        r"(\d+)\s*"
        r"(characters?|chars?|digits?|letters?)",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        return _sample(
            int(match.group(1)),
            match.group(2).lower(),
        )

    # "at least 4 characters"

    match = re.search(
        r"(?:at\s+least|minimum\s+of|no\s+fewer\s+than|min(?:imum)?)\s+"
        r"(\d+)\s*"
        r"(characters?|chars?|digits?|letters?)",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        return _sample(
            int(match.group(1)) + 2,
            match.group(2).lower(),
            readable=True,
        )

    # "must not exceed 200 characters"

    match = re.search(
        r"(?:not\s+exceed|no\s+more\s+than|at\s+most|maximum\s+of|max(?:imum)?)\s+"
        r"(\d+)\s*"
        r"(characters?|chars?|digits?|letters?)",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        limit = int(match.group(1))
        unit = match.group(2).lower()

        if "digit" in unit or "letter" in unit:
            return _sample(min(6, limit), unit)

        # Free text with only an upper bound: a readable value that
        # comfortably fits.
        return "Standard description"[:limit] or None

    return None


# ============================================================
# TIME
# ============================================================

def build_time_example(rule: dict) -> Optional[str]:
    """
    Generate examples for time-of-day rules.

    Examples:

        Must be a time in HH:MM format
        Start time in 24 hour format
        Must include seconds (HH:MM:SS)
    """

    text = _rule_text(rule).lower()

    if not re.search(
        r"\btime\b|hh\s*:\s*mm",
        text,
    ):
        return None

    # Exclude date-only rules that merely mention "datetime".
    if re.search(r"hh\s*:\s*mm\s*:\s*ss", text):
        return "09:30:00"

    if re.search(r"\bhh\s*:\s*mm\b|\btime\b", text):
        return "09:30"

    return None


# ============================================================
# EMAIL
# ============================================================

def build_email_example(rule: dict) -> Optional[str]:
    """
    Generate a deterministic email example.
    """

    text = _rule_text(rule).lower()

    if "email" not in text:
        return None

    return "user@example.com"


# ============================================================
# PHONE NUMBER
# ============================================================

def build_phone_example(rule: dict) -> Optional[str]:
    """
    Generate a basic phone number example when the rule
    explicitly refers to phone/mobile numbers.
    """

    text = _rule_text(rule).lower()

    if not any(
        keyword in text
        for keyword in (
            "phone number",
            "mobile number",
            "telephone number",
            "phone",
            "mobile",
        )
    ):
        return None

    # Cameroon-friendly generic example.
    return "690000001"


# ============================================================
# INTEGER
# ============================================================

def _wants_decimals(text: str) -> Optional[int]:
    """Number of decimal places the rule asks for, if it asks."""

    match = re.search(
        r"(\d+)\s*decimal",
        text,
    )

    if match:
        return max(0, int(match.group(1)))

    if "decimal" in text:
        return 2

    return None


def build_integer_example(rule: dict) -> Optional[str]:
    """
    Generate an integer example.
    """

    text = _rule_text(rule).lower()

    # A rule asking for decimal places is not an integer rule, even
    # when it also says "number".
    if _wants_decimals(text) is not None:
        return None

    if (
        "integer" in text
        or "whole number" in text
    ):
        return "1"

    return None


# ============================================================
# POSITIVE NUMBER
# ============================================================

def build_positive_number_example(
    rule: dict,
) -> Optional[str]:

    text = _rule_text(rule).lower()

    if not (
        "positive number" in text
        or "greater than zero" in text
        or "greater than 0" in text
        or "must be positive" in text
        or "decimal" in text
    ):
        return None

    places = _wants_decimals(text)

    if places:
        # Show the precision the rule asks for, so the example
        # demonstrates the format rather than merely satisfying it.
        return f"{120:.{places}f}"

    return "1"


# ============================================================
# DATE
# ============================================================

_DATE_LAYOUT_PATTERNS = (
    ("yyyy-mm-dd", "%Y-%m-%d"),
    ("yyyy/mm/dd", "%Y/%m/%d"),
    ("dd-mm-yyyy", "%d-%m-%Y"),
    ("dd/mm/yyyy", "%d/%m/%Y"),
    ("mm-dd-yyyy", "%m-%d-%Y"),
    ("mm/dd/yyyy", "%m/%d/%Y"),
)


def build_date_example(rule: dict) -> Optional[str]:
    """
    Generate an example date in the layout the rule asks for.

    Dates are generated relative to today rather than hardcoded. A
    fixed sample silently expires: "2026-01-15" was offered as the
    example for a rule requiring a FUTURE date long after that date
    had passed, so the assistant was recommending a value its own
    validator would reject.
    """

    text = _rule_text(rule).lower()

    if "date" not in text:
        return None

    layout = "%Y-%m-%d"

    for token, fmt in _DATE_LAYOUT_PATTERNS:
        if token in text:
            layout = fmt
            break

    today = datetime.now().date()

    if re.search(
        r"in\s+the\s+past|past\s+date|before\s+today",
        text,
    ):
        sample = today - timedelta(days=30)

    elif re.search(
        r"in\s+the\s+future|future\s+date|after\s+today"
        r"|later\s+than\s+today|not\s+in\s+the\s+past",
        text,
    ):
        sample = today + timedelta(days=180)

    else:
        # No direction stated: a near-future date reads as a sensible
        # configuration value and satisfies a future rule too.
        sample = today + timedelta(days=180)

    return sample.strftime(layout)


# ============================================================
# BOOLEAN
# ============================================================

def build_boolean_example(rule: dict) -> Optional[str]:
    """
    Generate an example for boolean requirements.
    """

    text = _rule_text(rule).lower()

    if any(
        phrase in text
        for phrase in (
            "boolean",
            "true or false",
            "true/false",
        )
    ):
        return "true"

    return None


# ============================================================
# REQUIRED TEXT
# ============================================================

def build_required_text_example(
    rule: dict,
) -> Optional[str]:

    text = _rule_text(rule).lower()

    if "required" not in text:
        return None

    # Avoid returning a generic string when the rule
    # already has a more specific constraint.
    if any(
        keyword in text
        for keyword in (
            "email",
            "phone",
            "date",
            "integer",
            "number",
            "boolean",
            "username",
            "alphanumeric",
            "letters and numbers",
        )
    ):
        return None

    return "Sample Value"


# ============================================================
# ALPHANUMERIC / USERNAME
# ============================================================

def build_alphanumeric_example(
    rule: dict,
) -> Optional[str]:

    text = _rule_text(rule).lower()

    if not any(
        keyword in text
        for keyword in (
            "username",
            "user name",
            "login",
            "user id",
            "alphanumeric",
            "letters and numbers",
        )
    ):
        return None

    if "only letters and numbers" in text or "alphanumeric" in text or "letters and numbers only" in text:
        return "User01"

    return "User01"


# ============================================================
# MAIN EXAMPLE BUILDER
# ============================================================

# ============================================================
# CONSTRAINT-DRIVEN EXAMPLE
# ============================================================

# Currency codes the validator accepts.
_CURRENCY_SAMPLE = "USD"

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _resolve_rule_contract(rule: dict) -> tuple[dict, str]:
    """
    Ask the validator how it reads this rule.

    Returns its effective constraints and semantic type. Deriving the
    example from the same interpretation the validator uses is what
    keeps the two from disagreeing about the same rule text.
    """

    # Imported lazily: groq_service builds an API client at import time
    # and nothing here needs it until an example is actually requested.

    from .groq_service import (
        _get_effective_constraints,
        _infer_semantic_type,
    )

    constraints = _get_effective_constraints(rule)
    semantic_type = _infer_semantic_type(rule, constraints)

    return constraints, str(semantic_type or "")


def _pad_to_length(
    value: str,
    min_length: Optional[int],
    max_length: Optional[int],
    exact_length: Optional[int],
    filler: str = "X",
) -> str:
    """Stretch or trim a value to satisfy the length constraints."""

    target = exact_length or min_length

    if target and len(value) < target:
        value = value + filler * (target - len(value))

    limit = exact_length or max_length

    if limit and len(value) > limit:
        value = value[:limit]

    return value


def _number_within(
    min_value: Optional[float],
    max_value: Optional[float],
    as_integer: bool,
) -> str:
    """Pick a value inside the allowed numeric range."""

    low = min_value if min_value is not None else (1 if as_integer else 1.0)
    high = max_value if max_value is not None else low + (9 if as_integer else 99)

    if low > high:
        low, high = high, low

    # Prefer a value comfortably inside the range rather than on a
    # boundary, since boundaries are often exclusive in practice.
    chosen = low + (high - low) / 2 if high > low else low

    if as_integer:
        chosen = int(round(chosen)) or int(low)
        return str(chosen)

    return f"{chosen:.2f}"


def build_example_from_constraints(rule: dict) -> Optional[str]:
    """
    Build a value from the constraints the validator itself derives.

    Handles the cases the text-matching builders miss: numeric ranges,
    length ranges, times, currencies, character-class requirements and
    prefix rules whose separator the two sides parsed differently.
    """

    try:
        constraints, semantic_type = _resolve_rule_contract(rule)
    except Exception as exc:
        logger.warning(
            "Could not resolve rule contract: %s",
            exc,
        )
        return None

    allowed = constraints.get("allowed_values")

    if isinstance(allowed, list) and allowed:
        first = _clean_value(allowed[0])
        if first:
            return first

    # A section of prose wants a sentence, not a code.

    if constraints.get("content_type") == "narrative":
        return build_narrative_example(
            rule,
            min_words=constraints.get("min_words") or 3,
        )

    exact_length = constraints.get("exact_length")
    min_length = constraints.get("min_length")
    max_length = constraints.get("max_length")

    min_value = constraints.get("min_value")
    max_value = constraints.get("max_value")

    # --------------------------------------------------------
    # Semantic types the validator checks by name
    # --------------------------------------------------------

    if semantic_type == "email":
        domain = _clean_value(
            constraints.get("domain")
        ) or "example.com"
        return f"user@{domain}"

    if semantic_type == "phone":
        return "+15550102233"

    if semantic_type == "currency":
        return _CURRENCY_SAMPLE

    if semantic_type == "password":
        return "Passw0rd!2024"

    if semantic_type == "full_name":
        return "John Doe"

    if semantic_type == "role":
        return "Administrator"

    if semantic_type == "status":
        return "Active"

    if semantic_type == "department":
        return "Finance"

    if semantic_type == "date":
        return build_date_example(rule) or "2026-01-15"

    # --------------------------------------------------------
    # Prefix + digit count, exactly as the validator reads it
    # --------------------------------------------------------

    prefix = _clean_value(
        constraints.get("prefix")
    )

    if prefix:
        digit_count = constraints.get("prefix_digit_count")

        if isinstance(digit_count, int) and digit_count > 0:
            value = prefix + str(1).zfill(digit_count)
        else:
            value = prefix + "001"

        suffix = _clean_value(constraints.get("suffix"))

        if suffix and not value.endswith(suffix):
            value += suffix

        return _pad_to_length(
            value,
            min_length,
            max_length,
            exact_length,
            filler="0",
        )

    # --------------------------------------------------------
    # Numbers
    # --------------------------------------------------------

    if semantic_type in ("integer", "int", "whole_number"):
        return _number_within(min_value, max_value, as_integer=True)

    if semantic_type in ("number", "numeric", "decimal", "float"):
        return _number_within(min_value, max_value, as_integer=False)

    if min_value is not None or max_value is not None:
        return _number_within(min_value, max_value, as_integer=False)

    # --------------------------------------------------------
    # Text shaped only by length and character classes
    # --------------------------------------------------------

    needs_upper = bool(constraints.get("uppercase"))
    needs_lower = bool(constraints.get("lowercase"))
    needs_number = bool(
        constraints.get("number")
        or constraints.get("numbers")
    )
    needs_special = bool(
        constraints.get("special_character")
        or constraints.get("special_characters")
    )
    no_number = bool(constraints.get("no_number"))
    no_spaces = bool(constraints.get("no_spaces"))

    if (
        exact_length
        or min_length
        or max_length
        or needs_upper
        or needs_lower
        or needs_number
        or needs_special
    ):

        value = "Sample"

        if needs_upper and not any(c.isupper() for c in value):
            value = value.capitalize()

        if needs_lower and not any(c.islower() for c in value):
            value = value.lower()

        if needs_number and not no_number:
            value += "1"

        if needs_special:
            value += "!"

        if no_spaces:
            value = value.replace(" ", "")

        filler = "0" if (needs_number and not no_number) else "X"

        return _pad_to_length(
            value,
            min_length,
            max_length,
            exact_length,
            filler=filler,
        )

    return None


# ============================================================
# NARRATIVE SECTIONS
# ============================================================

# Sample content for sections that commonly appear in the kinds of
# documents this system walks people through.

_SECTION_SAMPLES = {
    "client information":
        "Acme Corp, 12 Rue Bastos, Yaounde. Contact: Marie Nkomo, "
        "marie.nkomo@acme.cm",

    "problem statement":
        "Support requests currently take up to three days to answer, "
        "which is causing customers to abandon their orders.",

    "solution offered":
        "Deploy an SMS notification service that acknowledges every "
        "request within one minute and routes it to the right agent.",

    "scope of work":
        "Configure the messaging gateway, migrate existing contacts, "
        "and train four support agents over two weeks.",

    "pricing breakdown":
        "Setup 450,000 XAF; monthly licence 120,000 XAF; training "
        "80,000 XAF. Total first year: 1,970,000 XAF.",

    "timeline":
        "Kick-off 1 March 2026, configuration complete 20 March, "
        "go-live 1 April 2026.",

    "terms and conditions":
        "Payment is due within 30 days of invoice. Either party may "
        "terminate with 30 days written notice.",

    "deliverables":
        "A configured messaging gateway, a migrated contact list, and "
        "a training handbook for support agents.",

    "objectives":
        "Cut first-response time to under five minutes and raise "
        "customer satisfaction by 20 percent within six months.",

    "assumptions":
        "The client provides network access and a named project "
        "contact for the duration of the engagement.",

    "risks":
        "Delays in gateway approval could push go-live back by two "
        "weeks; mitigated by starting the application immediately.",

    "next steps":
        "Confirm acceptance of this proposal, then schedule the "
        "kick-off meeting for the week of 1 March.",

    "background":
        "Acme Corp has operated a manual support desk since 2019 and "
        "now handles more requests than the team can answer by phone.",

    "recommendation":
        "Proceed with the SMS notification service, starting with a "
        "four-week pilot in the Yaounde office.",
}


def build_narrative_example(
    rule: dict,
    min_words: int = 3,
) -> str:
    """
    A sample sentence for a section of prose.

    Matches the section by name where possible; otherwise builds a
    plausible opening line from the section's own name, so the user
    still sees the shape of an answer rather than a placeholder code.
    """

    label = str(
        (rule or {}).get("name")
        or (rule or {}).get("rule_name")
        or ""
    ).strip()

    key = label.lower()

    if key in _SECTION_SAMPLES:
        return _SECTION_SAMPLES[key]

    for section, sample in _SECTION_SAMPLES.items():
        if section in key or key in section:
            return sample

    # Worded without assuming what kind of document this is: the
    # fallback used to say "for this proposal" on every task.
    if label:
        sample = (
            f"A short paragraph setting out the {label.lower()}, "
            f"written in full sentences."
        )
    else:
        sample = (
            "A short paragraph answering this section in full "
            "sentences."
        )

    # Guarantee the sample would itself be accepted.
    if len(sample.split()) < max(1, int(min_words or 0)):
        sample += " Add the relevant detail here."

    return sample


# ============================================================
# NAMED FIELD SAMPLES
# ============================================================

# Concepts a rule can name where the field itself implies the shape of
# a correct value. Longest key wins, so "unit rate" beats "rate".

_FIELD_SAMPLES = {
    "currency": "USD",
    "currency code": "USD",
    "iso currency": "USD",

    "email": "user@example.com",
    "phone": "+15550102233",

    "time": "09:30",
    "start time": "09:30",
    "end time": "17:00",

    "percentage": "15.00",
    "tax rate": "15.00",
    "unit rate": "120.00",
    "rate": "15.00",
    "amount": "2500.00",
    "total": "15000.00",
    "price": "99.99",
    "quantity": "25",

    "full name": "John Doe",
    "contact": "John Doe",
    "customer": "Acme Corp",
    "company": "Acme Corp",
    "vendor": "TechWave Ltd",
    "department": "Finance",
    "location": "New York",

    "address": "12 Rue Bastos, Yaounde",
    "street": "12 Rue Bastos",
    "city": "Yaounde",
    "country": "Cameroon",
    "postal code": "BP 1234",

    # Compound names, so the head noun wins: "Customer ID" is an
    # identifier, not a customer.
    "customer name": "Acme Corp",
    "company name": "Acme Corp",
    "customer id": "CUST-0001",
    "customer address": "12 Rue Bastos, Yaounde",
    "customer email": "user@example.com",
    "customer phone": "+15550102233",
    "id": "ID-0001",
    "reference": "REF-0001",

    "role": "Administrator",
    "status": "Active",
    "priority": "High",
    "category": "Operating",
    "type": "Standard",
    "frequency": "DAILY",
    "target system": "PRODUCTION",
    "environment": "PRODUCTION",

    "description": "Standard description",
    "name": "Standard Name",
    "order": "1",
    "sequence": "1",

    "uom": "Each",
    "unit": "Each",
    "colour": "Blue",
    "color": "Blue",
    "weight": "120",
}


def build_field_sample_example(rule: dict) -> Optional[str]:
    """
    Fall back to what the field is called.

    Used when a rule states an expectation the constraint parser does
    not model — "a valid ISO currency code", "the target system" —
    but the field name alone implies a correct value.

    The field's name is consulted before its wider text, and its head
    noun before the whole name. Matching on longest key alone made
    "Customer ID" an id-shaped field called a customer: it matched
    "customer" and offered "Acme Corp".
    """

    name = str(
        (rule or {}).get("name")
        or (rule or {}).get("rule_name")
        or ""
    ).lower()

    words = re.findall(r"[a-z0-9]+", name)

    # 1. The whole field name.
    if words:
        phrase = " ".join(words)
        if phrase in _FIELD_SAMPLES:
            return _FIELD_SAMPLES[phrase]

    # 2. Its head noun — the trailing word or words.
    for size in (3, 2, 1):
        if len(words) < size:
            continue
        phrase = " ".join(words[-size:])
        if phrase in _FIELD_SAMPLES:
            return _FIELD_SAMPLES[phrase]

    # 3. Anything the rule text mentions, longest key first.
    text = _rule_text(rule).lower()

    if not text:
        return None

    for keyword in sorted(
        _FIELD_SAMPLES,
        key=len,
        reverse=True,
    ):
        if re.search(
            r"\b" + re.escape(keyword) + r"\b",
            text,
        ):
            return _FIELD_SAMPLES[keyword]

    return None


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def _candidate_examples(rule: dict) -> list[str]:
    """
    Every example this module can propose for a rule, best first.

    Order matters only among candidates that pass validation: the
    first valid one is shown. A specific text-derived example is
    preferred over a generic one, with the constraint-driven builder
    behind them as the safety net that catches what they misread.
    """

    builders = (
        extract_explicit_example,
        lambda r: (extract_allowed_values(r) or [None])[0],
        build_prefix_digits_example,
        build_length_example,
        build_email_example,
        build_phone_example,
        build_time_example,
        build_date_example,
        build_integer_example,
        build_positive_number_example,
        build_boolean_example,
        build_example_from_constraints,
        build_alphanumeric_example,
        build_field_sample_example,
        build_required_text_example,
    )

    candidates = []

    for builder in builders:

        try:
            value = builder(rule)
        except Exception as exc:
            logger.warning(
                "Example builder %s failed: %s",
                getattr(builder, "__name__", builder),
                exc,
            )
            continue

        value = _clean_value(value)

        if value and value not in candidates:
            candidates.append(value)

    return candidates


def build_example_value(rule: dict) -> str:
    """
    Main deterministic example generator.

    Proposes candidates, then returns the first one the validator
    accepts for this same rule. An example the user is shown as
    correct is therefore an example that would pass if they typed it.

    This is the function expected by:

        groq_service.py
        rule_router_service.py
        step_by_step_service.py
    """

    if not isinstance(rule, dict):
        rule = {
            "description": str(rule or "")
        }

    # A list or table step needs a sample of the whole answer, built
    # from each column's own example.

    from . import composite_rules

    if composite_rules.is_composite(rule):

        composite = composite_rules.build_composite_example(rule)

        if composite:
            return composite

    candidates = _candidate_examples(rule)

    # --------------------------------------------------------
    # Prefer a candidate that passes its own rule
    # --------------------------------------------------------

    try:
        from .groq_service import deterministic_validate_example

        for candidate in candidates:

            try:
                verdict = deterministic_validate_example(
                    example=candidate,
                    rule=rule,
                )
            except Exception:
                continue

            if verdict.get("valid"):
                return candidate

        logger.warning(
            "No generated example satisfies rule '%s'; "
            "falling back to a best-effort value.",
            rule.get("name", "unnamed"),
        )

    except Exception as exc:
        logger.warning(
            "Could not verify generated examples: %s",
            exc,
        )

    # --------------------------------------------------------
    # Nothing verified — best effort
    # --------------------------------------------------------

    if candidates:
        return candidates[0]

    # Last resort. Never "VALID001": the validator rejects generic
    # placeholders, so showing one told the user to type a value that
    # would have been refused. Describe the field instead.

    label = str(
        (rule or {}).get("name")
        or (rule or {}).get("rule_name")
        or ""
    ).strip()

    if label:
        return f"A valid {label.lower()}"

    return "A valid value for this step"



# ============================================================
# BUILD RULES WITH EXAMPLES
# ============================================================

def build_rules_with_examples(
    rules: list[dict] | None,
) -> list[dict]:
    """
    Add a concrete, AI-generated example to every rule.

    This function is used by skill_engine_service.py and by
    tasks.py at task-creation time (_store_rules_with_examples), so
    this is where a rules document is walked rule by rule and Groq is
    asked to produce the example every step of the walkthrough will
    show. Composite (table/list) rules are the one exception: their
    examples are still built column by column by build_example_value(),
    which AI generation for a single scalar value is not shaped for.

    A rule Groq cannot produce a validated example for after retrying
    (see groq_service.generate_rule_example_with_retry) is left with
    no example rather than one silently guessed by a local
    pattern-matcher — example_source is set to "ai_unavailable" so
    callers can tell the difference and say so, instead of showing a
    value the model never actually produced.

    It preserves the original rule information and adds:

        example
        example_value
        example_input
        example_source

    Example input:

        [
            {
                "id": 1,
                "name": "Employee ID",
                "description": "Must start with EMP followed by 3 digits"
            }
        ]

    Example output:

        [
            {
                "id": 1,
                "name": "Employee ID",
                "description": "...",
                "example": "EMP001",
                "example_value": "EMP001",
                "example_input": "EMP001",
                "example_source": "ai"
            }
        ]
    """

    if not rules:
        return []

    # Imported lazily: groq_service builds an API client at import
    # time, which nothing above this module needs until an example is
    # actually requested.

    from .groq_service import generate_rule_example_with_retry
    from . import composite_rules

    result = []

    for index, rule in enumerate(rules, start=1):

        # ----------------------------------------------------
        # Make sure the rule is a dictionary
        # ----------------------------------------------------

        if not isinstance(rule, dict):
            rule = {
                "id": index,
                "name": f"Rule {index}",
                "description": str(rule),
            }

        # ----------------------------------------------------
        # Copy the original rule
        # ----------------------------------------------------

        enriched_rule = dict(rule)

        # ----------------------------------------------------
        # Generate the example
        #
        # A composite (list/table) rule is not a single value Groq is
        # asked to produce — it is built column by column, as before.
        # Everything else goes to Groq first.
        # ----------------------------------------------------

        example = ""
        example_source = "ai_unavailable"

        if composite_rules.is_composite(enriched_rule):

            try:
                example = build_example_value(enriched_rule)
                example_source = "builder"
            except Exception as exc:
                logger.warning(
                    "Could not build a composite example for rule %s: %s",
                    enriched_rule.get("id", index),
                    exc,
                )
                example = ""
                example_source = "ai_unavailable"

        else:

            try:
                generated = generate_rule_example_with_retry(
                    rule=enriched_rule
                )

                if generated.get("success") and generated.get("example"):
                    example = str(generated["example"]).strip()
                    example_source = "ai"
                else:
                    logger.warning(
                        "Groq could not generate an example for rule "
                        "'%s': %s",
                        enriched_rule.get("name", index),
                        generated.get("validation_reason", ""),
                    )

            except Exception as exc:

                logger.warning(
                    "Could not reach Groq to build an example for "
                    "rule %s: %s",
                    enriched_rule.get("id", index),
                    exc,
                )

        # ----------------------------------------------------
        # Add example fields
        # ----------------------------------------------------

        enriched_rule["example"] = example
        enriched_rule["example_value"] = example
        enriched_rule["example_input"] = example
        enriched_rule["example_source"] = example_source

        # ----------------------------------------------------
        # Add ID if missing
        # ----------------------------------------------------

        if not enriched_rule.get("id"):
            enriched_rule["id"] = index

        # ----------------------------------------------------
        # Add name if missing
        # ----------------------------------------------------

        if not enriched_rule.get("name"):
            enriched_rule["name"] = (
                f"Rule {index}"
            )

        # ----------------------------------------------------
        # Add description if missing
        # ----------------------------------------------------

        if not enriched_rule.get("description"):
            enriched_rule["description"] = (
                enriched_rule.get("task")
                or enriched_rule.get(
                    "expected_outcome",
                    "",
                )
                or ""
            )

        result.append(enriched_rule)

    return result



# ============================================================
# COMPATIBILITY ALIASES
# ============================================================

def generate_example_value(rule: dict) -> str:
    """
    Compatibility alias for older code.
    """

    return build_example_value(rule)


def get_example_value(rule: dict) -> str:
    """
    Compatibility alias for older code.
    """

    return build_example_value(rule)


def build_example(rule: dict) -> str:
    """
    Compatibility alias for older code.
    """

    return build_example_value(rule)


# ============================================================
# TEST HELPER
# ============================================================

def explain_example_generation(rule: dict) -> dict:
    """
    Returns the generated example together with its source.
    Useful for debugging the rule engine.
    """

    example = build_example_value(rule)

    source = "generic fallback"

    if extract_explicit_example(rule):
        source = "explicit example"

    elif extract_allowed_values(rule):
        source = "allowed values"

    elif build_prefix_digits_example(rule):
        source = "prefix + digits"

    elif build_length_example(rule):
        source = "exact length"

    elif build_email_example(rule):
        source = "email"

    elif build_phone_example(rule):
        source = "phone"

    elif build_integer_example(rule):
        source = "integer"

    elif build_positive_number_example(rule):
        source = "positive number"

    elif build_date_example(rule):
        source = "date"

    elif build_boolean_example(rule):
        source = "boolean"

    elif build_required_text_example(rule):
        source = "required text"

    return {
        "example": example,
        "source": source,
        "rule": rule,
    }

