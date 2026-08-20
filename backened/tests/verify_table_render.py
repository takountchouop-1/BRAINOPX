"""
A table step's data is rendered as a table, with failing cells marked,
and user-typed values can never inject markup.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import guided_engine as engine
from app.services import composite_rules as cr
from app.services import step_by_step_service as sbs
from app.services import rule_router_service as rr
from app.services import step_presenter as presenter
from app.services.example_utils import build_rules_with_examples

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


TABLE = {
    "id": 1, "name": "Tariff Lines", "description": "one row per tariff",
    "input_shape": "table", "min_rows": 1,
    "columns": [
        {"name": "Tariff Code",
         "constraints": {"required": True, "prefix": "TRF", "prefix_digit_count": 3}},
        {"name": "Unit Rate",
         "constraints": {"required": True, "format": "number", "min_value": 0}},
        {"name": "Currency",
         "constraints": {"required": True, "allowed_values": ["USD", "XAF"]}},
    ],
}

RULES = build_rules_with_examples([TABLE])


def turn(text):
    steps = engine.build_steps(RULES)
    engine.prepare_example(steps[0], RULES[0], force_new=True)
    return engine.take_turn(
        steps=steps, current_index=0, rules=RULES, user_input=text
    )


print("=" * 74)
print("The example is shown as a table")
print("=" * 74)

steps = engine.build_steps(RULES)
engine.prepare_example(steps[0], RULES[0], force_new=True)
prompt = presenter.build_step_prompt(steps[0], 0, 1)
html = sbs._render_blocks(prompt)

check("a table element is emitted", "<table" in html, "table")
check("every column is a header",
      all(f"<th>{c['name']}</th>" in html for c in TABLE["columns"]), "headers")
check("rows are numbered", 'class="row-number"' in html, "numbered")

print()
print("=" * 74)
print("What the user entered is shown back, with bad cells marked")
print("=" * 74)

result = turn("TRF001, 120.00, USD\nTRF2, abc, EUR")
html = sbs._render_blocks(result["message_blocks"])

check("the submitted rows are rendered", "What you entered" in html, "caption")
check("the good row is present", "<td>TRF001</td>" in html, "row 1")
check("each failing cell is marked", html.count("bad-cell") == 3, str(html.count("bad-cell")))
check("a passing cell is not marked",
      '<td class="bad-cell">TRF001</td>' not in html, "row 1 clean")
check("the per-cell messages remain", "Row 2, Tariff Code" in html, "messages kept")
check("a corrected layout is offered", html.count("<table") == 2, str(html.count("<table")))

print()
print("=" * 74)
print("A wrong row length is marked as a whole row")
print("=" * 74)

html = sbs._render_blocks(turn("TRF001, 120.00")["message_blocks"])
check("the short row is flagged", "bad-row" in html, "row flagged")
check("the shortfall is explained", "expected 3 values" in html, "explained")

print()
print("=" * 74)
print("User-typed values cannot inject markup")
print("=" * 74)

XSS = '<img src=x onerror=alert(1)>'
html = sbs._render_blocks(turn(f"{XSS}, 1, USD")["message_blocks"])

check("no live tag from a cell", "<img" not in html, "escaped")
check("the value is shown escaped", "&lt;img" in html, "visible but inert")

# The same through the skill-engine renderer.
html2 = rr._html_message(turn(f"{XSS}, 1, USD")["message_blocks"])
check("skill-engine renderer also escapes cells", "<img" not in html2, "escaped")
check("skill-engine renderer keeps the table", "<table" in html2, "table kept")

print()
print("=" * 74)
print("Non-table steps are unaffected")
print("=" * 74)

SCALAR = build_rules_with_examples([
    {"id": 1, "name": "Tariff Code",
     "description": "Must start with TRF followed by 3 digits"},
])
steps = engine.build_steps(SCALAR)
engine.prepare_example(steps[0], SCALAR[0], force_new=True)
t = engine.take_turn(steps=steps, current_index=0, rules=SCALAR, user_input="nope")
html = sbs._render_blocks(t["message_blocks"])

check("no table for a single-value step", "<table" not in html, "plain")
check("the ordinary correction is shown", "What is missing" in html, "correction")

print()
print("=" * 74)
print("RESULT:", "ALL PASSED" if not FAIL else f"{len(FAIL)} FAILED -> {FAIL}")
print("=" * 74)
sys.exit(1 if FAIL else 0)
