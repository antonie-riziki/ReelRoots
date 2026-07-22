"""Gemini adapter for structured, evidence-constrained context generation."""

import json
import os

from google import genai
from google.genai import types


def _clean_json(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return None


class ContextAI:
    def __init__(self):
        self.model = os.getenv("CONTEXT_AI_MODEL", "gemini-2.0-flash")
        self.prompt_version = os.getenv("CONTEXT_PROMPT_VERSION", "context-v1")
        self.api_key = os.getenv("GOOGLE_API_KEY", "").strip()
        self._client = None

    def _generate(self, prompt):
        if not self.api_key:
            return None
        try:
            if self._client is None:
                self._client = genai.Client(api_key=self.api_key)
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                    max_output_tokens=2500,
                ),
            )
            return _clean_json(response.text)
        except Exception:
            return None

    def extract(self, reel, transcript):
        prompt = f"""You are extracting research leads for a cultural heritage context engine.
Do not infer facts. Use only the reel metadata and transcript below. Return JSON only.
Required shape: claims array with text/type; entities array with name/type/description; topics array of slugs; timeline array with date/event/location.
Allowed claim types: historical, cultural, media. Allowed entity types: person, place, date, event, organization, cultural_group.
Reel title: {reel.title}
Description: {reel.description}
Transcript or metadata: {transcript}"""
        result = self._generate(prompt)
        return result if isinstance(result, dict) else None

    def generate(self, reel, transcript, extraction, sources):
        source_text = "\n".join(
            f"[{index}] {source.title} | {source.publisher} | {source.url}\nExcerpt: {source.excerpt[:1200]}"
            for index, source in enumerate(sources)
        ) or "No supporting sources were retrieved."
        prompt = f"""You are ReelRoots Context Engine. Generate careful, readable context for a historical/cultural reel.
Return JSON only with keys: summary, key_facts, historical_context, claims, entities, timeline, related_topics, external_links, confidence.
Each claim must be an object with text, type, status, confidence, evidence_indices, evidence_summary.
Status must be exactly one of verified, partially_supported, disputed, insufficient_evidence, false_misleading.
Never present unsupported claims as facts. Every factual claim must cite source indices when possible. If no source supports it, use insufficient_evidence and an empty evidence_indices array. Keep uncertainty explicit. Use disputed or false_misleading only when retrieved evidence actually contradicts the claim. Do not upgrade original media into an authoritative source.
Reel title: {reel.title}
Description: {reel.description}
Transcript: {transcript}
Extraction: {json.dumps(extraction, ensure_ascii=True)}
Retrieved sources:
{source_text}"""
        result = self._generate(prompt)
        return result if isinstance(result, dict) else None
