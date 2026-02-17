# backend/app/services/ai_generator.py
import os
import json
import re
from typing import Dict, Any, Optional, List

from openai import OpenAI
from pydantic import BaseModel, Field

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

    return f"""
BRAND CONTEXT:
Brand: {brand_id}
Summary: {brand_profile_summary or "(No summary provided)"}
Tone tags: {", ".join(map(str, tone_tags)) if tone_tags else "(not provided)"}
Audiences: {", ".join(map(str, audiences)) if audiences else "(not provided)"}
Products/Services: {", ".join(map(str, services)) if services else "(not provided)"}
Value props: {", ".join(map(str, positioning)) if positioning else "(not provided)"}
CTA style: {json.dumps(cta_style, ensure_ascii=False) if cta_style else "(not provided)"}
Colors: {", ".join(map(str, colors)) if colors else "(not provided)"}
""".strip()


class PostOutput(BaseModel):
    hook: str = Field(..., description="Opening hook line only, 10 words max, plain text no markdown")
    subheading: str = Field(..., description="Product intro line only, 14 words max, plain text no markdown")
    bullets: List[str] = Field(..., min_length=3, max_length=3, description="3 key benefits, plain text no markdown")
    proof: str = Field(..., description="Social proof line only, 9 words max, plain text no markdown")
    cta: str = Field(..., description="Call to action line only, 10 words max, plain text no markdown")
    full_caption: str = Field(..., description="Complete formatted ad copy with all sections, emojis, bullets, line breaks - 15-30 lines total, ready to post, PLAIN TEXT ONLY NO MARKDOWN")
    hashtags: List[str] = Field(default_factory=list, description="Array of hashtags like #Tag")
    scheduled_at: str = Field(..., description="ISO 8601 UTC ends with Z")
    image_prompt: Optional[str] = Field(default=None, description="Simple background prompt - 1-2 colors, minimal objects, 10-15 words max")
    video_concept: Optional[str] = Field(default=None)
    thumbnail_prompt: Optional[str] = Field(default=None)
    media_prompt: Optional[str] = Field(default=None)


def strip_markdown(text: str) -> str:
    """Remove common Markdown formatting characters"""
    if not text:
        return text
    
    # Remove bold **text** and __text__
    text = text.replace('**', '')
    text = text.replace('__', '')
    
    # Remove italic *text* and _text_ (but preserve * for bullet points at line start)
    # Only remove * that are used for emphasis (not at line start for bullets)
    text = re.sub(r'(?<!\n)(?<!\n\n)(?<!\n )(?<!^\*)\*(?!\s)', '', text, flags=re.MULTILINE)
    text = re.sub(r'(?<!^)_(?!$)', '', text, flags=re.MULTILINE)
    
    # Remove inline code `text`
    text = text.replace('`', '')
    
    # Remove headers ### text
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # Remove strikethrough ~~text~~
    text = text.replace('~~', '')
    
    return text


def build_instructions(
    platform: str,
    brand_id: str,
    target_month: Optional[str] = None,
    posts_per_week: Optional[int] = None,
    client_now_utc_iso: Optional[str] = None,
    timezone: str = "Europe/London",
    posting_hour_local: int = 9,
) -> str:
    base = f"""
You are a professional copywriter creating commercial advertisements for {platform}.
Write in SIMPLE, CLEAR ENGLISH that anyone can understand — like explaining to a smart student.

Start with a scenario, something like, many org live in the past doing.. But according to the topic.

🚨 CRITICAL FORMATTING RULES - READ FIRST:
❌ ABSOLUTELY NO Markdown syntax (no **, no *, no _, no #, no backticks, no ~~)
❌ NO asterisks for bold or italics emphasis
❌ NO special formatting characters for styling
✅ Use PLAIN TEXT ONLY with emojis and line breaks
✅ Use emojis for visual emphasis instead of bold
✅ Use UPPERCASE for emphasis if needed (use sparingly)
✅ Bullet points use * at the START of lines only (for actual bullet lists, not emphasis)

WRONG: "🚀 **Introducing** the Future!"
RIGHT: "🚀 Introducing the Future!"

WRONG: "This is *amazing* technology"
RIGHT: "This is amazing technology" or "This is AMAZING technology"

CRITICAL: Generate TWO outputs:
1. Individual fields (hook, subheading, bullets, proof, cta) - SHORT versions for structured data (all plain text)
2. full_caption field - COMPLETE formatted ad with ALL sections below (all plain text)

COMPLETE AD STRUCTURE (for full_caption field):
Write the full_caption as a multi-paragraph formatted post following this EXACT structure:

1. OPENING HOOK (Emoji + Statement - PLAIN TEXT):
   Example: "🚀 Introducing the Future of Customer Communication!"
   
2. PRODUCT INTRODUCTION (Plain text, one clear sentence):
   Example: "Meet the NEW groundbreaking WhatsApp Chatbot Software designed for businesses, schools, institutions, and organizations that want to grow faster and serve customers 24/7."

3. IMAGINATION SECTION:
   Example: "Imagine having a smart assistant that:"

4. BENEFIT CHECKLIST (✅ format, 5-6 items - plain text only):
   Example:
   "✅ Replies to customers instantly on WhatsApp
   ✅ Answers questions automatically
   ✅ Books appointments and sends reminders
   ✅ Handles customer support without human stress
   ✅ Works day and night — even when you are offline"

5. DIFFERENTIATION (Plain text):
   Example: "This is not just a chatbot. This is a powerful AI assistant built to increase your sales, save your time, and improve your customer experience."

6. TARGET AUDIENCES (💼 emoji - plain text bullets with *):
   Example:
   "💼 Perfect for:
   * Businesses & Startups
   * Schools & Universities
   * Hospitals & Clinics
   * NGOs & Organizations
   * Online Shops & Services"

7. WHY CHOOSE US (🔹 format - plain text):
   Example:
   "Why This Now?
   🔹 Easy to use
   🔹 Fast setup
   🔹 Affordable for growing businesses
   🔹 Smart AI conversations
   🔹 Custom solution for YOUR organization"

8. URGENCY STATEMENT (Plain text):
   Example: "Stop losing customers because of late replies. Start converting chats into real revenue on WhatsApp today!"

9. VALUE PROPOSITIONS (3 emoji lines - plain text):
   Example:
   "📈 Turn conversations into customers.
   📲 Automate your business.
   🌍 Grow your brand with intelligent WhatsApp chatbots."

10. CLOSING CTA (Plain text):
    Example: "Contact us today and let your business speak automatically, professionally, and intelligently — 24/7."

FORMATTING RULES FOR full_caption:
- Use PLAIN TEXT only - absolutely NO Markdown formatting whatsoever
- NO ** for bold, NO * for italics, NO _ for underline, NO # for headers
- Use proper line breaks between sections for readability
- Include ALL emojis (🚀, ✅, 💼, 🔹, 📈, 📲, 🌍, etc.) for visual appeal
- Use bullet points with * at line start for lists (literal asterisks for bullets, NOT markdown emphasis)
- For emphasis, use emojis or UPPERCASE words (use sparingly, not every sentence)
- Keep it readable and well-spaced with blank lines between sections
- Total length: 15-30 lines of text
- Make it ready to copy-paste directly into social media posts

LANGUAGE STYLE:
✅ Simple 8th-grade English - clear and easy to understand
✅ Short, clear sentences - avoid complexity
✅ Active voice: "You get X" not "X is provided"
✅ Specific numbers when possible: "Save 5 hours daily" not "Save time"
✅ Conversational but professional - like a friendly expert
✅ Enthusiastic and helpful tone - make people excited

AVOID:
❌ Markdown formatting of any kind (**, *, _, #, `, ~~)
❌ Complex jargon or technical terms
❌ Long, complicated sentences
❌ Passive voice
❌ Vague claims without specifics
❌ Corporate buzzwords
""".strip()

    now_line = (
        f'- client_now_utc = "{client_now_utc_iso}" (THIS IS THE CURRENT TIME; do not schedule before this). '
        f'Schedule must be at least +2 hours after client_now_utc.'
        if client_now_utc_iso
        else "- client_now_utc is unknown; schedule in the future"
    )

    if target_month and posts_per_week:
        scheduling = f"""
SCHEDULING RULES:
- timezone_local = "{timezone}"
{now_line}
- target_month = "{target_month}" (YYYY-MM)
- posts_per_week = {posts_per_week}
- Prefer weekdays (Mon-Fri) and spread evenly across the month.
- Default posting time is {posting_hour_local:02d}:00 local time; convert to UTC and output scheduled_at ending with Z.
""".strip()
    else:
        scheduling = f"""
SCHEDULING RULES:
- timezone_local = "{timezone}"
{now_line}
- Choose the next valid weekday at {posting_hour_local:02d}:00 local time.
- Convert to UTC and output scheduled_at ending with Z.
""".strip()

    image_prompt_rules = f"""
IMAGE PROMPT RULES (CRITICAL - READ CAREFULLY):

YOU MUST GENERATE EXTREMELY SIMPLE BACKGROUNDS:

MANDATORY REQUIREMENTS:
1. ONLY 1-2 solid colors (use brand colors if provided, otherwise: green, blue, yellow, orange, purple, red)
2. MAXIMUM 1 simple object OR zero objects (strongly prefer zero objects)
3. If including 1 object: must be simple geometric shape ONLY (circle, rounded square, leaf shape, abstract curve)
4. NO complex illustrations, NO multiple objects, NO 3D renders, NO detailed textures, NO patterns
5. Portrait orientation 4:5 (1080x1350)
6. 80%+ of canvas should be EMPTY solid color for text placement
7. Keep prompt under 15 words maximum

GOOD EXAMPLES (copy this exact style):
✅ "Solid vibrant green background, flat design, portrait 4:5, no objects"
✅ "Bright yellow background, one white circle top-right corner, minimalist flat, portrait"
✅ "Solid orange background, small leaf shape bottom-left, simple flat, 4:5"
✅ "Two-color background: blue top, white bottom, clean division, portrait 4:5"
✅ "Solid lime green, subtle gradient, completely empty, portrait, commercial ad"
✅ "White background, 2 small yellow circles one corner, flat minimal, portrait"
✅ "Solid red background, no objects, flat graphic design, portrait 4:5"
✅ "Purple solid color, one green circle, simple, portrait orientation"

BAD EXAMPLES (NEVER generate like this):
❌ "Colorful 3D shapes, multiple objects, complex composition..."
❌ "Vibrant abstract design with many elements and textures..."
❌ "Playful arrangement of geometric shapes scattered across..."
❌ "Dynamic colorful background with various elements..."
❌ Any prompt with words: multiple, various, collection, arrangement, scattered, dynamic, playful, complex, detailed, realistic texture, 3D, rendered

SIMPLICITY CHECKLIST - YOUR PROMPT MUST PASS ALL:
- Colors: 1 or 2 only? ✓
- Objects: 0 or 1 simple shape? ✓
- Empty space: 80%+ for text? ✓
- Portrait 4:5 ratio? ✓
- Under 15 words? ✓
- No complex descriptors? ✓

FINAL OUTPUT: One very short sentence (10-15 words maximum) describing the simple colored background.
Example format: "Solid [color] background, [optional: one simple shape location], flat design, portrait 4:5"
""".strip()

    return "\n\n".join([base, scheduling, image_prompt_rules]).strip()


def generate_post(
    topic_text: str,
    platform: str,
    brand_id: str,
    brand_profile_summary=None,
    brand_profile_json=None,
    target_month: str | None = None,
    posts_per_week: int | None = None,
    client_now_utc_iso: str | None = None,
    timezone: str = "Europe/London",
    posting_hour_local: int = 9,
) -> Dict[str, Any]:

    brand_ctx = _brand_context_block(brand_id, brand_profile_summary, brand_profile_json)

    instructions = build_instructions(
        platform=platform,
        brand_id=brand_id,
        target_month=target_month,
        posts_per_week=posts_per_week,
        client_now_utc_iso=client_now_utc_iso,
        timezone=timezone,
        posting_hour_local=posting_hour_local,
    )

    user_input = f"""
{brand_ctx}

TOPIC:
{topic_text}

PLATFORM:
{platform}

Generate:
1. A complete formatted advertisement in the 'full_caption' field following ALL 10 steps with emojis and proper formatting - USE PLAIN TEXT ONLY, NO MARKDOWN
2. Individual short fields (hook, subheading, bullets, proof, cta) for structured data - ALL PLAIN TEXT, NO MARKDOWN
3. A VERY SIMPLE image_prompt: just 1-2 solid colors with 0-1 objects maximum, under 15 words

CRITICAL REMINDERS:
- NO ** or * or _ or # for formatting (plain text only)
- Image prompt must be extremely simple (like "Solid green background, flat, portrait 4:5")
- Full caption should be 15-30 lines with emojis, bullets, and line breaks
""".strip()

    resp = client.responses.parse(
        model=MODEL,
        instructions=instructions,
        input=user_input,
        text_format=PostOutput,
    )

    data: PostOutput = resp.output_parsed

    # Strip any Markdown formatting that might have slipped through
    full_caption_cleaned = strip_markdown(data.full_caption or "")
    hook_cleaned = strip_markdown(data.hook or "")
    subheading_cleaned = strip_markdown(data.subheading or "")
    proof_cleaned = strip_markdown(data.proof or "")
    cta_cleaned = strip_markdown(data.cta or "")

    # Normalize bullets / hashtags
    bullets = [strip_markdown(str(x).strip()) for x in (data.bullets or []) if str(x).strip()][:3]
    while len(bullets) < 3:
        bullets.append("")

    hashtags_list = [str(x).strip() for x in (data.hashtags or []) if str(x).strip()]
    hashtags = " ".join(hashtags_list).strip()

    structured = {
        "hook": hook_cleaned.strip(),
        "subheading": subheading_cleaned.strip(),
        "bullets": bullets,
        "proof": proof_cleaned.strip(),
        "cta": cta_cleaned.strip(),
        "hashtags": hashtags_list,
        "scheduled_at": data.scheduled_at,
        "image_prompt": data.image_prompt,
        "video_concept": data.video_concept,
        "thumbnail_prompt": data.thumbnail_prompt,
        "media_prompt": data.media_prompt,
    }

    return {
        "body_text": full_caption_cleaned.strip(),  # Use the complete cleaned caption
        "hashtags": hashtags,
        "scheduled_at": data.scheduled_at,
        "media_prompt": data.media_prompt,
        "structured": structured,
    }