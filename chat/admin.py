from django.contrib import admin
from .models import ChatMessage

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('role', 'message', 'created_at')
    list_filter = ('role',)
    ordering = ('-created_at',)
