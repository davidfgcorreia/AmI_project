"""
Shelf image upload + YOLO analysis endpoint.
"""
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import ShelfImage, Shelf
from ..models.schemas import ShelfAnalysis
from ..services.cv_detection import analyse_shelf_image
from ..core.database import get_db
import json

router = APIRouter(prefix="/api", tags=["Computer Vision"])


@router.post("/shelves/{shelf_id}/scan", response_model=ShelfAnalysis)
async def scan_shelf(
    shelf_id: int,
    highlight: str = Form(default=""),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a shelf photo → run YOLO detection → return detections
    with optional product highlighting.
    """
    # Verify shelf exists
    result = await db.execute(select(Shelf).where(Shelf.id == shelf_id))
    shelf = result.scalar_one_or_none()
    if not shelf:
        raise HTTPException(404, "Shelf not found")

    image_bytes = await image.read()
    analysis = analyse_shelf_image(
        image_bytes, shelf_id,
        highlight_label=highlight or None,
    )

    # Persist record
    record = ShelfImage(
        shelf_id=shelf_id,
        filename=analysis.get("highlighted_filename") or analysis["filename"],
        analysis_json=json.dumps(analysis["detections"]),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    img_file = analysis.get("highlighted_filename") or analysis["filename"]

    return ShelfAnalysis(
        shelf_id=shelf_id,
        detections=analysis["detections"],
        image_url=f"/static/shelf_images/{img_file}",
    )
