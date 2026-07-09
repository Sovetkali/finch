from django.urls import path
from .views import PingView, NotificationsStatusView, NotificationsUpdatesView

urlpatterns = [
    path('ping/', PingView.as_view(), name='ping'),
    path('notifications/status/', NotificationsStatusView.as_view(), name='notifications_status'),
    path('notifications/updates/', NotificationsUpdatesView.as_view(), name='notifications_updates'),
]
