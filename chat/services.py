import sys
from pathlib import Path
from django.conf import settings

# ai_module 경로 추가 (필요시)
# BASE_DIR = config.settings.BASE_DIR
# ai_module은 프로젝트 루트에 있으므로 바로 import 가능

try:
    from chat.ai_module.chatbot_graph_V8_FINAL import LegalRAGBuilder, Config
except ImportError:
    # 경로 문제 발생 시 처리
    import sys
    sys.path.append(str(settings.BASE_DIR))
    from chat.ai_module.chatbot_graph_V8_FINAL import LegalRAGBuilder, Config

class ChatbotService:
    _instance = None
    _builder = None
    _graph = None
    
    @classmethod
    async def get_instance(cls):
        if cls._instance is None:
            cls._instance = ChatbotService()
            await cls._instance._initialize()
        return cls._instance

    @classmethod
    def initialize(cls):
        """서버 시작 시 호출되는 동기 초기화 메서드"""
        if cls._instance is None:
            cls._instance = ChatbotService()
            cls._instance._sync_initialize()
            
    def _sync_initialize(self):
        config = Config()
        self._builder = LegalRAGBuilder(config)
        self._graph = self._builder.build()
        print("Chatbot Graph Initialized successfully (Sync).")


    async def _initialize(self):
        # Config 설정ddd
        # 실제 운영 환경에서는 환경 변수 로드가 필요합니다.
        
        config = Config()
        
        # Builder 초기화
        self._builder = LegalRAGBuilder(config)
        
        # 그래프 생성: Builder 내부의 build() 메서드 사용
        # build() 메서드 내부에서 _init_infrastructure() 호출 및 노드/엣지 연결을 모두 수행함
        self._graph = self._builder.build()
        
        print("Chatbot Graph Initialized successfully.")

    async def get_response(self, user_message: str):
        if not self._graph:
            await self._initialize()
            
        inputs = {
            "user_query": user_message, 
            "messages": [("user", user_message)],
            "retry_count": 0
        }
        
        try:
            # ainvoke로 비동기 실행
            result = await self._graph.ainvoke(inputs)
            return result.get("generated_answer", "죄송합니다. 답변을 생성하지 못했습니다.")
        except Exception as e:
            print(f"Error generation response: {e}")
            return f"오류가 발생했습니다: {str(e)}"
