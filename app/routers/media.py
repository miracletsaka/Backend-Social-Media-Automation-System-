# backend/app/routers/media.py
from __future__ import annotations

import base64
import os
import uuid
from datetime import datetime
from typing import Any, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.content_item import ContentItem
from app.services.state_machine import ensure_transition
from app.services.spaces_storage import upload_bytes_to_spaces

router = APIRouter(prefix="/media", tags=["media"])


def _parse_ids(payload: dict) -> List[uuid.UUID]:
    one = payload.get("content_item_id")
    many = payload.get("content_item_ids")

    if one and isinstance(one, str):
        try:
            return [uuid.UUID(one)]
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid content_item_id")

    if many and isinstance(many, list):
        out: List[uuid.UUID] = []
        for x in many:
            try:
                out.append(uuid.UUID(str(x)))
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid UUID in content_item_ids")
        if not out:
            raise HTTPException(status_code=400, detail="content_item_ids is empty")
        return out

    raise HTTPException(status_code=400, detail="Provide content_item_id or content_item_ids")


def _apply_make_result_to_item(
    item: ContentItem,
    make_data: dict,
) -> tuple[Optional[str], Optional[str]]:
    """
    Make must return either:
      - media_url
      OR
      - file_base64 + mime_type (backend uploads to Spaces)
    """
    media_type = (make_data.get("media_type") or item.content_type or "").strip().lower()  # image|video
    media_url = (make_data.get("media_url") or "").strip() or None
    thumb_url = (make_data.get("thumbnail_url") or "").strip() or None

    uploaded_media_url: Optional[str] = None
    uploaded_thumb_url: Optional[str] = None

    if not media_url:
        file_b64 = (make_data.get("file_base64") or "").strip()
        mime = (make_data.get("mime_type") or "").strip()
        if not file_b64 or not mime:
            raise ValueError("Make must return media_url OR (file_base64 + mime_type)")

        try:
            raw = base64.b64decode(file_b64)
        except Exception:
            raise ValueError("file_base64 is not valid base64")

        ext = (make_data.get("filename_ext") or ("png" if mime == "image/png" else "bin")).strip()

        uploaded_media_url = upload_bytes_to_spaces(
            content=raw,
            content_type=mime,
            key_prefix=f"content/{media_type or 'media'}",
            filename_ext=ext,
        )

        # optional thumbnail
        t_b64 = (make_data.get("thumbnail_base64") or "").strip()
        t_mime = (make_data.get("thumbnail_mime_type") or "").strip()
        if t_b64 and t_mime:
            try:
                t_raw = base64.b64decode(t_b64)
                t_ext = (make_data.get("thumbnail_ext") or "jpg").strip()
                uploaded_thumb_url = upload_bytes_to_spaces(
                    content=t_raw,
                    content_type=t_mime,
                    key_prefix="content/thumbnails",
                    filename_ext=t_ext,
                )
            except Exception:
                uploaded_thumb_url = None

    final_media_url = media_url or uploaded_media_url
    final_thumb_url = thumb_url or uploaded_thumb_url

    if not final_media_url:
        raise ValueError("Could not determine media_url")

    item.media_type = media_type or item.media_type
    item.media_url = final_media_url
    item.thumbnail_url = final_thumb_url
    item.media_provider = "spaces"  # or "openai" if you decide to store openai urls
    item.media_caption = (make_data.get("media_caption") or "").strip() or item.media_caption

    return final_media_url, final_thumb_url


@router.post("/generate")
def generate_media_for_items(payload: dict, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    UI calls this to generate media.
    NO callback endpoint required.

    Backend will:
      - set item -> GENERATING
      - call Make webhook (MAKE_MEDIA_WEBHOOK_URL)
      - Make returns JSON with media_url (or base64)
      - backend saves media_url and moves item -> PENDING_APPROVAL
    """
    make_url = (os.getenv("MAKE_MEDIA_WEBHOOK_URL") or "").strip()
    if not make_url:
        raise HTTPException(status_code=500, detail="MAKE_MEDIA_WEBHOOK_URL is not set in backend .env")

    make_api_key = (os.getenv("MAKE_API_KEY") or "").strip()
    if not make_api_key:
        raise HTTPException(status_code=500, detail="MAKE_API_KEY is not set in backend .env")

    ids = _parse_ids(payload)

    items = db.execute(select(ContentItem).where(ContentItem.id.in_(ids))).scalars().all()
    if not items:
        raise HTTPException(status_code=404, detail="No items found")

    now = datetime.utcnow()
    sent = 0
    updated = 0
    skipped: list[dict[str, Any]] = []

    for it in items:
        ct = (it.content_type or "").lower().strip()
        if ct not in ("image", "video"):
            skipped.append({"id": str(it.id), "reason": f"Not image/video: {it.content_type}"})
            continue

        # Move -> GENERATING
        try:
            ensure_transition(it.status, "GENERATING")
        except Exception:
            pass
        it.status = "GENERATING"
        it.updated_at = now
        it.last_error = None
        db.commit()

        prompt = (it.body_text or it.title or "").strip() or "Generate a social media visual for this post."

        # Call Make and WAIT for response
        try:
            with httpx.Client(timeout=120.0) as client:
                r = client.post(
                    make_url,
                    json={
                        "content_item_id": str(it.id),
                        "brand_id": it.brand_id,
                        "platform": it.platform,
                        "content_type": ct,
                        "status":it.status,
                        "prompt": prompt,
                    },
                    headers={
                        "Content-Type": "application/json",
                        "x-make-apikey": make_api_key,
                    },
                )

            if r.status_code >= 300:
                it.status = "FAILED"
                it.last_error = f"Make webhook error {r.status_code}: {r.text}"
                it.updated_at = now
                db.commit()
                skipped.append({"id": str(it.id), "reason": it.last_error})
                continue

            sent += 1

            make_data = r.json() if r.text else {}
            if not isinstance(make_data, dict):
                raise ValueError("Make response must be JSON object")

            # Apply result to item (media_url or base64)
            try:
                _apply_make_result_to_item(it, make_data)
            except Exception as e:
                it.status = "FAILED"
                it.last_error = f"Bad Make response: {e}"
                it.updated_at = now
                db.commit()
                skipped.append({"id": str(it.id), "reason": it.last_error})
                continue

            # Move -> PENDING_APPROVAL
            try:
                ensure_transition(it.status, "PENDING_APPROVAL")
            except Exception:
                pass
            it.status = "PENDING_APPROVAL"
            it.updated_at = now
            it.last_error = None
            db.commit()
            updated += 1

        except Exception as e:
            it.status = "FAILED"
            it.last_error = f"Make exception: {e}"
            it.updated_at = now
            db.commit()
            skipped.append({"id": str(it.id), "reason": str(e)})
            continue

    return {"sent": sent, "updated": updated, "skipped": len(skipped), "skipped_items": skipped}
