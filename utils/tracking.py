from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import math
import time


@dataclass
class Track:
    track_id: int
    centroid: Tuple[float, float]
    last_seen_ts: float
    last_move_ts: float
    idle_since_ts: Optional[float] = None


def centroid(xyxy: Tuple[int, int, int, int]) -> Tuple[float, float]:
    x1, y1, x2, y2 = xyxy
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


class CentroidTracker:
    def __init__(
        self,
        *,
        max_match_dist_px: float = 120.0,
        idle_move_thresh_px: float = 50.0,
        forget_after_s: float = 5.0,
    ):
        self._next_id = 1
        self.tracks: Dict[int, Track] = {}
        self.max_match_dist_px = max_match_dist_px
        self.idle_move_thresh_px = idle_move_thresh_px
        self.forget_after_s = forget_after_s

    def _dist(self, a: Tuple[float, float], b: Tuple[float, float]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def update(self, detections_xyxy: List[Tuple[int, int, int, int]]) -> Dict[int, Tuple[int, int, int, int]]:
        now = time.time()

        # Drop stale tracks
        stale = [tid for tid, t in self.tracks.items() if (now - t.last_seen_ts) > self.forget_after_s]
        for tid in stale:
            self.tracks.pop(tid, None)

        unmatched = set(self.tracks.keys())
        assigned: Dict[int, Tuple[int, int, int, int]] = {}

        for box in detections_xyxy:
            c = centroid(box)

            best_id = None
            best_d = float("inf")
            for tid in list(unmatched):
                d = self._dist(c, self.tracks[tid].centroid)
                if d < best_d:
                    best_d = d
                    best_id = tid

            if best_id is not None and best_d <= self.max_match_dist_px:
                t = self.tracks[best_id]
                move_d = self._dist(c, t.centroid)
                t.centroid = c
                t.last_seen_ts = now
                if move_d >= self.idle_move_thresh_px:
                    t.last_move_ts = now
                    t.idle_since_ts = None
                else:
                    if t.idle_since_ts is None:
                        t.idle_since_ts = t.last_move_ts
                assigned[best_id] = box
                unmatched.remove(best_id)
            else:
                tid = self._next_id
                self._next_id += 1
                self.tracks[tid] = Track(
                    track_id=tid,
                    centroid=c,
                    last_seen_ts=now,
                    last_move_ts=now,
                    idle_since_ts=None,
                )
                assigned[tid] = box

        return assigned

    def idle_duration_s(self, track_id: int) -> float:
        t = self.tracks.get(track_id)
        if not t or t.idle_since_ts is None:
            return 0.0
        return max(0.0, time.time() - t.idle_since_ts)

