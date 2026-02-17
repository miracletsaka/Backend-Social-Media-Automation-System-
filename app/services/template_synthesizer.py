import os, json, re
from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY env var")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

client = OpenAI(api_key=OPENAI_API_KEY)

def _extract_text(response) -> str:
    """Extract text from OpenAI response"""
    return response.choices[0].message.content

def sanitize_examples(examples: list[dict]) -> list[dict]:
    """Remove data URLs but preserve all design details for AI learning"""
    out = []
    for template in examples:
        sanitized = dict(template)
        # Remove data URLs but keep all other design properties
        if "backgroundImage" in sanitized and isinstance(sanitized["backgroundImage"], str):
            if sanitized["backgroundImage"].startswith("data:"):
                sanitized["backgroundImage"] = None
        out.append(sanitized)
    return out

def synthesize_template_from_examples(example_templates, brand_id: str, canvas_width: int, canvas_height: int):
    system = (
        "You are an award-winning graphic designer specializing in luxury product advertisements. "
        "Create stunning, premium templates inspired by high-end beauty and lifestyle brands. "
        "Your designs should be sophisticated, modern, and visually compelling.\n\n"
        "CRITICAL RULES FOR TEXT SHAPES:\n"
        "- ALL dynamic content MUST use 'dataField' property, NEVER 'text' property\n"
        "- Available dataFields: 'hook', 'subheading', 'proof', 'cta', 'hashtags', 'companyName'\n"
        "- Each text shape MUST have exactly ONE dataField assigned\n"
        "- NEVER create button shapes or shapes with type 'button'\n"
        "- For call-to-action, create a rounded-rect background + text shape with dataField='cta' on top\n"
        "- You MAY include decorative text shapes with 'text' property for design elements like stars, icons, or decorative labels\n\n"
        "DATAFIELD USAGE:\n"
        "- 'hook': Main headline (large, bold, attention-grabbing)\n"
        "- 'subheading': Supporting headline or product description\n"
        "- 'proof': Social proof, testimonials, or credibility statement\n"
        "- 'cta': Call-to-action text (on button background)\n"
        "- 'hashtags': Social media hashtags or campaign tags\n"
        "- 'companyName': Brand/company name\n\n"
        "DESIGN PRINCIPLES:\n"
        "- Use organic shapes (ellipse, rounded-rect) with gradients for modern luxury feel\n"
        "- Create visual hierarchy: hook (largest) → subheading → proof → cta\n"
        "- Layer shapes: background shapes (zIndex 0-2) → content shapes (zIndex 3+)\n"
        "- Include testimonial boxes with white/light backgrounds\n"
        "- Design memorable CTA: colored rounded-rect + bold text with dataField='cta'\n"
        "- Balance product imagery space with text content\n\n"
        "TECHNICAL REQUIREMENTS:\n"
        "- Return ONLY valid, formatted JSON (proper indentation for readability)\n"
        "- backgroundImage MUST be: https://neuroflow.lon1.digitaloceanspaces.com/neuroflow/grunge-texture.jpg\n"
        "- logoPlacement MUST be null\n"
        "- Output EXACTLY 10 to 16 shapes for rich design\n"
        "- Allowed shape types: rectangle, rounded-rect, ellipse, text, line\n"
        "- Allowed text shape properties: id, type, x, y, width, height, zIndex, textColor, fontSize, fontFamily, "
        "fontWeight, textAlign, padding, opacity, shadowBlur, shadowX, shadowY, shadowColor, dataField (REQUIRED for dynamic text), "
        "text (OPTIONAL for decorative static text only), borderColor, borderWidth\n"
        "- Background shape properties: id, type, x, y, width, height, zIndex, backgroundColor, borderColor, borderWidth, "
        "borderRadius, opacity, shadowBlur, shadowX, shadowY, shadowColor\n"
    )

    prompt = {
        "brand_id": brand_id,
        "canvas": {
            "width": canvas_width,
            "height": canvas_height,
        },
        "design_brief": (
            "Create a premium commercial software company advertisement template like the reference examples. "
            "CRITICAL: Use dataField properties for ALL dynamic text (hook, subheading, proof, cta, hashtags, companyName). "
            "Structure: organic background shapes → main headline (dataField='hook') → subheading box (dataField='subheading') → "
            "testimonial/proof box (dataField='proof') → CTA button (rounded-rect + text with dataField='cta') → "
            "hashtags/brand name (dataField='hashtags' and 'companyName'). "
            "You may add decorative text shapes with 'text' property for stars, ratings, or design elements."
        ),
        "reference_templates": [
            {
                "id": f"ref_{i}",
                "width": ex.get("canvasWidth"),
                "height": ex.get("canvasHeight"),
                "description": ex.get("name", "reference design"),
                "elements": ex.get("shapes", [])
            }
            for i, ex in enumerate(example_templates)
        ],
        "output_requirements": {
            "canvasWidth": canvas_width,
            "canvasHeight": canvas_height,
            "backgroundImage": "https://neuroflow.lon1.digitaloceanspaces.com/neuroflow/grunge-texture.jpg",
            "logoPlacement": None,
            "name": "descriptive template name",
            "description": "design philosophy and inspiration",
            "shapes": [
                {
                    "note": "Background shapes (ellipse/rounded-rect with gradients or solid colors)",
                    "zIndex": "0-2"
                },
                {
                    "note": "Text shape with dataField='hook' (main headline)",
                    "zIndex": "3+"
                },
                {
                    "note": "Rounded-rect + Text shape with dataField='subheading'",
                    "zIndex": "3+"
                },
                {
                    "note": "Rounded-rect + Text shape with dataField='proof' (testimonial/social proof)",
                    "zIndex": "3+"
                },
                {
                    "note": "Rounded-rect (button background) + Text shape with dataField='cta'",
                    "zIndex": "8+"
                },
                {
                    "note": "Text shape with dataField='hashtags' or 'companyName'",
                    "zIndex": "9+"
                },
                {
                    "note": "Optional: decorative text shapes with 'text' property (stars, icons, etc.)",
                    "zIndex": "any"
                }
            ]
        }
    }

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False, indent=2)}
        ],
        temperature=0.7,
        max_tokens=16000,
        response_format={"type": "json_object"}
    )

    text = _extract_text(response).strip()
    print("RAW OPENAI RESPONSE:", text[:500])  # Log first 500 chars

    # detect truncation early
    if not text.endswith("}") or text.count("{") > text.count("}"):
        raise RuntimeError("OpenAI response truncated (incomplete JSON). Increase max_output_tokens or reduce output size.")

    data = parse_json_strict(text)

    # enforce rules server-side (safety)
    data["backgroundImage"] = "https://neuroflow.lon1.digitaloceanspaces.com/neuroflow/grunge-texture.jpg"
    data["logoPlacement"] = None
    data["canvasWidth"] = canvas_width
    data["canvasHeight"] = canvas_height

    # Validate that text shapes have dataField
    if "shapes" in data:
        for shape in data["shapes"]:
            if shape.get("type") == "text":
                # Must have either dataField or text (for decorative elements)
                if not shape.get("dataField") and not shape.get("text"):
                    print(f"WARNING: Text shape {shape.get('id')} missing both dataField and text")
            # Remove any button types
            if shape.get("type") == "button":
                print(f"WARNING: Removing invalid button shape {shape.get('id')}")
                data["shapes"].remove(shape)

    return data

def _extract_json_object(text: str) -> str:
    """Extract the first full JSON object from a string"""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in response")
    return text[start : end + 1]

def _remove_trailing_commas(s: str) -> str:
    """Fix invalid JSON trailing commas"""
    s = re.sub(r",\s*([}\]])", r"\1", s)
    return s

def parse_json_strict(text: str) -> dict:
    """Try strict parse, then apply safe repairs and retry"""
    raw = text.strip()
    
    try:
        return json.loads(raw)
    except Exception:
        pass
    
    raw = _extract_json_object(raw)
    raw = _remove_trailing_commas(raw)
    
    return json.loads(raw)