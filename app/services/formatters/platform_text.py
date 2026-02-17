# backend/app/services/formatters/platform_text.py
from __future__ import annotations

from typing import Any, Iterable

def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    # If stored as JSON string accidentally
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        # try a very light fallback split
        return [x.strip() for x in s.split("\n") if x.strip()]
    return [str(value).strip()]

def _hashtags_text(hashtags: Any) -> str:
    tags = _as_list(hashtags)
    if not tags:
        return ""
    # Ensure hashtags start with #
    fixed = []
    for t in tags:
        t = t.strip()
        if not t:
            continue
        if not t.startswith("#"):
            t = "#" + t.replace(" ", "")
        fixed.append(t)
    return " " + " ".join(fixed)

def build_structured_text(
    *,
    platform: str,
    hook: str | None,
    subheading: str | None,
    bullets: Any,
    proof: str | None,
    cta: str | None,
    hashtags: Any,
    fallback_body_text: str | None = None,
) -> str:
    """
    Produces a beautiful caption using your structured fields.
    Platform rules:
      - LinkedIn: cleaner, fewer emojis, more spacing, professional tone.
      - Facebook: slightly more punchy, can use a couple emojis, more direct CTA.
    """
    p = (platform or "").lower().strip()

    b_list = _as_list(bullets)
    tags_text = _hashtags_text(hashtags)

    # fallback if fields empty
    if not any([hook, subheading, b_list, proof, cta]) and fallback_body_text:
        return (fallback_body_text.strip() + tags_text).strip()

    lines: list[str] = []

    if p == "linkedin":
        # LinkedIn: simple, clean
        if hook:
            lines.append(hook.strip())

        if subheading:
            lines.append("")  # spacing
            lines.append(subheading.strip())

        if b_list:
            lines.append("")
            lines.append("What you get:")
            for b in b_list[:3]:
                lines.append(f"• {b}")

        if proof:
            lines.append("")
            lines.append(f"Proof: {proof.strip()}")

        if cta:
            lines.append("")
            lines.append(f"{cta.strip()}")

        final = "\n".join(lines).strip()
        return (final + tags_text).strip()

    # Facebook default
    if hook:
        # a tiny bit of energy, but not spammy
        lines.append(f"🚀 {hook.strip()}")

    if subheading:
        lines.append("")
        lines.append(subheading.strip())

    if b_list:
        lines.append("")
        lines.append("✅ What you get:")
        for b in b_list[:3]:
            lines.append(f"• {b}")

    if proof:
        lines.append("")
        lines.append(f"🧾 Proof: {proof.strip()}")

    if cta:
        lines.append("")
        lines.append(f"👉 {cta.strip()}")

    final = "\n".join(lines).strip()
    return (final + tags_text).strip()
