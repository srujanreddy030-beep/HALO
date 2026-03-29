from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class Detection:
    xyxy: Tuple[int, int, int, int]
    conf: float
    cls: int
    name: str


def load_yolo(model_name_or_path: str):
    from ultralytics import YOLO

    return YOLO(model_name_or_path)


def detect_person(
    frame_bgr: np.ndarray,
    model,
    *,
    conf_thres: float = 0.4,
) -> List[Detection]:
    results = model.predict(frame_bgr, conf=conf_thres, verbose=False)
    if not results:
        return []

    r0 = results[0]
    names = getattr(r0, "names", {}) or {}
    dets: List[Detection] = []

    if r0.boxes is None or len(r0.boxes) == 0:
        return dets

    for b in r0.boxes:
        cls = int(b.cls.item())
        name = str(names.get(cls, cls))
        if name != "person" and cls != 0:
            continue
        conf = float(b.conf.item())
        x1, y1, x2, y2 = [int(v) for v in b.xyxy[0].tolist()]
        dets.append(Detection((x1, y1, x2, y2), conf, cls, "person"))
    return dets


def check_ppe_compliance(
    frame_bgr: np.ndarray,
    person_xyxy: Tuple[int, int, int, int],
    *,
    ppe_model=None,
    helmet_class: str = "helmet",
    vest_class: str = "vest",
    conf_thres: float = 0.35,
) -> Dict[str, Optional[bool]]:
    """
    Returns:
      {"helmet": True/False/None, "vest": True/False/None}

    None means "unknown" (no PPE model provided).
    """
    if ppe_model is None:
        return {"helmet": None, "vest": None}

    x1, y1, x2, y2 = person_xyxy
    h, w = frame_bgr.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w - 1, x2), min(h - 1, y2)
    crop = frame_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        return {"helmet": None, "vest": None}

    results = ppe_model.predict(crop, conf=conf_thres, verbose=False)
    if not results:
        return {"helmet": False, "vest": False}

    r0 = results[0]
    names = getattr(r0, "names", {}) or {}
    helmet = False
    vest = False

    if r0.boxes is not None:
        for b in r0.boxes:
            cls = int(b.cls.item())
            name = str(names.get(cls, cls))
            if name == helmet_class:
                helmet = True
            if name == vest_class:
                vest = True

    return {"helmet": helmet, "vest": vest}

