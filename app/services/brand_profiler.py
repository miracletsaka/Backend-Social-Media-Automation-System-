from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI


def build_brand_profile(raw_text: str, colors: list[str] | None, website_url: str) -> dict[str, Any]:
    """
    Returns a structured JSON profile.
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "").strip())
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    schema_hint = {
        "brand_name_guess": "",
        "one_liner": "",
        "tone": {
            "tags": [],
            "dos": [],
            "donts": [],
        },
        "positioning": {
            "value_props": [],
            "differentiators": [],
        },
        "audiences": [],
        "products_services": [],
        "proof_points": [],
        "cta_style": [],
        "visual": {
            "colors": colors or [],
            "style_notes": "",
        },
        "content_angles": [],   # IMPORTANT: “what to post about”
        "keywords": [],         # SEO-ish terms that appear frequently
    }

    prompt = f"""
You are a brand strategist and social media content director.

Your job:
1) Read the website scrape text
2) Extract key brand signals (copy, tone, positioning, products/services, CTAs)
3) Produce a compact, structured brand profile JSON matching the provided schema.

Rules:
- Be specific, not generic.
- If information is missing, infer carefully and label it as "inferred".
- Keep arrays short and punchy.
- Use simple language (business-friendly).
- Incorporate these detected colors if relevant: {colors or []}

Website: {website_url}

SCHEMA (must match shape; fill values):
{json.dumps(schema_hint, indent=2)}

SCRAPE TEXT:
{raw_text[:120000]}
"""

    r = client.responses.create(
        model=model,
        input=prompt,
        temperature=0.4,
    )

    text = (r.output_text or "").strip()
    # We expect JSON. If model returns extra text, try to locate JSON.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Profiler did not return JSON")

    obj = json.loads(text[start : end + 1])
    return obj


def summarize_profile(profile_json: dict[str, Any]) -> str:
    """
    Human-readable summary for UI.
    """
    tone = ", ".join(profile_json.get("tone", {}).get("tags", [])[:6])
    one_liner = profile_json.get("one_liner", "").strip()
    services = profile_json.get("products_services", [])[:6]
    vps = profile_json.get("positioning", {}).get("value_props", [])[:6]
    angles = profile_json.get("content_angles", [])[:6]

    lines = []
    if one_liner:
        lines.append(f"**One-liner:** {one_liner}")
    if tone:
        lines.append(f"**Tone:** {tone}")
    if services:
        lines.append(f"**Products/Services:** " + ", ".join(services))
    if vps:
        lines.append(f"**Value props:** " + "; ".join(vps))
    if angles:
        lines.append(f"**Recommended content angles:** " + "; ".join(angles))

    return "\n".join(lines).strip()
