from django.apps import AppConfig
from project.firebase import initialize_firebase
import logging


logger = logging.getLogger(__name__)


class NotificationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notification'

    def ready(self):
        try:
            initialize_firebase()
        except Exception as e:
            logger.warning("Firebase initialization warning: %s", e)
