"""macOS (and generic) webcam via OpenCV. Install with: pip install '.[mac]'

First use on macOS triggers a camera-permission prompt for your terminal app
(Terminal/iTerm/VS Code). Approve it, then restart `robo`. List nothing fancy —
the default webcam is device index 0 (override with ROBO_CAMERA_INDEX).

cv2 capture is blocking, so reads run in a thread executor to keep asyncio free.
"""
from __future__ import annotations

import asyncio
import logging

from robo.config import settings
from robo.vision.base import Camera

log = logging.getLogger("robo.vision.opencv")


class OpenCVCamera(Camera):
    def __init__(self) -> None:
        import cv2  # lazy: only needed where this backend is used

        self._cv2 = cv2
        self._cap = cv2.VideoCapture(settings.camera_index)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.camera_width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.camera_height)
        self._lock = asyncio.Lock()
        if not self._cap.isOpened():
            log.warning(
                "could not open webcam index %d — check camera permissions",
                settings.camera_index,
            )
        else:
            log.info("OpenCVCamera ready (index=%d)", settings.camera_index)

    def _grab(self) -> bytes | None:
        ok, frame = self._cap.read()
        if not ok:
            return None
        ok, buf = self._cv2.imencode(".jpg", frame, [self._cv2.IMWRITE_JPEG_QUALITY, 80])
        return buf.tobytes() if ok else None

    async def read_jpeg(self) -> bytes | None:
        async with self._lock:  # one read at a time on the capture device
            return await asyncio.get_running_loop().run_in_executor(None, self._grab)

    def close(self) -> None:
        try:
            self._cap.release()
        except Exception:  # noqa: BLE001
            pass
