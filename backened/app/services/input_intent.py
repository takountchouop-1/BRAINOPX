"""
input_intent.py

What the user was trying to do when a value did not satisfy a step.

A rejected input is not always a wrong answer. It can be a question,
a greeting, a remark about something else entirely, or a keyboard
mash. Answering all of those with "What is missing: must start with
TRF" is unhelpful — the user was not attempting a value at all.

This runs ONLY on input that has already failed validation, so a
correct answer can never be misread as a question. The result changes
the wording of the reply and nothing else: the step does not advance,
and the rules behind it stay hidden either way.

Classification is deterministic. No model call is involved in deciding
what the user meant.
"""

import re

# The user tried to answer, and got it wrong.
VALUE = "value"

# A question about this step: what is wanted, what the format is.
QUESTION_STEP = "question_step"

# A question about something this assistant has no knowledge of.
QUESTION_OTHER = "question_other"

# Greetings, thanks, and other conversation.
CHITCHAT = "chitchat"

# Nothing meaningful: key mashing, punctuation, single stray letters.
UNINTELLIGIBLE = "unintelligible"

# Nothing at all.
EMPTY = "empty"


_QUESTION_OPENERS = (
    "what", "whats", "what's", "how", "why", "who", "when", "where",
    "which", "can you", "could you", "would you", "do you", "does",
    "is it", "are you", "should i", "shall i", "tell me", "explain",
    "help", "i need help", "i don't", "i dont", "i do not",
    "give me", "show me", "any idea", "not sure", "no idea",
)

# Words that mean the question is about filling in this step.
_STEP_HELP_WORDS = {
    "format", "example", "mean", "means", "meaning", "enter", "input",
    "value", "supposed", "expect", "expected", "required", "require",
    "here", "this", "step", "field", "put", "type", "write", "fill",
    "provide", "accept", "accepted", "valid", "wrong", "help",
}

_CHITCHAT_PATTERNS = (
    r"^(hi|hey|hello|yo|good\s+(morning|afternoon|evening)|greetings)\b",
    r"^(thanks|thank\s+you|thx|ok|okay|k|cool|nice|great|fine|sure)\b\W*$",
    r"^(bye|goodbye|see\s+you|later)\b",
    r"^(who\s+are\s+you|what\s+are\s+you)\b",
    r"^(test|testing)\W*$",
)


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def is_pure_symbols(text: str) -> bool:
    """
    Nothing but punctuation — "//", "~", "!!!".

    No one types these meaning them as a value, so they are always
    answered as "not understood", however specific a complaint the
    validator could make about them.
    """

    stripped = str(text or "").strip()

    return bool(stripped) and not re.search(r"[A-Za-z0-9]", stripped)


def _step_expects_length(step: dict | None, length: int) -> bool:
    """Whether the step's own rule calls for an answer this short."""

    constraints = (step or {}).get("constraints") or {}

    exact = constraints.get("exact_length")
    if isinstance(exact, int) and exact == length:
        return True

    maximum = constraints.get("max_length")
    if isinstance(maximum, int) and maximum == length:
        return True

    return False


def _looks_unintelligible(text: str, step: dict | None = None) -> bool:
    """
    Nothing a person meant as an answer.

    Deliberately narrow: only very short runs with no vowel, or a
    value made entirely of punctuation. A short real answer that
    merely breaks the rule is a wrong value, not gibberish, and must
    keep getting the corrective message. A step whose own rule asks
    for exactly this many characters (e.g. a single-letter code) is
    never gibberish, however short — it must fall through to the
    validator so a wrong single letter still gets a corrective
    message instead of "not understood".
    """

    stripped = text.strip()

    if not stripped:
        return False

    if not re.search(r"[A-Za-z0-9]", stripped):
        return True

    letters = re.sub(r"[^A-Za-z]", "", stripped)

    # Only judge pure-letter input; anything with digits could be an
    # identifier the user genuinely tried.
    if letters != re.sub(r"\s+", "", stripped):
        return False

    if _step_expects_length(step, len(letters)):
        return False

    if len(letters) < 2:
        return True

    if len(letters) <= 6 and not re.search(r"[aeiou]", letters.lower()):
        return True

    return False


def _is_question(text: str) -> bool:
    lowered = text.strip().lower()

    if not lowered:
        return False

    if lowered.endswith("?"):
        return True

    return any(
        lowered.startswith(opener)
        for opener in _QUESTION_OPENERS
    )


def _mentions_step(text: str, step: dict) -> bool:
    """Whether a question is about the step in front of the user."""

    words = set(_words(text))

    if words & _STEP_HELP_WORDS:
        return True

    label = str(
        (step or {}).get("rule_name")
        or (step or {}).get("name")
        or ""
    )

    label_words = {
        word
        for word in _words(label)
        if len(word) > 2
    }

    return bool(words & label_words)


def classify(text: str, step: dict | None = None) -> str:
    """
    Decide what a failed input was.

    Only call this for input that did not validate.
    """

    value = str(text or "").strip()

    if not value:
        return EMPTY

    for pattern in _CHITCHAT_PATTERNS:
        if re.search(pattern, value.lower()):
            return CHITCHAT

    if _is_question(value):
        return (
            QUESTION_STEP
            if _mentions_step(value, step or {})
            else QUESTION_OTHER
        )

    if _looks_unintelligible(value, step):
        return UNINTELLIGIBLE

    return VALUE
