"""
Local audible alarm for safety incidents.

Uses Windows winsound (built-in, no extra dependencies needed).
On non-Windows systems, falls back silently.
"""

import os
import threading
from typing import Optional


def _beep(freq: int, duration_ms: int, count: int) -> None:
    """Play *count* beeps at *freq* Hz, each lasting *duration_ms* ms."""
    try:
        import winsound
        for i in range(count):
            winsound.Beep(freq, duration_ms)
            if i < count - 1:
                import time
                time.sleep(0.12)
    except (ImportError, RuntimeError):
        # Not on Windows or no audio device — ignore silently.
        pass


def play_alert(severity: str, *, blocking: bool = False) -> None:
    """
    Play an audible alert based on incident severity.

    Severity levels:
      CRITICAL → 3 high-pitched rapid beeps  (emergency — fall detected)
      HIGH     → 2 medium beeps              (PPE violation)
      MEDIUM   → 1 short beep                (idle too long)

    Set env var ENABLE_SOUND_ALERT=false to disable.
    """
    enabled = os.getenv("ENABLE_SOUND_ALERT", "true").strip().lower()
    if enabled not in ("true", "1", "yes"):
        return

    sev = severity.upper()
    if sev == "CRITICAL":
        freq, duration, count = 2400, 300, 3
    elif sev == "HIGH":
        freq, duration, count = 1600, 250, 2
    elif sev == "MEDIUM":
        freq, duration, count = 1000, 200, 1
    else:
        return

    if blocking:
        _beep(freq, duration, count)
    else:
        # Run in a background thread so it doesn't block the main loop.
        t = threading.Thread(target=_beep, args=(freq, duration, count), daemon=True)
        t.start()
