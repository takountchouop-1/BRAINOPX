import os
from dotenv import load_dotenv
from .groq_service import get_ai_response as groq_response

load_dotenv()

def get_ai_response(validation_errors, user_message, conversation_history=[], provider=None, rules_content="", parsed_rules=None, mode="validation", language="en"):
    """
    Get AI response from Groq.
    """
    return groq_response(
        task_name="BRAINOPX Configuration",
        validation_errors=validation_errors,
        conversation_history=conversation_history,
        user_message=user_message,
        rules_content=rules_content,
        parsed_rules=parsed_rules,
        mode=mode,
        language=language,
    )