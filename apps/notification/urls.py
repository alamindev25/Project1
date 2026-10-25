from django.urls import path
from .views import (
    DeleteNotificationsView, DeviceTokenView, NotificationListView, TestPushAPIView, 
    MarkNotificaitonsReadView, MarkNotificationReadView, Last30DaysNotificationsView,
    
)

urlpatterns = [
    path("device-token/", DeviceTokenView.as_view(), name="device-token"),
    path("test-push/", TestPushAPIView.as_view(), name="test-push"),
    path("notification-list/", NotificationListView.as_view(), name="notifications"),
    path("mark-all-read/", MarkNotificaitonsReadView.as_view(), name="mark-all-read"),
    path("mark-read/<int:notification_id>/", MarkNotificationReadView.as_view(), name="mark-read"),
    path("last-30-days/", Last30DaysNotificationsView.as_view(), name="notifications-last-30-days"),
    path("delete/<int:notification_id>/", DeleteNotificationsView.as_view(), name="delete-notification"),
    path("delete-all/", DeleteNotificationsView.as_view(), name="delete-all-notifications"),

]