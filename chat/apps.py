from django.apps import AppConfig


class ChatConfig(AppConfig):
    name = 'chat'

    def ready(self):
        from .services import ChatbotService
        import threading
        
        # 서버 시작 시 별도 스레드에서 모델 로딩 (메인 스레드 차단 방지)
        def load_model():
            print("Starting model loading in background...")
            ChatbotService.initialize()
            
        # runserver의 리로더가 두 번 실행되는 것을 방지하기 위해
        # 실제 서버 프로세스에서만 실행되도록 조건 확인 (선택 사항)
        # 하지만 간단하게 바로 실행
        threading.Thread(target=load_model).start()

