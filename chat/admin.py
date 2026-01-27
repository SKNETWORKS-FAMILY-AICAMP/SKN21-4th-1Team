# chat/admin.py
from django.contrib import admin
from .models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "role", "short_message", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("message",)
    ordering = ("-created_at",)

    def short_message(self, obj):
        return obj.message[:30]
    short_message.short_description = "메시지"
