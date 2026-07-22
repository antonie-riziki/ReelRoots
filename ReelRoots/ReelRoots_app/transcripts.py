"""Transcript extraction adapters for reel context generation."""

from dataclasses import dataclass
import os

import requests


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    status: str
    source: str = ""


class TranscriptExtractor:
    """Use an explicitly configured transcript service, otherwise metadata only."""

    def __init__(self):
        self.endpoint = os.getenv("TRANSCRIPT_API_URL", "").strip()
        self.user_agent = os.getenv(
            "REELROOTS_HTTP_USER_AGENT",
            "ReelRoots/0.1 (cultural heritage research platform)",
        )

    def extract(self, reel):
        if self.endpoint and reel.video_url:
            try:
                response = requests.post(
                    self.endpoint,
                    json={"video_url": reel.video_url, "title": reel.title, "source_url": reel.source_url},
                    headers={"User-Agent": self.user_agent},
                    timeout=20,
                )
                response.raise_for_status()
                transcript = str(response.json().get("transcript", "")).strip()
                if transcript:
                    return TranscriptResult(transcript[:20000], "external_api", self.endpoint)
            except (requests.RequestException, ValueError, TypeError):
                pass

        metadata = ". ".join(part.strip() for part in (reel.title, reel.description) if part and part.strip())
        return TranscriptResult(metadata[:20000], "metadata_fallback", "reel_metadata")
