from concurrent.futures import ThreadPoolExecutor
import os

from django.db import close_old_connections

from .moderation import process_submission


_executor = ThreadPoolExecutor(max_workers=int(os.getenv("MODERATION_WORKERS", "2")))


def _run(submission_id):
    close_old_connections()
    try:
        process_submission(str(submission_id))
    finally:
        close_old_connections()


def enqueue_submission(submission_id):
    return _executor.submit(_run, str(submission_id))
