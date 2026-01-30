
import os
import sys
import django
import asyncio
from unittest.mock import MagicMock

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from chat.ai_module.graph import LegalRAGBuilder
from chat.ai_module.config import Config
from chat.ai_module.schemas import AgentState

async def test_nodes():
    print(">>> Initializing Builder...")
    config = Config()
    builder = LegalRAGBuilder(config)
    
    # Mocking
    print(">>> Mocking VectorStoreManager & SparseManager...")
    mock_vs = MagicMock()
    # Mocking check_law_exists to return False (AsyncMock needed)
    from unittest.mock import AsyncMock
    mock_vs.check_law_exists = AsyncMock(return_value=False)
    mock_vs.get_embeddings.return_value = MagicMock()
    
    builder.set_components(vs_manager=mock_vs, reranker=MagicMock())
    builder.sparse_manager = MagicMock() 
    
    builder._init_infrastructure()
    
    verifier = builder._create_verify_law_node()

    # Test 1: Exact Match (근로기준법)
    print("\n[Test 1] Input: '근로기준법' (Exact Match)")
    state1 = AgentState(
        user_query="근로기준법 알려줘", 
        messages=[],
        query_analysis={"category": "노동법", "related_laws": ["근로기준법"]}
    )
    result1 = await verifier(state1)
    print(f"Result: {result1}")

    # Test 2: Fuzzy Match (근로 기준법 - Space)
    print("\n[Test 2] Input: '근로 기준법' (Fuzzy Match)")
    state2 = AgentState(
        user_query="근로 기준법 알려줘", 
        messages=[],
        query_analysis={"category": "노동법", "related_laws": ["근로 기준법"]}
    )
    result2 = await verifier(state2)
    print(f"Result: {result2}")
    
    # Test 3: Fail Case (가짜법)
    print("\n[Test 3] Input: '전국민돈벼락법' (Non-existent)")
    state3 = AgentState(
        user_query="전국민돈벼락법 알려줘", 
        messages=[],
        query_analysis={"category": "노동법", "related_laws": ["전국민돈벼락법"]}
    )
    result3 = await verifier(state3)
    print(f"Result: {'generated_answer' in result3}")

if __name__ == "__main__":
    asyncio.run(test_nodes())
