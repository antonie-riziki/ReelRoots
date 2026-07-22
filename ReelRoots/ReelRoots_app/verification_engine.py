"""Deterministic, evidence-first verification orchestration."""

from decimal import Decimal
import hashlib
import re

from django.db import transaction
from django.utils import timezone

from .models import KnowledgeSource, VerificationClaim, VerificationEvidence, VerificationRequest, VerificationResult
from .source_retrieval import KnowledgeSourceStore, SourceRetriever
from .verification_ai import VerificationAI
from .verification_content import ContentExtractionError, VerificationContentExtractor


STOPWORDS = {
    "about", "after", "again", "also", "because", "being", "between", "could", "first", "from", "have",
    "into", "more", "most", "other", "over", "that", "their", "there", "these", "they", "this", "through",
    "under", "were", "which", "while", "with", "would", "your", "what", "when", "where", "whose", "will",
}
CONTRADICTION_MARKERS = {"disputed", "debunked", "incorrect", "false", "myth", "否", "refuted", "untrue"}


def _tokens(text):
    return {token for token in re.findall(r"[a-zA-ZÀ-ÿ]{3,}", str(text or "").lower()) if token not in STOPWORDS}


def _clamp(value):
    return max(Decimal("0"), min(Decimal("1"), Decimal(str(value))))


def _safe_text(value, limit=5000):
    return " ".join(str(value or "").split())[:limit]


class EvidenceComparator:
    """Transparent lexical comparison; later replaceable with a reviewed ranker or embeddings."""

    def compare(self, claim_text, claim_type, candidates):
        if claim_type == "subjective":
            return {"assessment": "subjective", "confidence": Decimal("0.95"), "reasoning": "This statement is presented as an opinion or value judgment, so factual verification is not applicable.", "evidence": []}
        claim_terms = _tokens(claim_text)
        comparisons = []
        for candidate in candidates:
            source_terms = _tokens(f"{candidate.title} {candidate.publisher} {candidate.excerpt}")
            overlap = len(claim_terms & source_terms) / max(len(claim_terms), 1)
            quality = Decimal(str(candidate.authority_rank)) / Decimal("5")
            source_text = f"{candidate.title} {candidate.excerpt}".lower()
            contradiction = overlap >= 0.2 and any(marker in source_text for marker in CONTRADICTION_MARKERS)
            comparisons.append({"candidate": candidate, "relevance": _clamp(overlap), "quality": _clamp(quality), "contradiction": contradiction})
        if not comparisons:
            return {"assessment": "unable_to_verify", "confidence": Decimal("0.05"), "reasoning": "No sufficiently relevant source was retrieved for comparison.", "evidence": []}

        relevant = [item for item in comparisons if item["relevance"] >= Decimal("0.2")]
        contradictory = [item for item in relevant if item["contradiction"]]
        supporting = [item for item in relevant if not item["contradiction"]]
        best = max(relevant or comparisons, key=lambda item: (item["relevance"] * item["quality"], item["quality"]))
        relevance = best["relevance"]
        quality = best["quality"]
        agreement = Decimal(len(supporting)) / Decimal(max(len(supporting) + len(contradictory), 1))
        confidence = _clamp(Decimal("0.45") * relevance + Decimal("0.35") * quality + Decimal("0.20") * agreement)
        authoritative_support = any(item["quality"] >= Decimal("0.8") for item in supporting)
        authoritative_contradiction = any(item["quality"] >= Decimal("0.8") for item in contradictory)

        if authoritative_contradiction and not authoritative_support:
            assessment = "false" if best["relevance"] >= Decimal("0.7") else "disputed"
            reasoning = "Retrieved authoritative evidence contradicts the claim; review the cited excerpts for the scope of that disagreement."
        elif authoritative_support and relevance >= Decimal("0.65") and not contradictory:
            assessment = "supported"
            reasoning = f"{len(supporting)} relevant authoritative source(s) closely match the claim, with no retrieved contradiction."
        elif relevant and relevance >= Decimal("0.45"):
            assessment = "mostly_supported"
            reasoning = "The claim is substantially consistent with retrieved sources, but the evidence is incomplete or not uniformly authoritative."
        elif relevant:
            assessment = "partially_supported"
            reasoning = "Some retrieved evidence overlaps with the claim, but it does not establish the full statement."
        else:
            assessment = "unsupported"
            confidence = min(confidence, Decimal("0.25"))
            reasoning = "Sources were retrieved, but their available text does not substantiate the claim."

        evidence = []
        for item in sorted(comparisons, key=lambda row: (row["relevance"], row["quality"]), reverse=True)[:5]:
            relationship = "contradicts" if item["contradiction"] else "supports" if item["relevance"] >= Decimal("0.2") else "unclear"
            evidence.append({"candidate": item["candidate"], "relationship": relationship, "relevance": item["relevance"], "quality": item["quality"]})
        return {"assessment": assessment, "confidence": confidence, "reasoning": reasoning, "evidence": evidence}


class VerificationEngine:
    def __init__(self, extractor=None, ai=None, source_retriever=None, source_store=None, comparator=None):
        self.extractor = extractor or VerificationContentExtractor()
        self.ai = ai or VerificationAI()
        self.source_retriever = source_retriever or SourceRetriever()
        self.source_store = source_store or KnowledgeSourceStore()
        self.comparator = comparator or EvidenceComparator()

    def _progress(self, request, status, progress, message):
        request.status = status
        request.progress = progress
        request.status_message = message
        request.save(update_fields=["status", "progress", "status_message", "updated_at"])

    def process(self, request_id):
        request = VerificationRequest.objects.get(id=request_id)
        if request.status == "complete" and hasattr(request, "result"):
            return request.result
        request.started_at = timezone.now()
        request.error_message = ""
        request.save(update_fields=["started_at", "error_message", "updated_at"])
        try:
            self._progress(request, "extracting", 15, "Analyzing content")
            text, metadata = self.extractor.extract(request)
            request.extracted_text = text
            request.content_metadata = metadata
            request.content_hash = hashlib.sha256(f"{request.input_type}|{request.source_url}|{request.input_text}".encode() + text.encode()).hexdigest()
            request.save(update_fields=["extracted_text", "content_metadata", "content_hash", "updated_at"])

            self._progress(request, "extracting_claims", 32, "Extracting claims")
            extraction = self.ai.extract(text)
            raw_claims = extraction.get("claims", []) if isinstance(extraction, dict) and isinstance(extraction.get("claims", []), list) else []
            entities = extraction.get("entities", []) if isinstance(extraction, dict) and isinstance(extraction.get("entities", []), list) else []
            topics = extraction.get("topics", []) if isinstance(extraction, dict) and isinstance(extraction.get("topics", []), list) else []
            VerificationClaim.objects.filter(request=request).delete()

            self._progress(request, "finding_evidence", 52, "Finding evidence")
            claim_results = []
            for ordinal, raw_claim in enumerate(raw_claims[:20]):
                if not isinstance(raw_claim, dict) or not _safe_text(raw_claim.get("text")):
                    continue
                claim_text = _safe_text(raw_claim.get("text"), 5000)
                claim_type = raw_claim.get("type") if raw_claim.get("type") in {"factual", "historical", "cultural", "subjective"} else "factual"
                raw_topics = raw_claim.get("topic_slugs", []) if isinstance(raw_claim.get("topic_slugs", []), list) else []
                claim_topics = [str(item)[:120] for item in raw_topics if item][:10]
                query = " ".join([claim_text, " ".join(claim_topics)])[:180]
                candidates = self.source_retriever.retrieve_query(query, limit=5)
                comparison = self.comparator.compare(claim_text, claim_type, candidates)
                claim = VerificationClaim.objects.create(
                    request=request,
                    claim_text=claim_text,
                    claim_type=claim_type,
                    assessment=comparison["assessment"],
                    confidence_score=comparison["confidence"],
                    reasoning=comparison["reasoning"],
                    entities=[item for item in entities if isinstance(item, dict)][:20],
                    topic_slugs=claim_topics or [str(item)[:120] for item in topics if item][:10],
                    ordinal=ordinal,
                )
                persisted = self.source_store.persist([item["candidate"] for item in comparison["evidence"]])
                by_url = {source.url: source for source in persisted}
                for item in comparison["evidence"]:
                    source = by_url.get(item["candidate"].url)
                    if not source:
                        continue
                    VerificationEvidence.objects.create(
                        claim=claim,
                        source=source,
                        relationship=item["relationship"],
                        excerpt=source.excerpt[:3000],
                        relevance_score=item["relevance"],
                        quality_score=item["quality"],
                        comparison_note=comparison["reasoning"],
                    )
                claim_results.append({"claim": claim, "comparison": comparison})

            self._progress(request, "comparing_sources", 76, "Comparing sources")
            overall, confidence = self._overall_assessment([item["claim"] for item in claim_results])
            result, _ = VerificationResult.objects.update_or_create(
                request=request,
                defaults={
                    "overall_assessment": overall,
                    "confidence_score": confidence,
                    "entities": [item for item in entities if isinstance(item, dict)][:30],
                    "topic_slugs": [str(item)[:120] for item in topics if item][:30],
                    "model_name": getattr(self.ai, "model", ""),
                    "prompt_version": getattr(self.ai, "prompt_version", "verification-v1"),
                },
            )
            self._progress(request, "preparing_results", 90, "Preparing results")
            explanation = self.ai.explain(text, overall, self._claim_payload(claim_results), entities, topics)
            result.summary = explanation.get("summary", "")
            result.historical_context = explanation.get("historical_context", "")
            result.explanation = explanation.get("explanation", "")
            result.recommendations = explanation.get("recommendations", [])
            result.generated_at = timezone.now()
            result.save()
            request.status = "complete"
            request.progress = 100
            request.status_message = "Verification complete"
            request.completed_at = timezone.now()
            request.save(update_fields=["status", "progress", "status_message", "completed_at", "updated_at"])
            return result
        except ContentExtractionError as exc:
            self._fail(request, str(exc))
        except Exception as exc:
            self._fail(request, "Verification could not be completed safely.")
            request.error_message = str(exc)[:2000]
            request.save(update_fields=["error_message", "updated_at"])
        return None

    def _fail(self, request, message):
        request.status = "failed"
        request.progress = 100
        request.status_message = "Verification failed"
        request.error_message = _safe_text(message, 2000)
        request.save(update_fields=["status", "progress", "status_message", "error_message", "updated_at"])

    def _claim_payload(self, claim_results):
        return [{
            "text": item["claim"].claim_text,
            "assessment": item["claim"].assessment,
            "confidence": float(item["claim"].confidence_score),
            "reasoning": item["claim"].reasoning,
            "evidence": [{"title": source.source.title, "url": source.source.url, "relationship": source.relationship, "excerpt": source.excerpt[:800]} for source in item["claim"].evidence.select_related("source")],
        } for item in claim_results]

    def _overall_assessment(self, claims):
        if not claims:
            return "unable_to_verify", Decimal("0.05")
        if all(claim.assessment == "subjective" for claim in claims):
            return "subjective", Decimal("0.95")
        factual = [claim for claim in claims if claim.assessment != "subjective"]
        if not factual:
            return "subjective", Decimal("0.95")
        if all(claim.assessment == "unable_to_verify" for claim in factual):
            return "unable_to_verify", Decimal("0.05")
        if any(claim.assessment == "false" for claim in factual) and not any(claim.assessment in {"supported", "mostly_supported"} for claim in factual):
            return "false", min(_clamp(sum((claim.confidence_score for claim in factual), Decimal("0")) / len(factual)), Decimal("0.9"))
        values = {"supported": Decimal("1"), "mostly_supported": Decimal("0.8"), "partially_supported": Decimal("0.55"), "disputed": Decimal("0.35"), "unsupported": Decimal("0.15"), "misleading": Decimal("0.2"), "false": Decimal("0"), "unable_to_verify": Decimal("0.05")}
        score = sum((values.get(claim.assessment, Decimal("0.05")) for claim in factual), Decimal("0")) / len(factual)
        confidence = _clamp(sum((claim.confidence_score for claim in factual), Decimal("0")) / len(factual))
        if any(claim.assessment == "disputed" for claim in factual) and score < Decimal("0.65"):
            return "disputed", confidence
        if score >= Decimal("0.85"):
            return "supported", confidence
        if score >= Decimal("0.65"):
            return "mostly_supported", confidence
        if score >= Decimal("0.4"):
            return "partially_supported", confidence
        if any(claim.assessment == "misleading" for claim in factual):
            return "misleading", confidence
        return "unsupported", confidence
