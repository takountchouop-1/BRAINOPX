import sys
sys.path.append('.')

from app.services.groq_service import get_ai_response

print("✅ Import successful!")

# Test the function
response = get_ai_response(
    task_name="Test Task",
    validation_errors=[{"status": "open", "row": 1, "column": "test", "rule_violated": "Missing value"}],
    conversation_history=[],
    user_message="What's wrong?"
)

print("Response:", response)