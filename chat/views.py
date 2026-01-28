from django.http import JsonResponse
from django.shortcuts import render
import json
from .services import ChatbotService

# client = OpenAI(api_key=settings.OPENAI_API_KEY)

# def ask_openai(message):
#     response = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[
#             {"role": "system", "content": "너는 친절한 노동법 AI 상담사야."},
#             {"role": "user", "content": message}
#         ]
#     )
#     return response.choices[0].message.content



# # 채팅 화면 랜더링 (GET) 이 함수는 화면만 띄우는 역할. DB 저장 X / AI 호출 X
# def chat(request):
#     if "chat_history" not in request.session:
#         request.session["chat_history"] = []
#     return render(request, "chat/chat.html", {
#         "chat_history": request.session["chat_history"]
#     })


# 채팅 화면 랜더링 (GET)
def chat(request):
    # 'bot/index.html' -> 'chat/chat.html'로 변경
    return render(request, 'chat/chat.html', {
        # 기존 세션 기록 유지
        "chat_history": request.session.get("chat_history", [])
    })

# 채팅 API (Async View)
async def chat_api(request):
    if request.method == 'POST':
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                user_message = data.get('message', '')
            else:
                user_message = request.POST.get('message', '')
            
            if not user_message:
                return JsonResponse({'status': 'error', 'message': 'Empty message'}, status=400)

            # ChatbotService를 통해 답변 생성
            bot_service = await ChatbotService.get_instance()
            answer = await bot_service.get_response(user_message)
            
            # 기존 chat.html JS코드 호환을 위해 'reply' 키 포함
            return JsonResponse({'status': 'success', 'answer': answer, 'reply': answer})
        except Exception as e:
            print(f"Error: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
