"""Triage Agent — scores one message's true-urgency via Gemini on Vertex AI.

The SOP and country feed are injected into the prompt (no vector DB). Output is
structured to the TriageResult schema. Applies the bias-to-escalate rule: if the
model's confidence is below the floor, round the severity up one tier.
"""
from __future__ import annotations

import json
import time
from functools import lru_cache

from google import genai
from google.genai import types
from google.genai.errors import ClientError

from app.config import CONFIDENCE_FLOOR, LOCATION, PROJECT, TRIAGE_MODEL, USE_VERTEXAI
from app.schemas import ESCALATE_UP, Severity, TriageResult

SYSTEM_INSTRUCTION = """You are the Triage Agent for a national foreign ministry's
24/7 consular Duty Office during a crisis. You read one inbound citizen message and
assign its TRUE urgency using the provided SOP. Recall on life-threatening (P1) cases
matters far more than precision: when uncertain between two tiers, choose the MORE
severe one. Never downplay danger. Always cite the SOP tier that applies."""

PROMPT_TEMPLATE = """## SOP (authoritative triage rules)
{sop}

## Live country-conditions feed (context)
{feed}

## Inbound message to triage
\"\"\"{message}\"\"\"

Classify this message. Return severity (P1–P4), a short category, your confidence
(0–1), a one-sentence reason, and the SOP reference (e.g. 'P1 §4.2')."""


@lru_cache(maxsize=1)
def _client() -> genai.Client:
    if USE_VERTEXAI:
        return genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    return genai.Client()  # falls back to GEMINI_API_KEY if Vertex disabled


def _generate_with_backoff(client, model, contents, config, max_retries=6):
    """Call Gemini, retrying on 429 RESOURCE_EXHAUSTED with exponential backoff.

    New projects start with low Gemini quota; this keeps us under the rate limit.
    """
    delay = 4.0
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(model=model, contents=contents, config=config)
        except ClientError as e:
            if getattr(e, "code", None) == 429 and attempt < max_retries - 1:
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            raise


def triage_message(
    text: str,
    sop: str,
    feed: dict,
    *,
    client: genai.Client | None = None,
    model: str | None = None,
) -> TriageResult:
    client = client or _client()
    prompt = PROMPT_TEMPLATE.format(sop=sop, feed=json.dumps(feed), message=text)

    resp = _generate_with_backoff(
        client,
        model or TRIAGE_MODEL,
        prompt,
        types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=TriageResult,
        ),
    )

    result: TriageResult = resp.parsed  # pydantic instance per response_schema

    # Bias-to-escalate: low confidence → round severity up one tier.
    if result.confidence < CONFIDENCE_FLOOR:
        bumped = ESCALATE_UP[result.severity.value]
        if bumped != result.severity.value:
            result.severity = Severity(bumped)
            result.reason = f"[escalated: low confidence {result.confidence:.2f}] {result.reason}"
    return result
