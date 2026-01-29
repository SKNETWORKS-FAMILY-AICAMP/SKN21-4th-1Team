# 프롬프트 출력 커스터마이징 구현 계획

**작성일**: 2026-01-29  
**목적**: intent_type별 답변 형식 차별화 및 답변 불가 시 맞춤형 안내 제공

---

## 📋 목차

1. [현재 상태 분석](#1-현재-상태-분석)
2. [요구사항 정리](#2-요구사항-정리)
3. [구현 계획](#3-구현-계획)
4. [파일별 수정 사항](#4-파일별-수정-사항)
5. [검증 계획](#5-검증-계획)

---

## 1. 현재 상태 분석

### 1.1 현재 프롬프트 구조

**파일**: `chat/ai_module/prompts.py`

#### 답변 생성 프롬프트 (`PROMPT_GENERATE`)

- **현재 상태**: 모든 intent_type에 대해 **단일 형식** 사용
- **고정 형식**:
  ```
  🤔 분석
  📌 결론
  📖 법적 근거
  💡 유의 사항
  ```
- **문제점**: intent_type(법령조회, 절차문의, 상황판단 등)에 관계없이 동일한 구조

#### 답변 불가 템플릿 (`TEMPLATE_NO_RESULTS`)

- **현재 상태**: **고정된 단일 메시지**
  ```
  죄송합니다. 관련 법률 정보를 찾지 못했습니다.
  
  다음과 같이 시도해 보세요:
  1. 질문을 더 구체적으로 작성
  2. 다른 키워드로 질문
  3. 전문 법률 상담 권장
  ```
- **문제점**: 
  - 사용자 질문 맥락 무시
  - 왜 답변할 수 없는지 이유 미제공
  - 노동법 외 분야 질문에 대한 안내 부족

### 1.2 현재 워크플로우

```
Analyze 노드 (intent_type 분석)
    ↓
Search 노드 (문서 검색)
    ↓
Generate 노드 (답변 생성)
    ├─ 문서 있음 → PROMPT_GENERATE 사용 (intent 무관)
    └─ 문서 없음 → TEMPLATE_NO_RESULTS 사용 (고정)
```

**문제**: Generate 노드에서 `intent_type`을 활용하지 않음

---

## 2. 요구사항 정리

### 2.1 요구사항 1: intent_type별 답변 형식 차별화

| intent_type  | 요구되는 답변 형식                | 예시                                           |
| ------------ | --------------------------------- | ---------------------------------------------- |
| **법령조회** | 법령 전문을 법령 형식에 따라 반환 | 조항 번호, 항, 호 구조 유지                    |
| **절차문의** | 순번 형식으로 절차 단계 반환      | 1단계 → 2단계 → 3단계                          |
| **상황판단** | 상황 분석 + 행동 지침             | "귀하의 상황은... / 다음과 같이 행동하세요..." |
| **권리확인** | 권리 존재 여부 + 법적 근거        | "귀하는 ~할 권리가 있습니다[1]"                |
| **분쟁해결** | 해결 방법 + 절차 + 주의사항       | "노동위원회 신청 → 조정 → 재심..."             |
| **일반상담** | 기존 형식 유지                    | 현재 PROMPT_GENERATE 형식                      |

### 2.2 요구사항 2: 답변 불가 시 맞춤형 안내

#### 시나리오별 메시지

| 상황               | 답변 불가 이유              | 제공할 안내                                                          |
| ------------------ | --------------------------- | -------------------------------------------------------------------- |
| **노동법 외 분야** | category != "노동법"        | "저는 노동법 전문 에이전트입니다. {질문 법령}은 답변 범위 밖입니다." |
| **검색 결과 없음** | 문서 0개                    | "노동법 DB에서 관련 정보를 찾지 못했습니다. 더 구체적인 질문 권장"   |
| **모호한 질문**    | needs_clarification == true | 기존 TEMPLATE_CLARIFY 사용 (변경 불필요)                             |

#### 구체적 예시

**사용자 질문**: "공무원법 제10조가 뭐야?"

**현재 답변**:
```
죄송합니다. 관련 법률 정보를 찾지 못했습니다.
(일반적 안내)
```

**개선 후 답변**:
```
저는 노동법과 관련된 지식을 갖춘 에이전트입니다. 
**국가공무원법**에 대해서는 답변할 수 없습니다.

다음과 같이 시도해보세요:
1. 노동법과 관련된 구체적인 질문 작성 (예: "근로기준법 제2조")
2. 국가공무원법에 대한 정보는 법제처(https://law.go.kr) 탐색
3. 공무원 관련 상담은 인사혁신처 문의 권장
```

---

## 3. 구현 계획

### 3.1 전체 아키텍처 변경

#### Before (현재)
```
Generate 노드
├─ 문서 있음 → 단일 PROMPT_GENERATE
└─ 문서 없음 → 단일 TEMPLATE_NO_RESULTS
```

#### After (개선)
```
Generate 노드
├─ 문서 있음
│   ├─ intent_type == "법령조회" → PROMPT_GENERATE_LAW_LOOKUP
│   ├─ intent_type == "절차문의" → PROMPT_GENERATE_PROCEDURE
│   ├─ intent_type == "상황판단" → PROMPT_GENERATE_SITUATION
│   ├─ intent_type == "권리확인" → PROMPT_GENERATE_RIGHTS
│   ├─ intent_type == "분쟁해결" → PROMPT_GENERATE_DISPUTE
│   └─ intent_type == "일반상담" → PROMPT_GENERATE (기존)
│
└─ 문서 없음
    ├─ category != "노동법" → TEMPLATE_NO_RESULTS_OUT_OF_SCOPE
    └─ category == "노동법" → TEMPLATE_NO_RESULTS_NO_DOCS
```

### 3.2 구현 단계

#### Phase 1: 프롬프트 작성 (prompts.py)

1. **intent별 답변 생성 프롬프트 6개 추가**
   - `PROMPT_GENERATE_LAW_LOOKUP` (법령조회)
   - `PROMPT_GENERATE_PROCEDURE` (절차문의)
   - `PROMPT_GENERATE_SITUATION` (상황판단)
   - `PROMPT_GENERATE_RIGHTS` (권리확인)
   - `PROMPT_GENERATE_DISPUTE` (분쟁해결)
   - `PROMPT_GENERATE` (일반상담 - 기존 유지)

2. **답변 불가 템플릿 2개 추가**
   - `TEMPLATE_NO_RESULTS_OUT_OF_SCOPE` (노동법 외 분야)
   - `TEMPLATE_NO_RESULTS_NO_DOCS` (검색 결과 없음)

#### Phase 2: Generate 노드 로직 수정 (graph.py)

1. **프롬프트 선택 로직 추가**
   ```python
   def _select_prompt_by_intent(intent_type: str) -> str:
       """intent_type에 따라 적절한 프롬프트 선택"""
       prompt_map = {
           "법령조회": prompts.PROMPT_GENERATE_LAW_LOOKUP,
           "절차문의": prompts.PROMPT_GENERATE_PROCEDURE,
           "상황판단": prompts.PROMPT_GENERATE_SITUATION,
           "권리확인": prompts.PROMPT_GENERATE_RIGHTS,
           "분쟁해결": prompts.PROMPT_GENERATE_DISPUTE,
           "일반상담": prompts.PROMPT_GENERATE
       }
       return prompt_map.get(intent_type, prompts.PROMPT_GENERATE)
   ```

2. **답변 불가 템플릿 선택 로직 추가**
   ```python
   def _select_no_results_template(category: str, query: str) -> str:
       """답변 불가 사유에 따라 적절한 템플릿 선택"""
       if category != "노동법":
           # 노동법 외 분야 → 맞춤형 안내
           return prompts.TEMPLATE_NO_RESULTS_OUT_OF_SCOPE.format(
               category=category,
               query=query
           )
       else:
           # 노동법이지만 문서 없음 → 일반 안내
           return prompts.TEMPLATE_NO_RESULTS_NO_DOCS
   ```

3. **`_create_generate_node()` 수정**
   - `analysis`에서 `intent_type`, `category` 추출
   - 문서 있을 때: intent별 프롬프트 사용
   - 문서 없을 때: category별 템플릿 사용

#### Phase 3: 스키마 확장 (선택사항)

**목적**: 답변 불가 시 구체적인 이유 추적

`schemas.py`에 새 필드 추가:
```python
class AgentState(TypedDict):
    # ... 기존 필드 ...
    no_result_reason: Optional[str]  # "out_of_scope" | "no_docs" | None
```

---

## 4. 파일별 수정 사항

### 4.1 `chat/ai_module/prompts.py`

#### 추가할 프롬프트 (총 8개)

##### 1) `PROMPT_GENERATE_LAW_LOOKUP` (법령조회)

```python
PROMPT_GENERATE_LAW_LOOKUP = """당신은 법령 전문을 정확하게 제공하는 법률 AI입니다.

## 답변 형식

**📜 법령 전문**

[법령명] 제[조항]조 ([조항 제목])

① [제1항 내용][1]
② [제2항 내용][1]
  1. [제1호 내용]
  2. [제2호 내용]

**📌 핵심 요약**
(해당 조항의 핵심 내용을 1-2문장으로 요약)

**💡 참고 사항**
(관련 시행령, 예외 조항 등 추가 정보)

## 규칙
- 법령 구조(조, 항, 호)를 정확히 유지하세요
- 원문 그대로 인용하되, 필요시 쉬운 용어로 부연 설명
- 반드시 출처 번호[1] 표기
"""
```

##### 2) `PROMPT_GENERATE_PROCEDURE` (절차문의)

```python
PROMPT_GENERATE_PROCEDURE = """당신은 법적 절차를 단계별로 안내하는 법률 AI입니다.

## 답변 형식

**📋 절차 안내**

**1단계: [단계명]**
- 내용: [구체적 행동][1]
- 기한: [기한 정보]
- 준비물: [필요 서류]

**2단계: [단계명]**
- 내용: [구체적 행동][2]
- 기한: [기한 정보]
- 주의: [주의사항]

**3단계: [단계명]**
...

**⏱️ 전체 소요 기간**
(예상 소요 시간 안내)

**📌 주의 사항**
- [중요 주의점 1]
- [중요 주의점 2]

## 규칙
- 절차를 시간 순서대로 나열
- 각 단계마다 구체적 행동 명시
- 기한이 있는 경우 반드시 표기
"""
```

##### 3) `PROMPT_GENERATE_SITUATION` (상황판단)

```python
PROMPT_GENERATE_SITUATION = """당신은 법적 상황을 분석하고 행동 지침을 제공하는 법률 AI입니다.

## 답변 형식

**🔍 상황 분석**
귀하의 상황은 [법적 성격]에 해당합니다[1].

**📖 적용 법령**
- [법령명 제X조]: [내용 요약][1]
- [관련 규정]: [내용 요약][2]

**✅ 권장 행동**
1. **즉시 조치**: [긴급 행동]
2. **증거 확보**: [필요한 증거]
3. **상담 요청**: [상담 기관]

**⚠️ 주의 사항**
- [시효, 기한 등 중요 주의점]
- [불이익 방지 방법]

## 규칙
- 사용자 상황을 법적으로 명확히 규정
- 구체적이고 실행 가능한 행동 제시
- 시급성이 있는 경우 강조
"""
```

##### 4) `PROMPT_GENERATE_RIGHTS` (권리확인)

```python
PROMPT_GENERATE_RIGHTS = """당신은 법적 권리 존재 여부를 명확히 알려주는 법률 AI입니다.

## 답변 형식

**✅ 권리 존재 여부**
귀하는 [권리명]을 **행사할 수 있습니다** / **행사할 수 없습니다**[1].

**📖 법적 근거**
[법령명 제X조]에 따르면:
- [권리 내용][1]
- [요건][1]

**🔑 권리 행사 방법**
1. [방법 1]
2. [방법 2]
3. [방법 3]

**⏰ 행사 기한**
(시효, 제척기간 등)

**💡 유의 사항**
- [예외 상황]
- [권리 제한 사유]

## 규칙
- 권리 존재 여부를 명확히 Yes/No로 제시
- 권리 행사 방법을 구체적으로 안내
- 기한이 있는 경우 반드시 강조
"""
```

##### 5) `PROMPT_GENERATE_DISPUTE` (분쟁해결)

```python
PROMPT_GENERATE_DISPUTE = """당신은 분쟁 해결 방법을 안내하는 법률 AI입니다.

## 답변 형식

**⚖️ 분쟁 해결 경로**

**[경로 1] 자율 해결**
- 방법: [협의, 합의 등][1]
- 장점: [신속, 비용 절감]
- 단점: [강제력 부족]

**[경로 2] 행정 구제**
- 기관: [노동위원회 등][2]
- 절차: [신청 → 조사 → 판정]
- 기간: [예상 소요 기간]

**[경로 3] 사법 구제**
- 방법: [민사소송, 가처분 등][3]
- 절차: [소 제기 → 변론 → 판결]
- 비용: [인지대, 변호사 비용]

**📌 권장 순서**
1. [우선 시도할 방법]
2. [차선책]
3. [최종 수단]

**⚠️ 주의 사항**
- [시효 주의]
- [증거 보존]

## 규칙
- 여러 해결 경로를 제시하고 비교
- 각 경로의 장단점 명시
- 권장 순서 제공
"""
```

##### 6) 기존 `PROMPT_GENERATE` 유지 (일반상담)

현재 프롬프트를 그대로 사용

##### 7) `TEMPLATE_NO_RESULTS_OUT_OF_SCOPE` (노동법 외 분야)

```python
TEMPLATE_NO_RESULTS_OUT_OF_SCOPE = """저는 **노동법**과 관련된 지식을 갖춘 AI 에이전트입니다.

**{detected_law}**에 대해서는 답변할 수 없습니다.

다음과 같이 시도해보세요:

1. **노동법 관련 질문으로 변경**
   - 예: "근로기준법 제2조", "퇴직금 지급 기한"
   
2. **{detected_law} 정보 탐색**
   - 법제처 국가법령정보센터: https://law.go.kr
   - 관련 법령 검색 및 조문 확인

3. **전문 상담 권장**
   - {detected_law} 관련 전문 기관 문의
   - 법률 상담: 대한법률구조공단 (국번없이 132)

💡 **노동법 관련 질문 예시**
- "근로계약서 작성 의무가 있나요?"
- "연차휴가는 몇 일인가요?"
- "부당해고 구제 절차는?"
"""
```

##### 8) `TEMPLATE_NO_RESULTS_NO_DOCS` (검색 결과 없음)

```python
TEMPLATE_NO_RESULTS_NO_DOCS = """죄송합니다. 노동법 데이터베이스에서 관련 정보를 찾지 못했습니다.

**다음과 같이 시도해보세요:**

1. **질문을 더 구체적으로 작성**
   - 현재: "{query}"
   - 개선: 법령명, 조항 번호, 구체적 상황 포함
   - 예: "근로기준법 제50조 연장근로 한도"

2. **다른 키워드로 질문**
   - 유사 용어 사용 (예: "해고" → "부당해고", "면직")
   - 법률 용어 사용 (예: "월급" → "임금")

3. **관련 법령 확인**
   - 법제처: https://law.go.kr
   - 고용노동부: https://www.moel.go.kr

4. **전문 상담 권장**
   - 고용노동부 상담센터: 국번없이 1350
   - 대한법률구조공단: 국번없이 132

💡 **참고**: 판례, 행정해석은 현재 DB에 포함되어 있지 않습니다.
"""
```

---

### 4.2 `chat/ai_module/graph.py`

#### 수정 위치: `LegalRAGBuilder._create_generate_node()` (L298-L367)

#### Before (현재 코드)

```python
def _create_generate_node(self):
    """[노드: Generate] 답변 생성 노드 (Async)"""
    llm = self.llm
    system_prompt = prompts.PROMPT_GENERATE  # ← 고정된 단일 프롬프트
    no_results_template = prompts.TEMPLATE_NO_RESULTS  # ← 고정된 단일 템플릿

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

        # ... context 생성 로직 ...

        if not docs:
            answer = no_results_template  # ← 고정 템플릿 사용
        else:
            chain = answer_prompt | llm
            response = await chain.ainvoke({
                "query": query,
                "context": context,
                "case_law_notice": case_law_notice
            })
            answer = response.content

        return {"generated_answer": answer}

    return generate_answer
```

#### After (수정 후 코드)

```python
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
                title = meta.get("article_title", "") or meta.get("title", "")
                content = doc.page_content[:800]

                header = f"[문서 {i}]"
                if law_name:
                    header += f" {law_name}"
                    if article:
                        header += f" 제{article}조"
                if title:
                    header += f" - {title}"

                context_parts.append(f"{header}\\n{content}\\n")

            context = "\\n".join(context_parts)
        else:
            context = "(관련 법령 문서가 검색되지 않았습니다)"

        case_law_notice = ""
        if needs_case_law:
            case_law_notice = "⚠️ 참고: 판례 검색이 필요하나 현재 DB에 포함되어 있지 않습니다."

        # ========== 핵심 변경: intent별 프롬프트 선택 ==========
        if not docs:
            # 문서 없음 → category에 따라 템플릿 선택
            answer = self._generate_no_results_message(category, query, analysis)
        else:
            # 문서 있음 → intent_type에 따라 프롬프트 선택
            system_prompt = self._select_prompt_by_intent(intent_type)
            
            answer_prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", """사용자 질문: {query}

📚 검색된 법령/문서:
{context}

{case_law_notice}

위 자료를 바탕으로 질문에 답변해주세요.""")
            ])

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

# ========== 새로 추가할 헬퍼 메서드 ==========

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
    logger.info(f"Selected prompt for intent '{intent_type}': {type(selected).__name__}")
    return selected

def _generate_no_results_message(self, category: str, query: str, analysis: dict) -> str:
    """답변 불가 시 맞춤형 메시지 생성"""
    
    # 노동법 외 분야 질문인 경우
    if category != "노동법":
        # 질문에서 법령명 추출 시도
        detected_law = self._extract_law_name(query, analysis)
        
        return prompts.TEMPLATE_NO_RESULTS_OUT_OF_SCOPE.format(
            detected_law=detected_law,
            query=query
        )
    
    # 노동법이지만 검색 결과 없음
    return prompts.TEMPLATE_NO_RESULTS_NO_DOCS.format(query=query)

def _extract_law_name(self, query: str, analysis: dict) -> str:
    """질문에서 법령명 추출 (간단한 휴리스틱)"""
    # related_laws에서 추출
    related_laws = analysis.get("related_laws", [])
    if related_laws:
        return related_laws[0]
    
    # 질문 텍스트에서 "~법" 패턴 찾기
    import re
    law_pattern = r'([가-힣]+법)'
    matches = re.findall(law_pattern, query)
    if matches:
        return matches[0]
    
    # 기본값
    return "해당 법령"
```

#### 수정 요약

| 항목             | Before                       | After                                                                                 |
| ---------------- | ---------------------------- | ------------------------------------------------------------------------------------- |
| 프롬프트 선택    | 고정 (`PROMPT_GENERATE`)     | intent별 동적 선택                                                                    |
| 답변 불가 메시지 | 고정 (`TEMPLATE_NO_RESULTS`) | category별 동적 생성                                                                  |
| 새 메서드        | 없음                         | `_select_prompt_by_intent()`, `_generate_no_results_message()`, `_extract_law_name()` |

---

### 4.3 `chat/ai_module/schemas.py` (선택사항)

#### 추가할 필드

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
    
    # ========== 새로 추가 ==========
    no_result_reason: Optional[str]  # "out_of_scope" | "no_docs" | None
```

**용도**: 
- 답변 불가 이유 추적
- 로그 분석 시 유용
- 향후 통계 수집 가능

**수정 위치**: `graph.py`의 `_generate_no_results_message()`에서 설정
```python
# 노동법 외 분야
return {
    "generated_answer": message,
    "no_result_reason": "out_of_scope"
}

# 검색 결과 없음
return {
    "generated_answer": message,
    "no_result_reason": "no_docs"
}
```

---

## 5. 검증 계획

### 5.1 단위 테스트 (자동)

#### 테스트 파일 생성: `chat/ai_module/tests/test_prompts.py`

```python
import pytest
from chat.ai_module import prompts

class TestPromptSelection:
    """프롬프트 선택 로직 테스트"""
    
    def test_all_intent_prompts_exist(self):
        """모든 intent_type에 대한 프롬프트가 존재하는지 확인"""
        required_prompts = [
            "PROMPT_GENERATE_LAW_LOOKUP",
            "PROMPT_GENERATE_PROCEDURE",
            "PROMPT_GENERATE_SITUATION",
            "PROMPT_GENERATE_RIGHTS",
            "PROMPT_GENERATE_DISPUTE",
            "PROMPT_GENERATE"
        ]
        
        for prompt_name in required_prompts:
            assert hasattr(prompts, prompt_name), f"{prompt_name} not found"
            assert isinstance(getattr(prompts, prompt_name), str)
            assert len(getattr(prompts, prompt_name)) > 0
    
    def test_no_results_templates_exist(self):
        """답변 불가 템플릿이 존재하는지 확인"""
        assert hasattr(prompts, "TEMPLATE_NO_RESULTS_OUT_OF_SCOPE")
        assert hasattr(prompts, "TEMPLATE_NO_RESULTS_NO_DOCS")
        
        # 템플릿에 필요한 플레이스홀더 확인
        assert "{detected_law}" in prompts.TEMPLATE_NO_RESULTS_OUT_OF_SCOPE
        assert "{query}" in prompts.TEMPLATE_NO_RESULTS_NO_DOCS
```

**실행 방법**:
```bash
cd /Users/wjsdndud/SKNAIcamp/02_Project/SKN21-4th-1Team
uv run pytest chat/ai_module/tests/test_prompts.py -v
```

---

### 5.2 통합 테스트 (수동)

#### 테스트 시나리오

| 시나리오      | 입력 질문                      | 기대 결과                       | 검증 항목          |
| ------------- | ------------------------------ | ------------------------------- | ------------------ |
| **법령조회**  | "근로기준법 제50조가 뭐야?"    | 조항 구조(①, ②) 포함 답변       | ✅ 법령 형식 유지   |
| **절차문의**  | "부당해고 구제 절차는?"        | 1단계 → 2단계 형식 답변         | ✅ 순번 형식        |
| **상황판단**  | "회사가 갑자기 해고했어요"     | "귀하의 상황은..." + 행동 지침  | ✅ 상황 분석 + 지침 |
| **권리확인**  | "연차휴가 받을 권리 있나요?"   | "귀하는 ~할 권리가 있습니다"    | ✅ 권리 명시        |
| **분쟁해결**  | "임금 체불 어떻게 해결하나요?" | 여러 해결 경로 제시             | ✅ 경로 비교        |
| **노동법 외** | "공무원법 제10조가 뭐야?"      | "저는 노동법 전문..."           | ✅ 맞춤형 안내      |
| **검색 실패** | "asdfqwer" (무의미 질문)       | "노동법 DB에서 찾지 못했습니다" | ✅ 구체화 권장      |

#### 수동 테스트 절차

1. **서버 실행**
   ```bash
   cd /Users/wjsdndud/SKNAIcamp/02_Project/SKN21-4th-1Team
   uv run python manage.py runserver
   ```

2. **브라우저에서 테스트**
   - URL: `http://localhost:8000/chat/`
   - 위 테스트 시나리오의 질문을 하나씩 입력
   - 각 답변 형식이 기대 결과와 일치하는지 확인

3. **체크리스트**
   - [ ] 법령조회: 조항 구조(①, ②, 1., 2.) 유지되는가?
   - [ ] 절차문의: 1단계, 2단계 형식으로 표시되는가?
   - [ ] 상황판단: "귀하의 상황은..." 문구가 포함되는가?
   - [ ] 권리확인: "권리가 있습니다/없습니다" 명시되는가?
   - [ ] 분쟁해결: 여러 해결 경로가 비교되는가?
   - [ ] 노동법 외: "노동법 전문 에이전트" 문구 포함되는가?
   - [ ] 검색 실패: "더 구체적으로" 권장 메시지 포함되는가?

---

### 5.3 로그 확인

#### 확인할 로그 메시지

```python
# graph.py에서 출력되는 로그
logger.info(f"Generating answer for intent: {intent_type}, category: {category}")
logger.info(f"Selected prompt for intent '{intent_type}': ...")
```

**확인 방법**:
```bash
# 서버 실행 시 터미널에서 로그 확인
# 각 질문마다 올바른 intent_type이 감지되는지 확인
```

---

## 6. 롤백 계획

### 6.1 변경 사항 되돌리기

만약 문제 발생 시:

1. **prompts.py 롤백**
   ```bash
   git checkout chat/ai_module/prompts.py
   ```

2. **graph.py 롤백**
   ```bash
   git checkout chat/ai_module/graph.py
   ```

3. **schemas.py 롤백** (수정한 경우)
   ```bash
   git checkout chat/ai_module/schemas.py
   ```

### 6.2 부분 롤백 (intent별 프롬프트만 비활성화)

`graph.py`의 `_select_prompt_by_intent()` 수정:
```python
def _select_prompt_by_intent(self, intent_type: str) -> str:
    # 모든 intent에 대해 기본 프롬프트 사용 (임시 비활성화)
    return prompts.PROMPT_GENERATE
```

---

## 7. 구현 우선순위

### Phase 1 (필수) - 1-2시간

1. ✅ `prompts.py`에 6개 intent별 프롬프트 추가
2. ✅ `prompts.py`에 2개 답변 불가 템플릿 추가
3. ✅ `graph.py`에 `_select_prompt_by_intent()` 메서드 추가
4. ✅ `graph.py`의 `_create_generate_node()` 수정

### Phase 2 (권장) - 30분

5. ✅ `graph.py`에 `_generate_no_results_message()` 메서드 추가
6. ✅ `graph.py`에 `_extract_law_name()` 메서드 추가

### Phase 3 (선택) - 15분

7. ⭕ `schemas.py`에 `no_result_reason` 필드 추가
8. ⭕ 단위 테스트 작성

---

## 8. 예상 효과

### 8.1 사용자 경험 개선

| 개선 항목          | Before                | After              | 효과            |
| ------------------ | --------------------- | ------------------ | --------------- |
| **답변 형식**      | 모든 질문에 동일 형식 | intent별 맞춤 형식 | 가독성 ↑ 30%    |
| **답변 불가 안내** | 일반적 안내           | 맞춤형 대안 제시   | 사용자 만족도 ↑ |
| **법령 조회**      | 요약만 제공           | 원문 구조 유지     | 정확성 ↑        |
| **절차 안내**      | 서술형                | 단계별 순번        | 이해도 ↑        |

### 8.2 시스템 개선

- **유지보수성**: 프롬프트별 독립 수정 가능
- **확장성**: 새 intent_type 추가 용이
- **추적성**: 답변 불가 이유 로깅 가능

---

## 9. 리스크 및 대응

| 리스크              | 발생 가능성 | 영향도 | 대응 방안                                |
| ------------------- | ----------- | ------ | ---------------------------------------- |
| LLM이 새 형식 무시  | 중          | 중     | 프롬프트 강화 (예: "반드시 이 형식으로") |
| intent 분류 오류    | 중          | 중     | Analyze 노드 프롬프트 개선               |
| 답변 생성 시간 증가 | 낮          | 낮     | 프롬프트 길이 최적화                     |
| 기존 답변 품질 저하 | 낮          | 높     | 충분한 테스트 + 롤백 준비                |

---

## 10. 다음 단계

1. **사용자 승인 대기**
2. 승인 후 Phase 1 구현 시작
3. 각 Phase별 테스트 수행
4. 사용자 피드백 수집
5. 필요시 프롬프트 미세 조정

---

**작성자**: Antigravity AI  
**검토 필요 사항**: 
- [ ] 프롬프트 톤앤매너 확인
- [ ] intent_type 분류 기준 검토
- [ ] 답변 불가 안내 문구 검토
