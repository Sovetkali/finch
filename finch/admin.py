from django.contrib import admin

from .models import Comment, Finch, Subscription


admin.site.register(Finch)
admin.site.register(Comment)
admin.site.register(Subscription)
