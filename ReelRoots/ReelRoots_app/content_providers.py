"""Provider adapters and relevance classification for permitted media sources."""

from dataclasses import dataclass
from decimal import Decimal
import html
import os
import re
from urllib.parse import quote

import requests
from django.db import transaction

from .models import Reel, Topic


HERITAGE_TOPIC_TERMS = {
    "history": {"history", "historical", "archive", "documentary", "independence", "colonial"},
    "culture": {"culture", "cultural", "tradition", "traditional", "ceremony", "community"},
    "heritage": {"heritage", "museum", "artifact", "preservation", "ancestral"},
    "oral-history": {"oral", "storytelling", "story", "narrative", "elders"},
    "indigenous-knowledge": {"indigenous", "native", "maasai", "knowledge", "craft"},
    "architecture": {"architecture", "building", "monument", "fort", "mosque", "village"},
    "music": {"music", "song", "dance", "drum", "performance"},
    "food": {"food", "cooking", "recipe", "cuisine", "market"},
    "art": {"art", "artist", "painting", "textile", "sculpture"},
    "historical-figures": {"leader", "president", "activist", "figure", "ancestor"},
    "historical-events": {"event", "war", "revolution", "celebration", "independence"},
}


@dataclass(frozen=True)
class ExternalContentItem:
    external_id: str
    source_platform: str
    source_url: str
    video_url: str
    thumbnail_url: str
    creator_name: str
    original_creator_name: str
    title: str
    description: str
    duration_seconds: int
    source_attribution: str
    license_status: str
    content_type: str
    heritage_relevance: Decimal
    geographic_relevance: str
    topic_slugs: tuple
    context_summary: str
    external_references: tuple


def classify_heritage_relevance(title, description=""):
    text = f"{title} {description}".lower()
    matched = []
    for topic_slug, terms in HERITAGE_TOPIC_TERMS.items():
        if any(term in text for term in terms):
            matched.append(topic_slug)
    score = min(Decimal("1.0"), Decimal("0.35") + Decimal("0.12") * len(matched)) if matched else Decimal("0")
    return score, tuple(matched)


class WikimediaCommonsVideoProvider:
    """Discover open video files through the official Wikimedia Commons API."""

    platform = "wikimedia"
    queries = {
        "for-you": "African heritage filetype:video",
        "trending": "African culture filetype:video",
        "recent": "African preservation filetype:video",
        "history": "African history filetype:video",
        "culture": "African culture filetype:video",
        "heritage": "African heritage filetype:video",
        "oral-history": "African storytelling filetype:video",
    }

    def __init__(self):
        self.user_agent = os.getenv(
            "REELROOTS_HTTP_USER_AGENT",
            "ReelRoots/0.1 (cultural heritage research platform)",
        )

    def fetch(self, feed_type="for-you", page=1, per_page=18):
        query = self.queries.get(feed_type, self.queries["for-you"])
        response = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            headers={"User-Agent": self.user_agent},
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": query,
                "gsrnamespace": 6,
                "gsrlimit": per_page,
                "gsroffset": max(page - 1, 0) * per_page,
                "prop": "imageinfo",
                "iiprop": "url|mime|size|duration|extmetadata",
                "iiurlwidth": 720,
                "format": "json",
                "formatversion": 2,
            },
            timeout=10,
        )
        response.raise_for_status()
        items = []
        pages = response.json().get("query", {}).get("pages", [])
        for page_data in pages:
            info = (page_data.get("imageinfo") or [{}])[0]
            if not str(info.get("mime", "")).startswith("video/") or not info.get("url"):
                continue
            metadata = info.get("extmetadata") or {}
            title = str(page_data.get("title", "")).removeprefix("File:") or "Wikimedia Commons video"
            description = _metadata_value(metadata, "ImageDescription") or title
            creator = _metadata_value(metadata, "Artist") or _metadata_value(metadata, "Credit") or "Wikimedia Commons contributor"
            usage_terms = _metadata_value(metadata, "LicenseShortName") or _metadata_value(metadata, "UsageTerms")
            license_status = "public_domain" if "public domain" in usage_terms.lower() else "licensed"
            source_url = f"https://commons.wikimedia.org/wiki/{quote(page_data.get('title', ''), safe='') }"
            context_summary = (
                "This is an open-licensed visual artifact from Wikimedia Commons. "
                "The media itself is not historical evidence; factual context requires supporting sources."
            )
            relevance, topic_slugs = classify_heritage_relevance(title, description)
            if relevance < Decimal("0.45"):
                continue
            items.append(ExternalContentItem(
                external_id=str(page_data.get("pageid")),
                source_platform=self.platform,
                source_url=source_url,
                video_url=info["url"],
                thumbnail_url=info.get("thumburl") or (info.get("thumburls") or {}).get("2") or "",
                creator_name=creator,
                original_creator_name=creator,
                title=title,
                description=description,
                duration_seconds=_duration_seconds(info.get("duration") or _metadata_value(metadata, "Duration")),
                source_attribution=f"Video by {creator} via Wikimedia Commons · {usage_terms or 'license shown on source page'}",
                license_status=license_status,
                content_type="curated_external",
                heritage_relevance=relevance,
                geographic_relevance="Africa",
                topic_slugs=topic_slugs,
                context_summary=context_summary,
                external_references=(
                    ("Wikimedia Commons source", source_url),
                    ("Wikimedia reuse guidance", "https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia"),
                ),
            ))
        return items


def _metadata_value(metadata, key):
    value = metadata.get(key) or {}
    raw = value.get("value", "") if isinstance(value, dict) else value
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(raw)))).strip()


def _duration_seconds(value):
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip()
    if not text:
        return 0
    parts = text.split(":")
    try:
        total = 0
        for part in parts:
            total = total * 60 + int(float(part))
        return total
    except ValueError:
        return 0


@transaction.atomic
def ingest_external_items(items):
    """Normalize permitted provider items into the canonical Reel table."""

    topic_map = {topic.slug: topic for topic in Topic.objects.filter(is_active=True)}
    reels = []
    for item in items:
        reel, _ = Reel.objects.update_or_create(
            source_platform=item.source_platform,
            external_id=item.external_id,
            defaults={
                "creator_name": item.creator_name,
                "original_creator_name": item.original_creator_name,
                "source_url": item.source_url,
                "video_url": item.video_url,
                "thumbnail_url": item.thumbnail_url,
                "title": item.title,
                "description": item.description,
                "duration_seconds": item.duration_seconds,
                "source_attribution": item.source_attribution,
                "license_status": item.license_status,
                "content_type": item.content_type,
                "heritage_relevance": item.heritage_relevance,
                "geographic_relevance": item.geographic_relevance,
                "verification_status": "unreviewed",
                "confidence_score": Decimal("0.2"),
                "quality_score": Decimal("0.65"),
                "context_summary": item.context_summary,
                "external_references": [{"label": label, "url": url} for label, url in item.external_references],
                "status": "published",
            },
        )
        reel.topics.set([topic_map[slug] for slug in item.topic_slugs if slug in topic_map])
        reels.append(reel)
    return reels


def seed_provider_feed(feed_type="for-you"):
    return ingest_external_items(WikimediaCommonsVideoProvider().fetch(feed_type=feed_type))
