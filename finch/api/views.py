from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status

class PingView(APIView):
    """Simple endpoint to test DRF throttling."""
    permission_classes = [AllowAny]

    def get(self, request, format=None):
        user_id = getattr(request.user, "id", None)
        cache_key = f"ping-throttle:{user_id or request.META.get('REMOTE_ADDR', 'anonymous')}"
        if cache.get(cache_key):
            return Response({"detail": "Request was throttled."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        cache.set(cache_key, True, timeout=60)
        return Response({"message": "pong"})
from asgiref.sync import sync_to_async
from django.core.cache import cache
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from ..context_processors import unread_notifications_cache_key
from ..models import Notification

class NotificationsStatusView(APIView):
    """Return unread notification count. Throttled per user (100/min)."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get(self, request, format=None):
        cache_key = unread_notifications_cache_key(request.user.id)
        unread_count = cache.get(cache_key)
        if unread_count is None:
            unread_count = Notification.objects.filter(
                recipient=request.user, read_at__isnull=True
            ).count()
            cache.set(cache_key, unread_count, timeout=30)
        return Response({"unread_count": unread_count})

class NotificationsUpdatesView(APIView):
    """Return recent notifications with HTML rendering. Throttled per user (100/min)."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get(self, request, format=None):
        after_id = request.GET.get("after_id")
        try:
            after_id = int(after_id or 0)
        except ValueError:
            after_id = 0
        notifications_qs = Notification.objects.filter(
            recipient=request.user, id__gt=after_id
        ).select_related(
            "actor", "finch", "finch__user", "comment"
        ).order_by("created_at")
        new_notifications = list(notifications_qs[:20])
        html = render_to_string(
            "finch/_notifications_list.html",
            {"notifications": new_notifications, "suppress_empty": True},
        )
        cache_key = unread_notifications_cache_key(request.user.id)
        unread_count = cache.get(cache_key)
        if unread_count is None:
            unread_count = Notification.objects.filter(
                recipient=request.user, read_at__isnull=True
            ).count()
            cache.set(cache_key, unread_count, timeout=30)
        return Response({
            "html": html,
            "count": len(new_notifications),
            "unread_count": unread_count,
        })
