"""Contributor upload flow and owner-scoped reporting."""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from .decorators import api_login_required, reelroots_login_required
from .models import ContributorSubmission, ContributorTrustProfile, SubmissionReport
from .moderation import submit_submission
from .moderation_jobs import enqueue_submission
from .trust import recalculate_trust, trust_profile


MAX_MEDIA_BYTES = 50 * 1024 * 1024
ALLOWED_MEDIA_TYPES = {"video/mp4", "video/webm", "video/quicktime", "video/ogg"}
ALLOWED_THUMBNAIL_TYPES = {"image/jpeg", "image/png", "image/webp"}


@reelroots_login_required
def contributor_upload(request):
    trust = trust_profile(request.reelroots_profile)
    if request.method == "POST":
        required = ["title", "description", "category", "country", "region", "cultural_context", "permission_type"]
        if any(not str(request.POST.get(field, "")).strip() for field in required):
            return render(request, "contributor_upload.html", {"trust": trust, "error": "Complete the required metadata fields before submitting."}, status=400)
        media_file = request.FILES.get("media_file")
        if not media_file:
            return render(request, "contributor_upload.html", {"trust": trust, "error": "Add the content file before submitting."}, status=400)
        if media_file.size > MAX_MEDIA_BYTES:
            return render(request, "contributor_upload.html", {"trust": trust, "error": "Content files must be 50 MB or smaller."}, status=400)
        if media_file.content_type not in ALLOWED_MEDIA_TYPES:
            return render(request, "contributor_upload.html", {"trust": trust, "error": "Use an MP4, WebM, QuickTime, or Ogg video file."}, status=400)
        thumbnail_file = request.FILES.get("thumbnail_file")
        if thumbnail_file and (thumbnail_file.size > 5 * 1024 * 1024 or thumbnail_file.content_type not in ALLOWED_THUMBNAIL_TYPES):
            return render(request, "contributor_upload.html", {"trust": trust, "error": "Thumbnails must be JPG, PNG, or WebP images up to 5 MB."}, status=400)
        submission = ContributorSubmission.objects.create(
            profile=request.reelroots_profile,
            title=str(request.POST.get("title"))[:255],
            description=str(request.POST.get("description"))[:10000],
            category=str(request.POST.get("category"))[:120],
            country=str(request.POST.get("country"))[:150],
            region=str(request.POST.get("region"))[:150],
            cultural_context=str(request.POST.get("cultural_context"))[:15000],
            source_reference=str(request.POST.get("source_reference", "")).strip()[:2000],
            source_notes=str(request.POST.get("source_notes", ""))[:10000],
            permission_type=str(request.POST.get("permission_type"))[:20],
            permission_details=str(request.POST.get("permission_details", ""))[:5000],
            transcript=str(request.POST.get("transcript", ""))[:50000],
            media_file=media_file,
            thumbnail_file=thumbnail_file,
        )
        if request.POST.get("save_draft"):
            return render(request, "contributor_upload.html", {"trust": recalculate_trust(request.reelroots_profile), "saved": "Draft saved. Submit it when the metadata is ready."})
        submit_submission(submission)
        enqueue_submission(submission.id)
        return render(request, "contributor_upload.html", {"trust": recalculate_trust(request.reelroots_profile), "submitted": "Submitted for verification and moderator review. It will not publish automatically."})
    return render(request, "contributor_upload.html", {"trust": trust})


@require_POST
@api_login_required
def report_submission(request, submission_id):
    submission = ContributorSubmission.objects.filter(id=submission_id).first()
    if submission is None:
        return JsonResponse({"error": "Content was not found."}, status=404)
    if submission.profile_id == request.reelroots_profile.id:
        return JsonResponse({"error": "You cannot report your own submission."}, status=400)
    reason = str(request.POST.get("reason", "Other"))[:100]
    details = str(request.POST.get("details", ""))[:1000]
    report, created = SubmissionReport.objects.get_or_create(
        submission=submission,
        profile=request.reelroots_profile,
        defaults={"reason": reason, "details": details},
    )
    return JsonResponse({"status": "open", "created": created, "report_id": report.id}, status=201 if created else 200)
