# Assistant defect history

Every defect found in the guided walkthrough, with what caused it, what
fixed it, and the test that now prevents it coming back.

Read this **before** debugging a report of the form *"the assistant gave
a bad example"* or *"the assistant accepted something it should not"*.
Most such reports so far have turned out to be one of the recurring
patterns at the bottom of this file rather than a new problem.

Companion to `backened/knowledge/correction_memory.json`, which is what
the running system learns from users. This file is what *developers*
learn from. Add to it whenever a defect is fixed.

---

## The one pattern behind most defects

> **Any signal used to BUILD an example must also reach the VALIDATOR.**

Four separate bugs were the same mistake: one side of the system knew
something about a rule that the other side did not. The example builder
and the validator each read the rule independently, so they disagreed
about what the rule meant.

When adding a new kind of rule understanding, put it in **constraint
inference** (`groq_service._infer_text_constraints`) so both sides read
it from one place. Do not teach only the builder.

---

## Defects

### 1. Example builder called with the wrong signature

- **Symptom** Steps showed the generic `"A valid value satisfying this rule"` instead of a real example.
- **Cause** `build_example_value(step, ai_suggested_fix="")` — the function takes one argument. The `TypeError` was swallowed by a bare `except Exception`, so the whole deterministic tier silently returned `""`.
- **Fix** Corrected the call. `rule_router_service`.
- **Guard** `verify_fixes.py`

### 2. Model output rendered into the page unescaped

- **Symptom** None visible. Model-generated text and uploaded rule text reached `dangerouslySetInnerHTML`.
- **Cause** `verdict.summary` / `guidance` / `questions` interpolated raw into `ai_response`; `step_by_step_service` emitted `<span>` markup with no escaping at all.
- **Fix** `_esc()` in both services, applied to every dynamic interpolation.
- **Guard** `verify_fixes.py`, `verify_hidden_rules.py`

### 3. An LLM call on every submission

- **Symptom** Slow validation, high Groq spend.
- **Cause** `run_rule_workflow` regenerated an example on every user submission — up to `MAX_RETRIES` calls — to rebuild one the caller already held.
- **Fix** `known_example` parameter; callers pass the step's stored example. Validation was always deterministic; only the example needed the model.
- **Guard** `verify_fixes.py` (spy asserts zero Groq calls)

### 4. Guided sessions unreachable and race-prone

- **Symptom** Older sessions 404'd forever.
- **Cause** Sessions lived inside `SkillEngineRun.results_json` and were found by scanning the user's 10 most recent runs. Writes rewrote the whole blob.
- **Fix** `guided_sessions` table keyed by an indexed `session_id`; ownership checked on the session's own `user_id`.
- **Migration** `migrations/add_guided_sessions_table.py`
- **Guard** `verify_sessions.py` (asserts zero queries against `skill_engine_runs`)

### 5. Two engines that had already diverged

- **Symptom** Advancing a step in ConfigurationIngest showed no example for the next step; SkillEngine showed one.
- **Cause** `rule_router_service` and `step_by_step_service` each had their own copy of the step machine. A fix applied to one did not reach the other.
- **Fix** Extracted `guided_engine`. Both services now only persist; all decisions and wording are shared.
- **Guard** `verify_one_engine.py` (drives both, asserts identical decisions)

### 6. Rules uploaded with a new task were never stored

- **Symptom** *"The assistant does not read the rules for each step."*
- **Cause** `_store_rules_with_examples()` called `build_rules_with_examples` — **never imported** in `tasks.py`. The `NameError` hit a bare `except Exception: return []`, so every task stored zero rules.
- **Fix** Added the import; split the handler so parse failures and build failures log instead of vanishing.
- **Guard** `verify_task_creation.py`

### 7. `route_user_message` 500'd on every call

- **Cause** `route_message_to_rule(rules, user_message)` — the signature is `(user_message, rules)`. `AttributeError: 'list' object has no attribute 'strip'`.
- **Fix** Swapped the arguments.
- **Guard** `verify_hidden_rules.py`

### 8. Examples that failed their own rule

- **Symptom** 9 of 25 rules showed `VALID001`, which the validator rejects as a placeholder — the assistant recommended a value it would refuse.
- **Cause** The builder re-derived rule meaning with its own regexes, independently of the validator. Also missing builders for times, length ranges, `either X or Y`.
- **Fix** `build_example_from_constraints()` reads the validator's own constraints; `build_example_value()` now returns the first candidate that **passes validation for that rule**. `VALID001` removed entirely.
- **Guard** `diagnose_examples.py` (25/25 must pass their own rule)

### 9. Document sections treated as formatted fields

- **Symptom** *"Problem Statement"* offered `VALID001`; `sms` rejected while `price` accepted.
- **Cause** Prose sections yield no constraints, so there was nothing to build an example from and nothing to check.
- **Fix** `content_type: narrative` inferred for section-like rules; sample sentences; substance check (`min_words`). Also stopped rejecting abbreviations (`SMS`, `CRM`) as gibberish.
- **Guard** `verify_narrative.py`

### 10. Field name informed the example but not validation

- **Symptom** `kengne@gmail` accepted at the Email step, rejected in a table column for the same field.
- **Cause** Example builder read the field **name**; validator read only **constraints**. Semantic detection needed the phrase `"email address"`, so a field merely *named* `Email` matched nothing.
- **Fix** `_semantic_from_field_name()` feeds the semantic type, matched on the **head noun** so `Email Template` is not retyped.
- **Guard** `verify_field_names.py`

### 11. A vague `data_type` disabled all validation

- **Symptom** Same document, same run: some fields validated, others accepted anything, with no visible pattern.
- **Cause** `_infer_semantic_type` returned the parser's `data_type` **first and unconditionally**. The parser prompt requires one, so it often wrote `"text"` or `"string"`. The validator has no branch for those, so **every check was skipped**.
- **Fix** A declared type is honoured only if it is in `_KNOWN_SEMANTIC_TYPES`; anything else is treated as no information and inference continues.
- **Guard** `verify_field_names.py`
- **Note** This is the highest-impact defect found. A generic label silently switched validation off.

### 12. Most of each rule was never enforced

- **Symptom** `17-3-3432` accepted for a **YYYY-MM-DD** date; `2020-01-01` accepted for a **future** date; `12` accepted where **2 decimal places** were required; `120.00` accepted as a **percentage**.
- **Cause** No inference for `date_format`, `date_must_be`, `decimal_places`, or numeric ranges. The validator only knew "date" and "number".
- **Fix** Four new inferences feeding both the validator and the builder.
- **Guard** `diagnose_rates_dates.py`

### 13. A hardcoded example expired

- **Symptom** `Future Start Date` offered `2026-01-15` after that date had passed — invalid under its own rule.
- **Cause** Date examples were string literals.
- **Fix** Generated relative to today, in the layout the rule asks for.
- **Guard** `verify_narrative.py` (asserts shape, never a fixed date)

### 14. Only the first step was styled

- **Symptom** Step 1 had a green badge and example panel; every later step was plain text.
- **Cause** `get_step_initial_message` emitted CSS classes; `process_step_input` emitted plain lines. Two places building messages, only one styled.
- **Fix** The presenter tags each line with a role; one renderer maps roles to classes. Also fixed `.workflow-step` being nested inside `.task-title strong`, a selector it can never match.
- **Guard** manual — see `_render_blocks`

### 15. "I did not understand" replaced useful corrections

- **Symptom** `bh` on a rate step got *"I did not understand"* instead of *"must be a valid number"*.
- **Cause** The intent classifier ran on all failed input and overrode the correction.
- **Fix** The override applies only when the validator has **no specific complaint**, or the input is pure punctuation.
- **Guard** `verify_intent.py`

### 16. Learned advice offered for the wrong rule

- **Symptom** A user stuck on an `SCH` code was told *"Others got past this by entering: TRF432"* — a value its own validator rejects.
- **Cause** `correction_memory` groups errors by kind, so `must be 'SCH' followed by 3 digits` and the same complaint about `'TRF'` share one entry. Good for counting; wrong for advice.
- **Fix** A remembered value is offered only if it **validates against the rule in front of the user**, preferring corrections recorded on the same step.
- **Guard** `verify_operation_defects.py`

### 17. A question accepted as the answer

- **Symptom** *"give me an example need help"* was **accepted** as the content of a prose step.
- **Cause** Narrative steps validate on word count alone, so anything long enough passed. Intent classification ran only on *failed* input.
- **Fix** On narrative steps only, an otherwise-passing value that reads as a question or greeting is refused and answered with help. Format steps are untouched — a value satisfying a real format is an answer however it reads.
- **Guard** `verify_operation_defects.py`

### 18. Step / rule key mismatch (`name` vs `rule_name`)

- **Symptom** The guard for defect 17 silently never fired.
- **Cause** Rules carry `name`; guided steps carry `rule_name`. Constraint inference reads `name`, so passing a step made it look like an unnamed rule with no constraints.
- **Fix** Pass the **rule** for constraints and the **step** only for labels; `_looks_like_narrative` now accepts either key.
- **Note** Worth checking whenever a check "does nothing" — a step is not a drop-in for a rule.

### 19. Time fields demonstrated but not validated

- **Symptom** `Set Start Time` showed `09:30` and accepted `21`.
- **Fix** `time` semantic type from the field name, validated as `HH:MM[:SS]`.
- **Guard** `verify_operation_defects.py`

### 20. "Select …" fields asked for a paragraph

- **Symptom** `Select Operation Type` was offered *"A short paragraph setting out the select operation type **for this proposal**"*.
- **Cause** Narrative detection did not exclude choice fields; the fallback sentence assumed every document is a proposal.
- **Fix** A name starting `select|choose|pick|set|enter|specify` is never narrative; fallback wording no longer names a document type.
- **Guard** `verify_operation_defects.py`

### 21. Rules written as SQL constraints were not understood at all

- **Symptom** A rules document written as `CREATE TABLE` / `CHECK(...)` DDL (e.g. "PRODUCT INVENTORY") produced steps that accepted almost anything — a SKU of `/`, a product name of `421` — because the parser had no concept of SQL, only prose.
- **Cause** `parse_rules_to_json` had exactly one path: ask the model to read the document. Unlike natural-language rules, there was no deterministic fallback the way `_infer_text_constraints` already is for prose, so a model that misread or skipped a SQL column left nothing behind.
- **Fix** New `app/services/sql_constraint_parser.py` reads `CREATE TABLE` columns, `NOT NULL`, `PRIMARY KEY`/`UNIQUE`, `VARCHAR(n)` lengths, and `CHECK(...)` (`IN`, `BETWEEN`, `LIKE`, comparisons, `LEN()`) directly, with no model involved, and merges into the model's output — SQL wins on a shared column since it's ground truth, and fills in columns the model dropped. `RULES_PARSER_PROMPT` was also taught to map SQL syntax onto the same constraint schema.
- **Two bugs found once tested against a real uploaded document** (`product inventory.pdf`): (a) `_split_and_clauses`'s AND-splitter used `r"AND\b"` — missing the *leading* boundary — so it split `quantity_on_hand >= 0` into `quantity_on_h` / `and >= 0` mid-identifier, silently dropping the constraint; (b) a single CHECK naming several columns (`CHECK (length > 0 AND width > 0 AND height > 0)`) folded all three into one flat dict attributed to only the first column, so `width`/`height` lost their `min_value` entirely to key collisions. Both confirmed by re-extracting from the actual uploaded PDF, not a synthetic example.
- **Fix for those two** `\bAND\b` / `\bBETWEEN\b` (boundary on both sides); `_parse_check_expression` now returns `{column: constraints}` per clause instead of one flat dict, so an ANDed multi-column CHECK constrains every column it names.
- **Guard** `verify_sql_constraint_parser.py`
- **Note** A field with a real SQL type but no `CHECK` (e.g. `product_name VARCHAR(200) NOT NULL`) genuinely has no content constraint beyond length — that is not a bug, it is the source document under-specifying the column. Do not invent one; ask what the intended constraint is instead.

### 22. Fields with no recognised semantic type accepted almost anything

- **Symptom** In an "ORDER FULFILMENT" walkthrough, `09` was accepted for a Shipping Address whose own example was `12 Rue Bastos, Yaounde`; `/` was accepted for Shipping State, Shipping Country, and Gift Wrap; `M,./MN` was accepted for a Purchase Order Number right after a single `X` was rejected on the same step with a different, vaguer message. Typed fields (dates, enums, integers) validated correctly throughout — the gap was specific to fields `_infer_semantic_type` resolves to nothing for.
- **Cause** A field with no recognised semantic type and no explicit `min_length`/`pattern`/`allowed_values` had nothing checking it beyond the gibberish heuristic, and that heuristic only ran when `len(value) <= 3` — so `M,./MN` (6 characters) skipped it entirely, and pure-digit or pure-punctuation values never matched the heuristic's consonant/vowel test regardless of length. The `X` vs `M,./MN` inconsistency was a side effect of `input_intent` routing short flagged values to a different, vaguer message than everything else.
- **Fix** `deterministic_validate_example` (`groq_service.py`): the gibberish check now also runs at any length when punctuation is present (clean alphanumeric codes like `TRK4589` are still exempt when short-length-only would have missed them); a new baseline check rejects a value with zero letters or digits (pure punctuation, `/`); and when the field's own worked example contains letters, the submitted value must contain letters too, closing the address/postal-style gap without hardcoding field names.
- **Guard** `verify_free_text_gibberish.py`

### 23. A child table's columns were asked for twice, and every SQL-derived scalar rule was silently misread as a table

- **Symptom** In the same walkthrough, step 18 asked for the whole "Order Items" table (one row per line, all six columns), then steps 19–23 asked again, one at a time, for `Created At`, `Order Item Id`, `Product Id`, `Quantity`, `Unit Price` — columns already covered by step 18. Each duplicate step said "Enter one row per line, with values separated by commas" but showed a single scalar example, and a bare scalar answer was accepted as satisfying it.
- **Cause** Two things, compounding: (1) `parse_rules_to_json` merged the model's composite table rule and the deterministic SQL parser's per-column rules by exact rule-name match only — a column already inside the table rule's `columns` list (`"Order Item ID"`) never matches the SQL parser's own rule name for that column (`"Order Item Id"`) in the merge key map, so it was appended as a brand-new top-level rule instead of being recognised as already covered. (2) Every SQL-derived rule shares the boilerplate `expected_outcome` text "...satisfying the **column's** SQL constraints...", and `composite_rules.input_shape()`'s fallback regex `\bcolumns?\b` matches the bare word "column" inside "column's" (the trailing `s` is optional) — misclassifying every one of those ordinary scalar rules as a table, which produced the "one row per line" wording and let `validate_table`'s empty-columns fallback (`validate_list`, `min_items=1`) accept a single scalar as a valid one-item list.
- **Fix** `_merge_sql_rules()` now also checks every existing rule's `columns` list (and the SQL rule's raw keyword, not just its humanized display name) before appending — a match merges the SQL constraints into that column instead of creating a duplicate step. `input_shape()`'s regex was tightened from `\bcolumns?\b` to `\bcolumns\b` so a singular, possessive mention no longer false-triggers table detection.
- **Guard** `verify_order_items_dedup.py`
- **Follow-up** `_classify_unresolved_free_text_fields()` — a single batched model call per document, run once at rule-build time — asks the model to fill in `min_length`/`max_length`/`pattern` for any field defect 22's baseline still leaves unresolved, so a brand-new document's unfamiliar field names get real validation without a lookup table needing to be hand-extended for every new field. Constraints the document already stated always win over a classified guess; any model failure leaves the rules unchanged. **Guard** `verify_free_text_classification.py`

---

## Known limitation: choice fields without stated values

A rule like *"Set Operation Frequency"* or *"Select Target System"* is a
choice, but if the document does not enumerate the options, **nothing
can validate it** — the assistant accepts anything.

The example still looks specific (`DAILY`, `PRODUCTION`) because it
comes from a name-based sample, which makes the gap easy to miss.

The fix is not in the validator. It is that the rules document must
list the options, and `RULES_PARSER_PROMPT` must extract them into
`allowed_values`. Inventing a default set here would reject legitimate
values a document allows.

---

## Recurring causes — check these first

**A bare `except Exception` hiding a programming error.** Four defects
(1, 6, 7, and a missing import in `step_by_step_service`) were a
`TypeError` or `NameError` swallowed by a handler meant for runtime
failure. A swallowed `TypeError`/`NameError`/`AttributeError` is a bug,
not a fallback condition. If a fallback tier "never seems to work",
this is why.

**Two places doing the same job.** Defects 5, 8, 10 and 14 were all a
second implementation drifting from the first. Before adding a builder,
a message, or a validation branch, check whether one already exists.

**A default that silently means "no information".** Defect 11 is the
worst of these: a required field the model fills with a vague value,
consumed as though it were meaningful. When honouring a declared value,
check it against what the consumer can actually use.

**Examples and validation reading the rule separately.** Defects 8, 10,
12. One source of truth: constraint inference.

---

## When a new defect is reported

1. **Reproduce it in a script first.** Every defect above was confirmed by reproducing the exact reported input before any code changed. Several turned out to have a different cause than the symptom suggested.
2. **Check whether the example and the validator agree** for that rule. `diagnose_saleorder.py` and `diagnose_rates_dates.py` are templates.
3. **Check `_get_effective_constraints(rule)`** — if it returns only `{'required': True}`, the rule text is not being understood, and nothing downstream can work.
4. **Check `_infer_semantic_type(rule, constraints)`** — if it returns a type the validator has no branch for, no checks run.
5. Fix at the inference layer, not at the symptom.
6. Add a guard test and an entry here.

---

## Test suites

Run from `backened/` with `./venv/Scripts/python.exe`:

| Suite | Covers |
|---|---|
| `verify_fixes.py` | signature fix, escaping, no redundant Groq calls |
| `verify_sessions.py` | session table, ownership, no run scan |
| `verify_hidden_rules.py` | internal rule data never reaches the client |
| `verify_step_examples.py` | every step shows its own valid example |
| `verify_task_creation.py` | rules document → stored rules → walkthrough |
| `verify_one_engine.py` | both services make identical decisions |
| `verify_narrative.py` | prose sections |
| `verify_shapes.py` | list and table steps |
| `verify_field_names.py` | field-name semantics, vague `data_type` |
| `verify_intent.py` | correction vs "not understood" vs error |
| `verify_memory.py` | correction learning and the privacy gate |
| `verify_free_text_gibberish.py` | fields with no semantic type reject garbage, still accept real answers |
| `verify_order_items_dedup.py` | child-table columns merge once, no duplicate steps, `columns?` regex |
| `verify_free_text_classification.py` | unresolved-field targeting, classified constraints merge, model-failure safety |
| `diagnose_examples.py` | 25 rules: every example passes its own rule |
