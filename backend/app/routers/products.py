"""
Product & Shelf REST endpoints.
"""
import logging
from difflib import SequenceMatcher

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import Product, Shelf
from ..models.schemas import ProductCreate, ProductOut, ShelfCreate, ShelfOut
from ..core.database import get_db


def _similarity(a: str, b: str) -> float:
    """Fuzzy match score combining substring ratio and word overlap."""
    al, bl = a.lower(), b.lower()
    base = SequenceMatcher(None, al, bl).ratio()
    a_words = set(al.split())
    b_words = set(bl.split())
    overlap = len(a_words & b_words) / len(a_words) if a_words else 0
    return max(base, overlap)

logger = logging.getLogger("products")
router = APIRouter(prefix="/api", tags=["Products & Shelves"])


# ── Products ──────────────────────────────────────────────────────────────

@router.get("/products", response_model=list[ProductOut])
async def list_products(
    q: str = Query(default="", description="Search by name (fuzzy)"),
    db: AsyncSession = Depends(get_db),
):
    logger.info("[PRODUCTS] Search  q='%s'", q)
    result = await db.execute(select(Product))
    all_products = result.scalars().all()

    if not q:
        return all_products

    # Score every product by fuzzy similarity, return top matches
    scored = [(p, _similarity(q, p.name)) for p in all_products]
    scored.sort(key=lambda x: x[1], reverse=True)

    # Return products above a minimum threshold, up to 10
    MIN_SCORE = 0.25
    items = [p for p, score in scored[:10] if score >= MIN_SCORE]
    logger.info("[PRODUCTS] Found %d products for q='%s' (top score=%.2f)",
                len(items), q, scored[0][1] if scored else 0)
    return items


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Product not found")
    return p


@router.post("/products", response_model=ProductOut, status_code=201)
async def create_product(body: ProductCreate, db: AsyncSession = Depends(get_db)):
    logger.info("[PRODUCTS] ➕ Create  name='%s'  shelf=%s", body.name, body.shelf_id)
    p = Product(**body.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    logger.info("[PRODUCTS] ✔ Created  id=%d  name='%s'", p.id, p.name)
    return p


@router.put("/products/{product_id}", response_model=ProductOut)
async def update_product(product_id: int, body: ProductCreate,
                         db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Product not found")
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    await db.commit()
    await db.refresh(p)
    return p


@router.delete("/products/{product_id}", status_code=204)
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Product not found")
    await db.delete(p)
    await db.commit()


# ── Shelves ───────────────────────────────────────────────────────────────

@router.get("/shelves", response_model=list[ShelfOut])
async def list_shelves(db: AsyncSession = Depends(get_db)):
    logger.info("[SHELVES] 📋 Listing all shelves")
    result = await db.execute(select(Shelf))
    items = result.scalars().all()
    logger.info("[SHELVES] ✔ Returned %d shelves", len(items))
    return items


async def _rebuild_obstacle_grid(db: AsyncSession):
    """Clear and re-register all shelf obstacles on the pathfinding grid."""
    from ..services.pathfinding import register_obstacle, clear_obstacles
    clear_obstacles()
    result = await db.execute(select(Shelf))
    for s in result.scalars().all():
        register_obstacle(float(s.x), float(s.y), float(s.width), float(s.height))


@router.post("/shelves", response_model=ShelfOut, status_code=201)
async def create_shelf(body: ShelfCreate, db: AsyncSession = Depends(get_db)):
    s = Shelf(**body.model_dump())
    db.add(s)
    await db.commit()
    await db.refresh(s)
    await _rebuild_obstacle_grid(db)
    logger.info("[SHELVES] Created shelf id=%d '%s' at (%.1f, %.1f)", s.id, s.name, s.x, s.y)
    return s


@router.put("/shelves/{shelf_id}", response_model=ShelfOut)
async def update_shelf(shelf_id: int, body: ShelfCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Shelf).where(Shelf.id == shelf_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Shelf not found")
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    await db.commit()
    await db.refresh(s)
    await _rebuild_obstacle_grid(db)
    return s


@router.delete("/shelves/{shelf_id}", status_code=204)
async def delete_shelf(shelf_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Shelf).where(Shelf.id == shelf_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Shelf not found")
    # Unassign products from this shelf
    result = await db.execute(select(Product).where(Product.shelf_id == shelf_id))
    for p in result.scalars().all():
        p.shelf_id = None
    await db.delete(s)
    await db.commit()
    await _rebuild_obstacle_grid(db)
