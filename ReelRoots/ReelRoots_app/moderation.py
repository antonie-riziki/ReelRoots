"""Contributor submission lifecycle, risk assessment, and moderator actions."""

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from .models import ContributorSubmission, ModerationAction, Reel, Topic, VerificationRequest
from .trust import recalculate_trust, record_trust_signal
from .verification_engine import VerificationEngine


ALLOWED_TRANSITIONS = {
    "draft": {"submitted"},
    "submitted": {"processing", "needs_review"},
    "processing": {"needs_review", "flagged"},
    "needs_review": {"approved", "rejected", "flagged", "archived"},
    "approved": {"published", "rejected", "archived"},
    "published": {"flagged", "archived"},
    "flagged": {"needs_review", "rejected", "archived"},
    "rejected": {"draft", "archived"},
    "archived": set(),
}


def transition_submission(submission, to_status, action, notes="", moderator=None):
    if to_status not in ALLOWED_TRANSITIONS.get(submission.status, set()):
        raise ValueError(f"Cannot move submission from {submission.status} to {to_status}.")
    from_status = submission.status
    submission.status = to_status
    now = timezone.now()
    if to_status == "submitted":
        submission.submitted_at = now
    if to_status == "approved":
        submission.approved_at = now
    if to_status == "published":
        submission.published_at = now
    if notes:
        submission.moderation_notes = notes[:10000]
    submission.save()
    ModerationAction.objects.create(
        submission=submission,
        moderator=moderator,
        from_status=from_status,
        to_status=to_status,
        action=action[:80],
        notes=notes[:10000],
    )
    return submission


def _metadata_text(submission):
    return "\n".join([
        f"Title: {submission.title}",
        f"Description: {submission.description}",
        f"Category: {submission.category}",
        f"Country: {submission.country}",
        f"Region: {submission.region}",
        f"Cultural context: {submission.cultural_context}",
        f"Source notes: {submission.source_notes}",
        f"Transcript: {submission.transcript}",
    ])[:50000]


def create_submission_verification(submission):
    request = VerificationRequest.objects.create(
        profile=submission.profile,
        input_type="text",
        source_url=submission.source_reference,
        input_text=_metadata_text(submission),
        content_title=submission.title,
    )
    submission.verification_request = request
    submission.save(update_fields=["verification_request", "updated_at"])
    return request


def assess_submission_risk(submission, result=None):
    score = Decimal("0.25")
    reasons = []
    if submission.permission_type == "pending":
        score += Decimal("0.3")
        reasons.append("Ownership or permission requires moderator review.")
    if not submission.source_reference and not submission.source_notes:
        score += Decimal("0.2")
        reasons.append("No source or reference was provided.")
    if not submission.transcript:
        score += Decimal("0.05")
        reasons.append("No contributor transcript was provided.")
    if result:
        if result.overall_assessment in {"false", "misleading", "disputed"}:
            score += Decimal("0.35")
            reasons.append(f"Verification result is {result.get_overall_assessment_display().lower()}.")
        elif result.overall_assessment in {"unsupported", "unable_to_verify"}:
            score += Decimal("0.2")
            reasons.append("Verification evidence is insufficient to support the submission's claims.")
        if any(claim.assessment in {"false", "misleading", "disputed"} for claim in result.request.claims.all()):
            score += Decimal("0.15")
            reasons.append("At least one extracted claim needs historical review.")
    score = min(score, Decimal("1"))
    level = "high" if score >= Decimal("0.65") else "medium" if score >= Decimal("0.4") else "low"
    submission.risk_score = score
    submission.risk_level = level
    submission.risk_reasons = reasons
    submission.save(update_fields=["risk_score", "risk_level", "risk_reasons", "updated_at"])
    return score, level, reasons


@transaction.atomic
def submit_submission(submission):
    transition_submission(submission, "submitted", "submitted by contributor")
    recalculate_trust(submission.profile)
    return submission


def process_submission(submission_id):
    submission = ContributorSubmission.objects.select_related("profile").get(id=submission_id)
    try:
        transition_submission(submission, "processing", "processing started")
        request = submission.verification_request or create_submission_verification(submission)
        result = VerificationEngine().process(request.id)
        submission.refresh_from_db()
        submission.processed_at = timezone.now()
        if result:
            submission.ai_summary = result.summary
            assess_submission_risk(submission, result)
        else:
            submission.risk_score = Decimal("0.9")
            submission.risk_level = "high"
            submission.risk_reasons = ["Verification processing did not produce a result."]
            submission.save(update_fields=["processed_at", "risk_score", "risk_level", "risk_reasons", "updated_at"])
        if submission.status == "processing":
            transition_submission(submission, "needs_review", "automated processing completed", "Automatic publication is disabled; moderator review is required.")
        record_trust_signal(submission.profile, "source_quality", result.confidence_score if result else 0, "Verification confidence recorded for this submission.", submission=submission)
        recalculate_trust(submission.profile)
    except Exception as exc:
        submission.refresh_from_db()
        submission.risk_level = "high"
        submission.risk_score = Decimal("0.95")
        submission.risk_reasons = ["Processing failed and requires manual review."]
        submission.save(update_fields=["risk_score", "risk_level", "risk_reasons", "updated_at"])
        if submission.status == "processing":
            transition_submission(submission, "needs_review", "processing failed", str(exc)[:2000])
    return submission


def publish_submission(submission, moderator):
    if submission.status != "approved":
        raise ValueError("Only approved submissions can be published.")
    if submission.reel_id is None:
        verification = submission.verification_request.result if submission.verification_request_id and hasattr(submission.verification_request, "result") else None
        reel = Reel.objects.create(
            creator_profile=submission.profile,
            creator_name=submission.profile.name,
            creator_handle=slugify(submission.profile.name).replace("-", ""),
            original_creator_name=submission.profile.name,
            source_platform="native",
            external_id=str(submission.id),
            source_url=submission.source_reference,
            video_url=submission.media_file.url,
            thumbnail_url=submission.thumbnail_file.url if submission.thumbnail_file else "",
            title=submission.title,
            description=submission.description,
            source_attribution=f"Contributor submission by {submission.profile.name}",
            license_status={"owned": "owned", "licensed": "licensed", "public_domain": "public_domain", "permission": "permitted_embed"}.get(submission.permission_type, "pending_review"),
            content_type="creator",
            heritage_relevance=Decimal("0.75"),
            geographic_relevance=f"{submission.region}, {submission.country}",
            verification_status="verified" if verification and verification.overall_assessment == "supported" else "reviewed",
            confidence_score=verification.confidence_score if verification else Decimal("0.1"),
            quality_score=max(Decimal("0.4"), Decimal("0.9") - submission.risk_score / Decimal("3")),
            context_summary=submission.cultural_context,
            historical_context=submission.cultural_context,
            status="published",
        )
        topic, _ = Topic.objects.get_or_create(slug=slugify(submission.category), defaults={"name": submission.category, "group": "heritage"})
        reel.topics.add(topic)
        submission.reel = reel
        submission.save(update_fields=["reel", "updated_at"])
    transition_submission(submission, "published", "published by moderator", moderator=moderator)
    record_trust_signal(submission.profile, "moderator_decision", Decimal("0.9"), "A moderator approved and published this submission.", submission=submission)
    recalculate_trust(submission.profile)
    return submission
