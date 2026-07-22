from django.contrib import admin
from .models import *


class MediaInline(admin.TabularInline):
    model = Media
    extra = 1
    fields = ("media_type", "file", "caption", "uploaded_at")
    readonly_fields = ("uploaded_at",)


@admin.register(Archive)
class ArchiveAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "event_date",
        "country",
        "region",
        "category",
        "impact_level",
        "verification_status",
        "featured",
        "visibility",
    )

    list_filter = (
        "event_date",
        "country",
        "region",
        "category",
        "impact_level",
        "verification_status",
        "visibility",
        "featured",
    )

    search_fields = (
        "title",
        "summary",
        "description",
        "full_story",
        "county",
        "city",
        "country",
    )

    prepopulated_fields = {"slug": ("title",)}

    filter_horizontal = ("tags",)

    inlines = [MediaInline]

    ordering = ("-event_date",)

    readonly_fields = ("created_at", "updated_at", "view_count")

    fieldsets = (
        ("Core Information", {
            "fields": ("title", "slug", "event_date", "end_date")
        }),
        ("Location", {
            "fields": (
                "country",
                "region",
                "county",
                "city",
                "latitude",
                "longitude",
            )
        }),
        ("Classification", {
            "fields": ("category", "era", "impact_level", "tags")
        }),
        ("Content", {
            "fields": (
                "summary",
                "description",
                "full_story",
            )
        }),
        ("Quote", {
            "fields": (
                "quote_text",
                "quote_author",
                "quote_source",
            )
        }),
        ("Status & Visibility", {
            "fields": (
                "verification_status",
                "visibility",
                "featured",
                "view_count",
            )
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
        }),
    )


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone_verified", "onboarding_completed", "is_moderator", "created_at")
    list_filter = ("is_moderator", "onboarding_completed", "phone_verified_at")
    search_fields = ("name", "email", "phone_number", "institution")
    readonly_fields = ("supabase_user_id", "created_at", "updated_at")


@admin.register(ContributorSubmission)
class ContributorSubmissionAdmin(admin.ModelAdmin):
    list_display = ("title", "profile", "status", "risk_level", "risk_score", "created_at", "published_at")
    list_filter = ("status", "risk_level", "permission_type", "category")
    search_fields = ("title", "description", "country", "region", "profile__name", "profile__email")
    readonly_fields = ("submitted_at", "processed_at", "approved_at", "published_at", "created_at", "updated_at")


@admin.register(ContributorTrustProfile)
class ContributorTrustProfileAdmin(admin.ModelAdmin):
    list_display = ("profile", "level", "score", "confidence", "calculated_at")
    list_filter = ("level",)
    search_fields = ("profile__name", "profile__email")
    readonly_fields = ("score", "confidence", "component_scores", "explanation", "calculated_at", "updated_at")


@admin.register(ContributorTrustSignal)
class ContributorTrustSignalAdmin(admin.ModelAdmin):
    list_display = ("profile", "signal_type", "value", "weight", "created_at")
    list_filter = ("signal_type",)
    search_fields = ("profile__name", "profile__email", "explanation")
    readonly_fields = ("created_at",)


@admin.register(ModerationAction)
class ModerationActionAdmin(admin.ModelAdmin):
    list_display = ("submission", "from_status", "to_status", "action", "moderator", "created_at")
    list_filter = ("to_status", "action")
    search_fields = ("submission__title", "moderator__name", "notes")
    readonly_fields = ("created_at",)


@admin.register(SubmissionReport)
class SubmissionReportAdmin(admin.ModelAdmin):
    list_display = ("submission", "profile", "reason", "status", "reviewer", "created_at")
    list_filter = ("status", "reason")
    search_fields = ("submission__title", "profile__name", "profile__email", "details")
    readonly_fields = ("created_at",)
