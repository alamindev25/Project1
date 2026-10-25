import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class AIDocumentGenerator(models.Model):
    class Meta:
        managed = False  # No database table
        verbose_name = 'AI Document Generator'
        verbose_name_plural = 'AI Document Generator'

class ChatSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_chat_sessions')
    title = models.CharField(max_length=255, default='New Chat')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-updated_at']
    def __str__(self):
        return f"{self.title} - {self.user.username}"

class ChatMessage(models.Model):
    TYPE_CHOICES = (
        ('user', 'User'),
        ('bot', 'Bot')
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    content = models.TextField()
    outputs = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.type} - {self.session.id}"
