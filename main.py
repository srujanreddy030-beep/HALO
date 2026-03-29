"""
HALO — Hazard Analytics & Live Oversight
Main detection loop: webcam → YOLOv8 → pose estimation → alert pipeline.

Loads settings from .env file (copy .env.example → .env and fill in values).
"""

import argparse
import os
import time
from collections import deque
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

# Load .env before anything else reads env vars
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"))
except ImportError:
    pass  # python-dotenv not installed — rely on system env vars

from utils.alerts import send_email_alert, send_telegram_alert, send_sms_alert
from utils.database import init_db, log_incident
from utils.detection import check_ppe_compliance, detect_person, load_yolo
from utils.pose import PoseEstimator, is_fall_like
from utils.sound_alert import play_alert
from utils.tracking import CentroidTracker


DB_PATH = str(Path(__file__).with_name("worker_safety.db"))
ARTIFACTS_DIR = Path(__file__).with_name("artifacts")
INCIDENTS_DIR = ARTIFACTS_DIR / "incidents"
NORMAL_DIR = ARTIFACTS_DIR / "normal"
LATEST_FRAME_PATH = ARTIFACTS_DIR / "latest_frame.jpg"
STOP_SIGNAL_PATH = ARTIFACTS_DIR / "stop_signal"


def draw_label(frame, xyxy, text: str, color: Tuple[int, int, int]) -> None:
    x1, y1, x2, y2 = xyxy
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    cv2.rectangle(frame, (x1, max(0, y1 - th - 8)), (x1 + tw + 6, y1), color, -1)
    cv2.putText(
        frame,
        text,
        (x1 + 3, y1 - 6),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def save_snapshot(frame_bgr, *, prefix: str) -> str:
    INCIDENTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = INCIDENTS_DIR / f"{prefix}_{ts}.jpg"
    cv2.imwrite(str(path), frame_bgr)
    return str(path)

def save_video_clip(buffer: deque, prefix: str) -> str:
    INCIDENTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = INCIDENTS_DIR / f"{prefix}_{ts}.mp4"
    if not buffer:
        return ""
    h, w, _ = buffer[0].shape
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), 30, (w, h))
    for f in list(buffer):
        writer.write(f)
    writer.release()
    return str(path)

def save_normal_snapshot(frame_bgr, *, prefix: str) -> str:
    NORMAL_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = NORMAL_DIR / f"{prefix}_{ts}.jpg"
    cv2.imwrite(str(path), frame_bgr)
    return str(path)


class Cooldowns:
    def __init__(self):
        self._last: Dict[Tuple[Optional[int], str], float] = {}

    def allow(self, track_id: Optional[int], incident_type: str, *, every_s: float) -> bool:
        now = time.time()
        key = (track_id, incident_type)
        prev = self._last.get(key, 0.0)
        if (now - prev) >= every_s:
            self._last[key] = now
            return True
        return False


def _print_config_status() -> None:
    """Print a startup summary of the alert configuration."""
    from utils.alerts import is_email_configured, is_telegram_configured, is_sms_configured

    print("\n" + "=" * 52)
    print("  HALO — Hazard Analytics & Live Oversight")
    print("=" * 52)

    email_ok = is_email_configured()
    tg_ok = is_telegram_configured()
    sms_ok = is_sms_configured()
    sound_on = os.getenv("ENABLE_SOUND_ALERT", "true").strip().lower() in ("true", "1", "yes")

    print(f"  📧 Email alerts:    {'✅ Configured' if email_ok else '❌ Not configured'}")
    print(f"  📱 Telegram alerts: {'✅ Configured' if tg_ok else '❌ Not configured'}")
    print(f"  💬 SMS alerts:      {'✅ Configured' if sms_ok else '❌ Not configured'}")
    print(f"  🔊 Sound alerts:    {'✅ Enabled' if sound_on else '❌ Disabled'}")

    if not email_ok:
        print("\n  ⚠️  To enable email alerts:")
        print("      1. Copy .env.example → .env")
        print("      2. Fill in EMAIL_USER, EMAIL_PASSWORD, ALERT_RECIPIENT_EMAILS")
    print("=" * 52 + "\n")


def main(headless: bool = False) -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    init_db(DB_PATH)

    # Remove any leftover stop signal from a previous run
    if STOP_SIGNAL_PATH.exists():
        STOP_SIGNAL_PATH.unlink(missing_ok=True)

    _print_config_status()

    # Person model (auto-downloads yolov8n.pt if needed)
    person_model_name = os.getenv("PERSON_MODEL", "yolov8n.pt")
    person_model = load_yolo(person_model_name)

    # Optional PPE model (custom-trained); leave empty to disable PPE detection.
    ppe_model_path = os.getenv("PPE_MODEL", "").strip()
    ppe_model = load_yolo(ppe_model_path) if ppe_model_path else None

    cap = cv2.VideoCapture(int(os.getenv("CAMERA_INDEX", "0")))
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam. Try setting CAMERA_INDEX=1 (or another index).")

    pose = PoseEstimator()
    tracker = CentroidTracker(
        max_match_dist_px=float(os.getenv("TRACK_MATCH_DIST_PX", "140")),
        idle_move_thresh_px=float(os.getenv("IDLE_MOVE_THRESH_PX", "50")),
        forget_after_s=float(os.getenv("TRACK_FORGET_S", "5")),
    )

    idle_threshold_s = float(os.getenv("IDLE_THRESHOLD_S", str(10 * 60)))
    fall_persist_s = float(os.getenv("FALL_PERSIST_S", "3.0"))
    normal_snapshot_every_s = float(os.getenv("NORMAL_SNAPSHOT_EVERY_S", "30"))
    cooldowns = Cooldowns()
    fall_since: Dict[int, float] = {}

    zone_str = os.getenv("RESTRICTED_ZONE_POLYGON", "").strip()
    restricted_polygon = None
    if zone_str:
        try:
            pts = []
            for pt in zone_str.split(";"):
                x, y = pt.split(",")
                pts.append([int(x), int(y)])
            restricted_polygon = np.array(pts, np.int32)
        except Exception as e:
            print(f"⚠️  Error parsing RESTRICTED_ZONE_POLYGON: {e}")
            restricted_polygon = None

    frame_buffer = deque(maxlen=90)

    print("Running." + (" (headless mode)" if headless else " Press 'q' to quit.") + "\n")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.05)
                continue
            
            frame_buffer.append(frame.copy())
            if restricted_polygon is not None:
                cv2.polylines(frame, [restricted_polygon], isClosed=True, color=(0, 0, 255), thickness=2)
                cv2.putText(frame, "RESTRICTED ZONE", tuple(restricted_polygon[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

            dets = detect_person(frame, person_model, conf_thres=float(os.getenv("PERSON_CONF", "0.4")))
            boxes = [d.xyxy for d in dets]
            assigned = tracker.update(boxes)

            for track_id, box in assigned.items():
                ppe = check_ppe_compliance(frame, box, ppe_model=ppe_model)
                pose_res = pose.infer_posture(frame, box)
                idle_s = tracker.idle_duration_s(track_id)

                label_parts = [f"ID:{track_id}", f"{pose_res.posture}"]
                color = (0, 200, 0)

                # 🔴 CRITICAL: fall-like posture
                fall_like_now = is_fall_like(pose_res.posture, box)
                now_ts = time.time()
                if fall_like_now:
                    if track_id not in fall_since:
                        fall_since[track_id] = now_ts
                else:
                    fall_since.pop(track_id, None)

                fall_like_persisted = (
                    fall_like_now
                    and track_id in fall_since
                    and (now_ts - fall_since[track_id]) >= fall_persist_s
                )

                if fall_like_persisted:
                    color = (0, 0, 255)
                    label_parts.append("⚠ FALL!")
                    if cooldowns.allow(track_id, "fall", every_s=30):
                        media_path = save_video_clip(frame_buffer, prefix="fall")
                        ts_str = time.strftime("%Y-%m-%d %H:%M:%S")
                        msg = (
                            f"🔴 CRITICAL: Possible fall/injury detected for "
                            f"Worker #{track_id} at {ts_str}. "
                            f"Posture: {pose_res.posture} (confidence: {pose_res.score:.0%}, "
                            f"method: {pose_res.method}). Immediate attention required!"
                        )
                        # Sound alert (non-blocking)
                        play_alert("CRITICAL")
                        # Telegram
                        send_telegram_alert(msg, image_path=media_path)
                        # SMS
                        send_sms_alert(msg)
                        # Email with severity + track info
                        send_email_alert(
                            subject="Possible fall detected — Worker may be injured",
                            body=msg,
                            image_path=media_path,
                            severity="CRITICAL",
                            track_id=track_id,
                        )
                        # Database
                        log_incident(
                            DB_PATH,
                            track_id=track_id,
                            severity="CRITICAL",
                            incident_type="fall",
                            message=msg,
                            image_path=media_path,
                        )
                        print(f"  🔴 ALERT SENT — Fall detected (Track #{track_id})")
                else:
                    # Periodic normal snapshot for sitting/standing (for demo gallery).
                    if pose_res.posture in ("standing", "sitting"):
                        if cooldowns.allow(track_id, "normal_snapshot", every_s=normal_snapshot_every_s):
                            snap = save_normal_snapshot(frame, prefix=f"normal_{pose_res.posture}_id{track_id}")
                            msg = f"Normal snapshot ({pose_res.posture}) (track {track_id})."
                            log_incident(
                                DB_PATH,
                                track_id=track_id,
                                severity="INFO",
                                incident_type="normal_snapshot",
                                message=msg,
                                image_path=snap,
                            )

                # 🟠 HIGH: PPE missing (only if PPE model enabled)
                if ppe["helmet"] is False or ppe["vest"] is False:
                    color = (0, 140, 255)
                    miss = []
                    if ppe["helmet"] is False:
                        miss.append("helmet")
                    if ppe["vest"] is False:
                        miss.append("vest")
                    label_parts.append("NO_PPE:" + ",".join(miss))
                    if cooldowns.allow(track_id, "ppe", every_s=60):
                        media_path = save_video_clip(frame_buffer, prefix="ppe")
                        ts_str = time.strftime("%Y-%m-%d %H:%M:%S")
                        msg = (
                            f"🟠 HIGH: PPE violation detected for Worker #{track_id} "
                            f"at {ts_str}. Missing: {', '.join(miss)}. "
                            f"Worker must wear proper safety equipment!"
                        )
                        play_alert("HIGH")
                        send_telegram_alert(msg, image_path=media_path)
                        send_sms_alert(msg)
                        send_email_alert(
                            subject=f"PPE violation — missing {', '.join(miss)}",
                            body=msg,
                            image_path=media_path,
                            severity="HIGH",
                            track_id=track_id,
                        )
                        log_incident(
                            DB_PATH,
                            track_id=track_id,
                            severity="HIGH",
                            incident_type="ppe_violation",
                            message=msg,
                            image_path=media_path,
                        )
                        print(f"  🟠 ALERT SENT — PPE violation (Track #{track_id})")

                # 🟡 MEDIUM: idle too long
                if idle_s >= idle_threshold_s:
                    color = (0, 255, 255)
                    label_parts.append(f"IDLE:{int(idle_s)}s")
                    if cooldowns.allow(track_id, "idle", every_s=5 * 60):
                        media_path = save_video_clip(frame_buffer, prefix="idle")
                        ts_str = time.strftime("%Y-%m-%d %H:%M:%S")
                        msg = (
                            f"🟡 MEDIUM: Worker #{track_id} has been idle for "
                            f"{int(idle_s)} seconds at {ts_str}. "
                            f"Worker may need assistance or welfare check."
                        )
                        play_alert("MEDIUM")
                        send_telegram_alert(msg, image_path=media_path)
                        send_email_alert(
                            subject=f"Worker idle for {int(idle_s)}s — welfare check needed",
                            body=msg,
                            image_path=media_path,
                            severity="MEDIUM",
                            track_id=track_id,
                        )
                        log_incident(
                            DB_PATH,
                            track_id=track_id,
                            severity="MEDIUM",
                            incident_type="idle",
                            message=msg,
                            image_path=media_path,
                        )
                        print(f"  🟡 ALERT SENT — Worker idle (Track #{track_id})")

                # 🚫 CRITICAL: Restricted Zone Entry
                if restricted_polygon is not None:
                    # bottom-center of bounding box
                    bc_x = int((box[0] + box[2]) / 2)
                    bc_y = int(box[3])
                    if cv2.pointPolygonTest(restricted_polygon, (bc_x, bc_y), False) >= 0:
                        color = (0, 0, 255)
                        label_parts.append("⚠ ZONE_BREACH!")
                        if cooldowns.allow(track_id, "restricted_zone_entry", every_s=30):
                            media_path = save_video_clip(frame_buffer, prefix="zone")
                            ts_str = time.strftime("%Y-%m-%d %H:%M:%S")
                            msg = (
                                f"🚫 CRITICAL: Worker #{track_id} entered RESTRICTED ZONE "
                                f"at {ts_str}. Immediate attention required!"
                            )
                            play_alert("CRITICAL")
                            send_telegram_alert(msg, image_path=media_path)
                            send_sms_alert(msg)
                            send_email_alert(
                                subject=f"Worker #{track_id} entered restricted danger zone",
                                body=msg,
                                image_path=media_path,
                                severity="CRITICAL",
                                track_id=track_id,
                            )
                            log_incident(
                                DB_PATH, track_id=track_id, severity="CRITICAL",
                                incident_type="restricted_zone_entry", message=msg, image_path=media_path
                            )
                            print(f"  🚫 ALERT SENT — Zone breached (Track #{track_id})")

                draw_label(frame, box, " | ".join(label_parts), color)

            # Write latest frame for the dashboard (best-effort)
            try:
                cv2.imwrite(str(LATEST_FRAME_PATH), frame)
            except Exception:
                pass

            # Check for stop signal from the dashboard
            if STOP_SIGNAL_PATH.exists():
                print("\n  Stop signal received from dashboard. Shutting down...")
                STOP_SIGNAL_PATH.unlink(missing_ok=True)
                break

            if not headless:
                cv2.imshow("HALO — Lone Worker Safety (q to quit)", frame)
                if (cv2.waitKey(1) & 0xFF) == ord("q"):
                    break
            else:
                # Small sleep to avoid maxing out CPU in headless mode
                time.sleep(0.03)

    finally:
        pose.close()
        cap.release()
        if not headless:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HALO detection loop")
    parser.add_argument("--headless", action="store_true", help="Run without GUI window (for dashboard use)")
    args = parser.parse_args()
    main(headless=args.headless)
