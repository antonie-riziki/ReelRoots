import os

import africastalking
from django.core.exceptions import ImproperlyConfigured

from .supabase_client import supabase


class SMSConfigurationError(ImproperlyConfigured):
    """Raised when the SMS provider cannot be used for phone verification."""


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
    """Server-only Supabase Auth adapter. The secret key never reaches templates."""

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
        response = supabase.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "phone": phone_number,
                "email_confirm": True,
                "phone_confirm": False,
                "user_metadata": {"name": name},
            }
        )
        return self._user(response)

    def confirm_phone(self, user_id):
        return supabase.auth.admin.update_user_by_id(str(user_id), {"phone_confirm": True})

    def delete_user(self, user_id):
        try:
            return supabase.auth.admin.delete_user(str(user_id))
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
