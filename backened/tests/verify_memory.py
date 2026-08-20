"""
The assistant learns how users recover from an error and offers it to
the next person — without ever storing personal data.
"""
import os
import sys
import tempfile

sys.path.insert(0, r"e:\BRAINOPX\backened")

from app.services import correction_memory as memory

# Point the knowledge file at a scratch location for the test.
_tmp = tempfile.mkdtemp()
memory.KNOWLEDGE_DIR = _tmp
memory.KNOWLEDGE_PATH = os.path.join(_tmp, "correction_memory.json")

from app.services import guided_engine as engine
from app.services.example_utils import build_rules_with_examples

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


def walk(rules, inputs):
    """Run a fresh walkthrough, returning each turn."""
    steps = engine.build_steps(rules)
    engine.prepare_example(steps[0], rules[0], force_new=True)
    turns = []
    index = 0
    for text in inputs:
        turn = engine.take_turn(
            steps=steps, current_index=index, rules=rules, user_input=text
        )
        index = turn["current_index"]
        turns.append(turn)
        if index >= len(steps):
            break
    return turns


print("=" * 78)
print("Grouping errors by kind, not literal text")
print("=" * 78)

a = memory.signature("Value must be 'TRF' followed by exactly 3 digits.")
b = memory.signature("Value must be 'CUST' followed by exactly 4 digits.")
c = memory.signature("Value must be a date in YYYY-MM-DD format.")

check("same complaint about different rules shares a key", a == b, a)
check("a different complaint gets its own key", a != c, f"{a!r} vs {c!r}")

print()
print("=" * 78)
print("Learning from a user who recovered")
print("=" * 78)

DATE_RULES = build_rules_with_examples([
    {"id": 1, "name": "Start Date",
     "description": "Must be a date in YYYY-MM-DD format"},
])

turns = walk(DATE_RULES, ["17-3-3432", "2027-03-01"])

check("first value rejected", turns[0]["passed"] is False, str(turns[0]["passed"]))
check("second value accepted", turns[1]["passed"] is True, str(turns[1]["passed"]))

data = memory.load()
patterns = data.get("patterns", {})
check("the error was recorded", len(patterns) == 1, str(list(patterns)))

entry = list(patterns.values())[0]
check("the accepted value was stored",
      any(x["accepted"] == "2027-03-01" for x in entry["corrections"]),
      str(entry["corrections"]))
check("the rejected value was stored alongside",
      any(x["rejected"] == "17-3-3432" for x in entry["corrections"]),
      "paired")

print()
print("=" * 78)
print("Offering it to the next user who hits the same error")
print("=" * 78)

turns = walk(DATE_RULES, ["99/99/9999"])
lines = " ".join(turns[0]["message_lines"])

check("the next user is shown what worked", "Others got past this by entering" in lines, lines[:70])
check("the learned value is included", "2027-03-01" in lines, lines[:90])
check("the ordinary correction is still there", "What is missing" in lines, "correction kept")
check("the generated example is still there", "Use this format instead" in lines, "example kept")

print("\n  message the second user sees:")
for line in turns[0]["message_lines"]:
    if line:
        print(f"      {line}")

print()
print("=" * 78)
print("Repeated corrections build confidence")
print("=" * 78)

walk(DATE_RULES, ["bad-date", "2027-03-01"])
entry = list(memory.load()["patterns"].values())[0]
top = entry["corrections"][0]
check("a repeated correction is counted", top["count"] >= 2, str(top["count"]))
check("the error count grew", entry["seen"] >= 2, str(entry["seen"]))

print()
print("=" * 78)
print("Personal data is NEVER stored")
print("=" * 78)

before = len(memory.load()["patterns"])

PERSONAL = build_rules_with_examples([
    {"id": 1, "name": "Email", "description": "Must be a valid email address"},
])
walk(PERSONAL, ["leo", "kengne@gmail.com"])

PHONE = build_rules_with_examples([
    {"id": 1, "name": "Phone", "description": "Must be a valid phone number"},
])
walk(PHONE, ["teh", "+237690000001"])

blob = open(memory.KNOWLEDGE_PATH, encoding="utf-8").read()

check("no email address was written to the file", "kengne@gmail.com" not in blob, "absent")
check("no phone number was written to the file", "690000001" not in blob, "absent")
check("the error was still counted", "withheld" in blob, "counted but withheld")

check(
    "no guidance is offered on a personal step",
    memory.guidance_for(
        {"validation_errors": ["Value must be a valid email address."]},
        {"rule_name": "Email"},
    ) == "",
    "withheld",
)

print()
print("=" * 78)
print("A value that merely looks personal is skipped too")
print("=" * 78)

check("an address-like value is caught", memory._looks_personal("a@b.com"), "at sign")
check("a long digit run is caught", memory._looks_personal("237690000001"), "digits")
check("an ordinary code is not", memory._looks_personal("TRF001") is False, "kept")
check("a date is not", memory._looks_personal("2027-03-01") is False, "kept")

print()
print("=" * 78)
print("A broken or missing file is survivable")
print("=" * 78)

with open(memory.KNOWLEDGE_PATH, "w", encoding="utf-8") as fh:
    fh.write("{ this is not json")

check("a corrupt file reads as empty", memory.load()["patterns"] == {}, "recovered")

os.remove(memory.KNOWLEDGE_PATH)
check("a missing file reads as empty", memory.load()["patterns"] == {}, "recovered")

turns = walk(DATE_RULES, ["nope"])
check(
    "a walkthrough still works with no knowledge file",
    "What is missing" in " ".join(turns[0]["message_lines"]),
    "unaffected",
)

print()
print("=" * 78)
print("RESULT:", "ALL PASSED" if not FAIL else f"{len(FAIL)} FAILED -> {FAIL}")
print("=" * 78)
sys.exit(1 if FAIL else 0)
