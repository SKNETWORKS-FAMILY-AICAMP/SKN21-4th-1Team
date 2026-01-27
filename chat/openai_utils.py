import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def ask_openai(message: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "너는 노동법을 친절하게 설명하는 AI야."},
            {"role": "user", "content": message}
        ]
    )
    return response.choices[0].message.content
