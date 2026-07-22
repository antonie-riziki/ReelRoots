from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import PersonalizationEvent, ProfileInterest, ProfilePreference, Topic


EXPLICIT_WEIGHT = Decimal("5.0")
EVENT_WEIGHTS = {
    "watch": Decimal("0.75"),
    "completion": Decimal("4.0"),
    "save": Decimal("3.0"),
    "like": Decimal("2.0"),
    "share": Decimal("4.0"),
    "search": Decimal("1.5"),
}


def _topic(slug):
    return Topic.objects.filter(slug=slug, is_active=True).first()


@transaction.atomic
def set_explicit_interests(profile, topic_slugs):
    selected = set(topic_slugs)
    topics = {topic.slug: topic for topic in Topic.objects.filter(slug__in=selected, is_active=True)}
    ProfileInterest.objects.filter(profile=profile, source="explicit").exclude(topic__slug__in=selected).delete()
    for slug, topic in topics.items():
        ProfileInterest.objects.update_or_create(
            profile=profile,
            topic=topic,
            source="explicit",
            defaults={"weight": EXPLICIT_WEIGHT, "last_seen_at": timezone.now()},
        )


@transaction.atomic
def set_preferences(profile, *, regions, countries, languages, content_types):
    values = {
        "region": regions,
        "country": countries,
        "language": languages,
        "content_type": content_types,
    }
    for preference_type, selected in values.items():
        selected = set(selected)
        ProfilePreference.objects.filter(profile=profile, preference_type=preference_type).exclude(value__in=selected).delete()
        for value in selected:
            ProfilePreference.objects.get_or_create(
                profile=profile,
                preference_type=preference_type,
                value=value,
                defaults={"source": "explicit"},
            )


@transaction.atomic
def record_engagement(profile, *, event_type, topic_slug=None, content_key="", value=1, metadata=None):
    if event_type not in EVENT_WEIGHTS:
        raise ValueError("Unsupported personalization event.")
    topic = _topic(topic_slug) if topic_slug else None
    event_value = Decimal(str(value))
    if event_type == "completion":
        event_value = max(Decimal("0"), min(Decimal("1"), event_value))
    event = PersonalizationEvent.objects.create(
        profile=profile,
        event_type=event_type,
        topic=topic,
        content_key=content_key,
        value=event_value,
        metadata=metadata or {},
    )
    if topic:
        increment = EVENT_WEIGHTS[event_type] * (event_value if event_type == "completion" else Decimal("1"))
        signal, _ = ProfileInterest.objects.get_or_create(
            profile=profile,
            topic=topic,
            source="observed",
            defaults={"weight": Decimal("0")},
        )
        signal.weight += increment
        signal.event_count += 1
        signal.last_seen_at = timezone.now()
        signal.save(update_fields=["weight", "event_count", "last_seen_at"])
    return event


def ranked_interests(profile, limit=8):
    signals = ProfileInterest.objects.filter(profile=profile).select_related("topic")
    ranked = {}
    for signal in signals:
        ranked[signal.topic.slug] = ranked.get(signal.topic.slug, Decimal("0")) + signal.weight
    topics = {topic.slug: topic for topic in Topic.objects.filter(slug__in=ranked.keys())}
    return [
        {"slug": slug, "name": topics[slug].name, "score": float(score)}
        for slug, score in sorted(ranked.items(), key=lambda item: item[1], reverse=True)[:limit]
        if slug in topics
    ]


def profile_preferences(profile):
    grouped = {}
    for preference in profile.preferences.all():
        grouped.setdefault(preference.preference_type, []).append(preference.value)
    return grouped
