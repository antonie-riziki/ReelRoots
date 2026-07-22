"""Moderator-only dashboard and workflow actions."""

import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from .decorators import get_session_profile
from .models import ContributorSubmission, ReelReport, SubmissionReport
from .moderation import publish_submission, transition_submission
from .trust import recalculate_trust


def _moderator(view):
    def wrapped(request, *args, **kwargs):
        profile = get_session_profile(request)
        if profile is None or not profile.is_moderator:
            return JsonResponse({"error": "Moderator access required."}, status=403) if request.path.startswith("/api/") else render(request, "moderation_forbidden.html", status=403)
        request.reelroots_profile = profile
        return view(request, *args, **kwargs)
    wrapped.__name__ = getattr(view, "__name__", "moderator_view")
    return wrapped


@_moderator
@require_GET
def moderation_dashboard(request):
    status = request.GET.get("status", "needs_review")
    valid_statuses = {item[0] for item in ContributorSubmission.STATUSES}
    if status not in valid_statuses and status != "all":
        status = "needs_review"
    submissions = ContributorSubmission.objects.select_related("profile", "verification_request", "reel").prefetch_related("reports", "moderation_history")
    if status != "all":
        submissions = submissions.filter(status=status)
    submissions = list(submissions[:100])
    for submission in submissions:
        try:
            submission.verification_result = submission.verification_request.result if submission.verification_request_id else None
        except Exception:
            submission.verification_result = None
    return render(request, "moderation_dashboard.html", {
        "submissions": submissions,
        "selected_status": status,
        "statuses": ContributorSubmission.STATUSES,
        "submission_reports": SubmissionReport.objects.filter(status="open").select_related("submission", "profile")[:50],
        "reel_reports": ReelReport.objects.filter(status="open").select_related("reel", "profile")[:50],
    })


@_moderator
@require_POST
def moderation_action(request, submission_id):
    submission = get_object_or_404(ContributorSubmission, id=submission_id)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        data = request.POST
    action = str(data.get("action", "")).strip().lower()
    notes = str(data.get("notes", ""))[:10000]
    try:
        if action == "publish":
            submission = publish_submission(submission, request.reelroots_profile)
        else:
            destinations = {"approve": "approved", "reject": "rejected", "flag": "flagged", "archive": "archived", "review": "needs_review"}
            destination = destinations.get(action)
            if not destination:
                return JsonResponse({"error": "Unsupported moderation action."}, status=400)
            submission = transition_submission(submission, destination, f"moderator {action}", notes, request.reelroots_profile)
            if action in {"approve", "reject", "flag"}:
                recalculate_trust(submission.profile)
        return JsonResponse({"status": submission.status, "status_label": submission.get_status_display(), "id": str(submission.id)})
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
