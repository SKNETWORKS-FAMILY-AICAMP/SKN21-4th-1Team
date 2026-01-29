from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
import json
import asyncio
from .services import ChatbotService


# 채팅 화면 랜더링 (GET)
def chat(request):
    return render(request, 'chat/chat.html', {
        "chat_history": request.session.get("chat_history", [])
    })

#d
# 채팅 API - 스트리밍 응답 (Async View)
async def chat_api_streaming(request):
    """스트리밍 응답을 사용한 채팅 API"""
    if request.method == 'POST':
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                user_message = data.get('message', '')
            else:
                user_message = request.POST.get('message', '')
            
            if not user_message:
                return JsonResponse({'status': 'error', 'message': 'Empty message'}, status=400)

            # 스트리밍 응답 생성
            async def stream_generator():
                try:
                    bot_service = await ChatbotService.get_instance()
                    
                    # 스트리밍 모드로 답변 생성
                    full_answer = ""
                    async for chunk in bot_service.get_response_stream(user_message):
                        full_answer += chunk
                        yield f"data: {json.dumps({'chunk': chunk, 'status': 'streaming'})}\n\n"
                        await asyncio.sleep(0.01)  # Rate limiting
                    
                    # 완료 메시지 전송
                    yield f"data: {json.dumps({'status': 'done', 'full_answer': full_answer})}\n\n"
                    
                except Exception as e:
                    yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
            
            return StreamingHttpResponse(
                stream_generator(),
                content_type='text/event-stream'
            )
            
        except Exception as e:
            print(f"Error: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)


# 채팅 API - 일반 응답
async def chat_api(request):
    """일반 응답"""
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
            return JsonResponse({
                'status': 'success',
                'answer': answer,
                'reply': answer
            })
        except Exception as e:
            print(f"Error: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)