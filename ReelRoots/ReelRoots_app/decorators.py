from functools import wraps

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect

from .models import UserProfile


def get_session_profile(request):
    profile_id = request.session.get("profile_id")
    supabase_user_id = request.session.get("supabase_user_id")
    if not profile_id or not supabase_user_id:
        return None
    try:
        return UserProfile.objects.get(id=profile_id, supabase_user_id=supabase_user_id)
    except UserProfile.DoesNotExist:
        request.session.flush()
        return None


def reelroots_login_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        profile = get_session_profile(request)
        if profile is None:
            messages.info(request, "Sign in to continue.")
            return redirect("auth")
        request.reelroots_profile = profile
        return view(request, *args, **kwargs)

    return wrapped

def onboarding_required(view):
    @wraps(view)
    @reelroots_login_required
    def wrapped(request, *args, **kwargs):
        profile = request.reelroots_profile
        if not profile.onboarding_completed:
            return redirect("onboarding")
        return view(request, *args, **kwargs)

    return wrapped


def api_login_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        profile = get_session_profile(request)
        if profile is None:
            return JsonResponse({"error": "Authentication required."}, status=401)
        request.reelroots_profile = profile
        return view(request, *args, **kwargs)

    return wrapped
