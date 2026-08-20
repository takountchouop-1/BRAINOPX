"""
Free-text fields (address, state, country, gift wrap, PO number, ...)
carried no semantic type and no explicit constraints, so
deterministic_validate_example had nothing to check them with and
accepted anything — a Shipping Address of "09", a Shipping Country of
"/", a Purchase Order Number of "M,./MN". Meanwhile typed fields
(dates, enums, integers) already rejected garbage correctly, so the
gap was specific to fields with no recognised semantic type.

See docs/ASSISTANT_DEFECTS.md, defect 22.
"""
import sys

sys.path.insert(0, r"e:\BRAINOPX\backened")

from app.services.groq_service import deterministic_validate_example

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


def rejected(rule, value):
    verdict = deterministic_validate_example(example=value, rule=rule)
    return not verdict.get("valid"), "; ".join(verdict.get("errors", []) or [])


def accepted(rule, value):
    verdict = deterministic_validate_example(example=value, rule=rule)
    return bool(verdict.get("valid")), "; ".join(verdict.get("errors", []) or [])


print("=" * 76)
print("Garbage rejected for unrecognised free-text fields")
print("=" * 76)

ADDRESS = {"name": "Shipping Address", "example_input": "12 Rue Bastos, Yaounde", "constraints": {}}
STATE = {"name": "Shipping State", "example_input": "1", "constraints": {}}
COUNTRY = {"name": "Shipping Country", "example_input": "Cameroon", "constraints": {}}
GIFT_WRAP = {"name": "Gift Wrap", "example_input": "1", "constraints": {}}
PO_NUMBER = {"name": "Purchase Order Number", "example_input": "1", "constraints": {}}
POSTAL = {"name": "Shipping Postal", "example_input": "BP 1234", "constraints": {}}

ok, detail = rejected(ADDRESS, "09")
check("digits-only rejected where the example has letters (address)", ok, detail)

ok, detail = rejected(STATE, "/")
check("bare punctuation rejected (state)", ok, detail)

ok, detail = rejected(COUNTRY, "/")
check("bare punctuation rejected (country)", ok, detail)

ok, detail = rejected(GIFT_WRAP, "/")
check("bare punctuation rejected (gift wrap)", ok, detail)

ok, detail = rejected(PO_NUMBER, "M,./MN")
check("punctuation-laced consonant garbage rejected (PO number)", ok, detail)

ok, detail = rejected(POSTAL, "432")
check("digits-only rejected where the example has letters (postal)", ok, detail)

print()
print("=" * 76)
print("Legitimate free-text answers still pass")
print("=" * 76)

ok, detail = accepted({"name": "Shipping City", "example_input": "Yaounde", "constraints": {}}, "douala")
check("ordinary city name accepted", ok, detail)

ok, detail = accepted(PO_NUMBER, "PO-4521")
check("alphanumeric PO number with a dash accepted", ok, detail)

ok, detail = accepted(
    {"name": "Tracking Code", "example_input": "TRK1234", "constraints": {}},
    "TRK4589",
)
check("clean alphanumeric code with no vowels still accepted (no punctuation)", ok, detail)

ok, detail = accepted(
    {"name": "Delivery Instructions", "example_input": "A valid delivery instructions", "constraints": {}},
    "Leave at front desk",
)
check("real delivery instructions accepted", ok, detail)

print()
print("=" * 76)
print("RESULT:", "ALL PASSED" if not FAIL else f"{len(FAIL)} FAILED -> {FAIL}")
print("=" * 76)
sys.exit(1 if FAIL else 0)
