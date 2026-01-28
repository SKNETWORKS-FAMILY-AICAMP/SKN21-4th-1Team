from django.http import JsonResponse
from django.shortcuts import render
from .openai_utils import ask_openai


# 채팅 화면 렌더링 (GET)
def chat(request):
    return render(request, 'chat/chat.html', {
        "chat_history": request.session.get("chat_history", [])
    })


# 채팅 API - 일반 응답 (POST)
def chat_api(request):
    """일반 응답 API"""
    if request.method == 'POST':
        try:
            # POST 데이터에서 메시지 가져오기
            user_message = request.POST.get('message', '')
            
            if not user_message:
                return JsonResponse({'status': 'error', 'message': 'Empty message'}, status=400)

            # OpenAI를 통해 답변 생성
            answer = ask_openai(user_message)
            
            # 기존 chat.html JS코드 호환을 위해 'reply' 키 포함
            return JsonResponse({
                'status': 'success',
                'answer': answer,
                'reply': answer
            })
        except Exception as e:
            print(f"Error: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
