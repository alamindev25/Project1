from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.authentication import SessionAuthentication
from rest_framework.pagination import CursorPagination
from django.shortcuts import get_object_or_404
from .models import ChatSession, ChatMessage
from .serializers import GenerateDocumentRequestSerializer, ChatSessionSerializer, ChatMessageSerializer
from .services.openai_service import OpenAIDocumentGeneratorService
import logging

logger = logging.getLogger(__name__)

class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return  # bypass CSRF check

class GenerateDocumentView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = GenerateDocumentRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        description = serializer.validated_data['description']
        
        try:
            service = OpenAIDocumentGeneratorService()
            result = service.generate_document(description)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"AI Document Generation Error: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ChatSessionCursorPagination(CursorPagination):
    page_size = 15
    ordering = '-updated_at'

class ChatSessionListView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAdminUser]

    def get(self, request):
        queryset = ChatSession.objects.filter(user=request.user)
        
        mode = request.query_params.get('mode')
        if mode == 'review':
            queryset = queryset.filter(title__startswith='[Review] ')
        elif mode == 'generate':
            queryset = queryset.exclude(title__startswith='[Review] ')
            
        paginator = ChatSessionCursorPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        if page is not None:
            serializer = ChatSessionSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
            
        serializer = ChatSessionSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        session = ChatSession.objects.create(
            user=request.user,
            title=request.data.get('title', 'New Chat')
        )
        serializer = ChatSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ChatSessionDetailView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        session = get_object_or_404(ChatSession, pk=pk, user=request.user)
        serializer = ChatSessionSerializer(session)
        return Response(serializer.data)

    def patch(self, request, pk):
        session = get_object_or_404(ChatSession, pk=pk, user=request.user)
        if 'title' in request.data:
            session.title = request.data['title']
            session.save()
        serializer = ChatSessionSerializer(session)
        return Response(serializer.data)

    def delete(self, request, pk):
        session = get_object_or_404(ChatSession, pk=pk, user=request.user)
        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class ChatMessageCreateView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        session = get_object_or_404(ChatSession, pk=pk, user=request.user)
        
        # Determine if we should also update session title on first message
        if session.messages.count() == 0 and request.data.get('type') == 'user':
            prompt = request.data.get('content', '')
            if prompt:
                # Basic title generation on backend if needed, or rely on frontend sending patch
                pass

        message = ChatMessage.objects.create(
            session=session,
            type=request.data.get('type'),
            content=request.data.get('content'),
            outputs=request.data.get('outputs')
        )
        # Update session updated_at
        session.save()
        
        serializer = ChatMessageSerializer(message)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


