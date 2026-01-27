# 챗봇 RAG 연동 가이드 📚

## 현재 상황 요약

현재 Django 챗봇은 **OpenAI API를 직접 호출**하는 방식으로 구현되어 있습니다.
내일 RAG 서버로 교체하기 위한 준비가 되어 있습니다.

---

## 📁 파일 구조

```
chat/
├── views.py              # 메인 로직 (여기만 수정하면 됨!)
├── openai_utils.py       # OpenAI 함수 (참고용)
├── openai_client.py      # OpenAI 클라이언트 (참고용)
├── models.py             # DB 모델
├── urls.py               # URL 라우팅
└── templates/chat/
    └── chat.html         # 프론트엔드 (수정 완료, CSRF 토큰 추가됨)
```

---

## 🔧 현재 동작 방식

### 1. 사용자가 메시지 전송
- `chat.html`에서 AJAX POST 요청
- URL: `/chat/api/`
- Body: `message=사용자질문`
- **CSRF 토큰 포함** (오늘 수정됨)

### 2. Django가 요청 처리
- `views.py`의 `chat_api()` 함수 실행
- OpenAI API 호출: `ask_openai(user_message)`
- DB 저장 및 세션 저장
- JSON 응답: `{"reply": "AI답변"}`

### 3. 프론트엔드 응답 표시
- 타이핑 애니메이션으로 답변 출력

---

## 🚀 RAG 서버로 교체하는 방법

### ✅ 수정할 파일: `chat/views.py`

**현재 코드 (38번째 줄):**
```python
# OpenAI 호출
ai_answer = ask_openai(user_message)
# RAG 서버 호출할 때 아래 코드로 수정
# ai_answer = call_rag_server(user_message)
```

**→ 이렇게 수정:**
```python
# OpenAI 호출
# ai_answer = ask_openai(user_message)
# RAG 서버 호출
ai_answer = call_rag_server(user_message)
```

---

## 📝 RAG 함수 구현 예시

`views.py`에 다음 함수를 추가하세요:

```python
import requests

def call_rag_server(user_message):
    """
    RAG 서버에 질문을 전송하고 답변을 받아오는 함수
    """
    try:
        # RAG 서버 URL (팀원이 제공한 주소로 변경)
        RAG_SERVER_URL = "http://localhost:8001/api/rag"  # 예시
        
        # RAG 서버로 POST 요청
        response = requests.post(
            RAG_SERVER_URL,
            json={"question": user_message},  # RAG 서버 API 스펙에 맞춰 수정
            timeout=30
        )
        
        # 응답 확인
        if response.status_code == 200:
            data = response.json()
            return data.get("answer", "답변을 생성할 수 없습니다.")
        else:
            return f"RAG 서버 오류 (코드: {response.status_code})"
            
    except requests.exceptions.Timeout:
        return "RAG 서버 응답 시간 초과. 잠시 후 다시 시도해주세요."
    except Exception as e:
        print(f"RAG 서버 호출 오류: {e}")
        return "RAG 서버 연결에 실패했습니다."
```

---

## 🎯 RAG 팀원에게 필요한 정보

RAG 서버 개발자에게 다음 정보를 요청하세요:

### 1. **API 엔드포인트**
- [ ] RAG 서버 URL (예: `http://localhost:8001/api/rag`)

### 2. **요청 형식**
- [ ] HTTP 메서드: `POST`
- [ ] Request Body 형식:
  ```json
  {
    "question": "사용자 질문"
  }
  ```

### 3. **응답 형식**
- [ ] Response Body 형식:
  ```json
  {
    "answer": "AI 답변"
  }
  ```

### 4. **기타 설정**
- [ ] 인증 토큰 필요 여부
- [ ] 타임아웃 설정 (권장: 30초)
- [ ] 에러 코드 및 에러 메시지 형식

---

## ✅ 테스트 체크리스트

RAG 연동 후 다음을 확인하세요:

1. **기본 동작**
   - [ ] 질문 전송 시 RAG 서버 호출 확인
   - [ ] 답변이 프론트엔드에 정상 표시
   - [ ] 타이핑 애니메이션 작동

2. **DB 저장**
   - [ ] 사용자 메시지 저장 (`ChatMessage` 테이블)
   - [ ] AI 답변 저장

3. **에러 처리**
   - [ ] RAG 서버 다운 시 에러 메시지 표시
   - [ ] 타임아웃 시 사용자에게 알림
   - [ ] 네트워크 오류 처리

4. **성능**
   - [ ] 답변 생성 시간 확인 (30초 이내 권장)
   - [ ] 로딩 메시지 표시

---

## 🔍 디버깅 팁

### Django 서버 로그 확인
```bash
# 터미널에서 실시간 로그 확인
python manage.py runserver
```

### RAG 서버 연결 테스트
```python
# Python 콘솔에서 직접 테스트
import requests
response = requests.post(
    "http://localhost:8001/api/rag",
    json={"question": "임금체불이 뭐야?"}
)
print(response.json())
```

### 브라우저 개발자 도구
- **F12** → **Console 탭**: JavaScript 에러 확인
- **Network 탭**: AJAX 요청/응답 확인

---

## 📞 문제 발생 시

1. **RAG 서버가 응답하지 않음**
   - RAG 서버가 실행 중인지 확인
   - URL이 올바른지 확인
   - 방화벽/포트 설정 확인

2. **응답이 너무 느림**
   - `timeout` 값 조정 (30초 → 60초)
   - RAG 서버 성능 확인

3. **에러 메시지가 표시됨**
   - Django 터미널 로그 확인
   - `print()`로 디버깅 정보 출력
   - RAG 서버 응답 형식 확인

---

## 🎉 완료!

이 가이드대로 진행하면 5분 안에 RAG 연동을 완료할 수 있습니다.
추가 질문사항은 언제든지 물어보세요!
