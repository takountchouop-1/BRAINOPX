"""
excel_rule_parser.extract_vba_source only ever returned raw macro
text — useful for a human to read, but nothing turned it into
reviewable business-logic rules, and nothing stored it anywhere a
task's own rules could be found alongside it.

This exercises the full path added for that: tasks.py's
_extract_and_merge_excel_rules now also feeds any extracted VBA source
through groq_service.parse_rules_to_json (the same parser a rules
document gets) and returns the result as "vba_business_rules";
_merge_excel_metadata then persists both the raw source and the
interpreted rules onto category_metadata, under excel_vba_text and
excel_vba_business_rules respectively, without touching parsed_rules
from any unrelated rules document (which _store_rules_with_examples
would otherwise overwrite wholesale).

VBA_Parser itself is not exercised here (that needs a real
vbaProject.bin, which nothing in this environment can author) —
excel_rule_parser.extract_vba_source and groq_service._call_groq are
both stubbed, so this proves the wiring between "VBA text found" and
"business-logic rules stored", independent of oletools' own parsing.
"""
import json
import os
import sys

sys.path.insert(0, r"e:\BRAINOPX\backened")

import openpyxl

import app.routers.tasks as tasks_module
from app.services import excel_rule_parser
from app.services import groq_service

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


FAKE_VBA_SOURCE = """
Sub ValidateOrder()
    If Range("Quantity").Value < 0 Then
        MsgBox "Quantity cannot be negative"
    End If
    If Range("Quantity").Value > 500 Then
        MsgBox "Quantity cannot exceed 500 units per order"
    End If
End Sub
"""

FAKE_GROQ_RULES = [
    {
        "id": 1,
        "name": "Quantity",
        "description": "Order quantity validated by the ValidateOrder macro.",
        "task": "Please provide the quantity.",
        "data_type": "integer",
        "keywords": ["quantity"],
        "expected_outcome": "A quantity between 0 and 500 is entered.",
        "constraints": {"required": True, "min_value": 0, "max_value": 500},
    }
]


def fake_extract_vba_source(path):
    return FAKE_VBA_SOURCE


def fake_call_groq(system_prompt, user_prompt, temperature=0.0, max_tokens=5000):
    return json.dumps(FAKE_GROQ_RULES)


print("=" * 76)
print("Wiring: extract_vba_source -> parse_rules_to_json -> category_metadata")
print("=" * 76)

wb = openpyxl.Workbook()
ws = wb.active
ws.append(["Quantity", "Unit Price", "Total"])
ws.append([10, 5, 50])
template_path = "tmp_vba_business_logic_test.xlsx"
wb.save(template_path)

original_extract_vba = excel_rule_parser.extract_vba_source
original_call_groq = groq_service._call_groq
excel_rule_parser.extract_vba_source = fake_extract_vba_source
groq_service._call_groq = fake_call_groq

try:
    result = tasks_module._extract_and_merge_excel_rules(template_path, [])

    check("raw VBA source is returned", result["vba_text"] == FAKE_VBA_SOURCE)
    check(
        "VBA source was parsed into business-logic rules",
        result["vba_business_rules"] == FAKE_GROQ_RULES,
        str(result["vba_business_rules"]),
    )

    class _FakeTask:
        category_metadata = None

    task = _FakeTask()
    tasks_module._merge_excel_metadata(task, result)
    stored = json.loads(task.category_metadata)

    check(
        "excel_vba_text persisted on category_metadata",
        stored.get("excel_vba_text") == FAKE_VBA_SOURCE,
    )
    check(
        "excel_vba_business_rules persisted on category_metadata",
        stored.get("excel_vba_business_rules") == FAKE_GROQ_RULES,
        str(stored.get("excel_vba_business_rules")),
    )

    print()
    print("=" * 76)
    print("No VBA found -> nothing invented, no metadata written")
    print("=" * 76)

    excel_rule_parser.extract_vba_source = lambda path: ""
    empty_result = tasks_module._extract_and_merge_excel_rules(template_path, [])
    check("vba_text empty", empty_result["vba_text"] == "")
    check("vba_business_rules empty", empty_result["vba_business_rules"] == [])

    empty_task = _FakeTask()
    tasks_module._merge_excel_metadata(empty_task, empty_result)
    check(
        "category_metadata left untouched when there's nothing to store",
        empty_task.category_metadata is None,
    )

finally:
    excel_rule_parser.extract_vba_source = original_extract_vba
    groq_service._call_groq = original_call_groq
    os.remove(template_path)

print()
print(f"{'FAILED: ' + str(FAIL) if FAIL else 'ALL CHECKS PASSED'}")
sys.exit(1 if FAIL else 0)
