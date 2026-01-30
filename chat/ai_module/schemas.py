from typing import Annotated, TypedDict, Sequence, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# ============================================================
# [SECTION 3] State Definition - LangGraph 상태 정의
# ============================================================
class AgentState(TypedDict):
    """LangGraph Agent의 상태"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_query: str
    query_analysis: Optional[dict]
    retrieved_docs: Optional[List[Any]] # avoiding Document type hint circular import issues if possible, or use Any
    generated_answer: Optional[str]
    next_action: Optional[str]
    evaluation_result: Optional[dict]
    retry_count: Optional[int]


# ============================================================
# [SECTION 5] Pydantic Schemas - LLM 구조화된 출력용
# ============================================================
class ExpandedQuery(BaseModel):
    """[Node A] Multi-Query Expansion 결과"""
    original_query: str = Field(description="사용자 원본 질문")
    keyword_query: str = Field(description="BM25 검색용 핵심 키워드 조합")
    # HyDE 제거: 가상 답변 대신 유사 질문 확장
    expanded_queries: List[str] = Field(
        description="동의어/유의어를 포함한 확장된 3~4개의 법률 쿼리 리스트",
        default_factory=list
    )


class QueryAnalysis(BaseModel):
    """[Node B] 질문 분석 및 모호성 판단 결과"""
    category: str = Field(description="법률 분야: 노동법, 노동법 외, 기타(일상)")
    intent_type: str = Field(description="질문 의도: 법령조회, 절차문의, 상황판단, 권리확인, 분쟁해결, 일반상담")
    
    # Ambiguity Router fields
    is_ambiguous: bool = Field(description="질문이 모호하여 추가 정보가 필요한지 여부 (Specific vs Ambiguous)")
    missing_info: List[str] = Field(
        description="판단을 위해 부족한 필수 정보 목록 (예: '5인 이상 여부', '근로 기간')",
        default_factory=list
    )
    
    clarification_question: str = Field(default="", description="[Node C] 사용구: 사용자에게 정보를 요청하는 역질문")
    
    query_complexity: str = Field(default="medium", description="질문 난이도: simple, medium, complex")
    user_situation: str = Field(default="", description="사용자 상황 요약")
    core_question: str = Field(default="", description="문맥이 해소된 검색용 핵심 질문 (Standalone Query)")
    related_laws: List[str] = Field(default_factory=list, description="관련 법률명")


class AnswerEvaluation(BaseModel):
    """답변 평가 결과"""
    has_legal_basis: bool = Field(description="법적 근거 명시 여부")
    cites_retrieved_docs: bool = Field(description="검색 문서 인용 여부")
    is_relevant: bool = Field(description="답변 적합성")
    needs_more_search: bool = Field(description="추가 검색 필요 여부")
    quality_score: int = Field(description="품질 점수 (1-5)")
    improvement_suggestion: str = Field(default="", description="개선 제안")
