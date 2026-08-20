"""
A field with a generic SQL/text type and no CHECK constraint resolves
to no semantic type at all, so only the baseline punctuation/example
check in deterministic_validate_example ever applied to it — enough to
catch "/" but nothing document-specific, and nothing that adapts when
a brand new document introduces a field type this system has never
named before.

_classify_unresolved_free_text_fields batches every such field in one
document into a single model call and folds the result back into the
existing constraint vocabulary (min_length, max_length, pattern) — the
same vocabulary deterministic_validate_example already checks, so no
new validation branch is ever needed for an unfamiliar field name.

This suite never calls the network: _call_groq is replaced with a
fixed stand-in response, since what's under test is the targeting and
merge logic, not the model's judgement.

See docs/ASSISTANT_DEFECTS.md, defect 23 (adaptability follow-up).
"""
import json
import sys

sys.path.insert(0, r"e:\BRAINOPX\backened")

from app.services import groq_service as gs

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


print("=" * 76)
print("Only genuinely unresolved fields are targeted")
print("=" * 76)

normalized = [
    gs._normalize_parsed_rule(
        {"name": "Shipping Address", "description": "The delivery address", "data_type": "text"}, 1
    ),
    gs._normalize_parsed_rule(
        {"name": "Order ID", "description": "Numeric order id", "data_type": "integer"}, 2
    ),
    gs._normalize_parsed_rule(
        {
            "name": "Order Items",
            "input_shape": "table",
            "columns": [
                {"name": "Product Name"},
                {"name": "Quantity", "constraints": {"format": "integer"}},
            ],
        },
        3,
    ),
]

targets = [t[0]["name"] for t in gs._unresolved_free_text_targets(normalized)]

check("free-text scalar field is targeted", "Shipping Address" in targets, str(targets))
check("free-text table column is targeted", "Product Name" in targets, str(targets))
check("field with a known semantic type is not targeted", "Order ID" not in targets, str(targets))
check("table column that already has a format is not targeted", "Quantity" not in targets, str(targets))

print()
print("=" * 76)
print("Classification result reaches the field, without overriding it")
print("=" * 76)


def fake_call_groq(system_prompt, user_prompt, temperature=0.0, max_tokens=2000):
    fields = json.loads(user_prompt)
    out = []
    for f in fields:
        if f["name"] == "Shipping Address":
            out.append({"name": f["name"], "min_length": 5, "max_length": None, "pattern": None})
        elif f["name"] == "Product Name":
            out.append({"name": f["name"], "min_length": 2, "max_length": None, "pattern": None})
        else:
            out.append({"name": f["name"], "min_length": None, "max_length": None, "pattern": None})
    return json.dumps(out)


original_call_groq = gs._call_groq
gs._call_groq = fake_call_groq

try:
    result = gs._classify_unresolved_free_text_fields(normalized)
finally:
    gs._call_groq = original_call_groq

by_name = {r["name"]: r for r in result}

check("classified min_length reached the scalar field",
      by_name["Shipping Address"]["constraints"].get("min_length") == 5,
      str(by_name["Shipping Address"]["constraints"]))

order_columns = {c["name"]: c for c in by_name["Order Items"]["columns"]}
check("classified min_length reached the table column",
      order_columns["Product Name"]["constraints"].get("min_length") == 2,
      str(order_columns["Product Name"]["constraints"]))
check("column with a pre-existing format is untouched",
      order_columns["Quantity"]["constraints"] == {"format": "integer"},
      str(order_columns["Quantity"]["constraints"]))

print()
print("=" * 76)
print("A bad or failing model response never breaks rule building")
print("=" * 76)


def broken_call_groq(system_prompt, user_prompt, temperature=0.0, max_tokens=2000):
    raise RuntimeError("network down")


gs._call_groq = broken_call_groq

try:
    safe_result = gs._classify_unresolved_free_text_fields(
        [gs._normalize_parsed_rule({"name": "Notes", "description": "Free text", "data_type": "text"}, 1)]
    )
finally:
    gs._call_groq = original_call_groq

check("a model failure leaves rules unchanged rather than raising",
      safe_result[0]["name"] == "Notes", str(safe_result))

print()
print("=" * 76)
print("RESULT:", "ALL PASSED" if not FAIL else f"{len(FAIL)} FAILED -> {FAIL}")
print("=" * 76)
sys.exit(1 if FAIL else 0)
