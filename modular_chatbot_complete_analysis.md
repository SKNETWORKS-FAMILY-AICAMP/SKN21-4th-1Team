# 모듈화된 법률 RAG 챗봇 코드 분석

**작성일**: 2026-01-29  
**대상 디렉토리**: `chat/ai_module/`  
**목적**: 리팩토링된 모듈 구조 분석 및 성능 최적화 방안 제시

---
## 📋 목차

1. [모듈 구조 개요](#1-모듈-구조-개요)
2. [파일별 상세 분석](#2-파일별-상세-분석)
   - 2.1 [`__init__.py`](#21-__init__py)
   - 2.2 [`config.py`](#22-configpy)
   - 2.3 [`prompts.py`](#23-promptspy)
   - 2.4 [`schemas.py`](#24-schemaspy)
   - 2.5 [`infrastructure.py`](#25-infrastructurepy)
   - 2.6 [`graph.py`](#26-graphpy)
3. [파일 간 관계도](#3-파일-간-관계도)
4. [성능 최적화 방안](#4-성능-최적화-방안)
5. [최적화 코드 수정 가이드](#5-최적화-코드-수정-가이드)

---
## 1. 모듈 구조 개요

기존의 단일 파일(`chatbot_graph_V8_FINAL.py`, 965줄)을 **6개의 모듈**로 분리하여 유지보수성과 확장성을 크게 향상시켰습니다.

### 파일 구조

```
chat/ai_module/
├── __init__.py          (6줄)   - 패키지 진입점
├── config.py            (38줄)  - 설정 관리
├── prompts.py           (98줄)  - 프롬프트 템플릿
├── schemas.py           (56줄)  - 데이터 스키마
├── infrastructure.py    (207줄) - 인프라 컴포넌트
└── graph.py             (500줄) - LangGraph 로직
```

### 설계 원칙

| 원칙 | 설명 |
|------|------|
| **단일 책임** | 각 파일이 하나의 명확한 역할만 수행 |
| **의존성 분리** | 설정 → 스키마 → 인프라 → 로직 순으로 의존 |
| **재사용성** | 프롬프트, 설정 등을 독립적으로 수정 가능 |
| **테스트 용이성** | 각 모듈을 독립적으로 테스트 가능 |

---
## 2. 파일별 상세 분석

### 2.1 `__init__.py`

**역할**: 패키지의 **공개 API** 정의

```python
from .config import Config
from .infrastructure import VectorStoreManager, JinaReranker
from .graph import LegalRAGBuilder

__all__ = ["Config", "VectorStoreManager", "JinaReranker", "LegalRAGBuilder"]
```

#### 핵심 기능

- **외부 인터페이스**: 다른 모듈에서 `from chat.ai_module import Config` 형태로 임포트 가능
- **캡슐화**: 내부 구현(`prompts`, `schemas`)은 숨기고 필요한 것만 노출

#### 사용 예시

```python
# services.py에서 사용
from chat.ai_module import Config, LegalRAGBuilder, VectorStoreManager, JinaReranker

config = Config()
builder = LegalRAGBuilder(config)
```

---
### 2.2 `config.py`

**역할**: **중앙 집중식 설정 관리** (Django settings 연동)

```python
@dataclass
class Config:
    # Django settings에서 값을 가져오되, 없으면 기본값 사용
    LLM_MODEL: str = getattr(settings, "LLM_MODEL", "gpt-4o-mini")
    LLM_TEMPERATURE: float = getattr(settings, "LLM_TEMPERATURE", 0.0)
    
    TOP_K_VECTOR: int = getattr(settings, "TOP_K_VECTOR", 10)
    TOP_K_RERANK: int = getattr(settings, "TOP_K_RERANK", 5)
    TOP_K_FINAL: int = getattr(settings, "TOP_K_FINAL", 3)
    
    QDRANT_COLLECTION_NAME: str = getattr(settings, "QDRANT_COLLECTION_NAME", 
                                          os.getenv("QDRANT_COLLECTION_NAME"))
```

#### 핵심 특징

1. **Django 통합**: `django.conf.settings`에서 값을 우선 가져옴
2. **환경 변수 폴백**: Django settings에 없으면 `.env`에서 가져옴
3. **타입 안정성**: `@dataclass`로 타입 힌트 제공

#### 설정 항목 분류

| 카테고리 | 설정 항목 | 기본값 |
|----------|-----------|--------|
| **모델** | `LLM_MODEL` | `gpt-4o-mini` |
| | `EMBEDDING_MODEL` | `Qwen/Qwen3-Embedding-0.6B` |
| | `RERANKER_MODEL` | `jinaai/jina-reranker-v2-base-multilingual` |
| **RAG** | `TOP_K_VECTOR` | 10 |
| | `TOP_K_RERANK` | 5 |
| | `TOP_K_FINAL` | 3 |
| | `RELEVANCE_THRESHOLD` | 0.2 |
| **Qdrant** | `QDRANT_TIMEOUT` | 10초 |
| | `QDRANT_PREFER_GRPC` | True |

#### 성능 관련 설정

- **`TOP_K_VECTOR`**: 벡터 검색 결과 수 (↓ 값 → ↑ 속도, ↓ 재현율)
- **`QDRANT_TIMEOUT`**: Qdrant 연결 타임아웃 (↓ 값 → ↑ 응답성)
- **`QDRANT_PREFER_GRPC`**: gRPC 사용 여부 (True → 더 빠름)

---
### 2.3 `prompts.py`

**역할**: **모든 프롬프트 템플릿 관리**

#### 프롬프트 목록

| 변수명 | 사용 노드 | 목적 |
|--------|-----------|------|
| `PROMPT_QUERY_EXPANSION` | Query Expander | HyDE + Hybrid 쿼리 생성 |
| `PROMPT_ANALYZE` | Analyze | 질문 분석 (카테고리, 난이도 등) |
| `PROMPT_GENERATE` | Generate | 답변 생성 (인용 강제) |
| `PROMPT_EVALUATE` | Evaluate | 답변 품질 평가 |
| `TEMPLATE_CLARIFY` | Clarify | 명확화 요청 메시지 |
| `TEMPLATE_NO_RESULTS` | Generate | 검색 결과 없을 때 |

#### 예시: `PROMPT_GENERATE`

```python
PROMPT_GENERATE = """당신은 엄격한 기준을 가진 법률 AI 'A-TEAM'입니다.

## 핵심 원칙
1. **증거 기반**: 반드시 제공된 [검색된 문서]에 있는 내용만 사용
2. **Hallucination 금지**: 문서에 없는 법조문을 지어내지 마세요
3. **엄격한 인용**: 모든 진술 뒤에 [1], [2] 출처 표기

## 답변 형식
**🤔 분석**
...
"""
```

#### 장점

- **버전 관리**: 프롬프트 변경 이력 추적 용이
- **A/B 테스트**: 여러 프롬프트 버전 비교 가능
- **재사용**: 다른 프로젝트에서도 활용 가능

---
### 2.4 `schemas.py`

## 1) `AgentState` (TypedDict) - LangGraph 상태 컨테이너

### 전체 코드

```python
class AgentState(TypedDict):
    """LangGraph Agent의 상태"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_query: str
    query_analysis: Optional[dict]
    retrieved_docs: Optional[List[Any]]
    generated_answer: Optional[str]
    next_action: Optional[str]
    evaluation_result: Optional[dict]
    retry_count: Optional[int]
```

### 필드별 상세 설명

| 필드                | 타입                    | 설명                                                   | 예시 값                                                            |
| ------------------- | ----------------------- | ------------------------------------------------------ | ------------------------------------------------------------------ |
| `messages`          | `Sequence[BaseMessage]` | LangChain 메시지 히스토리 (대화 맥락 유지)             | `[HumanMessage("퇴직금 언제 받나요?"), AIMessage("14일 이내...")]` |
| `user_query`        | `str`                   | 사용자의 원본 질문                                     | `"퇴직금 언제 받나요?"`                                            |
| `query_analysis`    | `Optional[dict]`        | Analyze 노드의 분석 결과 (QueryAnalysis를 dict로 변환) | `{"category": "노동법", "complexity": "simple"}`                   |
| `retrieved_docs`    | `Optional[List[Any]]`   | Search 노드에서 검색된 문서 리스트                     | `[Document(page_content="근로기준법 제36조...")]`                  |
| `generated_answer`  | `Optional[str]`         | Generate 노드에서 생성된 최종 답변                     | `"퇴직금은 퇴직 후 14일 이내에 지급해야 합니다[1]."`               |
| `next_action`       | `Optional[str]`         | 다음 실행할 액션 (라우팅용)                            | `"search"`, `"clarify"`, `"end"`                                   |
| `evaluation_result` | `Optional[dict]`        | Evaluate 노드의 평가 결과                              | `{"quality_score": 5, "needs_more_search": false}`                 |
| `retry_count`       | `Optional[int]`         | 재검색 시도 횟수 (무한 루프 방지)                      | `0`, `1`, `2`                                                      |

### 핵심 특징

**`Annotated[Sequence[BaseMessage], add_messages]`**: LangGraph의 특수 기능
- `add_messages`는 메시지를 **누적**시키는 리듀서 함수
- 각 노드가 새 메시지를 추가하면 자동으로 기존 메시지에 병합됨

### 실제 사용 예시

```python
# Analyze 노드에서 상태 업데이트
def analyze_query(state: AgentState) -> dict:
    analysis = {"category": "노동법", "complexity": "simple"}
    return {"query_analysis": analysis}  # 기존 state에 병합됨

# Search 노드에서 상태 읽기
def search_documents(state: AgentState) -> dict:
    query = state["user_query"]  # "퇴직금 언제 받나요?"
    analysis = state["query_analysis"]  # {"category": "노동법", ...}
    # 검색 로직...
    return {"retrieved_docs": docs}
```

---

## 2) `HybridQuery` (Pydantic) - 쿼리 확장 결과

### 전체 코드

```python
class HybridQuery(BaseModel):
    """HyDE + Hybrid Search를 위한 쿼리 확장 결과"""
    keyword_query: str = Field(
        description="BM25 검색용: 조사 제거된 핵심 법률 키워드")
    semantic_query: str = Field(
        description="Vector 검색용: 질문 의도와 문맥을 포함한 자연어 문장")
    hyde_passage: str = Field(
        description="Vector 검색용 가상 문서: 예상되는 법조문 내용 (2-3문장)")
```

### 필드별 역할

| 필드             | 검색 방식          | 목적                                      | 예시                                                                           |
| ---------------- | ------------------ | ----------------------------------------- | ------------------------------------------------------------------------------ |
| `keyword_query`  | **Sparse (BM25)**  | 법률 용어의 정확한 키워드 매칭            | `"근로기준법 퇴직금 지급 청구"`                                                |
| `semantic_query` | **Dense (Vector)** | 질문의 의미와 의도 파악                   | `"퇴직금 지급 기한과 청구 방법에 대한 근로기준법 규정"`                        |
| `hyde_passage`   | **Dense (Vector)** | HyDE 기법: 예상 답변으로 검색 정확도 향상 | `"근로기준법 제36조에 따르면 퇴직금은 퇴직 후 14일 이내에 지급해야 합니다..."` |

### 실제 LLM 출력 예시

**입력 질문**: `"퇴직금 못 받았어요"`

**LLM이 생성한 JSON**:
```json
{
  "keyword_query": "근로기준법 퇴직금 지급 청구",
  "semantic_query": "퇴직금을 받지 못한 경우 법적 권리와 청구 방법",
  "hyde_passage": "근로기준법 제36조에 따르면 퇴직금은 퇴직 후 14일 이내에 지급해야 합니다. 지급하지 않을 경우 노동청에 진정을 제기할 수 있습니다."
}
```

**Pydantic이 자동으로 파싱**:
```python
hybrid = HybridQuery(
    keyword_query="근로기준법 퇴직금 지급 청구",
    semantic_query="퇴직금을 받지 못한 경우 법적 권리와 청구 방법",
    hyde_passage="근로기준법 제36조에 따르면..."
)

# 바로 속성으로 접근 가능
print(hybrid.keyword_query)  # "근로기준법 퇴직금 지급 청구"
```

### 왜 3개로 나누는가?

- **Sparse (keyword_query)**: "근로기준법", "제36조" 같은 정확한 법령명 매칭
- **Dense (semantic_query + hyde_passage)**: "퇴직금을 받지 못함" → "퇴직금 미지급" 같은 의미적 유사성
- **Hybrid**: 두 방식을 결합하여 재현율(Recall)과 정밀도(Precision) 모두 향상

---

## 3) `QueryAnalysis` (Pydantic) - 질문 분석 결과

### 전체 코드

```python
class QueryAnalysis(BaseModel):
    """질문 분석 결과"""
    category: str = Field(description="법률 분야: 노동법, 형사법, 민사법, 기타")
    intent_type: str = Field(description="질문 의도: 법령조회, 절차문의, 상황판단, 권리확인, 분쟁해결, 일반상담")
    needs_clarification: bool = Field(default=False, description="질문 모호 여부")
    needs_case_law: bool = Field(default=False, description="판례 검색 필요 여부")
    query_complexity: str = Field(default="medium", description="질문 난이도: simple, medium, complex")
    clarification_question: str = Field(default="", description="명확화 질문")
    user_situation: str = Field(default="", description="사용자 상황 요약")
    core_question: str = Field(default="", description="핵심 질문")
    related_laws: List[str] = Field(default_factory=list, description="관련 법률명")
```

### 필드별 상세 설명

| 필드                     | 타입        | 용도                                           | 예시 값                                     |
| ------------------------ | ----------- | ---------------------------------------------- | ------------------------------------------- |
| `category`               | `str`       | 법률 분야 분류 (검색 필터링)                   | `"노동법"`, `"형사법"`, `"민사법"`          |
| `intent_type`            | `str`       | 질문 의도 파악 (답변 스타일 결정)              | `"법령조회"`, `"절차문의"`, `"상황판단"`    |
| `needs_clarification`    | `bool`      | **라우팅 결정**: true면 Clarify 노드로         | `true` ("퇴직금"만 입력 시)                 |
| `needs_case_law`         | `bool`      | 판례 검색 필요 여부 (현재 미지원, 향후 확장용) | `true` ("부당해고 판례" 질문 시)            |
| `query_complexity`       | `str`       | **성능 최적화**: simple이면 Evaluate 생략      | `"simple"`, `"medium"`, `"complex"`         |
| `clarification_question` | `str`       | 명확화 필요 시 사용자에게 보낼 질문            | `"어떤 상황에서 퇴직금을 받지 못하셨나요?"` |
| `user_situation`         | `str`       | 사용자 상황 요약 (컨텍스트 유지)               | `"회사 퇴사 후 퇴직금 미지급"`              |
| `core_question`          | `str`       | 핵심 질문 추출 (긴 질문 요약)                  | `"퇴직금 지급 기한"`                        |
| `related_laws`           | `List[str]` | **검색 부스팅**: 관련 법률명으로 점수 가중치   | `["근로기준법", "근로자퇴직급여보장법"]`    |

### 실제 LLM 출력 예시

#### 예시 1: Simple 질문

**입력 질문**: `"근로기준법 제1조가 뭐야?"`

```json
{
  "category": "노동법",
  "intent_type": "법령조회",
  "needs_clarification": false,
  "needs_case_law": false,
  "query_complexity": "simple",
  "clarification_question": "",
  "user_situation": "근로기준법 제1조 내용 확인",
  "core_question": "근로기준법 제1조 내용",
  "related_laws": ["근로기준법"]
}
```

→ **라우팅**: `complexity == "simple"` → Evaluate 노드 생략

#### 예시 2: 명확화 필요

**입력 질문**: `"퇴직금"`

```json
{
  "category": "노동법",
  "intent_type": "일반상담",
  "needs_clarification": true,
  "needs_case_law": false,
  "query_complexity": "medium",
  "clarification_question": "퇴직금에 대해 어떤 것이 궁금하신가요? (지급 기한, 계산 방법, 청구 절차 등)",
  "user_situation": "퇴직금 관련 문의",
  "core_question": "퇴직금",
  "related_laws": ["근로기준법", "근로자퇴직급여보장법"]
}
```

→ **라우팅**: `needs_clarification == true` → Clarify 노드로 이동

#### 예시 3: Complex 질문

**입력 질문**: `"회사가 부당하게 해고했는데 복직 가능한가요? 판례도 알려주세요"`

```json
{
  "category": "노동법",
  "intent_type": "분쟁해결",
  "needs_clarification": false,
  "needs_case_law": true,
  "query_complexity": "complex",
  "clarification_question": "",
  "user_situation": "부당해고 후 복직 가능성 문의",
  "core_question": "부당해고 복직 가능성 및 판례",
  "related_laws": ["근로기준법", "노동위원회법"]
}
```

→ **라우팅**: `complexity == "complex"` → Evaluate 노드 실행

---

## 4) `AnswerEvaluation` (Pydantic) - 답변 품질 평가

### 전체 코드

```python
class AnswerEvaluation(BaseModel):
    """답변 평가 결과"""
    has_legal_basis: bool = Field(description="법적 근거 명시 여부")
    cites_retrieved_docs: bool = Field(description="검색 문서 인용 여부")
    is_relevant: bool = Field(description="답변 적합성")
    needs_more_search: bool = Field(description="추가 검색 필요 여부")
    quality_score: int = Field(description="품질 점수 (1-5)")
    improvement_suggestion: str = Field(default="", description="개선 제안")
```

### 필드별 평가 기준

| 필드                     | 평가 기준                        | True 예시                       | False 예시               |
| ------------------------ | -------------------------------- | ------------------------------- | ------------------------ |
| `has_legal_basis`        | 법령명, 조항 번호 명시 여부      | "근로기준법 제36조에 따르면..." | "일반적으로 퇴직금은..." |
| `cites_retrieved_docs`   | 검색 문서 인용 `[1]`, `[2]` 사용 | "...14일 이내입니다[1]."        | 인용 없이 답변만 작성    |
| `is_relevant`            | 질문에 직접 답하는가             | 퇴직금 질문에 퇴직금 답변       | 퇴직금 질문에 해고 답변  |
| `needs_more_search`      | 검색 결과 부족 여부              | 관련 문서 0-1개                 | 관련 문서 3개 이상       |
| `quality_score`          | 종합 품질 (1-5점)                | 5점: 완벽한 답변                | 1점: 답변 불가           |
| `improvement_suggestion` | 개선 방향 제안                   | "판례 추가 필요"                | "" (빈 문자열)           |

### 실제 LLM 평가 예시

#### 좋은 답변 (재검색 불필요)

```json
{
  "has_legal_basis": true,
  "cites_retrieved_docs": true,
  "is_relevant": true,
  "needs_more_search": false,
  "quality_score": 5,
  "improvement_suggestion": ""
}
```

→ **라우팅**: `quality_score >= 3` → END (답변 반환)

#### 나쁜 답변 (재검색 필요)

```json
{
  "has_legal_basis": false,
  "cites_retrieved_docs": false,
  "is_relevant": true,
  "needs_more_search": true,
  "quality_score": 2,
  "improvement_suggestion": "검색된 문서에 구체적인 법조문이 없음. 다른 키워드로 재검색 필요"
}
```

→ **라우팅**: `quality_score <= 2 AND needs_more_search == true` → Search 노드로 재검색

---

## 왜 Pydantic을 사용하는가?

### 1. LLM 출력 강제 (Structured Output)

**Pydantic 없이 (기존 방식)**:
```python
# LLM이 자유 형식으로 답변
response = llm.invoke("질문을 분석해줘")
# 출력: "이 질문은 노동법 분야이고, 난이도는 중간입니다..."

# 수동 파싱 필요 (오류 발생 가능)
if "노동법" in response:
    category = "노동법"
```

**Pydantic 사용 (현재 방식)**:
```python
# LLM에게 JSON 형식 강제
structured_llm = llm.with_structured_output(QueryAnalysis)
analysis = structured_llm.invoke("질문을 분석해줘")

# 자동으로 QueryAnalysis 객체로 변환됨
print(analysis.category)  # "노동법"
print(analysis.query_complexity)  # "medium"
```

### 2. 타입 검증 (Runtime Validation)

```python
# LLM이 잘못된 타입 반환 시 자동 오류 감지
{
  "quality_score": "높음"  # ❌ int가 아닌 str
}
# Pydantic이 자동으로 ValidationError 발생
```

### 3. 기본값 처리

```python
# LLM이 일부 필드를 누락해도 기본값으로 채워짐
QueryAnalysis(
    category="노동법",
    intent_type="법령조회"
    # needs_clarification은 자동으로 False
    # query_complexity는 자동으로 "medium"
)
```

### 4. IDE 자동완성

```python
analysis.  # ← IDE가 자동으로 필드 목록 표시
# category, intent_type, needs_clarification, ...
```

---

## TypedDict vs Pydantic 비교

| 특징          | TypedDict (`AgentState`)         | Pydantic (`HybridQuery` 등)  |
| ------------- | -------------------------------- | ---------------------------- |
| **용도**      | LangGraph 상태 관리              | LLM 출력 구조화              |
| **타입 검증** | ❌ 런타임 검증 없음 (타입 힌트만) | ✅ 런타임 자동 검증           |
| **기본값**    | ❌ 지원 안 함                     | ✅ `Field(default=...)`       |
| **LLM 연동**  | ❌ 불가능                         | ✅ `with_structured_output()` |
| **성능**      | ⚡ 빠름 (검증 없음)               | 🐢 느림 (검증 오버헤드)       |
| **사용 예**   | 노드 간 데이터 전달              | LLM 응답 파싱                |

---

## 요약

`schemas.py`는 챗봇의 **데이터 계약(Contract)**을 정의하는 핵심 파일입니다:

1. **`AgentState`**: LangGraph 노드 간 상태 전달
2. **`HybridQuery`**: Query Expansion 결과 (Sparse + Dense + HyDE)
3. **`QueryAnalysis`**: 질문 분석 결과 (라우팅 결정에 사용)
4. **`AnswerEvaluation`**: 답변 품질 평가 (재검색 여부 결정)

Pydantic을 사용하여 LLM의 자유로운 텍스트 출력을 **구조화된 데이터**로 강제하고, 타입 안정성을 보장합니다.

---
### 2.5 `infrastructure.py`

**역할**: **외부 리소스 연결** (Qdrant, 임베딩, Reranker)

#### 클래스 구조

```
infrastructure.py
├── JinaReranker          (L20-L91)
├── VectorStoreManager    (L97-L155)
└── SparseEmbeddingManager (L158-L207)
```

---

#### 1) `JinaReranker`

```python
class JinaReranker(BaseDocumentCompressor):
    def __init__(self, model_name, top_n):
        # Device 자동 선택: CUDA > MPS > CPU
        self.device = "cuda" if torch.cuda.is_available() else "mps" if ...
        
        # FP16 양자화
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if self.device != "cpu" else torch.float32
        )
    
    def compress_documents(self, documents, query):
        # [질문, 문서] 쌍으로 관련성 점수 계산
        pairs = [[query, doc.page_content] for doc in documents]
        scores = self.model(**inputs).logits
        # 상위 top_n개 선택
        return sorted_docs[:self.top_n]
```

**최적화 포인트**:
- **FP16 양자화** (L53): GPU 메모리 50% 절약
- **배치 처리**: 모든 문서를 한 번에 처리

---

#### 2) `VectorStoreManager`

```python
class VectorStoreManager:
    def initialize(self):
        # 임베딩 모델만 로딩 (무거운 작업)
        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.config.EMBEDDING_MODEL,
            encode_kwargs={'normalize_embeddings': True}
        )
    
    async def create_client(self) -> AsyncQdrantClient:
        # 매 요청마다 새 클라이언트 생성 (Lazy Loading)
        return AsyncQdrantClient(
            url=self.qdrant_url,
            timeout=self.config.QDRANT_TIMEOUT,
            prefer_grpc=True  # gRPC 사용
        )
```

**설계 포인트**:
- **Lazy Loading**: Qdrant 클라이언트는 필요할 때만 생성
- **이벤트 루프 안전**: 초기화 시점에 Async 클라이언트 생성 안 함
- **연결 관리**: 검색 후 `client.close()`로 명시적 해제

---

#### 3) `SparseEmbeddingManager`

```python
class SparseEmbeddingManager:
    def initialize(self):
        # BGE-M3 모델 로딩
        self.model = BGEM3FlagModel(
            self.config.SPARSE_EMBEDDING_MODEL,
            use_fp16=torch.cuda.is_available()
        )
    
    def encode_query(self, query: str) -> models.SparseVector:
        # Sparse 벡터 생성 (키워드 매칭용)
        output = self.model.encode(
            query,
            return_sparse=True,
            return_dense=False
        )
        weights = output['lexical_weights']  # {token_id: weight}
        return models.SparseVector(indices=..., values=...)
```

**역할**: 법률 용어의 정확한 키워드 매칭을 위한 희소 벡터 생성

---
### 2.6 `graph.py`

**역할**: **LangGraph 노드 및 워크플로우 구성**

#### 클래스: `LegalRAGBuilder`

```python
class LegalRAGBuilder:
    def __init__(self, config: Config):
        self.config = config
        self.llm = None
        self.vs_manager = None
        self.reranker = None
    
    def set_components(self, vs_manager, reranker):
        # 미리 로딩된 컴포넌트 주입 (의존성 주입)
        self.vs_manager = vs_manager
        self.reranker = reranker
    
    def build(self) -> CompiledStateGraph:
        # 그래프 빌드
        builder = StateGraph(AgentState)
        builder.add_node("analyze", self._create_analyze_node())
        builder.add_node("search", self._create_search_node())
        ...
        return builder.compile()
```

#### 노드 생성 메서드

| 메서드 | 노드명 | 주요 로직 |
|--------|--------|----------|
| `_create_analyze_node()` | analyze | LLM으로 질문 분석 → `QueryAnalysis` 반환 |
| `_create_clarify_node()` | clarify | 명확화 요청 메시지 생성 |
| `_create_search_node()` | search | **핵심**: Hybrid Search + Reranking |
| `_create_generate_node()` | generate | 검색 문서 기반 답변 생성 |
| `_create_evaluate_node()` | evaluate | 답변 품질 평가 |

---

#### 핵심 노드: `_create_search_node()` (L185-L296)

```python
async def search_documents(state: AgentState) -> dict:
    # 0. Qdrant 클라이언트 생성
    client = await self.vs_manager.create_client()
    
    try:
        # 1. Query Expansion (HyDE)
        hybrid = await query_expander(original_query)
        keyword_query = hybrid.keyword_query
        vector_query = hybrid.hyde_passage
        
        # 2. 임베딩 생성 (병렬)
        dense_vec, sparse_vec = await asyncio.gather(
            asyncio.to_thread(embeddings.embed_query, vector_query),
            asyncio.to_thread(sparse_manager.encode_query, keyword_query)
        )
        
        # 3. Qdrant Hybrid Search
        vector_docs = await self._execute_search(
            client, dense_vec, sparse_vec, collection_name, limit=10
        )
        
        # 4. Reranking
        reranked_docs = await asyncio.to_thread(
            reranker.compress_documents, vector_docs, original_query
        )
        
        # 5. Filtering & Boosting
        final_docs = [doc for doc in reranked_docs 
                      if doc.metadata['relevance_score'] >= 0.2][:3]
    
    finally:
        await client.close()
    
    return {"retrieved_docs": final_docs}
```

**성능 최적화 포인트**:
- **병렬 임베딩** (L229): Dense/Sparse 동시 생성
- **비동기 검색** (L232): I/O 대기 시간 최소화
- **연결 해제** (L250): 메모리 누수 방지

---

#### 라우팅 로직

```python
def _route_after_analysis(state) -> Literal["clarify", "search"]:
    if state["query_analysis"]["needs_clarification"]:
        return "clarify"
    return "search"

def _route_after_generate(state) -> Literal["evaluate", "end"]:
    complexity = state["query_analysis"]["query_complexity"]
    if complexity == "simple":
        return "end"  # 평가 생략
    return "evaluate"

def _route_after_evaluation(state) -> Literal["search", "end"]:
    if state["retry_count"] >= MAX_RETRY:
        return "end"
    if state["evaluation_result"]["quality_score"] <= 2:
        return "search"  # 재검색
    return "end"
```

**조건부 실행**으로 불필요한 노드 실행 방지 → 성능 향상

---
## 3. 파일 간 관계도

### 의존성 그래프

```
config.py (설정)
    ↓
prompts.py (프롬프트)
    ↓
schemas.py (데이터 구조)
    ↓
infrastructure.py (인프라)
    ↓ (Config, Schemas 사용)
graph.py (로직)
    ↓ (모든 모듈 사용)
__init__.py (진입점)
```

### 임포트 관계

| 파일 | 임포트하는 모듈 |
|------|------------------|
| `config.py` | `django.conf.settings`, `os` |
| `prompts.py` | (없음 - 순수 문자열) |
| `schemas.py` | `pydantic`, `langchain_core` |
| `infrastructure.py` | `config`, `torch`, `langchain_*` |
| `graph.py` | `config`, `schemas`, `infrastructure`, `prompts` |
| `__init__.py` | `config`, `infrastructure`, `graph` |

### 데이터 흐름

```
사용자 질문
    ↓
[graph.py] LegalRAGBuilder.build()
    ↓
[graph.py] analyze_node
    → [prompts.py] PROMPT_ANALYZE
    → [schemas.py] QueryAnalysis
    ↓
[graph.py] search_node
    → [infrastructure.py] VectorStoreManager
    → [infrastructure.py] SparseEmbeddingManager
    → [infrastructure.py] JinaReranker
    ↓
[graph.py] generate_node
    → [prompts.py] PROMPT_GENERATE
    ↓
최종 답변
```

---
## 4. 성능 최적화 방안

### 현재 병목 지점 분석

| 단계 | 소요 시간 (예상) | 병목 원인 |
|------|------------------|----------|
| **1. Analyze** | ~1초 | LLM API 호출 |
| **2. Query Expansion** | ~1초 | LLM API 호출 |
| **3. 임베딩 생성** | ~0.5초 | 모델 추론 (CPU/GPU) |
| **4. Qdrant 검색** | ~0.3초 | 네트워크 I/O |
| **5. Reranking** | ~0.5초 | 모델 추론 |
| **6. Generate** | ~2초 | LLM API 호출 (긴 프롬프트) |
| **7. Evaluate** | ~1초 | LLM API 호출 |
| **총합** | **~6.3초** | |

---

### 최적화 전략

#### 🚀 전략 1: LLM 호출 최소화

**현재 문제**: 총 4번의 LLM 호출 (Analyze, Expand, Generate, Evaluate)

**해결책**:

1. **Simple 질문 Fast Path**
   - Analyze에서 `complexity == "simple"` 판단 시 Expand, Evaluate 생략
   - **절감**: ~2초

2. **Query Expansion 캐싱**
   - 동일 질문 패턴은 캐시에서 재사용
   - **절감**: ~1초 (재방문 시)

3. **Evaluate 조건부 실행** (이미 구현됨)
   - Simple 질문은 평가 생략

---

#### ⚡ 전략 2: 병렬 처리 강화

**현재 문제**: 일부 단계가 순차 실행

**해결책**:

1. **Analyze + Query Expansion 병렬화**
   ```python
   analysis, hybrid = await asyncio.gather(
       analyze_chain.ainvoke(query),
       expand_chain.ainvoke(query)
   )
   ```
   - **절감**: ~1초

2. **임베딩 병렬화** (이미 구현됨)
   - Dense/Sparse 동시 생성

---

#### 🔧 전략 3: 모델 최적화

**현재 문제**: 임베딩/Reranking 모델이 무거움

**해결책**:

1. **임베딩 모델 경량화**
   - `Qwen3-Embedding-0.6B` → `all-MiniLM-L6-v2` (더 작음)
   - **절감**: ~0.2초

2. **Reranker 양자화** (이미 FP16 적용됨)
   - INT8 양자화 추가 고려

3. **배치 크기 조정**
   - Reranker의 `max_length=512` → `256`
   - **절감**: ~0.1초

---

#### 🗄️ 전략 4: 검색 최적화

**현재 문제**: 검색 결과 수가 많음

**해결책**:

1. **TOP_K 값 조정**
   - `TOP_K_VECTOR: 10 → 7`
   - `TOP_K_RERANK: 5 → 3`
   - **절감**: ~0.2초

2. **Qdrant 타임아웃 단축**
   - `QDRANT_TIMEOUT: 10 → 5`
   - **효과**: 실패 시 빠른 폴백

3. **gRPC 사용** (이미 적용됨)
   - `QDRANT_PREFER_GRPC: True`

---

#### 💾 전략 5: 캐싱 도입

**해결책**:

1. **임베딩 캐시**
   ```python
   from functools import lru_cache
   
   @lru_cache(maxsize=100)
   def get_embedding(text: str):
       return embeddings.embed_query(text)
   ```
   - **절감**: ~0.5초 (재방문 시)

2. **검색 결과 캐시**
   - Redis에 질문-문서 매핑 저장
   - **절감**: ~1초 (재방문 시)

---

### 최적화 효과 요약

| 전략 | 예상 절감 시간 | 난이도 |
|------|----------------|--------|
| Simple Fast Path | ~2초 | 쉬움 |
| Analyze + Expand 병렬화 | ~1초 | 중간 |
| TOP_K 값 조정 | ~0.2초 | 쉬움 |
| 임베딩 캐싱 | ~0.5초 (재방문) | 중간 |
| 검색 결과 캐싱 | ~1초 (재방문) | 어려움 |
| **총 절감** | **~4.7초** | |
| **최종 응답 시간** | **~1.6초** | |

---
## 5. 최적화 코드 수정 가이드

### 🎯 최적화 1: Simple Fast Path (즉시 적용 가능)

**수정 파일**: `graph.py`

**수정 위치**: `_create_search_node()` 메서드 내부 (L207-L219)

**Before**:
```python
# 1. Query Expansion (Async)
if query_expander:
    hybrid = await query_expander(original_query)
    keyword_query = hybrid.keyword_query
    vector_query = hybrid.hyde_passage
```

**After**:
```python
# 1. Query Expansion (조건부)
complexity = analysis.get("query_complexity", "medium")

if complexity == "simple":
    # Simple 질문은 Query Expansion 생략
    keyword_query = original_query
    vector_query = original_query
    logger.info("Simple query - skipping query expansion")
elif query_expander:
    hybrid = await query_expander(original_query)
    keyword_query = hybrid.keyword_query
    vector_query = hybrid.hyde_passage
```

**효과**: Simple 질문 시 ~1초 절감

**이유**: 
- Simple 질문(예: "근로기준법 제2조가 뭐야?")은 이미 명확하므로 Query Expansion 불필요
- LLM API 호출 1회 절약

---

### 🎯 최적화 2: TOP_K 값 조정

**수정 파일**: `config.py`

**수정 위치**: L22-L24

**Before**:
```python
TOP_K_VECTOR: int = getattr(settings, "TOP_K_VECTOR", 10)
TOP_K_RERANK: int = getattr(settings, "TOP_K_RERANK", 5)
TOP_K_FINAL: int = getattr(settings, "TOP_K_FINAL", 3)
```

**After**:
```python
TOP_K_VECTOR: int = getattr(settings, "TOP_K_VECTOR", 7)  # 10 → 7
TOP_K_RERANK: int = getattr(settings, "TOP_K_RERANK", 3)  # 5 → 3
TOP_K_FINAL: int = getattr(settings, "TOP_K_FINAL", 3)  # 유지
```

**효과**: ~0.2초 절감

**이유**:
- 벡터 검색 결과 10개 → 7개: Qdrant 검색 시간 단축
- Reranker 처리 문서 5개 → 3개: Reranker 추론 시간 단축
- 최종 문서는 3개로 유지하여 답변 품질 보장

---

### 🎯 최적화 3: Analyze + Expand 병렬화

**수정 파일**: `graph.py`

**수정 위치**: 새로운 노드 생성 (L146 이후)

**Before** (현재 구조):
```
analyze → search (내부에서 expand 호출)
```

**After** (병렬 구조):
```python
def _create_parallel_analyze_expand_node(self):
    """Analyze와 Query Expansion을 병렬 실행"""
    analyze_llm = self.llm.with_structured_output(QueryAnalysis)
    expand_llm = self.llm.with_structured_output(HybridQuery)
    
    async def parallel_node(state: AgentState) -> dict:
        query = state["user_query"]
        
        # 병렬 실행
        analysis, hybrid = await asyncio.gather(
            analyze_llm.ainvoke({"query": query}),
            expand_llm.ainvoke({"query": query})
        )
        
        return {
            "query_analysis": analysis.model_dump(),
            "expanded_query": hybrid.model_dump()
        }
    
    return parallel_node
```

**그래프 수정**:
```python
# build() 메서드 내부
builder.add_node("analyze_expand", self._create_parallel_analyze_expand_node())
builder.set_entry_point("analyze_expand")
```

**효과**: ~1초 절감

**이유**:
- 두 LLM 호출이 동시에 실행됨
- 네트워크 I/O 대기 시간 중복 제거

---

### 🎯 최적화 4: 임베딩 캐싱

**수정 파일**: `infrastructure.py`

**수정 위치**: `VectorStoreManager` 클래스 (L97-L155)

**추가 코드**:
```python
from functools import lru_cache

class VectorStoreManager:
    def __init__(self, config: Config):
        # ... 기존 코드 ...
        self._embedding_cache = {}  # 캐시 딕셔너리
    
    def get_embeddings(self) -> HuggingFaceEmbeddings:
        # ... 기존 코드 ...
        
        # 캐싱 래퍼 추가
        original_embed = self.embeddings.embed_query
        
        def cached_embed(text: str):
            if text in self._embedding_cache:
                logger.info("Embedding cache hit")
                return self._embedding_cache[text]
            
            result = original_embed(text)
            self._embedding_cache[text] = result
            return result
        
        self.embeddings.embed_query = cached_embed
        return self.embeddings
```

**효과**: ~0.5초 절감 (동일 질문 재방문 시)

**이유**:
- 동일한 텍스트의 임베딩을 재사용
- 모델 추론 시간 완전 제거

---

### 🎯 최적화 5: Reranker 배치 크기 조정

**수정 파일**: `infrastructure.py`

**수정 위치**: `JinaReranker.compress_documents()` (L68-L70)

**Before**:
```python
inputs = self.tokenizer(
    pairs, padding=True, truncation=True,
    return_tensors="pt", max_length=512
)
```

**After**:
```python
inputs = self.tokenizer(
    pairs, padding=True, truncation=True,
    return_tensors="pt", max_length=256  # 512 → 256
)
```

**효과**: ~0.1초 절감

**이유**:
- 토큰 길이 단축으로 Transformer 연산량 감소
- 법률 문서는 보통 256 토큰 이내로 핵심 내용 포함

---

### 📊 최적화 적용 우선순위

| 순위 | 최적화 | 난이도 | 효과 | 추천도 |
|------|--------|--------|------|--------|
| 1 | TOP_K 값 조정 | ⭐ | 0.2초 | ⭐⭐⭐⭐⭐ |
| 2 | Simple Fast Path | ⭐⭐ | 1초 | ⭐⭐⭐⭐⭐ |
| 3 | Reranker 배치 크기 | ⭐ | 0.1초 | ⭐⭐⭐⭐ |
| 4 | 임베딩 캐싱 | ⭐⭐⭐ | 0.5초 | ⭐⭐⭐⭐ |
| 5 | Analyze + Expand 병렬화 | ⭐⭐⭐⭐ | 1초 | ⭐⭐⭐ |

**권장 적용 순서**: 1 → 2 → 3 → 4 → 5

---
## 📝 결론

### 모듈화의 장점

1. **유지보수성**: 각 파일이 명확한 역할을 가짐
2. **확장성**: 새로운 기능 추가 시 해당 모듈만 수정
3. **테스트 용이성**: 각 모듈을 독립적으로 테스트 가능
4. **재사용성**: 다른 프로젝트에서도 활용 가능

### 성능 최적화 요약

- **현재 응답 시간**: ~6.3초
- **최적화 후**: ~1.6초 (약 75% 개선)
- **핵심 전략**: LLM 호출 최소화, 병렬 처리, 캐싱

### 다음 단계

1. **모니터링**: LangSmith로 각 노드별 실행 시간 측정
2. **A/B 테스트**: 최적화 전후 답변 품질 비교
3. **프로덕션 배포**: 점진적으로 최적화 적용

---

**작성 완료**: 2026-01-29  
**총 파일 수**: 6개  
**총 코드 라인**: 905줄 (기존 965줄에서 리팩토링)
