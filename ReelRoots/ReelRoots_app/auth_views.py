import json
import logging
import os
import secrets
from datetime import timedelta
from uuid import UUID

from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, ProgrammingError, transaction
from django.db.utils import OperationalError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import reelroots_login_required
from .forms import OnboardingForm, ProfileForm, SignInForm, SignUpForm, VerifyPhoneForm
from .integrations import (
    AfricaTalkingSMS,
    SMSConfigurationError,
    SupabaseAuth,
    SupabaseConfigurationError,
    SupabaseDuplicateAccountError,
)
from .models import PendingSignup, PhoneVerification, UserProfile
from .personalization import profile_preferences, set_explicit_interests, set_preferences
from .security import decrypt_secret, encrypt_secret, normalize_phone


PENDING_SIGNUP_SESSION_KEY = "pending_signup_id"
OTP_LIFETIME = timedelta(minutes=10)
PENDING_SIGNUP_LIFETIME = timedelta(minutes=15)
OTP_RESEND_COOLDOWN = timedelta(seconds=60)
logger = logging.getLogger(__name__)


def _code():
    return f"{secrets.randbelow(1_000_000):06d}"


def _user_id(user):
    value = getattr(user, "id", None)
    if value is None and isinstance(user, dict):
        value = user.get("id")
    return UUID(str(value))


def _session_value(session, name):
    value = getattr(session, name, None)
    if value is None and isinstance(session, dict):
        value = session.get(name)
    return value


def _establish_session(request, profile, auth_response):
    session = _session_value(auth_response, "session")
    if session is None:
        raise ValueError("Supabase did not return a login session.")
    request.session.cycle_key()
    request.session["profile_id"] = str(profile.id)
    request.session["supabase_user_id"] = str(profile.supabase_user_id)
    request.session["supabase_access_token"] = _session_value(session, "access_token")
    request.session["supabase_refresh_token"] = _session_value(session, "refresh_token")
    request.session.set_expiry(None)


def _signup_data(request):
    data = request.POST.copy()
    data["phone"] = request.POST.get("phone-number", "")
    data["confirm_password"] = request.POST.get("confirm-password", "")
    return data


def _form_error(form, fallback):
    errors = []
    for field_errors in form.errors.values():
        errors.extend(str(error) for error in field_errors)
    return "; ".join(errors) or fallback


def auth_page(request):
    active_tab = request.GET.get("tab", "signin")
    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "signin":
            form = SignInForm(request.POST)
            if form.is_valid():
                try:
                    auth = SupabaseAuth()
                    auth_response = auth.sign_in(form.cleaned_data["email"].lower(), form.cleaned_data["password"])
                    profile = UserProfile.objects.filter(supabase_user_id=_user_id(auth._user(auth_response))).first()
                    if profile is None:
                        messages.error(request, "Your account needs to be completed before you can sign in.")
                    elif not profile.phone_verified:
                        messages.error(request, "Verify your phone number before signing in.")
                    else:
                        _establish_session(request, profile, auth_response)
                        return redirect("home" if profile.onboarding_completed else "onboarding")
                except (OperationalError, ProgrammingError):
                    logger.exception("ReelRoots sign-in database is unavailable")
                    messages.error(
                        request,
                        "Your password was accepted, but ReelRoots profile storage is not configured. Set DATABASE_URL on the server.",
                    )
                except Exception:
                    messages.error(request, "Invalid email or password.")
            else:
                messages.error(request, _form_error(form, "Enter a valid email and password."))
        elif form_type == "signup":
            active_tab = "signup"
            form = SignUpForm(_signup_data(request))
            if form.is_valid():
                try:
                    _start_signup(request, form.cleaned_data)
                    messages.success(request, "We sent a verification code to your phone.")
                    return redirect("verify-phone")
                except SupabaseDuplicateAccountError:
                    messages.error(
                        request,
                        "An account with that email or phone already exists. Sign in or reset your password.",
                    )
                except (ValueError, IntegrityError):
                    messages.error(request, "That phone number or email is already in use.")
                except SMSConfigurationError:
                    messages.error(
                        request,
                        "Phone verification is not configured yet. Add AT_API_KEY, then try again.",
                    )
                except SupabaseConfigurationError:
                    logger.exception("ReelRoots signup could not authenticate to Supabase Admin")
                    messages.error(
                        request,
                        "Account creation is temporarily unavailable. Please check the server Supabase configuration.",
                    )
                except Exception:
                    logger.exception("ReelRoots signup failed while starting the account")
                    messages.error(request, "We could not start your account. Please try again.")
            else:
                messages.error(request, _form_error(form, "Check the signup form."))
        else:
            messages.error(request, "Choose sign in or sign up.")
    if active_tab not in {"signin", "signup"}:
        active_tab = "signin"
    return render(request, "auth.html", {"active_tab": active_tab})


def _start_signup(request, cleaned):
    phone_number = normalize_phone(cleaned["phone"])
    email = cleaned["email"].lower()
    if UserProfile.objects.filter(email=email).exists() or UserProfile.objects.filter(phone_number=phone_number).exists():
        raise IntegrityError("duplicate local account")
    now = timezone.now()
    if PendingSignup.objects.filter(expires_at__gt=now, email=email).exists():
        raise ValueError("pending signup exists")
    if PendingSignup.objects.filter(expires_at__gt=now, phone_number=phone_number).exists():
        raise ValueError("pending signup exists")

    sms = AfricaTalkingSMS()
    auth = SupabaseAuth()
    user = auth.create_staged_user(email=email, password=cleaned["password"], phone_number=phone_number, name=cleaned["name"])
    user_id = _user_id(user)
    pending = None
    try:
        with transaction.atomic():
            code = _code()
            pending = PendingSignup.objects.create(
                supabase_user_id=user_id,
                email=email,
                name=cleaned["name"],
                phone_number=phone_number,
                institution=cleaned.get("institution", ""),
                encrypted_password=encrypt_secret(cleaned["password"]),
                expires_at=now + PENDING_SIGNUP_LIFETIME,
            )
            PhoneVerification.objects.create(
                pending_signup=pending,
                code_hash=make_password(code),
                expires_at=now + OTP_LIFETIME,
            )
        try:
            sms.send_otp(phone_number, code)
        except Exception:
            pending.delete()
            raise
    except Exception:
        auth.delete_user(user_id)
        raise
    request.session[PENDING_SIGNUP_SESSION_KEY] = str(pending.id)


def verify_phone(request):
    pending_id = request.session.get(PENDING_SIGNUP_SESSION_KEY)
    pending = PendingSignup.objects.filter(id=pending_id).first() if pending_id else None
    if pending is None or pending.is_expired:
        messages.error(request, "This verification request has expired. Please start again.")
        request.session.pop(PENDING_SIGNUP_SESSION_KEY, None)
        return redirect("auth")
    if request.method == "POST":
        form = VerifyPhoneForm(request.POST)
        verification = pending.phone_verification
        if verification.is_expired:
            messages.error(request, "That code has expired. Request a new one.")
        elif verification.is_locked:
            messages.error(request, "Too many attempts. Request a new code.")
        elif form.is_valid() and check_password(form.cleaned_data["code"], verification.code_hash):
            try:
                auth = SupabaseAuth()
                auth.confirm_phone(pending.supabase_user_id)
                auth_response = auth.sign_in(pending.email, decrypt_secret(pending.encrypted_password))
                with transaction.atomic():
                    profile, _ = UserProfile.objects.get_or_create(
                        supabase_user_id=pending.supabase_user_id,
                        defaults={
                            "email": pending.email,
                            "name": pending.name,
                            "phone_number": pending.phone_number,
                            "institution": pending.institution,
                        },
                    )
                    profile.email = pending.email
                    profile.name = pending.name
                    profile.phone_number = pending.phone_number
                    profile.institution = pending.institution
                    profile.phone_verified_at = timezone.now()
                    profile.save()
                    _establish_session(request, profile, auth_response)
                    pending.delete()
                request.session.pop(PENDING_SIGNUP_SESSION_KEY, None)
                messages.success(request, "Phone verified. Let’s personalize your ReelRoots experience.")
                return redirect("onboarding")
            except Exception:
                messages.error(request, "We verified the code but could not finish your account. Please try again.")
        else:
            verification.attempts += 1
            verification.save(update_fields=["attempts", "last_sent_at"])
            messages.error(request, "That verification code is not valid.")
    return render(request, "verify_phone.html", {"phone_number": pending.phone_number})


@require_POST
def resend_phone_code(request):
    pending_id = request.session.get(PENDING_SIGNUP_SESSION_KEY)
    pending = PendingSignup.objects.filter(id=pending_id).first() if pending_id else None
    if pending is None or pending.is_expired:
        messages.error(request, "This verification request has expired. Please start again.")
        return redirect("auth")
    code = _code()
    verification = pending.phone_verification
    if verification.last_sent_at and timezone.now() - verification.last_sent_at < OTP_RESEND_COOLDOWN:
        messages.error(request, "Please wait a minute before requesting another code.")
        return redirect("verify-phone")
    verification.code_hash = make_password(code)
    verification.expires_at = timezone.now() + OTP_LIFETIME
    verification.attempts = 0
    verification.save()
    try:
        AfricaTalkingSMS().send_otp(pending.phone_number, code)
        messages.success(request, "A new verification code was sent.")
    except Exception:
        messages.error(request, "We could not send a new code. Please try again later.")
    return redirect("verify-phone")


def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        if email:
            try:
                SupabaseAuth().request_password_reset(email)
            except Exception:
                pass
        messages.success(request, "If that account exists, a password reset email is on its way.")
        return redirect("auth")
    return render(request, "forgot_password.html")


def reset_password(request):
    return render(request, "reset_password.html", {
        "supabase_url": os.getenv("SUPABASE_URL", ""),
        "supabase_publishable_key": os.getenv("SUPABASE_PUBLISHABLE_KEY", ""),
    })


@require_POST
def logout_view(request):
    SupabaseAuth().sign_out(request.session.get("supabase_access_token"), request.session.get("supabase_refresh_token"))
    request.session.flush()
    messages.success(request, "You have been signed out.")
    return redirect("landing-page")


@reelroots_login_required
def onboarding(request):
    profile = request.reelroots_profile
    if request.method == "POST":
        form = OnboardingForm(request.POST)
        if form.is_valid():
            set_explicit_interests(profile, form.cleaned_data["topics"])
            set_preferences(profile, regions=form.cleaned_data["regions"], countries=form.cleaned_data["countries"], languages=form.cleaned_data["languages"], content_types=form.cleaned_data["content_types"])
            profile.onboarding_completed = True
            profile.save(update_fields=["onboarding_completed", "updated_at"])
            messages.success(request, "Your personalized ReelRoots experience is ready.")
            return redirect("home")
        messages.error(request, "Choose at least one interest and one language to continue.")
    else:
        current = profile_preferences(profile)
        form = OnboardingForm(initial={
            "topics": list(profile.interests.filter(source="explicit").values_list("topic__slug", flat=True)),
            "regions": current.get("region", []),
            "countries": current.get("country", []),
            "languages": current.get("language", []),
            "content_types": current.get("content_type", []),
        })
    return render(request, "onboarding.html", {"form": form, "profile": profile})


@reelroots_login_required
def profile_settings(request):
    profile = request.reelroots_profile
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile was updated.")
            return redirect("user-profile")
    else:
        form = ProfileForm(instance=profile)
    return render(request, "profile_settings.html", {"form": form, "profile": profile})


@require_POST
@reelroots_login_required
def personalization_event(request):
    from .personalization import record_engagement
    try:
        data = json.loads(request.body or "{}")
        record_engagement(request.reelroots_profile, event_type=data.get("event_type", ""), topic_slug=data.get("topic_slug"), content_key=data.get("content_key", ""), value=data.get("value", 1), metadata=data.get("metadata", {}))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid personalization event."}, status=400)
    return JsonResponse({"status": "recorded"}, status=201)
