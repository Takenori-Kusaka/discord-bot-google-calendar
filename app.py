"""
Discord bot application that utilizes Google Calendar API and Gemini AI
for managing calendar events and providing intelligent responses.
"""

import os
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

# .env ファイルから環境変数を読み込む
load_dotenv()

# 環境変数を取得
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# Google AI Studioで発行したAPIキーを設定
genai.configure(api_key=GOOGLE_API_KEY)

# generateContent メソッドをサポートするモデルのみをフィルタリングして表示
print("Models supporting 'generateContent' method:")
for m in genai.list_models():
    if "generateContent" in m.supported_generation_methods:
        print(m.name)

# モデルを選択
model = genai.GenerativeModel("gemini-pro")

# プロンプトを設定
PROMPT = """
You are an AI assistant that helps manage Google Calendar. \
Please respond within 2000 characters. \
If you detect a date/time in user input, suggest adding a calendar event. \
Format your responses with simple markdown.
"""

# リクエストを送信してレスポンスを取得
try:
    response = model.generate_content(PROMPT)

    # レスポンスを表示
    print(f"\nResponse:\n{response.text}")

    # プロンプトに対するフィードバックを表示 (もしあれば)
    if response.prompt_feedback:
        print(f"\nPrompt Feedback:\n{response.prompt_feedback}")

    # 安全性評価を表示 (もしあれば)
    if response.candidates and response.candidates[0].safety_ratings:
        print(f"\nSafety Ratings:\n{response.candidates[0].safety_ratings}")

except (ConnectionError, google_exceptions.GoogleAPIError) as e:
    print(f"An error occurred: {e}")
