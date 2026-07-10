from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .models import PlatformEvent


@receiver(user_logged_in)
def record_login(sender, request, user, **kwargs):
    PlatformEvent.objects.create(
        event_type=PlatformEvent.LOGIN,
        user=user,
        path=getattr(request, "path", ""),
    )
