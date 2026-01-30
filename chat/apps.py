from django.apps import AppConfig


class ChatConfig(AppConfig):
    name = 'chat'

    def ready(self):
        # 서버 시작 시 무거운 모델(임베딩, 리랭커) 백그라운드 로드
        # runserver 사용 시 리로더에 의해 두 번 호출될 수 있으니 주의 (os.environ.get('RUN_MAIN') 체크 등은 옵션)
        from .services import ChatbotService
        import threading
        import logging
        
        logger = logging.getLogger(__name__)

        import os
        import sys
        
        # runserver 사용 시: 
        # 1. Main Process (Watcher) -> RUN_MAIN 미설정 -> 로딩 건너뜀
        # 2. Child Process (Server) -> RUN_MAIN='true' -> 로딩 실행
        if 'runserver' in sys.argv and os.environ.get('RUN_MAIN') != 'true':
            return

        def load_model():
            logger.info("🚀 [Startup] Starting model loading in background...")
            # 싱글톤 초기화 호출
            ChatbotService.initialize()
            logger.info("✅ [Startup] Model loading completed.")
            
        threading.Thread(target=load_model, daemon=True).start()
