# backend/app/services/image_generator.py
from __future__ import annotations

import os
import uuid
import mimetypes
from typing import Tuple, Optional

import boto3
from botocore.client import Config


def _spaces_client():
    key = os.getenv("DO_SPACES_KEY", "").strip()
    secret = os.getenv("DO_SPACES_SECRET", "").strip()
    endpoint = os.getenv("DO_SPACES_ENDPOINT", "").strip()
    region = os.getenv("DO_SPACES_REGION", "fra1").strip()

    if not key or not secret or not endpoint:
        raise RuntimeError("Missing DO_SPACES_KEY / DO_SPACES_SECRET / DO_SPACES_ENDPOINT in backend .env")

    session = boto3.session.Session()
    return session.client(
        "s3",
        region_name=region,
        endpoint_url=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        config=Config(signature_version="s3v4"),
    )


def _upload_file_to_spaces(local_path: str, key: str) -> str:
    bucket = os.getenv("DO_SPACES_BUCKET", "").strip()
    public_base = os.getenv("DO_SPACES_PUBLIC_BASE", "").strip()

    if not bucket:
        raise RuntimeError("Missing DO_SPACES_BUCKET in backend .env")
    if not public_base:
        raise RuntimeError("Missing DO_SPACES_PUBLIC_BASE in backend .env")

    content_type, _ = mimetypes.guess_type(local_path)
    content_type = content_type or "application/octet-stream"

    client = _spaces_client()
    client.upload_file(
        local_path,
        bucket,
        key,
        ExtraArgs={
            "ACL": "public-read",
            "ContentType": content_type,
        },
    )

    return f"{public_base.rstrip('/')}/{key}"


def _make_placeholder_png(output_path: str, text: str) -> None:
    """
    Placeholder image generator (fast unblock).
    Requires: pip install pillow
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1024, 1024), color=(245, 245, 245))
    draw = ImageDraw.Draw(img)

    msg = (text or "AI IMAGE").strip()[:140]
    draw.text((40, 40), msg, fill=(40, 40, 40))
    draw.rectangle([40, 120, 984, 984], outline=(140, 140, 140), width=4)
    draw.text((60, 150), "Placeholder (swap with real image model later)", fill=(90, 90, 90))

    img.save(output_path, format="PNG")


def generate_image_and_store(
    prompt: str,
    brand_id: str,
    platform: str,
    content_item_id: str,
) -> Tuple[str, str]:
    """
    Returns: (media_url, media_mime)
    Generates an image (placeholder) then uploads to Spaces.
    """
    tmp_dir = os.path.join(os.getcwd(), "tmp_media")
    os.makedirs(tmp_dir, exist_ok=True)

    filename = f"{content_item_id}_{uuid.uuid4().hex}.png"
    local_path = os.path.join(tmp_dir, filename)

    # Generate (placeholder)
    _make_placeholder_png(local_path, prompt)

    # Upload
    key = f"generated/{brand_id}/{platform}/{filename}"
    media_url = _upload_file_to_spaces(local_path, key)

    # Cleanup
    try:
        os.remove(local_path)
    except Exception:
        pass

    return media_url, "image/png"


# ✅ This is the missing function your router imports.
def generate_image_for_content_item(
    prompt: str,
    brand_id: str,
    platform: str,
    content_item_id: str,
) -> dict:
    """
    Compatibility wrapper for older code:
    returns dict with url + mime
    """
    url, mime = generate_image_and_store(
        prompt=prompt,
        brand_id=brand_id,
        platform=platform,
        content_item_id=content_item_id,
    )
    return {"media_url": url, "media_mime": mime}
