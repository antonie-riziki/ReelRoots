"""Verification page and owner-scoped request/result APIs."""

from datetime import timedelta

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.db import DatabaseError
from django.views.decorators.http import require_GET, require_POST

from .decorators import api_login_required, reelroots_login_required
from .models import VerificationRequest, VerificationResult
from .verification_jobs import enqueue_verification
import logging


MAX_VERIFICATION_REQUESTS_PER_HOUR = 10
logger = logging.getLogger(__name__)


@reelroots_login_required
def verification_page(request):
    return render(request, "verification.html", {"profile": request.reelroots_profile})


def _result_payload(verification_request):
    try:
        result = verification_request.result
    except VerificationResult.DoesNotExist:
        return None
    claims = []
    sources = {}
    for claim in verification_request.claims.prefetch_related("evidence__source").all():
        evidence = []
        for item in claim.evidence.all():
            source = item.source
            sources[source.url] = source
            evidence.append({
                "title": source.title,
                "publisher": source.publisher,
                "url": source.url,
                "relationship": item.relationship,
                "relationship_label": dict(item.RELATIONSHIPS).get(item.relationship, item.relationship),
                "excerpt": item.excerpt,
                "comparison_note": item.comparison_note,
                "relevance": float(item.relevance_score),
                "quality": float(item.quality_score),
            })
        claims.append({
            "id": str(claim.id),
            "text": claim.claim_text,
            "type": claim.claim_type,
            "assessment": claim.assessment,
            "assessment_label": dict(claim.ASSESSMENTS).get(claim.assessment, claim.assessment),
            "confidence": float(claim.confidence_score),
            "reasoning": claim.reasoning,
            "entities": claim.entities,
            "topics": claim.topic_slugs,
            "evidence": evidence,
        })
    return {
        "overall_assessment": result.overall_assessment,
        "overall_label": dict(result.ASSESSMENTS).get(result.overall_assessment, result.overall_assessment),
        "confidence": float(result.confidence_score),
        "summary": result.summary,
        "historical_context": result.historical_context,
        "explanation": result.explanation,
        "recommendations": result.recommendations,
        "entities": result.entities,
        "topics": result.topic_slugs,
        "model": result.model_name,
        "prompt_version": result.prompt_version,
        "generated_at": result.generated_at.isoformat() if result.generated_at else None,
        "claims": claims,
        "sources": [
            {"title": source.title, "publisher": source.publisher, "url": source.url, "type": source.source_type}
            for source in sorted(sources.values(), key=lambda item: (-item.authority_rank, item.title))
        ],
    }


def _request_payload(verification_request, include_result=True):
    payload = {
        "id": str(verification_request.id),
        "input_type": verification_request.input_type,
        "status": verification_request.status,
        "status_label": dict(VerificationRequest.STATUS_CHOICES).get(verification_request.status, verification_request.status),
        "progress": verification_request.progress,
        "status_message": verification_request.status_message,
        "created_at": verification_request.created_at.isoformat(),
        "error": verification_request.error_message if verification_request.status == "failed" else "",
    }
    if include_result and verification_request.status == "complete":
        payload["result"] = _result_payload(verification_request)
    return payload


@require_POST
@api_login_required
def create_verification_request(request):
    window_start = timezone.now() - timedelta(hours=1)
    if VerificationRequest.objects.filter(profile=request.reelroots_profile, created_at__gte=window_start).count() >= MAX_VERIFICATION_REQUESTS_PER_HOUR:
        return JsonResponse({"error": "Verification is limited to 10 submissions per hour. Please try again later."}, status=429)
    input_type = str(request.POST.get("input_type", "text")).strip().lower()
    allowed = {item[0] for item in VerificationRequest.INPUT_TYPES}
    if input_type not in allowed:
        return JsonResponse({"error": "Choose a supported content type."}, status=400)
    source_url = str(request.POST.get("source_url", "")).strip()[:2000]
    input_text = str(request.POST.get("input_text", ""))
    if len(input_text) > 50000:
        return JsonResponse({"error": "Text submissions must be 50,000 characters or fewer."}, status=400)
    source_file = request.FILES.get("source_file")
    if not source_url and not input_text.strip() and not source_file:
        return JsonResponse({"error": "Submit a URL, file, or text to begin verification."}, status=400)
    if source_file and source_file.size > 8 * 1024 * 1024:
        return JsonResponse({"error": "Uploaded files must be smaller than 8 MB."}, status=400)
    try:
        verification_request = VerificationRequest.objects.create(
            profile=request.reelroots_profile,
            input_type=input_type,
            source_url=source_url,
            source_file=source_file,
            input_text=input_text,
            content_title=str(request.POST.get("content_title", ""))[:500],
        )
    except DatabaseError:
        logger.exception("Verification request could not be stored")
        return JsonResponse({"error": "We could not save this verification request. Please try again."}, status=503)
    enqueue_verification(verification_request.id)
    return JsonResponse(_request_payload(verification_request, include_result=False), status=202)


@require_GET
@api_login_required
def verification_status(request, request_id):
    verification_request = get_object_or_404(VerificationRequest, id=request_id, profile=request.reelroots_profile)
    return JsonResponse(_request_payload(verification_request))


@require_GET
@api_login_required
def verification_result(request, request_id):
    verification_request = get_object_or_404(VerificationRequest, id=request_id, profile=request.reelroots_profile)
    if verification_request.status != "complete":
        return JsonResponse(_request_payload(verification_request, include_result=False), status=409)
    return JsonResponse(_request_payload(verification_request))
