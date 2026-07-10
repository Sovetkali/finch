from datetime import timedelta

from asgiref.sync import sync_to_async
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, F
from django.http import JsonResponse
from django.shortcuts import aget_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import format_html
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .forms import UserRegisterForm
from .context_processors import unread_notifications_cache_key
from .models import Comment, Finch, FinchView, Notification, PlatformEvent, Subscription
from .tasks import build_activation_message, send_activation_email_task
from .templatetags.finch_markup import MENTION_RE

FINCHES_PER_PAGE = 5


async def create_mention_notifications(text, actor, finch, comment=None):
    usernames = {
        match.group("username")
        for match in MENTION_RE.finditer(text or "")
        if match.group("username") != actor.username
    }
    if not usernames:
        return

    recipients = await sync_to_async(list)(
        User.objects.filter(username__in=usernames)
    )
    for recipient in recipients:
        await Notification.objects.acreate(
            recipient=recipient,
            actor=actor,
            event_type=Notification.MENTION,
            finch=finch,
            comment=comment,
        )
        cache.delete(unread_notifications_cache_key(recipient.id))


async def create_comment_notification(comment):
    if comment.finch.user_id == comment.user_id:
        return

    await Notification.objects.acreate(
        recipient_id=comment.finch.user_id,
        actor=comment.user,
        event_type=Notification.COMMENT,
        finch=comment.finch,
        comment=comment,
    )
    cache.delete(unread_notifications_cache_key(comment.finch.user_id))


async def create_follow_notification(actor, recipient):
    await Notification.objects.acreate(
        recipient=recipient,
        actor=actor,
        event_type=Notification.FOLLOW,
    )
    cache.delete(unread_notifications_cache_key(recipient.id))


@require_POST
async def record_profile_share(request):
    user = await request.auser()
    if not user.is_authenticated:
        return JsonResponse({"detail": "Authentication required."}, status=403)

    target_username = request.POST.get("target_username", "").strip()
    path = request.POST.get("path", "").strip()
    target_user = None
    if target_username:
        try:
            target_user = await User.objects.aget(username=target_username)
        except User.DoesNotExist:
            target_user = None

    await PlatformEvent.objects.acreate(
        event_type=PlatformEvent.PROFILE_SHARE,
        user=user,
        target_user=target_user,
        path=path,
    )
    return JsonResponse({"ok": True})


def visible_finches_for_user(user, followed_authors_ids):
    queryset = Finch.objects.select_related("user", "original", "original__user").annotate(
        comments_count=Count("comments")
    ).order_by("-created_at")
    if user.is_authenticated:
        return queryset.filter(user_id__in=followed_authors_ids)
    return queryset


async def render_async(request, template_name, context=None, *args, **kwargs):
    return await sync_to_async(render, thread_sensitive=True)(
        request,
        template_name,
        context,
        *args,
        **kwargs,
    )


async def index(request):
    user = await request.auser()

    if request.method == "POST":
        text = request.POST.get('text')
        if text:
            if len(text) > 140:
                messages.error(request, _("Text cannot exceed 140 characters."))
            else:
                if user.is_authenticated:
                    finch = await Finch.objects.acreate(user=user, text=text)
                    await create_mention_notifications(text, user, finch)
                else:
                    messages.error(request, _("Only authenticated users can post."))
                    return redirect('login')
        return redirect('index')
    
    if user.is_authenticated:
        followed_authors_ids = await sync_to_async(list)(
            Subscription.objects.filter(user=user).values_list("author_id", flat=True)
        )
    else:
        followed_authors_ids = []
    finches = visible_finches_for_user(user, followed_authors_ids)

    after_id = request.GET.get("after_id")
    if request.GET.get("format") == "json" and after_id:
        try:
            after_id = int(after_id)
        except ValueError:
            after_id = 0
        new_finches = await sync_to_async(list)(finches.filter(id__gt=after_id).order_by("-created_at"))
        context = {
            "finches": new_finches,
            "followed_authors_ids": set(followed_authors_ids),
            "suppress_empty": True,
        }
        html = await sync_to_async(render)(
            request,
            "finch/_finch_list.html",
            context,
        )
        return JsonResponse({
            "html": html.content.decode("utf-8"),
            "count": len(new_finches),
        })

    try:
        page = max(1, int(request.GET.get("page", 1) or 1))
    except ValueError:
        page = 1
    start = (page - 1) * FINCHES_PER_PAGE
    stop = start + FINCHES_PER_PAGE + 1
    finches_page = await sync_to_async(list)(finches[start:stop])
    has_next = len(finches_page) > FINCHES_PER_PAGE
    finches_page = finches_page[:FINCHES_PER_PAGE]

    context = {
        "finches": finches_page,
        "followed_authors_ids": set(followed_authors_ids),
        "next_page": page + 1 if has_next else None,
    }

    if request.GET.get("format") == "json":
        html = await sync_to_async(render)(
            request,
            "finch/_finch_list.html",
            context,
        )
        return JsonResponse({
            "html": html.content.decode("utf-8"),
            "next_page": context["next_page"],
        })

    return await render_async(request, "finch/index.html", context)


async def register(request):
    """Handle user registration.
    After a successful sign‑up the user is redirected to the onboarding page
    where they can copy an invitation link to share with friends.
    """
    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        is_valid = await sync_to_async(form.is_valid)()
        if is_valid:
            user = await sync_to_async(form.save)()
            activation_url = await sync_to_async(send_activation_email)(request, user)
            if settings.DEBUG:
                messages.success(
                    request,
                    format_html(
                        '{} <a href="{}">{}</a>',
                        _("Local development: confirm registration here:"),
                        activation_url,
                        _("activate account"),
                    ),
                )
            else:
                messages.success(request, _("Check your email: we sent an activation link."))
            return redirect("login")
    else:
        form = UserRegisterForm()

    return await render_async(request, "finch/register.html", {"form": form})


def send_activation_email(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    activation_url = request.build_absolute_uri(reverse("activate_account", kwargs={"uidb64": uid, "token": token}))
    message = build_activation_message(
        user,
        "https" if request.is_secure() else "http",
        request.get_host(),
        uid,
        token,
    )
    send_activation_email_task(user.email, "Confirm your Finch registration", message)
    return activation_url


async def activate_account(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = await User.objects.aget(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    token_is_valid = user is not None and await sync_to_async(default_token_generator.check_token)(user, token)
    if token_is_valid:
        user.is_active = True
        await user.asave(update_fields=["is_active"])
        await sync_to_async(login)(request, user)
        messages.success(request, _("Email confirmed. Welcome to Finch!"))
        return redirect("onboarding")

    if user is not None and user.is_active:
        await sync_to_async(login)(request, user)
        messages.info(request, _("Email is already confirmed. Welcome back!"))
        return redirect("onboarding")

    messages.error(request, _("The activation link is invalid or expired."))
    return redirect("login")


@login_required
async def onboarding(request):
    """Render onboarding page with a copy-to-clipboard invitation link.
    This is a manual share method (Option B)."""
    user = await request.auser()
    invite_url = request.build_absolute_uri(reverse("profile", kwargs={"username": user.username}))
    return await render_async(request, "finch/onboarding.html", {"invite_url": invite_url})


@login_required
async def follow_user(request, author_id):
    """Toggle subscription to another user (follow/unfollow)."""
    user = await request.auser()

    if user.id == author_id:
        return redirect('index')

    subscription_qs = Subscription.objects.filter(user=user, author_id=author_id)
    if await subscription_qs.aexists():
        await subscription_qs.adelete()
    else:
        try:
            author = await User.objects.aget(id=author_id)
        except User.DoesNotExist:
            referer = request.META.get('HTTP_REFERER')
            return redirect(referer) if referer else redirect('index')
        await Subscription.objects.acreate(user=user, author=author)
        await create_follow_notification(user, author)
    
    referer = request.META.get('HTTP_REFERER')
    return redirect(referer) if referer else redirect('index')


@login_required
async def subscriptions_list(request):
    """Display the profiles the current user follows and is followed by."""
    user = await request.auser()
    subscriptions = await sync_to_async(list)(
        Subscription.objects.filter(user=user).select_related('author')
    )
    followers = await sync_to_async(list)(
        Subscription.objects.filter(author=user).select_related('user')
    )
    following_ids = set(
        await sync_to_async(list)(
            Subscription.objects.filter(user=user).values_list("author_id", flat=True)
        )
    )
    return await render_async(
        request,
        "finch/subscriptions_list.html",
        {
            "subscriptions": subscriptions,
            "followers": followers,
            "following_ids": following_ids,
        },
    )


@login_required
async def delete_account(request):
    """Delete the current user's account and log them out."""
    user = await request.auser()

    if request.method == "POST":
        await sync_to_async(logout)(request)
        await user.adelete()
        return redirect("index")
    return await render_async(request, "finch/delete_account_confirm.html")


@login_required
@ensure_csrf_cookie
async def profile(request, username):
    """Display another user's finches page.

    Shows posts made by the user identified by their unique username.
    Also provides follow/unfollow button status.
    """
    user = await request.auser()
    target_user = await aget_object_or_404(User, username=username)
    finches = await sync_to_async(list)(
        Finch.objects.filter(user=target_user)
        .select_related("user", "original", "original__user")
        .annotate(comments_count=Count("comments"))
        .order_by("-created_at")
    )
    comments = await sync_to_async(list)(
        Comment.objects.filter(user=target_user)
        .select_related("finch", "finch__user")
        .order_by("-created_at")
    )
    is_following = await Subscription.objects.filter(user=user, author=target_user).aexists()
    context = {
        "profile_user": target_user,
        "finches": finches,
        "comments": comments,
        "is_following": is_following,
    }
    return await render_async(request, "finch/profile.html", context)


async def finch_detail(request, finch_id):
    """Display a single finch post."""
    user = await request.auser()
    if request.method == "POST":
        if not user.is_authenticated:
            return redirect("login")
        text = (request.POST.get("text") or "").strip()
        if text:
            if len(text) > 280:
                messages.error(request, _("Comment cannot exceed 280 characters."))
            else:
                finch = await aget_object_or_404(Finch, id=finch_id)
                comment = await Comment.objects.acreate(finch=finch, user=user, text=text)
                await create_comment_notification(comment)
                await create_mention_notifications(text, user, finch, comment)
        return redirect("finch_detail", finch_id=finch_id)

    if user.is_authenticated:
        viewer_id = f"user:{user.id}"
    else:
        if not request.session.session_key:
            await sync_to_async(request.session.create, thread_sensitive=True)()
        viewer_id = f"session:{request.session.session_key}"

    _, created = await FinchView.objects.aget_or_create(finch_id=finch_id, viewer_id=viewer_id)
    if created:
        await Finch.objects.filter(id=finch_id).aupdate(views_count=F("views_count") + 1)
    finch = await aget_object_or_404(Finch.objects.select_related("user", "original", "original__user"), id=finch_id)
    comments = await sync_to_async(list)(
        Comment.objects.filter(finch=finch).select_related("user").order_by("-created_at")
    )
    followed_authors_ids = []
    if user.is_authenticated:
        followed_authors_ids = await sync_to_async(list)(
            Subscription.objects.filter(user=user).values_list("author_id", flat=True)
        )
    context = {
        "finch": finch,
        "comments": comments,
        "followed_authors_ids": set(followed_authors_ids),
    }
    return await render_async(request, "finch/finch_detail.html", context)


@login_required
async def repost_finch(request, finch_id):
    """Create a repost for the current user."""
    if request.method != "POST":
        return redirect("finch_detail", finch_id=finch_id)

    user = await request.auser()
    original = await aget_object_or_404(Finch.objects.select_related("original"), id=finch_id)
    root_original = original.original or original
    already_reposted = await Finch.objects.filter(user=user, original=root_original).aexists()
    if original.user_id != user.id and not already_reposted:
        await Finch.objects.acreate(user=user, text=root_original.text, original=root_original)
    return redirect("finch_detail", finch_id=finch_id)


@login_required
async def delete_finch(request, finch_id):
    """Delete a finch post belonging to the current user."""
    user = await request.auser()
    finch = await aget_object_or_404(Finch, id=finch_id, user=user)
    if request.method == "POST":
        await finch.adelete()
        return redirect("profile", username=user.username)
    return await render_async(request, "finch/delete_confirm.html", {"finch": finch})


@login_required
async def notifications_list(request):
    user = await request.auser()
    notifications = Notification.objects.filter(recipient=user).select_related(
        "actor",
        "finch",
        "finch__user",
        "comment",
    )

    if request.method == "POST":
        await notifications.filter(read_at__isnull=True).aupdate(read_at=timezone.now())
        cache.delete(unread_notifications_cache_key(user.id))
        return redirect("notifications_list")

    return await render_async(
        request,
        "finch/notifications.html",
        {"notifications": await sync_to_async(list)(notifications[:50])},
    )


@login_required
async def notifications_status(request):
    user = await request.auser()
    unread_count = await Notification.objects.filter(recipient=user, read_at__isnull=True).acount()
    return JsonResponse({"unread_count": unread_count})


@login_required
async def notifications_updates(request):
    user = await request.auser()
    after_id = request.GET.get("after_id")
    try:
        after_id = int(after_id or 0)
    except ValueError:
        after_id = 0

    notifications = Notification.objects.filter(recipient=user, id__gt=after_id).select_related(
        "actor",
        "finch",
        "finch__user",
        "comment",
    ).order_by("created_at")
    new_notifications = await sync_to_async(list)(notifications[:20])
    html = await sync_to_async(render)(
        request,
        "finch/_notifications_list.html",
        {"notifications": new_notifications, "suppress_empty": True},
    )
    unread_count = await Notification.objects.filter(recipient=user, read_at__isnull=True).acount()
    return JsonResponse({
        "html": html.content.decode("utf-8"),
        "count": len(new_notifications),
        "unread_count": unread_count,
    })


def build_platform_stats_context(search_query="", page_number=1):
    today = timezone.now().date()
    now = timezone.now()
    users_qs = User.objects.all()
    if search_query:
        users_qs = users_qs.filter(username__icontains=search_query)
    posts_qs = Finch.objects.all()
    shares_qs = PlatformEvent.objects.filter(event_type=PlatformEvent.PROFILE_SHARE)
    logins_qs = PlatformEvent.objects.filter(event_type=PlatformEvent.LOGIN)
    paginator = Paginator(
        users_qs.order_by("-date_joined").values("id", "username", "is_staff", "last_login", "date_joined"),
        20,
    )
    page_obj = paginator.get_page(page_number)

    def avg_per_day(days):
        start = now - timedelta(days=days)
        return round(posts_qs.filter(created_at__gte=start).count() / max(days, 1), 2)

    return {
        "registered_users": users_qs.count(),
        "registered_users_list": list(page_obj.object_list),
        "users_page_obj": page_obj,
        "users_search_query": search_query,
        "users_today": users_qs.filter(date_joined__date=today).count(),
        "users_week": users_qs.filter(date_joined__gte=now - timedelta(days=7)).count(),
        "users_month": users_qs.filter(date_joined__gte=now - timedelta(days=30)).count(),
        "avg_posts_day": avg_per_day(1),
        "avg_posts_week": avg_per_day(7),
        "avg_posts_month": avg_per_day(30),
        "profile_share_clicks": shares_qs.count(),
        "recent_logins": list(logins_qs.select_related("user")[:20]),
        "recent_shares": list(shares_qs.select_related("user", "target_user")[:20]),
    }


@login_required
async def platform_stats(request):
    user = await request.auser()
    if not user.is_staff:
        return JsonResponse({"detail": "Forbidden."}, status=403)

    if request.method == "POST":
        post_data = await sync_to_async(request.POST.dict, thread_sensitive=True)()
        username = (post_data.get("username") or "").strip()
        is_staff_value = post_data.get("is_staff") in {"1", "true", "on", "yes"}
        if username:
            try:
                target_user = await User.objects.aget(username=username)
                target_user.is_staff = is_staff_value
                await target_user.asave(update_fields=["is_staff"])
                messages.success(request, _("Staff access updated for @%(username)s.") % {"username": username})
            except User.DoesNotExist:
                messages.error(request, _("User @%(username)s was not found.") % {"username": username})
        return redirect("platform_stats")

    search_query = request.GET.get("q", "").strip()
    try:
        page_number = int(request.GET.get("page", "1") or 1)
    except ValueError:
        page_number = 1
    context = await sync_to_async(build_platform_stats_context, thread_sensitive=True)(search_query, page_number)
    return await render_async(request, "finch/platform_stats.html", context)
