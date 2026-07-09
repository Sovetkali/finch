from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from finch.models import Finch, Subscription


class Command(BaseCommand):
    help = "Create bob's demo posts and subscribe sovetkali to bob."

    def handle(self, *args, **options):
        bob, _ = User.objects.get_or_create(username="bob")
        bob.set_password("bob12345")
        bob.save()

        sovetkali, sovetkali_created = User.objects.get_or_create(username="sovetkali")
        if sovetkali_created:
            sovetkali.set_password("sovetkali12345")
            sovetkali.save()
        Subscription.objects.get_or_create(user=sovetkali, author=bob)

        texts = [
            "Тестовый финч bob #12: самая свежая запись для первой страницы.",
            "Тестовый финч bob #11: скролл должен держать порядок по дате.",
            "Тестовый финч bob #10: первая пачка показывает пять постов.",
            "Тестовый финч bob #9: дальше подключается ленивая загрузка.",
            "Тестовый финч bob #8: этот пост ещё в первой выдаче.",
            "Тестовый финч bob #7: появляется после прокрутки.",
            "Тестовый финч bob #6: вторая порция тоже по свежести.",
            "Тестовый финч bob #5: проверка середины списка.",
            "Тестовый финч bob #4: ещё один пост для наблюдения.",
            "Тестовый финч bob #3: ближе к старым записям.",
            "Тестовый финч bob #2: предпоследний тестовый финч.",
            "Тестовый финч bob #1: самый старый тестовый финч.",
        ]

        Finch.objects.filter(user=bob, text__startswith="Тестовый финч bob #").delete()
        now = timezone.now()
        posts = [Finch(user=bob, text=text) for text in texts]
        Finch.objects.bulk_create(posts)

        for index, text in enumerate(texts):
            post = Finch.objects.get(user=bob, text=text)
            post.created_at = now - timedelta(minutes=index)
            post.save(update_fields=["created_at"])

        self.stdout.write(self.style.SUCCESS("Created 12 demo posts from bob and subscribed sovetkali to bob."))
