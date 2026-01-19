# backend/app/services/media_generator.py
from __future__ import annotations

import os
import uuid
from typing import Literal, Optional

MediaType = Literal["image", "video"]


def generate_media(
    *,
    brand_id: str,
    platform: str,
    content_type: str,
    prompt: str,
) -> dict:
    """
    V1: returns a media_url you can post via Make.
    Start with STUB mode so the pipeline works end-to-end.
    Later: replace with real generator + storage upload.

    Returns:
      {
        "media_url": "...",
        "media_type": "image" | "video",
        "thumbnail_url": "...optional"
      }
    """

    # V1: stub mode
    mode = os.getenv("MEDIA_GENERATION_MODE", "stub").lower().strip()
    ct = (content_type or "").lower().strip()

    if ct not in ("image", "video"):
        raise ValueError(f"Unsupported media content_type: {content_type}")

    if mode == "stub":
        # Public placeholder URLs (safe for testing Make + UI flow)
        # image -> placehold.co
        # video -> sample-videos.com (or any public mp4)
        if ct == "image":
            return {
                "media_url": f"https://placehold.co/1080x1080/png?text={brand_id}-{platform}-{uuid.uuid4().hex[:6]}",
                "media_type": "image",
                "thumbnail_url": None,
            }
        else:
            return {
                "media_url": "https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4",
                "media_type": "video",
                "thumbnail_url": "https://placehold.co/1280x720/png?text=Video+Thumb",
            }

    raise ValueError(f"Unknown MEDIA_GENERATION_MODE: {mode}")
