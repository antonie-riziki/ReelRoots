"""Small background queue for local development, with a management-command fallback."""

from concurrent.futures import ThreadPoolExecutor
import os

from django.db import close_old_connections

from .verification_engine import VerificationEngine


_executor = ThreadPoolExecutor(max_workers=int(os.getenv("VERIFICATION_WORKERS", "2")))


def _run(request_id):
    close_old_connections()
    try:
        VerificationEngine().process(request_id)
    finally:
        close_old_connections()


def enqueue_verification(request_id):
    """Queue work immediately; production can call the same engine from Celery/RQ."""
    return _executor.submit(_run, str(request_id))
