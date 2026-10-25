from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.notification.utils.notificaiton import create_and_send_notification
from .models import DeviceToken, Notification
from .serializers import DeviceTokenSerializer, NotificationSerializer
from django.utils import timezone
from datetime import timedelta


# Device Token Save
class DeviceTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            token = serializer.validated_data.get('token')
            device_type = serializer.validated_data.get('device_type')

            device_token, created = DeviceToken.objects.update_or_create(
                user=request.user,
                token=token,
                defaults={
                    'user': request.user,
                    'device_type': device_type
                }
            )
            
            # Serialize the saved object to include the id
            response_serializer = DeviceTokenSerializer(device_token)
            
            return Response({
                "status": 201,
                "success": True,
                "message": "Device token saved successfully.",
                "data": response_serializer.data
                }, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            return Response({
                "status": status.HTTP_400_BAD_REQUEST,
                "success": False,
                "message": "Failed to save device token.",
                "errors": str(e)
    }, status=status.HTTP_400_BAD_REQUEST)

# Notification List
class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        try: 
            tab = request.query_params.get('tab', 'new')
            queryset = Notification.objects.filter(user=user)

            if tab == 'new':
                queryset = queryset.filter(is_read=False)
            elif tab == 'earlier':
                queryset = queryset.filter(is_read=True)
            
            serializer = NotificationSerializer(queryset, many=True)

            return Response({
                "status": 200,
                "success": True,
                "message": "Notifications fetched successfully.",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                "status": 400,
                "success": False,
                "message": "Failed to fetch notifications.",
                "errors": str(e)
    }, status=status.HTTP_400_BAD_REQUEST)

# Mark Notifications as Read
class MarkNotificaitonsReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        try:
            Notification.objects.filter(user=user, is_read=False).update(is_read=True)

            return Response({
                "status": 200,
                "success": True,
                "message": "All notifications marked as read.",
                "data": None
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                "status": 400,
                "success": False,
                "message": "Failed to mark notifications as read.",
                "errors": str(e)
    }, status=status.HTTP_400_BAD_REQUEST)

# Mark a single Notification as Read
class MarkNotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        user = request.user

        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            notification.is_read = True
            notification.save()

            serializer = NotificationSerializer(notification)

            return Response({
                "status": 200,
                "success": True,
                "message": "Notification marked as read.",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        
        except Notification.DoesNotExist:
            return Response({
                "status": 404,
                "success": False,
                "message": "Notification not found.",
                "data": None
    }, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            return Response({
                "status": 400,
                "success": False,
                "message": str(e),
                "data": None
    }, status=status.HTTP_400_BAD_REQUEST)

# Last 30 days notifications
class Last30DaysNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        try:
            thirty_days_ago = timezone.now() - timedelta(days=30)
            queryset = Notification.objects.filter(user=user, created_at__gte=thirty_days_ago)
            serializer = NotificationSerializer(queryset, many=True)

            return Response({
                "status": 200,
                "success": True,
                "message": "Last 30 days notifications fetched successfully.",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                "status": 400,
                "success": False,
                "message": "Failed to fetch notifications.",
                "errors": str(e)
    }, status=status.HTTP_400_BAD_REQUEST)

# Delete Notifications
class DeleteNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, notification_id=None):
        user = request.user

        # Specific notification delete
        if notification_id:
            deleted_count, _ = Notification.objects.filter(
                id=notification_id,
                user=user
            ).delete()

            if deleted_count == 0:
                return Response({
                    "status": 404,
                    "success": False,
                    "message": "Notification not found.",
                    "data": None
                }, status=status.HTTP_404_NOT_FOUND)

            return Response({
                "status": 200,
                "success": True,
                "message": "Notification deleted successfully.",
                "data": None
            }, status=status.HTTP_200_OK)

        # Delete ALL notifications
        deleted_count, _ = Notification.objects.filter(
            user=user
        ).delete()

        return Response({
            "status": 200,
            "success": True,
            "message": f"{deleted_count} notifications deleted successfully.",
            "data": None
        }, status=status.HTTP_200_OK)

# Test Push Notification
class TestPushAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        create_and_send_notification(
            user=request.user,
            title="Test Notification 🚀",
            body="If you see this, push is working!", 
            n_type="system"
        )
        return Response({"success": True})
