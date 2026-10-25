from rest_framework import serializers
from .models import DeviceToken, Notification
from django.utils.timesince import timesince

# Device Token
class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = [
            'id',
            'token',
            'device_type',
        ]

# Notification
class NotificationSerializer(serializers.ModelSerializer):
    time_ago = serializers.SerializerMethodField()
    class Meta:
        model = Notification
        fields = [
            'id',
            'title',
            'body',
            'notification_type',
            'is_read',
            'time_ago',
            'created_at',
        ]

    def get_time_ago(self, obj):
        return timesince(obj.created_at) + " ago"