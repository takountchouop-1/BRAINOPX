"""Quick test for example_utils.py against the workflow rules file."""
import sys
sys.path.insert(0, ".")
from app.services.example_utils import build_example_value

# Simulate a rule parsed from the workflow steps rules file (RULE 1: Step ID)
rules = [
    {
        "id": 1,
        "name": "Step ID",
        "description": "Each workflow step must have a unique identifier. Format Requirements: Must start with WFS- followed by 3-6 digits. Example: WFS-001, WFS-002, WFS-100",
        "task": "Provide a unique step identifier starting with WFS-",
        "keywords": ["step id", "unique id"],
        "expected_outcome": "A unique identifier starting with WFS-",
    },
    {
        "id": 2,
        "name": "Step Name",
        "description": "Each workflow step must have a descriptive name. Format: Minimum 3 characters. Must be in Title Case. Example: \"Review Documents\", \"Approval Pending\"",
        "task": "Provide a descriptive step name in Title Case",
        "keywords": ["step name"],
        "expected_outcome": "A descriptive name in Title Case",
    },
    {
        "id": 3,
        "name": "Step Order",
        "description": "Each workflow step must have a sequential order number. Must be a positive integer. Examples: Correct: 1, 2, 3, 4, 5",
        "task": "Provide a sequential order number",
        "keywords": ["step order"],
        "expected_outcome": "A positive integer",
    },
    {
        "id": 4,
        "name": "Step Status",
        "description": "Each workflow step must have a valid status. Allowed Values: PENDING, IN_PROGRESS, APPROVED, REJECTED, COMPLETED",
        "task": "Provide a valid step status",
        "keywords": ["step status"],
        "expected_outcome": "One of the allowed status values",
    },
    {
        "id": 6,
        "name": "Step Assignee",
        "description": "Each workflow step must be assigned to a user. Must match an existing user ID. Example: USER-001",
        "task": "Provide a valid user ID",
        "keywords": ["step assignee", "assignee"],
        "expected_outcome": "A valid user ID",
    },
    {
        "id": 7,
        "name": "Step Deadline",
        "description": "Each workflow step must have a deadline. Must be in the format: YYYY-MM-DD. Cannot be in the past.",
        "task": "Provide a deadline date",
        "keywords": ["step deadline", "deadline"],
        "expected_outcome": "A date in YYYY-MM-DD format",
    },
    # TARIFF TASK (2015) - Format: TRF + 3 digits
    {
        "id": 1,
        "name": "Tariff Code",
        "description": "Each tariff must have a unique code. Format: TRF + 3 digits (e.g., TRF001, TRF002). Cannot be empty",
        "task": "Provide a unique tariff code",
        "keywords": ["tariff code"],
        "expected_outcome": "A unique tariff code",
    },
    {
        "id": 3,
        "name": "Currency",
        "description": "The currency for this tariff. Allowed currencies: USD, EUR, GBP, JPY, CHF. Must be one of the allowed values",
        "task": "Provide the currency",
        "keywords": ["currency"],
        "expected_outcome": "One of the allowed currencies",
    },
    {
        "id": 6,
        "name": "Validity Start Date",
        "description": "When the tariff becomes valid. Format: YYYY-MM-DD. Cannot be in the past",
        "task": "Provide the validity start date",
        "keywords": ["validity start date"],
        "expected_outcome": "A date in YYYY-MM-DD format",
    },
    # NOTIFICATION TASK - Format: NOT + 3 digits
    {
        "id": 1,
        "name": "Notification ID",
        "description": "Each notification must have a unique ID. Format: NOT + 3 digits (e.g., NOT001, NOT002). Cannot be empty",
        "task": "Provide a unique notification ID",
        "keywords": ["notification id"],
        "expected_outcome": "A unique notification ID",
    },
    {
        "id": 2,
        "name": "Notification Type",
        "description": "Type of notification. Allowed types: EMAIL, SMS, PUSH, SLACK, TEAMS. Cannot be empty",
        "task": "Provide the notification type",
        "keywords": ["notification type"],
        "expected_outcome": "One of the allowed types",
    },
    # OPERATIONS TASK - Format: SCH + 3 digits
    {
        "id": 1,
        "name": "Operation ID",
        "description": "Each operation must have a unique ID. Format: SCH + 3 digits (e.g., SCH001, SCH002). Cannot be empty",
        "task": "Provide a unique operation ID",
        "keywords": ["operation id"],
        "expected_outcome": "A unique operation ID",
    },
    {
        "id": 7,
        "name": "Target System",
        "description": "The system where operation runs. Must be: PRODUCTION, TESTING, DEVELOPMENT, STAGING. Cannot be empty",
        "task": "Provide the target system",
        "keywords": ["target system"],
        "expected_outcome": "One of the allowed systems",
    },
    # BUSINESS RULES TASK - Format: BR + 4 digits
    {
        "id": 1,
        "name": "Rule ID",
        "description": "Each business rule must have a unique ID. Format: BR + 4 digits (e.g., BR0001, BR0002). Cannot be empty",
        "task": "Provide a unique rule ID",
        "keywords": ["rule id"],
        "expected_outcome": "A unique rule ID",
    },
    {
        "id": 3,
        "name": "Category",
        "description": "The category of the business rule. Allowed categories: SALES, FINANCE, OPERATIONS, HR, COMPLIANCE. Cannot be empty",
        "task": "Provide the category",
        "keywords": ["category"],
        "expected_outcome": "One of the allowed categories",
    },
    {
        "id": 8,
        "name": "Effective Date",
        "description": "Date from which the rule is effective. Format: YYYY-MM-DD. Cannot be in the past",
        "task": "Provide the effective date",
        "keywords": ["effective date"],
        "expected_outcome": "A date in YYYY-MM-DD format",
    },
    # USER ACCOUNT TASK - Example: johndoe
    {
        "id": 1,
        "name": "Username",
        "description": "Must be unique. Minimum 4 characters. Only letters and numbers allowed. Example: johndoe, jsmith",
        "task": "Provide a username",
        "keywords": ["username"],
        "expected_outcome": "A valid username",
    },
    {
        "id": 2,
        "name": "Email",
        "description": "Must be a valid email format. Example: user@domain.com. Cannot be empty",
        "task": "Provide an email address",
        "keywords": ["email"],
        "expected_outcome": "A valid email",
    },
]

for rule in rules:
    example = build_example_value(rule, ai_suggested_fix="TR999")
    print(f"{rule['name']:15} -> Example: {example!r}")

