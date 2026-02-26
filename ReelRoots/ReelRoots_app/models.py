import uuid
from django.db import models
from django.utils.text import slugify


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




# class Profile(models.Model):
#     user = models.OneToOneField(User, on_delete=models.CASCADE)
#     institution = models.CharField(max_length=255, blank=True)