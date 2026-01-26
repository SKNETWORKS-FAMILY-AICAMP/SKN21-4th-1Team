# 법령 검색 및 Q&A 챗봇 
> RAG + LLM + Django 기반 법률 Q&A 챗봇


본 프로젝트는 **법령 데이터를 기반으로 사용자의 질문에 근거 있는 답변을 제공하는 AI 챗봇 웹서비스**입니다.  
RAG(Retrieval-Augmented Generation) 구조를 적용하여, 실제 법령 조문을 검색한 뒤 LLM을 통해 답변을 생성합니다.


---


# 📑 목차

1. 프로젝트 개요
2. 기술 스택 & 사용한 모델
3. 시스템 아키텍쳐
4. WBS
5. 트러블 슈팅
6. 수행 결과 (시연 페이지)
7. 프로젝트 개선 방향
8. 회고

---

# 📖 프로젝트 개요

### **프로젝트 정보**
- **프로젝트명**: 법령 검색 및 Q&A 챗봇 
- **개발 기간**: 3차(RAG 챗봇) + 4차(웹 서비스) 통합 프로젝트
- **팀 구성**: 6명
- **개발 환경**: Python 3.12+, SQLite
---

### **프로젝트 배경**

일반 사용자가 법령을 직접 검색하고 해석하는 것은 매우 어렵습니다.

- 법률 용어가 어렵고  
- 필요한 조문을 찾기 힘들며  
- 상황에 맞는 해석을 얻기 어렵기 때문입니다  

이를 해결하기 위해, **법령 데이터를 AI가 이해하고 설명해주는 챗봇 웹서비스**를 기획했습니다.

---

### **프로젝트 목표**

- 법령 데이터를 **조문 단위로 구조화**
- 벡터 검색 기반 **정확한 근거 제시**
- Django 기반 **웹 챗봇 UI 구현**
- 누구나 쉽게 사용할 수 있는 **법률 Q&A 서비스**

---

### **주요 기능**

#### 1. 법령 기반 질의응답
- 사용자의 질문을 자연어로 입력
- 관련 법령 조문을 벡터 검색
- 검색 결과를 기반으로 AI 답변 생성

#### 2. 근거 중심 답변
- 단순 요약이 아닌 **관련 조문 포함 답변**
- 법령 출처 명시

#### 3. 웹 챗봇 UI
- Django 기반 웹 페이지
- 실시간 채팅 형태의 UX
- 사용자 질문 / AI 답변 기록 유지

---

# 🛠 기술 스택 & 사용한 모델


| 분야                | 사용 도구 |
|---------------------|-----------|
| **Language**        | [![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=Python&logoColor=white)](https://www.python.org/) |
| **Collaboration Tool** | [![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white)](https://git-scm.com/) [![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/) [![Discord](https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com/) |
| **LLM Model**       | [![GPT-4o](https://img.shields.io/badge/GPT--4o%20-412991?style=for-the-badge&logo=openai&logoColor=white)](https://platform.openai.com/) 
| **Embedding Model** | [![text-embedding-3-small](https://img.shields.io/badge/text--embedding--3--small-00A67D?style=for-the-badge&logo=openai&logoColor=white)](https://platform.openai.com/docs/guides/embeddings) |
| **Vector DB**       | [![Pinecone](https://img.shields.io/badge/Pinecone-0075A8?style=for-the-badge&logo=pinecone&logoColor=white)](https://www.pinecone.io/) |
| **Orchestration / RAG** | [![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)](https://www.langchain.com/) [![LangGraph](https://img.shields.io/badge/LangGraph-000000?style=for-the-badge)](https://langchain-ai.github.io/langgraph/) |
| **Frontend** | ![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white) ![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white) ![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white) |
| **Development Env** | [![VS Code](https://img.shields.io/badge/VS%20Code-007ACC?style=for-the-badge&logo=visualstudiocode&logoColor=white)](https://code.visualstudio.com/) [![Conda](https://img.shields.io/badge/Conda-3EB049?style=for-the-badge&logo=anaconda&logoColor=white)](https://www.anaconda.com/)

<br>


---

# 시스템 아키텍쳐

### 프로젝트 구조

```
SKN21-3rd-1TEAM/
├── backend/
│   ├── common/
│   │   ├── rag_pipeline.py          # RAG 처리 흐름
│   │   ├── vector_db.py             # 벡터 DB 검색
│   │   ├── chunking.py              # 문서 전처리
│   │   └── prompts.py               # 공통 프롬프트
│   │
│   ├── domains/
│   │   ├── labor_law/               # 노동법 도메인 (A팀)
│   │   │   ├── data/                # 원본 데이터
│   │   │   ├── build_vector_db.py   # 벡터 DB 생성
│   │   │   └── config.py            # 도메인 설정
│   │   │
│   │   ├── welfare_law/             # 사회복지법 도메인 (B팀)
│   │   │   ├── data/                # 원본 데이터
│   │   │   ├── build_vector_db.py   # 벡터 DB 생성
│   │   │   └── config.py            # 도메인 설정
│   │   │
│   │   └── criminal_law/            # 형사법 도메인 (C팀)
│   │       ├── data/                # 원본 데이터
│   │       ├── build_vector_db.py   # 벡터 DB 생성
│   │       └── config.py            # 도메인 설정
│   │
│   └── run_rag.py                   # RAG 실행 엔트리
│
├── chat/
│   ├── views.py                     # 챗봇 요청 처리
│   ├── models.py                   # 사용자·채팅 모델
│   ├── urls.py                     # URL 라우팅
│   └── templates/
│       └── chat.html                # 챗봇 UI
│
├── config/
│   ├── settings.py                  # Django 설정
│   └── urls.py                      # 메인 URL
│
├── static/
│   ├── css/                         # 스타일시트
│   ├── js/                          # 프론트 스크립트
│   └── img/                         # 이미지 리소스
│
├── manage.py                        # Django 실행 파일
└── README.md                        # 프로젝트 문서
```

## 📝 회고


## 🚀 아쉬운 점 및 개선 방향

### 아쉬운 점

### 향후 개선 계획
