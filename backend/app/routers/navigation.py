"""
Navigation REST endpoint – takes a user position + product list,
returns an optimised A* path.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import Product, Shelf, ShelfImage
from ..models.schemas import (
    NavigateRequest, NavigateResponse, NavStep, ProductOut,
)
from ..services.pathfinding import multi_product_route, astar, path_distance
from ..services.kalman_fusion import get_tracker
from ..core.database import get_db

router = APIRouter(prefix="/api", tags=["Navigation"])


@router.post("/navigate", response_model=NavigateResponse)
async def navigate(body: NavigateRequest, db: AsyncSession = Depends(get_db)):
    """
    Generate a navigation path from the user's current fused position
    to one or more products. Supports product IDs or a text query.
    """
    tracker = get_tracker(body.session_id)
    start = tracker.position

    # Resolve products
    products = []
    if body.product_ids:
        result = await db.execute(
            select(Product).where(Product.id.in_(body.product_ids))
        )
        products = list(result.scalars().all())
    elif body.product_query:
        result = await db.execute(
            select(Product).where(
                Product.name.ilike(f"%{body.product_query}%")
            )
        )
        products = list(result.scalars().all())

    if not products:
        raise HTTPException(404, "No matching products found")

    # Get shelf positions for each product
    targets: list[tuple[float, float]] = []
    for p in products:
        if p.shelf_id is not None:
            shelf_result = await db.execute(
                select(Shelf).where(Shelf.id == p.shelf_id)
            )
            shelf = shelf_result.scalar_one_or_none()
            if shelf:
                targets.append((float(shelf.x), float(shelf.y)))
            else:
                targets.append((float(p.x_offset), 0.0))
        else:
            targets.append((float(p.x_offset), 0.0))

    # Compute path
    path_coords = multi_product_route(start, targets)
    if not path_coords:
        # Fallback: direct line
        path_coords = [start] + targets

    total_dist = path_distance(path_coords)

    # Find shelf image for the last target product
    shelf_image_url = None
    last_product = products[-1]
    if last_product.shelf_id is not None:
        img_result = await db.execute(
            select(ShelfImage)
            .where(ShelfImage.shelf_id == last_product.shelf_id)
            .order_by(ShelfImage.uploaded_at.desc())
            .limit(1)
        )
        img = img_result.scalar_one_or_none()
        if img:
            shelf_image_url = f"/static/shelf_images/{img.filename}"

    return NavigateResponse(
        path=[NavStep(x=x, y=y) for x, y in path_coords],
        distance=round(total_dist, 2),
        products=[ProductOut.model_validate(p) for p in products],
        shelf_image_url=shelf_image_url,
    )
