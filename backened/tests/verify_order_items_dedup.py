"""
A child-table rule (e.g. "Order Items", covering order_item_id,
product_id, quantity, ...) was being asked for twice: once as the
composite table itself, and then again one column at a time, because
the deterministic SQL parser's per-column rules never matched the
table rule's columns by name. A second, unrelated bug compounded it:
every SQL-derived rule's boilerplate description ("...satisfying the
column's SQL constraints...") tripped a `\\bcolumns?\\b` regex meant to
detect real table-shaped wording, so those duplicate scalar steps
displayed "enter one row per line" with a single-value example.

See docs/ASSISTANT_DEFECTS.md, defect 23.
"""
import sys

sys.path.insert(0, r"e:\BRAINOPX\backened")

from app.services import composite_rules as cr
from app.services import groq_service as gs

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


print("=" * 76)
print("A scalar SQL-derived rule is not misread as a table")
print("=" * 76)

scalar_rule = {
    "name": "Order Item Id",
    "description": "SQL constraint for `order_item_id` extracted from the uploaded document.",
    "task": "Please provide your value for Order Item Id.",
    "expected_outcome": "A value satisfying the column's SQL constraints is provided.",
    "constraints": {},
}
check("possessive 'column's' does not trigger table shape",
      cr.input_shape(scalar_rule) == "scalar", cr.input_shape(scalar_rule))

real_table = {
    "name": "Order Items",
    "description": "Enter one row per line, with these values separated by commas.",
    "columns": [{"name": "Order Item ID"}, {"name": "Product ID"}],
}
check("a real table rule still detects as table",
      cr.input_shape(real_table) == "table", cr.input_shape(real_table))

plural_columns_text = {
    "name": "Line Items",
    "description": "Provide values for all the columns listed below, one row per entry.",
}
check("an actual plural 'columns' mention still detects as table",
      cr.input_shape(plural_columns_text) == "table", cr.input_shape(plural_columns_text))

print()
print("=" * 76)
print("SQL-derived per-column rules merge into the table, not beside it")
print("=" * 76)

order_items_table = gs._normalize_parsed_rule(
    {
        "name": "Order Items",
        "input_shape": "table",
        "columns": [
            {"name": "Order Item ID"},
            {"name": "Order ID"},
            {"name": "Product ID"},
            {"name": "Quantity"},
            {"name": "Unit Price"},
            {"name": "Line Total"},
        ],
    },
    1,
)

sql_rules = [
    {"name": "Created At", "data_type": "date", "constraints": {"format": "date"}, "keywords": ["created_at"]},
    {"name": "Order Item Id", "data_type": "text", "constraints": {}, "keywords": ["order_item_id"]},
    {"name": "Product Id", "data_type": "text", "constraints": {}, "keywords": ["product_id"]},
    {"name": "Quantity", "data_type": "integer", "constraints": {"format": "integer"}, "keywords": ["quantity"]},
    {"name": "Unit Price", "data_type": "number", "constraints": {"format": "number"}, "keywords": ["unit_price"]},
]

merged = gs._merge_sql_rules([order_items_table], sql_rules)

check("no duplicate top-level steps for columns already in the table",
      [r["name"] for r in merged] == ["Order Items", "Created At"],
      str([r["name"] for r in merged]))

column_constraints = {c["name"]: c.get("constraints") for c in merged[0]["columns"]}
check("Quantity column picked up the SQL-derived integer format",
      (column_constraints.get("Quantity") or {}).get("format") == "integer",
      str(column_constraints.get("Quantity")))
check("Unit Price column picked up the SQL-derived number format",
      (column_constraints.get("Unit Price") or {}).get("format") == "number",
      str(column_constraints.get("Unit Price")))

print()
print("=" * 76)
print("A column renamed by the model still matches via the raw SQL identifier")
print("=" * 76)

renamed_table = gs._normalize_parsed_rule(
    {"name": "Order Items", "input_shape": "table", "columns": [{"name": "Item Ref"}]},
    1,
)
renamed_sql_rules = [
    {
        "name": "Item Ref",
        "data_type": "text",
        "constraints": {"min_length": 3},
        "keywords": ["order_item_id", "item ref"],
    },
]
renamed_merged = gs._merge_sql_rules([renamed_table], renamed_sql_rules)

check("still one top-level rule, not two",
      len(renamed_merged) == 1, str([r["name"] for r in renamed_merged]))
check("constraint reached the column despite the name mismatch",
      renamed_merged[0]["columns"][0]["constraints"].get("min_length") == 3,
      str(renamed_merged[0]["columns"][0]["constraints"]))

print()
print("=" * 76)
print("RESULT:", "ALL PASSED" if not FAIL else f"{len(FAIL)} FAILED -> {FAIL}")
print("=" * 76)
sys.exit(1 if FAIL else 0)
