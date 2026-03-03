"""
Computer Vision Service – YOLO Shelf Detection
───────────────────────────────────────────────
Uses YOLOv8 to detect products on shelf images, draws bounding-box
highlights, and returns detection metadata.
"""
import json
import uuid
from pathlib import Path
from io import BytesIO

import cv2
import numpy as np
from PIL import Image

from ..core.config import YOLO_CONFIDENCE, SHELF_IMG_DIR

# Lazy-load YOLO model to keep startup fast
_model = None


def _get_model():
    global _model
    if _model is None:
        from ultralytics import YOLO  # type: ignore[import-untyped]
        from ..core.config import YOLO_MODEL_PATH
        _model = YOLO(YOLO_MODEL_PATH)
    return _model


def analyse_shelf_image(image_bytes: bytes,
                        shelf_id: int,
                        highlight_label: str | None = None
                        ) -> dict:
    """
    Run YOLO detection on a shelf photo.

    Parameters
    ----------
    image_bytes : raw file bytes (JPEG/PNG)
    shelf_id    : associated shelf record ID
    highlight_label : if given, draw a green box around matches

    Returns
    -------
    {
        "filename": "...",
        "detections": [ {label, confidence, bbox: [x1,y1,x2,y2]} ],
        "highlighted_filename": "..." | None
    }
    """
    # Save original
    SHELF_IMG_DIR.mkdir(parents=True, exist_ok=True)
    uid = uuid.uuid4().hex[:10]
    orig_name = f"shelf_{shelf_id}_{uid}.jpg"
    orig_path = SHELF_IMG_DIR / orig_name
    orig_path.write_bytes(image_bytes)

    # Decode image
    np_img = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
    if img is None:
        return {"filename": orig_name, "detections": [], "highlighted_filename": None}

    model = _get_model()
    results = model.predict(img, conf=YOLO_CONFIDENCE, verbose=False)

    detections = []
    highlighted_filename = None

    if results and len(results) > 0:
        r = results[0]
        for box in r.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls = int(box.cls[0])
            label = model.names.get(cls, str(cls))
            detections.append({
                "label": label,
                "confidence": round(conf, 3),
                "bbox": [round(v, 1) for v in [x1, y1, x2, y2]],
            })

            # Draw highlight if label matches query
            if highlight_label and highlight_label.lower() in label.lower():
                cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)),
                              (0, 255, 0), 4)
                cv2.putText(img, f"{label} {conf:.0%}",
                            (int(x1), int(y1) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        # Save highlighted image
        if highlight_label:
            hl_name = f"shelf_{shelf_id}_{uid}_hl.jpg"
            cv2.imwrite(str(SHELF_IMG_DIR / hl_name), img)
            highlighted_filename = hl_name

    return {
        "filename": orig_name,
        "detections": detections,
        "highlighted_filename": highlighted_filename,
    }


def generate_highlight_overlay(original_path: str,
                               bbox: list[float],
                               label: str) -> str:
    """
    Draw a highlight box on an existing shelf image and return new filename.
    """
    src = Path(original_path)
    if not src.exists():
        return original_path

    img = cv2.imread(str(src))
    x1, y1, x2, y2 = [int(v) for v in bbox]
    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 4)
    cv2.putText(img, label, (x1, y1 - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)

    hl_path = src.parent / (src.stem + "_hl" + src.suffix)
    cv2.imwrite(str(hl_path), img)
    return hl_path.name
