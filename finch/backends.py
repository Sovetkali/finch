from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class CaseInsensitiveUsernameBackend(ModelBackend):
    """Authenticate users without considering username letter case."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        user_model = get_user_model()
        if username is None:
            username = kwargs.get(user_model.USERNAME_FIELD)
        if username is None or password is None:
            return None

        try:
            user = user_model._default_manager.get(
                **{f"{user_model.USERNAME_FIELD}__iexact": username}
            )
        except user_model.DoesNotExist:
            # Run the password hasher once to reduce timing differences between
            # existing and nonexistent users.
            user_model().set_password(password)
            return None
        except user_model.MultipleObjectsReturned:
            # Preserve access to existing case-only duplicates when the supplied
            # username matches one of them exactly. Other spellings are ambiguous.
            try:
                user = user_model._default_manager.get(
                    **{user_model.USERNAME_FIELD: username}
                )
            except user_model.DoesNotExist:
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
