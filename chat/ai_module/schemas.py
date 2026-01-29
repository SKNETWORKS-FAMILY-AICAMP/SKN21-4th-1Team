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
    category: str = Field(description="법률 분야: 노동법, 노동법 외, 기타(일상)")
    intent_type: str = Field(description="질문 의도: 법령조회, 절차문의, 상황판단, 권리확인, 분쟁해결, 일반상담")
    needs_clarification: bool = Field(default=False, description="질문 모호 여부")
    needs_case_law: bool = Field(default=False, description="판례 검색 필요 여부")
    query_complexity: str = Field(default="medium", description="질문 난이도: simple, medium, complex")
    clarification_question: str = Field(default="", description="명확화 질문")
    user_situation: str = Field(default="", description="사용자 상황 요약")
    core_question: str = Field(default="", description="사용자가 최종적으로 알고싶어하는 핵심 질문")
    related_laws: List[str] = Field(default_factory=list, description="관련 법률명")


class AnswerEvaluation(BaseModel):
    """답변 평가 결과"""
    has_legal_basis: bool = Field(description="법적 근거 명시 여부")
    cites_retrieved_docs: bool = Field(description="검색 문서 인용 여부")
    is_relevant: bool = Field(description="답변 적합성")
    needs_more_search: bool = Field(description="추가 검색 필요 여부")
    quality_score: int = Field(description="품질 점수 (1-5)")
    improvement_suggestion: str = Field(default="", description="개선 제안")
