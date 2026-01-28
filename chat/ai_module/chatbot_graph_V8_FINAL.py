################################################
# A-TEAM 법률 RAG 챗봇 (LangGraph V8)
# V8 리팩토링:
# - @dataclass Config로 설정 분리
# - 계층화된 구조: Infrastructure → Logic → Execution
# - 코드 가독성 향상
# 기존 기능: 질문 의도 분석, Hybrid Retriever, Query Expansion, Generator-Critic
# 작성자: SKN 3-1팀 A-TEAM
# 작성일: 2026-01-08
################################################


import os
import sys
import logging
import warnings
import asyncio
from pathlib import Path
from dataclasses import dataclass, field
from typing import (
    Annotated, TypedDict, Sequence, Optional, List, Literal, Dict, Any
)

# Third-party
import torch
from dotenv import load_dotenv, find_dotenv
from pydantic import BaseModel, Field
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# LangChain Core
from langchain_core.documents import Document, BaseDocumentCompressor
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings


# Qdrant & FlagEmbedding (BGE-M3)
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, AsyncQdrantClient, models
from FlagEmbedding import BGEM3FlagModel

# LangGraph
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langchain_core.runnables import RunnableLambda

# LangSmith Tracing
from langsmith import traceable


# Load Environment Variables
load_dotenv(find_dotenv())


# ============================================================
# [SECTION 1] Configuration - 모든 설정값을 한 곳에서 관리
# ============================================================
@dataclass
class Config:
    """Application Configuration (dataclass)

    모든 하드코딩된 값을 이곳에서 관리합니다.
    변경이 필요한 경우 이 클래스만 수정하면 됩니다.
    """

    # ═══════════════════════════════════════════════════════════
    # [1] Models - 사용할 모델 설정
    # ═══════════════════════════════════════════════════════════
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.0
    EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-0.6B"
    SPARSE_EMBEDDING_MODEL: str = "BAAI/bge-m3"  # BGE-M3 (Multilingual)
    RERANKER_MODEL: str = "jinaai/jina-reranker-v2-base-multilingual"

    # ═══════════════════════════════════════════════════════════
    # [2] RAG Settings - 검색 및 처리 설정
    # ═══════════════════════════════════════════════════════════
    VECTOR_DIM: int = 1024
    TOP_K_VECTOR: int = 10                  # Vector Search k (20 → 10 최적화)
    TOP_K_RERANK: int = 5                   # Reranker 후 상위 k개
    TOP_K_FINAL: int = 3                    # 최종 답변 생성에 사용할 문서 수 (5 → 3 최적화)
    RELEVANCE_THRESHOLD: float = 0.2        # 유사도 임계값
    MAX_RETRY: int = 2                      # 재검색 최대 횟수

    # ═══════════════════════════════════════════════════════════
    # [3] Qdrant - 벡터 DB 설정
    # ═══════════════════════════════════════════════════════════
    QDRANT_TIMEOUT: int = 10                # 30 → 10초로 최적화
    QDRANT_PREFER_GRPC: bool = True         # gRPC 사용 (더 빠름)

    # ═══════════════════════════════════════════════════════════
    # [4] PROMPTS - 노드별 시스템 프롬프트
    # ═══════════════════════════════════════════════════════════

    # --- [노드: Query Expansion] HyDE + Hybrid Search 용 프롬프트 ---
    PROMPT_QUERY_EXPANSION: str = """당신은 법률 검색 쿼리 생성 전문가입니다.

## 임무
사용자의 모호한 질문을 검색 엔진(Qdrant Hybrid Search)이 이해하기 쉬운 형태로 변환하세요.

## 전략
1. **키워드 추출 (Sparse용)**: 조사 등을 제거한 핵심 법률 명사만 추출하세요. (키워드 매칭 중요)
   - 예: "퇴직금 못 받았어요" → "근로기준법 퇴직금 지급 청구"
2. **의미 쿼리 (Dense용)**: 질문의 의도와 문맥을 포함한 자연어 문장을 작성하세요.
   - 예: "퇴직금 지급 기한과 청구 방법에 대한 근로기준법 규정"
3. **HyDE(가상 문서)**: 질문에 대한 예상 답변을 2문장으로 작성하세요.
   - 예: "근로기준법 제36조에 따르면 퇴직금은 퇴직 후 14일 이내에 지급해야 합니다..."

## 출력 규칙
- keyword_query: Sparse 검색용 (조사 제거, 핵심 명사만, 50자 이내)
- semantic_query: Dense 검색용 (의도 포함 자연어, 100자 이내)  
- hyde_passage: Dense 검색용 가상 문서 (2문장, 법령명/조항 포함)"""

    # --- [노드: Analyze] 질문 분석용 프롬프트 ---
    PROMPT_ANALYZE: str = """당신은 법률 질문을 심층 분석하는 전문가입니다.

## 분류
- category: 노동법, 형사법, 민사법, 기타
- intent_type: 법령조회, 절차문의, 상황판단, 권리확인, 분쟁해결, 일반상담
- query_complexity: 질문의 난이도 평가
  * simple: 단순 법령 조회, 정의 확인 (예: "근로기준법 제2조가 뭐야?")
  * medium: 일반적인 상황 판단, 절차 문의
  * complex: 복잡한 법적 해석, 여러 법령 비교, 판례 필요
- search_strategy: 법령우선, 행정해석우선, 판례필수, 종합검색
- target_doc_types: 법, 시행령, 시행규칙, 행정해석, 판정선례

## 규칙
- needs_clarification: 1~2단어만 있어 답변 불가능한 경우에만 true
- needs_case_law: 판례 언급 또는 법적 해석 쟁점이 있는 경우 true"""

    # --- [노드: Generate] Chain of Thought + In-Context Citation 프롬프트 ---
    PROMPT_GENERATE: str = """당신은 엄격한 기준을 가진 법률 AI 'A-TEAM'입니다.

## 핵심 원칙
1. **증거 기반**: 반드시 제공된 [검색된 문서]에 있는 내용만 사용하세요.
2. **Hallucination 금지**: 문서에 없는 법조문, 판례, 사실을 지어내지 마세요.
3. **엄격한 인용**: 모든 사실적 진술 뒤에 반드시 출처 인덱스를 표기하세요. (예: ...지급해야 합니다[1].)

## 답변 형식 (반드시 이 구조로 작성)

**🤔 분석**
(질문의 법적 쟁점과 적용 가능한 법조항을 분석하세요. 검색된 문서와 질문 간의 연결고리를 서술합니다.)

**📌 결론**
(핵심 답변을 1-2문장으로 명확하게 작성하세요. 반드시 출처 번호를 붙이세요[1].)

**📖 법적 근거**
- [법령명 제X조]: 해당 조항 내용 요약 [1]
- [관련 규정]: 추가 근거 요약 [2]

**💡 유의 사항**
(해석상 주의점, 예외 상황, 추가 확인이 필요한 사항을 안내하세요.)

## 인용 규칙
- 검색된 문서는 [문서 1], [문서 2], ... 형태로 제공됩니다.
- 답변에서 해당 문서를 인용할 때는 [1], [2], ... 로 표기하세요.
- 문서에 정보가 없으면 "제공된 문서에서 관련 정보를 찾을 수 없습니다"라고 명시하세요.

## 언어
- 한국어로 답변하세요.
- 법률 용어는 쉽게 풀어서 설명하세요."""

    # --- [노드: Evaluate] 답변 평가용 프롬프트 ---
    PROMPT_EVALUATE: str = """당신은 법률 답변의 품질을 평가하는 비평가입니다.

## 평가 기준
1. has_legal_basis: 법령명, 조항 번호 등 구체적 법적 근거 있는가
2. cites_retrieved_docs: 검색된 문서 내용이 반영되었는가
3. is_relevant: 질문에 직접 답하는가
4. needs_more_search: 검색 결과 부족하여 추가 검색 필요한가
5. quality_score: 1-5점

## 원칙
- 품질 3점 이상이면 통과, 2점 이하면 재검색 권장"""

    # --- [노드: Clarify] 명확화 요청 템플릿 ---
    TEMPLATE_CLARIFY: str = """안녕하세요! 질문을 잘 이해하기 위해 확인이 필요합니다.

{clarification_question}

위 내용을 포함해서 다시 질문해 주시면, 더 정확한 답변을 드릴 수 있습니다. 😊"""

    # --- [노드: Generate] 검색 결과 없음 시 답변 ---
    TEMPLATE_NO_RESULTS: str = """죄송합니다. 관련 법률 정보를 찾지 못했습니다.

다음과 같이 시도해 보세요:
1. 질문을 더 구체적으로 작성
2. 다른 키워드로 질문
3. 전문 법률 상담 권장

📌 참고: https://law.go.kr"""


# ============================================================
# [SECTION 2] Logging Setup
# ============================================================
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("LegalRAG-V8")


# ============================================================
# [SECTION 3] State Definition - LangGraph 상태 정의
# ============================================================
class AgentState(TypedDict):
    """LangGraph Agent의 상태"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_query: str
    query_analysis: Optional[dict]
    retrieved_docs: Optional[List[Document]]
    generated_answer: Optional[str]
    next_action: Optional[str]
    evaluation_result: Optional[dict]
    retry_count: Optional[int]


# ============================================================
# [SECTION 4] Reranker - 커스텀 Jina Reranker Wrapper
# ============================================================
class JinaReranker(BaseDocumentCompressor):
    """Jina Reranker Wrapper for LangChain"""
    model_name: str = "jinaai/jina-reranker-v2-base-multilingual"
    top_n: int = 7
    model: Any = None
    tokenizer: Any = None

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"

    def __init__(self, model_name: Optional[str] = None, top_n: Optional[int] = None, **kwargs):
        super().__init__(**kwargs)
        if model_name:
            self.model_name = model_name
        if top_n:
            self.top_n = top_n

        # Device selection: CUDA > MPS > CPU
        if torch.cuda.is_available():
            self.device = "cuda"
        elif torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

        logger.info(f"Loading Reranker: {self.model_name} on {self.device}")
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name, trust_remote_code=True)
        # 모델 양자화 (FP16) - optimization #8
        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name, 
            trust_remote_code=True, 
            torch_dtype=torch.float16 if self.device != "cpu" else torch.float32
        )
        self.model.to(self.device)
        self.model.eval()
        logger.info("Reranker loaded successfully")

    def compress_documents(
        self, documents: Sequence[Document], query: str, callbacks: Optional[Any] = None
    ) -> Sequence[Document]:
        if not documents:
            return []

        pairs = [[query, doc.page_content] for doc in documents]

        with torch.no_grad():
            inputs = self.tokenizer(
                pairs, padding=True, truncation=True,
                return_tensors="pt", max_length=512
            )
            # Move inputs to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            scores = self.model(**inputs).logits.squeeze(-1).float().cpu()
            scores = torch.sigmoid(scores).tolist()
            if not isinstance(scores, list):
                scores = [scores]

        # Sort and select top_n
        top_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:self.top_n]

        final_docs = []
        for i in top_indices:
            doc = documents[i]
            doc.metadata["relevance_score"] = scores[i]
            final_docs.append(doc)

        return final_docs


# ============================================================
# [SECTION 5] Pydantic Schemas - LLM 구조화된 출력용
# ============================================================
class HybridQuery(BaseModel):
    """HyDE + Hybrid Search를 위한 쿼리 확장 결과"""
    keyword_query: str = Field(
        description="BM25 검색용: 조사 제거된 핵심 법률 키워드 (예: '근로기준법 해고예고수당 부당해고')")
    semantic_query: str = Field(
        description="Vector 검색용: 질문 의도와 문맥을 포함한 자연어 문장")
    hyde_passage: str = Field(
        description="Vector 검색용 가상 문서: 예상되는 법조문 내용 (2-3문장)")


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


class AnswerEvaluation(BaseModel):
    """답변 평가 결과"""
    has_legal_basis: bool = Field(description="법적 근거 명시 여부")
    cites_retrieved_docs: bool = Field(description="검색 문서 인용 여부")
    is_relevant: bool = Field(description="답변 적합성")
    needs_more_search: bool = Field(description="추가 검색 필요 여부")
    quality_score: int = Field(description="품질 점수 (1-5)")
    improvement_suggestion: str = Field(default="", description="개선 제안")


# ============================================================
# [SECTION 6] Infrastructure Layer - 외부 리소스 연결
# ============================================================
class VectorStoreManager:
    """Qdrant 벡터스토어 관리 (Async Support)"""

    def __init__(self, config: Config):
        self.config = config
        self._load_env()
        self.embeddings = None
        self.client = None

    def _load_env(self):
        """환경 변수 로드"""
        self.collection_name = os.getenv("QDRANT_COLLECTION_NAME")
        self.qdrant_url = os.getenv("QDRANT_URL")
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY")

        if not self.qdrant_api_key:
            raise ValueError("QDRANT_API_KEY가 .env에 설정되지 않았습니다!")

    def initialize(self):
        """임베딩 모델만 초기화 (Qdrant 연결은 Lazy Loading)"""
        logger.info(f"Loading embedding model: {self.config.EMBEDDING_MODEL}")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.config.EMBEDDING_MODEL,
            model_kwargs={'trust_remote_code': True},
            encode_kwargs={'normalize_embeddings': True}
        )
        logger.info("Embedding model loaded")
        
        # Qdrant 연결은 실제 요청 시 수행 (이벤트 루프 충돌 방지)
        logger.info("Qdrant client will be initialized lazily on first request.")

    async def get_client(self) -> AsyncQdrantClient:
        """Qdrant Client Lazy Loading"""
        if self.client is None:
            logger.info("Connecting to Qdrant (Async) - Lazy Loading...")
            warnings.filterwarnings(
                'ignore', message='Api key is used with an insecure connection')
            
            self.client = AsyncQdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant_api_key,
                timeout=self.config.QDRANT_TIMEOUT,
                prefer_grpc=self.config.QDRANT_PREFER_GRPC
            )
            logger.info("Qdrant (Async) connected")
            
        return self.client

    def get_embeddings(self) -> HuggingFaceEmbeddings:
        if self.embeddings is None:
            raise ValueError("Embeddings model is not initialized. Call initialize() first.")
        return self.embeddings

    def get_collection_name(self) -> str:
        if self.collection_name is None:
            raise ValueError("Collection name is not set in environment variables.")
        return self.collection_name


class SparseEmbeddingManager:
    """Sparse Embedding (BGE-M3) 관리"""

    def __init__(self, config: Config):
        self.config = config
        self.model = None

    def initialize(self):
        """BGE-M3 모델 로딩 (Sparse)"""
        try:
            logger.info(
                f"Loading Sparse Model: {self.config.SPARSE_EMBEDDING_MODEL}")

            # Device check (Auto)
            use_fp16 = torch.cuda.is_available()
            self.model = BGEM3FlagModel(
                self.config.SPARSE_EMBEDDING_MODEL,
                use_fp16=use_fp16
            )
            logger.info("Sparse Model loaded (BGE-M3)")
        except Exception as e:
            logger.error(f"Failed to load Sparse Model: {e}")
            self.model = None

    def encode_query(self, query: str) -> Optional[models.SparseVector]:
        """쿼리를 Sparse Vector로 변환"""
        if not self.model:
            return None

        try:
            # BGE-M3 encode returns dict with 'lexical_weights'
            output = self.model.encode(
                query,
                return_dense=False,
                return_sparse=True,
                return_colbert_vecs=False
            )
            # Dict[str, float] where str is token_id
            weights = output['lexical_weights']
            if not isinstance(weights, dict):
                 weights = {}

            return models.SparseVector(
                indices=list(map(int, weights.keys())),
                values=list(map(float, weights.values()))
            )
        except Exception as e:
            logger.error(f"Sparse encoding failed: {e}")
            return None


# ============================================================
# [SECTION 7] Logic Layer - LangGraph 노드 및 워크플로우 구성
# ============================================================
class LegalRAGBuilder:
    """법률 RAG 그래프 빌더 (Async)"""

    def __init__(self, config: Config):
        self.config = config
        self.llm = None
        self.embeddings = None
        self.client = None  # AsyncQdrantClient
        self.sparse_manager = None
        self.query_expander = None
        self.reranker = None
        self.vs_manager = None

    def set_components(self, vs_manager: 'VectorStoreManager', reranker: 'JinaReranker'):
        """미리 로딩된 컴포넌트 주입"""
        self.vs_manager = vs_manager
        self.reranker = reranker

    def _init_infrastructure(self):
        """인프라 초기화"""
        # Vector Store Manager (Async)
        if not self.vs_manager:
            self.vs_manager = VectorStoreManager(self.config)
            self.vs_manager.initialize()
        
        self.embeddings = self.vs_manager.get_embeddings()

        # Sparse Embedding Manager
        if not self.sparse_manager:
            self.sparse_manager = SparseEmbeddingManager(self.config)
            self.sparse_manager.initialize()

        # LLM
        logger.info(f"Initializing LLM: {self.config.LLM_MODEL}")
        self.llm = ChatOpenAI(
            model=self.config.LLM_MODEL,
            temperature=self.config.LLM_TEMPERATURE,
            streaming=True
        )

        # Query Expander
        self.query_expander = self._create_query_expander()

        # Reranker
        if not self.reranker:
            self.reranker = JinaReranker(
                model_name=self.config.RERANKER_MODEL,
                top_n=self.config.TOP_K_RERANK
            )

    @traceable(run_type="retriever", name="Qdrant Hybrid Search")
    async def _execute_search(self, client: AsyncQdrantClient, dense_vec: List[float], sparse_vec: Optional[models.SparseVector], collection_name: str, limit: int) -> List[Document]:
        """Qdrant 검색 수행 (LangSmith 추적용)"""
        prefetch = [
            models.Prefetch(
                query=dense_vec,
                using="dense",
                limit=limit,
            )
        ]

        if sparse_vec:
            prefetch.append(
                models.Prefetch(
                    query=sparse_vec,
                    using="sparse",
                    limit=limit,
                )
            )

        # Execute Search
        results = await client.query_points(
            collection_name=collection_name,
            prefetch=prefetch,
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit
        )

        # Convert to Documents
        vector_docs = []
        for point in results.points:
            payload = point.payload
            text = payload.get("text", "")
            if text:
                doc = Document(
                    page_content=text,
                    metadata={k: v for k, v in payload.items()
                                if k != "text"}
                )
                doc.metadata["relevance_score"] = point.score
                vector_docs.append(doc)
        
        return vector_docs


    def _create_query_expander(self):
        """Query Expander 생성 [사용 프롬프트: PROMPT_QUERY_EXPANSION] - HyDE + Hybrid"""
        structured_llm = self.llm.with_structured_output(HybridQuery)

        expansion_prompt = ChatPromptTemplate.from_messages([
            ("system", self.config.PROMPT_QUERY_EXPANSION),
            ("human", "{query}")
        ])

        async def expand_query(query: str) -> HybridQuery:
            try:
                # Async invoke
                chain = expansion_prompt | structured_llm
                # Type hint for IDE
                result: HybridQuery = await chain.ainvoke({"query": query})  # type: ignore
                logger.info(
                    f"HyDE Query Generated - Keyword: {result.keyword_query[:40]}...")
                return result
            except Exception as e:
                logger.warning(f"Query expansion failed: {e}")
                # Fallback
                return HybridQuery(
                    keyword_query=query,
                    semantic_query=query,
                    hyde_passage=query
                )

        return expand_query

    # --- Nodes (Async) ---

    def _create_analyze_node(self):
        """[노드: Analyze] 질문 분석 노드 (Async)"""
        structured_llm = self.llm.with_structured_output(QueryAnalysis)

        analyze_prompt = ChatPromptTemplate.from_messages([
            ("system", self.config.PROMPT_ANALYZE),
            ("human", "{query}")
        ])

        async def analyze_query(state: AgentState) -> dict:
            query = state["user_query"]
            logger.info(f"Analyzing query: {query[:50]}...")

            chain = analyze_prompt | structured_llm
            analysis: QueryAnalysis = await chain.ainvoke({"query": query})  # type: ignore

            logger.info(
                f"Analysis: category={analysis.category}, intent={analysis.intent_type}")

            return {"query_analysis": analysis.model_dump()}

        return analyze_query

    def _create_clarify_node(self):
        """[노드: Clarify] 명확화 요청 노드"""
        template = self.config.TEMPLATE_CLARIFY

        async def request_clarification(state: AgentState) -> dict:
            analysis = state.get("query_analysis", {})
            clarification_q = analysis.get(
                "clarification_question", "질문을 좀 더 구체적으로 해주시겠어요?")

            answer = template.format(clarification_question=clarification_q)
            return {"generated_answer": answer, "next_action": "end"}

        return request_clarification

    def _create_search_node(self):
        """하이브리드 검색 노드 (Async + Qdrant Native Hybrid)"""
        # client = self.client  # 여기서는 client를 미리 가져올 수 없음 (Lazy)
        embeddings = self.embeddings
        sparse_manager = self.sparse_manager
        query_expander = self.query_expander
        reranker = self.reranker
        config = self.config
        collection_name = self.vs_manager.get_collection_name()

        async def search_documents(state: AgentState) -> dict:
            original_query = state["user_query"]
            analysis = state.get("query_analysis", {})
            related_laws = analysis.get("related_laws", [])

            # 0. Get Client (Lazy Loading)
            client = await self.vs_manager.get_client()

            # 1. Query Expansion (Async)
            keyword_query = original_query
            vector_query = original_query

            if query_expander:
                hybrid = await query_expander(original_query)
                keyword_query = hybrid.keyword_query
                # Dense: HyDE 우선, 없으면 semantic_query
                vector_query = hybrid.hyde_passage if hybrid.hyde_passage else hybrid.semantic_query

                logger.info(f"[Query] Keyword(Sparse): {keyword_query}")
                logger.info(f"[Query] Vector(Dense): {vector_query[:50]}...")

            # 2. Embedding Generation (Parallel: Dense + Sparse)
            # Embedding computation is CPU bound, run in thread if needed,
            # but usually fast enough or we can use asyncio.to_thread

            async def get_dense_vec():
                return await asyncio.to_thread(embeddings.embed_query, vector_query)

            async def get_sparse_vec():
                if sparse_manager:
                    return await asyncio.to_thread(sparse_manager.encode_query, keyword_query)
                return None

            dense_vec, sparse_vec = await asyncio.gather(get_dense_vec(), get_sparse_vec())

            # 3. Qdrant Native Hybrid Search (Traced)
            try:
                vector_docs = await self._execute_search(
                    client=client,
                    dense_vec=dense_vec,
                    sparse_vec=sparse_vec,
                    collection_name=collection_name,
                    limit=config.TOP_K_VECTOR
                )
                
                logger.info(f"Hybrid Search Results: {len(vector_docs)} docs")

            except Exception as e:
                logger.error(f"Search failed: {e}")
                import traceback
                traceback.print_exc()
                return {"retrieved_docs": []}

            # 4. Reranking (Async wrap or sync)
            if not vector_docs:
                return {"retrieved_docs": []}

            # Reranker logic (Sync) inside Async
            def rerank_logic(docs, query):
                if not reranker:
                    return docs
                return reranker.compress_documents(docs, query)

            reranked_docs = await asyncio.to_thread(rerank_logic, vector_docs, original_query)

            # 5. Filtering & Boosting
            final_docs = []
            for doc in reranked_docs:
                score = doc.metadata.get('relevance_score', 0)

                # Boosting
                law_name = doc.metadata.get('law_name', '')
                for rel_law in related_laws:
                    if rel_law in law_name:
                        score += 0.1
                        doc.metadata['boosted'] = True
                        break

                if score >= config.RELEVANCE_THRESHOLD:
                    final_docs.append(doc)

            # Sort and Slice
            final_docs.sort(key=lambda x: x.metadata.get(
                'relevance_score', 0), reverse=True)
            final_docs = final_docs[:config.TOP_K_FINAL]

            logger.info(f"Final selected: {len(final_docs)} docs")
            for i, doc in enumerate(final_docs, 1):
                meta = doc.metadata
                law = meta.get('law_name', '법령명')
                art = meta.get('article_no', '')
                title = meta.get('article_title', '') or meta.get('title', '')
                score = meta.get('relevance_score', 0)
                logger.info(f"   [{i}] {law} 제{art}조 {title} (Score: {score:.4f})")

            return {"retrieved_docs": final_docs}

        return search_documents

    def _create_generate_node(self):
        """[노드: Generate] 답변 생성 노드 (Async)"""
        llm = self.llm
        system_prompt = self.config.PROMPT_GENERATE
        no_results_template = self.config.TEMPLATE_NO_RESULTS

        answer_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", """사용자 질문: {query}

📚 검색된 법령/문서:
{context}

{case_law_notice}

위 자료를 바탕으로 질문에 답변해주세요.""")
        ])

        async def generate_answer(state: AgentState) -> dict:
            query = state["user_query"]
            docs = state.get("retrieved_docs", [])
            analysis = state.get("query_analysis", {})
            needs_case_law = analysis.get("needs_case_law", False)

            logger.info("Generating answer...")

            # Format context
            if docs:
                context_parts = []
                for i, doc in enumerate(docs, 1):
                    meta = doc.metadata
                    law_name = meta.get("law_name", "")
                    article = meta.get("article_no", "")
                    title = meta.get(
                        "article_title", "") or meta.get("title", "")
                    content = doc.page_content[:800]

                    header = f"[문서 {i}]"
                    if law_name:
                        header += f" {law_name}"
                        if article:
                            header += f" 제{article}조"
                    if title:
                        header += f" - {title}"

                    context_parts.append(f"{header}\n{content}\n")

                context = "\n".join(context_parts)
            else:
                context = "(관련 법령 문서가 검색되지 않았습니다)"

            case_law_notice = ""
            if needs_case_law:
                case_law_notice = "⚠️ 참고: 판례 검색이 필요하나 현재 DB에 포함되어 있지 않습니다."

            if not docs:
                answer = no_results_template
            else:
                chain = answer_prompt | llm
                response = await chain.ainvoke({
                    "query": query,
                    "context": context,
                    "case_law_notice": case_law_notice
                })
                answer = response.content

            logger.info("Answer generated")
            return {"generated_answer": answer}

        return generate_answer

    def _create_evaluate_node(self):
        """[노드: Evaluate] 답변 평가 노드 (Async)"""
        structured_llm = self.llm.with_structured_output(AnswerEvaluation)

        evaluate_prompt = ChatPromptTemplate.from_messages([
            ("system", self.config.PROMPT_EVALUATE),
            ("human", """## 질문
{query}

## 검색된 문서 요약
{context_summary}

## 생성된 답변
{answer}

평가해주세요.""")
        ])

        async def evaluate_answer(state: AgentState) -> dict:
            query = state["user_query"]
            answer = state.get("generated_answer", "")
            docs = state.get("retrieved_docs", [])
            retry_count = state.get("retry_count", 0) or 0

            logger.info(f"Evaluating answer (attempt {retry_count + 1})")

            if docs:
                context_summary = "\n".join([
                    f"- {doc.metadata.get('law_name', '문서')}: {doc.page_content[:100]}..."
                    for doc in docs[:5]
                ])
            else:
                context_summary = "(검색된 문서 없음)"

            chain = evaluate_prompt | structured_llm
            evaluation: AnswerEvaluation = await chain.ainvoke({  # type: ignore
                "query": query,
                "context_summary": context_summary,
                "answer": answer
            })

            logger.info(
                f"Evaluation: score={evaluation.quality_score}, needs_more={evaluation.needs_more_search}")

            return {
                "evaluation_result": evaluation.model_dump(),
                "retry_count": retry_count + 1
            }

        return evaluate_answer

    # --- Routing ---

    def _route_after_analysis(self, state: AgentState) -> Literal["clarify", "search"]:
        analysis = state.get("query_analysis", {})
        if analysis.get("needs_clarification", False):
            return "clarify"
        return "search"

    def _route_after_evaluation(self, state: AgentState) -> Literal["search", "end"]:
        evaluation = state.get("evaluation_result", {})
        retry_count = state.get("retry_count", 0) or 0

        if retry_count >= self.config.MAX_RETRY:
            logger.warning("Max retry reached")
            return "end"

        if evaluation.get("needs_more_search", False) and evaluation.get("quality_score", 3) <= 2:
            logger.info("Retrying search...")
            return "search"

        return "end"
    
    def _route_after_generate(self, state: AgentState) -> Literal["evaluate", "end"]:
        """답변 생성 후 라우팅: 난이도에 따라 평가 단계 조건부 실행"""
        analysis = state.get("analysis", {})
        complexity = analysis.get("query_complexity", "medium")
        
       # simple 질문은 평가 건너뛰고 바로 종료
        if complexity == "simple":
            logger.info("Simple query detected - skipping evaluation")
            return "end"
        
        # medium, complex는 평가 진행
        logger.info(f"Query complexity: {complexity} - proceeding to evaluation")
        return "evaluate"

    # --- Build Graph ---

    def build(self) -> CompiledStateGraph:
        """LangGraph 빌드"""
        self._init_infrastructure()

        builder = StateGraph(AgentState)

        # Nodes
        builder.add_node("analyze", self._create_analyze_node())
        builder.add_node("clarify", self._create_clarify_node())
        builder.add_node("search", self._create_search_node())
        builder.add_node("generate", self._create_generate_node())
        builder.add_node("evaluate", self._create_evaluate_node())

        # Edges
        builder.set_entry_point("analyze")

        builder.add_conditional_edges(
            "analyze",
            self._route_after_analysis,
            {
                "clarify": "clarify",
                "search": "search"
            }
        )

        builder.add_edge("clarify", END)
        builder.add_edge("search", "generate")
        
        # generate → evaluate OR end (난이도에 따라 조건부)
        builder.add_conditional_edges(
            "generate",
            self._route_after_generate,
            {"evaluate": "evaluate", "end": END}
        )

        builder.add_conditional_edges(
            "evaluate",
            self._route_after_evaluation,
            {"search": "search", "end": END}
        )

        return builder.compile()


# ============================================================
# [SECTION 8] Execution Layer - 실행 진입점
# ============================================================
async def main():
    print("🚀 Legal RAG Chatbot V8 (Async/Hybrid) Starting...")

    config = Config()
    app = LegalRAGBuilder(config).build()

    # Test Query
    # initial_query = "퇴직금 지급 기한과 안 줬을 때 신고 방법 알려줘"
    initial_query = "근로계약서 미작성시 벌금은 얼마인가요?"

    print(f"\n👤 질문: {initial_query}\n")

    initial_state = {
        "messages": [HumanMessage(content=initial_query)],
        "user_query": initial_query,
        "retry_count": 0
    }

    try:
        result = await app.ainvoke(initial_state)

        print("\n" + "=" * 50)
        print("🤖 AI 답변:")
        print("=" * 50)
        print(result.get("generated_answer", "답변 생성 실패"))
        print("=" * 50)

        evaluation = result.get("evaluation_result", {})
        print(f"📊 평가 점수: {evaluation.get('quality_score')}점")

    except Exception as e:
        logger.error(f"Execution failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
