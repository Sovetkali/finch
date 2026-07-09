from django.core.cache import cache

from .models import Notification

UNREAD_NOTIFICATIONS_CACHE_TTL = 30


def unread_notifications_cache_key(user_id):
    return f"unread_notifications_count:{user_id}"


def notifications(request):
    if not request.user.is_authenticated:
        return {"unread_notifications_count": 0}

    cache_key = unread_notifications_cache_key(request.user.id)
    unread_count = cache.get(cache_key)
    if unread_count is None:
        unread_count = Notification.objects.filter(
            recipient=request.user,
            read_at__isnull=True,
        ).count()
        cache.set(cache_key, unread_count, timeout=UNREAD_NOTIFICATIONS_CACHE_TTL)

    return {"unread_notifications_count": unread_count}
