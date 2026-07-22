import os
from supabase import create_client, Client
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

load_dotenv()

# Read configuration at startup, but defer the network-aware client setup until a view needs it.
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "").strip()

_supabase_client: Client | None = None


def get_supabase() -> Client:
    global _supabase_client
    if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY:
        raise ImproperlyConfigured(
            "SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY are required for public Supabase Auth operations."
        )
    if _supabase_client is None:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)
    return _supabase_client


def get_supabase_admin_config() -> tuple[str, str]:
    """Return server-only Admin API configuration without creating a JWT client.

    Supabase ``sb_secret_`` keys are opaque API keys, not JWTs. The installed
    Python Auth SDK sends its client key as ``Authorization: Bearer ...`` for
    Auth Admin requests, which makes Supabase try to parse an opaque key as a
    JWT and return ``unrecognized JWT kid <nil>``. Admin integrations use this
    configuration with the ``apikey`` header instead.
    """

    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        raise ImproperlyConfigured(
            "SUPABASE_URL and SUPABASE_SECRET_KEY are required for server-side Supabase Admin operations."
        )
    return SUPABASE_URL.rstrip("/"), SUPABASE_SECRET_KEY


class _LazySupabaseClient:
    def __getattr__(self, name):
        return getattr(get_supabase(), name)


supabase = _LazySupabaseClient()
