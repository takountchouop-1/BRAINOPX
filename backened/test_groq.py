import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

print("🔍 Testing DeepSeek API...")

model_name = "deepseek-chat"

try:
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello in 5 words"}
        ],
        temperature=0.3,
        max_tokens=300,
    )

    print(f"✅ DeepSeek ({model_name}) says:", response.choices[0].message.content)

except Exception as e:
    print(f"❌ Error: {e}")
