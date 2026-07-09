from django.db import models
from django.contrib.auth.models import User


class Finch(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Author")
    text = models.CharField(max_length=140, verbose_name="Message")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Posted date")
    original = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="reposts",
        blank=True,
        null=True,
        verbose_name="Original post",
    )
    views_count = models.PositiveIntegerField(default=0, verbose_name="Views")

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=["user", "-created_at"], name="finch_user_created_idx"),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username}: {self.text[:20]}..."


class Comment(models.Model):
    finch = models.ForeignKey(Finch, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comments")
    text = models.CharField(max_length=280, verbose_name="Comment")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Commented date")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}: {self.text[:20]}..."


class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'author') 

    def __str__(self):
        return f"{self.user.username} подписан на {self.author.username}"


class Notification(models.Model):
    MENTION = "mention"
    COMMENT = "comment"
    FOLLOW = "follow"
    EVENT_CHOICES = (
        (MENTION, "Mention"),
        (COMMENT, "Comment"),
        (FOLLOW, "Follow"),
    )

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_notifications")
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    finch = models.ForeignKey(Finch, on_delete=models.CASCADE, related_name="notifications", blank=True, null=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="notifications", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "read_at", "-created_at"], name="finch_notification_unread_idx"),
        ]

    @property
    def is_unread(self):
        return self.read_at is None

    def __str__(self):
        return f"{self.actor.username} -> {self.recipient.username}: {self.event_type}"
