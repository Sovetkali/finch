from django.apps import AppConfig


class FinchConfig(AppConfig):
    name = 'finch'

    def ready(self):
        from . import signals  # noqa: F401
