from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

def send_activation_email_task(email, subject, message):
    """Send activation email outside the request cycle when a worker is available."""
    EmailMessage(_(subject), message, to=[email]).send()
    return True


def build_activation_message(user, protocol, domain, uid, token):
    context = {
        "user": user,
        "protocol": protocol,
        "domain": domain,
        "uid": uid,
        "token": token,
    }
    return render_to_string("registration/account_activation_email.html", context)
