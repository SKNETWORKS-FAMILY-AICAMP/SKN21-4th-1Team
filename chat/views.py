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

# 채팅 API (Async View)
async def chat_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            
            if not user_message:
                return JsonResponse({'status': 'error', 'message': 'Empty message'}, status=400)

            # ChatbotService 인스턴스 획득 및 응답 생성
            bot_service = await ChatbotService.get_instance()
            answer = await bot_service.get_response(user_message)
            
            return JsonResponse({'status': 'success', 'answer': answer})
        except Exception as e:
            # 로그 출력
            print(f"Server Error: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
