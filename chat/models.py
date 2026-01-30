# chat/models.py
from django.db import models


class ChatMessage(models.Model):
    ROLE_CHOICES = (
        ("user", "User"),
        ("ai", "AI"),
    )

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE, null=True)
    session_id = models.CharField(max_length=100, db_index=True, null=True, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role}: {self.message[:20]}"
