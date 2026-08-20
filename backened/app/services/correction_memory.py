"""
correction_memory.py

What the assistant has learned from users correcting themselves.

When someone fails a step and then succeeds, the pair — what was
rejected, what was accepted — is recorded against the *kind* of error
they hit. The next person who trips on that same error is shown how
others got past it, on top of the ordinary correction.

    Step 6 of 8: Future Start Date — not accepted
    What is missing: Value must be a date in YYYY-MM-DD format.
    Others got past this by entering: 2027-03-01
    Use this format instead: 2027-02-09

Errors are grouped by pattern, not by literal text, so
"must be 'TRF' followed by exactly 3 digits" and the same complaint
about 'CUST' and 4 digits share one entry and one growing body of
evidence.

WHAT IS NEVER LEARNED
---------------------

Only values that passed deterministic validation are recorded, so a
wrong habit cannot be learned as correct.

Personal data is never recorded. A value entered for an email, phone,
name, address, username or password step is somebody's real detail,
and showing it to the next user would leak it. Those steps still count
their errors, but store no values. Values that merely look personal —
anything containing an @, or a long run of digits — are also skipped
whatever the step claims to be.
"""

import json
import logging
import os
import re
import tempfile
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()

# The file lives beside the app so it travels with a deployment and
# can be inspected and edited by hand.
KNOWLEDGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "knowledge",
)

KNOWLEDGE_PATH = os.path.join(
    KNOWLEDGE_DIR,
    "correction_memory.json",
)

# Steps whose values are personal. Nothing entered for these is kept.
_PERSONAL_TYPES = {
    "email",
    "phone",
    "full_name",
    "fullname",
    "username",
    "password",
}

_PERSONAL_NAME_WORDS = {
    "email", "mail", "phone", "mobile", "telephone", "name", "address",
    "contact", "person", "customer", "client", "user", "employee",
    "password", "passcode", "birth", "dob", "nationality", "passport",
    "account", "iban", "card",
}

# How many distinct corrections to remember per pattern.
_MAX_CORRECTIONS = 5

# How many times a correction must be seen before it is offered, so a
# single user's one-off does not become advice.
_MIN_CONFIDENCE = 1


# ============================================================
# ERROR PATTERNS
# ============================================================

def signature(error: str) -> str:
    """
    Group an error message by its kind rather than its literal text.

    Quoted values and numbers are replaced, so the same complaint
    about different rules lands on one entry.
    """

    text = str(error or "").strip().lower()

    if not text:
        return ""

    text = re.sub(r"'[^']*'", "'X'", text)
    text = re.sub(r'"[^"]*"', "'X'", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\b", "N", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip(" .")


def _first_error(verdict: dict) -> str:
    """The error a correction should be filed under."""

    if not isinstance(verdict, dict):
        return ""

    errors = verdict.get("validation_errors")

    if not isinstance(errors, list) or not errors:
        validation = verdict.get("validation")
        errors = (
            validation.get("errors")
            if isinstance(validation, dict)
            else None
        )

    if isinstance(errors, list) and errors:
        return str(errors[0])

    return ""


# ============================================================
# PRIVACY
# ============================================================

# Dates are digits and separators too. Recognised first so a date is
# not mistaken for a phone number: "2027-03-01" stripped of its
# hyphens is an eight digit run.
_DATE_SHAPES = (
    r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",
    r"\d{1,2}[-/]\d{1,2}[-/]\d{4}",
)


def _looks_personal(value: str) -> bool:
    """Whether a value looks like somebody's real detail."""

    text = str(value or "").strip()

    if not text:
        return False

    if "@" in text:
        return True

    for shape in _DATE_SHAPES:
        if re.fullmatch(shape, text):
            return False

    # A long run of digits is a phone number, an account, a card.
    if re.search(r"\d{7,}", re.sub(r"[\s\-().+]", "", text)):
        return True

    return False


def _is_personal_step(step: dict) -> bool:
    """Whether a step collects personal data."""

    from app.services.groq_service import (
        _get_effective_constraints,
        _infer_semantic_type,
    )

    rule = step or {}

    # Steps carry rule_name; rules carry name.
    probe = dict(rule)
    probe.setdefault("name", rule.get("rule_name", ""))

    try:
        semantic = _infer_semantic_type(
            probe,
            _get_effective_constraints(probe),
        )
    except Exception:
        semantic = ""

    if semantic in _PERSONAL_TYPES:
        return True

    words = set(
        re.findall(
            r"[a-z]+",
            str(probe.get("name", "")).lower(),
        )
    )

    return bool(words & _PERSONAL_NAME_WORDS)


# ============================================================
# STORAGE
# ============================================================

def _empty() -> dict:
    return {"version": 1, "patterns": {}}


def load() -> dict:
    """Read the knowledge file. A missing or broken file is not fatal."""

    try:
        with open(KNOWLEDGE_PATH, encoding="utf-8") as handle:
            data = json.load(handle)

        if isinstance(data, dict) and isinstance(data.get("patterns"), dict):
            return data

    except FileNotFoundError:
        pass

    except (json.JSONDecodeError, OSError, ValueError):
        logger.exception(
            "Correction memory at %s could not be read; starting empty.",
            KNOWLEDGE_PATH,
        )

    return _empty()


def _save(data: dict) -> None:
    """Write atomically, so a crash cannot leave a half-written file."""

    try:
        os.makedirs(KNOWLEDGE_DIR, exist_ok=True)

        handle = tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=KNOWLEDGE_DIR,
            delete=False,
        )

        with handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)

        os.replace(handle.name, KNOWLEDGE_PATH)

    except OSError:
        logger.exception(
            "Could not write correction memory to %s",
            KNOWLEDGE_PATH,
        )


# ============================================================
# LEARNING
# ============================================================

def record_correction(
    step: dict,
    rejected: str,
    accepted: str,
    verdict: dict,
) -> bool:
    """
    Remember that a user recovered from an error.

    Called only when `accepted` has passed deterministic validation,
    so what is stored is always a value the rules allow.

    Returns whether anything was stored.
    """

    key = signature(_first_error(verdict))

    if not key:
        return False

    accepted = str(accepted or "").strip()
    rejected = str(rejected or "").strip()

    if not accepted:
        return False

    with _LOCK:

        data = load()

        entry = data["patterns"].setdefault(
            key,
            {
                "signature": key,
                "seen": 0,
                "corrections": [],
            },
        )

        entry["seen"] = int(entry.get("seen", 0)) + 1
        entry["last_seen"] = datetime.now().isoformat(timespec="seconds")

        # Count the error either way; only the value is withheld.
        personal = (
            _is_personal_step(step)
            or _looks_personal(accepted)
            or _looks_personal(rejected)
        )

        if personal:
            entry["withheld"] = int(entry.get("withheld", 0)) + 1
            _save(data)
            return False

        corrections = entry.setdefault("corrections", [])

        for correction in corrections:
            if correction.get("accepted") == accepted:
                correction["count"] = int(correction.get("count", 0)) + 1
                break
        else:
            corrections.append({
                "accepted": accepted,
                "rejected": rejected,
                "step": str(step.get("rule_name") or step.get("name") or ""),
                "count": 1,
                "first_seen": entry["last_seen"],
            })

        # Keep the most frequently seen, so advice reflects what
        # actually works rather than whatever arrived last.
        corrections.sort(
            key=lambda item: int(item.get("count", 0)),
            reverse=True,
        )

        entry["corrections"] = corrections[:_MAX_CORRECTIONS]

        _save(data)

        return True


# ============================================================
# RECALL
# ============================================================

def guidance_for(
    verdict: dict,
    step: dict | None = None,
    rule: dict | None = None,
) -> str:
    """
    What previous users did to get past this error.

    A stored value is offered only if it would ACTUALLY BE ACCEPTED
    for the rule in front of the user. Errors are grouped by kind, so
    "must be 'SCH' followed by exactly 3 digits" and the same
    complaint about 'TRF' share an entry — useful for counting how
    often the shape trips people up, useless as advice. Without this
    check the assistant told someone stuck on an SCH code to enter
    "TRF432", which its own validator would have rejected.

    Corrections recorded against the same step are preferred, then
    anything else that still validates here.

    Returns "" when nothing has been learned, when nothing learned
    would pass, or when the step collects personal data — advice
    there could echo somebody's details back at another user.
    """

    key = signature(_first_error(verdict))

    if not key:
        return ""

    if step is not None and _is_personal_step(step):
        return ""

    entry = load().get("patterns", {}).get(key)

    if not entry:
        return ""

    target = rule if isinstance(rule, dict) else step

    if not isinstance(target, dict):
        return ""

    from app.services.groq_service import deterministic_validate_example

    label = str(
        (step or {}).get("rule_name")
        or (step or {}).get("name")
        or ""
    ).strip().lower()

    candidates = [
        correction
        for correction in entry.get("corrections", [])
        if int(correction.get("count", 0)) >= _MIN_CONFIDENCE
        and str(correction.get("accepted") or "").strip()
    ]

    # Same step first: most likely to be relevant as well as valid.
    candidates.sort(
        key=lambda item: (
            str(item.get("step", "")).strip().lower() != label,
            -int(item.get("count", 0)),
        )
    )

    for correction in candidates:

        accepted = str(correction["accepted"]).strip()

        try:
            outcome = deterministic_validate_example(
                example=accepted,
                rule=target,
            )
        except Exception:
            continue

        if outcome.get("valid"):
            return accepted

    return ""


def stats() -> dict:
    """A summary of what has been learned, for inspection."""

    data = load()

    patterns = data.get("patterns", {})

    return {
        "patterns": len(patterns),
        "total_seen": sum(
            int(entry.get("seen", 0))
            for entry in patterns.values()
        ),
        "with_guidance": sum(
            1
            for entry in patterns.values()
            if entry.get("corrections")
        ),
        "withheld": sum(
            int(entry.get("withheld", 0))
            for entry in patterns.values()
        ),
        "path": KNOWLEDGE_PATH,
    }
