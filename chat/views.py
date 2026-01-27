from django.shortcuts import render
from django.http import HttpResponse
from django.http import JsonResponse
from .models import ChatMessage
from .openai_client import get_ai_reply


# 채팅 화면 랜더링 (GET) 이 함수는 화면만 띄우는 역할. DB 저장 X / AI 호출 X
def chat(request):
    if "chat_history" not in request.session:
        request.session["chat_history"] = []
    return render(request, "chat/chat.html", {
        "chat_history": request.session["chat_history"]
    })

# 메세지 처리 API (POST)
def chat_api(request):
    if request.method == "POST":
        user_message = request.POST.get("message")

        # OpenAI 호출
        bot_reply = get_ai_reply(user_message)

        # session 저장
        chat_history = request.session.get("chat_history", [])
        chat_history.append(("user", user_message))
        chat_history.append(("bot", bot_reply))
        request.session["chat_history"] = chat_history

        # DB 저장
        ChatMessage.objects.create(role="user", message=user_message)
        ChatMessage.objects.create(role="ai", message=bot_reply)

        return JsonResponse({
            "reply": bot_reply
        })
