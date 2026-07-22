import uuid
from django.db import models
from django.utils.text import slugify
from django.utils import timezone


class Archive(models.Model):

    VERIFICATION_STATUS = [
        ("draft", "Draft"),
        ("reviewed", "Reviewed"),
        ("verified", "Verified"),
    ]

    VISIBILITY_CHOICES = [
        ("public", "Public"),
        ("private", "Private"),
        ("restricted", "Restricted"),
    ]

    IMPACT_LEVELS = [
        ("local", "Local"),
        ("national", "National"),
        ("continental", "Continental"),
        ("global", "Global"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Core Info
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)

    event_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    # Location
    country = models.CharField(max_length=150)
    region = models.CharField(
        max_length=150,
        help_text="East Africa, Africa, Worldwide (aggregated allowed)"
    )
    county = models.CharField(
        max_length=150,
        blank=True,
        help_text="Specific to Kenya"
    )
    city = models.CharField(max_length=150, blank=True)

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # Classification
    category = models.CharField(max_length=150)
    era = models.CharField(max_length=150, blank=True)
    impact_level = models.CharField(
        max_length=20,
        choices=IMPACT_LEVELS,
        default="national"
    )

    # Content
    summary = models.TextField(help_text="Short 2–4 sentence overview")
    description = models.TextField()
    full_story = models.TextField()

    # Quote
    quote_text = models.TextField(blank=True)
    quote_author = models.CharField(max_length=255, blank=True)
    quote_source = models.CharField(max_length=255, blank=True)

    # Tags
    tags = models.ManyToManyField("Tag", blank=True)

    # Meta
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS,
        default="draft"
    )

    visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default="public"
    )

    featured = models.BooleanField(default=False)
    view_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-event_date"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Media(models.Model):

    MEDIA_TYPES = [
        ("photo", "Photo"),
        ("video", "Video"),
        ("audio", "Audio"),
        ("document", "Document"),
    ]

    archive = models.ForeignKey(
        Archive,
        on_delete=models.CASCADE,
        related_name="media"
    )

    media_type = models.CharField(max_length=20, choices=MEDIA_TYPES)
    file = models.FileField(upload_to="archives/media/")
    caption = models.CharField(max_length=255, blank=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.media_type} - {self.archive.title}"


class UserProfile(models.Model):
    """Local application profile mapped to a Supabase Auth user."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supabase_user_id = models.UUIDField(unique=True)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=32, unique=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    institution = models.CharField(max_length=255, blank=True)
    onboarding_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    @property
    def phone_verified(self):
        return self.phone_verified_at is not None

    def mark_phone_verified(self):
        self.phone_verified_at = timezone.now()
        self.save(update_fields=["phone_verified_at", "updated_at"])

    def __str__(self):
        return self.name or self.email


class Topic(models.Model):
    """Controlled topic vocabulary used by onboarding and personalization."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    group = models.CharField(max_length=80, default="heritage")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["group", "name"]

    def __str__(self):
        return self.name


class ProfileInterest(models.Model):
    SOURCES = [
        ("explicit", "Explicit selection"),
        ("observed", "Observed behavior"),
    ]

    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="interests")
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="profile_interests")
    source = models.CharField(max_length=20, choices=SOURCES)
    weight = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    event_count = models.PositiveIntegerField(default=0)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["profile", "topic", "source"], name="unique_profile_topic_source")
        ]
        ordering = ["-weight", "topic__name"]


class ProfilePreference(models.Model):
    PREFERENCE_TYPES = [
        ("region", "Region"),
        ("country", "Country"),
        ("language", "Language"),
        ("content_type", "Content type"),
    ]

    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="preferences")
    preference_type = models.CharField(max_length=24, choices=PREFERENCE_TYPES)
    value = models.CharField(max_length=120)
    source = models.CharField(max_length=20, default="explicit")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "preference_type", "value"],
                name="unique_profile_preference",
            )
        ]
        ordering = ["preference_type", "value"]


class PersonalizationEvent(models.Model):
    EVENT_TYPES = [
        ("watch", "Watch"),
        ("completion", "Completion"),
        ("save", "Save"),
        ("like", "Like"),
        ("share", "Share"),
        ("search", "Search"),
    ]

    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="personalization_events")
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True, related_name="personalization_events")
    content_key = models.CharField(max_length=255, blank=True)
    value = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["profile", "event_type", "occurred_at"]),
            models.Index(fields=["profile", "topic", "occurred_at"]),
        ]


class PendingSignup(models.Model):
    """Short-lived staged signup; password is encrypted and never stored in plaintext."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supabase_user_id = models.UUIDField(unique=True)
    email = models.EmailField()
    name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=32)
    institution = models.CharField(max_length=255, blank=True)
    encrypted_password = models.TextField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["email", "phone_number", "expires_at"])]

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at


class PhoneVerification(models.Model):
    pending_signup = models.OneToOneField(PendingSignup, on_delete=models.CASCADE, related_name="phone_verification")
    code_hash = models.CharField(max_length=256)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    verified_at = models.DateTimeField(null=True, blank=True)
    last_sent_at = models.DateTimeField(auto_now=True)

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_locked(self):
        return self.attempts >= self.max_attempts




# class Profile(models.Model):
#     user = models.OneToOneField(User, on_delete=models.CASCADE)
#     institution = models.CharField(max_length=255, blank=True)
