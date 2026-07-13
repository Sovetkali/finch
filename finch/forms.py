from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _


class UserRegisterForm(UserCreationForm):
    """Custom form for user registration.
    
    Overrides the default unique error message for the username field to be in Russian
    and applies Bootstrap 'form-control' styling to all form fields.
    """
    email = forms.EmailField(label=_("Email"), required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")
        error_messages = {
            'username': {
                'unique': _("Пользователь с таким именем уже существует."),
            },
        }

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(_("Пользователь с таким именем уже существует."))
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("Пользователь с таким email уже существует."))
        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically append Bootstrap styling to all form fields
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_active = False
        if commit:
            user.save()
        return user
