"""
Intelligent Retail Ecosystem - FastAPI Backend
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
    logger.info("  Intelligent Retail Ecosystem - starting up")
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
    logger.info("✔  Backend ready - listening on http://0.0.0.0:8000")
    yield

    # Shutdown
    mqtt_task.cancel()
    await engine.dispose()


# ── App ──
app = FastAPI(
    title="Intelligent Retail Ecosystem",
    version="1.0.0",
    description="AmI backend - BLE fusion, navigation, CV, real-time tracking",
    lifespan=lifespan,
)

# CORS - allow PWA on any port during development
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
from .routers.tracking import router as tracking_router    # noqa: E402
from .routers.gateways import router as gateways_router    # noqa: E402
app.include_router(products_router)
app.include_router(nav_router)
app.include_router(tracking_router)
app.include_router(gateways_router)


# ── Health check ──
@app.get("/health")
async def health():
    return {"status": "ok", "service": "Intelligent Retail Ecosystem"}


# ── Supermarket seed ──
async def _seed_demo_data():
    """Seed shelves + products from supermarket.json if the DB is empty.
    Delete backend/store.db to re-seed from scratch.
    """
    import json
    from .models.database import Product, Shelf
    from .core.config import SUPERMARKET_JSON
    from sqlalchemy import select

    async with SessionLocal() as db:
        result = await db.execute(select(Shelf).limit(1))
        if result.scalar_one_or_none():
            return  # already seeded

        # ── Load product catalogue ──
        if not SUPERMARKET_JSON.exists():
            logger.warning("supermarket.json not found at %s - skipping seed", SUPERMARKET_JSON)
            return

        with open(SUPERMARKET_JSON, "r", encoding="utf-8") as f:
            catalogue = json.load(f)

        # ── Shelf layout: 3 rows × 5 columns = 15 shelves (one per category) ──
        # Store is 12×10 m, entrance at y=0, shelves placed in a supermarket grid.
        SHELF_DEFS = [
            # (category_key,           display_name,            aisle, x,    y   )
            ("dairy",                  "Dairy & Eggs",           "1",   1.5,  2.5),
            ("juices",                 "Juices & Drinks",        "1",   4.0,  2.5),
            ("bakery",                 "Bakery",                 "1",   6.5,  2.5),
            ("meat_and_fish",          "Meat & Fish",            "1",   9.0,  2.5),
            ("beverages",              "Beverages",              "1",  11.0,  2.5),
            ("fruits",                 "Fresh Fruits",           "2",   1.5,  5.5),
            ("vegetables",             "Fresh Vegetables",       "2",   4.0,  5.5),
            ("snacks_and_chips",       "Snacks & Chips",         "2",   6.5,  5.5),
            ("cereals_and_breakfast",  "Cereals & Breakfast",    "2",   9.0,  5.5),
            ("frozen_foods",           "Frozen Foods",           "2",  11.0,  5.5),
            ("canned_goods",           "Canned Goods",           "3",   1.5,  8.0),
            ("condiments_and_sauces",  "Condiments & Sauces",    "3",   4.0,  8.0),
            ("pasta_and_rice",         "Pasta & Rice",           "3",   6.5,  8.0),
            ("personal_care",          "Personal Care",          "3",   9.0,  8.0),
            ("cleaning_products",      "Cleaning Products",      "3",  11.0,  8.0),
        ]

        # Price ranges per category (min, max) in €
        PRICE_RANGES = {
            "dairy":                 (0.99,  5.99),
            "juices":                (1.29,  3.99),
            "bakery":                (0.99,  5.99),
            "meat_and_fish":         (3.99, 29.99),
            "beverages":             (0.89, 15.99),
            "fruits":                (0.49,  3.99),
            "vegetables":            (0.39,  2.99),
            "snacks_and_chips":      (0.99,  4.99),
            "cereals_and_breakfast": (1.99,  6.99),
            "frozen_foods":          (2.99,  8.99),
            "canned_goods":          (0.79,  3.99),
            "condiments_and_sauces": (1.49,  6.99),
            "pasta_and_rice":        (0.99,  3.99),
            "personal_care":         (1.99, 12.99),
            "cleaning_products":     (1.99,  9.99),
        }

        def make_price(category_key: str, product_name: str) -> float:
            lo, hi = PRICE_RANGES.get(category_key, (0.99, 9.99))
            # Deterministic pseudo-random price from product name hash
            t = (hash(product_name) & 0xFFFF) / 0xFFFF
            return round(lo + t * (hi - lo), 2)

        # ── Insert shelves ──
        shelves = []
        for cat_key, display_name, aisle, x, y in SHELF_DEFS:
            shelves.append(Shelf(
                name=display_name, aisle=aisle,
                x=x, y=y, width=1.2, height=0.5,
            ))
        db.add_all(shelves)
        await db.flush()  # assign IDs

        # ── Insert products ──
        products = []
        for shelf_obj, (cat_key, display_name, *_) in zip(shelves, SHELF_DEFS):
            items = catalogue.get(cat_key, [])
            for idx, item_name in enumerate(items):
                products.append(Product(
                    name=item_name,
                    category=display_name,
                    price=make_price(cat_key, item_name),
                    shelf_id=shelf_obj.id,
                    shelf_level=(idx % 4) + 1,  # cycle levels 1-4
                ))
        db.add_all(products)
        await db.commit()
        logger.info("Seeded %d shelves and %d products from supermarket.json",
                    len(shelves), len(products))


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
