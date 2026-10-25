from rest_framework import serializers
from .models import ChatSession, ChatMessage

class GenerateDocumentRequestSerializer(serializers.Serializer):
    description = serializers.CharField(required=True, min_length=10)

class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'type', 'content', 'outputs', 'created_at']

class ChatSessionSerializer(serializers.ModelSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)
    
    class Meta:
        model = ChatSession
        fields = ['id', 'title', 'created_at', 'updated_at', 'messages']