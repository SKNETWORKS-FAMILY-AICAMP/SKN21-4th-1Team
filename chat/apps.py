from django.apps import AppConfig


class ChatConfig(AppConfig):
    name = 'chat'

    # def ready(self):
    #     # torch 등 필요한 패키지 설치 후 활성화
    #     from .services import ChatbotService
    #     import threading
    #     
    #     def load_model():
    #         print("Starting model loading in background...")
    #         ChatbotService.initialize()
    #         
    #     threading.Thread(target=load_model).start()
