
import os
import sys
import django
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings') # Assuming project name is config or similar, checking manage.py usually helps but I'll guess 'config.settings' or 'mysite.settings'. 
# Wait, I need to check settings module name. I'll check manage.py first.
# But for now I will write the script and I can edit it.
# Actually I'll check manage.py first in next step.

sys.path.append(os.getcwd())
django.setup()

from chat.ai_module.graph import LegalRAGBuilder
from chat.ai_module.config import Config
from chat.ai_module.schemas import AgentState

async def test_nodes():
    print(">>> Initializing Builder...")
    config = Config()
    builder = LegalRAGBuilder(config)
    builder._init_infrastructure()
    
    # Mocking vs_manager to avoid real DB connection issues if any, 
    # but we want to test LLM nodes primarily.
    # builder.vs_manager = MagicMock()
    # builder.vs_manager.get_collection_name.return_value = "test_collection"
    
    # 1. Test Node A: Query Expansion
    print("\n[Test 1] Node A: Query Expansion (Input: '알바 잘림')")
    expander = builder._create_query_expander()
    expanded = await expander("알바 잘림")
    print(f"Original: {expanded.original_query}")
    print(f"Keyword: {expanded.keyword_query}")
    print(f"Expanded: {expanded.expanded_queries}")

    # 2. Test Node B: Ambiguity Router - Ambiguous Case
    print("\n[Test 2] Node B: Ambiguity (Input: '퇴직금 받을 수 있어?')")
    analyzer = builder._create_analyze_node()
    state_ambiguous = AgentState(user_query="퇴직금 받을 수 있어?", messages=[])
    result_ambiguous = await analyzer(state_ambiguous)
    analysis_amb = result_ambiguous['query_analysis']
    print(f"Is Ambiguous: {analysis_amb['is_ambiguous']}")
    print(f"Missing Info: {analysis_amb['missing_info']}")
    
    # 3. Test Node B: Ambiguity Router - Specific Case
    print("\n[Test 3] Node B: Ambiguity (Input: '5인 이상 사업장에서 2년 일하고 퇴사했는데 퇴직금 못받음')")
    state_specific = AgentState(user_query="5인 이상 사업장에서 2년 일하고 퇴사했는데 퇴직금 못받음", messages=[])
    result_specific = await analyzer(state_specific)
    analysis_spec = result_specific['query_analysis']
    print(f"Is Ambiguous: {analysis_spec['is_ambiguous']}")
    
    # 4. Test Node C: Clarification
    if analysis_amb['is_ambiguous']:
        print("\n[Test 4] Node C: Clarification Generation")
        clarifier = builder._create_clarify_node()
        # Feed the analysis from Test 2
        state_clarify = AgentState(
            user_query="퇴직금 받을 수 있어?", 
            messages=[],
            query_analysis=analysis_amb
        )
        clarify_result = await clarifier(state_clarify)
        print(f"Clarification Question: {clarify_result['generated_answer']}")

if __name__ == "__main__":
    asyncio.run(test_nodes())
