from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _fernet():
    key = getattr(settings, "DJANGO_ENCRYPTION_KEY", "")
    if not key:
        raise ImproperlyConfigured("DJANGO_ENCRYPTION_KEY is required for staged signup encryption.")
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured("DJANGO_ENCRYPTION_KEY must be a valid Fernet key.") from exc


def encrypt_secret(value):
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value):
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ImproperlyConfigured("The staged signup encryption key cannot decrypt this signup.") from exc


def normalize_phone(value):
    """Normalize Kenyan-style numbers while keeping the country code configurable."""
    raw = "".join(ch for ch in (value or "").strip() if ch.isdigit() or ch == "+")
    default_code = getattr(settings, "PHONE_DEFAULT_COUNTRY_CODE", "+254")
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    if raw.startswith("0"):
        raw = default_code + raw[1:]
    elif raw.startswith("7") or raw.startswith("1"):
        raw = default_code + raw
    if not raw.startswith("+"):
        raw = "+" + raw
    digits = raw[1:]
    if not digits.isdigit() or len(digits) < 10 or len(digits) > 15:
        raise ValueError("Enter a valid phone number including its country code.")
    return "+" + digits
