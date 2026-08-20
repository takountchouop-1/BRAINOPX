"""
Defects from the OPERATION walkthrough transcript.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import correction_memory as memory

_tmp = tempfile.mkdtemp()
memory.KNOWLEDGE_DIR = _tmp
memory.KNOWLEDGE_PATH = os.path.join(_tmp, "correction_memory.json")

from app.services import guided_engine as engine
from app.services.groq_service import (
    deterministic_validate_example,
    _get_effective_constraints,
    _infer_semantic_type,
)
from app.services.example_utils import build_rules_with_examples, build_example_value

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


def walk(rules, inputs):
    steps = engine.build_steps(rules)
    engine.prepare_example(steps[0], rules[0], force_new=True)
    turns, index = [], 0
    for text in inputs:
        t = engine.take_turn(steps=steps, current_index=index,
                             rules=rules, user_input=text)
        index = t["current_index"]
        turns.append(t)
        if index >= len(steps):
            break
    return turns


print("=" * 76)
print("A remembered value is never offered for a different rule")
print("=" * 76)

TRF = build_rules_with_examples([
    {"id": 1, "name": "Tariff Code",
     "description": "Must start with TRF followed by 3 digits"},
])
SCH = build_rules_with_examples([
    {"id": 1, "name": "Unique Operation ID",
     "description": "Must start with SCH followed by 3 digits"},
])

# Someone learns a TRF correction.
walk(TRF, ["TRF9", "TRF432"])

entry = list(memory.load()["patterns"].values())[0]
check("the TRF correction was learned",
      any(c["accepted"] == "TRF432" for c in entry["corrections"]), "stored")

# Someone else now fails an SCH rule with the SAME kind of error.
turns = walk(SCH, ["SCH0032"])
lines = " ".join(turns[0]["message_lines"])

check("TRF432 is NOT offered on an SCH rule", "TRF432" not in lines, lines[:80])
check("the correction is still given",
      "must be 'SCH' followed by exactly 3 digits" in lines.lower()
      or "SCH" in lines, "correction kept")

# A correction learned on the SAME rule is still offered.
walk(SCH, ["SCH0032", "SCH981"])
turns = walk(SCH, ["SCH7777"])
lines = " ".join(turns[0]["message_lines"])
check("a valid same-rule correction IS offered", "SCH981" in lines, lines[:90])

print()
print("=" * 76)
print("A time field is validated, not just demonstrated")
print("=" * 76)

for value, expected in [("21", False), ("9:30", False), ("09:30", True),
                        ("23:59", True), ("25:00", False), ("later", False)]:
    rule = {"name": "Set Start Time", "description": ""}
    got = bool(deterministic_validate_example(example=value, rule=rule).get("valid"))
    check(f"Start Time {value!r} {'accepted' if expected else 'rejected'}",
          got == expected, str(got))

check("the time example still passes its own rule",
      bool(deterministic_validate_example(
          example=build_example_value({"name": "Set Start Time", "description": ""}),
          rule={"name": "Set Start Time", "description": ""}).get("valid")),
      build_example_value({"name": "Set Start Time", "description": ""}))

print()
print("=" * 76)
print("A 'Select ...' field is not asked for a paragraph")
print("=" * 76)

for name in ("Select Operation Type", "Choose Environment", "Set Operation Frequency"):
    rule = {"name": name, "description": ""}
    constraints = _get_effective_constraints(rule)
    check(f"{name!r} not narrative",
          constraints.get("content_type") != "narrative",
          str(constraints.get("content_type")))
    check(f"{name!r} not offered a paragraph",
          "short paragraph" not in build_example_value(rule).lower(),
          build_example_value(rule)[:40])

print()
print("=" * 76)
print("A narrative example does not assume the document is a proposal")
print("=" * 76)

sample = build_example_value({"name": "Operating Notes", "description": ""})
check("no 'for this proposal' in the fallback",
      "for this proposal" not in sample.lower(), sample[:60])

print()
print("=" * 76)
print("A question is never accepted as the content of a prose step")
print("=" * 76)

PROSE = build_rules_with_examples([
    {"id": 1, "name": "Problem Statement", "description": ""},
])

for text, should_pass in [
    ("give me an example need help", False),
    ("what should I write here?", False),
    ("hello there my friend", False),
    ("Support requests take three days to answer.", True),
]:
    turns = walk(PROSE, [text])
    got = turns[0]["passed"]
    check(f"{text[:34]!r:38} {'accepted' if should_pass else 'rejected'}",
          got == should_pass, str(got))

joined = " ".join(walk(PROSE, ["give me an example need help"])[0]["message_lines"])
check("the help request gets a helpful reply",
      "what this step needs" in joined.lower(), joined[:70])

print()
print("=" * 76)
print("A real format step is never second-guessed")
print("=" * 76)

CODE = build_rules_with_examples([
    {"id": 1, "name": "Tariff Code",
     "description": "Must start with TRF followed by 3 digits"},
])
check("a valid code is accepted whatever it reads like",
      walk(CODE, ["TRF404"])[0]["passed"] is True, "accepted")

print()
print("=" * 76)
print("RESULT:", "ALL PASSED" if not FAIL else f"{len(FAIL)} FAILED -> {FAIL}")
print("=" * 76)
sys.exit(1 if FAIL else 0)
