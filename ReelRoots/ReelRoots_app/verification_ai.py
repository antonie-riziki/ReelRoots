"""LLM adapters that extract and explain verification data without deciding truth."""

import json
import re

from .ai_context import ContextAI


class VerificationAI:
    def __init__(self, ai=None):
        self.ai = ai or ContextAI()
        self.model = getattr(self.ai, "model", "")
        self.prompt_version = "verification-v1"

    def extract(self, text):
        prompt = f"""You are ReelRoots' claim extraction assistant.
Extract only claims explicitly stated in the submitted content. Do not decide whether any claim is true.
Return JSON only with claims, entities, and topics.
claims: objects with text, type (factual|historical|cultural|subjective), and topic_slugs.
entities: objects with name, type, and description.
topics: an array of short slugs.
If the text is empty or is only a statement of opinion, return an empty claims array.
Submitted content:
{text[:50000]}"""
        result = self.ai.generate_json(prompt)
        return result if isinstance(result, dict) else self._fallback_extract(text)

    def explain(self, submitted_text, assessment, claims, entities, topics):
        evidence_text = json.dumps(claims, ensure_ascii=True)
        prompt = f"""You are the explanation assistant for ReelRoots' verification engine.
The assessment and confidence were calculated by deterministic evidence comparison. Do not change them and do not add factual claims.
Write concise user-facing text only. Return JSON with summary, historical_context, explanation, recommendations.
Explain why the result was reached using the provided evidence relationships and source quality. State clearly when evidence is insufficient, sources disagree, historical interpretation varies, or a claim is subjective. Never reveal hidden reasoning or chain-of-thought.
Overall assessment: {assessment}
Claims and evidence: {evidence_text}
Extracted entities: {json.dumps(entities, ensure_ascii=True)}
Topics: {json.dumps(topics, ensure_ascii=True)}
Submitted content excerpt: {submitted_text[:4000]}"""
        result = self.ai.generate_json(prompt)
        if isinstance(result, dict):
            return {
                "summary": str(result.get("summary", ""))[:5000],
                "historical_context": str(result.get("historical_context", ""))[:10000],
                "explanation": str(result.get("explanation", ""))[:10000],
                "recommendations": [str(item)[:500] for item in result.get("recommendations", []) if item][:10],
            }
        return self._fallback_explanation(assessment, claims)

    def _fallback_extract(self, text):
        claims = []
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", text or ""):
            sentence = sentence.strip(" -•\t")
            if len(sentence.split()) < 5:
                continue
            claim_type = "subjective" if re.search(r"\b(I think|in my opinion|should|best|beautiful|worst)\b", sentence, re.I) else "factual"
            claims.append({"text": sentence[:2000], "type": claim_type, "topic_slugs": []})
        return {"claims": claims[:20], "entities": [], "topics": []}

    def _fallback_explanation(self, assessment, claims):
        if not claims:
            return {
                "summary": "No verifiable factual claims were identified.",
                "historical_context": "The submitted content did not provide enough text or evidence for historical analysis.",
                "explanation": "ReelRoots could not identify a claim that could be compared with sources.",
                "recommendations": ["Submit more text or a transcript for a more useful analysis."],
            }
        return {
            "summary": f"The evidence comparison result is {assessment.replace('_', ' ')}.",
            "historical_context": "Historical interpretation may vary, and this result reflects only the sources retrieved for the submitted claims.",
            "explanation": "This assessment was produced from source relevance, source authority, and agreement between retrieved evidence and each claim.",
            "recommendations": ["Review the cited sources and compare their scope, date, and institutional authority."],
        }
