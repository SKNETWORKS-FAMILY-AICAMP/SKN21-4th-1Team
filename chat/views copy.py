from django.http import JsonResponse
from django.shortcuts import render

import json
import asyncio
from .services import ChatbotService

# 메인 채팅 페이지
def index(request):
    return render(request, 'bot/index.html')

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
