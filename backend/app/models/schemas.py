"""
Pydantic schemas for request/response validation.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# ── Products ──
class ProductCreate(BaseModel):
    name: str
    category: str = "General"
    price: float = 0.0
    shelf_id: Optional[int] = None
    shelf_level: int = 1
    x_offset: float = 0.0
    in_stock: bool = True


class ProductOut(ProductCreate):
    id: int
    class Config:
        from_attributes = True


# ── Shelves ──
class ShelfCreate(BaseModel):
    name: str
    aisle: str
    x: float
    y: float
    width: float = 1.0
    height: float = 2.0
    shape: str = "circle"  # "circle" or "rect"


class ShelfOut(ShelfCreate):
    id: int
    class Config:
        from_attributes = True


# ── BLE reading from ESP32 ──
class BLEReading(BaseModel):
    gateway_id: str                          # e.g. "esp32_A"
    rssi: float                              # dBm
    session_id: str                          # phone's BLE session


# ── IMU packet from phone ──
class IMUData(BaseModel):
    session_id: str
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 0.0
    gyro_alpha: float = 0.0
    gyro_beta: float = 0.0
    gyro_gamma: float = 0.0
    step_count: int = 0
    heading: float = 0.0                     # degrees from North


# ── Position ──
class Position(BaseModel):
    x: float
    y: float
    accuracy: float = Field(default=1.5, description="Estimated error in metres")


# ── Navigation request / response ──
class NavigateRequest(BaseModel):
    session_id: str
    product_ids: list[int] = Field(default_factory=list)
    product_query: Optional[str] = None      # natural-language search


class NavStep(BaseModel):
    x: float
    y: float


class NavigateResponse(BaseModel):
    path: list[NavStep]
    distance: float                          # total metres
    products: list[ProductOut]
    shelf_image_url: Optional[str] = None


# ── Shelf image upload result ──
class ShelfAnalysis(BaseModel):
    shelf_id: int
    detections: list[dict]
    image_url: str
