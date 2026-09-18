"""Diagnose what rule/formula extraction actually finds in stored templates."""
import os
import json

from app.services import excel_rule_parser as xp
from app.services.excel_service import extract_column_headers, read_data_rows
from app.services.validation_service import infer_formula_rules

TEMPLATES = os.path.join("uploads", "templates")

files = sorted(
    f for f in os.listdir(TEMPLATES)
    if f.lower().endswith((".xlsx", ".xlsm"))
)

print(f"Found {len(files)} Excel templates.\n")

totals = {
    "data_validation": 0,
    "formula": 0,
    "cond_formatting": 0,
    "vba": 0,
    "inferred": 0,
    "any": 0,
}

for f in files:
    path = os.path.join(TEMPLATES, f)
    try:
        res = xp.extract_excel_business_rules(path)
        headers = extract_column_headers(path)
        rows = read_data_rows(path)
        inferred = infer_formula_rules(
            headers, rows,
            exclude_columns={r["name"] for r in res["column_rules"] if r.get("rule_type") == "formula"},
        )
    except Exception as e:
        print(f"{f}: ERROR {type(e).__name__}: {e}")
        continue

    dv = [r for r in res["column_rules"] if r.get("rule_type", "cell") == "cell"]
    fm = [r for r in res["column_rules"] if r.get("rule_type") == "formula"]
    notes = res["advisory_notes"]
    vba = res["vba_text"]

    has_any = bool(dv or fm or notes or vba or inferred)
    totals["data_validation"] += len(dv)
    totals["formula"] += len(fm)
    totals["cond_formatting"] += len(notes)
    totals["vba"] += 1 if vba else 0
    totals["inferred"] += len(inferred)
    totals["any"] += 1 if has_any else 0

    print(
        f"{f}\n"
        f"  headers={len(headers)} data_rows={len(rows)} | "
        f"DV={len(dv)} formula={len(fm)} condFmt={len(notes)} vba={bool(vba)} inferred={len(inferred)}"
    )
    for r in dv:
        print(f"    [DV] {json.dumps(r, ensure_ascii=False)[:120]}")
    for r in fm:
        print(f"    [FORMULA] {json.dumps(r, ensure_ascii=False)[:120]}")
    for r in inferred:
        print(f"    [INFERRED] {json.dumps(r, ensure_ascii=False)[:120]}")
    for n in notes:
        print(f"    [CF] {n[:120]}")

print("\nTOTALS:", json.dumps(totals))
print(f"Templates with anything extracted: {totals['any']}/{len(files)}")
