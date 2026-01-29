from django.urls import path
from . import views

urlpatterns = [
    path("", views.chat, name="chat"),
    path("api/", views.chat_api, name="chat_api"),
    path("<str:session_id>/", views.chat, name="chat_with_session"),
]
