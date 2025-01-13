import openai
from swarm import Swarm, Agent
import os
from dotenv import load_dotenv

load_dotenv()

# OpenAIクライアントを初期化します
# endpoint_url を指定して OpenAI クライアントを初期化します
openai_client = openai.OpenAI(
    api_key=os.getenv("LITE_LLM_API_KEY"),
    base_url=os.getenv("LITE_LLM_ENDPOINT_URL"),  # エンドポイントURLを指定
)
client = Swarm(openai_client)


def get_weather(location) -> str:
    return "{'temp':67, 'unit':'F'}"


agent = Agent(
    name="Agent",
    model="claude",
    instructions="You are a helpful agent.",
    functions=[get_weather],
)

messages = [{"role": "user", "content": "What's the weather in NYC?"}]

response = client.run(agent=agent, messages=messages)
print(response.messages[-1]["content"])
