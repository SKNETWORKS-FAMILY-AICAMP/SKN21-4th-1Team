import os
import django
import asyncio
import logging
from unittest.mock import MagicMock, patch

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from chat.services import ChatbotService
from chat.ai_module import LegalRAGBuilder

# Configure Logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

async def run_test():
    print("Initializing ChatbotService with Mocks...")

    # Mocking Heavy Components
    with patch('chat.services.VectorStoreManager') as MockVSManager, \
         patch('chat.ai_module.JinaReranker') as MockReranker:
        
        # Setup specific mocks
        mock_vs = MockVSManager.return_value
        mock_vs.get_embeddings.return_value = MagicMock() # Mock embeddings
        mock_vs.create_client.return_value = MagicMock() # Mock client
        
        service = await ChatbotService.get_instance()
        
        # Manually create graph if it didn't build because of mocks in logic
        # But ChatbotService should utilize the mocks during _sync_initialize
        
        queries = [
            ("안녕? 넌 누구니?", "기타(일상)"),
            ("이혼시 재산분할은 어떻게 되나요?", "노동법 외"),
            ("회사가 퇴직금을 안 줘요. 어떻게 해야 하나요?", "노동법")
        ]
        
        print("\nStarting RAG Logic Verification...\n")
        
        for query, expected_category in queries:
            print(f"\n>>> Query: '{query}'")
            print(f">>> Expected Category: {expected_category}")
            
            try:
                # We need to ensure the graph uses the patched components
                response = await service.get_response(query)
                print(f">>> Response Preview: {response[:200]}...")
            except Exception as e:
                print(f">>> Error: {e}")
                import traceback
                traceback.print_exc()
                
            print("-" * 60)

if __name__ == "__main__":
    asyncio.run(run_test())
