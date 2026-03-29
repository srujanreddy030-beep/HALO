"""
Pose estimation and fall detection using MediaPipe Pose landmarks.

Falls back to bounding-box aspect ratio heuristic if MediaPipe
fails to detect landmarks (e.g., person partially occluded).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np


@dataclass
class PoseResult:
    posture: str  # "standing" | "sitting" | "lying" | "unknown"
    score: float
    method: str = "box"  # "mediapipe" or "box" (fallback)


class PoseEstimator:
    """MediaPipe Pose-based posture estimator with box-heuristic fallback."""

    def __init__(self):
        self._mp_pose = None
        self._pose = None
        try:
            import mediapipe as mp
            # In newer mediapipe versions, solutions might not be attached to root mp
            if hasattr(mp, 'solutions'):
                self._mp_pose = mp.solutions.pose
            else:
                from mediapipe.python.solutions import pose as mp_pose
                self._mp_pose = mp_pose

            self._pose = self._mp_pose.Pose(
                static_image_mode=False,
                model_complexity=0,       # Fastest model (CPU-friendly)
                min_detection_confidence=0.5,
                min_tracking_confidence=0.4,
            )
        except ImportError:
            # MediaPipe not installed — fall back to box heuristic.
            pass

    def close(self) -> None:
        if self._pose is not None:
            self._pose.close()
            self._pose = None

    # ------------------------------------------------------------------
    # MediaPipe-based posture
    # ------------------------------------------------------------------
    def _mediapipe_posture(
        self,
        frame_bgr: np.ndarray,
        person_xyxy: Tuple[int, int, int, int],
    ) -> Optional[PoseResult]:
        """Return PoseResult from MediaPipe landmarks, or None if unavailable."""
        if self._pose is None:
            return None

        x1, y1, x2, y2 = person_xyxy
        h, w = frame_bgr.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        crop = frame_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        results = self._pose.process(rgb)
        if not results.pose_landmarks:
            return None

        lm = results.pose_landmarks.landmark
        PoseLM = self._mp_pose.PoseLandmark

        def _vis(idx) -> bool:
            return lm[idx].visibility > 0.4

        # Key landmarks
        l_shoulder = lm[PoseLM.LEFT_SHOULDER]
        r_shoulder = lm[PoseLM.RIGHT_SHOULDER]
        l_hip = lm[PoseLM.LEFT_HIP]
        r_hip = lm[PoseLM.RIGHT_HIP]

        if not all(_vis(i) for i in [
            PoseLM.LEFT_SHOULDER, PoseLM.RIGHT_SHOULDER,
            PoseLM.LEFT_HIP, PoseLM.RIGHT_HIP,
        ]):
            return None

        # Midpoints
        mid_shoulder_y = (l_shoulder.y + r_shoulder.y) / 2
        mid_hip_y = (l_hip.y + r_hip.y) / 2
        mid_shoulder_x = (l_shoulder.x + r_shoulder.x) / 2
        mid_hip_x = (l_hip.x + r_hip.x) / 2

        # Torso vector angle relative to vertical
        dx = mid_hip_x - mid_shoulder_x
        dy = mid_hip_y - mid_shoulder_y
        torso_angle = abs(math.degrees(math.atan2(dx, dy)))
        # 0° = perfectly upright, 90° = perfectly horizontal

        # Determine posture from torso angle
        if torso_angle > 60:
            return PoseResult("lying", 0.85, method="mediapipe")
        elif torso_angle > 35:
            return PoseResult("sitting", 0.75, method="mediapipe")
        else:
            return PoseResult("standing", 0.80, method="mediapipe")

    # ------------------------------------------------------------------
    # Box-ratio fallback
    # ------------------------------------------------------------------
    @staticmethod
    def _box_posture(person_xyxy: Tuple[int, int, int, int]) -> PoseResult:
        x1, y1, x2, y2 = person_xyxy
        bw = max(1, x2 - x1)
        bh = max(1, y2 - y1)
        aspect = bw / bh

        if aspect > 2.0:
            return PoseResult("lying", 0.65, method="box")
        if aspect > 0.9:
            return PoseResult("sitting", 0.55, method="box")
        return PoseResult("standing", 0.55, method="box")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def infer_posture(
        self,
        frame_bgr: np.ndarray,
        person_xyxy: Tuple[int, int, int, int],
    ) -> PoseResult:
        """Infer posture — tries MediaPipe first, falls back to box aspect ratio."""
        mp_result = self._mediapipe_posture(frame_bgr, person_xyxy)
        if mp_result is not None:
            return mp_result
        return self._box_posture(person_xyxy)


def is_fall_like(
    posture: str,
    person_xyxy: Tuple[int, int, int, int],
) -> bool:
    """
    Determine if the posture indicates a fall.

    Uses both posture label and box geometry as a double-check
    to reduce false positives.
    """
    x1, y1, x2, y2 = person_xyxy
    bw = max(1, x2 - x1)
    bh = max(1, y2 - y1)
    aspect = bw / bh

    # Fall-like when posture is "lying" AND box is wider than tall
    return posture == "lying" and aspect > 1.5
