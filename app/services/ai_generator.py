import os
import json
from typing import Dict, Any, Optional

from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _safe_list(x):
    if not x:
        return []
    if isinstance(x, list):
        return x
    return [x]


def _brand_context_block(
    brand_id: str,
    brand_profile_summary: Optional[str] = None,
    brand_profile_json: Optional[dict[str, Any]] = None,
) -> str:
    """
    Turn scraped profile into a short, usable prompt block.
    Keep it concise, otherwise the model will ramble.
    """
    tone_tags = []
    services = []
    audiences = []
    positioning = []
    cta_style = None
    colors = []

    if isinstance(brand_profile_json, dict):
        tone_tags = _safe_list((brand_profile_json.get("tone") or {}).get("tags"))
        services = _safe_list(brand_profile_json.get("products_services"))
        audiences = _safe_list(brand_profile_json.get("audiences"))
        positioning = _safe_list((brand_profile_json.get("positioning") or {}).get("value_props"))
        cta_style = brand_profile_json.get("cta_style")
        colors = _safe_list(brand_profile_json.get("colors"))

    # Keep it short but strong
    block = f"""
BRAND CONTEXT (use this to avoid generic writing):
Brand: {brand_id}

Brand summary:
{brand_profile_summary or "(No summary provided)"}

Tone tags: {", ".join([str(x) for x in tone_tags]) if tone_tags else "(not provided)"}
Target audiences: {", ".join([str(x) for x in audiences]) if audiences else "(not provided)"}
Products/Services: {", ".join([str(x) for x in services]) if services else "(not provided)"}
Positioning / Value props: {", ".join([str(x) for x in positioning]) if positioning else "(not provided)"}
CTA style/examples: {json.dumps(cta_style, ensure_ascii=False) if cta_style else "(not provided)"}
Brand colors: {", ".join([str(x) for x in colors]) if colors else "(not provided)"}
""".strip()

    return block


def build_instructions(platform: str, brand_id: str, content_type: str) -> str:
    base = f"""
You are a senior social media copywriter for {brand_id}.
Write ORIGINAL, non-generic marketing content based on the topic and brand context.
No fluff. Clear hook + value + CTA.
Avoid vague claims. Be concrete.
""".strip()

    # Platform style
    if platform == "linkedin":
        style = """
LinkedIn style:
- professional, insight-driven
- 120–220 words
- include 3–5 bullet points if helpful
- no hashtags OR max 3 hashtags at the end
""".strip()
    elif platform in ("facebook", "instagram"):
        style = """
Facebook/Instagram style:
- punchy, short-form
- 60–150 words
- strong first line hook
- include 5–12 relevant hashtags at the end (not spam)
""".strip()
    else:
        style = "Generic social style. Keep it clear and direct."

    # Content-type specific behavior
    if content_type == "text":
        ctype = """
Content type: TEXT
Return a caption and hashtags only.
""".strip()
    elif content_type == "image":
        ctype = """
Content type: IMAGE
Return:
1) caption
2) hashtags
3) IMAGE_PROMPT (a single detailed prompt for generating the image that matches the caption + brand style)
""".strip()
    elif content_type == "video":
        ctype = """
Content type: VIDEO
Return:
1) caption
2) hashtags
3) VIDEO_CONCEPT (short concept: scene + camera + on-screen text + duration)
4) THUMBNAIL_PROMPT (prompt for a thumbnail image)
""".strip()
    else:
        ctype = "Return caption and hashtags."

    return "\n\n".join([base, style, ctype]).strip()


def generate_post(
    topic_text: str,
    platform: str,
    brand_id: str,
    content_type: str = "text",
    brand_profile_summary: Optional[str] = None,
    brand_profile_json: Optional[dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Returns:
      {
        "body_text": "...",
        "hashtags": "...",
        "media_prompt": "...optional..."
      }
    """
    instructions = build_instructions(platform, brand_id, content_type)
    brand_ctx = _brand_context_block(brand_id, brand_profile_summary, brand_profile_json)

    # ✅ Ask for a strict, parseable output (prevents messy splits)
    # We return as labeled blocks.
    user_input = f"""
{brand_ctx}

TOPIC:
{topic_text}

OUTPUT FORMAT (MUST FOLLOW EXACTLY):
CAPTION:
<caption text>

HASHTAGS:
<hashtags line, either empty or starting with #>

IF IMAGE, ALSO INCLUDE:
IMAGE_PROMPT:
<prompt>

IF VIDEO, ALSO INCLUDE:
VIDEO_CONCEPT:
<concept>
THUMBNAIL_PROMPT:
<prompt>
""".strip()

    resp = client.responses.create(
        model=MODEL,
        instructions=instructions,
        input=user_input,
    )

    text = (resp.output_text or "").strip()

    # ✅ Parse labeled blocks robustly
    def extract_block(label: str) -> str:
        marker = f"{label}:"
        if marker not in text:
            return ""
        after = text.split(marker, 1)[1]
        # stop at next known label
        for nxt in ["CAPTION:", "HASHTAGS:", "IMAGE_PROMPT:", "VIDEO_CONCEPT:", "THUMBNAIL_PROMPT:"]:
            if nxt != marker and nxt in after:
                after = after.split(nxt, 1)[0]
        return after.strip()

    caption = extract_block("CAPTION")
    hashtags = extract_block("HASHTAGS")

    media_prompt = ""
    if content_type == "image":
        media_prompt = extract_block("IMAGE_PROMPT")
    elif content_type == "video":
        concept = extract_block("VIDEO_CONCEPT")
        thumb = extract_block("THUMBNAIL_PROMPT")
        # keep as one field for now (frontend can display later)
        media_prompt = f"VIDEO_CONCEPT: {concept}\nTHUMBNAIL_PROMPT: {thumb}".strip()

    # Final cleanup
    caption = caption.strip()
    hashtags = " ".join([h.strip() for h in hashtags.split() if h.strip()]).strip()

    out: Dict[str, str] = {"body_text": caption, "hashtags": hashtags}
    if media_prompt:
        out["media_prompt"] = media_prompt

    return out
