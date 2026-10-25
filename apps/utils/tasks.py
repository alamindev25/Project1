from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _is_redis_broker_reachable():
    broker_url = getattr(settings, 'CELERY_BROKER_URL', '')
    if not broker_url.startswith('redis://') and not broker_url.startswith('rediss://'):
        return True

    parsed = urlparse(broker_url)
    host = parsed.hostname or '127.0.0.1'
    port = parsed.port or 6379

    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


def _send_email_sync(subject, body, to_emails, from_email=None, html_body=None, attachments=None):
    email = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=from_email,
        to=to_emails,
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )

    if attachments:
        for attachment in attachments:
            email.attach(
                attachment['filename'],
                attachment['content'],
                attachment['mimetype']
            )

    if html_body:
        email.attach_alternative(html_body, "text/html")

    email.send()


def dispatch_email_task(subject, body, to_emails, from_email=None, html_body=None, attachments=None):
    """
    Queue email through Celery when possible.
    If broker/backend is down, fallback to synchronous send and avoid API 500.
    Returns True on success, False on failure.
    """
    use_async = bool(getattr(settings, "CELERY_EMAIL_ASYNC", False))
    if not use_async:
        try:
            _send_email_sync(
                subject=subject,
                body=body,
                to_emails=to_emails,
                from_email=from_email,
                html_body=html_body,
                attachments=attachments,
            )
            return True
        except Exception as sync_exc:
            logger.error("Synchronous email failed: %s", str(sync_exc))
            return False

    if not _is_redis_broker_reachable():
        logger.warning("Celery broker unreachable, using sync fallback.")
        try:
            _send_email_sync(
                subject=subject,
                body=body,
                to_emails=to_emails,
                from_email=from_email,
                html_body=html_body,
                attachments=attachments,
            )
            return True
        except Exception as sync_exc:
            logger.error("Synchronous fallback email failed: %s", str(sync_exc))
            return False

    try:
        send_email_task.apply_async(
            kwargs={
                'subject': subject,
                'body': body,
                'to_emails': to_emails,
                'from_email': from_email,
                'html_body': html_body,
                'attachments': attachments,
            },
            ignore_result=True,
        )
        return True
    except Exception as exc:
        logger.warning("Celery unavailable for email dispatch, using sync fallback: %s", str(exc))
        try:
            _send_email_sync(
                subject=subject,
                body=body,
                to_emails=to_emails,
                from_email=from_email,
                html_body=html_body,
                attachments=attachments,
            )
            return True
        except Exception as sync_exc:
            logger.error("Synchronous fallback email failed: %s", str(sync_exc))
            return False

# Celery task to send emails template
@shared_task(bind=True, max_retries=3)
def send_email_task(self, subject, body, to_emails, from_email=None, html_body=None, attachments=None):
    try:
        _send_email_sync(
            subject=subject,
            body=body,
            to_emails=to_emails,
            from_email=from_email,
            html_body=html_body,
            attachments=attachments,
        )
        
        logger.info(f"Email sent successfully to {to_emails}")
        return {"status": "success", "message": f"Email sent to {to_emails}"}
        
    except Exception as exc:
        logger.error(f"Failed to send email to {to_emails}: {str(exc)}")
        # Retry the task after 60 seconds
        raise self.retry(exc=exc, countdown=60)
