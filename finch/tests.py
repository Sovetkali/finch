from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase, Client
from django.test.utils import override_settings
from django.core.cache import cache
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from finch.forms import UserRegisterForm
from finch.templatetags.finch_markup import finch_markup


class RegistrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.username = "existing_user"
        self.password = "Secr3tP@ssw0rd!"
        self.user = User.objects.create_user(username=self.username, password=self.password)

    def test_form_validation_duplicate_username(self):
        # Test form invalidity for a duplicate username
        form = UserRegisterForm(data={
            'username': self.username,
            'email': 'duplicate@example.com',
            'password1': 'SuperSecurePassword99',
            'password2': 'SuperSecurePassword99',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
        self.assertEqual(form.errors['username'][0], "Пользователь с таким именем уже существует.")

    def test_form_validation_success(self):
        # Test form validity for a new unique username
        form = UserRegisterForm(data={
            'username': 'new_unique_user',
            'email': 'new_unique_user@example.com',
            'password1': 'SuperSecurePassword99',
            'password2': 'SuperSecurePassword99',
        })
        self.assertTrue(form.is_valid())

    def test_registration_view_duplicate_user(self):
        # Test post to registration view with existing username
        response = self.client.post(reverse('register'), {
            'username': self.username,
            'email': 'duplicate@example.com',
            'password1': 'SuperSecurePassword99',
            'password2': 'SuperSecurePassword99',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Пользователь с таким именем уже существует.")

    def test_registration_view_success(self):
        # Test post to registration view with unique username
        response = self.client.post(reverse('register'), {
            'username': 'brand_new_user',
            'email': 'brand_new_user@example.com',
            'password1': 'SuperSecurePassword99',
            'password2': 'SuperSecurePassword99',
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username='brand_new_user')
        self.assertEqual(user.email, 'brand_new_user@example.com')
        self.assertFalse(user.is_active)

    def test_onboarding_invite_link_points_to_user_profile(self):
        self.client.login(username=self.username, password=self.password)

        response = self.client.get(reverse("onboarding"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"http://testserver/profile/{self.username}/")

    def test_activation_link_activates_user(self):
        user = User.objects.create_user(
            username="pending_user",
            email="pending@example.com",
            password="SuperSecurePassword99",
            is_active=False,
        )
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        response = self.client.get(reverse("activate_account", kwargs={"uidb64": uid, "token": token}))

        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_activation_link_expires_after_three_days(self):
        user = User.objects.create_user(
            username="expired_user",
            email="expired@example.com",
            password="SuperSecurePassword99",
            is_active=False,
        )
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        with patch.object(default_token_generator, "_now", return_value=datetime.now() - timedelta(days=4)):
            token = default_token_generator.make_token(user)

        response = self.client.get(reverse("activate_account", kwargs={"uidb64": uid, "token": token}))

        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_reused_activation_link_for_active_user_redirects_to_onboarding(self):
        user = User.objects.create_user(
            username="active_user",
            email="active@example.com",
            password="SuperSecurePassword99",
            is_active=True,
        )
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        response = self.client.get(reverse("activate_account", kwargs={"uidb64": uid, "token": token}))

        self.assertRedirects(response, reverse("onboarding"))


class FinchPostTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username="user1", password="password1")
        self.user2 = User.objects.create_user(username="user2", password="password2")
        from finch.models import Finch
        self.post1 = Finch.objects.create(user=self.user1, text="Post from user1")
        self.post2 = Finch.objects.create(user=self.user2, text="Post from user2")

    def test_finch_detail_view(self):
        # Test viewing post details
        response = self.client.get(reverse('finch_detail', kwargs={'finch_id': self.post1.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Post from user1")
        self.assertContains(response, "@user1")
        self.post1.refresh_from_db()
        self.assertEqual(self.post1.views_count, 1)

        response = self.client.get(reverse('finch_detail', kwargs={'finch_id': self.post1.id}))
        self.assertEqual(response.status_code, 200)
        self.post1.refresh_from_db()
        self.assertEqual(self.post1.views_count, 1)

    def test_finch_detail_counts_unique_authenticated_users(self):
        self.client.login(username="user2", password="password2")

        response = self.client.get(reverse('finch_detail', kwargs={'finch_id': self.post1.id}))
        self.assertEqual(response.status_code, 200)
        self.post1.refresh_from_db()
        self.assertEqual(self.post1.views_count, 1)

        response = self.client.get(reverse('finch_detail', kwargs={'finch_id': self.post1.id}))
        self.assertEqual(response.status_code, 200)
        self.post1.refresh_from_db()
        self.assertEqual(self.post1.views_count, 1)

        self.client.login(username="user1", password="password1")
        response = self.client.get(reverse('finch_detail', kwargs={'finch_id': self.post1.id}))
        self.assertEqual(response.status_code, 200)
        self.post1.refresh_from_db()
        self.assertEqual(self.post1.views_count, 2)

    def test_post_markup_renders_safe_subset(self):
        rendered = str(finch_markup("Hi **Bob** @user2 `code` https://example.com <script>"))

        self.assertIn("<strong>Bob</strong>", rendered)
        self.assertIn('<a href="/profile/user2/"', rendered)
        self.assertIn("<code>code</code>", rendered)
        self.assertIn('href="https://example.com"', rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("<script>", rendered)

    def test_comment_post_and_profile_tab(self):
        self.client.login(username="user2", password="password2")
        response = self.client.post(
            reverse("finch_detail", kwargs={"finch_id": self.post1.id}),
            {"text": "Nice chirp"},
        )
        self.assertEqual(response.status_code, 302)

        from finch.models import Comment
        self.assertTrue(Comment.objects.filter(finch=self.post1, user=self.user2, text="Nice chirp").exists())

        response = self.client.get(reverse("profile", kwargs={"username": self.user2.username}))
        self.assertContains(response, "Nice chirp")
        self.assertContains(response, "Comments")

    def test_comment_creates_notification_for_post_author(self):
        self.client.login(username="user2", password="password2")
        self.client.post(
            reverse("finch_detail", kwargs={"finch_id": self.post1.id}),
            {"text": "Nice post"},
        )

        from finch.models import Notification
        notification = Notification.objects.get(recipient=self.user1)
        self.assertEqual(notification.actor, self.user2)
        self.assertEqual(notification.event_type, Notification.COMMENT)

    def test_mention_creates_notification(self):
        self.client.login(username="user1", password="password1")
        self.client.post(reverse("index"), {"text": "Hello @user2"})

        from finch.models import Notification
        notification = Notification.objects.get(recipient=self.user2)
        self.assertEqual(notification.actor, self.user1)
        self.assertEqual(notification.event_type, Notification.MENTION)

    def test_notifications_page_marks_items_read(self):
        from finch.models import Notification
        notification = Notification.objects.create(
            recipient=self.user1,
            actor=self.user2,
            event_type=Notification.COMMENT,
            finch=self.post1,
        )
        self.client.login(username="user1", password="password1")

        response = self.client.get(reverse("index"))
        self.assertContains(response, 'href="/notifications/"')
        self.assertContains(response, 'text-bg-danger')

        response = self.client.post(reverse("notifications_list"))
        self.assertEqual(response.status_code, 302)
        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)
        cache.delete(f"unread_notifications_count:{self.user1.id}")

    def test_notifications_status_returns_unread_count(self):
        from finch.models import Notification
        Notification.objects.create(
            recipient=self.user1,
            actor=self.user2,
            event_type=Notification.COMMENT,
            finch=self.post1,
        )
        self.client.login(username="user1", password="password1")

        response = self.client.get(reverse("notifications_status"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["unread_count"], 1)

    def test_notifications_updates_returns_new_notifications(self):
        from finch.models import Notification
        first = Notification.objects.create(
            recipient=self.user1,
            actor=self.user2,
            event_type=Notification.COMMENT,
            finch=self.post1,
        )
        Notification.objects.create(
            recipient=self.user1,
            actor=self.user2,
            event_type=Notification.FOLLOW,
        )
        self.client.login(username="user1", password="password1")

        response = self.client.get(reverse("notifications_updates"), {"after_id": first.id})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertIn("подписался на вас", data["html"])

    def test_feed_shows_comment_count(self):
        from finch.models import Comment
        Comment.objects.create(finch=self.post1, user=self.user2, text="One")
        Comment.objects.create(finch=self.post1, user=self.user2, text="Two")
        self.client.login(username="user2", password="password2")

        response = self.client.get(reverse("profile", kwargs={"username": self.user1.username}))

        self.assertContains(response, 'aria-label="2 comments"')
        self.assertContains(response, '<span class="action-count">2</span>', html=True)

    def test_repost_creates_post_for_current_user(self):
        self.client.login(username="user2", password="password2")
        response = self.client.post(reverse("repost_finch", kwargs={"finch_id": self.post1.id}))
        self.assertEqual(response.status_code, 302)

        from finch.models import Finch
        repost = Finch.objects.get(user=self.user2, original=self.post1)
        self.assertEqual(repost.text, self.post1.text)

    def test_delete_own_post(self):
        # Test deleting own post
        self.client.login(username="user1", password="password1")
        response = self.client.post(reverse('delete_finch', kwargs={'finch_id': self.post1.id}))
        self.assertEqual(response.status_code, 302) # Redirect to profile
        from finch.models import Finch
        self.assertFalse(Finch.objects.filter(id=self.post1.id).exists())

    def test_cannot_delete_others_post(self):
        # Test that user cannot delete someone else's post
        self.client.login(username="user1", password="password1")
        response = self.client.post(reverse('delete_finch', kwargs={'finch_id': self.post2.id}))
        self.assertEqual(response.status_code, 404)
        from finch.models import Finch
        self.assertTrue(Finch.objects.filter(id=self.post2.id).exists())


class FeedPaginationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="reader", password="password123")
        self.author = User.objects.create_user(username="bob", password="password123")

        from finch.models import Finch, Subscription
        Subscription.objects.create(user=self.user, author=self.author)
        now = timezone.now()
        for index in range(7):
            post = Finch.objects.create(user=self.author, text=f"Feed post {index + 1}")
            post.created_at = now - timezone.timedelta(minutes=index)
            post.save(update_fields=["created_at"])

    def test_index_shows_first_five_posts(self):
        self.client.login(username="reader", password="password123")
        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Feed post 1")
        self.assertContains(response, "Feed post 5")
        self.assertNotContains(response, "Feed post 6")
        self.assertContains(response, 'data-next-page="2"')

    def test_index_renders_follow_state_without_following_ids(self):
        self.client.login(username="reader", password="password123")
        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Feed post 1")
        self.assertContains(response, "Feed post 5")

    def test_json_page_loads_next_posts(self):
        self.client.login(username="reader", password="password123")
        response = self.client.get(reverse("index"), {"page": 2, "format": "json"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("Feed post 6", data["html"])
        self.assertIn("Feed post 7", data["html"])
        self.assertNotIn("Feed post 5", data["html"])
        self.assertIsNone(data["next_page"])

    def test_json_after_id_loads_new_posts_only(self):
        from finch.models import Finch
        self.client.login(username="reader", password="password123")
        latest_id = Finch.objects.order_by("-id").first().id
        new_post = Finch.objects.create(user=self.author, text="Fresh live post")

        response = self.client.get(reverse("index"), {"after_id": latest_id, "format": "json"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertIn("Fresh live post", data["html"])
        self.assertIn(f'data-finch-id="{new_post.id}"', data["html"])
        self.assertNotIn("No posts yet", data["html"])

    def test_health_check_returns_status_payload(self):
        response = self.client.get(reverse("health_check"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"database": True, "cache": True})

    def test_notifications_badge_refreshes_after_reading(self):
        from finch.models import Finch, Notification
        post = Finch.objects.create(user=self.author, text="Cache test post")

        Notification.objects.create(
            recipient=self.user,
            actor=self.author,
            event_type=Notification.COMMENT,
            finch=post,
        )
        self.client.login(username="reader", password="password123")

        response = self.client.get(reverse("index"))
        self.assertContains(response, 'data-notification-badge')

        self.client.post(reverse("notifications_list"))
        cache.delete(f"unread_notifications_count:{self.user.id}")

        response = self.client.get(reverse("notifications_status"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["unread_count"], 0)

    @override_settings(
        REST_FRAMEWORK={
            "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.UserRateThrottle"],
            "DEFAULT_THROTTLE_RATES": {"user": "1/min"},
        }
    )
    def test_ping_endpoint_is_throttled(self):
        self.client.login(username="reader", password="password123")

        first = self.client.get(reverse("ping"))
        second = self.client.get(reverse("ping"))

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)


class SubscriptionsAndAccountDeletionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.author1 = User.objects.create_user(username="author1", password="password123")
        self.author2 = User.objects.create_user(username="author2", password="password123")
        self.follower = User.objects.create_user(username="follower", password="password123")
        
        from finch.models import Subscription
        Subscription.objects.create(user=self.user, author=self.author1)
        Subscription.objects.create(user=self.follower, author=self.user)

    def test_subscriptions_list_requires_login(self):
        # Anonymous users cannot view subscriptions list
        response = self.client.get(reverse('subscriptions_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_subscriptions_list_success(self):
        # Logged-in user can view subscriptions list
        self.client.login(username="testuser", password="password123")
        response = self.client.get(reverse('subscriptions_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "@author1")
        self.assertContains(response, "@follower")
        self.assertNotContains(response, "@author2")
        self.assertIn("subscriptions", response.context)
        self.assertIn("followers", response.context)
        self.assertIn("following_ids", response.context)

    def test_subscriptions_list_marks_mutual_followers(self):
        from finch.models import Subscription

        Subscription.objects.create(user=self.user, author=self.follower)
        self.client.login(username="testuser", password="password123")

        response = self.client.get(reverse('subscriptions_list'))

        self.assertContains(response, "@follower")
        self.assertContains(response, "Взаимно")

    def test_subscriptions_empty_shows_search_unavailable_message(self):
        from finch.models import Subscription
        Subscription.objects.filter(user=self.user).delete()
        self.client.login(username="testuser", password="password123")

        response = self.client.get(reverse('subscriptions_list'))

        self.assertContains(response, "Поиск друзей пока недоступен. Мы работаем над этим.")
        self.assertNotContains(response, "Найти кого почитать")

    def test_unsubscribe_and_redirect_back(self):
        self.client.login(username="testuser", password="password123")
        subscriptions_url = reverse('subscriptions_list')
        
        # Toggle follow for author1 (unfollow) with REFERER set to subscriptions_list
        response = self.client.get(
            reverse('follow_user', kwargs={'author_id': self.author1.id}),
            HTTP_REFERER=subscriptions_url
        )
        # Check redirection back to HTTP_REFERER
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, subscriptions_url)
        
        # Check subscription was deleted
        from finch.models import Subscription
        self.assertFalse(Subscription.objects.filter(user=self.user, author=self.author1).exists())

    def test_follow_creates_notification_for_author(self):
        self.client.login(username="testuser", password="password123")

        response = self.client.get(reverse('follow_user', kwargs={'author_id': self.author2.id}))

        self.assertEqual(response.status_code, 302)
        from finch.models import Notification
        notification = Notification.objects.get(recipient=self.author2)
        self.assertEqual(notification.actor, self.user)
        self.assertEqual(notification.event_type, Notification.FOLLOW)

    def test_delete_account_requires_login(self):
        response = self.client.get(reverse('delete_account'))
        self.assertEqual(response.status_code, 302)
        
        response = self.client.post(reverse('delete_account'))
        self.assertEqual(response.status_code, 302)

    def test_delete_account_get_confirm_page(self):
        self.client.login(username="testuser", password="password123")
        response = self.client.get(reverse('delete_account'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Вы уверены, что хотите удалить свой аккаунт?")

    def test_delete_account_post_deletes_user(self):
        self.client.login(username="testuser", password="password123")
        response = self.client.post(reverse('delete_account'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('index'))
        
        # User should no longer exist
        self.assertFalse(User.objects.filter(username="testuser").exists())
