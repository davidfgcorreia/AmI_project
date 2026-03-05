"""
Intelligent Retail Ecosystem – FastAPI Backend
═══════════════════════════════════════════════
Central server handling:
  • BLE trilateration + IMU/PDR Kalman fusion
  • A* pathfinding with multi-product routing
  • YOLO shelf detection & highlighting
  • MQTT listener for ESP32 gateway data
  • WebSocket real-time position streaming
  • SQLite product/shelf database
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core.config import STATIC_DIR, SHELF_IMG_DIR
from .core.database import engine, SessionLocal, get_db  # noqa: F401
from .models.database import Base

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s  %(message)s")
logger = logging.getLogger("ire")


# ── Lifespan ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("═══════════════════════════════════════════════")
    logger.info("  Intelligent Retail Ecosystem – starting up")
    logger.info("═══════════════════════════════════════════════")
    logger.info("Creating database tables …")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed demo data if empty
    await _seed_demo_data()

    # Register all shelves as pathfinding obstacles
    await _register_shelf_obstacles()

    # Start MQTT listener in background
    from .services.mqtt_client import mqtt_listener
    mqtt_task = asyncio.create_task(mqtt_listener())

    from .core.config import STORE_WIDTH, STORE_HEIGHT, GRID_RESOLUTION, GATEWAY_POSITIONS
    logger.info("Store: %.0f×%.0f m  grid=%.1fm  gateways=%s",
                STORE_WIDTH, STORE_HEIGHT, GRID_RESOLUTION,
                list(GATEWAY_POSITIONS.keys()))
    logger.info("✔  Backend ready – listening on http://0.0.0.0:8000")
    yield

    # Shutdown
    mqtt_task.cancel()
    await engine.dispose()


# ── App ──
app = FastAPI(
    title="Intelligent Retail Ecosystem",
    version="1.0.0",
    description="AmI backend – BLE fusion, navigation, CV, real-time tracking",
    lifespan=lifespan,
)

# CORS – allow PWA on any port during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (shelf images)
SHELF_IMG_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── Routers ──
from .routers.products import router as products_router    # noqa: E402
from .routers.navigation import router as nav_router       # noqa: E402
from .routers.vision import router as vision_router        # noqa: E402
from .routers.tracking import router as tracking_router    # noqa: E402

app.include_router(products_router)
app.include_router(nav_router)
app.include_router(vision_router)
app.include_router(tracking_router)


# ── Health check ──
@app.get("/health")
async def health():
    return {"status": "ok", "service": "Intelligent Retail Ecosystem"}


# ── Demo seed ──
async def _seed_demo_data():
    """Insert sample shelves & products if the DB is empty."""
    from .models.database import Product, Shelf
    from sqlalchemy import select

    async with SessionLocal() as db:
        result = await db.execute(select(Shelf).limit(1))
        if result.scalar_one_or_none():
            return  # already seeded

        shelves = [
            Shelf(name="Aisle 1 – Left",   aisle="1", x=2.0,  y=2.0,  width=1.2, height=2.0),
            Shelf(name="Aisle 1 – Right",  aisle="1", x=4.0,  y=2.0,  width=1.2, height=2.0),
            Shelf(name="Aisle 2 – Left",   aisle="2", x=2.0,  y=5.0,  width=1.2, height=2.0),
            Shelf(name="Aisle 2 – Right",  aisle="2", x=4.0,  y=5.0,  width=1.2, height=2.0),
            Shelf(name="Aisle 3 – Left",   aisle="3", x=7.0,  y=2.0,  width=1.2, height=2.0),
            Shelf(name="Aisle 3 – Right",  aisle="3", x=9.0,  y=2.0,  width=1.2, height=2.0),
            Shelf(name="Aisle 4 – Left",   aisle="4", x=7.0,  y=5.0,  width=1.2, height=2.0),
            Shelf(name="Aisle 4 – Right",  aisle="4", x=9.0,  y=5.0,  width=1.2, height=2.0),
            Shelf(name="End-Cap North",     aisle="EC", x=5.5, y=8.5, width=2.0, height=1.5),
        ]
        db.add_all(shelves)
        await db.flush()

        products = [
            Product(name="KALLAX Shelf Unit",       category="Furniture",  price=49.99,  shelf_id=1, shelf_level=1),
            Product(name="BILLY Bookcase",           category="Furniture",  price=39.99,  shelf_id=1, shelf_level=2),
            Product(name="MALM Desk",                category="Furniture",  price=149.99, shelf_id=2, shelf_level=1),
            Product(name="LACK Coffee Table",        category="Furniture",  price=9.99,   shelf_id=2, shelf_level=2),
            Product(name="LED Desk Lamp",            category="Lighting",   price=19.99,  shelf_id=3, shelf_level=3),
            Product(name="TERTIAL Work Lamp",        category="Lighting",   price=12.99,  shelf_id=3, shelf_level=2),
            Product(name="FEJKA Artificial Plant",   category="Decoration", price=5.99,   shelf_id=4, shelf_level=1),
            Product(name="SMYCKA Artificial Flower",category="Decoration", price=3.99,   shelf_id=4, shelf_level=2),
            Product(name="KORKEN Jar with lid",      category="Kitchen",    price=4.99,   shelf_id=5, shelf_level=1),
            Product(name="VARDAGEN Casserole",       category="Kitchen",    price=29.99,  shelf_id=5, shelf_level=3),
            Product(name="365+ Frying Pan",          category="Kitchen",    price=14.99,  shelf_id=6, shelf_level=2),
            Product(name="DINERA Plate Set",         category="Kitchen",    price=24.99,  shelf_id=6, shelf_level=1),
            Product(name="POÄNG Armchair",           category="Furniture",  price=99.99,  shelf_id=7, shelf_level=1),
            Product(name="STRANDMON Wing Chair",     category="Furniture",  price=279.99, shelf_id=7, shelf_level=1),
            Product(name="KIVIK Sofa Cover",         category="Textile",    price=89.99,  shelf_id=8, shelf_level=2),
            Product(name="GURLI Throw",              category="Textile",    price=4.99,   shelf_id=8, shelf_level=3),
            Product(name="RIBBA Frame 50x70",        category="Decoration", price=12.99,  shelf_id=9, shelf_level=1),
            Product(name="SILVERHÖJDEN Frame",       category="Decoration", price=7.99,   shelf_id=9, shelf_level=2),
        ]
        db.add_all(products)
        await db.commit()
        logger.info("Seeded %d shelves and %d products", len(shelves), len(products))


async def _register_shelf_obstacles():
    """Load all shelves from DB and mark them on the pathfinding grid."""
    from .models.database import Shelf
    from .services.pathfinding import register_obstacle
    from sqlalchemy import select

    async with SessionLocal() as db:
        result = await db.execute(select(Shelf))
        shelves = result.scalars().all()

    for s in shelves:
        register_obstacle(float(s.x), float(s.y), float(s.width), float(s.height))
    logger.info("Registered %d shelf obstacles on pathfinding grid", len(shelves))
