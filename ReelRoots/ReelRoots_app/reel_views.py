import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .decorators import api_login_required
from .context_engine import ContextEngine, serialize_context
from .models import Reel, ReelComment, ReelCreatorFollow, ReelLike, ReelReport, ReelSave
from .personalization import record_engagement


def _payload(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}


def _reel_counts(reel, profile):
    return {
        "likes": reel.likes.count(),
        "saves": reel.saves.count(),
        "comments": reel.comments.filter(is_hidden=False).count(),
        "liked": ReelLike.objects.filter(reel=reel, profile=profile).exists(),
        "saved": ReelSave.objects.filter(reel=reel, profile=profile).exists(),
        "followed": ReelCreatorFollow.objects.filter(profile=profile, creator_key=reel.creator_key).exists(),
    }


@require_POST
@api_login_required
def reel_interaction(request, reel_id):
    reel = get_object_or_404(Reel, id=reel_id, status="published")
    profile = request.reelroots_profile
    data = _payload(request)
    action = str(data.get("action", "")).strip().lower()

    if action == "like":
        reaction, created = ReelLike.objects.get_or_create(reel=reel, profile=profile)
        if not created:
            reaction.delete()
        else:
            record_engagement(profile, event_type="like", content_key=reel.content_key)
    elif action == "save":
        bookmark, created = ReelSave.objects.get_or_create(reel=reel, profile=profile)
        if not created:
            bookmark.delete()
        else:
            record_engagement(profile, event_type="save", content_key=reel.content_key)
    elif action == "follow":
        follow, created = ReelCreatorFollow.objects.get_or_create(
            profile=profile,
            creator_key=reel.creator_key,
            defaults={"creator_name": reel.creator_name},
        )
        if not created:
            follow.delete()
    elif action == "share":
        record_engagement(profile, event_type="share", content_key=reel.content_key)
        return JsonResponse({"status": "recorded", "share_url": request.build_absolute_uri(reverse("reels")) + f"?reel={reel.id}"})
    elif action == "watch":
        record_engagement(profile, event_type="watch", content_key=reel.content_key, value=data.get("value", 1))
        Reel.objects.filter(id=reel.id).update(view_count=reel.view_count + 1)
    elif action == "completion":
        record_engagement(profile, event_type="completion", content_key=reel.content_key, value=data.get("value", 1))
    elif action == "report":
        reason = str(data.get("reason", "Other"))[:80]
        details = str(data.get("details", ""))[:500]
        ReelReport.objects.get_or_create(reel=reel, profile=profile, defaults={"reason": reason, "details": details})
    else:
        return JsonResponse({"error": "Unsupported reel action."}, status=400)

    return JsonResponse({"status": "ok", "counts": _reel_counts(reel, profile)})


@require_http_methods(["GET", "POST"])
@api_login_required
def reel_comments(request, reel_id):
    reel = get_object_or_404(Reel, id=reel_id, status="published")
    if request.method == "POST":
        body = str(_payload(request).get("body", "")).strip()
        if not body or len(body) > 500:
            return JsonResponse({"error": "Comments must be between 1 and 500 characters."}, status=400)
        comment = ReelComment.objects.create(reel=reel, profile=request.reelroots_profile, body=body)
        return JsonResponse({
            "comment": {
                "id": comment.id,
                "author": comment.profile.name,
                "body": comment.body,
                "created_at": comment.created_at.isoformat(),
            },
        }, status=201)

    comments = reel.comments.filter(is_hidden=False).select_related("profile")[:50]
    return JsonResponse({
        "comments": [
            {"id": comment.id, "author": comment.profile.name, "body": comment.body, "created_at": comment.created_at.isoformat()}
            for comment in comments
        ],
    })


@require_GET
def reel_context(request, reel_id):
    """Return cached or newly generated evidence-aware context for a public reel."""
    reel = get_object_or_404(Reel, id=reel_id, status="published")
    context = ContextEngine().get_or_generate(reel)
    return JsonResponse(serialize_context(context))
