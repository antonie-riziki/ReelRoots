import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Read configuration at startup, but defer the network-aware client setup until a view needs it.
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_PUBLISHABLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase URL or Key in environment variables.")

_supabase_client: Client | None = None


def get_supabase() -> Client:
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client


class _LazySupabaseClient:
    def __getattr__(self, name):
        return getattr(get_supabase(), name)


supabase = _LazySupabaseClient()
