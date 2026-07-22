"""Evidence-aware context generation shared by reels and future URL verification."""

from decimal import Decimal, InvalidOperation
import hashlib
import json
from urllib.parse import urlparse

from django.db import transaction
from django.utils import timezone

from .ai_context import ContextAI
from .models import (
    ContextClaim,
    ContextEntity,
    ContextEvidence,
    ContextTimelineEntry,
    ReelContext,
)
from .source_retrieval import KnowledgeSourceStore, SourceRetriever
from .transcripts import TranscriptExtractor


STATUSES = {item[0] for item in ReelContext.VERIFICATION_STATUSES}
CLAIM_TYPES = {item[0] for item in ContextClaim.CLAIM_TYPES}
ENTITY_TYPES = {item[0] for item in ContextEntity.ENTITY_TYPES}


def _confidence(value, default=0.1):
    try:
        return max(Decimal("0"), min(Decimal("1"), Decimal(str(value))))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(str(default))


def _status(value):
    value = str(value or "insufficient_evidence").strip().lower().replace(" ", "_")
    aliases = {"partially_supported": "partially_supported", "false": "false_misleading", "misleading": "false_misleading"}
    value = aliases.get(value, value)
    return value if value in STATUSES else "insufficient_evidence"


def _fingerprint(reel, transcript):
    payload = {
        "title": reel.title,
        "description": reel.description,
        "video_url": reel.video_url,
        "source_url": reel.source_url,
        "updated_at": reel.updated_at.isoformat() if reel.updated_at else "",
        "topics": list(reel.topics.values_list("slug", flat=True)),
        "transcript": transcript,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


class ContextEngine:
    def __init__(self, transcript_extractor=None, source_retriever=None, source_store=None, ai=None):
        self.transcript_extractor = transcript_extractor or TranscriptExtractor()
        self.source_retriever = source_retriever or SourceRetriever()
        self.source_store = source_store or KnowledgeSourceStore()
        self.ai = ai or ContextAI()

    def _fallback_extraction(self, reel):
        return {
            "claims": [],
            "entities": [],
            "topics": list(reel.topics.values_list("slug", flat=True)),
            "timeline": [],
        }

    def _fallback_generation(self, reel, extraction, sources):
        links = [{"label": source.title, "url": source.url} for source in sources if source.url]
        return {
            "summary": f"This reel presents a visual reference titled “{reel.title}”. Additional historical context has not been verified yet.",
            "key_facts": [],
            "historical_context": "No historical claim is presented as verified because supporting evidence is insufficient.",
            "claims": [],
            "entities": [],
            "timeline": [],
            "related_topics": extraction.get("topics", []),
            "external_links": links,
            "confidence": 0.1,
        }

    @transaction.atomic
    def get_or_generate(self, reel, force=False):
        transcript_result = self.transcript_extractor.extract(reel)
        fingerprint = _fingerprint(reel, transcript_result.text)
        context, _ = ReelContext.objects.get_or_create(reel=reel)
        if not force and context.generation_status == "complete" and context.source_fingerprint == fingerprint and (context.sources.exists() or not reel.source_url):
            return context

        context.generation_status = "generating"
        context.error_message = ""
        context.transcript = transcript_result.text
        context.transcript_status = transcript_result.status
        context.source_fingerprint = fingerprint
        context.model_name = getattr(self.ai, "model", "")
        context.prompt_version = getattr(self.ai, "prompt_version", "")
        context.save()

        try:
            extraction = self.ai.extract(reel, transcript_result.text) or self._fallback_extraction(reel)
            sources = self.source_retriever.retrieve(reel, extraction)
            source_objects = self.source_store.persist(sources)
            context.sources.set(source_objects)
            generated = self.ai.generate(reel, transcript_result.text, extraction, sources)
            if not generated:
                generated = self._fallback_generation(reel, extraction, source_objects)
            self._persist_generated(context, generated, extraction, source_objects)
            context.generation_status = "complete"
            context.generated_at = timezone.now()
            context.save(update_fields=[
                "summary", "historical_context", "key_facts", "related_topic_slugs", "external_links",
                "confidence_score", "verification_status", "generation_status", "generated_at", "updated_at",
            ])
        except Exception as exc:
            context.generation_status = "failed"
            context.error_message = str(exc)[:2000]
            context.verification_status = "insufficient_evidence"
            context.confidence_score = Decimal("0.1")
            context.summary = f"This reel presents a visual reference titled “{reel.title}”. Context generation is temporarily unavailable."
            context.historical_context = "No historical claim is presented as verified because supporting evidence is insufficient."
            context.key_facts = []
            context.related_topic_slugs = list(reel.topics.values_list("slug", flat=True))
            context.external_links = []
            context.save()
        return context

    def _persist_generated(self, context, generated, extraction, source_objects):
        ContextClaim.objects.filter(context=context).delete()
        ContextEntity.objects.filter(context=context).delete()
        ContextTimelineEntry.objects.filter(context=context).delete()
        context.summary = str(generated.get("summary") or "Context is not available yet.")[:10000]
        context.historical_context = str(generated.get("historical_context") or "No historical context has been verified yet.")[:20000]
        context.key_facts = [str(item)[:1000] for item in (generated.get("key_facts") or []) if item][:20]
        context.related_topic_slugs = [str(item)[:120] for item in (generated.get("related_topics") or extraction.get("topics") or []) if item][:30]
        context.external_links = [
            {"label": str(item.get("label") or item.get("title") or item["url"])[:255], "url": item["url"]}
            for item in (generated.get("external_links") or [])
            if isinstance(item, dict) and urlparse(str(item.get("url", ""))).scheme in {"http", "https"}
        ][:20]

        claim_statuses = []
        for ordinal, raw in enumerate(generated.get("claims") or []):
            if not isinstance(raw, dict) or not str(raw.get("text", "")).strip():
                continue
            indices = raw.get("evidence_indices") or []
            valid_indices = [index for index in indices if isinstance(index, int) and 0 <= index < len(source_objects)]
            claim_status = _status(raw.get("status"))
            confidence = _confidence(raw.get("confidence"))
            if not valid_indices:
                claim_status = "insufficient_evidence"
                confidence = min(confidence, Decimal("0.2"))
            elif not any(source_objects[index].authority_rank >= 4 for index in valid_indices):
                # Original media can establish what the media contains, but is not
                # an authoritative historical source on its own.
                if claim_status in {"verified", "disputed", "false_misleading"}:
                    claim_status = "partially_supported"
                    confidence = min(confidence, Decimal("0.4"))
            claim = ContextClaim.objects.create(
                context=context,
                claim_text=str(raw["text"]).strip()[:5000],
                claim_type=str(raw.get("type", "historical")) if str(raw.get("type", "historical")) in CLAIM_TYPES else "historical",
                verification_status=claim_status,
                confidence_score=confidence,
                evidence_summary=str(raw.get("evidence_summary", ""))[:3000],
                ordinal=ordinal,
            )
            claim_statuses.append(claim_status)
            relationships = raw.get("evidence_relationships") or {}
            for index in valid_indices:
                relationship = relationships.get(str(index), relationships.get(index, "")) if isinstance(relationships, dict) else ""
                if relationship not in {"supports", "contradicts", "unclear"}:
                    relationship = "contradicts" if claim_status in {"disputed", "false_misleading"} else "supports"
                if source_objects[index].source_type == "original_media":
                    relationship = "unclear"
                ContextEvidence.objects.create(
                    claim=claim,
                    source=source_objects[index],
                    relationship=relationship,
                    excerpt=source_objects[index].excerpt[:3000],
                    confidence_score=confidence,
                )

        for ordinal, raw in enumerate(generated.get("entities") or extraction.get("entities") or []):
            if not isinstance(raw, dict) or not str(raw.get("name", "")).strip():
                continue
            entity_type = str(raw.get("type", "place"))
            if entity_type not in ENTITY_TYPES:
                entity_type = "place"
            ContextEntity.objects.create(
                context=context,
                name=str(raw["name"]).strip()[:255],
                entity_type=entity_type,
                description=str(raw.get("description", ""))[:3000],
                confidence_score=_confidence(raw.get("confidence", 0.2)),
                ordinal=ordinal,
            )

        for ordinal, raw in enumerate(generated.get("timeline") or extraction.get("timeline") or []):
            if not isinstance(raw, dict) or not str(raw.get("event", "")).strip():
                continue
            ContextTimelineEntry.objects.create(
                context=context,
                date_label=str(raw.get("date", "Unknown date"))[:120],
                event=str(raw["event"]).strip()[:3000],
                location=str(raw.get("location", ""))[:255],
                confidence_score=_confidence(raw.get("confidence", 0.2)),
                ordinal=ordinal,
            )

        if not claim_statuses:
            overall = "insufficient_evidence"
        elif "false_misleading" in claim_statuses:
            overall = "false_misleading"
        elif "disputed" in claim_statuses:
            overall = "disputed"
        elif "insufficient_evidence" in claim_statuses:
            overall = "insufficient_evidence"
        elif "partially_supported" in claim_statuses:
            overall = "partially_supported"
        else:
            overall = "verified"
        context.verification_status = overall
        claim_confidence = [claim.confidence_score for claim in context.claims.all()]
        ai_confidence = _confidence(generated.get("confidence"), 0.1)
        context.confidence_score = min(ai_confidence, max(claim_confidence, default=Decimal("0.1"))) if claim_confidence else Decimal("0.1")


def _status_label(status):
    return dict(ReelContext.VERIFICATION_STATUSES).get(status, status.replace("_", " ").title())


def serialize_context(context):
    claims = []
    used_sources = {}
    for claim in context.claims.prefetch_related("evidence__source").all():
        evidence = []
        for item in claim.evidence.all():
            used_sources[item.source.url] = item.source
            evidence.append({
                "source": item.source.title,
                "title": item.source.title,
                "url": item.source.url,
                "relationship": item.relationship,
                "excerpt": item.excerpt,
            })
        claims.append({
            "text": claim.claim_text,
            "type": claim.claim_type,
            "status": claim.verification_status,
            "label": _status_label(claim.verification_status),
            "confidence": float(claim.confidence_score),
            "evidence_summary": claim.evidence_summary,
            "evidence": evidence,
        })
    for source in context.sources.all():
        used_sources[source.url] = source
    sources = [
        {"title": source.title, "publisher": source.publisher, "url": source.url, "type": source.source_type}
        for source in sorted(used_sources.values(), key=lambda item: (-item.authority_rank, item.title))
    ]
    return {
        "summary": context.summary,
        "key_facts": context.key_facts,
        "historical_context": context.historical_context,
        "claims": claims,
        "entities": [
            {"name": item.name, "type": item.entity_type, "description": item.description, "confidence": float(item.confidence_score)}
            for item in context.entities.all()
        ],
        "timeline": [
            {"date": item.date_label, "event": item.event, "location": item.location, "confidence": float(item.confidence_score)}
            for item in context.timeline.all()
        ],
        "related_topics": context.related_topic_slugs,
        "sources": sources,
        "external_links": context.external_links,
        "verification_status": context.verification_status,
        "verification_label": _status_label(context.verification_status),
        "confidence": float(context.confidence_score),
        "transcript_status": context.transcript_status,
        "model": context.model_name,
        "prompt_version": context.prompt_version,
        "generated_at": context.generated_at.isoformat() if context.generated_at else None,
    }
