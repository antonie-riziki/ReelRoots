from django.db import migrations, models
import django.db.models.deletion
import uuid


TOPICS = [
    ("history", "History", "heritage"),
    ("culture", "Culture", "heritage"),
    ("heritage", "Heritage", "heritage"),
    ("oral-history", "Oral history", "heritage"),
    ("indigenous-knowledge", "Indigenous knowledge", "heritage"),
    ("architecture", "Architecture", "heritage"),
    ("music", "Music", "culture"),
    ("food", "Food", "culture"),
    ("art", "Art", "culture"),
    ("historical-figures", "Historical figures", "history"),
    ("historical-events", "Historical events", "history"),
]


def seed_topics(apps, schema_editor):
    Topic = apps.get_model("ReelRoots_app", "Topic")
    for slug, name, group in TOPICS:
        Topic.objects.update_or_create(slug=slug, defaults={"name": name, "group": group, "is_active": True})


def remove_topics(apps, schema_editor):
    Topic = apps.get_model("ReelRoots_app", "Topic")
    Topic.objects.filter(slug__in=[slug for slug, _, _ in TOPICS]).delete()


class Migration(migrations.Migration):
    dependencies = [("ReelRoots_app", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("supabase_user_id", models.UUIDField(unique=True)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("name", models.CharField(max_length=150)),
                ("phone_number", models.CharField(max_length=32, unique=True)),
                ("phone_verified_at", models.DateTimeField(blank=True, null=True)),
                ("institution", models.CharField(blank=True, max_length=255)),
                ("onboarding_completed", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Topic",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(unique=True)),
                ("name", models.CharField(max_length=120)),
                ("group", models.CharField(default="heritage", max_length=80)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["group", "name"]},
        ),
        migrations.CreateModel(
            name="PendingSignup",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("supabase_user_id", models.UUIDField(unique=True)),
                ("email", models.EmailField(max_length=254)),
                ("name", models.CharField(max_length=150)),
                ("phone_number", models.CharField(max_length=32)),
                ("institution", models.CharField(blank=True, max_length=255)),
                ("encrypted_password", models.TextField()),
                ("expires_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="ProfileInterest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(choices=[("explicit", "Explicit selection"), ("observed", "Observed behavior")], max_length=20)),
                ("weight", models.DecimalField(decimal_places=4, default=0, max_digits=10)),
                ("event_count", models.PositiveIntegerField(default=0)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="interests", to="ReelRoots_app.userprofile")),
                ("topic", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="profile_interests", to="ReelRoots_app.topic")),
            ],
            options={"ordering": ["-weight", "topic__name"]},
        ),
        migrations.CreateModel(
            name="ProfilePreference",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("preference_type", models.CharField(choices=[("region", "Region"), ("country", "Country"), ("language", "Language"), ("content_type", "Content type")], max_length=24)),
                ("value", models.CharField(max_length=120)),
                ("source", models.CharField(default="explicit", max_length=20)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="preferences", to="ReelRoots_app.userprofile")),
            ],
            options={"ordering": ["preference_type", "value"]},
        ),
        migrations.CreateModel(
            name="PersonalizationEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("watch", "Watch"), ("completion", "Completion"), ("save", "Save"), ("like", "Like"), ("share", "Share"), ("search", "Search")], max_length=20)),
                ("content_key", models.CharField(blank=True, max_length=255)),
                ("value", models.DecimalField(decimal_places=4, default=1, max_digits=10)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="personalization_events", to="ReelRoots_app.userprofile")),
                ("topic", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="personalization_events", to="ReelRoots_app.topic")),
            ],
        ),
        migrations.CreateModel(
            name="PhoneVerification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code_hash", models.CharField(max_length=256)),
                ("expires_at", models.DateTimeField()),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("max_attempts", models.PositiveSmallIntegerField(default=5)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("last_sent_at", models.DateTimeField(auto_now=True)),
                ("pending_signup", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="phone_verification", to="ReelRoots_app.pendingsignup")),
            ],
        ),
        migrations.AddConstraint(
            model_name="profileinterest",
            constraint=models.UniqueConstraint(fields=("profile", "topic", "source"), name="unique_profile_topic_source"),
        ),
        migrations.AddConstraint(
            model_name="profilepreference",
            constraint=models.UniqueConstraint(fields=("profile", "preference_type", "value"), name="unique_profile_preference"),
        ),
        migrations.AddIndex(
            model_name="pendingsignup",
            index=models.Index(fields=["email", "phone_number", "expires_at"], name="ReelRoots_a_email_084f8b_idx"),
        ),
        migrations.AddIndex(
            model_name="personalizationevent",
            index=models.Index(fields=["profile", "event_type", "occurred_at"], name="ReelRoots_a_profile_30f9bd_idx"),
        ),
        migrations.AddIndex(
            model_name="personalizationevent",
            index=models.Index(fields=["profile", "topic", "occurred_at"], name="ReelRoots_a_profile_544f31_idx"),
        ),
        migrations.RunPython(seed_topics, remove_topics),
    ]
