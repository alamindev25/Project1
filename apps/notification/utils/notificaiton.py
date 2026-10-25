from apps.notification.models import Notification
from project.firebase import send_push_notification

# Create and send notification
def create_and_send_notification(user, title, body, n_type):
    Notification.objects.create(
        user=user,
        title=title,
        body=body,
        notification_type=n_type
    )

    send_push_notification(
        user=user,
        title=title,
        body=body
    )
