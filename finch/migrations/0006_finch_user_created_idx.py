from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finch", "0005_allow_follow_notifications_without_post"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="finch",
            index=models.Index(fields=["user", "-created_at"], name="finch_user_created_idx"),
        ),
    ]
