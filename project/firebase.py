import os

import firebase_admin
from django.conf import settings
from firebase_admin import credentials
from firebase_admin import messaging


# Initialize Firebase Admin
def initialize_firebase():
    if firebase_admin._apps:
        return True

    credential_file = os.getenv("FIREBASE_CREDENTIAL_FILE", "serviceAccountKey.json")
    credential_path = os.path.join(settings.BASE_DIR, credential_file)

    if not os.path.exists(credential_path):
        # Firebase credentials are optional in local/dev environments.
        return False

    cred = credentials.Certificate(credential_path)
    firebase_admin.initialize_app(cred)
    return True

# Function to send push notifications (No need when i call from notification utils)
def send_push_notification(user, title, body, data=None):
    from apps.notification.models import DeviceToken
    tokens = DeviceToken.objects.filter(
        user=user
    ).values_list('token', flat=True)

    if not tokens:
        return

    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        data=data or {},
        tokens=list(tokens)
    )

    response = messaging.send_each_for_multicast(message)

    return response

