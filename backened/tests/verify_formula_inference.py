"""
Two real report_analyses templates (a "sales" task and an
"inventory_report_analyses" task) each had a Total/Closing Stock
column whose values were arithmetically consistent with the other
columns on every sample row — but as plain typed numbers, not a live
Excel formula. excel_rule_parser.extract_formula_rules only reads an
actual formula cell, so it found nothing for either template, and an
uploaded file with a genuinely wrong Total/Closing Stock (confirmed
against real uploaded data) passed validation silently.

This exercises validation_service.infer_formula_rules: it looks for a
cross-column arithmetic relationship that holds exactly across every
sample row, from a small curated set of shapes (sum/difference/
product/percentage-discount), rather than fitting arbitrary
coefficients — the one row 3/row 4 problems above needed being
"Closing Stock = Opening Stock + In - Out" and "Total = Quantity *
Unit Price * (1 - Discount / 100)".

A key defect this also has to catch: a single linear identity among N
columns holds just as exactly when rearranged to solve for any one of
its columns, so a naive scan would report N redundant, purely
algebraic restatements of the very same relationship instead of one.
"""
import sys

sys.path.insert(0, r"e:\BRAINOPX\backened")

from app.services.validation_service import infer_formula_rules, validate_data_rows

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


print("=" * 76)
print("1. Inventory template: Closing Stock = Opening Stock + In - Out")
print("=" * 76)

inv_headers = ["Item Code", "Opening Stock", "In", "Out", "Closing Stock"]
inv_template_rows = [
    {"Item Code": "A", "Opening Stock": 100, "In": 50, "Out": 30, "Closing Stock": 120},
    {"Item Code": "B", "Opening Stock": 200, "In": 0, "Out": 50, "Closing Stock": 150},
    {"Item Code": "C", "Opening Stock": 50, "In": 100, "Out": 20, "Closing Stock": 130},
    {"Item Code": "D", "Opening Stock": 75, "In": 25, "Out": 25, "Closing Stock": 75},
]

inv_rules = infer_formula_rules(inv_headers, inv_template_rows)
check("exactly one rule found (not 4 algebraic restatements)", len(inv_rules) == 1, str(inv_rules))

inv_rule = inv_rules[0] if inv_rules else {}
check("targets Closing Stock, the rightmost/output column", inv_rule.get("name") == "Closing Stock")
check(
    "operands are Opening Stock, In, Out",
    set(inv_rule.get("operand_columns", {}).values()) == {"Opening Stock", "In", "Out"},
    str(inv_rule.get("operand_columns")),
)

inv_upload_rows = [
    {"_row_number": 2, "Opening Stock": 100, "In": 50, "Out": 30, "Closing Stock": 120},
    {"_row_number": 3, "Opening Stock": 200, "In": 0, "Out": 50, "Closing Stock": 200},  # should be 150
    {"_row_number": 4, "Opening Stock": 50, "In": 100, "Out": 20, "Closing Stock": 130},
]
inv_errors = validate_data_rows(db=None, rows=inv_upload_rows, column_rules=inv_rules)
check(
    "the row with the real mismatch (row 3) is flagged, and only that row",
    [e["row"] for e in inv_errors] == [3] and inv_errors[0]["kind"] == "formula_mismatch",
    str(inv_errors),
)

print()
print("=" * 76)
print("2. Sales template: Total = Quantity * Unit Price * (1 - Discount / 100)")
print("=" * 76)

sales_headers = ["Order ID", "Quantity", "Unit Price", "Discount", "Total"]
sales_template_rows = [
    {"Order ID": "1", "Quantity": 10, "Unit Price": 1200, "Discount": 0, "Total": 12000},
    {"Order ID": "2", "Quantity": 25, "Unit Price": 300, "Discount": 5, "Total": 7125},
    {"Order ID": "3", "Quantity": 50, "Unit Price": 75, "Discount": 10, "Total": 3375},
]

sales_rules = infer_formula_rules(sales_headers, sales_template_rows)
check("exactly one rule found", len(sales_rules) == 1, str(sales_rules))

sales_rule = sales_rules[0] if sales_rules else {}
check("targets Total", sales_rule.get("name") == "Total")
check(
    "operands are Quantity, Unit Price, Discount",
    set(sales_rule.get("operand_columns", {}).values()) == {"Quantity", "Unit Price", "Discount"},
    str(sales_rule.get("operand_columns")),
)

sales_upload_rows = [
    {"_row_number": 2, "Order ID": "1", "Quantity": 10, "Unit Price": 1200, "Discount": 0, "Total": 12000},
    {"_row_number": 3, "Order ID": "2", "Quantity": 25, "Unit Price": 300, "Discount": 5, "Total": 9999},
]
sales_errors = validate_data_rows(db=None, rows=sales_upload_rows, column_rules=sales_rules)
check(
    "the wrong Total is flagged",
    len(sales_errors) == 1 and sales_errors[0]["row"] == 3 and sales_errors[0]["kind"] == "formula_mismatch",
    str(sales_errors),
)
check(
    "the error message attributes it to a sample-data pattern, not a real formula",
    "sample data" in sales_errors[0]["rule_violated"],
    sales_errors[0]["rule_violated"],
)

print()
print("=" * 76)
print("3. No relationship among the columns -> no rule invented (no false positives)")
print("=" * 76)

random_headers = ["A", "B", "C"]
random_rows = [
    {"A": 3, "B": 17, "C": 41},
    {"A": 9, "B": 2, "C": 8},
    {"A": 100, "B": 5, "C": 0.5},
]
check("no spurious rule found", infer_formula_rules(random_headers, random_rows) == [])

print()
print("=" * 76)
print("4. exclude_columns lets a structural formula take precedence")
print("=" * 76)

check(
    "Closing Stock is skipped when already claimed by a structural rule",
    infer_formula_rules(inv_headers, inv_template_rows, exclude_columns={"Closing Stock"}) == [],
)

print()
print(f"{'FAILED: ' + str(FAIL) if FAIL else 'ALL CHECKS PASSED'}")
sys.exit(1 if FAIL else 0)
