from django.urls import path
from .views import GenerateDocumentView, ChatSessionListView, ChatSessionDetailView, ChatMessageCreateView

urlpatterns = [
    path('generate/', GenerateDocumentView.as_view(), name='ai_document_generate'),
    path('sessions/', ChatSessionListView.as_view(), name='ai_chat_sessions'),
    path('sessions/<uuid:pk>/', ChatSessionDetailView.as_view(), name='ai_chat_session_detail'),
    path('sessions/<uuid:pk>/messages/', ChatMessageCreateView.as_view(), name='ai_chat_message_create'),
]
