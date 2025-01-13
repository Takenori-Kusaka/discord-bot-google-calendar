import openai  # openai v1.0.0+
import os
from dotenv import load_dotenv

load_dotenv()
client = openai.OpenAI(
    api_key=os.getenv("LITE_LLM_API_KEY"),
    base_url="http://localhost:4000",  # 0.0.0.0 を localhost に変更
)
# request sent to model set on litellm proxy, `litellm --model`
response = client.chat.completions.create(
    model="claude",
    messages=[
        {"role": "user", "content": "this is a test request, write a short poem"}
    ],
)

print(response)
