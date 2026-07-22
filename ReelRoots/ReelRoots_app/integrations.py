import os

import africastalking
import httpx
from django.core.exceptions import ImproperlyConfigured

from .supabase_client import get_supabase_admin_config, supabase


class SMSConfigurationError(ImproperlyConfigured):
    """Raised when the SMS provider cannot be used for phone verification."""


class SupabaseConfigurationError(ImproperlyConfigured):
    """Raised when the server cannot authenticate to Supabase safely."""


class SupabaseDuplicateAccountError(ValueError):
    """Raised when Supabase already has the requested email or phone."""


class AfricaTalkingSMS:
    """Small provider adapter so OTP logic remains testable and provider-agnostic."""

    def __init__(self):
        # EMID and 20384 are the Africa's Talking account/sender details supplied
        # for ReelRoots. Environment variables still override them per deployment.
        self.username = os.getenv("AT_USERNAME", "").strip() or "EMID"
        self.api_key = os.getenv("AT_API_KEY", "").strip()
        self.sender_id = os.getenv("AT_SENDER_ID", "20384").strip() or "20384"
        if not self.api_key:
            raise SMSConfigurationError("AT_API_KEY is required to send SMS.")

    def send_message(self, phone_number, message_context):
        africastalking.initialize(username=self.username, api_key=self.api_key)
        recipients = [str(phone_number)]
        return africastalking.SMS.send(str(message_context), recipients, self.sender_id)

    def send_otp(self, phone_number, code):
        message = (
            f"Welcome to ReelRoots! Your verification code is {code}. "
            "It expires in 10 minutes."
        )
        return self.send_message(phone_number, message)


class SupabaseAuth:
    """Supabase Auth adapter with a safe split between public and Admin APIs.

    User-facing Auth calls use the publishable-key client. Admin calls use the
    server-only secret key in the ``apikey`` header through the Auth REST API;
    the secret key is intentionally never sent as a Bearer token.
    """

    @staticmethod
    def _admin_request(method, path, payload=None):
        base_url, secret_key = get_supabase_admin_config()
        headers = {
            "apikey": secret_key,
            "Content-Type": "application/json",
            "X-Client-Info": "reelroots-django",
        }
        try:
            response = httpx.request(
                method,
                f"{base_url}/auth/v1/{path}",
                headers=headers,
                json=payload,
                timeout=15,
            )
        except httpx.HTTPError as exc:
            raise SupabaseConfigurationError(
                "Supabase Auth could not be reached."
            ) from exc

        if response.is_success:
            if response.status_code == 204 or not response.content:
                return None
            return response.json()

        try:
            error_payload = response.json()
        except ValueError:
            error_payload = {}
        detail = str(
            error_payload.get("msg")
            or error_payload.get("message")
            or error_payload.get("error_description")
            or ""
        )
        normalized_detail = detail.lower()
        if response.status_code == 422 and (
            "already been registered" in normalized_detail
            or "already registered" in normalized_detail
            or "already exists" in normalized_detail
        ):
            raise SupabaseDuplicateAccountError(
                "A Supabase account with that email or phone already exists."
            )
        if response.status_code in {401, 403}:
            raise SupabaseConfigurationError(
                "Supabase Admin authentication was rejected. Check SUPABASE_SECRET_KEY."
            )
        raise SupabaseConfigurationError(
            f"Supabase Auth Admin request failed with HTTP {response.status_code}."
        )

    @staticmethod
    def _user(response):
        user = getattr(response, "user", None)
        if user is None and isinstance(response, dict):
            user = response.get("user")
        if user is None:
            raise ValueError("Supabase did not return a user.")
        return user

    @staticmethod
    def _session(response):
        return getattr(response, "session", None) or (response.get("session") if isinstance(response, dict) else None)

    def create_staged_user(self, *, email, password, phone_number, name):
        response = self._admin_request(
            "POST",
            "admin/users",
            {
                "email": email,
                "password": password,
                "phone": phone_number,
                "email_confirm": True,
                "phone_confirm": False,
                "user_metadata": {"name": name},
            },
        )
        return self._user(response)

    def confirm_phone(self, user_id):
        return self._admin_request(
            "PUT",
            f"admin/users/{user_id}",
            {"phone_confirm": True},
        )

    def delete_user(self, user_id):
        try:
            return self._admin_request("DELETE", f"admin/users/{user_id}")
        except Exception:
            return None

    def sign_in(self, email, password):
        return supabase.auth.sign_in_with_password({"email": email, "password": password})

    def sign_out(self, access_token=None, refresh_token=None):
        if access_token and refresh_token:
            try:
                supabase.auth.set_session(access_token, refresh_token)
            except Exception:
                pass
        try:
            return supabase.auth.sign_out()
        except Exception:
            return None

    def request_password_reset(self, email):
        redirect_to = os.getenv("SUPABASE_PASSWORD_RESET_REDIRECT_URL", "") or None
        if redirect_to:
            return supabase.auth.reset_password_for_email(email, {"redirect_to": redirect_to})
        return supabase.auth.reset_password_for_email(email)
