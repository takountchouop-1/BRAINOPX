"""
Excel templates commonly encode real business rules in layers the
system never read before this: a dropdown restricting a column to
approved values, a numeric range validation, and a formula column like
"Total = Quantity * Unit Price". Previously only the header row and a
guess from the template's own sample data were extracted — formulas
and data validation were silently ignored.

This exercises app.services.excel_rule_parser directly against a
template built with openpyxl (a list validation, a whole-number range
validation, and a formula column), then feeds the extracted rules into
validation_service.validate_data_rows end to end to confirm an
uploaded row that violates the dropdown, the range, or the formula is
actually flagged — and a clean row is not.
"""
import os
import sys
import tempfile

sys.path.insert(0, r"e:\BRAINOPX\backened")

import openpyxl
from openpyxl.worksheet.datavalidation import DataValidation

from app.services import excel_rule_parser
from app.services import validation_service

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


print("=" * 76)
print("Building a template: Order Id | Quantity | Unit Price | Total | Status")
print("=" * 76)

wb = openpyxl.Workbook()
ws = wb.active
ws.append(["Order Id", "Quantity", "Unit Price", "Total", "Status"])
ws.append([1, 10, 5, "=B2*C2", "Approved"])

status_dv = DataValidation(type="list", formula1='"Approved,Rejected,Pending"', allow_blank=True)
ws.add_data_validation(status_dv)
status_dv.add("E2:E1000")

qty_dv = DataValidation(type="whole", operator="between", formula1=1, formula2=100, allow_blank=True)
ws.add_data_validation(qty_dv)
qty_dv.add("B2:B1000")

fd, template_path = tempfile.mkstemp(suffix=".xlsx")
os.close(fd)
wb.save(template_path)

try:
    print()
    print("=" * 76)
    print("1. extract_data_validation_rules reads the dropdown and the range")
    print("=" * 76)

    dv_rules = excel_rule_parser.extract_data_validation_rules(template_path)
    dv_by_name = {r["name"]: r for r in dv_rules}

    check(
        "Status: allowed_values from the list validation",
        dv_by_name.get("Status", {}).get("allowed_values") == ["Approved", "Rejected", "Pending"],
        str(dv_by_name.get("Status", {}).get("allowed_values")),
    )
    check(
        "Quantity: min_value 1 from the whole-number range",
        dv_by_name.get("Quantity", {}).get("min_value") == 1,
        str(dv_by_name.get("Quantity")),
    )
    check(
        "Quantity: max_value 100 from the whole-number range",
        dv_by_name.get("Quantity", {}).get("max_value") == 100,
        str(dv_by_name.get("Quantity")),
    )

    print()
    print("=" * 76)
    print("2. extract_formula_rules reads Total = Quantity * Unit Price")
    print("=" * 76)

    formula_rules = excel_rule_parser.extract_formula_rules(template_path)
    check("exactly one formula rule found", len(formula_rules) == 1, str(formula_rules))

    total_rule = formula_rules[0] if formula_rules else {}
    check("formula rule targets Total", total_rule.get("name") == "Total")
    check(
        "formula rule's operands are Quantity and Unit Price",
        set(total_rule.get("operand_columns", {}).values()) == {"Quantity", "Unit Price"},
        str(total_rule.get("operand_columns")),
    )

    print()
    print("=" * 76)
    print("3. extract_excel_business_rules combines both, feeds validate_data_rows")
    print("=" * 76)

    extracted = excel_rule_parser.extract_excel_business_rules(template_path)
    column_rules = extracted["column_rules"]
    check(
        "combined column_rules has the 2 validation rules + 1 formula rule",
        len(column_rules) == 3,
        str(column_rules),
    )

    rows = [
        {  # clean row: Total really is Quantity * Unit Price, Status/Quantity in range
            "_row_number": 2, "Order Id": 1, "Quantity": 10, "Unit Price": 5,
            "Total": 50, "Status": "Approved",
        },
        {  # Total doesn't match the template's own formula (should be 80)
            "_row_number": 3, "Order Id": 2, "Quantity": 4, "Unit Price": 20,
            "Total": 999, "Status": "Approved",
        },
        {  # Quantity above the template's max, Status not one of the allowed values
            "_row_number": 4, "Order Id": 3, "Quantity": 200, "Unit Price": 1,
            "Total": 200, "Status": "Cancelled",
        },
    ]

    errors = validation_service.validate_data_rows(db=None, rows=rows, column_rules=column_rules)
    by_row_kind = {(e["row"], e["kind"]) for e in errors}

    check("clean row (2) produced no errors", all(e["row"] != 2 for e in errors), str(errors))
    check(
        "row 3: formula_mismatch on Total",
        (3, "formula_mismatch") in by_row_kind,
        str(by_row_kind),
    )
    check(
        "row 4: out_of_range on Quantity",
        (4, "out_of_range") in by_row_kind,
        str(by_row_kind),
    )
    check(
        "row 4: invalid_choice on Status",
        (4, "invalid_choice") in by_row_kind,
        str(by_row_kind),
    )
    check("exactly 3 errors total", len(errors) == 3, str(errors))

finally:
    os.remove(template_path)

print()
print(f"{'FAILED: ' + str(FAIL) if FAIL else 'ALL CHECKS PASSED'}")
sys.exit(1 if FAIL else 0)
