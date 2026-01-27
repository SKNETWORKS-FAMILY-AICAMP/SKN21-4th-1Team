from django.shortcuts import render
from django.http import HttpResponse
from django.http import JsonResponse
from .models import ChatMessage
from .openai_client import get_ai_reply
from openai import OpenAI
from django.conf import settings
from .openai_utils import ask_openai   

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def ask_openai(message):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "너는 친절한 노동법 AI 상담사야."},
            {"role": "user", "content": message}
        ]
    )
    return response.choices[0].message.content



# 채팅 화면 랜더링 (GET) 이 함수는 화면만 띄우는 역할. DB 저장 X / AI 호출 X
def chat(request):
    if "chat_history" not in request.session:
        request.session["chat_history"] = []
    return render(request, "chat/chat.html", {
        "chat_history": request.session["chat_history"]
    })

# 메세지 처리 API (POST)

def chat_api(request):
    user_message = request.POST.get("message")

    # OpenAI 호출
    ai_answer = ask_openai(user_message)
    # RAG 서버 호출할 때 아래 코드로 수정
    # ai_answer = call_rag_server(user_message)

    # Session 저장
    chat_history = request.session.get("chat_history", [])
    chat_history.append(("user", user_message))
    chat_history.append(("bot", ai_answer))
    request.session["chat_history"] = chat_history

    # DB 저장
    ChatMessage.objects.create(
        role="user",
        message=user_message
    )
    ChatMessage.objects.create(
        role="ai",
        message=ai_answer
    )

    return JsonResponse({
        "reply": ai_answer
    })