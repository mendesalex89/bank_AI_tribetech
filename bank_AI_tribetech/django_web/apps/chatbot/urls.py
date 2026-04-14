from django.urls import path
from . import views

urlpatterns = [
    path("", views.chatbot, name="chatbot"),
    path("api/chat/", views.api_chat, name="api_chat"),
]
