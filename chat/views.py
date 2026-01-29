from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
import json
import asyncio
import uuid
from django.db.models import F
from .services import ChatbotService
from .models import ChatMessage


# ... imports ...
import uuid
from django.db.models import F


# 채팅 화면 랜더링 (GET)
def chat(request, session_id=None):
    sidebar_sessions = []
    chat_history = []

    if request.user.is_authenticated:
        # 사이드바용 세션 목록: 각 세션의 첫 번째 메시지(보통 user 질문)를 가져옴
        # session_id별로 그룹화하고 가장 먼저 생성된 메시지를 찾음
        # 간단하게: session_id가 있는 메시지 중 role='user'인 것들 중 각 세션별 첫 메시지
        # 하지만 Django ORM으로 복잡한 그룹핑보다, python단에서 처리하거나 distinct를 사용
        # SQLite는 distinct on 지원 안함 -> python set set set 로직 사용

        # 1. 유저의 모든 메시지를 최신순으로 가져옴
        all_messages = ChatMessage.objects.filter(
            user=request.user, session_id__isnull=False
        ).order_by("-created_at")

        seen_sessions = set()
        for msg in all_messages:
            if msg.session_id not in seen_sessions:
                # 해당 세션의 첫 번째 메시지(제목용)는 가장 오래된 user 메시지여야 하는데,
                # 여기서는 '최근 메시지'가 잡힘. 제목을 '첫 질문'으로 하고 싶다면 로직 수정 필요.
                # 기획: "이전 히스토리의 사용자가 작성한 첫행이 말줄임으로 노출"
                # -> 각 세션별 가장 오래된 'user' 메시지를 찾아야 함.

                # 효율성을 위해: 세션 ID 목록을 먼저 뽑고, 각 세션별 첫질문 query? (N+1 문제)
                # 일단 단순하게: 모든 세션을 가져오고, 템플릿에는 session object 리스트를 넘김
                # 여기서는 session_id 목록만 추출
                seen_sessions.add(msg.session_id)

        # 세션별 정렬 (최신 대화가 위로)
        # seen_sessions에는 순서가 보장 안됨. all_messages 순회하며 순서 유지
        ordered_sessions = []
        seen = set()
        for msg in all_messages:
            if msg.session_id not in seen:
                seen.add(msg.session_id)

                # 해당 세션의 '첫 번째' 사용자 메시지 찾기
                first_msg = (
                    ChatMessage.objects.filter(
                        user=request.user, session_id=msg.session_id, role="user"
                    )
                    .order_by("created_at")
                    .first()
                )
                title = first_msg.message if first_msg else "새로운 대화"
                if len(title) > 15:
                    title = title[:15] + "..."

                ordered_sessions.append(
                    {
                        "session_id": msg.session_id,
                        "title": title,
                        "created_at": msg.created_at,  # 정렬용(가장 최근 메시지 기준)
                    }
                )

        sidebar_sessions = ordered_sessions

        # 특정 세션 선택 시 대화 내용 불러오기
        if session_id:
            chat_history = ChatMessage.objects.filter(
                user=request.user, session_id=session_id
            ).order_by("created_at")
        else:
            # 세션 ID가 없으면 새 ID 생성 (아직 DB 저장 안함)
            # 템플릿에서 빈 문자열 대신 이 ID를 사용하게 됨
            session_id = str(uuid.uuid4())

    return render(
        request,
        "chat/chat.html",
        {
            "sidebar_sessions": sidebar_sessions,
            "chat_history": chat_history,
            "current_session_id": session_id,
        },
    )


# 채팅 API - 스트리밍 응답 (Async View)
async def chat_api_streaming(request):
    """스트리밍 응답을 사용한 채팅 API"""
    if request.method == "POST":
        try:
            if request.content_type == "application/json":
                data = json.loads(request.body)
                user_message = data.get("message", "")
                session_id = data.get("session_id")  # 프론트에서 세션 ID 받음
            else:
                user_message = request.POST.get("message", "")
                session_id = request.POST.get("session_id")

            # 세션 ID가 없으면 생성
            if not session_id:
                session_id = str(uuid.uuid4())

            if not user_message:
                return JsonResponse(
                    {"status": "error", "message": "Empty message"}, status=400
                )

            # 사용자 메시지 먼저 저장 (동기화 보장)
            if request.user.is_authenticated:
                await asyncio.to_thread(
                    ChatMessage.objects.create,
                    user=request.user,
                    role="user",
                    message=user_message,
                    session_id=session_id,
                )

            # 비동기 통신을 위한 큐 생성
            queue = asyncio.Queue()

            # 백그라운드 생성 작업 함수
            async def generate_response_task(user, uid, msg):
                full_ans = ""
                try:
                    bot_service = await ChatbotService.get_instance()
                    
                    # 스트리밍 생성
                    async for chunk in bot_service.get_response_stream(msg, session_id=uid):
                        full_ans += chunk
                        await queue.put({"type": "chunk", "data": chunk})
                    
                    # AI 답변 DB 저장 (유저가 페이지를 떠나도 실행됨)
                    if user.is_authenticated:
                        await asyncio.to_thread(
                            ChatMessage.objects.create,
                            user=user,
                            role="ai",
                            message=full_ans,
                            session_id=uid,
                        )
                    
                    await queue.put({"type": "done", "data": full_ans})
                    
                except Exception as e:
                    print(f"Background generation error: {e}")
                    await queue.put({"type": "error", "data": str(e)})
                finally:
                    await queue.put(None) # 종료 신호

            # 백그라운드 작업 시작 (클라이언트 연결 여부와 상관없이 계속 실행됨)
            asyncio.create_task(generate_response_task(request.user, session_id, user_message))

            # SSE 응답 제너레이터 (클라이언트에게 큐의 데이터를 전달)
            async def stream_generator():
                # 초기 세션 정보 전송
                yield f"data: {json.dumps({'status': 'session_init', 'session_id': session_id})}\n\n"
                
                while True:
                    # 큐에서 데이터 가져오기 (대기)
                    item = await queue.get()
                    
                    if item is None: # 종료 신호
                        break
                        
                    if item["type"] == "chunk":
                        # 클라이언트가 연결된 경우에만 전송
                        if not await request.is_disconnected():
                            yield f"data: {json.dumps({'chunk': item['data'], 'status': 'streaming'})}\n\n"
                    
                    elif item["type"] == "done":
                        if not await request.is_disconnected():
                            yield f"data: {json.dumps({'status': 'done', 'full_answer': item['data']})}\n\n"
                    
                    elif item["type"] == "error":
                        if not await request.is_disconnected():
                            yield f"data: {json.dumps({'status': 'error', 'message': item['data']})}\n\n"
                    
                    # 연결이 끊겨도 loop는 계속 돌면서 queue를 비워줘야 task가 막히지 않음
                    # (Queue 사이즈가 무한대라면 상관없지만, 소비해주는 것이 좋음)

            return StreamingHttpResponse(
                stream_generator(), content_type="text/event-stream"
            )

        except Exception as e:
            print(f"Error: {e}")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    return JsonResponse({"status": "error", "message": "Invalid method"}, status=405)


# 채팅 API - 일반 응답
async def chat_api(request):
    """일반 응답"""
    if request.method == "POST":
        try:
            if request.content_type == "application/json":
                data = json.loads(request.body)
                user_message = data.get("message", "")
                session_id = data.get("session_id")
            else:
                user_message = request.POST.get("message", "")
                session_id = request.POST.get("session_id")

            if not session_id:
                session_id = str(uuid.uuid4())

            if not user_message:
                return JsonResponse(
                    {"status": "error", "message": "Empty message"}, status=400
                )

            # ChatbotService를 통해 답변 생성
            bot_service = await ChatbotService.get_instance()

            # 사용자 메시지 저장
            if request.user.is_authenticated:
                await asyncio.to_thread(
                    ChatMessage.objects.create,
                    user=request.user,
                    role="user",
                    message=user_message,
                    session_id=session_id,
                )

            answer = await bot_service.get_response(user_message, session_id=session_id)

            # AI 답변 저장
            if request.user.is_authenticated:
                await asyncio.to_thread(
                    ChatMessage.objects.create,
                    user=request.user,
                    role="ai",
                    message=answer,
                    session_id=session_id,
                )

            # 기존 chat.html JS코드 호환을 위해 'reply' 키 포함
            return JsonResponse(
                {
                    "status": "success",
                    "answer": answer,
                    "reply": answer,
                    "session_id": session_id,
                }
            )
        except Exception as e:
            print(f"Error: {e}")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    return JsonResponse({"status": "error", "message": "Invalid method"}, status=405)


# 채팅 세션 삭제 API
def delete_chat_session(request, session_id):
    """
    특정 세션의 대화 내용을 삭제하는 뷰 함수
    POST 또는 DELETE 요청만 허용합니다.
    """
    if request.method not in ["POST", "DELETE"]:
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    
    if not request.user.is_authenticated:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)
        
    try:
        # 현재 로그인한 사용자의 해당 세션 메시지만 삭제 (보안 강화)
        deleted_count, _ = ChatMessage.objects.filter(
            user=request.user, 
            session_id=session_id
        ).delete()
        
        if deleted_count == 0:
             return JsonResponse({"status": "error", "message": "Session not found or already deleted"}, status=404)

        return JsonResponse({"status": "success", "message": "Session deleted"})
        
    except Exception as e:
        print(f"Error deleting session: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
