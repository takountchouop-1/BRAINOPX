import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

print("🔍 Testing Groq API...")

# Use one of the available models
model_name = "openai/gpt-oss-120b"  # Available from your list

try:
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello in 5 words"}
        ],
        temperature=0.3,
        max_tokens=300,
        reasoning_effort="low",
    )
    
    print(f"✅ Groq ({model_name}) says:", response.choices[0].message.content)
    
except Exception as e:
    print(f"❌ Error: {e}")