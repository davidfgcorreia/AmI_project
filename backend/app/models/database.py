"""
SQLAlchemy models – Product, Shelf, ShelfImage, NavigationSession.

Uses SQLAlchemy 2.0 Mapped[] annotations so that Pyright / type checkers
correctly infer Python types (float, int, str, …) instead of Column[Unknown].
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship,
)


class Base(DeclarativeBase):
    pass


class Shelf(Base):
    __tablename__ = "shelves"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))          # e.g. "Aisle 3 – Left"
    aisle: Mapped[str] = mapped_column(String(60))
    x: Mapped[float] = mapped_column()                      # centre-point (m)
    y: Mapped[float] = mapped_column()
    width: Mapped[float] = mapped_column(default=1.0)       # metres
    height: Mapped[float] = mapped_column(default=2.0)      # shelf physical height
    created_at: Mapped[Optional[datetime]] = mapped_column(insert_default=datetime.utcnow)

    products: Mapped[List[Product]] = relationship(back_populates="shelf")
    images: Mapped[List[ShelfImage]] = relationship(back_populates="shelf")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str] = mapped_column(String(120), default="General")
    price: Mapped[float] = mapped_column(default=0.0)
    shelf_id: Mapped[Optional[int]] = mapped_column(ForeignKey("shelves.id"), default=None)
    shelf_level: Mapped[int] = mapped_column(default=1)     # 1=bottom … 5=top
    x_offset: Mapped[float] = mapped_column(default=0.0)    # offset within shelf
    in_stock: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(insert_default=datetime.utcnow)

    shelf: Mapped[Optional[Shelf]] = relationship(back_populates="products")


class ShelfImage(Base):
    __tablename__ = "shelf_images"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shelf_id: Mapped[int] = mapped_column(ForeignKey("shelves.id"))
    filename: Mapped[str] = mapped_column(String(300))
    analysis_json: Mapped[str] = mapped_column(Text, default="{}")  # YOLO detections
    uploaded_at: Mapped[Optional[datetime]] = mapped_column(insert_default=datetime.utcnow)

    shelf: Mapped[Shelf] = relationship(back_populates="images")
