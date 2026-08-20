"""
Input that is not an attempt at the value must get an answer about
what the user actually did — never the "what is missing" correction,
and never a leak of the rule.
"""
import os
import sys

sys.path.insert(0, r"e:\BRAINOPX\backened")

from app.services import guided_engine as engine
from app.services import input_intent
from app.services.example_utils import build_rules_with_examples, build_example_value

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


# build_rules_with_examples() now asks Groq for each rule's example.
# Stubbed here so this test stays deterministic and offline — it is
# about input-intent classification, not about what Groq returns —
# while still exercising the real code path with the same value the
# old deterministic builder used to produce.
import app.services.groq_service as groq_service_module


def _fake_generate_example(rule, max_retries=None):
    example = build_example_value(rule)
    return {
        "success": bool(example),
        "valid": bool(example),
        "source": "ai",
        "example": example,
        "explanation": "stubbed for tests",
        "constraints": {},
        "validation": None,
        "validation_reason": "",
        "attempt": 1,
        "attempts": [],
        "fallback_used": False,
    }


groq_service_module.generate_rule_example_with_retry = _fake_generate_example

RULES = build_rules_with_examples([
    {"id": 1, "name": "Tariff Code",
     "description": "Must start with TRF followed by 3 digits"},
    {"id": 2, "name": "Unit Rate",
     "description": "Must be a positive number with 2 decimal places"},
])


def turn(text):
    steps = engine.build_steps(RULES)
    engine.prepare_example(steps[0], RULES[0], force_new=True)
    return engine.take_turn(
        steps=steps, current_index=0, rules=RULES, user_input=text
    )


print("=" * 78)
print("Classification of failed input")
print("=" * 78)

CASES = [
    ("",                              input_intent.EMPTY),
    ("what format should I use?",     input_intent.QUESTION_STEP),
    ("what do you mean",              input_intent.QUESTION_STEP),
    ("help",                          input_intent.QUESTION_STEP),
    ("who is the president of France?", input_intent.QUESTION_OTHER),
    ("what is the weather today?",    input_intent.QUESTION_OTHER),
    ("hello",                         input_intent.CHITCHAT),
    ("thanks",                        input_intent.CHITCHAT),
    ("who are you",                   input_intent.CHITCHAT),
    ("!!!",                           input_intent.UNINTELLIGIBLE),
    ("x",                             input_intent.UNINTELLIGIBLE),
    ("xkcdfg",                        input_intent.UNINTELLIGIBLE),
    ("TRF9",                          input_intent.VALUE),
    ("ABC123",                        input_intent.VALUE),
    ("leo",                           input_intent.VALUE),
    ("Premium Tariff",                input_intent.VALUE),
]

for text, expected in CASES:
    got = input_intent.classify(text, {"rule_name": "Tariff Code"})
    check(f"{text!r:34} -> {expected}", got == expected, got)

print()
print("=" * 78)
print("A CORRECT answer is never intercepted")
print("=" * 78)

for good in ("TRF001", "TRF999"):
    result = turn(good)
    check(f"{good!r} accepted", result["passed"] is True, str(result["passed"]))
    check(f"{good!r} advances", result["current_index"] == 1, str(result["current_index"]))

print()
print("=" * 78)
print("What the user is told")
print("=" * 78)

for text in ("TRF9", "what format should I use?", "who is the president of France?",
             "hello", "!!!", ""):
    result = turn(text)
    lines = [ln for ln in result["message_lines"] if ln]
    print(f"\n  input {text!r}  (intent={result.get('intent')})")
    for line in lines:
        print(f"      {line}")

print()
print("=" * 78)
print("Off-track input is handled differently from a wrong value")
print("=" * 78)

wrong = turn("TRF9")
check("a wrong value gets the correction", "What is missing" in " ".join(wrong["message_lines"]), "correction")
check("a wrong value counts as an attempt", wrong["step"]["attempts"] == 1, str(wrong["step"]["attempts"]))
check("a wrong value is marked handled", wrong.get("handled") is True, str(wrong.get("handled")))

for text in ("what format should I use?", "hello", "!!!", "", "who is the president of France?"):
    result = turn(text)
    joined = " ".join(result["message_lines"])
    check(
        f"{text!r:34} does not get the correction text",
        "What is missing" not in joined,
        joined[:52],
    )
    check(
        f"{text!r:34} does not count as an attempt",
        result["step"]["attempts"] == 0,
        str(result["step"]["attempts"]),
    )
    check(
        f"{text!r:34} stays on the same step",
        result["current_index"] == 0,
        str(result["current_index"]),
    )

print()
print("=" * 78)
print("Each case says something specific")
print("=" * 78)

EXPECTED_TEXT = [
    ("who is the president of France?", "do not have information about that"),
    ("!!!",                             "did not understand"),
    ("",                                "have not entered anything"),
    ("what format should I use?",        "what this step needs"),
    ("hello",                            "carry on with the task"),
]

for text, phrase in EXPECTED_TEXT:
    joined = " ".join(turn(text)["message_lines"]).lower()
    check(f"{text!r:34} says {phrase!r}", phrase.lower() in joined, joined[:60])

print()
print("=" * 78)
print("The step is still restated, and the rule still hidden")
print("=" * 78)

for text in ("what format should I use?", "hello", "!!!", "who is the president of France?"):
    joined = " ".join(turn(text)["message_lines"])
    check(f"{text!r:34} repeats what to provide", "Enter the Tariff Code" in joined, "restated")
    check(f"{text!r:34} repeats the example", "TRF001" in joined, "example shown")
    check(
        f"{text!r:34} does not quote the rule",
        "followed by 3 digits" not in joined,
        "hidden",
    )

print()
print("=" * 78)
print("A wrong-looking value still gets the useful correction")
print("=" * 78)

# 'bh' on a rate step is a wrong number, not gibberish: the validator
# has something specific to say, so say it.
RATE = build_rules_with_examples([
    {"id": 1, "name": "Unit Rate",
     "description": "Must be a positive number with 2 decimal places"},
])


def rate_turn(text):
    steps = engine.build_steps(RATE)
    engine.prepare_example(steps[0], RATE[0], force_new=True)
    return engine.take_turn(
        steps=steps, current_index=0, rules=RATE, user_input=text
    )


for text, expect_correction in [
    ("bh", True),
    ("r", True),
    ("12", True),
    ("//", False),
    ("~", False),
    ("!!!", False),
]:
    result = rate_turn(text)
    joined = " ".join(result["message_lines"])
    got = "What is missing" in joined
    check(
        f"{text!r:6} -> {'correction' if expect_correction else 'not understood'}",
        got == expect_correction,
        joined.split("\n")[0][:58],
    )

check(
    "'bh' is told what is actually wrong",
    "valid number" in " ".join(rate_turn("bh")["message_lines"]),
    " ".join(rate_turn("bh")["message_lines"])[:70],
)
check(
    "'12' is told about the decimal places",
    "decimal place" in " ".join(rate_turn("12")["message_lines"]),
    " ".join(rate_turn("12")["message_lines"])[:70],
)
check(
    "pure punctuation is still not understood",
    "did not understand" in " ".join(rate_turn("//")["message_lines"]),
    " ".join(rate_turn("//")["message_lines"])[:70],
)

print()
print("=" * 78)
print("A failure inside the check reports an error, not a wrong value")
print("=" * 78)

from app.services import guided_engine as ge

real = ge.run_rule_workflow


def boom(*a, **kw):
    raise RuntimeError("validator exploded")


ge.run_rule_workflow = boom
try:
    result = turn("TRF001")
    joined = " ".join(result["message_lines"])
    check("an internal failure is reported as an error", "hit an error" in joined, joined[:60])
    check("the user is not told their value was wrong",
          "What is missing" not in joined, "no correction")
    check("nothing advances", result["current_index"] == 0, str(result["current_index"]))
    check("verdict marked error", result["public_verdict"]["status"] == "error",
          result["public_verdict"]["status"])
finally:
    ge.run_rule_workflow = real

print()
print("=" * 78)
print("RESULT:", "ALL PASSED" if not FAIL else f"{len(FAIL)} FAILED -> {FAIL}")
print("=" * 78)
sys.exit(1 if FAIL else 0)
