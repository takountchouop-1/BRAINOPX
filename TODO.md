# TODO: Generate & store example input per rule at task creation

## Goal
At task creation time (when a rules document is uploaded), automatically
understand each rule/step and generate + store the corresponding correct
example input for each different step, based on that step's rule/format.

## Steps
- [ ] 1. Add `build_rules_with_examples()` helper in example_utils.py that
         enriches each rule with its correct `example_input` value.
- [ ] 2. Update skill_engine_service.py to enrich parsed rules with examples
         when caching + when returning rules (get_rules_for_task, start_run).
- [ ] 3. Update tasks.py create_task/update_task to parse rules and store
         enriched rules (with example_input) in category_metadata.
- [ ] 4. Verify with a quick test that each rule gets a correct example.
