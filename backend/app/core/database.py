"""
Database session factory - shared dependency, avoids circular imports.
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from .config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    """FastAPI dependency - yields an async DB session."""
    async with SessionLocal() as session:
        yield session
