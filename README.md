# 법령 검색 및 Q&A 챗봇 
> RAG + LLM + Django 기반 법률 Q&A 챗봇


본 프로젝트는 **법령 데이터를 기반으로 사용자의 질문에 근거 있는 답변을 제공하는 AI 챗봇 웹서비스**입니다.  
RAG(Retrieval-Augmented Generation) 구조를 적용하여, 실제 법령 조문을 검색한 뒤 LLM을 통해 답변을 생성합니다.

<br>

---
# 팀원 및 담당 업무


| 성함       | 담당 업무                                                    |
| :--------- | :----------------------------------------------------------- |
| **김준석** | RAG 기반 모델 구축 및 개선 |
| **문지영** | Django 프로젝트 구조 설계, 채팅 세션 관리  |
| **박내은** | AWS 기반 서비스 배포 및 운영 |
| **박민정** | 서비스 기획 및 기술 설계 산출물 전반 담당 |
| **유성현** | AWS 기반 서비스 배포 및 운영 |
| **전우영** | RAG 기반 모델 구축 및 개선 |

---




# 📑 목차
<br>

1. 프로젝트 개요
2. 기술 스택 & 사용한 모델
3. 시스템 아키텍쳐
4. WBS
5. 트러블 슈팅
6. 수행 결과 (시연 페이지)
7. 프로젝트 개선 방향
8. 회고

<br>

---

# 📖 프로젝트 개요

### **프로젝트 정보**
- **프로젝트명**: 법령 검색 및 Q&A 챗봇 
- **개발 기간**: 3차(RAG 챗봇) + 4차(웹 서비스) 통합 프로젝트
- **팀 구성**: 6명
- **개발 환경**: Python 3.12+, SQLite



### **프로젝트 배경**

일반 사용자가 법령을 직접 검색하고 해석하는 것은 매우 어렵습니다.

- 법률 용어가 어렵고  
- 필요한 조문을 찾기 힘들며  
- 상황에 맞는 해석을 얻기 어렵기 때문입니다  

이를 해결하기 위해, **법령 데이터를 AI가 이해하고 설명해주는 챗봇 웹서비스**를 기획했습니다.


### **프로젝트 목표**

- 법령 데이터를 **조문 단위로 구조화**
- 벡터 검색 기반 **정확한 근거 제시**
- Django 기반 **웹 챗봇 UI 구현**
- 누구나 쉽게 사용할 수 있는 **법률 Q&A 서비스**


### **핵심 아이디어**

- 법률 분야를 노동법 / 사회복지법 / 형사법으로 분리
- 각 도메인별 전용 데이터와 벡터 DB 구축
- 공통 RAG 파이프라인을 활용해 정확한 근거 기반 응답 생성
- Django 웹 인터페이스를 통한 직관적인 챗봇 사용 경험 제공

<br><br>

---

# 🛠 기술 스택 & 사용한 모델


| 분야                | 사용 도구 |
|---------------------|-----------|
| **Language**        | [![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=Python&logoColor=white)](https://www.python.org/) |
| **Collaboration Tool** | [![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white)](https://git-scm.com/) [![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/) [![Discord](https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com/) |
| **LLM Model**       | [![GPT-4o](https://img.shields.io/badge/GPT--4o%20-412991?style=for-the-badge&logo=openai&logoColor=white)](https://platform.openai.com/) 
| **Embedding Model** |  |
| **Library** |![Pandas](https://img.shields.io/badge/pandas-%23150458.svg?style=for-the-badge&logo=pandas&logoColor=white) ![NumPy](https://img.shields.io/badge/numpy-%23013243.svg?style=for-the-badge&logo=numpy&logoColor=white) !logo=opencv&logoColor=white)|
| **Database** |![Static Badge](https://img.shields.io/badge/PINECONE-red?style=for-the-badge) ![SQLite](https://img.shields.io/badge/sqlite-%2307405e.svg?style=for-the-badge&logo=sqlite&logoColor=white)|
| **Orchestration / RAG** | [![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)](https://www.langchain.com/) [![LangGraph](https://img.shields.io/badge/LangGraph-000000?style=for-the-badge)](https://langchain-ai.github.io/langgraph/) |
| **Frontend** |![AWS](https://img.shields.io/badge/AWS-%23FF9900.svg?style=for-the-badge&logo=amazon-aws&logoColor=white) ![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white) ![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white) ![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white) |
| **Development Env** | [![VS Code](https://img.shields.io/badge/VS%20Code-007ACC?style=for-the-badge&logo=visualstudiocode&logoColor=white)](https://code.visualstudio.com/) [![Conda](https://img.shields.io/badge/Conda-3EB049?style=for-the-badge&logo=anaconda&logoColor=white)](https://www.anaconda.com/)

<br>


---

# 시스템 아키텍쳐

### 프로젝트 구조

```
SKN21-4TH-1TEAM/
├── backend/                         # RAG 기반 챗봇 백엔드 로직
│   ├── common/                      # 공통 RAG 파이프라인
│   │   ├── __init__.py
│   │   └── rag_pipeline.py          # 검색 → 프롬프트 → LLM 응답 흐름
│   │
│   ├── domains/                     # 도메인별 법률 챗봇 
│   │   ├── labor_law/               # 노동법
│   │   │   ├── data/                # 노동법 원본 문서
│   │   │   ├── build_vector_db.py   # 노동법 벡터 DB 생성
│   │   │   └── config.py            # 노동법 도메인 설정
│   │
│   └── run_rag.py                   # 도메인 선택 후 RAG 실행 엔트리
│
├── accounts/                        # Django 웹 애플리케이션 - 회원가입, 로그인, 로그아웃 설정
├── home/                            # Django 웹 애플리케이션 - 홈화면
├── chat/                            # Django 웹 애플리케이션 - 챗봇 화면
│   ├── admin.py                    # 관리자 페이지 설정
│   ├── apps.py                     # chat 앱 설정
│   ├── models.py                   # 채팅 데이터 모델
│   ├── urls.py                     # URL 라우팅
│   └── views.py                    # 챗봇 요청 처리
│
├── config/                          # Django 프로젝트 설정
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── static/                          # CSS / JS / 이미지 등 정적 파일
├── db.sqlite3                      # SQLite 데이터베이스
├── manage.py                       # Django 실행 진입점
└── README.md                       # 프로젝트 문서

```

---







# WBS
|단계|작업 내용|상태|
환경 설정,Django 프로젝트 초기화 및 앱 구조 생성,완료
인증 시스템,django-allauth 패키지 설치 및 설정,완료
OAuth 연동,Google Cloud Console 프로젝트 생성 및 API 연동,완료
UI/UX 설계,base.html을 활용한 공통 레이아웃 및 템플릿 상속 구조 구축,완료
기능 구현,"로그인, 회원가입, 로그아웃 기능 로직 및 URL 라우팅 연결",완료
디자인 개선,CSS를 활용한 반응형 로그인/회원가입 카드 UI 구현,완료
---

# 트러블 슈팅

---

# ✨ **주요 기능**

## 1. 법령 기반 질의응답
- 사용자의 질문을 자연어로 입력
- 관련 법령 조문을 벡터 검색
- 검색 결과를 기반으로 AI 답변 생성

## 2. 근거 중심 답변
- 단순 요약이 아닌 **관련 조문 포함 답변**
- 법령 출처 명시

## 3. 웹 챗봇 UI
- Django 기반 웹 페이지
- 실시간 채팅 형태의 UX
- 사용자 질문 / AI 답변 기록 유지

---

# 수행 결과 (시연 페이지)

---

# 🚀 프로젝트 개선 방향

---

# 📝 회고
