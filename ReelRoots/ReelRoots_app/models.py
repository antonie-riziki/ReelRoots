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


class Reel(models.Model):
    """Canonical, publishable short-form heritage media item."""

    SOURCE_PLATFORMS = [
        ("native", "ReelRoots"),
        ("pexels", "Pexels"),
        ("wikimedia", "Wikimedia Commons"),
        ("youtube", "YouTube"),
        ("vimeo", "Vimeo"),
        ("archive", "Archive"),
        ("other", "Other"),
    ]
    CONTENT_TYPES = [
        ("native", "Native ReelRoots video"),
        ("creator", "Creator upload"),
        ("licensed", "Licensed content"),
        ("public_domain", "Public-domain footage"),
        ("embed", "Permitted embed"),
        ("curated_external", "Curated external media"),
    ]
    LICENSE_STATUSES = [
        ("owned", "Owned"),
        ("licensed", "Licensed"),
        ("public_domain", "Public domain"),
        ("permitted_embed", "Permitted embed"),
        ("pending_review", "Pending review"),
    ]
    VERIFICATION_STATUSES = [
        ("unreviewed", "Unreviewed"),
        ("reviewed", "Reviewed"),
        ("verified", "Verified"),
        ("disputed", "Disputed"),
    ]
    STATUSES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("hidden", "Hidden"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator_profile = models.ForeignKey(
        UserProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reels",
    )
    creator_name = models.CharField(max_length=150)
    creator_handle = models.CharField(max_length=150, blank=True)
    original_creator_name = models.CharField(max_length=150, blank=True)
    topics = models.ManyToManyField("Topic", blank=True, related_name="reels")
    source_platform = models.CharField(max_length=32, choices=SOURCE_PLATFORMS)
    external_id = models.CharField(max_length=255, null=True, blank=True)
    source_url = models.URLField(blank=True)
    video_url = models.URLField()
    thumbnail_url = models.URLField(blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    publication_date = models.DateField(null=True, blank=True)
    source_attribution = models.CharField(max_length=255, blank=True)
    license_status = models.CharField(max_length=32, choices=LICENSE_STATUSES, default="pending_review")
    content_type = models.CharField(max_length=32, choices=CONTENT_TYPES, default="curated_external")
    heritage_relevance = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    geographic_relevance = models.CharField(max_length=150, blank=True)
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUSES, default="unreviewed")
    confidence_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    quality_score = models.DecimalField(max_digits=5, decimal_places=4, default=0.5)
    context_summary = models.TextField(blank=True)
    key_claims = models.JSONField(default=list, blank=True)
    historical_context = models.TextField(blank=True)
    important_people = models.JSONField(default=list, blank=True)
    important_locations = models.JSONField(default=list, blank=True)
    timeline = models.JSONField(default=list, blank=True)
    external_references = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUSES, default="draft")
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_platform", "external_id"],
                name="unique_reel_external_source",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "heritage_relevance", "created_at"]),
            models.Index(fields=["source_platform", "external_id"]),
        ]
        ordering = ["-created_at"]

    @property
    def content_key(self):
        return str(self.id)

    @property
    def creator_key(self):
        if self.creator_profile_id:
            return f"profile:{self.creator_profile_id}"
        return f"{self.source_platform}:{self.creator_name}"


class ReelLike(models.Model):
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name="likes")
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="reel_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["reel", "profile"], name="unique_reel_like")]


class ReelSave(models.Model):
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name="saves")
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="reel_saves")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["reel", "profile"], name="unique_reel_save")]


class ReelComment(models.Model):
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name="comments")
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="reel_comments")
    body = models.CharField(max_length=500)
    is_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["reel", "created_at"])]


class ReelCreatorFollow(models.Model):
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="followed_creators")
    creator_key = models.CharField(max_length=255)
    creator_name = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["profile", "creator_key"], name="unique_creator_follow")]


class ReelReport(models.Model):
    STATUS_CHOICES = [("open", "Open"), ("reviewed", "Reviewed"), ("dismissed", "Dismissed")]
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name="reports")
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="reel_reports")
    reason = models.CharField(max_length=80)
    details = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["reel", "profile"], name="unique_reel_report")]


class ReelContext(models.Model):
    """Cached, evidence-aware context document generated for a reel."""

    GENERATION_STATUSES = [
        ("pending", "Pending"),
        ("generating", "Generating"),
        ("complete", "Complete"),
        ("failed", "Failed"),
    ]
    VERIFICATION_STATUSES = [
        ("verified", "Verified"),
        ("partially_supported", "Partially supported"),
        ("disputed", "Disputed"),
        ("insufficient_evidence", "Insufficient evidence"),
        ("false_misleading", "False or misleading"),
    ]

    reel = models.OneToOneField(Reel, on_delete=models.CASCADE, related_name="context_document")
    transcript = models.TextField(blank=True)
    transcript_status = models.CharField(max_length=40, default="metadata_fallback")
    summary = models.TextField(blank=True)
    historical_context = models.TextField(blank=True)
    key_facts = models.JSONField(default=list, blank=True)
    related_topic_slugs = models.JSONField(default=list, blank=True)
    external_links = models.JSONField(default=list, blank=True)
    sources = models.ManyToManyField("KnowledgeSource", blank=True, related_name="contexts")
    model_name = models.CharField(max_length=120, blank=True)
    prompt_version = models.CharField(max_length=40, blank=True)
    source_fingerprint = models.CharField(max_length=64, blank=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    verification_status = models.CharField(max_length=32, choices=VERIFICATION_STATUSES, default="insufficient_evidence")
    generation_status = models.CharField(max_length=20, choices=GENERATION_STATUSES, default="pending")
    error_message = models.TextField(blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ContextClaim(models.Model):
    CLAIM_TYPES = [("historical", "Historical"), ("cultural", "Cultural"), ("media", "Media")]
    VERIFICATION_STATUSES = ReelContext.VERIFICATION_STATUSES

    context = models.ForeignKey(ReelContext, on_delete=models.CASCADE, related_name="claims")
    claim_text = models.TextField()
    claim_type = models.CharField(max_length=20, choices=CLAIM_TYPES, default="historical")
    verification_status = models.CharField(max_length=32, choices=VERIFICATION_STATUSES, default="insufficient_evidence")
    confidence_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    evidence_summary = models.TextField(blank=True)
    ordinal = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordinal", "id"]
        indexes = [models.Index(fields=["context", "verification_status"])]


class ContextEntity(models.Model):
    ENTITY_TYPES = [
        ("person", "Person"),
        ("place", "Place"),
        ("date", "Date"),
        ("event", "Event"),
        ("organization", "Organization"),
        ("cultural_group", "Cultural group"),
    ]

    context = models.ForeignKey(ReelContext, on_delete=models.CASCADE, related_name="entities")
    name = models.CharField(max_length=255)
    entity_type = models.CharField(max_length=30, choices=ENTITY_TYPES)
    description = models.TextField(blank=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    ordinal = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["entity_type", "ordinal", "name"]
        constraints = [models.UniqueConstraint(fields=["context", "entity_type", "name"], name="unique_context_entity")]


class ContextTimelineEntry(models.Model):
    context = models.ForeignKey(ReelContext, on_delete=models.CASCADE, related_name="timeline")
    date_label = models.CharField(max_length=120)
    event = models.TextField()
    location = models.CharField(max_length=255, blank=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    ordinal = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordinal", "id"]


class KnowledgeSource(models.Model):
    SOURCE_TYPES = [
        ("original_media", "Original media"),
        ("academic", "Academic publication"),
        ("archive", "Archive"),
        ("museum", "Museum"),
        ("university", "University"),
        ("government", "Government archive"),
        ("library", "Library"),
        ("journalism", "Reputable journalism"),
        ("cultural_institution", "Cultural institution"),
        ("other", "Other"),
    ]

    url = models.URLField(unique=True)
    title = models.CharField(max_length=500)
    publisher = models.CharField(max_length=255, blank=True)
    source_type = models.CharField(max_length=32, choices=SOURCE_TYPES, default="other")
    authority_rank = models.PositiveSmallIntegerField(default=1)
    license_name = models.CharField(max_length=255, blank=True)
    excerpt = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    last_retrieved_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-authority_rank", "publisher", "title"]


class ContextEvidence(models.Model):
    RELATIONSHIPS = [
        ("supports", "Supports"),
        ("contradicts", "Contradicts"),
        ("unclear", "Unclear"),
    ]

    claim = models.ForeignKey(ContextClaim, on_delete=models.CASCADE, related_name="evidence")
    source = models.ForeignKey(KnowledgeSource, on_delete=models.CASCADE, related_name="evidence")
    relationship = models.CharField(max_length=20, choices=RELATIONSHIPS, default="unclear")
    excerpt = models.TextField(blank=True)
    source_locator = models.CharField(max_length=255, blank=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=4, default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["claim", "source"], name="unique_claim_source_evidence")]




# class Profile(models.Model):
#     user = models.OneToOneField(User, on_delete=models.CASCADE)
#     institution = models.CharField(max_length=255, blank=True)
