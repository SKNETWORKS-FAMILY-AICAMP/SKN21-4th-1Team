from django.db import models

class ChatMessage(models.Model):
    role = models.CharField(max_length=10)  
    # "user" 또는 "ai"

    message = models.TextField()
    # 실제 채팅 내용

    created_at = models.DateTimeField(auto_now_add=True)
    # 저장 시각 (자동)

    def __str__(self):
        return f"{self.role}: {self.message[:20]}"
