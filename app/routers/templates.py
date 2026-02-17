import uuid, json
from datetime import datetime
from typing import Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from app.services.template_synthesizer import synthesize_template_from_examples
from app.database import get_db
from app.models.template import Template
import random

router = APIRouter(prefix="/templates", tags=["templates"])

# ✅ CREATE REQUEST
class TemplateCreateRequest(BaseModel):
    brand_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    shapes: Any
    canvasWidth: int
    canvasHeight: int
    backgroundImage: Optional[str] = None
    logoPlacement: Optional[Any] = None
    thumbnail_url: Optional[str] = None
    preview_url: Optional[str] = None


class SynthesizeTemplateReq(BaseModel):
    brand_id: Optional[str] = "neuroflow"
    canvas_width: Optional[int] = 1080
    canvas_height: Optional[int] = 1350

class TemplateUpdateRequest(BaseModel):
    brand_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None

    # ✅ allow updating the actual template content
    shapes: Optional[Any] = None
    canvasWidth: Optional[int] = None
    canvasHeight: Optional[int] = None
    backgroundImage: Optional[str] = None
    logoPlacement: Optional[Any] = None

    # ✅ thumbnail + preview updates
    thumbnail_url: Optional[str] = None
    preview_url: Optional[str] = None

@router.patch("/{template_id}")
def update_template(template_id: str, payload: TemplateUpdateRequest, db: Session = Depends(get_db)):
    tpl = db.query(Template).filter(Template.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")

    # ✅ update fields only if provided (PATCH semantics)
    if payload.brand_id is not None:
        tpl.brand_id = payload.brand_id

    if payload.name is not None:
        tpl.name = payload.name

    if payload.description is not None:
        tpl.description = payload.description

    # ✅ CRITICAL: persist shapes EXACTLY (includes customText, rotation, etc.)
    if payload.shapes is not None:
        try:
            tpl.shapes_json = json.dumps(payload.shapes, ensure_ascii=False)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid shapes JSON: {e}")

    if payload.canvasWidth is not None:
        tpl.canvas_width = str(int(payload.canvasWidth))

    if payload.canvasHeight is not None:
        tpl.canvas_height = str(int(payload.canvasHeight))

    if payload.backgroundImage is not None:
        tpl.background_image = payload.backgroundImage

    # logoPlacement: accept None to clear it
    if payload.logoPlacement is not None:
        try:
            tpl.logo_placement_json = json.dumps(payload.logoPlacement, ensure_ascii=False)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid logoPlacement JSON: {e}")

    if payload.thumbnail_url is not None:
        tpl.thumbnail_url = payload.thumbnail_url

    if payload.preview_url is not None:
        tpl.preview_url = payload.preview_url

    tpl.updated_at = datetime.utcnow()

    db.add(tpl)
    db.commit()
    db.refresh(tpl)

    return {"ok": True, "id": tpl.id}


# ✅ CREATE TEMPLATE
@router.post("")
def create_template(payload: TemplateCreateRequest, db: Session = Depends(get_db)):
    tid = str(uuid.uuid4())
    now = datetime.utcnow()

    row = Template(
        id=tid,
        brand_id=payload.brand_id,
        name=payload.name,
        description=payload.description,
        shapes_json=json.dumps(payload.shapes, ensure_ascii=False),
        canvas_width=str(payload.canvasWidth),
        canvas_height=str(payload.canvasHeight),
        background_image=payload.backgroundImage,
        logo_placement_json=json.dumps(payload.logoPlacement) if payload.logoPlacement else None,
        thumbnail_url=payload.thumbnail_url,
        preview_url=payload.preview_url,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()

    return {"ok": True, "id": tid}

# ✅ LIST TEMPLATES
@router.get("")
def list_templates(
    brand_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = select(Template).order_by(desc(Template.updated_at), desc(Template.created_at)).limit(limit)
    if brand_id:
        q = q.where(Template.brand_id == brand_id)

    rows = db.execute(q).scalars().all()

    out = []
    for t in rows:
        out.append({
            "id": t.id,
            "brand_id": t.brand_id,
            "name": t.name,
            "description": t.description,
            "shapes": json.loads(t.shapes_json or "[]"),
            "canvasWidth": int(t.canvas_width),
            "canvasHeight": int(t.canvas_height),
            "backgroundImage": t.background_image,
            "logoPlacement": json.loads(t.logo_placement_json) if t.logo_placement_json else None,
            "thumbnail_url": t.thumbnail_url,
            "preview_url": t.preview_url,
            "createdAt": t.created_at.isoformat() if t.created_at else None,
            "updatedAt": t.updated_at.isoformat() if t.updated_at else None,
        })
    return out


# ✅ GET SINGLE TEMPLATE
@router.get("/{template_id}")
def get_template(template_id: str, db: Session = Depends(get_db)):
    tpl = db.query(Template).filter(Template.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")

    return {
        "id": tpl.id,
        "brand_id": tpl.brand_id,
        "name": tpl.name,
        "description": tpl.description,
        "backgroundImage": tpl.background_image,
        "canvasWidth": int(tpl.canvas_width) if tpl.canvas_width is not None else None,
        "canvasHeight": int(tpl.canvas_height) if tpl.canvas_height is not None else None,
        "shapes": json.loads(tpl.shapes_json or "[]"),
        "logoPlacement": json.loads(tpl.logo_placement_json) if tpl.logo_placement_json else None,
        "thumbnail_url": tpl.thumbnail_url,
        "preview_url": tpl.preview_url,
        "createdAt": tpl.created_at.isoformat() if tpl.created_at else None,
        "updatedAt": tpl.updated_at.isoformat() if tpl.updated_at else None,
    }


# ✅ DELETE TEMPLATE
@router.delete("/{template_id}")
def delete_template(template_id: str, db: Session = Depends(get_db)):
    """Delete a template"""
    tpl = db.query(Template).filter(Template.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    
    db.delete(tpl)
    db.commit()
    
    return {"ok": True, "id": template_id}


# ✅ SYNTHESIZE AND SAVE
@router.post("/synthesize-and-save")
def synthesize_and_save_template(
    payload: SynthesizeTemplateReq,
    db: Session = Depends(get_db),
):
    brand_id = payload.brand_id or "neuroflow"
    canvas_width = payload.canvas_width or 1080
    canvas_height = payload.canvas_height or 1350

    templates = db.query(Template).filter(Template.shapes_json.isnot(None)).limit(50).all()
    if len(templates) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 templates in DB")

    picked = random.sample(templates, k=min(2, len(templates)))

    example_templates = []
    used_ids = []

    for t in picked:
        used_ids.append(t.id)

        try:
            shapes = json.loads(t.shapes_json or "[]")
        except Exception:
            shapes = []

        logo = None
        if t.logo_placement_json:
            try:
                logo = json.loads(t.logo_placement_json)
            except Exception:
                logo = None

        example_templates.append(
            {
                "id": t.id,
                "canvasWidth": int(t.canvas_width) if t.canvas_width else canvas_width,
                "canvasHeight": int(t.canvas_height) if t.canvas_height else canvas_height,
                "shapes": shapes,
                "backgroundImage": t.background_image,
                "logoPlacement": logo,
            }
        )

    synthesized = synthesize_template_from_examples(
        example_templates=example_templates,
        brand_id=brand_id,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    )

    shapes_out = synthesized.get("shapes") if isinstance(synthesized, dict) else None
    if not isinstance(shapes_out, list) or len(shapes_out) == 0:
        raise HTTPException(status_code=400, detail="Synthesis failed: no shapes returned")

    new_id = str(uuid.uuid4())
    name = (synthesized.get("name") if isinstance(synthesized, dict) else None) or "AI Premium Template"
    description = f"Generated from templates: {', '.join(used_ids)}"

    new_tpl = Template(
        id=new_id,
        brand_id=brand_id,
        name=name,
        description=description,
        shapes_json=json.dumps(shapes_out, ensure_ascii=False),
        canvas_width=str(int(synthesized.get("canvasWidth") or canvas_width)),
        canvas_height=str(int(synthesized.get("canvasHeight") or canvas_height)),
        background_image=synthesized.get("backgroundImage"),
        logo_placement_json=json.dumps(synthesized.get("logoPlacement"), ensure_ascii=False)
        if synthesized.get("logoPlacement")
        else None,
        thumbnail_url=synthesized.get("thumbnail_url"),
        preview_url=synthesized.get("preview_url"),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(new_tpl)
    db.commit()
    db.refresh(new_tpl)

    return {
        "ok": True,
        "template": {
            "id": new_tpl.id,
            "brand_id": new_tpl.brand_id,
            "name": new_tpl.name,
            "description": new_tpl.description,
            "backgroundImage": new_tpl.background_image,
            "canvasWidth": int(new_tpl.canvas_width),
            "canvasHeight": int(new_tpl.canvas_height),
            "shapes": json.loads(new_tpl.shapes_json or "[]"),
            "logoPlacement": json.loads(new_tpl.logo_placement_json) if new_tpl.logo_placement_json else None,
            "thumbnail_url": new_tpl.thumbnail_url,
            "preview_url": new_tpl.preview_url,
            "createdAt": new_tpl.created_at.isoformat() if new_tpl.created_at else None,
            "updatedAt": new_tpl.updated_at.isoformat() if new_tpl.updated_at else None,
        },
        "used_templates": used_ids,
    }