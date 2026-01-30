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
from .schemas import AgentState, ExpandedQuery, QueryAnalysis, AnswerEvaluation
from .infrastructure import VectorStoreManager, SparseEmbeddingManager, JinaReranker
from . import prompts

# 노동법 목록 imports for fuzzy matching
import difflib
import sys
import os

# ============================================================
# [SECTION 7] Logic Layer - LangGraph 노드 및 워크플로우 구성
# ============================================================
logger = logging.getLogger("LegalRAG-V8")

# 현재 파일 위치: chat/ai_module/graph.py
# labor_laws_list.py는 프로젝트 루트에 있음
try:
    from chat.ai_module.labor_laws_list import LABOR_LAWS_UNIQUE
except ImportError:
    # 경로 문제 발생 시 처리 (백업)
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from labor_laws_list import LABOR_LAWS_UNIQUE

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
        """[Node A: Query Rewriting] Query Expander 생성 (Multi-Query Expansion)"""
        structured_llm = self.llm.with_structured_output(ExpandedQuery)

        expansion_prompt = ChatPromptTemplate.from_messages([
            ("system", prompts.PROMPT_QUERY_EXPANSION),
            ("human", "{query}")
        ])

        async def expand_query(query: str) -> ExpandedQuery:
            try:
                # Async invoke
                chain = expansion_prompt | structured_llm
                # Type hint for IDE
                result: ExpandedQuery = await chain.ainvoke({"query": query})  # type: ignore
                logger.info(
                    f"[Node A] Expanded Queries: {result.expanded_queries}")
                return result
            except Exception as e:
                logger.warning(f"Query expansion failed: {e}")
                # Fallback
                return ExpandedQuery(
                    original_query=query,
                    keyword_query=query,
                    expanded_queries=[query]
                )

        return expand_query

    # --- Nodes (Async) ---

    def _create_analyze_node(self):
        """[Node B: Analyze] 질문 분석 및 모호성 판단 (Ambiguity Router)"""
        structured_llm = self.llm.with_structured_output(QueryAnalysis)

        analyze_prompt = ChatPromptTemplate.from_messages([
            ("system", prompts.PROMPT_ANALYZE),
            MessagesPlaceholder(variable_name="messages"),
            ("human", "{query}")
        ])

        async def analyze_query(state: AgentState) -> dict:
            query = state["user_query"]
            logger.info(f"[Node B] Analyzing query: {query[:50]}...")

            chain = analyze_prompt | structured_llm
            analysis: QueryAnalysis = await chain.ainvoke({
                "query": query,
                "messages": state["messages"]
            })  # type: ignore

            logger.info(
                f"Analysis: category={analysis.category}, intent={analysis.intent_type}, Ambiguous={analysis.is_ambiguous}")

            return {"query_analysis": analysis.model_dump()}

        return analyze_query

    def _create_verify_law_node(self):
        """[노드: Verify Law] 법령 존재 여부 검증 (Async)"""
        
        async def verify_law(state: AgentState) -> dict:
            analysis = state.get("query_analysis", {})
            related_laws = analysis.get("related_laws", [])
            query = state["user_query"]
            
            # 1. 법령 언급이 없거나 노동법이 아니면 패스
            if not related_laws or analysis.get("category") != "노동법":
                return {"next_action": "search"}

            target_law = related_laws[0]
            
            # --- [New] Clean Law Name (Suffix Removal) ---
            # "고용노동법 제34조" -> "고용노동법"
            original_target = target_law
            target_law = self._clean_law_name(target_law)
            
            logger.info(f"[Verify] Target: '{original_target}' -> Cleaned: '{target_law}'")
            
            # 2. 검증 로직 개선 (Fuzzy Match -> DB Check)
            verified_law = None
            
            # 2-1. Static List Check (Exact + Fuzzy with Threshold)
            if target_law in LABOR_LAWS_UNIQUE:
                verified_law = target_law
            else:
                # Fuzzy matching with ratio check
                matches = difflib.get_close_matches(target_law, LABOR_LAWS_UNIQUE, n=1, cutoff=0.4)
                if matches:
                    candidate = matches[0]
                    # Calculate exact ratio
                    ratio = difflib.SequenceMatcher(None, target_law, candidate).ratio()
                    logger.info(f"Fuzzy match candidate: {candidate}, Ratio: {ratio:.4f}")
                    
                    if ratio >= 0.8:
                        # High confidence: Auto-correct
                        verified_law = candidate
                        logger.info(f"Auto-correcting (High confidence): {target_law} -> {verified_law}")
                    else:
                        # Medium confidence (0.4 <= ratio < 0.8): Ambiguous -> Suggestion
                        # Will be handled in the 'else' block of 'if verified_law:'
                        logger.info(f"Ambiguous match (Medium confidence): {target_law} -> {candidate}")
                        pass
            
            # 2-2. DB Check (If not verified yet)
            if not verified_law:
                exists = await self.vs_manager.check_law_exists(target_law)
                if exists:
                    verified_law = target_law

            if verified_law:
                logger.info(f"Law verification passed: {verified_law}")
                
                # Update analysis with corrected law name if needed
                if verified_law != target_law:
                    logger.info(f"Correcting query: '{target_law}' -> '{verified_law}'")
                    new_query = query.replace(original_target, verified_law, 1)
                    analysis["related_laws"] = [verified_law]
                    
                    return {
                        "next_action": "search",
                        "user_query": new_query,
                        "query_analysis": analysis
                    }
                
                return {"next_action": "search"}
            else:
                logger.info(f"Law verification failed/ambiguous: {target_law}")
                
                # 3. 제안 (유사 법령 찾기)
                # Matches are already calculated or can be re-fetched.
                # Use strict cutoff for suggestion to avoid noise, but here we want to explain ambiguity.
                suggestions = difflib.get_close_matches(target_law, LABOR_LAWS_UNIQUE, n=3, cutoff=0.4)
                
                if suggestions:
                    suggestion_str = ", ".join([f"**'{s}'**" for s in suggestions])
                    msg = f"말씀하신 **'{target_law}'**은(는) 데이터베이스에 없지만, 비슷한 법령이 있습니다.\n혹시 {suggestion_str}을(를) 말씀하시는 건가요?"
                else:
                    msg = f"죄송합니다, 말씀하신 **'{target_law}'**은(는) 현재 노동법 데이터베이스에 등록되어 있지 않습니다. 정확한 법령명을 확인해 주시겠어요?"
                
                return {
                    "generated_answer": msg,
                    "next_action": "clarify_end" # End flow and show message
                }

        return verify_law

    def _create_clarify_node(self):
        """[Node C: Clarify] 역질문 생성 에이전트"""
        
        # 1. 템플릿 방식 대신 LLM 생성 방식 사용 (TEMPLATE_CLARIFY_GENERATOR)
        clarify_prompt = ChatPromptTemplate.from_messages([
            ("system", prompts.TEMPLATE_CLARIFY_GENERATOR),
            MessagesPlaceholder(variable_name="messages"),
            ("human", "{query}")
        ])

        async def request_clarification(state: AgentState) -> dict:
            query = state["user_query"]
            analysis = state.get("query_analysis", {})
            missing_info_list = analysis.get("missing_info", [])
            missing_str = ", ".join(missing_info_list) if missing_info_list else "구체적인 사실관계"
            
            logger.info(f"[Node C] Generating clarification for missing: {missing_str}")

            chain = clarify_prompt | self.llm
            response = await chain.ainvoke({
                "query": query,
                "messages": state["messages"],
                "missing_info": missing_str
            })
            
            return {"generated_answer": response.content, "next_action": "end"}

        return request_clarification

    def _create_search_node(self):
        """하이브리드 검색 노드 (Multi-Query Expansion + RRF)"""
        # client = self.client  # 여기서는 client를 미리 가져올 수 없음 (Lazy)
        embeddings = self.embeddings
        sparse_manager = self.sparse_manager
        query_expander = self.query_expander
        reranker = self.reranker
        config = self.config
        
        async def search_documents(state: AgentState) -> dict:
            analysis = state.get("query_analysis", {})
            # [Fix] Use core_question (standalone) if available, otherwise user_query
            search_target = analysis.get("core_question")
            if not search_target:
                search_target = state["user_query"]
                
             # 카테고리가 노동법 외인 경우 검색 최소화 또는 건너뛰기인데,
            # Flow상 verify_law -> search로 넘어온 것이므로 검색 진행
                
            logger.info(f"Searching with query (Core): {search_target}")
            
            related_laws = analysis.get("related_laws", [])
            collection_name = self.vs_manager.get_collection_name()

            # 0. Create Client
            client = await self.vs_manager.create_client()

            all_results = []

            try:
                # 1. Query Expansion (Node A)
                expanded = await query_expander(search_target)
                
                # Multi-Query Search List
                search_queries = [expanded.keyword_query] # 기본 키워드 쿼리
                search_queries.extend(expanded.expanded_queries) # 확장된 쿼리들
                
                # 중복 제거 및 Top 3 제한
                search_queries = list(dict.fromkeys(search_queries))[:4]
                logger.info(f"[Search] Executing multi-queries: {search_queries}")
                
                # 2. Parallel Search Execution
                async def perform_single_search(q_text):
                    # Embed
                    d_vec = await asyncio.to_thread(embeddings.embed_query, q_text)
                    s_vec = None
                    if sparse_manager:
                        s_vec = await asyncio.to_thread(sparse_manager.encode_query, q_text) # 키워드 쿼리는 q_text 그대로 사용 (Note: q_text might contain naturally formulated query, but split by spacer is handled inside encode_query?? No, expecting tokens. But SparseBM25 usually takes raw text. Checking logic assumed safe.)
                    
                    return await self._execute_search(
                        client=client,
                        dense_vec=d_vec,
                        sparse_vec=s_vec,
                        collection_name=collection_name,
                        limit=5 # 각 쿼리당 5개만 가져와서 합침
                    )

                tasks = [perform_single_search(q) for q in search_queries]
                results_lists = await asyncio.gather(*tasks)
                
                # 3. Merge & Deduplicate (Simple RRF concept or Score Max)
                unique_docs = {}
                for res_list in results_lists:
                    for doc in res_list:
                        # RRF style simple scoring or just Max score override
                        # ID 대신 content hash나 metadata로 중복 체크
                        doc_id = doc.metadata.get('id') or doc.page_content[:20]
                        if doc_id not in unique_docs:
                            unique_docs[doc_id] = doc
                        else:
                            # 이미 있으면 점수 더 높은걸로 교체 (Soft selection)
                            if doc.metadata.get('relevance_score', 0) > unique_docs[doc_id].metadata.get('relevance_score', 0):
                                unique_docs[doc_id] = doc
                
                vector_docs = list(unique_docs.values())
                logger.info(f"Merged Multi-Query Results: {len(vector_docs)} docs")

            except Exception as e:
                logger.error(f"Search failed: {e}")
                import traceback
                traceback.print_exc()
                return {"retrieved_docs": []}
            finally:
                if client:
                    await client.close()

            # 4. Reranking
            if not vector_docs:
                return {"retrieved_docs": []}

            # Reranker logic
            def rerank_logic(docs, query):
                if not reranker:
                    return docs
                return reranker.compress_documents(docs, query)

            reranked_docs = await asyncio.to_thread(rerank_logic, vector_docs, search_target) # Reranking은 원본 쿼리(Core) 기준

            # 5. Filtering & Boosting
            final_docs = []
            for doc in reranked_docs:
                score = doc.metadata.get('relevance_score', 0)

                # Boosting logic (Same as before)
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
        """[노드: Generate] 답변 생성 노드 (Async) - intent별 프롬프트 적용"""
        llm = self.llm

        async def generate_answer(state: AgentState) -> dict:
            query = state["user_query"]
            docs = state.get("retrieved_docs", [])
            analysis = state.get("query_analysis", {})
            
            # 분석 결과에서 정보 추출
            intent_type = analysis.get("intent_type", "일반상담")
            category = analysis.get("category", "노동법")
            needs_case_law = analysis.get("needs_case_law", False)

            logger.info(f"Generating answer for intent: {intent_type}, category: {category}")

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

            # ========== 핵심 변경: intent별 프롬프트 선택 ==========
            if category == "기타(일상)":
                # 일상 대화: PROMPT_DAILY_LIFE 사용 (Context 불필요)
                daily_prompt = ChatPromptTemplate.from_messages([
                    ("system", prompts.PROMPT_DAILY_LIFE),
                    MessagesPlaceholder(variable_name="messages"),
                    ("human", "{query}")
                ])
                chain = daily_prompt | llm
                response = await chain.ainvoke({
                    "messages": state["messages"],
                    "query": query
                })
                answer = response.content
                logger.info("Daily life conversation generated")

            elif category == "노동법 외":
                # 노동법 외: 검색 생략하고 안내 메시지 반환
                answer = self._generate_no_results_message(category, query, analysis)
                logger.info("Out of scope message generated")

            elif not docs:
                # 노동법이지만 문서 없음 → 일반적인 검색 실패 메시지
                answer = self._generate_no_results_message(category, query, analysis)
            
            else:
                # 노동법 + 문서 있음 → RAG 답변 생성
                system_prompt = self._select_prompt_by_intent(intent_type)
                
                answer_prompt = ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    MessagesPlaceholder(variable_name="messages"),
                    ("human", """사용자 질문: {query}

📚 검색된 법령/문서:
{context}

{case_law_notice}

위 자료를 바탕으로 질문에 답변해주세요.""")
                ])

                chain = answer_prompt | llm
                response = await chain.ainvoke({
                    "messages": state["messages"],
                    "query": query,
                    "context": context,
                    "case_law_notice": case_law_notice
                })
                answer = response.content
                logger.info("Legal RAG Answer generated")

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

    # --- Helper Methods for Prompt Selection ---

    def _select_prompt_by_intent(self, intent_type: str) -> str:
        """intent_type에 따라 적절한 프롬프트 선택"""
        prompt_map = {
            "법령조회": prompts.PROMPT_GENERATE_LAW_LOOKUP,
            "절차문의": prompts.PROMPT_GENERATE_PROCEDURE,
            "상황판단": prompts.PROMPT_GENERATE_SITUATION,
            "권리확인": prompts.PROMPT_GENERATE_RIGHTS,
            "분쟁해결": prompts.PROMPT_GENERATE_DISPUTE,
            "일반상담": prompts.PROMPT_GENERATE
        }
        selected = prompt_map.get(intent_type, prompts.PROMPT_GENERATE)
        logger.info(f"Selected prompt for intent '{intent_type}'")
        return selected

    def _generate_no_results_message(self, category: str, query: str, analysis: dict) -> str:
        """답변 불가 시 맞춤형 메시지 생성"""
        
        # 노동법 외 분야 질문인 경우
        if category != "노동법":
            # 질문에서 법령명 추출 시도
            detected_law = self._extract_law_name(query, analysis)
            
            return prompts.TEMPLATE_NO_RESULTS_OUT_OF_SCOPE.format(
                detected_law=detected_law
            )
        
        # 노동법이지만 검색 결과 없음
        return prompts.TEMPLATE_NO_RESULTS_NO_DOCS.format(query=query)

    def _extract_law_name(self, query: str, analysis: dict) -> str:
        """질문에서 법령명 추출 (간단한 휴리스틱)"""
        import re
        
        # related_laws에서 추출
        related_laws = analysis.get("related_laws", [])
        if related_laws:
            return related_laws[0]
        
        # 질문 텍스트에서 "~법" 패턴 찾기
        law_pattern = r'([가-힣]+법)'
        matches = re.findall(law_pattern, query)
        if matches:
            return matches[0]
        
        # 기본값
        return "해당 법령"

    def _clean_law_name(self, text: str) -> str:
        """법령명에서 '제XX조' 등 조항 번호 제거"""
        import re
        # Pattern: (공백)제(공백)숫자(공백)(조|항|호|목)... 끝까지
        pattern = r'\s*제\s*\d+\s*(조|항|호|목).*$'
        cleaned = re.sub(pattern, '', text).strip()
        return cleaned

    # --- Routing ---

    def _route_after_analysis(self, state: AgentState) -> Literal["clarify", "search", "generate", "verify_law"]:
        analysis = state.get("query_analysis", {})
        category = analysis.get("category", "노동법")
        
        # [Node B Logic] Ambiguous -> Clarify
        if analysis.get("is_ambiguous", False):
            return "clarify"
            
        # 기존 로직: needs_clarification (deprecated logic, but keeping for safely)
        if analysis.get("needs_clarification", False):
            return "clarify"
        
        # 노동법 외, 기타(일상)은 검색 생략하고 바로 Generate로 이동
        if category in ["노동법 외", "기타(일상)"]:
            logger.info(f"Skipping search for category: {category}")
            return "generate"

        # 노동법인 경우 Law Verification 단계 거침
        return "verify_law"

    def _route_after_verify(self, state: AgentState) -> Literal["search", "end"]:
        """검증 후 라우팅"""
        next_action = state.get("next_action", "search")
        if next_action == "clarify_end":
            return "end" # 이미 generated_answer에 안내 메시지가 있음
        return "search"

    def _route_after_evaluation(self, state: AgentState) -> Literal["search", "end"]:
        evaluation = state.get("evaluation_result", {})
        retry_count = state.get("retry_count", 0) or 0

        if retry_count >= self.config.MAX_RETRY:
            logger.warning("Max retry reached")
            return "end"

        # Strict Pass Criteria: 3가지 기준 중 하나라도 False면 재검색
        # 단, needs_more_search가 명시적으로 True인 경우도 포함
        is_perfect = (
            evaluation.get("has_legal_basis", False) and
            evaluation.get("cites_retrieved_docs", False) and
            evaluation.get("is_relevant", False)
        )

        if not is_perfect or evaluation.get("needs_more_search", False):
            logger.info(f"Evaluation failed (Perfect={is_perfect}). Retrying search...")
            return "search"

        return "end"
    
    def _route_after_generate(self, state: AgentState) -> Literal["evaluate", "end"]:
        """답변 생성 후 라우팅: 난이도 및 카테고리에 따라 평가 단계 조건부 실행"""
        analysis = state.get("query_analysis", {}) 
        complexity = analysis.get("query_complexity", "medium")
        category = analysis.get("category", "노동법")
        
        # 1. 노동법이 아닌 경우 (일상, 노동법 외) -> 평가 생략
        if category != "노동법":
            logger.info(f"Category '{category}' - skipping evaluation")
            return "end"

        # 2. simple 질문은 평가 건너뛰고 바로 종료
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
        builder.add_node("verify_law", self._create_verify_law_node())
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
                "search": "search",     # Fallback (old)
                "generate": "generate",
                "verify_law": "verify_law"
            }
        )

        builder.add_edge("clarify", END)
        
        # Verify Law -> Search or End
        builder.add_conditional_edges(
            "verify_law",
            self._route_after_verify,
            {
                "search": "search",
                "end": END
            }
        )
        
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
