"""
Product & Shelf REST endpoints.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import Product, Shelf
from ..models.schemas import ProductCreate, ProductOut, ShelfCreate, ShelfOut
from ..core.database import get_db

logger = logging.getLogger("products")
router = APIRouter(prefix="/api", tags=["Products & Shelves"])


# ── Products ──────────────────────────────────────────────────────────────

@router.get("/products", response_model=list[ProductOut])
async def list_products(
    q: str = Query(default="", description="Search by name (partial)"),
    db: AsyncSession = Depends(get_db),
):
    logger.info("[PRODUCTS] 🔍 Search  q='%s'", q)
    stmt = select(Product)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    result = await db.execute(stmt)
    items = result.scalars().all()
    logger.info("[PRODUCTS] ✔ Found %d products", len(items))
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


@router.post("/shelves", response_model=ShelfOut, status_code=201)
async def create_shelf(body: ShelfCreate, db: AsyncSession = Depends(get_db)):
    s = Shelf(**body.model_dump())
    db.add(s)
    await db.commit()
    await db.refresh(s)
    # Register on pathfinding grid
    from ..services.pathfinding import register_obstacle
    register_obstacle(float(s.x), float(s.y), float(s.width), float(s.height))
    logger.info("[SHELVES] ✔ Created shelf id=%d  '%s'  at (%.1f, %.1f)  → obstacle registered",
                s.id, s.name, s.x, s.y)
    return s
