import sys
from pathlib import Path
from django.conf import settings

# ai_module 경로 추가 (필요시)
# BASE_DIR = config.settings.BASE_DIR
# ai_module은 프로젝트 루트에 있으므로 바로 import 가능

try:
    from chat.ai_module import LegalRAGBuilder, Config, VectorStoreManager

except ImportError:
    # 경로 문제 발생 시 처리
    import sys
    sys.path.append(str(settings.BASE_DIR))
    from chat.ai_module import LegalRAGBuilder, Config, VectorStoreManager


class ChatbotService:
    _instance = None
    _builder = None
    _graph = None
    _vs_manager = None
    _reranker = None
    
    @classmethod
    async def get_instance(cls):
        if cls._instance is None:
            # 동기 초기화가 안 된 경우 (드문 경우)
            cls._instance = ChatbotService()
            cls._instance._sync_initialize()
            
        # 그래프가 아직 없으면 메인 루프에서 생성 (이벤트 루프 안전)
        if cls._instance._graph is None:
             await cls._instance._async_graph_build()
             
        return cls._instance

    @classmethod
    def initialize(cls):
        """서버 시작 시 호출되는 동기 초기화 메서드"""
        if cls._instance is None:
            cls._instance = ChatbotService()
            cls._instance._sync_initialize()
            
    def _sync_initialize(self):
        """무거운 모델 로딩 (동기/백그라운드 스레드 안전)"""
        print("무거운 모델(임베딩, 리랭커) 초기화 중...")
        config = Config()
        
        # 1. 벡터 저장소 매니저 (임베딩)
        self._vs_manager = VectorStoreManager(config)
        self._vs_manager.initialize()
        
        # 2. 리랭커
        from chat.ai_module import JinaReranker
        self._reranker = JinaReranker(
            model_name=config.RERANKER_MODEL,
            top_n=config.TOP_K_RERANK
        )
        
        print("무거운 모델 초기화 완료.")

    async def _async_graph_build(self):
        """그래프 및 LLM 초기화 (비동기/메인 스레드)"""
        print("챗봇 그래프 빌드 중 (비동기)...")
        config = Config()
        self._builder = LegalRAGBuilder(config)
        
        if not self._vs_manager or not self._reranker:
             print("경고: 무거운 모델이 로딩되지 않았습니다. 동기 초기화를 시도합니다.")
             self._sync_initialize()

        if self._vs_manager is None or self._reranker is None:
             raise RuntimeError("Critical: Heavy models failed to initialize.")

        # 주입 (미리 로딩된 모델)
        self._builder.set_components(self._vs_manager, self._reranker)
        
        # 그래프 생성
        self._graph = self._builder.build()
        print("챗봇 그래프 빌드 완료.")




    async def get_response(self, user_message: str):
        if not self._graph:
            await self._async_graph_build()
            
        inputs = {
            "user_query": user_message, 
            "messages": [("user", user_message)],
            "retry_count": 0
        }
        
        try:
            # ainvoke로 비동기 실행
            if self._graph is None:
                return "오류: 그래프가 초기화되지 않았습니다."

            result = await self._graph.ainvoke(inputs)
            return result.get("generated_answer", "죄송합니다. 답변을 생성하지 못했습니다.")
        except Exception as e:
            print(f"Error generation response: {e}")
            return f"오류가 발생했습니다: {str(e)}"
    
    async def get_response_stream(self, user_message: str):
        """스트리밍 응답 생성 (4번 최적화)"""
        if not self._graph:
            await self._async_graph_build()
            
        inputs = {
            "user_query": user_message,
            "messages": [("user", user_message)],
            "retry_count": 0
        }
        
        try:
            if self._graph is None:
                yield "오류: 그래프가 초기화되지 않았습니다."
                return

            # astream을 사용한 스트리밍
            async for event in self._graph.astream(inputs):
                # generate 노드의 출력을 스트리밍
                if "generated_answer" in event:
                    answer = event.get("generated_answer", "")
                    # 답변을 청크로 나눠서 yield
                    for char in answer:
                        yield char
                        
        except Exception as e:
            print(f"Error in streaming response: {e}")
            yield f"오류가 발생했습니다: {str(e)}"
