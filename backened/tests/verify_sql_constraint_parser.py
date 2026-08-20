"""
The AI assistant previously had no way to read rules written as SQL
DDL/CHECK constraints rather than prose — a document that was only a
CREATE TABLE with CHECK(...) columns produced no usable rules at all
if the model misread it, since there was no deterministic fallback
for SQL the way _infer_text_constraints already is for prose.

This exercises app.services.sql_constraint_parser directly, and then
groq_service.parse_rules_to_json end to end with the Groq call itself
stubbed out entirely — proving the SQL safety net alone is enough to
turn a pure-SQL document into working rules even when the model
returns nothing.
"""
import sys

sys.path.insert(0, r"e:\BRAINOPX\backened")

from app.services import groq_service
from app.services.sql_constraint_parser import extract_rules_from_sql

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


CREATE_TABLE_SQL = """
CREATE TABLE tariff (
    tariff_code VARCHAR(10) NOT NULL CHECK (tariff_code LIKE 'TRF%'),
    tariff_name VARCHAR(50) NOT NULL,
    unit_rate DECIMAL(10,2) NOT NULL CHECK (unit_rate > 0),
    currency VARCHAR(3) NOT NULL CHECK (currency IN ('USD', 'XAF', 'EUR')),
    status VARCHAR(10) CHECK (status IN ('ACTIVE', 'INACTIVE')),
    discount_percent INT CHECK (discount_percent BETWEEN 0 AND 100),
    PRIMARY KEY (tariff_code)
);
"""

print("=" * 76)
print("1. extract_rules_from_sql reads a CREATE TABLE directly")
print("=" * 76)

rules = extract_rules_from_sql(CREATE_TABLE_SQL)
by_name = {r["name"]: r for r in rules}

check("found all 6 columns", len(rules) == 6, str(sorted(by_name)))

tc = by_name.get("Tariff Code", {}).get("constraints", {})
check("tariff_code: required (NOT NULL)", tc.get("required") is True)
check("tariff_code: max_length 10 (VARCHAR(10))", tc.get("max_length") == 10)
check("tariff_code: prefix TRF (LIKE 'TRF%')", tc.get("prefix") == "TRF")
check("tariff_code: unique (PRIMARY KEY)", tc.get("unique") is True)

ur = by_name.get("Unit Rate", {}).get("constraints", {})
check("unit_rate: format number (DECIMAL)", ur.get("format") == "number")
check("unit_rate: min_value 0 (CHECK > 0)", ur.get("min_value") == 0)

cur = by_name.get("Currency", {}).get("constraints", {})
check(
    "currency: allowed_values from CHECK IN (...)",
    cur.get("allowed_values") == ["USD", "XAF", "EUR"],
    str(cur.get("allowed_values")),
)

dp = by_name.get("Discount Percent", {}).get("constraints", {})
check("discount_percent: min_value 0 (BETWEEN)", dp.get("min_value") == 0)
check("discount_percent: max_value 100 (BETWEEN)", dp.get("max_value") == 100)

tn = by_name.get("Tariff Name", {}).get("constraints", {})
check("tariff_name: required (NOT NULL, no CHECK)", tn.get("required") is True)
check("tariff_name: max_length 50", tn.get("max_length") == 50)

print()
print("=" * 76)
print("1b. Regressions found against a real uploaded document (product_inventory)")
print("=" * 76)

# defect 21: an identifier containing the literal substring "and"
# ("quantity_on_hand") was split mid-word by the AND-clause splitter,
# silently dropping its CHECK constraint entirely.
WORDPLAY_SQL = """
CREATE TABLE products (
    quantity_on_hand INT NOT NULL,
    reorder_level INT NOT NULL,
    CONSTRAINT chk_quantity_positive CHECK (quantity_on_hand >= 0),
    CONSTRAINT chk_reorder_level CHECK (reorder_level >= 0)
);
"""

wordplay_rules = extract_rules_from_sql(WORDPLAY_SQL)
wordplay_by_name = {r["name"]: r for r in wordplay_rules}

check(
    "an identifier containing 'and' (quantity_on_hand) is not split mid-word",
    wordplay_by_name.get("Quantity On Hand", {}).get("constraints", {}).get("min_value") == 0,
    str(wordplay_by_name.get("Quantity On Hand", {}).get("constraints")),
)
check(
    "its neighbour column is unaffected",
    wordplay_by_name.get("Reorder Level", {}).get("constraints", {}).get("min_value") == 0,
)

# defect 21: a single CHECK ANDing clauses for three different
# columns folded them into one flat dict attributed to only the
# first column, so the other two silently lost their constraint.
DIMENSIONS_SQL = """
CREATE TABLE products (
    length DECIMAL(8,2),
    width DECIMAL(8,2),
    height DECIMAL(8,2),
    CONSTRAINT chk_dimensions CHECK (length > 0 AND width > 0 AND height > 0)
);
"""

dim_rules = extract_rules_from_sql(DIMENSIONS_SQL)
dim_by_name = {r["name"]: r for r in dim_rules}

for col in ("Length", "Width", "Height"):
    check(
        f"multi-column CHECK: {col} gets its own min_value, not just the first column",
        dim_by_name.get(col, {}).get("constraints", {}).get("min_value") == 0,
        str(dim_by_name.get(col, {}).get("constraints")),
    )

print()
print("=" * 76)
print("2. A bare ALTER TABLE ... ADD CONSTRAINT CHECK, no CREATE TABLE at all")
print("=" * 76)

BARE_CHECK_SQL = """
Employee records must satisfy:

ALTER TABLE employee ADD CONSTRAINT chk_employee_id
    CHECK (employee_id LIKE 'EMP%');

CHECK (employee_email IN ('none'));
"""

bare_rules = extract_rules_from_sql(BARE_CHECK_SQL)
bare_by_name = {r["name"]: r for r in bare_rules}

check(
    "bare ALTER TABLE CHECK produced a rule",
    "Employee Id" in bare_by_name,
    str(sorted(bare_by_name)),
)
check(
    "prefix extracted from the bare CHECK",
    bare_by_name.get("Employee Id", {}).get("constraints", {}).get("prefix") == "EMP",
)

print()
print("=" * 76)
print("3. Non-SQL text produces nothing (no false positives)")
print("=" * 76)

check(
    "plain prose yields no SQL rules",
    extract_rules_from_sql("The tariff code must start with TRF.") == [],
)
check("empty text yields no SQL rules", extract_rules_from_sql("") == [])

print()
print("=" * 76)
print("4. parse_rules_to_json falls back to SQL rules when the model fails")
print("=" * 76)


def _broken_call_groq(*args, **kwargs):
    raise RuntimeError("Groq is unreachable in this test.")


real_call_groq = groq_service._call_groq
groq_service._call_groq = _broken_call_groq

try:
    parsed = groq_service.parse_rules_to_json(CREATE_TABLE_SQL)
finally:
    groq_service._call_groq = real_call_groq

parsed_by_name = {r["name"]: r for r in parsed}

check(
    "rules produced even though the model call raised",
    len(parsed) == 6,
    f"{len(parsed)} rules",
)
check(
    "tariff_code still carries its SQL constraints",
    parsed_by_name.get("Tariff Code", {}).get("constraints", {}).get("prefix") == "TRF",
)
check(
    "every rule has a unique id",
    len({r["id"] for r in parsed}) == len(parsed),
)

print()
print("=" * 76)
print("5. When the model half-understands a column, SQL constraints win")
print("=" * 76)


def _fake_call_groq(*args, **kwargs):
    import json

    # The model found the column but got the prefix wrong (a
    # believable failure mode) and missed the length limit entirely.
    return json.dumps(
        [
            {
                "id": 1,
                "name": "Tariff Code",
                "description": "A tariff identifier.",
                "task": "Please provide your value for Tariff Code.",
                "data_type": "identifier",
                "keywords": ["tariff", "code"],
                "expected_outcome": "A valid tariff code is entered.",
                "constraints": {"required": True, "prefix": "WRONG"},
            }
        ]
    )


groq_service._call_groq = _fake_call_groq

try:
    parsed = groq_service.parse_rules_to_json(CREATE_TABLE_SQL)
finally:
    groq_service._call_groq = real_call_groq

parsed_by_name = {r["name"]: r for r in parsed}
tc = parsed_by_name.get("Tariff Code", {}).get("constraints", {})

check(
    "SQL prefix overrides the model's wrong guess",
    tc.get("prefix") == "TRF",
    str(tc.get("prefix")),
)
check(
    "SQL max_length fills in what the model missed",
    tc.get("max_length") == 10,
    str(tc.get("max_length")),
)
check(
    "columns the model never mentioned still appear",
    "Currency" in parsed_by_name and "Unit Rate" in parsed_by_name,
    str(sorted(parsed_by_name)),
)
check(
    "no duplicate rule for the column both sources named",
    sum(1 for r in parsed if r["name"] == "Tariff Code") == 1,
)

print()
print(f"{'FAILED: ' + str(FAIL) if FAIL else 'ALL CHECKS PASSED'}")
sys.exit(1 if FAIL else 0)
