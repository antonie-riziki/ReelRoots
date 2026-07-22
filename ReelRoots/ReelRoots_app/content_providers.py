"""Provider adapters and relevance classification for permitted media sources."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import os

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


class PexelsVideoProvider:
    """Uses the official Pexels API; it never scrapes third-party platforms."""

    platform = "pexels"
    queries = {
        "for-you": "African heritage history culture documentary",
        "trending": "African heritage culture history",
        "recent": "African cultural preservation archive",
        "history": "African historical documentary archive",
        "culture": "African traditional culture ceremony",
        "heritage": "African heritage museum tradition",
        "oral-history": "African storytelling oral history",
    }

    def __init__(self):
        self.api_key = os.getenv("PEXEL_API_KEY", "").strip()

    def fetch(self, feed_type="for-you", page=1, per_page=18):
        if not self.api_key:
            return []
        query = self.queries.get(feed_type, self.queries["for-you"])
        response = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": self.api_key},
            params={"query": query, "per_page": per_page, "page": page},
            timeout=10,
        )
        response.raise_for_status()
        items = []
        for video in response.json().get("videos", []):
            files = [item for item in video.get("video_files", []) if item.get("link")]
            if not files:
                continue
            file = sorted(files, key=lambda item: (item.get("width") or 0), reverse=True)[0]
            title = f"{query.title()} — visual reference"
            description = "A curated visual reference discovered through the official Pexels API."
            relevance, topic_slugs = classify_heritage_relevance(title, description)
            if relevance < Decimal("0.45"):
                continue
            creator = (video.get("user") or {}).get("name") or "Pexels creator"
            source_url = video.get("url") or "https://www.pexels.com/videos/"
            items.append(ExternalContentItem(
                external_id=str(video.get("id")),
                source_platform=self.platform,
                source_url=source_url,
                video_url=file["link"],
                thumbnail_url=video.get("image") or "",
                creator_name=creator,
                original_creator_name=creator,
                title=title,
                description=description,
                duration_seconds=int(video.get("duration") or 0),
                source_attribution=f"Video by {creator} via Pexels",
                license_status="licensed",
                content_type="curated_external",
                heritage_relevance=relevance,
                geographic_relevance="Africa",
                topic_slugs=topic_slugs,
                context_summary="This is curated visual media related to cultural heritage. The footage is a visual reference and should not be treated as historical evidence without supporting sources.",
                external_references=(("Pexels source", source_url),),
            ))
        return items


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
    return ingest_external_items(PexelsVideoProvider().fetch(feed_type=feed_type))
