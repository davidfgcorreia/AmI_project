"""
Navigation REST endpoint – takes a user position + product list,
returns an optimised A* path.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.database import Product, Shelf
from ..models.schemas import NavigateRequest, NavigateResponse, NavStep, ProductOut
from ..services.kalman_fusion import get_tracker
from ..services.pathfinding import multi_product_route, astar, path_distance
from ..services.gateway_manager import get_positions as get_gateway_positions

logger = logging.getLogger("nav")

router = APIRouter(prefix="/api", tags=["Navigation"])


@router.get('/gateways')
async def get_gateways():
    """Return current BLE gateway positions (from runtime manager)."""
    return get_gateway_positions()


@router.post("/navigate", response_model=NavigateResponse)
async def navigate(body: NavigateRequest, db: AsyncSession = Depends(get_db)):
    """
    Generate a navigation path from the user's current fused position
    to one or more products. Supports product IDs or a text query.
    """
    tracker = get_tracker(body.session_id)
    start = tracker.position
    logger.info("[NAV] 🧭 Request  session=%s  start=(%.2f, %.2f)  product_ids=%s  query='%s'",
                body.session_id, start[0], start[1], body.product_ids, body.product_query or '')

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
        logger.warning("[NAV] ⚠ No products found for query")
        raise HTTPException(404, "No matching products found")

    logger.info("[NAV] 🛒 Found %d products: %s", len(products), [p.name for p in products])

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

    logger.info("[NAV] 🎯 Targets: %s", targets)

    # Compute path – multi_product_route returns (path, visit_order)
    path_coords, ordered_indices = multi_product_route(start, targets)
    if not path_coords:
        logger.warning("[NAV] ⚠ A* returned no path – using direct line")
        path_coords = [start] + targets
        ordered_indices = list(range(len(targets)))

    total_dist = path_distance(path_coords)
    logger.info("[NAV] ✔ Path: %d waypoints, %.2f m, visit order=%s",
                len(path_coords), total_dist, ordered_indices)

    # Return products sorted by the optimised visit order
    ordered_products = [products[i] for i in ordered_indices]

    return NavigateResponse(
        path=[NavStep(x=x, y=y) for x, y in path_coords],
        distance=round(total_dist, 2),
        products=[ProductOut.model_validate(p) for p in ordered_products],
        shelf_image_url=None,
    )
