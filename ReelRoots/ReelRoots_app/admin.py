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