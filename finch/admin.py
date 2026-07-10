from django.contrib import admin

from .models import Comment, Finch, PlatformEvent, Subscription


admin.site.register(Finch)
admin.site.register(Comment)
admin.site.register(Subscription)
admin.site.register(PlatformEvent)
