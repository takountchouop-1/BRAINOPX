import os
import sys
sys.path.insert(0, r"e:\BRAINOPX\backened")

from app.services import groq_service
from app.services import rule_router_service as rr
from app.services import step_by_step_service as sbs

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


print("=" * 70)
print("FIX 1: deterministic builder tier reachable (now in guided_engine)")
print("=" * 70)

from app.services import guided_engine

# rule=None forces the ladder past the AI tier down to build_example_value()
step = {
    "rule_name": "Tariff Code",
    "task": "Must start with TRF followed by 3 digits",
    "description": "Must start with TRF followed by 3 digits",
    "keywords": [],
}
value = guided_engine.prepare_example(step, rule=None, force_new=True)
check(
    "builder tier returns a real example (not the generic fallback)",
    value == "TRF001",
    repr(value),
)
check(
    "example_source recorded as builder",
    step.get("example_source") == "builder",
    repr(step.get("example_source")),
)

print()
print("=" * 70)
print("FIX 2: LLM / rule text escaped before reaching innerHTML")
print("=" * 70)

XSS = '<img src=x onerror=alert(1)>'

check(
    "_esc neutralises markup (rule_router_service)",
    "<img" not in rr._esc(XSS) and "&lt;img" in rr._esc(XSS),
    rr._esc(XSS),
)
check(
    "_esc neutralises markup (step_by_step_service)",
    "<img" not in sbs._esc(XSS) and "&lt;img" in sbs._esc(XSS),
    sbs._esc(XSS),
)
check(
    "_esc falls back to default when value is blank",
    rr._esc("", "Fallback text") == "Fallback text",
    rr._esc("", "Fallback text"),
)

# Full rendered message, as ConfigurationIngest.jsx receives it.
from app.services import step_presenter as _p

blocks = _p.build_failure_message(
    {"rule_name": XSS, "suggested_example": "TRF001"},
    0,
    2,
    {"validation_errors": [XSS]},
    corrected_example="TRF001",
)
msg = sbs._render_blocks(blocks)
check(
    "failure response contains no live markup",
    "<img" not in msg and "&lt;img" in msg,
    msg.replace("\n", " | ")[:90],
)

ok_blocks = _p.build_success_message(
    {"rule_name": XSS},
    0,
    2,
    next_step={"rule_name": XSS, "suggested_example": "TRF001"},
)
sbs_step_msg = sbs._render_blocks(ok_blocks)
check(
    "success response contains no live markup",
    "<img" not in sbs_step_msg and "&lt;img" in sbs_step_msg,
    sbs_step_msg.replace("\n", " | ")[:90],
)

print()
print("=" * 70)
print("FIX 3: known_example short-circuits Groq generation")
print("=" * 70)

calls = {"n": 0}
real = groq_service.generate_rule_example_with_retry


def spy(*a, **kw):
    calls["n"] += 1
    raise AssertionError("Groq example generation should not have been called")


groq_service.generate_rule_example_with_retry = spy

rule = {
    "id": 1,
    "name": "Tariff Code",
    "description": "Must start with TRF followed by 3 digits",
}

try:
    verdict = groq_service.run_rule_workflow(
        rule=rule,
        user_input="TRF042",
        conversation_history=[],
        known_example="TRF001",
    )
    check("no Groq call when known_example supplied", calls["n"] == 0, f"calls={calls['n']}")
    check("valid user input passes", verdict.get("passed") is True, str(verdict.get("passed")))
    check("reused example surfaced", verdict.get("example") == "TRF001", repr(verdict.get("example")))
    check("example marked valid", verdict.get("example_valid") is True, str(verdict.get("example_valid")))

    bad = groq_service.run_rule_workflow(
        rule=rule,
        user_input="XYZ999",
        conversation_history=[],
        known_example="TRF001",
    )
    check("invalid user input fails", bad.get("passed") is False, str(bad.get("passed")))
    check(
        "failure carries a corrective suggestion",
        bad.get("suggested_fix") == "TRF001",
        repr(bad.get("suggested_fix")),
    )
    check(
        "failure explains the problem",
        bool(bad.get("validation_errors")),
        str(bad.get("validation_errors"))[:80],
    )
    check("still no Groq call on the failure path", calls["n"] == 0, f"calls={calls['n']}")
finally:
    groq_service.generate_rule_example_with_retry = real

print()
print("=" * 70)
print("RESULT:", "ALL PASSED" if not FAIL else f"{len(FAIL)} FAILED -> {FAIL}")
print("=" * 70)
sys.exit(1 if FAIL else 0)
