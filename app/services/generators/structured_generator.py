from __future__ import annotations
from typing import Any

from app.services.brand_context import get_brand_context
from app.services.llm import call_llm_json  # replace with your actual OpenAI client wrapper


def generate_structured_post(brand_id: str, platform: str, topic_text: str, content_type: str) -> dict[str, Any]:
    brand_ctx = get_brand_context(brand_id)

    user_input = f"""
{brand_ctx}

PLATFORM: {platform}
CONTENT_TYPE: {content_type}

TOPIC / ANGLE:
{topic_text}

OUTPUT FORMAT (MUST FOLLOW EXACTLY):
Return ONLY valid JSON. No markdown. No extra text.

{{
  "hook": "string (1 line)",
  "subheading": "string (1 short line)",
  "bullets": ["string", "string", "string"],
  "proof": "string (1 line credibility/proof)",
  "cta": "string (1 line call-to-action)",
  "hashtags": ["#tag1", "#tag2", "#tag3"],
  "image_prompt": "string or null"
}}
""".strip()

    return call_llm_json(user_input)
