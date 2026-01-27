# 나중에 RAG 서버로 교체할 부분

from openai import OpenAI
from django.conf import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def get_ai_reply(user_message):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "너는 노동법 전문 AI 챗봇이다. 쉬운 말로 정확하게 설명해라."
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        temperature=0.3,
    )

    return response.choices[0].message.content
