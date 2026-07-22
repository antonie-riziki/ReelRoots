"""Reusable source retrieval and source persistence for context and verification."""

from dataclasses import dataclass, field
import os
from urllib.parse import urlparse

import requests

from .models import KnowledgeSource


@dataclass(frozen=True)
class SourceCandidate:
    title: str
    url: str
    publisher: str = ""
    source_type: str = "other"
    authority_rank: int = 1
    license_name: str = ""
    excerpt: str = ""
    metadata: dict = field(default_factory=dict)


def _abstract_text(inverted_index):
    if not isinstance(inverted_index, dict):
        return ""
    words = []
    for word, positions in inverted_index.items():
        for position in positions or []:
            words.append((position, word))
    return " ".join(word for _, word in sorted(words))[:1200]


def _classify_source(title, publisher):
    text = f"{title} {publisher}".lower()
    for term, source_type, rank in (
        ("unesco", "cultural_institution", 5),
        ("archive", "archive", 5),
        ("museum", "museum", 5),
        ("university", "university", 5),
        ("government", "government", 5),
        ("library", "library", 4),
    ):
        if term in text:
            return source_type, rank
    return "academic", 4


class OpenAlexRetriever:
    endpoint = "https://api.openalex.org/works"

    def __init__(self):
        self.user_agent = os.getenv(
            "REELROOTS_HTTP_USER_AGENT",
            "ReelRoots/0.1 (cultural heritage research platform)",
        )

    def search(self, query, limit=5):
        if not query:
            return []
        params = {"search": query[:180], "per-page": limit}
        email = os.getenv("REELROOTS_RESEARCH_EMAIL", "").strip()
        if email:
            params["mailto"] = email
        try:
            response = requests.get(self.endpoint, params=params, headers={"User-Agent": self.user_agent}, timeout=10)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            return []
        results = []
        for work in payload.get("results", []):
            locations = work.get("primary_location") or {}
            url = locations.get("landing_page_url") or work.get("doi") or work.get("id")
            if not url:
                continue
            publisher = ((locations.get("source") or {}).get("display_name") or "")
            source_type, rank = _classify_source(work.get("title", ""), publisher)
            results.append(SourceCandidate(
                title=work.get("title") or "Academic work",
                url=url,
                publisher=publisher,
                source_type=source_type,
                authority_rank=rank,
                excerpt=_abstract_text(work.get("abstract_inverted_index")),
                metadata={"openalex_id": work.get("id", ""), "publication_year": work.get("publication_year")},
            ))
        return results


class SourceRetriever:
    def __init__(self, academic_retriever=None):
        self.academic_retriever = academic_retriever or OpenAlexRetriever()

    def retrieve(self, reel, extraction):
        candidates = []
        if reel.source_url:
            candidates.append(SourceCandidate(
                title=reel.title or "Original reel source",
                url=reel.source_url,
                publisher=urlparse(reel.source_url).netloc,
                source_type="original_media",
                authority_rank=3,
                license_name=reel.license_status,
                excerpt=reel.description[:1200],
                metadata={"source_platform": reel.source_platform},
            ))
        entities = " ".join(item.get("name", "") for item in extraction.get("entities", []) if isinstance(item, dict))
        topics = " ".join(extraction.get("topics", []) or [])
        query = " ".join(part for part in (reel.title, entities, topics) if part)
        candidates.extend(self.academic_retriever.search(query))
        unique = {}
        for candidate in candidates:
            if candidate.url and candidate.url not in unique:
                unique[candidate.url] = candidate
        return list(unique.values())[:8]


class KnowledgeSourceStore:
    def persist(self, candidates):
        sources = []
        for candidate in candidates:
            source, _ = KnowledgeSource.objects.update_or_create(
                url=candidate.url,
                defaults={
                    "title": candidate.title[:500],
                    "publisher": candidate.publisher[:255],
                    "source_type": candidate.source_type,
                    "authority_rank": candidate.authority_rank,
                    "license_name": candidate.license_name[:255],
                    "excerpt": candidate.excerpt,
                    "metadata": candidate.metadata,
                },
            )
            sources.append(source)
        return sources
