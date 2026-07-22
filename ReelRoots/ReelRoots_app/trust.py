"""Dynamic contributor trust calculation with inspectable components."""

from decimal import Decimal

from django.db.models import Avg, Count, Q
from django.utils import timezone

from .models import ContributorSubmission, ContributorTrustProfile, ContributorTrustSignal, UserProfile


def _clamp(value):
    return max(Decimal("0"), min(Decimal("1"), Decimal(str(value))))


def trust_profile(profile):
    trust, _ = ContributorTrustProfile.objects.get_or_create(profile=profile)
    return trust


def record_trust_signal(profile, signal_type, value, explanation, submission=None, weight=1):
    return ContributorTrustSignal.objects.create(
        profile=profile,
        submission=submission,
        signal_type=signal_type,
        value=_clamp(value),
        weight=weight,
        explanation=explanation[:500],
    )


def recalculate_trust(profile):
    trust = trust_profile(profile)
    submissions = ContributorSubmission.objects.filter(profile=profile)
    approved = submissions.filter(status__in={"approved", "published"}).count()
    rejected = submissions.filter(status="rejected").count()
    flagged = submissions.filter(status="flagged").count()
    total_decided = approved + rejected + flagged
    accuracy = Decimal(approved) / Decimal(max(total_decided, 1))
    if not total_decided:
        accuracy = Decimal("0.2")

    quality = submissions.filter(status__in={"approved", "published"}).aggregate(value=Avg("reel__quality_score"))["value"] or Decimal("0.25")
    quality = _clamp(quality)
    source_quality = submissions.filter(verification_request__result__isnull=False).aggregate(
        value=Avg("verification_request__result__confidence_score")
    )["value"] or Decimal("0.2")
    source_quality = _clamp(source_quality)
    open_reports = submissions.filter(reports__status="open").distinct().count()
    report_score = _clamp(Decimal("1") - (Decimal(open_reports) * Decimal("0.15")))
    account_age = _clamp((timezone.now() - profile.created_at).days / 365)
    engagement = _clamp(Decimal(str(profile.reels.aggregate(value=Avg("quality_score"))["value"] or 0.2)))
    moderator_signals = ContributorTrustSignal.objects.filter(profile=profile, signal_type="moderator_decision").aggregate(value=Avg("value"))["value"]
    moderator_score = _clamp(moderator_signals if moderator_signals is not None else Decimal("0.3"))

    components = {
        "accuracy_history": float(accuracy),
        "content_quality": float(quality),
        "source_quality": float(source_quality),
        "community_reports": float(report_score),
        "account_age": float(account_age),
        "moderator_decisions": float(moderator_score),
        "engagement_patterns": float(engagement),
    }
    score = _clamp(
        Decimal("0.30") * accuracy
        + Decimal("0.18") * quality
        + Decimal("0.20") * source_quality
        + Decimal("0.12") * report_score
        + Decimal("0.08") * account_age
        + Decimal("0.08") * moderator_score
        + Decimal("0.04") * engagement
    )
    if score >= Decimal("0.8") and approved >= 5 and source_quality >= Decimal("0.7"):
        level = "heritage_partner"
    elif score >= Decimal("0.6") and approved >= 2:
        level = "verified_contributor"
    elif submissions.exists() or score >= Decimal("0.35"):
        level = "contributor"
    else:
        level = "viewer"
    explanation = [
        f"Accuracy history: {approved} approved/published, {rejected} rejected, {flagged} flagged.",
        f"Source quality currently contributes {round(float(source_quality) * 100)}% based on completed verification results.",
        f"Community report factor is {round(float(report_score) * 100)}% from {open_reports} open submission report(s).",
        "Trust is recalculated as new submissions, reports, and moderator decisions arrive; it is not a permanent label.",
    ]
    trust.level = level
    trust.score = score
    trust.confidence = _clamp(Decimal("0.35") + Decimal("0.1") * min(total_decided, 5))
    trust.component_scores = components
    trust.explanation = explanation
    trust.calculated_at = timezone.now()
    trust.save()
    return trust
