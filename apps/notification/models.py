from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL

# Device Token
class DeviceToken(models.Model):
    DEVICE_CHOICES = [
        ('android', 'Android'),
        ('ios', 'iOS')
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="device_tokens")
    token = models.CharField(max_length=255, unique=True)
    device_type = models.CharField(max_length=20, choices=DEVICE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return f"{self.user.email} - {self.device_type}"

# Notification
class Notification(models.Model):
    NOTIFICATION_TYPE = (
        ('session', 'Session'),
        ('streak', 'Streak'),
        ('achievement', 'Achievement'),
        ('system', 'System'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=255, null=True, blank=True)
    body = models.TextField(null=True, blank=True)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title