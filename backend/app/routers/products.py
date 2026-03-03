"""
Product & Shelf REST endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import Product, Shelf
from ..models.schemas import ProductCreate, ProductOut, ShelfCreate, ShelfOut
from ..core.database import get_db

router = APIRouter(prefix="/api", tags=["Products & Shelves"])


# ── Products ──────────────────────────────────────────────────────────────

@router.get("/products", response_model=list[ProductOut])
async def list_products(
    q: str = Query(default="", description="Search by name (partial)"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Product)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Product not found")
    return p


@router.post("/products", response_model=ProductOut, status_code=201)
async def create_product(body: ProductCreate, db: AsyncSession = Depends(get_db)):
    p = Product(**body.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
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
    result = await db.execute(select(Shelf))
    return result.scalars().all()


@router.post("/shelves", response_model=ShelfOut, status_code=201)
async def create_shelf(body: ShelfCreate, db: AsyncSession = Depends(get_db)):
    s = Shelf(**body.model_dump())
    db.add(s)
    await db.commit()
    await db.refresh(s)
    # Register on pathfinding grid
    from ..services.pathfinding import register_obstacle
    register_obstacle(float(s.x), float(s.y), float(s.width), float(s.height))
    return s
