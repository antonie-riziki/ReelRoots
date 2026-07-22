"""Transparent feed ranking that can later be replaced by learned retrieval."""

from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from .models import Reel


CATEGORY_SLUGS = {
    "history": "history",
    "culture": "culture",
    "heritage": "heritage",
    "oral-history": "oral-history",
    "indigenous-knowledge": "indigenous-knowledge",
    "architecture": "architecture",
    "music": "music",
    "food": "food",
    "art": "art",
}


def _interest_scores(profile):
    if profile is None:
        return {}
    return {
        row["topic__slug"]: Decimal(str(row["score"]))
        for row in profile.interests.values("topic__slug").annotate(score=Sum("weight"))
    }


def _preference_values(profile, kind):
    if profile is None:
        return set()
    return set(profile.preferences.filter(preference_type=kind).values_list("value", flat=True))


def _freshness_score(reel):
    age = timezone.now() - reel.created_at
    return Decimal("1") / (Decimal("1") + Decimal(str(max(age.days, 0))) / Decimal("30"))


def _score(reel, profile, interests):
    score = Decimal(str(reel.quality_score or 0)) * Decimal("2")
    score += Decimal(str(reel.heritage_relevance or 0)) * Decimal("4")
    score += _freshness_score(reel)
    score += Decimal(str(reel.likes_count or 0)) * Decimal("0.15")
    score += Decimal(str(reel.saves_count or 0)) * Decimal("0.35")
    score += Decimal("2") if reel.verification_status == "verified" else Decimal("0")
    for slug in reel.topics.values_list("slug", flat=True):
        score += interests.get(slug, Decimal("0"))
    regions = _preference_values(profile, "region")
    countries = _preference_values(profile, "country")
    if reel.geographic_relevance in regions or reel.geographic_relevance in countries:
        score += Decimal("2")
    return score


def get_ranked_reels(profile=None, feed_type="for-you", limit=30):
    queryset = Reel.objects.filter(status="published", heritage_relevance__gte=Decimal("0.45")).annotate(
        likes_count=Count("likes", distinct=True),
        saves_count=Count("saves", distinct=True),
    ).prefetch_related("topics")

    category_slug = CATEGORY_SLUGS.get(feed_type)
    if category_slug:
        queryset = queryset.filter(topics__slug=category_slug)
    elif feed_type == "following":
        if profile is None:
            return []
        followed = set(profile.followed_creators.values_list("creator_key", flat=True))
        # External creators are matched in Python because creator_key is derived.
        queryset = [reel for reel in queryset if reel.creator_key in followed or reel.creator_profile_id == profile.id]
    elif feed_type == "recent":
        return list(queryset.order_by("-created_at")[:limit])

    reels = list(queryset)
    interests = _interest_scores(profile)
    if feed_type == "trending":
        reels.sort(key=lambda reel: (reel.likes_count + (reel.saves_count * 2), reel.created_at), reverse=True)
    else:
        reels.sort(key=lambda reel: _score(reel, profile, interests), reverse=True)
    return reels[:limit]
