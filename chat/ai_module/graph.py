import asyncio
import logging
from typing import Literal, List, Optional
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langsmith import traceable
from qdrant_client import AsyncQdrantClient, models

from .config import Config
from .schemas import AgentState, HybridQuery, QueryAnalysis, AnswerEvaluation
from .infrastructure import VectorStoreManager, SparseEmbeddingManager, JinaReranker
from . import prompts

logger = logging.getLogger("LegalRAG-V8")

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

        # Reranker - if not injected
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
            ("system", prompts.PROMPT_QUERY_EXPANSION),
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
            ("system", prompts.PROMPT_ANALYZE),
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
        template = prompts.TEMPLATE_CLARIFY

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
        
        # Collection name might be dynamic or static
        # vs_manager.get_collection_name() retrieves it
        
        async def search_documents(state: AgentState) -> dict:
            original_query = state["user_query"]
            analysis = state.get("query_analysis", {})
            related_laws = analysis.get("related_laws", [])
            collection_name = self.vs_manager.get_collection_name()

            # 0. Create Client (Fresh per request)
            client = await self.vs_manager.create_client()

            try:
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
                async def get_dense_vec():
                    return await asyncio.to_thread(embeddings.embed_query, vector_query)

                async def get_sparse_vec():
                    if sparse_manager:
                        return await asyncio.to_thread(sparse_manager.encode_query, keyword_query)
                    return None

                dense_vec, sparse_vec = await asyncio.gather(get_dense_vec(), get_sparse_vec())

                # 3. Qdrant Native Hybrid Search (Traced)
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
            finally:
                # Clean up client
                if client:
                    await client.close()

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
        system_prompt = prompts.PROMPT_GENERATE
        no_results_template = prompts.TEMPLATE_NO_RESULTS

        answer_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
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
            ("system", prompts.PROMPT_EVALUATE),
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
        analysis = state.get("query_analysis", {}) # Fixed key: was 'analysis' in original, but 'query_analysis' is the state key
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
