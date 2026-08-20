"""
Run the PRODUCT SALES transcript through the real ConfigurationIngest
path (init_workflow -> process_step_input) and report which rule each
step is actually validated against.
"""
import json
import os
import sys

sys.path.insert(0, r"e:\BRAINOPX\backened")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import User, ConfigurationTask, ConfigurationRequest
from app.services import step_by_step_service as sbs
from app.services import guided_engine as engine
from app.services.example_utils import build_rules_with_examples
from app.services.groq_service import (
    deterministic_validate_example,
    _infer_semantic_type,
    _get_effective_constraints,
)

RULES = build_rules_with_examples([
    {"id": 1, "name": "Customer ID", "description": "Must start with CUST- followed by 4 digits"},
    {"id": 2, "name": "Customer Name", "description": ""},
    {"id": 3, "name": "Email", "description": ""},
    {"id": 4, "name": "Phone", "description": ""},
    {"id": 5, "name": "Address", "description": ""},
    {"id": 6, "name": "Order ID", "description": ""},
])

TRANSCRIPT = ["CUST-3245", "corps", "leo", "teh", "ewr", "ewew"]

print("=" * 78)
print("A. Direct validation (what verify_field_names tests)")
print("=" * 78)
for rule, value in zip(RULES, TRANSCRIPT):
    v = deterministic_validate_example(example=value, rule=rule)
    print(f"  {rule['name']:15} {value!r:12} "
          f"{'accepted' if v.get('valid') else 'REJECTED':9} "
          f"type={_infer_semantic_type(rule, _get_effective_constraints(rule))!r}")

print()
print("=" * 78)
print("B. Through the engine: which rule does each step resolve to?")
print("=" * 78)

steps = engine.build_steps(RULES)

for index, step in enumerate(steps):
    resolved = engine.find_rule(RULES, step.get("rule_id"))
    print(f"  step {index+1} rule_id={step.get('rule_id')!r:6} "
          f"step.rule_name={step.get('rule_name')!r:16} "
          f"resolved={'None -> falls back to step' if resolved is None else repr(resolved.get('name'))}")

print()
print("  Does a step carry a 'name' key the validator can read?")
print(f"    'name' in step: {'name' in steps[0]}")
print(f"    keys: {sorted(k for k in steps[0] if 'name' in k)}")

print()
print("=" * 78)
print("C. Full ConfigurationIngest path")
print("=" * 78)

db_engine = create_engine("sqlite://")
Base.metadata.create_all(bind=db_engine)
db = sessionmaker(bind=db_engine)()

user = User(full_name="U", email="u@x.com", hashed_password="x")
db.add(user)
db.commit()

task = ConfigurationTask(
    name="PRODUCT SALES", category="skill_engine",
    template_filename="t", template_file_path="t", expected_columns="[]",
)
db.add(task)
db.commit()

req = ConfigurationRequest(task_id=task.id, user_id=user.id, status="draft")
db.add(req)
db.commit()

sbs.init_workflow(req, db, RULES)

# What did init_workflow store?
stored = sbs._get_workflow_data(req)
print(f"  workflow rules stored: {len(stored.get('rules', []))}")
first = stored["rules"][0]
print(f"  first stored rule keys: {sorted(first.keys())}")

print()
for index, value in enumerate(TRANSCRIPT):
    result = sbs.process_step_input(req, db, value)
    expected = RULES[index]["name"]
    print(f"  step {index+1} ({expected:14}) {value!r:12} "
          f"passed={str(result['passed']):5} "
          f"step_name={result.get('step_name')!r}")

print()
print("=" * 78)
print("D. What the workflow's stored rules look like to the validator")
print("=" * 78)

for rule in stored.get("rules", []):
    constraints = _get_effective_constraints(rule)
    semantic = _infer_semantic_type(rule, constraints)
    print(f"  {rule.get('name'):15} name={rule.get('name')!r:16} "
          f"type={semantic!r:9} {constraints}")
